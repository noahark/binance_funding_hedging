"""Typed live borrow executor (Boundary C §5) — injected through the executor seam.

Wraps :class:`PortfolioMarginBorrowClient` and maps every transport/exchange
observation into the frozen :class:`ExecutorResult` vocabulary (deny by
default). It performs NO classification of its own beyond the archived rules:
success requires a valid normalized ``tranId``; every definite HTTP 4xx after
rate-limit handling is ``known_rejection`` (includes the
``51006/51014/51061`` pool family and auth rejects such as HTTP 401/``-2015``)
so the task stays in rotation; **Scheme C (operator product choice):**
transport failures (timeout / connection_error / missing status) are also
``known_rejection`` so high-frequency borrow tasks keep rotating — the operator
accepts possible over-borrow when a POST may have landed without a local
response; ``-1003``/429/418 are rate-limited; malformed/empty 2xx and 5xx remain
``unknown`` (exchange may have accepted without a usable body).

Only a POST that returned a usable ``tranId`` counts as borrowed
(DEC-2026-08-21); every other outcome leaves the task in rotation and is
recorded for Human to reconcile from the Binance console.

This module lives under ``backend/services/`` (it imports the network transport
and the shared signer) and is injected via ``BorrowTaskService(executor=...)``;
``backend/borrow_tasks/**`` never imports it.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from ..borrow_tasks import domain as D
from ..borrow_tasks.executor import ExecutorResult
from .portfolio_margin_borrow_client import BorrowHttpResponse, PortfolioMarginBorrowClient

# -1003 TOO_MANY_REQUESTS is verified; its exact PAPI HTTP representation is not,
# so HTTP 400 body code -1003 OR HTTP 429 are both rate-limited.
_RATE_LIMIT_BODY_CODE = "-1003"
# 418 ban: 300s minimum local cooldown, no auto-resume (manual re-arm only).
_BAN_COOLDOWN_SECONDS = Decimal("300")


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


def classify_post_response(response: BorrowHttpResponse) -> ExecutorResult:
    """Map a POST /papi/v1/marginLoan response to the result vocabulary.

    Ordering:

    1. transport error / missing status → ``known_rejection`` (Scheme C: stay in
       rotation; reason ``transport_error:…``). Operator accepts over-borrow risk.
    2. rate-limit: 429, 400+``-1003``, 418 → ``rate_limited``
    3. 2xx: valid ``tranId`` → ``success``; otherwise ``unknown``
    4. 5xx → ``unknown`` (exchange may have accepted)
    5. any other definite 4xx → ``known_rejection`` (request rejected; task
       stays in rotation). Covers pool codes 51006/14/61, auth HTTP 401/``-2015``,
       and other client/business 4xx.
    """
    if response.transport_error is not None or response.http_status is None:
        # Scheme C: do not block the task on connection/timeout — high-frequency
        # borrow of empty-pool assets prefers keep-trying over recon freeze.
        return ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
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
    # 2xx first: a valid normalized tranId is the only success proof; every
    # other 2xx (including one whose body carries a known rejection code) is
    # unknown; the task stays in rotation either way (DEC-2026-08-21).
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
            business_code=code,
            reason="malformed_2xx_no_tranid",
        )
    # 5xx may have been accepted by the exchange, so it is recorded as unknown
    # — even if the body happens to carry a known rejection code.
    if 500 <= status < 600:
        return ExecutorResult(
            result_category=D.RESULT_UNKNOWN,
            http_status=status,
            business_code=code,
            reason=f"possibly_accepted_5xx_{status}",
        )
    # Definite 4xx: exchange rejected the request (no accepted loan). Stay in
    # rotation — includes 401/-2015 auth rejects and 510xx pool rejects.
    if 400 <= status < 500:
        reason = (
            f"known_rejection:{code}"
            if code is not None
            else f"known_rejection:http_{status}"
        )
        return ExecutorResult(
            result_category=D.RESULT_KNOWN_REJECTION,
            http_status=status,
            business_code=code,
            reason=reason,
        )
    return ExecutorResult(
        result_category=D.RESULT_UNKNOWN,
        http_status=status,
        business_code=code,
        reason=f"unlisted_http_{status}",
    )


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
