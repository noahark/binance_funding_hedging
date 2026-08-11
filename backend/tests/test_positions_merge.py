"""Data-driven tests for the position merge (Task 1 / D14, 11-adr.md ADR-001).

``merge_positions`` is a pure function: it takes ``aggregate_positions`` buckets
and the snapshot's ``private_account`` block and returns merged rows +
``account_meta``. These tests cover the six display scenarios (normal / no_task /
no_um / single_leg / missing / empty), 1000x honest non-alignment, D15
(``includes_deleted_task``), N2 degradation, the P2 drift marker, and JSON
serializability (the handler ``json.dumps`` the rows).
"""
import json
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D


def _bucket(coin, direction, spot_qty="0", perp_qty="0", spot_avg="0",
            perp_avg="0", includes_deleted_task=False, position_qty=None,
            spot_symbol=None, spot_base_asset=None):
    if position_qty is None:
        # forward perp is a SELL -> negative; reverse a BUY -> positive
        position_qty = ("-" + perp_qty) if (direction == D.DIR_FORWARD and perp_qty != "0") else perp_qty
    return {
        "coin": coin, "direction": direction,
        "position_qty": position_qty, "spot_qty": spot_qty, "perp_qty": perp_qty,
        "spot_avg": spot_avg, "perp_avg": perp_avg,
        "spot_avg_price_incomplete": False, "perp_avg_price_incomplete": False,
        "includes_deleted_task": includes_deleted_task,
        "open_basis_rate": "0", "price_pnl": "0", "accrued_funding": "0",
        "borrow_interest": "0", "net_pnl": "0",
        # 步骤③：现货腿身份随 bucket 从 aggregate_positions 带出（有任务记录的行）。
        "spot_symbol": spot_symbol, "spot_base_asset": spot_base_asset,
    }


def _um(symbol, side, amt, unrealized_profit="0", liquidation_price="0"):
    return {
        "symbol": symbol, "position_side": side, "notional_usdt": "100",
        "position_amt": amt, "entry_price": "50000", "mark_price": "50100",
        "unrealized_profit": unrealized_profit, "liquidation_price": liquidation_price,
    }


def _pa(ums=None, spots=None, unifieds=None, verified=True, error=None, checked_at="2026-07-31T00:00:00Z"):
    return {
        "verified": verified, "error": error, "checked_at": checked_at,
        "um_positions": ums or [], "balances_spot": spots or [],
        "balances_unified": unifieds or [],
    }


# --------------------------------------------------------------------------- scenarios


def test_merge_normal_matched_um_and_task():
    # (a) normal: BTCUSDT forward (perp SHORT) — UM + task both present and matched.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
                         spot_avg="50000", perp_avg="50000")]
    pa = _pa(
        ums=[_um("BTCUSDT", "SHORT", "-0.5", unrealized_profit="12.5")],
        spots=[{"asset": "BTC", "free": "0.5", "locked": "0"}],
        unifieds=[{"asset": "BTC", "cross_margin_borrowed": "1000"}],
    )
    merged, meta = D.merge_positions(positions, pa)
    assert meta == {"verified": True, "error": None, "checked_at": "2026-07-31T00:00:00Z"}
    assert len(merged) == 1  # no duplicate: UM and task collapse to ONE row
    r = merged[0]
    assert r["coin"] == "BTCUSDT" and r["direction"] == D.DIR_FORWARD
    assert r["um_position_side"] == "SHORT" and r["um_position_amt"] == "-0.5"
    assert r["spot_balance"] == "0.5" and r["cross_margin_borrowed"] == "1000"
    assert r["price_pnl"] == "12.5"  # real unrealized PnL overlays the "0" placeholder
    assert r["unrealized_profit"] == "12.5"
    assert r["single_leg_exposure"] is False and r["drift"] is False
    assert r["match_status"] == "normal"  # G1: both sides present


def test_merge_no_task_1000x_honest_non_match():
    # (b) a manual 1000x UM position with no task; without an asset_map its base
    # asset (1000PEPE) does NOT auto-align to the spot asset PEPE — honest
    # 'no automatic alignment' (the snapshot-derived asset_map, when provided by
    # the composition root, does align it — see
    # test_merge_1000x_asset_map_aligns).
    pa = _pa(
        ums=[_um("1000PEPEUSDT", "LONG", "1000")],
        spots=[{"asset": "PEPE", "free": "100", "locked": "0"}],
    )
    merged, _ = D.merge_positions([], pa)
    assert len(merged) == 1
    r = merged[0]
    assert r["coin"] == "1000PEPEUSDT" and r["direction"] == D.DIR_REVERSE  # LONG -> reverse
    assert r["um_position_amt"] == "1000"
    assert r["spot_balance"] is None  # 1000PEPE != PEPE, no fabricated alignment
    assert r["cross_margin_borrowed"] is None
    assert r["match_status"] == "no_task"  # G1: UM present, no task record
    # G2: no local bookkeeping -> cost basis is unknown (None), NOT a fake "0"
    assert r["spot_avg"] is None and r["perp_avg"] is None
    assert r["spot_qty"] is None and r["perp_qty"] is None and r["position_qty"] is None


def test_merge_normal_symbol_aligns_to_spot():
    # corollary: a normal (non-1000x) symbol DOES align — PEPEUSDT -> PEPE.
    pa = _pa(
        ums=[_um("PEPEUSDT", "LONG", "100")],
        spots=[{"asset": "PEPE", "free": "100", "locked": "0"}],
    )
    merged, _ = D.merge_positions([], pa)
    assert merged[0]["spot_balance"] == "100"


def test_merge_no_um_task_only():
    # (c) task recorded a fill but the exchange has no UM position (possibly
    # liquidated / manually closed). Cost basis still shows; UM fields null.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
                         spot_avg="50000", perp_avg="50000")]
    merged, _ = D.merge_positions(positions, _pa())
    assert len(merged) == 1
    r = merged[0]
    assert r["coin"] == "BTCUSDT"
    assert r["um_position_amt"] is None and r["um_position_side"] is None
    assert r["spot_avg"] == "50000" and r["perp_avg"] == "50000"
    assert r["match_status"] == "no_um"  # G1: task record, no UM position


def test_merge_single_leg_exposure():
    # (d) the task filled its spot leg but not its perp leg (one orderId).
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0",
                         spot_avg="50000", perp_avg="0")]
    merged, _ = D.merge_positions(positions, _pa())
    assert merged[0]["single_leg_exposure"] is True
    assert merged[0]["match_status"] == "no_um"  # bucket present, no UM (single_leg is a separate marker)


def test_merge_exposure_flags_perp_only_naked_short():
    """裸空（合约腿在、现货腿没有）此前完全不报——旧判定只写了 spot>0 且 perp==0
    一个方向。裸空的风险上不封顶，是这个标记最该抓的形态。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0", perp_qty="0.5",
                         spot_avg="0", perp_avg="50000")]
    merged, _ = D.merge_positions(positions, _pa())
    assert merged[0]["single_leg_exposure"] is True


def test_merge_exposure_flags_partial_imbalance():
    """部分失衡（现货 2 / 合约 1）此前读作「无敞口」——旧判定要求合约腿完全为 0。
    一腿部分成交、或平仓平到一半中断，正是最容易落到这个形态的场合。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="2", perp_qty="1",
                         spot_avg="50000", perp_avg="50000")]
    merged, _ = D.merge_positions(positions, _pa())
    assert merged[0]["single_leg_exposure"] is True


def test_merge_exposure_tolerates_sub_one_percent_drift():
    """两腿本应恒等（同一个 q_common 发两腿）。留 1% 容差只为吸收精度/舍入，
    不该把它当成「允许 1% 敞口」——真实单腿至少是一整组的量级。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="1.000", perp_qty="0.995",
                         spot_avg="50000", perp_avg="50000")]
    merged, _ = D.merge_positions(positions, _pa())
    assert merged[0]["single_leg_exposure"] is False


def test_merge_exposure_false_for_no_task_row():
    """no_task 行（交易所有仓、本地无任务记录）两腿记账都是 0，不得据此报敞口——
    那是「不知道」，不是「已对平」。"""
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")])
    merged, _ = D.merge_positions([], pa)
    assert merged[0]["match_status"] == "no_task"
    assert merged[0]["single_leg_exposure"] is False


def test_merge_missing_sentinel_values():
    # (e) account verified but figures missing: liquidation_price "0" sentinel
    # preserved, unrealized_profit None. R2 (fix-merged-positions-n2-ui-v1): a
    # missing upnl must NOT paint the "0" placeholder as a real PnL — price_pnl is
    # None (missing), and a true "0" upnl stays a real figure (distinguishable).
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
                         spot_avg="50000", perp_avg="50000")]
    pa_missing = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5", unrealized_profit=None,
                              liquidation_price="0")])
    r = D.merge_positions(positions, pa_missing)[0][0]
    assert r["um_liquidation_price"] == "0"  # sentinel preserved verbatim, not dropped
    assert r["unrealized_profit"] is None
    assert r["price_pnl"] is None  # missing -> None, NOT the "0" placeholder
    # a true "0" upnl is a real figure and must be distinguishable from missing
    pa_zero = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5", unrealized_profit="0",
                           liquidation_price="0")])
    r0 = D.merge_positions(positions, pa_zero)[0][0]
    assert r0["price_pnl"] == "0" and r0["unrealized_profit"] == "0"


def test_merge_empty():
    # (f) nothing on either side.
    merged, meta = D.merge_positions([], _pa())
    assert merged == []
    assert meta["verified"] is True


def test_merge_no_duplicate_when_um_and_task_match():
    # When a UM position and a task bucket match on (symbol, side), they collapse
    # to a single row; a second task bucket for a symbol with no UM is a separate
    # no_um row. No duplicate rows.
    positions = [
        _bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5"),
        _bucket("ETHUSDT", D.DIR_FORWARD, spot_qty="0.2", perp_qty="0.2"),
    ]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")])  # only BTCUSDT has a UM position
    merged, _ = D.merge_positions(positions, pa)
    coins = [r["coin"] for r in merged]
    assert coins.count("BTCUSDT") == 1 and coins.count("ETHUSDT") == 1
    btc = next(r for r in merged if r["coin"] == "BTCUSDT")
    eth = next(r for r in merged if r["coin"] == "ETHUSDT")
    assert btc["um_position_amt"] == "-0.5"     # matched
    assert eth["um_position_amt"] is None        # no_um row


# --------------------------------------------------------------------------- degradation (N2)


def test_merge_degradation_private_account_none():
    # SnapshotNotReady / stub with no private_account: local rows still return,
    # account-derived fields nulled, account_meta reports the cause. No exception.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    merged, meta = D.merge_positions(positions, None)
    assert meta == {"verified": False, "error": "snapshot_not_ready", "checked_at": None}
    r = merged[0]
    assert r["um_position_amt"] is None and r["spot_balance"] is None
    assert r["coin"] == "BTCUSDT"  # local bookkeeping row still present


def test_merge_degradation_unverified_carries_error():
    # F-D: private_account present but verified=false (e.g. private_channel_disabled).
    # Account fields nulled, but the real error/checked_at propagate.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = {"verified": False, "error": "private_channel_disabled",
          "checked_at": "2026-07-31T00:00:00Z", "um_positions": [], "balances_spot": []}
    merged, meta = D.merge_positions(positions, pa)
    assert meta["verified"] is False
    assert meta["error"] == "private_channel_disabled"
    assert meta["checked_at"] == "2026-07-31T00:00:00Z"
    assert merged[0]["um_position_amt"] is None


# --------------------------------------------------------------------------- D15 / drift


def test_merge_d15_includes_deleted_task_passes_through():
    # A bucket flagged includes_deleted_task (D15) keeps the flag on the merged row.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
                         includes_deleted_task=True)]
    merged, _ = D.merge_positions(positions, _pa())
    assert merged[0]["includes_deleted_task"] is True


def test_merge_drift_marker_real_less_than_recorded():
    # P2: the real spot balance (0.2) is less than the recorded accumulation (0.5)
    # -> the operator manually reduced the hedge's spot leg -> drift flagged.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             spots=[{"asset": "BTC", "free": "0.2", "locked": "0"}])
    merged, _ = D.merge_positions(positions, pa)
    assert merged[0]["drift"] is True


def test_merge_no_drift_when_real_exceeds_recorded():
    # Extra deposit (real > recorded) is NOT risk-relevant -> not flagged.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             spots=[{"asset": "BTC", "free": "0.8", "locked": "0"}])
    merged, _ = D.merge_positions(positions, pa)
    assert merged[0]["drift"] is False


def test_merge_drift_counts_the_unified_account():
    """现货腿按 spot_route 落在两个账户之一：bStock / cap 打满走普通现货，其余走
    统一杠杆。旧判定只看普通现货账户，于是对绝大多数币恒为假阴性——「没报 drift」
    被读成「记账与实际相符」，而实际上这个检查根本没在看那个账户。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             unifieds=[{"asset": "BTC", "total_balance": "0.3"}])
    merged, _ = D.merge_positions(positions, pa)
    assert merged[0]["drift"] is True  # 统一账户只剩 0.3 < 记账 0.5


def test_merge_drift_sums_both_accounts():
    """两个账户之和达标就不算漂移：持仓可能一部分在普通现货、一部分在统一账户
    （平仓补足会在两者间划转），只看单边会误报。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             spots=[{"asset": "BTC", "free": "0.2", "locked": "0"}],
             unifieds=[{"asset": "BTC", "total_balance": "0.3"}])
    merged, _ = D.merge_positions(positions, pa)
    assert merged[0]["drift"] is False  # 0.2 + 0.3 == 0.5


def test_merge_no_drift_when_account_unreadable():
    """账户读不到时绝不报 drift。两个余额表在 verified=false 下都是空的，若照常
    求和就会把「读不到」算成 0，给每一行印一个假的漂移告警——正是 F4 那类错误。"""
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    merged, _ = D.merge_positions(positions, _pa(verified=False))
    assert merged[0]["drift"] is False


def _reverse_pa(*, borrowed="100", free="0", locked="0", verified=True):
    return _pa(
        verified=verified,
        unifieds=[{
            "asset": "BTC", "total_balance": "0",
            "cross_margin_borrowed": borrowed,
            "cross_margin_free": free,
            "cross_margin_locked": locked,
            "cross_margin_interest": "999",
        }],
    )


@pytest.mark.parametrize(
    "borrowed,free,locked,expected",
    [
        ("100", "0", "0", False),       # borrowed and sold: A=R=100
        ("100", "100", "0", True),      # borrowed but unsold
        ("100", "0", "100", True),      # pending sell remains locked
        ("100", "30", "0", True),       # partial fill: A=70
        ("100", "1", "0", False),       # exactly 1% shortage
        ("100", "1.001", "0", True),    # strictly more than 1%
    ],
)
def test_merge_reverse_drift_uses_borrowed_minus_free_and_locked(
    borrowed, free, locked, expected,
):
    positions = [_bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty="100", perp_qty="100",
        spot_base_asset="BTC",
    )]
    merged, _ = D.merge_positions(positions, _reverse_pa(
        borrowed=borrowed, free=free, locked=locked,
    ))
    assert merged[0]["drift"] is expected


def test_merge_reverse_drift_excludes_account_and_local_interest():
    position = _bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty="100", perp_qty="100",
        spot_base_asset="BTC",
    )
    position["borrow_interest"] = "12345"
    pa = _reverse_pa()
    pa["balances_unified"][0]["cross_margin_interest"] = "67890"
    assert D.merge_positions([position], pa)[0][0]["drift"] is False


def test_merge_reverse_drift_groups_same_asset_once():
    positions = []
    for cycle_id, qty in (("cycle-a", "60"), ("cycle-b", "40")):
        row = _bucket(
            "BTCUSDT", D.DIR_REVERSE, spot_qty=qty, perp_qty=qty,
            spot_base_asset="BTC",
        )
        row.update({
            "cycle_id": cycle_id,
            "cycle_opened_at": cycle_id,
            "cycle_closed_at": None,
        })
        positions.append(row)

    matched = D.merge_positions(positions, _reverse_pa())[0]
    short = D.merge_positions(positions, _reverse_pa(borrowed="70"))[0]
    assert [row["drift"] for row in matched] == [False, False]
    assert [row["drift"] for row in short] == [True, True]


@pytest.mark.parametrize(
    "field,bad",
    [
        (field, bad)
        for field in (
            "cross_margin_borrowed", "cross_margin_free", "cross_margin_locked",
        )
        for bad in (None, "", "text", "NaN", "Infinity", "-1")
    ],
)
def test_merge_reverse_drift_rejects_invalid_account_quantities(field, bad):
    pa = _reverse_pa(free="100")  # valid data would prove a drift
    if bad is None:
        pa["balances_unified"][0].pop(field)
    else:
        pa["balances_unified"][0][field] = bad
    position = _bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty="100", perp_qty="100",
        spot_base_asset="BTC",
    )
    assert D.merge_positions([position], pa)[0][0]["drift"] is False


@pytest.mark.parametrize("spot_qty", [None, "", "text", "NaN", "Infinity", "-1"])
def test_merge_reverse_drift_rejects_invalid_local_spot_qty(spot_qty):
    position = _bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty=spot_qty, perp_qty="100",
        spot_base_asset="BTC",
    )
    assert D.merge_positions([position], _reverse_pa(free="100"))[0][0]["drift"] is False


def test_merge_reverse_drift_excludes_closed_and_no_task_rows():
    closed = _bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty="100", perp_qty="100",
        spot_base_asset="BTC",
    )
    closed["cycle_closed_at"] = "2026-08-11T00:00:00Z"
    pa = _reverse_pa(free="100")
    pa["um_positions"] = [_um("BTCUSDT", "LONG", "100")]
    merged, _ = D.merge_positions([closed], pa)
    assert {row["match_status"] for row in merged} == {"no_task", "no_um"}
    assert all(row["drift"] is False for row in merged)


def test_merge_reverse_drift_false_when_account_unreadable():
    position = _bucket(
        "BTCUSDT", D.DIR_REVERSE, spot_qty="100", perp_qty="100",
        spot_base_asset="BTC",
    )
    assert D.merge_positions([position], _reverse_pa(verified=False))[0][0]["drift"] is False


@pytest.mark.parametrize(
    "spot,unified,expected",
    [("0.2", "0.2", True), ("0.2", "0.3", False), ("0.2", "0.4", False)],
)
def test_merge_forward_drift_ignores_reverse_account_fields(spot, unified, expected):
    positions = [_bucket(
        "BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
        spot_base_asset="BTC",
    )]
    pa = _pa(
        spots=[{"asset": "BTC", "free": spot, "locked": "0"}],
        unifieds=[{
            "asset": "BTC", "total_balance": unified,
            "cross_margin_borrowed": "999", "cross_margin_free": "888",
            "cross_margin_locked": "777",
        }],
    )
    assert D.merge_positions(positions, pa)[0][0]["drift"] is expected


# --------------------------------------------------------------------------- contract


def test_merge_rows_are_json_serializable():
    # The handler json.dumps the rows; no Decimal / non-native type may leak.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5",
                         spot_avg="50000", perp_avg="50000", includes_deleted_task=True)]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5", unrealized_profit="12.5",
                      liquidation_price="0")],
             spots=[{"asset": "BTC", "free": "0.2", "locked": "0"}],
             unifieds=[{"asset": "BTC", "cross_margin_borrowed": "1000"}])
    merged, meta = D.merge_positions(positions, pa)
    # must not raise
    json.dumps({"positions": merged, "account": meta})


# ---------------------------------------------------------------------------
# v4.1 §9.2 — four account-derived balance fields on every merged row
# (spot_balance / spot_balance_value_usdt / unified_balance /
#  unified_balance_value_usdt). Pure projection of the same published
# private_account rows; no price recompute; cross_margin_borrowed stays
# borrow-only; null vs a real decimal-string zero preserved per side.


def test_merge_four_account_fields_normal_same_coin_mapped():
    # Normal: BTCUSDT forward (perp SHORT). Spot + unified both carry BTC with
    # their existing amount and value_usdt — projected verbatim, no recompute.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(
        ums=[_um("BTCUSDT", "SHORT", "-0.5")],
        spots=[{"asset": "BTC", "free": "0.5", "locked": "0",
                "value_usdt": "30000.00000000"}],
        unifieds=[{"asset": "BTC", "total_balance": "100",
                   "cross_margin_borrowed": "10",
                   "value_usdt": "60000.00000000"}],
    )
    r = D.merge_positions(positions, pa)[0][0]
    assert r["spot_balance"] == "0.5"
    assert r["spot_balance_value_usdt"] == "30000.00000000"
    assert r["unified_balance"] == "100"
    assert r["unified_balance_value_usdt"] == "60000.00000000"
    # cross_margin_borrowed stays the borrow, NOT the unified balance.
    assert r["cross_margin_borrowed"] == "10"


def test_merge_four_account_fields_unified_missing_side_is_null():
    # Spot has BTC but the unified account has no BTC row: only the unified side
    # is null; the spot side keeps its amount/value.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(
        ums=[_um("BTCUSDT", "SHORT", "-0.5")],
        spots=[{"asset": "BTC", "free": "0.5", "locked": "0",
                "value_usdt": "30000.00000000"}],
        unifieds=[{"asset": "ETH", "total_balance": "2", "value_usdt": "6000"}],
    )
    r = D.merge_positions(positions, pa)[0][0]
    assert r["spot_balance"] == "0.5" and r["spot_balance_value_usdt"] == "30000.00000000"
    assert r["unified_balance"] is None and r["unified_balance_value_usdt"] is None


def test_merge_four_account_fields_spot_missing_side_is_null():
    # Unified has BTC but spot has no BTC row: only the spot side is null.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(
        ums=[_um("BTCUSDT", "SHORT", "-0.5")],
        spots=[{"asset": "ETH", "free": "1", "locked": "0", "value_usdt": "3000"}],
        unifieds=[{"asset": "BTC", "total_balance": "100",
                   "value_usdt": "60000.00000000"}],
    )
    r = D.merge_positions(positions, pa)[0][0]
    assert r["unified_balance"] == "100" and r["unified_balance_value_usdt"] == "60000.00000000"
    assert r["spot_balance"] is None and r["spot_balance_value_usdt"] is None


def test_merge_four_account_fields_all_null_when_not_verified():
    # private_account verified=false -> all four account fields null on every row
    # (the local bookkeeping row is still returned).
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(
        verified=False, error="private_channel_disabled",
        spots=[{"asset": "BTC", "free": "0.5", "locked": "0", "value_usdt": "30000"}],
        unifieds=[{"asset": "BTC", "total_balance": "100", "value_usdt": "60000"}],
    )
    r = D.merge_positions(positions, pa)[0][0]
    assert r["spot_balance"] is None
    assert r["spot_balance_value_usdt"] is None
    assert r["unified_balance"] is None
    assert r["unified_balance_value_usdt"] is None


def test_merge_four_account_fields_true_zero_stays_string_not_null():
    # A valid zero amount/value stays a decimal string, never degraded to null.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0", perp_qty="0")]
    pa = _pa(
        spots=[{"asset": "BTC", "free": "0", "locked": "0", "value_usdt": "0.00000000"}],
        unifieds=[{"asset": "BTC", "total_balance": "0",
                   "value_usdt": "0.00000000"}],
    )
    r = D.merge_positions(positions, pa)[0][0]
    assert r["spot_balance"] == "0"
    assert r["spot_balance_value_usdt"] == "0.00000000"
    assert r["unified_balance"] == "0"
    assert r["unified_balance_value_usdt"] == "0.00000000"


def test_merge_four_account_fields_1000x_not_auto_aligned():
    # Without an asset_map, 1000PEPEUSDT does NOT align to the PEPE spot/unified
    # asset (legacy non-goal #5): all four account fields are null for the 1000x
    # row. With the asset_map they align (test_merge_1000x_asset_map_aligns).
    pa = _pa(
        ums=[_um("1000PEPEUSDT", "LONG", "1000")],
        spots=[{"asset": "PEPE", "free": "100", "locked": "0", "value_usdt": "1"}],
        unifieds=[{"asset": "PEPE", "total_balance": "100", "value_usdt": "1"}],
    )
    r = D.merge_positions([], pa)[0][0]
    assert r["spot_balance"] is None
    assert r["spot_balance_value_usdt"] is None
    assert r["unified_balance"] is None
    assert r["unified_balance_value_usdt"] is None


def test_merge_1000x_asset_map_aligns():
    # The composition root passes the snapshot's resolved spot base_asset
    # (1000BONKUSDT -> BONK) as asset_map; the 1000x row then aligns to the
    # BONK spot/unified balances.
    pa = _pa(
        ums=[_um("1000BONKUSDT", "LONG", "1000")],
        spots=[{"asset": "BONK", "free": "100", "locked": "0", "value_usdt": "1"}],
        unifieds=[{"asset": "BONK", "total_balance": "100", "value_usdt": "1"}],
    )
    r = D.merge_positions([], pa, asset_map={"1000BONKUSDT": "BONK"})[0][0]
    assert r["spot_balance"] == "100"
    assert r["spot_balance_value_usdt"] == "1"
    assert r["unified_balance"] == "100"
    assert r["unified_balance_value_usdt"] == "1"


def test_merge_bstock_asset_map_aligns_spot():
    # Q1 case: SNXXUSDT (bStock) with a real active cycle; the snapshot's
    # resolved spot base_asset SNXXB aligns the row to the SNXXB spot balance.
    positions = [_bucket("SNXXUSDT", D.DIR_FORWARD, spot_qty="1.0", perp_qty="1.0")]
    pa = _pa(
        ums=[_um("SNXXUSDT", "SHORT", "-1.0")],
        spots=[{"asset": "SNXXB", "free": "1.0", "locked": "0",
                "value_usdt": "10.33"}],
        unifieds=[{"asset": "SNXXB", "total_balance": "1.0", "value_usdt": "10.33"}],
    )
    merged, _ = D.merge_positions(positions, pa, asset_map={"SNXXUSDT": "SNXXB"})
    r = merged[0]
    assert r["spot_balance"] == "1"          # fmt_decimal(Decimal('1.0'))
    assert r["spot_balance_value_usdt"] == "10.33"
    assert r["unified_balance"] == "1.0"     # total_balance passed through verbatim
    assert r["cross_margin_borrowed"] is None


def test_merge_asset_map_missing_coin_falls_back():
    # A coin absent from the asset_map falls back to the local rule (today's
    # behaviour) — a cold snapshot / missing spot row introduces no new state.
    pa = _pa(
        ums=[_um("PEPEUSDT", "LONG", "100")],
        spots=[{"asset": "PEPE", "free": "100", "locked": "0"}],
    )
    r = D.merge_positions([], pa, asset_map={"BTCUSDT": "BTC"})[0][0]
    assert r["spot_balance"] == "100"  # PEPEUSDT -> PEPE via the local rule


def test_merge_asset_map_normal_coin_unchanged():
    # A normal coin with an asset_map entry behaves identically to the fallback.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             spots=[{"asset": "BTC", "free": "0.5", "locked": "0"}])
    r = D.merge_positions(positions, pa, asset_map={"BTCUSDT": "BTC"})[0][0]
    assert r["spot_balance"] == "0.5"
    assert r["single_leg_exposure"] is False
    assert r["drift"] is False


def test_merge_does_not_mutate_source_private_account():
    # The projection must not alter the input private_account rows.
    positions = [_bucket("BTCUSDT", D.DIR_FORWARD, spot_qty="0.5", perp_qty="0.5")]
    spot_row = {"asset": "BTC", "free": "0.5", "locked": "0", "value_usdt": "30000"}
    unified_row = {"asset": "BTC", "total_balance": "100",
                   "cross_margin_borrowed": "10", "value_usdt": "60000"}
    pa = _pa(ums=[_um("BTCUSDT", "SHORT", "-0.5")],
             spots=[spot_row], unifieds=[unified_row])
    D.merge_positions(positions, pa)
    assert spot_row == {"asset": "BTC", "free": "0.5", "locked": "0", "value_usdt": "30000"}
    assert unified_row == {"asset": "BTC", "total_balance": "100",
                           "cross_margin_borrowed": "10", "value_usdt": "60000"}



# ---------------------------------------------------------------------------
# 展示环消费固化身份（symbol-identity-unification 步骤③，测试 5/6/7）
# ---------------------------------------------------------------------------

def test_merge_bstock_uses_frozen_identity_without_asset_map():
    """测试 5：有任务记录的行读 bucket 里的固化身份，不依赖快照 asset_map。

    这是 Q1 的正解：此前 merge 用 _merge_base_asset(coin) 只剥 USDT，
    SNXXUSDT -> SNXX，而账户里的资产是 SNXXB，于是 bStock 现货余额恒为 null。
    """
    positions = [_bucket("SNXXUSDT", D.DIR_FORWARD, spot_qty="1", perp_qty="1",
                         spot_symbol="SNXXBUSDT", spot_base_asset="SNXXB")]
    pa = _pa(
        ums=[_um("SNXXUSDT", "SHORT", "-1")],
        spots=[{"asset": "SNXXB", "free": "1", "locked": "0", "value_usdt": "10.33"}],
    )
    # 不传 asset_map —— 快照未就绪时也必须正确
    merged, _ = D.merge_positions(positions, pa)
    r = merged[0]
    assert r["spot_balance"] == "1"
    assert r["spot_balance_value_usdt"] == "10.33"
    # drift 判定依赖 real_spot，身份对了它才有意义（真实余额 1 == 记账 1 -> 无漂移）
    assert r["drift"] is False


def test_merge_multiplier_uses_frozen_identity_without_asset_map():
    positions = [_bucket("1000BONKUSDT", D.DIR_FORWARD, spot_qty="1000", perp_qty="1",
                         spot_symbol="BONKUSDT", spot_base_asset="BONK")]
    pa = _pa(
        ums=[_um("1000BONKUSDT", "SHORT", "-1")],
        spots=[{"asset": "BONK", "free": "1000", "locked": "0", "value_usdt": "20"}],
    )
    merged, _ = D.merge_positions(positions, pa)
    assert merged[0]["spot_balance"] == "1000"


def test_merge_no_task_row_still_uses_asset_map():
    """测试 6：no_task 行（UM 有仓、无任务记录）没有固化列，仍走 asset_map。"""
    pa = _pa(
        ums=[_um("SNXXUSDT", "SHORT", "-1")],
        spots=[{"asset": "SNXXB", "free": "1", "locked": "0", "value_usdt": "10.33"}],
    )
    merged, _ = D.merge_positions([], pa, {"SNXXUSDT": "SNXXB"})
    r = merged[0]
    assert r["match_status"] == "no_task"
    assert r["spot_balance"] == "1"


def test_merge_no_task_and_no_asset_map_falls_back_without_crashing():
    """测试 7：无任务记录且快照未就绪 → 回退旧规则，诚实地取不到，但不崩。"""
    pa = _pa(
        ums=[_um("SNXXUSDT", "SHORT", "-1")],
        spots=[{"asset": "SNXXB", "free": "1", "locked": "0"}],
    )
    merged, _ = D.merge_positions([], pa)
    r = merged[0]
    assert r["match_status"] == "no_task"
    assert r["spot_balance"] is None  # SNXX != SNXXB，不臆造对齐


def test_merge_frozen_identity_beats_asset_map_when_both_present():
    # 固化值优先于快照：任务的历史真值不该被当前快照覆盖。
    positions = [_bucket("SNXXUSDT", D.DIR_FORWARD, spot_qty="1", perp_qty="1",
                         spot_symbol="SNXXBUSDT", spot_base_asset="SNXXB")]
    pa = _pa(
        ums=[_um("SNXXUSDT", "SHORT", "-1")],
        spots=[{"asset": "SNXXB", "free": "1", "locked": "0"},
               {"asset": "WRONG", "free": "999", "locked": "0"}],
    )
    merged, _ = D.merge_positions(positions, pa, {"SNXXUSDT": "WRONG"})
    assert merged[0]["spot_balance"] == "1"  # 用固化的 SNXXB，不是 asset_map 的 WRONG
