"""Task-local bounded worker regressions (amendment 21 / dispatch 62 item 4).

Deterministic, offline, fake-transport only: no network, no Binance, no real
signing. These encode the amendment-21 task-local runtime contract that the
review-1 backend rework must honor:

* each task owns ONE bounded worker that queries ONLY its own legs (no global
  scan) — so one task's slow/blocked reconcile never blocks another's dispatch;
* concurrent Start/recover for the same task yields exactly one worker and one
  attempt reservation (no double POST);
* a confirmed 429 pauses THIS task only, the worker drains its in-flight pair to
  terminal before it exits, and the failure counter is NOT consumed — while a
  sibling task still dispatches freely;
* a confirmed insufficient-funds fact pauses THIS task only — while a sibling
  still dispatches;
* recovery of a pending pair on a FRESH service instance (old worker gone) over
  the SAME SQLite file queries ONLY the saved clientOrderId and never re-POSTs.

No sleep race is used: cross-task/concurrency cases synchronize on
``threading.Event`` / ``Barrier`` / ``thread.join``; single-task cases drive the
worker synchronously through the ``_pump_worker`` test seam.
"""
from __future__ import annotations

import threading
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LEG_REJECTED,
    LEG_UNKNOWN_QUERYING,
    LegDispatch,
    LiveAttemptDispatch,
)


# ---------------------------------------------------------------------------
# Clocks + fakes (self-contained; mirrors test_hedge_review2_regressions)
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self, t0: int = 0):
        self.t = t0

    def mono_us(self) -> int:
        return self.t

    def wall_us(self) -> int:
        return self.t


def _step(svc, task_id, clock, rounds=1):
    """Deterministic offline drive of one task's worker (amendment 21): advance
    the clock, then synchronously pump the task-local worker for ``rounds``
    rounds via the ``_pump_worker`` seam (no thread, no pacing wait)."""
    clock.t += 1_000_000
    svc._pump_worker(task_id, max_rounds=rounds)


def _filters(step="0.1") -> dict:
    return {
        "lot_size": {"min_qty": "0.0001", "max_qty": "9000", "step_size": step},
        "market_lot_size": {"min_qty": "0.0001", "max_qty": "9000", "step_size": step},
        "notional": {"min_notional": "5", "apply_min_to_market": True},
    }


def _ok_snapshot(*, usdt="1000000", step="0.1", est_price="50000") -> D.PreflightSnapshot:
    return D.PreflightSnapshot(
        spot_filters=_filters(step),
        perp_filters=_filters(step),
        balances={"USDT": Decimal(usdt), "BTC": Decimal("100")},
        position_mode=D.POS_MODE_BOTH,
        est_price=Decimal(est_price),
        rate_limit_order=50,
        symbol_tradable=True,
    )


class _FakeProvider:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot

    def get_snapshot(self, coin):
        return self.snapshot


class _RoutingExecutor:
    """Per-task scripted dispatch + a flat query deque. ``dispatch`` records the
    task it served so cross-task isolation is observable."""

    def __init__(self):
        self.scripts: dict[str, list] = {}
        self.queries: list = []
        self.dispatched: list[str] = []
        self.dispatch_calls = 0
        self.query_calls = 0

    def set_script(self, task_id, dispatches):
        self.scripts[task_id] = list(dispatches)

    def dispatch(self, ctx):
        self.dispatch_calls += 1
        self.dispatched.append(ctx.task_id)
        return self.scripts[ctx.task_id].pop(0)

    def query_leg(self, leg_name, coin, client_order_id):
        self.query_calls += 1
        if self.queries:
            return self.queries.pop(0)
        return None


def _leg(state, *, name="spot", order_id=None, status=None, executed="0",
         quote="0", avg=None, rate_limited=False, error_code=None,
         error_category=None, retry=None) -> LegDispatch:
    return LegDispatch(
        leg=name, dispatch_state=state, order_id=order_id, exchange_status=status,
        executed_qty=executed, cumulative_quote=quote, avg_price=avg,
        rate_limited=rate_limited, error_code=error_code,
        error_category=error_category, retry_after_seconds=retry,
    )


def _accepted_pair(task_id="t", *, executed="0.5", status=D.LEG_FILLED) -> LiveAttemptDispatch:
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=status,
                  executed=executed, quote="25000", avg="50000"),
        perp=_leg(LEG_ACCEPTED, name="perp", order_id="p1", status=status,
                  executed=executed, quote="25000", avg="50000"),
        record_payload={"transport": "live", "posted": True},
        rate_limited=False,
        retry_after_seconds=None,
    )


def _svc_with(db_path, executor, provider, clock):
    return HedgeOpenTaskService(
        db_path,
        executor=executor,
        preflight_provider=provider,
        mode="live",
        credentials_present=True,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )


def _live_svc(tmp_path, executor, provider, *, clock=None):
    clock = clock or _Clock()
    svc = _svc_with(str(tmp_path / "ho.sqlite3"), executor, provider, clock)
    svc.set_start_gate(True)
    return svc, clock


def _create(svc, *, direction=D.DIR_FORWARD, single_amount="0.5", target_n=2):
    _, doc = svc.create_task({
        "coin": "BTCUSDT", "direction": direction, "mode": "immediate",
        "single_amount": single_amount, "target_n": target_n,
    })
    return doc


# ---------------------------------------------------------------------------
# 1. A's blocked query_leg must not block B's reserve/submit (per-task isolation)
# ---------------------------------------------------------------------------


def test_1_task_a_query_blocked_does_not_block_task_b(tmp_path):
    """Dispatch item 4: A's reconcile query_leg is gated (blocked). B's worker,
    running independently, must still reserve + submit its own pair. Proves each
    worker queries ONLY its own legs (no global scan), so A's stuck query never
    blocks B's reserve/submit. Synchronized on Events — no sleep race."""
    gate = threading.Event()
    a_querying = threading.Event()

    class _Executor:
        def __init__(self):
            self.scripts = {}
            self.dispatched = []

        def dispatch(self, ctx):
            self.dispatched.append(ctx.task_id)
            return self.scripts[ctx.task_id].pop(0)

        def query_leg(self, leg_name, coin, cid):
            # The FIRST query call signals A reached its reconcile, then blocks.
            # After the test releases the gate, queries resolve FILLED so A's
            # worker drains and exits cleanly (no lingering daemon).
            if not a_querying.is_set():
                a_querying.set()
                gate.wait(5.0)
            return _leg(LEG_ACCEPTED, name=leg_name, order_id="x", status=D.LEG_FILLED,
                        executed="0.5", quote="25000", avg="50000")

    exe = _Executor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    doc_b = _create(svc, target_n=1)
    exe.scripts[doc_a["id"]] = [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )]
    exe.scripts[doc_b["id"]] = [_accepted_pair(doc_b["id"])]

    # Launch A's worker on a real thread. It dispatches its UNKNOWN pair, then on
    # the next round reaches query_leg and blocks on the gate.
    svc.ensure_worker(doc_a["id"])
    # Deterministic barrier: A is now blocked inside its reconcile query.
    assert a_querying.wait(timeout=5.0), "A's worker never reached its reconcile query"

    # B runs in THIS thread via the seam. B resolves on dispatch (never queries),
    # so A's blocked query does not delay B's reserve + submit.
    svc._pump_worker(doc_b["id"], max_rounds=4)
    assert len(svc.store.list_attempts_for_task(doc_b["id"])) == 1
    assert doc_b["id"] in exe.dispatched

    # Release A; its worker drains (FILLED) and exits — no lingering daemon.
    gate.set()
    a_thread = svc._workers.get(doc_a["id"])
    if a_thread is not None:
        a_thread.join(timeout=5.0)
    assert svc._workers.get(doc_a["id"]) is None


# ---------------------------------------------------------------------------
# 2. Concurrent Start/recover -> exactly one worker / one reservation
# ---------------------------------------------------------------------------


def test_2_concurrent_start_yields_one_worker_one_reservation(tmp_path):
    """Dispatch item 4: concurrent Start/recover for the SAME task must yield
    exactly one worker and one attempt reservation (no double POST). Proved with
    a counting executor that holds its single dispatch on a gate while N Start
    threads race past a barrier; the observed peak concurrent dispatches is 1."""
    state = {"in_dispatch": 0, "peak": 0}
    state_lock = threading.Lock()
    hold = threading.Event()

    class _CountingExecutor:
        def dispatch(self, ctx):
            with state_lock:
                state["in_dispatch"] += 1
                state["peak"] = max(state["peak"], state["in_dispatch"])
            hold.wait(5.0)  # hold the single worker in dispatch to observe
            with state_lock:
                state["in_dispatch"] -= 1
            return _accepted_pair(ctx.task_id)

        def query_leg(self, *a, **k):
            return None

    exe = _CountingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)

    # 6 concurrent Start/recover requests for the same task, released at once.
    barrier = threading.Barrier(6)

    def _start():
        barrier.wait()
        svc.ensure_worker(doc["id"])

    threads = [threading.Thread(target=_start) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    # The single worker is blocked in its first dispatch. Release it.
    hold.set()
    worker = svc._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)

    # Never more than one concurrent dispatch / reservation across the race.
    assert state["peak"] == 1
    # The atomic in-flight guard + single worker mean target_n pairs, not N x.
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 2


# ---------------------------------------------------------------------------
# 3. A's confirmed 429 -> paused + counter untouched + worker drains + B dispatches
# ---------------------------------------------------------------------------


def _absent_query(name):
    return _leg(LEG_REJECTED, name=name, error_code="http_404", error_category="absent")


def test_3_task_a_rate_limit_pauses_without_counter_and_b_still_dispatches(tmp_path):
    """Dispatch item 4 + user constraint 1: A's confirmed 429 pauses THIS task
    only (rate_limited), the worker DRAINS its in-flight pair to terminal before
    exiting WITHOUT consuming the failure counter, and B still dispatches."""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    doc_b = _create(svc, target_n=1)
    exe.set_script(doc_a["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, retry=2),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, retry=2),
        record_payload={"transport": "live"}, rate_limited=True, retry_after_seconds=2,
    )])
    exe.set_script(doc_b["id"], [_accepted_pair(doc_b["id"])])

    # Pre-arm the drain queries so A's 429 pair reconciles to confirmed-absent.
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])
    _step(svc, doc_a["id"], clock, rounds=3)  # 429 -> pause -> drain -> exit
    task_a = svc.store.get_task(doc_a["id"])
    assert task_a["status"] == D.STATUS_PAUSED
    assert task_a["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    assert task_a["fail_count"] == 0  # 429 never consumes the counter

    # B is untouched by A's 429 and dispatches its own pair.
    _step(svc, doc_b["id"], clock, rounds=3)
    assert len(svc.store.list_attempts_for_task(doc_b["id"])) == 1
    assert svc.store.get_task(doc_b["id"])["status"] == D.STATUS_DONE


# ---------------------------------------------------------------------------
# 4. A's confirmed insufficient funds -> paused (this task) + B dispatches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code,reason", [
    ("-2019", D.PAUSE_REASON_INSUFFICIENT_MARGIN),
    ("-3041", D.PAUSE_REASON_INSUFFICIENT_BALANCE),
])
def test_4_task_a_insufficient_funds_pauses_and_b_still_dispatches(tmp_path, code, reason):
    """Dispatch item 4: A's confirmed insufficient margin / balance pauses THIS
    task only (precise reason, no threshold wait), while B still dispatches.
    ``-2019`` -> margin; ``-3041`` -> balance."""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    doc_b = _create(svc, target_n=1)
    exe.set_script(doc_a["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code=code,
                  error_category="insufficient_funds"),
        perp=_leg(LEG_REJECTED, name="perp", error_code=code,
                  error_category="insufficient_funds"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    exe.set_script(doc_b["id"], [_accepted_pair(doc_b["id"])])
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc_a["id"], clock, rounds=3)  # insufficient -> pause -> drain -> exit
    task_a = svc.store.get_task(doc_a["id"])
    assert task_a["status"] == D.STATUS_PAUSED
    assert task_a["pause_reason"] == reason

    _step(svc, doc_b["id"], clock, rounds=3)
    assert len(svc.store.list_attempts_for_task(doc_b["id"])) == 1
    assert svc.store.get_task(doc_b["id"])["status"] == D.STATUS_DONE


def test_4b_unconfirmed_minus_2010_stays_fatal_stop_not_pause(tmp_path):
    """User constraint 2: an UNCONFIRMED ``-2010`` (no balance proof in the
    message) is NOT mistaken for a recoverable balance pause — it stays a fatal
    stop.宁可硬停,绝不误判为可恢复的余额暂停。"""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    exe.set_script(doc_a["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="-2010", error_category="fatal"),
        perp=_leg(LEG_REJECTED, name="perp", error_code="-2010", error_category="fatal"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc_a["id"], clock, rounds=2)
    task_a = svc.store.get_task(doc_a["id"])
    assert task_a["status"] == D.STATUS_STOPPED
    assert task_a["stop_reason"] == D.STOP_REASON_EXCHANGE_FATAL


# ---------------------------------------------------------------------------
# 5. Restart recovery on a fresh instance / same DB -> query clientOrderId, no resend
# ---------------------------------------------------------------------------


def test_5_restart_recovery_new_instance_same_db_no_resend(tmp_path):
    """Dispatch item 4 + user constraint 3: a pending pair is recovered by a
    FRESH service/store instance on the SAME SQLite file (old worker gone),
    sharing the same executor counter. Recovery discovery launches a drain worker
    that reconciles ONLY by the saved clientOrderId — zero additional dispatch
    (no second write), and the persisted pair resolves to terminal."""
    db_path = str(tmp_path / "ho.sqlite3")
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())

    # --- old service: dispatch a querying pair, persist clientOrderIds ---
    clock1 = _Clock()
    svc1 = _svc_with(db_path, exe, provider, clock1)
    svc1.set_start_gate(True)
    doc = _create(svc1, target_n=1)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    # round1: dispatch + mark querying (persist clientOrderIds, NO resolve);
    # round2: reconcile query (deque empty -> None) -> stays non-terminal.
    svc1._pump_worker(doc["id"], max_rounds=2)
    posts_before = exe.dispatch_calls
    assert posts_before == 1
    assert svc1.store.list_non_terminal_legs_for_task(doc["id"]), \
        "pair 1 persisted with non-terminal legs + clientOrderIds"
    # Old worker process is gone. No daemon was started (pump is synchronous).
    svc1.stop()
    del svc1

    # --- new service: fresh instance, SAME db file, SAME executor ---
    clock2 = _Clock()
    svc2 = _svc_with(db_path, exe, provider, clock2)
    svc2.set_start_gate(True)
    # Recovery discovery (live start) launches a worker for the RUNNING task with
    # non-terminal legs. Spy on ensure_worker so the assertion does NOT race on
    # whether the launched drain worker has already finished — under load it can
    # drain both legs to terminal and exit within the start() call.
    ensured = []
    _ensure_real = svc2.ensure_worker

    def _spy_ensure(tid):
        ensured.append(tid)
        return _ensure_real(tid)

    svc2.ensure_worker = _spy_ensure
    # Feed FILLED drain queries so the pair resolves.
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000"),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000"),
    ])
    svc2.start()  # final guardian fix: live start() does the ONE recovery handoff
    assert doc["id"] in ensured, "recovery discovery launched a drain worker"
    worker = svc2._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)

    # NO second POST: recovery queried the saved clientOrderIds only.
    assert exe.dispatch_calls == posts_before
    assert exe.query_calls >= 2
    # The persisted pair resolved to terminal; the drain worker exited (no
    # lingering daemon), no resend, no duplicate attempt.
    assert svc2.store.list_non_terminal_legs_for_task(doc["id"]) == []
    assert len(svc2.store.list_attempts_for_task(doc["id"])) == 1
    assert svc2.store.get_task(doc["id"])["status"] == D.STATUS_DONE


# ---------------------------------------------------------------------------
# 6. Final guardian-scanner removal (H-1): live start() = one recovery
#    handoff (no scheduler); live tick() = safe no-op; manual Start = task-local
# ---------------------------------------------------------------------------


def test_6a_live_start_does_one_recovery_handoff_and_does_not_start_scheduler(tmp_path):
    """Final guardian fix (H-1): a live-capable ``service.start()`` performs
    exactly ONE recovery discovery (each durable pending task handed to its own
    bounded worker) and does NOT start the periodic scheduler — so no thread
    scans all task cards forever. Proved with spies on ``_recover_workers`` and
    the scheduler's ``start``, plus a holding executor that keeps the launched
    worker observable. No network, no sleep race."""
    hold = threading.Event()

    class _HoldExecutor(_RoutingExecutor):
        def dispatch(self, ctx):
            self.dispatch_calls += 1
            self.dispatched.append(ctx.task_id)
            hold.wait(5.0)  # keep the recovery-launched worker alive + observable
            return self.scripts[ctx.task_id].pop(0)

    exe = _HoldExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_accepted_pair(doc["id"]), _accepted_pair(doc["id"])])

    calls = {"recover": 0, "scheduler_start": 0}
    _recover_real = svc._recover_workers

    def _spy_recover():
        calls["recover"] += 1
        _recover_real()

    svc._recover_workers = _spy_recover
    _sched_start_real = svc._scheduler.start

    def _spy_sched_start():
        calls["scheduler_start"] += 1
        _sched_start_real()

    svc._scheduler.start = _spy_sched_start

    svc.start()
    # Exactly ONE recovery handoff; the periodic scheduler thread is NOT started.
    assert calls["recover"] == 1
    assert calls["scheduler_start"] == 0
    assert svc._scheduler._thread is None
    # The durable RUNNING task was handed to its own bounded worker (now blocked).
    worker = svc._workers.get(doc["id"])
    assert worker is not None and worker.is_alive(), "recovery launched the worker"

    hold.set()
    if worker is not None:
        worker.join(timeout=5.0)
    assert svc._workers.get(doc["id"]) is None  # worker drained to done and exited


def test_6b_live_tick_is_a_safe_noop_no_scan_no_worker(tmp_path):
    """Final guardian fix (H-1): a live ``tick()`` is a SAFE NO-OP. Repeated
    direct calls never invoke ``_recover_workers()``, never enumerate the task
    list, and never launch a worker — so a periodic tick cannot become a
    guardian scanner even if it is somehow invoked. Spies on ``_recover_workers``,
    the store task enumeration, and ``ensure_worker``; two durable RUNNING tasks
    must stay worker-less across the ticks."""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    doc_b = _create(svc, target_n=1)

    calls = {"recover": 0, "list_tasks": 0, "ensure_worker": 0}
    svc._recover_workers = lambda: calls.__setitem__("recover", calls["recover"] + 1)
    _list_tasks_real = svc._store.list_tasks

    def _spy_list_tasks(status=None):
        calls["list_tasks"] += 1
        return _list_tasks_real(status)

    svc._store.list_tasks = _spy_list_tasks
    _ensure_real = svc.ensure_worker

    def _spy_ensure(task_id):
        calls["ensure_worker"] += 1
        return _ensure_real(task_id)

    svc.ensure_worker = _spy_ensure

    for _ in range(5):
        assert svc.tick() is False  # live tick is a no-op (returns False)

    assert calls["recover"] == 0        # never ran the recovery scanner
    assert calls["list_tasks"] == 0     # never enumerated any task list
    assert calls["ensure_worker"] == 0  # never launched a worker
    # Neither durable RUNNING task gained a worker from the ticks.
    assert svc._workers.get(doc_a["id"]) is None
    assert svc._workers.get(doc_b["id"]) is None


def test_6c_manual_post_start_launches_only_the_named_task(tmp_path):
    """Final guardian fix (H-1): a manual Start/recover launches ONLY the named
    task's worker — it never scans and never launches a sibling task's worker.
    Task A is started and held mid-dispatch (observable); task B (also RUNNING)
    must stay worker-less until its own Start. Cross-task linkage is gone."""
    hold = threading.Event()
    a_dispatched = threading.Event()

    class _HoldAExecutor(_RoutingExecutor):
        def dispatch(self, ctx):
            self.dispatch_calls += 1
            self.dispatched.append(ctx.task_id)
            if not a_dispatched.is_set():
                a_dispatched.set()
                hold.wait(5.0)  # keep A's worker alive + observable
            return self.scripts[ctx.task_id].pop(0)

    exe = _HoldAExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=2)
    doc_b = _create(svc, target_n=2)
    exe.set_script(doc_a["id"], [_accepted_pair(doc_a["id"]), _accepted_pair(doc_a["id"])])
    exe.set_script(doc_b["id"], [_accepted_pair(doc_b["id"]), _accepted_pair(doc_b["id"])])

    # Manual Start of A only.
    svc.post_start(doc_a["id"])
    assert a_dispatched.wait(timeout=5.0), "A's worker launched and reached dispatch"
    # A has a live worker; B does NOT — Start(A) never scanned or launched B.
    assert svc._workers.get(doc_a["id"]) is not None
    assert svc._workers.get(doc_b["id"]) is None

    hold.set()
    worker = svc._workers.get(doc_a["id"])
    if worker is not None:
        worker.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Review-1 r3 regressions (R1–R8): resume clears pause / pause+delete drain /
# deleted-restart drain / rate-limit single-leg / live worker observability /
# dry-run worker_active is None. All deterministic, offline, fake-transport only
# (no network, no sleep race).
# ---------------------------------------------------------------------------


def _rate_limited_unknown_pair():
    """A pair whose both legs come back UNKNOWN and rate-limited (a confirmed
    429): the worker pauses THIS task and the pair is later settled without
    consuming the failure counter."""
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, retry=2),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, retry=2),
        record_payload={"transport": "live"}, rate_limited=True, retry_after_seconds=2,
    )


def _unknown_pair():
    """A pair whose both legs are UNKNOWN (in-flight, not rate-limited)."""
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )


def _rejected_pair():
    """A pair whose both legs are confirmed REJECTED with no orderId (a plain
    confirmed failure — not rate-limited, not fatal, not insufficient)."""
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot"),
        perp=_leg(LEG_REJECTED, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )


def _filled_leg(name):
    return _leg(LEG_ACCEPTED, name=name, order_id=name[0] + "1", status=D.LEG_FILLED,
                executed="0.5", quote="25000", avg="50000")


def _attempt_id(svc, task_id, idx=0) -> int:
    return svc.store.list_attempts_for_task(task_id)[idx]["id"]


# R1 — 429 resume: pause_reason cleared; the 429 pair settles without consuming
# the failure counter (per-attempt fact, not the sticky task pause_reason); the
# NEXT pair FILLED counts as accepted_pair and bumps accepted/success.
def test_r1_rate_limit_resume_next_pair_counts_and_clears_pause(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_rate_limited_unknown_pair(), _accepted_pair(doc["id"])])
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # pair1 429 -> pause (rate_limited)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED

    # Manual resume: re-entering RUNNING clears the sticky pause_reason (P1-1).
    svc.store.set_task_status(doc["id"], D.STATUS_RUNNING, svc._wall_us())
    resumed = svc.store.get_task(doc["id"])
    assert resumed["status"] == D.STATUS_RUNNING
    assert resumed["pause_reason"] is None

    # The worker drains pair1 by its OWN per-attempt rate-limited fact (the
    # task-level pause_reason is already cleared) -> no failure counter; then
    # dispatches pair2 FILLED -> accepted_pair + counts.
    _step(svc, doc["id"], clock, rounds=3)
    task = svc.store.get_task(doc["id"])
    assert task["fail_count"] == 0            # 429 pair never consumed the counter
    assert task["accepted_pair_count"] == 1   # pair2 counted
    assert task["success_count"] == 1
    assert task["pause_reason"] is None       # not sticky after resume
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 2
    assert any(a["pair_outcome"] == D.PAIR_ACCEPTED for a in attempts)
    rl = [a for a in attempts if a.get("rate_limited")]
    assert rl and rl[0]["pair_outcome"] == D.PAIR_CONFIRMED_FAILED


# R2 — after a 429 resume, three subsequent CONFIRMED (non-rate-limited) failures
# still trip the consecutive-failure threshold pause.
def test_r2_rate_limit_resume_then_three_confirmed_fails_triggers_threshold(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=10)
    exe.set_script(doc["id"], [
        _rate_limited_unknown_pair(), _rejected_pair(), _rejected_pair(), _rejected_pair(),
    ])
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # pair1 429 -> pause
    assert svc.store.get_task(doc["id"])["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    svc.store.set_task_status(doc["id"], D.STATUS_RUNNING, svc._wall_us())  # resume

    _step(svc, doc["id"], clock, rounds=12)  # pair1 drain (no counter) + 3 fails
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE
    assert task["fail_count"] == 3
    assert task["consecutive_submission_failures"] == 3


# R3 — manual pause does NOT interrupt the worker: it keeps draining its own
# in-flight legs to terminal, settles the pair, and opens NO new pair.
def test_r3_pause_drains_inflight_to_terminal_and_settles_no_new_pair(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_unknown_pair(), _accepted_pair(doc["id"])])
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # dispatch pair1 UNKNOWN -> in-flight
    scheduled_before = svc.store.get_task(doc["id"])["scheduled_attempt_count"]
    assert scheduled_before == 1
    svc.post_pause(doc["id"])  # pause; worker NOT interrupted
    assert svc.store.get_task(doc["id"])["status"] == D.STATUS_PAUSED

    _step(svc, doc["id"], clock, rounds=3)  # worker drains, settles, exits
    assert exe.query_calls >= 2
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] for l in legs)
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1                 # pair2 never dispatched (paused)
    assert attempts[0]["pair_outcome"] is not None
    assert svc.store.get_task(doc["id"])["scheduled_attempt_count"] == scheduled_before


# R4 — manual delete is isomorphic to pause: the worker drains its own in-flight
# legs to terminal and settles, opening no new pair; DELETED stays sticky.
def test_r4_delete_drains_inflight_to_terminal_and_settles_no_new_pair(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_unknown_pair(), _accepted_pair(doc["id"])])
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # dispatch pair1 UNKNOWN -> in-flight
    scheduled_before = svc.store.get_task(doc["id"])["scheduled_attempt_count"]
    svc.post_delete(doc["id"])  # delete; worker NOT interrupted
    assert svc.store.get_task(doc["id"])["status"] == D.STATUS_DELETED

    _step(svc, doc["id"], clock, rounds=3)  # worker drains, settles, exits
    assert exe.query_calls >= 2
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] for l in legs)
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1
    assert attempts[0]["pair_outcome"] is not None
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DELETED  # sticky
    assert task["scheduled_attempt_count"] == scheduled_before


# R5 — a DELETED card left with non-terminal legs is drained to terminal by the
# ONE startup recovery handoff on a fresh instance (STATUS_DELETED now in the
# drain-only fallback). No resident scanner, no resend.
def test_r5_deleted_card_nonterminal_legs_recovered_on_restart(tmp_path):
    db_path = str(tmp_path / "ho.sqlite3")
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())

    clock1 = _Clock()
    svc1 = _svc_with(db_path, exe, provider, clock1)
    svc1.set_start_gate(True)
    doc = _create(svc1, target_n=2)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc1._pump_worker(doc["id"], max_rounds=1)  # dispatch UNKNOWN pair, in-flight
    svc1.store.set_task_status(doc["id"], D.STATUS_DELETED, clock1.wall_us())
    assert svc1.store.list_non_terminal_legs_for_task(doc["id"]), "non-terminal legs"
    svc1.stop()
    del svc1

    clock2 = _Clock()
    svc2 = _svc_with(db_path, exe, provider, clock2)
    svc2.set_start_gate(True)
    # Spy on ensure_worker: the assertion must not race on whether the launched
    # drain worker has already finished (it can drain both legs and exit within
    # start() under load). STATUS_DELETED is in the drain-only fallback.
    ensured = []
    _ensure_real = svc2.ensure_worker

    def _spy_ensure(tid):
        ensured.append(tid)
        return _ensure_real(tid)

    svc2.ensure_worker = _spy_ensure
    exe.queries.extend([_filled_leg("spot"), _filled_leg("perp")])
    svc2.start()  # ONE recovery handoff; DELETED now in drain-only fallback
    assert doc["id"] in ensured, "recovery launched a drain worker for the DELETED card"
    worker = svc2._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)
    assert exe.dispatch_calls == 1           # only the original dispatch, no resend
    assert exe.query_calls >= 2
    assert svc2.store.list_non_terminal_legs_for_task(doc["id"]) == []
    legs = svc2.store.list_legs_for_attempt(_attempt_id(svc2, doc["id"]))
    assert all(l["terminal"] for l in legs)
    assert svc2.store.get_task(doc["id"])["status"] == D.STATUS_DELETED  # sticky


# R6 — a 429 on one leg + the other leg FILLED -> single_leg outcome with the
# advisory leg_exposure recorded, and the failure counter untouched.
def test_r6_rate_limit_one_leg_other_filled_single_leg_exposure(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_rate_limited_unknown_pair()])
    # drain: spot -> FILLED (orderId), perp -> absent (no orderId) => single_leg
    exe.queries.extend([_filled_leg("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=3)  # 429 -> pause -> drain single_leg -> exit
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    assert task["fail_count"] == 0          # rate-limited -> no counter
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1
    assert attempts[0]["pair_outcome"] == D.PAIR_SINGLE_LEG
    assert task["leg_exposure"] is not None
    assert task["leg_exposure"]["leg"] == "spot"


# R7 — live worker_active tri-state + last_worker_exit_reason: preflight-
# incomplete exits the worker (task stays RUNNING) with a stable reason; while a
# worker holds the executor worker_active is True; a manual Start clears the
# reason on re-entering RUNNING.
def test_r7_live_worker_active_tri_state_and_exit_reason(tmp_path):
    # --- sub A: preflight incomplete -> worker exits, reason recorded ---
    exe_a = _RoutingExecutor()
    svc_a = _svc_with(str(tmp_path / "r7a.sqlite3"), exe_a, _FakeProvider(None), _Clock())
    svc_a.set_start_gate(True)  # None snapshot -> preflight incomplete
    doc_a = _create(svc_a, target_n=1)
    svc_a.post_start(doc_a["id"])  # RUNNING + real worker
    wa = svc_a._workers.get(doc_a["id"])
    if wa is not None:
        wa.join(timeout=5.0)
    task_a = svc_a.store.get_task(doc_a["id"])
    assert svc_a._worker_active_for(doc_a["id"]) is False
    assert task_a["last_worker_exit_reason"] == D.WORKER_EXIT_PREFLIGHT_INCOMPLETE
    assert task_a["status"] == D.STATUS_RUNNING  # preflight incomplete retries

    # --- sub B: while a live worker holds the executor, worker_active is True ---
    hold = threading.Event()
    reached = threading.Event()

    class _HoldDispatch(_RoutingExecutor):
        def dispatch(self, ctx):
            self.dispatch_calls += 1
            self.dispatched.append(ctx.task_id)
            if not reached.is_set():
                reached.set()
                hold.wait(5.0)  # keep the worker alive + holding the executor
            return self.scripts[ctx.task_id].pop(0)

    exe_b = _HoldDispatch()
    svc_b = _svc_with(str(tmp_path / "r7b.sqlite3"), exe_b, _FakeProvider(_ok_snapshot()), _Clock())
    svc_b.set_start_gate(True)
    doc_b = _create(svc_b, target_n=1)
    exe_b.set_script(doc_b["id"], [_accepted_pair(doc_b["id"])])
    svc_b.post_start(doc_b["id"])
    assert reached.wait(timeout=5.0), "worker launched and reached dispatch"
    assert svc_b._worker_active_for(doc_b["id"]) is True
    hold.set()
    wb = svc_b._workers.get(doc_b["id"])
    if wb is not None:
        wb.join(timeout=5.0)
    assert svc_b._worker_active_for(doc_b["id"]) is False

    # --- sub C: a manual Start clears the exit reason on re-entering RUNNING ---
    _, start_doc = svc_a.post_start(doc_a["id"])
    assert start_doc["last_worker_exit_reason"] is None
    wa2 = svc_a._workers.get(doc_a["id"])
    if wa2 is not None:
        wa2.join(timeout=5.0)


# R8 — in dry-run (record / disabled) the worker concept does not apply, so
# worker_active is None — never the misleading False.
def test_r8_dry_run_worker_active_is_none_not_false(tmp_path):
    from backend.hedge_open_tasks.executor import RecordTransportExecutor
    svc = HedgeOpenTaskService(
        str(tmp_path / "dry.sqlite3"),
        executor=RecordTransportExecutor(),
        preflight_provider=_FakeProvider(None),
        mode="disabled",
        credentials_present=False,
    )
    _, doc = svc.create_task({
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": "immediate",
        "single_amount": "0.5", "target_n": 1,
    })
    assert doc["worker_active"] is None
    assert "last_worker_exit_reason" in doc
    svc.stop()
