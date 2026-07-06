"""Task A v0.3 tests — cost-leg chain / net yield / sort_basis / private_account /
coverage / degradation / redaction scan (10-design §1.1-§1.5, §3.3-§3.5).

No network: ``urlopen`` is monkeypatched where the private client is exercised;
pure functions are tested directly; offline snapshots exercise the disabled
three-state. The §3.2 security-gate deny-by-default tests live in
``test_private_client.py``; this file covers the v0.3 computation + assembly
contract and the §3.3 degradation matrix + 落档 redaction scan.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest

from backend.domain.snapshot import (
    SORT_BASIS_ABS,
    SORT_BASIS_NET,
    assemble_borrow_validation,
    assemble_private_account,
    assemble_snapshot,
    compute_daily_from_hourly,
    compute_net_daily_yield,
    resolve_cost_leg_rate,
    select_borrow_candidates,
    sort_rows,
)
from backend.services import private_client
from backend.services.private_client import PrivateClient, _select_chain_tier

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE_DIR = REPO_ROOT / "reports/agent-runs/2026-07-private-account-v1"
FIXTURE = REPO_ROOT / "backend/tests/fixtures/private-account-v1-design.json"


def _row(symbol, daily, *, base=None, route="MARGIN_SPOT_CANDIDATE", tag="CRYPTO", net=None):
    return {
        "symbol": symbol,
        "base_asset": base or symbol.replace("USDT", ""),
        "daily_funding_rate": daily,
        "net_daily_yield": net,
        "route_class": route,
        "asset_tag": tag,
    }


# =========================================================================
# §3.4 net_daily_yield computation vectors (Decimal, neg-zero normalized)
# =========================================================================
@pytest.mark.parametrize(
    "daily,borrow,expected",
    [
        ("-0.00060000", "0.00020000", "0.00040000"),  # §3.4 #1
        ("-0.00060000", "0.00080000", "-0.00020000"),  # §3.4 #2 negative net as-is
        ("0.00030000", None, "0.00030000"),  # §3.4 #3 positive -> no borrow leg
        ("-0.00060000", None, None),  # §3.4 #5 chain broken -> null
        (None, None, None),  # §3.4 #6 null daily -> null
        ("-0.00060000", "0.00060000", "0.00000000"),  # neg-zero normalization
        ("0.00000000", None, "0.00000000"),  # zero funding -> zero net
    ],
)
def test_compute_net_daily_yield_vectors(daily, borrow, expected):
    assert compute_net_daily_yield(daily, borrow) == expected


def test_compute_net_daily_yield_no_float_no_scientific():
    out = compute_net_daily_yield("-0.00000001", "0.00000001")
    assert out == "0.00000000"
    assert "e" not in (out or "").lower()


def test_compute_daily_from_hourly_vector():
    # §3.4 #4: hourly 0.00000500 -> daily 0.00012000 (x24 normalization)
    assert compute_daily_from_hourly("0.00000500") == "0.00012000"
    assert compute_daily_from_hourly(None) is None
    assert compute_daily_from_hourly("") is None
    assert compute_daily_from_hourly("not-a-number") is None


# =========================================================================
# §1.3 cost-leg chain tier selection (pure function)
# =========================================================================
def test_chain_tier1_next_hourly_hits():
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {"BTC": "0.0003"}}, "5")
    assert chain["chain_hit_tier"] == 1
    assert chain["chain_hit_source"] == "next_hourly"
    assert chain["daily_by_asset"] == {"BTC": "0.00000500"}  # raw hourly; x24 at resolve
    assert chain["classic_margin_daily_interest_account_available"] is True


def test_chain_tier2_rate_history_when_e2_empty():
    chain = _select_chain_tier({}, {"BTC": "0.0003"}, {"0": {"BTC": "0.0003"}}, "5")
    assert chain["chain_hit_tier"] == 2
    assert chain["chain_hit_source"] == "rate_history"
    assert chain["daily_by_asset"] == {"BTC": "0.0003"}  # already daily


def test_chain_tier3_cross_margin_when_vip_level_known():
    chain = _select_chain_tier({}, {}, {"5": {"BTC": "0.0004"}, "0": {"BTC": "0.0003"}}, "5")
    assert chain["chain_hit_tier"] == 3
    assert chain["chain_hit_source"] == "cross_margin_tier"
    assert chain["daily_by_asset"] == {"BTC": "0.0004"}


def test_chain_tier4_vip0_reference_when_vip_level_missing():
    chain = _select_chain_tier({}, {}, {"0": {"BTC": "0.0003"}}, None)
    assert chain["chain_hit_tier"] == 4
    assert chain["chain_hit_source"] == "vip0_reference"
    assert chain["daily_by_asset"] == {"BTC": "0.0003"}


def test_chain_broken_when_all_tables_empty():
    chain = _select_chain_tier({}, {}, {}, None)
    assert chain["chain_hit_tier"] is None
    assert chain["chain_hit_source"] is None
    assert chain["daily_by_asset"] == {}
    assert chain["classic_margin_daily_interest_account_available"] is False


def test_resolve_cost_leg_rate_applies_x24_for_next_hourly():
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5")
    # raw hourly 0.00000500 -> daily 0.00012000 (x24 at resolve time)
    assert resolve_cost_leg_rate("BTC", chain) == "0.00012000"


def test_resolve_cost_leg_rate_passes_through_daily_for_other_tiers():
    chain = _select_chain_tier({}, {}, {"0": {"BTC": "0.00030000"}}, None)
    assert resolve_cost_leg_rate("BTC", chain) == "0.00030000"


def test_resolve_cost_leg_rate_none_when_asset_absent_or_broken():
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5")
    assert resolve_cost_leg_rate("DOGE", chain) is None  # asset not in tier table
    assert resolve_cost_leg_rate("BTC", None) is None
    broken = _select_chain_tier({}, {}, {}, None)
    assert resolve_cost_leg_rate("BTC", broken) is None


# =========================================================================
# §1.2 / §3.5 sort_basis (net reversal + Phase 2 abs regression)
# =========================================================================
def test_sort_net_reversal_core_assertion():
    # §3.5: AUSDT (net 0.00040000) ranks above BUSDT (net 0.00010000) although
    # BUSDT has the larger abs daily funding (0.00070000 > 0.00060000). Net yield
    # reverses the raw-rate ranking -- the core opportunity-quality assertion.
    rows = [
        _row("BUSDT", "-0.00070000", net="0.00010000"),  # bigger abs daily, expensive borrow
        _row("AUSDT", "-0.00060000", net="0.00040000"),  # smaller abs daily, cheap borrow
    ]
    order = [r["symbol"] for r in sort_rows(rows, SORT_BASIS_NET)]
    assert order == ["AUSDT", "BUSDT"]


def test_sort_net_signed_desc_nulls_last_symbol_tiebreak():
    rows = [
        _row("DUSDT", "-0.00060000", net=None),       # null -> last
        _row("CUSDT", "-0.00060000", net="-0.00020000"),  # negative net ranks lower
        _row("AUSDT", "-0.00060000", net="0.00040000"),
        _row("BUSDT", "-0.00060000", net="0.00040000"),   # tie -> symbol ASC (B after A)
    ]
    order = [r["symbol"] for r in sort_rows(rows, SORT_BASIS_NET)]
    assert order == ["AUSDT", "BUSDT", "CUSDT", "DUSDT"]


def test_sort_abs_basis_is_phase2_regression():
    # §3.5 disabled basis: abs(daily) DESC, nulls last, symbol ASC (Phase 2 total order).
    rows = [
        _row("DUSDT", None),
        _row("AUSDT", "0.00060000"),
        _row("BUSDT", "0.00060000"),
        _row("CUSDT", "0.00030000"),
    ]
    order = [r["symbol"] for r in sort_rows(rows, SORT_BASIS_ABS)]
    assert order == ["AUSDT", "BUSDT", "CUSDT", "DUSDT"]


def test_sort_default_basis_is_abs():
    # Existing callers pass no basis -> Phase 2 abs behavior (no regression).
    rows = [_row("BUSDT", "0.0009"), _row("AUSDT", "0.0001")]
    assert sort_rows(rows)[0]["symbol"] == "BUSDT"


# =========================================================================
# §1.5 borrow probe coverage (cap + truncation + dedup)
# =========================================================================
def test_select_borrow_candidates_caps_and_marks_truncation():
    rows = [_row(f"S{i}USDT", "-0.00001", base=f"C{i}") for i in range(6)]
    out = select_borrow_candidates(rows, max_calls=4)
    assert out["probed_assets"] == ["C0", "C1", "C2", "C3"]  # priority by abs DESC
    assert out["truncated_assets"] == {"C4", "C5"}
    assert out["coverage"] == {"probed": 4, "skipped": 2, "reason": "rate_limit_budget"}


def test_select_borrow_candidates_no_reason_when_within_cap():
    rows = [_row("AUSDT", "-0.0001", base="A"), _row("BUSDT", "-0.0002", base="B")]
    out = select_borrow_candidates(rows, max_calls=50)
    assert out["coverage"]["reason"] is None
    assert out["coverage"]["skipped"] == 0


def test_select_borrow_candidates_only_neg_margin_spot_crypto():
    rows = [
        _row("AUSDT", "-0.0001", base="A"),                       # candidate
        _row("BUSDT", "0.0001", base="B"),                        # positive -> excluded
        _row("CUSDT", "-0.0001", base="C", route="SPOT_ONLY_CANDIDATE"),  # wrong route
        _row("DUSDT", "-0.0001", base="D", tag="BSTOCK"),         # wrong tag
        _row("EUSDT", None, base="E"),                            # null daily -> excluded
    ]
    out = select_borrow_candidates(rows, max_calls=50)
    assert out["probed_assets"] == ["A"]
    assert out["coverage"]["probed"] == 1


def test_select_borrow_candidates_dedup_by_base_asset():
    rows = [
        _row("A1USDT", "-0.0002", base="A"),
        _row("A2USDT", "-0.0001", base="A"),  # same base_asset -> deduped
    ]
    out = select_borrow_candidates(rows, max_calls=50)
    assert out["probed_assets"] == ["A"]
    assert out["coverage"]["probed"] == 1


def test_borrow_validation_truncated_state():
    bv = assemble_borrow_validation(
        {"symbol": "XUSDT", "base_asset": "X"},
        {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {}, "daily_interest_vip0_by_coin": {}},
        {}, "t", None, truncated=True,
    )
    assert bv["verified"] is False
    assert bv["error"] == "not_probed_this_round"  # no silent truncation
    assert bv["classic_margin"]["daily_interest_account"] is None
    assert bv["checked_at"] is None


# =========================================================================
# §1.4 private_account + anti-double-count hard rule
# =========================================================================
def test_assemble_private_account_anti_double_count():
    # total = sum(unified totalWalletBalance priced) + sum(spot free+locked priced).
    # um/cm sub-fields inside totalWalletBalance are NOT re-added; um_positions
    # nominal is NEVER counted (exposure view only).
    unified = [
        {"asset": "BTC", "totalWalletBalance": "1.5"},   # 1.5 * 60000 = 90000
        {"asset": "USDT", "totalWalletBalance": "100"},  # stable -> 100
    ]
    spot = [
        {"asset": "ETH", "free": "2", "locked": "0.5"},  # 2.5 * 3000 = 7500
        {"asset": "USDC", "free": "50", "locked": "0"},  # stable -> 50
    ]
    um = [{"symbol": "BTCUSDT", "positionAmt": "10", "entryPrice": "60000"}]  # nominal NOT counted
    price_map = {"BTCUSDT": "60000", "ETHUSDT": "3000"}
    block, warnings = assemble_private_account(
        unified, spot, um, price_map, checked_at="2026-07-06T00:00:00Z", error=None
    )
    assert block["verified"] is True
    # 90000 + 100 + 7500 + 50 = 97650; um nominal (10*60000=600000) excluded.
    assert block["total_value_usdt"] == "97650.00000000"
    assert block["balances_unified"] == [
        {"asset": "BTC", "total_balance": "1.5"},
        {"asset": "USDT", "total_balance": "100"},
    ]
    assert block["balances_spot"][0] == {"asset": "ETH", "free": "2", "locked": "0.5"}
    assert block["um_positions"][0]["position_side"] == "LONG"
    assert block["valuation"]["price_source"] == "api_v3_ticker_price"
    assert block["valuation"]["priced_at"] == "2026-07-06T00:00:00Z"
    assert warnings == []


def test_assemble_private_account_disabled_state():
    block, warnings = assemble_private_account(
        None, None, None, {}, checked_at=None, error="private_channel_disabled"
    )
    assert block["verified"] is False
    assert block["balances_unified"] == []
    assert block["balances_spot"] == []
    assert block["um_positions"] == []
    assert block["total_value_usdt"] is None
    assert block["checked_at"] is None
    assert block["valuation"]["priced_at"] is None
    assert block["error"] == "private_channel_disabled"


def test_assemble_private_account_no_price_counts_zero_with_warning():
    unified = [{"asset": "WEIRD", "totalWalletBalance": "5"}]  # no WEIRDUSDT price
    block, warnings = assemble_private_account(
        unified, [], [], {}, checked_at="t", error=None
    )
    assert block["total_value_usdt"] == "0.00000000"  # counted at 0, not dropped
    assert any("WEIRD" in w and "0" in w for w in warnings)


def test_assemble_private_account_partial_failure_keeps_verified():
    # E3 failed (unified None) but E6 ok -> verified=true, unified empty, spot filled.
    block, _ = assemble_private_account(
        None, [{"asset": "USDT", "free": "10", "locked": "0"}], [], {"USDTUSDT": "1"},
        checked_at="t", error=None,
    )
    assert block["verified"] is True
    assert block["balances_unified"] == []
    assert block["total_value_usdt"] == "10.00000000"


def test_infer_position_side_short_for_negative():
    # §2.A.3 E4 open item: positionSide inferred from positionAmt sign.
    block, _ = assemble_private_account(
        [], [], [{"symbol": "ETHUSDT", "positionAmt": "-2.5"}], {}, checked_at="t", error=None
    )
    assert block["um_positions"][0]["position_side"] == "SHORT"


# =========================================================================
# Private fetcher mappings (urlopen monkeypatched; no network)
# =========================================================================
class _FakeResp:
    def __init__(self, body, status=200):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _client_with_routes(routes, monkeypatch):
    """PrivateClient whose urlopen routes by logical-path substring."""
    client = PrivateClient(
        "k" * 64, "s" * 64, user_agent="t", timeout=5,
        recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60,
    )
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        for needle, payload in routes.items():
            if needle in url:
                return _FakeResp(json.dumps(payload))
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
    return client


def test_fetch_unified_balances_maps_total_balance(monkeypatch):
    client = _client_with_routes({
        "/papi/v1/balance": [{"asset": "BTC", "totalWalletBalance": "1.5", "umWalletBalance": "0.3"}],
    }, monkeypatch)
    out = client.fetch_unified_balances()
    assert out == [{"asset": "BTC", "totalWalletBalance": "1.5", "umWalletBalance": "0.3"}]


def test_fetch_spot_balances_omit_zero(monkeypatch):
    client = _client_with_routes({
        "/api/v3/account": {
            "balances": [{"asset": "USDT", "free": "10", "locked": "0"}],
            "uid": 123,
        },
    }, monkeypatch)
    assert client.fetch_spot_balances() == [{"asset": "USDT", "free": "10", "locked": "0"}]


def test_fetch_cost_leg_chain_next_hourly_and_isisolated(monkeypatch):
    # H_intake fix: E2 MUST send isIsolated=false (else 400 -3026).
    captured = {}

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        captured["last_url"] = url
        if "/sapi/v1/account/info" in url:
            return _FakeResp(json.dumps({"vipLevel": 5, "isPortfolioMarginRetailEnabled": True}))
        if "/sapi/v1/margin/next-hourly-interest-rate" in url:
            assert "isIsolated=false" in url, "E2 must send isIsolated=false (H_intake fix)"
            assert "assets=BTC%2CETH" in url or "assets=BTC,ETH" in url
            return _FakeResp(json.dumps([
                {"asset": "BTC", "nextHourlyInterestRate": "0.00000500"},
                {"asset": "ETH", "nextHourlyInterestRate": "0.00000400"},
            ]))
        if "/sapi/v1/margin/interestRateHistory" in url:
            return _FakeResp(json.dumps([
                {"asset": "BTC", "timestamp": 1, "dailyInterestRate": "0.0003", "vipLevel": 5},
            ]))
        if "/sapi/v1/margin/crossMarginData" in url:
            return _FakeResp(json.dumps([
                {"vipLevel": 0, "coin": "BTC", "dailyInterest": "0.0003"},
                {"vipLevel": 5, "coin": "BTC", "dailyInterest": "0.0004"},
            ]))
        raise AssertionError(f"unexpected url: {url}")

    client = PrivateClient(
        "k" * 64, "s" * 64, user_agent="t", timeout=5,
        recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60,
    )
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)
    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)

    chain = client.fetch_cost_leg_chain(["BTC", "ETH"])
    assert chain["chain_hit_tier"] == 1
    assert chain["chain_hit_source"] == "next_hourly"
    assert chain["vip_level"] == "5"
    # raw hourly retained; x24 applied at resolve_cost_leg_rate.
    assert resolve_cost_leg_rate("BTC", chain) == "0.00012000"
    assert resolve_cost_leg_rate("ETH", chain) == "0.00009600"


def test_fetch_cost_leg_chain_degrades_to_vip0(monkeypatch):
    # E2 returns empty, E2b empty, E5 missing -> tier 4 vip0_reference.
    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/sapi/v1/account/info" in url:
            return _FakeResp(json.dumps({}))
        if "/sapi/v1/margin/next-hourly-interest-rate" in url:
            return _FakeResp(json.dumps([]))
        if "/sapi/v1/margin/interestRateHistory" in url:
            return _FakeResp(json.dumps([]))
        if "/sapi/v1/margin/crossMarginData" in url:
            return _FakeResp(json.dumps([
                {"vipLevel": 0, "coin": "BTC", "dailyInterest": "0.0003"},
            ]))
        raise AssertionError(f"unexpected url: {url}")

    client = PrivateClient(
        "k" * 64, "s" * 64, user_agent="t", timeout=5,
        recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60,
    )
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)
    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
    chain = client.fetch_cost_leg_chain(["BTC"])
    assert chain["chain_hit_tier"] == 4
    assert chain["chain_hit_source"] == "vip0_reference"
    assert resolve_cost_leg_rate("BTC", chain) == "0.00030000"


def test_e1_e1b_whitelisted_but_no_fetcher_calls_them():
    # §2: E1/E1b are discovery-only; registered in the whitelist (GET passes)
    # but NO high-level fetcher in private_client.py calls them this stage.
    assert PrivateClient._require_whitelisted("GET", "/papi/v1/margin/marginInterestHistory")
    assert PrivateClient._require_whitelisted("GET", "/papi/v1/portfolio/interest-history")
    src = Path(private_client.__file__).read_text(encoding="utf-8")
    # Everything after the WHITELIST block = fetcher bodies + helpers; neither
    # discovery-only path may appear there (they live only in the WHITELIST dict).
    after_whitelist = src[src.index("class PrivateEndpointError"):]
    assert "marginInterestHistory" not in after_whitelist
    assert "portfolio/interest-history" not in after_whitelist


# =========================================================================
# §3.3 degradation matrix — four states each schema-VALID (no 503)
# =========================================================================
def _two_rows():
    return [
        {
            "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT",
            "asset_tag": "CRYPTO", "asset_tag_source": "x", "asset_tag_confidence": "HIGH",
            "route_class": "MARGIN_SPOT_CANDIDATE", "positive_funding_enabled": True,
            "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
            "futures": {"symbol": "BTCUSDT", "status": "TRADING", "contract_type": "PERPETUAL",
                        "mark_price": "60000", "index_price": "60000", "last_funding_rate": "-0.0006",
                        "next_funding_time": 1, "min_notional": "5", "step_size": "0.001"},
            "spot": {"symbol": "BTCUSDT", "status": "TRADING", "exists": True,
                     "match_type": "exact_symbol", "min_notional": "5", "step_size": "0.001"},
            "margin_public": {"public_cross_margin_pair": None, "source": "unverified"},
            "funding_history": [], "ui_flags": [],
            "funding_interval_hours": 8, "daily_funding_rate": "-0.00060000",
        },
        {
            "symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT",
            "asset_tag": "CRYPTO", "asset_tag_source": "x", "asset_tag_confidence": "HIGH",
            "route_class": "MARGIN_SPOT_CANDIDATE", "positive_funding_enabled": True,
            "negative_funding_status": "PRIVATE_BORROW_VALIDATION_REQUIRED",
            "futures": {"symbol": "ETHUSDT", "status": "TRADING", "contract_type": "PERPETUAL",
                        "mark_price": "3000", "index_price": "3000", "last_funding_rate": "0.0003",
                        "next_funding_time": 1, "min_notional": "5", "step_size": "0.001"},
            "spot": {"symbol": "ETHUSDT", "status": "TRADING", "exists": True,
                     "match_type": "exact_symbol", "min_notional": "5", "step_size": "0.001"},
            "margin_public": {"public_cross_margin_pair": None, "source": "unverified"},
            "funding_history": [], "ui_flags": [],
            "funding_interval_hours": 8, "daily_funding_rate": "0.00030000",
        },
    ]


def _assemble_with_private(rows, private_account, classic_ref, cost_leg, checked_at, error):
    probed = select_borrow_candidates(rows, 50)
    for r in rows:
        base = r["base_asset"]
        rate = resolve_cost_leg_rate(base, cost_leg) if (base in probed["probed_assets"] and cost_leg) else None
        r["net_daily_yield"] = compute_net_daily_yield(r["daily_funding_rate"], rate)
        r["borrow_rate_source"] = cost_leg.get("chain_hit_source") if rate else None
        r["borrow_validation"] = assemble_borrow_validation(
            r, classic_ref, {}, checked_at, error, daily_interest_account=rate,
        )
    available = bool(classic_ref and cost_leg and cost_leg.get("chain_hit_tier") is not None)
    return assemble_snapshot(
        rows, generated_at="2026-07-06T00:00:00Z", data_time="2026-07-06T00:00:00Z",
        source_sample_id="degrade-test", private_channel_status="enabled" if classic_ref else "disabled",
        sort_basis=SORT_BASIS_NET if available else SORT_BASIS_ABS,
        private_account=private_account,
        borrow_validation_summary={
            "coverage": probed["coverage"],
            "classic_margin_daily_interest_account_available": available,
            "chain_hit_tier": cost_leg.get("chain_hit_tier") if cost_leg else None,
            "chain_hit_source": cost_leg.get("chain_hit_source") if cost_leg else None,
        },
    )


def _enabled_pa():
    pa, _ = assemble_private_account(
        [{"asset": "BTC", "totalWalletBalance": "1"}], [], [], {"BTCUSDT": "60000"},
        checked_at="2026-07-06T00:00:00Z", error=None,
    )
    return pa


@pytest.fixture(scope="session")
def v03_schema():
    return json.loads(
        (REPO_ROOT / "schemas/api/public-market/snapshot.schema.json").read_text()
    )


def test_degradation_env_missing_schema_pass(v03_schema):
    # State 1: private channel disabled (env missing). private_account renders the
    # three-state disabled block (verified=false, empty arrays, total null) — the
    # public snapshot still renders (§1.4).
    disabled_pa, _ = assemble_private_account(
        None, None, None, {}, checked_at=None, error="private_channel_disabled"
    )
    rows = _two_rows()
    classic_ref = None
    snap = _assemble_with_private(rows, disabled_pa, classic_ref, None, None, "private_channel_disabled")
    jsonschema.validate(snap, v03_schema)
    assert snap["sort_basis"] == SORT_BASIS_ABS
    assert snap["private_account"]["verified"] is False
    assert snap["private_account"]["total_value_usdt"] is None
    # negative-funding row with no borrow rate -> net null
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    assert btc["net_daily_yield"] is None


def test_degradation_e3_fail_schema_pass(v03_schema):
    # E3 (unified) failed but channel enabled -> verified=true partial block.
    pa, _ = assemble_private_account(
        None, [{"asset": "USDT", "free": "10", "locked": "0"}], [], {},
        checked_at="2026-07-06T00:00:00Z", error=None,
    )
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5")
    rows = _two_rows()
    snap = _assemble_with_private(rows, pa, {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {}, "daily_interest_vip0_by_coin": {}}, chain, "2026-07-06T00:00:00Z", None)
    jsonschema.validate(snap, v03_schema)
    assert snap["private_account"]["verified"] is True
    assert snap["private_account"]["balances_unified"] == []


def test_degradation_e6_fail_schema_pass(v03_schema):
    # E6 (spot) failed but channel enabled -> verified=true partial block.
    pa, _ = assemble_private_account(
        [{"asset": "BTC", "totalWalletBalance": "1"}], None, [], {"BTCUSDT": "60000"},
        checked_at="2026-07-06T00:00:00Z", error=None,
    )
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5")
    rows = _two_rows()
    snap = _assemble_with_private(rows, pa, {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {}, "daily_interest_vip0_by_coin": {}}, chain, "2026-07-06T00:00:00Z", None)
    jsonschema.validate(snap, v03_schema)
    assert snap["private_account"]["balances_spot"] == []


def test_degradation_chain_all_broken_schema_pass(v03_schema):
    # E2/E2b/E5 + crossMarginData all empty -> chain tier None. Classic_ref still
    # present (channel enabled) -> sort_basis abs (cost leg NOT available),
    # negative-funding rows net null, schema PASS.
    pa = _enabled_pa()
    broken = _select_chain_tier({}, {}, {}, None)
    rows = _two_rows()
    snap = _assemble_with_private(
        rows, pa,
        {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {}, "daily_interest_vip0_by_coin": {}},
        broken, "2026-07-06T00:00:00Z", None,
    )
    jsonschema.validate(snap, v03_schema)
    assert snap["sort_basis"] == SORT_BASIS_ABS
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    assert btc["net_daily_yield"] is None
    assert btc["borrow_rate_source"] is None
    assert snap["borrow_validation"]["chain_hit_tier"] is None


def test_enabled_chain_hit_sort_basis_net_and_net_yield_computed(v03_schema):
    pa = _enabled_pa()
    chain = _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5")  # hourly -> daily 0.00012
    rows = _two_rows()
    snap = _assemble_with_private(
        rows, pa,
        {"pair_listed_by_symbol": {"BTCUSDT": True}, "asset_borrowable_by_name": {"BTC": True},
         "daily_interest_vip0_by_coin": {"BTC": "0.0003"}},
        chain, "2026-07-06T00:00:00Z", None,
    )
    jsonschema.validate(snap, v03_schema)
    assert snap["sort_basis"] == SORT_BASIS_NET
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    # net = abs(-0.0006) - 0.00012 = 0.00048
    assert btc["net_daily_yield"] == "0.00048000"
    assert btc["borrow_rate_source"] == "next_hourly"
    assert btc["borrow_validation"]["classic_margin"]["daily_interest_account"] == "0.00012000"
    assert snap["borrow_validation"]["chain_hit_tier"] == 1


# =========================================================================
# §3.3 落档 redaction scan — committed fixtures/reports carry no real account
# numerics (account-level fields redacted per §2.A.4).
# =========================================================================
# Context segments that mark a value as account-level in the CONTRACT shape
# (design fixture). Values under these paths must be placeholders (<AMOUNT>/<ID>)
# or null. Market-data paths (futures.*/spot.*) are public/synthetic and exempt.
_ACCOUNT_CONTEXT_SEGMENTS = {
    "balances_unified", "balances_spot", "um_positions",
    "private_account", "borrow_validation", "total_value_usdt", "valuation",
}
# Raw camelCase field names that are account-level in the CAPTURED sample shape
# (E3/E4/E6/W4/E2/E2b raw responses). Used only against account-level sample
# files (market-level allPairs/allAssets/crossMarginData/ticker-price excluded).
_RAW_ACCOUNT_FIELDS = {
    "totalWalletBalance", "crossMarginAsset", "crossMarginBorrowed", "crossMarginFree",
    "crossMarginInterest", "crossMarginLocked", "umWalletBalance", "umUnrealizedPNL",
    "cmWalletBalance", "cmUnrealizedPNL", "negativeBalance", "nextHourlyInterestRate",
    "dailyInterestRate", "amount", "borrowLimit",
    "positionAmt", "entryPrice", "unRealizedProfit", "liquidationPrice",
    "free", "locked",
}
# Captured sample files that are account-level (evidence-index account-level=True);
# market-level files (allPairs/allAssets/crossMarginData/ticker-price) are public
# and intentionally not redacted, so they are excluded from this scan.
_ACCOUNT_LEVEL_SAMPLE_BASENAMES = {
    "sapi-v1-account-info.json",
    "sapi-v1-margin-next-hourly-interest-rate.json",
    "sapi-v1-margin-interestRateHistory.json",
    "papi-v1-balance.json",
    "papi-v1-um-positionRisk.json",
    "api-v3-account.json",
    "papi-v1-margin-marginInterestHistory.json",
    "papi-v1-portfolio-interest-history.json",
    # maxBorrowable-<asset>.json matched by prefix below
}


def _is_real_decimal(s):
    # A real captured numeric (not a placeholder). Placeholders: <AMOUNT>, <ID>, null.
    if not isinstance(s, str) or s == "" or s.startswith("<"):
        return False
    try:
        Decimal(s)
        return True
    except Exception:
        return False


def _walk_contract_account_values(obj, path_segments=()):
    """Yield (path, value) for string values inside account-context paths."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            segs = path_segments + (k,)
            in_ctx = any(s in _ACCOUNT_CONTEXT_SEGMENTS for s in segs)
            if isinstance(v, str) and in_ctx:
                yield (".".join(segs), v)
            yield from _walk_contract_account_values(v, segs)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_contract_account_values(v, path_segments)


def _walk_raw_account_fields(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _RAW_ACCOUNT_FIELDS and isinstance(v, str):
                yield (f"{path}.{k}", v)
            yield from _walk_raw_account_fields(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_raw_account_fields(v, f"{path}[{i}]")


def test_redaction_scan_design_fixture():
    # The design fixture's account-context fields must all be redacted placeholders.
    fx = json.loads(FIXTURE.read_text())
    leaks = [(p, v) for p, v in _walk_contract_account_values(fx) if _is_real_decimal(v)]
    assert leaks == [], f"unredacted account numerics in design fixture: {leaks}"


def test_redaction_scan_captured_samples():
    # The H_intake captured ACCOUNT-LEVEL samples must be redacted (bookkeeper
    # capture-time). Market-level samples (allPairs/allAssets/crossMarginData/
    # ticker-price) are public and excluded.
    sample_dir = REPO_ROOT / "reports/api-samples/2026-07-private-account-v1"
    leaks = []
    for path in sample_dir.rglob("*.json"):
        base = path.name
        is_account = (
            base in _ACCOUNT_LEVEL_SAMPLE_BASENAMES
            or base.startswith("papi-v1-margin-maxBorrowable-")
        )
        if not is_account:
            continue
        try:
            obj = json.loads(path.read_text())
        except Exception:
            continue
        for p, v in _walk_raw_account_fields(obj):
            if _is_real_decimal(v):
                leaks.append((base, p, v))
    assert leaks == [], f"unredacted captured account numerics: {leaks}"


# =========================================================================
# §3.2 hygiene — no websocket/listenKey scaffolding; single HMAC exit intact
# =========================================================================
def test_no_websocket_listenkey_scaffolding():
    bad = []
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        if "tests" in py.relative_to(REPO_ROOT).parts:
            continue
        text = py.read_text(encoding="utf-8")
        low = text.lower()
        if "websocket" in low or "listenkey" in low or "wss://" in low:
            bad.append(str(py.relative_to(REPO_ROOT)))
    assert bad == [], f"websocket/listenKey scaffolding found: {bad}"


def test_single_hmac_exit_unchased_after_v03():
    # Re-asserts the grep guard from test_private_client for completeness: only
    # private_client.py touches hmac/hashlib/signature after the v0.3 expansion.
    import re
    hmac_re = re.compile(r"\bhmac\b")
    hash_re = re.compile(r"hashlib")
    sig_re = re.compile(r"signature\s*=")
    bad = []
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        rel = py.relative_to(REPO_ROOT)
        if "tests" in rel.parts or rel.name == "private_client.py":
            continue
        text = py.read_text(encoding="utf-8")
        if hmac_re.search(text) or hash_re.search(text) or sig_re.search(text):
            bad.append(str(rel))
    assert bad == [], f"hmac/hashlib/signature outside private_client.py: {bad}"


def test_offline_snapshot_v03_fields_validate(v03_schema):
    # Offline (channel disabled): sort_basis=abs, private_account omitted (disabled),
    # rows carry net_daily_yield/borrow_rate_source (null), schema PASS.
    from backend.config import Config
    from backend.services.snapshot_service import SnapshotService
    snap = SnapshotService(Config(offline=True)).build_snapshot()
    jsonschema.validate(snap, v03_schema)
    assert snap["sort_basis"] == SORT_BASIS_ABS
    assert snap["private_account"]["verified"] is False  # three-state disabled block
    assert snap["private_account"]["balances_unified"] == []
    assert snap["private_account"]["total_value_usdt"] is None
    assert snap["borrow_validation"]["coverage"]["probed"] == 0
    for r in snap["rows"]:
        assert r["net_daily_yield"] is None or isinstance(r["net_daily_yield"], str)
        assert r["borrow_rate_source"] is None
        assert "daily_interest_account" in r["borrow_validation"]["classic_margin"]


# =========================================================================
# round1 BLOCKER fixes (embedded-review-a-round1 → round2)
#   A: §1.5 top-level warnings entry when coverage.skipped > 0
#   B: §1.4 private_account three-state gated on classic_ref (same as
#      borrow_validation), not on unified/spot None-ness
# =========================================================================
def test_truncation_appends_top_level_warning(v03_schema):
    # §1.5: when borrow_validation.coverage.skipped > 0 a top-level warnings
    # entry MUST appear alongside the coverage block (round1 blocker A). The
    # offline snapshot's schema-valid rows are re-assembled with a synthetic
    # truncation summary so the row pipeline is not re-run.
    from backend.config import Config
    from backend.services.snapshot_service import SnapshotService

    rows = SnapshotService(Config(offline=True)).build_snapshot()["rows"]
    snap = assemble_snapshot(
        rows,
        generated_at="2026-07-06T00:00:00Z",
        data_time="2026-07-06T00:00:00Z",
        source_sample_id="round2-truncation",
        borrow_validation_summary={
            "coverage": {"probed": 1, "skipped": 2, "reason": "rate_limit_budget"},
            "classic_margin_daily_interest_account_available": False,
            "chain_hit_tier": None,
            "chain_hit_source": None,
        },
    )
    jsonschema.validate(snap, v03_schema)
    joined = "\n".join(snap["warnings"])
    assert "truncated" in joined
    assert "not_probed_this_round" in joined
    assert "2 candidate" in joined  # the skipped count surfaces in the message


class _Round2StubPublic:
    offline = True
    request_log: dict = {}

    def __init__(self, raw):
        self._raw = raw

    def fetch_raw(self):
        return self._raw

    def fetch_ticker_price_map(self):
        return {}


class _Round2StubPrivate:
    """Minimal PrivateClient stub driving SnapshotService.build_snapshot."""

    def __init__(self, *, classic_ref, unified=None, um=None, spot=None,
                 cost_leg=None, last_error=None):
        self._classic_ref = classic_ref
        self._unified = unified
        self._um = um
        self._spot = spot
        self._cost_leg = cost_leg
        self.last_error = last_error

    def fetch_classic_reference(self):
        return self._classic_ref

    def fetch_cost_leg_chain(self, assets):
        return self._cost_leg

    def fetch_unified_balances(self):
        return self._unified

    def fetch_um_positions(self):
        return self._um

    def fetch_spot_balances(self):
        return self._spot

    def fetch_max_borrowable(self, asset):
        return None


def test_private_account_disabled_when_classic_ref_none_even_if_accounts_return(
    v03_schema, raw_inputs,
):
    # §1.4 heading: private_account 三态语义同 borrow_validation. classic_ref None
    # (channel disabled/failed) gates private_account verified=false EVEN WHEN
    # E3/E4/E6 would return data (round1 blocker B). Pre-fix the unified balance
    # would have produced verified=true while every row was verified=false.
    from backend.config import Config
    from backend.services.snapshot_service import SnapshotService

    raw = {
        "futures_exchange_info": raw_inputs["futures"],
        "premium_index": raw_inputs["premium"],
        "spot_exchange_info": raw_inputs["spot"],
        "funding_history_by_sym": raw_inputs["funding"],
        "funding_interval_by_sym": {},
        "warnings": [],
    }
    service = SnapshotService(Config(offline=True))
    service.client = _Round2StubPublic(raw)
    service._private = _Round2StubPrivate(
        classic_ref=None,                                       # channel failed
        unified=[{"asset": "BTC", "totalWalletBalance": "1"}],  # E3 would succeed
        um=[],
        spot=[{"asset": "USDT", "free": "10", "locked": "0"}],  # E6 would succeed
        last_error="classic_reference_failed",
    )
    snap = service.build_snapshot()
    jsonschema.validate(snap, v03_schema)
    assert snap["private_channel"] == "disabled"
    assert snap["private_account"]["verified"] is False
    assert snap["private_account"]["balances_unified"] == []
    assert snap["private_account"]["balances_spot"] == []
    assert snap["private_account"]["um_positions"] == []
    assert snap["private_account"]["total_value_usdt"] is None
    assert snap["private_account"]["error"] == "classic_reference_failed"
    # borrow_validation follows the same channel state -> every row disabled too
    for r in snap["rows"]:
        assert r["borrow_validation"]["verified"] is False
