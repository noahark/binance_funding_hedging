# 实施任务：SPOT_ONLY 标的现货路由修复（THE 51023）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
背景缺陷（实测）：THEUSDT forward 开仓，现货腿发到 `/papi/v1/margin/order`（全仓杠杆）
→ 交易所 `-51023 Trading pair does not exist.`（THEUSDT 在 PAPI margin 不存在）→ fail-closed
拒绝。THE 的 `route_class = SPOT_ONLY_CANDIDATE`（仅现货、无杠杆借币，现货
`isMarginTradingAllowed=False`）——`decide_spot_route` 输入缺「仅现货」状态，漏判为可走全仓。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-spot-only-route-fix`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 1（status.json 由当前会话代记，正式 Bookkeeper 复核）
- required_skill: `agents/skills/senior-developer.md`

## Goal

修复「仅现货（SPOT_ONLY，无杠杆借币）」标的的现货路由：现货腿必须走**普通现货端点**
（`/api/v3/order`，regular_spot），不得发到全仓杠杆（`/papi/v1/margin/order`，papi_margin）。

### 根因（已排查确认）

- `classify_route`（`backend/domain/classify.py:17`）：`isMarginTradingAllowed=False` →
  `SPOT_ONLY_CANDIDATE`（仅现货）——判定依据是**公开现货 exchangeInfo 的 isMarginTradingAllowed**。
- `decide_spot_route`（`backend/hedge_open_tasks/domain.py:940`）输入只有
  (direction, contract_type, spot_base_asset, cap_exceeded)——**没有「仅现货」状态**；
  forward 开仓且 cap 未超、非 TRADIFI → 默认 `papi_margin` → 现货腿发全仓 → SPOT_ONLY 标的 51023。
- provider 的 `_read_spot_leg`（`hedge_preflight_provider.py:250`）已读现货 exchangeInfo 原始记录
  （含 `isMarginTradingAllowed`），但返回元组 `(filters, tradable, symbol, base_asset)`
  **没带该字段**——修复只需透传。

### 修复要求

1. `_read_spot_leg` 返回元组**追加** `is_margin_trading_allowed: bool`（从现货原始记录
   `isMarginTradingAllowed`，读失败/缺失按 `False` 保守处理——仅现货按普通现货路由最安全）；
   调用处同步解包。
2. `get_snapshot` 的 route 决策（`hedge_preflight_provider.py:540` 附近）：在调
   `decide_spot_route` 前，**仅现货（`is_margin_trading_allowed is False`）→ 强制
   `regular_spot`**（普通现货端点 `/api/v3/order`），reason 用新增常量
   （如 `D.ROUTE_REASON_SPOT_ONLY_REGULAR`）；**不改 `decide_spot_route` 的既有规则**
   （MARGIN_SPOT/正常标的行为逐字不变）——仅现货是 provider 层的前置强制，不是新规则分支。
3. **-2027 排查（顺带，只排查不改）**：THE 合约腿 `-2027 Exceeded the maximum allowable
   position at current leverage`——确认是「THE 合约已有仓位/杠杆上限」的事实，还是合约开仓
   量超限的 bug；排查结论写 handoff（不改代码）。
4. 测试（`test_hedge_cycle_close.py` 或 `test_hedge_preflight*.py`）：
   - **仅现货标的**（`isMarginTradingAllowed=False`，构造 FakeSnapshot）forward 开仓
     preflight → `spot_route=regular_spot`、`spot_endpoint=/api/v3/order`；
   - **MARGIN_SPOT 标的**（True）回归 → 仍 `papi_margin`（既有行为不变）；
   - close 路径回归：仅现货标的 close+forward（卖现货）已固定 regular_spot，行为不变。
5. 回归全绿：`python3 -m pytest backend/tests -q` + `node frontend/self-check.js`。

### 不在本次范围

- 不改前端、不改 ledger、不改划转/完成判定/白名单；
- 不修 THE 合约 -2027（只排查）；不新增其他「顺手优化」。

## Allowed Files

可修改：

- `backend/services/hedge_preflight_provider.py`（`_read_spot_leg` 透传 + route 决策强制）
- `backend/hedge_open_tasks/domain.py`（仅新增 reason 常量，如 `ROUTE_REASON_SPOT_ONLY_REGULAR`）
- 相关测试文件

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `docs/planning/hedge-open-position-cycle-v1.md`（路由章节）
- `backend/domain/classify.py`（SPOT_ONLY 判定权威）

禁止：

- 回退既有改动、改前端/ledger/白名单、未授权提交、移动 HEAD、
  访问凭证、对实盘发单/划转

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-spot-only-route-fix.handoff.md`

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`（Current Status：数据已清理、从头测试起点）
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. 按需读取：`backend/services/hedge_preflight_provider.py`（`_read_spot_leg`:250、
   `get_snapshot` route 决策:530-545）、`backend/hedge_open_tasks/domain.py`
   （`decide_spot_route`:940、`spot_route_endpoint`:982）、`backend/domain/classify.py`
   （`classify_route`:17-29）、`backend/domain/snapshot.py`（`isMarginTradingAllowed` 用法:226）

## Acceptance Checks

1. **透传**：`_read_spot_leg` 返回含 `is_margin_trading_allowed`；调用处解包一致。
2. **强制路由**：仅现货（False）forward open → `spot_route=regular_spot`、
   `spot_endpoint=/api/v3/order`；MARGIN_SPOT（True）→ 仍 `papi_margin`（回归断言）；
   close 路径行为不变。
3. **-2027 排查结论**：handoff 记录 THE 合约 -2027 是事实还是 bug（带依据，不改代码）。
4. **回归**：`python3 -m pytest backend/tests -q` 全绿；`node frontend/self-check.js` 全绿。
5. **范围核对**：`git status --short` 仅 provider/domain/测试文件；无前端/ledger/白名单/实盘写。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用可执行形式
`读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`（下一关卡：Human 重启服务实盘复测
SPOT_ONLY 标的开仓 / 或本 stage 下一验证任务）。以 `[/TASK_RESULT]` 为最后非空白输出。

**评审状态**：本 stage 为验证 + 小 bug 修复（Human 2026-08-06 拍板）；修复完成经核验后，
是否复评由 Human 决定（本 stage 的 bug 均为实测可复现、非臆想，修复验证以测试 + 实盘复测为准）。
