#!/usr/bin/env python3
"""launchd service controller for ``com.aoke.funding-hedging.server``.

Owns LaunchAgent plist rendering and the operator subcommands
``render``/``install``/``start``/``stop``/``restart``/``status``/``doctor``/
``uninstall`` for the macOS user GUI domain (``gui/<uid>``).

Design authority (stage 2026-07-local-service-launchd-v1):
  00-task.md, 10-design.md, 11-adr.md, 12-development-breakdown.md,
  13-software-architect-amendment.md (A1-A8).

External-side-effect isolation (breakdown §3 / amendment A4):
  * The plist is built from a Python dict via ``plistlib`` (XML-safe), never by
    string interpolation, so a repository path containing spaces or XML
    metacharacters stays valid.
  * The subprocess executor and the LaunchAgents / Logs target directories are
    injectable. Tests inject a fake executor (recording argv) and point both
    directories at a temp dir, so the real ``launchctl`` binary is never spawned
    and the user's real ``~/Library/LaunchAgents`` domain is never mutated.
  * Every mutating subcommand (install/start/stop/restart/uninstall) requires an
    explicit ``--confirm`` flag; without it the command refuses before any
    subprocess call. ``render``/``status``/``doctor`` are non-mutating.
  * The controller never reads or sources ``.env`` and never places secrets in
    the plist.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import plistlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Sequence

LABEL = "com.aoke.funding-hedging.server"
SERVICE_URL_ENV = "FUNDING_HEDGING_SERVICE_URL"
DEFAULT_BASE_URL = "http://127.0.0.1:8787"
DEFAULT_LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
DEFAULT_LOGS_DIR = Path.home() / "Library" / "Logs" / "funding-hedging"
STDOUT_LOG_NAME = "server.stdout.log"
STDERR_LOG_NAME = "server.stderr.log"
DIAGNOSTICS_DIR_NAME = "diagnostics"
DIAG_TAIL_LINES = 200
# Bounded post-bootstrap readiness poll (review-2 P2): after a successful
# ``launchctl bootstrap``, install/restart wait for BOTH /healthz and /readyz
# to return HTTP 200 before claiming success. Explicit constants keep the retry
# ceiling bounded and testable (default window 60s, 1s interval).
READY_WAIT_SECONDS = 60
READY_POLL_INTERVAL_SECONDS = 1.0
LAUNCHCTL = "launchctl"
GIT = "git"

# launchctl stderr markers that mean the job is not loaded. Only these
# service-specific non-zero results may take the "not loaded" path. Generic
# text such as ``not found`` is intentionally excluded so an unrelated error
# like ``configuration file not found`` cannot authorize the not-loaded /
# uninstall path; ``unrecognized`` and unrelated ``no such`` errors are also
# excluded (amendment A4).
_NOT_LOADED_MARKERS = (
    "could not find service",
    "not loaded",
    "not bootstrapped",
)

# Secret-like patterns scrubbed from every doctor bundle field. The plist and
# launchctl print for this label never carry secrets, but log tails and captured
# text are redacted defensively before they are written to disk. Covers signed
# query values (e.g. ``?signature=<hex>``), Cookie/Set-Cookie headers,
# ``X-MBX-APIKEY`` headers, bearer tokens, and credential-like key/value data.
_SECRET_KV_RE = re.compile(
    r"(?i)(\b[A-Z0-9_]*(?:API_KEY|API_SECRET|SECRET|SIGNATURE|TOKEN|PASSWORD"
    r"|PASSPHRASE)(?:_FILE)?\b\s*[=:]\s*)\S+"
)
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")
_APIKEY_HEADER_RE = re.compile(r"(?i)(x-mbx-apikey\s*[:=]\s*)\S+")
_COOKIE_RE = re.compile(r"(?i)((?:set-)?cookie\s*[:=]\s*).+")
# Credentials embedded in a URL authority (``scheme://user:pass@host``) found in
# captured logs / launchctl text. The scheme is preserved; only the userinfo is
# replaced with a marker so the non-secret host/port/path structure survives.
_URL_USERINFO_RE = re.compile(
    r"(?i)((?:https?|ftp|wss?)://)([^/?#\s@]+(?::[^/?#\s@]*)?@)"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_stamp() -> str:
    # Filesystem-safe UTC timestamp for a diagnostics bundle directory.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _validate_base_url(value: str) -> str:
    """amendment A2: accept only a syntactically valid HTTP(S) base containing
    a host and an optional numeric port in the range 1..65535, with NO userinfo
    credentials, query, fragment, or non-root path, and no whitespace/control
    characters anywhere in the value. Returns the validated URL unchanged.
    Raises ``ValueError`` for any other shape; the error message deliberately
    omits the supplied value so a credential-bearing or signed URL is never
    echoed.
    """
    raw = value or ""
    # A valid URL never carries raw whitespace or control characters (they are
    # percent-encoded). Reject up front so a URL parser that silently strips
    # them cannot mask a malformed authority/host.
    if re.search(r"[\s\x00-\x1f\x7f]", raw):
        raise ValueError("base URL must not contain whitespace or control characters")
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        raise ValueError("base URL is not a syntactically valid URL")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("base URL must use an http or https scheme")
    if parsed.username or parsed.password:
        raise ValueError("base URL must not carry userinfo credentials")
    if not parsed.hostname:
        raise ValueError("base URL must include a host")
    if parsed.path not in ("", "/"):
        raise ValueError("base URL must not carry a non-root path")
    if parsed.query:
        raise ValueError("base URL must not carry a query string")
    if parsed.fragment:
        raise ValueError("base URL must not carry a fragment")
    # Accessing parsed.port may itself raise ValueError for a non-numeric or
    # out-of-range port (e.g. ``http://h:abc``, ``http://h:99999``); validate it
    # safely and surface a value-free message instead.
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("base URL port must be numeric and in the range 1..65535")
    if port is not None and not (1 <= port <= 65535):
        raise ValueError("base URL port must be in the range 1..65535")
    return value


def _redact(text: str) -> str:
    """Best-effort secret scrubbing for captured diagnostic text.

    Replaces credential-like key/value assignments, signed query values,
    bearer tokens, ``X-MBX-APIKEY`` headers, ``Cookie``/``Set-Cookie`` values,
    and credentials embedded in a URL authority (``scheme://user:pass@host``)
    with ``[REDACTED]``. The plist itself never contains secrets; this guards
    log tails and any incidental captured text.
    """
    redacted = text or ""
    if not redacted:
        return ""

    def _scrub(match: re.Match) -> str:
        return match.group(1) + "[REDACTED]"

    redacted = _SECRET_KV_RE.sub(_scrub, redacted)
    redacted = _BEARER_RE.sub(_scrub, redacted)
    redacted = _APIKEY_HEADER_RE.sub(_scrub, redacted)
    redacted = _COOKIE_RE.sub(_scrub, redacted)
    # URL userinfo: preserve the scheme, replace user[:pass]@ with a marker.
    redacted = _URL_USERINFO_RE.sub(
        lambda match: match.group(1) + "[REDACTED]@", redacted
    )
    return redacted


def real_executor(argv: Sequence[str]) -> subprocess.CompletedProcess:
    """Default subprocess runner: captures stdout/stderr as text, no shell."""
    return subprocess.run(list(argv), capture_output=True, text=True)


@dataclass
class ServiceControl:
    """Render the LaunchAgent and run operator subcommands.

    All mutable defaults (executor, target dirs, uid, base_url) are injectable
    so tests never touch the real LaunchAgent domain.
    """

    repo_root: Path
    uid: int = field(default_factory=os.getuid)
    executor: Callable[[Sequence[str]], subprocess.CompletedProcess] = real_executor
    launchagents_dir: Path = DEFAULT_LAUNCHAGENTS_DIR
    logs_dir: Path = DEFAULT_LOGS_DIR
    base_url: str = DEFAULT_BASE_URL
    # Readiness probe + sleeper collaborators for the post-bootstrap poll
    # (review-2 P2). Injectable so tests run with zero real network and zero
    # real waiting; defaults wire to the real HTTP probe and ``time.sleep``.
    probe: Optional[Callable] = None
    sleeper: Optional[Callable] = None

    def __post_init__(self) -> None:
        # amendment A2: validate the health base URL defensively so neither
        # ``status`` nor ``doctor`` can ever emit a credential-bearing or signed
        # URL, even when the controller is constructed directly.
        self.base_url = _validate_base_url(self.base_url)
        self.repo_root = Path(self.repo_root)
        self.launchagents_dir = Path(self.launchagents_dir)
        self.logs_dir = Path(self.logs_dir)
        self.plist_path = self.launchagents_dir / f"{LABEL}.plist"
        self.stdout_log = self.logs_dir / STDOUT_LOG_NAME
        self.stderr_log = self.logs_dir / STDERR_LOG_NAME
        self.diagnostics_dir = self.logs_dir / DIAGNOSTICS_DIR_NAME
        # Default readiness collaborators: the real HTTP probe and time.sleep.
        # Tests inject fakes so install/restart readiness waits need no network.
        self.probe = self.probe if self.probe is not None else self._probe
        self.sleeper = self.sleeper if self.sleeper is not None else time.sleep

    # ------------------------------------------------------------------
    # plist rendering (XML-safe; data-driven, no string interpolation)
    # ------------------------------------------------------------------
    def build_plist_dict(self) -> dict:
        run_server = str(self.repo_root / "scripts" / "run-server.sh")
        return {
            "Label": LABEL,
            "ProgramArguments": ["/bin/bash", run_server],
            "WorkingDirectory": str(self.repo_root),
            "RunAtLoad": True,
            "KeepAlive": True,  # amendment A1: true; intentional stop uses bootout
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "EnvironmentVariables": {
                "PYTHONUNBUFFERED": "1",
                "PYTHONFAULTHANDLER": "1",
            },
            "StandardOutPath": str(self.stdout_log),
            "StandardErrorPath": str(self.stderr_log),
        }

    def render_text(self) -> str:
        return plistlib.dumps(self.build_plist_dict(), fmt=plistlib.FMT_XML).decode(
            "utf-8"
        )

    def _write_plist(self) -> None:
        self.launchagents_dir.mkdir(parents=True, exist_ok=True)
        self.plist_path.write_text(self.render_text(), encoding="utf-8")

    def _ensure_logs_dir(self) -> None:
        # amendment A8: launchd writes StandardOutPath/StandardErrorPath only
        # when their parent exists, so the configured logs dir must exist
        # before any bootstrap. ``render``/``render_text`` stay side-effect
        # free; only mutating commands (install/restart) call this.
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # launchctl / git argv (built as pure data, separate from execution)
    # ------------------------------------------------------------------
    def _domain(self) -> str:
        return f"gui/{self.uid}"

    def _service_target(self) -> str:
        return f"gui/{self.uid}/{LABEL}"

    def _install_argv(self) -> List[str]:
        return [LAUNCHCTL, "bootstrap", self._domain(), str(self.plist_path)]

    def _start_argv(self) -> List[str]:
        return [LAUNCHCTL, "kickstart", self._service_target()]

    def _stop_argv(self) -> List[str]:
        return [LAUNCHCTL, "bootout", self._service_target()]

    def _print_argv(self) -> List[str]:
        return [LAUNCHCTL, "print", self._service_target()]

    def _git_argv(self, *args: str) -> List[str]:
        return [GIT, "-C", str(self.repo_root), *args]

    # ------------------------------------------------------------------
    # subprocess collaborators
    # ------------------------------------------------------------------
    def _run(self, argv: Sequence[str]) -> subprocess.CompletedProcess:
        return self.executor(list(argv))

    def _probe_load(self) -> tuple[str, subprocess.CompletedProcess]:
        # Classify ``launchctl print`` into three outcomes:
        #   "loaded"     -> rc 0; the job is bootstrapped.
        #   "not_loaded" -> a documented specific not-found/not-loaded result.
        #   "error"      -> permission, malformed-command, or other tool error.
        # Mutating commands must STOP on "error" before any launchd mutation;
        # only "not_loaded" may pass a guard that expects an unloaded job.
        cp = self._run(self._print_argv())
        if cp.returncode == 0:
            return "loaded", cp
        if self._is_not_loaded_result(cp):
            return "not_loaded", cp
        return "error", cp

    @staticmethod
    def _is_not_loaded_result(cp: subprocess.CompletedProcess) -> bool:
        if cp.returncode == 0:
            return False
        text = f"{cp.stderr or ''}\n{cp.stdout or ''}".lower()
        return any(marker in text for marker in _NOT_LOADED_MARKERS)

    def _parse_pid(self, print_text: str) -> str:
        match = re.search(r"(?im)^\s*pid\s*=\s*(\d+)\s*$", print_text or "")
        return match.group(1) if match else "n/a"

    @staticmethod
    def _parse_running(print_text: str) -> str:
        match = re.search(r"(?im)^\s*(?:state|run\s*state)\s*=\s*(\S+)", print_text or "")
        if match:
            return match.group(1)
        return "unknown"

    def _git_commit(self) -> str:
        cp = self._run(self._git_argv("rev-parse", "--short", "HEAD"))
        if cp.returncode != 0:
            return "n/a"
        return (cp.stdout or "").strip() or "n/a"

    def _git_dirty(self) -> str:
        cp = self._run(self._git_argv("status", "--porcelain"))
        if cp.returncode != 0:
            return "unknown"
        return "dirty" if (cp.stdout or "").strip() else "clean"

    # ------------------------------------------------------------------
    # HTTP health probes
    # ------------------------------------------------------------------
    def _probe(self, path: str, timeout: float = 2.0) -> tuple[Optional[int], str]:
        url = self.base_url.rstrip("/") + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status, (resp.read().decode("utf-8", "replace") or "")
        except urllib.error.HTTPError as exc:
            # A response was received (e.g. 503 not_ready): reachable, non-200.
            return exc.code, ""
        except Exception:
            return None, "unreachable"

    def _await_readiness(
        self,
        *,
        deadline: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> bool:
        """Bounded post-bootstrap readiness poll (review-2 P2).

        Returns True only when BOTH /healthz and /readyz return HTTP 200 within
        the deadline; 503, connection failure, or any other non-200 result keeps
        waiting until the bounded attempt ceiling is reached. The probe and
        sleeper are the injectable ``self.probe`` / ``self.sleeper`` so tests run
        with zero real network and zero real waiting. The loop is never
        unbounded: attempts are capped by ``READY_WAIT_SECONDS`` /
        ``READY_POLL_INTERVAL_SECONDS``.
        """
        deadline = READY_WAIT_SECONDS if deadline is None else deadline
        interval = READY_POLL_INTERVAL_SECONDS if interval is None else interval
        max_attempts = max(1, int(deadline // interval) + 1)
        for attempt in range(max_attempts):
            health_code, _ = self.probe("/healthz")
            ready_code, _ = self.probe("/readyz")
            if health_code == 200 and ready_code == 200:
                return True
            # Do not sleep after the final allowed probe: the deadline is the
            # last probe time, not one interval beyond it (default 61 probes,
            # 60 sleeps; deadline=2/interval=1 -> 3 probes, 2 sleeps).
            if attempt + 1 < max_attempts:
                self.sleeper(interval)
        return False

    # ------------------------------------------------------------------
    # subcommands (each returns a process exit code)
    # ------------------------------------------------------------------
    def render(self) -> int:
        # Non-mutating: stdout only, no LaunchAgents write, no launchctl.
        sys.stdout.write(self.render_text())
        return 0

    def install(self, *, confirm: bool) -> int:
        if not confirm:
            return self._refuse("install")
        state, print_cp = self._probe_load()
        if state == "error":
            sys.stderr.write(
                "install: launchctl print error before mutation; aborting"
                f" (rc={print_cp.returncode}).\n"
            )
            return 2
        if state == "loaded":
            sys.stderr.write(
                "install: job already loaded; use 'restart --confirm' instead.\n"
            )
            return 2
        self._write_plist()
        self._ensure_logs_dir()
        cp = self._run(self._install_argv())
        if cp.returncode != 0:
            sys.stderr.write(
                f"install: launchctl bootstrap failed (rc={cp.returncode}): "
                f"{_redact(cp.stderr or cp.stdout or '').strip()}\n"
            )
            return cp.returncode or 1
        # Bounded post-bootstrap readiness check (review-2 P2): bootstrap
        # accepting the job is not the same as the service actually listening.
        # Failures here retain the plist/logs for diagnostics and return nonzero.
        if not self._await_readiness():
            sys.stderr.write(
                "install: service did not become ready within the readiness"
                " window; the plist and logs were retained. Run 'status' or"
                " 'doctor' for diagnostics, and 'stop --confirm' to unload the"
                " job.\n"
            )
            return 1
        sys.stdout.write(f"installed plist -> {self.plist_path}\n")
        return 0

    def start(self, *, confirm: bool) -> int:
        if not confirm:
            return self._refuse("start")
        if not self.plist_path.exists():
            sys.stderr.write("start: plist not installed; run 'install --confirm'.\n")
            return 2
        state, print_cp = self._probe_load()
        if state == "error":
            sys.stderr.write(
                "start: launchctl print error before mutation; aborting"
                f" (rc={print_cp.returncode}).\n"
            )
            return 2
        if state != "loaded":
            sys.stderr.write("start: job not loaded; run 'install --confirm'.\n")
            return 2
        cp = self._run(self._start_argv())
        if cp.returncode != 0:
            sys.stderr.write(
                f"start: launchctl kickstart failed (rc={cp.returncode}): "
                f"{_redact(cp.stderr or cp.stdout or '').strip()}\n"
            )
            return cp.returncode or 1
        sys.stdout.write("started\n")
        return 0

    def stop(self, *, confirm: bool) -> int:
        if not confirm:
            return self._refuse("stop")
        state, print_cp = self._probe_load()
        if state == "error":
            sys.stderr.write(
                "stop: launchctl print error before mutation; aborting"
                f" (rc={print_cp.returncode}).\n"
            )
            return 2
        if state != "loaded":
            sys.stderr.write("stop: job not loaded; nothing to stop.\n")
            return 2
        cp = self._run(self._stop_argv())
        if cp.returncode != 0:
            sys.stderr.write(
                f"stop: launchctl bootout failed (rc={cp.returncode}): "
                f"{_redact(cp.stderr or cp.stdout or '').strip()}\n"
            )
            return cp.returncode or 1
        sys.stdout.write("stopped\n")
        return 0

    def restart(self, *, confirm: bool) -> int:
        if not confirm:
            return self._refuse("restart")
        if not self.plist_path.exists():
            sys.stderr.write(
                "restart: plist not installed; run 'install --confirm'.\n"
            )
            return 2
        state, print_cp = self._probe_load()
        if state == "error":
            sys.stderr.write(
                "restart: launchctl print error before mutation; aborting"
                f" (rc={print_cp.returncode}).\n"
            )
            return 2
        if state != "loaded":
            sys.stderr.write(
                "restart: job not loaded; run 'install --confirm'.\n"
            )
            return 2
        # Re-render the plist so bootstrap re-reads the current content, then
        # bootout + bootstrap. Any failed step fails the whole command.
        self._write_plist()
        self._ensure_logs_dir()
        cp_out = self._run(self._stop_argv())
        if cp_out.returncode != 0:
            sys.stderr.write(
                f"restart: bootout failed (rc={cp_out.returncode}): "
                f"{_redact(cp_out.stderr or cp_out.stdout or '').strip()}\n"
            )
            return cp_out.returncode or 1
        cp_in = self._run(self._install_argv())
        if cp_in.returncode != 0:
            sys.stderr.write(
                f"restart: bootstrap failed (rc={cp_in.returncode}): "
                f"{_redact(cp_in.stderr or cp_in.stdout or '').strip()}\n"
            )
            return cp_in.returncode or 1
        # Bounded post-bootstrap readiness check (review-2 P2): bootstrap
        # accepting the job is not the same as the service actually listening.
        # Failures here retain the plist/logs for diagnostics and return nonzero.
        if not self._await_readiness():
            sys.stderr.write(
                "restart: service did not become ready within the readiness"
                " window; the plist and logs were retained. Run 'status' or"
                " 'doctor' for diagnostics, and 'stop --confirm' to unload the"
                " job.\n"
            )
            return 1
        sys.stdout.write("restarted\n")
        return 0

    def uninstall(self, *, confirm: bool) -> int:
        if not confirm:
            return self._refuse("uninstall")
        cp = self._run(self._stop_argv())
        if cp.returncode != 0 and not self._is_not_loaded_result(cp):
            sys.stderr.write(
                f"uninstall: launchctl bootout failed (rc={cp.returncode}): "
                f"{_redact(cp.stderr or cp.stdout or '').strip()}\n"
            )
            return cp.returncode or 1
        # Unlink ONLY the known generated plist. Logs are never deleted.
        try:
            self.plist_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            sys.stderr.write(f"uninstall: failed to remove plist: {exc}\n")
            return 1
        sys.stdout.write(f"uninstalled plist ({self.plist_path}); logs retained\n")
        return 0

    def status(self) -> int:
        # Read-only. Preserves every field even when unavailable; reports
        # 'unreachable'/'error'/'not-loaded' rather than a traceback. Exit 0
        # only when loaded AND both health and readiness succeed.
        state, print_cp = self._probe_load()
        is_loaded = state == "loaded"
        print_text = print_cp.stdout or "" if is_loaded else ""
        pid = self._parse_pid(print_text) if is_loaded else "n/a"
        run_state = self._parse_running(print_text) if is_loaded else (
            "error" if state == "error" else "not-loaded"
        )
        health_code, _ = self._probe("/healthz")
        ready_code, _ = self._probe("/readyz")
        commit = self._git_commit()
        dirty = self._git_dirty()
        health_str = "200" if health_code == 200 else (
            str(health_code) if health_code is not None else "unreachable"
        )
        ready_str = "200" if ready_code == 200 else (
            str(ready_code) if ready_code is not None else "unreachable"
        )
        lines = [
            f"label: {LABEL}",
            f"loaded: {is_loaded}",
            f"running: {run_state}",
            f"pid: {pid}",
            f"url: {self.base_url}",
            f"health (/healthz): {health_str}",
            f"readiness (/readyz): {ready_str}",
            f"commit: {commit}",
            f"dirty: {dirty}",
            f"stdout_log: {self.stdout_log}",
            f"stderr_log: {self.stderr_log}",
        ]
        sys.stdout.write("\n".join(lines) + "\n")
        ok = is_loaded and health_code == 200 and ready_code == 200
        return 0 if ok else 1

    def doctor(self) -> int:
        # Read-only except a bounded bundle write beneath the configured logs
        # diagnostics directory (no LaunchAgent mutation, so no --confirm). Exit
        # 0 when the bundle was captured even if the service is down; non-zero
        # only on bundle-write or redaction failure.
        state, print_cp = self._probe_load()
        is_loaded = state == "loaded"
        print_text = print_cp.stdout or "" if is_loaded else (print_cp.stderr or "")
        pid = self._parse_pid(print_text) if is_loaded else "n/a"
        run_state = self._parse_running(print_text) if is_loaded else (
            "error" if state == "error" else "not-loaded"
        )
        health_code, _ = self._probe("/healthz")
        ready_code, _ = self._probe("/readyz")
        commit = self._git_commit()
        dirty = self._git_dirty()
        stdout_tail = _redact(self._tail(self.stdout_log))
        stderr_tail = _redact(self._tail(self.stderr_log))
        print_redacted = _redact(print_text)
        stamp = _utc_now_stamp()
        bundle_dir = self.diagnostics_dir / stamp
        summary = {
            "captured_at": _utc_now_iso(),
            "label": LABEL,
            "domain": self._domain(),
            "loaded": is_loaded,
            "running": run_state,
            "pid": pid,
            "url": self.base_url,
            "health": health_code,
            "readiness": ready_code,
            "commit": commit,
            "dirty": dirty,
            "launchctl_print_rc": print_cp.returncode,
            "stdout_log": str(self.stdout_log),
            "stderr_log": str(self.stderr_log),
            "tail_lines": DIAG_TAIL_LINES,
        }
        try:
            bundle_dir.mkdir(parents=True, exist_ok=True)
            (bundle_dir / "bundle.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (bundle_dir / "launchctl-print.txt").write_text(
                print_redacted, encoding="utf-8"
            )
            (bundle_dir / "stdout-tail.txt").write_text(stdout_tail, encoding="utf-8")
            (bundle_dir / "stderr-tail.txt").write_text(stderr_tail, encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"doctor: failed to write bundle: {exc}\n")
            return 1
        sys.stdout.write(
            f"doctor: bundle written -> {bundle_dir} (loaded={is_loaded},"
            f" health={health_code}, readiness={ready_code})\n"
        )
        return 0

    @staticmethod
    def _tail(path: Path, n: int = DIAG_TAIL_LINES) -> str:
        # Streaming bounded read: keep only the most recent n lines via a deque
        # so an unbounded log never fills memory. UTF-8 replacement behavior is
        # preserved.
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                window = collections.deque(fh, maxlen=n)
        except FileNotFoundError:
            return ""
        except OSError:
            return ""
        return "".join(window)

    @staticmethod
    def _refuse(command: str) -> int:
        sys.stderr.write(
            f"{command}: mutating command; retry with --confirm to proceed.\n"
        )
        return 2


# =========================================================================
# CLI
# =========================================================================
def _default_repo_root() -> Path:
    # scripts/service-control.py -> repo root is two parents up.
    return Path(__file__).resolve().parents[1]


def _resolve_base_url(cli_value: Optional[str]) -> str:
    # amendment A2: CLI flag > FUNDING_HEDGING_SERVICE_URL > local default.
    # Never reads .env.
    if cli_value:
        return cli_value
    env_value = os.environ.get(SERVICE_URL_ENV)
    if env_value:
        return env_value
    return DEFAULT_BASE_URL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="service-control.py",
        description="launchd controller for com.aoke.funding-hedging.server",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("render", help="print the rendered plist to stdout (no mutation)")

    for name, help_text in (
        ("install", "render + bootstrap the LaunchAgent"),
        ("start", "kickstart an installed service"),
        ("stop", "bootout a loaded service (keeps logs)"),
        ("restart", "bootout then bootstrap (re-reads the plist)"),
        ("uninstall", "bootout (tolerate not-loaded) and remove only the plist"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "--confirm",
            action="store_true",
            help="required gate for this mutating command",
        )

    p_status = sub.add_parser("status", help="read-only launchctl + HTTP + git summary")
    p_status.add_argument("--base-url", default=None)

    p_doctor = sub.add_parser(
        "doctor", help="write a bounded, secret-safe diagnostic bundle"
    )
    p_doctor.add_argument("--base-url", default=None)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    base_url = _resolve_base_url(getattr(args, "base_url", None))
    try:
        # amendment A2: validate before construction so an invalid base URL
        # (userinfo, query, fragment, non-root path, non-http scheme) exits
        # non-zero WITHOUT echoing the supplied value.
        base_url = _validate_base_url(base_url)
    except ValueError as exc:
        sys.stderr.write(f"service-control: rejected base URL: {exc}\n")
        return 2
    controller = ServiceControl(
        repo_root=_default_repo_root(),
        base_url=base_url,
    )
    command = args.command
    if command == "render":
        return controller.render()
    if command == "install":
        return controller.install(confirm=args.confirm)
    if command == "start":
        return controller.start(confirm=args.confirm)
    if command == "stop":
        return controller.stop(confirm=args.confirm)
    if command == "restart":
        return controller.restart(confirm=args.confirm)
    if command == "uninstall":
        return controller.uninstall(confirm=args.confirm)
    if command == "status":
        return controller.status()
    if command == "doctor":
        return controller.doctor()
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
