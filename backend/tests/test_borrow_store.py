"""SQLite store tests for backend/borrow_tasks/store.py (breakdown §3.6/§3.8).

Deterministic, no network. Uses pytest's ``tmp_path`` (a TemporaryDirectory)
for the SQLite file. Covers restart durability, the fail-closed pending-attempt
recovery, every result-category effect on task/settings state, the
effective-gap computation, newest-completion-first cursor pagination, the
optimistic-concurrency edit conflict, and soft-deletion retaining attempts.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.borrow_tasks import domain as D
from backend.borrow_tasks.executor import ExecutorResult
from backend.borrow_tasks.store import (
    BorrowTaskStore,
    UnknownTaskError,
    VersionConflictError,
)

NOW = 1_784_448_000_000_000  # 2026-07-19T08:00:00Z


def _store(tmp_path):
    return BorrowTaskStore(str(tmp_path / "borrow.sqlite3"))


def _disabled():
    return ExecutorResult(result_category=D.RESULT_EXECUTION_DISABLED, reason="executor_disabled")


# ---------------------------------------------------------------------------
# Restart durability (acceptance 1)
# ---------------------------------------------------------------------------
def test_restart_preserves_tasks_settings_cursor_attempts(tmp_path):
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1.5", 3, NOW)
    s1.create_task("B", "ETH", "2", 2, NOW + 1)
    s1.set_task_status("B", "paused", NOW + 2)
    s1.update_settings("0.5", 500_000, NOW + 3)
    att = s1.insert_pending_attempt("A", "BTC", "1.5", NOW + 10, NOW + 11, "A")
    s1.resolve_attempt(att["id"], _disabled(), NOW + 12)
    s1.close()

    s2 = BorrowTaskStore(path)
    tasks = s2.list_tasks()
    assert [t["id"] for t in tasks] == ["A", "B"]
    assert tasks[1]["status"] == "paused"
    assert tasks[0]["latest_result_category"] == D.RESULT_EXECUTION_DISABLED
    settings = s2.get_settings()
    assert settings["interval_seconds"] == "0.5"
    assert settings["interval_us"] == 500_000
    assert settings["round_robin_cursor"] == "A"        # cursor survived
    # seed(1) + update_settings(2) + insert_pending_attempt cursor bump(3)
    assert settings["version"] == 3
    entries, has_more = s2.list_attempts_page(50, None, None)
    assert has_more is False
    assert len(entries) == 1
    assert entries[0]["result_category"] == D.RESULT_EXECUTION_DISABLED


def test_restart_fail_closed_blocks_pending_attempt(tmp_path):
    # A pending attempt orphaned by a crash blocks its task (breakdown §3.8).
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 1, NOW)
    s1.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")  # left pending
    s1.close()

    s2 = BorrowTaskStore(path)
    task = s2.get_task("A")
    assert task["unresolved_attempt_id"] is not None    # fail-closed
    assert s2.list_eligible_tasks() == []               # blocked -> ineligible


def test_restart_preserves_unknown_outcome_block(tmp_path):
    # A resolved ``unknown`` outcome must stay blocked across close/reopen
    # (acceptance 4 / §6.1-1 invariant-across-restart). Startup recovery adds
    # markers for orphaned pending attempts but must NOT clear an already-
    # persisted unknown-outcome marker (the bug it regresses wiped it to NULL
    # because the task has no pending row).
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 1, NOW)
    att = s1.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s1.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 12
    )
    assert s1.get_task("A")["unresolved_attempt_id"] == att["id"]
    assert s1.list_eligible_tasks() == []
    s1.close()

    s2 = BorrowTaskStore(path)
    task = s2.get_task("A")
    assert task["unresolved_attempt_id"] == att["id"]      # marker preserved, not wiped
    assert s2.list_eligible_tasks() == []                  # still ineligible after reopen
    s2.clear_unresolved("A", NOW + 30)                     # test seam -> eligible again
    assert [t["id"] for t in s2.list_eligible_tasks()] == ["A"]


# ---------------------------------------------------------------------------
# Settings seed + update (§3.5)
# ---------------------------------------------------------------------------
def test_settings_default_seed(tmp_path):
    s = _store(tmp_path)
    st = s.get_settings()
    assert st["interval_seconds"] == "5"
    assert st["interval_us"] == 5_000_000
    assert st["round_robin_cursor"] is None
    assert st["global_cooldown_until_us"] is None
    assert st["version"] == 1


def test_update_settings_bumps_version(tmp_path):
    s = _store(tmp_path)
    st = s.update_settings("0.5", 500_000, NOW)
    assert st["version"] == 2
    assert s.get_interval_us() == 500_000


# ---------------------------------------------------------------------------
# Task listing + eligibility (§3.3 / §3.8)
# ---------------------------------------------------------------------------
def test_list_tasks_creation_order_includes_soft_deleted(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.create_task("B", "ETH", "1", 1, NOW + 1)
    s.create_task("C", "XRP", "1", 1, NOW + 2)
    s.set_task_status("B", "deleted", NOW + 3)
    tasks = s.list_tasks()
    assert [t["id"] for t in tasks] == ["A", "B", "C"]  # creation order, deleted retained
    assert tasks[1]["status"] == "deleted"


def test_list_eligible_excludes_non_borrowing_and_unresolved(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)              # eligible
    s.create_task("B", "ETH", "1", 1, NOW + 1)          # eligible
    s.create_task("C", "XRP", "1", 1, NOW + 2)
    s.set_task_status("C", "paused", NOW + 3)           # paused -> excluded
    s.create_task("D", "SOL", "1", 1, NOW + 4)
    s.set_task_status("D", "deleted", NOW + 5)          # deleted -> excluded
    s.create_task("E", "ADA", "1", 1, NOW + 6)          # will be blocked
    att = s.insert_pending_attempt("E", "ADA", "1", NOW + 7, NOW + 8, "E")
    s.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 9
    )
    eligible = s.list_eligible_tasks()
    assert [t["id"] for t in eligible] == ["A", "B"]


# ---------------------------------------------------------------------------
# Resolution effects per category (§3.6 / §3.8)
# ---------------------------------------------------------------------------
def test_resolve_success_increments_then_completes(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 2, NOW)
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(a1["id"], ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id="t1"), NOW + 12)
    t = s.get_task("A")
    assert t["success_count"] == 1 and t["status"] == "borrowing"
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 20, NOW + 21, "A")
    s.resolve_attempt(a2["id"], ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id="t2"), NOW + 22)
    t = s.get_task("A")
    assert t["success_count"] == 2 and t["status"] == "completed"
    assert t["latest_result_tran_id"] == "t2"


def test_resolve_known_rejection_leaves_runnable(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(
        att["id"],
        ExecutorResult(result_category=D.RESULT_KNOWN_REJECTION, business_code="-2014", reason="r"),
        NOW + 12,
    )
    t = s.get_task("A")
    assert t["unresolved_attempt_id"] is None
    assert t["success_count"] == 0 and t["status"] == "borrowing"
    assert t["latest_result_category"] == D.RESULT_KNOWN_REJECTION
    assert t["latest_result_business_code"] == "-2014"


def test_resolve_rate_limited_sets_global_cooldown(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(
        att["id"],
        ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED, reason="rl", retry_after_seconds=Decimal("2")
        ),
        NOW + 12,
    )
    st = s.get_settings()
    assert st["global_cooldown_until_us"] == NOW + 12 + 2_000_000
    assert s.get_task("A")["status"] == "borrowing"     # still runnable later


def test_resolve_unknown_blocks_task(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 12
    )
    t = s.get_task("A")
    assert t["unresolved_attempt_id"] == att["id"]
    assert t["latest_result_category"] == D.RESULT_UNKNOWN


# ---------------------------------------------------------------------------
# Effective gap + pagination (§3.6, amendment §3)
# ---------------------------------------------------------------------------
def test_effective_gap_uses_previous_dispatched(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 100, "A")
    s.resolve_attempt(a1["id"], _disabled(), NOW + 200)
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 1000, NOW + 1100, "A")
    s.resolve_attempt(a2["id"], _disabled(), NOW + 1200)
    entries, _ = s.list_attempts_page(50, None, None)
    assert entries[0]["id"] == a2["id"]                 # newest first
    assert entries[0]["effective_gap_us"] == (NOW + 1100) - (NOW + 100)
    assert entries[1]["effective_gap_us"] is None       # first attempt


def test_pagination_newest_first_with_cursor_boundary(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 100, NOW)
    for i in range(5):
        att = s.insert_pending_attempt("A", "BTC", "1", NOW + i * 1000, NOW + i * 1000 + 10, "A")
        s.resolve_attempt(att["id"], _disabled(), NOW + i * 1000 + 20)
    page1, more1 = s.list_attempts_page(2, None, None)
    assert more1 is True
    assert [e["id"] for e in page1] == [5, 4]
    last = page1[-1]
    ets = D.effective_ts_us(last["finished_at_us"], last["dispatched_at_us"], last["scheduled_at_us"])
    page2, more2 = s.list_attempts_page(2, ets, last["id"])
    assert more2 is True
    assert [e["id"] for e in page2] == [3, 2]
    last = page2[-1]
    ets = D.effective_ts_us(last["finished_at_us"], last["dispatched_at_us"], last["scheduled_at_us"])
    page3, more3 = s.list_attempts_page(2, ets, last["id"])
    assert more3 is False
    assert [e["id"] for e in page3] == [1]


# ---------------------------------------------------------------------------
# Optimistic concurrency + soft delete (§3.4)
# ---------------------------------------------------------------------------
def test_edit_version_conflict_raises(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 3, NOW)              # version 1
    s.edit_task("A", "2", 3, 1, NOW + 1)                # -> version 2
    with pytest.raises(VersionConflictError):
        s.edit_task("A", "3", 3, 1, NOW + 2)            # stale version 1


def test_soft_delete_retains_attempts(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(att["id"], _disabled(), NOW + 12)
    s.set_task_status("A", "deleted", NOW + 20)
    entries, _ = s.list_attempts_page(50, None, None)
    assert len(entries) == 1                            # ledger untouched
    assert s.get_task("A")["status"] == "deleted"


def test_clear_unresolved_test_seam(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 12
    )
    assert s.list_eligible_tasks() == []
    s.clear_unresolved("A", NOW + 30)
    assert [t["id"] for t in s.list_eligible_tasks()] == ["A"]


def test_resolve_unknown_attempt_raises_for_missing(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(UnknownTaskError):
        s.resolve_attempt(999, _disabled(), NOW)
