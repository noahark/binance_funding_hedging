Identity:
- task_id: `backend-ledger-store-fetch-v1`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `6`
- required_skill: `agents/skills/senior-developer.md`

Goal

交付双栏流水日志的**取数与本地账本底座**（三任务串行中的第一份），范围严格限定为：私有客户端的两条只读白名单与两个单页 fetcher、`backend/ledger_flow/domain.py` 的纯函数、`backend/ledger_flow/store.py` 的 SQLite 幂等账本。**本任务不接 HTTP 路由、不接定时调度、不接前端**——那是任务 B 与 C。

权威契约：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §13.2（行与汇总字段）、§13.5（上游分页）、§13.6（白名单）、§14（数据库 schema 与硬规则）、§15.4（增量定义）。

**1. `PrivateClient`（`backend/services/private_client.py`）**：白名单精确新增两条——`("GET", "/sapi/v1/margin/interestHistory") -> https://api.binance.com`、`("GET", "/papi/v1/um/income") -> https://papi.binance.com`；新增两个**单页** fetcher（分页循环不进客户端，属服务层）。新 fetcher **不得**写 `self.last_error`（那是快照 `borrow_validation` 的降级依据，被流水失败污染会改变行情页既有降级文案），失败以既有 `PrivateEndpointError` 上抛。不使用 `_cached_get`（拉取由调用方按窗口控制，TTL 缓存会让刷新拿到旧数据）。

**2. `backend/ledger_flow/domain.py`（纯函数，零 I/O、零网络与签名 import）**：原始行归一化、去重、排序、汇总、窗口校验、增量分组。四条最易错的硬规则必须逐条落实：

- **所有 ID 一律字符串**。`txId` / `tranId` 是 19 位长整型（`2328408217636413776 > 2^53`），以 JSON number 下发会被浏览器 `JSON.parse` 静默改值，而它们正是幂等键；入库同样存 `TEXT`。
- **金额与利率原样透传**币安返回的字符串：不 round、不 quantize、不转 float、不补零；缺失一律 `null`，绝不造 `0` 或 `""`（空串 `symbol` / `trade_id` 归一化为 `null`）。
- **汇总用 `Decimal` 精确求和**并输出 `format(total, 'f')`，且求和须在显式 `decimal.localcontext()`（`prec` ≥ 40）内完成、不依赖进程默认精度〔v1.2 / O4〕；**只要分组内有一行金额无法解析，该分组 `*_total` 必须为 `null` 且 `unparsed_row_count > 0`**——不得用部分和冒充完整合计。此规则同样适用于增量与今日累计分组。
- **排序键**：利息 `(accrued_at_ms, tx_id)` 倒序；合约流水 `(time_ms, income_type, tran_id)` 倒序。去重键：利息 `tx_id`；合约流水 `(income_type, tran_id)`。

**3. `backend/ledger_flow/store.py`（SQLite 账本）**：按 §14 建四张表（`interest_rows`、`um_income_rows`、`flow_refresh_runs`、`ledger_meta`）与索引；库路径由构造参数注入（生产为 `data/ledger-flow.sqlite3`，测试用临时库），连接模式沿用既有 store（`sqlite3.connect(path, check_same_thread=False)` + `threading.RLock`）。硬规则：

- **金额列一律 `TEXT`**；**任何查询都不得对金额列使用 `SUM`/`AVG`/算术运算**——SQLite 会把 TEXT 隐式转浮点、静默丢精度。汇总一律取行到 Python 用 `Decimal` 算。
- **幂等写入且绝不覆盖已存在的行**：`ON CONFLICT DO NOTHING`。`first_seen_run_id` / `first_seen_at_ms` 必须保持首次入库的值，否则重叠窗口回拉会把旧行重复计入增量。
- 一次写入批次的所有行共用同一个 `first_seen_at_ms`（服务端在事务内取一次时钟）。
- **事务模型按 §14 规则 5（v1.2 / F1 重写，此前的「明细 + run 记录 + meta 同一事务、失败整体回滚」与「一栏失败不影响另一栏」自相矛盾）**：store 必须能让调用方 (a) **单独写 run 记录且该写入不被任何明细失败回滚**；(b) 把**一个数据源**的明细 + 该源的 coverage 元数据（必要时含 `coverage_gaps`）作为**一个事务**提交；(c) 一源的事务失败不回滚另一源已提交的明细。不得把两源明细绑进同一个事务。
- **`ledger_meta` 的键集按 §14 更新为分源记账**〔v1.2 / F4〕：`interest_coverage_start_ms` / `interest_coverage_end_ms` / `income_coverage_start_ms` / `income_coverage_end_ms` / `coverage_gaps`（JSON 文本，元素 `{"source","start_ms","end_ms"}`）/ `schema_version`。**表结构不变**——`consecutive_failure_count` 不加列（§13.2 规则 10 由 B 实时算），分源 coverage 与空洞都存在既有键值表里。
- **必须提供给任务 B 的查询面（§14 规则 7）**：窗口内明细（时间倒序、可限条数）与窗口内全量行（供 `Decimal` 汇总）、按 `first_seen_at_ms > baseline` 的增量行、分源 coverage 与 `coverage_gaps` 的读写、run 记录写入、**按 `finished_at_ms` 倒序的最近 N 条 run 记录**（同时服务于 §15.4 的基准查找与 §13.2 规则 10 的连续失败计数）。**store 只提供数据，不判定「成功 run」语义**——「`kind ∈ {scheduled, startup_catchup, backfill}` 且两栏均 `ok`」的判定属 B（§15.4）〔v1.2 / F3；此前本 packet 写的「最近 N 次成功 scheduled run」与设计不一致，已废止〕。
- **空库安全**：所有查询在空库/无 run 记录时必须返回空集合或 `None`，不得抛异常——`GET flow-log` 的空态（§13.2 规则 13）依赖它。
- 永久保留，不实现任何自动清理。

不改快照 schema、不改 60 秒调度、不改 cache-refresh、不改持仓合并、不新增 HTTP 路由、不启动任何线程、不做下单/借还/划转/gate/凭证/部署/实盘操作。`backend/ledger_flow/__init__.py` **只放包 docstring**（任务 B、C 都不得再改它，一律用子模块路径导入）。

Allowed Files

- `backend/services/private_client.py`
- `backend/ledger_flow/__init__.py`（新建，仅 docstring）
- `backend/ledger_flow/domain.py`（新建）
- `backend/ledger_flow/store.py`（新建）
- `backend/tests/test_ledger_flow_domain.py`（新建）
- `backend/tests/test_ledger_flow_store.py`（新建）
- `backend/tests/test_private_client.py`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 12:55 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.pytest.txt`（测试原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（**定稿 v1.2**；§12–§18；本任务的冻结契约为 §13.2、§13.5、§13.6、§14、§15.2、§15.4）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`（v1.2 修订说明：F1–F6 改了什么、为什么）
- `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`
- `reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`
- `backend/services/private_client.py`、`backend/tests/test_private_client.py`、`backend/borrow_tasks/store.py`（连接与锁模式参照）

Acceptance Checks

1. 白名单精确新增两条只读 GET 且 base URL 正确；deny-by-default、GET-only、门禁先于签名构造、审计日志不含密钥/签名/完整 query 全部不变；`backend/tests/test_private_client.py` 的白名单条数断言由 13 更新为 15，base-url 集合断言同步包含两条新路径。
2. 两个新 fetcher 为单页读取、不写 `PrivateClient.last_error`、不走 TTL 缓存；失败以 `PrivateEndpointError` 上抛（以桩 `urlopen` 离线验证）。
3. `domain.py` 为纯函数模块（无网络/签名/sqlite import），覆盖：ID 一律字符串、金额原样透传、缺失为 `null`（含空串归一化）、`Decimal` 精确汇总、**含不可解析金额时该分组 `*_total` 为 `null` 且 `unparsed_row_count > 0`**、规定的去重键与倒序排序键。
4. `store.py` 幂等可验证：同一行重复写入不产生第二条、**不覆盖** `first_seen_run_id` / `first_seen_at_ms`；同批次行共用同一 `first_seen_at_ms`；四张表与索引按 §14 建立（表结构与 v1.1 相同）。
5. **事务模型可验证（§14 规则 5 / F1）**：run 记录的写入不被明细写入失败回滚；单源明细 + 该源 coverage 元数据同事务提交，中途失败该源整体回滚且**另一源已提交的明细不受影响**；以注入的失败点离线验证。
6. **查询面与语义边界（§14 规则 7 / F3）**：提供窗口明细、全量汇总行、`first_seen_at_ms > baseline` 增量行、分源 coverage 与 `coverage_gaps` 读写、run 记录写入、按 `finished_at_ms` 倒序的最近 N 条 run 记录；**store 不判定「成功 run」**；空库/无 run 时全部返回空集合或 `None` 而不抛异常。
7. 金额精度红线：金额列为 `TEXT`，代码中不存在对金额列的 `SUM`/`AVG`/算术 SQL，也无 `float()` 参与金额路径（以测试或静态断言证明其一）；`domain.py` 的汇总在显式 `localcontext()` 内完成。
8. 边界未被越过：未新增 HTTP 路由、未启动线程、未改快照 schema / 60 秒调度 / cache-refresh / 持仓合并 / 任何既有端点行为；`backend/ledger_flow/__init__.py` 仅含 docstring。
9. **交接件列明 `domain.py` 与 `store.py` 的全部公开函数签名**（名称、参数、返回结构、异常）〔v1.2 / O3〕——任务 B 只靠本交接件对接，签名不写清会导致 B 猜错接口。
10. 离线运行并把原始输出保存到 Allowed Files 中的 `.pytest.txt`：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py backend/tests/test_private_client.py`；全部以桩客户端与临时 SQLite 离线完成，不启动服务、不访问网络、不读凭据、不写 `data/`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。在一个 delivery commit 中提交允许的代码、测试、测试输出、status 与 handoff；handoff 的 `delivery_sha` 写 `pending`。不得自行启动任务 B / C、Reviewer、Bookkeeper，不得合并、部署或执行任何实盘/网络/凭据/下单操作。
