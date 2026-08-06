"""Read-only hedge-open preflight provider (breakdown §4.3 / ADR-4).

Assembles a :class:`backend.hedge_open_tasks.domain.PreflightSnapshot` from two
read-only sources immediately before a live send:

1. **Public exchange filters** (unsigned): spot ``GET /api/v3/exchangeInfo`` and
   UM ``GET /fapi/v1/exchangeInfo`` (recon §3.4 — PAPI has no exchangeInfo, so
   filters come from each market's public endpoint), plus a conservative spot
   ``GET /api/v3/ticker/price`` for the min-notional estimate.
2. **Private PM reads** (signed): ``GET /papi/v1/balance`` (crossMarginFree),
   ``GET /papi/v1/um/positionSide/dual`` (one-way vs hedge), and
   ``GET /papi/v1/rateLimit/order`` (the account's real order-rate limit).

The private reads reuse the single signer through :class:`HedgeOpenLiveClient`
(the hedge client owns its own allowlist for these three preflight endpoints;
``private_client.py``'s frozen whitelist cannot be extended and lacks them — see
the implementation report's deviation note versus breakdown §4.3's literal
"reuse private_client.py" wording). Public reads go through an injectable
``urlopen`` (default ``urllib.request.urlopen``).

Default-off: with no live client (or no credentials) :meth:`get_snapshot` returns
``None``, which the service treats as the dry-run "no preflight data" case
(:func:`domain.compute_preflight` then returns an unknown result so a task may
still be created to exercise the record transport). In live mode the service
fails the pair closed when a snapshot cannot be assembled.

Any partial read failure (a hedge-mode account, a missing step/filter, a failed
balance/position read) yields ``None`` rather than a half-populated snapshot, so
a live send is never authorized on incomplete facts.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional

from ..hedge_open_tasks import domain as D
from ..domain.normalize import resolve_spot_leg
from .hedge_open_live_client import HedgeOpenLiveClient

# Public (unsigned) market-data hosts (recon §2.1 / §3.4). Hardcoded; the public
# reader never signs and never touches credentials.
_SPOT_API_BASE = "https://api.binance.com"
_FAPI_BASE = "https://fapi.binance.com"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _parse_spot_filters(symbol_data: dict) -> dict:
    """Map a spot exchangeInfo symbol's filters to the domain filter dict shape.

    Domain reads ``lot_size``/``market_lot_size`` (step_size/min_qty/max_qty) and
    ``notional`` (min_notional/apply_min_to_market). A zero/absent step disables
    only that constraint (:func:`domain.effective_market_step`).
    """
    by_type = {f.get("filterType"): f for f in symbol_data.get("filters", []) if isinstance(f, dict)}
    lot = by_type.get("LOT_SIZE", {})
    market = by_type.get("MARKET_LOT_SIZE", {})
    notional = by_type.get("NOTIONAL", {})
    return {
        "lot_size": {
            "step_size": lot.get("stepSize"),
            "min_qty": lot.get("minQty"),
            "max_qty": lot.get("maxQty"),
        },
        "market_lot_size": {
            "step_size": market.get("stepSize"),
            "min_qty": market.get("minQty"),
            "max_qty": market.get("maxQty"),
        },
        "notional": {
            "min_notional": notional.get("minNotional"),
            "apply_min_to_market": notional.get("applyMinToMarket"),
            "notional": None,
        },
    }


def _parse_perp_filters(symbol_data: dict) -> dict:
    """Map a UM exchangeInfo symbol's filters to the domain filter dict shape.

    UM uses ``MIN_NOTIONAL`` (``notional``) with no ``applyMinToMarket`` flag, so
    the provider sets ``apply_min_to_market=True`` to make
    :func:`domain.min_notional` honor it (a False/absent flag would disable it).
    """
    by_type = {f.get("filterType"): f for f in symbol_data.get("filters", []) if isinstance(f, dict)}
    lot = by_type.get("LOT_SIZE", {})
    market = by_type.get("MARKET_LOT_SIZE", {})
    min_notional = by_type.get("MIN_NOTIONAL", {})
    return {
        "lot_size": {
            "step_size": lot.get("stepSize"),
            "min_qty": lot.get("minQty"),
            "max_qty": lot.get("maxQty"),
        },
        "market_lot_size": {
            "step_size": market.get("stepSize"),
            "min_qty": market.get("minQty"),
            "max_qty": market.get("maxQty"),
        },
        "notional": {
            "min_notional": None,
            "apply_min_to_market": True,
            "notional": min_notional.get("notional"),
        },
    }


def _find_symbol(symbols: list, coin: str) -> Optional[dict]:
    for sym in symbols:
        if isinstance(sym, dict) and sym.get("symbol") == coin:
            return sym
    return None


def _bstock_spot_alias(coin: str, perp_symbol: Optional[dict]) -> Optional[str]:
    """Return the B-suffix spot pair only for a TRADIFI perpetual."""
    if not isinstance(perp_symbol, dict):
        return None
    if perp_symbol.get("contractType") != "TRADIFI_PERPETUAL":
        return None
    base = perp_symbol.get("baseAsset")
    quote = perp_symbol.get("quoteAsset")
    if not isinstance(base, str) or not isinstance(quote, str) or not base or not quote:
        return None
    alias = f"{base}B{quote}"
    return alias if alias != coin else None


# S4b (ADR-H5): three-state leg existence from a public read result. True =
# confirmed present; False = confirmed absent; None = indeterminate (read failed
# or an unexpected shape). The caller never blocks on None — a transient
# public-marketdata failure is not escalated to a create-task failure.

def _spot_leg_exists(status: Optional[int], body: object, coin: str) -> Optional[bool]:
    """Spot ``GET /api/v3/exchangeInfo?symbol=`` returns 2xx + the symbol for an
    existing pair, or HTTP 400 body ``{"code": -1121, ...}`` for an unknown one."""
    if status is None or status >= 500:
        return None
    if status == 400 and isinstance(body, dict) and body.get("code") == -1121:
        return False
    if 200 <= status < 300 and isinstance(body, dict):
        symbols = body.get("symbols")
        if isinstance(symbols, list) and any(
            isinstance(s, dict) and s.get("symbol") == coin for s in symbols
        ):
            return True
    return None


def _perp_leg_exists(status: Optional[int], body: object, coin: str) -> Optional[bool]:
    """UM ``GET /fapi/v1/exchangeInfo`` returns the full symbol list; the coin is
    present (True) or absent (False) on a successful read, None on failure."""
    if status is None or status >= 500 or not isinstance(body, dict):
        return None
    if not 200 <= status < 300:
        return None
    symbols = body.get("symbols")
    if not isinstance(symbols, list):
        return None
    return any(isinstance(s, dict) and s.get("symbol") == coin for s in symbols)


class HedgePreflightProvider:
    """Read-only preflight data source for the live hedge-open path.

    Returns ``None`` (dry-run) when no live client/credentials are configured, or
    when any read fails or the account is not one-way (hedge mode fails closed).
    """

    def __init__(
        self,
        *,
        live_client: Optional[HedgeOpenLiveClient] = None,
        now_ms: Callable[[], int],
        public_urlopen: Optional[Callable] = None,
        user_agent: str = "funding-hedging-hedge-preflight",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        self._client = live_client
        self._now_ms = now_ms
        self._public_urlopen = public_urlopen or urllib.request.urlopen
        self._user_agent = user_agent
        self._timeout = timeout_seconds

    def _read_public_json(self, url: str) -> Optional[object]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with self._public_urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw)
        except Exception:
            return None

    def _read_public_with_status(self, url: str) -> tuple[Optional[int], object]:
        """Read a public endpoint surfacing the HTTP status + body, so a -1121
        (an unknown spot symbol returned as HTTP 400 with body
        ``{"code": -1121, ...}``) can be told apart from a transport failure.

        Returns ``(status, body)`` — ``(None, None)`` on a transport/decode
        failure. Unlike :meth:`_read_public_json`, an :class:`HTTPError` body is
        read (Binance ships the error code there) rather than swallowed.
        """
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
            with self._public_urlopen(req, timeout=self._timeout) as resp:
                status = getattr(resp, "status", None)
                if status is None:
                    status = getattr(resp, "code", None)  # http.client compat
                raw = resp.read().decode("utf-8", "replace")
            try:
                return int(status), json.loads(raw)
            except (TypeError, ValueError):
                return None, None
        except urllib.error.HTTPError as exc:
            # Binance returns HTTP 400 + body {"code": -1121, "msg": ...} for an
            # unknown symbol; surface the parsed body so the probe can read it.
            try:
                body = json.loads(exc.read().decode("utf-8", "replace"))
            except Exception:
                body = None
            try:
                return int(exc.code), body
            except (TypeError, ValueError):
                return None, body
        except Exception:
            return None, None

    def _read_spot_record(self, symbol: str) -> Optional[dict]:
        """Read one spot exchangeInfo symbol record (raw dict), or None on a read
        failure / absent symbol."""
        data = self._read_public_json(
            f"{_SPOT_API_BASE}/api/v3/exchangeInfo?symbol={symbol}"
        )
        if not isinstance(data, dict):
            return None
        return _find_symbol(data.get("symbols", []), symbol)

    def _read_perp_filters(self, coin: str) -> Optional[tuple[dict, bool, dict]]:
        data = self._read_public_json(f"{_FAPI_BASE}/fapi/v1/exchangeInfo")
        if not isinstance(data, dict):
            return None
        symbol = _find_symbol(data.get("symbols", []), coin)
        if symbol is None:
            return None
        tradable = symbol.get("status") == "TRADING"
        return _parse_perp_filters(symbol), tradable, symbol

    def _read_spot_leg(
        self, coin: str, perp_symbol: Optional[dict]
    ) -> Optional[tuple[dict, bool, str, str]]:
        """Resolve the spot leg via the shared :func:`resolve_spot_leg` pure
        function — the SINGLE resolution rule shared with the display path
        (design §6.5 / interface §5, acceptance S8). Reads the exact + bStock
        B-suffix candidate records, delegates selection (exact-first, then alias
        only for TRADIFI, both must be TRADING) to ``resolve_spot_leg``, and
        distinguishes a readable-but-non-tradable record (a fatal
        ``symbol_unavailable`` fact) from a read failure (``None`` -> fail-closed
        incomplete).

        Returns ``(filters, tradable, symbol, base_asset)`` — ``base_asset`` is
        the resolved spot record's ``baseAsset`` (``TSLAB`` for a bStock, never
        the contract ``TSLA``), the input used by the collateral-cap membership
        check. Returns ``None`` only when no candidate record could be read.
        """
        candidates = [coin]
        alias = _bstock_spot_alias(coin, perp_symbol)
        if alias is not None:
            candidates.append(alias)
        spot_by_sym: dict[str, dict] = {}
        read_ok = False
        for sym in candidates:
            rec = self._read_spot_record(sym)
            if rec is not None:
                read_ok = True
                spot_by_sym[sym] = rec
        if isinstance(perp_symbol, dict):
            contract_type = perp_symbol.get("contractType", "")
            base = perp_symbol.get("baseAsset", "")
            quote = perp_symbol.get("quoteAsset", "")
        else:
            contract_type = base = quote = ""
        spot, _match_type = resolve_spot_leg(contract_type, base, quote, spot_by_sym)
        if spot is not None:
            return (
                _parse_spot_filters(spot),
                True,
                spot.get("symbol", coin),
                spot.get("baseAsset", ""),
            )
        if read_ok:
            # A record was read but none is tradable -> a fatal symbol_unavailable
            # fact (compute_preflight maps it to REJECT_SYMBOL_UNAVAILABLE), not a
            # read failure. Surface the read record so the filters/tradable flag
            # carry the fact; base_asset is informational only on this path.
            non_tradable = next(iter(spot_by_sym.values()))
            return (
                _parse_spot_filters(non_tradable),
                False,
                non_tradable.get("symbol", coin),
                non_tradable.get("baseAsset", ""),
            )
        return None

    def _read_est_price(self, coin: str) -> Optional[Decimal]:
        """Conservative spot price for the forward min-notional estimate."""
        data = self._read_public_json(f"{_SPOT_API_BASE}/api/v3/ticker/price?symbol={coin}")
        if not isinstance(data, dict):
            return None
        price = data.get("price")
        if price is None:
            return None
        try:
            value = Decimal(str(price))
        except (InvalidOperation, ValueError, TypeError):
            return None
        return value if value > 0 else None

    def _read_balances(self) -> Optional[dict]:
        if self._client is None:
            return None
        response = self._client.get_balance(timestamp_ms=self._now_ms())
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, list)
        ):
            return None
        out: dict[str, Decimal] = {}
        for row in response.body:
            if not isinstance(row, dict):
                continue
            asset = row.get("asset")
            free = row.get("crossMarginFree")
            if asset is None or free is None:
                continue
            try:
                out[str(asset)] = Decimal(str(free))
            except (InvalidOperation, ValueError, TypeError):
                continue
        return out

    def _read_position_mode(self) -> Optional[str]:
        if self._client is None:
            return None
        response = self._client.get_position_side_dual(timestamp_ms=self._now_ms())
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, dict)
        ):
            return None  # read failed -> fail-closed incomplete
        dual = response.body.get("dualSidePosition")
        # A readable dualSidePosition=true is a two-way (hedge) account: a fatal
        # fact downstream (the frozen contract is one-way BOTH, PRD §5 / recon
        # §4.3). A literal false is the only one-way confirmation; a missing or
        # ambiguous value cannot confirm one-way, so it fails closed (clause 3).
        if dual is True:
            return D.POS_MODE_HEDGE
        if dual is False:
            return D.POS_MODE_BOTH
        return None

    def _read_rate_limit_order(self) -> Optional[int]:
        if self._client is None:
            return None
        response = self._client.get_rate_limit_order(timestamp_ms=self._now_ms())
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, list)
        ):
            return None
        # Pick the ORDERS rate limit's configured cap (recon §3.2 / §4.4).
        for row in response.body:
            if isinstance(row, dict) and row.get("rateLimitType") == "ORDERS":
                limit = row.get("limit")
                if isinstance(limit, int) and limit > 0:
                    return limit
        return None

    # --------------------------------------------- regular-spot route reads (§3)
    def _read_collateral_cap_hit(self, spot_base_asset: str) -> Optional[bool]:
        """FRESH read of the platform collateral-cap list (design §3 step 4).
        Returns True/False for whether ``spot_base_asset`` is on
        ``maxCollateralExceededAsset``, or None when the read failed (the caller
        fail-closes — never guess a route from a missing read).

        Reads ONLY ``maxCollateralExceededAsset``; ``openLongRestrictedAsset`` is
        never read or stored (decision §A-3). Membership is EXACT (design §5): no
        normalization, no case-folding, no multiplier-prefix stripping — the list
        and the spot ``baseAsset`` share one naming domain. The match input is
        the resolved spot base asset (``TSLAB`` for a bStock), never the contract
        base, because the caller passes the value ``resolve_spot_leg`` resolved.
        """
        if self._client is None:
            return None
        response = self._client.get_restricted_asset()
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, dict)
        ):
            return None
        assets = response.body.get("maxCollateralExceededAsset")
        if not isinstance(assets, list):
            return None
        return spot_base_asset in {a for a in assets if isinstance(a, str)}

    def _read_spot_account_usdt(self) -> Optional[Decimal]:
        """Standard Spot account free USDT (design §3 step 5). The regular_spot
        balance gate sizes the positive-funding BUY against THIS wallet, not PAPI
        ``crossMarginFree`` (design §2.4 — the two wallets are distinct). Returns
        the Decimal free USDT (``Decimal(0)`` when USDT is absent but the account
        read succeeded — a real zero, an insufficient-balance fact), or None when
        the read failed (caller fail-closes)."""
        if self._client is None:
            return None
        response = self._client.get_spot_account(timestamp_ms=self._now_ms())
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, dict)
        ):
            return None
        balances = response.body.get("balances")
        if not isinstance(balances, list):
            return None
        for row in balances:
            if isinstance(row, dict) and row.get("asset") == "USDT":
                free = row.get("free")
                if free is None:
                    return Decimal(0)
                try:
                    return Decimal(str(free))
                except (InvalidOperation, ValueError, TypeError):
                    return None
        return Decimal(0)

    def _read_spot_rate_limit_order(self) -> Optional[int]:
        """Standard Spot order-rate limit (design §3 step 5). A regular_spot
        order consumes the spot rate-limit budget, not the PAPI one (§3.5).
        Returns the ORDERS cap or None on a read failure."""
        if self._client is None:
            return None
        response = self._client.get_spot_rate_limit_order(timestamp_ms=self._now_ms())
        if (
            response.transport_error is not None
            or response.http_status is None
            or response.http_status >= 400
            or not isinstance(response.body, list)
        ):
            return None
        for row in response.body:
            if isinstance(row, dict) and row.get("rateLimitType") == "ORDERS":
                limit = row.get("limit")
                if isinstance(limit, int) and limit > 0:
                    return limit
        return None

    def get_snapshot(
        self, coin: str, direction: str, task_type: str = D.TASK_TYPE_OPEN,
    ) -> Optional[D.PreflightSnapshot]:
        """Assemble a fresh preflight snapshot, or ``None`` on any gap.

        ``None`` covers both the dry-run default (no live client) and a live read
        that could not be fully assembled (a missing filter/step, a failed
        balance/position/rate-limit read, or an ambiguous one-way confirmation).
        The service never authorizes a live send on a ``None`` snapshot. A
        readable-but-not-tradable symbol or a two-way position mode is NOT ``None``
        here — it is a fully-read fatal fact surfaced via the snapshot so
        :func:`domain.compute_preflight` can stop the task (amendment rows 1–2).

        ``direction`` drives the regular-spot route decision (design §3 step 4):
        a positive-funding (``forward``) direction reads the platform collateral-
        cap list FRESH and selects ``regular_spot`` when the resolved spot base
        asset hits the list (or the symbol is a TRADIFI bStock), then reads the
        standard Spot account/rate-limit facts that route needs. A negative-
        funding (``reverse``) direction NEVER reads the list and never selects
        ``regular_spot`` — it keeps the existing PAPI path (decision §E-1). Any
        read failure on a needed fact fails the whole snapshot closed (never guess
        a route from a missing read).
        """
        if self._client is None or not self._client.credentials_present:
            return None
        perp = self._read_perp_filters(coin)
        perp_symbol = perp[2] if perp is not None else None
        spot = (
            self._read_spot_leg(coin, perp_symbol)
            if perp_symbol is not None
            else None
        )
        balances = self._read_balances()
        position_mode = self._read_position_mode()
        rate_limit = self._read_rate_limit_order()
        spot_symbol = spot[2] if spot is not None else coin
        est_price = self._read_est_price(spot_symbol)
        # Any base read gap fails closed — never assemble a half-populated snapshot.
        if (
            spot is None
            or perp is None
            or balances is None
            or position_mode is None
            or rate_limit is None
        ):
            return None
        spot_filters, spot_tradable, spot_symbol, spot_base_asset = spot
        perp_filters, perp_tradable, perp_symbol_dict = perp
        contract_type = (
            perp_symbol_dict.get("contractType", "")
            if isinstance(perp_symbol_dict, dict)
            else ""
        )
        # Route decision (design §3 step 4 + 平仓现货卖出重设计). Forward open
        # reads the collateral-cap list fresh; reverse skips it and stays
        # papi_margin. A failed list read on a forward open direction fails
        # closed (never guess). close 任务的 ``direction`` 是反转后的余额检查
        # 方向，route 决策须按持仓方向（反转回来）——close+forward（卖现货）固定
        # regular_spot、不再走 cap 预检；close+reverse（买现货）固定 papi_margin。
        spot_route = D.SPOT_ROUTE_PAPI_MARGIN
        spot_route_reason = D.ROUTE_REASON_PAPI_DEFAULT
        spot_account_usdt: Optional[Decimal] = None
        spot_rate_limit: Optional[int] = None
        cap_exceeded: Optional[bool] = None
        route_dir = direction
        if task_type == D.TASK_TYPE_CLOSE:
            route_dir = D.DIR_REVERSE if direction == D.DIR_FORWARD else D.DIR_FORWARD
        # open+forward 才读 collateral-cap 列表（close 不依赖 cap：close+forward
        # 固定 regular_spot、close+reverse 固定 papi_margin）。
        if direction == D.DIR_FORWARD and task_type != D.TASK_TYPE_CLOSE:
            cap_exceeded = self._read_collateral_cap_hit(spot_base_asset)
            if cap_exceeded is None:
                return None
        spot_route, spot_route_reason = D.decide_spot_route(
            route_dir, contract_type, spot_base_asset, cap_exceeded,
            task_type=task_type,
        )
        if spot_route == D.SPOT_ROUTE_REGULAR_SPOT:
            spot_account_usdt = self._read_spot_account_usdt()
            spot_rate_limit = self._read_spot_rate_limit_order()
            if spot_account_usdt is None or spot_rate_limit is None:
                return None
        spot_endpoint = D.spot_route_endpoint(spot_route)
        return D.PreflightSnapshot(
            spot_filters=spot_filters,
            perp_filters=perp_filters,
            balances=balances,
            position_mode=position_mode,
            est_price=est_price,
            rate_limit_order=rate_limit,
            symbol_tradable=spot_tradable and perp_tradable,
            spot_symbol=spot_symbol if spot_symbol != coin else None,
            spot_route=spot_route,
            spot_route_reason=spot_route_reason,
            spot_route_endpoint=spot_endpoint,
            spot_account_usdt=spot_account_usdt,
            spot_rate_limit_order=spot_rate_limit,
        )

    def check_symbol_legs(self, coin: str) -> dict:
        """Three-state existence probe for a coin's spot + UM legs (S4b / ADR-H5).

        Public-only (unsigned); the probe works without credentials and is safe
        to call from the dry-run record transport as well as the live path.
        Returns ``{"spot": True|False|None, "perp": True|False|None}`` where
        ``True`` = confirmed present, ``False`` = confirmed absent (spot -1121 or
        perp not in the full exchangeInfo list), and ``None`` = indeterminate (a
        read failure the caller does NOT block on).
        """
        spot_status, spot_body = self._read_public_with_status(
            f"{_SPOT_API_BASE}/api/v3/exchangeInfo?symbol={coin}"
        )
        perp_status, perp_body = self._read_public_with_status(
            f"{_FAPI_BASE}/fapi/v1/exchangeInfo"
        )
        spot = _spot_leg_exists(spot_status, spot_body, coin)
        perp = _perp_leg_exists(perp_status, perp_body, coin)
        if spot is False and isinstance(perp_body, dict):
            perp_symbol = _find_symbol(perp_body.get("symbols", []), coin)
            alias = _bstock_spot_alias(coin, perp_symbol)
            if alias is not None:
                alias_status, alias_body = self._read_public_with_status(
                    f"{_SPOT_API_BASE}/api/v3/exchangeInfo?symbol={alias}"
                )
                if _spot_leg_exists(alias_status, alias_body, alias) is True:
                    spot = True
        return {"spot": spot, "perp": perp}
