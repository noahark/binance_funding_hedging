"""Hyperliquid 费率对比行（stage 2026-08-23-hyperliquid-funding-compare-v1）。

覆盖设计稿 §9 的后端验收：A1 DENY / A2 synthetic 跨类别撞名 / A3 HYPE /
A4 币安四列逐格不变 / A5 4h-8h 口径回归 / A6 币安独有标的 / A7 冷启动失败 /
A8 success→failure / A9 非法 funding 整源失败 / A9b 反向 oracle /
A9c offline 零网络 / A10 decimal string / A12 别名+乘数币 — / A13 原子组请求计数。
（A11/A14/A15/A16 的展示断言在 frontend/self-check.js。）

全程零网络：公共客户端与 HL 客户端均为注入的 stub，worker 逻辑经
``_scheduled_tick()`` 直驱（与既有 test_background_worker 同一模式）。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from backend.adapters.hyperliquid_public import HyperliquidPublicClient
from backend.config import Config
from backend.domain.snapshot import (
    assemble_snapshot,
    build_hyperliquid_matches,
    hl_key_for,
    build_rows,
)
from backend.services.snapshot_service import SnapshotService

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas/api/public-market/snapshot.schema.json"

T_END = 1783641600000


# ---------------------------------------------------------------- fixtures
def _sym(symbol, base, contract="PERPETUAL"):
    return {"symbol": symbol, "baseAsset": base, "quoteAsset": "USDT",
            "contractType": contract, "status": "TRADING", "filters": []}


def _spot(symbol):
    return {"symbol": symbol, "status": "TRADING",
            "isMarginTradingAllowed": True, "filters": []}


def _raw(symbols, intervals=None, rate="0.00010000"):
    syms, prem, spots = [], [], []
    for s in symbols:
        syms.append(s if isinstance(s, dict) else _sym(s, s[:-4]))
        base = syms[-1]["baseAsset"]
        prem.append({"symbol": syms[-1]["symbol"], "lastFundingRate": rate,
                     "markPrice": "1", "indexPrice": "1",
                     "nextFundingTime": T_END + 1, "time": T_END})
        spots.append(_spot(base + "USDT"))
    return {
        "futures_exchange_info": {"symbols": syms},
        "premium_index": prem,
        "spot_exchange_info": {"symbols": spots},
        "funding_history_by_sym": {},
        "funding_interval_by_sym": intervals or {},
        "warnings": [],
    }


def _hl(key, funding, *, delisted=False):
    """Adapter-normalized entry: key 含 dex 前缀，name 已剥前缀。"""
    name = key.split(":")[-1]
    return {"key": key, "name": name, "is_delisted": delisted,
            "funding": funding}


class _StubPublic:
    """Split-seam 公共 stub（offline=False，同 test_background_worker §7.1）。"""

    offline = False

    def __init__(self, raw):
        self._raw = raw

    def fetch_premium_index(self):
        return self._raw["premium_index"]

    def fetch_exchange_info_group_b(self):
        return {
            "futures_exchange_info": self._raw["futures_exchange_info"],
            "spot_exchange_info": self._raw["spot_exchange_info"],
            "funding_interval_by_sym": self._raw.get("funding_interval_by_sym", {}),
            "warnings": [],
        }

    def fetch_funding_rate(self, symbol, **kw):
        return []

    def fetch_premium_index_for(self, symbol):
        return {}

    def fetch_ticker_price_map(self):
        return {}


class _StubPrivate:
    def __init__(self):
        self.last_error = "private_channel_disabled"

    def fetch_classic_reference(self):
        return None


class _StubHL:
    """HL 客户端 stub：可注入批次数据，可切换失败。"""

    def __init__(self, main=(), xyz=(), history=None):
        self._main = list(main)
        self._xyz = list(xyz)
        self.calls = 0
        self.fail = False
        # 逐标的历史：HL key -> entries；未登记的 key 视为拉取失败。
        self.history = dict(history or {})
        self.history_calls = []
        self.history_fail = False

    def fetch_funding_compare(self):
        self.calls += 1
        if self.fail:
            raise OSError("hyperliquid upstream down")
        return {"main": self._main, "xyz": self._xyz}

    def fetch_funding_history(self, coin, start_ms):
        self.history_calls.append((coin, start_ms))
        if self.history_fail or coin not in self.history:
            raise OSError(f"hyperliquid history down for {coin}")
        return list(self.history[coin])


def _service(raw, hl=None):
    service = SnapshotService(Config(offline=False))
    service.client = _StubPublic(raw)
    service._private = _StubPrivate()
    service._hl_client = hl or _StubHL()
    return service


def _validate(snapshot):
    jsonschema.validate(instance=snapshot, schema=json.loads(SCHEMA_PATH.read_text()))


# =========================================================================
# 匹配规则（设计 §3/§5，纯函数）
# =========================================================================
def test_a1_deny_blocks_even_when_category_would_match():
    # binance BBUSDT/QNTUSDT 是 TRADIFI_PERPETUAL（类别与 xyz 一致）——
    # 只有 DENY 能拦下，证明 DENY 独立于类别校验生效。
    futures = [_sym("BBUSDT", "BB", "TRADIFI_PERPETUAL"),
               _sym("QNTUSDT", "QNT", "TRADIFI_PERPETUAL"),
               _sym("BTCUSDT", "BTC")]
    matches = build_hyperliquid_matches(
        [_hl("BTC", "0.00001000")],
        [_hl("xyz:BB", "0.00001000"), _hl("xyz:QNT", "0.00001000")],
        futures,
    )
    assert set(matches) == {"BTCUSDT"}


def test_a2_synthetic_cross_category_collision_is_blocked():
    # 两个不在 DENY 里的新撞名：main 上的 "TSLA"（币安 TSLAUSDT 是 TRADIFI）、
    # xyz 上的 "DOGE"（币安 DOGEUSDT 是加密 PERPETUAL）。类别校验须自动拦下，
    # 不依赖 BB/QNT 枚举。
    futures = [_sym("TSLAUSDT", "TSLA", "TRADIFI_PERPETUAL"),
               _sym("DOGEUSDT", "DOGE"),
               _sym("BTCUSDT", "BTC")]
    matches = build_hyperliquid_matches(
        [_hl("TSLA", "0.00001000"), _hl("BTC", "0.00001000")],
        [_hl("xyz:DOGE", "0.00001000")],
        futures,
    )
    assert set(matches) == {"BTCUSDT"}


def test_a2b_delisted_filtered_and_dex_label():
    futures = [_sym("HYPEUSDT", "HYPE")]
    matches = build_hyperliquid_matches(
        [_hl("HYPE", "0.00001250", delisted=True)],
        [_hl("xyz:TSLA", "0.00002000")],
        futures + [_sym("TSLAUSDT", "TSLA", "TRADIFI_PERPETUAL")],
    )
    # main HYPE isDelisted → 丢弃；xyz TSLA 正常配对
    assert set(matches) == {"TSLAUSDT"}
    assert matches["TSLAUSDT"]["dex"] == "xyz"


def test_a3_hype_row_and_decimal_string_wire():
    matches = build_hyperliquid_matches(
        [_hl("HYPE", "0.00001250")], [], [_sym("HYPEUSDT", "HYPE")]
    )
    block = matches["HYPEUSDT"]
    assert block == {
        "dex": "main",
        "funding_1h": "0.00001250",
        "daily_rate": "0.00030000",       # ×24
        "annualized_24h": "0.10950000",   # daily × 365
        # 历史两列：本用例未注入 history_by_key，故为 null（前四格不受影响）
        "funding_sum_24h": None,
        "annualized_7d": None,
    }
    # A10: decimal string，禁 JSON number。历史两列可为 null（游标未扫到），
    # 但一旦有值仍须是字符串——放宽只放宽到 null，不放宽到 float。
    for k, v in block.items():
        if k in ("funding_sum_24h", "annualized_7d"):
            assert v is None or isinstance(v, str), k
        else:
            assert isinstance(v, str), k


def test_a10_vectors_negative_scientific_zero():
    futures = [_sym("AUSDT", "A"), _sym("BUSDT", "B"), _sym("CUSDT", "C")]
    matches = build_hyperliquid_matches(
        [_hl("A", "-0.00002500"), _hl("B", "1e-5"), _hl("C", "0")],
        [], futures,
    )
    assert matches["AUSDT"]["daily_rate"] == "-0.00060000"
    assert matches["AUSDT"]["annualized_24h"] == "-0.21900000"
    # 科学计数法规范化为 schema decimal_string 兼容的定点串
    assert matches["BUSDT"]["funding_1h"] == "0.00001"
    assert matches["BUSDT"]["daily_rate"] == "0.00024000"
    # 零费率原样（negative-zero 不出现）
    assert matches["CUSDT"]["funding_1h"] == "0"
    assert matches["CUSDT"]["annualized_24h"] == "0.00000000"


# =========================================================================
# build_rows 投影（A4/A5/A12 回归）
# =========================================================================
_BTC_ETH = [_sym("BTCUSDT", "BTC"), _sym("ETHUSDT", "ETH")]


def _four_binance_columns(rows):
    return [
        {
            "last_funding_rate": r["futures"]["last_funding_rate"],
            "next_funding_time": r["futures"]["next_funding_time"],
            "daily_funding_rate": r["daily_funding_rate"],
            "annualized_funding_24h": r["annualized_funding_24h"],
        }
        for r in rows
    ]


def test_a4_binance_four_columns_unchanged_and_order_stable():
    raw = _raw(_BTC_ETH)
    premium = {p["symbol"]: p for p in raw["premium_index"]}
    spot = {s["symbol"]: s for s in raw["spot_exchange_info"]["symbols"]}
    base = build_rows(raw["futures_exchange_info"]["symbols"], premium, spot, {})
    with_hl = build_rows(
        raw["futures_exchange_info"]["symbols"], premium, spot, {},
        hyperliquid_by_sym=build_hyperliquid_matches(
            [_hl("BTC", "0.00001250")], [], _BTC_ETH
        ),
    )
    assert _four_binance_columns(base) == _four_binance_columns(with_hl)
    assert [r["symbol"] for r in base] == [r["symbol"] for r in with_hl]
    # 恒显式输出：无匹配行是 None 而非缺键（A6 行级形状）
    assert with_hl[0]["hyperliquid"] is not None
    assert with_hl[1]["hyperliquid"] is None
    assert "hyperliquid" in base[0] and base[0]["hyperliquid"] is None


def test_a5_interval_4h_and_8h_each_correct():
    raw = _raw(_BTC_ETH, intervals={"BTCUSDT": 4, "ETHUSDT": 8},
               rate="0.00010000")
    premium = {p["symbol"]: p for p in raw["premium_index"]}
    spot = {s["symbol"]: s for s in raw["spot_exchange_info"]["symbols"]}
    rows = {r["symbol"]: r for r in build_rows(
        raw["futures_exchange_info"]["symbols"], premium, spot, {},
        funding_interval_by_sym=raw["funding_interval_by_sym"])}
    # 4h：×24/4=×6；8h：×24/8=×3 —— 不得统一成 8h
    assert rows["BTCUSDT"]["daily_funding_rate"] == "0.00060000"
    assert rows["BTCUSDT"]["annualized_funding_24h"] == "0.21900000"
    assert rows["ETHUSDT"]["daily_funding_rate"] == "0.00030000"
    assert rows["ETHUSDT"]["annualized_funding_24h"] == "0.10950000"


def test_a12_alias_and_multiplier_symbols_show_no_hl_row():
    # GOLD（币安是 XAUUSDT）与 kPEPE（币安是 1000PEPEUSDT）都无 exact 同名：
    # 源成功（时间戳有值）的前提下仍为 null —— A6 同一形状的两种成因。
    futures = [_sym("XAUUSDT", "XAU", "TRADIFI_PERPETUAL"),
               _sym("1000PEPEUSDT", "1000PEPE"), _sym("BTCUSDT", "BTC")]
    matches = build_hyperliquid_matches(
        [_hl("BTC", "0.00001000"), _hl("kPEPE", "0.00001000")],
        [_hl("xyz:GOLD", "0.00001000")],
        futures,
    )
    assert set(matches) == {"BTCUSDT"}


# =========================================================================
# 适配器（A9 shape 校验 + A13 原子组请求计数）
# =========================================================================
def _adapter_with(fn):
    client = HyperliquidPublicClient(
        base_url="https://hl.invalid", user_agent="test", timeout=1.0
    )
    client._http_post_json = fn
    return client


def _payload(name="BTC", funding="0.00001250"):
    return [{"universe": [{"name": name}]}, [{"funding": funding}]]


def test_adapter_a13_success_exactly_two_posts():
    bodies = []

    def fn(body):
        bodies.append(body)
        return _payload("BTC" if body["dex"] == "" else "TSLA")

    client = _adapter_with(fn)
    out = client.fetch_funding_compare()
    assert [b["type"] for b in bodies] == ["metaAndAssetCtxs", "metaAndAssetCtxs"]
    assert [b["dex"] for b in bodies] == ["", "xyz"]
    assert client.request_log == {
        "POST /info metaAndAssetCtxs (main)": 1,
        "POST /info metaAndAssetCtxs (xyz)": 1,
    }
    assert [e["name"] for e in out["main"]] == ["BTC"]
    assert [e["key"] for e in out["xyz"]] == ["xyz:TSLA"]


def test_adapter_a13_first_post_failure_short_circuits():
    calls = []

    def fn(body):
        calls.append(body)
        raise OSError("main down")

    client = _adapter_with(fn)
    with pytest.raises(OSError):
        client.fetch_funding_compare()
    # 原子组已判失败：第二个 POST 不再发出
    assert len(calls) == 1 and calls[0]["dex"] == ""


def test_adapter_a9_invalid_funding_fails_whole_source():
    for bad in ("abc", None, "NaN", "Infinity", 0.0001):
        client = _adapter_with(lambda body, bad=bad: _payload(funding=bad))
        with pytest.raises(ValueError):
            client.fetch_funding_compare()


def test_adapter_a9_shape_violations_fail_whole_source():
    bad_payloads = [
        {"not": "a list"},
        [{"universe": []}, []],                       # 空 universe
        [{"universe": [{"name": "BTC"}]}, []],        # 长度不匹配
        [{"universe": [{"name": "BTC"}]}, [{}]],      # ctx 缺 funding
        [{"universe": [{}]}, [{"funding": "0.01"}]],  # universe 缺 name
    ]
    for payload in bad_payloads:
        client = _adapter_with(lambda body, p=payload: p)
        with pytest.raises(ValueError):
            client.fetch_funding_compare()


# =========================================================================
# service：source_id、失败语义、顶层时间字段（A6/A7/A8/A9b/A9c/A13）
# =========================================================================
_MAIN = [_hl("BTC", "0.00001250"), _hl("HYPE", "0.00002500")]
_XYZ = [_hl("xyz:TSLA", "0.00002000")]
_FUT = [_sym("BTCUSDT", "BTC"), _sym("HYPEUSDT", "HYPE"),
        _sym("ZKUSDT", "ZK"), _sym("TSLAUSDT", "TSLA", "TRADIFI_PERPETUAL")]


def test_service_a13_one_refresh_exactly_two_posts_and_due_gate():
    hl = _StubHL(_MAIN, _XYZ)
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()
    assert hl.calls == 1  # 恰好一次 fetch = 两次 POST（stub 内一次调用即一组）
    snap = service.get_snapshot()
    _validate(snap)
    # 立即再刷（60s 内）：HL due 不重取 —— 任一次刷新最多一组
    service._scheduled_tick()
    assert hl.calls == 1


def test_d4_predicted_fundings_never_called():
    # 所有路径零 predictedFundings 调用：适配器源码根本不存在该端点（D4）。
    import backend.adapters.hyperliquid_public as hl_mod
    src = Path(hl_mod.__file__).read_text(encoding="utf-8")
    assert "predictedFundings" not in src


def test_service_a6_a9b_partial_match_has_timestamp_not_null():
    hl = _StubHL(_MAIN, _XYZ)
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()
    snap = service.get_snapshot()
    _validate(snap)
    assert snap["hyperliquid_data_time"] is not None
    rows = {r["symbol"]: r for r in snap["rows"]}
    assert rows["BTCUSDT"]["hyperliquid"]["funding_1h"] == "0.00001250"
    assert rows["HYPEUSDT"]["hyperliquid"]["dex"] == "main"          # A3
    assert rows["TSLAUSDT"]["hyperliquid"]["dex"] == "xyz"
    assert rows["ZKUSDT"]["hyperliquid"] is None                     # A6
    # 币安首行四列照常（A4 服务层）
    assert rows["ZKUSDT"]["futures"]["last_funding_rate"] == "0.00010000"


def test_service_a7_cold_start_failure_publishes_with_null_timestamp():
    hl = _StubHL(_MAIN, _XYZ)
    hl.fail = True
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()
    snap = service.get_snapshot()
    _validate(snap)
    assert snap["hyperliquid_data_time"] is None
    assert all(r["hyperliquid"] is None for r in snap["rows"])
    # 不阻断发布：币安四列照常
    assert len(snap["rows"]) == 4
    assert snap["rows"][0]["futures"]["last_funding_rate"] == "0.00010000"


def test_service_a8_success_then_failure_clears_values_and_timestamp(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr("time.monotonic", lambda: clock["t"])
    hl = _StubHL(_MAIN, _XYZ)
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()
    assert service.get_snapshot()["hyperliquid_data_time"] is not None
    assert any(r["hyperliquid"] for r in service.get_snapshot()["rows"])
    # success → failure（跨过 60s due 窗口后的真实刷新尝试）：不留旧值、不留旧时间戳
    hl.fail = True
    clock["t"] += 61.0
    service._scheduled_tick()  # 尝试失败即弃缓存，绝无 warm last-good 投影
    snap = service.get_snapshot()
    assert snap["hyperliquid_data_time"] is None
    assert all(r["hyperliquid"] is None for r in snap["rows"])
    # 恢复成功：下一轮整组恢复
    hl.fail = False
    clock["t"] += 61.0
    service._scheduled_tick()
    snap = service.get_snapshot()
    assert snap["hyperliquid_data_time"] is not None
    rows = {r["symbol"]: r for r in snap["rows"]}
    assert rows["BTCUSDT"]["hyperliquid"]["funding_1h"] == "0.00001250"


def test_service_a9_valueerror_same_oracle_as_source_failure(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr("time.monotonic", lambda: clock["t"])
    hl = _StubHL(_MAIN, _XYZ)
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()

    def raise_invalid():
        raise ValueError("funding not a finite decimal")

    hl.fetch_funding_compare = raise_invalid
    clock["t"] += 61.0
    service._scheduled_tick()
    snap = service.get_snapshot()
    assert snap["hyperliquid_data_time"] is None
    assert all(r["hyperliquid"] is None for r in snap["rows"])


def test_service_a9c_offline_zero_hl_requests_all_null_schema_ok():
    hl = _StubHL(_MAIN, _XYZ)
    service = SnapshotService(Config(offline=True))
    service._hl_client = hl
    snap = service.get_snapshot()  # offline: build_snapshot + schema 校验
    assert hl.calls == 0
    assert snap["hyperliquid_data_time"] is None
    assert all(r["hyperliquid"] is None for r in snap["rows"])


def test_cache_refresh_button_does_not_force_hl(monkeypatch):
    # 「更新缓存」按钮只放宽账户面板组：HL 不进强制刷新集合。60s 内手动
    # 刷一轮，HL 因自身 due 未到而零调用。
    hl = _StubHL(_MAIN, _XYZ)
    service = _service(_raw(_FUT), hl)
    service._scheduled_tick()
    assert hl.calls == 1
    result = service._run_refresh_cycle(force_account_panels=True)
    assert result.published is True
    assert hl.calls == 1


# =========================================================================
# schema 兼容（IC-1：注册但非 required）
# =========================================================================
def test_schema_accepts_pre_v0_22_snapshot_without_hl_keys():
    # 既有 offline fixture 形状（无 hyperliquid_data_time / 行内 hyperliquid）
    # 必须继续通过校验 —— 顶层与行内都不得进 required。
    service = SnapshotService(Config(offline=True))
    snap = service.build_snapshot()
    legacy = json.loads(json.dumps(snap))
    for row in legacy["rows"]:
        row.pop("hyperliquid", None)
    legacy.pop("hyperliquid_data_time", None)
    _validate(legacy)


def test_assemble_snapshot_always_emits_hl_data_time():
    snap = assemble_snapshot(
        [], generated_at="2026-08-23T00:00:00Z", data_time="2026-08-23T00:00:00Z",
        source_sample_id="test",
    )
    assert "hyperliquid_data_time" in snap and snap["hyperliquid_data_time"] is None
    _validate(snap)


# ---------------------------------------------------------------- 历史两列
# fast/hl-funding-history-24h-7d：近 24h 与年化 7D 走逐标的 fundingHistory 游标，
# 与 main+xyz 原子组无关；未扫到/拉取失败只让这两格为 null。

def _hl_hist(t_end_ms, hours, rate="0.00001000"):
    """从 t_end 往回每小时一条，共 hours 条。"""
    return [{"funding_time": t_end_ms - i * 3_600_000, "funding_rate": rate}
            for i in range(hours)]


def test_hl_history_windows_reuse_binance_helpers():
    """近 24h = 窗口内求和；年化 7D = 求和 × 365/7。与币安同一对纯函数。"""
    t_end = 1_787_000_000_000
    hist = {"BTC": _hl_hist(t_end, 168, "0.00001000")}   # 7 天整，每小时 0.00001
    matches = build_hyperliquid_matches(
        [_hl("BTC", "0.00001250")], [], [_sym("BTCUSDT", "BTC")],
        history_by_key=hist, t_end_ms=t_end,
    )
    blk = matches["BTCUSDT"]
    # 24h 窗口含两端 -> 25 条 × 0.00001 = 0.00025
    assert blk["funding_sum_24h"] == "0.00025000"
    # 7D 窗口 168 条 × 0.00001 = 0.00168，年化 ×365/7
    assert blk["annualized_7d"] == "0.08760000"
    # 前四格不受历史影响
    assert blk["funding_1h"] == "0.00001250"
    assert blk["daily_rate"] == "0.00030000"


def test_hl_history_absent_leaves_first_four_cells_intact():
    """历史未扫到：两格 null，前四格照常（降级不扩散）。"""
    matches = build_hyperliquid_matches(
        [_hl("BTC", "0.00001250")], [], [_sym("BTCUSDT", "BTC")],
        history_by_key={}, t_end_ms=1_787_000_000_000,
    )
    blk = matches["BTCUSDT"]
    assert blk["funding_sum_24h"] is None
    assert blk["annualized_7d"] is None
    assert blk["annualized_24h"] == "0.10950000"


def test_hl_key_reverse_derivation():
    """游标据 dex+base_asset 反推 HL key —— 匹配是 exact，故可反推。"""
    assert hl_key_for("main", "BTC") == "BTC"
    assert hl_key_for("xyz", "NVDA") == "xyz:NVDA"


def test_sweep_fetches_hl_history_only_for_rows_with_counterpart():
    """游标只对有 HL 对手的行发历史请求；无对手的行零请求。

    费率须高于 default-view 阈值（0.0003，严格大于）才进历史候选集，否则整批
    候选为空、断言会被空集假通过 —— 这正是本测试第一版踩过的坑。
    """
    fut = _FUT + [_sym("ZKUSDT", "ZK")]
    hl = _StubHL(_MAIN, _XYZ, history={"BTC": [], "HYPE": [], "xyz:TSLA": []})
    service = _service(_raw(fut, rate="0.00050000"), hl)
    service._scheduled_tick()
    coins = [c for c, _ in hl.history_calls]
    assert coins, "候选集为空则本断言无意义（费率须高于 default-view 阈值）"
    assert "ZK" not in coins and "ZKUSDT" not in coins
    assert set(coins) <= {"BTC", "HYPE", "xyz:TSLA"}


def test_hl_history_failure_is_per_coin_not_whole_source(monkeypatch):
    """单币历史失败不影响主源：时间戳仍有值，前四格仍在，只两格为 null。"""
    clock = {"t": 1000.0}
    monkeypatch.setattr("time.monotonic", lambda: clock["t"])
    hl = _StubHL(_MAIN, _XYZ)
    hl.history_fail = True
    service = _service(_raw(_FUT, rate="0.00050000"), hl)
    service._scheduled_tick()
    snap = service.get_snapshot()
    assert snap["hyperliquid_data_time"] is not None       # 主源没被拖累
    row = {r["symbol"]: r for r in snap["rows"]}["BTCUSDT"]
    assert row["hyperliquid"]["annualized_24h"] == "0.10950000"
    assert row["hyperliquid"]["funding_sum_24h"] is None
    assert row["hyperliquid"]["annualized_7d"] is None


def test_hl_history_success_only_cache(monkeypatch):
    """成功写缓存、失败不擦既有窗口（FR-2，与币安历史组件同语义）。"""
    clock = {"t": 1000.0}
    monkeypatch.setattr("time.monotonic", lambda: clock["t"])
    t_end = 1_787_000_000_000
    hl = _StubHL(_MAIN, _XYZ, history={"BTC": _hl_hist(t_end, 168)})
    service = _service(_raw(_FUT, rate="0.00050000"), hl)
    service._scheduled_tick()
    assert "BTC" in service._hl_history_cache
    before = service._hl_history_cache["BTC"][1]
    hl.history_fail = True
    clock["t"] += 3600.0                       # 跨过 1800s TTL，触发重取并失败
    service._scheduled_tick()
    assert service._hl_history_cache["BTC"][1] == before   # 失败不擦
