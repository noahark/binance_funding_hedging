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


def _spot_sym(symbol, base):
    return {
        "symbol": symbol, "baseAsset": base, "status": "TRADING",
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
    # Structural proof: the provider's constructor takes only live_client + public
    # urlopen + clock/user_agent — never a SnapshotService or a cap cache. It
    # therefore cannot read the display cache even if one existed.
    import inspect
    params = inspect.signature(HedgePreflightProvider.__init__).parameters
    assert not any(
        "snapshot" in p or "cache" in p or "display" in p for p in params
    ), list(params)


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
