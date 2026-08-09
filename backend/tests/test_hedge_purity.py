"""Purity + allowlist guard for the hedge-open real-API path (breakdown §3.7).

Mirrors the borrow ``test_private_client.py`` static guard, extended to cover the
hedge domain package (10-design §9 / ADR-5):

1. ``hedge_open_tasks/**`` never imports a network transport or a signing/hashing
   primitive, and never imports the services-layer live client/executor/preflight
   provider — so the dry-run record transport's zero-network proof holds and a
   real POST is reachable ONLY through the injected live adapter (the seam).
2. ``HedgeOpenLiveClient`` carries exactly the frozen 12-endpoint allowlist
   (recon §3.1/§3.2/§4.1 for the 7 PAPI pairs; decision §E-2 / §4 + the
   ``restricted-asset.raw.json`` sample for the 5 regular-spot pairs),
   deny-by-default. Hosts are hardcoded per group, never caller-supplied: the 7
   PAPI pairs -> ``papi.binance.com``; the 5 regular-spot pairs ->
   ``api.binance.com``.
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

# The frozen allowlist. 8 PAPI pairs (recon §3.1/§3.2/§4.1; 功能三 2026-08 新增
# ``GET /papi/v1/um/positionRisk``——close 完成核实查合约持仓，与快照侧 E4 同一
# 端点、非新权限) hardbound to papi.binance.com; 5 regular-spot pairs (decision
# §E-2 / §4, evidenced by
# reports/api-samples/2026-08-spot-order-routing-v1/restricted-asset.raw.json)
# hardbound to api.binance.com. Method/path/host are facts; drift here — a
# missing entry, a sixth entry, or a wrong host — is a contract break.
_PAPI_HOST = "https://papi.binance.com"
_SPOT_HOST = "https://api.binance.com"
_FAPI_HOST = "https://fapi.binance.com"
_FROZEN_ALLOWLIST = {
    # ---- 7 PAPI endpoints (order writes + preflight reads) ----
    ("POST", "/papi/v1/margin/order"): _PAPI_HOST,
    ("POST", "/papi/v1/um/order"): _PAPI_HOST,
    ("GET", "/papi/v1/margin/order"): _PAPI_HOST,
    ("GET", "/papi/v1/um/order"): _PAPI_HOST,
    ("GET", "/papi/v1/balance"): _PAPI_HOST,
    ("GET", "/papi/v1/um/positionSide/dual"): _PAPI_HOST,
    ("GET", "/papi/v1/rateLimit/order"): _PAPI_HOST,
    # 功能三（2026-08）：close 完成核实——查该 symbol 合约持仓是否归零（E4）。
    ("GET", "/papi/v1/um/positionRisk"): _PAPI_HOST,
    # ---- 5 regular-spot endpoints (collateral-cap + spot order/account/limit) ----
    ("GET", "/sapi/v1/margin/restricted-asset"): _SPOT_HOST,
    ("POST", "/api/v3/order"): _SPOT_HOST,
    ("GET", "/api/v3/order"): _SPOT_HOST,
    ("GET", "/api/v3/account"): _SPOT_HOST,
    ("GET", "/api/v3/rateLimit/order"): _SPOT_HOST,
    # 平仓现货卖出重设计（2026-08）：万向划转（统一账户⇄普通现货账户）。
    ("POST", "/sapi/v1/asset/transfer"): _SPOT_HOST,
    # 开单前自动设置合约杠杆（THE -2027 方案 B，2026-08）：fapi 域名，写语义与订单一致。
    ("POST", "/papi/v1/um/leverage"): _PAPI_HOST,
    # 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1）：PAPI TRADE，weight 3000，
    # one-shot。与 /papi/v1/repayLoan（经典逐仓，禁止）是不同端点。
    ("POST", "/papi/v1/margin/repay-debt"): _PAPI_HOST,
}
# The two host groups, for the per-group hardcoded-host assertion.
_PAPI_KEYS = frozenset({
    ("POST", "/papi/v1/margin/order"),
    ("POST", "/papi/v1/um/order"),
    ("GET", "/papi/v1/margin/order"),
    ("GET", "/papi/v1/um/order"),
    ("GET", "/papi/v1/balance"),
    ("GET", "/papi/v1/um/positionSide/dual"),
    ("GET", "/papi/v1/rateLimit/order"),
    ("GET", "/papi/v1/um/positionRisk"),    ("POST", "/papi/v1/um/leverage"),  # 统一账户 UM 合约杠杆（2026-08：原 fapi 端点对 PM 账户 401，改 PAPI）
    ("POST", "/papi/v1/margin/repay-debt"),  # 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1）
})
_SPOT_KEYS = frozenset({
    ("GET", "/sapi/v1/margin/restricted-asset"),
    ("POST", "/api/v3/order"),
    ("GET", "/api/v3/order"),
    ("GET", "/api/v3/account"),
    ("GET", "/api/v3/rateLimit/order"),
    ("POST", "/sapi/v1/asset/transfer"),
})
_FAPI_KEYS = frozenset()


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


# ---- 2. frozen allowlist (recon §3.1/§3.2/§4.1 + decision §E-2 / §4) ----
def test_allowlist_is_exactly_the_frozen_allowlist():
    # Exact equality + length 16 (15 + 统一账户全仓杠杆还款 POST /papi/v1/margin/repay-debt):
    # the anti-expansion guard. A missing authorized one both fail here. Not a
    # subset/contains check.
    assert ALLOWLIST == _FROZEN_ALLOWLIST
    assert len(ALLOWLIST) == 16  # 15 + 统一账户全仓杠杆还款 repay-debt POST（2026-08-09）
    assert len(_PAPI_KEYS) == 10  # 9 + 统一账户全仓杠杆还款 repay-debt（PAPI TRADE，2026-08-09）
    assert len(_SPOT_KEYS) == 6
    assert len(_FAPI_KEYS) == 0  # 2026-08：杠杆端点改 PAPI 后无 fapi 端点
    assert _PAPI_KEYS.isdisjoint(_SPOT_KEYS)
    assert _PAPI_KEYS.isdisjoint(_FAPI_KEYS)
    assert _SPOT_KEYS.isdisjoint(_FAPI_KEYS)


def test_allowlist_hosts_hardcoded_per_group():
    # Hosts are hardcoded per endpoint group (never caller-supplied): the 8 PAPI
    # pairs -> papi.binance.com; the 6 regular-spot pairs -> api.binance.com; the
    # 1 papi leverage pair -> papi.binance.com.
    for key in _PAPI_KEYS:
        assert ALLOWLIST[key] == _PAPI_HOST, f"PAPI endpoint {key} not hardbound to {_PAPI_HOST}"
    for key in _SPOT_KEYS:
        assert ALLOWLIST[key] == _SPOT_HOST, f"spot endpoint {key} not hardbound to {_SPOT_HOST}"
    for key in _FAPI_KEYS:
        assert ALLOWLIST[key] == _FAPI_HOST, f"fapi endpoint {key} not hardbound to {_FAPI_HOST}"
    # No endpoint maps to any other host.
    assert set(ALLOWLIST.values()) == {_PAPI_HOST, _SPOT_HOST}  # 2026-08：杠杆端点改 PAPI 后无 fapi 端点


def test_allowlist_has_both_order_writes_and_queries():
    methods = {m for (m, _p) in ALLOWLIST}
    assert methods == {"GET", "POST"}


# ---- 3. deny-by-default + gate-fires-before-signing ----
@pytest.mark.parametrize("method,path", [
    ("POST", "/papi/v1/margin/maxBorrowable"),
    ("DELETE", "/papi/v1/um/order"),
    ("POST", "/papi/v1/um/positionRisk"),  # 写方法仍拒绝（只允许 GET 核实读）
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

# A money identifier fed by any of these WITHOUT ``default=None`` is a silent
# zero fabrication (10-unknown-not-zero D5 point 4). _num(None) -> Decimal(0);
# _decimal_str(None) -> "0" by default; ``or "0"`` and ``.get(…, "0")`` fabricate
# a zero when the source is missing. All four are FLAGGED together (task1b R1: the
# delivery wrongly treated the last two as safe markers that suppressed a finding).
_COERCER_RE = re.compile(r"\b(?:_num|_decimal_str)\s*\(")
_OR_ZERO_RE = re.compile(r"""\bor\s+["']0["']""")
_GET_ZERO_RE = re.compile(r"""\.get\([^)]*,\s*["']0["']\s*\)""")
# The one genuine keep-unknown marker: an explicit default=None (None stays None,
# never 0). Everything above is a fabrication, never "safe".
_SAFE_DEFAULT_RE = re.compile(r"default\s*=\s*None")
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
    """True when the RHS fabricates a zero from a missing money figure.

    ``default=None`` is the one genuine keep-unknown marker (None stays None).
    Otherwise any of ``_num(`/``_decimal_str(` (None -> 0), ``or "0"`` /
    ``or '0'``, or ``.get(…, "0")`` / ``.get(…, '0')`` is a fabrication and is
    flagged — task1b R1. ``_num(` need not appear for ``or "0"`` to fire, so
    ``avg_price = D.Decimal(x or "0")`` is no longer invisible."""
    if _SAFE_DEFAULT_RE.search(text):
        return False
    return bool(_COERCER_RE.search(text)
                or _OR_ZERO_RE.search(text)
                or _GET_ZERO_RE.search(text))


def _find_python_money_coercions(lines):
    """A money identifier assigned from, or a dict entry keyed by a money
    identifier whose value contains, a zero-fabricating construct without
    ``default=None``.

    The assignment target may be a bare name, a subscript ``obj["key"]``, or an
    attribute ``obj.attr`` (optionally chained), with ``=`` or an augmented op
    ``+=`` / ``-=`` / ``*=`` / ``/=`` (task1b R2: the old bare-name ``=`` rule hid
    S2's ``b["spot_notional"] += q * _num(…)``). A target is money if ANY of its
    identifier tokens is a money name."""
    out = []
    lhs_re = re.compile(
        r"^\s*([A-Za-z_]\w*(?:\[[^\]]*\]|\.[A-Za-z_]\w*)*)\s*"
        r"((?:\+|-|\*|/)?=)(?!=)\s*(.+)$"
    )
    dict_re = re.compile(r"""["']([A-Za-z_]\w*)["']\s*:\s*([^,}\n]+)""")
    for i, line in enumerate(lines, 1):
        m = lhs_re.match(line)
        if m:
            target, op, rhs = m.group(1), m.group(2), m.group(3)
            money_tok = next((t for t in re.findall(r"[A-Za-z_]\w*", target)
                              if _is_money_name(t)), None)
            if money_tok is not None and _uses_unsafe_coercer(rhs):
                kind = "augmented " if op != "=" else ""
                out.append((i, line.strip(),
                            f"money field '{money_tok}' {kind}assigned from a "
                            f"zero-coercing parser"))
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
    staying inside one statement (continuation lines are string fragments), and
    including the ``'0'`` line itself so a single-line ``INSERT … '0'`` anchors
    (task1b R3a). Returns the anchor line index, or None if the ``'0'`` is not
    inside such a statement (e.g. a CREATE TABLE column default, which is not a
    string fragment)."""
    j = idx
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
    """An allow-listed line (``# money-zero-ok``) and a ``default=None`` coercion
    are not reported. task1b R1 narrowed "safe" to ``default=None`` only: ``or "0"``
    and ``.get(…, "0")`` now FLAG (see test_detector_flags_or_zero_money_coercion),
    so they no longer appear here."""
    src = (
        'avg_price = _num(x)  # money-zero-ok: deliberate zero for a dry-run stub\n'
        'price = _decimal_str(v, default=None)\n'
    )
    assert find_money_zero_defaults(src, "<synth>") == []


def test_detector_flags_or_zero_money_coercion():
    """task1b R1: a money identifier fed by ``or "0"`` / ``or '0'`` /
    ``.get(…, "0")`` / ``.get(…, '0')`` is flagged, with or without ``_num(`` /
    ``_decimal_str(` on the same line. These fabricated a real-looking zero when
    the source was missing — the r6 / API-projection shape."""
    src = (
        'avg_price = D.Decimal(x or "0")\n'           # no _num( at all
        'quote = _num(q) or "0"\n'                     # _num( AND or "0"
        "notional = d.get('cumulative_quote_amt', '0')\n"
        "price = _decimal_str(v) or '0'\n"
    )
    lines = {ln for ln, _t, _r in find_money_zero_defaults(src, "<synth>")}
    assert {1, 2, 3, 4} <= lines, "all four or-zero/get-zero money coercions must flag"


def test_detector_flags_subscript_or_attribute_augmented_money_target():
    """task1b R2: a money-named subscript/attribute target with an augmented
    assignment — the exact shape of S2 (``b["spot_notional"] += q * _num(…)``) —
    is flagged, where the old bare-name ``=`` rule saw nothing. A bare quantity
    subscript (``b["spot_qty"] += q``) is not money and stays unflagged."""
    src = (
        'b["spot_notional"] += q * _num(row["spot_avg_price"])\n'
        'self.cumulative_quote -= fee * _decimal_str(x)\n'
        'b["spot_qty"] += q\n'
    )
    lines = {ln for ln, _t, _r in find_money_zero_defaults(src, "<synth>")}
    assert 1 in lines and 2 in lines, "subscript/attribute money targets must flag"
    assert 3 not in lines, "quantity subscript must not flag"


def test_detector_anchors_single_line_sql_insert():
    """task1b R3a: a single-line ``INSERT INTO … '0'`` naming a money column is
    anchored and flagged. The anchor walk now starts at the ``'0'`` line, so the
    statement no longer has to span lines to be seen."""
    src = 'store.execute("INSERT INTO t (cumulative_quote_amt) VALUES (\'0\')")\n'
    findings = find_money_zero_defaults(src, "<synth>")
    assert findings, "single-line INSERT money-column '0' must be flagged"
    assert findings[0][0] == 1


# ---------------------------------------------------------------------------
# B-1 (stage 2026-08-06): the dry-run record-transport fill simulator is
# removed from production. Grep proof that neither the hedge-open domain package
# nor backend/services/ carries any ``RecordTransport`` reference — the class
# survives only as the test-only RecordTransportFake under backend/tests/.
# ---------------------------------------------------------------------------
def test_no_record_transport_reference_in_production_code():
    bad = []
    for scope in (HEDGE_PKG, REPO_ROOT / "backend" / "services"):
        for py in scope.rglob("*.py"):
            if "RecordTransport" in py.read_text(encoding="utf-8"):
                bad.append(str(py.relative_to(REPO_ROOT)))
    assert bad == [], (
        "RecordTransport reference found in production code (dry-run fill "
        f"simulator must not be reachable at runtime): {bad}"
    )
