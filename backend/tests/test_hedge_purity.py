"""Purity + allowlist guard for the hedge-open real-API path (breakdown §3.7).

Mirrors the borrow ``test_private_client.py`` static guard, extended to cover the
hedge domain package (10-design §9 / ADR-5):

1. ``hedge_open_tasks/**`` never imports a network transport or a signing/hashing
   primitive, and never imports the services-layer live client/executor/preflight
   provider — so the dry-run record transport's zero-network proof holds and a
   real POST is reachable ONLY through the injected live adapter (the seam).
2. ``HedgeOpenLiveClient`` carries exactly the frozen 7-endpoint allowlist pinned
   by the archived recon (recon §3.1/§3.2/§4.1), deny-by-default, host hardcoded
   to ``papi.binance.com`` (never caller-supplied).
3. The allowlist gate raises BEFORE any signing primitive is called — an unknown
   path never reaches ``urlopen`` and never sends a signature.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services.hedge_open_live_client import ALLOWLIST, HedgeOpenLiveClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HEDGE_PKG = REPO_ROOT / "backend" / "hedge_open_tasks"

# Network / signing primitive imports. Matched on actual import statements +
# lowercase hmac/hashlib (mirrors test_private_client.py's case-sensitive guard,
# so an uppercase "HMAC" docstring mention does NOT trip it while a real
# ``import hmac`` does). The dry-run zero-network proof depends on this.
_FORBIDDEN_IMPORT_RE = re.compile(
    r"(import\s+urllib|from\s+urllib|import\s+socket|from\s+socket|"
    r"import\s+requests|from\s+requests|import\s+http\.client|from\s+http\.client|"
    r"\bhmac\b|\bhashlib\b)"
)
# The services-layer live modules the package must NOT import (injected instead).
_LIVE_MODULE_RE = re.compile(
    r"(hedge_open_live_client|live_hedge_executor|hedge_preflight_provider)"
)

# The frozen 7-endpoint allowlist pinned by the recon (recon §3.1/§3.2/§4.1).
# Method/path/host are facts; drift here is a contract break.
_FROZEN_ALLOWLIST = {
    ("POST", "/papi/v1/margin/order"): "https://papi.binance.com",
    ("POST", "/papi/v1/um/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/margin/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/order"): "https://papi.binance.com",
    ("GET", "/papi/v1/balance"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/positionSide/dual"): "https://papi.binance.com",
    ("GET", "/papi/v1/rateLimit/order"): "https://papi.binance.com",
}


# ---- 1. hedge_open_tasks/** purity (the dry-run zero-network proof) ----
def test_hedge_domain_package_imports_no_network_or_signing_primitive():
    bad = []
    for py in HEDGE_PKG.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _FORBIDDEN_IMPORT_RE.search(text):
            bad.append(py.name)
    assert bad == [], f"network/signing primitive found in hedge_open_tasks: {bad}"


def test_hedge_domain_package_does_not_import_live_adapter():
    """The live adapter is injected through the seam; the domain package must not
    import the services-layer live client/executor/preflight provider directly."""
    bad = []
    for py in HEDGE_PKG.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if _LIVE_MODULE_RE.search(text):
            bad.append(py.name)
    assert bad == [], f"hedge_open_tasks references a live-adapter module: {bad}"


def test_store_never_invokes_or_holds_an_executor():
    """Q6 命门 (amendment 21): the store is pure persistence — it must NEVER call
    an executor and never hold an executor reference. The executor is invoked
    ONLY by the service's task-local worker, between short store transactions
    with no lock/transaction held. This static guard pins that as a compile-time
    fact so a future edit cannot silently re-introduce an executor call under the
    store lock. (``.execute`` is excluded from the call ban — it collides with
    the SQLite cursor's ``.execute()``.)"""
    store_py = HEDGE_PKG / "store.py"
    text = store_py.read_text(encoding="utf-8")
    assert not re.search(r"\.\s*(?:dispatch|query_leg|query)\s*\(", text), (
        "store.py invokes an executor method (Q6 violation)"
    )
    assert "self._executor" not in text, "store.py holds an executor reference (Q6)"


# ---- 2. frozen allowlist (recon §3.1/§3.2/§4.1) ----
def test_allowlist_is_exactly_the_frozen_seven_endpoints():
    assert ALLOWLIST == _FROZEN_ALLOWLIST
    assert len(ALLOWLIST) == 7


def test_allowlist_hosts_all_hardcoded_papi():
    for (method, path), base in ALLOWLIST.items():
        assert base == "https://papi.binance.com", (method, path, base)


def test_allowlist_has_both_order_writes_and_queries():
    methods = {m for (m, _p) in ALLOWLIST}
    assert methods == {"GET", "POST"}


# ---- 3. deny-by-default + gate-fires-before-signing ----
@pytest.mark.parametrize("method,path", [
    ("POST", "/papi/v1/margin/maxBorrowable"),
    ("DELETE", "/papi/v1/um/order"),
    ("GET", "/papi/v1/um/positionRisk"),
    ("POST", "/papi/v1/balance"),
    ("GET", "/sapi/v1/margin/order"),
])
def test_allowlist_rejects_unknown_path(method, path):
    with pytest.raises(PermissionError):
        HedgeOpenLiveClient._require_whitelisted(method, path)


def test_gate_fires_before_signing():
    """An unknown path must raise without ever calling urlopen (no signature
    sent). The fake urlopen raises if reached, proving the gate precedes signing."""
    def boom(*args, **kwargs):
        raise AssertionError("urlopen must never be called for an unknown path")

    client = HedgeOpenLiveClient(
        api_key="k", api_secret="s", user_agent="t", urlopen=boom,
    )
    with pytest.raises(PermissionError):
        client._get_signed("/papi/v1/forbidden", {}, timestamp_ms=1, recv_window_ms=None)
    with pytest.raises(PermissionError):
        client._post_signed("/papi/v1/forbidden", {}, timestamp_ms=1, recv_window_ms=None)


def test_credentials_present_reflects_key_and_secret():
    assert HedgeOpenLiveClient("", "", user_agent="t").credentials_present is False
    assert HedgeOpenLiveClient("k", "", user_agent="t").credentials_present is False
    assert HedgeOpenLiveClient("", "s", user_agent="t").credentials_present is False
    assert HedgeOpenLiveClient("k", "s", user_agent="t").credentials_present is True


# ---------------------------------------------------------------------------
# D5 — money-zero tripwire (00-plan.md §5). A static guard that flags a money
# figure coerced to a zero by a silent default, so a new site cannot reintroduce
# the r4/r5/r6/r7/S1 family while the suite stays green. Quantity figures
# (filled_qty / cumulative_base_qty / base_qty / executed_qty / qty) are NOT
# money and are never flagged (00-plan.md §3 non-goal).
# ---------------------------------------------------------------------------

_LIVE_EXECUTOR = REPO_ROOT / "backend" / "services" / "live_hedge_executor.py"
_MONEY_ZERO_SCOPE = [HEDGE_PKG, _LIVE_EXECUTOR]

# Money figure names (00-plan.md §5). A missing value at one of these must stay
# NULL/None, never become a fabricated 0.
_MONEY_NAMES = {
    "price", "avg_price", "notional", "quote",
    "cumulative_quote_amt", "cumulative_quote",
}
_MONEY_SUFFIXES = ("_notional", "_avg_price", "_quote")
# Explicitly NOT money: quantity figures (a not-yet-filled leg genuinely fills 0).
_QUANTITY_NAMES = {
    "filled_qty", "cumulative_base_qty", "base_qty", "executed_qty", "qty",
}

# A money identifier assigned from one of these WITHOUT a safe marker is a silent
# zero coercion. _num(None) -> Decimal(0); _decimal_str(None) -> "0" by default.
_COERCER_RE = re.compile(r"\b(?:_num|_decimal_str)\s*\(")
# Safe markers: an explicit keep-unknown default, or an explicit real-zero
# fallback, makes the zero intentional rather than fabricated.
_SAFE_DEFAULT_RE = re.compile(r"default\s*=\s*None")
_SAFE_OR_ZERO_RE = re.compile(r"""\bor\s+["']0["']""")
_SAFE_GET_ZERO_RE = re.compile(r"""\.get\([^)]*,\s*["']0["']\s*\)""")
# SQL: a value-seeding statement whose column list may name a money column.
_SQL_STMT_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE)\b", re.IGNORECASE)
_ALLOWLIST_MARKER = "# money-zero-ok:"


def _is_money_name(name: str) -> bool:
    if name in _QUANTITY_NAMES:
        return False
    if name in _MONEY_NAMES:
        return True
    return any(name.endswith(suf) for suf in _MONEY_SUFFIXES)


def _uses_unsafe_coercer(text: str) -> bool:
    if not _COERCER_RE.search(text):
        return False
    if _SAFE_DEFAULT_RE.search(text):
        return False
    if _SAFE_OR_ZERO_RE.search(text):
        return False
    if _SAFE_GET_ZERO_RE.search(text):
        return False
    return True


def _find_python_money_coercions(lines):
    """A money identifier assigned from, or a dict entry keyed by a money
    identifier whose value contains, _num(/_decimal_str( without a safe marker."""
    out = []
    assign_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*(.+)$")
    dict_re = re.compile(r"""["']([A-Za-z_][A-Za-z0-9_]*)["']\s*:\s*([^,}\n]+)""")
    for i, line in enumerate(lines, 1):
        m = assign_re.match(line)
        if m and _is_money_name(m.group(1)) and _uses_unsafe_coercer(m.group(2)):
            out.append((i, line.strip(),
                        f"money field '{m.group(1)}' assigned from a zero-coercing parser"))
            continue
        m = dict_re.search(line)
        if m and _is_money_name(m.group(1)) and _uses_unsafe_coercer(m.group(2)):
            out.append((i, line.strip(),
                        f"money dict key '{m.group(1)}' value uses a zero-coercing parser"))
    return out


def _is_string_fragment(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    return s.startswith('"') or s.startswith("'")


def _sql_statement_anchor(lines, idx):
    """Walk up from the ``'0'`` line to the nearest INSERT INTO / UPDATE line,
    staying inside one statement (continuation lines are string fragments).
    Returns the anchor line index, or None if the ``'0'`` is not inside such a
    statement (e.g. a CREATE TABLE column default)."""
    j = idx - 1
    while j >= 0:
        if _SQL_STMT_RE.search(lines[j]):
            return j
        if not _is_string_fragment(lines[j]):
            return None
        j -= 1
    return None


def _statement_names_money_column(stmt: str) -> bool:
    return any(_is_money_name(tok)
               for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stmt))


def _find_sql_zero_in_money(lines):
    """Blunt SQL rule: a ``'0'`` literal inside an INSERT INTO / UPDATE statement
    whose column list names a money column. Positional column/value mapping is
    unreliable across hand-concatenated strings, so this flags any ``'0'`` in
    such a statement and relies on the allow-list for justified cases (e.g. a
    ``'0'`` that seeds a quantity column while a money column is NULL)."""
    out = []
    for idx, line in enumerate(lines):
        if "'0'" not in line:
            continue
        anchor = _sql_statement_anchor(lines, idx)
        if anchor is None:
            continue
        stmt = "\n".join(lines[anchor:idx + 1])
        if _statement_names_money_column(stmt):
            out.append((idx + 1, line.strip(),
                        "SQL INSERT/UPDATE names a money column and seeds a '0' literal"))
    return out


def _detect_money_zero(source: str):
    """Raw detector: every line flagged, INCLUDING allow-listed lines."""
    lines = source.splitlines()
    out = []
    out.extend(_find_python_money_coercions(lines))
    out.extend(_find_sql_zero_in_money(lines))
    return out


def find_money_zero_defaults(source: str, path: str = "<src>"):
    """Public detector — money figures coerced to a zero by a silent default,
    EXCLUDING lines marked ``# money-zero-ok: <reason>`` (intentional zeros).

    Returns ``(line_number, matched_text, reason)`` tuples. Pure over source
    text, callable over both real repository files and synthetic snippets.

    Honest coverage (00-plan.md §5): this reaches the r4 (wire coercion), r6
    (API projection), r7 (reconciled exposure) and S4 (seeded SQL literal)
    defect categories. It CANNOT reach r5 — whose defect was over-nulling a REAL
    exchange ``'0'``; no static pattern can tell a fabricated zero from a real
    one at rest. r5 is covered only by the paired regressions in test_hedge_store.
    """
    return [(ln, text, reason) for (ln, text, reason) in _detect_money_zero(source)
            if _ALLOWLIST_MARKER not in text]


def _money_zero_files():
    for entry in _MONEY_ZERO_SCOPE:
        if entry.is_dir():
            yield from sorted(entry.rglob("*.py"))
        else:
            yield entry


def test_no_unmarked_money_zero_coercion_in_tree():
    """Every money-zero coercion the detector flags must carry an inline
    ``# money-zero-ok: <reason>`` marker, or be fixed. No silent fabrications."""
    unmarked = []
    for py in _money_zero_files():
        src = py.read_text(encoding="utf-8")
        for ln, text, _reason in find_money_zero_defaults(src, str(py)):
            unmarked.append(f"{py}:{ln}: {text}")
    assert unmarked == [], (
        "unmarked money-zero coercion(s):\n" + "\n".join(unmarked))


def test_every_money_zero_ok_marker_sits_on_a_flagged_line():
    """Every ``# money-zero-ok`` marker must sit on a line the detector still
    flags (raw, ignoring the marker) — so a marker cannot survive as a blanket
    exemption after the code beneath it changes. A stale marker fails here."""
    stale = []
    for py in _money_zero_files():
        src = py.read_text(encoding="utf-8")
        lines = src.splitlines()
        raw_flagged = {ln for ln, _t, _r in _detect_money_zero(src)}
        for ln, line in enumerate(lines, 1):
            if _ALLOWLIST_MARKER in line and ln not in raw_flagged:
                stale.append(f"{py}:{ln}: marker not on a detector-flagged line")
    assert stale == [], (
        "stale money-zero-ok marker(s):\n" + "\n".join(stale))


def test_detector_flags_python_coercion_into_avg_price():
    """Meta (a): a Python coercion of a money field (avg_price) from _num( with no
    safe marker is flagged."""
    src = 'avg_price = _num(row["avg_price"])\n'
    findings = find_money_zero_defaults(src, "<synth>")
    assert findings, "expected avg_price = _num(...) to be flagged"
    assert findings[0][0] == 1
    assert "avg_price" in findings[0][1]


def test_detector_flags_sql_insert_seeding_money_column_with_zero():
    """Meta (b): a SQL INSERT that seeds a money column (cumulative_quote_amt)
    with a '0' literal is flagged."""
    src = (
        'store.execute(\n'
        '    "INSERT INTO hedge_open_leg"\n'
        '    " (cumulative_base_qty, cumulative_quote_amt, fee_amount)"\n'
        "    \" VALUES ('0', '0', NULL)\",\n"
        ')\n'
    )
    findings = find_money_zero_defaults(src, "<synth>")
    assert findings, "expected SQL money-column INSERT with '0' to be flagged"
    assert 4 in {ln for ln, _t, _r in findings}


def test_detector_flags_money_coercion_in_executor_scope():
    """Meta (c): a money coercion in backend/services/live_hedge_executor.py's
    scope (the layer previously excluded) is flagged — here _decimal_str, the
    executor's own parser, feeding a money field."""
    src = 'notional = _decimal_str(body.get("cumulative_quote"))\n'
    findings = find_money_zero_defaults(src, "<synth>")
    assert findings, "expected money field from _decimal_str (executor scope)"


def test_detector_does_not_flag_quantity_default():
    """A quantity default (filled_qty / cumulative_base_qty / executedQty) from
    _num(/_decimal_str( is NOT money and must not be flagged."""
    src = (
        'filled_qty = _num(row["filled_qty"])\n'
        'cumulative_base_qty = _num(row["cumulative_base_qty"])\n'
        'executed = _decimal_str(body.get("executedQty"))\n'
    )
    assert find_money_zero_defaults(src, "<synth>") == []


def test_detector_does_not_flag_allowlisted_or_safe_line():
    """An allow-listed line (``# money-zero-ok``) and a safe coercion
    (``default=None`` / ``or "0"``) are not reported by the public detector."""
    src = (
        'avg_price = _num(x)  # money-zero-ok: deliberate zero for a dry-run stub\n'
        'price = _decimal_str(v, default=None)\n'
        'quote = _num(q) or "0"\n'
    )
    assert find_money_zero_defaults(src, "<synth>") == []
