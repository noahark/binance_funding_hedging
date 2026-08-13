from __future__ import annotations

import http.client
import json
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

from backend.app.server import build_server
from backend.config import Config
from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.best_bid_ask_provider import BookTickerSnapshot
from backend.tests.fakes import RecordTransportFake


SPOT = ("binance", "spot", "BTCUSDT")
SWAP = ("binance", "swap", "BTCUSDT")


class _SnapshotService:
    def get_snapshot(self):
        return {"rows": []}


class _Preflight:
    def get_snapshot(self, coin, direction, task_type="open", position_side_mode=None):
        filters = {
            "lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
            "market_lot_size": {"min_qty": "0.001", "max_qty": "1000", "step_size": "0.001"},
            "notional": {"min_notional": "1", "apply_min_to_market": True},
        }
        return D.PreflightSnapshot(
            spot_filters=filters,
            perp_filters=filters,
            balances={"USDT": Decimal("1000000"), "BTC": Decimal("1000000")},
            position_mode=D.POS_MODE_BOTH,
            est_price=Decimal("100"),
        )


class _Market:
    def __init__(self):
        self.callback = None
        self.snapshots = {}

    def set_on_change(self, callback):
        self.callback = callback

    def subscribe(self, key):
        return None

    def release(self, key):
        return None

    def latest(self, key):
        return self.snapshots.get(key)

    def publish(self, key, *, bid, bid_qty, ask, ask_qty, status="live"):
        self.snapshots[key] = BookTickerSnapshot(
            key=key,
            bid_price=Decimal(bid),
            bid_qty=Decimal(bid_qty),
            ask_price=Decimal(ask),
            ask_qty=Decimal(ask_qty),
            exchange_ts_ms=None,
            received_at_us=123,
            generation=1,
            status=status,
            error_zh=None,
        )

    def close(self):
        return None


@contextmanager
def _server(tmp_path, *, market=True):
    executor = RecordTransportFake()
    provider = _Market() if market else None
    service = HedgeOpenTaskService(
        str(tmp_path / "smooth-api.sqlite3"),
        executor=executor,
        preflight_provider=_Preflight(),
        mode="disabled",
        market_provider=provider,
    )
    server = build_server(Config(bind_port=0), _SnapshotService(), None, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[:2], service, provider, executor
    finally:
        server.shutdown()
        server.server_close()
        service.close()


def _request(address, method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if data is None else {
        "Content-Type": "application/json", "Content-Length": str(len(data)),
    }
    conn = http.client.HTTPConnection(*address, timeout=5)
    conn.request(method, path, body=data, headers=headers)
    response = conn.getresponse()
    result = response.status, json.loads(response.read().decode())
    conn.close()
    return result


def _smooth_body(**changes):
    body = {
        "coin": "BTCUSDT", "direction": "forward", "mode": "smooth",
        "single_amount": "1", "target_n": 2,
        "slippage_threshold_pct": ".05",
    }
    body.update(changes)
    return body


def test_create_smooth_normalizes_threshold_and_exposes_gate_fields(tmp_path):
    with _server(tmp_path) as (address, _, _, _):
        status, task = _request(address, "POST", "/api/hedge-open-tasks", _smooth_body())
        assert status == 201
        assert task["mode"] == "smooth"
        assert task["status"] == "paused"
        assert task["pause_reason"] == "awaiting_manual_start"
        assert task["pause_reason_zh"] == "任务首次执行必须点击启动"
        assert task["slippage_threshold_pct"] == "0.05"
        assert task["smooth_gate_seq"] is None
        assert task["smooth_gate_started_at_us"] is None
        assert task["smooth_gate_deadline_at_us"] is None
        assert task["smooth_gate_force_requested"] is False
        assert task["smooth_gate_state"] == "none"


def test_create_smooth_accepts_long_integers_and_rejects_bad_formats(tmp_path):
    with _server(tmp_path) as (address, _, _, _):
        for raw in ("9" * 30, "-" + "9" * 100, "-0", ".05"):
            status, task = _request(
                address, "POST", "/api/hedge-open-tasks",
                _smooth_body(slippage_threshold_pct=raw),
            )
            assert status == 201
            expected = "0.00" if raw == "-0" else (
                "0.05" if raw == ".05" else raw + ".00"
            )
            assert task["slippage_threshold_pct"] == expected

        for raw in ("0.055", "1e-2", "5%", "", None, 1):
            status, error = _request(
                address, "POST", "/api/hedge-open-tasks",
                _smooth_body(slippage_threshold_pct=raw),
            )
            assert (status, error["error"]) == (400, "invalid_field")


def test_create_rejects_missing_market_invalid_mode_pair_and_threshold_leak(tmp_path):
    with _server(tmp_path, market=False) as (address, _, _, _):
        status, error = _request(
            address, "POST", "/api/hedge-open-tasks", _smooth_body()
        )
        assert (status, error["error"]) == (400, "smooth_market_unavailable")

    with _server(tmp_path / "next") as (address, _, _, _):
        status, error = _request(
            address, "POST", "/api/hedge-open-tasks",
            _smooth_body(task_type="close"),
        )
        assert (status, error["error"]) == (400, "invalid_field")
        status, error = _request(
            address, "POST", "/api/hedge-open-tasks",
            _smooth_body(mode="immediate"),
        )
        assert (status, error["error"]) == (400, "invalid_field")


def test_smooth_fill_once_requires_current_gate_seq_and_never_fills_all(tmp_path):
    with _server(tmp_path) as (address, service, _, executor):
        _, task = _request(address, "POST", "/api/hedge-open-tasks", _smooth_body())
        task_id = task["id"]
        status, error = _request(
            address, "POST", f"/api/hedge-open-tasks/{task_id}/fill-once",
            {"gate_seq": 1},
        )
        assert (status, error["error"]) == (409, "start_required")
        assert error["detail"] == "任务首次执行必须点击启动"

        status, started = _request(address, "POST", f"/api/hedge-open-tasks/{task_id}/start")
        assert status == 200
        assert started["status"] == "running"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            worker = service._workers.get(task_id)
            if worker is None or not worker.is_alive():
                break
            time.sleep(0.01)
        service.store.open_smooth_gate(task_id, 1, 10)

        status, error = _request(
            address, "POST", f"/api/hedge-open-tasks/{task_id}/fill-once"
        )
        assert (status, error["error"]) == (400, "invalid_field")
        status, error = _request(
            address, "POST", f"/api/hedge-open-tasks/{task_id}/fill-once",
            {"gate_seq": 2},
        )
        assert (status, error["error"]) == (409, "smooth_gate_conflict")
        status, task = _request(
            address, "POST", f"/api/hedge-open-tasks/{task_id}/fill-once",
            {"gate_seq": 1},
        )
        assert status == 200
        assert task["smooth_gate_force_requested"] is True
        assert executor.records == []

        status, error = _request(
            address, "POST", f"/api/hedge-open-tasks/{task_id}/fill-all"
        )
        assert (status, error["error"]) == (409, "smooth_fill_all_unsupported")


def test_task_logs_expose_real_market_values_and_disconnected_nulls(tmp_path):
    with _server(tmp_path) as (address, _, market, _):
        _, task = _request(address, "POST", "/api/hedge-open-tasks", _smooth_body())
        market.publish(SPOT, bid="99.9", bid_qty="2", ask="100", ask_qty="1")
        market.publish(SWAP, bid="100.1", bid_qty="1", ask="100.2", ask_qty="2")
        status, page = _request(
            address, "GET", f"/api/hedge-open-logs?task_id={task['id']}"
        )
        assert status == 200
        live = page["smooth_market"]
        assert live["spot"]["ask"] == "100"
        assert live["perp"]["bid"] == "100.1"
        assert live["forward_spread_pct"] == "0.10"
        assert live["spot_coverage_pct"] == "100.00"
        assert live["perp_coverage_pct"] == "100.00"
        assert live["gate_pass"] is True

        market.publish(
            SPOT, bid="99.9", bid_qty="2", ask="100", ask_qty="1",
            status="disconnected",
        )
        _, page = _request(
            address, "GET", f"/api/hedge-open-logs?task_id={task['id']}"
        )
        assert page["smooth_market"]["spot"] == {
            "status": "disconnected", "received_at_us": 123,
            "bid": None, "bid_qty": None, "ask": None, "ask_qty": None,
        }
        assert page["smooth_market"]["gate_pass"] is False
        assert page["smooth_dispatch_audits"] == []
