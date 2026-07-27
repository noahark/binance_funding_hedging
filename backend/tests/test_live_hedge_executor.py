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

    def post_margin_order(self, params, *, timestamp_ms, recv_window_ms=None):
        # S5 (ADR-H4): the fake client enforces the SAME offline wire rules as the
        # record transport, so a format-class defect is rejected here with a
        # Binance-style -4015 instead of an accepted fill.
        if validate_order_params(params):
            return _resp(400, {"code": -4015, "msg": "Illegal characters found in parameter 'newClientOrderId'."})
        return self._spot_post

    def post_um_order(self, params, *, timestamp_ms, recv_window_ms=None):
        if validate_order_params(params):
            return _resp(400, {"code": -4015, "msg": "Illegal characters found in parameter 'newClientOrderId'."})
        return self._perp_post

    def query_margin_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        self.spot_query_count += 1
        return self._spot_query or _resp(404)

    def query_um_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        self.perp_query_count += 1
        return self._perp_query or _resp(404)


def _ctx() -> AttemptContext:
    return AttemptContext(
        attempt_id="att1", task_id="t1", coin="BTCUSDT", direction=D.DIR_FORWARD,
        single_amount=Decimal("0.5"), q_common=Decimal("0.5"),
        position_side_mode=D.POS_MODE_BOTH, preflight_snapshot={"est_price": "50000"},
        filter_versions={}, target_n=3, ts_us=1000,
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


# ---- reconcile pass: query_leg (never a resend) ----
def test_query_leg_returns_verdict_for_non_terminal_leg():
    client = _FakeClient(spot_query=_resp(200, {"orderId": 11, "status": "FILLED"}))
    exe = _exe(client)
    verdict = exe.query_leg("spot", "BTCUSDT", "hgo-att1-s")
    assert verdict is not None
    assert verdict.dispatch_state == LEG_ACCEPTED


def test_query_leg_without_credentials_is_inconclusive():
    client = _FakeClient(creds=False)
    assert _exe(client).query_leg("spot", "BTCUSDT", "hgo-att1-s") is None


# ---- outcome + terminal helpers ----
def test_dispatch_to_outcome_accepted_pair_is_success():
    spot = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="1")
    perp = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="2")
    outcome = dispatch_to_outcome("att1", spot, perp, {"transport": "live"})
    assert outcome.category == D.ATTEMPT_SUCCESS
    assert outcome.spot["order_id"] == "1"


def test_dispatch_to_outcome_single_leg_is_exposure():
    spot = _leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED, order_id="1")
    perp = _leg_dispatch(state=LEG_REJECTED, order_id=None)
    outcome = dispatch_to_outcome("att1", spot, perp, {"transport": "live"})
    assert outcome.category == D.ATTEMPT_SINGLE_LEG_EXPOSURE


def test_leg_is_terminal_fill():
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_FILLED)) is True
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_ACCEPTED, status=D.LEG_NEW)) is False
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_REJECTED)) is True
    assert leg_is_terminal_fill(_leg_dispatch(state=LEG_UNKNOWN_QUERYING)) is False
