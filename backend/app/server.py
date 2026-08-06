"""HTTP server (stdlib http.server) bound to 127.0.0.1.

Routes:
  GET /api/public-market/snapshot        -> canonical snapshot JSON (live: pure
                                            read of the published state; 503
                                            before the first base publication
                                            or on validation failure).
  GET /api/public-market/symbol-snapshot -> one-shot selected-symbol refresh +
                                            single-row projection (v1).
  GET /api/public-market/funding-history -> legacy pure published-state history
                                            projection (compatibility).
  GET / and static assets                -> frontend/ (same-origin, no CORS).

Chosen over FastAPI/uvicorn to keep the runtime dependency surface to jsonschema
only (see 11-adr.md ADR-1).
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..borrow_tasks import BorrowError, BorrowTaskService
from ..borrow_tasks import domain as borrow_domain
from ..config import Config, DEFAULT, from_env
from ..hedge_open_tasks import HedgeError as HedgeOpenError
from ..hedge_open_tasks import HedgeOpenTaskService
from ..hedge_open_tasks import domain as hedge_open_domain
from ..ledger_flow.domain import WindowValidationError
from ..ledger_flow.scheduler import LedgerScheduler
from ..ledger_flow.service import LedgerFlowService
from ..ledger_flow.store import LedgerStore
from ..services.snapshot_service import SnapshotNotReady, SnapshotService

# Borrow-task route table (breakdown §3.1). Path templates with their allowed
# methods; matched longest-first. These routes are dispatched ONLY here and do
# not alter any GET snapshot/static behavior.
_BORROW_ROUTES = (
    (re.compile(r"^/api/borrow-tasks/(?P<task_id>[^/]+)/start$"), ("POST",), "_borrow_start"),
    (re.compile(r"^/api/borrow-tasks/(?P<task_id>[^/]+)/pause$"), ("POST",), "_borrow_pause"),
    (re.compile(r"^/api/borrow-tasks/(?P<task_id>[^/]+)/delete$"), ("POST",), "_borrow_delete"),
    (re.compile(r"^/api/borrow-tasks/(?P<task_id>[^/]+)/edit$"), ("POST",), "_borrow_edit"),
    (re.compile(r"^/api/borrow-tasks$"), ("GET", "POST"), "_borrow_tasks"),
    (re.compile(r"^/api/borrow-logs$"), ("GET",), "_borrow_logs"),
    (re.compile(r"^/api/borrow-logs/clear$"), ("POST",), "_borrow_logs_clear"),
    (re.compile(r"^/api/borrow-scheduler-settings$"), ("GET", "PUT"), "_borrow_settings"),
    # Boundary C execution control (§3.2): read-only status + idempotent global
    # Start/Stop. These never carry secrets and never accept a body field.
    (re.compile(r"^/api/borrow-execution/status$"), ("GET",), "_borrow_execution_status"),
    (re.compile(r"^/api/borrow-execution/start$"), ("POST",), "_borrow_execution_start"),
    (re.compile(r"^/api/borrow-execution/stop$"), ("POST",), "_borrow_execution_stop"),
)


def _is_borrow_path(path: str) -> bool:
    return (
        path == "/api/borrow-tasks"
        or path.startswith("/api/borrow-tasks/")
        or path == "/api/borrow-logs"
        or path.startswith("/api/borrow-logs/")
        or path == "/api/borrow-scheduler-settings"
        or path.startswith("/api/borrow-scheduler-settings/")
        or path == "/api/borrow-execution/status"
        or path == "/api/borrow-execution/start"
        or path == "/api/borrow-execution/stop"
        or path.startswith("/api/borrow-execution/")
    )


# Hedge-open route table (stage 2026-07-hedge-open-live-v1, breakdown §3.1). Path
# templates with their allowed methods; matched longest-first. These routes are
# dispatched ONLY here and do not alter any borrow or snapshot/static behavior.
_HEDGE_OPEN_ROUTES = (
    (
        re.compile(
            r"^/api/hedge-open-tasks/(?P<task_id>[^/]+)/(?P<action>pause|start|delete|fill-once|fill-all)$"
        ),
        ("POST",),
        "_hedge_open_action",
    ),
    (re.compile(r"^/api/hedge-open-tasks$"), ("GET", "POST"), "_hedge_open_tasks"),
    (re.compile(r"^/api/hedge-open-settings$"), ("GET",), "_hedge_open_settings"),
    # S3 (ADR-H2): concurrency-safe, confirmation-gated Start-gate write.
    (
        re.compile(r"^/api/hedge-open-settings/start-gate$"),
        ("POST",),
        "_hedge_open_start_gate",
    ),
    # 功能三：平仓闸门（独立于开单闸门，CAS/confirm 机制同 start-gate）。
    (
        re.compile(r"^/api/hedge-open-settings/close-gate$"),
        ("POST",),
        "_hedge_open_close_gate",
    ),
    (re.compile(r"^/api/hedge-open-logs$"), ("GET",), "_hedge_open_logs"),
    (re.compile(r"^/api/hedge-open-positions$"), ("GET",), "_hedge_open_positions"),
    # 功能三 ③a：周期结算日志（历史仓位页数据源）。
    (re.compile(r"^/api/hedge-open-close-logs$"), ("GET",), "_hedge_open_close_logs"),
)

_HEDGE_OPEN_ACTIONS = {
    "pause": "post_pause",
    "start": "post_start",
    "delete": "post_delete",
    "fill-once": "post_fill_once",
    "fill-all": "post_fill_all",
}


def _is_hedge_open_path(path: str) -> bool:
    return (
        path == "/api/hedge-open-tasks"
        or path.startswith("/api/hedge-open-tasks/")
        or path == "/api/hedge-open-settings"
        or path.startswith("/api/hedge-open-settings/")
        or path == "/api/hedge-open-logs"
        or path == "/api/hedge-open-positions"
        or path == "/api/hedge-open-close-logs"
    )


class _Handler(BaseHTTPRequestHandler):
    service = None  # injected via build_server
    borrow_service = None  # injected via build_server; None -> 503 on borrow routes
    hedge_open_service = None  # injected via build_server; None -> 503 on hedge routes
    ledger_flow_service = None  # injected in run(); None -> 503 on private-ledger routes
    frontend_dir = None
    server_version = "funding-hedging-public-market/1.0"

    def log_message(self, fmt, *args):  # silence default stderr access log
        return

    def do_GET(self):
        if self._try_hedge_open("GET"):
            return
        if self._try_borrow("GET"):
            return
        path = urlparse(self.path).path
        if path == "/healthz":
            self._handle_healthz()
            return
        if path == "/readyz":
            self._handle_readyz()
            return
        if path == "/api/public-market/snapshot":
            self._handle_snapshot()
            return
        if path == "/api/public-market/symbol-snapshot":
            self._handle_symbol_snapshot()
            return
        if path == "/api/public-market/funding-history":
            self._handle_funding_history()
            return
        if path == "/api/private-ledger/flow-log":
            self._handle_flow_log()
            return
        self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/public-market/cache-refresh":
            self._handle_cache_refresh()
            return
        if path == "/api/private-ledger/refresh":
            self._handle_flow_refresh()
            return
        if self._try_hedge_open("POST"):
            return
        if self._try_borrow("POST"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_PUT(self):
        if self._try_hedge_open("PUT"):
            return
        if self._try_borrow("PUT"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_DELETE(self):
        if self._try_hedge_open("DELETE"):
            return
        if self._try_borrow("DELETE"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_PATCH(self):
        if self._try_hedge_open("PATCH"):
            return
        if self._try_borrow("PATCH"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_HEAD(self):
        if self._try_borrow("HEAD"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_OPTIONS(self):
        if self._try_borrow("OPTIONS"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def _handle_snapshot(self):
        try:
            snapshot = self.service.get_snapshot()
        except SnapshotNotReady as exc:
            # brief cold-start window before the first base publication
            body = json.dumps(
                {"error": "snapshot_not_ready", "detail": str(exc)}
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        except Exception as exc:  # schema invalid or fetch error -> 503
            body = json.dumps(
                {"error": "snapshot_unavailable", "detail": str(exc)}
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        payload = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_symbol_snapshot(self):
        # Same-origin, one-shot selected-symbol refresh. The route path is fixed;
        # only the ``symbol`` query param is read. parse_qs drops blank values,
        # so ``?symbol=`` is treated as missing -> the service returns 400
        # invalid_symbol. 503 covers the brief pre-first-publication window.
        values = parse_qs(urlparse(self.path).query).get("symbol")
        symbol = values[0] if values else None
        status, payload = self.service.get_symbol_snapshot(symbol)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if status == 200:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_funding_history(self):
        # Same-origin, public read-only selected-symbol settled history (Task C).
        # The route path is fixed; only the ``symbol`` query param is read.
        # parse_qs drops blank values by default, so ``?symbol=`` is treated as
        # missing -> the service returns 400 invalid_symbol.
        values = parse_qs(urlparse(self.path).query).get("symbol")
        symbol = values[0] if values else None
        status, payload = self.service.get_funding_history(symbol)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if status == 200:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_cache_refresh(self):
        # POST /api/public-market/cache-refresh (design §5.1) — the first WRITE
        # route in the public-market namespace. Its only side effect is local:
        # enqueue (or reuse) one RefreshCacheCommand and bounded-wait its done
        # event. ALL Binance I/O happens inside the snapshot worker; this handler
        # performs no upstream fetch and writes no cache. The route takes no body
        # fields; any posted body is drained and ignored.
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            self._send_json(
                400,
                json.dumps(
                    {"error": "invalid_json", "detail": "invalid Content-Length"}
                ).encode("utf-8"),
            )
            return
        if length > 0:
            self.rfile.read(length)
        # No live worker -> honest failure (design §4.1: a cache command needs the
        # worker to run the cycle). Offline mode never starts the worker.
        if not self.service._worker_running():
            self._send_json(
                503,
                json.dumps(
                    {
                        "error": "cache_refresh_unavailable",
                        "detail": "snapshot worker not running",
                    }
                ).encode("utf-8"),
            )
            return
        cmd = self.service.submit_cache_refresh()
        cmd.done.wait(timeout=self.service.config.cache_refresh_timeout_seconds)
        if not cmd.done.is_set():
            # Still queued / running: 202 queued. The worker keeps refreshing in
            # the background; no auto-polling is added (design §5.1).
            self._send_json(
                202,
                json.dumps(
                    {"status": "queued", "detail": "refresh still in progress"}
                ).encode("utf-8"),
            )
            return
        result = cmd.result
        published = bool(result and result.published)
        account_panels = result.account_panels if result is not None else "not_attempted"
        self._send_json(
            200,
            json.dumps(
                {"published": published, "account_panels": account_panels}
            ).encode("utf-8"),
        )

    # ------------------------------------------------------------ private-ledger
    # Dual-ledger flow-log (design 2026-08-04-dual-ledger-flow-log §13.1–§13.4).
    # GET flow-log is a PURE read of the local ledger (zero upstream I/O); POST
    # refresh triggers one manual run. Both 200 responses carry Cache-Control:
    # no-store. The service is wired in run(); None here -> 503.

    def _handle_flow_log(self):
        if self.ledger_flow_service is None:
            self._send_ledger(
                503, {"error": "flow_log_unavailable",
                      "detail": "flow-log service not configured"})
            return
        query = parse_qs(urlparse(self.path).query)
        start = query.get("start", [None])[0]
        end = query.get("end", [None])[0]
        if start is None or end is None:
            self._send_ledger(
                400, {"error": "invalid_window",
                      "detail": "start and end query params are required"})
            return
        try:
            start_ms = int(start)
            end_ms = int(end)
        except (ValueError, TypeError):
            self._send_ledger(
                400, {"error": "invalid_window",
                      "detail": "start and end must be integer milliseconds"})
            return
        try:
            payload = self.ledger_flow_service.get_flow_log(start_ms, end_ms)
        except WindowValidationError as exc:
            self._send_ledger(400, {"error": "invalid_window", "detail": str(exc)})
            return
        self._send_ledger(200, payload)

    def _handle_flow_refresh(self):
        # No request body field is read (§13.4); any posted body is drained.
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            length = 0
        if length > 0:
            self.rfile.read(length)
        if self.ledger_flow_service is None:
            self._send_ledger(
                503, {"error": "flow_log_unavailable",
                      "detail": "flow-log service not configured"})
            return
        status, payload = self.ledger_flow_service.trigger_refresh()
        self._send_ledger(status, payload)

    def _send_ledger(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if status == 200:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_healthz(self):
        # Liveness only: the handler running proves the process is alive. Fixed
        # secret-free body; no snapshot/account data, paths, or environment.
        body = json.dumps(
            {"status": "ok", "service": "com.aoke.funding-hedging.server"}
        ).encode("utf-8")
        self._send_json(200, body)

    def _handle_readyz(self):
        # Readiness only: a pure published-state read via get_snapshot(). 503 on
        # cold start, SnapshotNotReady, or any exception. The exception object is
        # caught and discarded; its text never reaches the response. No business
        # payload, no data_time/rows, no raw exception string.
        try:
            self.service.get_snapshot()
        except Exception:
            self._send_json(503, json.dumps({"status": "not_ready"}).encode("utf-8"))
            return
        self._send_json(200, json.dumps({"status": "ready"}).encode("utf-8"))

    def _send_json(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------ borrow

    def _try_borrow(self, method: str) -> bool:
        """Dispatch borrow-task routes. Returns True if handled (incl. errors).

        A borrow-prefix path with no borrow service wired answers 503; a known
        path with a disallowed method answers 405; a borrow-prefix path that
        matches no known route answers 404. Non-borrow paths return False so
        the caller falls through to the existing handlers.
        """
        path = urlparse(self.path).path
        if not _is_borrow_path(path):
            return False
        if self.borrow_service is None:
            self._send_borrow(
                503,
                {"error": "borrow_service_unavailable", "detail": "borrow service not configured"},
            )
            return True
        for regex, allowed, handler_name in _BORROW_ROUTES:
            match = regex.match(path)
            if match is None:
                continue
            if method not in allowed:
                self._send_borrow(
                    405, {"error": "method_not_allowed", "detail": f"{method} not allowed on {path}"}
                )
                return True
            getattr(self, handler_name)(**match.groupdict())
            return True
        self._send_borrow(404, {"error": "not_found", "detail": f"unknown borrow path {path}"})
        return True

    def _send_borrow(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            # A HEAD response carries the headers but no message body (RFC 9110
            # §9.3.2); the Content-Length above advertises what a GET would send.
            self.wfile.write(body)

    def _read_json_body(self, required: bool = True):
        """Return ``(data, error)`` where error is a ``(status, payload)`` pair."""
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            return None, (400, {"error": "invalid_json", "detail": "invalid Content-Length"})
        if length > borrow_domain.BODY_MAX_BYTES:
            return None, (
                413,
                {"error": "body_too_large", "detail": f"request body exceeds {borrow_domain.BODY_MAX_BYTES} bytes"},
            )
        raw = self.rfile.read(length) if length > 0 else b""
        if required:
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("application/json"):
                return None, (400, {"error": "invalid_json", "detail": "content-type must be application/json"})
            if not raw:
                return None, (400, {"error": "invalid_json", "detail": "empty request body"})
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, (400, {"error": "invalid_json", "detail": "body is not valid UTF-8"})
        if not text.strip():
            return ({} if not required else None), (
                None if not required else (400, {"error": "invalid_json", "detail": "empty request body"})
            )
        try:
            return json.loads(text), None
        except json.JSONDecodeError:
            return None, (400, {"error": "invalid_json", "detail": "malformed JSON"})

    def _drain_body(self):
        """Enforce the body cap then read/discard an optional body.

        Returns ``(status, payload)`` for an oversized or malformed body, else
        ``None``. Body-optional mutations share the same ``BODY_MAX_BYTES`` cap
        as body-required mutations (breakdown §3.6 / §3.7).
        """
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            return (400, {"error": "invalid_json", "detail": "invalid Content-Length"})
        if length > borrow_domain.BODY_MAX_BYTES:
            return (
                413,
                {
                    "error": "body_too_large",
                    "detail": f"request body exceeds {borrow_domain.BODY_MAX_BYTES} bytes",
                },
            )
        if length > 0:
            self.rfile.read(length)
        return None

    def _safe(self, fn, *args):
        try:
            return fn(*args)
        except BorrowError as exc:
            return exc.status, exc.as_payload()

    def _borrow_tasks(self):
        if self.command == "GET":
            self._send_borrow(*self.borrow_service.list_tasks())
            return
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.create_task, data))

    def _borrow_start(self, task_id):
        error = self._drain_body()
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.post_start, task_id))

    def _borrow_pause(self, task_id):
        error = self._drain_body()
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.post_pause, task_id))

    def _borrow_delete(self, task_id):
        error = self._drain_body()
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.post_delete, task_id))

    def _borrow_edit(self, task_id):
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.post_edit, task_id, data))

    def _borrow_logs(self):
        query = parse_qs(urlparse(self.path).query)
        cursor = query.get("cursor", [None])[0]
        limit = query.get("limit", [None])[0]
        self._send_borrow(*self._safe(self.borrow_service.get_logs, cursor, limit))

    def _borrow_logs_clear(self):
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.clear_logs, data))

    def _borrow_settings(self):
        if self.command == "GET":
            self._send_borrow(*self.borrow_service.get_settings())
            return
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.put_settings, data))

    # Boundary C execution control handlers (§3.2). Status is a pure read;
    # Start/Stop accept only an (optional, empty) body — no fields are read, so
    # the toggle cannot be influenced by request content.
    def _borrow_execution_status(self):
        self._send_borrow(*self.borrow_service.get_execution_status())

    def _borrow_execution_start(self):
        error = self._drain_body()
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self.borrow_service.post_execution_start())

    def _borrow_execution_stop(self):
        error = self._drain_body()
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self.borrow_service.post_execution_stop())

    # ------------------------------------------------------------ hedge-open

    def _try_hedge_open(self, method: str) -> bool:
        """Dispatch hedge-open routes. Returns True if handled (incl. errors).

        Mirrors ``_try_borrow``: a hedge-open path with no service wired answers
        503; a known path with a disallowed method answers 405; a hedge-open path
        matching no known route answers 404. Non-hedge paths return False so the
        caller falls through to the borrow/static handlers.
        """
        path = urlparse(self.path).path
        if not _is_hedge_open_path(path):
            return False
        if self.hedge_open_service is None:
            self._send_hedge_open(
                503,
                {"error": "hedge_open_service_unavailable", "detail": "hedge-open service not configured"},
            )
            return True
        for regex, allowed, handler_name in _HEDGE_OPEN_ROUTES:
            match = regex.match(path)
            if match is None:
                continue
            if method not in allowed:
                self._send_hedge_open(
                    405, {"error": "method_not_allowed", "detail": f"{method} not allowed on {path}"}
                )
                return True
            getattr(self, handler_name)(**match.groupdict())
            return True
        self._send_hedge_open(404, {"error": "not_found", "detail": f"unknown hedge-open path {path}"})
        return True

    def _send_hedge_open(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_json(status, body)

    def _read_hedge_body(self, required: bool = True):
        """Return ``(data, error)`` for a hedge-open JSON body (own body cap)."""
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            return None, (400, {"error": "invalid_json", "detail": "invalid Content-Length"})
        if length > hedge_open_domain.BODY_MAX_BYTES:
            return None, (
                413,
                {"error": "body_too_large", "detail": f"request body exceeds {hedge_open_domain.BODY_MAX_BYTES} bytes"},
            )
        raw = self.rfile.read(length) if length > 0 else b""
        if required:
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("application/json"):
                return None, (400, {"error": "invalid_json", "detail": "content-type must be application/json"})
            if not raw:
                return None, (400, {"error": "invalid_json", "detail": "empty request body"})
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, (400, {"error": "invalid_json", "detail": "body is not valid UTF-8"})
        if not text.strip():
            return ({} if not required else None), (
                None if not required else (400, {"error": "invalid_json", "detail": "empty request body"})
            )
        try:
            return json.loads(text), None
        except json.JSONDecodeError:
            return None, (400, {"error": "invalid_json", "detail": "malformed JSON"})

    def _drain_hedge_body(self):
        """Enforce the hedge-open body cap then read/discard an optional body."""
        try:
            length = int(self.headers.get("Content-Length", "") or "0")
        except ValueError:
            return (400, {"error": "invalid_json", "detail": "invalid Content-Length"})
        if length > hedge_open_domain.BODY_MAX_BYTES:
            return (
                413,
                {"error": "body_too_large", "detail": f"request body exceeds {hedge_open_domain.BODY_MAX_BYTES} bytes"},
            )
        if length > 0:
            self.rfile.read(length)
        return None

    def _safe_hedge(self, fn, *args):
        try:
            return fn(*args)
        except HedgeOpenError as exc:
            return exc.status, exc.as_payload()

    def _hedge_open_tasks(self):
        if self.command == "GET":
            status = parse_qs(urlparse(self.path).query).get("status", [None])[0]
            self._send_hedge_open(*self._safe_hedge(self.hedge_open_service.list_tasks, status))
            return
        data, error = self._read_hedge_body(required=True)
        if error is not None:
            self._send_hedge_open(*error)
            return
        self._send_hedge_open(*self._safe_hedge(self.hedge_open_service.create_task, data))

    def _hedge_open_action(self, task_id, action):
        error = self._drain_hedge_body()
        if error is not None:
            self._send_hedge_open(*error)
            return
        method = _HEDGE_OPEN_ACTIONS[action]
        self._send_hedge_open(*self._safe_hedge(getattr(self.hedge_open_service, method), task_id))

    def _hedge_open_settings(self):
        self._send_hedge_open(*self.hedge_open_service.get_settings())

    def _hedge_open_start_gate(self):
        # S3 (ADR-H2): the body carries enabled/confirm/version; the service does
        # the CAS + same-transaction audit. Errors (400/409) flow through
        # _safe_hedge as HedgeError -> (status, payload).
        data, error = self._read_hedge_body(required=True)
        if error is not None:
            self._send_hedge_open(*error)
            return
        self._send_hedge_open(
            *self._safe_hedge(self.hedge_open_service.put_start_gate, data)
        )

    def _hedge_open_close_gate(self):
        # 功能三：平仓闸门 CAS 写（镜像 start-gate；confirm/version 机制一致）。
        data, error = self._read_hedge_body(required=True)
        if error is not None:
            self._send_hedge_open(*error)
            return
        self._send_hedge_open(
            *self._safe_hedge(self.hedge_open_service.put_close_gate, data)
        )

    def _hedge_open_close_logs(self):
        # 功能三 ③a：周期结算日志（历史仓位页数据源，按 closed_at 倒序）。
        self._send_hedge_open(
            *self._safe_hedge(self.hedge_open_service.get_close_logs)
        )

    def _hedge_open_logs(self):
        query = parse_qs(urlparse(self.path).query)
        cursor = query.get("cursor", [None])[0]
        limit = query.get("limit", [None])[0]
        # Amendment 17: the additive entries timeline paginates on its own
        # entries_limit / entries_cursor (independent of the legacy cursor/limit
        # that still drive logs/attempts/next_cursor). Both are optional and
        # opaque; parse_qs drops blank values, so ``?entries_cursor=`` is treated
        # as absent (first page), matching the legacy cursor convention.
        entries_cursor = query.get("entries_cursor", [None])[0]
        entries_limit = query.get("entries_limit", [None])[0]
        # 任务卡内嵌日志（2026-07-31-hedge-task-inline-log-v1）：可选 task_id 过滤，
        # 仅读路径——有值时 get_logs 一次返回该任务全部 attempt+leg，不分页。
        task_id = query.get("task_id", [None])[0]
        self._send_hedge_open(*self._safe_hedge(
            self.hedge_open_service.get_logs,
            cursor, limit, entries_cursor, entries_limit, task_id,
        ))

    def _hedge_open_positions(self):
        # Backend merge (Task 1 / D14, 11-adr.md ADR-001): join the task-record
        # position buckets with the snapshot's private_account. This handler is
        # the composition root that holds both services; SnapshotService is NOT
        # injected into HedgeOpenTaskService (the two stay decoupled — the merge
        # is a pure function in hedge_open_domain). N2: a cold or unverified
        # account NEVER 503s this endpoint — the local bookkeeping rows still
        # return, with account-derived fields nulled and account_meta reporting
        # the cause. get_snapshot() is a zero-upstream pure read (F-B), so this
        # adds no exchange request.
        _, body = self.hedge_open_service.get_positions()
        positions = body.get("positions", []) if isinstance(body, dict) else []
        private_account = None
        try:
            snapshot = self.service.get_snapshot()
        except SnapshotNotReady:
            snapshot = None
        if isinstance(snapshot, dict) and isinstance(snapshot.get("private_account"), dict):
            private_account = snapshot["private_account"]
        merged, account_meta = hedge_open_domain.merge_positions(positions, private_account)
        # Stage 2026-08-03-hedge-status-account-refresh-v1 (design §3.5): pass the
        # full fixed five-key source_checked_at object through the positions
        # account meta, so the open-positions panel can show the same per-source
        # success times as the snapshot. merge_positions (hedge_open domain) is
        # not modified; this is a post-merge attachment in the composition root.
        # When the snapshot/private_account is absent the fixed all-null shape is
        # still emitted so the five keys are always present.
        if isinstance(private_account, dict):
            account_meta["source_checked_at"] = private_account.get("source_checked_at")
        else:
            account_meta["source_checked_at"] = {
                "price_map": None,
                "unified_balances": None,
                "um_positions": None,
                "spot_balances": None,
                "pm_account": None,
            }
        # 持仓周期费率/利息统计（功能二，stage3 §3.2/§3.3）：纯读、现算、不写库。
        # 对每个带周期字段的 merged row 现算三列（窗口 = [cycle_opened_at,
        # cycle_closed_at 或 now]，毫秒换算在查询层）；ledger 未注入 / 无周期 /
        # 窗口起点不可解析 → 三列保持占位；coverage 不足（含窗口内 gaps）→ 三列
        # 置 None + stats_incomplete 标记，绝不把覆盖率不足的窗口当成真值；
        # 任一源不可解析 → net_pnl = None（「暂无」，绝不部分相加）。
        # base_asset 推导复用 hedge_open_domain._merge_base_asset 规则（1000x
        # 资产不自动对齐），在组合根本地推导，不改 domain.py。
        lsvc = self.ledger_flow_service
        # Human 2026-08-05：利息按币（asset）计，资金费按 USDT 计——net_pnl 必须把
        # 利息换算成 U 再相加，否则单位不一致。价格源 = 公开行情缓存 rows 的
        # opening_quotes（纯读、无请求）；键 = symbol（如 RSRUSDT），匹配
        # `{base_asset}USDT`。缺失/stale/无该 symbol → 利息 U 值 None（「暂无」），
        # net_pnl 绝不部分相加。注：private_account 不含 price_map（估值只留在
        # value_usdt 里），故不能从 private_account 取价。
        price_map = {}
        if isinstance(snapshot, dict):
            for _r in snapshot.get("rows") or []:
                _oq = _r.get("opening_quotes") or {}
                if _oq.get("status") == "fresh" and _oq.get("spot_bid_price"):
                    price_map[_r.get("symbol")] = _oq["spot_bid_price"]
        for row in merged:
            row["stats_incomplete"] = False
            cycle_id = row.get("cycle_id")
            opened_us = _iso_to_us(row.get("cycle_opened_at"))
            if not cycle_id or lsvc is None or opened_us is None:
                # 无统计：三列 None（前端「暂无」）；真零与占位在 wire 上可区分
                # （null = 未知/无统计，字符串含 "0" = 真值）。
                row["accrued_funding"] = None
                row["borrow_interest"] = None
                row["borrow_interest_usdt"] = None
                row["net_pnl"] = None
                continue
            closed_us = _iso_to_us(row.get("cycle_closed_at"))
            window_us = (opened_us, closed_us or _now_us())
            start_ms, end_ms = window_us[0] // 1000, window_us[1] // 1000
            cov = lsvc.coverage_for_window(start_ms, end_ms)
            if not cov.get("complete"):
                row["stats_incomplete"] = True
                row["accrued_funding"] = None
                row["borrow_interest"] = None
                row["borrow_interest_usdt"] = None
                row["net_pnl"] = None
                continue
            funding = lsvc.sum_funding_by_symbol(
                row.get("coin"), start_ms, end_ms,
            )
            base_asset = hedge_open_domain._merge_base_asset(row.get("coin"))
            interest = (
                lsvc.sum_interest_by_asset(base_asset, start_ms, end_ms)
                if base_asset else None
            )
            row["accrued_funding"] = funding
            row["borrow_interest"] = interest
            # 利息币值 → U 值：真零无需价格（0 × 任何 = 0）；非零缺价格 → None（无法换算）。
            interest_usdt = None
            if interest is not None:
                if Decimal(interest) == 0:
                    interest_usdt = "0"
                else:
                    price = price_map.get(f"{base_asset}USDT") if base_asset else None
                    if price is not None:
                        interest_usdt = str(Decimal(interest) * Decimal(price))
            row["borrow_interest_usdt"] = interest_usdt
            # 单位一致：net_pnl = 资金费(U) + 利息换算(U)；任一不可解析 → 「暂无」。
            if funding is not None and interest_usdt is not None:
                row["net_pnl"] = str(Decimal(funding) + Decimal(interest_usdt))
            else:
                row["net_pnl"] = None  # 任一不可解析/无价格 → 「暂无」
        self._send_hedge_open(200, {"positions": merged, "account": account_meta})

    def _serve_static(self, path: str):
        if path == "/":
            path = "/index.html"
        rel = unquote(path).lstrip("/")
        candidate = (self.frontend_dir / rel).resolve()
        try:
            candidate.relative_to(self.frontend_dir.resolve())  # block traversal
        except ValueError:
            self.send_error(403)
            return
        if not candidate.is_file():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        data = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_server(
    config: Config,
    service: SnapshotService,
    borrow_service: BorrowTaskService | None = None,
    hedge_open_service: HedgeOpenTaskService | None = None,
) -> ThreadingHTTPServer:
    _Handler.service = service
    _Handler.borrow_service = borrow_service
    _Handler.hedge_open_service = hedge_open_service
    _Handler.frontend_dir = config.frontend_dir
    return ThreadingHTTPServer((config.bind_host, config.bind_port), _Handler)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit_lifecycle(event: str, **fields) -> None:
    """Minimal UTC-timestamped lifecycle record to stderr (architect amendment A7).

    Only a fixed event name plus non-secret host/port and exception class where
    applicable. Never includes exception text, URLs, environment values,
    snapshot/account data, or HTTP bodies. Not a general logging framework.
    """
    record = {"event": event, "ts": _utc_now_iso()}
    record.update(fields)
    sys.stderr.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_us() -> int:
    return int(time.time() * 1_000_000)


def _iso_to_us(iso: str | None) -> int | None:
    """``us_to_iso`` 输出（``YYYY-MM-DDTHH:MM:SS.ffffffZ``）解析回微秒。"""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return int(dt.timestamp() * 1_000_000)


def _build_borrow_service(config: Config) -> BorrowTaskService:
    """Construct the borrow authority with the config-selected executor (§4.1).

    In ``live`` mode the exact-path PM borrow client is built from the dedicated
    credentials; empty credentials keep the process safe — the dispatch gate
    blocks and ``block_reason`` reports ``borrow_credentials_missing``. The
    sidecar execution-owner lock is acquired inside the service constructor; a
    non-owner process still serves read/mutation APIs but never dispatches.
    """
    mode = config.borrow_executor
    executor = None
    credentials_present = False
    if mode == "live":
        from ..services.live_borrow_executor import LiveBorrowExecutor
        from ..services.portfolio_margin_borrow_client import PortfolioMarginBorrowClient

        client = PortfolioMarginBorrowClient(
            api_key=config.binance_borrow_api_key,
            api_secret=config.binance_borrow_api_secret,
            user_agent=config.user_agent,
        )
        executor = LiveBorrowExecutor(client, now_ms=_now_ms)
        credentials_present = client.credentials_present
    return BorrowTaskService(
        str(config.borrow_db_path),
        executor=executor,
        mode=mode,
        credentials_present=credentials_present,
    )


def _build_hedge_service(config: Config) -> HedgeOpenTaskService:
    """Construct the hedge-open authority (stage 2026-07-hedge-open-real-api-v1).

    Executor mode comes from ``config.hedge_executor`` (validated in
    ``config.py`` from ``APP_HEDGE_EXECUTOR``; default ``disabled``). Default
    off: only the dry-run record transport is wired. In ``live`` mode the narrow
    exact-path PAPI adapter is built from the dedicated hedge credentials and
    injected (with a fresh-preflight provider) — a real POST is still gated
    downstream by the durable Start gate AND a fresh passing preflight AND the
    per-send ``_live_dispatch_capable`` check (ADR-4 / breakdown §3.7). Empty
    credentials keep the process safe: the live executor is constructed but
    refuses to POST (``credentials_present=False`` ->
    ``hedge_open_execution_blocked``). The durable SQLite store lives next to the
    borrow store under the gitignored ``data/`` dir.
    """
    mode = config.hedge_executor
    db_path = config.borrow_db_path.parent / "hedge-open-tasks.sqlite3"
    if mode != "live":
        return HedgeOpenTaskService(str(db_path), mode=mode)
    from ..services.hedge_open_live_client import HedgeOpenLiveClient
    from ..services.hedge_preflight_provider import HedgePreflightProvider
    from ..services.live_hedge_executor import LiveHedgeExecutor

    client = HedgeOpenLiveClient(
        api_key=config.binance_hedge_api_key,
        api_secret=config.binance_hedge_api_secret,
        user_agent=config.user_agent,
    )
    executor = LiveHedgeExecutor(client, now_ms=_now_ms)
    preflight_provider = HedgePreflightProvider(
        live_client=client,
        now_ms=_now_ms,
        user_agent=config.user_agent,
    )
    return HedgeOpenTaskService(
        str(db_path),
        mode=mode,
        executor=executor,
        preflight_provider=preflight_provider,
        credentials_present=client.credentials_present,
    )


def _build_restricted_asset_client(config: Config):
    """Build the read-only restricted-asset client injected into SnapshotService
    (decision §E-4 / interface §10). Uses the existing hedge API key and is
    INDEPENDENT of ``APP_HEDGE_EXECUTOR`` and the private channel: the display
    column is populated even when the hedge executor is ``disabled``. Returns
    ``None`` in offline mode or when the hedge API key is absent — either way the
    column degrades to ``unknown`` for every row (the honest state, §10).

    Constructing the client sends NO request and changes no Start gate;
    SnapshotService may call ONLY ``get_restricted_asset`` through it (the client's
    deny-by-default allowlist + hardcoded host enforce that)."""
    if config.offline or not config.binance_hedge_api_key:
        return None
    from ..services.hedge_open_live_client import HedgeOpenLiveClient

    return HedgeOpenLiveClient(
        api_key=config.binance_hedge_api_key,
        api_secret=config.binance_hedge_api_secret,
        user_agent=config.user_agent,
    )


def run(config: Config = None) -> None:
    config = config or DEFAULT
    service = SnapshotService(
        config, restricted_asset_client=_build_restricted_asset_client(config)
    )
    borrow_service = _build_borrow_service(config)
    hedge_open_service = _build_hedge_service(config)
    # Stage 2026-08-03-hedge-status-account-refresh-v1 (design §5.2): wire the
    # open-task status hook to the snapshot worker's non-waiting cache-refresh
    # submitter. A real ``running → 非 running`` task transition then enqueues
    # (or reuses) one RefreshCacheCommand so the next published snapshot reflects
    # the post-transition account state. The two services stay decoupled — only
    # this callback crosses them, and it never blocks (wait=False). ``getattr``
    # keeps ``run`` robust to a minimal SnapshotService stub that does not
    # expose the submitter (the real service always does).
    _cache_refresher = getattr(service, "submit_cache_refresh", None)
    if callable(_cache_refresher):
        hedge_open_service.configure_cache_refresh(_cache_refresher)
    # Dual-ledger flow-log (stage 2026-08-04-dual-ledger-flow-log-v1 task B):
    # reuse the snapshot's PrivateClient (same credential read + offline /
    # private_channel gates — no second key read, no new signing surface) and
    # the shared gitignored data/ dir for the ledger DB. The cadence thread
    # starts ONLY when the private channel is usable (§15.3); GET flow-log still
    # reads the local ledger otherwise (last_run reflects the last real run).
    ledger_store = LedgerStore(str(config.borrow_db_path.parent / "ledger-flow.sqlite3"))
    ledger_flow_service = LedgerFlowService(
        ledger_store, service.private_client, now_ms=_now_ms)
    ledger_scheduler = LedgerScheduler(ledger_flow_service, now_ms=_now_ms)
    if ledger_flow_service.is_usable():
        ledger_flow_service.mark_scheduler_enabled()
    # build_server keeps its original 2-arg call shape here so process-level
    # stubs of build_server keep working; the borrow authority is wired onto the
    # handler class separately (build_server defaults it to None first).
    server = build_server(config, service)
    _Handler.borrow_service = borrow_service
    _Handler.hedge_open_service = hedge_open_service
    _Handler.ledger_flow_service = ledger_flow_service
    # 功能三：close_log 费率/利息复用 ledger 汇总（duck-typed；结算失败不阻塞平仓）。
    hedge_open_service._ledger_flow_service = ledger_flow_service
    _emit_lifecycle("server_start", host=config.bind_host, port=config.bind_port)
    _emit_lifecycle(
        "hedge_open_execution_mode",
        mode=hedge_open_service.mode,
        start_gate=hedge_open_service.is_start_gate_on(),
    )
    # Distinct sanitized startup event when live mode cannot execute because the
    # dedicated hedge credentials are missing/empty (breakdown §3.7): the process
    # still starts and serves, emits the frozen blocked marker, and sends zero
    # signed hedge traffic (the live adapter refuses to POST). Credential presence
    # is a boolean here; the value is never logged.
    if config.hedge_executor == "live" and not hedge_open_service.credentials_present:
        _emit_lifecycle(
            "hedge_open_execution_blocked",
            hedge_executor="live",
            hedge_execution_blocked=hedge_open_domain.BLOCK_HEDGE_CREDENTIALS_MISSING,
        )
    # Boundary C observability (D2/D7): report sanitized mode + ownership + the
    # frozen startup recovery counts. Only non-secret integer/enum/ownership
    # facts — no credential value, response body, signed data, or env value.
    _emit_lifecycle(
        "borrow_execution_mode",
        mode=config.borrow_executor,
        execution_owner=borrow_service.is_execution_owner,
        live_authorized_task_count=borrow_service.store.count_live_authorized_tasks(),
        recovered_orphan_blocker_count=borrow_service.store.count_pending_orphan_attempts(),
    )
    # Distinct sanitized startup event when live mode cannot execute because the
    # dedicated borrow credentials are missing/empty (§3.4): the process still
    # starts and serves, emits the frozen blocked markers, and sends zero signed
    # borrow traffic. Credential presence is a boolean here; the value is never
    # logged.
    if config.borrow_executor == "live" and not borrow_service.credentials_present:
        _emit_lifecycle(
            "borrow_execution_blocked",
            borrow_executor="live",
            borrow_execution_blocked=borrow_domain.BLOCK_BORROW_CREDENTIALS_MISSING,
        )
    print(
        f"serving public-market snapshot on http://{config.bind_host}:{config.bind_port}"
        f" (offline={config.offline}, top_n={config.top_n}, ttl={config.cache_ttl_seconds}s,"
        f" private_channel_enabled={config.private_channel_enabled},"
        f" background_refresh={config.background_refresh_enabled})"
    )
    fatal = False
    try:
        # Worker startup is inside the lifecycle failure boundary: a
        # ``start_worker()`` failure is fatal and must emit ``server_fatal_error``
        # and clean up, exactly like a main-loop failure. launchd (KeepAlive=true)
        # then restarts the process.
        service.start_worker()
        borrow_service.start()
        hedge_open_service.start()
        if ledger_flow_service.is_usable():
            ledger_scheduler.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Fatal startup/main-loop exception: record the class only, clean up,
        # then exit non-zero. Exception text is never emitted.
        fatal = True
        _emit_lifecycle("server_fatal_error", exception_class=type(exc).__name__)
    finally:
        _emit_lifecycle("server_stop")
        try:
            borrow_service.stop()
        except Exception:
            # cleanup must never mask the fatal exit or raise a secondary error
            pass
        try:
            hedge_open_service.stop()
        except Exception:
            pass
        try:
            service.stop_worker()
        except Exception:
            # cleanup must never mask the fatal exit or raise a secondary error
            pass
        try:
            ledger_scheduler.stop()
        except Exception:
            pass
        try:
            ledger_store.close()
        except Exception:
            pass
        server.server_close()
    if fatal:
        raise SystemExit(1)


if __name__ == "__main__":
    run(from_env())
