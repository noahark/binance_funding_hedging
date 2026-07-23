"""HTTP API contract tests for the hedge-open routes (12-breakdown §3 / ADR-5).

In-process ``ThreadingHTTPServer`` on an OS-assigned loopback port (no real
launchd, no network, no real Binance POST). Proves the frozen §3 contract over
the wire: endpoint existence + status codes, the exact task/settings/error
field names (explicit key-set assertions, which pin the contract as strictly as
a JSON schema with ``additionalProperties: false``), the determinate error codes
(``invalid_field`` / ``insufficient_state`` / ``unknown_task`` / ``invalid_json``
/ ``body_too_large`` / ``method_not_allowed``), the soft-delete semantics, the
durable-gate posture (the default executor is the dry-run record transport, so
a real POST is never reachable), 405 on a disallowed method, and that hedge-open
wiring neither requires the borrow wiring nor shadows ``/healthz``.
"""
from __future__ import annotations

import http.client
import json
import threading
import urllib.request
from contextlib import contextmanager

import pytest

from backend.app.server import build_server
from backend.config import Config
from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.executor import OutcomeSpec, RecordTransportExecutor
from backend.hedge_open_tasks.service import HedgeOpenTaskService

# The exact frozen field sets the §3 contract pins. Asserting the full key set
# (no more, no less) rejects any drift in the wire shape.
_TASK_KEYS = {
    "id", "coin", "direction", "mode", "single_amount", "target_n",
    "success_count", "fail_count", "status", "q_common", "position_side_mode",
    "leg_exposure", "created_at", "updated_at",
}
_SETTINGS_KEYS = {"executor_mode", "start_gate", "interval_seconds"}
_ERROR_KEYS = {"error", "detail"}
_POSITION_KEYS = {
    "coin", "direction", "position_qty", "spot_avg", "perp_avg",
    "open_basis_rate", "price_pnl", "accrued_funding", "borrow_interest",
    "net_pnl",
}


class _StubSnapshotService:
    """Snapshot stub so build_server's ``service`` arg is satisfied with no I/O."""

    def get_snapshot(self):
        return {"rows": []}


class _Clock:
    def __init__(self, t0=0):
        self.t = t0

    def mono_us(self):
        return self.t

    def wall_us(self):
        return self.t


def _svc(tmp_path, *, executor=None, mode="disabled", clock=None):
    return HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"),
        executor=executor,
        mode=mode,
        mono_us=clock.mono_us if clock else None,
        wall_us=clock.wall_us if clock else None,
    )


@contextmanager
def _server(hedge_service):
    """A hedge-open server with NO borrow wiring (borrow_service=None) to prove
    hedge-open stands on its own and does not shadow existing routes."""
    cfg = Config(bind_port=0)
    server = build_server(cfg, _StubSnapshotService(), None, hedge_service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        if hedge_service is not None:
            hedge_service.close()


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


def _create_body(direction=D.DIR_FORWARD, single_amount="0.5", target_n=3):
    return {
        "coin": "BTCUSDT", "direction": direction, "mode": "immediate",
        "single_amount": single_amount, "target_n": target_n,
    }


def _post_create(host, port, body=None):
    """POST the create body; return the full ``(status, content_type, payload)``."""
    body, ctype = _post_json(body or _create_body())
    return _req(host, port, "POST", "/api/hedge-open-tasks", body=body, content_type=ctype)


def _create_task(host, port, body=None):
    """POST a valid create body and return the parsed task doc (201 expected)."""
    _, _, payload = _post_create(host, port, body)
    return _json(payload)


# ===========================================================================
# Create + list: 201, exact field set, dry-run default (§3.1 / §3.3)
# ===========================================================================
def test_create_returns_201_exact_task_field_set_dry_run(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, ct, payload = _post_create(host, port)
        assert status == 201
        assert ct == "application/json; charset=utf-8"
        doc = _json(payload)
        assert set(doc.keys()) == _TASK_KEYS          # frozen field set, no drift
        assert doc["coin"] == "BTCUSDT"
        assert doc["direction"] == "forward"
        assert doc["mode"] == "immediate"
        assert doc["status"] == "running"             # created runnable
        assert doc["success_count"] == 0
        assert doc["fail_count"] == 0
        # No preflight provider wired -> dry-run: q_common / position_side_mode
        # are unresolved; leg_exposure is clean on a fresh task.
        assert doc["q_common"] is None
        assert doc["position_side_mode"] is None
        assert doc["leg_exposure"] is None


def test_list_returns_200_task_list_shape(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        created = _create_task(host, port)
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks")
        assert status == 200
        page = _json(payload)
        assert set(page.keys()) == {"tasks"}
        assert [t["id"] for t in page["tasks"]] == [created["id"]]
        assert set(page["tasks"][0].keys()) == _TASK_KEYS


def test_decimal_single_amount_echoed_verbatim_no_float(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        body, ctype = _post_json(
            {"coin": "ETHUSDT", "direction": "reverse", "mode": "immediate",
             "single_amount": "0.00100000", "target_n": 1}
        )
        status, _, payload = _req(
            host, port, "POST", "/api/hedge-open-tasks", body=body, content_type=ctype
        )
        assert status == 201
        assert _json(payload)["single_amount"] == "0.00100000"


# ===========================================================================
# Settings: GET default shape, read-only this round (§3.5 / §9)
# ===========================================================================
def test_settings_default_shape(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-settings")
        assert status == 200
        settings = _json(payload)
        assert set(settings.keys()) == _SETTINGS_KEYS
        assert settings["executor_mode"] == "disabled"
        assert settings["start_gate"] is False
        assert settings["interval_seconds"] == 1


def test_settings_reports_live_mode_when_configured(tmp_path):
    with _server(_svc(tmp_path, mode="live")) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-settings")
        assert status == 200
        assert _json(payload)["executor_mode"] == "live"


# ===========================================================================
# Determinate error codes (§3.7): invalid_field / invalid_json / unknown_task
# ===========================================================================
def test_unknown_body_key_is_invalid_field(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _post_create(host, port, {**_create_body(), "noise": 1})
        assert status == 400
        doc = _json(payload)
        assert set(doc.keys()) == _ERROR_KEYS
        assert doc["error"] == "invalid_field"


def test_bad_direction_is_invalid_field(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _post_create(
            host, port, {"coin": "BTCUSDT", "direction": "up", "mode": "immediate",
                         "single_amount": "0.5", "target_n": 1}
        )
        assert status == 400
        assert _json(payload)["error"] == "invalid_field"


def test_smooth_mode_rejected_as_invalid_field(tmp_path):
    # Frozen §3.1 freezes mode=immediate this round; ``smooth`` is a reserved
    # vocabulary word for a later round and must be rejected at create (400
    # invalid_field) so the immediate engine never dispatches a smooth-labeled
    # task — never silently accepted with a 201.
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _post_create(
            host, port, {"coin": "BTCUSDT", "direction": "forward", "mode": "smooth",
                         "single_amount": "0.5", "target_n": 1}
        )
        assert status == 400
        doc = _json(payload)
        assert set(doc.keys()) == _ERROR_KEYS
        assert doc["error"] == "invalid_field"


def test_malformed_json_is_invalid_json(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _req(
            host, port, "POST", "/api/hedge-open-tasks",
            body="{not json", content_type="application/json",
        )
        assert status == 400
        assert _json(payload)["error"] == "invalid_json"


def test_oversized_body_is_body_too_large(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        blob = '{"coin": "BTCUSDT", ' + ('"x": "0",' * (D.BODY_MAX_BYTES + 10)) + '"y": 1}'
        status, _, payload = _req(
            host, port, "POST", "/api/hedge-open-tasks",
            body=blob, content_type="application/json",
        )
        assert status == 413
        assert _json(payload)["error"] == "body_too_large"


def test_action_on_unknown_task_is_unknown_task(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _req(
            host, port, "POST", "/api/hedge-open-tasks/nope/fill-once"
        )
        assert status == 404
        doc = _json(payload)
        assert set(doc.keys()) == _ERROR_KEYS
        assert doc["error"] == "unknown_task"


# ===========================================================================
# Task lifecycle + invalid_state (§3.4)
# ===========================================================================
def test_fill_once_advances_then_done_is_invalid_state(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        tid = _create_task(host, port, _create_body(target_n=1))["id"]
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 200
        doc = _json(payload)
        assert doc["success_count"] == 1
        assert doc["status"] == "done"
        # a further fill on a done task -> invalid_state (409).
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 409
        assert _json(payload)["error"] == "invalid_state"


def test_injected_single_leg_exposure_blocks_further_fill(tmp_path):
    # The record-transport executor is injectable: seed a single-leg fill so the
    # exposure drill is reachable end-to-end over HTTP. Frozen §3.2 requires the
    # Task response's leg_exposure to be {leg,qty,price,ts}; spot-only fill ->
    # leg="spot" with the spot leg's actual qty/price (dry-run placeholder price).
    exe = RecordTransportExecutor([OutcomeSpec.spot_only_filled()])
    with _server(_svc(tmp_path, executor=exe)) as (host, port):
        tid = _create_task(host, port)["id"]
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 200
        doc = _json(payload)
        assert doc["status"] == "exposure_alert"
        assert set(doc["leg_exposure"].keys()) == {"leg", "qty", "price", "ts"}
        assert doc["leg_exposure"]["leg"] == "spot"
        assert doc["leg_exposure"]["qty"] == "0.5"
        assert doc["leg_exposure"]["price"] == "1"  # dry-run placeholder, no preflight
        # a further fill while exposed -> invalid_state.
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 409
        assert _json(payload)["error"] == "invalid_state"


def test_injected_perp_only_exposure_http_shape(tmp_path):
    # §3.2 HTTP regression for the other single-leg direction: perp-only fill ->
    # leg="perp" with the perp leg's actual qty/price, not the failed spot leg.
    exe = RecordTransportExecutor([OutcomeSpec.perp_only_filled()])
    with _server(_svc(tmp_path, executor=exe)) as (host, port):
        tid = _create_task(host, port)["id"]
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 200
        doc = _json(payload)
        assert doc["status"] == "exposure_alert"
        assert set(doc["leg_exposure"].keys()) == {"leg", "qty", "price", "ts"}
        assert doc["leg_exposure"]["leg"] == "perp"
        assert doc["leg_exposure"]["qty"] == "0.5"
        assert doc["leg_exposure"]["price"] == "1"  # dry-run placeholder, no preflight
        # a further fill while exposed -> invalid_state.
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-once")
        assert status == 409
        assert _json(payload)["error"] == "invalid_state"


# ===========================================================================
# Soft-delete semantics (§3: deleted excluded from default list)
# ===========================================================================
def test_soft_delete_excludes_from_default_list(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        a = _create_task(host, port)["id"]
        b = _create_task(host, port)["id"]
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{a}/delete")
        assert status == 200
        assert _json(payload)["status"] == "deleted"
        # default list excludes deleted.
        _, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks")
        assert [t["id"] for t in _json(payload)["tasks"]] == [b]
        # status=deleted filter surfaces it.
        _, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks?status=deleted")
        assert [t["id"] for t in _json(payload)["tasks"]] == [a]
        # deleting again -> invalid_state.
        status, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{a}/delete")
        assert status == 409
        assert _json(payload)["error"] == "invalid_state"


def test_status_all_includes_deleted_default_excludes(tmp_path):
    # Frozen §3.1: ``status=all`` is the one list view that surfaces soft-deleted
    # tasks (the default view excludes them, ``status=deleted`` surfaces only
    # them). FE index.html fetches ``?status=all`` and depends on deleted being
    # present for the deleted filter.
    with _server(_svc(tmp_path)) as (host, port):
        a = _create_task(host, port)["id"]
        _create_task(host, port)["id"]  # a non-deleted task to prove selectivity
        _, _, payload = _req(host, port, "POST", f"/api/hedge-open-tasks/{a}/delete")
        assert _json(payload)["status"] == "deleted"
        # default list excludes the deleted task.
        _, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks")
        assert a not in {t["id"] for t in _json(payload)["tasks"]}
        # status=all includes the deleted task.
        _, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks?status=all")
        assert a in {t["id"] for t in _json(payload)["tasks"]}
        # status=deleted surfaces only the deleted task.
        _, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks?status=deleted")
        assert [t["id"] for t in _json(payload)["tasks"]] == [a]


# ===========================================================================
# 405 on a disallowed method (§3.1)
# ===========================================================================
def test_put_on_tasks_collection_is_method_not_allowed(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        body, ctype = _post_json({"interval_seconds": "2"})
        status, _, payload = _req(
            host, port, "PUT", "/api/hedge-open-tasks", body=body, content_type=ctype
        )
        assert status == 405
        assert _json(payload)["error"] == "method_not_allowed"


# ===========================================================================
# Logs: newest-first cursor pagination + record-transport payload (§3.6)
# ===========================================================================
def test_logs_pagination_and_record_transport_payload(tmp_path):
    exe = RecordTransportExecutor()
    with _server(_svc(tmp_path, executor=exe)) as (host, port):
        tid = _create_task(host, port, _create_body(target_n=3))["id"]
        status, _, _ = _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-all")
        assert status == 200
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-logs?limit=2")
        assert status == 200
        page = _json(payload)
        assert set(page.keys()) == {"logs", "next_cursor"}
        assert len(page["logs"]) == 2
        assert page["next_cursor"] is not None
        # newest first.
        assert page["logs"][0]["id"] > page["logs"][1]["id"]
        first = page["logs"][0]
        assert set(first.keys()) == {"id", "task_id", "ts", "attempt_id", "kind", "payload"}
        # The record-transport log proves the would-send params were recorded,
        # never POSTed.
        assert first["kind"] == "record_transport"
        assert first["payload"]["posted"] is False


# ===========================================================================
# Positions projection (§3.3)
# ===========================================================================
def test_positions_shape_after_fill(tmp_path):
    exe = RecordTransportExecutor()
    with _server(_svc(tmp_path, executor=exe)) as (host, port):
        tid = _create_task(host, port, _create_body(target_n=1))["id"]
        _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-all")
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-positions")
        assert status == 200
        positions = _json(payload)["positions"]
        assert len(positions) == 1
        assert set(positions[0].keys()) == _POSITION_KEYS
        # forward perp is a SELL -> negative signed qty; clean decimal string.
        assert positions[0]["position_qty"].startswith("-")


# ===========================================================================
# Round-1 safety posture (ADR-5): real POST unreachable; /healthz not shadowed
# ===========================================================================
def test_full_scenario_makes_zero_urllib_calls(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("urlopen must never be called on a hedge-open path")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    exe = RecordTransportExecutor(
        [OutcomeSpec.spot_only_filled(), OutcomeSpec.both_failed(), OutcomeSpec.balanced()]
    )
    with _server(_svc(tmp_path, executor=exe)) as (host, port):
        tid = _create_task(host, port, _create_body(target_n=2))["id"]
        # exercise every endpoint; reaching the end proves no network call.
        _req(host, port, "POST", f"/api/hedge-open-tasks/{tid}/fill-all")
        _req(host, port, "GET", "/api/hedge-open-tasks")
        _req(host, port, "GET", "/api/hedge-open-settings")
        _req(host, port, "GET", "/api/hedge-open-logs")
        _req(host, port, "GET", "/api/hedge-open-positions")


def test_healthz_not_shadowed_by_hedge_open_wiring(tmp_path):
    # hedge-open wiring must not shadow the existing /healthz route.
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _req(host, port, "GET", "/healthz")
        assert status == 200


def test_unknown_hedge_path_is_not_found(tmp_path):
    with _server(_svc(tmp_path)) as (host, port):
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks/x/y/z")
        assert status == 404
        assert _json(payload)["error"] == "not_found"


def test_hedge_routes_503_when_service_not_wired(tmp_path):
    # When no hedge service is wired, hedge routes answer 503 (not 500).
    cfg = Config(bind_port=0)
    server = build_server(cfg, _StubSnapshotService(), None, None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        status, _, payload = _req(host, port, "GET", "/api/hedge-open-tasks")
        assert status == 503
        assert _json(payload)["error"] == "hedge_open_service_unavailable"
    finally:
        server.shutdown()
        server.server_close()
