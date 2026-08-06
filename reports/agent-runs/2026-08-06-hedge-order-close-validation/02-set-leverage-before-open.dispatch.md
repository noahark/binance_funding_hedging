# 实施任务：开单前自动设置合约杠杆（3 倍，每任务一次）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
背景：THE 合约开仓 `-2027 Exceeded the maximum allowable position at current leverage`——
交易所以前默认 20 倍杠杆、现最大 10 倍，开仓量在 10 倍下超限。Human 拍板方案 B：**开单
（合约下单）前自动设置该币 3 倍杠杆，每任务只设置一次，放在开单校验通过之后**。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-set-leverage-before-open`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 2
- required_skill: `agents/skills/senior-developer.md`

## Goal

开单任务（`task_type='open'`）在**合约下单前**自动设置该币合约杠杆为 **3 倍**：

- **时机**：开单校验（fresh preflight）**通过之后**、`prepare_attempt`/发单**之前**
  （`_dispatch_one_for_task` live 路径，`service.py:2250`——`_resolve_fresh_preflight` ok 分支后）。
- **每任务只设置一次**：仅 `scheduled_attempt_count == 0`（首个 attempt 发单前）执行；
  后续 attempt（重试/加仓轮次）**不再重复设置**（Human 明确：不是开几次设几次）。
- **失败 fail-closed**：杠杆设置失败 → **阻止发单**、任务暂停 + 任务卡日志中文原因
  （避免在错误杠杆下开仓——若继续下单可能按默认/旧杠杆成交，仓位风险不可控）。
- dry-run（无 live client）跳过（不设杠杆，模拟成功）。

### 实现要求

1. **`backend/services/hedge_open_live_client.py`**：
   - 白名单受控扩展：`("POST", "/fapi/v1/leverage"): "https://fapi.binance.com"`
     （设置合约杠杆，权重 1 类；参数 `symbol` + `leverage`，签名 POST，写语义与订单一致——
     超时/5xx 不重试）。
   - 新方法 `set_leverage(symbol, leverage, *, timestamp_ms, recv_window_ms=None)`：
     签名 POST，返回原始响应；业务失败（非 200 或 body 含错误）抛错带详情（沿用
     `universal_transfer` 的 body 截断模式）。
2. **`backend/services/live_hedge_executor.py`**：`set_leverage(coin, leverage)`——
   调 client（duck-typed，供 service 访问；dry-run executor 无此方法 → service 跳过）。
   杠杆值由 service 传入（常量 `D.OPEN_LEVERAGE = 3`，见下）。
3. **`backend/hedge_open_tasks/domain.py`**：新增常量 `OPEN_LEVERAGE = 3`
   （Human 拍板；注释注明后续可配置化）、失败暂停 reason
   `PAUSE_REASON_LEVERAGE_SET_FAILED`（+中文文案，如「设置合约杠杆失败，任务已暂停（fail-closed，
   未发单）」）。
4. **`backend/hedge_open_tasks/service.py`** `_dispatch_one_for_task`（live 路径）：
   - fresh preflight `ok` 后、`prepare_attempt` 前插入：
     `task_type == TASK_TYPE_OPEN and scheduled_attempt_count == 0` →
     `self._set_leverage_before_open(task, now_us)`：
       - executor 有 `set_leverage`（live）→ 调 `set_leverage(coin, D.OPEN_LEVERAGE)`；
       - 成功 → 继续发单（幂等：交易所重复设置同值无害，但本任务级只调一次）；
       - 失败/异常 → `_pause_task_local`（`PAUSE_REASON_LEVERAGE_SET_FAILED`，中文原因
         带交易所错误详情）+ 任务卡日志（kind 如 `leverage_set_failed`）→ 返回暂停信号，
         **不创建 attempt、不发单**。
   - dry-run（无 `set_leverage` 方法）→ 跳过。
5. **测试**（`test_hedge_cycle_close.py` 或新增 `test_hedge_leverage.py`）：
   - live 模式开单任务：`scheduled_attempt_count==0` 首 attempt 前调 `set_leverage(coin, 3)` 一次；
     成功后 attempt 正常创建/发单；
   - **每任务一次**：target_n>1 时首次设、后续 attempt 不再调（spy 计数 = 1）；
   - **失败 fail-closed**：`set_leverage` 抛错 → 任务暂停（`PAUSE_REASON_LEVERAGE_SET_FAILED`）、
     无 attempt、日志有中文原因 + 错误详情；
   - dry-run：跳过（不调）；
   - 平仓任务（task_type='close'）不设杠杆（回归断言）。
6. **回归全绿**：`python3 -m pytest backend/tests -q` + `node frontend/self-check.js`。

### 不在本次范围

- 不改前端/ledger/划转/完成判定/SPOT_ONLY 路由；
- 不做「全市场批量设置杠杆」（Human 已否决方案 A）、不做杠杆可配置 UI（3 倍先硬编码，
  后续可配置化）；
- 不处理 THE 的既有仓位/杠杆档位（设置 3 倍若被币安档位拒绝（如该币最低档 >3 或档位上限 <3），
  按 fail-closed 暂停并如实记录——这是交易所事实，不是本地可绕过）。

## Allowed Files

可修改：

- `backend/services/hedge_open_live_client.py`（白名单 + set_leverage）
- `backend/services/live_hedge_executor.py`（set_leverage 方法）
- `backend/hedge_open_tasks/domain.py`（OPEN_LEVERAGE + PAUSE_REASON_LEVERAGE_SET_FAILED + 中文）
- `backend/hedge_open_tasks/service.py`（_dispatch_one_for_task 插入 + _set_leverage_before_open）
- 相关测试文件

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `backend/services/hedge_open_live_client.py` 现有写方法模式（universal_transfer）
- `backend/hedge_open_tasks/service.py`（`_dispatch_one_for_task`:2250、`_resolve_fresh_preflight`）

禁止：

- 回退既有改动（SPOT_ONLY 修复等）、改前端/ledger、未授权提交、移动 HEAD、
  访问凭证、对实盘发单/划转/设杠杆（本任务只做代码 + 测试库验证）

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-set-leverage-before-open.handoff.md`

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. 按需读取：`backend/hedge_open_tasks/service.py`（`_dispatch_one_for_task`:2250、
   `_resolve_fresh_preflight`:2153、`_pause_task_local` 先例）、
   `backend/services/hedge_open_live_client.py`（ALLOWLIST + `universal_transfer` 写模式）、
   `backend/services/live_hedge_executor.py`（`universal_transfer`:645 模式）

## Acceptance Checks

1. **白名单**：`POST /fapi/v1/leverage` 进白名单（冻结测试同步）；`set_leverage` 签名 POST、
   参数冻结（symbol/leverage）、超时/5xx 不重试、业务失败抛错带 body 详情。
2. **时机**：live 开单任务 fresh preflight ok 后、prepare_attempt 前设置；设置成功后 attempt
   正常创建。
3. **每任务一次**：target_n>1 时 `set_leverage` 恰好调用 1 次（后续 attempt 不重复）。
4. **fail-closed**：设置失败 → 任务暂停（中文原因 + 错误详情）、无 attempt、不发单、日志落库。
5. **不越界**：平仓任务不设杠杆；dry-run 跳过；SPOT_ONLY 修复/其他逻辑未回退。
6. **回归**：`python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js` 全绿。
7. **范围核对**：`git status --short` 仅列内文件；无前端/ledger/实盘写。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用可执行形式
`读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`（下一关卡：Human 重启服务实盘复测——
开一个合约标的下单，确认先设 3 倍杠杆再发单成功）。以 `[/TASK_RESULT]` 为最后非空白输出。

**评审状态**：本 stage 为验证 + 小 bug 修复（Human 拍板）；修复完成经核验后，是否复评由
Human 决定。设置杠杆属实盘资金/风险操作，**实盘启用需 Human 单独明确授权**（本任务只做
代码 + 测试库验证）。
