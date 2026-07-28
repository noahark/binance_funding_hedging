"""Pure domain tests for backend/hedge_open_tasks/domain.py.

No SQLite, no HTTP, no network. Covers the round-1 frozen logic: direction
mapping (ADR-3), common-grid lcm rounding incl. mismatched steps (ADR-2),
preflight accept/reject incl. insufficient balance and filter violations
(10-design §5), acceptance-based single-leg classification (ADR-3/ADR-4 — a leg
is "accepted" when an orderId was returned, regardless of fill state), the
``>= threshold`` consecutive-submission-failure pause + status transitions, and
the carried-forward validation/encoding helpers.
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


@pytest.mark.parametrize("direction", [D.DIR_FORWARD, D.DIR_REVERSE])
def test_preflight_missing_est_price_fails_closed_both_directions(direction):
    """Amendment 21 / dispatch P1#1: price-completeness is direction-independent.
    A missing (or zero/negative) ``est_price`` cannot size notional or the USDT
    need and is an UNREADABLE fact, so it fails closed to INCOMPLETE for BOTH
    forward and reverse — the old reverse branch never checked ``est_price`` and
    the old forward minNotional path silently skipped notional when it was None.
    Zero attempt, zero POST, zero failure count: the balance gate is never
    reached (``balance_ok`` stays None)."""
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("100000"), "BTC": Decimal("100")}, est_price=None),
        "BTCUSDT", direction, Decimal("0.5"), 3,
    )
    assert pf.rejection == D.REJECT_PREFLIGHT_INCOMPLETE
    assert pf.q_common is not None  # the common grid is still computable
    assert pf.balance_ok is None    # balance gate never reached -> no sizing


@pytest.mark.parametrize("est_price", ["0", "-1"])
def test_preflight_non_positive_est_price_fails_closed(est_price):
    """A zero or negative est_price is equally an unreadable sizing fact: it must
    fail closed to INCOMPLETE (not a filter violation), for both directions."""
    pf = D.compute_preflight(
        snapshot(balances={"USDT": Decimal("100000")}, est_price=est_price),
        "BTCUSDT", D.DIR_FORWARD, Decimal("0.5"), 3,
    )
    assert pf.rejection == D.REJECT_PREFLIGHT_INCOMPLETE


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
    # A required market step that cannot be read is fail-closed INCOMPLETE
    # (amendment I-7), NOT a below_min_qty filter violation. Conflating the two
    # would wrongly fatal-stop the task on a missing read instead of retrying.
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
    assert pf.rejection == D.REJECT_PREFLIGHT_INCOMPLETE


# ---------------------------------------------------------------------------
# Acceptance-based classification (ADR-3 / ADR-4)
# ---------------------------------------------------------------------------

def _leg(status, qty, price="50000", order_id="x"):
    """A leg dict. ``order_id`` is the acceptance signal (ADR-3): a truthy
    value means the leg was taken by the exchange (FILLED/NEW/PARTIALLY_FILLED
    with an orderId); ``None`` means it was confirmed not accepted."""
    return {"status": status, "filled_qty": qty, "avg_price": price, "order_id": order_id}


def test_classify_both_filled_aligned_is_success():
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("FILLED", "0.5")) == D.ATTEMPT_SUCCESS


def test_classify_one_accepted_one_rejected_is_exposure():
    # One leg accepted (orderId present), the other confirmed not accepted ->
    # single_leg_exposure (advisory, recorded but never a gate).
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("REJECTED", "0", order_id=None)) == D.ATTEMPT_SINGLE_LEG_EXPOSURE
    assert D.classify_attempt(_leg("REJECTED", "0", order_id=None), _leg("FILLED", "0.5")) == D.ATTEMPT_SINGLE_LEG_EXPOSURE


def test_classify_both_filled_mismatched_qty_is_success():
    # DI-6: both legs accepted is success even when the filled qtys differ.
    assert D.classify_attempt(_leg("FILLED", "0.5"), _leg("FILLED", "0.4")) == D.ATTEMPT_SUCCESS


def test_classify_neither_accepted_is_failed():
    # Neither leg carries an orderId (confirmed submission failure) -> failed.
    assert D.classify_attempt(_leg("REJECTED", "0", order_id=None), _leg("EXPIRED", "0", order_id=None)) == D.ATTEMPT_FAILED


def test_classify_partial_fill_is_accepted_when_order_id_present():
    # A PARTIALLY_FILLED leg is still ACCEPTED (orderId present); both partial ->
    # success, not exposure (ADR-3: acceptance keys the verdict, not fill).
    assert D.classify_attempt(_leg("PARTIALLY_FILLED", "0.2"), _leg("PARTIALLY_FILLED", "0.3")) == D.ATTEMPT_SUCCESS


def test_build_leg_exposure_spot_only_is_section_3_2_shape():
    # Frozen §3.2: leg_exposure is null|{leg,qty,price,ts}. Spot accepted, perp
    # not -> leg="spot" with the spot leg's actual qty/price; the un-accepted
    # perp leg is NOT carried here (its full detail lives in the leg table, §3.3).
    exp = D.build_leg_exposure(_leg("FILLED", "0.5", "50000"), _leg("REJECTED", "0", order_id=None), 1)
    assert exp is not None
    assert set(exp.keys()) == {"leg", "qty", "price", "ts"}
    assert exp["leg"] == "spot"
    assert exp["qty"] == "0.5"
    assert exp["price"] == "50000"


def test_build_leg_exposure_perp_only_is_section_3_2_shape():
    # Perp accepted, spot not -> leg="perp" with the perp leg's actual qty/price.
    exp = D.build_leg_exposure(_leg("REJECTED", "0", order_id=None), _leg("FILLED", "0.5", "50000"), 1)
    assert exp is not None
    assert set(exp.keys()) == {"leg", "qty", "price", "ts"}
    assert exp["leg"] == "perp"
    assert exp["qty"] == "0.5"
    assert exp["price"] == "50000"


def test_build_leg_exposure_none_when_neither_accepted():
    assert D.build_leg_exposure(_leg("REJECTED", "0", order_id=None), _leg("REJECTED", "0", order_id=None), 1) is None


def test_build_leg_exposure_none_when_both_accepted():
    # DI-6: both legs accepted classifies as success, so this never reaches
    # build_leg_exposure in practice; the None is its defensive both-accepted
    # guard. The full detail lives in the leg table (§3.3).
    assert D.build_leg_exposure(_leg("FILLED", "0.5"), _leg("FILLED", "0.4"), 1) is None


@pytest.mark.parametrize("bad_ts", [0, -1])
def test_build_leg_exposure_rejects_non_positive_timestamp(bad_ts):
    # T5 backstop (10-design §4(a)): a non-positive exposure timestamp is always a
    # programming error — fail loudly rather than render a 1970 epoch.
    spot = _leg("FILLED", "0.5", "50000")
    perp = _leg("REJECTED", "0", order_id=None)
    with pytest.raises(D.HedgeError) as exc:
        D.build_leg_exposure(spot, perp, bad_ts)
    assert exc.value.code == "invalid_field"


# ---------------------------------------------------------------------------
# Status transitions + >=threshold consecutive-failure pause (ADR-3 / 10-design §7)
# ---------------------------------------------------------------------------

def test_resolve_success_reaching_target_is_done():
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SUCCESS, 3, 3, 0, 3) == D.STATUS_DONE


def test_resolve_success_below_target_stays_running():
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SUCCESS, 1, 3, 0, 3) == D.STATUS_RUNNING


def test_resolve_single_leg_is_advisory_keeps_running():
    # A single-leg exposure is ADVISORY in the sense it never freezes scheduling
    # (breakdown §4.5): it does not jump straight to paused on a single outcome.
    # R2-F1 (user authorization 28 §2.1): a single_leg DOES, however, count toward
    # the consecutive-submission-failure brake — so below the threshold the task
    # keeps running and the exposure is recorded, but the count is incremented.
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_SINGLE_LEG_EXPOSURE, 1, 3, 0, 3) == D.STATUS_RUNNING


def test_resolve_single_leg_at_threshold_is_paused():
    # R2-F1: a single-leg exposure participates in the consecutive-submission-
    # failure brake. The threshold-th (>=) consecutive single_leg pauses the task,
    # exactly like the threshold-th confirmed failure (so the brake is no longer
    # bypassable by always landing on exactly one accepted leg).
    assert D.resolve_status_after_attempt(
        D.STATUS_RUNNING, D.ATTEMPT_SINGLE_LEG_EXPOSURE, 0, 5, 3, 3
    ) == D.STATUS_PAUSED
    assert D.resolve_status_after_attempt(
        D.STATUS_RUNNING, D.ATTEMPT_SINGLE_LEG_EXPOSURE, 0, 5, 4, 3
    ) == D.STATUS_PAUSED


def test_resolve_single_leg_below_threshold_stays_running():
    # R2-F1: below the threshold a single_leg keeps the task running (the brake
    # has not fired; the exposure remains advisory-only for this one outcome).
    assert D.resolve_status_after_attempt(
        D.STATUS_RUNNING, D.ATTEMPT_SINGLE_LEG_EXPOSURE, 0, 5, 2, 3
    ) == D.STATUS_RUNNING


def test_resolve_failed_at_threshold_is_paused():
    # >= threshold (the 3rd consecutive submission failure) -> paused.
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 3, 3) == D.STATUS_PAUSED


def test_resolve_failed_over_threshold_is_paused():
    # 4th consecutive failure (>= 3) -> still paused.
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 4, 3) == D.STATUS_PAUSED


def test_resolve_failed_below_threshold_stays_running():
    # 2 failures < 3 threshold -> still running.
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 2, 3) == D.STATUS_RUNNING


def test_resolve_honors_task_snapshotted_threshold():
    # The threshold is task-snapshotted; a task that snapshotted 1 pauses on the
    # very first consecutive submission failure (>= 1).
    assert D.resolve_status_after_attempt(D.STATUS_RUNNING, D.ATTEMPT_FAILED, 0, 3, 1, 1) == D.STATUS_PAUSED


def test_resolve_deleted_is_sticky():
    for category in D.ALL_ATTEMPT_CATEGORIES:
        assert D.resolve_status_after_attempt(D.STATUS_DELETED, category, 9, 3, 9, 3) == D.STATUS_DELETED


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


# ---------------------------------------------------------------------------
# T2 error classification (ADR-T3): two-layer code classifier + attempt rollup.
# Stage 2026-07-hedge-order-truth-v1 — the hard non-regression constraint
# (10-design §2(c)) is that adding the margin positive-code path (51169 ->
# collateral_cap) changes NO negative code's verdict. The matrices below prove it.
# ---------------------------------------------------------------------------


def test_classify_51169_margin_is_collateral_cap_not_insufficient():
    # 02-collateral-cap-finding.md: 51169 is a platform collateral-cap rejection,
    # NOT an account funds shortage. It is its own category, never insufficient_funds.
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, "51169", None) == D.ERROR_CATEGORY_COLLATERAL_CAP


def test_classify_51169_um_is_unclassified_not_null():
    # 51169 is margin-specific (the spot/margin leg). On UM it has no seeded rule,
    # so it is the EXPLICIT unclassified (a code was present but unrecognized) —
    # never NULL (no code) and never collateral_cap.
    assert D.classify_exchange_code(D.PRODUCT_UM, "51169", None) == D.ERROR_CATEGORY_UNCLASSIFIED


def test_classify_no_code_is_none_distinct_from_unclassified():
    # NULL (no code) and unclassified (code present, unrecognized) must never
    # collapse — that collapse was exactly the defect this stage fixes.
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, None, None) is None
    assert D.classify_exchange_code(D.PRODUCT_UM, None, None) is None


def test_classify_unknown_codes_are_unclassified_on_both_products():
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, "99999", None) == D.ERROR_CATEGORY_UNCLASSIFIED
    assert D.classify_exchange_code(D.PRODUCT_UM, "99999", None) == D.ERROR_CATEGORY_UNCLASSIFIED
    # An unlisted negative code is equally unclassified (not NULL).
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, "-5000", None) == D.ERROR_CATEGORY_UNCLASSIFIED
    assert D.classify_exchange_code(D.PRODUCT_UM, "-5000", None) == D.ERROR_CATEGORY_UNCLASSIFIED


def _negative_code_expectations() -> list[tuple[str, str]]:
    """Map every negative code in the vocabulary to the category it must keep on
    BOTH products. ``-2019``/``-3041`` are insufficient_funds (the insufficient
    layer precedes the fatal layer); every other fatal-set code (incl. ``-2010``
    with no message) is fatal; the auth set is auth."""
    expected: dict[str, str] = {}
    for code in D.AUTH_AMBIGUOUS_EXCHANGE_CODES:
        expected[code] = D.ERROR_CATEGORY_AUTH
    for code in D.INSUFFICIENT_FUNDS_CODES:  # checked before FATAL_EXCHANGE_CODES
        expected[code] = D.ERROR_CATEGORY_INSUFFICIENT_FUNDS
    for code in D.FATAL_EXCHANGE_CODES:
        expected.setdefault(code, D.ERROR_CATEGORY_FATAL)  # -2010 (no msg) -> fatal
    return sorted(expected.items())


@pytest.mark.parametrize("code,expected", _negative_code_expectations())
def test_classify_negative_codes_keep_verdict_on_both_products(code, expected):
    """Hard non-regression (10-design §2(c)): every negative code keeps its verdict
    on BOTH products. Adding the margin positive-code path (51169) perturbed none."""
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, code, None) == expected
    assert D.classify_exchange_code(D.PRODUCT_UM, code, None) == expected


def test_classify_minus_2010_message_confirms_insufficient_balance():
    # -2010 is overloaded: only an "insufficient ... balance" message confirms it
    # as a recoverable pause; without that proof it stays a fatal stop.
    for msg in ("Account has insufficient balance.", "insufficient available balance for X"):
        assert D.classify_exchange_code(D.PRODUCT_MARGIN, "-2010", msg) == D.ERROR_CATEGORY_INSUFFICIENT_FUNDS
        assert D.classify_exchange_code(D.PRODUCT_UM, "-2010", msg) == D.ERROR_CATEGORY_INSUFFICIENT_FUNDS


def test_classify_minus_2010_without_balance_message_stays_fatal():
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, "-2010", "Margin is insufficient.") == D.ERROR_CATEGORY_FATAL
    assert D.classify_exchange_code(D.PRODUCT_MARGIN, "-2010", None) == D.ERROR_CATEGORY_FATAL
    assert D.classify_exchange_code(D.PRODUCT_UM, "-2010", None) == D.ERROR_CATEGORY_FATAL


def test_collateral_cap_pause_reason_constant_and_frozen_message():
    # 10-design §2(d) / ADR-T3: pause_reason is the stable machine enum; the
    # operator message is FROZEN verbatim (only {asset} is filled). It must NOT be
    # the insufficient_margin wording, which would assert the false "保证金不足".
    assert D.PAUSE_REASON_COLLATERAL_CAP_FULL == "collateral_cap_full"
    assert D.collateral_cap_pause_reason_zh("NOM") == (
        "NOM 已达币安平台级抵押金额上限（该上限为全平台所有用户共享，并非本"
        "账户保证金不足，追加资金无效）。现货腿当前无法买入保证金账户，可更换"
        "其他币种或稍后重试；若该币上限占用未满 100%，调小金额也可能成功。"
    )
    # The denial "并非本账户保证金不足" is the only appearance of 保证金不足 — the
    # message never adopts the shortage framing it explicitly rejects.
    assert "并非本账户保证金不足" in D.collateral_cap_pause_reason_zh("NOM")


def test_rollup_returns_none_when_neither_leg_carries_a_category():
    assert D.rollup_leg_error_category(None, None, None, None) == (None, None)
    assert D.rollup_leg_error_category(None, "x", None, "y") == (None, None)


def test_rollup_collateral_cap_ranks_above_insufficient_funds():
    # 10-design §2(e): both pause, but collateral_cap is the more specific
    # diagnosis and ranks higher — it wins the attempt row from either leg.
    assert D.rollup_leg_error_category(
        D.ERROR_CATEGORY_COLLATERAL_CAP, "51169",
        D.ERROR_CATEGORY_INSUFFICIENT_FUNDS, "-2019",
    ) == (D.ERROR_CATEGORY_COLLATERAL_CAP, "51169")
    assert D.rollup_leg_error_category(
        D.ERROR_CATEGORY_INSUFFICIENT_FUNDS, "-2019",
        D.ERROR_CATEGORY_COLLATERAL_CAP, "51169",
    ) == (D.ERROR_CATEGORY_COLLATERAL_CAP, "51169")


def test_rollup_priority_order_fatal_auth_cap_insufficient_unclassified_absent():
    # fatal > auth > collateral_cap > insufficient_funds > unclassified > absent.
    assert D.rollup_leg_error_category(
        D.ERROR_CATEGORY_AUTH, "-1021", D.ERROR_CATEGORY_FATAL, "-1013",
    ) == (D.ERROR_CATEGORY_FATAL, "-1013")
    assert D.rollup_leg_error_category(
        D.ERROR_CATEGORY_UNCLASSIFIED, "99999", D.ERROR_CATEGORY_ABSENT, "-2013",
    ) == (D.ERROR_CATEGORY_UNCLASSIFIED, "99999")
    assert D.rollup_leg_error_category(
        None, None, D.ERROR_CATEGORY_ABSENT, "-2013",
    ) == (D.ERROR_CATEGORY_ABSENT, "-2013")


def test_rollup_tie_prefers_spot_category_and_code():
    assert D.rollup_leg_error_category(
        D.ERROR_CATEGORY_FATAL, "-1013a", D.ERROR_CATEGORY_FATAL, "-1013b",
    ) == (D.ERROR_CATEGORY_FATAL, "-1013a")
