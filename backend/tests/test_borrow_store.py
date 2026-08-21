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
    s1.update_settings("2.5", 2_500_000, NOW + 3)
    att = s1.insert_pending_attempt("A", "BTC", "1.5", NOW + 10, NOW + 11, "A")
    s1.resolve_attempt(att["id"], _disabled(), NOW + 12)
    s1.close()

    s2 = BorrowTaskStore(path)
    tasks = s2.list_tasks()
    # Newest first (B created after A).
    assert [t["id"] for t in tasks] == ["B", "A"]
    assert tasks[0]["status"] == "paused"
    assert tasks[1]["latest_result_category"] == D.RESULT_EXECUTION_DISABLED
    settings = s2.get_settings()
    assert settings["interval_seconds"] == "2.5"
    assert settings["interval_us"] == 2_500_000
    assert settings["round_robin_cursor"] == "A"        # cursor survived
    # seed(1) + update_settings(2) + insert_pending_attempt cursor bump(3)
    assert settings["version"] == 3
    entries, has_more = s2.list_attempts_page(50, None, None)
    assert has_more is False
    assert len(entries) == 1
    assert entries[0]["result_category"] == D.RESULT_EXECUTION_DISABLED


def test_restart_releases_orphaned_pending_attempt(tmp_path):
    # DEC-2026-08-21: a pending attempt orphaned by a crash is recorded as a
    # response-less unknown and its task RELEASED — only a POST that returned a
    # usable loan id counts as borrowed, so an unconfirmed one is treated as
    # "did not borrow" rather than stalling the task indefinitely.
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 1, NOW)
    s1.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")  # left pending
    s1.close()

    s2 = BorrowTaskStore(path)
    assert s2.get_task("A")["unresolved_attempt_id"] is None
    assert [t["id"] for t in s2.list_eligible_tasks()] == ["A"]
    att = s2.list_attempts_page(50, None, None)[0][0]
    assert att["outcome"] == D.OUTCOME_RESOLVED
    assert att["result_category"] == D.RESULT_UNKNOWN
    assert att["reason"] == D.REASON_CRASH_ORPHAN_RESPONSELESS  # audit trail kept


# ---------------------------------------------------------------------------
# Settings seed + update (§3.5)
# ---------------------------------------------------------------------------
def test_settings_default_seed(tmp_path):
    s = _store(tmp_path)
    st = s.get_settings()
    assert st["interval_seconds"] == "1"
    assert st["interval_us"] == 1_000_000
    assert st["round_robin_cursor"] is None
    assert st["global_cooldown_until_us"] is None
    assert st["version"] == 1


def test_update_settings_bumps_version(tmp_path):
    s = _store(tmp_path)
    st = s.update_settings("2.5", 2_500_000, NOW)
    assert st["version"] == 2
    assert s.get_interval_us() == 2_500_000


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
    # Newest first for UI listing; soft-deleted rows stay in the list.
    assert [t["id"] for t in tasks] == ["C", "B", "A"]
    assert tasks[1]["status"] == "deleted"


def test_clear_attempt_logs_keeps_unresolved_marker(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.create_task("B", "ETH", "1", 1, NOW + 1)
    # Finished attempt on A
    att_a = s.insert_pending_attempt("A", "BTC", "1", NOW + 2, NOW + 3, "A")
    s.resolve_attempt(att_a["id"], _disabled(), NOW + 4)
    # In-flight (still pending) on B — must be retained: deleting it would
    # break the resolve that is about to land.
    att_b = s.insert_pending_attempt("B", "ETH", "1", NOW + 5, NOW + 6, "B")
    page, _ = s.list_attempts_page(50, None, None)
    assert len(page) >= 2
    result = s.clear_attempt_logs()
    assert result["deleted_count"] >= 1
    assert result["retained_unresolved_count"] == 1
    page2, _ = s.list_attempts_page(50, None, None)
    assert len(page2) == 1
    assert page2[0]["id"] == att_b["id"]
    # In-flight marker still points at the retained row
    task_b = s.get_task("B")
    assert task_b["unresolved_attempt_id"] == att_b["id"]


def test_list_eligible_excludes_non_borrowing_but_not_unknown(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)              # eligible
    s.create_task("B", "ETH", "1", 1, NOW + 1)          # eligible
    s.create_task("C", "XRP", "1", 1, NOW + 2)
    s.set_task_status("C", "paused", NOW + 3)           # paused -> excluded
    s.create_task("D", "SOL", "1", 1, NOW + 4)
    s.set_task_status("D", "deleted", NOW + 5)          # deleted -> excluded
    s.create_task("E", "ADA", "1", 1, NOW + 6)          # unknown -> still eligible
    att = s.insert_pending_attempt("E", "ADA", "1", NOW + 7, NOW + 8, "E")
    s.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 9
    )
    # F: in flight right now -> excluded until its resolve lands.
    s.create_task("F", "DOT", "1", 1, NOW + 10)
    s.insert_pending_attempt("F", "DOT", "1", NOW + 11, NOW + 12, "F")
    eligible = s.list_eligible_tasks()
    assert [t["id"] for t in eligible] == ["A", "B", "E"]


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


def test_resolve_unknown_does_not_block_task(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.resolve_attempt(
        att["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk"), NOW + 12
    )
    t = s.get_task("A")
    assert t["unresolved_attempt_id"] is None            # DEC-2026-08-21: not blocked
    assert [x["id"] for x in s.list_eligible_tasks()] == ["A"]
    assert t["latest_result_category"] == D.RESULT_UNKNOWN


# ---------------------------------------------------------------------------
# Effective gap + pagination (§3.6, amendment §3)
# ---------------------------------------------------------------------------
def test_effective_gap_uses_previous_dispatched(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 100, "A")
    s.resolve_attempt(a1["id"], _disabled(), NOW + 200)
    # Distinct failure reason so the second row is not coalesced away.
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 1000, NOW + 1100, "A")
    s.resolve_attempt(
        a2["id"],
        ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
            business_code="51061",
            reason="known_rejection:51061",
        ),
        NOW + 1200,
    )
    entries, _ = s.list_attempts_page(50, None, None)
    assert entries[0]["id"] == a2["id"]                 # newest first
    assert entries[0]["effective_gap_us"] == (NOW + 1100) - (NOW + 100)
    assert entries[1]["effective_gap_us"] is None       # first attempt


def test_pagination_newest_first_with_cursor_boundary(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 100, NOW)
    # Distinct reasons so coalesce does not collapse the page set.
    for i in range(5):
        att = s.insert_pending_attempt("A", "BTC", "1", NOW + i * 1000, NOW + i * 1000 + 10, "A")
        s.resolve_attempt(
            att["id"],
            ExecutorResult(
                result_category=D.RESULT_KNOWN_REJECTION,
                business_code=str(51000 + i),
                reason=f"known_rejection:{51000 + i}",
            ),
            NOW + i * 1000 + 20,
        )
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


def test_same_failure_coalesces_updates_finished_at_only(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    rej = ExecutorResult(
        result_category=D.RESULT_KNOWN_REJECTION,
        business_code="51061",
        reason="known_rejection:51061",
    )
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 100, "A")
    r1 = s.resolve_attempt(a1["id"], rej, NOW + 200)
    assert r1["id"] == a1["id"]
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 1000, NOW + 1100, "A")
    r2 = s.resolve_attempt(a2["id"], rej, NOW + 1200)
    # Second attempt deleted; first row kept with bumped finished_at.
    assert r2["id"] == a1["id"]
    assert r2["finished_at_us"] == NOW + 1200
    assert r2["dispatched_at_us"] == NOW + 100  # first-seen dispatch kept
    assert r2["result_category"] == D.RESULT_KNOWN_REJECTION
    assert r2["business_code"] == "51061"
    entries, _ = s.list_attempts_page(50, None, None)
    assert len(entries) == 1
    assert entries[0]["id"] == a1["id"]
    assert entries[0]["finished_at_us"] == NOW + 1200
    t = s.get_task("A")
    assert t["unresolved_attempt_id"] is None
    assert t["latest_result_finished_at_us"] == NOW + 1200
    assert t["latest_result_category"] == D.RESULT_KNOWN_REJECTION
    assert s.get_attempt(a2["id"]) is None


def test_different_failure_reason_does_not_coalesce(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 10, "A")
    s.resolve_attempt(
        a1["id"],
        ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
            business_code="51061",
            reason="known_rejection:51061",
        ),
        NOW + 20,
    )
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 100, NOW + 110, "A")
    s.resolve_attempt(
        a2["id"],
        ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
            business_code="51006",
            reason="known_rejection:51006",
        ),
        NOW + 120,
    )
    entries, _ = s.list_attempts_page(50, None, None)
    assert len(entries) == 2
    assert {e["business_code"] for e in entries} == {"51061", "51006"}


def test_success_after_failure_is_own_row_then_failure_again_new_cluster(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    rej = ExecutorResult(
        result_category=D.RESULT_KNOWN_REJECTION,
        business_code="51061",
        reason="known_rejection:51061",
    )
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 10, "A")
    s.resolve_attempt(a1["id"], rej, NOW + 20)
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 100, NOW + 110, "A")
    s.resolve_attempt(
        a2["id"],
        ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id="t1"),
        NOW + 120,
    )
    a3 = s.insert_pending_attempt("A", "BTC", "1", NOW + 200, NOW + 210, "A")
    s.resolve_attempt(a3["id"], rej, NOW + 220)
    a4 = s.insert_pending_attempt("A", "BTC", "1", NOW + 300, NOW + 310, "A")
    r4 = s.resolve_attempt(a4["id"], rej, NOW + 320)
    # Rows: fail#1, success, fail#2 (a4 coalesced into a3)
    entries, _ = s.list_attempts_page(50, None, None)
    assert len(entries) == 3
    assert r4["id"] == a3["id"]
    assert r4["finished_at_us"] == NOW + 320
    cats = [e["result_category"] for e in entries]
    assert cats == [
        D.RESULT_KNOWN_REJECTION,
        D.RESULT_SUCCESS,
        D.RESULT_KNOWN_REJECTION,
    ]


def test_unknown_does_not_coalesce(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    a1 = s.insert_pending_attempt("A", "BTC", "1", NOW, NOW + 10, "A")
    s.resolve_attempt(
        a1["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="u"), NOW + 20
    )
    a2 = s.insert_pending_attempt("A", "BTC", "1", NOW + 100, NOW + 110, "A")
    s.resolve_attempt(
        a2["id"], ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="u"), NOW + 120
    )
    entries, _ = s.list_attempts_page(50, None, None)
    assert len(entries) == 2


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


def test_resolve_unknown_attempt_raises_for_missing(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(UnknownTaskError):
        s.resolve_attempt(999, _disabled(), NOW)


# ===========================================================================
# Boundary C: live-authorization, durable Start/Stop, resolve matrix, migration
# ===========================================================================

def _success(tran_id="t-1"):
    return ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id=tran_id)


def _unknown():
    return ExecutorResult(result_category=D.RESULT_UNKNOWN, reason="unk")


def test_new_task_is_live_authorized_for_dispatch(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 2, NOW)
    task = s.get_task("A")
    assert task["live_authorized"] == 1
    # eligible by default (borrowing, authorized, below target, no unresolved)
    assert [t["id"] for t in s.list_eligible_tasks()] == ["A"]


def test_success_after_delete_stays_deleted_count_increments(tmp_path):
    # §5.4 resolve matrix (defense-in-depth): if the operator deletes a task
    # while an attempt is already in flight, the success that lands afterwards
    # keeps status=deleted but the real success is still audited (+1).
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 5, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s.set_task_status("A", D.STATUS_DELETED, NOW + 12)  # delete in-flight
    s.resolve_attempt(att["id"], _success(), NOW + 13)
    task = s.get_task("A")
    assert task["status"] == D.STATUS_DELETED  # matrix: deleted stays deleted
    assert task["success_count"] == 1          # success still audited/incremented


def test_resolve_status_matrix_is_fail_closed():
    # §5.4: deleted/completed are terminal (never reopen); reaching target
    # completes a runnable task; otherwise the current status is preserved.
    # (Some of these branches are unreachable through the store API alone — a
    # paused task cannot have a new attempt inserted — so the matrix itself is
    # the unit under test here.)
    from backend.borrow_tasks.store import _resolve_status

    assert _resolve_status(D.STATUS_DELETED, 3, 1) == D.STATUS_DELETED
    assert _resolve_status(D.STATUS_COMPLETED, 0, 5) == D.STATUS_COMPLETED
    assert _resolve_status(D.STATUS_BORROWING, 5, 5) == D.STATUS_COMPLETED
    assert _resolve_status(D.STATUS_BORROWING, 4, 5) == D.STATUS_BORROWING
    assert _resolve_status(D.STATUS_PAUSED, 5, 5) == D.STATUS_COMPLETED
    assert _resolve_status(D.STATUS_PAUSED, 1, 5) == D.STATUS_PAUSED


# ---- durable global Start/Stop + rate cooldown ----

def test_execution_enabled_defaults_false_and_toggle(tmp_path):
    s = _store(tmp_path)
    settings = s.get_settings()
    assert settings["execution_enabled"] == 0
    assert settings["requires_rearm"] == 0
    assert s.count_live_authorized_tasks() == 0
    s.create_task("A", "BTC", "1", 1, NOW)
    assert s.count_live_authorized_tasks() == 1
    s.set_execution_enabled(True, NOW)
    assert s.get_settings()["execution_enabled"] == 1
    s.set_execution_enabled(False, NOW + 1)
    assert s.get_settings()["execution_enabled"] == 0


def test_start_does_not_bypass_active_418_cooldown_or_rearm(tmp_path):
    # §5.1: a manual Start must NOT clear an active cooldown or a 418 ban whose
    # 300s minimum has not elapsed. 418 fires at NOW+5 -> cooldown ends at
    # NOW+5+300s; a Start at NOW+6 is far inside that window.
    s = _store(tmp_path)
    s.set_execution_enabled(True, NOW)
    s.create_task("A", "BTC", "1", 1, NOW + 2)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 3, NOW + 4, "A")
    s.resolve_attempt(
        att["id"],
        ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=418,
            retry_after_seconds=Decimal("300"),
        ),
        NOW + 5,
    )
    st = s.get_settings()
    assert st["requires_rearm"] == 1
    cooldown_until = st["global_cooldown_until_us"]
    assert cooldown_until == NOW + 5 + 300 * 1_000_000
    # Early Start (inside the 300s window) clears NOTHING except execution_enabled.
    s.set_execution_enabled(True, NOW + 6)
    st = s.get_settings()
    assert st["execution_enabled"] == 1
    assert st["requires_rearm"] == 1                          # still armed
    assert st["global_cooldown_until_us"] == cooldown_until   # cooldown untouched
    # A live-gated insert stays blocked (both cooldown and rearm still active).
    blocked = s.insert_pending_attempt("A", "BTC", "1", NOW + 8, NOW + 9, "A", live_gates=True)
    assert blocked is None


def test_start_after_418_cooldown_expiry_rearms_and_clears(tmp_path):
    # §5.1: 418 requires BOTH local 300s expiry AND a subsequent manual Start;
    # local expiry alone never auto-resumes.
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A")
    s.resolve_attempt(
        att["id"],
        ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=418,
            retry_after_seconds=Decimal("300"),
        ),
        NOW + 3,
    )
    assert s.get_settings()["requires_rearm"] == 1
    # After 300s elapsed but BEFORE any Start: still armed (no auto-resume).
    after_expiry = NOW + 3 + 300 * 1_000_000 + 1
    assert s.get_settings()["requires_rearm"] == 1
    # The manual Start after expiry is the single re-arm exit.
    s.set_execution_enabled(True, after_expiry)
    st = s.get_settings()
    assert st["requires_rearm"] == 0
    assert st["global_cooldown_until_us"] is None
    assert st["execution_enabled"] == 1


def _rate_limit_via_resolve(s, task_id, asset, retry_seconds, finished_us, http_status=None):
    """Drive the production rate-limit path: resolve a rate_limited attempt.

    The store's ``set_rate_cooldown`` / ``set_requires_rearm`` setters existed
    only for the reconciliation pass and were removed with it (DEC-2026-08-21);
    cooldown and 418 re-arm now persist solely through ``resolve_attempt``.
    """
    att = s.insert_pending_attempt(task_id, asset, "1", finished_us - 2, finished_us - 1, task_id)
    s.resolve_attempt(
        att["id"],
        ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=http_status,
            retry_after_seconds=Decimal(retry_seconds),
        ),
        finished_us,
    )


def test_start_does_not_bypass_ordinary_rate_cooldown(tmp_path):
    # An ordinary 429/-1003 cooldown (no rearm) is also not bypassed by Start.
    s = _store(tmp_path)
    s.set_execution_enabled(True, NOW)
    s.create_task("A", "BTC", "1", 1, NOW + 1)
    _rate_limit_via_resolve(s, "A", "BTC", 120, NOW + 2)  # cooldown ends NOW+2+120s
    cooldown_until = s.get_settings()["global_cooldown_until_us"]
    # Early Start inside the ordinary cooldown: cooldown preserved.
    s.set_execution_enabled(True, NOW + 3)
    assert s.get_settings()["global_cooldown_until_us"] == cooldown_until
    assert s.get_settings()["execution_enabled"] == 1


def test_count_pending_orphan_attempts_reports_this_startups_orphans(tmp_path):
    # The sanitized startup integer answers "how many borrows did the previous
    # process leave unconfirmed" — each is one balance for Human to check.
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 3, NOW)
    assert s1.count_pending_orphan_attempts() == 0        # nothing recovered
    s1.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A")  # left pending
    assert s1.count_pending_orphan_attempts() == 0        # not yet a restart
    s1.close()

    s2 = BorrowTaskStore(path)
    assert s2.count_pending_orphan_attempts() == 1        # recovered on this startup
    s2.close()

    s3 = BorrowTaskStore(path)
    assert s3.count_pending_orphan_attempts() == 0        # idempotent: nothing new


# ---- atomic live-gate insert returns None on every failed predicate ----

def test_insert_pending_live_gates_block_when_globally_stopped(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.set_execution_enabled(False, NOW)  # explicitly stopped
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A", live_gates=True)
    assert att is None  # zero row, zero POST


def test_insert_pending_live_gates_block_in_cooldown(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.set_execution_enabled(True, NOW)
    _rate_limit_via_resolve(s, "A", "BTC", 120, NOW + 1)  # cooldown active at NOW+1
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 2, NOW + 3, "A", live_gates=True)
    assert att is None


def test_insert_pending_live_gates_block_when_rearm_required(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.set_execution_enabled(True, NOW)
    # Force requires_rearm by resolving a 418
    att0 = s.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A")
    s.resolve_attempt(
        att0["id"],
        ExecutorResult(result_category=D.RESULT_RATE_LIMITED, http_status=418,
                       retry_after_seconds=Decimal("300")),
        NOW + 3,
    )
    blocked = s.insert_pending_attempt("A", "BTC", "1", NOW + 5, NOW + 6, "A", live_gates=True)
    assert blocked is None  # rearm gate blocks even though eligible otherwise


def test_insert_pending_live_gates_block_when_not_live_authorized(tmp_path):
    # Review-2 P1: a borrowing task with live_authorized=0 (migrated/inconsistent
    # state) must fail the atomic live gate INSIDE the transaction — zero attempt
    # row — even with execution enabled and no cooldown/rearm. The pre-fix code
    # selected live_authorized but never checked it under live_gates.
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.set_task_status("A", D.STATUS_BORROWING, NOW, live_authorized=0)
    s.set_execution_enabled(True, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A", live_gates=True)
    assert att is None
    entries, _ = s.list_attempts_page(50, None, None)
    assert entries == []                       # zero attempt rows persisted


def test_insert_pending_live_gates_pass_when_all_open(tmp_path):
    s = _store(tmp_path)
    s.create_task("A", "BTC", "1", 1, NOW)
    s.set_execution_enabled(True, NOW)
    att = s.insert_pending_attempt("A", "BTC", "1", NOW + 1, NOW + 2, "A", live_gates=True)
    assert att is not None
    assert att["outcome"] == D.OUTCOME_PENDING



# ---------------------------------------------------------------------------
# Crash-orphan pending attempts are recorded and released (DEC-2026-08-21)
# ---------------------------------------------------------------------------
def test_restart_orphan_pending_is_recorded_as_responseless_unknown(tmp_path):
    # A crash-orphaned pending attempt (insert committed, resolve never ran) is
    # recorded at startup as a response-less unknown so the borrow log shows
    # which POST was never confirmed — and the task is released (DEC-2026-08-21).
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 1, NOW)
    s1.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")  # orphaned pending
    s1.close()

    s2 = BorrowTaskStore(path)
    assert s2.get_task("A")["unresolved_attempt_id"] is None
    assert [t["id"] for t in s2.list_eligible_tasks()] == ["A"]
    att = s2.list_attempts_page(50, None, None)[0][0]
    assert att["outcome"] == D.OUTCOME_RESOLVED
    assert att["result_category"] == D.RESULT_UNKNOWN
    assert att["reason"] == D.REASON_CRASH_ORPHAN_RESPONSELESS
    assert att["finished_at_us"] is not None


def test_restart_orphan_recovery_is_idempotent(tmp_path):
    # Recovery only touches outcome='pending' rows, so a second startup finds
    # none and does not rewrite the already-recorded orphan.
    path = str(tmp_path / "borrow.sqlite3")
    s1 = BorrowTaskStore(path)
    s1.create_task("A", "BTC", "1", 1, NOW)
    s1.insert_pending_attempt("A", "BTC", "1", NOW + 10, NOW + 11, "A")
    s1.close()

    s2 = BorrowTaskStore(path)
    first = s2.list_attempts_page(50, None, None)[0][0]
    assert first["outcome"] == D.OUTCOME_RESOLVED          # transitioned on first startup
    s2.close()

    s3 = BorrowTaskStore(path)
    second = s3.get_attempt(first["id"])
    assert second["outcome"] == D.OUTCOME_RESOLVED
    assert second["finished_at_us"] == first["finished_at_us"]   # not re-anchored
    assert second["reason"] == first["reason"]
    # Still exactly one attempt row (no duplication).
    entries, has_more = s3.list_attempts_page(50, None, None)
    assert has_more is False
    assert len(entries) == 1


# ---- idempotent migration from a raw pre-C database ----

def test_migration_quarantines_pre_c_borrowing_and_is_idempotent(tmp_path):
    """Build a pre-C DB by raw SQL (no live_authorized column), then open via the
    store: borrowing -> paused once, live_authorized=0, counts/logs preserved;
    re-opening is a no-op (PRAGMA user_version gate)."""
    import sqlite3
    path = str(tmp_path / "prec.sqlite3")
    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE borrow_task (
            id TEXT PRIMARY KEY, asset TEXT, amount_per_attempt TEXT,
            success_target INTEGER, success_count INTEGER, status TEXT,
            version INTEGER, creation_seq INTEGER, created_at_us INTEGER,
            updated_at_us INTEGER, unresolved_attempt_id INTEGER,
            latest_result_category TEXT, latest_result_business_code TEXT,
            latest_result_reason TEXT, latest_result_tran_id TEXT,
            latest_result_finished_at_us INTEGER
        );
        CREATE TABLE borrow_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, asset TEXT,
            sequence INTEGER, outcome TEXT, result_category TEXT,
            business_code TEXT, reason TEXT, http_status INTEGER, tran_id TEXT,
            requested_amount TEXT, scheduled_at_us INTEGER, dispatched_at_us INTEGER,
            finished_at_us INTEGER, latency_ms INTEGER, effective_gap_us INTEGER
        );
        CREATE TABLE borrow_settings (
            id INTEGER PRIMARY KEY, interval_seconds TEXT, interval_us INTEGER,
            round_robin_cursor TEXT, global_cooldown_until_us INTEGER,
            version INTEGER, updated_at_us INTEGER
        );
        INSERT INTO borrow_settings VALUES (1, '5', 5000000, NULL, NULL, 1, 0);
        INSERT INTO borrow_task VALUES (
            'A', 'BTC', '1', 3, 1, 'borrowing', 1, 1, 0, 0, NULL,
            NULL, NULL, NULL, NULL, NULL);
        """
    )
    raw.commit()
    raw.close()

    s = BorrowTaskStore(path)
    task = s.get_task("A")
    assert task["status"] == D.STATUS_PAUSED  # quarantined once
    assert task["live_authorized"] == 0        # NOT auto-authorized
    assert task["success_count"] == 1          # count preserved
    assert s.list_eligible_tasks() == []       # paused + unauthorized -> ineligible
    assert s._conn.execute("PRAGMA user_version").fetchone()[0] == 1

    # re-open: idempotent (no double-quarantine, still paused)
    s.close()
    s2 = BorrowTaskStore(path)
    assert s2.get_task("A")["status"] == D.STATUS_PAUSED
    assert s2.get_task("A")["live_authorized"] == 0
    s2.close()


# ===========================================================================
# Cross-task attribution gate (§5.3 / risk §11 — no false cross-task credit)
# ===========================================================================
