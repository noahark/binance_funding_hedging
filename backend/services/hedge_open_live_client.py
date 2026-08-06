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

Regular-spot account route (stage 2026-08-02-spot-order-routing-cap-display-v1,
decision §E-2) — five exact pairs HARDBOUND to the public spot host
``https://api.binance.com`` (never caller-supplied), pinned by
``reports/api-samples/2026-08-spot-order-routing-v1/restricted-asset.raw.json``:

* ``GET  /sapi/v1/margin/restricted-asset`` platform collateral-cap list (API-key
  only, unsigned, MARKET_DATA, weight 1) — read by BOTH the positive-funding
  order preflight (§3, fresh per preflight) and the display cache (§6); the
  response's ``openLongRestrictedAsset`` is never read or stored (decision §A-3).
* ``POST /api/v3/order``                 regular-spot leg write     (TRADE, signed)
* ``GET  /api/v3/order``                 regular-spot leg query (origClientOrderId)
* ``GET  /api/v3/account``               standard Spot account balance (preflight)
* ``GET  /api/v3/rateLimit/order``       standard Spot order rate limit (preflight)

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

Default-off (ADR-4) — order execution path: an instance that may POST an order
is constructed ONLY under ``APP_HEDGE_EXECUTOR=live`` with credentials present,
and a real POST still requires the durable Start gate + a fresh passing
preflight; in disabled/record mode no order-writing instance exists and zero
signed traffic leaves the process. Display path is separate (decision §E-4 /
interface §10): the composition root (``server._build_restricted_asset_client``)
constructs a deny-by-default instance from the existing hedge API key and
injects it into :class:`backend.services.snapshot_service.SnapshotService`
INDEPENDENTLY of ``APP_HEDGE_EXECUTOR`` and the private channel, so the
collateral-cap column is populated even when the order executor is disabled.
That display client may call ONLY the ``GET /sapi/v1/margin/restricted-asset``
above（由行情服务的调用面保证；白名单只保证不会越出这 12 条）；
constructing it sends no request and changes no Start gate. Tests inject a fake
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
    # 功能三（2026-08）：close 完成核实——查该 symbol 合约持仓是否归零。
    ("GET", "/papi/v1/um/positionRisk"): "https://papi.binance.com",
    # 平仓现货卖出重设计（2026-08）：万向划转——统一账户⇄普通现货账户
    # （forward close 补足现货 / USDT 回流）。用户万向划转（权重 TRADE）。
    ("POST", "/sapi/v1/asset/transfer"): "https://api.binance.com",
    ("GET", "/papi/v1/rateLimit/order"): "https://papi.binance.com",
    # Regular spot account route (stage 2026-08-02-spot-order-routing-cap-display-v1
    # §4 / decision §E-2). Five exact (method, path) pairs HARDBOUND to the public
    # spot host — never caller-supplied. The restricted-asset read is platform-level
    # MARKET_DATA (API-key only, unsigned); the four /api/v3 endpoints are the
    # regular-spot order/query/account/rate-limit surface used by the positive-
    # funding regular_spot route. Hosts bound here; config cannot override them.
    ("GET", "/sapi/v1/margin/restricted-asset"): "https://api.binance.com",
    ("POST", "/api/v3/order"): "https://api.binance.com",
    ("GET", "/api/v3/order"): "https://api.binance.com",
    ("GET", "/api/v3/account"): "https://api.binance.com",
    ("GET", "/api/v3/rateLimit/order"): "https://api.binance.com",
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
UM_POSITION_RISK_PATH = "/papi/v1/um/positionRisk"
RATE_LIMIT_ORDER_PATH = "/papi/v1/rateLimit/order"
# Regular-spot account route paths (decision §E-2 / §4), all on api.binance.com.
# restricted-asset is the shared platform collateral-cap list (stage
# 2026-08-02-spot-order-routing-cap-display-v1); the four /api/v3 paths serve the
# regular_spot positive-funding order loop.
RESTRICTED_ASSET_PATH = "/sapi/v1/margin/restricted-asset"
SPOT_ORDER_PATH = "/api/v3/order"
SPOT_ACCOUNT_PATH = "/api/v3/account"
UNIVERSAL_TRANSFER_PATH = "/sapi/v1/asset/transfer"
# 万向划转 type 冻结枚举（平仓现货卖出重设计）：统一账户 → 普通现货账户
# （forward close 补足现货）/ 普通现货账户 → 统一账户（USDT 回流）。仅此两个。
TRANSFER_TYPE_PM_MAIN = "PORTFOLIO_MARGIN_MAIN"
TRANSFER_TYPE_MAIN_PM = "MAIN_PORTFOLIO_MARGIN"
_ALLOWED_TRANSFER_TYPES = frozenset({TRANSFER_TYPE_PM_MAIN, TRANSFER_TYPE_MAIN_PM})
SPOT_RATE_LIMIT_ORDER_PATH = "/api/v3/rateLimit/order"


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

    def _get_apikey_only(self, path: str) -> HedgeHttpResponse:
        """Unsigned GET carrying ONLY ``X-MBX-APIKEY`` (recon
        ``reports/api-samples/2026-08-spot-order-routing-v1/restricted-asset.raw.json``):
        no ``timestamp``, no ``recvWindow``, no query string, no HMAC signature —
        a platform-level MARKET_DATA read. Still gated by the deny-by-default
        allowlist + hardcoded host (decision §E-2); the only caller is the
        restricted-asset read, shared by the positive-funding preflight (§3) and
        the display cache (§6)."""
        base = self._require_whitelisted("GET", path)
        req = urllib.request.Request(
            base + path,
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

    def fetch_um_positions(self, *, symbol: Optional[str] = None,
                           timestamp_ms: int,
                           recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/um/positionRisk — close 完成核实（功能三）：查该 symbol
        合约持仓是否归零。``symbol`` 省略时查全量（调用方按 symbol 过滤）。
        """
        params = {"symbol": symbol} if symbol else {}
        return self._get_signed(
            UM_POSITION_RISK_PATH, params, timestamp_ms, recv_window_ms,
        )

    def get_rate_limit_order(self, *, timestamp_ms: int,
                             recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /papi/v1/rateLimit/order — the account's real order-rate limit.

        Cannot be substituted by the public exchangeInfo limit (recon §4.4).
        """
        return self._get_signed(RATE_LIMIT_ORDER_PATH, {}, timestamp_ms, recv_window_ms)

    # ------------------------------------------ regular-spot account route (§4)
    #
    # The positive-funding ``regular_spot`` path uses the STANDARD spot account
    # (api.binance.com), not PAPI cross margin. These four signed reads/writes +
    # the unsigned restricted-asset read are the only regular-spot exit points;
    # they share the deny-by-default allowlist and hardcoded host above. The
    # negative-funding route never reaches them.

    def get_restricted_asset(self) -> HedgeHttpResponse:
        """GET /sapi/v1/margin/restricted-asset — the platform collateral-cap
        list (decision §A-3 / §E-2). API-key only, unsigned, no params. Returns
        ``{"openLongRestrictedAsset": [], "maxCollateralExceededAsset": [...]}``;
        the caller reads ONLY ``maxCollateralExceededAsset`` and never stores
        ``openLongRestrictedAsset`` (decision §A-3)."""
        return self._get_apikey_only(RESTRICTED_ASSET_PATH)

    def post_spot_order(self, params: Dict[str, str], *, timestamp_ms: int,
                        recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """POST /api/v3/order — the regular-spot leg write.

        ``params`` is the would-send shape WITHOUT ``sideEffectType`` (a regular
        spot order is not a margin borrow/repay); this method adds timestamp +
        recvWindow + signature and sends. One-shot; never retried here. Distinct
        endpoint + param shape from :meth:`post_margin_order` (PAPI keeps
        ``sideEffectType=NO_SIDE_EFFECT``)."""
        return self._post_signed(SPOT_ORDER_PATH, params, timestamp_ms, recv_window_ms)

    def query_spot_order(self, symbol: str, orig_client_order_id: str, *,
                         timestamp_ms: int,
                         recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /api/v3/order?symbol=..&origClientOrderId=.. — the regular-spot
        leg reconciliation lookup (mirrors :meth:`query_margin_order` but on the
        standard spot endpoint)."""
        return self._get_signed(
            SPOT_ORDER_PATH,
            {"symbol": symbol, "origClientOrderId": orig_client_order_id},
            timestamp_ms,
            recv_window_ms,
        )

    def get_spot_account(self, *, timestamp_ms: int,
                         recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /api/v3/account — the standard Spot account balance snapshot.

        Used by the positive-funding regular_spot preflight to size the available
        USDT for a spot BUY (PAPI ``crossMarginFree`` cannot answer this — design
        §2.4) and by forward-close spot-sell balance pre-check / re-check."""
        return self._get_signed(SPOT_ACCOUNT_PATH, {}, timestamp_ms, recv_window_ms)

    def universal_transfer(
        self, type_: str, asset: str, amount: str, *,
        timestamp_ms: int, recv_window_ms: Optional[int] = None,
    ) -> HedgeHttpResponse:
        """POST /sapi/v1/asset/transfer — 用户万向划转（平仓现货卖出重设计）。

        ``type_`` 仅允许冻结枚举（``PORTFOLIO_MARGIN_MAIN`` 统一→现货 /
        ``MAIN_PORTFOLIO_MARGIN`` 现货→统一）；``asset``/``amount`` 由内部计算传入，
        拒绝外部注入。One-shot：超时/5xx 不重试（写语义与订单一致），由调用方
        fail-closed 处理。返回原始响应，tranId 由调用方解析。
        """
        if type_ not in _ALLOWED_TRANSFER_TYPES:
            raise ValueError(f"transfer type not allowed: {type_!r}")
        return self._post_signed(
            UNIVERSAL_TRANSFER_PATH,
            {"type": type_, "asset": asset, "amount": str(amount)},
            timestamp_ms,
            recv_window_ms,
        )

    def get_spot_rate_limit_order(self, *, timestamp_ms: int,
                                  recv_window_ms: Optional[int] = None) -> HedgeHttpResponse:
        """GET /api/v3/rateLimit/order — the standard Spot order-rate limit.

        Distinct from the PAPI limit (``get_rate_limit_order``); a regular_spot
        order consumes the spot rate-limit budget, not the PAPI one (design §3.5)."""
        return self._get_signed(SPOT_RATE_LIMIT_ORDER_PATH, {}, timestamp_ms, recv_window_ms)
