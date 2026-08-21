"""Scheduler tests for backend/borrow_tasks (breakdown §3.8 / acceptance 2,4,5).

Drives ``BorrowTaskService.tick`` with an injected fake clock and a test-only
:class:`PaperBorrowExecutor` — no real scheduler thread, no network. Covers the
global decimal round-robin order, fractional-interval effective gaps, skipping
of paused/deleted/completed/blocked tasks, cursor survival across restart, the
cooldown gate, the per-task at-most-one-unresolved invariant, and completion.
"""
from __future__ import annotations

import threading

import pytest

from backend.borrow_tasks import domain as D
from backend.borrow_tasks.executor import ExecutorResult
from backend.borrow_tasks.scheduler import select_next_task
from backend.borrow_tasks.service import BorrowTaskService
from backend.tests.borrow_paper_executor import (
    PaperBorrowExecutor,
    execution_disabled,
    known_rejection,
    rate_limited,
    success,
    unknown,
)

NOW_US = 1_784_448_000_000_000  # 2026-07-19T08:00:00Z (store wall timestamps)


class FakeClock:
    """Single time source used as both monotonic and wall clock in tests."""

    def __init__(self, t0: int = 0):
        self.t = t0

    def mono_us(self) -> int:
        return self.t

    def wall_us(self) -> int:
        return self.t


def _service(tmp_path, executor, clock):
    return BorrowTaskService(
        str(tmp_path / "borrow.sqlite3"),
        executor=executor,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )


def _create(svc, asset, target=5):
    status, doc = svc.create_task({"asset": asset, "amount_per_attempt": "1", "success_target": target})
    assert status == 201
    return doc["id"]


# ---------------------------------------------------------------------------
# Pure selection function
# ---------------------------------------------------------------------------
def _t(task_id, seq):
    return {"id": task_id, "creation_seq": seq}


def test_select_next_task_order_and_wrap():
    a, b, c = _t("A", 1), _t("B", 2), _t("C", 3)
    assert select_next_task([a, b, c], None)["id"] == "A"
    assert select_next_task([a, b, c], "A")["id"] == "B"
    assert select_next_task([a, b, c], "B")["id"] == "C"
    assert select_next_task([a, b, c], "C")["id"] == "A"   # wrap
    assert select_next_task([], None) is None


def test_select_next_task_cursor_points_at_removed_task():
    # cursor references a task no longer eligible (deleted) -> restart from first
    b, c = _t("B", 2), _t("C", 3)
    assert select_next_task([b, c], "A")["id"] == "B"


# ---------------------------------------------------------------------------
# Round-robin A -> B -> C -> A on a 3s setting (acceptance 2)
# ---------------------------------------------------------------------------
def test_round_robin_abc_at_3s(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "3"})
    ids = [_create(svc, a) for a in ("BTC", "ETH", "XRP")]
    for t in (0, 3_000_000, 6_000_000, 9_000_000):
        clock.t = t
        svc.tick()
    order = [task_id for (task_id, _att, _cat) in exe.calls]
    assert order == [ids[0], ids[1], ids[2], ids[0]]


def test_scheduler_skips_paused_deleted_completed_and_in_flight(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([execution_disabled()] * 10)
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    a = _create(svc, "BTC")            # stays eligible
    b_paused = _create(svc, "ETH")
    c_deleted = _create(svc, "XRP")
    d_completed = _create(svc, "SOL", target=1)
    e_blocked = _create(svc, "ADA")

    # Put B/C/D/E into the four non-eligible states directly via the store
    # (these states are not reachable by ticks in A+B; the point is that the
    # scheduler selection skips every one of them).
    svc.store.set_task_status(b_paused, D.STATUS_PAUSED, NOW_US)
    svc.store.set_task_status(c_deleted, D.STATUS_DELETED, NOW_US)
    # complete D with one store-level success
    att_d = svc.store.insert_pending_attempt(d_completed, "SOL", "1", NOW_US, NOW_US + 1, d_completed)
    svc.store.resolve_attempt(att_d["id"], ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id="t"), NOW_US + 2)
    assert svc.store.get_task(d_completed)["status"] == D.STATUS_COMPLETED
    # block E by leaving an attempt in flight (an unknown RESULT no longer
    # blocks — DEC-2026-08-21 — but a dispatch still in flight does)
    svc.store.insert_pending_attempt(e_blocked, "ADA", "1", NOW_US, NOW_US + 1, e_blocked)
    assert svc.store.get_task(e_blocked)["unresolved_attempt_id"] is not None

    # Only A is eligible -> A is the sole task rotated across both ticks.
    clock.t = 0
    svc.tick()
    clock.t = 2_000_000
    svc.tick()
    order = [task_id for (task_id, _a, _c) in exe.calls]
    assert order == [a, a]


def test_cursor_survives_restart_mid_cycle(tmp_path):
    path = str(tmp_path / "borrow.sqlite3")
    clock = FakeClock(0)
    svc = _service(tmp_path, PaperBorrowExecutor([]), clock)
    svc.put_settings({"interval_seconds": "3"})
    ids = [_create(svc, a) for a in ("BTC", "ETH", "XRP")]
    clock.t = 0
    svc.tick()                       # A dispatched, cursor -> A
    svc.close()

    clock2 = FakeClock(3_000_000)
    exe2 = PaperBorrowExecutor([])
    svc2 = BorrowTaskService(
        path, executor=exe2, mono_us=clock2.mono_us, wall_us=clock2.wall_us
    )
    svc2.tick()                      # cursor was A -> next is B
    order = [task_id for (task_id, _a, _c) in exe2.calls]
    assert order == [ids[1]]


# ---------------------------------------------------------------------------
# Fractional interval + observable effective gap (acceptance 2)
# ---------------------------------------------------------------------------
def test_fractional_interval_stored_and_effective_gap(tmp_path):
    clock = FakeClock(0)
    # Distinct results so same-failure coalesce does not collapse gap rows.
    exe = PaperBorrowExecutor([
        execution_disabled(),
        known_rejection(business_code="51061", reason="known_rejection:51061"),
        rate_limited(),
    ])
    svc = _service(tmp_path, exe, clock)
    status, doc = svc.put_settings({"interval_seconds": "2.5"})
    assert status == 200 and doc["interval_us"] == 2_500_000
    _create(svc, "BTC", target=10)
    for t in (0, 2_500_000, 5_000_000):
        clock.t = t
        svc.tick()
    _status, page = svc.get_logs(None, None)
    entries = page["entries"]                          # newest first
    assert [e["effective_gap_us"] for e in entries] == [2_500_000, 2_500_000, None]


# ---------------------------------------------------------------------------
# Cooldown gate (acceptance 5)
# ---------------------------------------------------------------------------
def test_rate_limit_cooldown_suppresses_until_expiry(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([rate_limited(retry_after_seconds=10), execution_disabled()])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC", target=10)
    clock.t = 0
    assert svc.tick() is True                          # rate_limited -> cooldown set
    clock.t = 1_000_000
    assert svc.tick() is False                         # suppressed (cooldown future)
    clock.t = 5_000_000
    assert svc.tick() is False                         # still suppressed
    clock.t = 11_000_000
    assert svc.tick() is True                          # cooldown expired -> dispatch
    assert len(exe.calls) == 2                         # only the two real dispatches


# ---------------------------------------------------------------------------
# Unknown keeps its task in the rotation (DEC-2026-08-21)
# ---------------------------------------------------------------------------
def test_unknown_keeps_its_task_in_the_rotation(tmp_path):
    # DEC-2026-08-21: an unconfirmed POST is treated as "did not borrow", so the
    # task keeps its slot in the round robin instead of dropping out of it.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor(
        [unknown(), execution_disabled(), execution_disabled(), execution_disabled()]
    )
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    ids = [_create(svc, a) for a in ("BTC", "ETH", "XRP")]
    for i, t in enumerate((0, 2_000_000, 4_000_000, 6_000_000)):
        clock.t = t
        svc.tick()
    order = [task_id for (task_id, _a, _c) in exe.calls]
    assert order == [ids[0], ids[1], ids[2], ids[0]]   # A comes back around
    assert svc.store.get_task(ids[0])["unresolved_attempt_id"] is None


# ---------------------------------------------------------------------------
# Success increments + completion stops dispatch (acceptance 5)
# ---------------------------------------------------------------------------
def test_success_completes_and_stops_dispatch(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success(), success(), success()])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    a = _create(svc, "BTC", target=2)
    clock.t = 0
    svc.tick()                        # success_count 1
    clock.t = 2_000_000
    svc.tick()                        # success_count 2 -> completed
    clock.t = 4_000_000
    assert svc.tick() is False        # completed -> not eligible -> no dispatch
    task = svc.store.get_task(a)
    assert task["status"] == "completed"
    assert task["success_count"] == 2
    assert len(exe.calls) == 2


# ---------------------------------------------------------------------------
# No eligible tick records nothing and keeps the cursor (§3.8)
# ---------------------------------------------------------------------------
def test_no_eligible_tick_records_nothing_and_keeps_cursor(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    clock.t = 0
    assert svc.tick() is False
    assert svc.store.get_settings()["round_robin_cursor"] is None
    paused = _create(svc, "BTC")
    svc.post_pause(paused)
    clock.t = 1_000_000
    assert svc.tick() is False
    assert exe.calls == []


# ===========================================================================
# Boundary C: ownership, live gates, no-catch-up, one-shot, containment
# ===========================================================================

def _live_service(tmp_path, executor, clock, *, credentials_present=True, db_path=None):
    return BorrowTaskService(
        db_path or str(tmp_path / "borrow.sqlite3"),
        executor=executor,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
        mode="live",
        credentials_present=credentials_present,
    )


def test_non_owner_startup_does_not_touch_the_owners_in_flight_attempt(tmp_path):
    # DEC-2026-08-21 startup recovery clears in-flight markers and finalizes
    # pending attempts, so it MUST be owner-gated: a non-owner opening the same
    # DB while the owner is mid-POST would strip the owner's marker, after which
    # clear_attempt_logs deletes the row the owner is about to resolve — and a
    # real tranId success is lost with resolve_attempt raising into a swallowed
    # except. The store is therefore opened only after the ownership lock.
    path = str(tmp_path / "borrow.sqlite3")
    clock = FakeClock(0)

    class BlockingExecutor:
        """Blocks inside execute() until released, so a POST is genuinely in flight."""

        def __init__(self):
            self.entered = threading.Event()
            self.release = threading.Event()

        def execute(self, task, attempt):
            self.entered.set()
            # No timeout: the POST must not self-release and let a slow runner
            # race past the non-owner assertions below.
            self.release.wait()
            return success()

    exe = BlockingExecutor()
    owner = BorrowTaskService(
        path, executor=exe, mono_us=clock.mono_us, wall_us=clock.wall_us
    )
    assert owner.is_execution_owner is True
    tid = _create(owner, "BTC")

    t = threading.Thread(target=owner.tick, daemon=True)
    t.start()
    try:
        assert exe.entered.wait(10) is True                # POST is in flight
        in_flight_id = owner.store.get_task(tid)["unresolved_attempt_id"]
        assert in_flight_id is not None

        # A second process starts against the same DB while the POST is in flight.
        non_owner = BorrowTaskService(
            path, executor=PaperBorrowExecutor([]), mono_us=clock.mono_us, wall_us=clock.wall_us
        )
        try:
            assert non_owner.is_execution_owner is False
            # The owner's marker survives, so a log wipe cannot delete the pending row.
            assert non_owner.store.get_task(tid)["unresolved_attempt_id"] == in_flight_id
            assert non_owner.store.clear_attempt_logs()["retained_unresolved_count"] == 1
        finally:
            non_owner.close()
    finally:
        exe.release.set()
        t.join(10)
    assert t.is_alive() is False                           # the tick really finished
    # The real tranId success was recorded, not lost.
    task = owner.store.get_task(tid)
    assert task["success_count"] == 1
    assert task["unresolved_attempt_id"] is None
    owner.close()


def test_second_process_is_non_owner_and_never_dispatches(tmp_path):
    # §4.3: a second BorrowTaskService on the same DB cannot acquire the sidecar
    # lock, so it serves APIs but never dispatches — not even on a forced tick.
    path = str(tmp_path / "borrow.sqlite3")
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()])
    owner = BorrowTaskService(
        path, executor=exe, mono_us=clock.mono_us, wall_us=clock.wall_us
    )
    assert owner.is_execution_owner is True
    _create(owner, "BTC")
    clock.t = 0
    owner.tick()                       # owner dispatches one attempt
    assert len(exe.calls) == 1

    # A second service on the SAME path is the non-owner.
    exe2 = PaperBorrowExecutor([success()])
    non_owner = BorrowTaskService(
        path, executor=exe2, mono_us=clock.mono_us, wall_us=clock.wall_us
    )
    assert non_owner.is_execution_owner is False
    clock.t = 1_000_000
    assert non_owner.tick() is False    # forced tick as non-owner -> no dispatch
    assert exe2.calls == []             # zero dispatches, zero signed POSTs
    owner.close()
    non_owner.close()


def test_live_mode_without_credentials_dispatches_nothing(tmp_path):
    # §4.2 dual layer: live mode + missing credentials -> the service gate blocks
    # in _dispatch_one before any attempt row or executor call (layer 1); the
    # executor's own credentials gate is layer 2. Together: zero signed POSTs.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()] * 5)
    svc = _live_service(tmp_path, exe, clock, credentials_present=False)
    svc.store.set_execution_enabled(True, NOW_US)   # globally started
    _create(svc, "BTC")
    clock.t = 0
    assert svc.tick() is False
    assert exe.calls == []                          # zero executor calls -> zero POSTs
    status = svc.get_execution_status()[1]
    assert status["block_reason"] == D.BLOCK_BORROW_CREDENTIALS_MISSING
    assert status["can_execute"] is False
    svc.close()


def test_live_mode_globally_stopped_dispatches_nothing(tmp_path):
    # §3.3: even with credentials + ownership, execution_enabled=0 blocks the
    # atomic insert (live_gates) -> zero rows, zero POSTs.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()])
    svc = _live_service(tmp_path, exe, clock)
    _create(svc, "BTC")                             # execution_enabled defaults to 0
    clock.t = 0
    assert svc.tick() is False
    assert exe.calls == []
    svc.close()


def test_live_mode_unauthorized_task_dispatches_nothing(tmp_path):
    # Review-2 P1 regression: a borrowing task with live_authorized=0
    # (migrated/inconsistent) must fail the atomic live gate inside
    # insert_pending_attempt — zero attempt rows and zero executor POSTs — even
    # with execution enabled, credentials present, and ownership held.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()])
    svc = _live_service(tmp_path, exe, clock)
    svc.store.set_execution_enabled(True, NOW_US)
    tid = _create(svc, "BTC")                       # live_authorized=1 by Confirm
    svc.store.set_task_status(tid, D.STATUS_BORROWING, NOW_US, live_authorized=0)
    clock.t = 0
    assert svc.tick() is False
    assert exe.calls == []                          # zero signed POSTs
    entries, _ = svc.store.list_attempts_page(50, None, None)
    assert entries == []                            # zero attempt rows persisted
    svc.close()


def test_live_mode_authorized_task_dispatches_once(tmp_path):
    # Positive control: live_authorized=1 with every gate open passes the atomic
    # live_authorized recheck inside the transaction and dispatches exactly once.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()])
    svc = _live_service(tmp_path, exe, clock)
    svc.store.set_execution_enabled(True, NOW_US)
    _create(svc, "BTC")                             # live_authorized=1 by Confirm
    clock.t = 0
    assert svc.tick() is True
    assert len(exe.calls) == 1
    svc.close()


@pytest.mark.parametrize(
    "result",
    [
        success(),
        known_rejection(),
        rate_limited(retry_after_seconds=2),
        unknown(),
        execution_disabled(),
    ],
    ids=["success", "known_rejection", "rate_limited", "unknown", "execution_disabled"],
)
def test_one_executor_call_per_tick_regardless_of_category(tmp_path, result):
    # §5.2 one-shot: every result category produces exactly ONE executor call and
    # ONE ledger row per tick; the scheduler never re-dispatches the same attempt.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([result])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC", target=10)
    clock.t = 0
    svc.tick()
    assert len(exe.calls) == 1
    page = svc.get_logs(None, None)[1]
    assert len(page["entries"]) == 1
    svc.close()


def test_missed_time_is_not_replayed_as_a_burst(tmp_path):
    # §9-6: _last_tick_mono advances to `now` (not now+interval), so a large clock
    # jump yields at most ONE dispatch per tick — never a burst of catch-up POSTs.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()] * 100)
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC", target=100)
    clock.t = 0
    svc.tick()                                    # dispatch 1, _last_tick_mono = 0
    clock.t = 1_000_000_000                       # ~16 min of "missed" 1s ticks
    svc.tick()                                    # one catch-up tick -> ONE dispatch
    assert len(exe.calls) == 2
    svc.close()


def test_executor_exception_is_contained_as_unknown(tmp_path):
    # §5.2 containment: an executor.execute() exception maps to unknown and
    # never propagates out of tick.
    class BoomExecutor:
        def execute(self, task, attempt):
            raise RuntimeError("boom")

    clock = FakeClock(0)
    svc = _service(tmp_path, BoomExecutor(), clock)
    svc.put_settings({"interval_seconds": "2"})
    tid = _create(svc, "BTC", target=10)
    clock.t = 0
    assert svc.tick() is True                      # did not raise; dispatch happened
    task = svc.store.get_task(tid)
    assert task["unresolved_attempt_id"] is None          # unknown does not block
    assert task["latest_result_category"] == D.RESULT_UNKNOWN
    entry = svc.get_logs(None, None)[1]["entries"][0]
    assert entry["reason"].startswith("executor_exception")
    svc.close()


def test_store_resolve_exception_does_not_kill_tick(tmp_path):
    # §5.2 belt-and-braces: if resolve_attempt itself raises, the tick swallows it
    # (attempt stays pending, task stays blocked) and the scheduler survives.
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success()])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC", target=10)

    def boom(*_a, **_kw):
        raise RuntimeError("resolve blew up")

    svc.store.resolve_attempt = boom               # inject a raising resolve
    clock.t = 0
    assert svc.tick() is True                       # dispatch happened; resolve contained
    svc.close()


def test_post_start_at_target_completes_instead_of_borrowing(tmp_path):
    # §5.4 belt+braces: a paused task already at its target completes on Start
    # rather than moving to borrowing (so it cannot receive an extra POST). This
    # exact state is unreachable through the public matrix (a success at target
    # always completes a runnable task), so it is set up directly here.
    clock = FakeClock(0)
    svc = _service(tmp_path, PaperBorrowExecutor([]), clock)
    tid = _create(svc, "BTC", target=2)
    svc.store.set_task_status(tid, D.STATUS_PAUSED, NOW_US)
    with svc.store._conn:                           # test-only: count == target, paused
        svc.store._conn.execute(
            "UPDATE borrow_task SET success_count = success_target WHERE id = ?",
            (tid,),
        )
    status, doc = svc.post_start(tid)
    assert status == 200
    assert doc["status"] == D.STATUS_COMPLETED
    assert doc["live_authorized"] is True
    svc.close()
