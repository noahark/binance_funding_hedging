"""Unit tests for backend.ledger_flow.scheduler (design §15.1 / §15.3).

The cadence decision is pure and clock-driven; these tests inject a fake
service + an explicit ``now`` and assert ``decide`` / ``_startup_catchup``
without starting any thread. Covers the four decide gates, the all-met→
``scheduled`` path, the three startup-catchup branches, and ``stop()``
idempotency. (Added by the review-1 fix round — F2.)
"""
from __future__ import annotations

import pytest

from backend.ledger_flow.scheduler import LedgerScheduler

_H = 60 * 60 * 1000
_MIN = 60 * 1000


class _FakeService:
    """Controls the scheduler's service queries; records run_once calls."""

    def __init__(self):
        self.had_success = False
        self.attempts = 0
        self.last_attempt = None
        self.last_success = None
        self.coverage = False
        self.runs = []
        self.seen_since = None  # last since_ms passed to the hour queries

    def had_successful_run_since(self, since_ms):
        self.seen_since = since_ms
        return self.had_success

    def count_attempts_since(self, since_ms):
        return self.attempts

    def last_attempt_finished_since(self, since_ms):
        return self.last_attempt

    def last_successful_finished(self):
        return self.last_success

    def coverage_exists(self):
        return self.coverage

    def run_once(self, kind):
        self.runs.append(kind)
        return {"run": {"id": 1, "kind": kind, "finished_at_ms": 0,
                        "interest_status": "ok", "interest_error": None,
                        "income_status": "ok", "income_error": None,
                        "truncated": 0}, "interest_new": 0, "income_new": 0}


def _sched(svc):
    # now_ms is unused for decide/startup tests (they take an explicit now).
    return LedgerScheduler(svc, now_ms=lambda: 0)


# --------------------------------------------------------------------------- #
# decide: the four gates + the all-met path
# --------------------------------------------------------------------------- #
def test_decide_not_due_before_minute_one():
    svc = _FakeService()
    sch = _sched(svc)
    now = 100 * _H  # exactly on the hour -> minute-of-hour 0
    assert (now // 60000) % 60 == 0
    assert sch.decide(now) == (False, None)
    assert svc.runs == []


def test_decide_not_due_when_hour_already_has_success():
    svc = _FakeService()
    svc.had_success = True
    sch = _sched(svc)
    now = 100 * _H + 5 * _MIN  # minute 5
    assert sch.decide(now) == (False, None)
    # decide passes the natural-hour start as the since bound.
    assert svc.seen_since == 100 * _H


def test_decide_not_due_when_attempt_budget_exhausted():
    svc = _FakeService()
    svc.attempts = 3  # first try + two retries already this hour
    sch = _sched(svc)
    now = 100 * _H + 5 * _MIN
    assert sch.decide(now) == (False, None)


def test_decide_not_due_within_five_minutes_of_last_attempt():
    svc = _FakeService()
    svc.last_attempt = 100 * _H + 3 * _MIN  # 2 minutes before now
    sch = _sched(svc)
    now = 100 * _H + 5 * _MIN
    assert sch.decide(now) == (False, None)


def test_decide_due_when_all_gates_open():
    svc = _FakeService()
    sch = _sched(svc)
    now = 100 * _H + 6 * _MIN  # minute 6, no success, no attempts
    assert sch.decide(now) == (True, "scheduled")


def test_decide_due_again_five_minutes_after_a_failed_attempt():
    svc = _FakeService()
    svc.last_attempt = 100 * _H + 1 * _MIN  # 5 minutes before now (exactly)
    sch = _sched(svc)
    now = 100 * _H + 6 * _MIN
    # now - last == 5min, which is not < 5min -> the retry gate is open.
    assert sch.decide(now) == (True, "scheduled")


# --------------------------------------------------------------------------- #
# _startup_catchup: three branches
# --------------------------------------------------------------------------- #
def test_startup_catchup_empty_ledger_runs_backfill():
    svc = _FakeService()  # last_success None, coverage False
    sch = _sched(svc)
    sch._startup_catchup()
    assert svc.runs == ["backfill"]


def test_startup_catchup_stale_with_coverage_runs_startup_catchup():
    svc = _FakeService()
    now = 100 * _H
    svc.last_success = now - 2 * _H  # older than an hour
    svc.coverage = True
    sch = LedgerScheduler(svc, now_ms=lambda: now)
    sch._startup_catchup()
    assert svc.runs == ["startup_catchup"]


def test_startup_catchup_recent_does_not_run():
    svc = _FakeService()
    now = 100 * _H
    svc.last_success = now - 30 * _MIN  # within the hour
    svc.coverage = True
    sch = LedgerScheduler(svc, now_ms=lambda: now)
    sch._startup_catchup()
    assert svc.runs == []


# --------------------------------------------------------------------------- #
# stop() idempotency
# --------------------------------------------------------------------------- #
def test_stop_is_idempotent_and_safe_before_start():
    svc = _FakeService()
    sch = _sched(svc)
    # stop() without start() must not raise.
    sch.stop()
    sch.stop()  # idempotent
    assert svc.runs == []
