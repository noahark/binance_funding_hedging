"""Test-only paper borrow executor (breakdown §3.9).

Lives in the test tree (NOT in the product package) so no runtime configuration
can ever select it. Tests inject it through the ``BorrowTaskService`` constructor.
It replays a scripted deterministic result list covering every §3.6 category and
performs zero network I/O.
"""
from __future__ import annotations

from decimal import Decimal

from backend.borrow_tasks import domain as D
from backend.borrow_tasks.executor import ExecutorResult


def success(tran_id: str = "paper-1") -> ExecutorResult:
    return ExecutorResult(result_category=D.RESULT_SUCCESS, tran_id=tran_id)


def known_rejection(business_code: str = "-2014", reason: str = "not_vip_qualified") -> ExecutorResult:
    return ExecutorResult(
        result_category=D.RESULT_KNOWN_REJECTION,
        business_code=business_code,
        reason=reason,
    )


def rate_limited(retry_after_seconds=2, reason: str = "rate_limited") -> ExecutorResult:
    return ExecutorResult(
        result_category=D.RESULT_RATE_LIMITED,
        reason=reason,
        retry_after_seconds=Decimal(str(retry_after_seconds)),
    )


def unknown(reason: str = "unknown_outcome") -> ExecutorResult:
    return ExecutorResult(result_category=D.RESULT_UNKNOWN, reason=reason)


def execution_disabled() -> ExecutorResult:
    return ExecutorResult(
        result_category=D.RESULT_EXECUTION_DISABLED, reason="executor_disabled"
    )


class PaperBorrowExecutor:
    """Replay a scripted result list; hold the last result once exhausted."""

    def __init__(self, results):
        self._results = list(results)
        self._index = 0
        self.calls: list = []

    def execute(self, task: dict, attempt: dict) -> ExecutorResult:
        if not self._results:
            result = execution_disabled()
        else:
            result = self._results[min(self._index, len(self._results) - 1)]
        self._index += 1
        self.calls.append((task["id"], attempt["id"], result.result_category))
        return result
