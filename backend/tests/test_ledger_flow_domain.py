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


# ---- cross-margin capital-flow normalization (stage 2026-08-10) ----
def test_normalize_capital_rows_maps_fields_and_id_as_string():
    # id/tranId arrive as JSON numbers (Python int, exact) -> str idempotency
    # key; amount passed through verbatim with its sign preserved.
    rows = D.normalize_capital_rows([
        {"id": 159745763323, "tranId": 399260348988, "timestamp": 1786341345000,
         "asset": "USDT", "type": "TRANSFER", "amount": "10"},
        {"id": 159745756972, "tranId": 399260281458, "timestamp": 1786341331000,
         "asset": "USDT", "type": "TRANSFER", "amount": "-10"},
    ])
    assert rows == [
        {"id": "159745763323", "tran_id": "399260348988", "time_ms": 1786341345000,
         "asset": "USDT", "flow_type": "TRANSFER", "amount": "10"},
        {"id": "159745756972", "tran_id": "399260281458", "time_ms": 1786341331000,
         "asset": "USDT", "flow_type": "TRANSFER", "amount": "-10"},
    ]


def test_normalize_capital_rows_drops_missing_id_or_time_or_asset_or_tranid():
    # id is the PK/dedup key; time_ms/asset/tran_id are NOT NULL. Missing any
    # -> the row is dropped (cannot be stored / placed in time / cross-ref'd).
    rows = D.normalize_capital_rows([
        {"id": 1, "tranId": 1, "timestamp": 1, "asset": "USDT"},          # ok
        {"tranId": 2, "timestamp": 1, "asset": "USDT"},                   # no id
        {"id": 3, "tranId": 3, "asset": "USDT"},                          # no time
        {"id": 4, "tranId": 4, "timestamp": 1},                           # no asset
        {"id": 5, "timestamp": 1, "asset": "USDT"},                       # no tranId
        "not-a-dict",
    ])
    assert [r["id"] for r in rows] == ["1"]


def test_normalize_capital_rows_non_list_is_empty():
    assert D.normalize_capital_rows(None) == []
    assert D.normalize_capital_rows({}) == []


def test_dedup_capital_rows_by_id_keeps_multi_type_same_tranid():
    # recon §3.3 / frontend baseline: same tranId with different flow_type has
    # DIFFERENT id and must all survive (they are distinct ledger lines).
    rows = [
        {"id": "601", "tran_id": "399258471825", "time_ms": 1, "asset": "USDT",
         "flow_type": "SELL_INCOME", "amount": "16.533"},
        {"id": "602", "tran_id": "399258471825", "time_ms": 1, "asset": "WLD",
         "flow_type": "SELL_EXPENSE", "amount": "-49.5"},
        {"id": "601", "tran_id": "399258471825", "time_ms": 1, "asset": "USDT",
         "flow_type": "SELL_INCOME", "amount": "16.533"},  # exact id dup
    ]
    out = D.dedup_capital_rows(rows)
    assert [r["id"] for r in out] == ["601", "602"]  # dup dropped, both types kept


# --------------------------------------------------------------------------- #
# 资金费率收益曲线（2026-08-20）
# --------------------------------------------------------------------------- #
HOUR = 3_600_000
_T0 = 1_000 * HOUR


def _series(**over):
    """默认一份四类流水俱全的最小输入；用关键字覆盖单项。"""
    args = dict(
        interest_rows=[{"accrued_at_ms": _T0, "asset": "WLD", "interest": "0.5"}],
        income_rows=[
            {"time_ms": _T0, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "3"},
            {"time_ms": _T0, "income_type": "COMMISSION", "asset": "USDT", "income": "-0.4"},
            {"time_ms": _T0, "income_type": "REALIZED_PNL", "asset": "USDT", "income": "-26"},
        ],
        capital_rows=[{"time_ms": _T0, "flow_type": "TRADING_COMMISSION",
                       "asset": "BNB", "amount": "-0.001"}],
        close_logs=[],
        price_map={"WLDUSDT": "2", "BNBUSDT": "600"},
        start_ms=0, end_ms=_T0 + HOUR, bucket_ms=HOUR,
    )
    args.update(over)
    return D.build_pnl_series(**args)


def test_pnl_series_costs_are_negative_and_net_is_their_sum():
    out = _series()
    t = out["totals"]
    assert t["funding"] == "3"
    assert Decimal(t["fees"]) == Decimal("-1.0")      # -0.4 USDT + (-0.001 BNB × 600)
    assert Decimal(t["interest"]) == Decimal("-1.0")  # 0.5 WLD × 2，账本正数取负
    # 净收益就是四项直接相加，不做二次符号翻转
    assert Decimal(t["net"]) == sum(
        Decimal(t[k]) for k in ("funding", "fees", "interest", "slippage"))
    assert Decimal(t["net"]) == Decimal("1.0")


def test_pnl_series_realized_pnl_excluded_from_net():
    """REALIZED_PNL 由现货腿反向盈亏抵消，绝不能混进净收益。"""
    with_realized = _series()
    without = _series(income_rows=[
        {"time_ms": _T0, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "3"},
        {"time_ms": _T0, "income_type": "COMMISSION", "asset": "USDT", "income": "-0.4"},
    ])
    assert with_realized["totals"]["net"] == without["totals"]["net"]


def test_pnl_series_unpriced_asset_is_skipped_not_zeroed():
    """缺价资产必须登记并跳过——当 0 处理会把成本凭空抹掉。"""
    out = _series(price_map={"BNBUSDT": "600"})       # WLD 无价
    assert out["unpriced_assets"] == ["WLD"]
    assert Decimal(out["totals"]["interest"]) == Decimal("0")
    assert Decimal(out["totals"]["net"]) == Decimal("2.0")   # 少了 1.0 的利息成本


def test_pnl_series_starts_at_an_explicit_zero_point():
    """无零起点时「区间累计 = 末值 − 首值」会把首桶增量当成期初存量扣掉。"""
    out = _series()
    first = out["points"][0]
    assert first[0] == out["points"][1][0] - HOUR
    assert [Decimal(v) for v in first[1:6]] == [Decimal(0)] * 5


def test_pnl_series_marks_points_before_spot_flow_as_partial():
    """现货流水入库前缺现货手续费与滑点两项，净收益偏高，必须标出来。"""
    out = _series(
        interest_rows=[{"accrued_at_ms": _T0 - HOUR, "asset": "WLD", "interest": "0.5"}],
        capital_rows=[{"time_ms": _T0, "flow_type": "TRADING_COMMISSION",
                       "asset": "BNB", "amount": "-0.001"}],
        # 出点节拍是「有资金费结算的小时」，两个待查时刻各补一笔
        income_rows=[{"time_ms": _T0 - HOUR, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "0"}, {"time_ms": _T0, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "0"}],
    )
    assert out["spot_flow_start_ms"] == _T0
    by_t = {p[0]: p[6] for p in out["points"]}
    assert by_t[_T0 - HOUR] == 1     # 现货流水之前
    assert by_t[_T0] == 0            # 起点之后


@pytest.mark.parametrize("direction,kind,spot,perp,expected", [
    # 与前端 computeHedgeSlippagePnl 的四个分支逐一对齐（卖出腿 − 买入腿）
    ("forward", "open", "10", "11", "10"),    # 卖合约买现货
    ("reverse", "open", "11", "10", "10"),    # 卖现货买合约
    ("forward", "close", "11", "10", "10"),   # 平：卖现货买合约
    ("reverse", "close", "10", "11", "10"),   # 平：卖合约买现货
])
def test_slippage_pnl_matches_frontend_branches(direction, kind, spot, perp, expected):
    got = D.slippage_pnl(direction, kind, spot, perp, "10")
    assert got == Decimal(expected)


@pytest.mark.parametrize("spot,perp,qty", [
    (None, "10", "1"), ("10", None, "1"), ("10", "10", None),
    ("0", "10", "1"), ("10", "10", "0"), ("-1", "10", "1"), ("abc", "10", "1"),
])
def test_slippage_pnl_missing_or_nonpositive_is_none_not_zero(spot, perp, qty):
    assert D.slippage_pnl("forward", "open", spot, perp, qty) is None


def test_pnl_series_slippage_lands_on_open_and_close_instants():
    """开单滑点归开仓时刻、平单滑点归平仓时刻——两者可能落在不同的桶。"""
    out = _series(
        interest_rows=[], capital_rows=[],
        income_rows=[{"time_ms": _T0, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "0"}, {"time_ms": _T0 + HOUR, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "0"}],   # 两个待查时刻各补一笔结算才会出点
        close_logs=[{"direction": "forward",
                     "spot_open_avg": "10", "open_avg_price": "11", "open_qty": "10",
                     "spot_close_avg": "11", "close_avg_price": "10", "spot_close_qty": "10",
                     "opened_at_us": _T0 * 1000, "closed_at_us": (_T0 + HOUR) * 1000}],
    )
    by_t = {p[0]: p for p in out["points"]}
    assert Decimal(by_t[_T0][4]) == Decimal("10")            # 开单 +10
    assert Decimal(by_t[_T0 + HOUR][4]) == Decimal("20")     # 累计到平单 +10


# --- 未平仓周期的开仓滑点（评审 2026-08-20 必改项）---------------------------- #
def _open_fill(**over):
    """在持仓周期的一个成交批次（两腿已配对）。"""
    base = {"direction": "forward", "kind": "open", "spot_avg": "10", "perp_avg": "11",
            "qty": "10", "at_ms": _T0, "incomplete": False}
    base.update(over)
    return base


def test_pnl_series_counts_open_cycle_fill_slippage():
    """持仓期间资金费/手续费/利息已进另外三条线，开/平滑点同样要算——当下收益正来自这些持仓。"""
    without = _series(close_logs=[], open_cycle_fills=[])
    with_open = _series(close_logs=[], open_cycle_fills=[_open_fill()])
    assert Decimal(without["totals"]["slippage"]) == Decimal("0")
    assert Decimal(with_open["totals"]["slippage"]) == Decimal("10")   # (11−10)×10
    # 净收益随之下移同样的量，不能只动滑点列
    assert (Decimal(with_open["totals"]["net"]) - Decimal(without["totals"]["net"])
            == Decimal("10"))


def test_pnl_series_open_cycle_fill_slippage_lands_on_fill_instant():
    out = _series(close_logs=[], open_cycle_fills=[_open_fill(at_ms=_T0 - HOUR)],
                  income_rows=[{"time_ms": _T0 - HOUR, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "0"}])   # 待查时刻补一笔结算才会出点
    by_t = {p[0]: p for p in out["points"]}
    assert Decimal(by_t[_T0 - HOUR][4]) == Decimal("10")   # 归到开仓那一桶


@pytest.mark.parametrize("bad", [
    {"incomplete": True},              # 均价不全（spot/perp avg incomplete）
    {"spot_avg": None},                # 缺价
    {"qty": "0"},                      # 数量非正
    {"at_ms": None},            # 缺开仓时刻
])
def test_pnl_series_unusable_open_cycle_fill_is_flagged_not_zeroed(bad):
    """算不出就登记 slippage_incomplete_count，绝不当 0——当 0 会把成本抹掉。"""
    out = _series(close_logs=[], open_cycle_fills=[_open_fill(**bad)])
    assert out["slippage_incomplete_count"] == 1
    assert Decimal(out["totals"]["slippage"]) == Decimal("0")


def test_pnl_series_open_cycle_fills_absent_keeps_counter_zero():
    out = _series(close_logs=[], open_cycle_fills=[])
    assert out["slippage_incomplete_count"] == 0


def test_pnl_series_keeps_bucket_overlapping_unaligned_window_start():
    """窗口起点不落在桶边界时，首个桶不得整桶丢弃（评审 2026-08-20）。"""
    out = D.build_pnl_series(
        interest_rows=[], capital_rows=[], close_logs=[], open_cycle_fills=[],
        income_rows=[{"time_ms": _T0 + 30 * 60_000, "income_type": "FUNDING_FEE",
                      "asset": "USDT", "income": "7"}],
        price_map={}, start_ms=_T0 + 15 * 60_000, end_ms=_T0 + 45 * 60_000,
        bucket_ms=HOUR)
    assert out["points"], "落在未对齐首桶内的流水被整桶丢掉了"
    assert Decimal(out["totals"]["funding"]) == Decimal("7")


def test_pnl_series_ignores_slippage_events_outside_window():
    """close-log 是全量传入（不按时间窗读），窗口外的腿绝不能被算进来。"""
    logs = [{"direction": "forward", "spot_open_avg": "10", "open_avg_price": "11",
             "open_qty": "10", "spot_close_avg": "11", "close_avg_price": "10",
             "spot_close_qty": "10",
             "opened_at_us": (_T0 + 5 * 60_000) * 1000,      # 窗口前
             "closed_at_us": (_T0 + 50 * 60_000) * 1000}]    # 窗口后
    out = _series(interest_rows=[], income_rows=[],
                  capital_rows=[{"time_ms": _T0 + 30 * 60_000, "flow_type": "TRADING_COMMISSION",
                                 "asset": "USDT", "amount": "-1"}],
                  close_logs=logs, open_cycle_fills=[],
                  start_ms=_T0 + 15 * 60_000, end_ms=_T0 + 45 * 60_000)
    assert Decimal(out["totals"]["slippage"]) == Decimal("0")
    # 窗口外的腿不算「算不出」——它只是不属于这个区间
    assert out["slippage_incomplete_count"] == 0


def test_pnl_series_flags_close_log_leg_with_missing_fields():
    """close-log 的价格/数量列允许 NULL：算不出必须留痕，不能静默少计。"""
    logs = [{"direction": "forward", "spot_open_avg": None, "open_avg_price": "11",
             "open_qty": "10", "spot_close_avg": "11", "close_avg_price": "10",
             "spot_close_qty": "10",
             "opened_at_us": _T0 * 1000, "closed_at_us": _T0 * 1000}]
    out = _series(close_logs=logs, open_cycle_fills=[])
    assert out["slippage_incomplete_count"] == 1          # 开仓腿缺现货均价
    assert Decimal(out["totals"]["slippage"]) == Decimal("10")   # 平仓腿仍计入


def test_pnl_series_ignores_open_cycle_fill_outside_window():
    """窗口外的在持仓批次：既不计入滑点，也不算「算不出」（评审第三轮）。"""
    out = _series(close_logs=[], open_cycle_fills=[
        _open_fill(at_ms=_T0 - 5 * HOUR),                    # 窗口外、可算
        _open_fill(at_ms=_T0 - 5 * HOUR, incomplete=True),   # 窗口外、算不出
    ], start_ms=_T0 - HOUR, end_ms=_T0 + HOUR)
    assert Decimal(out["totals"]["slippage"]) == Decimal("0")
    assert out["slippage_incomplete_count"] == 0


def test_pnl_series_counts_unbalanced_fill_but_still_sums_it():
    """两腿量不等（敞口）的滑点**要计入**合计，同时必须计数供脚注标注。

    计入是刻意的：不计入曲线就与历史仓位页分家（close-log 在敞口周期同样按加权
    均价出数）。计数同样刻意：TSTUSDT 现货 7000 / 合约 6500 推出的 +2.28U 静默
    上屏会被当成实测滑点。两条一起锁——去掉任一条都应让本用例红。
    """
    out = _series(close_logs=[], open_cycle_fills=[_open_fill(unbalanced=True)])
    assert Decimal(out["totals"]["slippage"]) == Decimal("10")   # 照常计入
    assert out["slippage_unbalanced_count"] == 1
    assert out["slippage_incomplete_count"] == 0                 # 不是「算不出」


def test_pnl_series_unbalanced_counter_zero_without_flag():
    """未标失衡的批次不得进计数——常驻的警告等于没有警告。"""
    out = _series(close_logs=[], open_cycle_fills=[_open_fill()])
    assert out["slippage_unbalanced_count"] == 0


def test_pnl_series_unusable_unbalanced_fill_counts_only_as_incomplete():
    """算不出的批次不进失衡计数：它根本没进合计，标它失真会误导。"""
    out = _series(close_logs=[], open_cycle_fills=[
        _open_fill(unbalanced=True, incomplete=True)])
    assert out["slippage_incomplete_count"] == 1
    assert out["slippage_unbalanced_count"] == 0


def test_pnl_series_unbalanced_fill_outside_window_not_counted():
    """窗口外的失衡批次不属于本区间，不该让脚注为它报警。"""
    out = _series(close_logs=[], open_cycle_fills=[
        _open_fill(at_ms=_T0 - 5 * HOUR, unbalanced=True)],
        start_ms=_T0 - HOUR, end_ms=_T0 + HOUR)
    assert out["slippage_unbalanced_count"] == 0


def test_pnl_series_counts_unbalanced_open_legs_in_close_log():
    """close-log 固化了开仓两腿量，失衡能判就得判（实测 THEUSDT 现货 600/合约 400）。

    平仓腿只有现货数量列、无合约腿数量，判不了——不为它伪造对比，宁可漏报。
    """
    logs = [{"direction": "forward", "spot_open_avg": "10", "open_avg_price": "11",
             "open_qty": "10", "spot_open_qty": "15",          # 两腿量不等
             "spot_close_avg": "11", "close_avg_price": "10", "spot_close_qty": "10",
             "opened_at_us": _T0 * 1000, "closed_at_us": _T0 * 1000}]
    out = _series(close_logs=logs, open_cycle_fills=[])
    assert out["slippage_unbalanced_count"] == 1        # 开仓腿失衡
    # 开(11−10)×10 + 平(11−10)×10：失衡不改变金额，只加标注
    assert Decimal(out["totals"]["slippage"]) == Decimal("20")


def test_pnl_series_balanced_close_log_open_legs_not_counted():
    logs = [{"direction": "forward", "spot_open_avg": "10", "open_avg_price": "11",
             "open_qty": "10", "spot_open_qty": "10",
             "spot_close_avg": "11", "close_avg_price": "10", "spot_close_qty": "10",
             "opened_at_us": _T0 * 1000, "closed_at_us": _T0 * 1000}]
    assert _series(close_logs=logs, open_cycle_fills=[])["slippage_unbalanced_count"] == 0


def test_pnl_series_close_fill_of_open_cycle_uses_close_branch():
    """在持仓周期上的部分平仓也要算，且走 close 分支（买卖腿与开仓相反）。"""
    opened = _series(close_logs=[], open_cycle_fills=[_open_fill(kind="open")])
    closed = _series(close_logs=[], open_cycle_fills=[_open_fill(kind="close")])
    # forward: open 卖合约(11)买现货(10)=+10；close 卖现货(10)买合约(11)=-10
    assert Decimal(opened["totals"]["slippage"]) == Decimal("10")
    assert Decimal(closed["totals"]["slippage"]) == Decimal("-10")


def test_pnl_series_emits_only_on_funding_settlement_hours():
    """出点节拍 = 有资金费结算的小时（Human 2026-08-20）。两次结算之间的成本
    不丢，累积到下一个结算点；末桶始终保留，否则末值不含最后一段成本。"""
    out = _series(
        income_rows=[
            {"time_ms": _T0, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "1"},
            {"time_ms": _T0 + 4 * HOUR, "income_type": "FUNDING_FEE", "asset": "USDT", "income": "1"},
        ],
        # 中间那两个小时只有利息，不该单独出点，但金额必须累积进下一个结算点
        interest_rows=[{"accrued_at_ms": _T0 + HOUR, "asset": "WLD", "interest": "0.5"},
                       {"accrued_at_ms": _T0 + 2 * HOUR, "asset": "WLD", "interest": "0.5"}],
        capital_rows=[], close_logs=[], open_cycle_fills=[],
        start_ms=0, end_ms=_T0 + 10 * HOUR)
    ts = [p[0] for p in out["points"]]
    assert _T0 + HOUR not in ts and _T0 + 2 * HOUR not in ts, "无结算的小时不该出点"
    assert _T0 in ts and _T0 + 4 * HOUR in ts
    # 两笔利息（0.5 WLD × 2 元 = 1 U 各）累积到第二个结算点
    by_t = {p[0]: p for p in out["points"]}
    assert Decimal(by_t[_T0 + 4 * HOUR][3]) == Decimal("-2")
    assert Decimal(out["totals"]["interest"]) == Decimal("-2")
