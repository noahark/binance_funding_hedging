# Task Handoff: 2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun`
- role: `Implementer`（target_model: deepseek）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 CST`
- base_sha: `f153cdc`（`git rev-parse f153cdc` 直取）
- delivery_sha: `pending`（本任务未获提交授权，改动保留在工作树，由 Bookkeeper 处理交付提交）

### 背景

2026-08-06 THE 实盘事件（`evidence/2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`
+ `-glm-diagnosis-crosscheck.md` 双模型互证）：

- **A 取证盲区**：16:41:59 合约腿 `papi.binance.com` 抛 `URLError` → `_send` 只留
  `"connection_error"` 字符串、`exc` 整体丢弃；另有 `_error_leg` 连 raw 都不落库（异常静默）。
- **B 假成交污染**：16:35 重启漏加载 `.env` → `APP_HEDGE_EXECUTOR=disabled` 缺省 →
  默认注入 `RecordTransportExecutor` → 16:38:06 任务 `e22ce275` 产生 2 笔假成交
  （`dryspot-*`/`dryperp-*` 4 条 leg 行）→ 本地口径现货虚增 400、合约虚增 400
  （面板 800/600 vs 交易所真实 400/200）。Human 拍板：**删除系统内 dry-run 类下单/成交模式**。

### 实际修改范围

**A-1 `backend/services/hedge_open_live_client.py`**：新增模块级脱敏辅助
`_transport_error_text(category, exc)`，`_send` 的 TimeoutError / URLError / 其他异常
三分支全部改为 `"<分类>:<ExcType>: <msg>"` 形态并保留 `exc` 详情。约束：分类词仍为
前缀；长度 ≤200；`URLError.reason` 优先于 `str(exc)`；消息含 `http`/`?` 时只保留类型名
（签名/API key 泄漏风险高于取证价值）。`HedgeHttpResponse` 字段与 DB schema 未动，
`_raw_response_dict` 直通 `hedge_open_raw_response.transport_error`。

**A-2 `backend/services/live_hedge_executor.py`**：`_error_leg` 用 `exc` 构造与
`_raw_response_dict` 形状一致的 raw dict（`{"http_status": None, "transport_error":
"<leg_send_exception>:<ExcType>: <msg>", "code": None, "msg": None, "body": ""}`，
脱敏规则同 A-1；`exc is None` 时 `"leg_send_exception:unknown"`），并设置
`raw_response` 使 `_persist_leg_raw` 不再跳过；`dispatch._run` 的 except 增加
`[HEDGE_LEG]` stderr 诊断日志（沿用 `[SET_LEVERAGE]` 先例）。控制流不变：该腿仍
`LEG_UNKNOWN_QUERYING`（查询、绝不重发，ADR-2）。

**B-1 移除生产 dry-run 执行器**：

- `backend/hedge_open_tasks/executor.py`：删除 `OutcomeSpec`、`RecordTransportExecutor`、
  `_simulate_leg`、`_rejected_leg`、`_snapshot_price`、`_leg_qty_filters`（已核验仅该类
  使用）；保留 `AttemptContext` / `AttemptOutcome` / `HedgeExecutor` Protocol /
  `DisabledHedgeExecutor`；模块 docstring 改写为 disabled + live 两态。
- `backend/hedge_open_tasks/__init__.py`：移除 `RecordTransportExecutor` / `OutcomeSpec`
  的 import 与 `__all__` 条目。
- `backend/hedge_open_tasks/service.py`：`:36` import 移除 `RecordTransportExecutor`；
  `:481` 默认执行器改为 `executor or DisabledHedgeExecutor()` 并重写注释块；
  `_dispatch_simulated` docstring 更新（不再产生模拟成交，只写
  `category=ATTEMPT_DISABLED` + `filled_qty=0`，`cumulative_base_qty=0` 不参与聚合）。
- `backend/services/hedge_preflight_provider.py`：4 处注释 dry-run/record transport
  表述改为 disabled（零成交），仅改注释不改逻辑。

**B-2 测试夹具迁移**：

- 新建 `backend/tests/fakes.py`：`RecordTransportFake`（原 `RecordTransportExecutor`
  逐字搬运，仅改名）+ `OutcomeSpec` / `_simulate_leg` / `_rejected_leg` /
  `_snapshot_price` / `_leg_qty_filters`。
- 7 个测试文件 import 改指 `backend.tests.fakes`：test_hedge_executor / test_hedge_api /
  test_hedge_service / test_hedge_wire_constraints / test_hedge_cycle_close /
  test_hedge_task_local / test_hedge_leverage。
- `backend/tests/test_hedge_purity.py` 新增 `test_no_record_transport_reference_in_production_code`
  （grep 证明 `backend/hedge_open_tasks/` + `backend/services/` 无 `RecordTransport`）。

**B-3 历史假数据清理（破坏性，Human 已授权）**：

- 新脚本 `scripts/clean-dryrun-fake-fills.py`（默认 dry-run 只读；`--apply` 先备份再
  单事务清理；写前核验任务名下 leg 全为 dry 前缀否则拒执行；`--audit` 落盘 JSON）。
- 执行记录见 `evidence/2026-08-06-hedge-order-close-validation-dryclean.audit.json`：
  备份 `data/hedge-open-tasks.sqlite3.bak-dryclean-20260806-182416`；
  删除 4 条 dry leg + 2 个 attempt（id 4/5）；任务 `e22ce275` 三计数归零、status→deleted；
  `hedge_open_raw_response` 0 行无需清理；`hedge_open_log` 3 条（含 2 条 record_transport
  定性证据）保留。

**B-4 启动模式可见性**：`backend/app/server.py::_build_hedge_service` 在非 live 分支
打印醒目 stderr 警告「对冲下单已禁用…不会真实发单，也不会产生成交记录」；live 分支
行为不变；既有 `hedge_open_execution_mode` 生命周期事件保留不动。

### 测试断言变动说明（dispatch 要求逐条说明）

1. `test_hedge_executor.py::test_service_default_executor_is_record_transport` →
   `test_service_default_executor_is_disabled`：断言对象从 `RecordTransportExecutor`
   改为 `DisabledHedgeExecutor`。理由：B-1 将生产默认执行器改为 Disabled（零成交），
   原断言语义已不存在，属 B-1 直接后果。
2. `test_hedge_service.py::test_live_mode_without_injected_executor_still_record_transport`
   → `..._still_disabled`：同上，默认执行器断言改为 `DisabledHedgeExecutor`，
   `_live_dispatch_capable() is False` 断言不变（Disabled 无 `dispatch` 方法）。
3. `test_hedge_service.py::test_fill_once_advances_success` /
   `test_fill_all_runs_to_done` / `test_tick_respects_start_gate` 与
   `test_hedge_api.py::test_fill_once_advances_then_done_is_invalid_state`：
   构造 svc 时显式注入 `executor=RecordTransportFake()`；断言逐字不变。理由：B-1 后
   默认 executor 不再模拟成交，注入 fake 是保住这些端到端场景（fill→success/done/
   invalid_state）的唯一方式，场景覆盖一条未删。
4. `test_hedge_cycle_close.py::_svc` helper：默认注入 `RecordTransportFake()`。
   理由：该文件全部测试（open/close 周期、完成判定、结算日志）依赖模拟成交；
   `_StubCloseVerifyExecutor` 等包装逻辑不变，断言逐字不变。
5. `test_hedge_wire_constraints.py::test_prefix_s1_derivation_fails_offline_and_new_derivation_restores`：
   `monkeypatch.setattr` 目标从 `backend.hedge_open_tasks.executor` 改为
   `backend.tests.fakes`。理由：fake 迁移后 `_client_order_ids` 在 fakes 模块命名空间
   绑定（import 时拷贝），patch 生产模块不再影响 fake；断言与场景逐字不变。
6. 其余 5 处测试文件改动仅为 import 行与标识符改名（`RecordTransportExecutor` →
   `RecordTransportFake`），断言逻辑逐字不变。

### 命令与结果

- `scripts/clean-dryrun-fake-fills.py`（dry-run 核验）→ 通过（4 dry legs / 2 attempts /
  0 raw / verification 空）
- `scripts/clean-dryrun-fake-fills.py --apply --audit …/dryclean.audit.json` →
  对账：`spot_qty 800→400`、`perp_qty 600→200`、`position_qty -600→-200`；
  attempt 6/7 的 leg 与 raw 行双库比对 `identical: True`（零改动）；
  备份文件存在（376832 字节）。
- 人工证据（默认 disabled 零成交 + transport_error 详情可读回）通过。
- `python3 -m pytest backend/tests -q` → **1446 passed**（含本次新增：
  A-1 4 个传输异常测试、A-2 2 个异常证据测试、B-2 purity 断言、B-4 stderr 警告测试）。
- `node frontend/self-check.js` → 全部自检通过。

### 未完成事项 / 不能假设的事实

- 周期 `096232b7` 的 `first_task_id`/`last_task_id` 现指向已删除任务 `e22ce275`
  （dispatch 声明为另一条已记录待办，本次未动周期表）。
- 本任务未提交（无提交授权）；工作树含 01（SPOT_ONLY 路由）/ 02（set-leverage）既有
  未提交改动，均未回退。
- `data/hedge-open-tasks.sqlite3.bak-dryclean-20260806-182416` 为 B-3 清理前备份，
  请保留至 Human 确认面板口径正确后按既有惯例处理。
- 工作区新增 `.reasonix/`（宿主桌面元数据）与 `macos_input_outage_playbook.md`
  （其他会话产物）非本任务文件，未触碰。
- 服务当前停止；下一步由 Human 重启实盘复测。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-dryclean.audit.json`
  2. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun.handoff.md`
  3. `reports/agent-runs/2026-08-06-hedge-order-close-validation/03-transport-evidence-and-drop-dryrun.dispatch.md`
  4. `backend/hedge_open_tasks/service.py`（:481 默认执行器、`_dispatch_simulated`）
  5. `backend/services/live_hedge_executor.py`（`_error_leg`、`_run`）
  6. `backend/services/hedge_open_live_client.py`（`_transport_error_text`、`_send`）
- 执行：Human 用 `scripts/run-server.sh` 重启服务实盘复测——(a) 面板持仓回到 400/200
  与交易所一致；(b) 故意 `python3 -m backend.app.server`（不加载 .env）启动一次，
  确认 disabled 模式有醒目 stderr 警告、且点「成交 1 次」不再产生任何假成交记录。
- 关卡：面板对账（400/200）与 disabled 无假成交均为 Human 目视验收。
- 不能假设的事实：服务未运行；`hedge_open_settings.executor_mode_snapshot` 仍是陈旧
  死字段（停 2026-07-27，dispatch 声明不在本次范围）；前端无 executor_mode 常驻标识
  （Opus P0-3 另开任务）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun
执行结果: completed
结果摘要: 传输层异常详情全保全（_send 三分支 + _error_leg 落 raw）；dry-run 假成交执行器移出生产（仅测试 fake）；历史 4 笔假成交已清理（800/600→400/200/-200，备份+审计）；disabled 启动醒目警告；1446 测试 + self-check 全绿
产物: [backend/services/hedge_open_live_client.py, backend/services/live_hedge_executor.py, backend/hedge_open_tasks/executor.py, backend/hedge_open_tasks/__init__.py, backend/hedge_open_tasks/service.py, backend/services/hedge_preflight_provider.py, backend/app/server.py, backend/tests/fakes.py, backend/tests/test_hedge_open_live_client.py, backend/tests/test_live_hedge_executor.py, backend/tests/test_hedge_executor.py, backend/tests/test_hedge_api.py, backend/tests/test_hedge_service.py, backend/tests/test_hedge_wire_constraints.py, backend/tests/test_hedge_cycle_close.py, backend/tests/test_hedge_task_local.py, backend/tests/test_hedge_leverage.py, backend/tests/test_hedge_purity.py, backend/tests/test_service_health.py, scripts/clean-dryrun-fake-fills.py, reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-dryclean.audit.json, reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun.handoff.md]
检查结果: [A-1 transport_error 三分支详情+脱敏+≤200 通过(pass), A-2 _error_leg 落 raw+状态不变 通过(pass), B-1 生产 grep 无 RecordTransport+默认 Disabled 通过(pass), B-2 7 文件迁 fakes+纯度断言 通过(pass), B-3 对账 800→400/600→200/-600→-200+备份+6/7 零改动 通过(pass), B-4 disabled 启动警告 通过(pass), 回归 pytest 1446 passed+self-check 全绿 通过(pass), 范围核对 Allowed Files 内+既有改动未回退 通过(pass)]
阻塞项: [none]
本地北京时间: 2026-08-06 18:29:59 CST
下一步模型: deepseek（Bookkeeper；本任务回执的直接接收者）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun.handoff.md；执行：核验交接件与 dryclean.audit.json、确认工作树改动范围后封存 delivered/reported；关卡：Human 用 scripts/run-server.sh 重启服务实盘复测（面板 400/200 + disabled 警告无假成交）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
