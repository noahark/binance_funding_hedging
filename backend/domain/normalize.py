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


# Real-metal futures baseAssets (stage 2026-07-ui-filter-balance-metal-v1).
# Evidence: reports/api-samples/2026-07-ui-filter-balance-metal-v1/
# 20260708T0928Z/normalized/metal-symbol-summary.json — all five listed as
# contractType=TRADIFI_PERPETUAL on Binance public /fapi/v1/exchangeInfo. A metal
# TRADIFI_PERPETUAL is METAL, not BSTOCK, so the base_asset check runs BEFORE the
# TRADIFI_PERPETUAL -> BSTOCK mapping.
REAL_METAL_BASE_ASSETS = {"XAU", "XAG", "COPPER", "XPT", "XPD"}


def asset_tag_for(contract_type: str, base_asset: str = "") -> tuple:
    """Map contractType/baseAsset -> (asset_tag, asset_tag_source, asset_tag_confidence).

    Order (first match wins):
    1. ``base_asset`` in :data:`REAL_METAL_BASE_ASSETS` -> ``METAL`` (checked
       before TRADIFI so a metal TRADIFI_PERPETUAL is never tagged BSTOCK).
    2. ``contractType == TRADIFI_PERPETUAL`` -> ``BSTOCK``.
    3. ``contractType == PERPETUAL`` -> ``CRYPTO``.
    4. otherwise -> ``UNKNOWN``.

    ``base_asset`` defaults to ``""`` so existing single-argument callers and
    tests keep working; pass the symbol's ``baseAsset`` to enable METAL detection.
    """
    if str(base_asset).upper() in REAL_METAL_BASE_ASSETS:
        return ("METAL", "base_asset_metal_symbol", "HIGH")
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


def _tradable_spot(spot_by_sym: dict, symbol: str) -> Optional[dict]:
    """Return the spot record for ``symbol`` only when it is currently tradable.

    A record resolves only when its ``status == "TRADING"``. Absent, a missing
    ``status``, ``BREAK``, ``HALT``, and every other value fail closed (return
    None): Binance keeps non-trading symbols in ``exchangeInfo`` (frozen evidence
    under ``reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`` —
    AERGOUSDT/XMRUSDT/LITUSDT sit there with ``status="BREAK"`` and a zero
    bookTicker while their perpetuals quote normally), but such a record is not a
    usable spot leg.
    """
    spot = spot_by_sym.get(symbol)
    if spot is not None and spot.get("status") == "TRADING":
        return spot
    return None


def resolve_spot_leg(
    contract_type: str,
    base_asset: str,
    quote_asset: str,
    spot_by_sym: dict,
) -> tuple:
    """Resolve the public spot leg for a futures symbol.

    Returns ``(spot_obj|None, match_type|None)``:

    1. ``exact_symbol`` — ``spot_by_sym[base_asset + quote_asset]`` (normal
       crypto; futures symbol equals spot symbol), but only when that spot record
       is currently tradable (``status == "TRADING"``).
    2. ``bstock_b_suffix_alias`` — only when ``contract_type ==
       "TRADIFI_PERPETUAL"``: ``spot_by_sym[base_asset + "B" + quote_asset]``,
       again only when tradable. Binance bStocks use a "B"-suffixed spot/margin
       symbol, e.g. futures ``TSLAUSDT`` -> spot ``TSLABUSDT``.
    3. ``(None, None)`` — no currently tradable public spot leg.

    Both candidates gate on ``status == "TRADING"`` via :func:`_tradable_spot`, so
    a non-trading exact record (``BREAK``/``HALT``/missing/unknown) is skipped
    before the alias is tried; the alias is then used only if it is itself
    tradable. The alias is also gated on ``TRADIFI_PERPETUAL`` so normal crypto
    exact-symbol matching is never polluted. ``asset_tag_for`` already marks
    TRADIFI as ``BSTOCK``; the existing ``negative_funding_status`` priority then
    yields ``DISABLED_BSTOCK`` for a bStock even when its route is
    ``MARGIN_SPOT_CANDIDATE`` — no classifier change is needed.
    """
    exact = _tradable_spot(spot_by_sym, base_asset + quote_asset)
    if exact is not None:
        return exact, "exact_symbol"
    if contract_type == "TRADIFI_PERPETUAL":
        alias = _tradable_spot(spot_by_sym, base_asset + "B" + quote_asset)
        if alias is not None:
            return alias, "bstock_b_suffix_alias"
    return None, None
