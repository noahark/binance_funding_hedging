Identity:
- task_id: `fix-review1-dual-ledger-flow-log-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `20`
- required_skill: `agents/skills/minimal-change-engineer.md`

Goal

统一 review-1（deepseek，`review-1-dual-ledger-flow-log-v1`）对 A+B+C+前端最终交付给出 `REWORK`，两项 in-range 发现。本任务为**修复轮**（`rework_count` 0→1，根因按 F1 命名：「任务 B 引入新装配依赖未同步既有测试桩，且回归声明未覆盖全量」）。**最小修复，不改交付行为**。

**F1（in-range 阻塞）**：`backend/app/server.py:954`（任务 B `550f8b7`）新增 `LedgerFlowService(ledger_store, service.private_client, ...)`，但既有测试桩 `backend/tests/test_service_health.py:255 class _RunStubService` 无 `private_client` 属性，导致 5 个既有测试失败（实测全量 `1336 passed, 5 failed`）：
- `test_run_fatal_when_start_worker_raises`、`test_run_fatal_when_serve_forever_raises`、`test_run_keyboard_interrupt_cleans_up_and_exits_zero`、`test_run_emits_borrow_execution_mode_with_recovery_counts`、`test_run_live_missing_credentials_emits_distinct_blocked_event`。
- **修复要求（评审给定，最小）**：在 `_RunStubService.__init__` 增加 `self.private_client = None`（`LedgerFlowService.is_usable()` 对 `client=None` 返回 `False`，调度器不启动，恰好走通设计 §15.3「通道不可用不调度」路径）；**重跑 `backend/tests/test_service_health.py` 与全量 `pytest backend/tests/`，确认 0 failed**，并把全量原始输出保存为证据（B 的「194 回归全绿」不覆盖 `test_service_health.py`，不可作为回归证据——全量以 `pytest backend/tests/` 实测为准）。

**F2（in-range 建议）**：`backend/ledger_flow/scheduler.py` 无任何单元测试。
- **修复要求（评审给定）**：新增 `backend/tests/test_ledger_flow_scheduler.py`，注入时钟覆盖：分钟<1 不跑、本小时已有成功 run 不跑、预算 3 次耗尽不跑、距上次尝试 <5min 不跑、各条件满足返回 `("scheduled")`；`_startup_catchup` 空库→backfill、上次成功>1h→startup_catchup、≤1h 不跑；`stop()` 幂等。

**不得**修改 `server.py` 装配逻辑、`scheduler.py` 行为、`ledger_flow/service.py`、`domain.py`、`store.py`、前端或契约——本任务只补测试与桩。若发现 F1 真正根因在 `server.py`（桩补不了），停止并回报 Bookkeeper，不得自行扩大改动。

Allowed Files

- `backend/tests/test_service_health.py`（仅 `_RunStubService` 补桩）
- `backend/tests/test_ledger_flow_scheduler.py`（新建）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.pytest.txt`（**全量**回归原始输出：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/`）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/minimal-change-engineer.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`（**必读**：F1/F2 原文、修复要求、检查结果）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（任务 B 交付事实与 scheduler/service 签名）
- `backend/app/server.py`、`backend/tests/test_service_health.py`、`backend/ledger_flow/scheduler.py`、`backend/ledger_flow/service.py`（只读参考）

Acceptance Checks

1. F1：`_RunStubService` 补 `private_client = None`（或等价最小桩）；`backend/tests/test_service_health.py` 单独跑全绿，**全量 `pytest backend/tests/` 0 failed**（原始输出存 `.pytest.txt`，含通过数与耗时）。
2. F2：`test_ledger_flow_scheduler.py` 覆盖评审列出的全部分支（decide 四判据 + 满足时返回 + startup_catchup 三分支 + stop 幂等），注入时钟离线运行。
3. 交付行为零改动：`server.py` 装配、`scheduler.py` 行为、service/domain/store、前端、契约均未动（git diff 仅限 Allowed Files）。
4. 交接件与回执：handoff（Source Report + Human Brief）+ 合规 `[TASK_RESULT v2]` + 三行中文交接；`delivery_sha` 写 `pending`（或被授予提交权时提交）；status 仅改本任务状态。
5. 未启动服务、未访问网络、未读凭据、未执行实盘操作。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。不得自行启动 Reviewer/Bookkeeper，不得合并、部署或执行任何实盘/网络/凭据/下单操作。完成后停止，等待 Bookkeeper 封存并安排 review-1 复审。
