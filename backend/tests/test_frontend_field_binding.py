"""Bind the frontend's position-field names to the backend's actual output.

E4 (PROJECT_STATE): the merged-position fields cross the front/back seam by
**hand-typed name** in three places — `domain.py` row keys, `test_hedge_api.py`
`_POSITION_KEYS`, and `index.html` `p.xxx` / `posRow.xxx`. A rename on either
side renders `—` on the page with every test still green: no error, no crash,
no log line. You find out by staring at a dash.

Authority is `_POSITION_KEYS`, and the chain that makes it trustworthy is:

  `test_hedge_api.py::test_positions_shape_after_fill` pins
  `_POSITION_KEYS == set(GET /api/hedge-open-positions response keys)` against a
  **real HTTP response**  →  this module pins `frontend refs ⊆ _POSITION_KEYS`
  →  therefore `frontend refs ⊆ what the API actually sends`.

`merge_positions` alone is NOT the authority: the handler adds fields on top of
the merged rows (`stats_incomplete`, `borrow_interest_usdt` — cycle funding /
interest stats computed at read time in `server.py`), so the merge layer's output
is a strict subset of the wire contract. Anchoring here would have wrongly failed
two live, correctly-rendered fields.

Direction matters: frontend ⊆ backend is enforced (reading a field the backend
never sends is the silent-dash bug). The reverse is NOT enforced — the backend
legitimately publishes fields this particular table does not render.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from backend.hedge_open_tasks import domain as D
from backend.tests.test_hedge_api import _POSITION_KEYS, _TASK_KEYS

INDEX_HTML = Path(__file__).resolve().parents[2] / "frontend" / "index.html"

# 统一账户还款（stage 2026-08-09-pm-margin-repay-v1 T2）：前端还款代码块的扫描锚点。
# 与持仓字段绑定同纪律——改名/重构导致正则抓空时测试会红，而不是静默放行。
_REPAY_SUBMIT_FN = "function submitMarginRepay("
_REPAY_RENDER_FN = "function renderRepayStatus("
# renderRepayStatus 里 `r.xxx` 允许出现的前端本地标记（不是后端记录字段）：
# 请求层错误、传输未知、恢复查询失败、成功后刷新失败。
_REPAY_LOCAL_MARKERS = {"request_error", "transport_unknown", "recovery_error", "refresh_failed"}


def _repay_backend_record_keys() -> set[str]:
    """后端还款记录的真实键集（store `_row_to_doc` 的输出，POST/GET 响应同形）。"""
    from backend.margin_repay.store import MarginRepayStore

    store = MarginRepayStore(":memory:")
    rec, is_new = store.begin(
        client_request_id="00000000-0000-4000-8000-000000000000",
        asset="BTC", amount="0", repay_asset="USDT", now_us=1,
    )
    assert is_new
    keys = set(rec.keys())
    assert len(keys) >= 8, "还款记录字段过少，权威源取错了"
    return keys


def _repay_fn_block(text: str, anchor: str) -> str:
    start = text.index(anchor)
    tail = text.find("\n      function ", start + len(anchor))
    return text[start: tail if tail != -1 else len(text)]


def test_margin_repay_post_body_matches_backend_contract():
    """前端还款 POST body 必须恰含后端 `_REPAY_REQUIRED_FIELDS` 四字段。

    「恰含」双向钉死：少一个字段后端 400，多一个字段（如 specifyRepayAssets
    或任何偿还资产字段）后端同样 400——这是冻结的请求体契约（验收检查 4）。
    """
    from backend.app.server import _REPAY_REQUIRED_FIELDS

    text = INDEX_HTML.read_text(encoding="utf-8")
    block = _repay_fn_block(text, _REPAY_SUBMIT_FN)
    m = re.search(r"hedgeApi\('/api/margin-repay',\s*\{.*?body:\s*\{([^}]*)\}", block, re.S)
    assert m, "未在 submitMarginRepay 找到还款 POST 调用，字段绑定扫描失效"
    # body 逐项（支持 `key: value` 与 shorthand `key` 两种写法），取每项首个标识符为键。
    items = [seg.strip() for seg in m.group(1).split(",") if seg.strip()]
    assert items, "还款 POST body 为空，字段绑定扫描失效"
    keys = set()
    for seg in items:
        km = re.match(r"^([a-z_][a-z0-9_]*)", seg)
        assert km, f"还款 POST body 项无法解析键名: {seg}"
        keys.add(km.group(1))
    assert keys == set(_REPAY_REQUIRED_FIELDS), (
        f"还款请求体字段与后端冻结契约不一致：前端 {sorted(keys)} vs "
        f"后端 {sorted(_REPAY_REQUIRED_FIELDS)}"
    )


def test_margin_repay_record_fields_consumed_exist_in_backend_record():
    """renderRepayStatus 读取的每个记录字段，后端记录都必须真的发出来。

    四态展示读错字段名会静默显示空（页面不报错、测试全绿），与 E4 同形状。
    """
    block = _repay_fn_block(INDEX_HTML.read_text(encoding="utf-8"), _REPAY_RENDER_FN)
    refs = set(re.findall(r"\br\.([a-z_][a-z0-9_]*)", block))
    assert len(refs) >= 7, (
        f"renderRepayStatus 只扫到 {len(refs)} 个 `r.xxx` 引用：正则可能已失效，"
        "字段绑定检查形同虚设。若是有意重构，请同步扫描锚点与下限。"
    )
    unknown = sorted(refs - _REPAY_LOCAL_MARKERS - _repay_backend_record_keys())
    assert not unknown, (
        f"还款四态展示读取了后端记录不存在的字段（页面会静默留白）：{unknown}；"
        f"后端记录 {sorted(_repay_backend_record_keys())}"
    )


@pytest.mark.parametrize(
    "needle",
    ["specifyRepayAssets", "repayLoan", "papi.binance.com", "binance.com"],
)
def test_margin_repay_forbidden_strings_absent_from_frontend(needle):
    """前端绝不出现偿还资产参数名、/repayLoan 路径或交易所 URL（验收检查 4）。

    前端只能发本地 `/api/margin-repay`；偿还资产固定 USDT 是服务端行为，
    前端出现这些字符串意味着越权或外联。
    """
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert needle not in text, f"frontend/index.html 出现违禁字符串: {needle}"

# 前端消费持仓行的两个变量名。**新增消费点必须加进来**，否则它不被本检查覆盖。
# 每个都配了最小引用数下限：改名/重构导致正则抓空时测试会红，而不是静默放行
# （一个永远抓不到东西的检查比没有检查更糟——它给人已被保护的错觉）。
_POSITION_CONSUMERS = {
    # renderHedgeMergedPositions + spotLegLine 内的 p.xxx（函数内扫描）
    "p": 20,
    # 市场表/开单弹框里按 coin 找持仓行的两处 posRow.xxx（全局扫描）
    "posRow": 2,
}

# `p` 只在这个函数（及紧邻的 spotLegLine helper）里代表持仓行；全局扫 `p.` 会把
# parts.map(p => ...) 之类的无关变量一起抓进来。
_POSITION_RENDER_FN = "function renderHedgeMergedPositions()"
_SPOT_LEG_HELPER = "function spotLegLine("
_SMOOTH_RENDER_FN = "function renderSmoothTaskExtras("


def _merge_layer_fields() -> set[str]:
    """``merge_positions`` 实际产出的字段名（wire 契约的**真子集**，handler 还会追加）。

    取两种行的并集：有任务记录的行（bucket + UM 都在）与 no_task 行（只有 UM）。
    ``_merge_build_row`` 有意让所有行的键集一致，取并集只是防御该性质被改掉。
    """
    bucket = {
        "coin": "BTCUSDT", "direction": D.DIR_FORWARD, "position_qty": "-0.5",
        "spot_qty": "0.5", "perp_qty": "0.5", "spot_avg": "50000",
        "perp_avg": "50000", "spot_avg_price_incomplete": False,
        "perp_avg_price_incomplete": False, "includes_deleted_task": False,
        "open_basis_rate": "0", "price_pnl": "0", "accrued_funding": "0",
        "borrow_interest": "0", "net_pnl": "0",
        "spot_symbol": "BTCUSDT", "spot_base_asset": "BTC",
    }
    um = {
        "symbol": "BTCUSDT", "position_side": "SHORT", "position_amt": "-0.5",
        "notional_usdt": "100", "entry_price": "50000", "mark_price": "50100",
        "unrealized_profit": "12.5", "liquidation_price": "0",
    }
    private_account = {
        "verified": True, "error": None, "checked_at": "2026-08-07T00:00:00Z",
        "um_positions": [um],
        "balances_spot": [{"asset": "BTC", "free": "0.5", "locked": "0",
                           "value_usdt": "25000"}],
        "balances_unified": [{"asset": "BTC", "total_balance": "0.5",
                              "cross_margin_borrowed": "0", "value_usdt": "25000"}],
    }
    with_task, _ = D.merge_positions([bucket], private_account)
    no_task, _ = D.merge_positions([], private_account)
    fields = set(with_task[0].keys()) | set(no_task[0].keys())
    assert len(fields) > 20, "merge_positions 产出字段过少，权威源取错了"
    return fields


def _frontend_refs() -> dict[str, set[str]]:
    """按消费变量提取前端引用的字段名。"""
    text = INDEX_HTML.read_text(encoding="utf-8")

    start = text.index(_POSITION_RENDER_FN)
    # 到下一个同级函数定义为止；spotLegLine 在其之前，单独并入。
    tail = text.find("\n      function ", start + len(_POSITION_RENDER_FN))
    render_block = text[start: tail if tail != -1 else len(text)]
    helper_start = text.index(_SPOT_LEG_HELPER)
    helper_end = text.find("\n      function ", helper_start + len(_SPOT_LEG_HELPER))
    render_block += text[helper_start: helper_end if helper_end != -1 else len(text)]

    return {
        "p": set(re.findall(r"\bp\.([a-z_][a-z0-9_]*)", render_block)),
        "posRow": set(re.findall(r"\bposRow\.([a-z_][a-z0-9_]*)", text)),
    }


def test_frontend_position_fields_exist_in_backend_output():
    """前端读的每个持仓字段，后端都必须真的发出来。

    这是 E4 的核心断言。它红了通常意味着：某一侧改了字段名，而另一侧还在用旧名——
    页面会安静地显示 `—`，别的测试不会有任何反应。
    """
    refs = _frontend_refs()
    unknown = {var: sorted(names - _POSITION_KEYS) for var, names in refs.items()}
    unknown = {var: names for var, names in unknown.items() if names}
    assert not unknown, (
        f"前端读取了后端不发送的持仓字段（页面会静默显示 —）：{unknown}；"
        f"wire 契约 {sorted(_POSITION_KEYS)}"
    )


def test_merge_layer_fields_are_all_in_the_wire_contract():
    """merge 层新增的字段必须同步进 ``_POSITION_KEYS``。

    与上面那条共同封住两端：这条防「后端加了字段但契约常量没跟上」，上面那条防
    「前端读了契约里没有的名字」。merge 层是纯函数、最容易被单独改动，而
    ``test_hedge_api`` 那条要跑完整 HTTP 链路才能覆盖它。
    """
    extra = sorted(_merge_layer_fields() - _POSITION_KEYS)
    assert not extra, (
        f"merge_positions 产出了 _POSITION_KEYS 未声明的字段：{extra}；"
        "请同步 test_hedge_api.py 的契约常量，否则前端字段绑定检查会放行不存在的名字"
    )


@pytest.mark.parametrize("var,floor", sorted(_POSITION_CONSUMERS.items()))
def test_frontend_scan_still_finds_references(var, floor):
    """扫描本身没有失效。

    上面的检查靠正则从 index.html 里抓引用。一旦函数改名、变量改名或代码结构变动
    导致抓不到东西，上面那条会**因为集合为空而通过**——一个永远绿的检查比没有检查
    更糟，它给人已被保护的错觉。这里为每个消费点钉一个引用数下限。
    """
    found = _frontend_refs()[var]
    assert len(found) >= floor, (
        f"`{var}.xxx` 只扫到 {len(found)} 个引用（下限 {floor}）：正则可能已失效，"
        f"字段绑定检查形同虚设。若是有意重构，请同步 _POSITION_CONSUMERS 与扫描锚点。"
    )


def test_smooth_task_card_fields_exist_in_task_wire_contract():
    """平滑任务卡不得读取任务 API 中不存在的字段并静默画成破折号。"""
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index(_SMOOTH_RENDER_FN)
    end = text.find("\n      function ", start + len(_SMOOTH_RENDER_FN))
    block = text[start:end if end != -1 else len(text)]
    refs = set(re.findall(r"\btask\.([a-z_][a-z0-9_]*)", block))
    assert {
        "id", "target_n", "slippage_threshold_pct", "smooth_gate_seq",
        "smooth_gate_deadline_at_us",
    } <= refs
    assert refs <= _TASK_KEYS, (
        f"平滑任务卡读取了 task API 不发送的字段：{sorted(refs - _TASK_KEYS)}"
    )


def test_smooth_frontend_reuses_log_poll_and_has_no_new_timer():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "doc.smooth_market" in text
    assert "refreshExpandedRunningHedgeLogs();" in text
    assert text.count("setInterval(() =>") == 4


def test_expanded_log_poll_keeps_non_running_tasks_and_skips_collapsed_tasks():
    text = INDEX_HTML.read_text(encoding="utf-8")
    load_start = text.index("async function loadHedgeTasks()")
    load_end = text.index("async function loadHedgePositions()", load_start)
    load_block = text[load_start:load_end]
    refresh_start = text.index("async function refreshExpandedRunningHedgeLogs()")
    refresh_end = text.index("function patchHedgeTaskLogTable", refresh_start)
    refresh_block = text[refresh_start:refresh_end]
    assert "task && task.status === 'running'" not in load_block
    assert "return task\n              ? loadHedgeTaskLogs(id)" in load_block
    assert "return Boolean(task);" in refresh_block
    assert "state.hedgeLogExpanded" in refresh_block


def test_smooth_dynamic_market_only_renders_for_running_cards():
    text = INDEX_HTML.read_text(encoding="utf-8")
    card_start = text.index("function renderHedgeTaskCard(task)")
    card_end = text.index("async function loadHedgeTaskLogs", card_start)
    card_block = text[card_start:card_end]
    assert "滑点阈值：<strong>${escapeHtml(hedgeText(task.slippage_threshold_pct))}%</strong>" in card_block
    assert "task.mode === 'smooth' && task.status === 'running'" in card_block
    assert "task.mode === 'smooth' ? renderSmoothTaskExtras(task)" not in card_block
