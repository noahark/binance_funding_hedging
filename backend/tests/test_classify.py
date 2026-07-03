"""Unit tests for the pure classification logic."""
from __future__ import annotations

from backend.domain.classify import classify_route, negative_funding_status


def test_route_margin_spot_candidate():
    assert classify_route("PERPETUAL", "BTCUSDT", True) == "MARGIN_SPOT_CANDIDATE"


def test_route_spot_only_candidate():
    assert classify_route("PERPETUAL", "XVGUSDT", False) == "SPOT_ONLY_CANDIDATE"


def test_route_perp_only_when_no_spot():
    assert classify_route("PERPETUAL", None, False) == "PERP_ONLY_EXCLUDED"


def test_route_tradifi_no_spot_excluded():
    assert classify_route("TRADIFI_PERPETUAL", None, False) == "PERP_ONLY_EXCLUDED"


def test_route_non_perpetual_excluded():
    assert classify_route("CURRENT_QUARTER", "X", True) == "PERP_ONLY_EXCLUDED"


def test_negative_priority_perp_only_beats_bstock():
    # MSTRUSDT/TSLAUSDT are PERP_ONLY + BSTOCK -> DISABLED_PERP_ONLY wins.
    assert negative_funding_status("PERP_ONLY_EXCLUDED", "BSTOCK") == "DISABLED_PERP_ONLY"


def test_negative_bstock_when_route_has_spot():
    assert negative_funding_status("MARGIN_SPOT_CANDIDATE", "BSTOCK") == "DISABLED_BSTOCK"


def test_negative_spot_only():
    assert negative_funding_status("SPOT_ONLY_CANDIDATE", "CRYPTO") == "DISABLED_SPOT_ONLY"


def test_negative_margin_private_required():
    assert (
        negative_funding_status("MARGIN_SPOT_CANDIDATE", "CRYPTO")
        == "PRIVATE_BORROW_VALIDATION_REQUIRED"
    )
