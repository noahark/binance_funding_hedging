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
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..borrow_tasks import BorrowError, BorrowTaskService
from ..borrow_tasks import domain as borrow_domain
from ..config import Config, DEFAULT, from_env
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
    (re.compile(r"^/api/borrow-scheduler-settings$"), ("GET", "PUT"), "_borrow_settings"),
)


def _is_borrow_path(path: str) -> bool:
    return (
        path == "/api/borrow-tasks"
        or path.startswith("/api/borrow-tasks/")
        or path == "/api/borrow-logs"
        or path.startswith("/api/borrow-logs/")
        or path == "/api/borrow-scheduler-settings"
        or path.startswith("/api/borrow-scheduler-settings/")
    )


class _Handler(BaseHTTPRequestHandler):
    service = None  # injected via build_server
    borrow_service = None  # injected via build_server; None -> 503 on borrow routes
    frontend_dir = None
    server_version = "funding-hedging-public-market/1.0"

    def log_message(self, fmt, *args):  # silence default stderr access log
        return

    def do_GET(self):
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
        self._serve_static(path)

    def do_POST(self):
        if self._try_borrow("POST"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_PUT(self):
        if self._try_borrow("PUT"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_DELETE(self):
        if self._try_borrow("DELETE"):
            return
        self._send_borrow(404, {"error": "not_found", "detail": "unknown path"})

    def do_PATCH(self):
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

    def _borrow_settings(self):
        if self.command == "GET":
            self._send_borrow(*self.borrow_service.get_settings())
            return
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        self._send_borrow(*self._safe(self.borrow_service.put_settings, data))

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
) -> ThreadingHTTPServer:
    _Handler.service = service
    _Handler.borrow_service = borrow_service
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


def run(config: Config = None) -> None:
    config = config or DEFAULT
    service = SnapshotService(config)
    borrow_service = BorrowTaskService(str(config.borrow_db_path))
    # build_server keeps its original 2-arg call shape here so process-level
    # stubs of build_server keep working; the borrow authority is wired onto the
    # handler class separately (build_server defaults it to None first).
    server = build_server(config, service)
    _Handler.borrow_service = borrow_service
    _emit_lifecycle("server_start", host=config.bind_host, port=config.bind_port)
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
            service.stop_worker()
        except Exception:
            # cleanup must never mask the fatal exit or raise a secondary error
            pass
        server.server_close()
    if fatal:
        raise SystemExit(1)


if __name__ == "__main__":
    run(from_env())
