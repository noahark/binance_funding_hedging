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
from backend.tests.test_hedge_api import _POSITION_KEYS

INDEX_HTML = Path(__file__).resolve().parents[2] / "frontend" / "index.html"

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
