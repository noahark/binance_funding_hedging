# Task Handoff: backend-ledger-schedule-api-v1

## Source Report (author-only; immutable after task end)

- task_id: `backend-ledger-schedule-api-v1`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 20:06:14 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`（取自 `status.json.base_sha`；见下「SHA 说明」）
- delivery_sha: `pending`（dispatch 授权在一个 delivery commit 内提交，本交接件创建于该 commit 之前）

### 任务背景与范围

双栏流水日志三任务串行（A→B→C）中的第二份，在任务 A 已交付的 `domain.py` / `store.py` 之上交付**拉取编排、每小时整点定时刷新、增量统计与两条 HTTP 路由**。**本任务不改前端（任务 C），也不改任务 A 的任何文件。** 权威契约：设计定稿 v1.2 的 §13.1–§13.5、§14、§15。

### 实际修改范围

1. `backend/ledger_flow/service.py`（新建）—— 拉取编排 + §13.2 响应装配 + 增量统计 + POST refresh。
2. `backend/ledger_flow/scheduler.py`（新建）—— 整点节拍守护线程（参照 `borrow_tasks/scheduler.py`）。
3. `backend/app/server.py` —— `_Handler` 加 `ledger_flow_service` 类属性；`do_GET` 加 `/api/private-ledger/flow-log`、`do_POST` 加 `/api/private-ledger/refresh`；新增 `_handle_flow_log`/`_handle_flow_refresh`/`_send_ledger`；`run()` 内构造 LedgerStore/Service/Scheduler、`build_server` 签名不变、可用时启动调度器、`finally` 停调度器并关库。
4. `backend/services/snapshot_service.py` —— **仅新增一个只读 `@property private_client`** 暴露既有 `self._private`（复用同一套 offline/private_channel_enabled 门禁，无第二次凭据读取、无新签名面）；其余行为一字未动。
5. `docs/api/public-market-contract.md` —— 追加 v0.12 amendment（两条路由/参数/响应字段/空态/ID·null/排序去重/截断分源/增量基准与连续失败计数/错误码/`Cache-Control: no-store`；不改 snapshot schema）。
6. `backend/tests/test_ledger_flow_service.py`（新建）—— 20 个 service 测试。
7. `backend/tests/test_ledger_flow_api.py`（新建）—— 11 个 HTTP 线上测试。
8. `reports/.../evidence/backend-ledger-schedule-api-v1.pytest.txt`（新建）—— 原始 pytest 输出（31 passed）。
9. `reports/.../status.json` —— 仅 `current_task.state` 由 `dispatched` 改为 `reported`，其余字段一字未动。

**未改动**：任务 A 的 `domain.py`/`store.py`/`__init__.py`、`frontend/*`、`PROJECT_STATE.md`、`ACTIVE.json`、snapshot JSON schema、60 秒快照调度、cache-refresh、持仓合并、任何既有端点。未下单/借还/划转/gate/凭据/部署/实盘。

### `backend/ledger_flow/service.py` —— 公开签名

- `class LedgerFlowService`
  - `__init__(self, store: LedgerStore, private_client, *, now_ms: Callable[[], int])` —— 注入 store、共享 `PrivateClient`、毫秒时钟（测试驱动不睡眠）。
  - `is_usable(self) -> bool` —— 私有只读通道是否可拉（`private_client.enabled`）。
  - `mark_scheduler_enabled(self)` / `property scheduler_enabled` —— 调度器启动后置真；`scheduler_enabled` 进响应顶层。
  - `run_once(self, kind: str) -> dict | None` —— 一次 run（单飞 `acquire(blocking=False)`，忙返回 `None`）。返回 `{"run": <run_record>, "interest_new": int, "income_new": int}`；`new` 取自 `commit_*` 返回值（准确）。`kind ∈ {scheduled, manual, backfill, startup_catchup}`。
  - `get_flow_log(self, start_ms: int, end_ms: int) -> dict` —— **纯读本地库、零上游 I/O**；窗口非法抛 `domain.WindowValidationError`（handler→400）。返回 §13.2 完整响应。
  - `trigger_refresh(self) -> tuple[int, dict]` —— `(409, private_channel_disabled)` / `(429, flow_log_busy)` / `(200, §13.4 manual 摘要)`。
  - 调度器辅助（`scheduler.py` 调用）：`had_successful_run_since(since_ms)`、`count_attempts_since(since_ms)`、`last_attempt_finished_since(since_ms)`、`last_successful_finished()`、`coverage_exists()`。

- 关键判定：
  - **分源窗口**（§15.2）：`window_end=now`，`window_start=max(<src>_cov_end-3h, now-30d)`；空库首次 30 天 backfill；缺口>30d 截断并向 `coverage_gaps` 记该源空洞。
  - **截断 F6(b)**：左栏降序→`coverage_end=window_end`、`start` 不前移、记空洞 `[window_start, oldest]`；右栏升序→`coverage_end=newest`、不记空洞（下轮自愈）。
  - **成功 run 分类（F3，service 权威）**：`kind∈{scheduled,startup_catchup,backfill}` 且两栏 `ok`；`manual` 永不参与基准。
  - **`baseline_ms`**=倒数第二次成功 run 的 `finished_at_ms`；不足两次→`complete=false`+`baseline_ms=null` 不下发数字。
  - **`consecutive_failure_count`**：从最近 run 起连续数「任一栏 error」、遇首个非 error 即停；`disabled` 不计；无 run→0（不落列）。
  - **`coverage.complete`**（F4）：`window.start>=cov.start` 且与窗口相交的 `gaps` 为空；尾巴用 `pending_tail_ms=max(0,window.end-cov.end)` 单独表达，不计入 `complete`。聚合 `start`=两源较晚者、`end`=两源较早者。
  - **`today`**：北京时间当日 00:00 为界、按发生时间归属（`_beijing_day_start_ms`）。
  - 错误只记稳定短码（`interest_history_failed`/`um_income_failed`/`rate_limited`/`private_channel_disabled`），不含币安报文/URL。

### `backend/ledger_flow/scheduler.py` —— 公开签名

- `class LedgerScheduler`
  - `__init__(self, service: LedgerFlowService, *, now_ms, poll_seconds=20.0)`。
  - `start()` / `stop()` —— daemon 线程 + `threading.Event` 停止（参照 `borrow_tasks/scheduler.py`）。
  - `decide(self, now: int) -> tuple[bool, str|None]` —— **纯判定**：分钟≥1 且本自然小时无成功 run 且尝试<3 且距上次≥5min → `(True,"scheduled")`；否则 `(False,None)`。
  - 启动时 `_startup_catchup()`：上次成功 run 距今>1h（或库空）→ 立即 `backfill`（库空）/`startup_catchup`（有覆盖）。

### `PrivateClient` 复用与装配

- `SnapshotService.private_client`（新 `@property`）→ 既有 `self._private`（同一套 offline/private_channel_enabled 门禁）。
- `run()`：`LedgerStore(borrow_db_path.parent/"ledger-flow.sqlite3")` + `LedgerFlowService(store, service.private_client, now_ms=_now_ms)` + `LedgerScheduler`；`build_server` 签名不变；`_Handler.ledger_flow_service` 注入；`is_usable()` 时启动调度器并 `mark_scheduler_enabled()`；`finally` 停调度器、关库。

### store API 约束说明（请评审关注）

任务 A 的 `store.py` 提供 `insert_run(run)->id`（写完整记录）与 `commit_*(run_id,…)`（需 run_id），**无 `update_run`**。因 `commit_*` 的 `first_seen_run_id` 必须指向已存在的 run 记录，`run_once` 的写入顺序只能是：**先 `insert_run`（用 fetch 结果填 status/fetched，`new_row_count` 走 `insert_run` 的默认 0）拿 run_id → 再 `commit_interest`/`commit_income`**。因此 `flow_refresh_runs` 表里存储的 `*_new_row_count` 恒为 0。**这不影响任何对外语义**：`last_run` 不含 `new_row_count`；`delta` 用 `first_seen_at_ms>baseline`；`POST refresh` 的 `*_new_row_count` 取自 `commit_*` 返回值（准确）；`consecutive_failure_count` 只看 status。若评审要求存储准确的 `new_row_count`，须在任务 A 的 store 增 `update_run`（属 A 的文件，本任务不越界改）。事务隔离（F1）仍完全成立：`insert_run` 独立事务、两源 `commit_*` 各自独立事务，互不回滚（见 service 测试 `test_partial_failure_interest_error_income_ok` 与 store 测试）。

### 命令与结果（离线，不启动真实服务/不访问网络/不读凭据/不写 `data/`）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md` → `PASS(absent)`（2026-08-04 20:06 CST；与 Bookkeeper 预检一致）。
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`。
- `git rev-parse HEAD`（本 commit 前）→ `2bc2582b5e20dd0b123e93b2dad9125176d49a42`（含任务 A 封存提交与前端 fake 原型提交，与本任务 Allowed Files 零重叠）。
- 离线 pytest（AC9 精确命令）→ **31 passed in 6.05s**，原始输出已存 `evidence/backend-ledger-schedule-api-v1.pytest.txt`：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_api.py`
- 回归核对（A 的 domain/store/private + snapshot + borrow_api + hedge_api）→ **194 passed**，无回归。
- 全程桩 client、注入时钟与临时 SQLite（`tmp_path`）；HTTP 测试用进程内 `ThreadingHTTPServer`(loopback:0)+`http.client`，无真实网络；未写 `data/ledger-flow.sqlite3`。

### SHA 说明（与任务 A 同）

`status.json.base_sha = dc4cc6d`，dispatch 禁止改动除 `current_task.state` 外字段，故本交接件 `base_sha` 沿用 `dc4cc6d`。本 delivery commit 实际父提交为 `2bc2582`。`dc4cc6d..delivery_sha` 评审区间含任务 A 提交与前端 fake 原型提交（触及 `backend/ledger_flow/{__init__,domain,store}.py`、`backend/services/private_client.py`、`backend/tests/test_private_client.py`、`backend/tests/test_ledger_flow_{domain,store}.py`、`frontend/*` 及若干 `reports/`）；本任务实际受审范围为本文「实际修改范围」所列 Allowed Files。是否前移 `base_sha` 属 Bookkeeper 写权限。

### 仓库内证据路径

- 设计定稿 v1.2：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13.1–§13.5/§14/§15）
- 任务 A 交接（domain/store 签名）：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`
- 代码：`backend/ledger_flow/service.py`、`backend/ledger_flow/scheduler.py`、`backend/app/server.py`、`backend/services/snapshot_service.py`
- 契约：`docs/api/public-market-contract.md`（v0.12 amendment）
- 测试：`backend/tests/test_ledger_flow_service.py`、`backend/tests/test_ledger_flow_api.py`
- 测试原始输出：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.pytest.txt`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`；`docs/api/public-market-contract.md`（v0.12 amendment）；`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13.2/§13.7）；`backend/ledger_flow/service.py`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- 执行：Bookkeeper 核验本交接件与原始 pytest 输出、封存 delivery commit、写实际 `delivery_sha`；随后由 Human 决定是否路由任务 C（前端接真实数据）并做前后端联调。
- 关卡：本阶段为 `HIGH_RISK`，按 Human 决定「先联调通过再统一评审 A+B+C」（review-1 暂缓）；联调通过后统一走 review-1+review-2（跨 provider）。
- 不能假设的事实：GET flow-log 形状以本交接件与契约 v0.12 为准（含 `scheduler_enabled`/分源 `coverage.by_source`/`coverage.gaps`/`pending_tail_ms`/空态）；store 的 run 记录 `new_row_count` 恒 0（见 store API 约束说明）；fetcher 为单页、分页属 service；`coverage` advance/min 由 service 算、store 只持久化；`base_sha` 与本 commit 实际父提交 `2bc2582` 不一致，评审范围以 Allowed Files 为准。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: backend-ledger-schedule-api-v1
执行结果: completed（完成）
结果摘要: 任务B交付拉取编排+整点调度+两条路由+增量统计：service.py 落实分源窗口/分页/截断F6(b)/单飞/分源事务/F3成功run分类与baseline/F2连续失败计数/F4 coverage诚实性护栏/§13.2响应含空态；scheduler.py 整点20s节拍+启动catchup+5min重试预算；server.py 接GET flow-log(纯读零上游)与POST refresh，200带no-store，build_server签名不变；snapshot_service 仅加只读访问器复用同一PrivateClient。离线pytest 31全过+回归194全过，未接前端/未改任务A。
产物: [backend/ledger_flow/service.py, backend/ledger_flow/scheduler.py, backend/app/server.py, backend/services/snapshot_service.py, docs/api/public-market-contract.md, backend/tests/test_ledger_flow_service.py, backend/tests/test_ledger_flow_api.py, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.pytest.txt, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json]
检查结果: [AC1 F1事务模型(run独立落库不被明细失败回滚/单源明细+coverage同事务/任一页失败仅该栏error零明细coverage不推进另一栏不受影响/错误只稳定短码): pass, AC2 分源窗口与截断(日常max(cov_end-3h,now-30d)/空库30d backfill/缺口>30d记空洞/截断左栏coverage_end=window_end记空洞右栏coverage_end=newest不记/启动超1h补拉): pass, AC3 节拍与重试(注入时钟离线验证:同小时只成功一次/失败5min重试本小时≤2次重试/通道未启用不启动且scheduler_enabled=false/单飞并发一忙): pass, AC4 增量与失败计数(baseline=倒数第二次成功run含startup_catchup/backfill两栏ok/manual不移基准且行计入增量/不足两次complete=false不下发数字/consecutive_failure_count实时算disabled不计失败/分组不跨币种/today北京日界发生时间): pass, AC5 两路由(GET零上游无30天限/row_limit_applied与全量row_count·summary并存/两路由200带no-store/POST 200-429-409-503齐备不读body字段/manual推进coverage/非GET不落入GET): pass, AC6 coverage与空态(complete仅起点覆盖+无相交gaps/正常运行仍为true尾巴用pending_tail_ms/窗口落空洞内为false/聚合start较晚end较早/空库200且逐字段同§13.2规则13不503不省字段): pass, AC7 精度与边界(ID字符串/金额透传缺失null/不可解析分组null/localcontext/无SQL聚合无float/快照调度cache-refresh持仓合并既有端点未改/snapshot仅加只读访问器/未改任务A与__init__): pass, AC8 契约v0.12追加两路由+参数+响应字段+空态+ID·null+排序去重+截断分源+基准与失败计数+错误码+no-store且不改snapshot schema: pass, AC9 离线pytest 31passed原始输出已存+回归A+snapshot+borrow+hedge 194passed无回归: pass]
阻塞项: [none；store API 无update_run故flow_refresh_runs的new_row_count恒0(不影响任何对外语义,见交接件store API约束说明);base_sha(dc4cc6d)与本commit实际父提交2bc2582不一致,评审范围以Allowed Files为准,是否前移base_sha属Bookkeeper写权限]
本地北京时间: 2026-08-04 20:06:14 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md；docs/api/public-market-contract.md；docs/planning/2026-08-04-dual-ledger-flow-log-design.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json；执行：核验并封存本任务（写实际 delivery_sha），随后按 Human 决定路由任务 C（前端接真实数据）并做前后端联调；关卡：联调通过后按 HIGH_RISK 统一走 review-1+review-2（跨 provider，A+B+C 一起）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）
