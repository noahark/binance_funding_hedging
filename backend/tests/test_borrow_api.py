"""HTTP API contract tests for the borrow-task routes (breakdown §3.1/§3.2/§3.7).

In-process ``ThreadingHTTPServer`` on an OS-assigned loopback port (no real
launchd, no network). Every 2xx body is validated against its §3.2 schema (with
cross-file ``$ref`` resolved through a ``referencing`` registry), every §3.7
error code is shown reachable and determinate, the runtime ``DisabledBorrow``
path is shown to persist one sanitized ``execution_disabled`` ledger row, and
the borrow wiring is shown not to shadow the existing snapshot/healthz routes.
"""
from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager
from pathlib import Path

import jsonschema
import pytest
import referencing

from backend.app.server import build_server, _build_borrow_service
from backend.borrow_tasks.service import BorrowTaskService
from backend.borrow_tasks.executor import DisabledBorrowExecutor
from backend.borrow_tasks import domain as D
from backend.config import Config
from backend.tests.borrow_paper_executor import (
    PaperBorrowExecutor,
    execution_disabled,
    known_rejection,
    rate_limited,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas" / "api" / "borrow-tasks"


class _StubSnapshotService:
    """Snapshot stub so build_server's ``service`` arg is satisfied with no I/O."""

    def __init__(self, snapshot=None):
        self._snapshot = snapshot if snapshot is not None else {"rows": []}

    def get_snapshot(self):
        return self._snapshot


class _Clock:
    def __init__(self, t0=0):
        self.t = t0

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


def _create(svc, asset, target=3):
    status, doc = svc.create_task(
        {"asset": asset, "amount_per_attempt": "1", "success_target": target}
    )
    assert status == 201
    return doc["id"]


# ---------------------------------------------------------------------------
# Schema validators: all five §3.2 schemas registered together so the
# task-list -> task $ref resolves without a filesystem registry.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def validators():
    registry = referencing.Registry()
    schemas = {}
    for name in (
        "task",
        "task-list",
        "log-page",
        "scheduler-settings",
        "execution-status",
        "error",
    ):
        schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
        schemas[name] = schema
        registry = registry.with_resource(
            schema["$id"], referencing.Resource.from_contents(schema)
        )
    return {
        name: jsonschema.Draft202012Validator(schema, registry=registry)
        for name, schema in schemas.items()
    }


# ---------------------------------------------------------------------------
# In-process server harness
# ---------------------------------------------------------------------------
@contextmanager
def _server(borrow_service, snapshot_service=None):
    cfg = Config(bind_port=0)
    server = build_server(
        cfg, snapshot_service or _StubSnapshotService(), borrow_service
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        if borrow_service is not None:
            borrow_service.close()


def _req(host, port, method, path, body=None, content_type=None, extra=None):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    headers = dict(extra or {})
    data = None
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers["Content-Length"] = str(len(data))
        if content_type:
            headers["Content-Type"] = content_type
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    out = resp.status, resp.getheader("Content-Type"), resp.read()
    conn.close()
    return out


def _json(payload):
    return json.loads(payload.decode("utf-8"))


def _post_json(obj):
    return json.dumps(obj), "application/json"


# ===========================================================================
# Create + list: 201, schema-valid, borrowing on creation (§3.1 / §3.3)
# ===========================================================================
def test_create_task_returns_201_schema_valid_and_borrowing(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        body, ctype = _post_json(
            {"asset": "BTC", "amount_per_attempt": "1.5", "success_target": 3}
        )
        status, ct, payload = _req(host, port, "POST", "/api/borrow-tasks", body=body, content_type=ctype)
        assert status == 201
        assert ct == "application/json; charset=utf-8"
        doc = _json(payload)
        validators["task"].validate(doc)
        assert doc["schema_version"] == D.SCHEMA_VERSION
        assert doc["asset"] == "BTC"
        assert doc["amount_per_attempt"] == "1.5"          # echoed verbatim, no float
        assert doc["status"] == "borrowing"                # created runnable (§3.1)
        assert doc["success_count"] == 0
        assert doc["unresolved_attempt_id"] is None
        assert doc["latest_result"] is None

        status, _, payload = _req(host, port, "GET", "/api/borrow-tasks")
        assert status == 200
        page = _json(payload)
        validators["task-list"].validate(page)
        assert [t["id"] for t in page["tasks"]] == [doc["id"]]


def test_decimal_amount_echoed_verbatim_no_float(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        body, ctype = _post_json(
            {"asset": "ETH", "amount_per_attempt": "0.00100000", "success_target": 1}
        )
        status, _, payload = _req(host, port, "POST", "/api/borrow-tasks", body=body, content_type=ctype)
        assert status == 201
        assert _json(payload)["amount_per_attempt"] == "0.00100000"


# ===========================================================================
# Settings: GET default + PUT fractional interval, schema-valid (§3.5)
# ===========================================================================
def test_settings_get_default_then_put_fractional(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/borrow-scheduler-settings")
        assert status == 200
        settings = _json(payload)
        validators["scheduler-settings"].validate(settings)
        assert settings["interval_seconds"] == "5"
        assert settings["interval_us"] == 5_000_000
        assert settings["round_robin_cursor"] is None
        assert settings["global_cooldown_until"] is None

        # A fractional interval at/above the frozen 2-second floor is accepted.
        body, ctype = _post_json({"interval_seconds": "2.5"})
        status, _, payload = _req(
            host, port, "PUT", "/api/borrow-scheduler-settings", body=body, content_type=ctype
        )
        assert status == 200
        updated = _json(payload)
        validators["scheduler-settings"].validate(updated)
        assert updated["interval_seconds"] == "2.5"
        assert updated["interval_us"] == 2_500_000

        # A sub-floor fractional value is rejected at the backend authority.
        body, ctype = _post_json({"interval_seconds": "0.5"})
        status, _, payload = _req(
            host, port, "PUT", "/api/borrow-scheduler-settings", body=body, content_type=ctype
        )
        assert status == 400
        assert _json(payload)["error"] == "invalid_interval"


# ===========================================================================
# Logs: newest-first cursor pagination, schema-valid, sanitized category (§3.6)
# ===========================================================================
def test_logs_pagination_cursor_boundary_and_schema(validators, tmp_path):
    clock = _Clock(0)
    # Distinct outcomes so same-failure coalesce does not collapse the page set.
    svc = BorrowTaskService(
        str(tmp_path / "bt.sqlite3"),
        executor=PaperBorrowExecutor([
            known_rejection(business_code="51061", reason="known_rejection:51061"),
            known_rejection(business_code="51006", reason="known_rejection:51006"),
            known_rejection(business_code="51014", reason="known_rejection:51014"),
            execution_disabled(),
            rate_limited(),
        ]),
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC")
    for t in (0, 2_000_000, 4_000_000):
        clock.t = t
        svc.tick()
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/borrow-logs?limit=2")
        assert status == 200
        page1 = _json(payload)
        validators["log-page"].validate(page1)
        assert len(page1["entries"]) == 2
        assert page1["next_cursor"] is not None
        # newest first
        assert page1["entries"][0]["id"] > page1["entries"][1]["id"]
        assert page1["entries"][0]["result_category"] in (
            "known_rejection", "execution_disabled", "rate_limited"
        )

        status, _, payload = _req(
            host, port, "GET", f"/api/borrow-logs?limit=2&cursor={page1['next_cursor']}"
        )
        assert status == 200
        page2 = _json(payload)
        validators["log-page"].validate(page2)
        ids1 = {e["id"] for e in page1["entries"]}
        ids2 = {e["id"] for e in page2["entries"]}
        assert ids1.isdisjoint(ids2)                       # no overlap across the boundary


# ===========================================================================
# Runtime DisabledBorrow path persists ONE sanitized execution_disabled row
# ===========================================================================
def test_runtime_disabled_executor_persists_sanitized_row(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))  # default Disabled executor
    assert isinstance(svc._executor, DisabledBorrowExecutor)
    svc.put_settings({"interval_seconds": "2"})
    _create(svc, "BTC")
    assert svc.tick() is True                              # one backend attempt
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/borrow-logs")
        assert status == 200
        page = _json(payload)
        validators["log-page"].validate(page)
        assert len(page["entries"]) == 1
        entry = page["entries"][0]
        assert entry["outcome"] == "resolved"
        assert entry["result_category"] == "execution_disabled"
        assert entry["reason"] == "executor_disabled"
        assert entry["tran_id"] is None                    # no Binance id (zero writes)


# ===========================================================================
# §3.7 error vocabulary — every code is reachable, determinate, schema-valid
# ===========================================================================
_STATIC_ERROR_CASES = [
    # (label, method, path, body, content_type, expected_status, expected_code)
    ("invalid_json_malformed", "POST", "/api/borrow-tasks", "{bad", "application/json", 400, "invalid_json"),
    ("invalid_json_missing_content_type", "POST", "/api/borrow-tasks",
     json.dumps({"asset": "BTC", "amount_per_attempt": "1", "success_target": 1}),
     None, 400, "invalid_json"),
    ("invalid_field_bad_asset", "POST", "/api/borrow-tasks",
     json.dumps({"asset": "btc", "amount_per_attempt": "1", "success_target": 1}),
     "application/json", 400, "invalid_field"),
    ("invalid_interval_zero", "PUT", "/api/borrow-scheduler-settings",
     json.dumps({"interval_seconds": "0"}), "application/json", 400, "invalid_interval"),
    ("invalid_interval_sub_floor", "PUT", "/api/borrow-scheduler-settings",
     json.dumps({"interval_seconds": "0.5"}), "application/json", 400, "invalid_interval"),
    ("invalid_cursor_garbage", "GET", "/api/borrow-logs?cursor=!!!", None, None, 400, "invalid_cursor"),
    ("invalid_limit_zero", "GET", "/api/borrow-logs?limit=0", None, None, 400, "invalid_limit"),
    ("unknown_task_pause", "POST", "/api/borrow-tasks/no-such-task/pause", None, None, 404, "unknown_task"),
    ("not_found_deep_subpath", "GET", "/api/borrow-tasks/x/y/z", None, None, 404, "not_found"),
    ("method_not_allowed_put_collection", "PUT", "/api/borrow-tasks", None, None, 405, "method_not_allowed"),
    ("method_not_allowed_delete_collection", "DELETE", "/api/borrow-tasks", None, None, 405, "method_not_allowed"),
    ("method_not_allowed_patch_logs", "PATCH", "/api/borrow-logs", None, None, 405, "method_not_allowed"),
    ("invalid_field_unknown_key_create", "POST", "/api/borrow-tasks",
     json.dumps({"asset": "BTC", "amount_per_attempt": "1", "success_target": 1, "bogus_field": 1}),
     "application/json", 400, "invalid_field"),
    ("body_too_large", "POST", "/api/borrow-tasks", "x" * 17_000, "application/json", 413, "body_too_large"),
]


@pytest.mark.parametrize(
    "label,method,path,body,content_type,expected_status,expected_code",
    _STATIC_ERROR_CASES,
    ids=[c[0] for c in _STATIC_ERROR_CASES],
)
def test_static_error_codes_reachable_and_determinate(
    validators, tmp_path, label, method, path, body, content_type, expected_status, expected_code
):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, ct, payload = _req(host, port, method, path, body=body, content_type=content_type)
        assert status == expected_status, (label, payload)
        assert ct == "application/json; charset=utf-8"
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == expected_code
        assert "detail" in err and isinstance(err["detail"], str)


def test_invalid_transition_pause_when_not_borrowing(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")
    with _server(svc) as (host, port):
        status, _, _ = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/pause")
        assert status == 200
        # already paused -> cannot pause again
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/pause")
        assert status == 409
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "invalid_transition"


def test_invalid_transition_start_when_borrowing(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")                       # borrowing
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/start")
        assert status == 409
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "invalid_transition"


def test_version_conflict_on_stale_edit(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")                       # version 1
    with _server(svc) as (host, port):
        body, ctype = _post_json({"amount_per_attempt": "2", "success_target": 3, "version": 1})
        status, _, _ = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/edit", body=body, content_type=ctype)
        assert status == 200                            # -> version 2
        # stale version 1 again -> conflict
        body, ctype = _post_json({"amount_per_attempt": "3", "success_target": 3, "version": 1})
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/edit", body=body, content_type=ctype)
        assert status == 409
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "version_conflict"


def test_edit_success_returns_updated_task(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")                       # version 1
    with _server(svc) as (host, port):
        body, ctype = _post_json({"amount_per_attempt": "2", "success_target": 5, "version": 1})
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/edit", body=body, content_type=ctype)
        assert status == 200
        doc = _json(payload)
        validators["task"].validate(doc)
        assert doc["version"] == 2
        assert doc["amount_per_attempt"] == "2"
        assert doc["success_target"] == 5


def test_borrow_routes_503_when_service_not_wired(validators):
    # build_server with borrow_service=None -> every borrow route answers 503.
    with _server(None) as (host, port):
        status, ct, payload = _req(host, port, "GET", "/api/borrow-tasks")
        assert status == 503
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "borrow_service_unavailable"


# ===========================================================================
# Regression: borrow wiring does not shadow healthz / snapshot / static routes
# ===========================================================================
def test_borrow_wiring_does_not_shadow_healthz_or_snapshot(tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    snap = _StubSnapshotService({"rows": [{"symbol": "BTCUSDT"}]})
    with _server(svc, snapshot_service=snap) as (host, port):
        status, _, payload = _req(host, port, "GET", "/healthz")
        assert status == 200
        assert _json(payload)["status"] == "ok"
        status, _, payload = _req(host, port, "GET", "/api/public-market/snapshot")
        assert status == 200
        assert "rows" in _json(payload)                 # snapshot handler still reached
        # and a borrow GET still works alongside them
        status, _, payload = _req(host, port, "GET", "/api/borrow-tasks")
        assert status == 200


def test_delete_then_delete_is_invalid_transition(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/delete")
        assert status == 200
        assert _json(payload)["status"] == "deleted"
        status, _, payload = _req(host, port, "POST", f"/api/borrow-tasks/{task_id}/delete")
        assert status == 409
        assert _json(payload)["error"] == "invalid_transition"


# ===========================================================================
# Round-1 fix coverage: unsupported methods, unknown fields, body cap (§3.1/§3.7)
# ===========================================================================
def test_unsupported_head_on_borrow_path_returns_405(tmp_path):
    # HEAD must not fall through to stdlib 501 HTML; every unsupported method on
    # a borrow path answers the frozen 405 JSON (breakdown §3.1). A HEAD reply
    # carries the headers but no message body (RFC 9110 §9.3.2).
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, ct, payload = _req(host, port, "HEAD", "/api/borrow-tasks")
        assert status == 405
        assert ct == "application/json; charset=utf-8"
        assert payload == b""                              # no body on HEAD


def test_edit_rejects_unknown_field(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")
    with _server(svc) as (host, port):
        body, ctype = _post_json(
            {"amount_per_attempt": "2", "success_target": 3, "version": 1, "bogus_field": 9}
        )
        status, _, payload = _req(
            host, port, "POST", f"/api/borrow-tasks/{task_id}/edit", body=body, content_type=ctype
        )
        assert status == 400
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "invalid_field"
        assert "bogus_field" in err["detail"]


def test_settings_rejects_unknown_field(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        body, ctype = _post_json({"interval_seconds": "5", "bogus_field": 9})
        status, _, payload = _req(
            host, port, "PUT", "/api/borrow-scheduler-settings", body=body, content_type=ctype
        )
        assert status == 400
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "invalid_field"
        assert "bogus_field" in err["detail"]


def test_pause_oversized_body_returns_413(validators, tmp_path):
    # Body-optional mutations enforce the same BODY_MAX_BYTES cap as
    # body-required mutations (breakdown §3.6 / §3.7).
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    task_id = _create(svc, "BTC")
    with _server(svc) as (host, port):
        status, ct, payload = _req(
            host, port, "POST", f"/api/borrow-tasks/{task_id}/pause", body="x" * 17_000
        )
        assert status == 413
        assert ct == "application/json; charset=utf-8"
        err = _json(payload)
        validators["error"].validate(err)
        assert err["error"] == "body_too_large"


# ===========================================================================
# Boundary C execution control routes (§3.2 / §3.3): status / start / stop
# ===========================================================================
def test_execution_status_disabled_projection_schema_valid(validators, tmp_path):
    # Default service is mode=disabled: read-only status is schema-valid and
    # reports the fail-closed projection (can_execute False, executor_disabled).
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, ct, payload = _req(host, port, "GET", "/api/borrow-execution/status")
        assert status == 200
        assert ct == "application/json; charset=utf-8"
        doc = _json(payload)
        validators["execution-status"].validate(doc)
        assert doc["schema_version"] == D.EXECUTION_SCHEMA_VERSION
        assert doc["mode"] == "disabled"
        assert doc["execution_enabled"] is False
        assert doc["can_execute"] is False
        assert doc["block_reason"] == "executor_disabled"
        assert doc["live_authorized_task_count"] == 0

        # A live-authorized task is reflected in the count even in disabled mode.
        _create(svc, "BTC")
        status, _, payload = _req(host, port, "GET", "/api/borrow-execution/status")
        assert _json(payload)["live_authorized_task_count"] == 1


def test_execution_start_then_stop_toggle_and_schema(validators, tmp_path):
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "POST", "/api/borrow-execution/start")
        assert status == 200
        started = _json(payload)
        validators["execution-status"].validate(started)
        assert started["execution_enabled"] is True

        status, _, payload = _req(host, port, "POST", "/api/borrow-execution/stop")
        assert status == 200
        stopped = _json(payload)
        validators["execution-status"].validate(stopped)
        assert stopped["execution_enabled"] is False


def test_execution_start_oversized_body_returns_413(validators, tmp_path):
    # Start/Stop drain the body under the same cap as every other mutation.
    svc = BorrowTaskService(str(tmp_path / "bt.sqlite3"))
    with _server(svc) as (host, port):
        status, ct, payload = _req(
            host, port, "POST", "/api/borrow-execution/start", body="x" * 17_000
        )
        assert status == 413
        assert ct == "application/json; charset=utf-8"
        assert _json(payload)["error"] == "body_too_large"


def test_execution_status_never_leaks_credentials(validators, tmp_path):
    # §3.3: the status projection carries mode + presence, never the secret. Build
    # the real live wiring with leak-marked dedicated credentials and assert the
    # response body contains neither (the GET never invokes the client -> no
    # network; construction stores the key/secret but does not contact Binance).
    cfg = Config(
        bind_port=0,
        borrow_executor="live",
        borrow_db_path=tmp_path / "bt.sqlite3",
        binance_borrow_api_key="LEAK-KEY-AAAA",
        binance_borrow_api_secret="LEAK-SECRET-BBBB",
    )
    svc = _build_borrow_service(cfg)
    try:
        assert svc.is_execution_owner is True
        with _server(svc) as (host, port):
            status, _, payload = _req(host, port, "GET", "/api/borrow-execution/status")
            assert status == 200
            blob = payload.decode("utf-8")
            assert "LEAK-KEY-AAAA" not in blob
            assert "LEAK-SECRET-BBBB" not in blob
            doc = _json(payload)
            validators["execution-status"].validate(doc)
            assert doc["mode"] == "live"
            # creds present + owner, but execution_enabled defaults to 0 -> stopped.
            assert doc["block_reason"] == "globally_stopped"
            assert doc["can_execute"] is False
    finally:
        svc.close()


def test_live_missing_credentials_blocks_dispatch_zero_signed_traffic(validators, tmp_path):
    # §4.2: live mode with no credentials reports borrow_credentials_missing and,
    # even after a global Start, dispatches nothing (zero signed POSTs). The HTTP
    # status path plus a forced tick together prove the dual-layer gate.
    exe = PaperBorrowExecutor([execution_disabled()] * 5)
    svc = BorrowTaskService(
        str(tmp_path / "bt.sqlite3"),
        executor=exe,
        mode="live",
        credentials_present=False,
    )
    _create(svc, "BTC")
    with _server(svc) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/borrow-execution/status")
        assert status == 200
        doc = _json(payload)
        validators["execution-status"].validate(doc)
        assert doc["block_reason"] == "borrow_credentials_missing"
        assert doc["can_execute"] is False

        # Operator Start flips execution_enabled, yet dispatch is still gated by
        # the missing-credentials layer -> no executor call, no signed POST.
        _req(host, port, "POST", "/api/borrow-execution/start")
        assert svc.tick() is False
        assert exe.calls == []
