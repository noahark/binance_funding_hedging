"""Pure classification logic: route_class and negative_funding_status.

The negative_funding_status priority is an explicit ordered sequence and is NOT
interchangeable (see docs/api/public-market-contract.md "Priority for
negative_funding_status").
"""
from __future__ import annotations

from typing import Optional


def classify_route(
    contract_type: str,
    spot_symbol: Optional[str],
    spot_margin_allowed: bool,
) -> str:
    """Determine route_class from contract type and the PUBLIC spot leg.

    Uses only the public spot ``isMarginTradingAllowed`` field. The /sapi
    margin pair lists are NOT used: they require an API key in Phase 1, so
    margin_public.source stays "unverified".
    """
    if contract_type not in ("PERPETUAL", "TRADIFI_PERPETUAL"):
        return "PERP_ONLY_EXCLUDED"
    if spot_symbol is None:
        return "PERP_ONLY_EXCLUDED"
    if spot_margin_allowed:
        return "MARGIN_SPOT_CANDIDATE"
    return "SPOT_ONLY_CANDIDATE"


def negative_funding_status(route_class: str, asset_tag: str) -> str:
    """Ordered priority (do not reorder):

    1. PERP_ONLY_EXCLUDED            -> DISABLED_PERP_ONLY
    2. asset_tag == BSTOCK           -> DISABLED_BSTOCK
    3. SPOT_ONLY_CANDIDATE           -> DISABLED_SPOT_ONLY
    4. otherwise (MARGIN_SPOT_...)   -> PRIVATE_BORROW_VALIDATION_REQUIRED
    """
    if route_class == "PERP_ONLY_EXCLUDED":
        return "DISABLED_PERP_ONLY"
    if asset_tag == "BSTOCK":
        return "DISABLED_BSTOCK"
    if route_class == "SPOT_ONLY_CANDIDATE":
        return "DISABLED_SPOT_ONLY"
    return "PRIVATE_BORROW_VALIDATION_REQUIRED"
