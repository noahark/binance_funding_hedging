"""Service-layer tests for backend.ledger_flow.service (design §13 / §15).

Offline: a stub client exposing the two single-page fetchers, an injectable
millisecond clock, and a temp SQLite store. Covers run_once (backfill /
scheduled overlap / partial failure / single-flight / truncation F6(b) /
downtime gap), the §13.2 response assembly (populated + empty state §13.2
rule 13), the §15.4 delta baseline (success classification, manual excluded,
<2 success → incomplete), consecutive_failure_count, and the POST refresh
409/429/200 branches.
"""
from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import pytest

from backend.ledger_flow import domain
from backend.ledger_flow.service import LedgerFlowService, _beijing_day_start_ms
from backend.ledger_flow.store import LedgerStore
from backend.services.private_client import PrivateEndpointError

NOW = 1785798060000


# --------------------------------------------------------------------------- #
# stubs / helpers
# --------------------------------------------------------------------------- #
class StubClient:
    """Exposes only the two flow-log fetchers; page-indexed seeding."""

    def __init__(self):
        self.enabled = True
        self.interest_pages = []      # list of {total, rows}; page i -> index i-1
        self.income_pages = []        # list of list-of-rows
        self.interest_fn = None       # callable(current) -> page (overrides pages)
        self.income_fn = None
        self.interest_raise = None    # (page, exc)
        self.income_raise = None
        # cross-margin capital-flow (single page, no fromId paging)
        self.capital_pages = []       # list of list-of-raw-rows; call i -> index i
        self.capital_fn = None        # callable(start_time, end_time, limit) -> page
        self.capital_raise = None     # exc (single page)
        self._capital_seen = []       # records (start, end, limit) per call

    def fetch_interest_history_page(self, *, start_time, end_time, current, size):
        if self.interest_raise and current == self.interest_raise[0]:
            raise self.interest_raise[1]
        if self.interest_fn is not None:
            return self.interest_fn(current)
        idx = current - 1
        return self.interest_pages[idx] if idx < len(self.interest_pages) else {"total": 0, "rows": []}

    def fetch_um_income_page(self, *, start_time, end_time, page, limit):
        if self.income_raise and page == self.income_raise[0]:
            raise self.income_raise[1]
        if self.income_fn is not None:
            return self.income_fn(page)
        idx = page - 1
        return self.income_pages[idx] if idx < len(self.income_pages) else []

    def fetch_capital_flow_page(self, *, start_time, end_time, limit):
        if self.capital_raise is not None:
            raise self.capital_raise
        if self.capital_fn is not None:
            return self.capital_fn(start_time, end_time, limit)
        idx = len(self._capital_seen)
        self._capital_seen.append((start_time, end_time, limit))
        return self.capital_pages[idx] if idx < len(self.capital_pages) else []


def _svc(tmp_path, client=None, now=NOW):
    store = LedgerStore(os.path.join(tmp_path, "l.sqlite3"))
    clock = {"now": now}
    svc = LedgerFlowService(store, client or StubClient(), now_ms=lambda: clock["now"])
    svc._set_now = lambda v: clock.__setitem__("now", v)
    svc._store = store
    return svc


def _irow(tx, ms, asset="HOME", interest="0.1"):
    return {"tx_id": str(tx), "accrued_at_ms": ms, "asset": asset,
            "raw_asset": asset, "principal": "1.0", "interest": interest,
            "interest_rate": "0.01", "type": "PERIODIC", "isolated_symbol": None}


def _urow(tran, ms, itype="FUNDING_FEE", income="0.1", symbol="MUUSDT", asset="USDT"):
    return {"tran_id": str(tran), "income_type": itype, "time_ms": ms,
            "symbol": symbol, "income": income, "asset": asset,
            "info": itype, "trade_id": None}


def _run(store, **over):
    base = dict(kind="scheduled", started_at_ms=NOW, finished_at_ms=NOW,
                window_start_ms=0, window_end_ms=NOW,
                interest_status="ok", interest_error=None,
                interest_fetched_row_count=1, interest_new_row_count=1,
                income_status="ok", income_error=None,
                income_fetched_row_count=1, income_new_row_count=1,
                truncated=False)
    base.update(over)
    return store.insert_run(base)


# --------------------------------------------------------------------------- #
# run_once: backfill / scheduled overlap / partial failure / single-flight
# --------------------------------------------------------------------------- #
def test_backfill_first_run_covers_1d(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 1, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.1"}]}]
    client.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                             "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                             "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    assert out["interest_new"] == 1 and out["income_new"] == 1
    cov = svc._store.get_coverage()
    # first-ever → 1-day backfill window on both sources, end = now.
    assert cov["interest_start_ms"] == NOW - 86400 * 1000
    assert cov["interest_end_ms"] == NOW
    assert cov["income_start_ms"] == NOW - 86400 * 1000
    assert cov["income_end_ms"] == NOW


def test_scheduled_3h_overlap_is_idempotent(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 1, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.1"}]}]
    client.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                             "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                             "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    svc._set_now(NOW + 4 * 3600 * 1000)  # next hour, 3h overlap re-pulls same rows
    out = svc.run_once("scheduled")
    assert out["interest_new"] == 0 and out["income_new"] == 0  # idempotent, no dup
    assert len(svc._store.query_interest_rows(0, 10 ** 14)) == 1


def test_partial_failure_interest_error_income_ok(tmp_path):
    client = StubClient()
    client.interest_raise = (1, PrivateEndpointError(
        "/sapi/v1/margin/interestHistory", 500, "HTTP 500"))
    client.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                             "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                             "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("scheduled")
    run = out["run"]
    assert run["interest_status"] == "error"
    assert run["interest_error"] == "interest_history_failed"
    assert run["income_status"] == "ok"
    # interest zero rows + coverage not advanced; income committed + coverage advanced.
    assert svc._store.query_interest_rows(0, 10 ** 14) == []
    cov = svc._store.get_coverage()
    assert cov["interest_start_ms"] is None and cov["interest_end_ms"] is None
    assert cov["income_end_ms"] == NOW
    assert len(svc._store.query_income_rows(0, 10 ** 14)) == 1


def test_rate_limited_fetch_classified_as_rate_limited(tmp_path):
    client = StubClient()
    client.interest_raise = (1, PrivateEndpointError(
        "/sapi/v1/margin/interestHistory", 429, "HTTP 429"))
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("scheduled")
    assert out["run"]["interest_error"] == "rate_limited"


def test_run_once_single_flight_returns_none_when_busy(tmp_path):
    client = StubClient()
    svc = _svc(tmp_path, client)
    svc._flight_lock.acquire()  # pretend another run is in flight
    try:
        assert svc.run_once("scheduled") is None
    finally:
        svc._flight_lock.release()


# --------------------------------------------------------------------------- #
# truncation F6(b): left records gap, right self-heals
# --------------------------------------------------------------------------- #
def test_truncation_interest_left_records_gap(tmp_path):
    client = StubClient()
    # always-full page -> interest loop hits the 40-page cap (truncated).
    client.interest_fn = lambda p: {"total": 99999, "rows": [
        {"txId": p * 1000 + i, "interestAccuredTime": NOW - p * 1000, "asset": "HOME",
         "interest": "0.1"} for i in range(100)]}
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    assert out["run"]["truncated"] == 1
    cov = svc._store.get_coverage()
    ws = NOW - 86400 * 1000
    assert cov["interest_end_ms"] == NOW            # left end advances to window_end
    assert cov["interest_start_ms"] != ws           # start NOT moved to window_start
    gap = [g for g in cov["gaps"] if g["source"] == "interest"]
    assert gap and gap[0]["start_ms"] == ws and gap[0]["end_ms"] == cov["interest_start_ms"]


def test_truncation_income_right_no_gap_end_newest(tmp_path):
    client = StubClient()
    # always-full page -> income loop hits the 10-page cap (truncated).
    client.income_fn = lambda p: [{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                                   "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                                   "time": NOW - (10 - p) * 1000 - 60000, "tranId": p * 1000 + i,
                                   "tradeId": ""} for i in range(1000)]
    client.interest_pages = [{"total": 0, "rows": []}]
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    assert out["run"]["truncated"] == 1
    cov = svc._store.get_coverage()
    # right end advances only to newest_fetched, NOT window_end; no gap recorded.
    assert cov["income_end_ms"] < NOW
    assert all(g["source"] != "income" for g in cov["gaps"])


def test_downtime_gap_over_30d_recorded(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 0, "rows": []}]
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    # seed stale coverage end > 30d ago.
    svc._store.commit_interest(rows=[], run_id=_run(svc._store), first_seen_at_ms=NOW,
                               coverage_start_ms=10, coverage_end_ms=NOW - 31 * 86400 * 1000)
    svc.run_once("scheduled")
    cov = svc._store.get_coverage()
    gap = [g for g in cov["gaps"] if g["source"] == "interest"]
    assert gap  # downtime > 30d recorded, not silently left as a hole


# --------------------------------------------------------------------------- #
# delta baseline (§15.4 / F3) + consecutive_failure_count (§13.2 rule 10 / F2)
# --------------------------------------------------------------------------- #
def test_delta_baseline_second_success_and_manual_excluded(tmp_path):
    svc = _svc(tmp_path)
    s = svc._store
    r1 = _run(s, finished_at_ms=1000)               # success #1 (older)
    r2 = _run(s, finished_at_ms=2000)               # success #2 (most recent)
    _run(s, finished_at_ms=3000, kind="manual")     # manual: excluded from baseline
    # rows: one before baseline (excluded), one after (in delta), manual's after.
    s.commit_interest(rows=[_irow("A", 500)], run_id=r1, first_seen_at_ms=500,
                     coverage_start_ms=0, coverage_end_ms=1000)
    s.commit_interest(rows=[_irow("B", 1500)], run_id=r2, first_seen_at_ms=1500,
                     coverage_start_ms=0, coverage_end_ms=2000)
    s.commit_interest(rows=[_irow("C", 2900)], run_id=3, first_seen_at_ms=2900,
                     coverage_start_ms=None, coverage_end_ms=None)
    resp = svc.get_flow_log(0, NOW)
    assert resp["delta"]["complete"] is True
    assert resp["delta"]["baseline_ms"] == 1000      # 2nd-most-recent SUCCESS (manual excluded)
    assets = resp["delta"]["interest_by_asset"]
    assert sum(g["row_count"] for g in assets) == 2  # B + C (first_seen > 1000), not A


def test_delta_incomplete_under_two_success(tmp_path):
    svc = _svc(tmp_path)
    _run(svc._store, finished_at_ms=1000)            # only one success
    resp = svc.get_flow_log(0, NOW)
    assert resp["delta"]["complete"] is False
    assert resp["delta"]["baseline_ms"] is None
    assert resp["delta"]["interest_by_asset"] == []


def test_consecutive_failure_count(tmp_path):
    svc = _svc(tmp_path)
    s = svc._store
    _run(s, finished_at_ms=1000, interest_status="ok", income_status="ok")
    _run(s, finished_at_ms=2000, interest_status="error", income_status="ok")
    _run(s, finished_at_ms=3000, income_status="error", interest_status="ok")
    resp = svc.get_flow_log(0, NOW)
    # most recent two are errors, then an ok stops the run -> count 2.
    assert resp["last_run"]["consecutive_failure_count"] == 2


# --------------------------------------------------------------------------- #
# coverage.complete + pending_tail (§13.2 rule 7 / F4)
# --------------------------------------------------------------------------- #
def test_coverage_complete_pending_tail_and_gap_in_window(tmp_path):
    svc = _svc(tmp_path)
    s = svc._store
    _run(s)
    s.commit_interest(rows=[_irow("A", 1000)], run_id=1, first_seen_at_ms=1000,
                     coverage_start_ms=1000, coverage_end_ms=5000,
                     new_gaps=[{"source": "interest", "start_ms": 2000, "end_ms": 3000}])
    s.commit_income(rows=[_urow("B", 1000)], run_id=1, first_seen_at_ms=1000,
                   coverage_start_ms=1000, coverage_end_ms=5000)
    # window after the gap, within coverage -> complete; tail = end - cov_end.
    resp = svc.get_flow_log(3500, 6000)
    cov = resp["coverage"]
    assert cov["complete"] is True
    assert cov["pending_tail_ms"] == 1000            # 6000 - 5000
    assert cov["by_source"]["interest"] == {"start_ms": 1000, "end_ms": 5000}
    assert cov["gaps"] == []                         # gap [2000,3000] does not intersect
    # window that intersects the recorded gap -> not complete.
    resp2 = svc.get_flow_log(2500, 6000)
    assert resp2["coverage"]["complete"] is False
    assert any(g["source"] == "interest" for g in resp2["coverage"]["gaps"])


def test_window_fully_inside_gap_is_not_complete(tmp_path):
    svc = _svc(tmp_path)
    s = svc._store
    _run(s)
    s.commit_interest(rows=[_irow("A", 1000)], run_id=1, first_seen_at_ms=1000,
                     coverage_start_ms=1000, coverage_end_ms=5000,
                     new_gaps=[{"source": "interest", "start_ms": 2000, "end_ms": 4000}])
    s.commit_income(rows=[_urow("B", 1000)], run_id=1, first_seen_at_ms=1000,
                   coverage_start_ms=1000, coverage_end_ms=5000)
    resp = svc.get_flow_log(2500, 3500)              # fully inside the gap
    assert resp["coverage"]["complete"] is False     # never "no records" inside a hole


# --------------------------------------------------------------------------- #
# empty state (§13.2 rule 13) + today Beijing day boundary
# --------------------------------------------------------------------------- #
def test_get_flow_log_empty_state_shape(tmp_path):
    svc = _svc(tmp_path)
    resp = svc.get_flow_log(1, NOW)
    assert resp["schema_version"] == "private-ledger/v2"
    assert resp["scheduler_enabled"] is False
    assert resp["last_run"] is None
    assert resp["coverage"] == {
        "start_ms": None, "end_ms": None, "complete": False, "pending_tail_ms": None,
        "by_source": {"interest": None, "income": None, "capital_flow": None}, "gaps": []}
    assert resp["delta"]["complete"] is False and resp["delta"]["baseline_ms"] is None
    assert resp["interest"]["rows"] == [] and resp["interest"]["row_count"] == 0
    assert resp["um_income"]["rows"] == [] and resp["um_income"]["row_count"] == 0
    assert resp["interest"]["row_limit_applied"] is False
    # capital block: empty-state (NOT an error state); last_run null (never pulled).
    assert resp["capital_flow"]["rows"] == [] and resp["capital_flow"]["row_count"] == 0
    assert resp["capital_flow"]["last_run"] is None


def test_today_attribution_by_beijing_day(tmp_path):
    svc = _svc(tmp_path, now=NOW)
    s = svc._store
    _run(s)
    day_start = _beijing_day_start_ms(NOW)
    # one row yesterday (Beijing), one today — distinct assets so grouping shows them.
    s.commit_interest(rows=[_irow("Y", day_start - 1, asset="YESTERDAY")], run_id=1,
                     first_seen_at_ms=1000, coverage_start_ms=0, coverage_end_ms=NOW)
    s.commit_interest(rows=[_irow("T", day_start + 1, asset="TODAY")], run_id=1,
                     first_seen_at_ms=1000, coverage_start_ms=0, coverage_end_ms=NOW)
    resp = svc.get_flow_log(0, NOW)
    assert resp["today"]["day_start_ms"] == day_start
    assets = {g["asset"] for g in resp["today"]["interest_by_asset"]}
    assert "TODAY" in assets and "YESTERDAY" not in assets     # only today's row


def test_row_limit_applied_and_full_summary(tmp_path):
    svc = _svc(tmp_path)
    s = svc._store
    _run(s)
    rows = [_irow(i, 1000 + i) for i in range(600)]
    s.commit_interest(rows=rows, run_id=1, first_seen_at_ms=1000,
                     coverage_start_ms=0, coverage_end_ms=2000)
    resp = svc.get_flow_log(0, 10 ** 14)
    assert resp["interest"]["row_count"] == 600           # full count
    assert resp["interest"]["row_limit_applied"] is True
    assert len(resp["interest"]["rows"]) == 500           # display slice
    assert resp["interest"]["summary_by_asset"][0]["row_count"] == 600  # summary on full


# --------------------------------------------------------------------------- #
# POST refresh (§13.4): 409 / 429 / 200
# --------------------------------------------------------------------------- #
def test_trigger_refresh_409_when_disabled(tmp_path):
    client = StubClient()
    client.enabled = False
    svc = _svc(tmp_path, client)
    status, payload = svc.trigger_refresh()
    assert status == 409 and payload["error"] == "private_channel_disabled"


def test_trigger_refresh_429_when_busy(tmp_path):
    svc = _svc(tmp_path)
    svc._flight_lock.acquire()
    try:
        status, payload = svc.trigger_refresh()
        assert status == 429 and payload["error"] == "flow_log_busy"
    finally:
        svc._flight_lock.release()


def test_trigger_refresh_200_manual_advances_coverage(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 1, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.1"}]}]
    client.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                             "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                             "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]
    svc = _svc(tmp_path, client)
    status, payload = svc.trigger_refresh()
    assert status == 200
    assert payload["kind"] == "manual"
    assert payload["interest_new_row_count"] == 1
    # manual run advances coverage (F6(a): data-equivalent to scheduled).
    assert svc._store.get_coverage()["interest_end_ms"] == NOW


def test_trigger_refresh_error_response_has_no_binance_body(tmp_path):
    client = StubClient()
    client.interest_raise = (1, PrivateEndpointError(
        "/sapi/v1/margin/interestHistory", 500, "sensitive-upstream-detail"))
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    status, payload = svc.trigger_refresh()
    assert status == 200  # the run completes (one pane errored); refresh itself succeeded
    blob = str(payload)
    assert "sensitive-upstream-detail" not in blob
    assert payload["interest_error"] == "interest_history_failed"


# --------------------------------------------------------------------------- #
# 持仓周期汇总（功能二，stage3 §3.1）：sum_funding_by_symbol / sum_interest_by_asset
# / coverage_for_window —— 纯读汇总，不触发拉取
# --------------------------------------------------------------------------- #
def test_sum_funding_by_symbol_filters_window_type_symbol(tmp_path):
    client = StubClient()
    client.income_pages = [[
        {"symbol": "MUUSDT", "incomeType": "FUNDING_FEE", "income": "0.1",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 2000, "tranId": 1, "tradeId": ""},
        {"symbol": "MUUSDT", "incomeType": "FUNDING_FEE", "income": "0.2",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 1000, "tranId": 2, "tradeId": ""},
        {"symbol": "MUUSDT", "incomeType": "COMMISSION", "income": "5",
         "asset": "USDT", "info": "COMMISSION", "time": NOW - 1000, "tranId": 3, "tradeId": ""},
        {"symbol": "OTHERUSDT", "incomeType": "FUNDING_FEE", "income": "9",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 1000, "tranId": 4, "tradeId": ""},
        {"symbol": "MUUSDT", "incomeType": "FUNDING_FEE", "income": "7",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 30000, "tranId": 5, "tradeId": ""},
    ]]
    client.interest_pages = [{"total": 0, "rows": []}]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")  # 30 天窗口全落库；coverage 建立
    # 窗口 [NOW-2000, NOW-1000]：MUUSDT FUNDING_FEE = 0.1+0.2 = 0.3
    # （COMMISSION 类型、OTHERUSDT symbol、窗口外 NOW-30000 行均排除）
    assert svc.sum_funding_by_symbol("MUUSDT", NOW - 2000, NOW - 1000) == "0.3"
    assert svc.sum_funding_by_symbol("OTHERUSDT", NOW - 2000, NOW - 1000) == "9"
    assert svc.sum_funding_by_symbol("NOPEUSDT", NOW - 2000, NOW - 1000) == "0"  # 无行 → 真零


def test_sum_funding_by_symbol_unparseable_returns_none(tmp_path):
    client = StubClient()
    client.income_pages = [[
        {"symbol": "MUUSDT", "incomeType": "FUNDING_FEE", "income": "0.1",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 1000, "tranId": 1, "tradeId": ""},
        {"symbol": "MUUSDT", "incomeType": "FUNDING_FEE", "income": "oops",
         "asset": "USDT", "info": "FUNDING_FEE", "time": NOW - 1000, "tranId": 2, "tradeId": ""},
    ]]
    client.interest_pages = [{"total": 0, "rows": []}]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    # 任一行不可解析 → None（绝不部分相加 0.1）
    assert svc.sum_funding_by_symbol("MUUSDT", NOW - 2000, NOW) is None


def test_sum_interest_by_asset_filters_window_and_asset(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 4, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 2000, "asset": "HOME", "interest": "0.1"},
        {"txId": 2, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.2"},
        {"txId": 3, "interestAccuredTime": NOW - 1000, "asset": "OTHER", "interest": "9"},
        {"txId": 4, "interestAccuredTime": NOW - 30000, "asset": "HOME", "interest": "7"},
    ]}]
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    assert svc.sum_interest_by_asset("HOME", NOW - 2000, NOW - 1000) == "0.3"
    assert svc.sum_interest_by_asset("OTHER", NOW - 2000, NOW - 1000) == "9"
    assert svc.sum_interest_by_asset("MISSING", NOW - 2000, NOW - 1000) == "0"


def test_sum_interest_by_asset_unparseable_returns_none(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 2, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.1"},
        {"txId": 2, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "bad"},
    ]}]
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    assert svc.sum_interest_by_asset("HOME", NOW - 2000, NOW) is None


def test_coverage_for_window_wraps_gap_aware_judgement(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 0, "rows": []}]
    client.income_pages = [[]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")  # 双源 coverage 建立（起点 = NOW-30d）
    cov = svc.coverage_for_window(NOW - 1000, NOW)
    assert cov["complete"] is True
    assert cov["start_ms"] is not None and cov["end_ms"] == NOW
    # 窗口起点早于 coverage 起点 → 不完整（诚实降级，绝不把未覆盖窗口当真值）
    early = svc.coverage_for_window(NOW - 30 * 24 * 3600 * 1000 - 3600_000, NOW)
    assert early["complete"] is False


# --------------------------------------------------------------------------- #
# cross-margin capital-flow (stage 2026-08-10) — isolated third source
# --------------------------------------------------------------------------- #
_D = 24 * 60 * 60 * 1000
_3H = 3 * 60 * 60 * 1000


def _crow(i, ms, tran_id=399260348988, ftype="TRANSFER", asset="USDT", amount="10"):
    return {"id": i, "tranId": tran_id, "timestamp": ms, "asset": asset,
            "type": ftype, "amount": amount}


def _seed_two(client):
    client.interest_pages = [{"total": 0, "rows": []}]
    client.income_pages = [[]]


def test_capital_first_run_window_is_one_day(tmp_path):
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[_crow(159745763323, NOW - 1000)]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    # first-ever capital → [now-1d, now], single page, limit 1000.
    assert client._capital_seen == [(NOW - _D, NOW, 1000)]
    assert out["capital"] == {"status": "ok", "error": None,
                              "fetched_row_count": 1, "new_row_count": 1,
                              "possibly_incomplete": False}
    state = svc._store.get_capital_flow_state()
    assert state["start_ms"] == NOW - _D and state["end_ms"] == NOW
    assert state["last_run"]["possibly_incomplete"] is False


def test_capital_incremental_window_3h_overlap(tmp_path):
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[], []]  # two scheduled pulls, both empty
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")          # first call window = [now-1d, now], end=NOW
    later = NOW + 4 * 3600 * 1000
    svc._set_now(later)
    svc.run_once("scheduled")         # second call window = [end-3h, later]
    assert client._capital_seen[1] == (NOW - _3H, later, 1000)


def test_capital_full_page_marks_possibly_incomplete(tmp_path):
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[_crow(i, NOW - i) for i in range(1000)]]
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    assert out["capital"]["possibly_incomplete"] is True  # == limit
    assert out["capital"]["new_row_count"] == 1000
    # coverage still advances to now (full page is a success, not a failure):
    assert svc._store.get_capital_flow_state()["end_ms"] == NOW


def test_capital_failure_isolated_and_does_not_advance_end(tmp_path):
    client = StubClient()
    client.interest_pages = [{"total": 1, "rows": [
        {"txId": 1, "interestAccuredTime": NOW - 1000, "asset": "HOME", "interest": "0.1"}]}]
    client.income_pages = [[{"symbol": "MUUSDT", "incomeType": "FUNDING_FEE",
                             "income": "0.1", "asset": "USDT", "info": "FUNDING_FEE",
                             "time": NOW - 1000, "tranId": 9, "tradeId": ""}]]
    client.capital_raise = PrivateEndpointError(
        "/sapi/v1/margin/capital-flow", 500, "HTTP 500")
    svc = _svc(tmp_path, client)
    out = svc.run_once("backfill")
    # capital failed, but interest/income succeeded and coverage advanced:
    assert out["capital"]["status"] == "error"
    assert out["interest_new"] == 1 and out["income_new"] == 1
    cov = svc._store.get_coverage()
    assert cov["interest_end_ms"] == NOW and cov["income_end_ms"] == NOW
    cstate = svc._store.get_capital_flow_state()
    assert cstate["start_ms"] is None and cstate["end_ms"] is None  # NOT advanced
    assert cstate["last_run"]["error"] == "capital_flow_failed"


def test_capital_never_succeeded_leaves_coverage_for_window_untouched(tmp_path):
    # P0-1: capital (never succeeded) must not change coverage_for_window's
    # aggregate vs a capital-less baseline. coverage_for_window is the server.py
    # consumer that gates hedging net-PnL display.
    client = StubClient()
    _seed_two(client)
    client.capital_raise = PrivateEndpointError("/sapi/v1/margin/capital-flow", 500, "x")
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    cov = svc.coverage_for_window(NOW - 1000, NOW)
    assert set(cov.keys()) == {"start_ms", "end_ms", "complete",
                               "pending_tail_ms", "by_source", "gaps"}
    assert set(cov["by_source"].keys()) == {"interest", "income"}  # no capital here
    assert cov["complete"] is True


def test_capital_succeeding_does_not_shrink_coverage_aggregate(tmp_path):
    # P0-1: capital coverage is display-only and must not shrink the two-source
    # aggregate, even when it begins later.
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[_crow(1, NOW - 1000)]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    assert svc._store.get_capital_flow_state()["start_ms"] == NOW - _D  # capital start
    run_id = _run(svc._store)
    for commit in (svc._store.commit_interest, svc._store.commit_income):
        commit(rows=[], run_id=run_id, first_seen_at_ms=NOW,
               coverage_start_ms=NOW - 5 * _D, coverage_end_ms=NOW)
    payload = svc.get_flow_log(NOW - 5 * _D, NOW)
    # capital present in by_source (display-only) but the aggregate start stays
    # at the two-source 5d floor:
    assert payload["coverage"]["by_source"]["capital_flow"] == {
        "start_ms": NOW - _D, "end_ms": NOW}
    assert payload["coverage"]["start_ms"] == NOW - 5 * _D
    assert payload["coverage"]["complete"] is True


def test_flow_log_capital_block_shape_and_schema_not_bumped(tmp_path):
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[_crow(159745763323, NOW - 1000)]]
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    payload = svc.get_flow_log(NOW - _D, NOW)
    assert payload["schema_version"] == "private-ledger/v2"   # NOT bumped
    cap = payload["capital_flow"]
    assert cap["row_count"] == 1
    assert cap["rows"][0] == {"id": "159745763323", "tran_id": "399260348988",
                              "time_ms": NOW - 1000, "asset": "USDT",
                              "flow_type": "TRANSFER", "amount": "10"}
    assert cap["last_run"]["status"] == "ok"


def test_flow_log_capital_empty_state_when_never_pulled(tmp_path):
    # Never-run store: capital_flow block present with empty rows + null last_run
    # (empty-state, NOT an error state). schema_version still v2.
    client = StubClient()
    _seed_two(client)
    client.capital_pages = [[]]  # first pull empty -> end advances, but block ok
    svc = _svc(tmp_path, client)
    svc.run_once("backfill")
    payload = svc.get_flow_log(NOW - _D, NOW)
    assert payload["capital_flow"]["row_count"] == 0
    assert payload["capital_flow"]["rows"] == []
    assert payload["coverage"]["by_source"]["capital_flow"] == {
        "start_ms": NOW - _D, "end_ms": NOW}


# --------------------------------------------------------------------------- #
# 利息折 U 合计（阶段 2026-08-28-repaid-interest-price-v1，T5/T7）
# --------------------------------------------------------------------------- #

_HOUR = 3_600_000


def _seed_interest(svc, rows):
    run_id = _run(svc._store)  # insert_run 返回 run id
    svc._store.commit_interest(
        rows=rows, run_id=run_id, first_seen_at_ms=NOW,
        coverage_start_ms=0, coverage_end_ms=NOW)


def _repay(crid, *, amount="0", status="succeeded", update_time=None,
           updated_at_us=None, price="5"):
    rec = {
        "client_request_id": crid, "asset": "HOME", "amount": amount,
        "repay_asset": "USDT", "status": status, "repaid_amount": None,
        "update_time": update_time, "error_code": None, "error_message": None,
        "repay_price_usdt": price,
        "repay_price_source": "snapshot_spot_bid_at_capture" if price is not None else None,
        "updated_at_us": updated_at_us,
    }
    return rec


def test_sum_interest_usdt_matches_pnl_series_exactly(tmp_path):
    """T7：同一 (interest_rows, repay_records, price_map) 下，持仓视图的
    sum_interest_usdt_by_asset 与曲线 build_pnl_series 的利息折算逐位相等。"""
    t0 = NOW - 10 * _HOUR
    rows = [
        _irow("t1", t0, asset="HOME", interest="0.5"),                # 终态前 → 存储价
        _irow("t2", t0 + _HOUR, asset="HOME", interest="0.25"),       # 终态后 re-borrow → 当前价
    ]
    svc = _svc(tmp_path)
    _seed_interest(svc, rows)
    repays = [_repay("a", update_time=str(t0 + 1000), price="2")]
    price_map = {"HOMEUSDT": "3"}
    # 持仓视图消费者
    svc_value = svc.sum_interest_usdt_by_asset("HOME", t0, NOW, price_map, repays)
    assert svc_value == "1.75"  # 0.5×2 + 0.25×3
    # 曲线消费者（同一 domain 权威）
    series = domain.build_pnl_series(
        interest_rows=svc._store.query_interest_rows(t0, NOW, limit=None),
        income_rows=[{"time_ms": t0, "income_type": "FUNDING_FEE",
                      "asset": "USDT", "income": "0"}],
        capital_rows=[], close_logs=[], open_cycle_fills=[],
        repay_records=repays, price_map=price_map,
        start_ms=t0, end_ms=NOW, bucket_ms=_HOUR)
    assert series["unpriced_assets"] == []
    assert Decimal(series["totals"]["interest"]) == -Decimal(svc_value)


def test_sum_interest_usdt_fail_closed_on_missing_stored_price(tmp_path):
    """T5 service 侧：终态行缺存储价 → 整体 None（绝不部分相加）。"""
    t0 = NOW - 10 * _HOUR
    svc = _svc(tmp_path)
    _seed_interest(svc, [_irow("t1", t0, asset="HOME", interest="0.5")])
    repays = [_repay("a", update_time=str(t0 + 1000), price=None)]
    assert svc.sum_interest_usdt_by_asset("HOME", t0, NOW, {"HOMEUSDT": "3"}, repays) is None
    # 非终态（开放桶）缺当前价同样 fail-closed
    assert svc.sum_interest_usdt_by_asset("HOME", t0, NOW, {}) is None


def test_sum_interest_usdt_zero_rules(tmp_path):
    """空窗口 → "0"（真零）；USDT 本位无需价格；不可解析 → None。"""
    t0 = NOW - 10 * _HOUR
    svc = _svc(tmp_path)
    _seed_interest(svc, [
        _irow("t1", t0, asset="USDT", interest="0.5"),
        _irow("t2", t0, asset="HOME", interest="not-a-number"),
    ])
    assert svc.sum_interest_usdt_by_asset("HOME", NOW + _HOUR, NOW + 2 * _HOUR, {}) == "0"
    assert svc.sum_interest_usdt_by_asset("USDT", t0, NOW, {}) == "0.5"
    assert svc.sum_interest_usdt_by_asset("HOME", t0, NOW, {"HOMEUSDT": "2"}) is None
    # 币本位合计不受影响（仍走 sum_interest_by_asset）
    assert svc.sum_interest_by_asset("HOME", t0, NOW) is None
