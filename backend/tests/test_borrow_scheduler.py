"""Scheduler tests for backend/borrow_tasks (breakdown §3.8 / acceptance 2,4,5).

Drives ``BorrowTaskService.tick`` with an injected fake clock and a test-only
:class:`PaperBorrowExecutor` — no real scheduler thread, no network. Covers the
global decimal round-robin order, fractional-interval effective gaps, skipping
of paused/deleted/completed/blocked tasks, cursor survival across restart, the
cooldown gate, the per-task at-most-one-unresolved invariant, and completion.
"""
from __future__ import annotations

from backend.borrow_tasks import domain as D
from backend.borrow_tasks.executor import ExecutorResult
from backend.borrow_tasks.scheduler import select_next_task
from backend.borrow_tasks.service import BorrowTaskService
from backend.tests.borrow_paper_executor import (
    PaperBorrowExecutor,
    execution_disabled,
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


def test_scheduler_skips_paused_deleted_completed_blocked(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([execution_disabled()] * 10)
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "1"})
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
    # block E with an unknown outcome
    att_e = svc.store.insert_pending_attempt(e_blocked, "ADA", "1", NOW_US, NOW_US + 1, e_blocked)
    svc.store.resolve_attempt(att_e["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="u"), NOW_US + 2)
    assert svc.store.get_task(e_blocked)["unresolved_attempt_id"] is not None

    # Only A is eligible -> A is the sole task rotated across both ticks.
    clock.t = 0
    svc.tick()
    clock.t = 1_000_000
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
    exe = PaperBorrowExecutor([])
    svc = _service(tmp_path, exe, clock)
    status, doc = svc.put_settings({"interval_seconds": "0.5"})
    assert status == 200 and doc["interval_us"] == 500_000
    _create(svc, "BTC", target=10)
    for t in (0, 500_000, 1_000_000):
        clock.t = t
        svc.tick()
    _status, page = svc.get_logs(None, None)
    entries = page["entries"]                          # newest first
    assert [e["effective_gap_us"] for e in entries] == [500_000, 500_000, None]


# ---------------------------------------------------------------------------
# Cooldown gate (acceptance 5)
# ---------------------------------------------------------------------------
def test_rate_limit_cooldown_suppresses_until_expiry(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([rate_limited(retry_after_seconds=10), execution_disabled()])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "1"})
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
# Unknown blocks only its task; others rotate; seam unblocks (acceptance 4)
# ---------------------------------------------------------------------------
def test_unknown_blocks_only_its_task_and_seam_unblocks(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor(
        [unknown(), execution_disabled(), execution_disabled(), execution_disabled()]
    )
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "1"})
    ids = [_create(svc, a) for a in ("BTC", "ETH", "XRP")]
    clock.t = 0
    svc.tick()                        # A -> unknown -> blocked
    clock.t = 1_000_000
    svc.tick()                        # B
    clock.t = 2_000_000
    svc.tick()                        # C
    clock.t = 3_000_000
    svc.tick()                        # B again (A blocked, cursor C wraps to B)
    order = [task_id for (task_id, _a, _c) in exe.calls]
    assert order == [ids[0], ids[1], ids[2], ids[1]]
    assert svc.store.get_task(ids[0])["unresolved_attempt_id"] is not None
    svc.clear_unresolved(ids[0])
    assert svc.store.get_task(ids[0])["unresolved_attempt_id"] is None


# ---------------------------------------------------------------------------
# Success increments + completion stops dispatch (acceptance 5)
# ---------------------------------------------------------------------------
def test_success_completes_and_stops_dispatch(tmp_path):
    clock = FakeClock(0)
    exe = PaperBorrowExecutor([success(), success(), success()])
    svc = _service(tmp_path, exe, clock)
    svc.put_settings({"interval_seconds": "1"})
    a = _create(svc, "BTC", target=2)
    clock.t = 0
    svc.tick()                        # success_count 1
    clock.t = 1_000_000
    svc.tick()                        # success_count 2 -> completed
    clock.t = 2_000_000
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
    svc.put_settings({"interval_seconds": "1"})
    clock.t = 0
    assert svc.tick() is False
    assert svc.store.get_settings()["round_robin_cursor"] is None
    paused = _create(svc, "BTC")
    svc.post_pause(paused)
    clock.t = 1_000_000
    assert svc.tick() is False
    assert exe.calls == []
