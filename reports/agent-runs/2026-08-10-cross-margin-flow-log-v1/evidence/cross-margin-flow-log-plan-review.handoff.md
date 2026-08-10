# Task Handoff: cross-margin-flow-log-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `cross-margin-flow-log-plan-review`
- role: Reviewer（独立高风险计划评审，只读）
- target model: opus5（provider: anthropic）
- required_skill: `agents/skills/software-architect.md`
- stage_id: `2026-08-10-cross-margin-flow-log-v1`
- created_at: 2026-08-10 16:53:49 CST
- base_sha: `92256cb0849653a2daf41b894f7bd6c7860ac73c`
- delivery_sha: `none`（计划评审无交付提交）
- status_revision 核对: `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/status.json` revision=1、
  phase=`plan_review`、current_task.id 与 dispatch 一致、base_sha 与 `git rev-parse` 一致。

### 评审结论

**REWORK。**

被审对象是 `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`（尚未实现的计划）。
数据源选择（capital-flow 全仓、拒绝 `papi .../marginAccountFlow`）、幂等键立场（禁止单靠 `tranId`）、
非目标边界（不接 `asset/transfer`、不做逐仓、不改互转 POST）**判定正确，予以保留**。

不通过的原因是：计划把「与现有 dual-ledger 共存」写成了一句方向性描述，而没有冻结共存所必需的条款。
现有 `ledger_flow` 的 run 记录、coverage 聚合、delta 基线三者是**同一套两源模型**，第三源无论并入还是
独立，都会触碰它们；其中 coverage 聚合还被对冲任务的持仓周期净盈亏统计消费。按当前计划直接实现，
最可能的结果不是"少做了点什么"，而是**既有已交付功能回归**（P0-1）与**静默漏账**（P0-3/P0-4）。
以下发现全部为 `in-range`（针对本次待实现范围），无 `pre-existing-*` 项，均有当前代码路径或 recon 原文
锚点，不援引 `AGENTS.md` §1 Scenario Admission 的假设通道。

---

### 只读评审范围与实际执行的检查

只读读取：`AGENTS.md`、本 stage dispatch/status/change-plan、`reports/agent-runs/ACTIVE.json`、
`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer）、
`agents/skills/software-architect.md`、recon 正文与 sanitized 形状、
`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（行数核对）、
`backend/ledger_flow/{domain,store,service,scheduler}.py`、`backend/services/private_client.py`、
`docs/api/public-market-contract.md` §Dual-Ledger Flow-Log Amendment、`frontend/index.html`、
`frontend/self-check.js`。为核对「additive 是否破坏既有消费方」额外只读了
`backend/app/server.py` 的 flow-log 路由与 `coverage_for_window` 消费点（dispatch Inputs 第 17 项指向的
三栏扩展，其后端消费点必须一并核对，否则 Acceptance Check 4 无法作答）。

执行的只读命令与结果（未改动仓库任何既有文件）：

```text
$ test ! -e reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md
PREFLIGHT_OK: handoff absent

$ git status --short
 M frontend/index.html
 M frontend/self-check.js

$ git diff --stat
 frontend/index.html    | 308 +++++++++++++++++++++++++++++++++++++++++++++++--
 frontend/self-check.js |  41 ++++++-
 2 files changed, 334 insertions(+), 15 deletions(-)

$ git rev-parse HEAD
d44c08f184412a051d38768b8eaa11c7dbbb823f

$ git show HEAD:frontend/index.html | grep -c "flow-log-capital-col"
0

$ python3 -c "... sqlite3 data/ledger-flow.sqlite3 ..."
interest_rows 279 / um_income_rows 196 / flow_refresh_runs 130
ledger_meta: schema_version=private-ledger/v2,
  interest_coverage_start_ms=1783253538807, interest_coverage_end_ms=1786348871793,
  income_coverage_start_ms=1783253538807,  income_coverage_end_ms=1786348871793
```

---

### 发现（全部 in-range；按严重度）

#### P0-1 coverage 聚合被第三源污染 → 对冲任务「持仓周期净盈亏」立刻回归为「暂无」

- 证据：`backend/ledger_flow/service.py:415-442`（`_build_coverage`：`start_ms` 取两源较晚者、`end_ms`
  取两源较早者，`complete` 要求 `window_start >= cov_start` 且窗口内无 gap）；
  `backend/ledger_flow/service.py:383-389`（`coverage_for_window` 公开包装）；
  `backend/app/server.py:1401-1408`（`cov.get("complete")` 为假 → 该对冲行 `accrued_funding` /
  `borrow_interest` / `borrow_interest_usdt` / `net_pnl` 全部置 `None` 并标 `stats_incomplete`）。
- 实际效果：capital-flow 首次接入时其 coverage_start 最早只能是接入日往前 7～30 天。一旦第三源进入
  aggregate，**所有开仓时间早于该点的对冲任务行的持仓周期资金费/利息/净盈亏会在上线当刻全部变成
  「暂无」**。现网库 income/interest 覆盖起点是 `1783253538807`，第三源不可能追平这个起点。
- 计划 §4.2.1 只写了「利息与 `um/income` 既有语义、表结构、幂等键与默认筛选不变」，没有识别这条**跨功能**
  耦合，因此该条不足以挡住这次回归。
- 计划须冻结（可直接抄入 §4.2）：capital-flow 的覆盖仅写入 `coverage.by_source.capital_flow` 这一新键，
  **不参与** aggregate `start_ms` / `end_ms` / `complete` / `pending_tail_ms`，`coverage_for_window` 的返回
  语义与消费方保持不变；验收加一条可执行断言：capital 源从未成功（或持续失败）时，
  `coverage_for_window(既有窗口)` 的 `complete` 与接入前逐位相同。

#### P0-2 run 记录 / `last_run` / delta 基线三处耦合未决，且现网库有 130 行 run 记录

- 证据：`backend/ledger_flow/store.py:74-90`（`flow_refresh_runs` 列固定，`interest_status` /
  `income_status` 为 `NOT NULL`）；`store.py:41-97` 全部为 `CREATE TABLE IF NOT EXISTS`（**对已存在的表不会
  补列**）；实测现网 `data/ledger-flow.sqlite3` 已有 `flow_refresh_runs` 130 行；
  `service.py:306-311`（`_is_success_run` 要求 kind ∈ `{scheduled,startup_catchup,backfill}` **且两源均 ok**）；
  `service.py:470-489`（`_compute_delta` 的 `baseline_ms` = 第二新 success run）；
  `service.py:444-459`（`_format_last_run` 取 `recent_runs(1)`，**不按 kind 过滤**）。
- 两条路都各有必须写死的后果，计划两条都没选：
  - (a) **并入同一 run 记录**：必须写显式 `ALTER TABLE flow_refresh_runs ADD COLUMN`（约 4 列）迁移，
    否则现网库启动即报 `no such column`；并且必须冻结 `_is_success_run` 是否纳入 capital 状态——纳入则
    capital 源不稳时**利息与合约两栏的「本次新增」一起停摆**（baseline 不再前移），不纳入则 run 显示成功
    而 capital 实际失败。
  - (b) **独立 run kind 写同一张表**：`interest_status` / `income_status` 需要 NOT NULL 占位值，且
    `_format_last_run` 取最近一条 run 不分 kind，UI「上次运行」会周期性显示成一条利息/合约源为
    `disabled` 的运行，看起来像既有两源坏了。
- 推荐（最小且不动既有语义）：capital-flow 用**独立 run kind**，`_SUCCESS_KINDS` 与 delta **不纳入**
  capital，`_format_last_run` 按 kind 过滤后再取最近一条（或 capital 的运行状态单独放进第三块，不进
  `last_run`）。无论选哪条，计划必须写出迁移语句或「零迁移」的具体理由，并给一条**针对已有 130 行 run 的
  现网库**升级后可跑的验证断言。

#### P0-3 ≤7 天切片的 coverage 推进规则未定义 → 中间切片失败会被静默吞掉

- 证据：`service.py:181-195`（`_compute_window` 只产出**单个**窗口 `[cov_end-3h, now]`，30 天 floor）；
  `service.py:258-300`（成功即把 `coverage_end` 推到 `window_end`，truncated 时才记 gap）；
  recon §3.1（单次 `startTime`/`endTime` 最大间隔 **7 天**，历史约 90 天）。
- 实际效果：首次 backfill 30 天需 ≥5 个切片。沿用「一次 run = 一个 window + 一个 truncated 位」的模型时，
  第 3 片失败而其余片成功，coverage 仍会推进到 `window_end`，**账本自称覆盖了实际没拉到的区间**，
  且此后永不回补（下一次 run 从 `cov_end-3h` 起算）。
- 计划须冻结：切片按时间**升序**逐片提交；`capital_flow_coverage_end_ms` 只推进到**最后一个连续成功切片**
  的末端；任一片失败即停止推进并记 gap；写死单次 run 的切片数上限、首次接入的窗口长度（30 天 / 7 天 /
  90 天三选一）与由此产生的权重预算（recon §3.7：100 IP/次 × 切片数 × 每片页数）。验收检查 §5.5 目前只
  要求「不单次越界请求」，须升级为「中间切片失败时 coverage 不越过失败点」。

#### P0-4 `fromId` 翻页协议未冻结，而 recon 明确未证明返回序

- 证据：recon §3.6 原文「精确排序未做双向严格证明；设计时应用 `timestamp`/`id` 本地排序，**不依赖隐式
  序**」；recon §3.1「分页 `fromId`（`id > fromId`）、`limit` 默认 500、最大 1000」。
- 实际效果：若按常见写法「取本页 `max(id)` 作下一 `fromId`，返回行数 < limit 即停」，而上游该切片返回为
  **降序**，第二页请求 `id > max_id` 会立即返回空并提前终止，**静默漏掉该切片内 id 更小的全部行**；
  恰好返回 `limit` 行的切片最危险。计划 §4.1.2 只写了「单页 fetcher + service 增量窗口」，未定义终止条件。
- 计划须冻结：单切片终止条件（`len(page) < limit` **且** `fromId` 严格递增，二者同时成立才终止）、
  每切片翻页上限、达上限即 `truncated` 并记 gap；配一条 mock 断言：上游按降序或乱序返回时不得提前终止、
  不得漏行。保守替代方案（也可接受）：单切片只发一次 `limit=1000`，行数达上限即判 `truncated` 记 gap，
  完全不做 `fromId` 翻页。

#### P1-1 工作树已有 308 行未提交的第三栏实现，计划未纳入

- 证据：`git status --short` 显示 `frontend/index.html`、`frontend/self-check.js` 为 modified；
  `git diff --stat` 为 308 / 41 行；`git show HEAD:frontend/index.html | grep -c "flow-log-capital-col"`
  返回 `0`（HEAD `d44c08f` 与 base_sha `92256cb` 均不含）。工作树内容：
  `frontend/index.html:1490-1505`（第三栏 DOM + 「预览」徽标 + 五个筛选框）、
  `frontend/index.html:6923-6941`（`FLOW_LOG_CAPITAL_TYPE_ZH` 16 项）、
  `frontend/index.html:6944-6955`（`FLOW_LOG_CAPITAL_FAKE_ROWS` 假数据）、
  `frontend/index.html:6985-7008`（方向文案「入全仓/出全仓」与 TRANSFER/BORROW/REPAY/TRADE/OTHER 五桶）；
  未提交的 `frontend/self-check.js` 已断言这批 DOM id 与「全仓杠杆流水」标题，并**另含一处与本 stage 无关
  的 crypto stub 修复**（`newTransferRequestId` 用例）。
- 实际效果：实现者若从 base_sha 出发重写前端会覆盖这批工作（`AGENTS.md` §3 第 3 条）；若直接一起提交，
  未经计划的改动会混入 `base_sha..delivery_sha`，污染 review-1/review-2 的受审范围。
- 计划须冻结：这批未提交改动的处置（由 Bookkeeper 先单独提交为基线，还是纳入本 stage 交付范围并在
  dispatch 的 Allowed Files 中写明），以及实现必须**沿用**既有 DOM id
  （`flow-log-capital-col` / `-status` / `-summary` / `-body` / `-filters` / `-filter-transfer|borrow|repay|trade|other`）
  与既有五桶筛选；接真实数据时删除「预览」徽标与 `FLOW_LOG_CAPITAL_FAKE_ROWS`。

#### P1-2 additive 的真实约束在前端，不在后端

- 判定：后端新增顶层 `capital_flow` 块与 `coverage.by_source.capital_flow` 键本身是 additive，**不破坏**
  旧客户端。
- 但证据：`frontend/self-check.js:595-660` 的基准 payload 与 `:6186` / `:6220` / `:6244` / `:6272` 四处
  coverage fixture 都只含 `interest` / `um_income` / `by_source:{interest,income}`。前端若强制读取
  `payload.capital_flow.rows`，这些既有用例会在渲染时抛错。
- 计划须冻结：缺失 `capital_flow` 块 → 中栏渲染为**空态**（不是错误态）；`schema_version` 保持
  `private-ledger/v2` 不 bump（`store.py:107` 的 `_SCHEMA_VERSION_VALUE` 与 `service.py:403` 是同一字符串，
  bump 需同步 DB meta、响应、`docs/api/public-market-contract.md` 三处）。

#### P2-1 默认筛选与既有实现不一致

计划 §3 表把 `TRADING_COMMISSION` 写为「（实现可选）默认开」，而工作树 `frontend/index.html:6996-7001`
已把它归入 `TRADE` 桶且**默认关**。须二选一冻结并删掉「实现可选」措辞，否则实现与 self-check 断言会打架。

#### P2-2 互转可见性的口径需要一行文案（非扩域）

capital-flow 站在**全仓钱包**记账（recon §3.5）。不经全仓的划转（例如 MAIN 与 UM/CM 直转）不会出现在
中栏。计划应冻结一行 UI/文档口径，避免把中栏当成「所有互转的全集」。

---

### 对 dispatch 六条 Acceptance Checks 的逐条判断

1. **capital-flow 是否足以支撑中栏与互转可见性；是否必须同 stage 接 `asset/transfer`** —— 足够；
   **不必须**。证据：recon §3.5 四笔互转 `tranId`（`399260348988` / `399260281458` / `399216264416` /
   `399072495589`）全部在 capital-flow `type=TRANSFER` 中命中，方向由 `amount` 符号给出；本地
   `data/asset-transfer.sqlite3` 可按 `tranId` 左连补发起端与 `client_request_id`。计划把
   `asset/transfer` 列为非目标是对的，仅需补 P2-2 的口径文案。→ `pass`
2. **幂等键（禁止单靠 tranId）与多 type 同行是否被覆盖** —— 已覆盖且正确。计划 §4.1.3 要求 `id` 唯一，
   §5.3 要求同 `tranId` 多 type 行全部保留；recon §3.3 证明 `id` 是自增流水 ID 兼翻页键，工作树假数据
   `frontend/index.html:6947-6949`（同一 `tran_id=399258471825` 三行不同 `id`）与之一致；计划已把逐仓
   列为非目标，`id` 唯一性只需在「不传 symbol 的全仓查询面」成立。→ `pass`
3. **7 天切片 + 小时调度 + 权重 100 能否与现有 ledger scheduler 合并** —— **不能简单合并**；须独立 run
   kind，且 coverage 聚合、delta 基线、`last_run` 三处必须显式隔离，切片推进规则必须写死。计划未覆盖。
   → `fail`（P0-1 / P0-2 / P0-3）
4. **flow-log API additive 形状是否破坏旧客户端/self-check** —— 后端 additive 不破坏；真实约束在前端对
   缺失块的降级与 `schema_version` 不 bump，计划未冻结。→ `fail`（P1-2）
5. **新假设场景是否满足 §1 Scenario Admission** —— 本次未使用假设场景阻塞：全部发现均锚定当前代码路径
   （`service.py` / `store.py` / `server.py` 行号）、recon 原文或可复现的 git/sqlite 命令输出。→ `pass`
6. **唯一 handoff / Source Report / Human Brief / marker / delivery_sha=none / 评审结论字段** ——
   本文件为本任务唯一写入，preflight 已记录路径此前不存在。→ `pass`

---

### 未完成事项

- 未验证 capital-flow 在**真实翻页**下的返回序（Reviewer 只读，且发起实盘签名请求超出本任务范围）。
  这正是 P0-4 要求把翻页协议写成 fail-closed 形态、而不是依赖实测序的原因。
- 未评估首次 backfill 的实际权重占用（需要实盘计数）。计划应在实现前把切片数上限写死，由实现轮的
  mock 测试与首次运行日志确认。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md`
  2. `reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md`
  3. `backend/ledger_flow/service.py`
  4. `backend/ledger_flow/store.py`
  5. `backend/app/server.py`
  6. `frontend/self-check.js`
- 执行：Bookkeeper 核验本 handoff 并把 `REWORK` 结论落进 `status.json`（计划评审的 verdict 返回 Planner，
  按 `AGENTS.md` §8「计划评审」不触碰 `rework_count`）；随后由 Planner 按 P0-1..P2-2 改写
  `00-change-plan.md`，其中 P0-1/P0-2/P0-3/P0-4 必须逐条落成计划正文里的冻结条款与可执行验收断言；
  P1-1 需要 Human 先决定工作树 308 行未提交前端改动的处置。
- 关卡：改写后的计划需再过一次独立跨 provider 只读计划评审（`AGENTS.md` §8 HIGH_RISK 计划评审门），
  通过后才进入实现 dispatch。
- 不能假设的事实：
  - 不能假设 `CREATE TABLE IF NOT EXISTS` 会给现网已存在的 `flow_refresh_runs`（130 行）补列。
  - 不能假设 coverage 聚合只影响流水日志页面——它经 `coverage_for_window` 决定对冲任务行的净盈亏是否显示。
  - 不能假设 capital-flow 的翻页返回按 `id` 升序：recon §3.6 明确未证明。
  - 不能假设前端第三栏要从零写：工作树已有未提交的假数据版本，DOM id 与筛选桶已被未提交 self-check 断言。
  - 不能假设 `delta` /「本次新增」与第三源无关：`_is_success_run` 一旦纳入 capital 状态即影响既有两栏。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: cross-margin-flow-log-plan-review
执行结果: completed（完成）
结果摘要: 只读计划评审完成，结论 REWORK。数据源选择（capital-flow 全仓、弃用 marginAccountFlow）、幂等键用 id、非目标边界均判定正确并保留。不通过原因：计划没冻结与现有双账本共存的条款——第三源若并入 coverage 聚合会让对冲任务的持仓周期净盈亏当场变「暂无」；run 表已有 130 行且不会自动补列；7 天切片与 fromId 翻页缺终止规则会静默漏账；工作树另有 308 行未提交的第三栏前端未纳入计划。
产物: [reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md]
检查结果: [capital-flow 足以支撑中栏与互转可见性、无需同 stage 接 asset/transfer=pass；幂等键禁用单 tranId、改用 id 且多 type 同行保留=pass；7 天切片与小时调度能否并入现有 scheduler=fail（须独立 run kind，coverage/delta/last_run 三处必须隔离）；flow-log additive 形状=fail（后端 additive 安全，但前端须对缺失块降级、schema_version 不得 bump）；切片与翻页的漏账防护=fail（coverage 只能推进到最后一个连续成功切片；fromId 终止条件须 fail-closed）；工作树 308 行未提交第三栏前端未纳入计划=fail；新假设场景证据门=pass（全部发现锚定代码行号/recon 原文/可复现命令）；唯一 handoff 与评审结论字段合规=pass]
阻塞项: [P1-1 需 Human 先决定工作树未提交的 308 行前端改动如何处置（先单独提交为基线，还是纳入本 stage 交付范围）]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md
修复要求: reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md
本地北京时间: 2026-08-10 16:53:49 CST
下一步模型: codex（本阶段 Bookkeeper，由 Human 启动其终端）
下一步任务: 读取：reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md；reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/00-change-plan.md；backend/ledger_flow/service.py；backend/ledger_flow/store.py；backend/app/server.py；frontend/self-check.js；执行：核验本 handoff 并把 REWORK 结论写入 status.json（计划评审 verdict 返回 Planner，不递增 rework_count），再准备 Planner 改写计划的 dispatch；关卡：Human 先裁定工作树 308 行未提交前端改动的处置，改写后的计划须再过一次独立跨 provider 只读计划评审才能进入实现。
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- bookkeeper: grok（本轮由 Human 指定代行 codex 槽位）
- verified_at: 2026-08-10 17:44:34 CST
- status_revision_at_verify: 1（plan_review / current_task=cross-margin-flow-log-plan-review / state=dispatched）
- source_payload_sha256: `392741bf4688320998fe0c60c0c9b7dddd1cefd38458d1eb24d2790df15afa64`（marker 前全部字节）
- 核验命令与结果：
  - `test -f reports/agent-runs/2026-08-10-cross-margin-flow-log-v1/evidence/cross-margin-flow-log-plan-review.handoff.md` → 存在
  - handoff 含 `评审结论: REWORK`、P0-1..P0-4 / P1-1..P1-2 / P2-1..P2-2、delivery_sha=none
  - 与 Human 转达的整改回执一致：数据源选择保留；共存四条冻结；P1-1 已由 Human 裁定「提交」
- 裁定：`执行结果 completed` + `评审结论 REWORK` 形式合规 → **核验通过（计划 REWORK，不递增 rework_count）**
- Human 后续决策（2026-08-10，经转达已落盘）：
  1. 历史仅 1 天 + 小时增量；2. 不做分页；3. 未提交前端拆两提交进基线；
  4. P0-1/P0-2 采用「独立表 + ledger_meta，不碰 flow_refresh_runs / aggregate」；
  5. 采纳「改写为净收缩后不必二次完整计划评审」，由 Bookkeeper 在实现 dispatch 核对 10 项冻结表。
- 已执行：crypto 自检桩单独提交 `d702843`；三栏 UI 基线 `a11a873`；改写 `00-change-plan.md`；准备实现 dispatch。
- 后续：`status.json` revision 递增，`base_sha`=`a11a873…`，phase→implement，派工实现者。

## Errata (append-only)

- 2026-08-10 Bookkeeper：Required Reading 中「改写后须再过一次完整计划评审」已被 Human 采纳的替代路径取代（净收缩 + Bookkeeper 10 项核对进实现 dispatch）。源区块不改写，以本 Errata 为准。
