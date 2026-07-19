"""Executor seam + zero-network / no-credential proofs (breakdown §3.9 / §5.1-9).

Covers DisabledBorrowExecutor (the only runtime-reachable executor), the
test-only PaperBorrowExecutor, the grep-level proof that the borrow package
uses no network or signing primitives, a runtime proof that a full scheduler +
API scenario issues zero ``urlopen`` calls, and a proof that poisoned
environment secrets never reach the ledger or any API body.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import urllib.request

from backend.borrow_tasks import domain as D
from backend.borrow_tasks.executor import DisabledBorrowExecutor, ExecutorResult
from backend.borrow_tasks.service import BorrowTaskService
from backend.tests.borrow_paper_executor import (
    PaperBorrowExecutor,
    execution_disabled,
    known_rejection,
    rate_limited,
    success,
    unknown,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BORROW_PKG = REPO_ROOT / "backend" / "borrow_tasks"


class _Clock:
    def __init__(self, t0=0):
        self.t = t0

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


# ---------------------------------------------------------------------------
# DisabledBorrowExecutor — the only runtime-reachable executor
# ---------------------------------------------------------------------------
def test_disabled_executor_returns_execution_disabled_with_no_io():
    result = DisabledBorrowExecutor().execute({"id": "t"}, {"id": 1})
    assert result.result_category == D.RESULT_EXECUTION_DISABLED
    assert result.reason == "executor_disabled"
    assert result.tran_id is None
    assert result.retry_after_seconds is None


def test_service_default_executor_is_disabled(tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    assert isinstance(svc._executor, DisabledBorrowExecutor)


# ---------------------------------------------------------------------------
# PaperBorrowExecutor — deterministic scripted replay (test-only)
# ---------------------------------------------------------------------------
def test_paper_executor_replays_categories_in_order_then_holds_last():
    exe = PaperBorrowExecutor(
        [success("t1"), known_rejection(), rate_limited(3), unknown(), execution_disabled()]
    )
    outs = [exe.execute({"id": "a"}, {"id": i}) for i in range(6)]
    categories = [o.result_category for o in outs[:5]]
    assert categories == [
        D.RESULT_SUCCESS,
        D.RESULT_KNOWN_REJECTION,
        D.RESULT_RATE_LIMITED,
        D.RESULT_UNKNOWN,
        D.RESULT_EXECUTION_DISABLED,
    ]
    assert outs[5].result_category == D.RESULT_EXECUTION_DISABLED   # holds last
    assert outs[0].tran_id == "t1"
    assert exe.calls[0] == ("a", 0, D.RESULT_SUCCESS)


# ---------------------------------------------------------------------------
# AST-level proof: no network / signing modules are imported in the borrow
# package (substring grep would false-flag the docstrings that document the
# prohibition; an import scan is the precise, honest proof).
# ---------------------------------------------------------------------------
def test_no_network_or_signing_imports_in_borrow_package():
    import ast

    forbidden_roots = {"urllib", "http", "socket", "hmac", "hashlib", "ssl", "requests"}
    bad = []
    for py in BORROW_PKG.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_roots:
                        bad.append((py.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in forbidden_roots:
                    bad.append((py.name, node.module))
    assert bad == [], f"forbidden network/signing imports in borrow_tasks: {bad}"


def test_paper_executor_lives_outside_product_package():
    # PaperBorrowExecutor must NOT be importable from the product package, so no
    # runtime config can ever select it.
    import backend.borrow_tasks as pkg
    assert not hasattr(pkg, "PaperBorrowExecutor")


# ---------------------------------------------------------------------------
# Runtime proof: a full scenario issues ZERO urllib calls
# ---------------------------------------------------------------------------
def test_full_scenario_makes_zero_urllib_calls(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("urlopen must never be called on a borrow path")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    clock = _Clock(0)
    exe = PaperBorrowExecutor(
        [success(), unknown(), rate_limited(2), known_rejection(), execution_disabled()]
    )
    svc = BorrowTaskService(
        str(tmp_path / "bt.sqlite3"),
        executor=exe,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.put_settings({"interval_seconds": "1"})
    for asset in ("BTC", "ETH", "XRP", "SOL", "ADA"):
        svc.create_task({"asset": asset, "amount_per_attempt": "1", "success_target": 9})
    for t in range(5):
        clock.t = t * 1_000_000
        svc.tick()                    # exercises every category
    # exercise the read API surface too
    svc.list_tasks()
    svc.get_settings()
    svc.get_logs(None, None)
    # reaching here proves no borrow path attempted a network call


# ---------------------------------------------------------------------------
# No-credential proof: poisoned env secrets never reach ledger or API bodies
# ---------------------------------------------------------------------------
def test_poisoned_env_secrets_never_leak(tmp_path, monkeypatch):
    secrets = {
        "BINANCE_API_KEY": "SECRETKEY-AAAA",
        "BINANCE_API_SECRET": "SECRETSECRET-BBBB",
        "BINANCE_SIGNATURE": "SIG-CCCC-DDDD",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    clock = _Clock(0)
    svc = BorrowTaskService(
        str(tmp_path / "bt.sqlite3"),
        executor=PaperBorrowExecutor([execution_disabled()]),
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.put_settings({"interval_seconds": "1"})
    svc.create_task({"asset": "BTC", "amount_per_attempt": "1", "success_target": 5})
    clock.t = 0
    svc.tick()
    _, tasks = svc.list_tasks()
    _, logs = svc.get_logs(None, None)
    _, settings = svc.get_settings()
    blob = json.dumps([tasks, logs, settings])
    for secret in secrets.values():
        assert secret not in blob
    # executor reasons are sanitized controlled vocabulary only
    for entry in logs["entries"]:
        assert entry["reason"] in (None, "executor_disabled")
