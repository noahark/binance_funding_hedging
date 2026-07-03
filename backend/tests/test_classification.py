"""Tests for route classification and negative funding priority."""

from __future__ import annotations

from backend.domain.classification import (
    classify_symbol,
    negative_funding_status,
)
from backend.domain.symbols import SymbolInfo


def _sym(
    symbol: str,
    *,
    spot_status: str | None = "TRADING",
    margin: bool | None = False,
    base: str | None = None,
) -> SymbolInfo:
    return SymbolInfo(
        symbol=symbol,
        base_asset=base or symbol.replace("USDT", ""),
        quote_asset="USDT",
        perp_status="TRADING",
        spot_status=spot_status,
        futures_filters=[],
        spot_filters=[] if spot_status else None,
        spot_margin_allowed=margin if spot_status else None,
        spot_permissions=None,
    )


def test_margin_spot_candidate() -> None:
    result = classify_symbol(_sym("BTCUSDT", margin=True))
    assert result.route_class == "MARGIN_SPOT_CANDIDATE"
    assert result.positive_funding_candidate is True
    assert result.negative_funding_status == "PRIVATE_BORROW_VALIDATION_REQUIRED"


def test_spot_only_candidate() -> None:
    result = classify_symbol(_sym("SPOTONLYUSDT", margin=False))
    assert result.route_class == "SPOT_ONLY_CANDIDATE"
    assert result.negative_funding_status == "DISABLED_SPOT_ONLY"


def test_perp_only_excluded() -> None:
    result = classify_symbol(_sym("PERPONLYUSDT", spot_status=None))
    assert result.route_class == "PERP_ONLY_EXCLUDED"
    assert result.exclusion_reason == "NO_SPOT_MARKET"
    assert result.positive_funding_candidate is False
    assert result.negative_funding_status == "DISABLED_PERP_ONLY"


def test_bstock_tag_curated() -> None:
    result = classify_symbol(_sym("TSLAUSDT", margin=False))
    assert result.asset_tag == "BSTOCK"
    assert result.asset_tag_confidence == "HIGH"
    assert result.asset_tag_source == "curated_list"
    assert result.negative_funding_status == "DISABLED_BSTOCK"


def test_negative_funding_priority_order() -> None:
    assert negative_funding_status("PERP_ONLY_EXCLUDED", "BSTOCK") == "DISABLED_PERP_ONLY"
    assert negative_funding_status("MARGIN_SPOT_CANDIDATE", "BSTOCK") == "DISABLED_BSTOCK"
    assert negative_funding_status("SPOT_ONLY_CANDIDATE", "CRYPTO") == "DISABLED_SPOT_ONLY"
    assert (
        negative_funding_status("MARGIN_SPOT_CANDIDATE", "CRYPTO")
        == "PRIVATE_BORROW_VALIDATION_REQUIRED"
    )