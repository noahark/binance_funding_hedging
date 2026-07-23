"""Pure domain tests for backend/hedge_open_tasks/domain.py.

No SQLite, no HTTP, no network. Covers the round-1 frozen logic: direction
mapping (ADR-3), common-grid lcm rounding incl. mismatched steps (ADR-2),
preflight accept/reject incl. insufficient balance and filter violations
(10-design §5), single-leg classification (ADR-4), the >3-fail termination +
status transitions, and the carried-forward validation/encoding helpers.
Filter fixtures mirror the real public BTCUSDT samples captured in
reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md
(never hardcoded into production code — read per attempt in live mode).
"""
from __future__ import annotations

import pytest
from decimal import Decimal

from backend.hedge_open_tasks import domain as D


# ---------------------------------------------------------------------------
# Fixtures mirroring the real BTCUSDT public exchangeInfo samples (recon §C)
# ---------------------------------------------------------------------------

def spot_filters_btcusdt() -> dict:
    # spot: LOT_SIZE step 0.00001; MARKET_LOT_SIZE stepSize=0 (disabled);
    # NOTIONAL.minNotional=5, applyMinToMarket=true.
    return {
        "lot_size": {"min_qty": "0.00001", "max_qty": "9000", "step_size": "0.00001"},
        "market_lot_size": {"min_qty": "0", "max_qty": "9000", "step_size": "0"},
        "notional": {"min_notional": "5", "apply_min_to_market": True},
    }


def perp_filters_btcusdt() -> dict:
    # USDⓈ-M: LOT_SIZE step 0.001; MARKET_LOT_SIZE min/step 0.001 max 120;
    # MIN_NOTIONAL.notional=50.
    return {
        "lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
        "market_lot_size": {"min_qty": "0.001", "max_qty": "120", "step_size": "0.001"},
        "notional": {"notional": "50"},
    }


def snapshot(*, balances, position_mode="BOTH", est_price="50000", spot=None, perp=None):
    return D.PreflightSnapshot(
        spot_filters=spot or spot_filters_btcusdt(),
        perp_filters=perp or perp_filters_btcusdt(),
        balances=balances,
        position_mode=position_mode,
        est_price=Decimal(est_price) if est_price else None,
    )


# ---------------------------------------------------------------------------
# Direction mapping (ADR-3)
# ---------------------------------------------------------------------------

def test_direction_mapping_forward_one_way():
    a = D.direction_to_leg_actions(D.DIR_FORWARD, D.POS_MODE_BOTH)
    assert a.spot_side == "BUY"
    assert a.perp_side == "SELL"
    assert a.perp_position_side == "BOTH"
    assert a.spot_side_effect == "NO_SIDE_EFFECT"


def test_direction_mapping_forward_hedge():
    a = D.direction_to_leg_actions(D.DIR_FORWARD, D.POS_MODE_HEDGE)
    assert a.spot_side == "BUY"
    assert a.perp_side == "SELL"
    assert a.perp_position_side == "SHORT"


def test_direction_mapping_reverse_one_way():
    a = D.direction_to_leg_actions(D.DIR_REVERSE, D.POS_MODE_BOTH)
    assert a.spot_side == "SELL"
    assert a.perp_side == "BUY"
    assert a.perp_position_side == "BOTH"


def test_direction_mapping_reverse_hedge():
    a = D.direction_to_leg_actions(D.DIR_REVERSE, D.POS_MODE_HEDGE)
    assert a.spot_side == "SELL"
    assert a.perp_side == "BUY"
    assert a.perp_position_side == "LONG"


# ---------------------------------------------------------------------------
# Common-grid rounding (ADR-2 — correctness-critical)
# ---------------------------------------------------------------------------

def test_decimal_lcm_equal_steps():
    assert D.decimal_lcm(Decimal("0.001"), Decimal("0.001")) == Decimal("0.001")


def test_decimal_lcm_mismatched_steps_btcusdt():
    # spot step 0.00001 vs perp step 0.001 -> common grid 0.001 (perp step is a
    # whole multiple of the spot step). Independent per-leg rounding would yield
    # unequal legs -> manufactured exposure; the lcm avoids that.
    assert D.decimal_lcm(Decimal("0.00001"), Decimal("0.001")) == Decimal("0.001")


def test_decimal_lcm_coprime_units():
    # 0.5 = 50 x 0.01 ; 0.25 = 25 x 0.01 ; lcm(50,25)=50 -> 0.5
    assert D.decimal_lcm(Decimal("0.5"), Decimal("0.25")) == Decimal("0.5")


def test_decimal_lcm_integer_steps():
    assert D.decimal_lcm(Decimal("1"), Decimal("2")) == Decimal("2")


def test_floor_to_grid_truncates_down():
    assert D.floor_to_grid(Decimal("0.123456"), Decimal("0.001")) == Decimal("0.123")
    assert D.floor_to_grid(Decimal("0.999"), Decimal("0.25")) == Decimal("0.75")


def test_effective_market_step_uses_lot_when_market_disabled():
    # spot MARKET_LOT_SIZE step=0 -> fall back to LOT_SIZE step 0.00001.
    assert D.effective_market_step(spot_filters_btcusdt()) == Decimal("0.00001")


def test_effective_market_step_uses_market_when_enabled():
    # perp MARKET_LOT_SIZE step=0.001 -> use it.
    assert D.effective_market_step(perp_filters_btcusdt()) == Decimal("0.001")


# ---------------------------------------------------------------------------
# Preflight (10-design §5)
# ---------------------------------------------------------------------------

def test_preflight_forward_accept():
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("100000")}),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 3,
    )
    assert pf.rejection is None
    assert pf.q_common == Decimal("0.5")
    assert pf.position_side_mode == "BOTH"
    assert pf.balance_ok is True


def test_preflight_forward_insufficient_usdt():
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("50000")}),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 3,
    )
    assert pf.rejection == D.REJECT_INSUFFICIENT_BALANCE
    assert pf.required == Decimal("75000")   # 0.5 * 3 * 50000
    assert pf.available == Decimal("50000")
    assert pf.balance_ok is False


def test_preflight_reverse_accept():
    pf = D.compute_preflight(
        snapshot(balances={"BTC": Decimal("2")}),
        "BTCUSDT", D.DIR_REVERSE, Decimal("0.5"), 3,
    )
    assert pf.rejection is None
    assert pf.q_common == Decimal("0.5")
    assert pf.required == Decimal("1.5")     # 0.5 * 3 base
    assert pf.balance_ok is True


def test_preflight_reverse_insufficient_base():
    pf = D.compute_preflight(
        snapshot(balances={"BTC": Decimal("1")}),
        "BTCUSDT", D.DIR_REVERSE, Decimal("0.5"), 3,
    )
    assert pf.rejection == D.REJECT_INSUFFICIENT_BALANCE
    assert pf.required == Decimal("1.5")
    assert pf.available == Decimal("1")


def test_preflight_below_min_qty_when_amount_under_grid():
    # 0.0005 floored onto grid 0.001 -> 0 -> below min qty.
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("100000")}),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.0005"), 1,
    )
    assert pf.rejection == D.REJECT_BELOW_MIN_QTY


def test_preflight_below_min_notional():
    # q_common 0.001 at price 100 -> notional 0.1 < 50 -> below min notional.
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("100000")}, est_price="100"),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.001"), 1,
    )
    assert pf.rejection == D.REJECT_BELOW_MIN_NOTIONAL


def test_preflight_snapshot_none_is_dry_run_unknown():
    # No live preflight data (dry-run) -> unknown, never a rejection, so a task
    # can still be created to exercise the record transport.
    pf = D.compute_preflight(None, "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 3)
    assert pf.rejection is None
    assert pf.q_common is None
    assert pf.balance_ok is None
    assert pf.snapshot_record["available"] is False


def test_preflight_step_unreadable_rejects():
    bad = {
        "lot_size": {"step_size": "0"},
        "market_lot_size": {"step_size": "0"},
        "notional": {},
    }
    pf = D.compute_preflight(
        D.PreflightSnapshot(
            spot_filters=bad, perp_filters=perp_filters_btcusdt(),
            balances={"USDT": Decimal("100000")}, position_mode="BOTH",
            est_price=Decimal("50000"),
        ),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 1,
    )
    assert pf.rejection == D.REJECT_BELOW_MIN_QTY


# ---------------------------------------------------------------------------
# Single-leg classification (ADR-4)
# ---------------------------------------------------------------------------

def _leg(status, qty, price="50000"):
    return {"status": status, "filled_qty": qty, "avg_price": price, "order_id": "x"}


def test_classify_both_filled_aligned_is_success():
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("FILLED", "0.5")) == D.ATTEMPT_SUCCESS


def test_classify_one_filled_one_rejected_is_exposure():
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("REJECTED", "0")) == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert D.classify_attempt(_leg("REJECTED", "0"), _leg("FILLED", "0.5")) == D.ATTEMPT_SINGLE_LEG_EXPOSURE


def test_classify_both_filled_mismatched_qty_is_success():
    # fix-3 (DI-6): 成交数量校验 removed — both legs FILLED is success even when
    # the filled qtys differ (spot market BUY vs quantity legs cannot pre-align).
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("FILLED", "0.4")) == D.ATTEMPT_SUCCESS


def test_classify_neither_filled_is_failed():
    assert D.classify_attempt(_leg("REJECTED", "0"), _leg("EXPIRED", "0")) == D.ATTEMPT_FAILED


def test_build_leg_exposure_spot_only_is_section_3_2_shape():
    # Frozen §3.2: leg_exposure is null|{leg,qty,price,ts}. Spot-only fill ->
    # leg="spot" with the spot leg's actual qty/price; the failed perp leg is
    # NOT carried here (its full detail lives in the Fill JSON, §3.3).
    exp = D.build_leg_exposure(_leg("FILLED", "0.5", "50000"), _leg("REJECTED", "0"), 1)
    assert exp is not None
    assert set(exp.keys()) == {"leg", "qty", "price", "ts"}
    assert exp["leg"] == "spot"
    assert exp["qty"] == "0.5"
    assert exp["price"] == "50000"


def test_build_leg_exposure_perp_only_is_section_3_2_shape():
    # Perp-only fill -> leg="perp" with the perp leg's actual qty/price.
    exp = D.build_leg_exposure(_leg("REJECTED", "0"), _leg("FILLED", "0.5", "50000"), 1)
    assert exp is not None
    assert set(exp.keys()) == {"leg", "qty", "price", "ts"}
    assert exp["leg"] == "perp"
    assert exp["qty"] == "0.5"
    assert exp["price"] == "50000"


def test_build_leg_exposure_none_when_neither_filled():
    assert D.build_leg_exposure(_leg("REJECTED", "0"), _leg("REJECTED", "0"), 1) is None


def test_build_leg_exposure_none_when_both_filled_mismatched():
    # fix-3 (DI-6): both legs FILLED now classifies as success, so this input no
    # longer reaches build_leg_exposure in practice; the None here is its
    # defensive both-filled guard. The full detail lives in the fills table (§3.3).
    assert D.build_leg_exposure(_leg("FILLED", "0.5"), _leg("FILLED", "0.4"), 1) is None


# ---------------------------------------------------------------------------
# Status transitions + >3-fail termination (ADR-4 / 10-design §7)
# ---------------------------------------------------------------------------

def test_resolve_success_reaching_target_is_done():
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SUCCESS, 3, 3, 0) == D.STATUS_DONE


def test_resolve_success_below_target_stays_running():
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SUCCESS, 1, 3, 0) == D.STATUS_RUNNING


def test_resolve_single_leg_is_exposure_alert():
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SINGLE_LEG_EXPOSURE, 1, 3, 0) == D.STATUS_EXPOSURE_ALERT


def test_resolve_failed_over_threshold_terminates():
    # >3 (i.e. the 4th) failed attempt -> paused (terminated plan).
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 4) == D.STATUS_PAUSED


def test_resolve_failed_at_threshold_stays_running():
    # exactly 3 failures is NOT >3 -> still running.
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 3) == D.STATUS_RUNNING


def test_resolve_deleted_is_sticky():
    for category in D.ALL_ATTEMPT_CATEGORIES:
        assert D.resolve_status_after_attempt(D.STATUS_DELETED, category, 9, 3, 9) == D.STATUS_DELETED


# ---------------------------------------------------------------------------
# Validation + helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("coin", ["BTCUSDT", "ETHUSDT", "1000SATSUSDT"])
def test_validate_coin_accepts_usdt_symbols(coin):
    assert D.validate_coin(coin) == coin


@pytest.mark.parametrize("coin", ["btc", "BTC", "BTC-USDT", "", "BTCEUR", 1, None])
def test_validate_coin_rejects_non_usdt(coin):
    with pytest.raises(D.HedgeError) as exc:
        D.validate_coin(coin)
    assert exc.value.code == "invalid_field"


def test_base_asset_strips_usdt():
    assert D.base_asset("BTCUSDT") == "BTC"
    assert D.base_asset("ETHUSDT") == "ETH"


def test_validate_direction_mode_amount_target():
    assert D.validate_direction("forward") == "forward"
    assert D.validate_mode("immediate") == "immediate"
    assert D.validate_single_amount("0.5") == "0.5"
    assert D.validate_target_n(3) == 3
    for bad in ("up", None):
        with pytest.raises(D.HedgeError):
            D.validate_direction(bad)
    for bad in ("fast", None):
        with pytest.raises(D.HedgeError):
            D.validate_mode(bad)
    for bad in ("0", "-1", "1.2.3", 0.5, None):
        with pytest.raises(D.HedgeError):
            D.validate_single_amount(bad)
    for bad in (0, -1, 1.5, "1", True, None):
        with pytest.raises(D.HedgeError):
            D.validate_target_n(bad)


def test_reject_unknown_keys_names_first_extra():
    with pytest.raises(D.HedgeError) as exc:
        D.reject_unknown_keys({"coin": "BTCUSDT", "extra": 1}, ("coin",))
    assert exc.value.code == "invalid_field"
    assert "extra" in exc.value.detail


def test_validate_limit_bounds():
    assert D.validate_limit(None) == 50
    assert D.validate_limit(1) == 1
    for bad in (0, 201, 1.5):
        with pytest.raises(D.HedgeError):
            D.validate_limit(bad)


def test_filter_status_for_list_mapping():
    # Frozen §3.1: the default view (None/"") excludes deleted and maps to the
    # ``None`` sentinel; ``status=all`` must NOT collapse onto the default — it
    # returns the distinct ``LIST_ALL`` marker so the store includes deleted.
    # ``deleted``/``running`` filter to that status; unknown -> invalid_field.
    assert D.filter_status_for_list(None) is None
    assert D.filter_status_for_list("") is None
    assert D.filter_status_for_list("all") == D.LIST_ALL
    assert D.filter_status_for_list("deleted") == D.STATUS_DELETED
    assert D.filter_status_for_list("running") == D.STATUS_RUNNING
    with pytest.raises(D.HedgeError):
        D.filter_status_for_list("bogus")


def test_cursor_round_trip_and_reject():
    token = D.encode_cursor(1_700_000_000_000_000, 42)
    assert D.decode_cursor(token) == (1_700_000_000_000_000, 42)
    assert D.decode_cursor("!!!") is None
    assert "=" not in token


def test_us_to_iso_utc_microsecond():
    iso = D.us_to_iso(1_784_448_000_000_000)
    assert iso == "2026-07-19T08:00:00.000000Z"
    assert D.us_to_iso(None) is None


def test_hedge_error_payload_carries_extra():
    err = D.HedgeError(400, "insufficient_balance", "x", extra={"required": "1"})
    assert err.as_payload() == {"error": "insufficient_balance", "detail": "x", "required": "1"}
