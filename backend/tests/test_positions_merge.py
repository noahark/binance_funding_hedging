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

from backend.hedge_open_tasks import domain as D


def _bucket(coin, direction, spot_qty="0", perp_qty="0", spot_avg="0",
            perp_avg="0", includes_deleted_task=False, position_qty=None):
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
    # (b) a manual 1000x UM position with no task; its base asset (1000PEPE) does
    # NOT auto-align to the spot asset PEPE — honest 'no automatic alignment'.
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
