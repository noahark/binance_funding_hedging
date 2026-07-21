"""Borrow executor seam — the no-network port (breakdown §3.9).

The executor returns a typed :class:`ExecutorResult` rather than an HTTP
object. The runtime-reachable executors are :class:`DisabledBorrowExecutor`
(zero I/O) and, only under explicit live configuration,
:class:`backend.services.live_borrow_executor.LiveBorrowExecutor`. The test-only
``PaperBorrowExecutor`` lives in ``backend/tests/borrow_paper_executor.py`` so
no runtime configuration can ever select it.

This module imports only :mod:`decimal` and :mod:`dataclasses`; it must never
import network or signing primitives (grep proof, breakdown §5.1-9).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Protocol

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


@dataclass(frozen=True)
class ReconcileOutcome:
    """Outcome of one loan-record reconciliation read (Boundary C §5.3).

    ``matched=True`` only for a unique ``CONFIRMED`` record whose ``txId`` is a
    valid positive integer. ``rate_limited=True`` means the reconciliation GET
    itself was rate-limited (the service extends the shared cooldown and retries
    the same step later, without advancing the reconcile schedule).
    ``requires_rearm=True`` means the rate-limit was a 418 ban whose manual re-arm
    requirement must be persisted by the service (a reconciliation GET can observe
    a 418 just like a POST; the durable ``requires_rearm`` flag must not be lost).
    """

    matched: bool
    tran_id: str | None = None
    rate_limited: bool = False
    retry_after_seconds: Decimal | None = None
    requires_rearm: bool = False


class BorrowExecutor(Protocol):
    """Executor port. ``execute`` must not hold a store transaction/lock.

    ``reconcile`` returns ``None`` when the executor cannot reconcile at all
    (disabled / non-live); otherwise a :class:`ReconcileOutcome` for one read.
    """

    def execute(self, task: dict, attempt: dict) -> ExecutorResult: ...

    def reconcile(self, task: dict, attempt: dict) -> Optional[ReconcileOutcome]: ...


class DisabledBorrowExecutor:
    """The default executor: zero I/O, zero signed traffic.

    Returns ``execution_disabled`` with no network I/O and cannot reconcile.
    Every scheduled backend attempt therefore persists one sanitized
    ``execution_disabled`` row and never contacts Binance; it is not a browser
    simulation.
    """

    def execute(self, task: dict, attempt: dict) -> ExecutorResult:
        return ExecutorResult(
            result_category=RESULT_EXECUTION_DISABLED,
            reason="executor_disabled",
        )

    def reconcile(self, task: dict, attempt: dict) -> Optional[ReconcileOutcome]:
        return None
