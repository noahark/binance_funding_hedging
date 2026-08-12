"""Offline tests for the public-egress IP service + route (stage
2026-08-12-local-ip-display-v1).

Every transport is a fake; no real network leaves the process. Covers the
accepted plan's acceptance checks: primary success, 5-minute success/failure
cache with zero repeat outbound calls, primary-fail/invalid fallback to one
backup call, invalid/private backup rejection, two-source first-fail
``unavailable``, stale preserving the last successful ``checked_at``, the 64-byte
read cap, the HTTP 503-when-uninjected branch, and the exact four-field /
three-state 200 body with ``Cache-Control: no-store``. Also pins the R1
injection seam: ``build_server`` resets ``public_ip_service`` on every build,
and ``run()`` assigns it only after ``build_server`` returns.
"""
from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager

import pytest

from backend.app import server as server_module
from backend.app.server import _Handler, build_server
from backend.config import Config
from backend.services.public_ip_service import PublicIpService

PRIMARY = "https://api.ipify.org?format=json"
BACKUP = "https://checkip.amazonaws.com/"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, body, sink):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self._sink = sink

    def read(self, n=-1):
        self._sink.append(n)
        if n is None or n < 0:
            chunk, self._body = self._body, b""
        else:
            chunk, self._body = self._body[:n], self._body[n:]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeOpen:
    """Records every URL call; returns scripted responses per URL, in order."""

    def __init__(self):
        self.calls = []
        self.read_sizes = []
        self._script = {}

    def set(self, url, *responses):
        self._script[url] = list(responses)

    def __call__(self, url, timeout=None):
        self.calls.append(url)
        queue = self._script.get(url)
        if not queue:
            raise AssertionError(f"unexpected urlopen for {url}")
        resp = queue.pop(0)
        if isinstance(resp, BaseException):
            raise resp
        return _FakeResponse(resp, self.read_sizes)


class _Clock:
    def __init__(self, t0=1000.0):
        self.t = t0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _svc(fake, clock):
    return PublicIpService(urlopen=fake, clock=clock)


# --------------------------------------------------------------------------- #
# Service: primary success + exact shape
# --------------------------------------------------------------------------- #
def test_primary_success_exact_shape():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}')
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok"
    assert r["public_ip"] == "8.8.8.8"
    assert r["source"] == "api.ipify.org"
    assert isinstance(r["checked_at"], str) and r["checked_at"].endswith("Z")
    assert fake.calls == [PRIMARY]                      # backup never called


def test_primary_success_accepts_ipv6():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"2001:4860:4860::8888"}')
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok"
    assert r["public_ip"] == "2001:4860:4860::8888"
    assert fake.calls == [PRIMARY]


# --------------------------------------------------------------------------- #
# Service: 5-minute success cache -> zero repeat outbound
# --------------------------------------------------------------------------- #
def test_success_cache_no_repeat_within_ttl():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}')
    clock = _Clock()
    svc = _svc(fake, clock)
    svc.get()
    svc.get()
    clock.advance(299)                                 # still inside 5 minutes
    svc.get()
    assert fake.calls == [PRIMARY]                     # exactly one fetch, no repeats


def test_success_cache_refetches_after_ttl():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}', b'{"ip":"1.1.1.1"}')
    clock = _Clock()
    svc = _svc(fake, clock)
    first = svc.get()
    clock.advance(300)                                 # TTL boundary passed
    second = svc.get()
    assert first["public_ip"] == "8.8.8.8"
    assert second["public_ip"] == "1.1.1.1"
    assert fake.calls == [PRIMARY, PRIMARY]            # one refetch after expiry


# --------------------------------------------------------------------------- #
# Service: primary fail / invalid -> exactly one backup fallback
# --------------------------------------------------------------------------- #
def test_primary_exception_falls_back_to_backup_once():
    fake = _FakeOpen()
    fake.set(PRIMARY, OSError("network down"))
    fake.set(BACKUP, b"1.1.1.1\n")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok"
    assert r["public_ip"] == "1.1.1.1"
    assert r["source"] == "checkip.amazonaws.com"
    assert fake.calls == [PRIMARY, BACKUP]             # exactly one backup call


def test_primary_invalid_json_falls_back_to_backup():
    fake = _FakeOpen()
    fake.set(PRIMARY, b"<!DOCTYPE html><html>")        # hijack / non-JSON
    fake.set(BACKUP, b"1.1.1.1")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok" and r["public_ip"] == "1.1.1.1"
    assert fake.calls == [PRIMARY, BACKUP]


def test_primary_non_string_ip_falls_back_to_backup():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":12345}')                 # non-string ip
    fake.set(BACKUP, b"1.1.1.1")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok" and r["public_ip"] == "1.1.1.1"
    assert fake.calls == [PRIMARY, BACKUP]


# --------------------------------------------------------------------------- #
# Service: invalid / private backup rejected
# --------------------------------------------------------------------------- #
def test_invalid_backup_value_rejected_unavailable():
    fake = _FakeOpen()
    fake.set(PRIMARY, b"not json")
    fake.set(BACKUP, b"garbage-not-an-ip")
    r = _svc(fake, _Clock()).get()
    assert r == {"status": "unavailable", "public_ip": None,
                 "source": None, "checked_at": None}
    assert fake.calls == [PRIMARY, BACKUP]


def test_private_ip_rejected_falls_back_then_unavailable():
    # A private primary is rejected (must not pose as public egress) -> backup is
    # tried; a private backup is also rejected -> unavailable, no value invented.
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"192.168.1.5"}')
    fake.set(BACKUP, b"10.0.0.1")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "unavailable"
    assert r["public_ip"] is None
    assert fake.calls == [PRIMARY, BACKUP]


def test_private_primary_public_backup_succeeds():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"172.16.0.9"}')
    fake.set(BACKUP, b"1.1.1.1")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok" and r["public_ip"] == "1.1.1.1"
    assert r["source"] == "checkip.amazonaws.com"


# --------------------------------------------------------------------------- #
# Service: both fail first time -> unavailable
# --------------------------------------------------------------------------- #
def test_both_fail_first_time_unavailable():
    fake = _FakeOpen()
    fake.set(PRIMARY, OSError("down"))
    fake.set(BACKUP, OSError("down"))
    r = _svc(fake, _Clock()).get()
    assert r == {"status": "unavailable", "public_ip": None,
                 "source": None, "checked_at": None}


# --------------------------------------------------------------------------- #
# Service: failure cached -> zero new outbound within 5 minutes
# --------------------------------------------------------------------------- #
def test_failure_cached_no_repeat_within_ttl():
    fake = _FakeOpen()
    fake.set(PRIMARY, OSError("down"))
    fake.set(BACKUP, OSError("down"))
    clock = _Clock()
    svc = _svc(fake, clock)
    assert svc.get()["status"] == "unavailable"
    calls_after_first = len(fake.calls)
    clock.advance(120)
    assert svc.get()["status"] == "unavailable"
    clock.advance(120)
    assert svc.get()["status"] == "unavailable"
    assert len(fake.calls) == calls_after_first        # zero new outbound


# --------------------------------------------------------------------------- #
# Service: stale preserves last successful value + checked_at
# --------------------------------------------------------------------------- #
def test_stale_after_success_then_failure_preserves_last_success():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}')
    clock = _Clock()
    svc = _svc(fake, clock)
    ok = svc.get()
    assert ok["status"] == "ok" and ok["public_ip"] == "8.8.8.8"
    ok_checked_at = ok["checked_at"]

    clock.advance(400)                                 # past TTL
    fake.set(PRIMARY, OSError("down"))
    fake.set(BACKUP, OSError("down"))
    stale = svc.get()
    assert stale["status"] == "stale"
    assert stale["public_ip"] == "8.8.8.8"
    assert stale["source"] == "api.ipify.org"
    assert stale["checked_at"] == ok_checked_at        # last success time kept


# --------------------------------------------------------------------------- #
# Service: 64-byte read cap + truncation fail-closed
# --------------------------------------------------------------------------- #
def test_reads_at_most_64_bytes():
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}')
    _svc(fake, _Clock()).get()
    assert fake.read_sizes == [64]                      # single read, capped at 64


def test_truncates_long_body_and_falls_back():
    # The ip value sits past byte 64 -> a 64-byte read yields invalid JSON ->
    # fail-closed fallback to the backup source.
    body = b'{"padding":"' + b'x' * 60 + b'","ip":"8.8.8.8"}'
    assert len(body) > 64
    fake = _FakeOpen()
    fake.set(PRIMARY, body)
    fake.set(BACKUP, b"1.1.1.1")
    r = _svc(fake, _Clock()).get()
    assert r["status"] == "ok" and r["public_ip"] == "1.1.1.1"
    assert fake.read_sizes == [64, 64]


# --------------------------------------------------------------------------- #
# HTTP wire
# --------------------------------------------------------------------------- #
class _StubSnapshot:
    def get_snapshot(self):
        return {}


class _StubIpService:
    def __init__(self, payload):
        self._payload = payload

    def get(self):
        return dict(self._payload)


@contextmanager
def _server(public_ip_service):
    cfg = Config(bind_port=0)
    saved = _Handler.public_ip_service
    httpd = build_server(cfg, _StubSnapshot())        # resets public_ip_service=None
    _Handler.public_ip_service = public_ip_service    # assign AFTER build_server
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield host, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        _Handler.public_ip_service = saved


def _req(host, port, path):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    out = (resp.status, resp.getheader("Cache-Control"), resp.read())
    conn.close()
    return out


@pytest.mark.parametrize("payload", [
    {"status": "ok", "public_ip": "8.8.8.8", "source": "api.ipify.org",
     "checked_at": "2026-01-01T00:00:00Z"},
    {"status": "stale", "public_ip": "8.8.8.8", "source": "api.ipify.org",
     "checked_at": "2026-01-01T00:00:00Z"},
    {"status": "unavailable", "public_ip": None, "source": None,
     "checked_at": None},
])
def test_http_200_three_states_exact_fields_and_no_store(payload):
    with _server(_StubIpService(payload)) as (host, port):
        status, cache_ctrl, body = _req(host, port, "/api/system/public-ip")
    data = json.loads(body)
    assert status == 200
    assert cache_ctrl == "no-store"
    assert set(data.keys()) == {"status", "public_ip", "source", "checked_at"}
    assert data == payload


def test_http_503_when_not_injected():
    with _server(None) as (host, port):
        status, cache_ctrl, body = _req(host, port, "/api/system/public-ip")
    assert status == 503
    assert cache_ctrl is None                          # no-store only on 200
    assert json.loads(body) == {"error": "public_ip_unavailable"}


def test_http_response_not_merged_with_snapshot():
    # The endpoint returns only the IP contract over the wire — no snapshot rows
    # or data block are merged in.
    fake = _FakeOpen()
    fake.set(PRIMARY, b'{"ip":"8.8.8.8"}')
    with _server(PublicIpService(urlopen=fake, clock=_Clock())) as (host, port):
        status, _, body = _req(host, port, "/api/system/public-ip")
    data = json.loads(body)
    assert status == 200
    assert set(data.keys()) == {"status", "public_ip", "source", "checked_at"}
    assert "rows" not in data and "data" not in data


# --------------------------------------------------------------------------- #
# R1 injection seam: build_server resets; run() injects after build_server
# --------------------------------------------------------------------------- #
def test_build_server_resets_public_ip_service_each_call():
    cfg = Config(bind_port=0)
    first = build_server(cfg, _StubSnapshot())
    first.server_close()
    _Handler.public_ip_service = "sentinel"
    second = build_server(cfg, _StubSnapshot())
    try:
        assert _Handler.public_ip_service is None     # reset on every build
    finally:
        second.server_close()
        _Handler.public_ip_service = None


class _RunSnapshotStub:
    def __init__(self, config, **kwargs):
        self.config = config

    private_client = None

    def start_worker(self):
        pass

    def stop_worker(self):
        pass


class _NoopBorrow:
    is_execution_owner = True
    credentials_present = False

    class _Store:
        def count_live_authorized_tasks(self):
            return 0

        def count_pending_orphan_attempts(self):
            return 0

    store = _Store()

    def start(self):
        pass

    def stop(self):
        pass


class _NoopHedge:
    mode = "disabled"
    credentials_present = False

    def is_start_gate_on(self):
        return False

    def start(self):
        pass

    def stop(self):
        pass


class _ServeForeverStub:
    """serve_forever raises KeyboardInterrupt so run() exits its loop."""

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass


def test_run_injects_public_ip_after_build_server(monkeypatch, tmp_path):
    # Guards R1 read-B: run() must assign public_ip_service only AFTER build_server
    # returns. The real build_server resets the attr to None, so a before-call
    # assignment would be wiped (production route would 503 while every offline
    # test stayed green). We wrap the REAL build_server so its reset runs, then
    # assert both: (a) the attr is None while build_server runs, and (b) a real
    # PublicIpService is present after run() returns.
    seen_during_build = []
    real_build = server_module.build_server

    def wrapped_build(c, s):
        httpd = real_build(c, s)                       # real reset executes here
        seen_during_build.append(server_module._Handler.public_ip_service)
        httpd.server_close()                           # release the bound port
        return _ServeForeverStub()

    monkeypatch.setattr(server_module, "SnapshotService", _RunSnapshotStub)
    monkeypatch.setattr(server_module, "_build_borrow_service",
                        lambda cfg: _NoopBorrow())
    monkeypatch.setattr(server_module, "_build_hedge_service",
                        lambda cfg: _NoopHedge())
    monkeypatch.setattr(server_module, "build_server", wrapped_build)

    saved = server_module._Handler.public_ip_service
    try:
        server_module.run(Config(bind_port=0, borrow_db_path=tmp_path / "b.sqlite3"))
        assert seen_during_build == [None]             # not assigned before build_server
        assert isinstance(                             # assigned after build_server
            server_module._Handler.public_ip_service, PublicIpService)
    finally:
        server_module._Handler.public_ip_service = saved
