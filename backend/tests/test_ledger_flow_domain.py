"""Pure-function tests for backend.ledger_flow.domain (design §13.2 / §14).

Offline: no network, no signing, no sqlite — domain is a pure module. Covers
the four frozen hard rules: IDs as strings, amounts verbatim / missing→None,
Decimal summation under an explicit localcontext (prec ≥ 40), unparseable
amount → null total + unparsed count, plus the dedup keys and DESC sort keys.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from backend.ledger_flow import domain as D

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_SOURCE = (REPO_ROOT / "backend/ledger_flow/domain.py").read_text(encoding="utf-8")


# ---- module purity: no network / signing / sqlite imports ----
def test_domain_has_no_network_signing_or_sqlite_imports():
    """domain.py is pure: it must not import any I/O, signing, or persistence
    module (design §16 — domain is zero-I/O and offline-testable)."""
    forbidden = ["urllib", "requests", "socket", "hmac", "hashlib",
                 "sqlite3", "binance_signing", "aiohttp", "http"]
    bad = [name for name in forbidden if name in DOMAIN_SOURCE]
    assert bad == [], f"domain.py imports forbidden module(s): {bad}"


# ---- rule 1: all IDs are strings (19-digit longs preserved exactly) ----
def test_interest_txid_long_preserved_as_exact_string():
    # 2328408217636413776 > 2**53; arriving as a JSON number (Python int, exact)
    # must become the exact decimal string — never exponent / never mutated.
    big = 2328408217636413776
    assert big > 2 ** 53
    rows = D.normalize_interest_rows([
        {"txId": big, "interestAccuredTime": 1785798000000, "asset": "HOME",
         "interest": "0.00008975"},
    ])
    assert rows[0]["tx_id"] == "2328408217636413776"


def test_interest_txid_string_input_preserved_verbatim():
    rows = D.normalize_interest_rows([
        {"txId": "9999999999999999999", "interestAccuredTime": 1, "asset": "X"},
    ])
    assert rows[0]["tx_id"] == "9999999999999999999"


def test_income_tranid_long_preserved_as_exact_string():
    rows = D.normalize_income_rows([
        {"tranId": 4005036198425048448, "incomeType": "FUNDING_FEE",
         "time": 1783411200000, "income": "0.08", "asset": "USDT", "symbol": "MUUSDT"},
    ])
    assert rows[0]["tran_id"] == "4005036198425048448"


# ---- rule 2: amounts/rates verbatim; missing → None; empty string → None ----
def test_interest_amounts_passed_through_verbatim():
    rows = D.normalize_interest_rows([
        {"txId": "1", "interestAccuredTime": 1, "asset": "A",
         "principal": "1.0", "interest": "0.00008975",
         "interestRate": "0.00215396"},
    ])
    r = rows[0]
    assert r["principal"] == "1.0"            # no rounding / no zero-pad
    assert r["interest"] == "0.00008975"      # 8 dp preserved
    assert r["interest_rate"] == "0.00215396"


def test_interest_missing_amounts_are_none_not_zero():
    rows = D.normalize_interest_rows([
        {"txId": "1", "interestAccuredTime": 1, "asset": "A",
         "principal": None, "interest": None, "interestRate": None},
    ])
    r = rows[0]
    assert r["principal"] is None
    assert r["interest"] is None
    assert r["interest_rate"] is None


def test_interest_empty_optional_text_becomes_none():
    # isolated_symbol "" (cross-margin rows omit it) -> None.
    rows = D.normalize_interest_rows([
        {"txId": "1", "interestAccuredTime": 1, "asset": "A", "isolatedSymbol": ""},
    ])
    assert rows[0]["isolated_symbol"] is None


def test_income_empty_symbol_and_tradeid_become_none():
    # TRANSFER rows have symbol=""; funding rows have tradeId="".
    rows = D.normalize_income_rows([
        {"symbol": "", "incomeType": "TRANSFER", "income": "-1.0", "asset": "USDT",
         "time": 1785163055000, "tranId": 111, "tradeId": ""},
    ])
    r = rows[0]
    assert r["symbol"] is None
    assert r["trade_id"] is None


def test_normalize_drops_rows_missing_idempotency_key_or_time():
    # A row without its idempotency key or timestamp cannot be stored (NOT NULL)
    # or placed in a window; normalize drops it rather than fabricate values.
    rows = D.normalize_interest_rows([
        {"txId": None, "interestAccuredTime": 1, "asset": "A"},      # no txId
        {"txId": "2", "interestAccuredTime": None, "asset": "A"},    # no time
        {"txId": "3", "interestAccuredTime": 1, "asset": None},      # no asset
        {"txId": "4", "interestAccuredTime": 1, "asset": "A"},       # ok
        "not-a-dict",
    ])
    assert len(rows) == 1
    assert rows[0]["tx_id"] == "4"


# ---- dedup keys (first occurrence wins — never overwrites) ----
def test_dedup_interest_by_tx_id_first_wins():
    rows = [
        {"tx_id": "1", "accrued_at_ms": 100, "asset": "A", "interest": "0.1"},
        {"tx_id": "1", "accrued_at_ms": 100, "asset": "A", "interest": "0.9"},  # dup
        {"tx_id": "2", "accrued_at_ms": 200, "asset": "A", "interest": "0.2"},
    ]
    out = D.dedup_interest_rows(rows)
    assert [r["tx_id"] for r in out] == ["1", "2"]
    assert out[0]["interest"] == "0.1"  # first wins, not overwritten by 0.9


def test_dedup_income_by_type_tranid_first_wins():
    rows = [
        {"tran_id": "1", "income_type": "FUNDING_FEE", "time_ms": 100, "income": "0.1"},
        {"tran_id": "1", "income_type": "FUNDING_FEE", "time_ms": 100, "income": "0.9"},
        {"tran_id": "1", "income_type": "COMMISSION", "time_ms": 100, "income": "0.2"},
    ]
    out = D.dedup_income_rows(rows)
    # (FUNDING_FEE, 1) deduped; (COMMISSION, 1) is a distinct key -> 2 rows.
    assert len(out) == 2
    assert out[0]["income"] == "0.1"  # first wins


# ---- sort keys (final display order, time DESC + stable tie-break) ----
def test_sort_interest_desc_by_time_then_txid():
    rows = [
        {"tx_id": "3", "accrued_at_ms": 100, "asset": "A"},
        {"tx_id": "9", "accrued_at_ms": 300, "asset": "A"},
        {"tx_id": "1", "accrued_at_ms": 100, "asset": "A"},  # same time as tx3
    ]
    out = D.sort_interest_desc(rows)
    assert [(r["accrued_at_ms"], r["tx_id"]) for r in out] == [
        (300, "9"), (100, "3"), (100, "1"),
    ]


def test_sort_income_desc_by_time_then_type_then_tranid():
    rows = [
        {"tran_id": "5", "income_type": "COMMISSION", "time_ms": 100},
        {"tran_id": "2", "income_type": "FUNDING_FEE", "time_ms": 100},
        {"tran_id": "9", "income_type": "FUNDING_FEE", "time_ms": 300},
        {"tran_id": "1", "income_type": "FUNDING_FEE", "time_ms": 100},
    ]
    out = D.sort_income_desc(rows)
    assert [(r["time_ms"], r["income_type"], r["tran_id"]) for r in out] == [
        (300, "FUNDING_FEE", "9"),
        # same time 100: income_type DESC -> FUNDING_FEE before COMMISSION,
        # then tran_id DESC within FUNDING_FEE.
        (100, "FUNDING_FEE", "2"),
        (100, "FUNDING_FEE", "1"),
        (100, "COMMISSION", "5"),
    ]


# ---- rule 3: Decimal summation (exact, format 'f', explicit localcontext) ----
def test_summarize_interest_decimal_sum_exact_and_plain_format():
    rows = [
        {"asset": "HOME", "interest": "0.00008975"},
        {"asset": "HOME", "interest": "0.00008975"},
    ]
    out = D.summarize_interest_by_asset(rows)
    assert out == [{"asset": "HOME", "interest_total": "0.00017950",
                    "row_count": 2, "unparsed_row_count": 0}]


def test_summarize_decimal_not_float():
    # 0.1 + 0.2 must be exactly "0.3", not the float 0.30000000000000004.
    rows = [{"asset": "A", "interest": "0.1"}, {"asset": "A", "interest": "0.2"}]
    out = D.summarize_interest_by_asset(rows)
    assert out[0]["interest_total"] == "0.3"


def test_summarize_uses_localcontext_prec_at_least_40():
    # A sum whose result has 30 significant digits would be rounded at the
    # Python default Decimal prec (28) but is exact at prec ≥ 40. This proves
    # the explicit localcontext is in effect, not the process default.
    big = "12345678901234567890.1234567890"  # 30 significant digits
    rows = [{"asset": "A", "interest": big}, {"asset": "A", "interest": "0.0000000001"}]
    out = D.summarize_interest_by_asset(rows)
    assert out[0]["interest_total"] == "12345678901234567890.1234567891"
    assert out[0]["unparsed_row_count"] == 0


def test_summarize_skips_none_amounts_not_counted_unparsed():
    # Missing (None) amounts are skipped, NOT counted as unparseable; the
    # remaining parseable amounts still sum.
    rows = [{"asset": "A", "interest": None}, {"asset": "A", "interest": "0.5"}]
    out = D.summarize_interest_by_asset(rows)
    assert out[0]["interest_total"] == "0.5"
    assert out[0]["row_count"] == 2
    assert out[0]["unparsed_row_count"] == 0


# ---- rule 4: unparseable amount → null total + unparsed_row_count > 0 ----
def test_summarize_unparseable_nulls_total_and_counts():
    rows = [
        {"asset": "A", "interest": "0.1"},
        {"asset": "A", "interest": "not-a-number"},  # unparseable
        {"asset": "A", "interest": "0.2"},
    ]
    out = D.summarize_interest_by_asset(rows)
    assert out[0]["asset"] == "A"
    assert out[0]["interest_total"] is None       # never a partial sum
    assert out[0]["row_count"] == 3
    assert out[0]["unparsed_row_count"] == 1


def test_summarize_income_by_type_asset_never_cross_currency():
    # USDT funding fee and BNB commission stay in separate groups — never summed.
    rows = [
        {"income_type": "FUNDING_FEE", "asset": "USDT", "income": "0.1"},
        {"income_type": "FUNDING_FEE", "asset": "USDT", "income": "0.2"},
        {"income_type": "COMMISSION", "asset": "BNB", "income": "-0.0001"},
    ]
    out = D.summarize_income_by_type_asset(rows)
    groups = {(g["income_type"], g["asset"]): g for g in out}
    assert groups[("FUNDING_FEE", "USDT")]["income_total"] == "0.3"
    assert groups[("COMMISSION", "BNB")]["income_total"] == "-0.0001"


def test_summarize_funding_by_symbol_only_funding_fee_ranked_desc():
    rows = [
        {"symbol": "MUUSDT", "asset": "USDT", "income_type": "FUNDING_FEE", "income": "0.08"},
        {"symbol": "RSRUSDT", "asset": "USDT", "income_type": "FUNDING_FEE", "income": "-0.02"},
        {"symbol": "MUUSDT", "asset": "USDT", "income_type": "COMMISSION", "income": "-0.001"},
        {"symbol": "MUUSDT", "asset": "USDT", "income_type": "FUNDING_FEE", "income": "0.04"},
    ]
    out = D.summarize_funding_by_symbol(rows)
    # COMMISSION excluded; MUUSDT sums 0.12, RSRUSDT -0.02; ranked DESC.
    assert [(g["symbol"], g["income_total"], g["row_count"]) for g in out] == [
        ("MUUSDT", "0.12", 2),
        ("RSRUSDT", "-0.02", 1),
    ]


def test_summarize_funding_unparseable_nulls_total():
    rows = [
        {"symbol": "MUUSDT", "asset": "USDT", "income_type": "FUNDING_FEE", "income": "0.08"},
        {"symbol": "MUUSDT", "asset": "USDT", "income_type": "FUNDING_FEE", "income": "bad"},
    ]
    out = D.summarize_funding_by_symbol(rows)
    assert out[0]["income_total"] is None
    assert out[0]["row_count"] == 2


# ---- window validation (§13.3 — service maps failure to HTTP 400) ----
def test_validate_window_rejects_start_ge_end():
    with pytest.raises(D.WindowValidationError):
        D.validate_window(10, 10)
    with pytest.raises(D.WindowValidationError):
        D.validate_window(20, 10)


def test_validate_window_accepts_valid_and_non_int():
    assert D.validate_window(1, 2) == (1, 2)
    with pytest.raises(D.WindowValidationError):
        D.validate_window("1", 2)  # type: ignore[arg-type]


def test_validate_window_has_no_30_day_cap():
    # The page reads the local ledger; custom windows may exceed 30 days.
    big = 31 * 24 * 3600 * 1000
    assert D.validate_window(0, big) == (0, big)
