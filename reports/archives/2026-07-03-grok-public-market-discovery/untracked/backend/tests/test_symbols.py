"""Tests for futures/spot symbol join."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from backend.domain.classification import classify_symbol
from backend.domain.symbols import join_futures_spot

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_join_includes_tradifi_perpetual_bstock_with_spot() -> None:
    joined = join_futures_spot(_load("fapi_exchange_info.json"), _load("spot_exchange_info.json"))
    by_symbol = {s.symbol: s for s in joined}

    assert "TSLAUSDT" in by_symbol
    tsla = by_symbol["TSLAUSDT"]
    assert tsla.spot_status == "TRADING"

    result = classify_symbol(tsla)
    assert result.asset_tag == "BSTOCK"
    assert result.negative_funding_status == "DISABLED_BSTOCK"


def test_join_includes_tradifi_perpetual_bstock_perp_only() -> None:
    joined = join_futures_spot(_load("fapi_exchange_info.json"), _load("spot_exchange_info.json"))
    by_symbol = {s.symbol: s for s in joined}

    assert "COINUSDT" in by_symbol
    coin = by_symbol["COINUSDT"]
    assert coin.spot_status is None

    result = classify_symbol(coin)
    assert result.asset_tag == "BSTOCK"
    assert result.route_class == "PERP_ONLY_EXCLUDED"
    assert result.negative_funding_status == "DISABLED_PERP_ONLY"


def test_join_excludes_non_trading_perpetual() -> None:
    joined = join_futures_spot(_load("fapi_exchange_info.json"), _load("spot_exchange_info.json"))
    symbols = {s.symbol for s in joined}

    assert "OMGUSDT" not in symbols


def test_join_perpetual_trading_regression() -> None:
    joined = join_futures_spot(_load("fapi_exchange_info.json"), _load("spot_exchange_info.json"))
    by_symbol = {s.symbol: s for s in joined}

    btc = by_symbol["BTCUSDT"]
    assert btc.perp_status == "TRADING"
    assert btc.spot_status == "TRADING"

    assert classify_symbol(btc).route_class == "MARGIN_SPOT_CANDIDATE"