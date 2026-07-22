"""Tests for the typed live borrow executor (Boundary C §5).

No network: the PM borrow client is a fake that returns scripted
:class:`BorrowHttpResponse` objects. Covers the POST classification matrix
(§5.1), ``tranId`` arbitrary-precision normalization, exact-Decimal principal
matching, the credentials self-defense gate, and reconciliation prove/ambiguity
(unique / zero / multiple / cross-task / rate-limited).
"""
from __future__ import annotations

import pytest
from decimal import Decimal

from backend.borrow_tasks import domain as D
from backend.services.live_borrow_executor import (
    LiveBorrowExecutor,
    _decimal_equal,
    _normalize_tran_id,
    classify_post_response,
    classify_reconcile_response,
)
from backend.services.portfolio_margin_borrow_client import (
    BorrowHttpResponse,
    PortfolioMarginBorrowClient,
)


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
    # the task is not blocked for reconciliation — only 2xx/5xx/transport stay unknown.
    r = classify_post_response(_resp(400, {"code": -2014}))
    assert r.result_category == D.RESULT_KNOWN_REJECTION
    assert r.business_code == "-2014"
    for raw in (-51007, 51007, 51099):
        r2 = classify_post_response(_resp(400, {"code": raw}))
        assert r2.result_category == D.RESULT_KNOWN_REJECTION
        assert r2.business_code == str(raw)


def test_classify_http_401_2015_is_known_rejection_not_blocked():
    # Live DEXE: unlisted_http_401 / -2015 must not become unknown (待对账).
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
    # closed to unknown and blocks the task for reconciliation instead of
    # returning to rotation and authorizing a second borrow POST.
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
    # Scheme C: timeout / connection_error must not enter unknown/recon block.
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
# Decimal principal matching (exact; no float path)
# ---------------------------------------------------------------------------
def test_decimal_equal_exact_and_scale():
    assert _decimal_equal("1.5", "1.5") is True
    assert _decimal_equal("1.50", "1.5") is True  # Decimal equality ignores scale
    assert _decimal_equal("0.0001", "0.0001") is True
    assert _decimal_equal("1.5", "1.6") is False
    assert _decimal_equal(None, "1.5") is False
    assert _decimal_equal("not-a-number", "1.5") is False


# ---------------------------------------------------------------------------
# LiveBorrowExecutor over a fake client
# ---------------------------------------------------------------------------
class FakeClient:
    def __init__(self, *, creds=True):
        self._creds = creds
        self.post_response = None
        self.get_response = None
        self.posts = []
        self.gets = []

    @property
    def credentials_present(self):
        return self._creds

    def post_margin_loan(self, asset, amount, *, timestamp_ms, recv_window_ms=None):
        self.posts.append((asset, amount, timestamp_ms))
        return self.post_response

    def fetch_loan_records(self, asset, *, timestamp_ms, **kw):
        self.gets.append((asset, kw))
        return self.get_response

    @staticmethod
    def records_from(resp):
        return PortfolioMarginBorrowClient.records_from(resp)


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
    # carrying a known rejection code is classified unknown (not
    # known_rejection), so exactly ONE POST leaves the executor and the task
    # blocks for reconciliation — it is never returned to rotation for a second
    # borrow POST after an ambiguous response.
    fc = FakeClient()
    fc.post_response = _resp(200, {"code": -51006})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 1000)
    r = exe.execute(_task(), _attempt())
    assert r.result_category == D.RESULT_UNKNOWN
    assert r.tran_id is None
    assert fc.posts == [("BTC", "1.5", 1000)]  # exactly one POST, then block


# ---------------------------------------------------------------------------
# Reconciliation (§5.3): prove / ambiguity / rate-limit
# ---------------------------------------------------------------------------
def test_reconcile_unique_confirmed_match_proves_success():
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "4242", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt(amount="1.5"))
    assert outcome.matched is True
    assert outcome.tran_id == "4242"


def test_reconcile_zero_records_not_matched():
    fc = FakeClient()
    fc.get_response = _resp(200, {"rows": [], "total": 0})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt())
    assert outcome.matched is False


def test_reconcile_multiple_confirmed_not_matched():
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [
            {"txId": "1", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500},
            {"txId": "2", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500},
        ],
        "total": 2,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_asset_mismatch_not_matched():
    # The executor's single-task matcher requires the row asset to equal the
    # task asset; a different-asset row never matches. (Durable cross-task
    # attribution between two real tasks lives in the store/service layer, not
    # here — the executor has no ledger access.)
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "1", "status": "CONFIRMED", "asset": "ETH", "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(asset="BTC"), _attempt(amount="1.5")).matched is False


def test_reconcile_principal_mismatch_not_matched():
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "1", "status": "CONFIRMED", "asset": "BTC", "principal": "1.6", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_non_confirmed_not_matched():
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "1", "status": "PENDING", "asset": "BTC", "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_rate_limited_get_surfaces_without_matching():
    fc = FakeClient()
    fc.get_response = _resp(429, {"code": -1003}, retry_after=90)
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt())
    assert outcome.matched is False
    assert outcome.rate_limited is True
    assert outcome.retry_after_seconds == Decimal("90")


def test_classify_reconcile_non_rate_limited_returns_none():
    assert classify_reconcile_response(_resp(200, {"rows": [], "total": 0})) is None
    assert classify_reconcile_response(_resp(None, None, transport_error="x")) is None


def test_reconcile_known_tran_id_uses_tx_id_param():
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "555", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    exe.reconcile(_task(), _attempt(amount="1.5", tran_id="555"))
    assert fc.gets[0][1]["tx_id"] == "555"


# ---------------------------------------------------------------------------
# Reconciliation pagination fail-closed + 418 manual re-arm (§5.1 / §5.3)
# ---------------------------------------------------------------------------
def test_reconcile_pagination_incomplete_not_matched():
    # One CONFIRMED row matches locally, but the envelope declares total=2 while
    # only one row was inspected -> cannot prove global uniqueness -> not matched.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "1", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500}],
        "total": 2,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_pagination_complete_with_one_match_proves_success():
    # total == len(rows) == 1 -> the single match is globally unique -> success.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "9", "status": "CONFIRMED", "asset": "BTC", "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt(amount="1.5"))
    assert outcome.matched is True
    assert outcome.tran_id == "9"


def test_reconcile_418_ban_carries_requires_rearm():
    # A reconciliation GET that observes a 418 ban must surface the manual-rearm
    # requirement so the store persists requires_rearm (no auto-resume).
    fc = FakeClient()
    fc.get_response = _resp(418, {})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt())
    assert outcome.matched is False
    assert outcome.rate_limited is True
    assert outcome.requires_rearm is True
    assert outcome.retry_after_seconds == Decimal("300")


def test_reconcile_429_rate_limited_does_not_require_rearm():
    # An ordinary 429 rate-limit surfaces without the 418 manual-rearm flag.
    fc = FakeClient()
    fc.get_response = _resp(429, {"code": -1003}, retry_after=90)
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt())
    assert outcome.rate_limited is True
    assert outcome.requires_rearm is False


def test_reconcile_responseless_window_endtime_capped_at_request_timestamp():
    # response-less unknown: endTime passed to the client must not be later than
    # the signed request timestamp, and the span must not exceed the 30-day cap.
    fc = FakeClient()
    fc.get_response = _resp(200, {"rows": [], "total": 0})
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 5_000_000)  # ts_ms == 5_000_000
    exe.reconcile(_task(), _attempt(amount="1.5", dispatched_us=1_000_000))
    kw = fc.gets[0][1]
    assert kw["end_ms"] == 5_000_000               # == signed request timestamp
    assert kw["end_ms"] - kw["start_ms"] <= 30 * 86_400 * 1_000  # span <= 30 days
    assert kw["start_ms"] >= 0


# ---------------------------------------------------------------------------
# Reconciliation fail-closed matching (bookkeeper BK-C-001 residual / §5.3)
# ---------------------------------------------------------------------------
def test_reconcile_missing_total_not_matched():
    # A unique matching row with NO declared total cannot prove global uniqueness.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "4242", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 1500}],
    })  # no "total"
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_bool_total_not_matched():
    # A boolean total is not a valid int64 total -> fail closed.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "4242", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 1500}],
        "total": True,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_total_below_row_count_not_matched():
    # total=0 while one row was returned -> inconsistent envelope -> fail closed.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "4242", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 1500}],
        "total": 0,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_known_tran_id_mismatch_not_matched():
    # Known tranId="555" but the response row says txId="999": the candidate is
    # NOT the posted transaction -> stay blocked.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "999", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5", tran_id="555")).matched is False


def test_reconcile_row_missing_timestamp_not_matched():
    # A row missing the documented timestamp field is contract-invalid -> the
    # whole read fails closed (no success proof from a malformed row).
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "4242", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5"}],  # no timestamp
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_malformed_row_not_silently_dropped():
    # One valid matching row plus one malformed row: the malformed member cannot
    # be filtered away to prove the valid one unique -> fail closed.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [
            {"txId": "4242", "status": "CONFIRMED", "asset": "BTC",
             "principal": "1.5", "timestamp": 1500},
            "junk",
        ],
        "total": 2,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False


def test_reconcile_responseless_candidate_timestamp_in_window_matches():
    # Response-less path: a candidate whose timestamp falls inside the dispatched
    # [startTime, endTime] window is accepted (dispatched_us=1s -> anchor 1000ms,
    # now=2000ms -> window [0, 2000]; timestamp 1500 is inside).
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "7", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 1500}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    outcome = exe.reconcile(_task(), _attempt(amount="1.5"))
    assert outcome.matched is True
    assert outcome.tran_id == "7"


def test_reconcile_responseless_candidate_timestamp_outside_window_not_matched():
    # Same window [0, 2000] but the candidate timestamp (3000) is later than the
    # dispatched endTime -> it cannot be this attempt's loan -> stay blocked.
    fc = FakeClient()
    fc.get_response = _resp(200, {
        "rows": [{"txId": "7", "status": "CONFIRMED", "asset": "BTC",
                  "principal": "1.5", "timestamp": 3000}],
        "total": 1,
    })
    exe = LiveBorrowExecutor(fc, now_ms=lambda: 2000)
    assert exe.reconcile(_task(), _attempt(amount="1.5")).matched is False
