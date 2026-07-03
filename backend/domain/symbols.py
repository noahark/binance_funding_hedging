"""Symbol join logic for USDⓈ-M perpetuals and spot markets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SymbolInfo:
    """Joined futures and optional spot symbol metadata."""

    symbol: str
    base_asset: str
    quote_asset: str
    perp_status: str
    spot_status: str | None
    futures_filters: list[dict[str, Any]]
    spot_filters: list[dict[str, Any]] | None
    spot_margin_allowed: bool | None
    spot_permissions: list[str] | None


def _spot_margin_allowed(spot_symbol: dict[str, Any]) -> bool:
    if "isMarginTradingAllowed" in spot_symbol:
        return bool(spot_symbol["isMarginTradingAllowed"])
    permissions = spot_symbol.get("permissions") or []
    permission_sets = spot_symbol.get("permissionSets") or []
    for perm in permissions:
        if perm == "MARGIN":
            return True
    for perm_set in permission_sets:
        if isinstance(perm_set, list) and "MARGIN" in perm_set:
            return True
        if perm_set == "MARGIN":
            return True
    return False


def _index_spot_symbols(spot_exchange_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for sym in spot_exchange_info.get("symbols", []):
        if sym.get("quoteAsset") == "USDT" and sym.get("status") == "TRADING":
            result[sym["symbol"]] = sym
    return result


def join_futures_spot(
    fapi_exchange_info: dict[str, Any],
    spot_exchange_info: dict[str, Any],
) -> list[SymbolInfo]:
    """Join USDⓈ-M perpetuals with spot markets by base/quote (USDT)."""
    spot_by_symbol = _index_spot_symbols(spot_exchange_info)
    joined: list[SymbolInfo] = []

    for perp in fapi_exchange_info.get("symbols", []):
        if perp.get("contractType") != "PERPETUAL":
            continue
        if perp.get("quoteAsset") != "USDT":
            continue

        symbol = perp["symbol"]
        spot = spot_by_symbol.get(symbol)
        spot_status = spot["status"] if spot else None
        margin_allowed: bool | None = None
        spot_filters: list[dict[str, Any]] | None = None
        spot_permissions: list[str] | None = None

        if spot is not None:
            margin_allowed = _spot_margin_allowed(spot)
            spot_filters = list(spot.get("filters", []))
            spot_permissions = list(spot.get("permissions") or [])

        joined.append(
            SymbolInfo(
                symbol=symbol,
                base_asset=perp["baseAsset"],
                quote_asset=perp["quoteAsset"],
                perp_status=perp.get("status", "UNKNOWN"),
                spot_status=spot_status,
                futures_filters=list(perp.get("filters", [])),
                spot_filters=spot_filters,
                spot_margin_allowed=margin_allowed,
                spot_permissions=spot_permissions,
            )
        )

    return sorted(joined, key=lambda s: s.symbol)