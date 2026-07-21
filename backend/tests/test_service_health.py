"""``GET /healthz`` and ``GET /readyz`` contract tests
(stage 2026-07-local-service-launchd-v1, breakdown §4 / amendment A5-A6).

Both routes are operational local contracts added to ``backend/app/server.py``:
secret-free, business-payload-free, and never echo raw exception text.

  /healthz  -> 200 + ``{"status":"ok","service":"com.aoke.funding-hedging.server"}``
  /readyz   -> 200 + ``{"status":"ready"}`` when a published snapshot is readable
               503 + ``{"status":"not_ready"}`` on cold start, SnapshotNotReady,
               or any other exception.

No network: an injected stub service covers ready/cold/exception shapes; a real
``SnapshotService`` in live mode with an empty published state proves the
readiness probe performs ZERO upstream I/O. The server runs in-process on an
OS-assigned loopback port (port 0); no real launchd or external dependency.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager

import pytest

from backend.app import server as server_module
from backend.app.server import build_server
from backend.borrow_tasks.domain import BLOCK_BORROW_CREDENTIALS_MISSING
from backend.config import Config
from backend.services.snapshot_service import SnapshotNotReady, SnapshotService

SERVICE = "com.aoke.funding-hedging.server"


class _StubService:
    """Minimal service stub: only ``get_snapshot()`` is exercised by /readyz."""

    def __init__(self, snapshot=None, exc=None):
        self._snapshot = snapshot
        self._exc = exc
        self.get_snapshot_calls = 0

    def get_snapshot(self):
        self.get_snapshot_calls += 1
        if self._exc is not None:
            raise self._exc
        return self._snapshot


@contextmanager
def _server(service):
    cfg = Config(bind_port=0)
    server = build_server(cfg, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def _get(base: str, path: str):
    try:
        with urllib.request.urlopen(base + path, timeout=3) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# =========================================================================
# /healthz — fixed 200 liveness body
# =========================================================================
def test_healthz_returns_fixed_200_body():
    service = _StubService(snapshot={"rows": []})
    with _server(service) as base:
        code, body = _get(base, "/healthz")
    assert code == 200
    assert json.loads(body) == {"status": "ok", "service": SERVICE}
    # liveness never touches the snapshot
    assert service.get_snapshot_calls == 0


def test_healthz_succeeds_even_when_snapshot_not_ready():
    # /healthz is liveness only: it must answer 200 regardless of readiness.
    service = _StubService(exc=SnapshotNotReady("cold"))
    with _server(service) as base:
        code, body = _get(base, "/healthz")
    assert code == 200
    assert json.loads(body) == {"status": "ok", "service": SERVICE}


# =========================================================================
# /readyz — ready 200 / cold start 503 / arbitrary exception 503
# =========================================================================
def test_readyz_ready_returns_200():
    service = _StubService(snapshot={"rows": [{"symbol": "BTCUSDT"}]})
    with _server(service) as base:
        code, body = _get(base, "/readyz")
    assert code == 200
    assert json.loads(body) == {"status": "ready"}
    assert service.get_snapshot_calls == 1


def test_readyz_ready_body_has_no_business_payload():
    service = _StubService(snapshot={"rows": [{"symbol": "BTCUSDT"}], "data_time": "X"})
    with _server(service) as base:
        _, body = _get(base, "/readyz")
    parsed = json.loads(body)
    assert set(parsed.keys()) == {"status"}
    raw = body.decode("utf-8")
    assert "BTCUSDT" not in raw
    assert "data_time" not in raw
    assert "rows" not in raw


def test_readyz_cold_start_returns_503():
    service = _StubService(exc=SnapshotNotReady("no published state yet"))
    with _server(service) as base:
        code, body = _get(base, "/readyz")
    assert code == 503
    assert json.loads(body) == {"status": "not_ready"}


def test_readyz_arbitrary_exception_returns_503_without_leaking_text():
    leak = "SECRET_LEAK_TOKEN_0xDEADBEEF_xyz"
    service = _StubService(exc=RuntimeError(leak))
    with _server(service) as base:
        code, body = _get(base, "/readyz")
    assert code == 503
    raw = body.decode("utf-8")
    assert leak not in raw
    assert "RuntimeError" not in raw
    parsed = json.loads(raw)
    assert set(parsed.keys()) == {"status"}
    assert parsed == {"status": "not_ready"}


# =========================================================================
# /readyz — zero upstream I/O on a REAL live-mode service (amendment A6)
# =========================================================================
class _RecordingPublic:
    """Records every upstream method; returns benign values if ever called.

    On the /readyz cold-start path ``get_snapshot()`` raises SnapshotNotReady
    before touching the client, so every list stays empty. If a regression made
    readiness trigger a fetch, the recorded call list would be non-empty.
    """

    offline = False

    def __init__(self):
        self.calls: list = []

    def fetch_raw(self):
        self.calls.append("fetch_raw")
        return {}

    def fetch_funding_rate(self, *args, **kwargs):
        self.calls.append("fetch_funding_rate")
        return []

    def fetch_premium_index_for(self, *args, **kwargs):
        self.calls.append("fetch_premium_index_for")
        return {}

    def fetch_ticker_price_map(self, *args, **kwargs):
        self.calls.append("fetch_ticker_price_map")
        return {}


class _StubPrivate:
    def __init__(self):
        self.last_error = "private_channel_disabled"

    def fetch_classic_reference(self):
        return None

    def fetch_cost_leg_chain(self, assets, *, force=False):
        return None

    def fetch_unified_balances(self):
        return None

    def fetch_um_positions(self):
        return None

    def fetch_spot_balances(self):
        return None

    def fetch_max_borrowable(self, asset, *, force=False):
        return None


def test_readyz_cold_start_triggers_no_upstream_io():
    cfg = Config(offline=False, bind_port=0)
    service = SnapshotService(cfg)  # live mode; no worker started by build_server
    public = _RecordingPublic()
    service.client = public
    service._private = _StubPrivate()
    # NOTE: _scheduled_tick() is intentionally NOT called -> _published_state
    # is None -> cold start.
    with _server(service) as base:
        code, body = _get(base, "/readyz")
    assert code == 503
    assert json.loads(body) == {"status": "not_ready"}
    assert public.calls == []  # zero upstream I/O on the readiness probe


# =========================================================================
# routes do not shadow existing /api/* or static behavior; content-type check
# =========================================================================
def test_healthz_content_type_is_json():
    service = _StubService(snapshot={"rows": []})
    cfg = Config(bind_port=0)
    server = build_server(cfg, service)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        with urllib.request.urlopen(base + "/healthz", timeout=3) as resp:
            assert resp.headers.get("Content-Type") == "application/json; charset=utf-8"
    finally:
        server.shutdown()
        server.server_close()


def test_unknown_health_path_is_not_healthz():
    # A path that merely contains 'healthz' must not match the fixed route.
    service = _StubService(snapshot={"rows": []})
    with _server(service) as base:
        code, _ = _get(base, "/healthz/extra")
    # Falls through to static serving -> 404 (not the healthz 200 body).
    assert code == 404


# =========================================================================
# lifecycle (server_start / server_fatal_error / server_stop) — amendment A7
# =========================================================================
def _parse_lifecycle(stderr_text: str):
    events = []
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


class _RunStubService:
    """Stub for ``run()``: records worker lifecycle and raises on demand."""

    def __init__(self, config):
        self.config = config
        self.start_calls = 0
        self.stop_calls = 0
        self.start_exc = None

    def start_worker(self):
        self.start_calls += 1
        if self.start_exc is not None:
            raise self.start_exc

    def stop_worker(self):
        self.stop_calls += 1


class _StubServer:
    """Stub HTTP server: serve_forever raises the injected exception."""

    def __init__(self, loop_exc=None):
        self._loop_exc = loop_exc
        self.close_calls = 0

    def serve_forever(self):
        if self._loop_exc is None:
            raise AssertionError("serve_forever called without an injected exc")
        raise self._loop_exc

    def server_close(self):
        self.close_calls += 1


def test_run_fatal_when_start_worker_raises(monkeypatch, capsys):
    secret = "WORKER-BOOM-SECRET-xyz"
    instances = []

    def fake_service(config):
        svc = _RunStubService(config)
        svc.start_exc = RuntimeError(secret)
        instances.append(svc)
        return svc

    srv = _StubServer(loop_exc=None)
    monkeypatch.setattr(server_module, "SnapshotService", fake_service)
    monkeypatch.setattr(server_module, "build_server", lambda c, s: srv)

    with pytest.raises(SystemExit) as exc:
        server_module.run(Config(bind_port=0))
    assert exc.value.code == 1

    err = capsys.readouterr().err
    assert secret not in err  # exception text never emitted
    events = _parse_lifecycle(err)
    names = [e["event"] for e in events]
    assert "server_start" in names
    assert "server_fatal_error" in names
    assert events[-1]["event"] == "server_stop"
    fatal = next(e for e in events if e["event"] == "server_fatal_error")
    assert fatal.get("exception_class") == "RuntimeError"
    # start failed; serve_forever never ran; worker stopped safely; server closed
    assert instances[0].start_calls == 1
    assert instances[0].stop_calls == 1
    assert srv.close_calls == 1


def test_run_fatal_when_serve_forever_raises(monkeypatch, capsys):
    secret = "LOOP-BOOM-SECRET-abc"
    instances = []

    def fake_service(config):
        svc = _RunStubService(config)
        instances.append(svc)
        return svc

    srv = _StubServer(loop_exc=RuntimeError(secret))
    monkeypatch.setattr(server_module, "SnapshotService", fake_service)
    monkeypatch.setattr(server_module, "build_server", lambda c, s: srv)

    with pytest.raises(SystemExit) as exc:
        server_module.run(Config(bind_port=0))
    assert exc.value.code == 1

    err = capsys.readouterr().err
    assert secret not in err
    events = _parse_lifecycle(err)
    names = [e["event"] for e in events]
    assert "server_start" in names
    assert "server_fatal_error" in names
    assert events[-1]["event"] == "server_stop"
    fatal = next(e for e in events if e["event"] == "server_fatal_error")
    assert fatal.get("exception_class") == "RuntimeError"
    assert instances[0].start_calls == 1
    assert instances[0].stop_calls == 1
    assert srv.close_calls == 1


def test_run_keyboard_interrupt_cleans_up_and_exits_zero(monkeypatch, capsys):
    instances = []

    def fake_service(config):
        svc = _RunStubService(config)
        instances.append(svc)
        return svc

    srv = _StubServer(loop_exc=KeyboardInterrupt())
    monkeypatch.setattr(server_module, "SnapshotService", fake_service)
    monkeypatch.setattr(server_module, "build_server", lambda c, s: srv)

    # the normal/keyboard path does NOT raise SystemExit
    server_module.run(Config(bind_port=0))

    err = capsys.readouterr().err
    events = _parse_lifecycle(err)
    names = [e["event"] for e in events]
    assert "server_start" in names
    assert "server_stop" in names
    assert "server_fatal_error" not in names
    assert instances[0].start_calls == 1
    assert instances[0].stop_calls == 1
    assert srv.close_calls == 1


# =========================================================================
# borrow startup observability (Boundary C D2/D7 / §3.4) — bookkeeper BK-C-004
# =========================================================================
class _StubBorrowStore:
    """Only the two sanitized integer counts the startup event reads."""

    def __init__(self, live_authorized=0, orphan=0):
        self._live_authorized = live_authorized
        self._orphan = orphan

    def count_live_authorized_tasks(self):
        return self._live_authorized

    def count_pending_orphan_attempts(self):
        return self._orphan


class _StubBorrowService:
    """Stand-in for BorrowTaskService: exposes only the sanitized startup facts."""

    def __init__(self, *, credentials_present, owner=True, live_authorized=0, orphan=0):
        self.credentials_present = credentials_present
        self.is_execution_owner = owner
        self.store = _StubBorrowStore(live_authorized, orphan)

    def start(self):
        pass

    def stop(self):
        pass


def _wire_run(monkeypatch, borrow_service):
    # Drive run() straight into the KeyboardInterrupt exit so it emits the
    # borrow startup events and then cleans up, without a real HTTP loop.
    monkeypatch.setattr(server_module, "SnapshotService", _RunStubService)
    monkeypatch.setattr(
        server_module, "build_server", lambda c, s: _StubServer(loop_exc=KeyboardInterrupt())
    )
    monkeypatch.setattr(server_module, "_build_borrow_service", lambda config: borrow_service)


def test_run_emits_borrow_execution_mode_with_recovery_counts(monkeypatch, capsys):
    # D2/D7: startup emits the sanitized borrow mode event carrying the frozen
    # recovery counts (live-authorized tasks + recovered orphan blockers) as
    # plain integers plus the ownership boolean — no secret value on stderr.
    _wire_run(
        monkeypatch,
        _StubBorrowService(credentials_present=False, owner=True,
                           live_authorized=2, orphan=1),
    )
    server_module.run(Config(borrow_executor="disabled", bind_port=0))

    events = _parse_lifecycle(capsys.readouterr().err)
    mode = next(e for e in events if e["event"] == "borrow_execution_mode")
    assert mode["mode"] == "disabled"
    assert mode["execution_owner"] is True
    assert mode["live_authorized_task_count"] == 2
    assert mode["recovered_orphan_blocker_count"] == 1
    # Not blocked: no distinct blocked event in this (non-live) startup.
    assert "borrow_execution_blocked" not in [e["event"] for e in events]


def test_run_live_missing_credentials_emits_distinct_blocked_event(monkeypatch, capsys):
    # §3.4: live mode with empty dedicated credentials still starts and serves,
    # but emits a DISTINCT sanitized blocked event marking the missing creds.
    # The credential VALUE is never on stderr — only the boolean presence is.
    secret = "LIVE-BORROW-SECRET-DO-NOT-LOG-xyz"
    _wire_run(
        monkeypatch,
        _StubBorrowService(credentials_present=False, owner=True),
    )
    server_module.run(Config(
        borrow_executor="live",
        binance_borrow_api_key=secret,
        binance_borrow_api_secret=secret,
        bind_port=0,
    ))

    err = capsys.readouterr().err
    events = _parse_lifecycle(err)
    names = [e["event"] for e in events]
    assert "borrow_execution_mode" in names
    blocked = next((e for e in events if e["event"] == "borrow_execution_blocked"), None)
    assert blocked is not None
    assert blocked["borrow_executor"] == "live"
    assert blocked["borrow_execution_blocked"] == BLOCK_BORROW_CREDENTIALS_MISSING
    assert secret not in err  # credential value never emitted
