"""Pure domain tests for backend/borrow_tasks/domain.py (breakdown §3.3–§3.6).

No SQLite, no HTTP, no network. Covers decimal/interval parsing discipline,
asset/amount/target validation, opaque-cursor round-trip, the COALESCE
effective-timestamp key, and the ISO microsecond representation.
"""
from __future__ import annotations

import pytest

from backend.borrow_tasks import domain as D


# ---------------------------------------------------------------------------
# Interval parsing — decimal string -> exact integer microseconds (§3.5)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value, expected_us",
    [
        ("5", 5_000_000),
        ("3", 3_000_000),
        ("2", 2_000_000),         # frozen 2-second capacity floor (inclusive)
        ("2.0", 2_000_000),
        ("2.5", 2_500_000),       # fractional but at/above the floor
        ("100", 100_000_000),
    ],
)
def test_parse_interval_accepts_positive_decimals(value, expected_us):
    seconds_str, interval_us = D.parse_interval_seconds(value)
    assert seconds_str == value            # echoed verbatim
    assert interval_us == expected_us


@pytest.mark.parametrize(
    "value",
    [
        "0", "-1", "0.0", "0.0000001", "0.0000015", "abc", "", "1e3", " 1", "1 ",
        # sub-floor cadences are rejected (Boundary C §3.5 frozen 2s floor)
        "0.5", "1", "1.5", "1.999", "0.000001",
    ],
)
def test_parse_interval_rejects_invalid_strings(value):
    with pytest.raises(D.BorrowError) as exc:
        D.parse_interval_seconds(value)
    assert exc.value.code == "invalid_interval"
    assert exc.value.status == 400


def test_parse_interval_floor_boundary():
    # The frozen shared-IP capacity floor is 2 seconds: 2 and 2.0 pass, every
    # sub-2 value (including 1.999 and 0.5) fails with invalid_interval.
    assert D.parse_interval_seconds("2") == ("2", 2_000_000)
    assert D.parse_interval_seconds("2.0") == ("2.0", 2_000_000)
    for sub_floor in ("1.999", "0.5", "1", "1.5"):
        with pytest.raises(D.BorrowError) as exc:
            D.parse_interval_seconds(sub_floor)
        assert exc.value.code == "invalid_interval"


def test_parse_interval_rejects_json_number():
    # Decimal discipline: a JSON number must be rejected at the boundary.
    with pytest.raises(D.BorrowError) as exc:
        D.parse_interval_seconds(0.5)
    assert exc.value.code == "invalid_interval"


def test_parse_interval_error_is_deterministic_payload():
    try:
        D.parse_interval_seconds("bad")
    except D.BorrowError as exc:
        assert exc.as_payload() == {"error": "invalid_interval", "detail": exc.detail}
    else:
        pytest.fail("expected BorrowError")


# ---------------------------------------------------------------------------
# Amount / asset / success_target validation (§3.3 / §3.4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["12.5", "1", "0.001", "100.000000"])
def test_validate_amount_accepts_decimal_strings(value):
    assert D.validate_amount(value) == value


@pytest.mark.parametrize("value", ["0", "-1", "0.0", "1.2.3", "abc", "", "1e2", 12.5, None])
def test_validate_amount_rejects_invalid(value):
    with pytest.raises(D.BorrowError) as exc:
        D.validate_amount(value)
    assert exc.value.code == "invalid_field"


@pytest.mark.parametrize("value", ["BTC", "HOME", "ABC123", "A"])
def test_validate_asset_accepts_uppercase(value):
    assert D.validate_asset(value) == value


@pytest.mark.parametrize("value", ["btc", "BT-C", "BTC USDT", "", "ab", 1, None])
def test_validate_asset_rejects_non_uppercase(value):
    with pytest.raises(D.BorrowError) as exc:
        D.validate_asset(value)
    assert exc.value.code == "invalid_field"


def test_validate_success_target_rejects_non_positive_and_non_integer():
    for bad in [0, -1, 1.5, "1", True, None]:
        with pytest.raises(D.BorrowError):
            D.validate_success_target(bad)
    assert D.validate_success_target(3) == 3


# ---------------------------------------------------------------------------
# Limit bounds (§3.6)
# ---------------------------------------------------------------------------
def test_validate_limit_defaults_and_bounds():
    assert D.validate_limit(None) == 50
    assert D.validate_limit(1) == 1
    assert D.validate_limit(200) == 200
    for bad in [0, -1, 201, 1.5]:
        with pytest.raises(D.BorrowError) as exc:
            D.validate_limit(bad)
        assert exc.value.code == "invalid_limit"


# ---------------------------------------------------------------------------
# Opaque cursor encodes the full COALESCE boundary (amendment §3)
# ---------------------------------------------------------------------------
def test_cursor_round_trip_presolves_boundary():
    token = D.encode_cursor(1_700_000_000_000_000, 42)
    assert D.decode_cursor(token) == (1_700_000_000_000_000, 42)


def test_cursor_decode_rejects_garbage():
    for bad in ["!!!", "notb64", "1", "1:2", "==", "AAAA", None]:
        assert D.decode_cursor(bad) is None


def test_cursor_omits_padding():
    token = D.encode_cursor(100, 5)
    assert "=" not in token


# ---------------------------------------------------------------------------
# Effective timestamp + ISO representation
# ---------------------------------------------------------------------------
def test_effective_ts_uses_first_available():
    assert D.effective_ts_us(3, 2, 1) == 3
    assert D.effective_ts_us(None, 2, 1) == 2
    assert D.effective_ts_us(None, None, 1) == 1
    assert D.effective_ts_us(None, None, None) == 0


def test_us_to_iso_is_utc_microsecond_with_z():
    # 2026-07-19T08:00:00.000000Z = epoch us 1784448000000000
    iso = D.us_to_iso(1_784_448_000_000_000)
    assert iso == "2026-07-19T08:00:00.000000Z"
    assert iso.endswith("Z")
    assert len(iso.split("T")[1]) == len("08:00:00.000000Z")


def test_us_to_iso_none_passthrough():
    assert D.us_to_iso(None) is None
