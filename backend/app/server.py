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
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..config import Config, DEFAULT, from_env
from ..services.snapshot_service import SnapshotNotReady, SnapshotService


class _Handler(BaseHTTPRequestHandler):
    service = None  # injected via build_server
    frontend_dir = None
    server_version = "funding-hedging-public-market/1.0"

    def log_message(self, fmt, *args):  # silence default stderr access log
        return

    def do_GET(self):
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


def build_server(config: Config, service: SnapshotService) -> ThreadingHTTPServer:
    _Handler.service = service
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
    server = build_server(config, service)
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
            service.stop_worker()
        except Exception:
            # cleanup must never mask the fatal exit or raise a secondary error
            pass
        server.server_close()
    if fatal:
        raise SystemExit(1)


if __name__ == "__main__":
    run(from_env())
