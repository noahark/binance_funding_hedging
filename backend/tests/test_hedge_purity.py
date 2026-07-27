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
