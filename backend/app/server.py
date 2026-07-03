"""HTTP server (stdlib http.server) bound to 127.0.0.1.

Routes:
  GET /api/public-market/snapshot  -> snapshot JSON; HTTP 503 on validation
                                      failure (never serves an invalid snapshot)
  GET /  and static assets         -> frontend/ (same-origin static host, no CORS)

Chosen over FastAPI/uvicorn to keep the runtime dependency surface to jsonschema
only (see 11-adr.md ADR-1).
"""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..config import Config, DEFAULT
from ..services.snapshot_service import SnapshotService


class _Handler(BaseHTTPRequestHandler):
    service = None  # injected via build_server
    frontend_dir = None
    server_version = "funding-hedging-public-market/1.0"

    def log_message(self, fmt, *args):  # silence default stderr access log
        return

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/public-market/snapshot":
            self._handle_snapshot()
            return
        self._serve_static(path)

    def _handle_snapshot(self):
        try:
            snapshot = self.service.get_snapshot()
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


def run(config: Config = None) -> None:
    config = config or DEFAULT
    service = SnapshotService(config)
    server = build_server(config, service)
    print(
        f"serving public-market snapshot on http://{config.bind_host}:{config.bind_port}"
        f" (offline={config.offline}, top_n={config.top_n}, ttl={config.cache_ttl_seconds}s)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
