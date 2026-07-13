#!/usr/bin/env python3
"""Deterministic tests for ``scripts/service-control.py``
(stage 2026-07-local-service-launchd-v1, breakdown §2-§3-§5 / amendment A4-A5).

The controller is loaded via importlib because ``service-control.py`` has a
hyphen filename (not a valid Python identifier). A fake subprocess executor
records argv and returns canned ``CompletedProcess`` results; LaunchAgents and
Logs directories point at a temp dir. Together these prove the user's real
``~/Library/LaunchAgents`` domain is never mutated and the real ``launchctl``
binary is never spawned.

Coverage:
  * plist renders and re-parses through ``plistlib`` with the exact frozen keys;
  * a repository path containing spaces / XML metacharacters stays valid;
  * the plist never embeds secrets (.env / BINANCE_*);
  * each launchctl verb builds the exact frozen argv via the fake executor;
  * every mutating command refuses without ``--confirm`` (no subprocess call);
  * the resolved install target is inside tmp_path (no real-domain mutation);
  * the real home LaunchAgents plist is not touched by the suite;
  * ``status`` / ``doctor`` produce the §5.2 / §5.3 fields, correct exit codes,
    the 200-line tail cap, and secret redaction.
  * install/restart run a bounded post-bootstrap readiness poll before claiming
    success (review-2 P2): bounded attempt ceiling, retained plist, redacted
    actionable stderr, zero real network / zero real waiting.
"""
from __future__ import annotations

import importlib.util
import json
import plistlib
import socket
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

REPO_ROOT = _SCRIPTS.parent
REAL_HOME_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.aoke.funding-hedging.server.plist"

UID = 501  # fixed, non-secret test uid; never the live os.getuid() value


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "service_control_under_test", _SCRIPTS / "service-control.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec_module: ``service-control.py`` uses
    # ``from dataclasses import dataclass, field`` and a ``@dataclass`` whose
    # field defaults (e.g. ``field(default_factory=os.getuid)``) resolve the
    # module mid-execution. On the repository's Python 3.9 the unregistered
    # module raises from dataclasses and every test using this fixture errors
    # (the 31 setup errors seen in bookkeeper reconciliation).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


class FakeExecutor:
    """Records argv; returns canned CompletedProcess via per-argv[0] callables."""

    def __init__(self):
        self.calls: list = []
        self._handlers = {}

    def on(self, key, fn):
        self._handlers[key] = fn
        return self

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        fn = self._handlers.get(argv[0])
        if fn is None:
            return subprocess.CompletedProcess(argv, 0, "", "")
        return fn(argv)

    def launchctl_calls(self, verb):
        return [c for c in self.calls if c[0] == "launchctl" and len(c) > 1 and c[1] == verb]


def _cp(argv, rc=0, out="", err=""):
    return subprocess.CompletedProcess(list(argv), rc, out, err)


def _ready_200_probe(path, timeout=2.0):
    # Default readiness collaborator for install/restart success-path tests
    # (review-2 P2): both /healthz and /readyz report HTTP 200 so the bounded
    # poll returns on the first attempt with zero real network and zero real
    # waiting. status/doctor bypass this because they call self._probe directly.
    return (200, "")


def _no_sleep(seconds):
    # Default sleeper: never blocks. Keeps the readiness wait out of the suite
    # entirely; failing-ceiling tests inject a counting sleeper instead.
    return None


def _controller(mod, tmp_path, *, fake=None, base_url=None, repo=None, launchagents=None, logs=None, probe=None, sleeper=None):
    repo = repo or (tmp_path / "repo")
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "run-server.sh").write_text("#!/bin/bash\n")
    launchagents = launchagents or (tmp_path / "LaunchAgents")
    logs = logs or (tmp_path / "logs")
    return mod.ServiceControl(
        repo_root=repo,
        uid=UID,
        executor=fake or FakeExecutor(),
        launchagents_dir=launchagents,
        logs_dir=logs,
        base_url=base_url or mod.DEFAULT_BASE_URL,
        probe=_ready_200_probe if probe is None else probe,
        sleeper=_no_sleep if sleeper is None else sleeper,
    )


# =========================================================================
# Plist rendering — re-parse, exact keys, space/XML-safe, secret-free
# =========================================================================
def test_plist_roundtrips_through_plistlib_with_exact_keys(mod, tmp_path):
    ctrl = _controller(mod, tmp_path)
    parsed = plistlib.loads(ctrl.render_text().encode("utf-8"))
    run_server = str(ctrl.repo_root / "scripts" / "run-server.sh")
    assert parsed["Label"] == mod.LABEL
    assert parsed["ProgramArguments"] == ["/bin/bash", run_server]
    assert parsed["WorkingDirectory"] == str(ctrl.repo_root)
    assert parsed["RunAtLoad"] is True
    assert parsed["KeepAlive"] is True
    assert parsed["ThrottleInterval"] == 10
    assert parsed["ProcessType"] == "Background"
    assert parsed["EnvironmentVariables"] == {
        "PYTHONUNBUFFERED": "1",
        "PYTHONFAULTHANDLER": "1",
    }
    assert parsed["StandardOutPath"] == str(ctrl.stdout_log)
    assert parsed["StandardErrorPath"] == str(ctrl.stderr_log)


def test_plist_repo_path_with_space_and_xml_chars_stays_valid(mod, tmp_path):
    # A repo path containing spaces and XML metacharacters must round-trip
    # through plistlib, which XML-escapes <, >, &. Validate the escaping and the
    # re-parse, not a raw literal ``<>&`` run appearing unescaped in the XML.
    weird = tmp_path / "ai code" / "repo<>&'\""
    weird.mkdir(parents=True, exist_ok=True)
    ctrl = _controller(mod, tmp_path, repo=weird)
    text = ctrl.render_text()
    parsed = plistlib.loads(text.encode("utf-8"))
    assert parsed["WorkingDirectory"] == str(weird)
    assert parsed["ProgramArguments"][1] == str(weird / "scripts" / "run-server.sh")
    # the space survives unescaped (proves the path was serialized); the raw
    # metacharacter run never appears literally because plistlib escaped it.
    assert "ai code" in text
    assert "repo<>&" not in text


def test_plist_contains_no_secrets(mod, tmp_path):
    ctrl = _controller(mod, tmp_path)
    text = ctrl.render_text()
    for needle in (".env", "BINANCE", "API_KEY", "API_SECRET", "SECRET", "TOKEN"):
        assert needle not in text, f"plist leaks secret-like token: {needle}"
    parsed = plistlib.loads(text.encode("utf-8"))
    assert "EnvironmentVariables" in parsed
    # only the two non-secret Python env vars are present
    assert set(parsed["EnvironmentVariables"]) == {"PYTHONUNBUFFERED", "PYTHONFAULTHANDLER"}


# =========================================================================
# launchctl argv — exact frozen construction via the fake executor
# =========================================================================
def test_install_bootstrap_argv_when_not_loaded(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.install(confirm=True)
    assert rc == 0
    # exact frozen bootstrap argv
    assert ctrl._install_argv() in fake.calls
    assert ["launchctl", "bootstrap", f"gui/{UID}", str(ctrl.plist_path)] in fake.calls
    # plist was written to the tmp LaunchAgents dir
    assert ctrl.plist_path.is_file()
    # round-trips
    plistlib.loads(ctrl.plist_path.read_bytes())


def test_install_refuses_when_already_loaded(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0, out="pid = 1234\nstate = running") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.install(confirm=True)
    assert rc != 0
    # already loaded -> bootstrap must NEVER be called
    assert fake.launchctl_calls("bootstrap") == []
    # and the plist must not have been written (fail before side effect)
    assert not ctrl.plist_path.exists()


def test_start_kickstart_argv(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0, out="state = running") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.start(confirm=True)
    assert rc == 0
    assert ctrl._start_argv() in fake.calls
    assert ["launchctl", "kickstart", f"gui/{UID}/{mod.LABEL}"] in fake.calls


def test_start_fails_when_not_loaded(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.start(confirm=True)
    assert rc != 0
    assert fake.launchctl_calls("kickstart") == []


def test_stop_bootout_argv(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0, out="state = running") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.stop(confirm=True)
    assert rc == 0
    assert ctrl._stop_argv() in fake.calls
    assert ["launchctl", "bootout", f"gui/{UID}/{mod.LABEL}"] in fake.calls


def test_stop_fails_when_not_loaded(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.stop(confirm=True)
    assert rc != 0
    assert fake.launchctl_calls("bootout") == []


def test_restart_bootout_then_bootstrap_argv(mod, tmp_path):
    sequence = {"i": 0}

    def launchctl(a):
        if a[1] == "print":
            return _cp(a, rc=0, out="state = running")
        sequence["i"] += 1
        return _cp(a, rc=0)

    fake = FakeExecutor().on("launchctl", launchctl)
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.restart(confirm=True)
    assert rc == 0
    verbs = [c[1] for c in fake.calls if c[0] == "launchctl" and c[1] != "print"]
    # bootout (stop) must precede bootstrap (start) so the plist is re-read
    assert verbs == ["bootout", "bootstrap"]


def test_restart_fails_whole_command_if_bootout_fails(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0, out="state = running")
        if a[1] == "print"
        else (_cp(a, rc=5, err="bootout failed") if a[1] == "bootout" else _cp(a, rc=0)),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.restart(confirm=True)
    assert rc != 0
    # bootout failed -> bootstrap must NOT be attempted
    assert fake.launchctl_calls("bootstrap") == []


def test_uninstall_bootout_then_unlink_keeps_logs(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0) if a[1] == "bootout" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    # a log file exists and must be retained
    ctrl.stderr_log.parent.mkdir(parents=True, exist_ok=True)
    ctrl.stderr_log.write_text("some log\n")
    rc = ctrl.uninstall(confirm=True)
    assert rc == 0
    assert ["launchctl", "bootout", f"gui/{UID}/{mod.LABEL}"] in fake.calls
    assert not ctrl.plist_path.exists()
    assert ctrl.stderr_log.exists()  # logs retained


def test_uninstall_tolerates_not_loaded_result(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=36, err="Bootout failed: Could not find service")
        if a[1] == "bootout"
        else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.uninstall(confirm=True)
    assert rc == 0
    assert not ctrl.plist_path.exists()


def test_uninstall_fails_on_other_bootout_error(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="operation not permitted")
        if a[1] == "bootout"
        else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.uninstall(confirm=True)
    assert rc != 0
    # a non not-loaded error must NOT remove the plist
    assert ctrl.plist_path.exists()


# =========================================================================
# --confirm gate — mutating commands refuse and never call the executor
# =========================================================================
@pytest.mark.parametrize("command", ["install", "start", "stop", "restart", "uninstall"])
def test_mutating_commands_refuse_without_confirm(mod, tmp_path, command):
    fake = FakeExecutor()
    ctrl = _controller(mod, tmp_path, fake=fake)
    method = getattr(ctrl, command)
    rc = method(confirm=False)
    assert rc != 0
    assert fake.calls == []  # zero subprocess invocations without --confirm


def test_render_is_non_mutating_and_writes_no_dir(mod, tmp_path, capsys):
    fake = FakeExecutor()
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.render()
    assert rc == 0
    out = capsys.readouterr().out
    assert "<plist version=" in out
    assert mod.LABEL in out
    # render must NOT write the LaunchAgents dir, NOT create the logs dir, and
    # NOT call any subprocess (amendment: render stays side-effect free).
    assert not ctrl.plist_path.exists()
    assert not ctrl.logs_dir.exists()
    assert not ctrl.launchagents_dir.exists()
    assert fake.calls == []


# =========================================================================
# External-side-effect isolation — tmp target, real domain untouched
# =========================================================================
def test_resolved_install_target_is_inside_tmp(mod, tmp_path):
    ctrl = _controller(mod, tmp_path)
    assert ctrl.launchagents_dir == tmp_path / "LaunchAgents"
    assert ctrl.logs_dir == tmp_path / "logs"
    # the install target plist path is beneath tmp_path, never the home dir
    assert str(ctrl.plist_path).startswith(str(tmp_path))
    assert ctrl.plist_path != REAL_HOME_PLIST


def test_real_home_launchagents_plist_not_touched_by_suite(mod, tmp_path):
    # Belt-and-suspenders: even if the real plist exists on this machine, the
    # suite (which uses tmp dirs) must not create or modify it.
    before_exists = REAL_HOME_PLIST.exists()
    before_mtime = REAL_HOME_PLIST.stat().st_mtime if before_exists else None

    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.install(confirm=True)  # writes only under tmp_path
    ctrl.uninstall(confirm=True)

    after_exists = REAL_HOME_PLIST.exists()
    after_mtime = REAL_HOME_PLIST.stat().st_mtime if after_exists else None
    assert before_exists == after_exists
    if before_exists:
        assert before_mtime == after_mtime


# =========================================================================
# Health probe server (status exit codes) + base-url resolution
# =========================================================================
@contextmanager
def _health_server(health_code=200, ready_code=200):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            return

        def do_GET(self):
            if self.path == "/healthz":
                code = self.server._health_code
            elif self.path == "/readyz":
                code = self.server._ready_code
            else:
                code = 404
            body = b'{"status":"ok"}' if code == 200 else b'{"status":"not_ready"}'
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv._health_code = health_code
    srv._ready_code = ready_code
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def _closed_port_url():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


def _git_handler(commit="abc1234", dirty=False):
    def git(a):
        if "rev-parse" in a:
            return _cp(a, rc=0, out=f"{commit}\n")
        if "status" in a:
            return _cp(a, rc=0, out=" M file\n" if dirty else "")
        return _cp(a, rc=0)
    return git


def test_status_green_exits_zero_with_all_fields(mod, tmp_path, capsys):
    with _health_server(200, 200) as base:
        fake = FakeExecutor()
        fake.on("launchctl", lambda a: _cp(a, rc=0, out="pid = 4242\nstate = running\n") if a[1] == "print" else _cp(a, rc=0))
        fake.on("git", _git_handler("abc1234", dirty=False))
        ctrl = _controller(mod, tmp_path, fake=fake, base_url=base)
        rc = ctrl.status()
    out = capsys.readouterr().out
    assert rc == 0
    assert "loaded: True" in out
    assert "pid: 4242" in out
    assert f"url: {base}" in out
    assert "health (/healthz): 200" in out
    assert "readiness (/readyz): 200" in out
    assert "commit: abc1234" in out
    assert "dirty: clean" in out
    assert str(ctrl.stdout_log) in out
    assert str(ctrl.stderr_log) in out
    # read-only: only print + git, no mutating launchctl verb
    assert fake.launchctl_calls("bootstrap") == []
    assert fake.launchctl_calls("bootout") == []
    assert fake.launchctl_calls("kickstart") == []


def test_status_unreachable_reports_unreachable_and_nonzero(mod, tmp_path, capsys):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    rc = ctrl.status()
    out = capsys.readouterr().out
    assert rc != 0  # not all of loaded/health/ready succeeded
    assert "unreachable" in out
    assert "Traceback" not in out


def test_status_not_loaded_nonzero(mod, tmp_path, capsys):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    rc = ctrl.status()
    out = capsys.readouterr().out
    assert rc != 0
    assert "loaded: False" in out


def test_status_dirty_flag_reports_dirty(mod, tmp_path, capsys):
    with _health_server(200, 200) as base:
        fake = FakeExecutor()
        fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
        fake.on("git", _git_handler("deadbeef", dirty=True))
        ctrl = _controller(mod, tmp_path, fake=fake, base_url=base)
        rc = ctrl.status()
    out = capsys.readouterr().out
    assert "commit: deadbeef" in out
    assert "dirty: dirty" in out


def test_base_url_resolution_precedence(mod, monkeypatch):
    # CLI value wins over env wins over default (amendment A2).
    monkeypatch.setenv("FUNDING_HEDGING_SERVICE_URL", "http://env.example:9999")
    assert mod._resolve_base_url("http://cli.example:1") == "http://cli.example:1"
    assert mod._resolve_base_url(None) == "http://env.example:9999"
    monkeypatch.delenv("FUNDING_HEDGING_SERVICE_URL", raising=False)
    assert mod._resolve_base_url(None) == mod.DEFAULT_BASE_URL


# =========================================================================
# doctor — bounded bundle, exit codes, 200-line cap, secret redaction
# =========================================================================
def test_doctor_writes_bundle_and_exits_zero_when_service_down(mod, tmp_path, capsys):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    rc = ctrl.doctor()
    out = capsys.readouterr().out
    assert rc == 0  # bundle captured even though service is down
    assert "bundle written" in out
    # regression for the resolved load state referenced in the success line
    # (a stale ``loaded`` name would raise NameError and drop this line).
    assert "loaded=" in out
    # bundle lives ONLY beneath the configured (tmp) logs diagnostics dir
    bundles = list(ctrl.diagnostics_dir.glob("*"))
    assert len(bundles) == 1
    bundle = bundles[0]
    assert str(bundle).startswith(str(tmp_path))
    summary = json.loads((bundle / "bundle.json").read_text())
    assert summary["label"] == mod.LABEL
    assert summary["loaded"] is False
    assert summary["health"] is None  # unreachable
    assert summary["readiness"] is None
    assert summary["tail_lines"] == 200
    assert (bundle / "launchctl-print.txt").exists()
    assert (bundle / "stdout-tail.txt").exists()
    assert (bundle / "stderr-tail.txt").exists()


def test_doctor_tails_at_most_200_lines(mod, tmp_path):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    ctrl.stdout_log.parent.mkdir(parents=True, exist_ok=True)
    # 500 lines; the last 200 must be kept, earlier ones dropped.
    lines = [f"line {i}\n" for i in range(500)]
    ctrl.stdout_log.write_text("".join(lines))
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    tail = (bundle / "stdout-tail.txt").read_text()
    tail_lines = tail.splitlines()
    assert len(tail_lines) <= 200
    assert "line 499" in tail  # last line kept
    assert "line 499" == tail_lines[-1]
    assert "line 100" not in tail  # beyond the 200-line window, dropped


def test_doctor_redacts_secret_kv_in_stderr_tail(mod, tmp_path):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    ctrl.stderr_log.parent.mkdir(parents=True, exist_ok=True)
    ctrl.stderr_log.write_text(
        "startup line\n"
        "BINANCE_API_KEY=AKIAsupersecret0123\n"
        "BINANCE_API_SECRET=0xDEADBEEFcafef00d\n"
        "token: abcdef1234567890\n"
    )
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    stderr_tail = (bundle / "stderr-tail.txt").read_text()
    assert "BINANCE_API_KEY=[REDACTED]" in stderr_tail
    assert "BINANCE_API_SECRET=[REDACTED]" in stderr_tail
    # the raw secret values must never reach the bundle
    assert "AKIAsupersecret0123" not in stderr_tail
    assert "0xDEADBEEFcafef00d" not in stderr_tail


def test_doctor_redacts_in_launchctl_print_and_summary_is_secret_free(mod, tmp_path):
    secret = "SUPERSECRET_LAUNCHCTL_BLOB"
    fake = FakeExecutor()
    fake.on(
        "launchctl",
        lambda a: _cp(a, rc=0, out=f"state = running\nAPI_KEY={secret}\n") if a[1] == "print" else _cp(a, rc=0),
    )
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    print_text = (bundle / "launchctl-print.txt").read_text()
    assert secret not in print_text
    assert "API_KEY=[REDACTED]" in print_text


# =========================================================================
# amendment A2 — base URL validation (no credential/query/fragment/path echo)
# =========================================================================
@pytest.mark.parametrize(
    "bad",
    [
        "http://user:pass@127.0.0.1:8787",        # userinfo credentials
        "http://127.0.0.1:8787/healthz",          # non-root path
        "http://127.0.0.1:8787/?signature=abc",   # query string (signed)
        "http://127.0.0.1:8787#frag",             # fragment
        "ftp://127.0.0.1:8787",                   # non-http scheme
        "127.0.0.1:8787",                         # no scheme
        "",                                        # empty
    ],
)
def test_validate_base_url_rejects_invalid(mod, bad):
    with pytest.raises(ValueError):
        mod._validate_base_url(bad)


@pytest.mark.parametrize(
    "good",
    [
        "http://127.0.0.1:8787",
        "https://example.test",
        "http://host",      # no port
        "http://host/",     # root path only
    ],
)
def test_validate_base_url_accepts_valid(mod, good):
    assert mod._validate_base_url(good) == good


def test_controller_rejects_credential_bearing_base_url(mod, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError):
        mod.ServiceControl(
            repo_root=repo,
            uid=UID,
            executor=FakeExecutor(),
            launchagents_dir=tmp_path / "LaunchAgents",
            logs_dir=tmp_path / "logs",
            base_url="http://user:secret-token@127.0.0.1:8787",
        )


def test_main_rejects_invalid_cli_base_url_without_echo(mod, monkeypatch, capsys):
    secret = "USER-PASS-SECRET-TOKEN-1234567890"
    rc = mod.main(["status", "--base-url", f"http://{secret}:x@127.0.0.1:8787"])
    out = capsys.readouterr()
    assert rc != 0
    assert secret not in out.err  # credential never echoed
    assert secret not in out.out
    assert "base URL" in out.err


def test_main_rejects_invalid_env_base_url_without_echo(mod, monkeypatch, capsys):
    secret = "ENV-SIGNED-QUERY-abcdef0123"
    monkeypatch.setenv(mod.SERVICE_URL_ENV, f"http://127.0.0.1:8787/?signature={secret}")
    rc = mod.main(["status"])
    out = capsys.readouterr()
    assert rc != 0
    assert secret not in out.err  # signed value never echoed
    assert secret not in out.out
    assert "base URL" in out.err


# =========================================================================
# amendment A8 — logs dir exists before bootstrap (install/restart)
# =========================================================================
def test_install_creates_logs_dir_before_bootstrap(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    assert not ctrl.logs_dir.exists()
    rc = ctrl.install(confirm=True)
    assert rc == 0
    # the StandardOut/ErrorPath parents must exist so launchd can write to them
    assert ctrl.logs_dir.is_dir()
    assert ctrl.stdout_log.parent == ctrl.logs_dir
    assert ctrl.stderr_log.parent == ctrl.logs_dir
    assert ["launchctl", "bootstrap", f"gui/{UID}", str(ctrl.plist_path)] in fake.calls


def test_restart_creates_logs_dir_before_bootstrap(mod, tmp_path):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    assert not ctrl.logs_dir.exists()
    rc = ctrl.restart(confirm=True)
    assert rc == 0
    assert ctrl.logs_dir.is_dir()
    assert fake.launchctl_calls("bootstrap")


# =========================================================================
# diagnostic privacy — signed query, Cookie/Set-Cookie, X-MBX-APIKEY, bearer
# =========================================================================
def test_doctor_redacts_signed_query_cookie_apikey_bearer(mod, tmp_path):
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    ctrl.stderr_log.parent.mkdir(parents=True, exist_ok=True)
    signed = "9f8e7d6c5b4a39383736353433"
    cookie_val = "supersecretcookie123"
    apikey = "vmPUzzzzapikeyvalue9876"
    bearer_val = "mF_9.B5f-4.1JqM"
    ctrl.stderr_log.write_text(
        f"GET /api?symbol=BTC&signature={signed}\n"
        f"Cookie: sessionid={cookie_val}; other=y\n"
        f"Set-Cookie: tracker=zzz; HttpOnly\n"
        f"X-MBX-APIKEY: {apikey}\n"
        f"Authorization: Bearer {bearer_val}\n"
    )
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    blob = (bundle / "stderr-tail.txt").read_text()
    # no dummy secret bytes survive in any written bundle file
    assert signed not in blob
    assert cookie_val not in blob
    assert apikey not in blob
    assert bearer_val not in blob
    # the redaction markers survive, preserving the non-secret structure
    assert "signature=[REDACTED]" in blob
    assert "Cookie: [REDACTED]" in blob
    assert "Set-Cookie: [REDACTED]" in blob
    assert "X-MBX-APIKEY: [REDACTED]" in blob
    assert "Bearer [REDACTED]" in blob


def test_doctor_summary_url_has_no_credentials_or_query(mod, tmp_path):
    # the fixed host/port summary URL must never carry credentials or a query
    fake = FakeExecutor()
    fake.on("launchctl", lambda a: _cp(a, rc=0, out="state = running\n") if a[1] == "print" else _cp(a, rc=0))
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url="http://127.0.0.1:8787")
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    summary = json.loads((bundle / "bundle.json").read_text())
    assert summary["url"] == "http://127.0.0.1:8787"
    assert "@" not in summary["url"]
    assert "?" not in summary["url"]


# =========================================================================
# amendment A4 — do NOT collapse a non-zero print into "not loaded"
# =========================================================================
@pytest.mark.parametrize(
    "err_text",
    [
        "Operation not permitted",
        "unrecognized command",
        "No such file or directory",
        "configuration file not found",
    ],
)
def test_is_not_loaded_result_false_for_tool_errors(mod, err_text):
    cp = subprocess.CompletedProcess(["launchctl", "print"], 1, "", err_text)
    assert mod.ServiceControl._is_not_loaded_result(cp) is False


@pytest.mark.parametrize("command", ["install", "start", "stop", "restart"])
def test_mutating_command_aborts_when_print_is_tool_error(mod, tmp_path, command):
    # A permission/malformed-command/tool error from launchctl print must NOT
    # be treated as "not loaded": the command stops before any launchd mutation
    # and does not write the plist (install) or reach bootstrap/bootout.
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Operation not permitted") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    # start/restart gate on the plist existing; pre-create so the print guard
    # is actually reached.
    if command in ("start", "restart"):
        ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
        ctrl.plist_path.write_text("placeholder")
    method = getattr(ctrl, command)
    rc = method(confirm=True)
    assert rc != 0
    # no launchd mutation reached
    assert fake.launchctl_calls("bootstrap") == []
    assert fake.launchctl_calls("bootout") == []
    assert fake.launchctl_calls("kickstart") == []
    if command == "install":
        assert not ctrl.plist_path.exists()
    if command == "restart":
        assert ctrl.plist_path.read_text() == "placeholder"


@pytest.mark.parametrize(
    "err_text",
    [
        "unrecognized command",
        "No such file or directory",
    ],
)
def test_uninstall_does_not_authorize_deletion_on_broad_errors(mod, tmp_path, err_text):
    # Broad "unrecognized" / unrelated "no such" errors must NOT authorize
    # plist deletion; the plist stays in place.
    fake = FakeExecutor().on(
        "launchctl",
        lambda a, e=err_text: _cp(a, rc=1, err=e) if a[1] == "bootout" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.uninstall(confirm=True)
    assert rc != 0
    assert ctrl.plist_path.exists()


# =========================================================================
# amendment A4 — service-specific not-loaded vs generic "configuration file
# not found"; "Could not find service" remains tolerated
# =========================================================================
def test_is_not_loaded_result_true_for_could_not_find_service(mod):
    cp = subprocess.CompletedProcess(["launchctl", "print"], 1, "", "Could not find service")
    assert mod.ServiceControl._is_not_loaded_result(cp) is True


def test_install_aborts_on_configuration_file_not_found(mod, tmp_path):
    # A generic "configuration file not found" must NOT authorize the
    # not-loaded path: install aborts, writes no plist, never bootstraps.
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="configuration file not found") if a[1] == "print" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    rc = ctrl.install(confirm=True)
    assert rc != 0
    assert not ctrl.plist_path.exists()
    assert fake.launchctl_calls("bootstrap") == []


def test_uninstall_keeps_plist_on_configuration_file_not_found(mod, tmp_path):
    # A generic "configuration file not found" must NOT authorize plist deletion.
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="configuration file not found") if a[1] == "bootout" else _cp(a, rc=0),
    )
    ctrl = _controller(mod, tmp_path, fake=fake)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.uninstall(confirm=True)
    assert rc != 0
    assert ctrl.plist_path.exists()


# =========================================================================
# amendment A2 — port range and host character validation (no value echo)
# =========================================================================
@pytest.mark.parametrize(
    "bad",
    [
        "http://127.0.0.1:abc",       # non-numeric port
        "http://127.0.0.1:99999",     # port out of range (too large)
        "http://127.0.0.1:0",         # port 0 (below 1)
        "http://127.0.0.1:-1",        # negative port
        "http://ho st:8787",          # whitespace in host
        "http://host\x00:8787",       # control character in host
    ],
)
def test_validate_base_url_rejects_bad_port_or_host(mod, bad):
    with pytest.raises(ValueError):
        mod._validate_base_url(bad)


def test_main_rejects_out_of_range_port_without_echo(mod, monkeypatch, capsys):
    rc = mod.main(["status", "--base-url", "http://127.0.0.1:99999"])
    out = capsys.readouterr()
    assert rc != 0
    assert "99999" not in out.err  # the rejected port value is never echoed
    assert "99999" not in out.out
    assert "base URL" in out.err


# =========================================================================
# diagnostic privacy — userinfo credentials embedded in URLs in captured logs
# =========================================================================
def test_doctor_redacts_userinfo_url_in_logs(mod, tmp_path):
    user = "loguser"
    pw = "DUMMY_SECRET"
    fake = FakeExecutor()
    fake.on(
        "launchctl",
        lambda a: _cp(a, rc=0, out=f"endpoint http://{user}:{pw}@127.0.0.1:8787/x\n") if a[1] == "print" else _cp(a, rc=0),
    )
    fake.on("git", _git_handler())
    ctrl = _controller(mod, tmp_path, fake=fake, base_url=_closed_port_url())
    ctrl.stderr_log.parent.mkdir(parents=True, exist_ok=True)
    ctrl.stderr_log.write_text(f"upstream=http://{user}:{pw}@127.0.0.1:8787/path\n")
    ctrl.doctor()
    bundle = next(ctrl.diagnostics_dir.glob("*"))
    # search EVERY written bundle file: no dummy username/password bytes survive
    for f in bundle.iterdir():
        blob = f.read_text()
        assert user not in blob, f"userinfo username survived in {f.name}"
        assert pw not in blob, f"userinfo password survived in {f.name}"
    # the non-secret URL structure (scheme/host/port/path) is preserved
    stderr_tail = (bundle / "stderr-tail.txt").read_text()
    assert "http://[REDACTED]@127.0.0.1:8787/path" in stderr_tail
    print_text = (bundle / "launchctl-print.txt").read_text()
    assert "http://[REDACTED]@127.0.0.1:8787/x" in print_text


# =========================================================================
# review-2 P2 — bounded post-bootstrap readiness polling (install/restart)
# =========================================================================
def _make_const_probe(health, ready, body=""):
    """Injectable probe returning constant (health, ready) codes; counts calls.

    Drives install/restart to the bounded attempt ceiling with zero real
    network. ``body`` lets a test prove the readiness path never leaks an
    arbitrary response body into diagnostics.
    """
    counts = {"healthz": 0, "readyz": 0}

    def probe(path, timeout=2.0):
        if path == "/healthz":
            counts["healthz"] += 1
            return (health, body)
        if path == "/readyz":
            counts["readyz"] += 1
            return (ready, body)
        return (None, "unreachable")

    probe.counts = counts
    return probe


def _make_warmup_probe(fail_health, fail_ready, warmup_rounds):
    """Probe that fails for ``warmup_rounds`` complete health+ready rounds,
    then returns (200, 200) forever — a service that warms up then goes ready.
    """
    rounds = {"done": 0}
    counts = {"healthz": 0, "readyz": 0}

    def probe(path, timeout=2.0):
        if path == "/healthz":
            counts["healthz"] += 1
            return (200, "") if rounds["done"] >= warmup_rounds else (fail_health, "")
        if path == "/readyz":
            counts["readyz"] += 1
            ready = (200, "") if rounds["done"] >= warmup_rounds else (fail_ready, "")
            if rounds["done"] < warmup_rounds:
                rounds["done"] += 1
            return ready
        return (None, "unreachable")

    probe.counts = counts
    return probe


def _make_sleeper():
    """No-op sleeper recording the requested waits (zero real waiting)."""
    sleeps = []

    def sleeper(seconds):
        sleeps.append(seconds)

    sleeper.sleeps = sleeps
    return sleeper


def _expected_attempts(mod):
    # Mirror the controller's bounded ceiling so the test tracks the frozen
    # constants rather than a hard-coded number.
    return max(1, int(mod.READY_WAIT_SECONDS // mod.READY_POLL_INTERVAL_SECONDS) + 1)


def test_install_succeeds_after_health_and_ready_become_200(mod, tmp_path, capsys):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    probe = _make_warmup_probe(fail_health=None, fail_ready=503, warmup_rounds=2)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    rc = ctrl.install(confirm=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert f"installed plist -> {ctrl.plist_path}" in out
    # Succeeded within the bounded window: fewer probe calls than the ceiling.
    assert probe.counts["healthz"] < _expected_attempts(mod)
    assert probe.counts["readyz"] < _expected_attempts(mod)


def test_restart_succeeds_after_health_and_ready_become_200(mod, tmp_path, capsys):
    def launchctl(a):
        if a[1] == "print":
            return _cp(a, rc=0, out="state = running")
        return _cp(a, rc=0)

    fake = FakeExecutor().on("launchctl", launchctl)
    probe = _make_warmup_probe(fail_health=None, fail_ready=503, warmup_rounds=1)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.restart(confirm=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "restarted" in out
    # bootout -> bootstrap ordering is preserved despite the readiness poll.
    verbs = [c[1] for c in fake.calls if c[0] == "launchctl" and c[1] != "print"]
    assert verbs == ["bootout", "bootstrap"]


def test_install_fails_at_bounded_ceiling_when_health_always_unreachable(mod, tmp_path, capsys):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    secret = "DUMMY_READINESS_BODY_SECRET"
    probe = _make_const_probe(None, None, body=secret)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    rc = ctrl.install(confirm=True)
    captured = capsys.readouterr()
    assert rc != 0
    # Bounded: probe reached exactly the attempt ceiling, never beyond it.
    assert probe.counts["healthz"] == _expected_attempts(mod)
    assert probe.counts["readyz"] == _expected_attempts(mod)
    assert len(sleeper.sleeps) == max(0, _expected_attempts(mod) - 1)
    # Zero real waiting: every injected sleep is the poll interval only.
    assert all(s == mod.READY_POLL_INTERVAL_SECONDS for s in sleeper.sleeps)
    # The plist is retained for diagnostics (no silent cleanup on failure).
    assert ctrl.plist_path.is_file()
    # Actionable, redacted stderr; no success text, body, secret or URL leak.
    err = captured.err
    assert "ready" in err
    assert "status" in err
    assert "doctor" in err
    assert "stop --confirm" in err
    assert "installed plist" not in err
    assert secret not in err
    assert "http" not in err


def test_install_fails_at_bounded_ceiling_when_health_200_but_ready_503(mod, tmp_path, capsys):
    fake = FakeExecutor().on(
        "launchctl",
        lambda a: _cp(a, rc=1, err="Could not find service") if a[1] == "print" else _cp(a, rc=0),
    )
    probe = _make_const_probe(200, 503)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    rc = ctrl.install(confirm=True)
    captured = capsys.readouterr()
    assert rc != 0
    # Health is up but readiness never reaches 200: bounded ceiling reached.
    assert probe.counts["healthz"] == _expected_attempts(mod)
    assert probe.counts["readyz"] == _expected_attempts(mod)
    assert len(sleeper.sleeps) == max(0, _expected_attempts(mod) - 1)
    err = captured.err
    assert "ready" in err
    assert "stop --confirm" in err
    assert "installed plist" not in err


def test_await_readiness_small_window_is_three_probes_two_sleeps_false(mod, tmp_path):
    # Boundary check for the final-sleep fix: deadline=2/interval=1 must do
    # exactly three probe rounds and two sleeps (no sleep after the last probe),
    # then return False. Zero real network, zero real waiting.
    fake = FakeExecutor()
    probe = _make_const_probe(None, None)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    result = ctrl._await_readiness(deadline=2, interval=1)
    assert result is False
    assert probe.counts["healthz"] == 3
    assert probe.counts["readyz"] == 3
    assert len(sleeper.sleeps) == 2
    assert all(s == 1 for s in sleeper.sleeps)


def test_restart_fails_at_bounded_ceiling_when_readiness_never_succeeds(mod, tmp_path, capsys):
    def launchctl(a):
        if a[1] == "print":
            return _cp(a, rc=0, out="state = running")
        return _cp(a, rc=0)

    fake = FakeExecutor().on("launchctl", launchctl)
    secret = "DUMMY_RESTART_BODY_SECRET"
    probe = _make_const_probe(None, None, body=secret)
    sleeper = _make_sleeper()
    ctrl = _controller(mod, tmp_path, fake=fake, probe=probe, sleeper=sleeper)
    ctrl.plist_path.parent.mkdir(parents=True, exist_ok=True)
    ctrl.plist_path.write_text("placeholder")
    rc = ctrl.restart(confirm=True)
    captured = capsys.readouterr()
    assert rc != 0
    # readiness never reached: bounded probe ceiling, one fewer sleep.
    assert probe.counts["healthz"] == _expected_attempts(mod)
    assert probe.counts["readyz"] == _expected_attempts(mod)
    assert len(sleeper.sleeps) == max(0, _expected_attempts(mod) - 1)
    # no success text on stdout
    assert "restarted" not in captured.out
    # launchctl stays strictly bootout -> bootstrap; no extra cleanup call
    verbs = [c[1] for c in fake.calls if c[0] == "launchctl" and c[1] != "print"]
    assert verbs == ["bootout", "bootstrap"]
    # plist retained for diagnostics
    assert ctrl.plist_path.is_file()
    # actionable, redacted stderr; no body/secret/URL/success leak
    err = captured.err
    assert "ready" in err
    assert "status" in err
    assert "doctor" in err
    assert "stop --confirm" in err
    assert "restarted" not in err
    assert secret not in err
    assert "http" not in err
