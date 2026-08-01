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

    def _read_spot_filters(self, coin: str) -> Optional[tuple[dict, bool]]:
        data = self._read_public_json(f"{_SPOT_API_BASE}/api/v3/exchangeInfo?symbol={coin}")
        if not isinstance(data, dict):
            return None
        symbol = _find_symbol(data.get("symbols", []), coin)
        if symbol is None:
            return None
        tradable = symbol.get("status") == "TRADING"
        return _parse_spot_filters(symbol), tradable

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
        self, coin: str, perp_symbol: dict
    ) -> Optional[tuple[dict, bool, str]]:
        """Resolve exact spot first, then the frozen bStock B-suffix alias."""
        exact = self._read_spot_filters(coin)
        if exact is not None and exact[1]:
            return exact[0], exact[1], coin

        alias = _bstock_spot_alias(coin, perp_symbol)
        if alias is not None:
            aliased = self._read_spot_filters(alias)
            if aliased is not None:
                return aliased[0], aliased[1], alias
            # An exact non-trading/missing bStock symbol is not enough to
            # authorize a send when the alias read is incomplete.
            if exact is None or not exact[1]:
                return None

        if exact is not None:
            return exact[0], exact[1], coin
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

    def get_snapshot(self, coin: str) -> Optional[D.PreflightSnapshot]:
        """Assemble a fresh preflight snapshot, or ``None`` on any gap.

        ``None`` covers both the dry-run default (no live client) and a live read
        that could not be fully assembled (a missing filter/step, a failed
        balance/position/rate-limit read, or an ambiguous one-way confirmation).
        The service never authorizes a live send on a ``None`` snapshot. A
        readable-but-not-tradable symbol or a two-way position mode is NOT ``None``
        here — it is a fully-read fatal fact surfaced via the snapshot so
        :func:`domain.compute_preflight` can stop the task (amendment rows 1–2).
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
        # Any read gap fails closed — never assemble a half-populated snapshot
        # (amendment clause 3: account/symbol status, position mode, price/
        # balance, NOTIONAL/MIN_NOTIONAL, the current order rate-limit fact; a
        # missing one is rejected). The rate-limit fact is direction-independent,
        # so a missing read fails the snapshot here.
        if (
            spot is None
            or perp is None
            or balances is None
            or position_mode is None
            or rate_limit is None
        ):
            return None
        spot_filters, spot_tradable, spot_symbol = spot
        perp_filters, perp_tradable, _ = perp
        return D.PreflightSnapshot(
            spot_filters=spot_filters,
            perp_filters=perp_filters,
            balances=balances,
            position_mode=position_mode,
            est_price=est_price,
            rate_limit_order=rate_limit,
            symbol_tradable=spot_tradable and perp_tradable,
            spot_symbol=spot_symbol if spot_symbol != coin else None,
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
