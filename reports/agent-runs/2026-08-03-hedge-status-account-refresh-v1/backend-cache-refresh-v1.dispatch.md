Identity:
- task_id: `backend-cache-refresh-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `1`
- required_skill: `agents/skills/senior-developer.md`

Goal

实现已批准设计 `docs/planning/hedge-status-account-refresh-v4.md` 的后端、HTTP 契约、schema、开单任务状态钩子和离线测试，不接入前端。约 60 秒 scheduled tick、人工缓存刷新 POST 与开单任务真实 `running → 非 running` 必须复用同一条 SnapshotService worker refresh cycle；所有 Binance I/O 仍只在 worker 内发生。实现 source 级新鲜度、完整/部分/未尝试结果，并保留 GET pure-read、既有 F4 限制和 Human 接受的执行中命令合并窗口。不得执行实盘操作、读取凭证、启动服务或做网络验证。

Allowed Files

- `backend/config.py`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/app/server.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `backend/tests/test_account_cache_refresh_v1.py`（可新建）
- `backend/tests/test_private_client.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_hedge_api.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_hedge_store.py`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-cache-refresh-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`
- `backend/services/snapshot_service.py`、`backend/services/private_client.py`、`backend/domain/snapshot.py`、`backend/app/server.py`、`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`
- `schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md` 与 Allowed Files 中现有测试

Acceptance Checks

1. scheduled、POST 和状态钩子都经唯一 worker-only refresh-cycle helper；force 仅绕过账户/估值 source 的 due 与四个 private transport 精确 key，保留既有 compose、Group C、assemble、validate、publish。
2. `RefreshCacheCommand` 有独立 done/result 与固定 in-flight key；worker 正确区分 symbol command、cache command、sentinel 和 scheduled tick；未运行 worker 时 POST 立即诚实失败；命令异常不会杀死 worker。
3. `RefreshResult` 将 `published` 与 `complete | partial | not_attempted` 分离。complete 包含 `price_map`、unified、UM、spot 及 capability 可用时 PM；partial/未尝试不得被 POST 表述为账户完整更新。
4. `source_checked_at` 固定输出五个 nullable UTC key：`price_map`、`unified_balances`、`um_positions`、`spot_balances`、`pm_account`。每个 source 仅成功写 cache 时推进；失败保留 last-good 值与旧时间；PM capability 不存在时 key 为 null。`checked_at` 与 `valuation.priced_at` 保持既有聚合兼容语义，不表示报价新鲜度。
5. snapshot 与 `/api/hedge-open-positions` 的 account meta 同步该字段；JSON schema 与 API contract 同次更新；字段缺失或额外 key 的测试必须校验失败，不能被 scheduled 异常吞掉。
6. `POST /api/public-market/cache-refresh` 只入队或复用并有界等待；GET `/snapshot` 与 `/hedge-open-positions` 仍无上游 I/O。成功、partial、not_attempted、失败、queued timeout 的 API 测试覆盖齐全。
7. Store 在事务提交后提供真实 old/new transition，保留已有 task/bool 返回形状；HedgeOpenTaskService 仅对真实 `running → 非 running` 提交非等待 cache command。覆盖 `set_task_status`、`pause_task`、`stop_task_fatal`、`resolve_attempt`、`finalize_attempt`、`settle_attempt_no_counters` 的触发或零触发事实。
8. 运行并保存相关离线 pytest 结果；至少覆盖新增测试、private client/account、snapshot、hedge API/service/store 测试。不得使用真实 API key、网络或运行服务。

Stop

只在 Allowed Files 内修改。创建交接件后，以其中 Human Brief 的内容生成合规 `[TASK_RESULT v2]`；将 status 的本任务状态改为 `reported`。在一次有意命名的 delivery commit 中提交允许的代码、测试、契约、status 与交接件；交接件的 `delivery_sha` 写 `pending`。不要自行启动 Reviewer、Bookkeeper、前端任务、部署或任何实盘/网络操作。
