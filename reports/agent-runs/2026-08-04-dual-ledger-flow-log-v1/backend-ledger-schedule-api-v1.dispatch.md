Identity:
- task_id: `backend-ledger-schedule-api-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `<由 Bookkeeper 在路由本 packet 时写入当时的实际 revision；本 packet 由 Planner 起草时 status.json revision 为 2>`
- required_skill: `agents/skills/senior-developer.md`

Goal

在任务 A 已交付的 `backend/ledger_flow/domain.py` 与 `store.py` 之上，交付**拉取编排、每小时定时刷新、增量统计与两条 HTTP 路由**（三任务串行中的第二份）。**本任务不改前端**（那是任务 C），也不得修改任务 A 的文件。

权威契约：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §13.1–§13.5（路由与响应）、§15（节拍、窗口、重试、增量定义）、§14（账本硬规则）。

**1. `backend/ledger_flow/service.py`（拉取编排）**：一次 run = 用注入的 `PrivateClient` 按 §13.5 分页拉两个源（左 `size=100`/`current` 递增、上限 40 页；右 `limit=1000`/`page` 递增、上限 10 页，**不传** `incomeType`、**不传** `symbol`），去重后经 store 幂等入库，并在同一事务写 `flow_refresh_runs` 记录与 `ledger_meta` 的覆盖范围。

- **任一页失败 → 该栏本次 run 记 `error` 且该栏本次不写库**；另一栏不受影响。半截账比没有账更危险。
- 达到页数上限仍未拉完 → run 记 `truncated=true`。
- 错误只记稳定短码（`interest_history_failed` / `um_income_failed` / `rate_limited` / `private_channel_disabled`），**不得**携带币安原始报文或 URL。
- **单飞锁**：`scheduled` / `manual` / `backfill` / `startup_catchup` 共用一把进程级锁，`acquire(blocking=False)`，抢不到即返回忙（不排队）。
- 拉取窗口按 §15.2：`window_end = now`，`window_start = max(coverage_end_ms - 3h, now - 30d)`；空库首次为 `kind="backfill"`、回补 30 天。**3 小时重叠回拉是硬要求**——资金费会分批到账也会晚到（原型脚本因此在发现新资金费后 `Sleep 10s` 再拉一次），靠幂等键去重，重叠不会产生重复行。缺口 > 30 天时窗口截断为最近 30 天且覆盖范围标为不连续，**不得静默留下空洞**。

**2. `backend/ledger_flow/scheduler.py`（节拍）**：守护线程每 **20 秒**醒一次，当「当前分钟 ≥ 1」且「当前自然小时尚无成功的 scheduled run」时执行一次 `kind="scheduled"` run。**不得**用 sleep 到精确时刻——时钟跳变与休眠唤醒会让精确定时失效，而「本小时是否已成功」这个判据天然幂等，也天然覆盖漏跑补偿。启动时若上次成功 run 距今超过 1 小时（或库为空）立即执行一次 `startup_catchup` / `backfill`。失败则 5 分钟后重试、本小时最多重试 2 次（共 3 次尝试），仍失败等下个整点；每次尝试都落一条 run 记录。私有通道未启用或离线模式：**调度器不启动**。线程模式参照既有 `backend/borrow_tasks/scheduler.py`（monotonic 节拍 + `threading.Event` 停止）。

**3. 增量统计（§15.4，最容易做错的一处）**：

```text
baseline_ms = 倒数第二次成功 scheduled/startup_catchup run 的 finished_at_ms
本次新增    = 所有 first_seen_at_ms > baseline_ms 的行
```

- 口径是**入库时间**不是发生时间；**手动刷新不移动 `baseline_ms`**，它带进来的行仍落在当前增量窗口内，下一次整点刷新才把基准前移。
- 不足两次成功 scheduled run → `delta.complete=false`，**不下发可能误导的数字**。
- 增量分组：利息按 `asset`；合约流水按 `(income_type, asset)`；**再加**资金费按 `symbol` 的分组，且 `symbol` 分组内仍按 `asset` 分列，**永远不跨币种相加**。
- `today` 参照按**发生时间**归属、以**北京时间**当日 00:00 为界；`delta` 与 `today` 口径不同，不得混用。

**4. HTTP 路由（`backend/app/server.py`）**：

- `GET /api/private-ledger/flow-log?start=<ms>&end=<ms>` —— **纯读本地库、零上游 I/O**，响应严格按 §13.2；窗口长度**不再有 30 天上限**；参数非法回 `400 invalid_window`，服务未装配回 `503 flow_log_unavailable`。
- `POST /api/private-ledger/refresh` —— 触发一次 `kind="manual"` run，响应按 §13.4；忙 `429 flow_log_busy`、私有通道未启用 `409 private_channel_disabled`、未装配 `503`。无请求体字段（body 读完即丢弃），不接受时间窗参数。
- 装配沿用 borrow/hedge 的 `_Handler` 类属性注入模式在 `run()` 内完成；`build_server` 签名保持不变。`backend/services/snapshot_service.py` **只允许**新增一个只读访问器暴露既有 `PrivateClient` 实例（复用同一次凭据读取与同一套 `offline / private_channel_enabled` 门禁），不得改动其它任何行为。

**5. 响应硬规则复核**（与任务 A 同源，服务层同样要守）：ID 一律字符串；金额原样透传、缺失为 `null`；**禁止对金额列使用 SQL 聚合**，汇总一律 Python `Decimal` 且分组内有不可解析金额时 `*_total` 为 `null`；明细每栏最多返回 **500 行**（时间倒序）而 `row_count` 与 `summary` 始终按**全量**计算；`coverage.complete=false` 必须如实下发（诚实性护栏，前端据此提示「本地数据只到某日」，**空结果绝不能被呈现为"这段时间没有流水"**）。

不改快照 JSON schema、不改 60 秒快照调度、不改 cache-refresh、不改持仓合并、不改任何既有端点行为、不改任务 A 的文件、不动 `backend/ledger_flow/__init__.py`（用子模块路径导入）、不做下单/借还/划转/gate/凭证/部署/实盘操作。

Allowed Files

- `backend/ledger_flow/service.py`（新建）
- `backend/ledger_flow/scheduler.py`（新建）
- `backend/app/server.py`
- `backend/services/snapshot_service.py`（仅新增只读访问器）
- `backend/tests/test_ledger_flow_service.py`（新建）
- `backend/tests/test_ledger_flow_api.py`（新建）
- `docs/api/public-market-contract.md`（追加 v0.12 amendment）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（create-only；Bookkeeper 须在路由前执行 `test ! -e` 并把结果记在本节；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.pytest.txt`（测试原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13、§14、§15、§17）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`（任务 A 的交付事实与实际接口）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`
- `backend/ledger_flow/domain.py`、`backend/ledger_flow/store.py`（任务 A 已交付）、`backend/app/server.py`、`backend/borrow_tasks/scheduler.py`（线程模式参照）、`docs/api/public-market-contract.md`

Acceptance Checks

1. 一次 run 的编排正确：按 §13.5 分页与页数上限拉两个源、去重后幂等入库、run 记录与覆盖范围在同一事务写入；任一页失败仅该栏记 `error` 且该栏不写库、另一栏不受影响；达上限置 `truncated`；错误只含稳定短码。
2. 窗口与补偿：日常窗口为 `max(coverage_end_ms - 3h, now - 30d)` → `now`；空库首次回补 30 天；缺口 > 30 天时截断且覆盖范围标为不连续；启动时超过 1 小时未成功会立即补拉。
3. 节拍与重试（用可注入的时钟离线验证，不得真等）：同一自然小时只成功执行一次 scheduled run；失败后 5 分钟重试、本小时最多 2 次重试；私有通道未启用时调度器不启动；单飞锁下并发 run 只有一个执行、另一个得到忙。
4. 增量口径正确：`baseline_ms` 取倒数第二次成功 scheduled/startup_catchup run 的完成时间；**手动 run 不移动基准且其带入的行计入当前增量**；不足两次成功 scheduled run 时 `delta.complete=false` 且不下发数字；增量按 `asset` / `(income_type, asset)` / 资金费按 `symbol` 分组且从不跨币种相加；`today` 按发生时间与北京时间日界。
5. 两条路由行为符合 §13.1–§13.4：`GET` 零上游 I/O、无 30 天窗口限制、`row_limit_applied` 与全量 `row_count`/`summary` 并存、`coverage.complete` 如实下发；`POST` 的 200/429/409/503 分支齐备且无请求体字段被读取；非 GET 方法不落入 `GET` 路由。
6. 精度与边界红线：ID 一律字符串、金额原样透传、缺失为 `null`、分组含不可解析金额时 `*_total` 为 `null`；代码中无对金额列的 SQL 聚合或 `float()`；快照 schema / 60 秒调度 / cache-refresh / 持仓合并 / 既有端点行为均未改动；`snapshot_service.py` 的改动仅为新增只读访问器；未修改任务 A 的文件与 `__init__.py`。
7. `docs/api/public-market-contract.md` 追加 v0.12 amendment：两条路由、参数校验、`private-ledger/v2` 响应字段、`coverage`/`last_run`/`delta`/`today` 语义、字符串 ID 与 `null` 规则、排序与去重键、页数上限与 `truncated`、增量基准定义、错误码集合；不修改 snapshot JSON schema。
8. 离线运行并把原始输出保存到 Allowed Files 中的 `.pytest.txt`：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_api.py`；全部以桩客户端、注入时钟与临时 SQLite 离线完成，不启动真实服务、不访问网络、不读凭据、不写 `data/`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。在一个 delivery commit 中提交允许的代码、契约、测试、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`。不得自行启动任务 C、Reviewer、Bookkeeper，不得合并、部署或执行任何实盘/网络/凭据/下单操作。
