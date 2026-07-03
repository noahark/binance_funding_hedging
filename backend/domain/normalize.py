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
