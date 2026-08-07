"""Typed live-executor tests (breakdown §3.5 / §3.7 / ADR-4).

No real network: the :class:`HedgeOpenLiveClient` is faked so each leg's POST/GET
response is scripted. Asserts the acceptance-based response classification keyed
on the recon's timeout/ambiguous reconciliation ladder (recon §3.3), concurrent
two-leg dispatch, the best-effort single client-ID query for an unknown leg
(never a resend), the shared rate-limit flag, and the no-credentials fail-closed
posture.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import AttemptContext
from backend.hedge_open_tasks.wire_constraints import validate_order_params
from backend.services.hedge_open_live_client import HedgeHttpResponse
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LEG_REJECTED,
    LEG_UNKNOWN_QUERYING,
    LiveHedgeExecutor,
    classify_leg_response,
    classify_query_response,
    dispatch_to_outcome,
    leg_is_terminal_fill,
)


def _resp(http_status, body=None, transport_error=None) -> HedgeHttpResponse:
    return HedgeHttpResponse(http_status, body, "", transport_error, None)


def _leg_dispatch(*, state=LEG_ACCEPTED, order_id="1", status=D.LEG_FILLED):
    from backend.services.live_hedge_executor import LegDispatch
    return LegDispatch(leg="spot", dispatch_state=state, order_id=order_id,
                       exchange_status=status, executed_qty="0.5",
                       cumulative_quote="25000", avg_price="50000")


class _FakeClient:
    """Scripts per-leg POST + query responses; counts query calls."""

    def __init__(self, *, spot_post=None, perp_post=None, spot_query=None,
                 perp_query=None, creds=True):
        self._spot_post = spot_post or _resp(200, {"orderId": 1, "status": "FILLED"})
        self._perp_post = perp_post or _resp(200, {"orderId": 2, "status": "FILLED"})
        self._spot_query = spot_query
        self._perp_query = perp_query
        self.credentials_present = creds
        self.spot_query_count = 0
        self.perp_query_count = 0
        self.spot_post_symbols = []
        self.perp_post_symbols = []
        self.spot_query_symbols = []
        self.perp_query_symbols = []
        # Regular-spot route (stage 2026-08-02): distinct methods so a test can
        # prove the spot leg used /api/v3/order, not the PAPI margin endpoint.
        self.regular_spot_post_params = []
        self.regular_spot_post_used = False
        self.margin_spot_post_used = False

    def post_margin_order(self, params, *, timestamp_ms, recv_window_ms=None):
        self.margin_spot_post_used = True
        self.spot_post_symbols.append(params["symbol"])
        # S5 (ADR-H4): the fake client enforces the SAME offline wire rules as the
        # record transport, so a format-class defect is rejected here with a
        # Binance-style -4015 instead of an accepted fill.
        if validate_order_params(params):
            return _resp(400, {"code": -4015, "msg": "Illegal characters found in parameter 'newClientOrderId'."})
        return self._spot_post

    def post_spot_order(self, params, *, timestamp_ms, recv_window_ms=None):
        self.regular_spot_post_used = True
        self.regular_spot_post_params.append(dict(params))
        self.spot_post_symbols.append(params["symbol"])
        if validate_order_params(params):
            return _resp(400, {"code": -4015, "msg": "Illegal characters found in parameter 'newClientOrderId'."})
        return self._spot_post

    def post_um_order(self, params, *, timestamp_ms, recv_window_ms=None):
        self.perp_post_symbols.append(params["symbol"])
        if validate_order_params(params):
            return _resp(400, {"code": -4015, "msg": "Illegal characters found in parameter 'newClientOrderId'."})
        return self._perp_post

    def query_margin_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        self.spot_query_count += 1
        self.spot_query_symbols.append(symbol)
        return self._spot_query or _resp(404)

    def query_spot_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        self.spot_query_count += 1
        self.spot_query_symbols.append(symbol)
        return self._spot_query or _resp(404)

    def query_um_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        self.perp_query_count += 1
        self.perp_query_symbols.append(symbol)
        return self._perp_query or _resp(404)


def _ctx(*, spot_symbol=None, spot_route=None) -> AttemptContext:
    # 2026-08-07 身份统一：现货腿 symbol 走 AttemptContext.spot_symbol（由 service
    # 从任务固化列传入），不再藏在预检快照里。
    snapshot = {"est_price": "50000"}
    if spot_route is not None:
        snapshot["spot_route"] = spot_route
    return AttemptContext(
        attempt_id="att1", task_id="t1", coin="BTCUSDT", direction=D.DIR_FORWARD,
        single_amount=Decimal("0.5"), q_common=Decimal("0.5"),
        position_side_mode=D.POS_MODE_BOTH, preflight_snapshot=snapshot,
        filter_versions={}, target_n=3, ts_us=1000, spot_symbol=spot_symbol,
    )


def _exe(client) -> LiveHedgeExecutor:
    return LiveHedgeExecutor(client, now_ms=lambda: 1000)


# ---- classify_leg_response (POST verdict ladder, recon §3.3) ----
def test_post_transport_error_is_unknown():
    assert classify_leg_response(_resp(None, transport_error="timeout"), "spot").dispatch_state == LEG_UNKNOWN_QUERYING


def test_post_2xx_with_order_id_is_accepted():
    d = classify_leg_response(_resp(200, {"orderId": 123, "status": "FILLED", "executedQty": "0.5"}), "spot")
    assert d.dispatch_state == LEG_ACCEPTED
    assert d.order_id == "123"
    assert d.exchange_status == "FILLED"
    assert d.executed_qty == "0.5"


def test_post_2xx_without_order_id_is_unknown():
    assert classify_leg_response(_resp(200, {"msg": "malformed"}), "spot").dispatch_state == LEG_UNKNOWN_QUERYING


def test_post_2xx_new_status_is_accepted_not_filled():
    # NEW (accepted but not filled) is still ACCEPTED; fill is observational.
    d = classify_leg_response(_resp(200, {"orderId": 7, "status": "NEW", "executedQty": "0"}), "perp")
    assert d.dispatch_state == LEG_ACCEPTED
    assert d.exchange_status == "NEW"


def test_post_5xx_generic_is_unknown():
    assert classify_leg_response(_resp(500, {"msg": "boom"}), "spot").dispatch_state == LEG_UNKNOWN_QUERYING


def test_post_503_unknown_error_is_unknown():
    assert classify_leg_response(_resp(503, {"msg": "Unknown error"}), "spot").dispatch_state == LEG_UNKNOWN_QUERYING


@pytest.mark.parametrize("body", [
    {"code": -1008, "msg": "x"},
    {"msg": "Service Unavailable"},
])
def test_post_503_throttle_failure_is_rejected(body):
    assert classify_leg_response(_resp(503, body), "spot").dispatch_state == LEG_REJECTED


def test_post_429_is_unknown_and_rate_limited():
    d = classify_leg_response(_resp(429, {"code": -1003}), "spot")
    assert d.dispatch_state == LEG_UNKNOWN_QUERYING
    assert d.rate_limited is True


def test_post_418_ban_is_rate_limited():
    d = classify_leg_response(_resp(418, {}), "spot")
    assert d.rate_limited is True
    assert d.dispatch_state == LEG_UNKNOWN_QUERYING


def test_post_400_rate_limit_body_is_rate_limited():
    d = classify_leg_response(_resp(400, {"code": -1003, "msg": "too many"}), "spot")
    assert d.rate_limited is True


def test_post_400_other_is_rejected():
    assert classify_leg_response(_resp(400, {"code": -2010, "msg": "insufficient"}), "spot").dispatch_state == LEG_REJECTED


# ---- classify_query_response (GET origClientOrderId ladder) ----
def test_query_transport_error_is_inconclusive_none():
    assert classify_query_response(_resp(None, transport_error="timeout"), "spot") is None


def test_query_5xx_is_inconclusive_none():
    assert classify_query_response(_resp(500, {}), "spot") is None


def test_query_4xx_is_rejected_absent():
    d = classify_query_response(_resp(404, {"msg": "no order"}), "spot")
    assert d is not None and d.dispatch_state == LEG_REJECTED


def test_query_2xx_with_order_id_is_accepted():
    d = classify_query_response(_resp(200, {"orderId": 55, "status": "FILLED"}), "perp")
    assert d.dispatch_state == LEG_ACCEPTED
    assert d.order_id == "55"


def test_query_2xx_without_order_id_stays_unknown():
    # R2-F2 (user authorization 28 §2.2): a 2xx query missing a valid orderId is
    # NOT a confirmed absent signal — only an explicit 404 / Binance -2013 is.
    # A malformed 2xx stays UNKNOWN_QUERYING so the worker keeps querying by
    # client ID (never resends, never rejects a possibly-accepted order as
    # absent, which would open the next group on a maybe-already-filled leg).
    d = classify_query_response(_resp(200, {"msg": "absent"}), "spot")
    assert d is not None
    assert d.dispatch_state == LEG_UNKNOWN_QUERYING


def test_query_rate_limited_keeps_unknown_with_rate_limited_signal():
    # R2-F2: a rate-limited query (429 / -1003 / 418) must surface a typed
    # rate-limit signal — UNKNOWN_QUERYING + rate_limited=True — so the task's
    # worker can observe the throttle, pause THIS task, keep the pending leg, and
    # exit for manual recovery. Returning None drops the fact and lets the worker
    # keep polling straight into the IP ban.
    d = classify_query_response(_resp(429, {"code": -1003}), "spot")
    assert d is not None
    assert d.dispatch_state == LEG_UNKNOWN_QUERYING
    assert d.rate_limited is True


# ---- T3 raw-response capture (10-design §3) — stage 2026-07-hedge-order-truth-v1.
# Every classified interaction carries its sanitized response for persistence; the
# dict is response-only (no request param / signature / api key ever present).
_RAW_KEYS = {"http_status", "transport_error", "code", "msg", "body"}


def test_post_4xx_carries_sanitized_raw_response():
    raw_body = '{"code":51169,"msg":"MARGIN_TRADE_COEFF_INSUFFICIENT"}'
    resp = HedgeHttpResponse(400, {"code": 51169, "msg": "MARGIN_TRADE_COEFF_INSUFFICIENT"},
                             raw_body, None, None)
    d = classify_leg_response(resp, "spot")
    assert d.raw_response is not None
    assert set(d.raw_response.keys()) == _RAW_KEYS  # response-only, no secret fields
    assert d.raw_response["http_status"] == 400
    assert d.raw_response["code"] == "51169"
    assert d.raw_response["msg"] == "MARGIN_TRADE_COEFF_INSUFFICIENT"
    assert d.raw_response["body"] == raw_body  # verbatim


def test_post_transport_error_still_carries_raw_response():
    # Capture happens at response-arrival time, terminal or not — a transport
    # failure (no HTTP status) is still recorded for forensics.
    resp = HedgeHttpResponse(None, None, "", "timeout", None)
    d = classify_leg_response(resp, "spot")
    assert d.raw_response is not None
    assert d.raw_response["http_status"] is None
    assert d.raw_response["transport_error"] == "timeout"


def test_query_2xx_carries_raw_response():
    raw_body = '{"orderId":55,"status":"FILLED"}'
    resp = HedgeHttpResponse(200, {"orderId": 55, "status": "FILLED"}, raw_body, None, None)
    d = classify_query_response(resp, "perp")
    assert d is not None and d.raw_response is not None
    assert set(d.raw_response.keys()) == _RAW_KEYS
    assert d.raw_response["body"] == raw_body


# ---- T1 fill-figure sourcing (10-design §1) — stage 2026-07-hedge-order-truth-v1.
# The margin/UM asymmetry is an intentional per-product rule: the spot (margin)
# POST RESULT carries cummulativeQuoteQty (authoritative); the perp (UM) POST only
# proves acceptance — its 2026-07-14 RESULT body dropped cumQuote/avgPrice, so the
# authoritative figures come from the order-detail GET (inline confirm here). A
# missing figure is None (NULL), never a coerced "0".
def test_post_margin_2xx_carries_quote_from_post_result():
    resp = _resp(200, {"orderId": 1, "status": "FILLED", "executedQty": "0.5",
                       "cummulativeQuoteQty": "25000"})
    d = classify_leg_response(resp, "spot")
    assert d.dispatch_state == LEG_ACCEPTED
    assert d.cumulative_quote == "25000"  # authoritative from the POST RESULT
    assert d.avg_price is None
    assert leg_is_terminal_fill(d) is True  # margin FILLED -> terminal


def test_post_um_2xx_carries_no_quote_acceptance_only():
    # The UM POST body has orderId/status/executedQty but NO cumQuote/avgPrice
    # (the 2026-07-14 removal). classify must NOT synthesize a quote from the POST.
    resp = _resp(200, {"orderId": 7, "status": "FILLED", "executedQty": "0.5"})
    d = classify_leg_response(resp, "perp")
    assert d.dispatch_state == LEG_ACCEPTED
    assert d.order_id == "7"
    assert d.executed_qty == "0.5"
    assert d.cumulative_quote is None  # POST is acceptance-only for UM
    assert d.avg_price is None


def test_post_um_2xx_carries_post_raw_response():
    raw_body = '{"orderId":2,"status":"FILLED","executedQty":"0.5"}'
    resp = HedgeHttpResponse(200, {"orderId": 2, "status": "FILLED",
                                    "executedQty": "0.5"}, raw_body, None, None)
    d = classify_leg_response(resp, "perp")
    assert d.raw_response is not None  # POST raw still captured even w/o quote
    assert set(d.raw_response.keys()) == _RAW_KEYS
    assert d.raw_response["body"] == raw_body
    assert d.confirm_raw_response is None  # classify_leg_response does POST only


def test_dispatch_um_accepted_confirms_figures_inline():
    # T1 §1(b): a UM leg POST-accepted immediately confirms its authoritative
    # figures via the order-detail GET; the merged dispatch carries the GET's
    # cumQuote/avgPrice and is a terminal fill.
    client = _FakeClient(
        perp_post=_resp(200, {"orderId": 2, "status": "FILLED", "executedQty": "0.5"}),
        perp_query=_resp(200, {"orderId": 2, "status": "FILLED", "executedQty": "0.5",
                                "cumQuote": "25000", "avgPrice": "50000"}),
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.perp.dispatch_state == LEG_ACCEPTED
    assert dispatch.perp.cumulative_quote == "25000"  # from the inline confirm GET
    assert dispatch.perp.avg_price == "50000"
    assert leg_is_terminal_fill(dispatch.perp) is True
    assert client.perp_query_count == 1  # exactly one inline confirm GET
    assert client.spot_query_count == 0  # margin leg needs no confirm


def test_dispatch_um_confirm_inconclusive_keeps_nonterminal_quote_none():
    # T1 §1(b): a 5xx confirm is inconclusive — the leg keeps POST acceptance but
    # stays non-terminal with quote=None, drained next round. Never a coerced 0.
    client = _FakeClient(
        perp_post=_resp(200, {"orderId": 2, "status": "FILLED", "executedQty": "0.5"}),
        perp_query=_resp(500, {}),
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.perp.dispatch_state == LEG_ACCEPTED  # POST acceptance kept
    assert dispatch.perp.cumulative_quote is None        # unknown, not 0
    assert leg_is_terminal_fill(dispatch.perp) is False  # non-terminal -> drain


def test_dispatch_um_confirm_404_does_not_overturn_post_acceptance():
    # T1 §1(b): a POST-just-accepted UM order 404-ing on the immediate confirm is
    # eventual-consistency noise, NOT a real absent signal — the POST orderId
    # stands; the leg keeps acceptance with quote=None and drains later.
    client = _FakeClient(
        perp_post=_resp(200, {"orderId": 2, "status": "FILLED", "executedQty": "0.5"}),
        perp_query=_resp(404),
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.perp.dispatch_state == LEG_ACCEPTED  # NOT overturned to REJECTED
    assert dispatch.perp.order_id == "2"
    assert dispatch.perp.cumulative_quote is None


def test_dispatch_um_confirm_carries_confirm_raw_response():
    # T1+T3 §3(b): the UM inline-confirm GET response rides on confirm_raw_response
    # for raw persistence (source=order_confirm); the POST raw stays on raw_response.
    client = _FakeClient(
        perp_post=_resp(200, {"orderId": 2, "status": "FILLED", "executedQty": "0.5"}),
        perp_query=_resp(200, {"orderId": 2, "status": "FILLED",
                                "cumQuote": "25000", "avgPrice": "50000"}),
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.perp.confirm_raw_response is not None
    assert set(dispatch.perp.confirm_raw_response.keys()) == _RAW_KEYS
    assert dispatch.perp.raw_response is not None  # POST raw still present
    assert dispatch.spot.confirm_raw_response is None  # margin leg does not confirm


# ---- orderId normalization (acceptance proof must be a positive integer) ----
@pytest.mark.parametrize("value,expected", [
    (123, "123"), ("456", "456"), ("007", "7"), (0, None), (-1, None),
    (None, None), ("1.5", None), ("abc", None), (True, None),
])
def test_order_id_normalization(value, expected):
    d = classify_leg_response(_resp(200, {"orderId": value, "status": "FILLED"}), "spot")
    if expected is None:
        assert d.dispatch_state == LEG_UNKNOWN_QUERYING  # no valid orderId -> unknown
    else:
        assert d.order_id == expected


# ---- strict fake client: offline wire rules -> Binance-style -4015 (S5) ----
def test_fake_client_rejects_overlong_client_id_with_binance_style_4015():
    """S5 (ADR-H4): the strict fake client enforces the same offline wire rules
    as the record transport, so a too-long ``newClientOrderId`` is rejected with
    a Binance-style ``-4015`` (the code a real 38-char id returned). A clean body
    is still accepted (the default scripted 200)."""
    client = _FakeClient()
    bad = {
        "symbol": "BTCUSDT", "side": "BUY", "type": "MARKET",
        "quantity": "0.5", "newClientOrderId": "x" * 37,
    }
    resp = client.post_margin_order(bad, timestamp_ms=1)
    assert resp.http_status == 400
    assert resp.body["code"] == -4015
    good = {**bad, "newClientOrderId": "hgxs"}
    assert client.post_margin_order(good, timestamp_ms=1).http_status == 200


# ---- concurrent two-leg dispatch ----
def test_dispatch_both_accepted_needs_no_query():
    client = _FakeClient()
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.spot.dispatch_state == LEG_ACCEPTED
    assert dispatch.perp.dispatch_state == LEG_ACCEPTED
    assert dispatch.spot.order_id == "1"
    assert dispatch.rate_limited is False
    assert client.spot_query_count == 0  # accepted synchronously -> no query
    assert dispatch.record_payload["posted"] is True


def test_dispatch_uses_bstock_alias_for_spot_post_and_query():
    client = _FakeClient(
        spot_post=_resp(500, {"msg": "timeout"}),
        spot_query=_resp(200, {"orderId": 11, "status": "FILLED", "executedQty": "0.5"}),
    )
    dispatch = _exe(client).dispatch(_ctx(spot_symbol="TSLABUSDT"))
    assert dispatch.record_payload["spot_order_params"]["symbol"] == "TSLABUSDT"
    assert dispatch.record_payload["perp_order_params"]["symbol"] == "BTCUSDT"
    assert client.spot_post_symbols == ["TSLABUSDT"]
    assert client.spot_query_symbols == ["TSLABUSDT"]


def test_dispatch_unknown_leg_resolved_by_single_client_id_query():
    client = _FakeClient(
        spot_post=_resp(None, transport_error="timeout"),  # unknown POST
        spot_query=_resp(200, {"orderId": 11, "status": "FILLED"}),  # query resolves
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.spot.dispatch_state == LEG_ACCEPTED  # resolved by ONE query
    assert dispatch.spot.order_id == "11"
    assert client.spot_query_count == 1  # queried exactly once (never resent)


def test_dispatch_unknown_leg_stays_unknown_when_query_inconclusive():
    client = _FakeClient(
        spot_post=_resp(None, transport_error="timeout"),
        spot_query=_resp(500, {}),  # query also ambiguous -> stays unknown
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.spot.dispatch_state == LEG_UNKNOWN_QUERYING
    assert client.spot_query_count == 1


def test_dispatch_surfaces_rate_limited_flag_when_any_leg_throttled():
    client = _FakeClient(
        spot_post=_resp(429, {"code": -1003}),
        spot_query=_resp(429, {"code": -1003}),  # query still throttled
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.rate_limited is True


def test_dispatch_post_unknown_query_throttled_preserves_rate_limited():
    # R2-F2: when the POST is ambiguous (no rate-limit verdict of its own) but the
    # best-effort query surfaces a 429, the merged leg verdict must carry the
    # rate-limit signal end-to-end. Swallowing the query-time throttle (taking
    # only the POST's rate_limited=False) hides a real limit from the worker.
    client = _FakeClient(
        spot_post=_resp(None, transport_error="timeout"),  # POST ambiguous
        spot_query=_resp(429, {"code": -1003}),  # best-effort query throttled
    )
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.rate_limited is True
    assert dispatch.spot.dispatch_state == LEG_UNKNOWN_QUERYING


def test_dispatch_without_credentials_fails_closed_unknown():
    client = _FakeClient(creds=False)
    dispatch = _exe(client).dispatch(_ctx())
    assert dispatch.spot.dispatch_state == LEG_UNKNOWN_QUERYING
    assert dispatch.perp.dispatch_state == LEG_UNKNOWN_QUERYING


# ---- regular-spot route dispatch (design §4): /api/v3/order, no sideEffectType ----
def test_dispatch_regular_spot_uses_spot_endpoint_and_omits_side_effect_type():
    # A regular_spot route posts the spot leg via post_spot_order (/api/v3/order),
    # NOT post_margin_order (PAPI), and the spot params carry NO sideEffectType.
    # The perp leg still posts via post_um_order (PAPI UM unchanged).
    client = _FakeClient()
    dispatch = _exe(client).dispatch(_ctx(spot_route=D.SPOT_ROUTE_REGULAR_SPOT))
    assert dispatch.spot.dispatch_state == LEG_ACCEPTED
    assert client.regular_spot_post_used is True
    assert client.margin_spot_post_used is False
    spot_params = client.regular_spot_post_params[0]
    assert "sideEffectType" not in spot_params  # the regular-spot shape omits it
    # The perp leg is unchanged (PAPI UM).
    assert client.perp_post_symbols == ["BTCUSDT"]
    # The endpoint follows the route on the record payload's preflight snapshot.
    assert dispatch.record_payload["preflight_snapshot"]["spot_route"] == D.SPOT_ROUTE_REGULAR_SPOT


def test_dispatch_papi_margin_spot_keeps_side_effect_type():
    # The default PAPI margin route keeps sideEffectType=NO_SIDE_EFFECT (unchanged).
    client = _FakeClient()
    _exe(client).dispatch(_ctx(spot_route=D.SPOT_ROUTE_PAPI_MARGIN))
    assert client.margin_spot_post_used is True
    assert client.regular_spot_post_used is False


def test_build_regular_spot_order_params_has_no_side_effect_type():
    # The param builder for /api/v3/order omits sideEffectType entirely; the PAPI
    # margin builder keeps it. The two shapes are deliberately distinct (design §4).
    from backend.hedge_open_tasks.executor import build_spot_order_params
    actions = D.direction_to_leg_actions(D.DIR_FORWARD, D.POS_MODE_BOTH)
    regular = D.build_regular_spot_order_params("LINKUSDT", actions, Decimal("0.5"), "cid")
    margin = build_spot_order_params("LINKUSDT", actions, Decimal("0.5"), "cid")
    assert "sideEffectType" not in regular
    assert margin["sideEffectType"] == D.SIDE_EFFECT_NO_SIDE_EFFECT
    # Both still carry the wire-approved MARKET order keys.
    assert regular["type"] == D.ORDER_TYPE_MARKET
    assert regular["symbol"] == "LINKUSDT"


def test_classify_regular_spot_51169_is_unclassified_not_collateral_cap():
    # A regular-spot leg (PRODUCT_SPOT) returning 51169 is UNCLASSIFIED — it must
    # not inherit the margin collateral_cap pause (51169 is a PAPI margin code that
    # /api/v3/order cannot return). PAPI margin keeps collateral_cap.
    cap_body = _resp(400, {"code": 51169, "msg": "MARGIN_TRADE_COEFF_INSUFFICIENT"})
    assert classify_leg_response(cap_body, "spot", D.PRODUCT_SPOT).error_category == D.ERROR_CATEGORY_UNCLASSIFIED
    assert classify_leg_response(cap_body, "spot", D.PRODUCT_MARGIN).error_category == D.ERROR_CATEGORY_COLLATERAL_CAP


# ---- reconcile pass: query_leg (never a resend) ----
def test_query_leg_returns_verdict_for_non_terminal_leg():
    client = _FakeClient(spot_query=_resp(200, {"orderId": 11, "status": "FILLED"}))
    exe = _exe(client)
    # endpoint is the leg-row authority: PAPI margin path here (a regular-spot
    # leg would pass /api/v3/order and route to the spot querier + PRODUCT_SPOT).
    verdict = exe.query_leg("spot", "BTCUSDT", "hgo-att1-s", "/papi/v1/margin/order")
    assert verdict is not None
    assert verdict.dispatch_state == LEG_ACCEPTED


def test_query_leg_without_credentials_is_inconclusive():
    client = _FakeClient(creds=False)
    assert _exe(client).query_leg(
        "spot", "BTCUSDT", "hgo-att1-s", "/papi/v1/margin/order"
    ) is None


# ---- outcome + terminal helpers ----
def test_dispatch_to_outcome_accepted_pair_is_success():
    spot = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="1")
    perp = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="2")
    outcome = dispatch_to_outcome("att1", spot, perp, {"transport": "live"}, 1_784_448_000_000_000)
    assert outcome.category == D.ATTEMPT_SUCCESS
    assert outcome.spot["order_id"] == "1"


def test_dispatch_to_outcome_single_leg_is_exposure():
    spot = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="1")
    perp = _leg_dispatch(state=LEG_REJECTED, order_id=None)
    ts_us = 1_784_448_000_000_000
    outcome = dispatch_to_outcome("att1", spot, perp, {"transport": "live"}, ts_us)
    assert outcome.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    # T5 (stage 2026-07-hedge-order-truth-v1): the live exposure timestamp is the
    # settlement wall clock, never the 1970 epoch a forgotten 0 would render.
    assert outcome.exposure is not None
    assert outcome.exposure["ts"] == D.us_to_iso(ts_us)
    assert outcome.exposure["ts"] != "1970-01-01T00:00:00.000000Z"


def test_leg_is_terminal_fill():
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED)) is True
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_NEW)) is False
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_REJECTED)) is True
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_UNKNOWN_QUERYING)) is False


# ---- R2-Rerun-F1: avgPrice 的数值零（含币安 "0.00000"）不是真实成交价 ----

def test_avg_price_decimal_drops_any_numeric_zero_keeps_nonzero_verbatim():
    # 解析层：任何可解析为数值零的输入（"0"、"0.00000"、"0E-8"、"-0"、0）一律 None；
    # 非零值逐字原样（不补零/截断/科学计数法）；缺失/不可解析 -> None。
    from backend.services.live_hedge_executor import _avg_price_decimal
    for zero in ["0", "0.00000", "0.0", "0E-8", "-0", "0e0", 0]:
        assert _avg_price_decimal(zero) is None, f"{zero!r} 应判为数值零 -> None"
    assert _avg_price_decimal("50000.12") == "50000.12"     # 非零逐字
    assert _avg_price_decimal("0.0000123") == "0.0000123"   # 极小但非零，逐字保留
    for missing in [None, "", "abc", True, False]:
        assert _avg_price_decimal(missing) is None, f"{missing!r} 缺失/不可解析 -> None"


def test_quote_decimal_real_zero_is_preserved_not_dropped():
    # 硬约束【易错】：成交额的 "0" 是真实零成交（合法值），与均价零含义不同——
    # _quote_decimal 不得跟着 _avg_price_decimal 把 "0" 丢掉，T1 NULL 契约完好。
    from backend.services.live_hedge_executor import _quote_decimal
    assert _quote_decimal("0") == "0"
    assert _quote_decimal("0.00000") == "0.00000"
    assert _quote_decimal("25000") == "25000"


def test_query_zero_avg_price_is_not_a_real_price():
    # 端到端（AC3/AC4）：合约腿「已受理但未成交」的订单详情（status=NEW、avgPrice="0.00000"）
    # 经 classify_query_response 后 avg_price 为 None（前端渲染 —，页面上不出现 0）；
    # 非零 avgPrice 仍优先取用。
    body_zero = {"orderId": 55, "status": "NEW", "executedQty": "0", "avgPrice": "0.00000"}
    d_zero = classify_query_response(_resp(200, body_zero), "perp")
    assert d_zero is not None and d_zero.dispatch_state == LEG_ACCEPTED
    assert d_zero.avg_price is None                  # 零均价不落库、不展示
    body_real = {"orderId": 55, "status": "FILLED", "executedQty": "0.5", "avgPrice": "50000.12"}
    d_real = classify_query_response(_resp(200, body_real), "perp")
    assert d_real is not None and d_real.avg_price == "50000.12"   # 真实均价照常


# ---- A-2 (stage 2026-08-06): a leg-send Python exception keeps evidence ----
def test_dispatch_leg_exception_carries_raw_response_and_stays_unknown():
    """A Python exception raised during send (whitelist PermissionError, Request
    construction, …) must persist a sanitized raw-response row instead of being
    silently dropped, and the leg stays LEG_UNKNOWN_QUERYING (query by client id,
    never resend — ADR-2)."""

    class _RaisingPerpClient(_FakeClient):
        def post_um_order(self, params, *, timestamp_ms, recv_window_ms=None):
            raise PermissionError(
                "hedge endpoint not whitelisted: POST /papi/v1/um/order"
            )

    dispatch = _exe(_RaisingPerpClient()).dispatch(_ctx())
    assert dispatch.perp.dispatch_state == LEG_UNKNOWN_QUERYING
    assert dispatch.perp.raw_response is not None
    raw = dispatch.perp.raw_response
    assert raw["http_status"] is None
    assert raw["code"] is None and raw["msg"] is None
    assert raw["body"] == ""
    assert raw["transport_error"].startswith(
        "leg_send_exception:PermissionError:"
    )
    assert "whitelisted" in raw["transport_error"]
    # the other leg still dispatched normally
    assert dispatch.spot.dispatch_state == LEG_ACCEPTED


def test_error_leg_without_exception_marks_unknown():
    from backend.services.live_hedge_executor import _error_leg

    d = _error_leg("spot", None)
    assert d.dispatch_state == LEG_UNKNOWN_QUERYING
    assert d.raw_response is not None
    assert d.raw_response["transport_error"] == "leg_send_exception:unknown"
