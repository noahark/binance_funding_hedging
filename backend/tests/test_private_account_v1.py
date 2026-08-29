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
from backend.domain.snapshot import _cross_margin_borrowed_value_usdt
from backend.domain.snapshot import _max_borrowable_value_usdt
from backend.domain.snapshot import _user_min_borrow_value_usdt
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
    assert out["rate_probe_assets"] == ["C0", "C1", "C2", "C3", "C4", "C5"]  # full pool
    assert out["borrowability_probe_assets"] == ["C0", "C1", "C2", "C3"]  # first 4
    assert out["borrowability_unprobed_assets"] == {"C4", "C5"}  # rest, rate covered
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
    assert out["rate_probe_assets"] == ["A"]
    assert out["borrowability_probe_assets"] == ["A"]
    assert out["coverage"]["probed"] == 1


def test_select_borrow_candidates_dedup_by_base_asset():
    rows = [
        _row("A1USDT", "-0.0002", base="A"),
        _row("A2USDT", "-0.0001", base="A"),  # same base_asset -> deduped
    ]
    out = select_borrow_candidates(rows, max_calls=50)
    assert out["rate_probe_assets"] == ["A"]
    assert out["borrowability_probe_assets"] == ["A"]
    assert out["coverage"]["probed"] == 1


def test_borrow_validation_truncated_state():
    # borrowability_truncated keeps the borrow rate; clears ONLY portfolio额度.
    bv = assemble_borrow_validation(
        {"symbol": "XUSDT", "base_asset": "X"},
        {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {}, "daily_interest_vip0_by_coin": {}},
        {}, "t", None, daily_interest_account="0.00010000", borrowability_truncated=True,
    )
    assert bv["verified"] is False
    assert bv["error"] == "borrowability_not_probed"
    assert bv["classic_margin"]["daily_interest_account"] == "0.00010000"  # KEPT
    assert bv["checked_at"] == "t"  # KEPT
    assert bv["portfolio_account"]["max_borrowable"] is None  # cleared


# =========================================================================
# Stage 2026-07-borrow-task-ui-fake-v1 B1 — classic_margin user_min_borrow
# additive contract: raw-string preservation, asset_borrowable-mirrored gates,
# 2dp ROUND_HALF_UP valuation, borrowability_truncated retention, schema, and
# the unchanged 8dp max_borrowable_value_usdt.
# =========================================================================
_UMB_ROW = {"symbol": "BTCUSDT", "base_asset": "BTC"}


def _umb_ref(umb_by_name):
    return {
        "pair_listed_by_symbol": {"BTCUSDT": True},
        "asset_borrowable_by_name": {"BTC": True},
        "daily_interest_vip0_by_coin": {"BTC": "0.0003"},
        "user_min_borrow_by_name": umb_by_name,
    }


def test_user_min_borrow_value_usdt_stable_and_half_up():
    # Stable USD assets price at 1; 2dp ROUND_HALF_UP (1.005 -> 1.01).
    assert _user_min_borrow_value_usdt("USDT", "1.005", {}) == "1.01"
    assert _user_min_borrow_value_usdt("USDC", "0", {}) == "0.00"  # raw zero -> "0.00"
    assert _user_min_borrow_value_usdt("USDT", "123.4", {}) == "123.40"  # exactly 2dp


def test_user_min_borrow_value_usdt_nonstable_price_routing():
    # Non-stable uses <ASSET>USDT price; half-up at the third decimal (55.555 -> 55.56).
    assert _user_min_borrow_value_usdt("BTC", "0.001", {"BTCUSDT": "60000"}) == "60.00"
    assert _user_min_borrow_value_usdt("BTC", "0.001", {"BTCUSDT": "55555"}) == "55.56"


def test_user_min_borrow_value_usdt_null_on_missing_or_invalid():
    # Missing price, invalid/non-parseable amount, None/blank -> None (no warning).
    assert _user_min_borrow_value_usdt("BTC", "0.001", {}) is None          # no price
    assert _user_min_borrow_value_usdt("BTC", "abc", {"BTCUSDT": "1"}) is None  # bad amount
    assert _user_min_borrow_value_usdt("BTC", None, {}) is None
    assert _user_min_borrow_value_usdt("BTC", "", {}) is None


def test_user_min_borrow_value_usdt_always_two_decimals():
    import re
    for asset, amt, pm, expected in [
        ("USDT", "1.005", {}, "1.01"),
        ("BTC", "0.001", {"BTCUSDT": "60000"}, "60.00"),
        ("USDC", "0", {}, "0.00"),
        ("USDT", "1000", {}, "1000.00"),
    ]:
        v = _user_min_borrow_value_usdt(asset, amt, pm)
        assert v == expected
        assert re.fullmatch(r"-?\d+\.\d{2}", v)  # exactly two decimals


def test_assemble_user_min_borrow_classic_ref_none_branch():
    bv = assemble_borrow_validation(_UMB_ROW, None, {}, None, "private_channel_disabled")
    cm = bv["classic_margin"]
    assert cm["user_min_borrow"] is None
    assert cm["user_min_borrow_value_usdt"] is None


def test_assemble_user_min_borrow_pair_not_listed_branch():
    ref = _umb_ref({"BTC": "0.001"})
    ref["pair_listed_by_symbol"] = {"BTCUSDT": False}  # not listed
    bv = assemble_borrow_validation(_UMB_ROW, ref, {}, "t", None, price_map={"BTCUSDT": "60000"})
    cm = bv["classic_margin"]
    assert cm["user_min_borrow"] is None
    assert cm["user_min_borrow_value_usdt"] is None


def test_assemble_user_min_borrow_pair_listed_preserves_raw_and_values():
    ref = _umb_ref({"BTC": "0.001"})  # synthetic nonzero raw (test-only)
    bv = assemble_borrow_validation(_UMB_ROW, ref, {}, "t", None, price_map={"BTCUSDT": "60000"})
    cm = bv["classic_margin"]
    # raw decimal string preserved VERBATIM (output === input)
    assert cm["user_min_borrow"] == "0.001"
    assert cm["user_min_borrow_value_usdt"] == "60.00"  # 0.001 * 60000
    # raw "0" (the real captured value) is valid and values to "0.00"
    ref0 = _umb_ref({"BTC": "0"})
    bv0 = assemble_borrow_validation(_UMB_ROW, ref0, {}, "t", None, price_map={"BTCUSDT": "60000"})
    assert bv0["classic_margin"]["user_min_borrow"] == "0"
    assert bv0["classic_margin"]["user_min_borrow_value_usdt"] == "0.00"


def test_assemble_user_min_borrow_map_missing_key_is_null():
    # pair listed but base_asset absent from user_min_borrow_by_name -> null
    ref = _umb_ref({})  # no BTC key
    bv = assemble_borrow_validation(_UMB_ROW, ref, {}, "t", None, price_map={"BTCUSDT": "60000"})
    assert bv["classic_margin"]["user_min_borrow"] is None
    assert bv["classic_margin"]["user_min_borrow_value_usdt"] is None


def test_assemble_user_min_borrow_truncated_branch_retained():
    # borrowability_truncated keeps classic_margin incl. both user_min_borrow*
    # exactly as it keeps asset_borrowable / daily_interest_account.
    ref = {
        "pair_listed_by_symbol": {"XUSDT": True},
        "asset_borrowable_by_name": {"X": True},
        "daily_interest_vip0_by_coin": {"X": "0.0003"},
        "user_min_borrow_by_name": {"X": "0.5"},
    }
    bv = assemble_borrow_validation(
        {"symbol": "XUSDT", "base_asset": "X"}, ref, {}, "t", None,
        daily_interest_account="0.00010000", borrowability_truncated=True,
        price_map={"XUSDT": "2"},
    )
    cm = bv["classic_margin"]
    assert cm["user_min_borrow"] == "0.5"           # retained
    assert cm["user_min_borrow_value_usdt"] == "1.00"  # 0.5 * 2, retained
    assert cm["daily_interest_account"] == "0.00010000"  # existing retention unchanged
    assert bv["portfolio_account"]["max_borrowable"] is None  # only portfolio cleared


def test_assemble_max_borrowable_value_usdt_keeps_eight_decimals():
    # The new 2dp field must NOT alter the existing 8dp max_borrowable_value_usdt.
    assert _max_borrowable_value_usdt("BTC", "0.001", {"BTCUSDT": "60000"}) == "60.00000000"
    bv = assemble_borrow_validation(
        _UMB_ROW, _umb_ref({"BTC": "0.001"}), {"BTC": {"max_borrowable": "0.001", "borrow_limit": "60"}},
        "t", None, price_map={"BTCUSDT": "60000"},
    )
    pa = bv["portfolio_account"]
    cm = bv["classic_margin"]
    assert pa["max_borrowable_value_usdt"] == "60.00000000"  # 8dp untouched
    assert cm["user_min_borrow_value_usdt"] == "60.00"        # 2dp, distinct path


def test_user_min_borrow_schema_accepts_decimal_string_or_null(v03_schema):
    # Positive: a listed classic_ref yields a non-null raw user_min_borrow (decimal
    # string) and a null value (no price via the helper) — both schema-valid.
    rows = _two_rows()
    snap = _assemble_with_private(
        rows, _enabled_pa(),
        {"pair_listed_by_symbol": {"BTCUSDT": True}, "asset_borrowable_by_name": {"BTC": True},
         "daily_interest_vip0_by_coin": {"BTC": "0.0003"},
         "user_min_borrow_by_name": {"BTC": "0.001"}},
        _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5"),
        "2026-07-06T00:00:00Z", None,
    )
    jsonschema.validate(snap, v03_schema)
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    cm = btc["borrow_validation"]["classic_margin"]
    assert cm["user_min_borrow"] == "0.001"          # decimal_string accepted
    assert cm["user_min_borrow_value_usdt"] is None  # null accepted
    # A hand-set 2dp decimal string for the value field is also schema-valid.
    cm["user_min_borrow_value_usdt"] = "60.00"
    jsonschema.validate(snap, v03_schema)


def test_user_min_borrow_schema_rejects_missing_field_and_extra_property(v03_schema):
    rows = _two_rows()
    snap = _assemble_with_private(
        rows, _enabled_pa(),
        {"pair_listed_by_symbol": {"BTCUSDT": True}, "asset_borrowable_by_name": {"BTC": True},
         "daily_interest_vip0_by_coin": {"BTC": "0.0003"}},
        _select_chain_tier({"BTC": "0.00000500"}, {}, {"0": {}}, "5"),
        "2026-07-06T00:00:00Z", None,
    )
    btc = next(r for r in snap["rows"] if r["symbol"] == "BTCUSDT")
    cm = btc["borrow_validation"]["classic_margin"]
    # baseline valid (7 classic_margin fields incl. both new fields, null here)
    jsonschema.validate(snap, v03_schema)
    assert "user_min_borrow" in cm and "user_min_borrow_value_usdt" in cm
    # negative: missing a required new field
    bad_missing = dict(cm)
    del bad_missing["user_min_borrow"]
    btc["borrow_validation"]["classic_margin"] = bad_missing
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, v03_schema)
    # negative: undeclared property (additionalProperties: false)
    btc["borrow_validation"]["classic_margin"] = dict(cm, bogus_field="x")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, v03_schema)


# =========================================================================
# §1.4 private_account + anti-double-count hard rule
# =========================================================================
def test_assemble_private_account_maps_cross_margin_borrowed():
    unified = [
        {
            "asset": "CETUS",
            "totalWalletBalance": "1",
            "crossMarginBorrowed": "1",
            "crossMarginInterest": "0.0001",
        },
        {"asset": "USDT", "totalWalletBalance": "10", "crossMarginBorrowed": "0"},
    ]
    block, _ = assemble_private_account(
        unified, [], [], {"CETUSUSDT": "0.05", "USDTUSDT": "1"},
        checked_at="t", error=None,
    )
    by_asset = {b["asset"]: b for b in block["balances_unified"]}
    assert by_asset["CETUS"]["cross_margin_borrowed"] == "1"
    assert by_asset["USDT"]["cross_margin_borrowed"] == "0"
    # crossMarginFree absent in this sample -> null (absent is NOT zero).
    assert by_asset["CETUS"]["cross_margin_free"] is None
    assert by_asset["USDT"]["cross_margin_free"] is None
    # Wallet gross is still reported on its own field; with no pm_account the
    # unified side contributes nothing to the total (2026-08-17: no fallback).
    assert block["unified_wallet_value_usdt"] == "10.05000000"
    assert block["spot_value_usdt"] == "0.00000000"
    assert block["total_value_usdt"] == "0.00000000"
    # Debt sum is priced separately under pm_account.total_debt_usdt.
    # 2026-08-16: outstanding interest counts as debt alongside the principal —
    # CETUS 1 @ 0.05 = 0.05 principal + 0.0001 @ 0.05 = 0.000005 interest.
    assert block["pm_account"]["total_debt_usdt"] == "0.05000500"


# ---------------------------------------------------------------------------
# F4 (2026-08-07): unavailable_sources —— 区分「没读到」与「读到了，确实是空的」
# ---------------------------------------------------------------------------

def _assemble(**kw):
    return assemble_private_account(
        unified=kw.get("unified", []),
        spot=kw.get("spot", []),
        um_positions=kw.get("um_positions", []),
        price_map={},
        checked_at="2026-08-07T00:00:00Z",
        error=None,
        pm_account=kw.get("pm_account", {}),
    )[0]


def test_unavailable_sources_key_always_present():
    """键恒存在（成功路径为空列表，不得省略）。

    消费方按「缺失即全部可用」处理，所以生产链路必须无条件输出这个键——否则某条
    忘了填的组装路径会静默退回旧的假声明行为，而没有任何测试会红。
    """
    assert _assemble()["unavailable_sources"] == []


def test_unavailable_sources_flags_a_failed_source():
    """``None`` 入参 = 该源本次没读到。"""
    assert _assemble(um_positions=None)["unavailable_sources"] == ["um_positions"]
    assert _assemble(pm_account=None)["unavailable_sources"] == ["pm_account"]


def test_unavailable_sources_does_not_flag_a_genuinely_empty_source():
    """``[]`` 是「读到了，确实没有」——**绝不能**被当成失败。

    这是整个判据的关键：拿「数组为空」当失败信号，会在账户真的空仓时误报「读不到」，
    等于把一个假声明换成另一个假声明。
    """
    block = _assemble(um_positions=[], unified=[], spot=[])
    assert block["unavailable_sources"] == []
    assert block["verified"] is True


def test_unavailable_sources_lists_every_source_when_block_degrades():
    """整块降级（两个余额源都没了）→ 四个账户源全部列出，而不是空列表。

    空列表在消费侧等同「全部可用」，在这条路径上会是又一次假声明。
    """
    block, _ = assemble_private_account(
        unified=None, spot=None, um_positions=None, price_map={},
        checked_at=None, error="private_channel_disabled",
    )
    assert block["verified"] is False
    assert block["unavailable_sources"] == [
        "unified_balances", "um_positions", "spot_balances", "pm_account",
    ]


def test_assemble_private_account_maps_cross_margin_free():
    """``crossMarginFree`` -> ``cross_margin_free``: raw passthrough, absent is
    null (not zero), and it never moves ``unified_wallet_value_usdt`` (the wallet
    sum already covers the asset). Since 2026-08-17 the unified side of
    ``total_value_usdt`` is ``actualEquity``, so no per-asset row can reach the
    headline total at all."""
    unified = [
        # free < total: the rest is encumbered (borrowed against / locked).
        {"asset": "BTC", "totalWalletBalance": "1.5", "crossMarginFree": "0.40000000"},
        # A real zero is distinct from an absent key.
        {"asset": "USDT", "totalWalletBalance": "100", "crossMarginFree": "0"},
        # Absent key (frozen pre-2026-08 shape) -> null.
        {"asset": "ETH", "totalWalletBalance": "2"},
    ]
    block, _ = assemble_private_account(
        unified, [], [], {"BTCUSDT": "60000", "USDTUSDT": "1", "ETHUSDT": "3000"},
        checked_at="t", error=None,
    )
    by_asset = {b["asset"]: b for b in block["balances_unified"]}
    assert by_asset["BTC"]["cross_margin_free"] == "0.40000000"  # raw string, no requantize
    assert by_asset["USDT"]["cross_margin_free"] == "0"
    assert by_asset["ETH"]["cross_margin_free"] is None
    # Anti-double-count: wallet gross = Σ(totalWalletBalance priced) only —
    # crossMarginFree never moves it. 1.5*60000 + 100*1 + 2*3000 = 96100
    assert block["unified_wallet_value_usdt"] == "96100.00000000"


def test_assemble_private_account_maps_cross_margin_locked_and_schema(v03_schema):
    unified = [
        {
            "asset": "BTC",
            "totalWalletBalance": "1",
            "crossMarginBorrowed": "1",
            "crossMarginFree": "0.25",
            "crossMarginLocked": "0.75",
            "crossMarginInterest": "999",
        },
        {"asset": "ETH", "totalWalletBalance": "0"},
    ]
    block, _ = assemble_private_account(
        unified, [], [], {"BTCUSDT": "60000", "ETHUSDT": "3000"},
        checked_at="t", error=None,
    )
    by_asset = {b["asset"]: b for b in block["balances_unified"]}
    assert by_asset["BTC"]["cross_margin_locked"] == "0.75"
    assert by_asset["ETH"]["cross_margin_locked"] is None
    # 2026-08-16: crossMarginInterest is now projected (outstanding interest is a
    # live liability with no other source). Absent upstream key -> null, never 0.
    assert by_asset["BTC"]["cross_margin_interest"] == "999"
    assert by_asset["BTC"]["cross_margin_interest_value_usdt"] == "59940000.00000000"
    assert by_asset["ETH"]["cross_margin_interest"] is None
    # null amount values at 0 (same branch as the principal), never null-by-price
    assert by_asset["ETH"]["cross_margin_interest_value_usdt"] == "0.00000000"

    snap = _assemble_with_private(
        _two_rows(), block,
        {"pair_listed_by_symbol": {}, "asset_borrowable_by_name": {},
         "daily_interest_vip0_by_coin": {}},
        None, "t", None,
    )
    jsonschema.validate(snap, v03_schema)
    snap_by_asset = {
        b["asset"]: b for b in snap["private_account"]["balances_unified"]
    }
    locked = snap_by_asset["BTC"].pop("cross_margin_locked")
    jsonschema.validate(snap, v03_schema)  # additive field stays optional
    snap_by_asset["BTC"]["cross_margin_locked"] = "not-a-decimal"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(snap, v03_schema)
    snap_by_asset["BTC"]["cross_margin_locked"] = locked


def test_assemble_private_account_pm_account_equity_and_leverage():
    unified = [
        {"asset": "USDT", "totalWalletBalance": "500", "crossMarginBorrowed": "100"},
    ]
    spot = [
        {"asset": "USDT", "free": "50", "locked": "0"},
    ]
    pm = {
        "accountEquity": "397.8",
        "actualEquity": "397.5",
        "totalAvailableBalance": "200.1",
        "accountInitialMargin": "50",
        "accountMaintMargin": "20",
        "uniMMR": "5.167",
        "accountStatus": "NORMAL",
    }
    block, _ = assemble_private_account(
        unified, spot, [], {}, checked_at="t", error=None, pm_account=pm,
    )
    pa = block["pm_account"]
    assert pa["source"] == "papi_v1_account"
    assert pa["account_equity_usdt"] == "397.8"
    assert pa["actual_equity_usdt"] == "397.5"
    assert pa["total_available_balance_usdt"] == "200.1"
    assert pa["account_initial_margin_usdt"] == "50"
    assert pa["account_maint_margin_usdt"] == "20"
    assert pa["uni_mmr"] == "5.167"
    assert pa["account_status"] == "NORMAL"
    assert pa["total_debt_usdt"] == "100.00000000"
    # Spot 50 + unified net worth 397.5 (actualEquity) = 447.5. NOT wallet gross
    # 500, and NOT accountEquity 397.8 — the App-facing figure is actualEquity.
    assert block["spot_value_usdt"] == "50.00000000"
    assert block["unified_wallet_value_usdt"] == "500.00000000"
    assert block["total_value_usdt"] == "447.50000000"
    # leverage = total (447.5) / net worth (397.5) — same equity source as the
    # net-worth card, so the on-screen division stays self-consistent.
    assert pa["leverage_ratio"] == "1.12578616"


def test_assemble_private_account_pm_account_null_when_fetch_missing():
    block, _ = assemble_private_account(
        [{"asset": "USDT", "totalWalletBalance": "1"}],
        [], [], {}, checked_at="t", error=None, pm_account=None,
    )
    pa = block["pm_account"]
    assert pa["source"] is None
    assert pa["account_equity_usdt"] is None
    assert pa["uni_mmr"] is None
    assert pa["total_debt_usdt"] == "0.00000000"
    # 2026-08-17: no equity -> the unified side contributes NOTHING to the total
    # (partial sum, frontend renders it red). It must NOT fall back to wallet
    # gross — a different quantity whose gap to net worth is neither small nor
    # of a fixed sign (live 2026-08-17: gross 100.69 vs net worth 191.42).
    # Gross stays on its own field.
    assert block["total_value_usdt"] == "0.00000000"
    assert block["unified_wallet_value_usdt"] == "1.00000000"
    # Only pm_account is None here ([] means "read it, genuinely empty").
    assert block["unavailable_sources"] == ["pm_account"]


def test_assemble_private_account_no_leverage_when_total_is_partial():
    """Spot source missing -> the total is a partial sum, so leverage is unknown.

    With spot gone the numerator degenerates to the net worth itself and the
    ratio would read a tidy ``1.00`` — a number that looks whole and carries
    nothing, sitting right next to a total already flagged red as incomplete.
    """
    block, _ = assemble_private_account(
        [{"asset": "USDT", "totalWalletBalance": "50"}],
        None,  # spot fetch failed/disabled
        [], {}, checked_at="t", error=None,
        pm_account={"accountEquity": "80", "actualEquity": "90"},
    )
    assert block["unavailable_sources"] == ["spot_balances"]
    assert block["total_value_usdt"] == "90.00000000"  # unified side only
    assert block["pm_account"]["leverage_ratio"] is None


def test_assemble_private_account_empty_spot_yields_a_real_leverage():
    """A spot fetch that returned a genuinely empty array is NOT a missing source.

    ``[]`` means "asked, and there really is nothing there", so the total is
    complete and the resulting ``1.00`` is a true ratio — the mirror case of
    ``test_..._no_leverage_when_total_is_partial``, where ``None`` means the fetch
    failed. Contract and schema both spell this out. Without this assertion,
    narrowing the completeness check to a truthiness test on ``spot`` would blank
    a perfectly valid ratio, and nothing would go red.
    """
    block, _ = assemble_private_account(
        [{"asset": "USDT", "totalWalletBalance": "50"}],
        [],  # read it; genuinely empty
        [], {}, checked_at="t", error=None,
        pm_account={"actualEquity": "90"},
    )
    assert "spot_balances" not in block["unavailable_sources"]
    assert block["spot_value_usdt"] == "0.00000000"
    assert block["total_value_usdt"] == "90.00000000"
    assert block["pm_account"]["leverage_ratio"] == "1.00000000"


def test_assemble_private_account_leverage_survives_unrelated_source_loss():
    """Only the two sources that FORM the total may gate the ratio.

    ``unified_balances`` feeds the per-asset rows and the debt sum; ``um_positions``
    is an exposure view. Neither enters ``total_value_usdt``, so losing either must
    NOT blank the leverage — widening the completeness check to them would hide a
    ratio that is still perfectly well defined.
    """
    for label, unified, um in (("unified lost", None, []), ("um lost", [], None)):
        block, _ = assemble_private_account(
            unified,
            [{"asset": "USDT", "free": "100", "locked": "0"}],
            um, {}, checked_at="t", error=None,
            pm_account={"actualEquity": "90"},
        )
        assert block["total_value_usdt"] == "190.00000000", label
        assert block["pm_account"]["leverage_ratio"] == "2.11111111", label


def test_assemble_private_account_account_equity_alone_is_not_net_worth():
    """actualEquity absent (endpoint kept, field renamed/removed upstream): the
    accountEquity number must not stand in for it under any label."""
    block, _ = assemble_private_account(
        [{"asset": "USDT", "totalWalletBalance": "50"}],
        [{"asset": "USDT", "free": "100", "locked": "0"}],
        [], {}, checked_at="t", error=None,
        pm_account={"accountEquity": "80"},
    )
    pa = block["pm_account"]
    assert pa["account_equity_usdt"] == "80"
    assert pa["actual_equity_usdt"] is None
    # Spot only. The 80 must not surface in the total, and no ratio is derived.
    assert block["total_value_usdt"] == "100.00000000"
    assert pa["leverage_ratio"] is None


def test_assemble_private_account_anti_double_count():
    # total = unified net worth (papi actualEquity) + sum(spot free+locked priced).
    # um_positions nominal is NEVER counted (exposure view only). Wallet gross is
    # reported on its own field and never enters the total (2026-08-17). Note that
    # gross does NOT cover the um/cm sub-accounts (settled 2026-08-17, see the
    # contract), which is exactly why it must not stand in for net worth.
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
    # Net worth below wallet gross is the live shape: gross counts borrowed
    # assets, net worth does not.
    pm = {"accountEquity": "85000", "actualEquity": "88000"}
    block, warnings = assemble_private_account(
        unified, spot, um, price_map, checked_at="2026-07-06T00:00:00Z", error=None,
        pm_account=pm,
    )
    assert block["verified"] is True
    # total = net worth (88000) + spot (7550) = 95550. NOT gross 90100, NOT
    # accountEquity 85000. um nominal (10*60000=600000) excluded.
    assert block["unified_wallet_value_usdt"] == "90100.00000000"
    assert block["spot_value_usdt"] == "7550.00000000"
    assert block["total_value_usdt"] == "95550.00000000"
    assert block["balances_unified"] == [
        {
            "asset": "BTC",
            "total_balance": "1.5",
            "cross_margin_free": None,
            "cross_margin_locked": None,
            "cross_margin_borrowed": None,
            "value_usdt": "90000.00000000",
            "cross_margin_borrowed_value_usdt": "0.00000000",
            "cross_margin_interest": None,
            "cross_margin_interest_value_usdt": "0.00000000",
        },
        {
            "asset": "USDT",
            "total_balance": "100",
            "cross_margin_free": None,
            "cross_margin_locked": None,
            "cross_margin_borrowed": None,
            "value_usdt": "100.00000000",
            "cross_margin_borrowed_value_usdt": "0.00000000",
            "cross_margin_interest": None,
            "cross_margin_interest_value_usdt": "0.00000000",
        },
    ]
    assert block["balances_spot"][0] == {"asset": "ETH", "free": "2", "locked": "0.5", "value_usdt": "7500.00000000"}
    assert block["balances_spot"][1] == {"asset": "USDC", "free": "50", "locked": "0", "value_usdt": "50.00000000"}
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
    assert block["spot_value_usdt"] is None
    assert block["unified_wallet_value_usdt"] is None
    assert block["pm_account"]["account_equity_usdt"] is None
    assert block["pm_account"]["source"] is None
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


def test_assemble_private_account_value_usdt_null_when_missing_price():
    unified = [{"asset": "NOPE", "totalWalletBalance": "5"}]
    spot = [{"asset": "NOPE2", "free": "1", "locked": "0"}]
    block, warnings = assemble_private_account(
        unified, spot, [], {}, checked_at="t", error=None
    )
    assert block["balances_unified"][0]["value_usdt"] is None
    assert block["balances_spot"][0]["value_usdt"] is None
    assert any("NOPE" in w and "value_usdt unavailable" in w for w in warnings)
    assert any("NOPE2" in w and "value_usdt unavailable" in w for w in warnings)
    # total still counts missing price as 0 (original _usdt_value semantics)
    assert block["total_value_usdt"] == "0.00000000"


def test_assemble_private_account_value_usdt_zero_not_null():
    # Valid zero balance should produce "0.00000000", not null.
    unified = [{"asset": "BTC", "totalWalletBalance": "0"}]
    spot = [{"asset": "ETH", "free": "0", "locked": "0"}]
    block, warnings = assemble_private_account(
        unified, spot, [], {"BTCUSDT": "60000", "ETHUSDT": "3000"},
        checked_at="t", error=None,
    )
    assert block["balances_unified"][0]["value_usdt"] == "0.00000000"
    assert block["balances_spot"][0]["value_usdt"] == "0.00000000"
    assert block["total_value_usdt"] == "0.00000000"
    assert warnings == []


def test_assemble_private_account_um_positions_have_no_value_usdt():
    block, _ = assemble_private_account(
        [], [], [{"symbol": "BTCUSDT", "positionAmt": "1"}], {}, checked_at="t", error=None
    )
    assert "value_usdt" not in block["um_positions"][0]


def test_assemble_private_account_um_notional_usdt():
    # Prefer exchange notional (absolute); fallback |amt * mark|.
    block, _ = assemble_private_account(
        [],
        [],
        [{
            "symbol": "BTCUSDT",
            "positionAmt": "-0.5",
            "markPrice": "60000",
            "notional": "-30000.12",
        }],
        {},
        checked_at="t",
        error=None,
    )
    pos = block["um_positions"][0]
    assert pos["position_side"] == "SHORT"
    assert pos["notional_usdt"] == "30000.12000000"
    block2, _ = assemble_private_account(
        [],
        [],
        [{"symbol": "ETHUSDT", "positionAmt": "2", "markPrice": "3000"}],
        {},
        checked_at="t",
        error=None,
    )
    assert block2["um_positions"][0]["notional_usdt"] == "6000.00000000"


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


def test_assemble_private_account_sorts_balances_by_abs_net_desc_nulls_last_asset_asc():
    # abs(net) DESC, nulls last, asset ASC; spot net = value_usdt.
    unified = [
        {"asset": "AA", "totalWalletBalance": "1"},      # value=100, B=0, abs(net)=100
        {"asset": "BB", "totalWalletBalance": "1"},      # value=200, B=0, abs(net)=200 -> first
        {"asset": "CC", "totalWalletBalance": "1"},      # value=50, B=0, abs(net)=50
        {"asset": "NO_PRICE", "totalWalletBalance": "1"},  # null net
        {"asset": "ZERO", "totalWalletBalance": "0"},    # abs(net)=0
    ]
    spot = [
        {"asset": "AA", "free": "1", "locked": "0"},   # 100
        {"asset": "BB", "free": "1", "locked": "0"},   # 200 -> first
        {"asset": "DD", "free": "1", "locked": "0"},   # 150
        {"asset": "NO_PRICE2", "free": "1", "locked": "0"},  # null
        {"asset": "ZERO2", "free": "0", "locked": "0"},  # 0
    ]
    price_map = {
        "AAUSDT": "100",
        "BBUSDT": "200",
        "CCUSDT": "50",
        "DDUSDT": "150",
        "ZEROUSDT": "10",
        "ZERO2USDT": "10",
    }
    block, _ = assemble_private_account(
        unified, spot, [], price_map, checked_at="t", error=None,
    )
    assert [b["asset"] for b in block["balances_unified"]] == ["BB", "AA", "CC", "ZERO", "NO_PRICE"]
    assert [b["asset"] for b in block["balances_spot"]] == ["BB", "DD", "AA", "ZERO2", "NO_PRICE2"]
    assert block["balances_unified"][-1]["value_usdt"] is None
    assert block["balances_spot"][-1]["value_usdt"] is None
    assert block["balances_unified"][3]["value_usdt"] == "0.00000000"
    assert block["balances_spot"][3]["value_usdt"] == "0.00000000"


def test_assemble_private_account_sorts_unified_by_abs_net_not_gross_hold():
    # Large hold + large borrow ranks by abs(net), not gross hold; negative net uses abs.
    # MID: V=100 B=0   net=+100 abs=100 -> first
    # NEG: V=10  B=30  net=-20  abs=20
    # HI:  V=200 B=190 net=+10  abs=10
    # NOPRICE: no price -> null net last
    unified = [
        {"asset": "HI", "totalWalletBalance": "2", "crossMarginBorrowed": "1.9"},
        {"asset": "MID", "totalWalletBalance": "1", "crossMarginBorrowed": "0"},
        {"asset": "NEG", "totalWalletBalance": "1", "crossMarginBorrowed": "3"},
        {"asset": "NOPRICE", "totalWalletBalance": "1", "crossMarginBorrowed": "1"},
    ]
    price_map = {
        "HIUSDT": "100",
        "MIDUSDT": "100",
        "NEGUSDT": "10",
    }
    block, _ = assemble_private_account(
        unified, [], [], price_map, checked_at="t", error=None,
    )
    by = {b["asset"]: b for b in block["balances_unified"]}
    assert by["HI"]["value_usdt"] == "200.00000000"
    assert by["HI"]["cross_margin_borrowed_value_usdt"] == "190.00000000"
    assert by["MID"]["cross_margin_borrowed_value_usdt"] == "0.00000000"
    assert by["NEG"]["value_usdt"] == "10.00000000"
    assert by["NEG"]["cross_margin_borrowed_value_usdt"] == "30.00000000"
    assert by["NOPRICE"]["value_usdt"] is None
    assert [b["asset"] for b in block["balances_unified"]] == ["MID", "NEG", "HI", "NOPRICE"]


def test_assemble_private_account_sort_tiebreak_asset_asc_stable_same_asset():
    # Same abs(net) ties: asset ASC; same asset retains input order.
    unified = [
        {"asset": "B", "totalWalletBalance": "1"},   # value=100
        {"asset": "A", "totalWalletBalance": "1"},   # value=100 -> should come before B
        {"asset": "A", "totalWalletBalance": "2"},   # value=200 -> first
    ]
    block, _ = assemble_private_account(
        unified, [], [], {"AUSDT": "100", "BUSDT": "100"}, checked_at="t", error=None,
    )
    assert [b["asset"] for b in block["balances_unified"]] == ["A", "A", "B"]
    # Same-asset tie-break: original input order ("A" with totalWalletBalance=2 before "A" with 1).
    assert block["balances_unified"][0]["total_balance"] == "2"
    assert block["balances_unified"][1]["total_balance"] == "1"


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
        rate = resolve_cost_leg_rate(base, cost_leg) if (base in probed["rate_probe_assets"] and cost_leg) else None
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
    # binance_signing.py (the shared signer extracted in Boundary C) constructs
    # the hmac/hashlib/signature surface; private_client.py and the borrow
    # transport delegate to it and build none inline.
    import re
    hmac_re = re.compile(r"\bhmac\b")
    hash_re = re.compile(r"hashlib")
    sig_re = re.compile(r"signature\s*=")
    bad = []
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        rel = py.relative_to(REPO_ROOT)
        if "tests" in rel.parts or rel.name == "binance_signing.py":
            continue
        text = py.read_text(encoding="utf-8")
        if hmac_re.search(text) or hash_re.search(text) or sig_re.search(text):
            bad.append(str(rel))
    assert bad == [], f"hmac/hashlib/signature outside binance_signing.py: {bad}"


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
    assert "可借额度未探测" in joined
    assert "利率仍覆盖" in joined
    assert "2 asset" in joined  # the skipped count surfaces in the message


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


# =========================================================================
# borrow-cost-coverage-v2 — next-hourly batching + rate/borrowability decouple
# (Gate B: single-call assets hard cap 20; rate budget decoupled from the
# maxBorrowable budget; borrowability_truncated keeps the borrow rate)
# =========================================================================
def _assets_param_from_url(url: str) -> list:
    """Extract the comma-joined ``assets`` param from a next-hourly request URL."""
    query = url.split("?", 1)[1]
    for kv in query.split("&"):
        if kv.startswith("assets="):
            return kv[len("assets="):].split(",")
    return []


def _client_with_urlopen(fake_urlopen, monkeypatch):
    """PrivateClient with a custom urlopen fake (per-request control)."""
    client = PrivateClient(
        "k" * 64, "s" * 64, user_agent="t", timeout=5,
        recv_window=10000, ttl_seconds=3600, fast_ttl_seconds=60,
    )
    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)
    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
    return client


def test_borrowability_truncated_keeps_rate():
    # §4.1 (blocking regression): borrow_check_max_calls=2, 4 negative candidates;
    # next-hourly covers all 4; maxBorrowable probes only the first 2. Assets 3/4
    # KEEP the borrow rate and render error="borrowability_not_probed" with the
    # portfolio amount fields cleared —穿过行装配的集成断言.
    rows = [
        _row("AUSDT", "-0.0001", base="A"),
        _row("BUSDT", "-0.0002", base="B"),
        _row("CUSDT", "-0.0003", base="C"),
        _row("DUSDT", "-0.0004", base="D"),
    ]
    probe = select_borrow_candidates(rows, max_calls=2)
    # abs rate DESC: D(-0.0004), C(-0.0003), B(-0.0002), A(-0.0001)
    assert probe["rate_probe_assets"] == ["D", "C", "B", "A"]
    assert probe["borrowability_probe_assets"] == ["D", "C"]
    assert probe["borrowability_unprobed_assets"] == {"B", "A"}
    rate_probe_assets = probe["rate_probe_assets"]
    borrowability_unprobed = probe["borrowability_unprobed_assets"]
    # next-hourly covers all 4 (hourly 0.00000500 -> daily 0.00012000)
    cost_leg = _select_chain_tier(
        {a: "0.00000500" for a in rate_probe_assets}, {}, {"0": {}}, "5"
    )
    classic_ref = {
        "pair_listed_by_symbol": {}, "asset_borrowable_by_name": {},
        "daily_interest_vip0_by_coin": {},
    }
    # maxBorrowable probes ONLY borrowability_probe_assets (A, B).
    portfolio_by_asset = {
        a: {"max_borrowable": "1.5", "borrow_limit": "2.0"}
        for a in probe["borrowability_probe_assets"]
    }
    for r in rows:
        base = r["base_asset"]
        rate = resolve_cost_leg_rate(base, cost_leg) if base in rate_probe_assets else None
        r["net_daily_yield"] = compute_net_daily_yield(r["daily_funding_rate"], rate)
        r["borrow_rate_source"] = cost_leg.get("chain_hit_source") if rate else None
        r["borrow_validation"] = assemble_borrow_validation(
            r, classic_ref, portfolio_by_asset, "t", None,
            daily_interest_account=rate,
            borrowability_truncated=(base in borrowability_unprobed),
        )
    # unprobed assets (B, A) keep the rate; borrowability_not_probed; no portfolio额度
    for base in borrowability_unprobed:
        r = next(x for x in rows if x["base_asset"] == base)
        assert r["borrow_rate_source"] == "next_hourly"
        assert r["borrow_validation"]["classic_margin"]["daily_interest_account"] == "0.00012000"
        assert r["net_daily_yield"] is not None
        assert r["borrow_validation"]["portfolio_account"]["max_borrowable"] is None
        assert r["borrow_validation"]["error"] == "borrowability_not_probed"
        assert r["borrow_validation"]["verified"] is False
    # probed assets (D, C) get portfolio额度 + verified=true
    for base in probe["borrowability_probe_assets"]:
        r = next(x for x in rows if x["base_asset"] == base)
        assert r["borrow_validation"]["portfolio_account"]["max_borrowable"] == "1.5"
        assert r["borrow_validation"]["verified"] is True


def test_next_hourly_subset_miss_no_fabrication():
    # §4.2: next-hourly returns only 3/4 assets; the missing asset gets NO rate
    # (not fabricated, does not fall back to rate_history tier② for that asset).
    rows = [
        _row("AUSDT", "-0.0001", base="A"),
        _row("BUSDT", "-0.0002", base="B"),
        _row("CUSDT", "-0.0003", base="C"),
        _row("DUSDT", "-0.0004", base="D"),
    ]
    probe = select_borrow_candidates(rows, max_calls=50)  # none truncated
    rate_probe_assets = probe["rate_probe_assets"]
    # next-hourly returns only A/B/C (D missing — root cause B shape).
    cost_leg = _select_chain_tier(
        {"A": "0.00000500", "B": "0.00000500", "C": "0.00000500"},
        {}, {"0": {}}, "5",
    )
    classic_ref = {
        "pair_listed_by_symbol": {}, "asset_borrowable_by_name": {},
        "daily_interest_vip0_by_coin": {},
    }
    for r in rows:
        base = r["base_asset"]
        rate = resolve_cost_leg_rate(base, cost_leg) if base in rate_probe_assets else None
        r["net_daily_yield"] = compute_net_daily_yield(r["daily_funding_rate"], rate)
        r["borrow_rate_source"] = cost_leg.get("chain_hit_source") if rate else None
        r["borrow_validation"] = assemble_borrow_validation(
            r, classic_ref, {}, "t", None, daily_interest_account=rate,
        )
    d = next(x for x in rows if x["symbol"] == "DUSDT")
    assert d["borrow_rate_source"] is None
    assert d["borrow_validation"]["classic_margin"]["daily_interest_account"] is None
    # present assets DO get a rate (not all blanked)
    a = next(x for x in rows if x["symbol"] == "AUSDT")
    assert a["borrow_rate_source"] == "next_hourly"
    assert a["borrow_validation"]["classic_margin"]["daily_interest_account"] == "0.00012000"


def test_batch_merge_covers_all(monkeypatch):
    # §4.3: >20 assets must be batched at NEXT_HOURLY_BATCH_SIZE=15 (Gate B hard
    # cap 20); the merged table covers ALL assets before tier selection.
    assets = [f"A{i}" for i in range(22)]  # 2 batches: 15 + 7

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/sapi/v1/account/info" in url:
            return _FakeResp(json.dumps({"vipLevel": 5}))
        if "/sapi/v1/margin/next-hourly-interest-rate" in url:
            batch = _assets_param_from_url(url)
            assert len(batch) <= 20, f"batch exceeds hard cap: {len(batch)}"
            return _FakeResp(json.dumps([
                {"asset": a, "nextHourlyInterestRate": "0.00000500"} for a in batch
            ]))
        if "/sapi/v1/margin/interestRateHistory" in url:
            return _FakeResp(json.dumps([]))
        if "/sapi/v1/margin/crossMarginData" in url:
            return _FakeResp(json.dumps([]))
        raise AssertionError(f"unexpected url: {url}")

    client = _client_with_urlopen(fake_urlopen, monkeypatch)
    chain = client.fetch_cost_leg_chain(assets)
    assert chain["chain_hit_tier"] == 1
    assert chain["chain_hit_source"] == "next_hourly"
    # all 22 covered after merge; each resolves to daily 0.00000500 x24.
    for a in assets:
        assert resolve_cost_leg_rate(a, chain) == "0.00012000"


def test_partial_batch_failure_partial_merge(monkeypatch):
    # §4.3: one batch fails (HTTP 500); only THAT batch is skipped — merged
    # batches are kept, no tier-wide downgrade to rate_history, no silent pass.
    assets = [f"A{i}" for i in range(30)]  # 2 batches: [0:15], [15:30]

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/sapi/v1/account/info" in url:
            return _FakeResp(json.dumps({"vipLevel": 5}))
        if "/sapi/v1/margin/next-hourly-interest-rate" in url:
            batch = _assets_param_from_url(url)
            if batch[0] == "A15":  # second batch -> 500 (Binance code=2 size>20)
                return _FakeResp(json.dumps({"code": 2, "msg": "size>20"}), 500)
            return _FakeResp(json.dumps([
                {"asset": a, "nextHourlyInterestRate": "0.00000500"} for a in batch
            ]))
        if "/sapi/v1/margin/interestRateHistory" in url:
            return _FakeResp(json.dumps([]))
        if "/sapi/v1/margin/crossMarginData" in url:
            return _FakeResp(json.dumps([]))
        raise AssertionError(f"unexpected url: {url}")

    client = _client_with_urlopen(fake_urlopen, monkeypatch)
    chain = client.fetch_cost_leg_chain(assets)
    # merged success batch keeps tier① (no downgrade to tier② rate_history)
    assert chain["chain_hit_source"] == "next_hourly"
    assert resolve_cost_leg_rate("A0", chain) == "0.00012000"   # success batch hit
    assert resolve_cost_leg_rate("A15", chain) is None          # failed batch -> None
    assert resolve_cost_leg_rate("A29", chain) is None
    # failure recorded (not a silent pass)
    assert client.last_error and "next_hourly_batch_failed" in client.last_error


# =========================================================================
# borrowability-zero-mapping-v1 — _max_borrowable_value_usdt 折算
# (additive ≈USDT value; mirrors _usdt_value_optional: stable priced at 1,
# missing price -> None, no warnings; 8dp _quantize_rate; neg-zero normalized)
# =========================================================================
@pytest.mark.parametrize(
    "asset,amount,price_map,expected",
    [
        # 51061 confirmed-zero: amount "0" with a price -> "0.00000000"
        ("SPELL", "0", {"SPELLUSDT": "0.5"}, "0.00000000"),
        ("BTC", "10", {"BTCUSDT": "60000"}, "600000.00000000"),
        ("BTC", "2", {"BTCUSDT": "3"}, "6.00000000"),
        # missing price -> None (not 0, not a warning)
        ("SPELL", "1.5", {}, None),
        # null / blank / bad amount -> None
        ("BTC", None, {"BTCUSDT": "60000"}, None),
        ("BTC", "", {"BTCUSDT": "60000"}, None),
        ("BTC", "not-a-number", {"BTCUSDT": "60000"}, None),
        # stable assets priced at 1 (no price needed); amount at 8dp
        ("USDT", "5.5", {}, "5.50000000"),
        ("USDC", "5.5", {"USDCUSDT": "9"}, "5.50000000"),
    ],
)
def test_max_borrowable_value_usdt_conversion(asset, amount, price_map, expected):
    assert _max_borrowable_value_usdt(asset, amount, price_map) == expected


# =========================================================================
# unified-balance-card-net-value-b-v1 — _cross_margin_borrowed_value_usdt
# (display-only 8dp liability; null/blank/zero -> 0; invalid or no price -> None)
# =========================================================================
@pytest.mark.parametrize(
    "asset,amount,price_map,expected",
    [
        # stable non-zero priced at 1
        ("USDT", "5.5", {}, "5.50000000"),
        ("USDC", "5.5", {"USDCUSDT": "9"}, "5.50000000"),
        # non-stable positive with price
        ("BTC", "0.001", {"BTCUSDT": "60000"}, "60.00000000"),
        ("CETUS", "1", {"CETUSUSDT": "0.05"}, "0.05000000"),
        # valid zero variants
        ("BTC", "0", {"BTCUSDT": "60000"}, "0.00000000"),
        ("BTC", "0.0", {"BTCUSDT": "60000"}, "0.00000000"),
        ("BTC", "0.00000000", {"BTCUSDT": "60000"}, "0.00000000"),
        # null / blank = no effective borrow -> zero (NOT null)
        ("BTC", None, {"BTCUSDT": "60000"}, "0.00000000"),
        ("BTC", "", {"BTCUSDT": "60000"}, "0.00000000"),
        # invalid non-empty amount -> null
        ("BTC", "not-a-number", {"BTCUSDT": "60000"}, None),
        ("BTC", "abc", {}, None),
        # non-zero missing / blank / bad price -> null
        ("BTC", "0.001", {}, None),
        ("BTC", "0.001", {"BTCUSDT": ""}, None),
        ("BTC", "0.001", {"BTCUSDT": "bad"}, None),
    ],
)
def test_cross_margin_borrowed_value_usdt_branches(asset, amount, price_map, expected):
    assert _cross_margin_borrowed_value_usdt(asset, amount, price_map) == expected


def test_assemble_private_account_emits_borrowed_value_key_on_every_unified_row():
    unified = [
        {"asset": "BTC", "totalWalletBalance": "1", "crossMarginBorrowed": "0.5"},
        {"asset": "USDT", "totalWalletBalance": "10", "crossMarginBorrowed": None},
        {"asset": "NOPE", "totalWalletBalance": "1", "crossMarginBorrowed": "2"},
    ]
    block, _ = assemble_private_account(
        unified, [], [], {"BTCUSDT": "100"}, checked_at="t", error=None,
    )
    by_asset = {b["asset"]: b for b in block["balances_unified"]}
    assert by_asset["BTC"]["cross_margin_borrowed_value_usdt"] == "50.00000000"
    assert by_asset["USDT"]["cross_margin_borrowed_value_usdt"] == "0.00000000"
    # non-zero borrow, no price -> null; key still present
    assert by_asset["NOPE"]["cross_margin_borrowed_value_usdt"] is None
    # Wallet gross unchanged: debt is reported, never subtracted from it.
    assert block["unified_wallet_value_usdt"] == "110.00000000"


# =========================================================================
# borrowability-zero-mapping-v1 — assemble_borrow_validation portfolio_account
# 三分支: classic_ref-None / borrowability_truncated / verified. Each branch
# emits the SAME 5-key portfolio_account; only the additive error_code +
# max_borrowable_value_usdt differ per branch.
# =========================================================================
_PA_KEYS = {"max_borrowable", "borrow_limit", "error_code",
            "max_borrowable_value_usdt", "source"}


def test_borrow_validation_classic_ref_none_branch_additive_fields():
    # classic_ref None (channel disabled/failed): both additive fields None.
    bv = assemble_borrow_validation(
        {"symbol": "SPELLUSDT", "base_asset": "SPELL"}, None, {},
        None, "private_channel_disabled",
    )
    assert set(bv["portfolio_account"]) == _PA_KEYS
    assert bv["portfolio_account"]["error_code"] is None
    assert bv["portfolio_account"]["max_borrowable_value_usdt"] is None


def test_borrow_validation_truncated_branch_additive_fields():
    # borrowability_truncated: portfolio cleared; both additive fields None
    # (but the borrow rate + checked_at are KEPT).
    bv = assemble_borrow_validation(
        {"symbol": "SPELLUSDT", "base_asset": "SPELL"},
        {"pair_listed_by_symbol": {"SPELLUSDT": True},
         "asset_borrowable_by_name": {"SPELL": True},
         "daily_interest_vip0_by_coin": {"SPELL": "0.0003"}},
        {}, "t", None,
        daily_interest_account="0.00012000", borrowability_truncated=True,
    )
    assert set(bv["portfolio_account"]) == _PA_KEYS
    assert bv["portfolio_account"]["error_code"] is None
    assert bv["portfolio_account"]["max_borrowable_value_usdt"] is None
    assert bv["classic_margin"]["daily_interest_account"] == "0.00012000"  # rate kept


def test_borrow_validation_verified_branch_zero_mapping_with_error_code():
    # 51061 confirmed-zero: max_borrowable="0" + error_code="51061" carried
    # through; the ≈USDT value is "0.00000000" (price present). verified stays
    # true (verified does NOT consult max_borrowable).
    bv = assemble_borrow_validation(
        {"symbol": "SPELLUSDT", "base_asset": "SPELL"},
        {"pair_listed_by_symbol": {"SPELLUSDT": True},
         "asset_borrowable_by_name": {"SPELL": True},
         "daily_interest_vip0_by_coin": {"SPELL": "0.0003"}},
        {"SPELL": {"max_borrowable": "0", "borrow_limit": None,
                   "error_code": "51061"}},
        "t", None, price_map={"SPELLUSDT": "0.5"},
    )
    pa = bv["portfolio_account"]
    assert set(pa) == _PA_KEYS
    assert pa["max_borrowable"] == "0"
    assert pa["error_code"] == "51061"
    assert pa["max_borrowable_value_usdt"] == "0.00000000"
    assert bv["verified"] is True


def test_borrow_validation_verified_branch_quota_with_conversion():
    # Quota case: max_borrowable="2" + error_code=None; conversion 2 * 3 = 6.
    bv = assemble_borrow_validation(
        {"symbol": "BTCUSDT", "base_asset": "BTC"},
        {"pair_listed_by_symbol": {"BTCUSDT": True},
         "asset_borrowable_by_name": {"BTC": True},
         "daily_interest_vip0_by_coin": {"BTC": "0.0005"}},
        {"BTC": {"max_borrowable": "2", "borrow_limit": "60", "error_code": None}},
        "t", None, price_map={"BTCUSDT": "3"},
    )
    pa = bv["portfolio_account"]
    assert set(pa) == _PA_KEYS
    assert pa["max_borrowable"] == "2"
    assert pa["error_code"] is None
    assert pa["max_borrowable_value_usdt"] == "6.00000000"


def test_borrow_validation_verified_branch_missing_price_value_null():
    # Quota present but no USDT price -> value null while max_borrowable kept.
    bv = assemble_borrow_validation(
        {"symbol": "XYZUSDT", "base_asset": "XYZ"},
        {"pair_listed_by_symbol": {"XYZUSDT": True},
         "asset_borrowable_by_name": {"XYZ": True},
         "daily_interest_vip0_by_coin": {}},
        {"XYZ": {"max_borrowable": "1.5", "borrow_limit": "2", "error_code": None}},
        "t", None, price_map={},  # no XYZUSDT price
    )
    pa = bv["portfolio_account"]
    assert set(pa) == _PA_KEYS
    assert pa["max_borrowable"] == "1.5"
    assert pa["max_borrowable_value_usdt"] is None


# ── total_value_excluding_bnb_usdt (Human 2026-08-29) ──────────────────────
# BNB is held only to pay fees, so it is the one long with no futures leg
# against it and its price move lands in the total undamped. These lock the
# subtraction and, more importantly, the fail-closed rule: a component that
# cannot be subtracted must null the whole figure, never leave it high.

def _bnb_inputs(*, unified_extra=None, spot_bnb=True, price=True):
    unified = [{"asset": "USDT", "totalWalletBalance": "500"}]
    bnb_row = {"asset": "BNB", "totalWalletBalance": "0.03"}
    bnb_row.update(unified_extra or {})
    unified.append(bnb_row)
    spot = [{"asset": "USDT", "free": "50", "locked": "0"}]
    if spot_bnb:
        spot.append({"asset": "BNB", "free": "0.02", "locked": "0"})
    price_map = {"BNBUSDT": "700"} if price else {}
    pm = {"actualEquity": "397.5"}
    return unified, spot, price_map, pm


def test_total_excluding_bnb_subtracts_both_sides():
    unified, spot, price_map, pm = _bnb_inputs()
    block, _ = assemble_private_account(
        unified, spot, [], price_map, checked_at="t", error=None, pm_account=pm,
    )
    # spot 50 USDT + 14 BNB = 64; total = 64 + actualEquity 397.5 = 461.5
    assert block["spot_value_usdt"] == "64.00000000"
    assert block["total_value_usdt"] == "461.50000000"
    # minus spot BNB 14 and unified BNB 21
    assert block["total_value_excluding_bnb_usdt"] == "426.50000000"


def test_total_excluding_bnb_uses_unified_net_not_gross():
    """Borrowed and accrued interest come off the unified BNB before it does.

    Holding 0.03 BNB against 0.01 borrowed is 0.02 BNB of one's own; excluding
    the gross 21 would remove borrowed value that the equity never counted.
    """
    unified, spot, price_map, pm = _bnb_inputs(
        unified_extra={"crossMarginBorrowed": "0.01"},
    )
    block, _ = assemble_private_account(
        unified, spot, [], price_map, checked_at="t", error=None, pm_account=pm,
    )
    assert block["total_value_usdt"] == "461.50000000"
    # unified BNB net = 21 − 7 = 14; spot BNB 14; 461.5 − 28 = 433.5
    assert block["total_value_excluding_bnb_usdt"] == "433.50000000"


def test_total_excluding_bnb_null_when_bnb_price_missing():
    """No price -> value_usdt null -> the whole figure nulls, never a short sub.

    Subtracting only the side it could read would leave the remainder high by
    exactly the side it could not, which reconciles as profit never earned.
    """
    unified, spot, price_map, pm = _bnb_inputs(price=False)
    block, _ = assemble_private_account(
        unified, spot, [], price_map, checked_at="t", error=None, pm_account=pm,
    )
    assert block["total_value_excluding_bnb_usdt"] is None


def test_total_excluding_bnb_null_when_total_is_partial():
    """A partial total (no equity read) cannot carry a meaningful exclusion."""
    unified, spot, price_map, _ = _bnb_inputs()
    block, _ = assemble_private_account(
        unified, spot, [], price_map, checked_at="t", error=None, pm_account=None,
    )
    assert block["total_value_usdt"] is not None  # partial sum still published
    assert block["total_value_excluding_bnb_usdt"] is None


def test_total_excluding_bnb_equals_total_when_no_bnb_held():
    """No BNB is a real zero, not an unknown — the figure still publishes."""
    block, _ = assemble_private_account(
        [{"asset": "USDT", "totalWalletBalance": "500"}],
        [{"asset": "USDT", "free": "50", "locked": "0"}],
        [], {}, checked_at="t", error=None, pm_account={"actualEquity": "397.5"},
    )
    assert block["total_value_excluding_bnb_usdt"] == block["total_value_usdt"]
    assert block["total_value_excluding_bnb_usdt"] == "447.50000000"
