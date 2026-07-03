"""Offline server smoke test (not auto-collected by pytest; no test_ prefix).

Starts the real stdlib http.server in a background thread and exercises the
snapshot endpoint and the static frontend host over real loopback HTTP, then
schema-validates the response.

Run explicitly:

    .venv/bin/python backend/tests/smoke_server.py

Note: the Harness sandbox blocks loopback TCP between separate processes, so
this smoke keeps the server in-process (a background thread) and connects from
the same process. Run with the sandbox network disabled (local self-connect
only; no external access).
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Allow running as `python backend/tests/smoke_server.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import jsonschema

from backend.app.server import build_server
from backend.config import Config
from backend.services.snapshot_service import SnapshotService


def main() -> int:
    cfg = Config(offline=True, bind_port=8787)
    service = SnapshotService(cfg)
    server = build_server(cfg, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(0.5)
        base = f"http://{cfg.bind_host}:{cfg.bind_port}"

        def get(path: str) -> bytes:
            return urllib.request.urlopen(base + path, timeout=3).read()

        snap = json.loads(get("/api/public-market/snapshot"))
        schema = json.loads(cfg.schema_path.read_text())
        jsonschema.validate(snap, schema)
        print("GET /api/public-market/snapshot -> HTTP 200, schema-valid")
        print(
            f"  rows={len(snap['rows'])} warnings={len(snap['warnings'])} "
            f"total_rows={snap['summary']['total_rows']}"
        )
        print(
            f"  data_time={snap['data_time']} generated_at={snap['generated_at']} "
            f"source_sample_id={snap['source_sample_id']}"
        )

        index = get("/")
        print(f"GET / -> HTTP 200, frontend index.html bytes={len(index)}")
        assert len(index) > 0, "frontend index.html empty"

        fixture = get("/fixture/public-market-snapshot.json")
        print(
            f"GET /fixture/public-market-snapshot.json -> HTTP 200, bytes={len(fixture)}"
        )

        print("SMOKE OK")
        return 0
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
