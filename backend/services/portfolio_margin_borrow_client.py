"""Exact-path Portfolio Margin borrow transport (Boundary C §3 / §8.1).

The ONLY outbound HTTP surface for real borrowing. Its allowlist contains
exactly two verified method/path pairs (host hardcoded, never caller-supplied):

* ``POST https://papi.binance.com/papi/v1/marginLoan``  (weight 100)
* ``GET  https://papi.binance.com/papi/v1/margin/marginLoan``  (weight 10)

Security gates (mirrors ``private_client.py``, with its OWN allowlist):

1. **deny-by-default + exact path.** ``_require_whitelisted`` raises BEFORE any
   signing primitive is called. The POST is the only non-GET method permitted.
2. **One signer.** Signing and sending consume one ``signed_payload`` string from
   :mod:`binance_signing`; this module never constructs a signature inline.
3. **One serializer.** The POST body is the exact ``application/x-www-form-
   urlencoded`` bytes that were signed (signature last); no parameter is split
   between query and body.
4. **No internal retry.** Each call is one transport attempt (one-shot POST).
5. **Module-level timeout.** ``DEFAULT_TIMEOUT_SECONDS = 10`` — test-overridable
   via the constructor, never env-configurable, never ``config.request_timeout``.

The client returns a typed :class:`BorrowHttpResponse`; classification into the
frozen result categories lives in :mod:`live_borrow_executor` so this module
stays a thin, auditable transport. No credentials are ever placed in a URL,
log, or exception message.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import binance_signing

# ---- deny-by-default allowlist: (method, exact-path) -> base URL (hardcoded) ----
# The single source of truth for which borrow endpoints may be called. Hosts are
# bound here and are NOT overridable from config (anti-injection). Frozen by the
# archived evidence capture (Boundary C §8.1).
ALLOWLIST = {
    ("POST", "/papi/v1/marginLoan"): "https://papi.binance.com",
    ("GET", "/papi/v1/margin/marginLoan"): "https://papi.binance.com",
}

# Borrow-POST transport timeout (Boundary C §5.1). Module-level constant, NOT
# env-configurable and NOT config.request_timeout. Test-overridable via the
# constructor so fake/recording transports can pin it.
DEFAULT_TIMEOUT_SECONDS = 10.0
# recvWindow cap documented by the archived POST parameter table (≤ 60000ms).
DEFAULT_RECV_WINDOW_MS = 60_000
_LOAN_RECORD_MAX_SIZE = 100


@dataclass(frozen=True)
class BorrowHttpResponse:
    """Sanitized transport result consumed by the typed live executor.

    ``http_status`` is ``None`` for a transport-level failure (timeout /
    connection loss / DNS) where no HTTP response was received. ``body`` is the
    parsed JSON value (dict / list) or ``None`` when the body was empty or not
    valid JSON. ``transport_error`` names the failure class for classification.
    No credential, signature, or full private body is retained.
    """

    http_status: Optional[int]
    body: object
    raw_body: str
    transport_error: Optional[str]
    retry_after_seconds: Optional[int]


def _parse_retry_after(header_value: Optional[str]) -> Optional[int]:
    """Parse ``Retry-After`` as whole seconds. Non-numeric/missing -> ``None``.

    The classification layer applies the fail-closed default (60s) and the
    ``[60, 300]`` clamp; this helper only parses.
    """
    if header_value is None:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


class PortfolioMarginBorrowClient:
    """Exact-path PM borrow + loan-record transport (the only borrow HTTP exit)."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        user_agent: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
        urlopen: Optional[Callable] = None,
    ):
        self._api_key = api_key or ""
        self._api_secret = api_secret or ""
        self._user_agent = user_agent
        self._timeout = timeout_seconds
        self._recv_window_ms = recv_window_ms
        self._urlopen = urlopen or urllib.request.urlopen

    @property
    def credentials_present(self) -> bool:
        return bool(self._api_key and self._api_secret)

    # -- security gate (raises BEFORE any signing primitive is called) --
    @staticmethod
    def _require_whitelisted(method: str, path: str) -> str:
        if (method, path) not in ALLOWLIST:
            raise PermissionError(f"borrow endpoint not whitelisted: {method} {path}")
        return ALLOWLIST[(method, path)]

    # -- single transport attempt (no retry); returns a typed response --
    def _send(self, req: urllib.request.Request) -> BorrowHttpResponse:
        try:
            with self._urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                status = getattr(resp, "status", None) or resp.getcode()
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                transport_error = None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            status = exc.code
            retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
            transport_error = None
        except TimeoutError:
            return BorrowHttpResponse(None, None, "", "timeout", None)
        except urllib.error.URLError as exc:
            # connection loss / DNS / refused — no HTTP response was received
            return BorrowHttpResponse(None, None, "", "connection_error", None)
        except Exception as exc:  # any other transport-level failure
            return BorrowHttpResponse(None, None, "", type(exc).__name__, None)
        body = None
        if raw:
            try:
                body = json.loads(raw)
            except (ValueError, TypeError):
                body = None
        return BorrowHttpResponse(status, body, raw, transport_error, retry_after)

    # -- POST /papi/v1/marginLoan (the only borrow write) --
    def post_margin_loan(
        self,
        asset: str,
        amount: str,
        *,
        timestamp_ms: int,
        recv_window_ms: Optional[int] = None,
    ) -> BorrowHttpResponse:
        base = self._require_whitelisted("POST", "/papi/v1/marginLoan")
        window = self._recv_window_ms if recv_window_ms is None else recv_window_ms
        params = {
            "asset": asset,
            "amount": amount,
            "timestamp": str(timestamp_ms),
            "recvWindow": str(window),
        }
        # The signed body IS the sent body (application/x-www-form-urlencoded,
        # signature last); no parameter is split between query and body.
        body = binance_signing.signed_payload(params, self._api_secret)
        req = urllib.request.Request(
            base + "/papi/v1/marginLoan",
            data=body.encode("utf-8"),
            method="POST",
            headers={
                "X-MBX-APIKEY": self._api_key,
                "User-Agent": self._user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        return self._send(req)

    # -- GET /papi/v1/margin/marginLoan (loan-record reconciliation) --
    def fetch_loan_records(
        self,
        asset: str,
        *,
        timestamp_ms: int,
        tx_id: Optional[str] = None,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        size: int = _LOAN_RECORD_MAX_SIZE,
        recv_window_ms: Optional[int] = None,
    ) -> BorrowHttpResponse:
        base = self._require_whitelisted("GET", "/papi/v1/margin/marginLoan")
        window = self._recv_window_ms if recv_window_ms is None else recv_window_ms
        params = {
            "asset": asset,
            "timestamp": str(timestamp_ms),
            "recvWindow": str(window),
        }
        # txId precedence when present (verified txId == tranId correspondence);
        # otherwise a bounded dispatch-anchored startTime/endTime window.
        if tx_id is not None:
            params["txId"] = str(tx_id)
        if start_ms is not None:
            params["startTime"] = str(start_ms)
        if end_ms is not None:
            params["endTime"] = str(end_ms)
        params["size"] = str(min(max(size, 1), _LOAN_RECORD_MAX_SIZE))
        qs = binance_signing.signed_payload(params, self._api_secret)
        req = urllib.request.Request(
            base + "/papi/v1/margin/marginLoan?" + qs,
            method="GET",
            headers={
                "X-MBX-APIKEY": self._api_key,
                "User-Agent": self._user_agent,
            },
        )
        return self._send(req)

    @staticmethod
    def raw_rows(response: BorrowHttpResponse) -> Optional[List]:
        """Return the envelope's raw ``rows`` list, or ``None`` when not an envelope.

        The documented 200 contract is the envelope ``{"rows": [...], "total": N}``
        (archived Query Margin Loan Record evidence). Unlike
        :meth:`records_from` (which filters non-dict members), this returns the
        UNFILTERED rows so the executor's matcher can fail-closed on any malformed
        member instead of silently dropping it and proving success on the
        remainder. Returns ``None`` for a transport/HTTP error or a body that is
        not the contract envelope (non-dict body or a non-list ``rows``).
        """
        if response.transport_error is not None or response.http_status is None:
            return None
        if response.http_status >= 400:
            return None
        body = response.body
        if not isinstance(body, dict):
            return None
        rows = body.get("rows")
        if not isinstance(rows, list):
            return None
        return rows

    @staticmethod
    def records_from(response: BorrowHttpResponse) -> List[dict]:
        """Return the loan-record rows from a GET response (empty on any failure).

        Thin convenience wrapper over :meth:`raw_rows` that additionally drops
        non-dict members. Field-level contract validation (``txId``/``asset``/
        ``principal``/``timestamp``/``status``) lives in the executor's matcher,
        which uses :meth:`raw_rows` directly so a malformed member fails closed
        rather than being silently filtered away.
        """
        rows = PortfolioMarginBorrowClient.raw_rows(response)
        if rows is None:
            return []
        return [r for r in rows if isinstance(r, dict)]

    @staticmethod
    def declared_total(response: BorrowHttpResponse) -> Optional[int]:
        """Return the envelope ``total`` (non-negative int) or ``None``.

        ``None`` covers every fail-closed shape: transport/HTTP error, a body that
        is not the contract envelope, or a ``total`` that is missing/bool/non-int/
        negative. The executor uses this to keep an attempt blocked when a single
        inspected page cannot prove global uniqueness (``total`` exceeds the rows
        actually inspected) — the design never declares a local match unique while
        pagination evidence is incomplete.
        """
        if response.transport_error is not None or response.http_status is None:
            return None
        if response.http_status >= 400:
            return None
        body = response.body
        if not isinstance(body, dict):
            return None
        total = body.get("total")
        if isinstance(total, bool) or not isinstance(total, int):
            return None
        if total < 0:
            return None
        return total
