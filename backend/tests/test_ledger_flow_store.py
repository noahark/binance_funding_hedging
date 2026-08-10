"""Tests for backend.ledger_flow.store (design §14, v1.2 F1/F3/F4).

Offline against a temp SQLite file. Covers: the four tables + indexes; amount
columns are TEXT with no SQL aggregation anywhere; idempotent writes that never
overwrite first_seen_*; the F1 transaction model (run record never rolled back
by a detail failure; one source's detail+coverage in one transaction; two
sources independent); the query surface for task B; empty-DB safety; and that
the store does not judge "success run" semantics.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from backend.ledger_flow.store import LedgerStore, _SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[2]
STORE_SOURCE = (REPO_ROOT / "backend/ledger_flow/store.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def store(tmp_path):
    s = LedgerStore(str(tmp_path / "ledger-flow.sqlite3"))
    yield s
    s.close()


def _run(overrides=None):
    base = dict(
        kind="scheduled", started_at_ms=1000, finished_at_ms=2000,
        window_start_ms=0, window_end_ms=2000,
        interest_status="ok", interest_error=None,
        interest_fetched_row_count=1, interest_new_row_count=1,
        income_status="ok", income_error=None,
        income_fetched_row_count=1, income_new_row_count=1,
        truncated=False,
    )
    if overrides:
        base.update(overrides)
    return base


def _interest(tx_id, ms, asset="HOME", interest="0.1"):
    return {"tx_id": tx_id, "accrued_at_ms": ms, "asset": asset,
            "raw_asset": asset, "principal": "1.0", "interest": interest,
            "interest_rate": "0.01", "type": "PERIODIC", "isolated_symbol": None}


def _income(tran_id, ms, income_type="FUNDING_FEE", income="0.1", symbol="MUUSDT",
            asset="USDT"):
    return {"tran_id": tran_id, "income_type": income_type, "time_ms": ms,
            "symbol": symbol, "income": income, "asset": asset,
            "info": income_type, "trade_id": None}


# --------------------------------------------------------------------------- #
# schema: four tables + indexes; amount columns TEXT; no SQL aggregation
# --------------------------------------------------------------------------- #
def test_four_tables_and_indexes_created(store):
    names = {r[0] for r in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    for t in ("interest_rows", "um_income_rows", "flow_refresh_runs", "ledger_meta"):
        assert t in names
    for idx in ("idx_interest_time", "idx_interest_seen", "idx_income_time",
                "idx_income_seen", "idx_runs_finished"):
        assert idx in names


def test_amount_columns_are_text(store):
    def cols(table):
        return {r[1]: r[2] for r in store._conn.execute(f"PRAGMA table_info({table})")}
    ic = cols("interest_rows")
    for c in ("principal", "interest", "interest_rate", "raw_asset", "tx_id"):
        assert ic[c] == "TEXT", f"interest_rows.{c} must be TEXT, got {ic[c]}"
    uc = cols("um_income_rows")
    for c in ("income", "tran_id", "symbol"):
        assert uc[c] == "TEXT", f"um_income_rows.{c} must be TEXT, got {uc[c]}"


def test_no_sql_aggregation_on_amounts_in_source():
    """Red line: no SUM()/AVG()/TOTAL() call anywhere in store.py — SQLite would
    coerce TEXT amounts to float. (The docstring mentions SUM/AVG in prose
    without parens, so we match the SQL call form specifically.)"""
    assert re.search(r"\b(SUM|AVG|TOTAL)\s*\(", STORE_SOURCE) is None
    # the amount path never touches float()
    assert re.search(r"\bfloat\s*\(", STORE_SOURCE) is None


def test_schema_version_meta_set(store):
    assert store.get_meta("schema_version") == "private-ledger/v2"


# --------------------------------------------------------------------------- #
# idempotency: never overwrite first_seen_*; same batch shares first_seen_at_ms
# --------------------------------------------------------------------------- #
def test_interest_idempotent_no_overwrite(store):
    run_id = store.insert_run(_run())
    r1 = store.commit_interest(
        rows=[_interest("A", 100)], run_id=run_id, first_seen_at_ms=1000,
        coverage_start_ms=0, coverage_end_ms=2000)
    assert r1 == {"fetched_row_count": 1, "new_row_count": 1}
    # re-insert the SAME row under a later run/clock -> new=0, first_seen kept.
    r2 = store.commit_interest(
        rows=[_interest("A", 100)], run_id=999, first_seen_at_ms=9999,
        coverage_start_ms=None, coverage_end_ms=None)
    assert r2 == {"fetched_row_count": 1, "new_row_count": 0}
    got = store.query_interest_rows(0, 10_000_000_000)
    assert len(got) == 1
    assert got[0]["first_seen_run_id"] == run_id   # NOT overwritten to 999
    assert got[0]["first_seen_at_ms"] == 1000       # NOT overwritten to 9999


def test_same_batch_shares_one_first_seen_at_ms(store):
    run_id = store.insert_run(_run())
    store.commit_interest(
        rows=[_interest("A", 100), _interest("B", 200), _interest("C", 300)],
        run_id=run_id, first_seen_at_ms=1500,
        coverage_start_ms=0, coverage_end_ms=2000)
    seen = {r["first_seen_at_ms"] for r in store.query_interest_rows(0, 10_000_000_000)}
    assert seen == {1500}


def test_income_idempotent_composite_key(store):
    run_id = store.insert_run(_run())
    store.commit_income(
        rows=[_income("1", 100, "FUNDING_FEE")], run_id=run_id, first_seen_at_ms=1000,
        coverage_start_ms=0, coverage_end_ms=2000)
    # same (income_type, tran_id) -> no second row; a different type is distinct.
    store.commit_income(
        rows=[_income("1", 100, "FUNDING_FEE"), _income("1", 100, "COMMISSION")],
        run_id=run_id, first_seen_at_ms=2000,
        coverage_start_ms=None, coverage_end_ms=None)
    rows = store.query_income_rows(0, 10_000_000_000)
    assert len(rows) == 2
    ff = [r for r in rows if r["income_type"] == "FUNDING_FEE"][0]
    assert ff["first_seen_at_ms"] == 1000  # not overwritten


# --------------------------------------------------------------------------- #
# F1 transaction model
# --------------------------------------------------------------------------- #
def test_run_record_not_rolled_back_by_detail_failure(store):
    # commit_income succeeds; a later commit_interest that fails must NOT erase
    # the already-committed run record.
    run_id = store.insert_run(_run())
    store.commit_income(
        rows=[_income("1", 100)], run_id=run_id, first_seen_at_ms=1500,
        coverage_start_ms=0, coverage_end_ms=2000)
    with pytest.raises(sqlite3.IntegrityError):
        store.commit_interest(
            rows=[{"tx_id": "X", "accrued_at_ms": 100, "asset": None}],  # NOT NULL
            run_id=run_id, first_seen_at_ms=1500,
            coverage_start_ms=0, coverage_end_ms=2000)
    runs = store.recent_runs(5)
    assert len(runs) == 1
    assert runs[0]["id"] == run_id


def test_source_detail_and_coverage_one_transaction(store):
    # An interest commit that fails mid-way rolls back BOTH its rows AND its
    # coverage advance (no partial state, no coverage over unproven data).
    run_id = store.insert_run(_run())
    with pytest.raises(sqlite3.IntegrityError):
        store.commit_interest(
            rows=[_interest("OK", 100),
                  {"tx_id": "BAD", "accrued_at_ms": 200, "asset": None}],
            run_id=run_id, first_seen_at_ms=1500,
            coverage_start_ms=0, coverage_end_ms=2000)
    assert store.query_interest_rows(0, 10_000_000_000) == []   # no partial rows
    cov = store.get_coverage()
    assert cov["interest_start_ms"] is None                      # no coverage advance
    assert cov["interest_end_ms"] is None


def test_two_sources_independent(store):
    # income commits first; interest then fails. income's rows AND coverage
    # must survive the interest transaction's rollback.
    run_id = store.insert_run(_run())
    store.commit_income(
        rows=[_income("1", 100)], run_id=run_id, first_seen_at_ms=1500,
        coverage_start_ms=0, coverage_end_ms=2000)
    with pytest.raises(sqlite3.IntegrityError):
        store.commit_interest(
            rows=[{"tx_id": "X", "accrued_at_ms": 100, "asset": None}],
            run_id=run_id, first_seen_at_ms=1500,
            coverage_start_ms=0, coverage_end_ms=2000)
    assert len(store.query_income_rows(0, 10_000_000_000)) == 1
    cov = store.get_coverage()
    assert cov["income_start_ms"] == 0 and cov["income_end_ms"] == 2000
    assert cov["interest_start_ms"] is None


# --------------------------------------------------------------------------- #
# query surface (for task B)
# --------------------------------------------------------------------------- #
def test_query_interest_window_desc_and_limit(store):
    run_id = store.insert_run(_run())
    rows = [_interest(str(i), 100 + i) for i in range(10)]
    store.commit_interest(rows=rows, run_id=run_id, first_seen_at_ms=1500,
                          coverage_start_ms=0, coverage_end_ms=2000)
    full = store.query_interest_rows(0, 10_000_000_000)
    assert [r["accrued_at_ms"] for r in full] == sorted(
        (r["accrued_at_ms"] for r in full), reverse=True)  # DESC by time
    limited = store.query_interest_rows(0, 10_000_000_000, limit=3)
    assert len(limited) == 3
    assert [r["accrued_at_ms"] for r in limited] == [109, 108, 107]


def test_query_since_delta_by_first_seen(store):
    run_id1 = store.insert_run(_run())
    store.commit_interest(rows=[_interest("A", 100)], run_id=run_id1,
                          first_seen_at_ms=1000, coverage_start_ms=0,
                          coverage_end_ms=2000)
    run_id2 = store.insert_run(_run({"finished_at_ms": 3000}))
    store.commit_interest(rows=[_interest("B", 200)], run_id=run_id2,
                          first_seen_at_ms=3000, coverage_start_ms=0,
                          coverage_end_ms=3000)
    delta = store.query_interest_since(2000)  # first_seen_at_ms > 2000
    assert [r["tx_id"] for r in delta] == ["B"]


def test_get_coverage_per_source_and_gaps(store):
    run_id = store.insert_run(_run())
    store.commit_income(rows=[_income("1", 100)], run_id=run_id,
                        first_seen_at_ms=1500, coverage_start_ms=100,
                        coverage_end_ms=200,
                        new_gaps=[{"source": "income", "start_ms": 50, "end_ms": 100}])
    store.commit_interest(rows=[_interest("A", 100)], run_id=run_id,
                          first_seen_at_ms=1500, coverage_start_ms=0,
                          coverage_end_ms=200,
                          new_gaps=[{"source": "interest", "start_ms": 0, "end_ms": 50}])
    cov = store.get_coverage()
    assert cov["interest_start_ms"] == 0 and cov["interest_end_ms"] == 200
    assert cov["income_start_ms"] == 100 and cov["income_end_ms"] == 200
    # gaps sorted by start_ms ascending; both sources recorded.
    assert cov["gaps"] == [
        {"source": "interest", "start_ms": 0, "end_ms": 50},
        {"source": "income", "start_ms": 50, "end_ms": 100},
    ]


def test_coverage_gaps_dedup(store):
    run_id = store.insert_run(_run())
    gap = [{"source": "interest", "start_ms": 0, "end_ms": 50}]
    store.commit_interest(rows=[_interest("A", 100)], run_id=run_id,
                          first_seen_at_ms=1500, coverage_start_ms=0,
                          coverage_end_ms=200, new_gaps=gap)
    store.commit_interest(rows=[_interest("B", 110)], run_id=run_id,
                          first_seen_at_ms=1500, coverage_start_ms=0,
                          coverage_end_ms=210, new_gaps=gap)  # same gap again
    assert store.get_coverage()["gaps"] == [{"source": "interest",
                                             "start_ms": 0, "end_ms": 50}]


def test_recent_runs_desc_finished_only(store):
    # An unfinished run (finished_at_ms=None) is excluded; results are DESC.
    store.insert_run(_run({"finished_at_ms": None}))   # unfinished, excluded
    store.insert_run(_run({"finished_at_ms": 1000}))
    store.insert_run(_run({"finished_at_ms": 2000}))
    runs = store.recent_runs(5)
    assert [r["finished_at_ms"] for r in runs] == [2000, 1000]


def test_store_does_not_judge_success_run(store):
    # The store returns runs regardless of status/kind — classifying a
    # "success run" (kind in {scheduled,startup_catchup,backfill} AND both ok)
    # is the service's job (§13.2 rule 10 / §15.4 / v1.2 F3).
    store.insert_run(_run({"kind": "manual", "interest_status": "error",
                           "interest_error": "interest_history_failed",
                           "finished_at_ms": 1000}))
    runs = store.recent_runs(5)
    assert len(runs) == 1   # not filtered out by the store


# --------------------------------------------------------------------------- #
# empty-DB safety (§13.2 rule 13)
# --------------------------------------------------------------------------- #
def test_empty_db_all_queries_safe(store):
    assert store.query_interest_rows(0, 10_000_000_000) == []
    assert store.query_income_rows(0, 10_000_000_000) == []
    assert store.query_interest_since(0) == []
    assert store.query_income_since(0) == []
    assert store.recent_runs(5) == []
    cov = store.get_coverage()
    assert cov == {"interest_start_ms": None, "interest_end_ms": None,
                   "income_start_ms": None, "income_end_ms": None, "gaps": []}


# --------------------------------------------------------------------------- #
# amount precision survives the store round-trip (TEXT, verbatim)
# --------------------------------------------------------------------------- #
def test_high_precision_amount_round_trips_verbatim(store):
    amt = "0.0000897500000000123456789"  # more precision than float can hold
    run_id = store.insert_run(_run())
    store.commit_interest(rows=[_interest("A", 100, interest=amt)], run_id=run_id,
                          first_seen_at_ms=1500, coverage_start_ms=0,
                          coverage_end_ms=2000)
    got = store.query_interest_rows(0, 10_000_000_000)[0]
    assert got["interest"] == amt  # exact string, not float-coerced


def test_reopen_existing_db_is_idempotent(tmp_path):
    # CREATE TABLE IF NOT EXISTS + upsert schema_version: reopening is a no-op.
    p = str(tmp_path / "ledger-flow.sqlite3")
    s1 = LedgerStore(p)
    run_id = s1.insert_run(_run())
    s1.commit_interest(rows=[_interest("A", 100)], run_id=run_id,
                       first_seen_at_ms=1000, coverage_start_ms=0,
                       coverage_end_ms=2000)
    s1.close()
    s2 = LedgerStore(p)
    assert s2.get_meta("schema_version") == "private-ledger/v2"
    assert len(s2.query_interest_rows(0, 10_000_000_000)) == 1
    s2.close()


# --------------------------------------------------------------------------- #
# cross-margin capital-flow (stage 2026-08-10) — isolated table + own meta
# --------------------------------------------------------------------------- #
def _cap(row_id, ms, tran_id="399258471825", asset="USDT", ftype="TRANSFER",
         amount="10"):
    return {"id": str(row_id), "tran_id": str(tran_id), "time_ms": ms,
            "asset": asset, "flow_type": ftype, "amount": amount}


def test_capital_table_created(store):
    names = {r[0] for r in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    assert "margin_capital_flow_rows" in names
    assert "idx_capital_time" in names


def test_capital_amount_column_is_text(store):
    cols = {r[1]: r[2] for r in store._conn.execute(
        "PRAGMA table_info(margin_capital_flow_rows)")}
    for c in ("amount", "id", "tran_id", "asset", "flow_type"):
        assert cols[c] == "TEXT", f"margin_capital_flow_rows.{c} must be TEXT"


def test_capital_commit_idempotent_no_overwrite(store):
    r1 = store.commit_capital_flow(
        rows=[_cap("601", 100)], first_seen_at_ms=1000,
        coverage_start_ms=0, coverage_end_ms=2000,
        last_run={"status": "ok"})
    assert r1 == {"fetched_row_count": 1, "new_row_count": 1}
    # re-insert the SAME id under a later clock -> new=0, first_seen kept.
    r2 = store.commit_capital_flow(
        rows=[_cap("601", 100)], first_seen_at_ms=9999,
        coverage_start_ms=None, coverage_end_ms=None)
    assert r2 == {"fetched_row_count": 1, "new_row_count": 0}
    got = store.query_capital_flow_rows(0, 10_000_000_000)
    assert len(got) == 1 and got[0]["first_seen_at_ms"] == 1000  # NOT overwritten


def test_capital_multi_type_same_tranid_all_retained(store):
    # same tranId, different flow_type, different id -> all kept (recon §3.3).
    store.commit_capital_flow(
        rows=[_cap("601", 100, ftype="SELL_INCOME", amount="16.533"),
              _cap("602", 100, asset="WLD", ftype="SELL_EXPENSE", amount="-49.5")],
        first_seen_at_ms=1000, coverage_start_ms=0, coverage_end_ms=2000)
    rows = store.query_capital_flow_rows(0, 10_000_000_000)
    assert {r["id"] for r in rows} == {"601", "602"}
    assert {r["tran_id"] for r in rows} == {"399258471825"}  # both share tranId


def test_capital_coverage_and_last_run_stamped(store):
    out = store.commit_capital_flow(
        rows=[_cap("601", 100), _cap("602", 200)],
        first_seen_at_ms=1500, coverage_start_ms=0, coverage_end_ms=2000,
        last_run={"finished_at_ms": 1500, "status": "ok", "error": None,
                  "possibly_incomplete": True, "window_start_ms": 0,
                  "window_end_ms": 2000})
    # store stamps the authoritative fetched/new counts into last_run.
    assert out == {"fetched_row_count": 2, "new_row_count": 2}
    state = store.get_capital_flow_state()
    assert state["start_ms"] == 0 and state["end_ms"] == 2000
    assert state["last_run"]["fetched_row_count"] == 2
    assert state["last_run"]["new_row_count"] == 2
    assert state["last_run"]["possibly_incomplete"] is True


def test_capital_failed_pull_advances_nothing(store):
    # coverage_*=None on a failed pull -> coverage stays None, last_run still
    # recorded (error trace) but fetched/new stamped to 0.
    store.commit_capital_flow(
        rows=[], first_seen_at_ms=1500, coverage_start_ms=None,
        coverage_end_ms=None,
        last_run={"finished_at_ms": 1500, "status": "error",
                  "error": "capital_flow_failed", "possibly_incomplete": False})
    state = store.get_capital_flow_state()
    assert state["start_ms"] is None and state["end_ms"] is None
    assert state["last_run"]["status"] == "error"
    assert state["last_run"]["new_row_count"] == 0


def test_capital_empty_db_state_safe(store):
    state = store.get_capital_flow_state()
    assert state == {"start_ms": None, "end_ms": None, "last_run": None}
    assert store.query_capital_flow_rows(0, 10_000_000_000) == []


def test_capital_query_window_desc_and_limit(store):
    store.commit_capital_flow(
        rows=[_cap(str(i), 100 + i) for i in range(5)],
        first_seen_at_ms=1500, coverage_start_ms=0, coverage_end_ms=2000)
    full = store.query_capital_flow_rows(0, 10_000_000_000)
    assert [r["time_ms"] for r in full] == sorted(
        (r["time_ms"] for r in full), reverse=True)  # DESC by time
    limited = store.query_capital_flow_rows(0, 10_000_000_000, limit=2)
    assert len(limited) == 2


def test_capital_isolated_from_two_source_coverage(store):
    # Writing capital must NOT touch flow_refresh_runs, the shared
    # coverage_gaps, or interest/income coverage (P0-1/P0-2 isolation).
    run_id = store.insert_run(_run())
    store.commit_income(rows=[_income("1", 100)], run_id=run_id,
                        first_seen_at_ms=1500, coverage_start_ms=100,
                        coverage_end_ms=200)
    store.commit_capital_flow(
        rows=[_cap("601", 150)], first_seen_at_ms=1500,
        coverage_start_ms=0, coverage_end_ms=2000,
        last_run={"status": "ok"})
    # the two-source coverage is byte-identical to a capital-less baseline:
    cov = store.get_coverage()
    assert set(cov.keys()) == {"interest_start_ms", "interest_end_ms",
                               "income_start_ms", "income_end_ms", "gaps"}
    assert cov["interest_start_ms"] is None          # never set
    assert cov["income_start_ms"] == 100 and cov["income_end_ms"] == 200
    assert cov["gaps"] == []
    # the shared run table has exactly ONE row (the interest/income run), and
    # it carries NO capital column (zero-migration):
    assert len(store.recent_runs(5)) == 1
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(flow_refresh_runs)")}
    assert not any("capital" in c for c in cols)
