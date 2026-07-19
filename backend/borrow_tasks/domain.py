"""Borrow-task domain primitives for the A+B durable slice.

Pure constants, validation and representation helpers. No SQLite, no network,
 no executor. This module is imported by the store, service and tests; it must
never import any network transport or cryptographic signing/hashing primitive
so the zero-network proof (breakdown §5.1-9) holds.

Decimal discipline: money (``amount_per_attempt``) and the scheduler interval
cross the HTTP boundary as JSON strings, are parsed with :class:`Decimal`, and
are stored/echoed verbatim. No float ever touches a value path.

Time discipline (breakdown §3.10): all API timestamps are UTC ISO-8601 with
microsecond precision and a trailing ``Z``. Internally every timestamp is an
integer count of microseconds since the Unix epoch, so a 0.5-second gap is
observable (``effective_gap_us``). Two clocks are used: a monotonic clock for
tick spacing and a wall clock for recorded timestamps.
"""
from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Frozen vocabulary and constants (breakdown §3.3 / §3.5 / §3.6)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "borrow-tasks/v1"

STATUS_BORROWING = "borrowing"
STATUS_PAUSED = "paused"
STATUS_DELETED = "deleted"
STATUS_COMPLETED = "completed"
ALL_STATUSES = (STATUS_BORROWING, STATUS_PAUSED, STATUS_DELETED, STATUS_COMPLETED)
RUNNABLE_STATUSES = (STATUS_BORROWING, STATUS_PAUSED)  # editable states

OUTCOME_PENDING = "pending"
OUTCOME_RESOLVED = "resolved"

RESULT_SUCCESS = "success"
RESULT_KNOWN_REJECTION = "known_rejection"
RESULT_RATE_LIMITED = "rate_limited"
RESULT_UNKNOWN = "unknown"
RESULT_EXECUTION_DISABLED = "execution_disabled"
ALL_RESULT_CATEGORIES = (
    RESULT_SUCCESS,
    RESULT_KNOWN_REJECTION,
    RESULT_RATE_LIMITED,
    RESULT_UNKNOWN,
    RESULT_EXECUTION_DISABLED,
)

# Seed scheduler row (breakdown §3.5): one global frequency default of 5s.
DEFAULT_INTERVAL_SECONDS = "5"
DEFAULT_INTERVAL_US = 5_000_000

# HTTP body cap and log page bounds (breakdown §3.6 / §3.7).
BODY_MAX_BYTES = 16384
LIMIT_DEFAULT = 50
LIMIT_MIN = 1
LIMIT_MAX = 200

# Shape regexes (breakdown §3.3 / §3.4 / §3.5).
_ASSET_RE = re.compile(r"^[A-Z0-9]+$")
_AMOUNT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_INTERVAL_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Errors (deterministic 4xx mapping, breakdown §3.7)
# ---------------------------------------------------------------------------


class BorrowError(Exception):
    """A deterministic, sanitized borrow-API error carrying its HTTP shape."""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail

    def as_payload(self) -> dict:
        return {"error": self.code, "detail": self.detail}


def invalid_field(name: str, reason: str) -> BorrowError:
    return BorrowError(400, "invalid_field", f"{name}: {reason}")


# ---------------------------------------------------------------------------
# Validation (raises BorrowError on any deviation; deterministic)
# ---------------------------------------------------------------------------


def validate_asset(value) -> str:
    if not isinstance(value, str) or not _ASSET_RE.match(value):
        raise invalid_field("asset", "must be a non-empty A-Z0-9 string")
    return value


def validate_amount(value) -> str:
    if not isinstance(value, str) or not _AMOUNT_RE.match(value):
        raise invalid_field("amount_per_attempt", "must be a decimal string ^[0-9]+(\\.[0-9]+)?$")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise invalid_field("amount_per_attempt", "not a finite decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise invalid_field("amount_per_attempt", "must be finite and > 0")
    return value  # echoed verbatim, no float on the value path


def validate_success_target(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid_field("success_target", "must be a positive integer")
    if value < 1:
        raise invalid_field("success_target", "must be >= 1")
    return value


def parse_interval_seconds(value):
    """Return ``(interval_seconds, interval_us)`` or raise ``invalid_interval``.

    A JSON number is rejected (decimal discipline). The string must match the
    decimal shape, be finite and > 0, and normalize to an exact integer number
    of microseconds >= 1. Finer-than-microsecond values (e.g. ``"0.0000001"``)
    are rejected. There is no upper bound or product minimum.
    """
    if not isinstance(value, str):
        raise BorrowError(400, "invalid_interval", "interval_seconds must be a JSON string")
    if not _INTERVAL_RE.match(value):
        raise BorrowError(400, "invalid_interval", "interval_seconds must match ^[0-9]+(\\.[0-9]+)?$")
    try:
        seconds = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise BorrowError(400, "invalid_interval", "interval_seconds is not a finite decimal") from exc
    if not seconds.is_finite() or seconds <= 0:
        raise BorrowError(400, "invalid_interval", "interval_seconds must be finite and > 0")
    scaled = seconds * Decimal(1_000_000)
    truncated = scaled.to_integral_value()
    if scaled != truncated or truncated < 1:
        raise BorrowError(400, "invalid_interval", "interval_seconds is finer than one microsecond")
    return value, int(truncated)


def reject_unknown_keys(body: dict, allowed) -> None:
    """Raise ``invalid_field`` naming the first unexpected key, if any.

    Called before field validation so unknown/typoed keys are rejected
    deterministically instead of being silently ignored (breakdown §3.7). The
    offending field name appears in ``detail``.
    """
    extra = sorted(k for k in body if k not in allowed)
    if extra:
        raise invalid_field(extra[0], f"unexpected field(s): {', '.join(extra)}")


def validate_limit(value):
    """Return a bounded integer page size or raise ``invalid_limit``."""
    if value is None:
        return LIMIT_DEFAULT
    if isinstance(value, bool) or not isinstance(value, int):
        raise BorrowError(400, "invalid_limit", "limit must be an integer")
    if value < LIMIT_MIN or value > LIMIT_MAX:
        raise BorrowError(400, "invalid_limit", f"limit must be in [{LIMIT_MIN}, {LIMIT_MAX}]")
    return value


# ---------------------------------------------------------------------------
# Cursor (opaque, encodes the full COALESCE sort boundary per amendment §3)
# ---------------------------------------------------------------------------


def encode_cursor(effective_ts_us: int, attempt_id: int) -> str:
    raw = f"{effective_ts_us}:{attempt_id}".encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(value):
    """Return ``(effective_ts_us, attempt_id)`` or ``None`` if undecodable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding).decode("ascii")
        ts_str, id_str = decoded.split(":", 1)
        return int(ts_str), int(id_str)
    except Exception:
        return None


def effective_ts_us(finished_at_us, dispatched_at_us, scheduled_at_us) -> int:
    """Newest-completion-first sort key (amendment §3)."""
    for candidate in (finished_at_us, dispatched_at_us, scheduled_at_us):
        if candidate is not None:
            return candidate
    return 0


# ---------------------------------------------------------------------------
# Time representation
# ---------------------------------------------------------------------------


def us_to_iso(us) -> str | None:
    if us is None:
        return None
    dt = _EPOCH + timedelta(microseconds=int(us))
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
