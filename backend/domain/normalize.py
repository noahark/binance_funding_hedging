"""Pure normalization helpers.

No I/O. Decimal fields are passed through as strings straight from the raw
JSON (Binance already returns them as strings); no float touches any
price/rate/quantity path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def filter_of(symbol_obj: Optional[dict], filter_type: str, key: str) -> Optional[str]:
    """Return the value of ``key`` under filterType ``filter_type``, or None.

    Futures symbols use ``MIN_NOTIONAL``/``notional``; spot symbols use the new
    ``NOTIONAL``/``minNotional`` filter. Observed and frozen in the contract
    stage.
    """
    if not symbol_obj:
        return None
    for f in symbol_obj.get("filters", []):
        if f.get("filterType") == filter_type:
            return f.get(key)
    return None


def asset_tag_for(contract_type: str) -> tuple:
    """Map contractType -> (asset_tag, asset_tag_source, asset_tag_confidence)."""
    if contract_type == "TRADIFI_PERPETUAL":
        return ("BSTOCK", "futures_contractType_tradifi_perpetual", "HIGH")
    if contract_type == "PERPETUAL":
        return ("CRYPTO", "futures_contractType_perpetual", "HIGH")
    return ("UNKNOWN", "rule_default_unmapped_contractType", "LOW")


def iso_from_ms(ms_epoch: int) -> str:
    """Render a millisecond epoch as a second-precision UTC ISO string.

    Uses integer division so no float touches the time path.
    """
    seconds = int(ms_epoch) // 1000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def resolve_spot_leg(
    contract_type: str,
    base_asset: str,
    quote_asset: str,
    spot_by_sym: dict,
) -> tuple:
    """Resolve the public spot leg for a futures symbol.

    Returns ``(spot_obj|None, match_type|None)``:

    1. ``exact_symbol`` — ``spot_by_sym[base_asset + quote_asset]`` (normal
       crypto; futures symbol equals spot symbol).
    2. ``bstock_b_suffix_alias`` — only when ``contract_type ==
       "TRADIFI_PERPETUAL"``: ``spot_by_sym[base_asset + "B" + quote_asset]``.
       Binance bStocks use a "B"-suffixed spot/margin symbol, e.g. futures
       ``TSLAUSDT`` -> spot ``TSLABUSDT``.
    3. ``(None, None)`` — no public spot leg.

    The alias is gated on ``TRADIFI_PERPETUAL`` so normal crypto exact-symbol
    matching is never polluted. ``asset_tag_for`` already marks TRADIFI as
    ``BSTOCK``; the existing ``negative_funding_status`` priority then yields
    ``DISABLED_BSTOCK`` for a bStock even when its route is
    ``MARGIN_SPOT_CANDIDATE`` — no classifier change is needed.
    """
    exact = spot_by_sym.get(base_asset + quote_asset)
    if exact is not None:
        return exact, "exact_symbol"
    if contract_type == "TRADIFI_PERPETUAL":
        alias = spot_by_sym.get(base_asset + "B" + quote_asset)
        if alias is not None:
            return alias, "bstock_b_suffix_alias"
    return None, None
