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

import dataclasses
import json
import threading
import time
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.hedge_open_tasks.wire_constraints import validate_order_params
from backend.services.hedge_open_live_client import HedgeHttpResponse
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LEG_REJECTED,
    LEG_UNKNOWN_QUERYING,
    LegDispatch,
    LiveAttemptDispatch,
    LiveHedgeExecutor,
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
        self.um_qty = None

    def get_snapshot(
        self, coin, direction, task_type="open", position_side_mode=None,
    ):
        return self.snapshot

    def cached_um_position_qty(self, coin):
        return self.um_qty


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

    def query_spot_free(self, asset):
        return Decimal("1000000")

    def universal_transfer(self, type_, asset, amount):  # pragma: no cover - ample balance
        raise AssertionError("unexpected transfer")

    def dispatch(self, ctx):
        self.dispatch_calls += 1
        self.dispatched.append(ctx.task_id)
        return self.scripts[ctx.task_id].pop(0)

    def query_leg(self, leg_name, coin, client_order_id, endpoint):
        self.query_calls += 1
        if self.queries:
            return self.queries.pop(0)
        return None


def _wire_resp(http_status, body=None, transport_error=None) -> HedgeHttpResponse:
    """A ``HedgeHttpResponse`` whose ``raw_body`` mirrors the real wire text (JSON),
    so the persisted raw ``body`` column is non-empty and retrievable."""
    raw_body = json.dumps(body) if isinstance(body, (dict, list)) else (body or "")
    return HedgeHttpResponse(http_status, body, raw_body, transport_error, None)


class _LiveWireClient:
    """A minimal real-wire fake: scripts per-leg POST + GET ``HedgeHttpResponse``
    objects the way the real PAPI client returns them, so
    :class:`LiveHedgeExecutor`.dispatch drives the genuine ``_send_one_leg`` path
    (POST classify, the UNKNOWN immediate best-effort query, and the UM inline
    confirm). Used where :class:`_RoutingExecutor` — which fakes ``dispatch``
    wholesale — cannot exercise the in-executor query."""

    def __init__(self, *, spot_post, perp_post, spot_query, perp_query):
        self._spot_post = spot_post
        self._perp_post = perp_post
        self._spot_query = spot_query
        self._perp_query = perp_query
        self.credentials_present = True

    def post_margin_order(self, params, *, timestamp_ms, recv_window_ms=None):
        if validate_order_params(params):
            return _wire_resp(400, {"code": -4015, "msg": "Illegal characters in newClientOrderId."})
        return self._spot_post

    def post_um_order(self, params, *, timestamp_ms, recv_window_ms=None):
        if validate_order_params(params):
            return _wire_resp(400, {"code": -4015, "msg": "Illegal characters in newClientOrderId."})
        return self._perp_post

    def query_margin_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        return self._spot_query

    def query_um_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        return self._perp_query

    def set_leverage(self, symbol, leverage, *, timestamp_ms, recv_window_ms=None):
        # 开单前设置杠杆（THE -2027 方案 B）：wire fake 模拟成功（200 + leverage 字段）。
        return _wire_resp(200, {"symbol": symbol, "leverage": leverage})


def _leg(state, *, name="spot", order_id=None, status=None, executed="0",
         quote="0", avg=None, rate_limited=False, error_code=None,
         error_category=None, retry=None, raw=None) -> LegDispatch:
    return LegDispatch(
        leg=name, dispatch_state=state, order_id=order_id, exchange_status=status,
        executed_qty=executed, cumulative_quote=quote, avg_price=avg,
        rate_limited=rate_limited, error_code=error_code,
        error_category=error_category, retry_after_seconds=retry,
        raw_response=raw,
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

        def query_leg(self, leg_name, coin, cid, endpoint):
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

        def query_leg(self, leg_name, coin, cid, endpoint):
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
# A-9 (ADR-003 acceptance 5): the cadence drop must not raise order frequency
# ---------------------------------------------------------------------------


def test_a9_cadence_drop_does_not_raise_order_frequency(tmp_path):
    """Per-task serial dispatch (A-9: one pair reaches terminal before the next
    is dispatched) lives in _worker_round, which _pump_worker drives with NO
    pacing wait — so the 1s -> 100ms cadence change is structurally invisible to
    order frequency. A target_n=3 task whose every dispatch resolves terminal
    must yield exactly 3 dispatches and 3 attempts, one per pair."""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=3)
    exe.set_script(doc["id"], [_accepted_pair(doc["id"]) for _ in range(3)])
    svc._pump_worker(doc["id"], max_rounds=12)
    assert exe.dispatch_calls == 3
    assert len(svc.store.list_attempts_for_task(doc["id"])) == 3
    assert svc.store.get_task(doc["id"])["scheduled_attempt_count"] == 3


# ---------------------------------------------------------------------------
# 3. A's confirmed 429 -> paused + counter untouched + worker drains + B dispatches
# ---------------------------------------------------------------------------


def _absent_query(name):
    return _leg(LEG_REJECTED, name=name, error_code="http_404", error_category="absent")


def _retry_cap_queries(exe, *, final, already=0, cap=D.LEG_QUERY_MAX_RETRIES):
    """F1 辅助：把每条腿已查询 ``already`` 次后的共享查询队列，推进到第 ``cap``
    次（收口）查询恰好消费 ``final``（两个 verdict）。queries 是 spot/perp 交替
    消费的共享 deque，所以每轮占位需要 2 个 None；调用方随后 pump ``cap - already``
    轮，使两条腿的第 ``cap`` 次查询同时拿到 ``final`` 并各自按最后一次结果分流
    （404 / -2013 -> absent 终态；inconclusive -> 人工暂停）。"""
    exe.queries.extend([None] * (2 * (cap - 1 - already)))
    exe.queries.extend(final)


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


def test_4c_collateral_cap_51169_pauses_with_frozen_message(tmp_path):
    """T2 (stage 2026-07-hedge-order-truth-v1): a 51169 platform collateral-cap
    rejection on the margin (spot) leg classifies to ``collateral_cap`` — its OWN
    category, never ``insufficient_funds`` — and pauses THIS task with the frozen
    ``collateral_cap_full`` reason + verbatim asset-specific message. The attempt
    row carries the truthful diagnosis, not NULL (10-design §2(e))."""
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=1)
    exe.set_script(doc_a["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP),
        perp=_leg(LEG_REJECTED, name="perp", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc_a["id"], clock, rounds=3)  # collateral_cap -> pause -> drain -> exit
    task_a = svc.store.get_task(doc_a["id"])
    assert task_a["status"] == D.STATUS_PAUSED
    assert task_a["pause_reason"] == D.PAUSE_REASON_COLLATERAL_CAP_FULL
    # 10-design §2(d): the operator message is FROZEN verbatim, {asset}=BTC, and
    # is NOT the insufficient_margin ("保证金不足") wording.
    assert task_a["pause_reason_zh"] == D.collateral_cap_pause_reason_zh("BTC")
    # 10-design §2(e): the attempt row rolls the leg diagnosis up — collateral_cap,
    # not NULL.
    attempts = svc.store.list_attempts_for_task(doc_a["id"])
    assert attempts and attempts[0]["error_category"] == D.ERROR_CATEGORY_COLLATERAL_CAP
    assert attempts[0]["error_code"] == "51169"


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


def test_4d_live_single_leg_exposure_timestamp_is_settlement_wall_clock(tmp_path):
    """T5 acceptance (10-design §4(b) / 00-task.md T5): on the LIVE dispatch path
    (``service._dispatch_to_outcome``), a single-leg exposure's timestamp is the
    settlement wall clock — NOT the 1970 epoch a forgotten ``0`` rendered. This
    exercises the live path the bug hid behind; testing only ``executor.py`` does
    not satisfy T5 (that path already passed ``ctx.ts_us``)."""
    exe = _RoutingExecutor()
    base = 1_784_447_999_000_000  # one step (+1_000_000) lands on a 2026 wall clock
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()), clock=_Clock(base))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
                  executed="0.5", quote="25000", avg="50000"),
        perp=_leg(LEG_REJECTED, name="perp", order_id=None),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch -> single_leg exposure
    settled_ts = base + 1_000_000
    task = svc.store.get_task(doc["id"])
    assert task["leg_exposure"] is not None
    assert task["leg_exposure"]["ts"] == D.us_to_iso(settled_ts)
    assert task["leg_exposure"]["ts"] != "1970-01-01T00:00:00.000000Z"


# F2 (review-2): a discarded settlement exception silently stalls the task. The
# bare ``except Exception: pass`` at both settlement call sites used to swallow
# ANY failure from finalize_attempt — the T5 ``ts_us <= 0`` backstop, a DB error,
# a future rollup bug — leaving pair_outcome NULL, which is precisely
# prepare_attempt's in-flight guard. With an injected zero clock the T5 backstop
# fires on a terminal single-leg attempt; the exception must be recorded (not
# swallowed), the worker must survive, and the attempt must stay unsettled.


def test_drain_settlement_failure_is_recorded_not_swallowed(tmp_path):
    """F2 drain site (``_reconcile_own_legs`` -> ``finalize_attempt``): a real
    service settlement path driven with an injected zero clock. A single-leg
    pair dispatched with one UNKNOWN leg is drained to a FILLED accepted spot +
    REJECTED perp; finalize_attempt then raises the T5 ``ts_us <= 0`` backstop.
    The exception must not escape (worker continues), an operator-visible event
    must be recorded naming the failure, and the attempt must stay unsettled."""
    exe = _RoutingExecutor()
    svc, _clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()), clock=_Clock(0))
    doc = _create(svc, target_n=1)
    # An UNKNOWN pair (has_querying -> legs marked for drain; the dispatch path
    # does NOT compute exposure, so the zero clock does not raise here).
    exe.set_script(doc["id"], [_unknown_pair()])
    # F1 计数机制：absent 只在第 LEG_QUERY_MAX_RETRIES 次查询时确认终态。占位到
    # 上限前一步，第 10 次查询 spot -> FILLED accepted、perp -> absent REJECTED，
    # 即 single-leg 终态 -> finalize(ts_us=0) 抛 T5（wall clock 保持 0）。
    _retry_cap_queries(exe, final=[_filled_leg("spot"), _absent_query("perp")])

    svc._pump_worker(doc["id"], max_rounds=1)  # round 1: dispatch -> in-flight
    # The wall clock stays at zero (that is what trips finalize_attempt's
    # ts_us<=0 backstop below); no dispatched_at_us anchor is involved — the
    # retry counter alone drives the absent confirmation at the cap.
    # rounds 2..11: 9 轮 None 占位 + 第 10 轮终态收口 -> finalize raises.
    svc._pump_worker(doc["id"], max_rounds=D.LEG_QUERY_MAX_RETRIES)

    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["pair_outcome"] is None  # still unsettled — no fabrication
    # Both settlement sites fire on this round: the drain raise leaves a crash-gap
    # that the crash-gap loop then hits, so BOTH must record — fixing only one
    # site would leave the count at 1.
    events = svc.store.list_task_event_logs(20, kinds=("settlement_failed",))
    assert len(events) >= 2
    payload = json.loads(events[0]["payload"])
    assert payload["attempt_id"] == attempt["id"]
    assert "ts_us" in payload["error"]  # names the T5 timestamp backstop
    # No credentials / headers / tokens / request body leak into the event.
    assert set(payload) <= {"attempt_id", "error_type", "error"}


def test_crash_gap_settlement_failure_is_recorded(tmp_path):
    """F2 crash-gap site (``_recover_crash_gaps`` -> ``finalize_attempt``): the
    second bare except, on the loop meant to unstick exactly this state. A
    crash-gap attempt (both legs terminal, pair_outcome NULL) that is also
    single-leg raises the T5 backstop under a zero clock; that exception too must
    be recorded, not swallowed. Constructs the gap directly (the state a crash
    between leg-terminalization and pair settlement leaves), then drives one
    worker round through the real recovery path — isolating the crash-gap site
    from the drain site above."""
    exe = _RoutingExecutor()
    svc, _clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()), clock=_Clock(0))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc._pump_worker(doc["id"], max_rounds=1)  # dispatch UNKNOWN pair, in-flight
    # Simulate the crash gap: close both legs to terminal WITHOUT settling the
    # pair (one accepted, one rejected -> single-leg), as a crash would leave it.
    attempt_id = _attempt_id(svc, doc["id"])
    legs = svc.store.list_legs_for_attempt(attempt_id)
    spot = next(l for l in legs if l["leg"] == "spot")
    perp = next(l for l in legs if l["leg"] == "perp")
    svc.store.resolve_leg_from_query(
        spot["id"], exchange_status=D.LEG_FILLED, order_id="s1",
        base_qty="0.5", quote_amt="25000", fee_amount=None, fee_asset=None,
        now_us=0, terminal=True,
    )
    svc.store.resolve_leg_from_query(
        perp["id"], exchange_status=D.LEG_REJECTED, order_id=None,
        base_qty="0", quote_amt="0", fee_amount=None, fee_asset=None,
        now_us=0, terminal=True,
    )
    assert svc.store.get_attempt(attempt_id)["pair_outcome"] is None  # crash-gap

    # Recovery round: the crash-gap loop finalizes -> build_leg_exposure(0) raises.
    # Recorded, not swallowed; the worker survives.
    svc._pump_worker(doc["id"], max_rounds=1)

    events = svc.store.list_task_event_logs(20, kinds=("settlement_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["attempt_id"] == attempt_id
    assert "ts_us" in payload["error"]
    assert svc.store.get_attempt(attempt_id)["pair_outcome"] is None  # unsettled


# task1d (review-2 audit): five post-POST sites discarded a failed self._store.*
# state write, leaving the system believing something false about an order or a
# task with nothing operator-visible. Each now records a ``state_write_failed``
# task event (carrying the operation name + exception, no credentials) and keeps
# the worker alive; nothing is fabricated and the write POST is never resent. One
# deterministic fault-injection test per site drives the real service path with
# the named store call forced to raise.


def test_s1_resolve_leg_write_failure_records_and_preserves_raw(tmp_path):
    """S1 (``_reconcile_own_legs`` -> ``resolve_leg_from_query``): the old
    ``except Exception: continue`` discarded the leg write AND skipped the raw
    capture right after it — losing the exchange's own query words. Force the leg
    write to raise; the failure is recorded (state_write_failed), the raw response
    is STILL captured (R2), the worker continues, and the leg stays unsettled."""
    exe = _RoutingExecutor()
    svc, _clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()), clock=_Clock(0))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    # A terminal query verdict CARRYING a raw response, so the drain reaches
    # resolve_leg_from_query and the raw capture has something to persist.
    raw = {"http_status": 200, "transport_error": None, "code": None,
           "msg": "ok", "body": "{\"status\":\"FILLED\"}"}
    exe.queries.extend([_leg(LEG_ACCEPTED, name="spot", order_id="s1",
                             status=D.LEG_FILLED, executed="0.5", quote="25000",
                             avg="50000", raw=raw)])

    def _boom(*_a, **_k):
        raise RuntimeError("boom-resolve_leg_from_query")
    svc.store.resolve_leg_from_query = _boom

    svc._pump_worker(doc["id"], max_rounds=1)  # dispatch UNKNOWN pair
    svc._pump_worker(doc["id"], max_rounds=1)  # drain -> resolve_leg_from_query raises

    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["pair_outcome"] is None  # leg not recorded terminal -> unsettled
    events = svc.store.list_task_event_logs(20, kinds=("state_write_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["operation"] == "resolve_leg_from_query"
    assert "boom-resolve_leg_from_query" in payload["error"]
    assert set(payload) <= {"attempt_id", "operation", "error_type", "error"}
    # R2: the raw response was STILL captured despite the leg write failing.
    rows = svc.store.list_raw_responses_for_attempt(attempt["id"])
    assert any(r["source"] == "order_query" for r in rows)


def test_s2_rate_limit_stamp_failure_settles_without_consuming_counter(tmp_path):
    """S2/R3 (``_dispatch_live`` -> ``mark_attempt_rate_limited``): if the
    per-attempt rate-limit stamp fails at dispatch, a later reconcile used to
    settle the 429 pair as an ordinary failure and consume the counter the design
    exempts. Force the stamp to fail; the failure is recorded, and settlement
    retries the stamp before deciding — the pair settles WITHOUT the counter and
    the worker continues."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, retry=2),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, retry=2),
        record_payload={"transport": "live"}, rate_limited=True, retry_after_seconds=2,
    )])
    # F1 计数机制：404 在第 LEG_QUERY_MAX_RETRIES 次查询才确认 absent（原为推进
    # 时钟过容忍窗口）。占位到上限前一步，第 10 次查询 404 -> settle。
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])

    def _boom(*_a, **_k):
        raise RuntimeError("boom-mark_attempt_rate_limited")
    svc.store.mark_attempt_rate_limited = _boom

    _step(svc, doc["id"], clock, rounds=1)  # 429 dispatch -> pause (rate_limited)
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)  # drain (at cap) -> settle

    task = svc.store.get_task(doc["id"])
    assert task["fail_count"] == 0  # R3: 429 pair never consumed the counter
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["pair_outcome"] is not None  # settled (recovered), not stalled
    events = svc.store.list_task_event_logs(20, kinds=("state_write_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["operation"] == "mark_attempt_rate_limited"
    assert set(payload) <= {"attempt_id", "operation", "error_type", "error"}


def test_s3_pause_class_resolve_attempt_failure_is_recorded(tmp_path):
    """S3 (``_dispatch_live`` -> pause-class ``resolve_attempt``): orders already
    sent and both legs terminal with a confirmed collateral-cap fact; a discarded
    resolve_attempt leaves pair_outcome NULL and the in-flight guard stalls the
    task. Force resolve_attempt to raise; the failure is recorded, the pause still
    takes effect, and the pair stays unsettled (not fabricated)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    raw = {"http_status": 400, "transport_error": None,
           "code": "51169", "msg": "cap", "body": "{}"}
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        perp=_leg(LEG_REJECTED, name="perp", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])

    def _boom(*_a, **_k):
        raise RuntimeError("boom-resolve_attempt")
    svc.store.resolve_attempt = _boom

    _step(svc, doc["id"], clock, rounds=1)  # dispatch -> S3 resolve raises

    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED  # the pause still took effect
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["pair_outcome"] is None  # resolve failed -> not fabricated
    events = svc.store.list_task_event_logs(20, kinds=("state_write_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["operation"] == "resolve_attempt"
    assert set(payload) <= {"attempt_id", "operation", "error_type", "error"}


def test_s4_normal_resolve_attempt_failure_is_recorded(tmp_path):
    """S4 (``_dispatch_live`` -> normal ``resolve_attempt``): the main path — a
    real order placed (both legs accepted) and its conclusion never persisted.
    Force resolve_attempt to raise; the failure is recorded, the worker continues,
    and the pair stays unsettled (its conclusion is not fabricated)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_accepted_pair(doc["id"])])

    def _boom(*_a, **_k):
        raise RuntimeError("boom-resolve_attempt")
    svc.store.resolve_attempt = _boom

    _step(svc, doc["id"], clock, rounds=1)  # dispatch -> S4 resolve raises

    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["pair_outcome"] is None  # conclusion not fabricated
    events = svc.store.list_task_event_logs(20, kinds=("state_write_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["operation"] == "resolve_attempt"
    assert set(payload) <= {"attempt_id", "operation", "error_type", "error"}


def test_s5_mark_leg_querying_failure_is_recorded(tmp_path):
    """S5 (``_mark_legs_querying`` -> ``mark_leg_querying``): a leg needing drain
    was never marked, so an in-flight order would never be reconciled by client
    ID. Force mark_leg_querying to raise; the failure is recorded, the worker
    continues, and the leg is not fabricated into a querying state (it stays
    PREPARED)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])

    def _boom(*_a, **_k):
        raise RuntimeError("boom-mark_leg_querying")
    svc.store.mark_leg_querying = _boom

    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> mark_legs_querying

    events = svc.store.list_task_event_logs(20, kinds=("state_write_failed",))
    assert len(events) >= 1
    payload = json.loads(events[0]["payload"])
    assert payload["operation"] == "mark_leg_querying"
    assert set(payload) <= {"attempt_id", "operation", "error_type", "error"}
    # Not fabricated: the legs stay PREPARED (the write failed), never marked
    # querying, never terminal.
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    legs = svc.store.list_legs_for_attempt(attempt["id"])
    assert all(l["dispatch_state"] == D.LEG_PREPARED for l in legs)
    assert all(not l["terminal"] for l in legs)


# ---------------------------------------------------------------------------
# 4e/4f/4g. T3 raw-response persistence (10-design §3): every POST and every drain
# query is captured verbatim, so an unexplainable exchange reply is readable from
# the DB alone — and a raw-persistence failure can never turn a good pair bad.
# ---------------------------------------------------------------------------


def test_4e_collateral_cap_51169_post_rejection_persists_raw_response(tmp_path):
    """T3 (10-design §3(b)): a 51169 margin POST rejection is persisted verbatim.
    The dispatch's acceptance test is ``SELECT business_code, business_msg, body
    FROM hedge_open_raw_response`` — the next unexplainable collateral-cap reply
    must be explainable from the DB alone, without asking Binance support. Both
    legs' POST responses land with ``source=order_post`` and the exact body."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    raw = {"http_status": 400, "transport_error": None,
           "code": "51169", "msg": "MARGIN_TRADE_COEFF_INSUFFICIENT",
           "body": '{"code":51169,"msg":"MARGIN_TRADE_COEFF_INSUFFICIENT"}'}
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        perp=_leg(LEG_REJECTED, name="perp", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock, rounds=2)
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    rows = svc.store.list_raw_responses_for_attempt(attempt["id"])
    assert len(rows) == 2  # one POST response per leg
    for r in rows:
        assert r["source"] == "order_post"
        assert r["business_code"] == "51169"
        assert r["business_msg"] == "MARGIN_TRADE_COEFF_INSUFFICIENT"
        assert r["body"] == '{"code":51169,"msg":"MARGIN_TRADE_COEFF_INSUFFICIENT"}'
        assert r["body_truncated"] == 0
        assert r["http_status"] == 400
    assert next(r for r in rows if r["leg"] == "spot")["endpoint"] == D.SPOT_ORDER_PATH
    assert next(r for r in rows if r["leg"] == "perp")["endpoint"] == D.PERP_ORDER_PATH
    # The canonical clientOrderId is captured, so the row ties to a resendable key.
    assert next(r for r in rows if r["leg"] == "spot")["client_order_id"] is not None


def test_4f_drain_query_response_persists_with_order_query_source(tmp_path):
    """T3 (10-design §3(c)): the best-effort single client-ID query that drains an
    UNKNOWN leg ALSO persists its response (``source=order_query``), so a 429 / 404
    at reconcile time is as readable as the POST that started it. Script an
    UNKNOWN pair (no POST raw), then resolve both legs via FILLED query responses
    that carry raw bodies — the raw rows must be the drain GETs, not POSTs."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])  # POST UNKNOWN -> no POST raw
    raw_s = {"http_status": 200, "transport_error": None, "code": None, "msg": None,
             "body": '{"orderId":"s1","status":"FILLED","executedQty":"0.5"}'}
    raw_p = {"http_status": 200, "transport_error": None, "code": None, "msg": None,
             "body": '{"orderId":"p1","status":"FILLED","executedQty":"0.5"}'}
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000", raw=raw_s),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000", raw=raw_p),
    ])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=3)  # reconcile drains both legs -> resolve
    assert exe.query_calls >= 2
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["business_code"] is None for r in qrows)  # 2xx, no error code
    assert all(r["body"] in (raw_s["body"], raw_p["body"]) for r in qrows)
    assert next(r for r in qrows if r["leg"] == "spot")["endpoint"] == D.SPOT_ORDER_PATH
    assert next(r for r in qrows if r["leg"] == "perp")["endpoint"] == D.PERP_ORDER_PATH


def test_4h_dispatch_unknown_post_fallback_query_persists_post_and_query_raw(tmp_path):
    """T3 §3 (review-1 P1): a POST that returns UNKNOWN (5xx) triggers an immediate
    best-effort order-detail GET inside ``LiveHedgeExecutor._send_one_leg``. When
    that GET resolves the leg, the raw table must hold BOTH the POST response
    (``source=order_post``, the inconclusive 5xx) AND the fallback GET
    (``source=order_query``, the FILLED body that decided the leg's fate). The GET
    body was previously discarded. The perp leg's POST is conclusive, so it gets no
    ``order_query`` row — its only GET is the UM inline confirm (``order_confirm``).
    Order verdicts are unchanged: the fix only adds the dropped GET row."""
    client = _LiveWireClient(
        spot_post=_wire_resp(500, {"msg": "Service Unavailable"}),  # POST -> UNKNOWN
        spot_query=_wire_resp(200, {                                # GET resolves it
            "orderId": 1, "status": "FILLED", "executedQty": "0.5",
            "cummulativeQuoteQty": "25000", "avgPrice": "50000"}),
        perp_post=_wire_resp(200, {                                 # POST conclusive -> ACCEPTED
            "orderId": 2, "status": "FILLED", "executedQty": "0.5"}),
        perp_query=_wire_resp(200, {                                # UM inline confirm
            "orderId": 2, "status": "FILLED", "cumQuote": "25000", "avgPrice": "50000"}),
    )
    exe = LiveHedgeExecutor(client, now_ms=lambda: 1000)
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    _step(svc, doc["id"], clock, rounds=2)
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    rows = svc.store.list_raw_responses_for_attempt(attempt["id"])

    # spot: POST UNKNOWN (5xx) -> immediate fallback GET resolved it. Both the POST
    # (5xx body) and the GET (FILLED body) persist, on distinct sources — the GET no
    # longer overwrites the POST, nor is it dropped.
    spot_rows = [r for r in rows if r["leg"] == "spot"]
    assert {r["source"] for r in spot_rows} == {"order_post", "order_query"}
    post = next(r for r in spot_rows if r["source"] == "order_post")
    assert post["http_status"] == 500
    query = next(r for r in spot_rows if r["source"] == "order_query")
    assert query["http_status"] == 200
    assert query["business_code"] is None          # 2xx FILLED: no business code (NULL)
    assert query["business_msg"] is None
    assert query["client_order_id"] is not None    # ties to the resendable clientOrderId
    assert '"status": "FILLED"' in query["body"]   # GET body retrievable from the DB

    # perp: conclusive POST (accepted) -> its only GET is the UM confirm. No
    # ``order_query`` row: the in-executor fallback query never ran for this leg.
    perp_rows = [r for r in rows if r["leg"] == "perp"]
    assert {r["source"] for r in perp_rows} == {"order_post", "order_confirm"}

    # Order verdict UNCHANGED by the fix: the immediate GET resolved the spot leg to
    # FILLED with authoritative figures exactly as before (the fix only adds the raw
    # row); both legs are terminal.
    legs = svc.store.list_legs_for_attempt(attempt["id"])
    spot_leg = next(l for l in legs if l["leg"] == "spot")
    assert spot_leg["exchange_status"] == D.LEG_FILLED
    assert spot_leg["cumulative_quote_amt"] == "25000"
    assert spot_leg["terminal"] == 1


def test_4g_raw_persist_failure_does_not_break_business_write(tmp_path):
    """T3 (10-design §3(e)): control-flow isolation is absolute. A raw-persistence
    failure (disk full / locked) MUST NOT turn a resolved collateral_cap pair into
    anything else — the business write stands (pair resolved, task paused), and the
    failure is best-effort surfaced as a ``raw_persist_failed`` task event rather
    than swallowed silently."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    raw = {"http_status": 400, "transport_error": None,
           "code": "51169", "msg": "cap", "body": "{}"}
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        perp=_leg(LEG_REJECTED, name="perp", error_code="51169",
                  error_category=D.ERROR_CATEGORY_COLLATERAL_CAP, raw=raw),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])

    def _boom(*_a, **_k):
        raise RuntimeError("disk full")
    svc.store.append_raw_response = _boom  # simulate persistence failure

    _step(svc, doc["id"], clock, rounds=2)
    task = svc.store.get_task(doc["id"])
    # The business write stands: pair resolved + paused collateral_cap, NOT turned
    # into a failure by the raw-persistence error.
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_COLLATERAL_CAP_FULL
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    assert attempt["error_category"] == D.ERROR_CATEGORY_COLLATERAL_CAP
    # No raw row landed (the persist raised both times).
    assert svc.store.list_raw_responses_for_attempt(attempt["id"]) == []
    # The failure was surfaced as a best-effort audit event (not silent).
    events = svc.store.list_task_event_logs(20, kinds=("raw_persist_failed",))
    assert len(events) >= 1
    assert events[0]["kind"] == "raw_persist_failed"


def test_4i_drain_rate_limited_query_persists_order_query_row(tmp_path):
    """Review-1 r3 P1-1 (00-task.md §T3): a drain query that comes back
    rate-limited (a 429 / -1003 / 418) is a CONCLUSIVE verdict whose raw must be
    persisted — the rate-limited branch previously ``continue``d before reaching
    the ``_persist_leg_raw`` call. Script an UNKNOWN pair (no POST raw), then
    return both drain GETs as rate-limited: each leg lands exactly one
    ``order_query`` row carrying the 429 body, the task pauses rate_limited
    exactly as today, the legs stay non-terminal, and nothing is resent."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])  # POST UNKNOWN -> no POST raw
    raw_429 = {"http_status": 429, "transport_error": None, "code": None,
               "msg": None, "body": '{"code":-1003,"msg":"Request weight limited"}'}
    exe.queries.extend([
        _leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, raw=raw_429),
        _leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, raw=raw_429),
    ])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=1)  # reconcile: both legs 429 -> pause
    assert exe.query_calls == 2
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2  # the previously-dropped 429 evidence is now retrievable
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["http_status"] == 429 for r in qrows)
    assert all(r["body"] == raw_429["body"] for r in qrows)
    # Pause semantics, non-terminal handling, and never-resend are unchanged.
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    legs = svc.store.list_legs_for_attempt(attempt["id"])
    assert all(l["terminal"] == 0 for l in legs)  # legs kept, never resent
    assert exe.dispatch_calls == 1  # no second dispatch / no resend


def test_4j_repeated_malformed_2xx_drain_grows_one_row_per_leg(tmp_path):
    """Review-1 r3 P1-2 (user rule 2026-07-28/29): a malformed 2xx (no orderId)
    returns an UNKNOWN verdict, so the leg stays non-terminal and drain re-queries
    it every worker round. Repeated identical responses across several rounds must
    produce EXACTLY ONE ``order_query`` row per leg — not one per round — while the
    leg still stays non-terminal and is still re-queried (a storage cap, not a
    behaviour change)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])  # POST UNKNOWN -> no POST raw
    raw_bad = {"http_status": 200, "transport_error": None, "code": None,
               "msg": None, "body": '{"status":"NEW"}'}  # 2xx, no orderId -> UNKNOWN
    # Enough identical malformed-2xx verdicts for several drain rounds (2 legs each).
    exe.queries.extend([_leg(LEG_UNKNOWN_QUERYING, name="spot", raw=raw_bad)
                        for _ in range(10)])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=4)  # reconcile re-queries both legs each round
    assert exe.query_calls > 2  # re-queried across multiple rounds (not stuck)
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2  # exactly one row per leg, NOT one per round
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["body"] == raw_bad["body"] for r in qrows)
    # The leg is still non-terminal and still being drained (behaviour unchanged).
    legs = svc.store.list_legs_for_attempt(attempt["id"])
    assert all(l["terminal"] == 0 for l in legs)


def test_4k_drain_new_then_filled_replaces_placeholder_order_query_row(tmp_path):
    """Review-1 r5 P1 (00-task.md §T3): a first non-decisive order_query (NEW)
    inserts a placeholder row; the later FILLED query (decisive) REPLACES that row
    in place. One order_query row per leg survives, holding the FILLED body and
    stamped decisive — the conclusive verdict §T3 requires persisted is the one
    kept, not the earlier NEW."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])  # POST UNKNOWN -> no POST raw
    raw_new = {"http_status": 200, "transport_error": None, "code": None,
               "msg": None, "body": '{"orderId":"s1","status":"NEW"}'}
    raw_filled = {"http_status": 200, "transport_error": None, "code": None,
                  "msg": None,
                  "body": '{"orderId":"s1","status":"FILLED","executedQty":"0.5"}'}
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000", raw=raw_filled),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000", raw=raw_filled),
    ])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=2)  # reconcile: NEW (placeholder) then FILLED
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2  # one row per leg — the NEW placeholder was replaced, not doubled
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["body"] == raw_filled["body"] for r in qrows)  # FILLED won, not NEW
    assert all(r["decisive"] == 1 for r in qrows)


def test_4l_drain_new_then_confirmed_absent_replaces_placeholder_order_query_row(tmp_path):
    """Review-1 r5 P1 (00-task.md §T3): a confirmed-absent order-detail read
    (404 / -2013) is decisive, so it replaces a prior non-decisive placeholder —
    one order_query row per leg holding the absent response."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    raw_new = {"http_status": 200, "transport_error": None, "code": None,
               "msg": None, "body": '{"orderId":"s1","status":"NEW"}'}
    raw_absent = {"http_status": 404, "transport_error": None, "code": "-2013",
                  "msg": "Order does not exist.",
                  "body": '{"code":-2013,"msg":"Order does not exist."}'}
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_REJECTED, name="spot", error_code="-2013", quote=None,
             error_category=D.ERROR_CATEGORY_ABSENT, raw=raw_absent),
        _leg(LEG_REJECTED, name="perp", error_code="-2013", quote=None,
             error_category=D.ERROR_CATEGORY_ABSENT, raw=raw_absent),
    ])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=2)  # reconcile: NEW then confirmed-absent
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["body"] == raw_absent["body"] for r in qrows)  # absent won, not NEW
    assert all(r["business_code"] == "-2013" for r in qrows)
    assert all(r["decisive"] == 1 for r in qrows)


def test_4m_drain_new_then_rate_limited_replaces_placeholder_and_pauses(tmp_path):
    """Review-1 r5 P1 (00-task.md §T3): a rate-limit signal (429 / -1003 / 418) is
    decisive, so it replaces a prior non-decisive placeholder — one order_query row
    per leg holding the 429 body. The task still pauses rate_limited exactly as
    today, the legs stay non-terminal, and nothing is resent."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    raw_new = {"http_status": 200, "transport_error": None, "code": None,
               "msg": None, "body": '{"orderId":"s1","status":"NEW"}'}
    raw_429 = {"http_status": 429, "transport_error": None, "code": None,
               "msg": None, "body": '{"code":-1003,"msg":"Request weight limited"}'}
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_NEW, raw=raw_new),
        _leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, raw=raw_429),
        _leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, raw=raw_429),
    ])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _step(svc, doc["id"], clock, rounds=2)  # reconcile: NEW then 429 -> pause
    attempt = svc.store.list_attempts_for_task(doc["id"])[0]
    qrows = [r for r in svc.store.list_raw_responses_for_attempt(attempt["id"])
             if r["source"] == "order_query"]
    assert len(qrows) == 2
    assert {r["leg"] for r in qrows} == {"spot", "perp"}
    assert all(r["body"] == raw_429["body"] for r in qrows)  # 429 won, not NEW
    assert all(r["decisive"] == 1 for r in qrows)
    # Pause semantics, non-terminal handling, and never-resend are unchanged.
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    legs = svc.store.list_legs_for_attempt(attempt["id"])
    assert all(l["terminal"] == 0 for l in legs)
    assert exe.dispatch_calls == 1  # no second dispatch / no resend


# ---------------------------------------------------------------------------
# Cadence-500ms task: absent/inconclusive tolerance window (acceptance 5 & 6).
# A 404 / -2013 on a freshly POSTed leg is eventual-consistency noise (mirrors
# _confirm_um_figures), and a still-inconclusive leg is genuinely unknown — so
# within the window neither confirms absent; only after it does a 404 / -2013
# confirm absent, while a still-inconclusive leg escalates to manual recovery
# (never equated with absent — R2-F2).
# ---------------------------------------------------------------------------


def test_absent_below_retry_cap_stays_nonterminal_then_confirms_at_cap(tmp_path):
    """F1 (acceptance 5): a 404 / -2013 received BEFORE the retry cap leaves the
    leg non-terminal (keep querying, never resend); the SAME 404 received AT the
    cap (the LEG_QUERY_MAX_RETRIES-th query) confirms absent (terminal ->
    failure). No dispatched_at_us anchor is involved."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight

    # Below the cap: a 404 must NOT confirm absent — legs stay non-terminal.
    exe.queries.extend([_absent_query("spot"), _absent_query("perp")])
    _step(svc, doc["id"], clock, rounds=1)
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # still draining, never resent
    assert svc.store.list_attempts_for_task(doc["id"])[0]["pair_outcome"] is None

    # At the cap (10th query): the same 404 confirms absent -> terminal failure.
    _retry_cap_queries(exe, already=1,
                       final=[_absent_query("spot"), _absent_query("perp")])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES - 1)
    assert svc.store.get_task(doc["id"])["fail_count"] == 1  # absent confirmed


def test_inconclusive_at_retry_cap_pauses_for_manual_recovery_not_absent(tmp_path):
    """F1 (acceptance 6, R2-F2): a leg whose queries stay inconclusive (malformed
    2xx -> UNKNOWN_QUERYING) for the whole retry budget is NEVER equated with
    absent. It is left non-terminal and the task pauses for manual recovery
    (order_state_unknown) — not confirmed-failed, never resent."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight

    # The 10th (cap) query is still inconclusive (NOT a 404 / -2013).
    _retry_cap_queries(exe, final=[
        _leg(LEG_UNKNOWN_QUERYING, name="spot"),
        _leg(LEG_UNKNOWN_QUERYING, name="perp"),
    ])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)  # drain to cap -> pause

    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_ORDER_STATE_UNKNOWN
    assert task["fail_count"] == 0  # never confirmed absent / failed
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # left non-terminal, never resent
    assert exe.dispatch_calls == 1  # no resend


# ---------------------------------------------------------------------------
# fix-review1-retry-counter (F1): no-anchor legs, restart semantics, counter
# cleanup, and the verdict-None signal site (F4).
# ---------------------------------------------------------------------------


def test_no_anchor_leg_404_confirms_absent_at_retry_cap(tmp_path):
    """F1 acceptance 1 (404): a leg WITHOUT dispatched_at_us (legacy row /
    crash gap) still counts its retries and closes at the cap — the 10th query
    404 confirms absent terminal. Must fail if the counter is removed (no anchor
    = infinite re-query, the F1 root cause)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    # 抹掉 dispatched_at_us：旧库行 / prepare_attempt 落库后崩溃间隙的真实形态。
    with svc.store._lock, svc.store._conn:
        svc.store._conn.execute(
            "UPDATE hedge_open_leg SET dispatched_at_us = NULL WHERE terminal = 0"
        )
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)
    task = svc.store.get_task(doc["id"])
    assert task["fail_count"] == 1  # absent confirmed despite no anchor
    assert task["status"] != D.STATUS_PAUSED  # a confirmed absent is a failure
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 1 for l in legs)


def test_no_anchor_leg_inconclusive_pauses_at_retry_cap(tmp_path):
    """F1 acceptance 1 (inconclusive): a leg WITHOUT dispatched_at_us whose
    queries stay inconclusive for the whole budget escalates to manual recovery
    (paused, order_state_unknown) — never equated with absent, never resent."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    with svc.store._lock, svc.store._conn:
        svc.store._conn.execute(
            "UPDATE hedge_open_leg SET dispatched_at_us = NULL WHERE terminal = 0"
        )
    _retry_cap_queries(exe, final=[
        _leg(LEG_UNKNOWN_QUERYING, name="spot"),
        _leg(LEG_UNKNOWN_QUERYING, name="perp"),
    ])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_ORDER_STATE_UNKNOWN
    assert task["fail_count"] == 0
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # non-terminal, never resent
    assert exe.dispatch_calls == 1


def test_restart_resets_retry_counter_and_recovers_without_resend(tmp_path):
    """F1 acceptance 2: the retry counter is process-local — a fresh service on
    the SAME db restarts the budget from zero (matching the legacy JS loop), and
    the recovery path re-queries by client ID only (never resends)."""
    db_path = str(tmp_path / "ho.sqlite3")
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())

    clock1 = _Clock()
    svc1 = _svc_with(db_path, exe, provider, clock1)
    svc1.set_start_gate(True)
    doc = _create(svc1, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc1._pump_worker(doc["id"], max_rounds=1)  # dispatch UNKNOWN pair
    # 数 3 次（未达上限），腿保持非终态。
    exe.queries.extend([None] * 6)
    svc1._pump_worker(doc["id"], max_rounds=3)
    legs1 = svc1.store.list_legs_for_attempt(_attempt_id(svc1, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs1)
    assert svc1._leg_query_retries == {legs1[0]["id"]: 3, legs1[1]["id"]: 3}
    posts_before = exe.dispatch_calls
    assert posts_before == 1
    svc1.stop()
    del svc1

    # 新实例：计数从零重新开始；恢复按 clientOrderId 重查、不重发；达上限的
    # 404 判 absent（收口需要重新数满 10 次，而不是按原计数或原下单时间）。
    clock2 = _Clock()
    svc2 = _svc_with(db_path, exe, provider, clock2)
    svc2.set_start_gate(True)
    assert svc2._leg_query_retries == {}  # fresh budget after restart
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])
    svc2._pump_worker(doc["id"], max_rounds=D.LEG_QUERY_MAX_RETRIES)
    assert exe.dispatch_calls == posts_before  # no resend
    task = svc2.store.get_task(doc["id"])
    assert task["fail_count"] == 1  # absent confirmed on the fresh budget
    legs2 = svc2.store.list_legs_for_attempt(_attempt_id(svc2, doc["id"]))
    assert all(l["terminal"] == 1 for l in legs2)


def test_retry_counter_cleared_on_terminal_leg_and_worker_exit(tmp_path):
    """F1 acceptance 3: the in-process retry dict does not grow without bound —
    a leg reaching terminal state clears its entry, and a worker exit clears
    every entry of its task (including non-terminal legs left by a
    manual-recovery pause)."""
    # 子 A：pump 路径，腿终态即清理（不走 worker finally）。
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)
    assert svc._leg_query_retries == {}  # terminal legs cleared their entries

    # 子 B：真线程 worker 自然退出（inconclusive 达上限 -> 人工暂停 -> 退出），
    # 非终态腿的计数也被 worker 退出清理。
    db_path = str(tmp_path / "b.sqlite3")
    exe_b = _RoutingExecutor()
    svc_b = _svc_with(db_path, exe_b, _FakeProvider(_ok_snapshot()), _Clock())
    svc_b.set_start_gate(True)
    doc_b = _create(svc_b, target_n=1)
    exe_b.set_script(doc_b["id"], [_unknown_pair()])
    svc_b._pump_worker(doc_b["id"], max_rounds=1)  # dispatch -> in-flight
    exe_b.queries.extend([None] * (2 * D.LEG_QUERY_MAX_RETRIES))
    svc_b.ensure_worker(doc_b["id"])
    wb = svc_b._workers.get(doc_b["id"])
    if wb is not None:
        wb.join(timeout=15.0)
    assert svc_b.store.get_task(doc_b["id"])["status"] == D.STATUS_PAUSED
    assert svc_b._leg_query_retries == {}  # worker exit cleared the counters


def test_inconclusive_verdict_none_at_cap_pauses_manual_recovery(tmp_path):
    """F4 (review-1): a drain query returning None (transport error / 5xx /
    timeout) at the retry cap is its OWN signal site — the task pauses manually,
    the legs stay non-terminal, the failure counter is untouched, nothing is
    resent. Deleting the verdict-None signal site in ``_reconcile_own_legs``
    must fail this test (the malformed-2xx site alone must not mask it)."""
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    # 10 次查询全部返回 None：verdict is None 分支。
    exe.queries.extend([None] * (2 * D.LEG_QUERY_MAX_RETRIES))
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_ORDER_STATE_UNKNOWN
    assert task["fail_count"] == 0  # failure counter untouched
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # non-terminal, never resent
    assert exe.dispatch_calls == 1


# ---------------------------------------------------------------------------
# F2 (review-1): the retry-cap inconclusive drain must NOT rewrite a non-running
# task's sticky status (deleted / done / stopped) to paused — the event is still
# recorded, the legs stay non-terminal, nothing is resent.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [D.STATUS_DELETED, D.STATUS_DONE, D.STATUS_STOPPED])
def test_inconclusive_cap_drain_keeps_non_running_status_sticky(tmp_path, status):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    _step(svc, doc["id"], clock, rounds=1)  # dispatch UNKNOWN -> in-flight
    svc.store.set_task_status(doc["id"], status, svc._wall_us())
    _retry_cap_queries(exe, final=[
        _leg(LEG_UNKNOWN_QUERYING, name="spot"),
        _leg(LEG_UNKNOWN_QUERYING, name="perp"),
    ])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == status  # sticky — NOT rewritten to paused
    assert task["pause_reason"] is None
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # non-terminal, never resent
    assert exe.dispatch_calls == 1
    # 可见人工核对事件仍被记录（F2：记录事件但不改状态、不重发），但它必须用
    # 终态专属的 kind——终态任务既没暂停也不可恢复，沿用 task_paused 会让时间线
    # 印出「任务暂停 / 已暂停」两个假声明（2026-08-07 修）。
    assert svc.store.list_task_event_logs(20, kinds=("task_paused",)) == []
    events = svc.store.list_task_event_logs(20, kinds=("order_state_unknown_final",))
    payloads = [json.loads(e["payload"]) for e in events]
    assert any(p.get("reason") == D.PAUSE_REASON_ORDER_STATE_UNKNOWN for p in payloads)
    # 文案不得声称任务被暂停、也不得指示去做一个不存在的「手动恢复」；
    # 必须点明去交易所核实 + 系统不会重发。（说「无法恢复」是诚实的，允许。）
    zh = next(p["reason_zh"] for p in payloads if p.get("reason_zh"))
    assert "暂停" not in zh and "手动恢复" not in zh
    assert "核实" in zh and "不会重发" in zh


# ---------------------------------------------------------------------------
# fix-runtime-seam-scan (F2-P1 root fix): the SAME family, exercised CONCURRENTLY.
# The static tests above set the terminal status BEFORE the drain; they cannot
# cover the window where post_delete lands DURING a no-lock executor query and a
# stale worker snapshot then writes status. The store-side conditional write
# (pause_task / stop_task_fatal: running/paused only) must keep the sticky
# status, still record the event, and never resend.
# ---------------------------------------------------------------------------


class _BarrierQueryExecutor(_RoutingExecutor):
    """F2-P1 并发回归辅助：第一次 query_leg 调用阻塞，让测试在 executor 查询
    进行中执行 post_delete（真线程 worker 才能产生这个交错——_pump_worker 是
    同步测试缝，无法在查询中途插入外部写）。release 后按脚本返回 verdict。
    ``reentered`` 标记 worker 已进入第二轮查询（第一轮 drain 已处理完）。"""

    def __init__(self):
        super().__init__()
        self.query_started = threading.Event()
        self.release = threading.Event()
        self.reentered = threading.Event()
        self._qcount = 0

    def query_leg(self, leg_name, coin, cid, endpoint):
        self._qcount += 1
        if self._qcount == 1:
            self.query_started.set()
            self.release.wait(10.0)
        elif self._qcount == 2:
            self.reentered.set()
        return super().query_leg(leg_name, coin, cid, endpoint)


def _wait_worker_past_first_drain(svc, exe, task_id, timeout=8.0):
    """等待 worker 完成第一轮 drain 的状态写（退出，或进入第二轮查询——
    reentered 说明第一轮已处理完）。并发测试的确定性锚点，无 sleep 竞态。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        worker = svc._workers.get(task_id)
        if worker is None or exe.reentered.is_set():
            return
        time.sleep(0.01)
    raise AssertionError("worker did not finish the first drain round")


def _wait_for_event(svc, kinds, reason, timeout=8.0):
    """轮询等待 kind/reason 匹配的任务事件（并发测试用；事件由 worker 线程写）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = svc.store.list_task_event_logs(50, kinds=kinds)
        if any(json.loads(e["payload"]).get("reason") == reason for e in events):
            return
        time.sleep(0.01)
    raise AssertionError(f"event kind={kinds} reason={reason} never recorded")


def test_concurrent_delete_during_drain_rate_limited_keeps_deleted(tmp_path):
    """F2-P1 并发回归（429 站点，pre-existing-release-critical）：executor 查询
    进行中 post_delete，429 drain 收口不得把已删除任务复活为 paused。最终状态
    deleted、腿非终态、无重发、rate_limited 事件仍记录。破坏 pause_task 的
    条件写（改回无条件）即失败。"""
    exe = _BarrierQueryExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc.ensure_worker(doc["id"])  # 真线程 worker
    assert exe.query_started.wait(5.0), "worker never reached the drain query"
    svc.post_delete(doc["id"])  # 查询进行中删除
    exe.queries.extend([
        _leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True),
        _leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True),
    ])
    exe.release.set()
    _wait_for_event(svc, ("rate_limited",), D.PAUSE_REASON_RATE_LIMITED)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DELETED  # 粘性，未被复活为 paused
    assert task["pause_reason"] is None
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # 429 不 resolve
    assert exe.dispatch_calls == 1  # 无重发
    svc.stop()
    worker = svc._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)


def test_concurrent_delete_during_drain_insufficient_keeps_deleted(tmp_path):
    """F2-P1 并发回归（insufficient_* 站点，pre-existing-release-critical）：
    查询进行中 post_delete + drain 返回 insufficient 分类 -> 不得复活为 paused。"""
    exe = _BarrierQueryExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc.ensure_worker(doc["id"])
    assert exe.query_started.wait(5.0), "worker never reached the drain query"
    svc.post_delete(doc["id"])
    exe.queries.extend([
        _leg(LEG_UNKNOWN_QUERYING, name="spot", error_code="-2019",
             error_category=D.ERROR_CATEGORY_INSUFFICIENT_FUNDS),
        _leg(LEG_UNKNOWN_QUERYING, name="perp", error_code="-2019",
             error_category=D.ERROR_CATEGORY_INSUFFICIENT_FUNDS),
    ])
    exe.release.set()
    _wait_for_event(svc, ("task_paused",), D.PAUSE_REASON_INSUFFICIENT_BALANCE)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DELETED  # 粘性
    assert task["pause_reason"] is None
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # 非终态（UNKNOWN_QUERYING）
    assert exe.dispatch_calls == 1  # 无重发
    svc.stop()
    worker = svc._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)


def test_concurrent_delete_during_drain_order_state_unknown_keeps_deleted(tmp_path):
    """F2-P1 并发回归（order_state_unknown 站点，in-range）：查询进行中
    post_delete + 计数达上限的 inconclusive -> 不得复活为 paused。"""
    exe = _BarrierQueryExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [_unknown_pair()])
    svc.ensure_worker(doc["id"])
    assert exe.query_started.wait(5.0), "worker never reached the drain query"
    svc.post_delete(doc["id"])
    # 第 10 次查询（计数达上限）返回畸形 2xx -> SIGNAL_ORDER_STATE_UNKNOWN。
    exe.queries.extend([None] * (2 * (D.LEG_QUERY_MAX_RETRIES - 1)))
    exe.queries.extend([
        _leg(LEG_UNKNOWN_QUERYING, name="spot"),
        _leg(LEG_UNKNOWN_QUERYING, name="perp"),
    ])
    exe.release.set()
    # 终态任务用 order_state_unknown_final（2026-08-07）：并发删除落在查询窗口内时，
    # 这条并发路径与上面的静态 sticky 测试必须走同一个 kind——否则「已删任务不自称
    # 暂停」这条修复只在慢路径成立，快路径仍印假声明。
    _wait_for_event(svc, ("order_state_unknown_final",), D.PAUSE_REASON_ORDER_STATE_UNKNOWN)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DELETED  # 粘性
    assert task["pause_reason"] is None
    legs = svc.store.list_legs_for_attempt(_attempt_id(svc, doc["id"]))
    assert all(l["terminal"] == 0 for l in legs)  # 非终态
    assert exe.dispatch_calls == 1  # 无重发
    svc.stop()
    worker = svc._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)


class _BarrierFatalProvider:
    """同族（_stop_task_fatal_preflight）辅助：get_snapshot 阻塞（模拟 preflight
    网络读取），返回 symbol_tradable=False 的 snapshot -> fatal preflight。"""

    def __init__(self, snapshot, started, release):
        self._snapshot = snapshot
        self.started = started
        self.release = release

    def get_snapshot(
        self, coin, direction, task_type="open", position_side_mode=None,
    ):
        self.started.set()
        self.release.wait(10.0)
        return self._snapshot


def test_concurrent_delete_during_fatal_preflight_keeps_deleted(tmp_path):
    """运行时接缝族 #1 同族确认：fatal preflight 的 preflight 网络读取（无锁）
    期间 post_delete，旧快照不得把已删除任务复活为 stopped。stop_task_fatal 的
    条件写守卫（running/paused only）保证粘性；task_stopped 事件仍记录。"""
    started = threading.Event()
    release = threading.Event()
    fatal_snapshot = dataclasses.replace(_ok_snapshot(), symbol_tradable=False)
    exe = _RoutingExecutor()
    # 创建任务用正常 provider（create_task 本身会做一次 preflight 检查）；
    # 随后替换为「阻塞 + fatal」的 provider，让 worker 的下一轮 preflight 读取
    # 产生并发窗口。
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    svc._preflight = _BarrierFatalProvider(fatal_snapshot, started, release)
    svc.ensure_worker(doc["id"])
    # round1: drain(无腿) -> 旧快照 running -> dispatch -> preflight 网络读取（阻塞）。
    assert started.wait(5.0), "worker never reached the preflight read"
    svc.post_delete(doc["id"])  # preflight 读取进行中删除
    release.set()
    worker = svc._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=10.0)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DELETED  # 未被复活为 stopped
    assert task["stop_reason"] is None
    assert exe.dispatch_calls == 0  # fatal preflight 在任何 POST 之前 -> 无下单、无重发
    # task_stopped 事件仍记录（可见；状态未被改写）。
    events = svc.store.list_task_event_logs(50, kinds=("task_stopped",))
    assert any(
        json.loads(e["payload"]).get("stop_reason") == D.STOP_REASON_SYMBOL_UNAVAILABLE
        for e in events
    )


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
    # F1 计数机制：pair1 的 404 在第 LEG_QUERY_MAX_RETRIES 次查询确认 absent。
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])

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
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES + 4)
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
    # F1 计数机制：pair1 的 404 在第 LEG_QUERY_MAX_RETRIES 次查询确认 absent。
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # pair1 429 -> pause
    assert svc.store.get_task(doc["id"])["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    svc.store.set_task_status(doc["id"], D.STATUS_RUNNING, svc._wall_us())  # resume
    # (the three later _rejected_pair dispatches are terminal at dispatch and
    # are unaffected by the retry budget).

    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES + 8)  # pair1 drain (no counter) + 3 fails
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
    # F1 计数机制：drain 的 404 在第 LEG_QUERY_MAX_RETRIES 次查询确认 absent。
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # dispatch pair1 UNKNOWN -> in-flight
    scheduled_before = svc.store.get_task(doc["id"])["scheduled_attempt_count"]
    assert scheduled_before == 1
    svc.post_pause(doc["id"])  # pause; worker NOT interrupted
    assert svc.store.get_task(doc["id"])["status"] == D.STATUS_PAUSED
    # P2-1 (Review-1 r4): post_pause must NOT set the per-task stop event —
    # interrupting the worker mid-pair would abandon in-flight REAL orders.
    # The seam (_pump_worker) no longer clears an existing event, so together
    # they make R3 genuinely FAIL if the deleted _wake_worker interrupt is ever
    # re-introduced into post_pause.
    assert svc._stop_events[doc["id"]].is_set() is False

    # F1 计数机制：无时钟推进；计数到上限后 404 确认 absent，worker 收尾退出。
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)  # worker drains, settles, exits
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
    # F1 计数机制：drain 的 404 在第 LEG_QUERY_MAX_RETRIES 次查询确认 absent。
    _retry_cap_queries(exe, final=[_absent_query("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # dispatch pair1 UNKNOWN -> in-flight
    scheduled_before = svc.store.get_task(doc["id"])["scheduled_attempt_count"]
    svc.post_delete(doc["id"])  # delete; worker NOT interrupted
    assert svc.store.get_task(doc["id"])["status"] == D.STATUS_DELETED
    # P2-1 (Review-1 r4): post_delete must NOT set the per-task stop event.
    assert svc._stop_events[doc["id"]].is_set() is False

    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)  # worker drains, settles, exits
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


def _accepted_done_with_nonterminal_perp():
    """P2-2 (Review-1 r4) scenario: an accepted pair that reaches done with one
    leg accepted-but-NEW (terminal=0 by design). With target_n=1 the first
    accepted pair pushes the task to done; the perp leg is accepted (orderId
    returned) but not yet FILLED, so service._leg_terminal leaves it non-terminal
    for the reconcile pass to poll — exactly the leg a restart must not forget."""
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
                  executed="0.5", quote="25000", avg="50000"),
        perp=_leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_NEW,
                  executed="0", quote="0", avg=None),
        record_payload={"transport": "live", "posted": True},
        rate_limited=False, retry_after_seconds=None,
    )


# R9 — a DONE card left with an accepted-but-non-terminal leg (a target-reaching
# pair whose perp was accepted+NEW) is drained to terminal by the ONE startup
# recovery handoff on a fresh instance (STATUS_DONE now in the drain-only
# fallback). No resident scanner, no resend, status stays done. Mirrors R5
# (DELETED) but for the target-reaching case; finalize_attempt is idempotent on
# the already-resolved accepted pair, so the counter is not double-counted.
def test_r9_done_card_nonterminal_accepted_leg_recovered_on_restart(tmp_path):
    db_path = str(tmp_path / "ho.sqlite3")
    exe = _RoutingExecutor()
    provider = _FakeProvider(_ok_snapshot())

    # --- old service: dispatch the target-reaching pair (spot FILLED, perp
    #     accepted+NEW). resolve_attempt marks the pair accepted and pushes the
    #     task to done while leaving the perp leg non-terminal, then stop. ---
    clock1 = _Clock()
    svc1 = _svc_with(db_path, exe, provider, clock1)
    svc1.set_start_gate(True)
    doc = _create(svc1, target_n=1)
    exe.set_script(doc["id"], [_accepted_done_with_nonterminal_perp()])
    svc1._pump_worker(doc["id"], max_rounds=1)  # dispatch -> accepted -> done
    assert svc1.store.get_task(doc["id"])["status"] == D.STATUS_DONE
    legs1 = svc1.store.list_legs_for_attempt(_attempt_id(svc1, doc["id"]))
    perp1 = next(l for l in legs1 if l["leg"] == "perp")
    assert perp1["terminal"] == 0            # accepted-but-NEW, left for reconcile
    assert svc1.store.list_non_terminal_legs_for_task(doc["id"]), \
        "done card holds an accepted-but-non-terminal leg"
    posts_before = exe.dispatch_calls
    assert posts_before == 1
    svc1.stop()
    del svc1

    # --- new service: fresh instance, SAME db file, SAME executor. The ONE
    #     recovery handoff drains the accepted-but-NEW perp leg to terminal. ---
    clock2 = _Clock()
    svc2 = _svc_with(db_path, exe, provider, clock2)
    svc2.set_start_gate(True)
    # Spy on ensure_worker: the assertion must not race on whether the launched
    # drain worker has already finished (it can drain the leg and exit within
    # start() under load). STATUS_DONE is now in the drain-only fallback.
    ensured = []
    _ensure_real = svc2.ensure_worker

    def _spy_ensure(tid):
        ensured.append(tid)
        return _ensure_real(tid)

    svc2.ensure_worker = _spy_ensure
    exe.queries.extend([_filled_leg("perp")])  # drain: perp -> FILLED (terminal)
    svc2.start()  # ONE recovery handoff; DONE now in drain-only fallback
    assert doc["id"] in ensured, "recovery launched a drain worker for the DONE card"
    worker = svc2._workers.get(doc["id"])
    if worker is not None:
        worker.join(timeout=5.0)
    assert exe.dispatch_calls == posts_before    # only the original dispatch, no resend
    assert exe.query_calls >= 1
    assert svc2.store.list_non_terminal_legs_for_task(doc["id"]) == []
    legs = svc2.store.list_legs_for_attempt(_attempt_id(svc2, doc["id"]))
    assert all(l["terminal"] for l in legs)
    perp = next(l for l in legs if l["leg"] == "perp")
    assert perp["exchange_status"] == D.LEG_FILLED  # reconciled from NEW to FILLED
    task = svc2.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DONE            # sticky
    assert task["accepted_pair_count"] == 1           # finalize_attempt is idempotent


# R6 — a 429 on one leg + the other leg FILLED -> single_leg outcome with the
# advisory leg_exposure recorded, and the failure counter untouched.
def test_r6_rate_limit_one_leg_other_filled_single_leg_exposure(tmp_path):
    exe = _RoutingExecutor()
    svc, clock = _live_svc(tmp_path, exe, _FakeProvider(_ok_snapshot()))
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [_rate_limited_unknown_pair()])
    # drain: spot -> FILLED (orderId), perp -> absent (no orderId) => single_leg
    # F1 计数机制：perp 的 404 在第 LEG_QUERY_MAX_RETRIES 次查询确认 absent
    # (-> single-leg: spot FILLED, perp confirmed-absent)。
    _retry_cap_queries(exe, final=[_filled_leg("spot"), _absent_query("perp")])

    _step(svc, doc["id"], clock, rounds=1)  # 429 dispatch -> pause (rate_limited)
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES)  # drain single_leg -> settle
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    assert task["fail_count"] == 0          # rate-limited -> no counter
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1
    assert attempts[0]["pair_outcome"] == D.PAIR_SINGLE_LEG
    assert task["leg_exposure"] is not None
    assert task["leg_exposure"]["leg"] == "spot"


# R7 — live worker_active tri-state + pause-on-preflight-incomplete:
# stage 2026-08-06 task 05 §5 (Human decision 4) — a preflight failure now
# PAUSES the task with a Chinese reason naming the failed read (previously it
# exited the worker while the task stayed RUNNING, the silent-stall defect).
def test_r7_live_worker_active_tri_state_and_exit_reason(tmp_path):
    # --- sub A: preflight incomplete -> task PAUSED with a named failed read ---
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
    assert task_a["status"] == D.STATUS_PAUSED  # 不再静默 running（§5 可见暂停）
    assert task_a["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE
    assert "预检数据不完整" in (task_a["pause_reason_zh"] or "")
    # 失败读名：_FakeProvider(None) 无 last_failed_read → 通用文案；有失败读名时
    # 中文原因必须含读名（见 preflight-incomplete 专项测试）。
    events = svc_a.store.list_task_event_logs_page(
        50, ("preflight_incomplete",), None, None, None,
    )
    assert any(ev["kind"] == "preflight_incomplete" for ev in events)

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
    from backend.tests.fakes import RecordTransportFake
    svc = HedgeOpenTaskService(
        str(tmp_path / "dry.sqlite3"),
        executor=RecordTransportFake(),
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


# ---------------------------------------------------------------------------
# Stage 2026-08-06 task 05 §5: preflight failure is a VISIBLE pause (Human
# decision 4). The worker still exits WITHOUT retry, but the task pauses with a
# Chinese reason naming the failed read — no more 33-minute silent stall.
# ---------------------------------------------------------------------------
class _FailedReadProvider(_FakeProvider):
    last_failed_read = "balances"

    def get_snapshot(
        self, coin, direction, task_type="open", position_side_mode=None,
    ):
        return None  # preflight incomplete


def test_preflight_incomplete_pause_names_failed_read(tmp_path):
    exe = _RoutingExecutor()
    svc = _svc_with(str(tmp_path / "pf.sqlite3"), exe, _FailedReadProvider(), _Clock())
    svc.set_start_gate(True)
    doc = _create(svc, target_n=1)
    svc.post_start(doc["id"])  # RUNNING + real worker
    wa = svc._workers.get(doc["id"])
    if wa is not None:
        wa.join(timeout=5.0)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED  # 可见暂停，不再静默 running
    assert task["pause_reason"] == D.PAUSE_REASON_PREFLIGHT_INCOMPLETE
    assert "预检数据不完整" in (task["pause_reason_zh"] or "")
    assert "balances" in (task["pause_reason_zh"] or "")  # 失败读名必须出现
    # 事件落库（诊断事件带 failed_read + 暂停事件带 reason_zh）
    events = svc.store.list_task_event_logs_page(
        50, ("preflight_incomplete", "task_paused"), None, None, None,
    )
    payloads = [json.loads(ev["payload"]) for ev in events]
    assert any(p.get("failed_read") == "balances" for p in payloads)
    # 无重试：worker 退出后任务保持 paused（未被自动恢复/重发）。
    assert svc._worker_active_for(doc["id"]) is False


# ---------------------------------------------------------------------------
# Stage 2026-08-06 task 05 §4.1 (Human decision 2): the close-flat verification
# runs ONCE at the state-transition point (scheduled_attempt_count >= target_n),
# NOT every round. Ordinary rounds make ZERO query_symbol_um_qty calls.
# ---------------------------------------------------------------------------
def test_close_flat_verify_only_at_target_reached(tmp_path):
    exe = _RoutingExecutor()
    verify_calls = {"n": 0}

    def _verify(coin):
        verify_calls["n"] += 1
        return 0  # 合约无仓 → flat

    exe.query_symbol_um_qty = _verify
    svc = _svc_with(str(tmp_path / "close.sqlite3"), exe, _FakeProvider(_ok_snapshot()), _Clock())
    svc.set_start_gate(True)
    # 先建一个 open 周期（close 任务要求存在活跃周期）。
    od = svc.create_task({
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": "immediate",
        "single_amount": "0.5", "target_n": 1,
    })[1]
    exe.set_script(od["id"], [_accepted_pair(od["id"])])
    svc.post_start(od["id"])
    wo = svc._workers.get(od["id"])
    if wo is not None:
        wo.join(timeout=5.0)
    assert svc.store.get_active_cycle("BTCUSDT", "forward") is not None
    provider = svc._preflight
    provider.um_qty = Decimal("-10")  # 两轮发单前 UM 门走新鲜缓存，final 才实时查
    doc = svc.create_task({
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "mode": "immediate",
        "single_amount": "0.5", "target_n": 2, "task_type": "close",
    })[1]
    exe.set_script(doc["id"], [_accepted_pair(doc["id"]), _accepted_pair(doc["id"])])
    svc.post_start(doc["id"])
    wa = svc._workers.get(doc["id"])
    if wa is not None:
        wa.join(timeout=5.0)
    # 轮 1/2（scheduled 0→1→2）不 verify；轮 3（scheduled=2 >= target_n）恰好一次。
    assert verify_calls["n"] == 1, f"平完判定应只在次数用完那一轮调用一次: {verify_calls}"
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_DONE
    # 周期已关（auto_close）+ 结算日志写入。
    assert svc.store.get_active_cycle("BTCUSDT", "forward") is None
    close_logs = svc.store.list_close_logs()
    assert any(row["close_reason"] == D.CLOSE_REASON_AUTO_CLOSE for row in close_logs)
