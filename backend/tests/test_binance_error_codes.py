"""Display-only Binance business-code map (borrow UX)."""
from __future__ import annotations

from backend.borrow_tasks.binance_error_codes import (
    business_code_display_fields,
    lookup_binance_error_code,
)
from backend.borrow_tasks.service import attempt_to_doc, task_to_doc


def test_lookup_accepts_either_sign():
    for raw in ("-2015", "2015", "+2015"):
        hit = lookup_binance_error_code(raw)
        assert hit is not None
        assert hit["name"] == "REJECTED_MBX_KEY"
        assert "API-key" in hit["message_en"] or "API Key" in hit["message_zh"]


def test_lookup_pm_pool_empty_51061():
    hit = lookup_binance_error_code("51061")
    assert hit["name"] == "INSUFFICIENT_LOANABLE_ASSET"
    assert "loanable" in hit["message_en"].lower() or "可贷" in hit["message_zh"]


def test_lookup_unknown_returns_none():
    assert lookup_binance_error_code("99999") is None
    assert lookup_binance_error_code(None) is None
    assert lookup_binance_error_code("abc") is None


def test_attempt_to_doc_includes_display_fields():
    doc = attempt_to_doc({
        "id": 1,
        "task_id": "t",
        "asset": "DEXE",
        "sequence": 1,
        "outcome": "resolved",
        "result_category": "unknown",
        "business_code": "-2015",
        "reason": "unlisted_http_401",
        "http_status": 401,
        "tran_id": None,
        "requested_amount": "1",
        "scheduled_at_us": 1,
        "dispatched_at_us": 2,
        "finished_at_us": 3,
        "latency_ms": 1,
        "effective_gap_us": None,
    })
    assert doc["business_code"] == "-2015"
    assert doc["business_code_name"] == "REJECTED_MBX_KEY"
    assert doc["business_code_message_zh"]
    assert "权限" in doc["business_code_message_zh"] or "API" in doc["business_code_message"]


def test_latest_result_on_task_includes_display_fields():
    doc = task_to_doc({
        "id": "t",
        "asset": "BTC",
        "amount_per_attempt": "1",
        "success_target": 1,
        "success_count": 0,
        "status": "borrowing",
        "version": 1,
        "live_authorized": 1,
        "unresolved_attempt_id": None,
        "latest_result_category": "known_rejection",
        "latest_result_business_code": "51061",
        "latest_result_reason": "known_rejection:51061",
        "latest_result_tran_id": None,
        "latest_result_finished_at_us": 10,
        "created_at_us": 1,
        "updated_at_us": 10,
    })
    lr = doc["latest_result"]
    assert lr["business_code_name"] == "INSUFFICIENT_LOANABLE_ASSET"
    assert lr["business_code_message_zh"]


def test_display_fields_null_when_unmapped():
    fields = business_code_display_fields("424242")
    assert fields == {
        "business_code_name": None,
        "business_code_message": None,
        "business_code_message_zh": None,
    }
