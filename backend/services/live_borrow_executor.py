"""Typed live borrow executor (Boundary C §5) — injected through the executor seam.

Wraps :class:`PortfolioMarginBorrowClient` and maps every transport/exchange
observation into the frozen :class:`ExecutorResult` vocabulary (deny by
default). It performs NO classification of its own beyond the archived rules:
success requires a valid normalized ``tranId``; ``known_rejection`` is exactly
``-51006/-51014/-51061``; ``-1003``/429/418 are rate-limited; everything else
(timeout, connection loss, malformed/empty 2xx, 5xx, unlisted 4xx, exceptions)
is ``unknown``.

Reconciliation (§5.3) queries the loan-record endpoint and proves success only
on a unique ``CONFIRMED`` record whose ``asset`` and ``Decimal(principal)`` match
the dispatched attempt exactly. Zero / multiple / cross-task ambiguity returns
``matched=False``; a rate-limited reconciliation GET surfaces so the service can
extend the shared cooldown without advancing the reconcile step.

This module lives under ``backend/services/`` (it imports the network transport
and the shared signer) and is injected via ``BorrowTaskService(executor=...)``;
``backend/borrow_tasks/**`` never imports it.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from ..borrow_tasks import domain as D
from ..borrow_tasks.executor import ExecutorResult, ReconcileOutcome
from .portfolio_margin_borrow_client import BorrowHttpResponse, PortfolioMarginBorrowClient

# The frozen known-rejection set (Boundary C §5.1). Every other 4xx -> unknown.
_KNOWN_REJECTION_CODES = {"-51006", "-51014", "-51061"}
# -1003 TOO_MANY_REQUESTS is verified; its exact PAPI HTTP representation is not,
# so HTTP 400 body code -1003 OR HTTP 429 are both rate-limited.
_RATE_LIMIT_BODY_CODE = "-1003"
# 418 ban: 300s minimum local cooldown, no auto-resume (manual re-arm only).
_BAN_COOLDOWN_SECONDS = Decimal("300")
# Bounded dispatch-anchored reconciliation window (local conservative policy,
# not a Binance SLA). The archived selection contract caps a window at 30 days.
_RECONCILE_WINDOW_BACKSTEP_MS = 1_000
_RECONCILE_WINDOW_SPAN_MS = 30 * 86_400 * 1_000


def _business_code(response: BorrowHttpResponse) -> Optional[str]:
    body = response.body
    if isinstance(body, dict):
        code = body.get("code")
        if code is not None:
            return str(code)
    return None


def _normalize_tran_id(value) -> Optional[str]:
    """Arbitrary-precision-positive-integer -> canonical string; never float.

    ``tranId`` is documented int64; JSON may deliver it as an int or a numeric
    string. Anything non-positive, non-integer, empty, or unparseable is rejected
    so a malformed/empty 2xx never counts as success.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError):
            return None
        if not parsed.is_finite() or parsed <= 0:
            return None
        if parsed != parsed.to_integral_value():
            return None
        return format(parsed.to_integral_value(), "f")
    return None


def _clamped_retry_after(raw_seconds: Optional[int]) -> Decimal:
    """Thin shim over the shared ``D.clamp_retry_after`` (kept for the §5.1 name)."""
    return D.clamp_retry_after(raw_seconds)


def _decimal_equal(principal_raw, requested_amount: str) -> bool:
    """Exact Decimal equality of the loan-record principal vs requested amount."""
    if principal_raw is None:
        return False
    try:
        return Decimal(str(principal_raw)) == Decimal(str(requested_amount))
    except (InvalidOperation, ValueError, TypeError):
        return False


# Frozen loan-record row contract (archived Query Margin Loan Record evidence;
# breakdown §5.3). Every returned row must satisfy all five fields before it may
# be used as success proof; one malformed member fails the whole read closed.
_LOAN_RECORD_STATUSES = ("PENDING", "CONFIRMED", "FAILED")


def _is_int64_like(value) -> bool:
    """``txId``/``timestamp`` are documented int64: a non-bool int or an
    int-valued numeric string. ``bool`` is rejected (it subclasses ``int``)."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError):
            return False
        return parsed.is_finite() and parsed == parsed.to_integral_value()
    return False


def _row_timestamp_ms(row) -> Optional[int]:
    """Return a row's ``timestamp`` as an int (ms), or ``None`` if not int64-like."""
    ts = row.get("timestamp")
    if not _is_int64_like(ts):
        return None
    if isinstance(ts, int):
        return ts
    return int(Decimal(ts.strip()).to_integral_value())


def _row_contract_valid(row) -> bool:
    """A row proves nothing unless every frozen field parses safely.

    ``txId`` (positive int64), ``asset`` (non-empty string), ``principal``
    (finite decimal), ``timestamp`` (int64), and ``status`` (frozen enum) must
    all be present and contract-valid. Any single malformed row fails the entire
    read closed — it is never silently filtered away to prove success.
    """
    if not isinstance(row, dict):
        return False
    if _normalize_tran_id(row.get("txId")) is None:
        return False
    asset = row.get("asset")
    if not isinstance(asset, str) or not asset:
        return False
    principal = row.get("principal")
    if principal is None or isinstance(principal, bool):
        return False
    try:
        amount = Decimal(str(principal))
    except (InvalidOperation, ValueError, TypeError):
        return False
    if not amount.is_finite():
        return False
    if not _is_int64_like(row.get("timestamp")):
        return False
    if row.get("status") not in _LOAN_RECORD_STATUSES:
        return False
    return True


def classify_post_response(response: BorrowHttpResponse) -> ExecutorResult:
    """Map a POST /papi/v1/marginLoan response to the frozen result vocabulary."""
    if response.transport_error is not None or response.http_status is None:
        return ExecutorResult(
            result_category=D.RESULT_UNKNOWN,
            http_status=None,
            reason=f"transport_error:{response.transport_error or 'none'}",
        )
    status = response.http_status
    code = _business_code(response)
    if status == 429 or (status == 400 and code == _RATE_LIMIT_BODY_CODE):
        return ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=status,
            reason="rate_limited_429_or_1003",
            business_code=code,
            retry_after_seconds=_clamped_retry_after(response.retry_after_seconds),
        )
    if status == 418:
        return ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=418,
            reason="rate_limited_418_ban",
            retry_after_seconds=_BAN_COOLDOWN_SECONDS,
        )
    if code in _KNOWN_REJECTION_CODES:
        return ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
            http_status=status,
            business_code=code,
            reason=f"known_rejection:{code}",
        )
    if 200 <= status < 300:
        tran_id = None
        if isinstance(response.body, dict):
            tran_id = _normalize_tran_id(response.body.get("tranId"))
        if tran_id is not None:
            return ExecutorResult(
                result_category=D.RESULT_SUCCESS,
                http_status=status,
                tran_id=tran_id,
                reason="post_success_tran_id",
            )
        return ExecutorResult(
            result_category=D.RESULT_UNKNOWN,
            http_status=status,
            reason="malformed_2xx_no_tranid",
        )
    return ExecutorResult(
        result_category=D.RESULT_UNKNOWN,
        http_status=status,
        business_code=code,
        reason=f"unlisted_http_{status}",
    )


def classify_reconcile_response(response: BorrowHttpResponse) -> Optional[ExecutorResult]:
    """If a reconciliation GET is itself rate-limited, surface it; else ``None``.

    A rate-limited GET must not advance the reconcile step; the service extends
    the shared cooldown and retries the same step later.
    """
    if response.transport_error is not None or response.http_status is None:
        return None
    status = response.http_status
    code = _business_code(response)
    if status == 429 or (status == 400 and code == _RATE_LIMIT_BODY_CODE):
        return ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=status,
            reason="reconcile_rate_limited",
            business_code=code,
            retry_after_seconds=_clamped_retry_after(response.retry_after_seconds),
        )
    if status == 418:
        return ExecutorResult(
            result_category=D.RESULT_RATE_LIMITED,
            http_status=418,
            reason="reconcile_rate_limited_418_ban",
            retry_after_seconds=_BAN_COOLDOWN_SECONDS,
        )
    return None


class LiveBorrowExecutor:
    """Production executor over the exact-path PM borrow client."""

    def __init__(self, client: PortfolioMarginBorrowClient, *, now_ms: Callable[[], int]):
        self._client = client
        self._now_ms = now_ms

    @property
    def credentials_present(self) -> bool:
        return self._client.credentials_present

    def execute(self, task: dict, attempt: dict) -> ExecutorResult:
        # Belt-and-braces credentials gate (§4.2): the service already refuses to
        # dispatch without credentials, but the executor never trusts that and
        # refuses to send a signed POST with empty keys regardless of caller.
        if not self._client.credentials_present:
            return ExecutorResult(
                result_category=D.RESULT_EXECUTION_DISABLED,
                reason="borrow_credentials_missing",
            )
        response = self._client.post_margin_loan(
            task["asset"],
            attempt["requested_amount"],
            timestamp_ms=self._now_ms(),
        )
        return classify_post_response(response)

    def reconcile(self, task: dict, attempt: dict) -> Optional[ReconcileOutcome]:
        """Query the loan-record endpoint; prove success only on a unique match.

        A response-less unknown is queried over a bounded dispatch-anchored
        ``startTime``/``endTime`` window whose ``endTime`` never exceeds the signed
        request timestamp and whose span never exceeds the archived 30-day cap. A
        known ``tranId`` uses the precise ``txId`` selection instead.

        Success is proven only when ALL of the following hold (any miss stays
        blocked): the body is the ``{"rows": [...], "total": N}`` envelope; the
        declared ``total`` exactly equals the number of raw rows returned (a single
        inspected page proves global uniqueness only at exact equality — missing /
        bool / non-int / negative ``total``, or ``total`` above OR below the raw
        row count, all fail closed); EVERY returned row satisfies the frozen field
        contract (``txId``/``asset``/``principal``/``timestamp``/``status``) so a
        malformed member is never silently dropped to prove success; exactly one
        contract-valid ``CONFIRMED`` row matches asset + exact Decimal principal;
        on the known-ID path the candidate's canonical ``txId`` equals the posted
        ``tranId``; on the response-less path the candidate ``timestamp`` falls
        inside the dispatched ``[startTime, endTime]`` window. A rate-limited read
        (429/-1003/418) surfaces without advancing the reconcile step; a 418 ban
        additionally carries the manual-rearm requirement through to the store.
        """
        if not self._client.credentials_present:
            return None
        asset = task["asset"]
        requested_amount = attempt["requested_amount"]
        dispatched_at_us = attempt.get("dispatched_at_us")
        known_tran_id = attempt.get("tran_id")
        ts_ms = self._now_ms()
        start_ms: Optional[int] = None
        end_ms: Optional[int] = None
        if known_tran_id:
            response = self._client.fetch_loan_records(
                asset, timestamp_ms=ts_ms, tx_id=str(known_tran_id)
            )
        else:
            anchor_ms = dispatched_at_us // 1000 if dispatched_at_us else ts_ms
            # Dispatch-anchored window: endTime never later than the signed request
            # timestamp; span capped at the archived 30-day maximum so the query
            # never asks Binance for records newer than the request itself.
            window_floor_ms = ts_ms - _RECONCILE_WINDOW_SPAN_MS
            start_ms = max(anchor_ms - _RECONCILE_WINDOW_BACKSTEP_MS, window_floor_ms)
            end_ms = ts_ms
            response = self._client.fetch_loan_records(
                asset,
                timestamp_ms=ts_ms,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        rate_limited = classify_reconcile_response(response)
        if rate_limited is not None:
            return ReconcileOutcome(
                matched=False,
                rate_limited=True,
                retry_after_seconds=rate_limited.retry_after_seconds,
                requires_rearm=rate_limited.http_status == 418,
            )
        raw_rows = PortfolioMarginBorrowClient.raw_rows(response)
        total = PortfolioMarginBorrowClient.declared_total(response)
        # Envelope completeness + pagination fail-closed (§5.3): a single
        # inspected page proves global uniqueness only when the declared total
        # exactly equals the raw row count. Missing/bool/non-int/negative total
        # (-> None) and any total != raw row count (above OR below) stay blocked.
        if raw_rows is None or total is None or total != len(raw_rows):
            return ReconcileOutcome(matched=False)
        # Frozen row contract: every returned row must carry all five fields in
        # contract-valid form. One malformed member fails the whole read closed —
        # it is never filtered away to prove success on the remainder.
        for row in raw_rows:
            if not _row_contract_valid(row):
                return ReconcileOutcome(matched=False)
        confirmed = [
            r for r in raw_rows
            if r.get("status") == "CONFIRMED"
            and str(r.get("asset")) == asset
            and _decimal_equal(r.get("principal"), requested_amount)
        ]
        if len(confirmed) != 1:
            return ReconcileOutcome(matched=False)
        candidate = confirmed[0]
        tran_id = _normalize_tran_id(candidate.get("txId"))
        if tran_id is None:
            return ReconcileOutcome(matched=False)
        # Known-ID fast path (§5.3): the response candidate must BE the posted
        # transaction — canonical txId == tranId — else the read proves nothing.
        if known_tran_id is not None:
            known_canonical = _normalize_tran_id(known_tran_id)
            if known_canonical is None or tran_id != known_canonical:
                return ReconcileOutcome(matched=False)
        # Response-less window path: the candidate timestamp must actually fall
        # inside the dispatched [startTime, endTime] window we queried.
        if start_ms is not None and end_ms is not None:
            cand_ts = _row_timestamp_ms(candidate)
            if cand_ts is None or cand_ts < start_ms or cand_ts > end_ms:
                return ReconcileOutcome(matched=False)
        return ReconcileOutcome(matched=True, tran_id=tran_id)
