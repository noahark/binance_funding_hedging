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
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from ..asset_transfer.store import (
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    STATUS_UNKNOWN,
    AssetTransferStore,
)
from ..margin_repay.store import MarginRepayStore
from ..borrow_tasks import BorrowError, BorrowTaskService
from ..borrow_tasks import domain as borrow_domain
from ..config import Config, DEFAULT, from_env
from ..hedge_open_tasks import HedgeError as HedgeOpenError
from ..hedge_open_tasks import HedgeOpenTaskService
from ..hedge_open_tasks import domain as hedge_open_domain
from ..ledger_flow import domain as ledger_domain
from ..ledger_flow.domain import WindowValidationError
from ..ledger_flow.scheduler import LedgerScheduler
from ..ledger_flow.service import LedgerFlowService
from ..ledger_flow.store import LedgerStore
# 只取冻结的划转枚举常量（模块无导入副作用）；枚举的唯一权威仍在客户端模块，
# 此处不复制字面量。客户端类本身仍按既有惯例在构造函数内延迟导入。
from ..services.hedge_open_live_client import (
    TRANSFER_TYPE_MAIN_PM,
    TRANSFER_TYPE_PM_MAIN,
)
from ..services.public_ip_service import PublicIpService
from ..services.best_bid_ask_provider import (
    BestBidAskProvider,
    default_source_available,
)
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
#
# Smooth close V1 (2026-08-14) reuses this table. Frozen create body keys:
# coin / direction / mode / single_amount / target_n / task_type /
# slippage_threshold_pct. mode=smooth + task_type=close is legal. Start,
# fill-once (gate_seq), logs, positions and close-gate stay on these paths.
# Running-task book is GET /api/hedge-open-logs?task_id=… (smooth_market);
# the browser opens no live push channel — backend book-ticker subscriptions
# stay inside HedgeOpenTaskService.
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


# 一次批量 max-withdraw 的资产数上限（Q4）。币安该接口无批量版，N 个资产 = N 次签名
# 请求，上限防止一个畸形 query 把 IP 权重池打空。实测统一账户 18 个资产，30 留了余量。
_MAX_WITHDRAW_ASSET_CAP = 30

# ---- 资产互转（stage 2026-08-06-asset-transfer-live-v1）----
# 方向映射只在服务端做：请求体不接受币安 transfer type，杜绝外部注入。
_TRANSFER_ACCOUNTS = ("unified", "spot")
_TRANSFER_TYPE_BY_DIRECTION = {
    ("unified", "spot"): TRANSFER_TYPE_PM_MAIN,
    ("spot", "unified"): TRANSFER_TYPE_MAIN_PM,
}
_TRANSFER_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# 正十进制字符串：先用正则挡掉负号、科学计数法（1e3）与空白，再交给 Decimal。
_TRANSFER_AMOUNT_RE = re.compile(r"^\d+(\.\d+)?$")

_TRANSFER_REQUIRED_FIELDS = (
    "client_request_id", "from_account", "to_account", "asset", "amount", "confirm",
)

# HTTP 状态码的人话含义（review-1 R5）。币安在限流/封禁时常返回空 body 或 HTML，
# 只回 "http 429" 用户看不懂发生了什么；有 msg 时原文一字不改地附在后面。
_TRANSFER_HTTP_MEANING = {
    400: "请求被币安拒绝",
    401: "API 认证失败（密钥或签名无效）",
    403: "无权限（WAF 拒绝或 API 权限不足）",
    418: "IP 已被币安封禁（此前触发限流未停止）",
    429: "请求过于频繁，已触发币安限流",
    500: "币安服务端错误",
    503: "币安服务暂时不可用",
}
# 限流/封禁归 unknown 而非 failed（review-1 R5）。理由不是钱可能已转，而是
# 「失败」在界面上会引导重试，而重试必须换新 client_request_id 才能真正外发——
# 万一那笔其实成功了就会转两次。限流场景本就该停下来人工核对。
_TRANSFER_RATE_LIMIT_STATUSES = (418, 429)


def _transfer_error_message(http_status: int, msg) -> str:
    """把 HTTP 状态码翻成人话，并原样附上币安的原始说明（若有）。"""
    meaning = _TRANSFER_HTTP_MEANING.get(http_status)
    label = f"{meaning}（HTTP {http_status}）" if meaning else f"HTTP {http_status}"
    if isinstance(msg, str) and msg.strip():
        return f"{label}：{msg}"
    return label


# ---- 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1，T1）----
# 复用资产划转已冻结的「无符号普通十进制」形状正则（同一目的：先挡负号、科学计数法与
# 空白），再在本校验里实现还款特有的「精确 "0" = 全部，其余必须严格大于零」分支。
# 偿还资产固定为 USDT（与客户端 REPAY_SPECIFY_ASSET 同源），由服务端写入，请求体不接受。
_REPAY_REQUIRED_FIELDS = ("client_request_id", "asset", "amount", "confirm")
_REPAY_ALLOWED_FIELDS = frozenset(_REPAY_REQUIRED_FIELDS)
# 这些状态码结果不明（钱可能已还），归 unknown 而非 failed——failed 在界面上会引导重试，
# 而重试换新编号万一那笔成功了就会还两次。比划转多一个 408（请求超时，结果不明）。
_REPAY_UNKNOWN_HTTP_STATUSES = (408, 418, 429)


def _opt_str(value) -> Optional[str]:
    """币安回传字段的去类型化存库辅助：``None`` 透传，其余转字符串。"""
    return None if value is None else str(value)


def _parse_margin_repay_request(data):
    """校验还款请求体，返回 ``(parsed, error)``；``error`` 为 ``(status, payload)``。

    四个字段必填且不允许出现偿还资产等额外字段（``specifyRepayAssets`` 或任何未知键一律
    拒绝，杜绝外部覆盖服务端固定的 USDT）。``amount`` 仅接受无符号普通十进制字符串：
    精确 ``"0"`` 表示全部（外发时省略 amount），其余必须严格大于零；``"0.0"``、``"0.00"``、
    ``"00"``、负数、科学计数法、空白与非字符串均拒绝（全程不用 float）。
    """
    if not isinstance(data, dict):
        return None, (400, {"error": "invalid_request", "detail": "请求体必须是 JSON 对象"})
    unknown = set(data) - _REPAY_ALLOWED_FIELDS
    if unknown:
        return None, (400, {
            "error": "invalid_request",
            "detail": f"不允许的字段: {', '.join(sorted(unknown))}（偿还资产由服务端固定）",
        })
    missing = [k for k in _REPAY_REQUIRED_FIELDS if k not in data]
    if missing:
        return None, (400, {
            "error": "invalid_request",
            "detail": f"缺少必填字段: {', '.join(missing)}",
        })
    client_request_id = data["client_request_id"]
    if not isinstance(client_request_id, str) or not _TRANSFER_UUID_RE.match(client_request_id):
        return None, (400, {
            "error": "invalid_request",
            "detail": "client_request_id 必须是 UUID 格式",
        })
    asset = data["asset"]
    if not isinstance(asset, str) or not asset.strip():
        return None, (400, {"error": "invalid_request", "detail": "asset 不能为空"})
    amount = data["amount"]
    if not isinstance(amount, str) or not _TRANSFER_AMOUNT_RE.match(amount):
        return None, (400, {
            "error": "invalid_request",
            "detail": "amount 必须是无符号普通十进制字符串（不接受负号、科学计数法或空白）",
        })
    if amount == "0":
        repay_all = True
    elif Decimal(amount) > 0:
        repay_all = False
    else:
        # 形状合法但既非精确 "0" 也非正数：如 "0.0" / "0.00" / "00"。拒绝，禁止外发
        # amount=0* 一类的数值零（计划评审实现提示第 1 条）。
        return None, (400, {
            "error": "invalid_request",
            "detail": 'amount 仅接受精确 "0"（全部）或严格大于零的正数',
        })
    if data["confirm"] is not True:
        return None, (400, {
            "error": "confirm_required",
            "detail": "confirm 必须为 true",
        })
    return {
        "client_request_id": client_request_id,
        "asset": asset,
        "amount": amount,
        "repay_all": repay_all,
    }, None


def _parse_asset_transfer_request(data):
    """校验划转请求体，返回 ``(parsed, error)``；``error`` 为 ``(status, payload)``。

    只做形状与取值校验，**不做余额充足性预判**——快照缓存 60 秒可能已过期，
    余额不足交由币安返回错误码后原样回显（00-intake.md §4.2）。
    """
    if not isinstance(data, dict):
        return None, (400, {"error": "invalid_request", "detail": "请求体必须是 JSON 对象"})
    missing = [k for k in _TRANSFER_REQUIRED_FIELDS if k not in data]
    if missing:
        return None, (400, {
            "error": "invalid_request",
            "detail": f"缺少必填字段: {', '.join(missing)}",
        })
    client_request_id = data["client_request_id"]
    if not isinstance(client_request_id, str) or not _TRANSFER_UUID_RE.match(client_request_id):
        return None, (400, {
            "error": "invalid_request",
            "detail": "client_request_id 必须是 UUID 格式",
        })
    from_account = data["from_account"]
    to_account = data["to_account"]
    if from_account not in _TRANSFER_ACCOUNTS or to_account not in _TRANSFER_ACCOUNTS:
        return None, (400, {
            "error": "invalid_request",
            "detail": "from_account / to_account 仅支持 unified 或 spot",
        })
    if from_account == to_account:
        return None, (400, {
            "error": "invalid_request",
            "detail": "转出与转入账户不能相同",
        })
    asset = data["asset"]
    if not isinstance(asset, str) or not asset.strip():
        return None, (400, {"error": "invalid_request", "detail": "asset 不能为空"})
    amount = data["amount"]
    if not isinstance(amount, str) or not _TRANSFER_AMOUNT_RE.match(amount):
        return None, (400, {
            "error": "invalid_request",
            "detail": "amount 必须是正十进制字符串（不接受负号、科学计数法或空白）",
        })
    if Decimal(amount) <= 0:
        return None, (400, {"error": "invalid_request", "detail": "amount 必须大于 0"})
    # 动钱前的显式意图确认（Human O-1 决定的唯一门）：防止误调用与误触发。
    if data["confirm"] is not True:
        return None, (400, {
            "error": "confirm_required",
            "detail": "confirm 必须为 true",
        })
    return {
        "client_request_id": client_request_id,
        "from_account": from_account,
        "to_account": to_account,
        "asset": asset,
        "amount": amount,
    }, None


class _Handler(BaseHTTPRequestHandler):
    service = None  # injected via build_server
    borrow_service = None  # injected via build_server; None -> 503 on borrow routes
    hedge_open_service = None  # injected via build_server; None -> 503 on hedge routes
    ledger_flow_service = None  # injected in run(); None -> 503 on private-ledger routes
    public_ip_service = None  # injected in run(); None -> 503 on /api/system/public-ip
    # 资产互转（stage 2026-08-06-asset-transfer-live-v1）：store 与 PAPI 客户端
    # 分别注入；任一为 None -> 该路由 503（不做静默降级）。
    asset_transfer_store = None
    asset_transfer_client = None
    # 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1）：store 总是注入（GET
    # 恢复零上游），client 受 APP_MARGIN_REPAY_ENABLED 闸门控制——未注入时 POST 返回 503。
    margin_repay_store = None
    margin_repay_client = None
    frontend_dir = None
    server_version = "funding-hedging-public-market/1.0"

    def log_message(self, fmt, *args):  # silence default stderr access log
        return

    def handle(self) -> None:
        # Client may close before we finish writing (refresh / nav-away / aborted
        # fetch). socketserver otherwise dumps a full traceback for this benign
        # ConnectionError. Catch only ConnectionError so real bugs still surface.
        try:
            super().handle()
        except ConnectionError:
            pass

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
        if path == "/api/private-ledger/pnl-series":
            self._handle_pnl_series()
            return
        if path == "/api/private-account/max-withdraw":
            self._handle_max_withdraw()
            return
        if path == "/api/margin-repay":
            self._handle_margin_repay_get()
            return
        if path == "/api/system/public-ip":
            self._handle_public_ip()
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
        if path == "/api/asset-transfer":
            self._handle_asset_transfer()
            return
        if path == "/api/margin-repay":
            self._handle_margin_repay_post()
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

    def _handle_pnl_series(self):
        """GET /api/private-ledger/pnl-series?start=&end=&bucket= — 资金费率收益
        曲线（2026-08-20）。四条构成（资金费 / 手续费 / 利息 / 滑点）与合成净收益
        的累计序列，口径同持仓级 net_pnl。纯读、现算、不写库。

        滑点两个来源：已平仓周期取全量 close-log；在持仓周期取周期级两腿加权均价
        （``list_open_cycle_slippage_basis``）——当下的收益正来自这些持仓，漏掉它
        净收益就不完整。两个来源**同一口径**，故周期平仓时曲线不重排。算不出的
        （缺价/缺量）计入 ``slippage_incomplete_count``，两腿成交量不等（敞口）
        推出的滑点计入 ``slippage_unbalanced_count``，均只在脚注明示，**不**遮蔽
        净收益；遮蔽只发生在数据源读失败（``*_ok=false``）或缺行情价
        （``unpriced_assets``）时。
        """
        if self.ledger_flow_service is None or self.hedge_open_service is None:
            self._send_ledger(
                503, {"error": "pnl_series_unavailable",
                      "detail": "ledger-flow or hedge-open service not configured"})
            return
        query = parse_qs(urlparse(self.path).query)
        start, end = query.get("start", [None])[0], query.get("end", [None])[0]
        bucket = query.get("bucket", ["hour"])[0]
        bucket_ms = {"hour": 3600_000, "day": 86_400_000}.get(bucket)
        if bucket_ms is None:
            self._send_ledger(400, {"error": "invalid_bucket",
                                    "detail": "bucket must be hour or day"})
            return
        store = self.ledger_flow_service._store
        # 窗口可省：默认取本地账本全量。起点必须落在**已覆盖范围的开头**而不是 0
        # ——从 0 起算会被 coverage 判成「起点截断」，让完整的默认视图永远挂着
        # 不完整警告，真出现空洞时反而没人再信那条提示。
        try:
            end_ms = int(end) if end is not None else _now_ms()
            if start is not None:
                start_ms = int(start)
            else:
                cov = store.get_coverage()
                starts = [v for v in (cov.get("interest_start_ms"), cov.get("income_start_ms"))
                          if v is not None]
                start_ms = max(starts) if starts else 0
        except (ValueError, TypeError):
            self._send_ledger(400, {"error": "invalid_window",
                                    "detail": "start and end must be integer milliseconds"})
            return
        # 折算价与持仓级 net_pnl 同源：公开行情缓存的 opening_quotes（纯读、无请求）。
        price_map = {}
        try:
            snapshot = self.service.get_snapshot()
        except SnapshotNotReady:
            snapshot = None
        if isinstance(snapshot, dict):
            for row in snapshot.get("rows") or []:
                quotes = row.get("opening_quotes") or {}
                if quotes.get("status") == "fresh" and quotes.get("spot_bid_price"):
                    price_map[row.get("symbol")] = quotes["spot_bid_price"]

        # 全量 close-log：历史页的 limit=100 是分页展示语义，用在这里会在周期数
        # 超过 100 后悄悄丢掉最早周期的滑点，而其资金费等仍在账本里。
        status, close_doc = self._safe_hedge(self.hedge_open_service.get_close_logs, None)
        close_logs = close_doc.get("logs") or [] if status == 200 else []
        # 在持仓周期：周期级两腿加权均价，与 close-log 逐字同口径（2026-08-21）。
        # 均价的分母是该周期 open/close 腿的累计成交量，**不是** aggregate_positions
        # 的剩余净持仓（open−close）——后者已被平掉的部分不该从开仓成本基里消失。
        pos_status, fills_doc = self._safe_hedge(
            self.hedge_open_service.get_open_cycle_slippage_basis)
        open_cycle_fills = fills_doc.get("fills") or [] if pos_status == 200 else []

        try:
            payload = ledger_domain.build_pnl_series(
                interest_rows=store.query_interest_rows(start_ms, end_ms),
                income_rows=store.query_income_rows(start_ms, end_ms),
                capital_rows=store.query_capital_flow_rows(start_ms, end_ms),
                close_logs=close_logs,
                open_cycle_fills=open_cycle_fills,
                price_map=price_map,
                start_ms=start_ms, end_ms=end_ms, bucket_ms=bucket_ms,
            )
        except WindowValidationError as exc:
            self._send_ledger(400, {"error": "invalid_window", "detail": str(exc)})
            return
        payload["schema_version"] = "private-ledger-pnl/v1"
        payload["served_at_ms"] = _now_ms()
        payload["window"] = {"start_ms": start_ms, "end_ms": end_ms}
        payload["coverage"] = self.ledger_flow_service.coverage_for_window(start_ms, end_ms)
        # 合约已实现盈亏：对冲下由现货腿反向盈亏抵消，故**不进净收益**，单列供对账。
        payload["realized_pnl"] = ledger_domain.summarize_income_by_type_asset(
            [r for r in store.query_income_rows(start_ms, end_ms)
             if r.get("income_type") == "REALIZED_PNL"])
        payload["close_logs_ok"] = status == 200
        payload["open_fills_ok"] = pos_status == 200
        self._send_ledger(200, payload)

    def _handle_max_withdraw(self):
        """GET /api/private-account/max-withdraw?assets=USDT,BNB,... — 统一账户
        各资产的最大可转出额（Q4, 2026-08-07；2026-08-07 晚改为批量）。

        按需读，不进快照：币安的 `maxWithdraw` **没有批量版**，一个资产一次签名请求，
        且该值随价格波动，缓存住就会在转出那一刻给出过期的数。改批量是为了让前端发
        **一个**请求而不是 N 个并发——循环放在后端，对交易所的节奏由这里控制。

        单个资产读失败**不影响**其余资产：每个资产各自带 ``error``，整体仍 200。
        取不到时该资产 ``max_withdraw: null`` 而非错误码——调用方要能区分「读不到」
        和「是 0」（后者在满仓抵押时是合法且重要的答案）。
        """
        query = parse_qs(urlparse(self.path).query)
        raw = (query.get("assets", [""])[0] or "").strip()
        assets = [a.strip().upper() for a in raw.split(",") if a.strip()]
        if not assets or not all(a.isalnum() for a in assets):
            self._send_ledger(
                400, {"error": "invalid_asset",
                      "detail": "assets query param is required "
                                "(comma-separated, alphanumeric)"})
            return
        if len(assets) > _MAX_WITHDRAW_ASSET_CAP:
            self._send_ledger(
                400, {"error": "too_many_assets",
                      "detail": f"at most {_MAX_WITHDRAW_ASSET_CAP} assets per request"})
            return
        client = getattr(self.service, "private_client", None)
        if client is None or not getattr(client, "enabled", False):
            self._send_ledger(
                503, {"error": "private_account_unavailable",
                      "detail": "private client not configured"})
            return
        results = []
        seen = set()
        for asset in assets:
            if asset in seen:  # 去重：同一资产不重复打交易所
                continue
            seen.add(asset)
            result = client.fetch_max_withdraw(asset, force=True)
            results.append({
                "asset": asset,
                "max_withdraw": (result or {}).get("max_withdraw"),
                "error": None if result else (client.last_error or "max_withdraw_failed"),
            })
        self._send_ledger(200, {"results": results})

    def _handle_public_ip(self):
        """GET /api/system/public-ip — 本机后端进程观察到的公网出口 IP（只读、同源）。

        仅供 Human 核对 API 白名单；不能证明币安实际看到的出口 IP（VPN/代理/路由
        可能不同），绝不驱动白名单、交易、借贷、划转、还款或任何 live gate。未注入
        服务时固定 503，不外呼；该端点不是公共市场快照的一部分。
        """
        if self.public_ip_service is None:
            self._send_ledger(503, {"error": "public_ip_unavailable"})
            return
        self._send_ledger(200, self.public_ip_service.get())

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

    # -------------------------------------------------------- asset transfer

    def _handle_asset_transfer(self):
        """POST /api/asset-transfer — 统一账户 ⇄ 普通现货账户的受控划转。

        Human 2026-08-06 决定（O-1/O-2）：不设独立闸门、不设单笔上限。动钱约束为
        ``confirm: true`` 必填 + 全量落库审计 + ``client_request_id`` 幂等。

        币安 ``/sapi/v1/asset/transfer`` **没有幂等键**，重复提交会真的转两次；
        幂等由本地唯一索引提供——``store.begin`` 返回 ``is_new=False`` 即直接回放
        首次结果，绝不二次外发。外发是 one-shot：超时/5xx 不重试，记 ``unknown``。
        """
        if self.asset_transfer_store is None or self.asset_transfer_client is None:
            self._send_borrow(503, {
                "error": "asset_transfer_unavailable",
                "detail": "划转通道未配置（离线模式或缺少 API 凭证）",
            })
            return
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        parsed, verr = _parse_asset_transfer_request(data)
        if verr is not None:
            self._send_borrow(*verr)
            return
        # 币种白名单：必须在转出账户当前快照的余额里，杜绝任意币种注入与打字错误。
        whitelist = self._asset_transfer_assets(parsed["from_account"])
        if whitelist is None:
            self._send_borrow(503, {
                "error": "snapshot_not_ready",
                "detail": "账户快照未就绪，无法校验币种，请稍后重试",
            })
            return
        if parsed["asset"] not in whitelist:
            self._send_borrow(400, {
                "error": "unknown_asset",
                "detail": f"{parsed['asset']} 不在转出账户的余额列表中",
            })
            return
        record, is_new = self.asset_transfer_store.begin(
            client_request_id=parsed["client_request_id"],
            from_account=parsed["from_account"],
            to_account=parsed["to_account"],
            asset=parsed["asset"],
            amount=parsed["amount"],
            now_us=_now_us(),
        )
        if not is_new:
            # 幂等回放：该 client_request_id 已处理过，不再外发。
            self._send_borrow(200, record)
            return
        resolution = self._dispatch_asset_transfer(
            _TRANSFER_TYPE_BY_DIRECTION[(parsed["from_account"], parsed["to_account"])],
            parsed["asset"],
            parsed["amount"],
        )
        record = self.asset_transfer_store.resolve(
            parsed["client_request_id"], now_us=_now_us(), **resolution
        )
        self._send_borrow(200, record)

    def _asset_transfer_assets(self, account: str):
        """转出账户当前快照里的资产集合；快照未就绪返回 ``None``（调用方 503）。"""
        try:
            snapshot = self.service.get_snapshot()
        except Exception:
            return None
        private_account = (snapshot or {}).get("private_account") or {}
        key = "balances_unified" if account == "unified" else "balances_spot"
        rows = private_account.get(key) or []
        return {
            row.get("asset") for row in rows
            if isinstance(row, dict) and row.get("asset")
        }

    def _dispatch_asset_transfer(self, transfer_type: str, asset: str, amount: str) -> dict:
        """一次性外发并把结果分类成落库字段（00-intake.md §4.6）。

        传输失败或 5xx -> ``unknown``，**不是失败**：钱可能已经转了，不重试，
        由人工去币安核对。4xx -> ``failed``，币安 code/msg 原样带回。200 且带
        ``tranId`` -> ``succeeded``；200 但无 ``tranId`` -> ``unknown``（结果不明，
        不擅自当成功）。
        """
        try:
            resp = self.asset_transfer_client.universal_transfer(
                transfer_type, asset, amount, timestamp_ms=_now_ms(),
            )
        except Exception as exc:
            # 未预期异常也必须落终态，否则记录会永远停在 pending，前端不知结果。
            return {
                "status": STATUS_UNKNOWN,
                "error_message": f"transport_exception:{type(exc).__name__}",
            }
        if resp is None or resp.transport_error is not None or resp.http_status is None:
            return {
                "status": STATUS_UNKNOWN,
                "error_message": f"transport_error:{getattr(resp, 'transport_error', None)}",
            }
        body = resp.body if isinstance(resp.body, dict) else {}
        if resp.http_status == 200:
            tran_id = body.get("tranId")
            if tran_id is None:
                return {"status": STATUS_UNKNOWN, "error_message": "http 200 但响应缺少 tranId"}
            return {"status": STATUS_SUCCEEDED, "tran_id": str(tran_id)}
        code = body.get("code")
        if resp.http_status in _TRANSFER_RATE_LIMIT_STATUSES:
            status = STATUS_UNKNOWN
        elif 400 <= resp.http_status < 500:
            status = STATUS_FAILED
        else:
            status = STATUS_UNKNOWN
        return {
            "status": status,
            "error_code": None if code is None else str(code),
            "error_message": _transfer_error_message(resp.http_status, body.get("msg")),
        }

    # ---------------------------------------------------------- margin repay

    def _handle_margin_repay_post(self):
        """POST /api/margin-repay — 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1）。

        独立闸门 ``APP_MARGIN_REPAY_ENABLED`` 默认关闭，不受 ``APP_HEDGE_EXECUTOR`` 控制。
        币安 ``/papi/v1/margin/repay-debt`` 没有客户端幂等键、也无法按本地请求号查结果——
        重复提交会真的还两次（每次最多 50,000 USD）。幂等由本地 ``client_request_id`` 唯一
        索引提供：``store.begin`` 返回 ``is_new=False`` 即直接回放首次结果，绝不二次外发。
        外发 one-shot：超时/5xx/408/418/429 记 ``unknown``（钱可能已还），不重试。
        """
        if self.margin_repay_store is None or self.margin_repay_client is None:
            self._send_borrow(503, {
                "error": "margin_repay_unavailable",
                "detail": "还款通道未配置（未开启 APP_MARGIN_REPAY_ENABLED、离线模式或缺少 API 凭证）",
            })
            return
        data, error = self._read_json_body(required=True)
        if error is not None:
            self._send_borrow(*error)
            return
        parsed, verr = _parse_margin_repay_request(data)
        if verr is not None:
            self._send_borrow(*verr)
            return
        # 借款资产白名单：必须精确命中当前统一账户快照中 cross_margin_borrowed > 0 的资产，
        # 杜绝任意资产注入与打字错误（也杜绝给未借款资产发起无意义还款）。
        borrowed = self._margin_repay_borrowed_assets()
        if borrowed is None:
            self._send_borrow(503, {
                "error": "snapshot_not_ready",
                "detail": "账户快照未就绪，无法校验借款资产，请稍后重试",
            })
            return
        if parsed["asset"] not in borrowed:
            self._send_borrow(400, {
                "error": "unknown_asset",
                "detail": f"{parsed['asset']} 当前不在统一账户借款资产中（cross_margin_borrowed > 0）",
            })
            return
        record, is_new = self.margin_repay_store.begin(
            client_request_id=parsed["client_request_id"],
            asset=parsed["asset"],
            amount=parsed["amount"],
            repay_asset="USDT",
            now_us=_now_us(),
        )
        if not is_new:
            # 幂等回放：该 client_request_id 已处理过，不再外发。
            self._send_borrow(200, record)
            return
        resolution = self._dispatch_margin_repay(parsed["asset"], parsed["repay_all"], parsed["amount"])
        record = self.margin_repay_store.resolve(
            parsed["client_request_id"], now_us=_now_us(), **resolution
        )
        self._send_borrow(200, record)

    def _handle_margin_repay_get(self):
        """GET /api/margin-repay?client_request_id=<UUID> — 纯本地恢复查询。

        只读 SQLite 记录，**不访问快照、不调用币安**（页面重载或浏览器到本机服务响应丢失后
        用同一请求号恢复状态）。存在返回记录、不存在 404、非法/缺失/重复参数 400。
        """
        if self.margin_repay_store is None:
            self._send_borrow(503, {
                "error": "margin_repay_unavailable",
                "detail": "还款存储未配置",
            })
            return
        qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if list(qs) != ["client_request_id"] or len(qs.get("client_request_id", [])) != 1:
            self._send_borrow(400, {
                "error": "invalid_request",
                "detail": "仅接受单一参数 client_request_id",
            })
            return
        client_request_id = qs["client_request_id"][0]
        if not _TRANSFER_UUID_RE.match(client_request_id):
            self._send_borrow(400, {
                "error": "invalid_request",
                "detail": "client_request_id 必须是 UUID 格式",
            })
            return
        record = self.margin_repay_store.get(client_request_id)
        if record is None:
            self._send_borrow(404, {
                "error": "not_found",
                "detail": "未找到该 client_request_id 的还款记录",
            })
            return
        self._send_borrow(200, record)

    def _margin_repay_borrowed_assets(self):
        """统一账户当前快照中 ``cross_margin_borrowed > 0`` 的资产集合；快照未就绪返回
        ``None``（调用方 503，零外发）。不缓存负债额，每次按当前快照实时判定。"""
        try:
            snapshot = self.service.get_snapshot()
        except Exception:
            return None
        private_account = (snapshot or {}).get("private_account") or {}
        rows = private_account.get("balances_unified") or []
        borrowed = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("asset"):
                continue
            raw = row.get("cross_margin_borrowed")
            if raw is None or raw == "":
                continue
            try:
                if Decimal(str(raw)) > 0:
                    borrowed.add(row["asset"])
            except (ValueError, TypeError):
                continue
        return borrowed

    def _dispatch_margin_repay(self, asset: str, repay_all: bool, amount: str) -> dict:
        """一次性外发并把结果分类成落库字段。

        成功判定从严（计划 §3 / 验收 6）：仅 HTTP 200 + JSON 对象 + ``success is True`` +
        响应 ``asset`` 与请求一致才归 ``succeeded``；否则即便 200 也归 ``unknown``。
        明确普通 4xx 拒绝归 ``failed``；网络/超时/无 HTTP、408、418、429、5xx 与非典型状态码
        归 ``unknown``（钱可能已还，禁止重试）。任何上游结果都落终态，不自动重试。
        """
        amount_arg = None if repay_all else amount
        try:
            resp = self.margin_repay_client.repay_margin_debt(
                asset, amount_arg, timestamp_ms=_now_ms(),
            )
        except Exception as exc:
            # 未预期异常也必须落终态，否则记录会永远停在 pending。
            return {
                "status": STATUS_UNKNOWN,
                "error_message": f"transport_exception:{type(exc).__name__}",
            }
        if resp is None or resp.transport_error is not None or resp.http_status is None:
            return {
                "status": STATUS_UNKNOWN,
                "error_message": f"transport_error:{getattr(resp, 'transport_error', None)}",
            }
        status_code = resp.http_status
        body = resp.body if isinstance(resp.body, dict) else {}
        if status_code == 200:
            if body.get("success") is True and body.get("asset") == asset:
                return {
                    "status": STATUS_SUCCEEDED,
                    "repaid_amount": _opt_str(body.get("amount")),
                    "update_time": _opt_str(body.get("updateTime")),
                }
            return {"status": STATUS_UNKNOWN, "error_message": "http 200 但响应不满足严格成功条件"}
        if status_code in _REPAY_UNKNOWN_HTTP_STATUSES or status_code >= 500:
            status = STATUS_UNKNOWN
        elif 400 <= status_code < 500:
            status = STATUS_FAILED
        else:
            status = STATUS_UNKNOWN
        return {
            "status": status,
            "error_code": _opt_str(body.get("code")),
            "error_message": _transfer_error_message(status_code, body.get("msg")),
        }

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
        method = _HEDGE_OPEN_ACTIONS[action]
        if action == "fill-once":
            data, error = self._read_hedge_body(required=False)
            if error is not None:
                self._send_hedge_open(*error)
                return
            args = (task_id, data)
        else:
            error = self._drain_hedge_body()
            if error is not None:
                self._send_hedge_open(*error)
                return
            args = (task_id,)
        self._send_hedge_open(
            *self._safe_hedge(getattr(self.hedge_open_service, method), *args)
        )

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
        # 统一解析器（2026-08-07 unified-resolver）：从快照 rows 的已解析现货真值
        # （resolve_spot_leg 的 spot.base_asset，如 bStock 的 SNXXB、1000x 的 BONK）
        # 构造 {合约 symbol: 现货 base asset} 映射传入 merge，展示层不再自己剥字符串；
        # 快照未就绪/无 spot 时映射为空 → merge 回退旧规则（现状不变）。
        asset_map = {}
        if isinstance(snapshot, dict):
            for _r in snapshot.get("rows") or []:
                _spot = _r.get("spot") if isinstance(_r, dict) else None
                if isinstance(_spot, dict) and _spot.get("base_asset"):
                    asset_map[_r.get("symbol")] = _spot["base_asset"]
        merged, account_meta = hedge_open_domain.merge_positions(
            positions, private_account, asset_map
        )
        # Stage 2026-08-03-hedge-status-account-refresh-v1 (design §3.5): pass the
        # full fixed five-key source_checked_at object through the positions
        # account meta, so the open-positions panel can show the same per-source
        # success times as the snapshot. merge_positions (hedge_open domain) is
        # not modified; this is a post-merge attachment in the composition root.
        # When the snapshot/private_account is absent the fixed all-null shape is
        # still emitted so the five keys are always present.
        # F4（2026-08-07）：把「哪些账户源本次没读到」一并透传，供持仓表提示
        # 「未获取到交易所持仓数据，仅展示本地缓存记录」。与 source_checked_at 同模式
        # 放在组装根——它是**纯展示**数据，merge 层不消费（表格保留、只加一行红字，
        # 没有行级判定）。缺失一律按空列表处理：`[]` 语义是「全部可用」，而旧块/
        # 测试构造块不带该键，绝不能因此反过来报「读不到」。
        if isinstance(private_account, dict):
            account_meta["source_checked_at"] = private_account.get("source_checked_at")
            account_meta["unavailable_sources"] = (
                private_account.get("unavailable_sources") or []
            )
        else:
            account_meta["source_checked_at"] = {
                "price_map": None,
                "unified_balances": None,
                "um_positions": None,
                "spot_balances": None,
                "pm_account": None,
            }
            # 快照整个不在 -> 四个账户源确实一个都没读到。这里**必须**列全，不能填
            # 空列表：空列表的语义是「全部可用」，在这条路径上会是又一次假声明。
            account_meta["unavailable_sources"] = [
                "unified_balances", "um_positions", "spot_balances", "pm_account",
            ]
        # 持仓周期费率/利息统计（功能二，stage3 §3.2/§3.3）：纯读、现算、不写库。
        # 对每个带周期字段的 merged row 现算三列（窗口 = [cycle_opened_at,
        # cycle_closed_at 或 now]，毫秒换算在查询层）；ledger 未注入 / 无周期 /
        # 窗口起点不可解析 → 三列保持占位；coverage 不足（含窗口内 gaps）→ 三列
        # 置 None + stats_incomplete 标记，绝不把覆盖率不足的窗口当成真值；
        # 任一源不可解析 → net_pnl = None（「暂无」，绝不部分相加）。
        # base_asset 推导优先用统一解析器的快照真值（asset_map，bStock/1000x
        # 对齐），缺失时回退 _merge_base_asset 旧规则（1000x 不对齐），组合根推导。
        lsvc = self.ledger_flow_service
        # Human 2026-08-05：利息按币（asset）计，资金费按 USDT 计——net_pnl 必须把
        # 利息换算成 U 再相减，否则单位不一致。价格源 = 公开行情缓存 rows 的
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
            # 与 merge 层同序（步骤③）：任务固化列 > 快照 asset_map > 旧规则。
            base_asset = (
                row.get("spot_base_asset")
                or asset_map.get(row.get("coin"))
                or hedge_open_domain._merge_base_asset(row.get("coin"))
            )
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
            # 单位一致：net_pnl = 资金费(U) − 利息换算(U) − 开仓手续费(U)（利息与
            # 手续费都是成本，账本记正数；2026-08-08 Human 更正利息为减项，
            # 2026-08-20 Human Fast 增补手续费减项）。三个源任一缺失、不全
            # （trading_fee_incomplete）或不可解析 → 「暂无」，绝不输出残缺假数据。
            fee_usdt = row.get("trading_fee_usdt")
            if (funding is not None and interest_usdt is not None
                    and not row.get("trading_fee_incomplete")
                    and fee_usdt is not None):
                try:
                    row["net_pnl"] = str(
                        Decimal(funding) - Decimal(interest_usdt) - Decimal(fee_usdt))
                except InvalidOperation:
                    row["net_pnl"] = None
            else:
                row["net_pnl"] = None  # 任一缺失/不全/不可解析 → 「暂无」
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
    _Handler.public_ip_service = None  # injected in run() after this returns
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
    if config.offline:
        market_provider = None
    elif default_source_available():
        market_provider = BestBidAskProvider()
    else:
        market_provider = None
        print(
            "[HEDGE-OPEN] 平滑开单公共盘口不可用：未安装 ccxt；"
            "新建平滑任务将被拒绝，既存任务仍可超时或人工放行。",
            file=sys.stderr, flush=True,
        )
    if mode != "live":
        # B-4 (stage 2026-08-06): THE dry-run pollution incident's direct cause
        # was a process started as disabled without anyone noticing. Make the
        # disabled state unmistakable on the service terminal at startup.
        print(
            "!!! [HEDGE-OPEN] 对冲下单已禁用（APP_HEDGE_EXECUTOR=disabled）："
            "任何任务不会真实发单，也不会产生成交记录。"
            "如需实盘开单，请用 scripts/run-server.sh 加载 .env 并以 live 模式启动。",
            file=sys.stderr, flush=True,
        )
        return HedgeOpenTaskService(
            str(db_path), mode=mode, market_provider=market_provider
        )
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
        market_provider=market_provider,
    )


def _build_asset_transfer_client(config: Config):
    """构造资产互转用的 PAPI/SAPI 客户端（stage 2026-08-06-asset-transfer-live-v1）。

    与 ``_build_restricted_asset_client`` 同一模式：复用既有 hedge 凭证，独立于
    ``APP_HEDGE_EXECUTOR``。**这是有意的**——该开关的语义是「对冲开单任务是否真实
    发单」，而划转是用户手动发起的独立动作，不属于开单链路。离线模式或缺少 API key
    时返回 ``None``，路由随即 503（不静默降级成假成功）。

    客户端的 deny-by-default 路径白名单 + 硬编码 host 限制了它能做什么；本通路只
    调用 ``universal_transfer``，其 transfer type 由服务端映射后传入（冻结枚举）。
    """
    if config.offline or not config.binance_hedge_api_key:
        return None
    from ..services.hedge_open_live_client import HedgeOpenLiveClient

    return HedgeOpenLiveClient(
        api_key=config.binance_hedge_api_key,
        api_secret=config.binance_hedge_api_secret,
        user_agent=config.user_agent,
    )


def _build_margin_repay_client(config: Config):
    """构造统一账户全仓杠杆还款用的 PAPI 客户端（stage 2026-08-09-pm-margin-repay-v1）。

    **独立默认关闭闸门** ``APP_MARGIN_REPAY_ENABLED``（与划转不同：划转无独立开关，已接受
    风险）。只有显式开启、非离线且还款所需 key/secret 均存在时才构造 client；否则返回
    ``None``，POST 路由随即 503（零上游，不静默降级）。复用 hedge API 凭证（PAPI TRADE
    端点，与开单同 key），不受 ``APP_HEDGE_EXECUTOR`` 控制（该开关只管对冲开单）。客户端
    的 deny-by-default 白名单 + 硬编码 host 限制了它能做什么；本通路只调用
    ``repay_margin_debt``，其 asset/amount 由服务端校验后传入，指定偿还资产固定 USDT。
    """
    if not config.margin_repay_enabled or config.offline:
        return None
    if not config.binance_hedge_api_key or not config.binance_hedge_api_secret:
        return None
    from ..services.hedge_open_live_client import HedgeOpenLiveClient

    return HedgeOpenLiveClient(
        api_key=config.binance_hedge_api_key,
        api_secret=config.binance_hedge_api_secret,
        user_agent=config.user_agent,
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
    # Stage 2026-08-06 task 05 (§1.3): wire the hedge preflight + close-spot
    # gate to the snapshot worker's READ-ONLY cache (get_cached_source). Same
    # decoupled pattern as configure_cache_refresh above — only this callable
    # crosses the two services, and it never triggers a refresh.
    _snapshot_reader = getattr(service, "get_cached_source", None)
    if callable(_snapshot_reader):
        hedge_open_service.configure_snapshot_reader(_snapshot_reader)
        # 预检 provider 的 snapshot_reader 是构造参数；_build_hedge_service 已在
        # 上面构建，此处通过服务层转发注入（provider 由 service 持有并只读转发）。
        hedge_open_service.configure_preflight_reader(_snapshot_reader)
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
    # 真实公网出口 IP（stage 2026-08-12-local-ip-display-v1）：进程内缓存只读服务，
    # 构造期零 I/O、惰性外呼；仅供 Human 核对 API 白名单。在 build_server 返回后注入，
    # 与 ledger_flow_service 同一装配顺序（build_server 已把该属性复位为 None）。
    _Handler.public_ip_service = PublicIpService()
    # 资产互转（stage 2026-08-06-asset-transfer-live-v1）：独立库 + 独立客户端。
    _Handler.asset_transfer_store = AssetTransferStore(
        str(config.borrow_db_path.parent / "asset-transfer.sqlite3")
    )
    _Handler.asset_transfer_client = _build_asset_transfer_client(config)
    # 统一账户全仓杠杆还款（stage 2026-08-09-pm-margin-repay-v1）：独立库 + 独立默认关闭
    # 闸门。store 总是注入（GET 恢复零上游），client 受 APP_MARGIN_REPAY_ENABLED 控制。
    _Handler.margin_repay_store = MarginRepayStore(
        str(config.borrow_db_path.parent / "margin-repay.sqlite3")
    )
    _Handler.margin_repay_client = _build_margin_repay_client(config)
    # 启动可见性（提示，非闸门）：清楚区分启用/未启用，且不泄露任何凭证。
    if _Handler.margin_repay_client is None:
        print(
            "[MARGIN-REPAY] 还款端点未启用：APP_MARGIN_REPAY_ENABLED 未开启，或离线模式，"
            "或缺少 hedge API 凭证。POST /api/margin-repay 一律返回 503（GET 仅读本地记录）。",
            file=sys.stderr, flush=True,
        )
    else:
        print(
            "!!! [MARGIN-REPAY] 还款端点已启用：POST /api/margin-repay 会向币安"
            "POST /papi/v1/margin/repay-debt 发起真实还款，**不受 APP_HEDGE_EXECUTOR 控制**。"
            "指定偿还资产固定 USDT（同币资产仍优先）；单次最多 50,000 USD 由交易所终判；"
            "全部还款记入 data/margin-repay.sqlite3（client_request_id 幂等，one-shot 不重试）。",
            file=sys.stderr, flush=True,
        )
    # review-1 R1：划转端点没有独立开关（Human O-1 决定），且不受
    # APP_HEDGE_EXECUTOR 控制。开单链路在禁用时会打醒目提示，划转此前什么都不打，
    # 启动后无从判断这个口子是死是活——这里补上可见性（是提示，不是闸门）。
    if _Handler.asset_transfer_client is None:
        print(
            "[ASSET-TRANSFER] 划转端点未启用（离线模式或缺少 API 凭证）："
            "POST /api/asset-transfer 一律返回 503。",
            file=sys.stderr, flush=True,
        )
    else:
        print(
            "!!! [ASSET-TRANSFER] 划转端点已启用：POST /api/asset-transfer 会向币安"
            "发出真实划转，**不受 APP_HEDGE_EXECUTOR 控制**（该开关只管对冲开单）。"
            "唯一门槛是请求体 confirm=true；全部划转记入 data/asset-transfer.sqlite3。",
            file=sys.stderr, flush=True,
        )
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
        # Legacy field name (frozen for log consumers): since DEC-2026-08-21 no
        # task is ever blocked, so the value is the number of in-flight POSTs the
        # PREVIOUS process left unconfirmed — each one a balance to check on the
        # Binance console, not a stalled task.
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
        f" (offline={config.offline}, ttl={config.cache_ttl_seconds}s,"
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
