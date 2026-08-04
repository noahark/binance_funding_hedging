Identity:
- task_id: `backend-ledger-schedule-api-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `11`
- required_skill: `agents/skills/senior-developer.md`

Goal

在任务 A 已交付的 `backend/ledger_flow/domain.py` 与 `store.py` 之上，交付**拉取编排、每小时定时刷新、增量统计与两条 HTTP 路由**（三任务串行中的第二份）。**本任务不改前端**（那是任务 C），也不得修改任务 A 的文件。

权威契约：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §13.1–§13.5（路由与响应）、§15（节拍、窗口、重试、增量定义）、§14（账本硬规则）。

**1. `backend/ledger_flow/service.py`（拉取编排）**：一次 run = 用注入的 `PrivateClient` 按 §13.5 分页拉两个源（左 `size=100`/`current` 递增、上限 40 页；右 `limit=1000`/`page` 递增、上限 10 页，**不传** `incomeType`、**不传** `symbol`），去重后经 store 幂等入库，并写 `flow_refresh_runs` 记录与分源 coverage 元数据。

- **事务模型按 §14 规则 5（v1.2 / F1）**：**run 记录必定落库**（含两栏各自的 status/error/计数/truncated），不因任一栏失败而回滚；**明细按栏各自一个事务**（该栏明细 + 该栏 coverage 元数据同事务）；一栏失败不回滚另一栏已提交的明细。
- **任一页失败 → 该栏本次 run 记 `error`、该栏零明细、该栏 coverage 不推进**；另一栏照常提交。半截账比没有账更危险。
- **达到页数上限（`truncated=true`）时不丢数据、但 coverage 只推进到「已证明连续覆盖」处（v1.2 / F6(b)）**：左栏（`interestHistory` **降序**，缺口在旧端）→ `interest_coverage_end_ms = window_end`，`interest_coverage_start_ms` 不前移，并向 `coverage_gaps` 追加 `{"source":"interest","start_ms":window_start,"end_ms":oldest_fetched_ms}`；右栏（`um/income` **升序**，缺口在新端）→ `income_coverage_end_ms = newest_fetched_ms`（**不是** `window_end`），不记空洞，下一轮自动续拉追平。**注意这是对计划评审 F6(b)「整栏丢弃」建议的具名偏离**，理由写在 §15.2（整栏丢弃会让同一窗口每轮截断每轮丢弃，形成不可自愈的永久停滞）。
- 错误只记稳定短码（`interest_history_failed` / `um_income_failed` / `rate_limited` / `private_channel_disabled`），**不得**携带币安原始报文或 URL。
- **单飞锁**：`scheduled` / `manual` / `backfill` / `startup_catchup` 共用一把进程级锁，`acquire(blocking=False)`，抢不到即返回忙（不排队）。
- **拉取窗口按数据源分别计算（§15.2 / v1.2）**：`window_end(src) = now`，`window_start(src) = max(<src>_coverage_end_ms - 3h, now - 30d)`；空库首次为 `kind="backfill"`、两源均回补 30 天。**两源不共用窗口起点**——共用会让「利息成功、资金费连续失败超过 3 小时」把 coverage 推过资金费从未拉到的时段，制造静默空洞。**3 小时重叠回拉是硬要求**（资金费分批到账也会晚到，原型脚本因此 `Sleep 10s` 再拉一次），靠幂等键去重。缺口 > 30 天时窗口截断为最近 30 天，`<src>_coverage_start_ms` 不变并向 `coverage_gaps` 追加该源缺口，**不得静默留下空洞**。

**2. `backend/ledger_flow/scheduler.py`（节拍）**：守护线程每 **20 秒**醒一次，当「当前分钟 ≥ 1」且「当前自然小时尚无成功的 scheduled run」时执行一次 `kind="scheduled"` run。**不得**用 sleep 到精确时刻——时钟跳变与休眠唤醒会让精确定时失效，而「本小时是否已成功」这个判据天然幂等，也天然覆盖漏跑补偿。启动时若上次成功 run 距今超过 1 小时（或库为空）立即执行一次 `startup_catchup` / `backfill`。失败则 5 分钟后重试、本小时最多重试 2 次（共 3 次尝试），仍失败等下个整点；每次尝试都落一条 run 记录。私有通道未启用或离线模式：**调度器不启动**且响应的 `scheduler_enabled` 为 `false`。线程模式参照既有 `backend/borrow_tasks/scheduler.py`（monotonic 节拍 + `threading.Event` 停止）。

**3. 增量统计（§15.4，最容易做错的一处）**：

```text
成功 run    = kind ∈ {scheduled, startup_catchup, backfill}
              且 interest_status == "ok" 且 income_status == "ok"
baseline_ms = 倒数第二次「成功 run」的 finished_at_ms
本次新增    = 所有 first_seen_at_ms > baseline_ms 的行
```

- **「成功 run」的定义是冻结的（v1.2 / F3）**：`kind` 含 `startup_catchup` 与 `backfill`（否则重启或首次建库后基准要等两个整点才建立）；`manual` **永不**参与基准；两栏都必须 `ok`（`disabled` 与任一栏 `error` 都不算）。**该判定属 service，不属 store**——store 只按 `finished_at_ms` 倒序返回最近 N 条 run 记录。
- 口径是**入库时间**不是发生时间；**手动刷新不移动 `baseline_ms`**，它带进来的行仍落在当前增量窗口内，下一次整点刷新才把基准前移。
- 不足两次「成功 run」→ `delta.complete=false` **且 `delta.baseline_ms=null`**，**不下发可能误导的数字**。
- **`last_run.consecutive_failure_count` 由本服务从 run 表实时计算，不新增数据库列（v1.2 / F2）**：从最近一条已完成 run 起向前数，连续满足「任一栏 `status == "error"`」的条数，遇到第一条两栏都不是 `error` 即停；`disabled` 不计为失败；无 run 记录时为 `0`。
- 增量分组：利息按 `asset`；合约流水按 `(income_type, asset)`；**再加**资金费按 `symbol` 的分组，且 `symbol` 分组内仍按 `asset` 分列，**永远不跨币种相加**。
- `today` 参照按**发生时间**归属、以**北京时间**当日 00:00 为界；`delta` 与 `today` 口径不同，不得混用。

**4. HTTP 路由（`backend/app/server.py`）**：

- `GET /api/private-ledger/flow-log?start=<ms>&end=<ms>` —— **纯读本地库、零上游 I/O**，响应严格按 §13.2（含 `scheduler_enabled`、分源 `coverage.by_source`、`coverage.gaps`、`coverage.pending_tail_ms`）；窗口长度**不再有 30 天上限**；参数非法回 `400 invalid_window`，服务未装配回 `503 flow_log_unavailable`。
- **空态必须按 §13.2 规则 13 的冻结形状返回 200（v1.2 / F5）**：从未有过 run → `last_run: null`；从未成功过 → `coverage` 三值为 `{null, null, false}` 且 `by_source` 两侧为 `null`、`gaps: []`；`delta.complete: false` 且 `baseline_ms: null`；两栏 `rows: []`、`row_count: 0`、`row_limit_applied: false`。**空库不得回 503/500，也不得省略字段**——前端的三态判定（§13.2 规则 14）依赖这些字段存在。
- **`coverage.complete` 的唯一判定按 §13.2 规则 7（v1.2 / F4）**：`window.start_ms >= coverage.start_ms` **且**与窗口相交的 `gaps` 为空，两者全真才是 `true`；聚合 `coverage.start_ms` 取两源较晚者、`end_ms` 取两源较早者；`gaps` 只返回与本次窗口相交的空洞（最多 20 条、按 `start_ms` 升序）。**窗口尾部尚未刷新的部分单独用 `coverage.pending_tail_ms = max(0, window.end_ms - coverage.end_ms)` 表达，绝不计入 `complete`**——查询终点通常是「此刻」而 coverage 只到上次刷新，算进去会让页面永远显示「不完整」，护栏退化成噪音。
- **两条路由的 200 响应都必须带 `Cache-Control: no-store`**〔v1.2 / O5〕，与既有 `/api/public-market/snapshot`、`symbol-snapshot` 一致。
- `POST /api/private-ledger/refresh` —— 触发一次 `kind="manual"` run，响应按 §13.4；忙 `429 flow_log_busy`、私有通道未启用 `409 private_channel_disabled`、未装配 `503`。无请求体字段（body 读完即丢弃），不接受时间窗参数。**manual run 在数据面与定时 run 完全等价（v1.2 / F6(a)）：同样按 §15.2 算窗口、同样写明细、同样推进分源 coverage**；唯一区别是不参与 §15.4 的基准计算。
- 装配沿用 borrow/hedge 的 `_Handler` 类属性注入模式在 `run()` 内完成；`build_server` 签名保持不变。`backend/services/snapshot_service.py` **只允许**新增一个只读访问器暴露既有 `PrivateClient` 实例（复用同一次凭据读取与同一套 `offline / private_channel_enabled` 门禁），不得改动其它任何行为。

**5. 响应硬规则复核**（与任务 A 同源，服务层同样要守）：ID 一律字符串；金额原样透传、缺失为 `null`；**禁止对金额列使用 SQL 聚合**，汇总一律 Python `Decimal`（显式 `localcontext()`，`prec` ≥ 40）且分组内有不可解析金额时 `*_total` 为 `null`；明细每栏最多返回 **500 行**（时间倒序）而 `row_count` 与 `summary` 始终按**全量**计算；`coverage.complete=false` 必须如实下发（诚实性护栏，**空结果绝不能被呈现为"这段时间没有流水"**）。

不改快照 JSON schema、不改 60 秒快照调度、不改 cache-refresh、不改持仓合并、不改任何既有端点行为、不改任务 A 的文件、不动 `backend/ledger_flow/__init__.py`（用子模块路径导入）、不做下单/借还/划转/gate/凭证/部署/实盘操作。

Allowed Files

- `backend/ledger_flow/service.py`（新建）
- `backend/ledger_flow/scheduler.py`（新建）
- `backend/app/server.py`
- `backend/services/snapshot_service.py`（仅新增只读访问器）
- `backend/tests/test_ledger_flow_service.py`（新建）
- `backend/tests/test_ledger_flow_api.py`（新建）
- `docs/api/public-market-contract.md`（追加 v0.12 amendment）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 12:55 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
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
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（**定稿 v1.2**；§13、§14、§15、§17）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`（v1.2 修订说明：F1–F6 改了什么、为什么）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`（任务 A 的交付事实与 `store`/`domain` 公开函数签名）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`
- `backend/ledger_flow/domain.py`、`backend/ledger_flow/store.py`（任务 A 已交付）、`backend/app/server.py`、`backend/borrow_tasks/scheduler.py`（线程模式参照）、`docs/api/public-market-contract.md`

Acceptance Checks

1. **事务模型（§14 规则 5 / F1）**：run 记录必定落库且不被明细失败回滚；明细按栏各自事务（该栏明细 + 该栏 coverage 同事务）；任一页失败仅该栏记 `error`、该栏零明细、该栏 coverage 不推进，另一栏已提交明细不受影响；错误只含稳定短码。
2. **分源窗口与截断语义（§15.2 / F6(b)）**：日常窗口按源各自计算 `max(<src>_coverage_end_ms - 3h, now - 30d)` → `now`；空库首次两源均回补 30 天；缺口 > 30 天时截断并向 `coverage_gaps` 追加该源缺口；`truncated` 时**已拉行照常写入**，左栏 `coverage_end=window_end` 且记空洞、右栏 `coverage_end=newest_fetched_ms` 且不记空洞；启动时超过 1 小时未成功会立即补拉。
3. 节拍与重试（用可注入的时钟离线验证，不得真等）：同一自然小时只成功执行一次 scheduled run；失败后 5 分钟重试、本小时最多 2 次重试；私有通道未启用时调度器不启动且 `scheduler_enabled=false`；单飞锁下并发 run 只有一个执行、另一个得到忙。
4. **增量与失败计数（§15.4 / F3、§13.2 规则 10 / F2）**：`baseline_ms` 取倒数第二次「成功 run」（`kind ∈ {scheduled, startup_catchup, backfill}` 且两栏均 `ok`）的完成时间；**手动 run 不移动基准且其带入的行计入当前增量**；不足两次成功 run 时 `delta.complete=false` 且 `baseline_ms=null`、不下发数字；`consecutive_failure_count` 由 run 表实时计算（不新增列，`disabled` 不计失败）；增量按 `asset` / `(income_type, asset)` / 资金费按 `symbol` 分组且从不跨币种相加；`today` 按发生时间与北京时间日界。
5. 两条路由行为符合 §13.1–§13.4：`GET` 零上游 I/O、无 30 天窗口限制、`row_limit_applied` 与全量 `row_count`/`summary` 并存、两条路由 200 响应均带 `Cache-Control: no-store`；`POST` 的 200/429/409/503 分支齐备且无请求体字段被读取、manual 成功同样推进 coverage；非 GET 方法不落入 `GET` 路由。
6. **`coverage` 与空态（§13.2 规则 7/13 / F4、F5）**：`complete` 仅在「窗口起点不早于覆盖起点」且「与窗口相交的 `gaps` 为空」时为 `true`；**正常运行（窗口终点为此刻、coverage 停在上次刷新）必须仍为 `true`，尾巴由 `pending_tail_ms` 单独表达**；窗口完全落在空洞内时必须为 `false`（离线用构造的空洞数据验证）；聚合 `start_ms` 取两源较晚者、`end_ms` 取两源较早者；空库返回 200 且形状与 §13.2 规则 13 逐字段一致（`last_run: null`、coverage 三值 `null/null/false`、`delta.complete=false`），不得 503 或省略字段。
7. 精度与边界红线：ID 一律字符串、金额原样透传、缺失为 `null`、分组含不可解析金额时 `*_total` 为 `null`；汇总在显式 `localcontext()` 内；代码中无对金额列的 SQL 聚合或 `float()`；快照 schema / 60 秒调度 / cache-refresh / 持仓合并 / 既有端点行为均未改动；`snapshot_service.py` 的改动仅为新增只读访问器；未修改任务 A 的文件与 `__init__.py`。
8. `docs/api/public-market-contract.md` 追加 v0.12 amendment：两条路由、参数校验、`private-ledger/v2` 响应字段（含 `scheduler_enabled`、`coverage.by_source`、`coverage.gaps`）、`coverage`/`last_run`/`delta`/`today` 语义与空态形状、字符串 ID 与 `null` 规则、排序与去重键、页数上限与 `truncated` 的分源处理、增量基准与连续失败计数定义、错误码集合、`Cache-Control: no-store`；不修改 snapshot JSON schema。
9. 离线运行并把原始输出保存到 Allowed Files 中的 `.pytest.txt`：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_api.py`；全部以桩客户端、注入时钟与临时 SQLite 离线完成，不启动真实服务、不访问网络、不读凭据、不写 `data/`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。在一个 delivery commit 中提交允许的代码、契约、测试、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`。不得自行启动任务 C、Reviewer、Bookkeeper，不得合并、部署或执行任何实盘/网络/凭据/下单操作。
