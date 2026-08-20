"""手续费回补与成交拉取测试（stage 2026-08-19-hedge-order-fee-cost-v1 T3）。

纯离线：签名成交明细、公开 BNB K 线、节流 sleep 全部注入假实现；覆盖
10-design §8 的夹具——纯 BNB、纯 USDT、BNB+USDT、本币、第三种资产、拉取
失败、缺 BNB 价、合约分钟窗、limit=1000 截断、断点/幂等、控速与 running 保护。
"""
from __future__ import annotations

import json
import urllib.request
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks import fee_fetcher as FF
from backend.hedge_open_tasks.store import HedgeOpenStore
from backend.services.hedge_open_live_client import (
    ALLOWLIST,
    HedgeOpenLiveClient,
    MARGIN_MY_TRADES_PATH,
    SPOT_MY_TRADES_PATH,
    UM_USER_TRADES_PATH,
)
from backend.tests.test_hedge_store import _apply, _create, _outcome

US = 1_000_000
MS = 1_000


def _trade(asset: str, commission: str, order_id=101) -> dict:
    return {"commissionAsset": asset, "commission": commission, "orderId": order_id}


class _FakeTransport:
    """脚本式假传输：记录调用，按腿返回预置列表；可抛 RateLimited/FeeFetchError。"""

    def __init__(self, *, trades=None, bnb_price="600.5", raise_on=None):
        self.calls = []
        self.trades = trades or []
        self.bnb_price = bnb_price
        self.raise_on = raise_on or {}  # {(route, symbol): exception}

    def spot_trades(self, symbol, order_id, limit):
        self.calls.append(("spot", symbol, order_id, limit))
        exc = self.raise_on.get(("spot", symbol))
        if exc:
            raise exc
        # 真实端点按 orderId 过滤；假实现同语义。
        return [t for t in self.trades if str(t.get("orderId")) == str(order_id)]

    def margin_trades(self, symbol, order_id, limit):
        self.calls.append(("margin", symbol, order_id, limit))
        exc = self.raise_on.get(("margin", symbol))
        if exc:
            raise exc
        return [t for t in self.trades if str(t.get("orderId")) == str(order_id)]

    def um_trades(self, symbol, start_ms, end_ms, limit):
        self.calls.append(("um", symbol, start_ms, end_ms, limit))
        exc = self.raise_on.get(("um", symbol))
        if exc:
            raise exc
        return self.trades

    def bnb_close_price(self, start_ms):
        self.calls.append(("kline", start_ms))
        return self.bnb_price


# ---------------------------------------------------------------------------
# group_trades：§8 分组夹具
# ---------------------------------------------------------------------------

def test_group_pure_bnb():
    bnb, oq, oa, inc, reason = FF.group_trades(
        [_trade("BNB", "0.001"), _trade("BNB", "0.002")], "BTC")
    assert bnb == Decimal("0.003")
    assert (oq, oa, inc, reason) == (None, None, False, "ok")


def test_group_pure_usdt():
    bnb, oq, oa, inc, reason = FF.group_trades(
        [_trade("USDT", "0.5")], "BTC")
    assert bnb is None
    assert oq == Decimal("0.5") and oa == "USDT"
    assert (inc, reason) == (False, "ok")


def test_group_bnb_plus_usdt():
    bnb, oq, oa, inc, _ = FF.group_trades(
        [_trade("BNB", "0.001"), _trade("USDT", "0.25")], "BTC")
    assert bnb == Decimal("0.001")
    assert oq == Decimal("0.25") and oa == "USDT"
    assert inc is False


def test_group_base_asset_fee():
    _, oq, oa, inc, reason = FF.group_trades([_trade("BTC", "0.01")], "BTC")
    assert oq == Decimal("0.01") and oa == "BTC"
    assert (inc, reason) == (False, "ok")


def test_group_third_asset_unpricable():
    bnb, oq, oa, inc, reason = FF.group_trades(
        [_trade("ETH", "0.01")], "BTC")
    assert (bnb, oq, oa) == (None, None, None)
    assert inc is True and "unpricable" in reason


def test_group_third_asset_alongside_bnb_writes_bnb_only():
    bnb, oq, oa, inc, _ = FF.group_trades(
        [_trade("BNB", "0.001"), _trade("ETH", "0.01")], "BTC")
    assert bnb == Decimal("0.001")
    assert (oq, oa) == (None, None)
    assert inc is True


def test_group_multi_other_assets_incomplete():
    bnb, oq, oa, inc, reason = FF.group_trades(
        [_trade("USDT", "0.1"), _trade("BTC", "0.01"), _trade("BNB", "0.001")], "BTC")
    assert bnb == Decimal("0.001")
    assert (oq, oa) == (None, None)
    assert inc is True and reason == "multi_other_assets"


def test_group_zero_commission_assets_dropped():
    # BNB 真扣 + USDT 侧零佣金行：零合计资产不参与分类，不误报两种资产。
    bnb, oq, oa, inc, _ = FF.group_trades(
        [_trade("BNB", "0.001"), _trade("USDT", "0")], "BTC")
    assert bnb == Decimal("0.001")
    assert (oq, oa) == (None, None)
    assert inc is False


def test_group_all_zero_is_no_fee_found():
    result = FF.group_trades([_trade("USDT", "0")], "BTC")
    assert result == (None, None, None, True, "no_fee_found")


def test_group_empty_trades():
    assert FF.group_trades([], "BTC") == (None, None, None, True, "no_trades")


def test_group_bad_shape_fail_closed():
    for bad in (["oops"], [_trade("BNB", None)], [{"commissionAsset": "BNB"}]):
        bnb, oq, oa, inc, reason = FF.group_trades(bad, "BTC")
        assert (bnb, oq, oa) == (None, None, None)
        assert inc is True and reason == "bad_trade_shape"


# ---------------------------------------------------------------------------
# um_query_window：B1a 分钟级窗
# ---------------------------------------------------------------------------

def test_um_window_normal():
    window = FF.um_query_window(1_000 * US, 2_000 * US)
    assert window == (1_000 * MS, 2_000 * MS, False)


def test_um_window_dispatch_missing_falls_back():
    window = FF.um_query_window(None, 2_000 * US)
    assert window == ((2_000 * US - FF.UM_FALLBACK_WINDOW_US) // MS, 2_000 * MS, False)


def test_um_window_last_query_missing_extends():
    start = 1_000 * US
    window = FF.um_query_window(start, None)
    assert window == (1_000 * MS, (start + FF.UM_FALLBACK_WINDOW_US) // MS, False)


def test_um_window_both_missing_unbuildable():
    assert FF.um_query_window(None, None) is None


def test_um_window_zero_width_or_reversed_extends_fallback():
    # inline resolve 用同一 now_us 落两列 → 零宽窗；倒置同理。向前扩 10 分钟
    # （成交在 dispatched 附近，多余成交由本地 orderId 过滤兜底）。
    t = 2_000 * US
    assert FF.um_query_window(t, t) == (
        t // MS, (t + FF.UM_FALLBACK_WINDOW_US) // MS, False)
    assert FF.um_query_window(2_000 * US, 1_000 * US) == (
        2_000 * MS, (2_000 * US + FF.UM_FALLBACK_WINDOW_US) // MS, False)


def test_um_window_span_over_7d_clamped():
    start_us = 1_000 * US
    window = FF.um_query_window(start_us, start_us + 8 * 24 * 60 * 60 * US)
    assert window == (
        start_us // MS, (start_us + FF.UM_WINDOW_MAX_US) // MS, True)


# ---------------------------------------------------------------------------
# fetch_leg_fees：路由、截断、UM 本地过滤、冻价
# ---------------------------------------------------------------------------

def _fetch(transport, endpoint=D.PERP_ORDER_PATH, order_id=101, symbol="BTCUSDT",
           base="BTC", dispatched=1_000 * US, last_query=2_000 * US):
    return FF.fetch_leg_fees(
        transport, endpoint=endpoint, order_id=order_id, symbol=symbol,
        base_asset=base, dispatched_at_us=dispatched, last_query_at_us=last_query)


def test_fetch_spots_route_uses_symbol_and_order_id():
    t = _FakeTransport(trades=[_trade("USDT", "0.5")])
    out = _fetch(t, endpoint=D.REGULAR_SPOT_ORDER_PATH)
    assert t.calls[0] == ("spot", "BTCUSDT", "101", FF.LIMIT)
    assert out.columns.fee_other_qty == "0.5"
    assert out.incomplete is False


def test_fetch_margin_route():
    t = _FakeTransport(trades=[_trade("USDT", "0.5")])
    _fetch(t, endpoint=D.SPOT_ORDER_PATH)
    assert t.calls[0][0] == "margin"


def test_fetch_um_route_minute_window_and_local_order_filter():
    t = _FakeTransport(
        trades=[_trade("USDT", "0.1", order_id=999), _trade("USDT", "0.4", order_id=101)])
    out = _fetch(t, endpoint=D.PERP_ORDER_PATH)
    assert t.calls[0] == ("um", "BTCUSDT", 1_000 * MS, 2_000 * MS, FF.LIMIT)
    assert out.columns.fee_other_qty == "0.4"  # 只保留 orderId=101 的成交


def test_fetch_um_filter_empty_is_unknown_not_zero():
    t = _FakeTransport(trades=[_trade("USDT", "0.3", order_id=999)])
    out = _fetch(t, endpoint=D.PERP_ORDER_PATH)
    assert out.columns is None
    assert out.reason == "no_trades"


def test_fetch_um_clamped_window_fails_without_get():
    t = _FakeTransport()
    start = 1_000 * US
    out = _fetch(t, endpoint=D.PERP_ORDER_PATH, dispatched=start,
                 last_query=start + 8 * 24 * 3600 * US)
    assert out.columns is None and out.reason == "um_window_clamped_7d"
    assert t.calls == []  # 不为不可信窗口消耗签名配额


def test_fetch_truncated_list_not_summed():
    t = _FakeTransport(trades=[_trade("USDT", "0.5")] * FF.LIMIT)
    out = _fetch(t)
    assert out.columns is None and out.reason == "truncated_at_limit"


def test_fetch_bnb_price_frozen_from_kline_at_dispatch():
    t = _FakeTransport(trades=[_trade("BNB", "0.001")])
    out = _fetch(t)
    assert ("kline", 1_000 * MS) in t.calls
    assert out.columns == FF.LegFeeColumns("0.001", "600.5", None, None)
    assert out.incomplete is False


def test_fetch_bnb_price_missing_keeps_qty_marks_incomplete():
    t = _FakeTransport(trades=[_trade("BNB", "0.001")], bnb_price=None)
    out = _fetch(t)
    assert out.columns == FF.LegFeeColumns("0.001", None, None, None)
    assert out.incomplete is True and out.reason == "bnb_price_missing"


def test_fetch_bnb_price_raising_degrades_to_missing():
    def boom(ms):
        raise RuntimeError("kline down")
    t = _FakeTransport(trades=[_trade("BNB", "0.001")])
    t.bnb_close_price = boom
    out = _fetch(t)
    assert out.columns.fee_bnb_qty == "0.001"
    assert out.columns.fee_bnb_price is None and out.incomplete is True


def test_fetch_rate_limited_propagates():
    t = _FakeTransport(raise_on={("um", "BTCUSDT"): FF.RateLimited(429)})
    with pytest.raises(FF.RateLimited):
        _fetch(t)


def test_fetch_http_error_is_leg_failure():
    t = _FakeTransport(raise_on={("um", "BTCUSDT"): FF.FeeFetchError("http=None")})
    out = _fetch(t)
    assert out.columns is None and out.reason.startswith("fetch_error:")


def test_fetch_unknown_endpoint_or_missing_identity():
    t = _FakeTransport()
    assert _fetch(t, endpoint="/wat").reason == "leg_identity_missing"
    assert _fetch(t, order_id=None).reason == "leg_identity_missing"


# ---------------------------------------------------------------------------
# store：update_leg_fees / list_legs_missing_fees
# ---------------------------------------------------------------------------

def _store_with_filled_legs(tmp_path, *, statuses=("done",)):
    """两条 FILLED 腿（spot=/papi/v1/margin/order、perp=/papi/v1/um/order）。"""
    store = HedgeOpenStore(str(tmp_path / "ho.sqlite3"))
    _create(store, "t1")
    _apply(store, "t1", _outcome(), 1_100)
    for status in statuses:
        store.set_task_status("t1", status, 1_200)
    legs = store._conn.execute(
        "SELECT id, leg, endpoint, order_id FROM hedge_open_leg ORDER BY id"
    ).fetchall()
    store._conn.execute(
        "UPDATE hedge_open_leg SET dispatched_at_us = ?, last_query_at_us = ?",
        (1_000 * US, 2_000 * US),
    )
    store._conn.commit()
    return store, [dict(r) for r in legs]


def test_update_leg_fees_writes_then_idempotent_guard(tmp_path):
    store, legs = _store_with_filled_legs(tmp_path)
    leg_id = legs[0]["id"]
    assert store.update_leg_fees(
        leg_id, fee_bnb_qty="0.001", fee_bnb_price="600",
        fee_other_qty=None, fee_other_asset=None) is True
    # 已写入是该腿历史真值：再次写入（哪怕值不同）被守卫拒绝。
    assert store.update_leg_fees(
        leg_id, fee_bnb_qty="9", fee_bnb_price="9",
        fee_other_qty="9", fee_other_asset="9") is False
    row = store._conn.execute(
        "SELECT fee_bnb_qty, fee_bnb_price, fee_other_qty, fee_other_asset"
        " FROM hedge_open_leg WHERE id = ?", (leg_id,)).fetchone()
    assert tuple(row) == ("0.001", "600", None, None)
    store.close()


def test_list_legs_missing_fees_filters_and_advances(tmp_path):
    store, legs = _store_with_filled_legs(tmp_path)
    ids = [l["id"] for l in store.list_legs_missing_fees()]
    assert ids == sorted(l["id"] for l in legs)
    # 写掉第一条后：选择器排除它；游标排除其前的；失败集合排除指定 id。
    first = ids[0]
    store.update_leg_fees(
        first, fee_bnb_qty="0.001", fee_bnb_price="600",
        fee_other_qty=None, fee_other_asset=None)
    assert first not in [l["id"] for l in store.list_legs_missing_fees()]
    assert [l["id"] for l in store.list_legs_missing_fees(after_id=first - 1)] == \
        [l["id"] for l in legs if l["id"] > first - 1 and l["id"] != first]
    last = ids[-1]
    assert last not in [
        l["id"] for l in store.list_legs_missing_fees(exclude_ids=[last])]
    # 非 FILLED / 无 order_id 的腿永远不是候选。
    store._conn.execute(
        "UPDATE hedge_open_leg SET exchange_status = 'CANCELED' WHERE id = ?",
        (ids[-1],))
    store._conn.commit()
    assert ids[-1] not in [l["id"] for l in store.list_legs_missing_fees()]
    store.close()


# ---------------------------------------------------------------------------
# BackfillEngine：断点、控速、running 保护、dry-run、close_log 红线
# ---------------------------------------------------------------------------

def _engine(tmp_path, transport, *, sleep_recorder=None):
    store, legs = _store_with_filled_legs(tmp_path)
    progress = tmp_path / "progress.json"
    sleep = (lambda s: sleep_recorder.append(s)) if sleep_recorder is not None \
        else (lambda s: None)
    engine = FF.BackfillEngine(
        store=store, transport=transport, progress_path=progress, sleep=sleep)
    return engine, store, legs, progress


def test_engine_writes_fees_and_advances_cursor(tmp_path):
    # 两腿各自的 order_id（_outcome 固化 spot="os"、perp="op"）。
    t = _FakeTransport(trades=[
        _trade("USDT", "0.5", order_id="os"),
        _trade("USDT", "0.7", order_id="op")])
    engine, store, legs, progress = _engine(tmp_path, t)
    summary = engine.run()
    assert summary["attempted"] == 2 and summary["written"] == 2
    assert summary["failed"] == 0 and summary["cursor"] == legs[-1]["id"]
    data = json.loads(progress.read_text(encoding="utf-8"))
    assert data["cursor"] == legs[-1]["id"] and data["failed"] == {}
    rows = store._conn.execute(
        "SELECT endpoint, fee_other_qty FROM hedge_open_leg ORDER BY id").fetchall()
    assert {r["endpoint"]: r["fee_other_qty"] for r in rows} == {
        D.SPOT_ORDER_PATH: "0.5", D.PERP_ORDER_PATH: "0.7"}
    store.close()


def test_engine_recovers_progress_and_skips_written_and_failed(tmp_path):
    t = _FakeTransport(trades=[  # 第三种资产 → 两腿都判定失败
        _trade("ETH", "0.01", order_id="os"),
        _trade("ETH", "0.02", order_id="op")])
    engine, store, legs, progress = _engine(tmp_path, t)
    summary = engine.run()
    assert summary["failed"] == 2 and summary["written"] == 0
    assert json.loads(progress.read_text(encoding="utf-8"))["failed"] == {
        str(l["id"]): "other_asset_unpricable:ETH" for l in legs}
    # 重跑：已尝试失败的腿不再发 GET（省配额），游标不动。
    t2 = _FakeTransport(trades=[_trade("USDT", "0.5")])
    engine2 = FF.BackfillEngine(
        store=store, transport=t2, progress_path=progress, sleep=lambda s: None)
    summary2 = engine2.run()
    assert summary2["attempted"] == 0 and t2.calls == []
    # 写掉一条后重跑同样跳过（四列非空被选择器排除）。
    store.close()


def test_engine_rerun_after_partial_write_skips_written(tmp_path):
    t = _FakeTransport(trades=[
        _trade("USDT", "0.5", order_id="os"),
        _trade("USDT", "0.5", order_id="op")])
    engine, store, legs, progress = _engine(tmp_path, t)
    engine.run(max_legs=1)
    summary2 = engine.run()
    assert summary2["attempted"] == 1  # 第二条（第一条已写入被排除）
    store.close()


def test_engine_refuses_when_running_task(tmp_path):
    s = HedgeOpenStore(str(tmp_path / "running.sqlite3"))
    _create(s, "t1")  # _create 默认 initial_status=running
    t = _FakeTransport()
    engine = FF.BackfillEngine(
        store=s, transport=t, progress_path=tmp_path / "p.json")
    summary = engine.run()
    assert summary["refused"] == "running_tasks"
    assert t.calls == [] and not (tmp_path / "p.json").exists()
    s.close()


def test_engine_stops_on_rate_limit_and_saves_breakpoint(tmp_path):
    t = _FakeTransport(
        trades=[_trade("USDT", "0.5", order_id="os")],
        raise_on={("um", "BTCUSDT"): FF.RateLimited(418)})
    engine, store, legs, progress = _engine(tmp_path, t)
    # 现货腿（margin 路由）先成功，合约腿（um）触发 418 → 整轮停。
    summary = engine.run()
    assert summary["stopped"] == "rate_limited:418"
    assert summary["attempted"] == 1 and summary["written"] == 1
    data = json.loads(progress.read_text(encoding="utf-8"))
    # 游标停在已成功的那条；被限速的腿 id > cursor，冷却重跑会再试它。
    assert data["cursor"] == min(l["id"] for l in legs)
    store.close()


def test_engine_throttles_signed_gets(tmp_path):
    sleeps = []
    t = _FakeTransport(trades=[
        _trade("USDT", "0.5", order_id="os"),
        _trade("USDT", "0.5", order_id="op")])
    engine, store, legs, progress = _engine(tmp_path, t, sleep_recorder=sleeps)
    engine.run()
    assert sleeps == [FF.THROTTLE_SECONDS]  # 2 条腿 → 中间 1 次节流
    store.close()


def test_engine_dry_run_zero_network_zero_writes(tmp_path):
    def boom(*a, **k):
        raise AssertionError("dry-run must not touch transport")
    engine, store, legs, progress = _engine(
        tmp_path, FF.FeeTransport(
            spot_trades=boom, margin_trades=boom, um_trades=boom,
            bnb_close_price=boom))
    summary = engine.run(dry_run=True)
    assert summary["planned_legs"] == [l["id"] for l in legs]
    assert summary["attempted"] == 0
    assert not progress.exists()
    left = store.list_legs_missing_fees()
    assert len(left) == 2
    store.close()


def test_engine_never_touches_close_log(tmp_path):
    t = _FakeTransport(trades=[
        _trade("USDT", "0.5", order_id="os"),
        _trade("USDT", "0.5", order_id="op")])
    engine, store, legs, progress = _engine(tmp_path, t)
    store.insert_close_log({
        "cycle_id": "c1", "symbol": "BTCUSDT", "direction": D.DIR_FORWARD,
        "opened_at_us": 1, "closed_at_us": 2, "close_reason": "auto_close",
        "settled_at_us": 3})
    before = store.list_close_logs()
    engine.run()
    assert store.list_close_logs() == before  # 断点 1：旧结算行原样
    store.close()


def test_progress_round_trip_and_corrupt_fallback(tmp_path):
    p = tmp_path / "p.json"
    FF.save_progress(p, 42, {"7": "no_trades"})
    assert FF.load_progress(p) == {"cursor": 42, "failed": {"7": "no_trades"}}
    (tmp_path / "bad.json").write_text("{oops", encoding="utf-8")
    assert FF.load_progress(tmp_path / "bad.json") == {"cursor": 0, "failed": {}}
    assert FF.load_progress(tmp_path / "absent.json") == {"cursor": 0, "failed": {}}


# ---------------------------------------------------------------------------
# ALLOWLIST / 签名客户端 / 公开 K 线（验收检查 1、2）
# ---------------------------------------------------------------------------

def test_allowlist_contains_three_trade_history_gets():
    assert ALLOWLIST[("GET", "/api/v3/myTrades")] == "https://api.binance.com"
    assert ALLOWLIST[("GET", "/papi/v1/margin/myTrades")] == "https://papi.binance.com"
    assert ALLOWLIST[("GET", "/papi/v1/um/userTrades")] == "https://papi.binance.com"
    # K 线是公开无签名读取，绝不进签名白名单。
    assert not any("klines" in path for _m, path in ALLOWLIST)


class _UrlopenCapture:
    def __init__(self, body):
        self.requests = []
        self._body = body

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        return _FakeResp(self._body)


class _FakeResp:
    def __init__(self, payload):
        import io
        self._buf = io.BytesIO(json.dumps(payload).encode())

    def read(self, *a):
        return self._buf.read()

    def info(self):
        return {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _client(capture):
    return HedgeOpenLiveClient("k", "s", user_agent="t", urlopen=capture)


def test_client_spot_and_um_trade_gets_sign_and_pass_params():
    capture = _UrlopenCapture([])
    client = _client(capture)
    client.get_spot_my_trades("BTCUSDT", "123", timestamp_ms=1)
    url = capture.requests[-1].get_full_url()
    assert url.startswith("https://api.binance.com/api/v3/myTrades?")
    for part in ("symbol=BTCUSDT", "orderId=123", "limit=1000",
                 "timestamp=1", "signature="):
        assert part in url
    client.get_margin_my_trades("BTCUSDT", "123", timestamp_ms=1)
    assert capture.requests[-1].get_full_url().startswith(
        "https://papi.binance.com/papi/v1/margin/myTrades?")
    client.get_um_user_trades("BTCUSDT", start_time_ms=5, end_time_ms=9,
                              timestamp_ms=1)
    url = capture.requests[-1].get_full_url()
    assert url.startswith("https://papi.binance.com/papi/v1/um/userTrades?")
    for part in ("startTime=5", "endTime=9"):
        assert part in url
    assert "orderId" not in url  # UM 无 orderId 参数（B1a）


def test_public_kline_close_live_and_offline(monkeypatch):
    from backend.adapters.binance_public import BinancePublicClient
    capture = _UrlopenCapture([[1, "600", "601", "599", "600.5", "1", 1, 1, 1, 1, 1, "0"]])
    monkeypatch.setattr(urllib.request, "urlopen", capture)
    client = BinancePublicClient(
        offline=False, offline_dir="/tmp/x", futures_base_url="https://f.b",
        spot_base_url="https://api.binance.com", user_agent="t", timeout=1)
    assert client.fetch_kline_close("BNBUSDT", start_time_ms=1234) == "600.5"
    assert "symbol=BNBUSDT" in capture.requests[-1].get_full_url()
    assert "interval=1m" in capture.requests[-1].get_full_url()
    assert "startTime=1234" in capture.requests[-1].get_full_url()
    assert "limit=1" in capture.requests[-1].get_full_url()
    # 非字符串 close / 空结果 → None（不臆造）。
    monkeypatch.setattr(urllib.request, "urlopen", _UrlopenCapture([]))
    assert client.fetch_kline_close("BNBUSDT", start_time_ms=1) is None
    monkeypatch.setattr(urllib.request, "urlopen", _UrlopenCapture([[1, 1, 1, 1, 7.5]]))
    assert client.fetch_kline_close("BNBUSDT", start_time_ms=1) is None
    offline = BinancePublicClient(
        offline=True, offline_dir="/tmp/x", futures_base_url="https://f.b",
        spot_base_url="https://s.b", user_agent="t", timeout=1)
    assert offline.fetch_kline_close("BNBUSDT", start_time_ms=1) is None


def test_backfill_script_exists_and_compiles():
    import py_compile
    import tempfile
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "scripts" / "backfill-leg-fees.py"
    assert script.exists()
    with tempfile.NamedTemporaryFile(suffix=".pyc") as fh:
        py_compile.compile(str(script), cfile=fh.name, doraise=True)
