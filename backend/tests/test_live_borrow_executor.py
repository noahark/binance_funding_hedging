"""Tests for the typed live borrow executor (Boundary C §5).

No network: the PM borrow client is a fake that returns scripted
:class:`BorrowHttpResponse` objects. Covers the POST classification matrix
(§5.1), ``tranId`` arbitrary-precision normalization, and the credentials
self-defense gate.
"""
from __future__ import annotations

import pytest
from decimal import Decimal

from backend.borrow_tasks import domain as D
from backend.services.live_borrow_executor import (
    LiveBorrowExecutor,
    _normalize_tran_id,
    classify_post_response,
)
from backend.services.portfolio_margin_borrow_client import BorrowHttpResponse


def _resp(status, body=None, transport_error=None, retry_after=None):
    return BorrowHttpResponse(status, body, "{}", transport_error, retry_after)


# ---------------------------------------------------------------------------
# POST classification matrix (§5.1)
# ---------------------------------------------------------------------------
def test_classify_success_valid_tranid():
    r = classify_post_response(_resp(200, {"tranId": 12345}))
    assert r.result_category == D.RESULT_SUCCESS
    assert r.tran_id == "12345"
    assert r.http_status == 200


def test_classify_malformed_2xx_no_tranid_is_unknown():
    r = classify_post_response(_resp(200, {}))
    assert r.result_category == D.RESULT_UNKNOWN
    r2 = classify_post_response(_resp(200, {"tranId": "abc"}))
    assert r2.result_category == D.RESULT_UNKNOWN


def test_classify_known_rejection_exact_codes():
    # Docs use negative form; live PAPI wire has returned positive 51061 (DEXE).
    for raw in (-51006, -51014, -51061, 51006, 51014, 51061):
        r = classify_post_response(_resp(400, {"code": raw}))
        assert r.result_category == D.RESULT_KNOWN_REJECTION
        assert r.business_code == str(raw)


def test_classify_other_4xx_is_known_rejection_stays_in_rotation():
    # Scheme A: definite 4xx (auth / unlisted business) are known_rejection so
    # it is a definite rejection — only malformed 2xx / 5xx classify as unknown.
    r = classify_post_response(_resp(400, {"code": -2014}))
    assert r.result_category == D.RESULT_KNOWN_REJECTION
    assert r.business_code == "-2014"
    for raw in (-51007, 51007, 51099):
        r2 = classify_post_response(_resp(400, {"code": raw}))
        assert r2.result_category == D.RESULT_KNOWN_REJECTION
        assert r2.business_code == str(raw)


def test_classify_http_401_2015_is_known_rejection_not_blocked():
    # Live DEXE: unlisted_http_401 / -2015 is a definite rejection, not unknown.
    r = classify_post_response(
        _resp(401, {"code": -2015, "msg": "Invalid API-key, IP, or permissions for action."})
    )
    assert r.result_category == D.RESULT_KNOWN_REJECTION
    assert r.http_status == 401
    assert r.business_code == "-2015"
    assert r.reason == "known_rejection:-2015"


def test_classify_429_rate_limited_with_clamped_retry_after():
    r = classify_post_response(_resp(429, {"code": -1003}, retry_after=5))
    assert r.result_category == D.RESULT_RATE_LIMITED
    assert r.retry_after_seconds == Decimal("60")  # 5 clamped up to floor 60
    # Ceiling half of the [60, 300] band (was a store-setter test before the
    # reconciliation subsystem was removed; clamping only lives here now).
    r = classify_post_response(_resp(429, {"code": -1003}, retry_after=9999))
    assert r.retry_after_seconds == Decimal("300")


def test_classify_1003_under_http_400_is_rate_limited():
    r = classify_post_response(_resp(400, {"code": -1003}, retry_after=120))
    assert r.result_category == D.RESULT_RATE_LIMITED
    assert r.retry_after_seconds == Decimal("120")


def test_classify_418_ban_300s_no_auto_resume():
    r = classify_post_response(_resp(418, {}))
    assert r.result_category == D.RESULT_RATE_LIMITED
    assert r.http_status == 418
    assert r.retry_after_seconds == Decimal("300")


def test_classify_5xx_is_unknown():
    r = classify_post_response(_resp(503, "upstream"))
    assert r.result_category == D.RESULT_UNKNOWN


@pytest.mark.parametrize("raw", [-51006, -51014, -51061, 51006, 51014, 51061])
def test_classify_2xx_with_known_code_is_unknown(raw):
    # Review-2 P1 regression: a 2xx body carrying a known rejection code is NOT
    # a clean rejection — the 2xx may still have been accepted — so it fails
    # closed to unknown and is never counted as a successful borrow.
    r = classify_post_response(_resp(200, {"code": raw}))
    assert r.result_category == D.RESULT_UNKNOWN
    assert r.business_code == str(raw)
    assert r.tran_id is None


@pytest.mark.parametrize("raw", [-51006, -51014, -51061, 51006, 51014, 51061])
def test_classify_5xx_with_known_code_is_unknown(raw):
    # A 5xx is possibly accepted by the exchange; a body carrying a known code
    # does not make it a definite rejection, so every 5xx stays unknown.
    for status in (500, 502, 503):
        r = classify_post_response(_resp(status, {"code": raw}))
        assert r.result_category == D.RESULT_UNKNOWN
        assert r.business_code == str(raw)


@pytest.mark.parametrize("raw", [-51006, -51014, -51061, 51006, 51014, 51061])
def test_classify_4xx_with_known_code_remains_known_rejection(raw):
    # Positive control: definite 4xx with either documented (-) or wire (+) form
    # classifies as known_rejection and stays in rotation.
    r = classify_post_response(_resp(400, {"code": raw}))
    assert r.result_category == D.RESULT_KNOWN_REJECTION
    assert r.business_code == str(raw)


def test_classify_dexe_style_positive_51061_is_known_rejection():
    # Live DEXE marginLoan: HTTP 400 body code 51061 (positive) must not become
    # unlisted_http_400 / unknown.
    r = classify_post_response(
        _resp(400, {"code": 51061, "msg": "insufficient loanable assets"})
    )
    assert r.result_category == D.RESULT_KNOWN_REJECTION
    assert r.business_code == "51061"
    assert r.reason == "known_rejection:51061"


def test_classify_transport_error_is_known_rejection_scheme_c():
    # Scheme C: timeout / connection_error classify as known_rejection, not unknown.
    for err in ("timeout", "connection_error", "URLError"):
        r = classify_post_response(_resp(None, None, transport_error=err))
        assert r.result_category == D.RESULT_KNOWN_REJECTION
        assert r.http_status is None
        assert r.reason == f"transport_error:{err}"


# ---------------------------------------------------------------------------
# tranId arbitrary-precision normalization (never float)
# ---------------------------------------------------------------------------
def test_normalize_tran_id_int_and_string():
    assert _normalize_tran_id(12345) == "12345"
    assert _normalize_tran_id("12345") == "12345"
    assert _normalize_tran_id("  42 ") == "42"


def test_normalize_large_integer_no_float_loss():
    big = "9223372036854775807"  # int64 max
    assert _normalize_tran_id(big) == big
    bigger = "99999999999999999999999999"  # beyond int64
    assert _normalize_tran_id(bigger) == bigger
    assert "e" not in _normalize_tran_id(bigger).lower()  # no scientific notation


def test_normalize_tran_id_rejects_invalid():
    # Non-positive, non-integer, empty, unparseable, bool, or float-typed -> None.
    # ("1.0"/"12.0" ARE valid integer values and normalize to "1"/"12".)
    for bad in (None, True, 0, -1, "", "1.5", "abc", 1.5):
        assert _normalize_tran_id(bad) is None
    assert _normalize_tran_id("1.0") == "1"
    assert _normalize_tran_id("12.0") == "12"


# ---------------------------------------------------------------------------
# LiveBorrowExecutor over a fake client
# ---------------------------------------------------------------------------
class FakeClient:
    def __init__(self, *, creds=True):
        self._creds = creds
        self.post_response = None
        self.posts = []

    @property
    def credentials_present(self):
        return self._creds

    def post_margin_loan(self, asset, amount, *, timestamp_ms, recv_window_ms=None):
        self.posts.append((asset, amount, timestamp_ms))
        return self.post_response


def _task(asset="BTC", amount="1.5"):
    return {"id": "t1", "asset": asset, "amount_per_attempt": amount}


def _attempt(amount="1.5", tran_id=None, dispatched_us=1_000_000):
    return {
        "id": 7, "task_id": "t1", "asset": "BTC", "requested_amount": amount,
        "tran_id": tran_id, "dispatched_at_us": dispatched_us,
    }


def test_executor_execute_classifies_post():
    fc = FakeClient()
    fc.post_response = _resp(200, {"tranId": 999})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 1000)
    r = exe.execute(_task(), _attempt())
    assert r.result_category == D.RESULT_SUCCESS
    assert r.tran_id == "999"
    assert fc.posts == [("BTC", "1.5", 1000)]


def test_executor_credentials_gate_blocks_post():
    # No credentials: execute refuses without ever calling post_margin_loan.
    fc = FakeClient(creds=False)
    fc.post_response = _resp(200, {"tranId": 1})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 1000)
    r = exe.execute(_task(), _attempt())
    assert r.result_category == D.RESULT_EXECUTION_DISABLED
    assert fc.posts == []  # zero signed POST


def test_executor_2xx_known_code_is_unknown_one_post_only():
    # Service-level zero-second-POST regression (review-2 P1): a 2xx body
    # carrying a known rejection code is classified unknown (not success, not
    # known_rejection), and exactly ONE POST leaves the executor — the executor
    # never re-POSTs on its own after an ambiguous response. Under
    # DEC-2026-08-21 the task itself stays in rotation; that is asserted at the
    # store/scheduler level (test_borrow_scheduler.py
    # test_unknown_keeps_its_task_in_the_rotation).
    fc = FakeClient()
    fc.post_response = _resp(200, {"code": -51006})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 1000)
    r = exe.execute(_task(), _attempt())
    assert r.result_category == D.RESULT_UNKNOWN
    assert r.tran_id is None
    assert fc.posts == [("BTC", "1.5", 1000)]  # exactly one POST, no self-retry
