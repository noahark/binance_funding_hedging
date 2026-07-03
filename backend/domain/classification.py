"""Route classification and negative funding status priority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.domain.symbols import SymbolInfo

RouteClass = Literal[
    "MARGIN_SPOT_CANDIDATE",
    "SPOT_ONLY_CANDIDATE",
    "PERP_ONLY_EXCLUDED",
]
AssetTag = Literal["CRYPTO", "BSTOCK", "UNKNOWN"]
AssetTagConfidence = Literal["HIGH", "MEDIUM", "LOW"]
NegativeFundingStatus = Literal[
    "DISABLED_PERP_ONLY",
    "DISABLED_BSTOCK",
    "DISABLED_SPOT_ONLY",
    "PRIVATE_BORROW_VALIDATION_REQUIRED",
]

CURATED_BSTOCK_SYMBOLS: frozenset[str] = frozenset(
    {
        "TSLAUSDT",
        "AAPLUSDT",
        "AMZNUSDT",
        "GOOGUSDT",
        "MSFTUSDT",
        "NVDAUSDT",
        "METAUSDT",
        "COINUSDT",
    }
)

BSTOCK_HEURISTIC_BASES: frozenset[str] = frozenset(
    {"TSLA", "AAPL", "AMZN", "GOOG", "MSFT", "NVDA", "META", "COIN"}
)


@dataclass(frozen=True)
class ClassificationResult:
    """Classification output for a symbol."""

    route_class: RouteClass
    asset_tag: AssetTag
    asset_tag_confidence: AssetTagConfidence
    asset_tag_source: str
    positive_funding_candidate: bool
    negative_funding_status: NegativeFundingStatus
    exclusion_reason: str | None


def classify_route(symbol_info: SymbolInfo) -> RouteClass:
    """Determine route class from joined symbol info."""
    if symbol_info.spot_status is None:
        return "PERP_ONLY_EXCLUDED"
    if symbol_info.spot_margin_allowed is True:
        return "MARGIN_SPOT_CANDIDATE"
    return "SPOT_ONLY_CANDIDATE"


def classify_asset_tag(symbol_info: SymbolInfo) -> tuple[AssetTag, AssetTagConfidence, str]:
    """Detect asset tag via curated list and heuristic."""
    if symbol_info.symbol in CURATED_BSTOCK_SYMBOLS:
        return "BSTOCK", "HIGH", "curated_list"

    if symbol_info.base_asset in BSTOCK_HEURISTIC_BASES:
        return "BSTOCK", "MEDIUM", "heuristic"

    return "CRYPTO", "HIGH", "exchangeInfo"


def negative_funding_status(
    route_class: RouteClass,
    asset_tag: AssetTag,
) -> NegativeFundingStatus:
    """Deterministic priority function for negative funding status."""
    if route_class == "PERP_ONLY_EXCLUDED":
        return "DISABLED_PERP_ONLY"
    if asset_tag == "BSTOCK":
        return "DISABLED_BSTOCK"
    if route_class == "SPOT_ONLY_CANDIDATE":
        return "DISABLED_SPOT_ONLY"
    return "PRIVATE_BORROW_VALIDATION_REQUIRED"


def classify_symbol(symbol_info: SymbolInfo) -> ClassificationResult:
    """Full classification for a joined symbol."""
    route = classify_route(symbol_info)
    asset_tag, confidence, source = classify_asset_tag(symbol_info)
    has_spot = symbol_info.spot_status is not None
    exclusion_reason = "NO_SPOT_MARKET" if route == "PERP_ONLY_EXCLUDED" else None

    return ClassificationResult(
        route_class=route,
        asset_tag=asset_tag,
        asset_tag_confidence=confidence,
        asset_tag_source=source,
        positive_funding_candidate=has_spot,
        negative_funding_status=negative_funding_status(route, asset_tag),
        exclusion_reason=exclusion_reason,
    )