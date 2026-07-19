"""Borrow executor seam — the no-network port (breakdown §3.9).

The executor returns a typed :class:`ExecutorResult` rather than an HTTP
object. In A+B the only runtime-reachable executor is
:class:`DisabledBorrowExecutor`, which performs zero I/O. The test-only
``PaperBorrowExecutor`` lives in ``backend/tests/borrow_paper_executor.py`` so
no runtime configuration can ever select it.

Neither executor performs network I/O, signing, or any call to Binance. This
module imports only :mod:`decimal` and :mod:`dataclasses`; it must never import
network or signing primitives (grep proof, breakdown §5.1-9).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .domain import RESULT_EXECUTION_DISABLED


@dataclass(frozen=True)
class ExecutorResult:
    """Frozen executor result fields (the sanitized vocabulary of §3.6)."""

    result_category: str
    business_code: str | None = None
    reason: str | None = None
    http_status: int | None = None
    tran_id: str | None = None
    retry_after_seconds: Decimal | None = None


class BorrowExecutor(Protocol):
    """Executor port. ``execute`` must not hold a store transaction/lock."""

    def execute(self, task: dict, attempt: dict) -> ExecutorResult: ...


class DisabledBorrowExecutor:
    """The ONLY executor reachable from configuration in A+B.

    Returns ``execution_disabled`` with no network I/O. Every scheduled backend
    attempt therefore persists one sanitized ``execution_disabled`` row and
    never contacts Binance; it is not a browser simulation.
    """

    def execute(self, task: dict, attempt: dict) -> ExecutorResult:
        return ExecutorResult(
            result_category=RESULT_EXECUTION_DISABLED,
            reason="executor_disabled",
        )
