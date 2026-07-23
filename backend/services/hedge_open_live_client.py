"""Exact-path hedge-open PAPI order + preflight transport (ADR-4 / breakdown §3.7).

The ONLY outbound HTTP surface for real hedge-open order writes and the private
preflight reads its live path needs. Its allowlist contains exactly the verified
method/path pairs (host hardcoded, never caller-supplied) — facts pinned by
``reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md``
§3.1/§3.2/§4.1:

* ``POST /papi/v1/margin/order``        margin leg write            (weight 1, TRADE)
* ``POST /papi/v1/um/order``             UM leg write                (weight 1, TRADE)
* ``GET  /papi/v1/margin/order``         margin leg query (origClientOrderId) (weight 2)
* ``GET  /papi/v1/um/order``             UM leg query (origClientOrderId)     (weight 2)
* ``GET  /papi/v1/balance``              preflight PM balances       (weight 20)
* ``GET  /papi/v1/um/positionSide/dual`` preflight one-way position mode (weight 30)
* ``GET  /papi/v1/rateLimit/order``      preflight order rate limit  (weight 1)

Security gates (mirrors ``portfolio_margin_borrow_client.py`` with its OWN
allowlist — the borrow client and this one are distinct auditable surfaces):

1. **deny-by-default + exact path.** ``_require_whitelisted`` raises BEFORE any
   signing primitive is called. The two POSTs are the only non-GET methods.
2. **One signer.** Signing/sending consume one ``signed_payload`` string from
   :mod:`binance_signing`; this module never constructs a signature inline and
   never forks the signer (the static guard in ``test_private_client.py`` is the
   single-signer proof).
3. **One serializer.** The POST body is the exact ``application/x-www-form-
   urlencoded`` bytes that were signed (signature last); the GET query string is
   the exact signed bytes. No parameter is split between query and body.
4. **No internal retry.** Each call is one transport attempt (one-shot). A
   timeout/5xx on a write POST is NEVER resent here — the executor queries it by
   client ID instead (recon §3.3 / breakdown §3.5).
5. **Module-level timeout.** ``DEFAULT_TIMEOUT_SECONDS = 10`` — test-overridable
   via the constructor, never env-configurable.

Default-off (ADR-4): an instance is constructed ONLY under
``APP_HEDGE_EXECUTOR=live`` with credentials present; in disabled/record mode no
instance exists and zero signed traffic leaves the process. Tests inject a fake
``urlopen``; no real credential is ever placed in a URL, log, or exception.

The client returns a typed :class:`HedgeHttpResponse`; classification into the
attempt/leg vocabulary lives in :mod:`live_hedge_executor`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from . import binance_signing

# ---- deny-by-default allowlist: (method, exact-path) -> base URL (hardcoded) ----
# The single source of truth for which hedge-open endpoints may be called. Hosts
# are bound here and are NOT overridable from config (anti-injection). Pinned by
# the archived recon evidence (recon §3.1/§3.2/§4.1).
ALLOWLIST: Dict[tuple, str] = {
    ("POST", "/papi/v1/margin/order"): "https://papi.binance.com",
    ("POST", "/papi/v1/um/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/margin/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/balance"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/positionSide/dual"): "https://papi.binance.com",
    ("GET", "/papi/v1/rateLimit/order"): "https://papi.binance.com",
}

# Order-write transport timeout (mirror borrow client §5.1). Module-level, NOT
# env-configurable; test-overridable via the constructor.
DEFAULT_TIMEOUT_SECONDS = 10.0
# recvWindow cap documented by the archived PAPI parameter table (≤ 60000ms).
DEFAULT_RECV_WINDOW_MS = 60_000

# Endpoint paths (recon §3.1/§3.2) — exported so the executor/preflight provider
# cite the exact frozen path next to each call rather than a magic string.
MARGIN_ORDER_PATH = "/papi/v1/margin/order"
UM_ORDER_PATH = "/papi/v1/um/order"
BALANCE_PATH = "/papi/v1/balance"
POSITION_SIDE_DUAL_PATH = "/papi/v1/um/positionSide/dual"
RATE_LIMIT_ORDER_PATH = "/papi/v1/rateLimit/order"


@dataclass(frozen=True)
class HedgeHttpResponse:
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
    """Parse ``Retry-After`` as whole seconds. Non-numeric/missing -> ``None``."""
    if header_value is None:
        return None
    text = header_value.strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


class HedgeOpenLiveClient:
    """Exact-path hedge-open order + preflight transport (the only hedge HTTP exit)."""

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
            raise PermissionError(f"hedge endpoint not whitelisted: {method} {path}")
        return ALLOWLIST[(method, path)]

    # -- single transport attempt (no retry); returns a typed response --
    def _send(self, req: urllib.request.Request) -> HedgeHttpResponse:
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
            return HedgeHttpResponse(None, None, "", "timeout", None)
        except urllib.error.URLError as exc:
            # connection loss / DNS / refused — no HTTP response was received
            return HedgeHttpResponse(None, None, "", "connection_error", None)
        except Exception as exc:  # any other transport-level failure
            return HedgeHttpResponse(None, None, "", type(exc).__name__, None)
        body = None
        if raw:
            try:
                body = json.loads(raw)
            except (ValueError, TypeError):
                body = None
        return HedgeHttpResponse(status, body, raw, transport_error, retry_after)

    def _post_signed(self, path: str, params: Dict[str, str], timestamp_ms: int,
                     recv_window_ms: Optional[int]) -> HedgeHttpResponse:
        """POST one order leg. The signed form body IS the sent body (signature
        last); no parameter is split between query and body."""
        base = self._require_whitelisted("POST", path)
        window = self._recv_window_ms if recv_window_ms is None else recv_window_ms
        full = dict(params)
        full["timestamp"] = str(timestamp_ms)
        full["recvWindow"] = str(window)
        body = binance_signing.signed_payload(full, self._api_secret)
        req = urllib.request.Request(
            base + path,
            data=body.encode("utf-8"),
            method="POST",
            headers={
                "X-MBX-APIKEY": self._api_key,
                "User-Agent": self._user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        return self._send(req)

    def _get_signed(self, path: str, params: Dict[str, str], timestamp_ms: int,
                    recv_window_ms: Optional[int]) -> HedgeHttpResponse:
        """Signed GET (leg query or preflight read). The signed query string IS
        the sent query string (signature last)."""
        base = self._require_whitelisted("GET", path)
        window = self._recv_window_ms if recv_window_ms is None else recv_window_ms
        full = dict(params)
        full["timestamp"] = str(timestamp_ms)
        full["recvWindow"] = str(window)
        qs = binance_signing.signed_payload(full, self._api_secret)
        req = urllib.request.Request(
            base + path + "?" + qs,
            method="GET",
            headers={
                "X-MBX-APIKEY": self._api_key,
                "User-Agent": self._user_agent,
            },
        )
        return self._send(req)

    # ------------------------------------------------------ order writes (POST)

    def post_margin_order(self, params: Dict[str, str], *, timestamp_ms: int,
                          recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """POST /papi/v1/margin/order — the margin leg write.

        ``params`` is the already-built would-send shape (symbol/side/type/
        quantity/sideEffectType/newClientOrderId/newOrderRespType) from
        ``executor.build_spot_order_params``; this method adds timestamp +
        recvWindow + signature and sends. One-shot; never retried here.
        """
        return self._post_signed(MARGIN_ORDER_PATH, params, timestamp_ms, recv_window_ms)

    def post_um_order(self, params: Dict[str, str], *, timestamp_ms: int,
                      recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """POST /papi/v1/um/order — the UM leg write (positionSide supplied)."""
        return self._post_signed(UM_ORDER_PATH, params, timestamp_ms, recv_window_ms)

    # ------------------------------------------- order queries (GET, by client ID)

    def query_margin_order(self, symbol: str, orig_client_order_id: str, *,
                           timestamp_ms: int,
                           recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/margin/order?symbol=..&origClientOrderId=.. (recon §3.3).

        The reconciliation lookup for a margin leg after a timeout/ambiguous POST.
        Queries by the persisted client ID — never by orderId (which may be
        unknown), never by resending the write POST.
        """
        return self._get_signed(
            MARGIN_ORDER_PATH,
            {"symbol": symbol, "origClientOrderId": orig_client_order_id},
            timestamp_ms,
            recv_window_ms,
        )

    def query_um_order(self, symbol: str, orig_client_order_id: str, *,
                       timestamp_ms: int,
                       recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/um/order?symbol=..&origClientOrderId=.. (recon §3.3)."""
        return self._get_signed(
            UM_ORDER_PATH,
            {"symbol": symbol, "origClientOrderId": orig_client_order_id},
            timestamp_ms,
            recv_window_ms,
        )

    # ----------------------------------------------------- preflight reads (GET)

    def get_balance(self, *, timestamp_ms: int,
                    recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/balance — PM crossMarginFree balances (preflight)."""
        return self._get_signed(BALANCE_PATH, {}, timestamp_ms, recv_window_ms)

    def get_position_side_dual(self, *, timestamp_ms: int,
                               recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/um/positionSide/dual — one-way vs hedge mode (preflight).

        ``dualSidePosition=false`` => one-way ``BOTH`` (the frozen contract mode);
        ``true`` => hedge mode, which fails preflight closed (PRD §5 / recon §4.3).
        """
        return self._get_signed(POSITION_SIDE_DUAL_PATH, {}, timestamp_ms, recv_window_ms)

    def get_rate_limit_order(self, *, timestamp_ms: int,
                             recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/rateLimit/order — the account's real order-rate limit.

        Cannot be substituted by the public exchangeInfo limit (recon §4.4).
        """
        return self._get_signed(RATE_LIMIT_ORDER_PATH, {}, timestamp_ms, recv_window_ms)
