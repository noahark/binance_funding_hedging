"""Unit tests for the pure normalization helpers."""
from __future__ import annotations

from backend.domain.normalize import (
    SPOT_MATCH_BSTOCK,
    SPOT_MATCH_EXACT,
    SPOT_MATCH_MULTIPLIER,
    SPOT_SYMBOL_DENY,
    SPOT_SYMBOL_MAP,
    asset_tag_for,
    filter_of,
    iso_from_ms,
    resolve_spot_identity,
    resolve_spot_leg,
)


def test_asset_tag_tradifi_maps_to_bstock():
    assert asset_tag_for("TRADIFI_PERPETUAL") == (
        "BSTOCK",
        "futures_contractType_tradifi_perpetual",
        "HIGH",
    )


def test_asset_tag_perpetual_maps_to_crypto():
    assert asset_tag_for("PERPETUAL") == (
        "CRYPTO",
        "futures_contractType_perpetual",
        "HIGH",
    )


def test_asset_tag_unmapped_is_unknown():
    tag, _, conf = asset_tag_for("CURRENT_QUARTER")
    assert tag == "UNKNOWN"
    assert conf == "LOW"


# --- METAL asset tag (stage 2026-07-ui-filter-balance-metal-v1) ---
# A real-metal baseAsset is METAL regardless of contractType, and the check runs
# BEFORE the TRADIFI_PERPETUAL -> BSTOCK mapping, so a metal TRADIFI_PERPETUAL is
# never tagged BSTOCK. The base_asset default keeps single-argument callers intact.


def test_asset_tag_metal_perpetual_base_asset():
    assert asset_tag_for("PERPETUAL", "XAU") == (
        "METAL",
        "base_asset_metal_symbol",
        "HIGH",
    )


def test_asset_tag_metal_takes_priority_over_tradifi_bstock():
    # COPPER ships as contractType=TRADIFI_PERPETUAL but is METAL, not BSTOCK.
    assert asset_tag_for("TRADIFI_PERPETUAL", "COPPER") == (
        "METAL",
        "base_asset_metal_symbol",
        "HIGH",
    )


def test_asset_tag_metal_base_asset_is_case_insensitive():
    assert asset_tag_for("PERPETUAL", "xag")[0] == "METAL"


def test_asset_tag_single_arg_callers_still_work():
    # The default base_asset="" preserves the original single-argument contract.
    assert asset_tag_for("TRADIFI_PERPETUAL")[0] == "BSTOCK"
    assert asset_tag_for("PERPETUAL")[0] == "CRYPTO"


def test_filter_of_futures_min_notional_and_lot_size():
    sym = {
        "filters": [
            {"filterType": "MIN_NOTIONAL", "notional": "50"},
            {"filterType": "LOT_SIZE", "stepSize": "0.001"},
        ]
    }
    assert filter_of(sym, "MIN_NOTIONAL", "notional") == "50"
    assert filter_of(sym, "LOT_SIZE", "stepSize") == "0.001"


def test_filter_of_spot_notional_filter():
    sym = {"filters": [{"filterType": "NOTIONAL", "minNotional": "5"}]}
    assert filter_of(sym, "NOTIONAL", "minNotional") == "5"


def test_filter_of_missing_or_none():
    assert filter_of({"filters": []}, "MIN_NOTIONAL", "notional") is None
    assert filter_of(None, "MIN_NOTIONAL", "notional") is None


def test_iso_from_ms_matches_frozen_data_time():
    # 1783055489000 ms is the max premiumIndex.time in the frozen sample; the
    # frozen data_time is "2026-07-03T05:11:29Z". Integer division, no float.
    assert iso_from_ms(1783055489000) == "2026-07-03T05:11:29Z"


def test_iso_from_ms_ignores_subsecond_part():
    assert iso_from_ms(1783055489999) == "2026-07-03T05:11:29Z"


def test_resolve_spot_leg_exact_symbol():
    spot = {"BTCUSDT": {"symbol": "BTCUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "BTC", "USDT", spot)
    assert obj["symbol"] == "BTCUSDT"
    assert match_type == "exact_symbol"


def test_resolve_spot_leg_bstock_alias_for_tradifi():
    # Futures TSLAUSDT -> spot TSLABUSDT via baseAsset+"B"+quoteAsset alias.
    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert obj["symbol"] == "TSLABUSDT"
    assert match_type == "bstock_b_suffix_alias"


def test_resolve_spot_leg_mapped_pair_must_still_be_tradable():
    # 表命中也要过 TRADING 真值确认：映射存在但现货停牌/下架 -> (None, None)。
    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "BREAK"}}
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_must_not_alias_b_to_bounce_bit():
    # 真实撞车（2026-08-07 实测）：合约 BUSDT 的 baseAsset 是 B，而 base+"B"+quote
    # 恰好等于 BBUSDT —— 那是另一个币 BB(BounceBit) 的现货对。字符串层面无法区分
    # （"B"+"B" == "BB"），旧的猜测式后缀规则会把 B 的现货腿下单到 BounceBit。
    # 显式表不收录 BUSDT，因此必须解析为「无现货腿」。
    spot = {"BBUSDT": {"symbol": "BBUSDT", "baseAsset": "BB", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "B", "USDT", spot)
    assert obj is None
    assert match_type is None


def test_spot_symbol_map_shape_invariants():
    # 表由脚本生成，这里锁住形状，防手工编辑写坏。
    assert SPOT_SYMBOL_MAP, "例外表不得为空"
    for contract, entry in SPOT_SYMBOL_MAP.items():
        assert isinstance(contract, str) and contract.endswith("USDT"), contract
        assert isinstance(entry, tuple) and len(entry) == 2, contract
        spot_symbol, match_type = entry
        assert isinstance(spot_symbol, str) and spot_symbol.endswith("USDT"), contract
        assert match_type in (SPOT_MATCH_BSTOCK, SPOT_MATCH_MULTIPLIER), contract
        # 同名标的应走 exact，不该占用例外表的位置。
        assert spot_symbol != contract, f"{contract} 与现货同名，不应进表"


def test_spot_symbol_deny_never_overlaps_map():
    # 一个合约不能既被映射又被拒绝——那是自相矛盾的两条结论。
    overlap = set(SPOT_SYMBOL_DENY) & set(SPOT_SYMBOL_MAP)
    assert not overlap, f"deny 与 map 冲突: {overlap}"
    assert "BUSDT" in SPOT_SYMBOL_DENY
    assert "BUSDT" not in SPOT_SYMBOL_MAP


def test_spot_symbol_map_covers_known_live_symbols():
    # 实盘出现过的标的必须在表内（SNXX 有活跃对冲周期；1000BONK 是乘数族样板）。
    assert SPOT_SYMBOL_MAP["SNXXUSDT"] == ("SNXXBUSDT", SPOT_MATCH_BSTOCK)
    assert SPOT_SYMBOL_MAP["1000BONKUSDT"] == ("BONKUSDT", SPOT_MATCH_MULTIPLIER)


def test_resolve_spot_leg_unmapped_contract_never_guesses():
    # 表外标的即使存在形似的现货对，也不得被猜中（fail-closed：宁可无腿，不可错腿）。
    spot = {
        "FOOBUSDT": {"symbol": "FOOBUSDT", "status": "TRADING"},
        "BARUSDT": {"symbol": "BARUSDT", "status": "TRADING"},
    }
    assert resolve_spot_leg("PERPETUAL", "FOO", "USDT", spot) == (None, None)
    assert resolve_spot_leg("PERPETUAL", "1000BAR", "USDT", spot) == (None, None)


def test_resolve_spot_leg_bstock_alias_mu_case():
    # 2026-08-05 follow-up 案例：合约 MUUSDT（TRADIFI，baseAsset MU）-> 现货
    # MUBUSDT。注意 MUUUSDT 是另一个真实合约（-> MUUBUSDT），并非 MUUSDT 的笔误
    # （2026-08-07 表方案 verify 证实两者并存）。
    spot = {"MUBUSDT": {"symbol": "MUBUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "MU", "USDT", spot)
    assert obj["symbol"] == "MUBUSDT"
    assert match_type == "bstock_b_suffix_alias"


def test_resolve_spot_leg_multiplier_strip():
    # 1000BONKUSDT futures -> spot BONKUSDT via the literal "1000" prefix strip.
    spot = {"BONKUSDT": {"symbol": "BONKUSDT", "status": "TRADING"}}
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", spot)
    assert obj["symbol"] == "BONKUSDT"
    assert match_type == "multiplier_strip_alias"


def test_resolve_spot_leg_multiplier_exact_beats_strip():
    # If a spot pair literally named 1000BONKUSDT exists (it does not today),
    # exact matching wins; the strip is a fallback, never a replacement.
    spot = {
        "1000BONKUSDT": {"symbol": "1000BONKUSDT", "status": "TRADING"},
        "BONKUSDT": {"symbol": "BONKUSDT", "status": "TRADING"},
    }
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", spot)
    assert obj["symbol"] == "1000BONKUSDT"
    assert match_type == "exact_symbol"


def test_resolve_spot_leg_multiplier_no_spot_none():
    # Strip yields no tradable spot pair -> (None, None), never a guess.
    obj, match_type = resolve_spot_leg("PERPETUAL", "1000BONK", "USDT", {})
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_none_when_no_spot():
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "NVDA", "USDT", {})
    assert obj is None
    assert match_type is None


def test_resolve_spot_leg_exact_beats_alias_for_tradifi():
    # If a TRADIFI futures symbol coincidentally also has an EXACT spot symbol,
    # exact-symbol matching wins (alias is a fallback, never a replacement).
    spot = {
        "TSLAUSDT": {"symbol": "TSLAUSDT", "status": "TRADING"},
        "TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"},
    }
    obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
    assert obj["symbol"] == "TSLAUSDT"
    assert match_type == "exact_symbol"


# --- resolve_spot_identity：现货腿身份（只答「叫什么」，不答「有没有」）---
# 方案 docs/planning/symbol-identity-unification-2026-08-07.opus5.md §2.2：
# 身份来自静态表（稳定、可固化），存在性由 check_symbol_legs 实时探测负责。


def test_resolve_spot_identity_mapped_bstock():
    assert resolve_spot_identity("SNXXUSDT") == ("SNXXBUSDT", "SNXXB", SPOT_MATCH_BSTOCK)


def test_resolve_spot_identity_mapped_multiplier():
    assert resolve_spot_identity("1000BONKUSDT") == ("BONKUSDT", "BONK", SPOT_MATCH_MULTIPLIER)


def test_resolve_spot_identity_unmapped_is_same_name():
    # 表外即同名：绝大多数普通币走这条路。
    assert resolve_spot_identity("BTCUSDT") == ("BTCUSDT", "BTC", SPOT_MATCH_EXACT)


def test_resolve_spot_identity_never_returns_none_for_legless_contract():
    # BUSDT 实际无现货腿，但 identity 仍返回同名身份——「有没有腿」不归它答，
    # 由 check_symbol_legs 拦截（方案 §2.2 / §2.3，r1 的 D1 已据此撤销）。
    assert resolve_spot_identity("BUSDT") == ("BUSDT", "B", SPOT_MATCH_EXACT)


def test_resolve_spot_identity_base_is_derivable_from_symbol():
    # 测试 11 的纯函数部分：spot_base_asset 恒等于 spot_symbol 剥去 USDT。
    for contract in SPOT_SYMBOL_MAP:
        spot_symbol, base, _match = resolve_spot_identity(contract)
        assert spot_symbol == base + "USDT", contract
