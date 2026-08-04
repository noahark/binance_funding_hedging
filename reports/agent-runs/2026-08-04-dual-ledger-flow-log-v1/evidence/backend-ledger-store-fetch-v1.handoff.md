# Task Handoff: backend-ledger-store-fetch-v1

## Source Report (author-only; immutable after task end)

- task_id: `backend-ledger-store-fetch-v1`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 16:48:29 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`（取自 `status.json.base_sha`，dispatch 禁止改动其它字段；见下「SHA 说明」）
- delivery_sha: `pending`（dispatch 授权在一个 delivery commit 内提交，本交接件创建于该 commit 之前）

### 任务背景与范围

双栏流水日志三任务串行（A→B→C）中的第一份。范围严格限定为取数与本地账本底座：私有客户端的两条只读白名单与两个单页 fetcher、`backend/ledger_flow/domain.py` 纯函数、`backend/ledger_flow/store.py` SQLite 幂等账本。**未接 HTTP 路由、未接定时调度、未接前端**——属任务 B、C。权威契约：设计定稿 v1.2 的 §13.2 / §13.5 / §13.6 / §14 / §15.4。

### 实际修改范围

1. `backend/services/private_client.py` —— `WHITELIST` 精确新增两条只读 GET（`/sapi/v1/margin/interestHistory`→`api.binance.com`、`/papi/v1/um/income`→`papi.binance.com`，13→15）；`PrivateClient` 类末尾新增两个**单页** fetcher。deny-by-default / GET-only / 门禁先于签名 / 审计日志不含密钥签名 / 单一 HMAC 出口全部未动。
2. `backend/ledger_flow/__init__.py`（新建）—— 仅包 docstring。
3. `backend/ledger_flow/domain.py`（新建）—— 纯函数（归一化/去重/排序/Decimal 汇总/窗口校验/增量分组）；零网络、零签名、零 sqlite import。
4. `backend/ledger_flow/store.py`（新建）—— SQLite 幂等账本；四表 + 索引；金额列 `TEXT`，模块内无任何 `SUM`/`AVG`/`TOTAL`/算术 SQL、无 `float()`。
5. `backend/tests/test_private_client.py` —— 白名单条数断言 13→15、base-url 集合断言补两条新路径、新增 4 个 fetcher 离线桩测试。
6. `backend/tests/test_ledger_flow_domain.py`（新建）—— 22 个 domain 纯函数测试。
7. `backend/tests/test_ledger_flow_store.py`（新建）—— 21 个 store 测试。
8. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.pytest.txt`（新建）—— 原始 pytest 输出（84 passed）。
9. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json` —— 仅 `current_task.state` 由 `dispatched` 改为 `reported`，其余字段一字未动。

**未改动**：`backend/app/server.py`、`backend/services/snapshot_service.py`、`backend/domain/*`、`frontend/*`、`PROJECT_STATE.md`、`ACTIVE.json`、快照 schema、60 秒调度、cache-refresh、持仓合并。未新增 HTTP 路由、未启动任何线程（store 仅用 `threading.RLock()` 锁对象，不创建 `Thread`）、未下单/借还/划转/gate/凭据/部署/实盘。

### `backend/ledger_flow/domain.py` —— 公开函数签名（任务 B 的对接契约，AC9）

**模块常量**：
- `INTEREST_TYPE_LABELS: Dict[str, str]` —— `type` 枚举→中文文案（PERIODIC→小时计息…），展示用。
- `INCOME_TYPE_LABELS: Dict[str, str]` —— `incomeType` 枚举→中文文案（FUNDING_FEE→资金费…）。
- `class WindowValidationError(ValueError)` —— 窗口非法时上抛；service 映射为 HTTP 400。

**归一化**（原始 camelCase → snake_case 规范行；ID 一律 str，金额/利率原样字符串，缺失/空串→`None`）：
- `normalize_interest_rows(raw_rows: Any) -> List[dict]`
  入参：`interestHistory` 的 `rows[]`（元素含 `txId`/`interestAccuredTime`/`asset`/`rawAsset`/`principal`/`interest`/`interestRate`/`type`/`isolatedSymbol`）。
  返回：每行 `{"tx_id":str, "accrued_at_ms":int, "asset":str, "raw_asset":str|None, "principal":str|None, "interest":str|None, "interest_rate":str|None, "type":str|None, "isolated_symbol":str|None}`。
  丢弃：缺 `txId`/`interestAccuredTime`/`asset` 或非 dict 的行（无法入库或定位时间）。不抛异常。
- `normalize_income_rows(raw_rows: Any) -> List[dict]`
  入参：`um/income` 数组（元素含 `tranId`/`incomeType`/`time`/`symbol`/`income`/`asset`/`info`/`tradeId`）。
  返回：每行 `{"tran_id":str, "income_type":str, "time_ms":int, "symbol":str|None, "income":str|None, "asset":str|None, "info":str|None, "trade_id":str|None}`。
  丢弃：缺 `tranId`/`incomeType`/`time` 或非 dict 的行。空串 `symbol`/`tradeId`→`None`。

**去重**（首次出现者胜，绝不覆盖）：
- `dedup_interest_rows(rows: List[dict]) -> List[dict]` —— 键 `tx_id`。
- `dedup_income_rows(rows: List[dict]) -> List[dict]` —— 键 `(income_type, tran_id)`。

**排序**（即最终展示序，时间倒序 + 稳定次键）：
- `sort_interest_desc(rows) -> List[dict]` —— `(accrued_at_ms DESC, tx_id DESC)`。
- `sort_income_desc(rows) -> List[dict]` —— `(time_ms DESC, income_type DESC, tran_id DESC)`。

**汇总**（`Decimal` 精确和，显式 `localcontext(prec=40)`，`format(total,"f")`；分组内任一金额不可解析→该组 `*_total=None` 且 `unparsed_row_count>0`；`None` 金额跳过不计为不可解析；同一套函数服务于窗口区间累计、`delta` 增量、`today` 今日累计三处，传不同行子集即可）：
- `summarize_interest_by_asset(rows) -> List[dict]` —— 按 `asset` 分组；元素 `{"asset","interest_total":str|None,"row_count":int,"unparsed_row_count":int}`；按 asset 升序。
- `summarize_income_by_type_asset(rows) -> List[dict]` —— 按 `(income_type, asset)` 分组（永不跨币种）；元素 `{"income_type","asset","income_total":str|None,"row_count":int,"unparsed_row_count":int}`。
- `summarize_funding_by_symbol(rows) -> List[dict]` —— 仅取 `income_type=="FUNDING_FEE"`，按 `(symbol, asset)` 分组；元素 `{"symbol","asset","income_total":str|None,"row_count":int}`（注意：无 `unparsed_row_count`，与 §13.2 `funding_by_symbol` 冻结形状一致；`income_total` 仍于不可解析时为 `None`）；按 `income_total` 降序、`None` 沉底、`symbol` 升序兜底。

**窗口校验**：
- `validate_window(start_ms: int, end_ms: int) -> Tuple[int, int]` —— `start_ms < end_ms` 通过则原样返回；否则抛 `WindowValidationError`。**无 30 天上限**（读本地库）。非 int 也抛。`start`/`end` 缺失或非纯数字的解析由 service 负责（→400）。

### `backend/ledger_flow/store.py` —— 公开函数签名（任务 B 的对接契约，AC9）

- `class LedgerStore`
  - `__init__(self, db_path: str)` —— 连接 `sqlite3.connect(db_path, check_same_thread=False)` + `threading.RLock()`（沿用 `borrow_tasks/store.py`）；建四表 + 索引；写 `schema_version=private-ledger/v2`。`db_path` 注入（生产 `data/ledger-flow.sqlite3`，测试用临时库）。
  - `close(self) -> None`
  - `insert_run(self, run: dict) -> int` —— 写一条**完整** `flow_refresh_runs`，返回自增 `id`。**独立事务**，绝不被明细失败回滚。`run` 键：`kind`、`started_at_ms`、`finished_at_ms`（可 `None`）、`window_start_ms`、`window_end_ms`、`interest_status`、`interest_error`（可空）、`interest_fetched_row_count`、`interest_new_row_count`、`income_status`、`income_error`（可空）、`income_fetched_row_count`、`income_new_row_count`、`truncated`（bool→0/1）。
  - `commit_interest(self, *, rows: List[dict], run_id: int, first_seen_at_ms: int, coverage_start_ms: int|None, coverage_end_ms: int|None, new_gaps: List[dict]|None=None) -> {"fetched_row_count":int,"new_row_count":int}` —— 单一事务：幂等插行（`ON CONFLICT(tx_id) DO NOTHING`，**绝不覆盖** `first_seen_*`）+ upsert 该源 coverage + 追加 `new_gaps`。同批所有行共用同一 `first_seen_at_ms`/`run_id`。中途失败→该源整体回滚。`coverage_*` 传 `None` 表示不更新该端点（service 已算好 min/advance，store 只持久化）。
  - `commit_income(self, *, rows, run_id, first_seen_at_ms, coverage_start_ms, coverage_end_ms, new_gaps=None) -> {"fetched_row_count":int,"new_row_count":int}` —— 同上，键 `(income_type, tran_id)`。
  - `query_interest_rows(self, start_ms: int, end_ms: int, *, limit: int|None=None) -> List[dict]` —— 窗口 `[start,end]` 闭区间明细，`(accrued_at_ms DESC, tx_id DESC)`；`limit=None` 取全量（供 Decimal 汇总），传 `500` 供展示截断。行 dict = 规范 interest 形状 + `first_seen_run_id`/`first_seen_at_ms`。
  - `query_income_rows(self, start_ms, end_ms, *, limit=None) -> List[dict]` —— 同上，`(time_ms DESC, income_type DESC, tran_id DESC)`。
  - `query_interest_since(self, baseline_ms: int) -> List[dict]` —— `first_seen_at_ms > baseline_ms` 的增量行（`delta`）。
  - `query_income_since(self, baseline_ms: int) -> List[dict]` —— 同上。
  - `get_coverage(self) -> {"interest_start_ms":int|None, "interest_end_ms":int|None, "income_start_ms":int|None, "income_end_ms":int|None, "gaps":List[{"source","start_ms","end_ms"}]}` —— 分源 coverage + 全量 gaps（按 `start_ms` 升序）。service 负责按查询窗口相交过滤并截断 20 条。从未成功→对应 `None`；无 gaps→`[]`。
  - `get_meta(self, key: str) -> str | None` —— `ledger_meta` 低层读（如 `schema_version`）。
  - `recent_runs(self, n: int) -> List[dict]` —— 最近 `n` 条**已完成**（`finished_at_ms IS NOT NULL`）run，`finished_at_ms DESC`。**store 不判定「成功 run」语义**——按 `kind`+两栏 status 分类是 service 的事（§13.2 规则 10 / §15.4 / F3）。

`coverage_gaps` 为 `ledger_meta` 中单一 JSON 文本，两源共用、按 `{source,start_ms,end_ms}` 去重、读时按 `start_ms` 升序。`new_gaps` 元素形状：`{"source":"interest"|"income","start_ms":int,"end_ms":int}`。

### `PrivateClient` 新增 fetcher 签名（`backend/services/private_client.py`）

- `fetch_interest_history_page(self, *, start_time: int, end_time: int, current: int, size: int) -> Dict[str, Any]` —— 单页 `GET /sapi/v1/margin/interestHistory`，返回原始 `{"total":int,"rows":[...]}`。**不写 `last_error`、不走 `_cached_get`、失败抛 `PrivateEndpointError`**。分页循环与 `size≤100`/`current≥1`/40 页上限由 service 控制。
- `fetch_um_income_page(self, *, start_time: int, end_time: int, page: int, limit: int) -> List[Any]` —— 单页 `GET /papi/v1/um/income`，返回原始数组。不传 `incomeType`/`symbol`（要全类型）。同上不写 `last_error`/不走缓存/失败抛错。`limit≤1000`/`page≥1`/10 页上限由 service 控制。

### 关键设计判定

- **fetcher 不写 `last_error`**：该字段是快照 `borrow_validation` 的降级依据；被流水失败污染会改既有行情页降级文案。两 fetcher 直接走 `_signed_get`（不经 `_cached_get`，避免刷新拿到 TTL 旧数据），失败让 `PrivateEndpointError` 上抛，由 service 记 `status="error"`。
- **domain 四硬规则**：19 位 `txId`/`tranId`（`>2^53`）一律 `str`；金额/利率原样字符串、不 round/quantize/float/补零、缺失与空串→`None`；汇总在显式 `localcontext(prec=40)` 内 `Decimal` 求和并 `format(total,"f")`；分组内任一不可解析金额→`*_total=None` 且 `unparsed_row_count>0`（绝不用部分和冒充合计），`None` 金额跳过不计为不可解析。去重键/排序键按 §13.2 规则 6。
- **store 事务模型（F1）**：`insert_run` 独立事务、`commit_interest`/`commit_income` 各自一个事务（明细+coverage+gaps 同提交）；任一源失败回滚该源整体、不回滚另一源已提交明细、不回滚 run 记录。已用注入失败点离线验证（见 `test_source_detail_and_coverage_one_transaction` / `test_two_sources_independent` / `test_run_record_not_rolled_back_by_detail_failure`）。
- **金额精度红线**：金额列 `TEXT`；store 无 `SUM`/`AVG`/`TOTAL`/算术 SQL、无 `float()`（静态正则断言）；高精度金额 `0.0000897500000000123456789` 经 store 往返逐字符不变；domain 汇总在 `localcontext(prec=40)`（用 30 位有效数字和证明非进程默认 prec=28）。
- **store 不判成功语义**：`recent_runs` 原样返回 run（含 `error`/`manual`），分类属 service（`test_store_does_not_judge_success_run`）。
- **空库安全**：所有查询在空库返回 `[]`/`None`、不抛异常（`test_empty_db_all_queries_safe`），支撑 §13.2 规则 13 的空态。

### SHA 说明（请 Bookkeeper 关注）

- `status.json.base_sha = dc4cc6d9...`，dispatch 禁止改动除 `current_task.state` 外的任何字段，故本交接件 `base_sha` 沿用 `dc4cc6d`。
- 本 delivery commit 的实际父提交（创建本交接件前的 `HEAD`）为 `a8dee7887e8e8db557d87f6fa609c1f8fd5a3da1`。`dc4cc6d..a8dee78` 区间含有**前端 fake 原型**提交（触及 `frontend/index.html`、`frontend/self-check.js` 及若干 `reports/`），与本任务 Allowed Files **零重叠**、非本交付。因此评审区间 `dc4cc6d..delivery_sha` 会包含这些无关提交；评审应以本任务的 Allowed Files（`backend/services/private_client.py`、`backend/ledger_flow/*`、`backend/tests/test_ledger_flow_*.py`、`backend/tests/test_private_client.py`）为实际受审范围。是否将 `base_sha` 前移至 `a8dee78` 以收紧评审区间，属 Bookkeeper 写权限，本任务不擅改。

### 命令与结果（离线，不启动服务/不访问网络/不读凭据/不写 `data/`）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md` → `PASS(absent)`（2026-08-04 16:48 CST；与 Bookkeeper 预检一致）。
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`。
- `git rev-parse HEAD`（本 commit 前）→ `a8dee7887e8e8db557d87f6fa609c1f8fd5a3da1`。
- 离线 pytest（AC10 精确命令）→ **84 passed in 0.30s**，原始输出已存 `evidence/backend-ledger-store-fetch-v1.pytest.txt`：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py backend/tests/test_private_client.py`
- 全程用桩 `urlopen` 与临时 SQLite（`tmp_path`）；未写 `data/ledger-flow.sqlite3`、未生成 `backend/ledger_flow/__pycache__`（`PYTHONDONTWRITEBYTECODE=1`）。

### 仓库内证据路径

- 设计定稿 v1.2：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13.2/§13.5/§13.6/§14/§15.4）
- 代码：`backend/services/private_client.py`、`backend/ledger_flow/__init__.py`、`backend/ledger_flow/domain.py`、`backend/ledger_flow/store.py`
- 测试：`backend/tests/test_ledger_flow_domain.py`、`backend/tests/test_ledger_flow_store.py`、`backend/tests/test_private_client.py`
- 测试原始输出：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.pytest.txt`
- 实盘证据（实现输入）：`reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`、`reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md`；`backend/ledger_flow/domain.py`；`backend/ledger_flow/store.py`；`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13.2/§13.5/§14/§15.2/§15.4）；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- 执行：Bookkeeper 核验本交接件与原始 pytest 输出、封存 delivery commit、写实际 `delivery_sha`；随后由 Human 决定是否路由任务 B（`backend-ledger-schedule-api-v1`，service+scheduler+两条路由）。
- 关卡：Bookkeeper 核验 `reported`→`verified`；本任务为 `HIGH_RISK`（资金/账务语义），交付后须 review-1 + review-2（跨 provider）；B 依赖本交接件列明的 domain/store 签名。
- 不能假设的事实：store 不判「成功 run」语义（分类属 B 的 service）；coverage advance/min 由 service 算、store 只持久化；fetcher 为单页、分页循环属 B；`base_sha` 与本 commit 实际父提交 `a8dee78` 不一致（见「SHA 说明」），评审范围以 Allowed Files 为准。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: backend-ledger-store-fetch-v1
执行结果: completed（完成）
结果摘要: 任务A交付流水日志取数+本地账本底座：private_client 加2条只读白名单(13→15)与2个单页fetcher(不写last_error/不走缓存/失败上抛)；domain纯函数落实ID字符串/金额透传/Decimal精确和/unparseable→null+count/去重排序；store SQLite四表幂等账本按F1分源事务+查询面+空库安全。离线pytest 84全过。未接路由/调度/前端。
产物: [backend/services/private_client.py, backend/ledger_flow/__init__.py, backend/ledger_flow/domain.py, backend/ledger_flow/store.py, backend/tests/test_ledger_flow_domain.py, backend/tests/test_ledger_flow_store.py, backend/tests/test_private_client.py, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.pytest.txt, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json]
检查结果: [AC1白名单13→15+base-url正确+GET-only/门禁先签名/审计不含密钥不变: pass, AC2两单页fetcher不写last_error/不走TTL缓存/失败抛PrivateEndpointError(桩urlopen验证): pass, AC3 domain纯函数四硬规则(ID字符串/金额透传/缺失空串→null/Decimal localcontext prec40/unparseable→null+count/去重键/倒序排序键)且无网络签名sqlite import: pass, AC4 store幂等不覆盖first_seen+同批共享first_seen_at_ms+四表与索引按§14: pass, AC5 F1事务模型(run独立不回滚/单源明细+coverage同事务整体回滚/两源互不影响,注入失败点验证): pass, AC6查询面(窗口明细可限/全量汇总行/first_seen>baseline增量/分源coverage+gaps读写/run记录/finished_at倒序最近N)+store不判成功语义+空库返回空或None不抛: pass, AC7金额列TEXT+无SUM/AVG/TOTAL/float()+domain localcontext(30位有效数字和证明非默认prec): pass, AC8边界未越(无新路由/无线程/快照调度cache-refresh持仓合并不变/__init__仅docstring)+AC9 domain/store公开签名全列明+AC10离线pytest 84passed原始输出已存: pass]
阻塞项: [none；base_sha(status.json=dc4cc6d)与本commit实际父提交a8dee78不一致,因dispatch禁改status其它字段,评审范围以本任务Allowed Files为准,是否前移base_sha属Bookkeeper写权限]
本地北京时间: 2026-08-04 16:48:29 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-store-fetch-v1.handoff.md；backend/ledger_flow/domain.py；backend/ledger_flow/store.py；docs/planning/2026-08-04-dual-ledger-flow-log-design.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json；执行：核验并封存本任务（写实际 delivery_sha），按 HIGH_RISK 起草 review-1；关卡：review-1 + review-2（跨 provider）通过且 Human 决策后方可路由任务 B（backend-ledger-schedule-api-v1）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）
