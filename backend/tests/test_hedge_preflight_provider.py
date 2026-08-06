"""S4b (ADR-H5) three-state leg-existence probe tests for
backend/services/hedge_preflight_provider.py.

No real network: the public ``urlopen`` is injected. The probe distinguishes
three states per leg — True (present), False (confirmed absent, e.g. a spot
-1121), None (indeterminate read failure) — and the caller never blocks on None.
"""
from __future__ import annotations

import io
import json
import urllib.error
from decimal import Decimal
from types import SimpleNamespace

from backend.services.hedge_preflight_provider import (
    HedgePreflightProvider,
    _perp_leg_exists,
    _spot_leg_exists,
)


class _Resp:
    """Minimal http response: .status / .read() / context manager, matching what
    the provider reads via ``with urlopen(req, timeout=...) as resp``."""

    def __init__(self, status, body):
        self.status = status
        self._raw = json.dumps(body).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body):
    """A real urllib HTTPError carrying a JSON body, the way Binance ships a
    -1121 (HTTP 400 + body ``{"code": -1121, ...}``)."""
    return urllib.error.HTTPError(
        "https://api.binance.com/x", code, "Bad Request", {},
        io.BytesIO(json.dumps(body).encode()),
    )


class _FakeUrlopen:
    """Routes by URL substring: ``fapi`` -> the perp response, otherwise spot.
    Any stored value that is an Exception instance is raised (transport or HTTP
    error); a _Resp is returned as a 2xx response."""

    def __init__(self, spot, perp):
        self._spot = spot
        self._perp = perp
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        target = self._perp if "fapi" in url else self._spot
        if isinstance(target, BaseException):
            raise target
        return target


def _provider(spot, perp):
    fake = _FakeUrlopen(spot, perp)
    return HedgePreflightProvider(now_ms=lambda: 0, public_urlopen=fake), fake


COIN = "BTCUSDT"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_spot_leg_exists_states():
    assert _spot_leg_exists(200, {"symbols": [{"symbol": COIN}]}, COIN) is True
    assert _spot_leg_exists(400, {"code": -1121, "msg": "Invalid symbol"}, COIN) is False
    assert _spot_leg_exists(None, None, COIN) is None            # transport failure
    assert _spot_leg_exists(500, None, COIN) is None             # 5xx indeterminate
    assert _spot_leg_exists(200, {"symbols": []}, COIN) is None  # 2xx but missing
    assert _spot_leg_exists(400, {"code": -1000}, COIN) is None  # 400 not -1121


def test_perp_leg_exists_states():
    assert _perp_leg_exists(200, {"symbols": [{"symbol": COIN}]}, COIN) is True
    assert _perp_leg_exists(200, {"symbols": []}, COIN) is False  # absent in list
    assert _perp_leg_exists(None, None, COIN) is None
    assert _perp_leg_exists(500, {"symbols": []}, COIN) is None


# ---------------------------------------------------------------------------
# check_symbol_legs end-to-end (three-state x two-leg matrix)
# ---------------------------------------------------------------------------

def test_check_symbol_legs_both_present():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN, "status": "TRADING"}]}),
        _Resp(200, {"symbols": [{"symbol": COIN, "status": "TRADING"}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": True}


def test_check_symbol_legs_spot_minus_1121_perp_present():
    # The KORUUSDT case: spot leg absent (HTTP 400 body code -1121), UM present.
    prov, _ = _provider(
        _http_error(400, {"code": -1121, "msg": "Invalid symbol"}),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": False, "perp": True}


def test_check_symbol_legs_perp_absent_spot_present():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        _Resp(200, {"symbols": [{"symbol": "ETHUSDT"}]}),  # coin not in UM list
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": False}


def test_check_symbol_legs_both_absent():
    prov, _ = _provider(
        _http_error(400, {"code": -1121, "msg": "Invalid symbol"}),
        _Resp(200, {"symbols": [{"symbol": "ETHUSDT"}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": False, "perp": False}


def test_check_symbol_legs_spot_transport_failure_is_indeterminate():
    # A plain transport error (connection reset / timeout) on spot -> None,
    # NOT False: the probe must never assert absence on a failed read.
    prov, _ = _provider(
        ConnectionError("public marketdata unreachable"),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": None, "perp": True}


def test_check_symbol_legs_perp_transport_failure_is_indeterminate():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        OSError("read timed out"),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": None}


def test_check_symbol_legs_uses_correct_public_endpoints():
    prov, fake = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    prov.check_symbol_legs(COIN)
    spot_url = [u for u in fake.urls if "fapi" not in u][0]
    perp_url = [u for u in fake.urls if "fapi" in u][0]
    assert spot_url.endswith(f"/api/v3/exchangeInfo?symbol={COIN}")
    assert perp_url.endswith("/fapi/v1/exchangeInfo")


class _BstockUrlopen:
    """URL-aware public fixture for the TSLAUSDT -> TSLABUSDT case."""

    def __init__(self):
        self.urls = []

    @staticmethod
    def _spot_symbol(symbol):
        return {
            "symbol": symbol,
            "status": "TRADING",
            "isMarginTradingAllowed": True,
            "filters": [
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                {"filterType": "NOTIONAL", "minNotional": "5", "applyMinToMarket": True},
            ],
        }

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if "fapi" in url:
            return _Resp(200, {"symbols": [{
                "symbol": "TSLAUSDT",
                "status": "TRADING",
                "contractType": "TRADIFI_PERPETUAL",
                "baseAsset": "TSLA",
                "quoteAsset": "USDT",
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                    {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                    {"filterType": "MIN_NOTIONAL", "notional": "5"},
                ],
            }]})
        if "ticker/price" in url:
            assert url.endswith("symbol=TSLABUSDT")
            return _Resp(200, {"price": "100"})
        if url.endswith("symbol=TSLAUSDT"):
            raise _http_error(400, {"code": -1121, "msg": "Invalid symbol"})
        if url.endswith("symbol=TSLABUSDT"):
            return _Resp(200, {"symbols": [self._spot_symbol("TSLABUSDT")]})
        raise AssertionError(f"unexpected public URL: {url}")


class _BstockPrivate:
    credentials_present = True

    @staticmethod
    def get_balance(*, timestamp_ms):
        return SimpleNamespace(
            transport_error=None,
            http_status=200,
            body=[{"asset": "USDT", "crossMarginFree": "100000"}],
        )

    @staticmethod
    def get_position_side_dual(*, timestamp_ms):
        return SimpleNamespace(transport_error=None, http_status=200, body={"dualSidePosition": False})

    @staticmethod
    def get_rate_limit_order(*, timestamp_ms):
        return SimpleNamespace(
            transport_error=None,
            http_status=200,
            body=[{"rateLimitType": "ORDERS", "limit": 100}],
        )

    # Regular-spot route reads (stage 2026-08-02-spot-order-routing-cap-display-v1).
    # The cap list does NOT contain TSLAB, so a forward bStock resolves to
    # regular_spot via the TRADIFI rule (tradifi_regular_spot), not the cap rule.
    @staticmethod
    def get_restricted_asset():
        return SimpleNamespace(
            transport_error=None,
            http_status=200,
            body={"maxCollateralExceededAsset": ["LINK"], "openLongRestrictedAsset": []},
        )

    @staticmethod
    def get_spot_account(*, timestamp_ms):
        return SimpleNamespace(
            transport_error=None,
            http_status=200,
            body={"balances": [{"asset": "USDT", "free": "5000"}]},
        )

    @staticmethod
    def get_spot_rate_limit_order(*, timestamp_ms):
        return SimpleNamespace(
            transport_error=None,
            http_status=200,
            body=[{"rateLimitType": "ORDERS", "limit": 50}],
        )


def test_bstock_alias_is_accepted_by_symbol_probe():
    fake = _BstockUrlopen()
    prov = HedgePreflightProvider(now_ms=lambda: 0, public_urlopen=fake)
    assert prov.check_symbol_legs("TSLAUSDT") == {"spot": True, "perp": True}
    assert any(url.endswith("symbol=TSLABUSDT") for url in fake.urls)


def test_bstock_alias_flows_into_preflight_snapshot_and_price_read():
    from backend.hedge_open_tasks import domain as D

    fake = _BstockUrlopen()
    prov = HedgePreflightProvider(
        live_client=_BstockPrivate(), now_ms=lambda: 0, public_urlopen=fake,
    )
    snapshot = prov.get_snapshot("TSLAUSDT", D.DIR_FORWARD)
    assert snapshot is not None
    assert snapshot.spot_symbol == "TSLABUSDT"
    assert snapshot.est_price == 100
    # A forward bStock routes to the standard spot account (regular_spot) via the
    # TRADIFI rule; the endpoint follows that one decision.
    assert snapshot.spot_route == D.SPOT_ROUTE_REGULAR_SPOT
    assert snapshot.spot_route_reason == D.ROUTE_REASON_TRADIFI_REGULAR_SPOT
    assert snapshot.spot_route_endpoint == D.REGULAR_SPOT_ORDER_PATH
    assert any("ticker/price?symbol=TSLABUSDT" in url for url in fake.urls)


def test_disabled_preflight_provider_has_no_leg_probe():
    # The dry-run default provider exposes no probe -> create_task duck-types it
    # away and never blocks (10-design §2.4b: dry-run unchanged, offline zero-net).
    from backend.hedge_open_tasks.service import DisabledPreflightProvider
    assert not hasattr(DisabledPreflightProvider(), "check_symbol_legs")


# ---------------------------------------------------------------------------
# Regular-spot route decision (design §3 step 4 / decision §E-1, §E-3).
# Fake-transport routing tests: the provider reads public exchangeInfo/ticker
# via public_urlopen and private facts (cap list, balances, spot account) via
# the live_client; both are injected, no real network.
# ---------------------------------------------------------------------------
from backend.hedge_open_tasks import domain as _D  # noqa: E402


def _spot_sym(symbol, base, margin_allowed=True):
    return {
        "symbol": symbol, "baseAsset": base, "status": "TRADING",
        "isMarginTradingAllowed": margin_allowed,
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.01", "minQty": "0.01", "maxQty": "9000"},
            {"filterType": "MARKET_LOT_SIZE", "stepSize": "0", "minQty": "0", "maxQty": "9000"},
            {"filterType": "NOTIONAL", "minNotional": "5", "applyMinToMarket": True},
        ],
    }


def _perp_sym(symbol, contract_type, base, quote="USDT"):
    return {
        "symbol": symbol, "contractType": contract_type, "baseAsset": base,
        "quoteAsset": quote, "status": "TRADING",
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.01", "minQty": "0.01", "maxQty": "9000"},
            {"filterType": "MARKET_LOT_SIZE", "stepSize": "0", "minQty": "0", "maxQty": "9000"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
        ],
    }


class _RoutingPublic:
    """Routes public reads by URL: fapi exchangeInfo -> the perp record(s);
    spot exchangeInfo?symbol=X -> a spot record (or HTTPError -1121 if absent);
    ticker/price -> a fixed price."""

    def __init__(self, perp_records, spot_records_by_symbol, price="10"):
        self._perp = perp_records
        self._spots = spot_records_by_symbol
        self._price = price
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if "/fapi/v1/exchangeInfo" in url:
            return _Resp(200, {"symbols": self._perp})
        if "/api/v3/exchangeInfo?symbol=" in url:
            sym = url.rsplit("symbol=", 1)[1]
            rec = self._spots.get(sym)
            if rec is None:
                raise _http_error(400, {"code": -1121, "msg": "Invalid symbol"})
            return _Resp(200, {"symbols": [rec]})
        if "/api/v3/ticker/price" in url:
            return _Resp(200, {"price": self._price})
        raise AssertionError(f"unexpected public URL: {url}")


class _RoutingPrivate:
    """Live-client fake with configurable cap list + standard-spot USDT.
    Records which methods were called so the reverse-direction test can prove
    the cap list is NOT read."""

    def __init__(self, cap_assets, spot_usdt="100000", cap_fail=False,
                 spot_account_fail=False, spot_ratelimit_fail=False):
        self.credentials_present = True
        self._cap = cap_assets
        self._spot_usdt = spot_usdt
        self._cap_fail = cap_fail
        self._spot_account_fail = spot_account_fail
        self._spot_ratelimit_fail = spot_ratelimit_fail
        self.calls = []

    def get_balance(self, *, timestamp_ms):
        self.calls.append("balance")
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body=[{"asset": "USDT", "crossMarginFree": "100000"}],
        )

    def get_position_side_dual(self, *, timestamp_ms):
        self.calls.append("position")
        return SimpleNamespace(transport_error=None, http_status=200, body={"dualSidePosition": False})

    def get_rate_limit_order(self, *, timestamp_ms):
        self.calls.append("papi_ratelimit")
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body=[{"rateLimitType": "ORDERS", "limit": 100}],
        )

    def get_restricted_asset(self):
        self.calls.append("restricted_asset")
        if self._cap_fail:
            return SimpleNamespace(transport_error="connection_error", http_status=None, body=None)
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body={"maxCollateralExceededAsset": list(self._cap), "openLongRestrictedAsset": []},
        )

    def get_spot_account(self, *, timestamp_ms):
        self.calls.append("spot_account")
        if self._spot_account_fail:
            return SimpleNamespace(transport_error="timeout", http_status=None, body=None)
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body={"balances": [{"asset": "USDT", "free": self._spot_usdt}]},
        )

    def get_spot_rate_limit_order(self, *, timestamp_ms):
        self.calls.append("spot_ratelimit")
        if self._spot_ratelimit_fail:
            return SimpleNamespace(transport_error="timeout", http_status=None, body=None)
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body=[{"rateLimitType": "ORDERS", "limit": 50}],
        )


def _route_provider(public, private):
    return HedgePreflightProvider(
        live_client=private, now_ms=lambda: 0, public_urlopen=public,
    )


def test_routing_forward_cap_hit_selects_regular_spot_collateral_cap():
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    snap = _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    assert snap.spot_route_reason == _D.ROUTE_REASON_COLLATERAL_CAP_PRECHECK
    assert snap.spot_route_endpoint == _D.REGULAR_SPOT_ORDER_PATH
    assert snap.spot_account_usdt is not None  # regular_spot read performed


def test_routing_forward_bstock_selects_regular_spot_tradifi():
    # TSLAUSDT is TRADIFI; exact spot absent (-1121), B-suffix TSLABUSDT resolves.
    # The match/list input is TSLAB (the resolved spot base), not TSLA.
    priv = _RoutingPrivate(cap_assets=[])  # TSLAB NOT in list
    pub = _RoutingPublic(
        [_perp_sym("TSLAUSDT", "TRADIFI_PERPETUAL", "TSLA")],
        {"TSLABUSDT": _spot_sym("TSLABUSDT", "TSLAB")},
    )
    snap = _route_provider(pub, priv).get_snapshot("TSLAUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_symbol == "TSLABUSDT"
    assert snap.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    assert snap.spot_route_reason == _D.ROUTE_REASON_TRADIFI_REGULAR_SPOT


def test_routing_forward_normal_crypto_no_hit_stays_papi():
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_perp_sym("BTCUSDT", "PERPETUAL", "BTC")],
                         {"BTCUSDT": _spot_sym("BTCUSDT", "BTC")})
    snap = _route_provider(pub, priv).get_snapshot("BTCUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert snap.spot_route_reason == _D.ROUTE_REASON_PAPI_DEFAULT
    # papi_margin does NOT read the standard spot account.
    assert "spot_account" not in priv.calls


def test_routing_reverse_never_reads_restricted_asset_or_selects_regular_spot():
    # Decision §E-1: negative funding keeps papi_margin even on a cap-hit asset,
    # and the restricted-asset list is NOT read at all.
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    snap = _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_REVERSE)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert "restricted_asset" not in priv.calls
    assert "spot_account" not in priv.calls


def test_routing_forward_spot_only_selects_regular_spot():
    # THE 51023 根因复现修复：仅现货标的（公开现货 isMarginTradingAllowed=False，
    # 如 THEUSDT）forward 开仓，现货腿必须走普通现货端点 /api/v3/order
    # （regular_spot），绝不发到全仓杠杆 /papi/v1/margin/order。cap 列表不包含
    # 该资产、也不是 TRADIFI——旧逻辑会漏判为 papi_margin，现由 provider 前置强制。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    snap = _route_provider(pub, priv).get_snapshot("THEUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    assert snap.spot_route_reason == _D.ROUTE_REASON_SPOT_ONLY_REGULAR
    assert snap.spot_route_endpoint == _D.REGULAR_SPOT_ORDER_PATH
    # regular_spot 特有读取被执行（标准现货账户 + 现货 rate limit）
    assert "spot_account" in priv.calls
    assert "spot_ratelimit" in priv.calls


def test_routing_forward_margin_spot_stays_papi_when_no_cap_hit():
    # MARGIN_SPOT 回归（dispatch 验收 2）：isMarginTradingAllowed=True 的普通标的
    # forward 开仓、cap 未命中、非 TRADIFI → 仍 papi_margin（既有行为逐字不变）。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic([_perp_sym("BTCUSDT", "PERPETUAL", "BTC")],
                         {"BTCUSDT": _spot_sym("BTCUSDT", "BTC", margin_allowed=True)})
    snap = _route_provider(pub, priv).get_snapshot("BTCUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert snap.spot_route_reason == _D.ROUTE_REASON_PAPI_DEFAULT
    assert "spot_account" not in priv.calls


def test_routing_close_forward_spot_only_keeps_close_sell_regular():
    # close 路径回归：仅现货标的 close+forward（卖现货）行为不变——仍固定
    # regular_spot，reason 是 close_sell_regular_spot（decide 规则），不被
    # 仅现货前置强制劫持（强制仅作用于 open+forward）。注意 close 任务传给
    # get_snapshot 的 direction 是反转后的余额检查方向（REVERSE）。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    snap = _route_provider(pub, priv).get_snapshot(
        "THEUSDT", _D.DIR_REVERSE, task_type=_D.TASK_TYPE_CLOSE,
    )
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    assert snap.spot_route_reason == _D.ROUTE_REASON_CLOSE_SELL_REGULAR
    assert snap.spot_route_endpoint == _D.REGULAR_SPOT_ORDER_PATH


def test_routing_close_reverse_spot_only_keeps_papi():
    # close 路径回归 2：仅现货标的 close+reverse（买现货还币）行为不变——仍
    # papi_margin（decide 规则），不被仅现货强制劫持。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    snap = _route_provider(pub, priv).get_snapshot(
        "THEUSDT", _D.DIR_FORWARD, task_type=_D.TASK_TYPE_CLOSE,
    )
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert snap.spot_route_reason == _D.ROUTE_REASON_PAPI_DEFAULT


def test_routing_reverse_spot_only_keeps_papi():
    # 仅现货标的 reverse（开仓卖现货）不在本次强制范围：仍走既有 decide 规则
    # papi_margin（负费率方向从不选 regular_spot，决策 §E-1 逐字保留）。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    snap = _route_provider(pub, priv).get_snapshot("THEUSDT", _D.DIR_REVERSE)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert "restricted_asset" not in priv.calls


def test_routing_forward_cap_read_failure_fails_closed():
    # A failed restricted-asset read on a forward direction returns None (no
    # attempt, no POST); the route is never guessed from a missing read.
    priv = _RoutingPrivate(cap_assets=["LINK"], cap_fail=True)
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    assert _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_FORWARD) is None


def test_routing_regular_spot_account_read_failure_fails_closed():
    # A regular_spot route whose standard-spot account read fails returns None
    # (distinguishable from an insufficient balance, which returns a snapshot with
    # a balance shortfall — see test_routing_regular_spot_insufficient_usdt).
    priv = _RoutingPrivate(cap_assets=["LINK"], spot_account_fail=True)
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    assert _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_FORWARD) is None


def test_routing_regular_spot_rate_limit_read_failure_fails_closed():
    priv = _RoutingPrivate(cap_assets=["LINK"], spot_ratelimit_fail=True)
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    assert _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_FORWARD) is None


def test_routing_regular_spot_insufficient_usdt_is_distinguishable_from_read_failure():
    # cap hit -> regular_spot; standard spot USDT is short. The snapshot is
    # returned (read succeeded) and compute_preflight rejects INSUFFICIENT_BALANCE
    # — a different signal from the None returned on a read failure above.
    priv = _RoutingPrivate(cap_assets=["LINK"], spot_usdt="1")
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    snap = _route_provider(pub, priv).get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is not None
    pf = _D.compute_preflight(snap, "LINKUSDT", _D.DIR_FORWARD, Decimal("1"), 1)
    assert pf.rejection == _D.REJECT_INSUFFICIENT_BALANCE


# ---------------------------------------------------------------------------
# Cache isolation (design §6.4 / acceptance S6): the preflight reads the
# restricted-asset list FRESH on every preflight; it has no reference to the
# SnapshotService display cache, so a stale display value can never route an
# order through the wrong account.
# ---------------------------------------------------------------------------
def test_preflight_provider_accepts_no_display_cache_input():
    # Structural proof (stage 2026-08-06 task 05, §1): the provider reads the
    # SnapshotService-local cache ONLY through the injected read-only
    # ``snapshot_reader`` callable (default None = unchanged real-time path). It
    # never imports SnapshotService and carries no cache object of its own, so
    # the two services stay decoupled.
    import inspect
    params = inspect.signature(HedgePreflightProvider.__init__).parameters
    assert "snapshot_reader" in params
    assert params["snapshot_reader"].default is None
    assert not any(
        "cache" in p or "display" in p for p in params
    ), list(params)
    import backend.services.hedge_preflight_provider as mod
    src = inspect.getsource(mod)
    assert "import snapshot_service" not in src
    assert "from snapshot_service" not in src


def test_preflight_re_reads_restricted_asset_fresh_each_call():
    # A first read "exceeded" -> regular_spot; a second read "not exceeded" ->
    # papi_margin. The route follows the FRESH read every time (never memoized),
    # so a cap that just cleared is honored immediately.
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_perp_sym("LINKUSDT", "PERPETUAL", "LINK")],
                         {"LINKUSDT": _spot_sym("LINKUSDT", "LINK")})
    prov = _route_provider(pub, priv)
    first = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert first.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    # The list changes (e.g. a just-cleared cap) — the next preflight sees it.
    priv._cap = []
    second = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert second.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    # The list was read twice (fresh on each preflight — display cache is never
    # consulted, never back-filled).
    assert priv.calls.count("restricted_asset") == 2


# ---------------------------------------------------------------------------
# Stage 2026-08-06 task 05: SnapshotService-local cache reads (§2/§3) + the
# failed-read name (§5.3). All fake transport — no real network.
# ---------------------------------------------------------------------------
import time as _time
from datetime import datetime, timezone as _tz

_LINK_PERP = _perp_sym("LINKUSDT", "PERPETUAL", "LINK")
_LINK_SPOT = _spot_sym("LINKUSDT", "LINK")


def _fresh_caches(mono_now=None, *, cap_exceeded=frozenset(), wall_now=None):
    """A full fresh-enough snapshot-cache map for LINKUSDT (all 7 sources).

    Entry timestamps are monotonic (``mono_now``); the ``restricted_asset``
    ``checked_at`` is wall-clock UTC (``wall_now``) because its staleness is
    judged on ``checked_at`` (dispatch §2). Pass a stale value to either to age
    that dimension.
    """
    mono_now = _time.monotonic() if mono_now is None else mono_now
    wall_now = _time.time() if wall_now is None else wall_now
    checked_at = datetime.fromtimestamp(wall_now, _tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "group_b_public": (
            mono_now,
            {"futures_exchange_info": {"symbols": [_LINK_PERP]},
             "spot_exchange_info": {"symbols": [_LINK_SPOT]}},
        ),
        "price_map": (mono_now, {"LINKUSDT": "10"}),
        "unified_balances": (mono_now, [{"asset": "USDT", "crossMarginFree": "100000"}]),
        "spot_balances": (mono_now, [{"asset": "USDT", "free": "100000"}]),
        "restricted_asset": (
            mono_now,
            {"exceeded": set(cap_exceeded), "checked_at": checked_at},
        ),
    }


def _cached_provider(private, public, caches, now_ms=lambda: 0):
    reader = (lambda sid: caches.get(sid)) if caches is not None else None
    return HedgePreflightProvider(
        live_client=private, now_ms=now_ms, public_urlopen=public,
        snapshot_reader=reader,
    )


def test_get_snapshot_cache_hit_zero_network_after_account_warmup():
    # §2/§3：全部缓存命中时 get_snapshot 零网络请求。账户级配置（position_mode /
    # rate_limit / spot_rate_limit）是进程内 600s TTL，首次调用实时预热一次。
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    prov = _cached_provider(priv, pub, _fresh_caches())
    # 预热账户 TTL（实时读三次）→ 之后的 get_snapshot 全部命中缓存。
    assert prov._read_position_mode() == _D.POS_MODE_BOTH
    assert prov._read_rate_limit_order() == 100
    assert prov._read_spot_rate_limit_order() == 50
    pub.urls.clear()
    priv.calls.clear()
    snap = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN  # cap 未打满 → papi
    assert pub.urls == [], f"缓存命中不应有任何 public 网络请求: {pub.urls}"
    assert priv.calls == [], f"缓存命中不应有任何 client 调用: {priv.calls}"


def test_check_symbol_legs_cache_hit_zero_network():
    # §2：建卡路径 check_symbol_legs 命中同一份 group_b_public → 零网络，
    # 不再重复拉 1.06MB fapi exchangeInfo。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    prov = _cached_provider(priv, pub, _fresh_caches())
    out = prov.check_symbol_legs("LINKUSDT")
    assert out == {"spot": True, "perp": True}
    assert pub.urls == []


def test_check_symbol_legs_cache_absent_coin_confirmed_false():
    # 新鲜缓存确认该币不存在 → False（权威），不是 None。
    prov = _cached_provider(_RoutingPrivate([]), _RoutingPublic([], {}), _fresh_caches())
    out = prov.check_symbol_legs("NOPEUSDT")
    assert out == {"spot": False, "perp": False}


def test_stale_cache_degrades_to_realtime():
    # §2：每个缓存项超上限 → 降级实时读（spy 断言网络请求发生）。
    stale = _time.monotonic() - 10 * 3600.0  # 10h 前的 entry（monotonic 维度）
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    # cap 列表保持新鲜（fail-closed 项只随 checked_at 判定），其余项全部超龄。
    caches = _fresh_caches(mono_now=stale)
    prov = _cached_provider(priv, pub, caches)
    snap = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is not None  # cap 新鲜 → 不 fail-closed
    assert "fapi/v1/exchangeInfo" in " ".join(pub.urls)  # exchangeInfo 降级实时
    assert "balance" in priv.calls  # balances 降级实时
    assert "restricted_asset" not in priv.calls  # cap 走缓存（未降级）


def test_restricted_asset_stale_fails_closed_no_realtime():
    # §2 要点：restricted_asset 超龄 → forward open FAIL-CLOSED（get_snapshot
    # 返回 None），且绝不降级实时读（priv.calls 无 restricted_asset）。
    stale_wall = _time.time() - 10 * 3600.0  # checked_at 10h 前 → cap 超龄
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    caches = _fresh_caches(wall_now=stale_wall)
    # now_ms 必须是真实 wall clock（checked_at 与它比较判陈旧）。
    prov = _cached_provider(priv, pub, caches, now_ms=lambda: _time.time() * 1000)
    snap = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is None  # fail-closed
    assert prov.last_failed_read == "collateral_cap"
    assert "restricted_asset" not in priv.calls  # 不降级实时读、不猜


def test_restricted_asset_missing_fails_closed():
    # 无 restricted_asset 缓存（reader 缺该 source）→ forward open fail-closed。
    priv = _RoutingPrivate(cap_assets=["LINK"])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    caches = _fresh_caches()
    del caches["restricted_asset"]
    prov = _cached_provider(priv, pub, caches)
    assert prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD) is None
    assert "restricted_asset" not in priv.calls


def test_account_config_ttl_read_once_per_600s_and_failure_not_cached():
    # §3：position_mode / rate_limit 在 600s 内各只读一次；读失败不写缓存。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    prov = _cached_provider(priv, pub, None)  # 无 snapshot_reader
    assert prov._read_position_mode() == _D.POS_MODE_BOTH
    assert prov._read_position_mode() == _D.POS_MODE_BOTH
    assert priv.calls.count("position") == 1  # 第二次命中 TTL
    assert prov._read_rate_limit_order() == 100
    assert prov._read_rate_limit_order() == 100
    assert priv.calls.count("papi_ratelimit") == 1
    # 失败不缓存：下一次调用仍实时（仍失败 → None，fail-closed 不变）。
    failing = _RoutingPrivate(cap_assets=[], spot_account_fail=True)
    _orig_dual = failing.get_position_side_dual
    def _fail_dual(*, timestamp_ms):
        failing.calls.append("position")
        return SimpleNamespace(transport_error="timeout", http_status=None, body=None)
    failing.get_position_side_dual = _fail_dual
    prov2 = _cached_provider(failing, pub, None)
    assert prov2._read_position_mode() is None
    assert prov2._read_position_mode() is None  # 失败未缓存 → 每次实时
    assert failing.calls.count("position") == 2


def test_last_failed_read_names_first_failure():
    # §5.3：第一个失败的读被记录，供暂停中文原因使用。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic([_LINK_PERP], {"LINKUSDT": _LINK_SPOT})
    prov = _cached_provider(priv, pub, None)
    priv.get_balance = lambda *, timestamp_ms: SimpleNamespace(
        transport_error="connection_error", http_status=None, body=None)
    snap = prov.get_snapshot("LINKUSDT", _D.DIR_FORWARD)
    assert snap is None
    assert prov.last_failed_read == "balances"
    # 下一次成功调用重置标记。
    prov2 = _cached_provider(_RoutingPrivate(cap_assets=[]), pub, _fresh_caches())
    prov2._read_position_mode(); prov2._read_rate_limit_order(); prov2._read_spot_rate_limit_order()
    assert prov2.get_snapshot("LINKUSDT", _D.DIR_FORWARD) is not None
    assert prov2.last_failed_read is None


# ---------------------------------------------------------------------------
# Stage 2026-08-06 task 06：close+forward 余额检查读错钱包修复（unified → 普通
# 现货账户）。THE 实盘场景：普通现货持有 THE 600、统一账户无 THE → 不再误报
# 「当前可用 0」。
# ---------------------------------------------------------------------------
_THE_SPOT_FILTERS = {
    "lot_size": {"min_qty": "0.01", "max_qty": "9000", "step_size": "0.01"},
    "market_lot_size": {"min_qty": "0", "max_qty": "9000", "step_size": "0"},
    "notional": {"min_notional": "5", "apply_min_to_market": True},
}
_THE_PERP_FILTERS = {
    "lot_size": {"min_qty": "0.01", "max_qty": "9000", "step_size": "0.01"},
    "market_lot_size": {"min_qty": "0.01", "max_qty": "9000", "step_size": "0.01"},
    "notional": {"notional": "5"},
}


class _TheSpotPrivate(_RoutingPrivate):
    """普通现货账户持有 THE 600（free），统一账户（balances）无 THE。"""

    def get_spot_account(self, *, timestamp_ms):
        self.calls.append("spot_account")
        return SimpleNamespace(
            transport_error=None, http_status=200,
            body={"balances": [{"asset": "USDT", "free": "100000"},
                               {"asset": "THE", "free": "600"}]},
        )


def test_close_forward_reads_standard_spot_base_free_the_scenario():
    # THE 实盘场景（Human 复测暴露）：普通现货 THE 600、统一账户无 THE、
    # close+forward 单次 200×2 → spot_account_base_free=600、balance_ok=True
    # （不再误拦「当前可用 0」）。
    priv = _TheSpotPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    prov = _route_provider(pub, priv)
    snap = prov.get_snapshot("THEUSDT", _D.DIR_REVERSE, task_type=_D.TASK_TYPE_CLOSE)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_REGULAR_SPOT
    assert snap.spot_account_base_free == Decimal("600")
    pf = _D.compute_preflight(snap, "THEUSDT", _D.DIR_REVERSE, Decimal("200"), 2)
    assert pf.rejection is None
    assert pf.balance_ok is True
    assert pf.available == Decimal("600")
    assert pf.required == Decimal("400")


def test_compute_preflight_reverse_regular_spot_uses_standard_spot_base():
    # 纯 domain：REVERSE + regular_spot → available 取普通现货账户该币
    # （spot_account_base_free），不用统一账户 balances（THE 场景误拦的根因修复）。
    snap = _D.PreflightSnapshot(
        spot_filters=_THE_SPOT_FILTERS, perp_filters=_THE_PERP_FILTERS,
        balances={},  # 统一账户无该币
        position_mode=_D.POS_MODE_BOTH, est_price=Decimal("10"),
        spot_route=_D.SPOT_ROUTE_REGULAR_SPOT,
        spot_route_reason=_D.ROUTE_REASON_CLOSE_SELL_REGULAR,
        spot_route_endpoint=_D.REGULAR_SPOT_ORDER_PATH,
        spot_account_usdt=Decimal("100000"), spot_rate_limit_order=50,
        spot_account_base_free=Decimal("600"),
    )
    pf = _D.compute_preflight(snap, "THEUSDT", _D.DIR_REVERSE, Decimal("200"), 2)
    assert pf.balance_ok is True
    assert pf.available == Decimal("600")


def test_compute_preflight_reverse_regular_spot_missing_base_is_zero():
    # 语义与 FORWARD 分支一致：可用量缺失但账户读取成功 = 真 0（不足事实），
    # 不是 None / 不是读取失败。
    snap = _D.PreflightSnapshot(
        spot_filters=_THE_SPOT_FILTERS, perp_filters=_THE_PERP_FILTERS,
        balances={}, position_mode=_D.POS_MODE_BOTH, est_price=Decimal("10"),
        spot_route=_D.SPOT_ROUTE_REGULAR_SPOT,
        spot_route_reason=_D.ROUTE_REASON_CLOSE_SELL_REGULAR,
        spot_route_endpoint=_D.REGULAR_SPOT_ORDER_PATH,
        spot_account_usdt=Decimal("100000"), spot_rate_limit_order=50,
        spot_account_base_free=None,  # 未读取（或缺失）→ 按 0 计
    )
    pf = _D.compute_preflight(snap, "THEUSDT", _D.DIR_REVERSE, Decimal("200"), 2)
    assert pf.balance_ok is False
    assert pf.available == Decimal("0")
    assert pf.rejection == _D.REJECT_INSUFFICIENT_BALANCE


def test_compute_preflight_reverse_papi_margin_keeps_balances_verbatim():
    # 负向回归：REVERSE + papi_margin（reverse 开仓 / close+reverse 买现货）→
    # available 仍取统一账户 balances，逐字不变。
    snap = _D.PreflightSnapshot(
        spot_filters=_THE_SPOT_FILTERS, perp_filters=_THE_PERP_FILTERS,
        balances={"THE": Decimal("2")}, position_mode=_D.POS_MODE_BOTH,
        est_price=Decimal("10"),  # 默认 papi_margin
        spot_account_base_free=None,  # regular_spot 之外不读
    )
    pf = _D.compute_preflight(snap, "THEUSDT", _D.DIR_REVERSE, Decimal("0.5"), 3)
    assert pf.balance_ok is True
    assert pf.available == Decimal("2")
    assert pf.required == Decimal("1.5")


def test_non_regular_spot_never_reads_standard_spot_base():
    # provider 侧：非 regular_spot 路由（close+reverse / reverse 开仓）不读
    # spot_account_base_free（保持 None），且不触发额外普通现货账户读取。
    priv = _RoutingPrivate(cap_assets=[])
    pub = _RoutingPublic(
        [_perp_sym("THEUSDT", "PERPETUAL", "THE")],
        {"THEUSDT": _spot_sym("THEUSDT", "THE", margin_allowed=False)},
    )
    prov = _route_provider(pub, priv)
    # close+reverse（买现货还币）→ papi_margin
    snap = prov.get_snapshot("THEUSDT", _D.DIR_FORWARD, task_type=_D.TASK_TYPE_CLOSE)
    assert snap is not None
    assert snap.spot_route == _D.SPOT_ROUTE_PAPI_MARGIN
    assert snap.spot_account_base_free is None
