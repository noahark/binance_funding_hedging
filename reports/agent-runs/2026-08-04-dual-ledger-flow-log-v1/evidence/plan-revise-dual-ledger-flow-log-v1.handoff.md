# Task Handoff: plan-revise-dual-ledger-flow-log-v1

## Source Report (author-only; immutable after task end)

- task_id: `plan-revise-dual-ledger-flow-log-v1`
- role: `Planner`（计划修订；不写业务代码）
- target model: `opus5`（provider `anthropic`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 13:25:57 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`
- delivery_sha: `none`（文档修订，未提交 commit；产物留在工作树交 Bookkeeper 封存）

### 任务背景与范围

计划评审 `plan-review-dual-ledger-flow-log-v1`（deepseek，只读）对设计定稿 v1.1 与三份实现 dispatch 给出 `REWORK`，F1–F6 全部 `in-range` 并附可执行修改要求，另有 O1–O8 观察。本任务按 `plan-revise` dispatch 落实 F1–F6 与观察项，产出**设计定稿 v1.2**，并对齐 A、B 两份实现 dispatch。**未写业务代码、未启动任何模型终端、未执行网络/凭据/实盘操作、未改动 C（frontend）packet。** 计划评审 `REWORK` 按 `AGENTS.md` §8 不触 `rework_count`（仍为 0）。

### 实际修改范围

1. `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` —— 定稿 v1.1 → **v1.2**。改动集中在 §13.1/§13.2/§13.5/§13.7/§14/§15.2/§15.3/§15.4/§16/§17.3/§17.4，顶部定稿标记与 §10 修订记录各更新/追加一行。**草案 §1–§10 原文仍一字未改**（`git diff` 的删除行全部落在 §11 之后，唯一例外是我自己在 v1.0 插入的定稿标记块）。修订点在正文用 `〔v1.2 / Fx｜Ox〕` 就地标注，便于重评审定位。
2. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`（A）—— 对齐 F1/F2/F3/F4/F6 与 O3/O4；验收项由 7 条扩为 10 条。
3. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`（B）—— 对齐 F1–F6 与 O5；验收项由 8 条扩为 9 条。
4. 新建本交接件。
5. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json` —— 仅 `current_task.state` 由 `dispatched` 改为 `reported`，其余字段一字未动。

**未改动**：C packet、`backend/`、`frontend/`、`PROJECT_STATE.md`、`ACTIVE.json`、其它任何文件。

### F1–F6 逐条落实

| # | 修订结论 | 落点 |
|---|---|---|
| **F1** 事务粒度矛盾 | 采纳评审推荐。**run 记录必定落库**（含两栏 status/error/计数/truncated），不因任一栏失败而回滚；**明细按栏各自一个事务**（该栏明细 + 该栏 coverage 元数据同事务）；失败栏零明细、coverage 不推进；一栏事务失败不回滚另一栏已提交明细；**禁止把两源明细绑进同一事务**。 | 设计 §14 规则 5（重写）、§13.5 第 4 条；A 的 store 硬规则 + 验收 5；B 的 service 第 1 条 + 验收 1 |
| **F2** `consecutive_failure_count` 无数据源 | 采纳评审推荐，**不新增列**：由 service 从 run 表实时计数——从最近一条已完成 run 向前数连续「任一栏 `error`」的条数，遇到第一条两栏都不是 `error` 即停；`disabled` 不计失败；无记录为 `0`。 | 设计 §13.2 规则 10、§15.3；A（store 只提供「按 `finished_at_ms` 倒序最近 N 条 run」）；B 的增量统计第 4 条 + 验收 4 |
| **F3** 基准口径不一致（含 O7） | 冻结「成功 run」定义：`kind ∈ {scheduled, startup_catchup, backfill}` **且两栏均 `ok`**；`manual` 永不参与基准；`delta.complete` 与 `baseline_ms=null` 同步同一判定。A packet 里与设计冲突的「最近 N 次成功 scheduled run」措辞已废止，改为「store 只按 `finished_at_ms` 倒序返回最近 N 条 run 记录，**不判定成功语义**」。 | 设计 §15.4（重写）、§13.2 规则 11；A 的 store 查询面 + 验收 6；B 的增量统计 + 验收 4 |
| **F4** coverage 内部空洞无法表达 | 采纳评审意图并扩展数据模型：coverage 改为**按数据源分别记账**，响应新增 `coverage.by_source`（两源各自 `[start,end]`）与 `coverage.gaps`（与查询窗口相交的空洞，最多 20 条）；聚合 `start` 取两源较晚者、`end` 取两源较早者；`complete` 判定重写为「窗口起点不早于覆盖起点 **且** 与窗口相交的 `gaps` 为空」。**窗口完全落在空洞内必然得到 `false`**，堵死「空结果被读成『没有流水』」。**表结构不变**——分源 coverage 与空洞都存在既有 `ledger_meta` 键值表。 | 设计 §13.2 规则 7、§15.2、§13.7 新增「覆盖不完整文案」行；B 的路由第 3 条 + 验收 6；A 的 `ledger_meta` 键集 |
| **F5** 空库空态形状未冻结 | 采纳评审推荐并补一个判别字段：`last_run: null`、`coverage` 三值 `{null, null, false}`（`by_source` 两侧 `null`、`gaps: []`）、`delta.complete: false` 且 `baseline_ms: null`、两栏 `rows: []`/`row_count: 0`；**新增顶层 `scheduler_enabled`**，作为「没数据是因为没开通道」与「没数据是因为真没流水」的唯一确定性依据；并给出**前端三态判定表**（5 行、按顺序取第一个命中）。空库必须回 200，不得 503 或省略字段。 | 设计 §13.2 规则 13/14（新增）、§15.3；B 的路由第 2 条 + 验收 3/6 |
| **F6** manual/truncated 语义未定义 | (a) 采纳：**manual run 在数据面与定时 run 完全等价**——同样算窗口、写明细、**推进分源 coverage**（`kind` 如实记 `manual`），唯一区别是不参与基准。(b) **具名偏离评审推荐**，见下节。 | 设计 §15.3、§13.4、§15.2；B 的 service + 路由 + 验收 2/5 |

### 两处对评审建议的具名偏离（重评审须确认）

1. **F6(b) 截断处理**。评审推荐「`truncated=true` 时该栏整栏回滚、不提交明细」。本修订采纳其**意图**（coverage 绝不越过未拉到的数据），但**不采纳整栏丢弃**：同一窗口每轮都会截断、每轮都丢弃，数据永远无法落库，形成**不可自愈的永久停滞**。改为：**提交已拉行**，coverage 只推进到「已证明连续覆盖」处，并按两个接口**相反的返回顺序**分别处理——左栏 `interestHistory` **降序**（缺口在旧端）→ `interest_coverage_end = window_end`、`start` 不前移并记空洞；右栏 `um/income` **升序**（缺口在新端）→ `income_coverage_end = newest_fetched_ms`（**不是** `window_end`）、不记空洞，下一轮自动续拉追平。
2. **`coverage.complete` 不含窗口尾部**（修订过程中发现的新问题，非评审发现）。评审 F4 的推荐判定含「`window.end_ms <= coverage.end_ms`」。照此实现会**永远**判为 `false`：查询窗口终点通常是「此刻」，而 coverage 只到上一次刷新，正常运行时永远差 0–60 分钟。护栏一旦恒亮就等于没有护栏。改为：`complete` 只判「起点覆盖 + 无相交空洞」，窗口尾部未刷新的部分单独用 **`coverage.pending_tail_ms = max(0, window.end_ms - coverage.end_ms)`** 表达，由前端常驻显示「最近 X 分钟的流水尚未刷新」——调度器停摆时这个数字自然变大，正好是需要被看见的信号。

### 观察项处理

| 观察 | 处理 |
|---|---|
| O1 >3h 晚到且发生时间早于 `coverage_end-3h` 的记录永久丢失且无检测 | 写入 §17.4「尽力而为的捕获边界」，明确本页不是审计级完备账本 |
| O2 「零重叠」措辞 vs 三份 packet 都含 `status.json` | §16 增加语义例外说明：共享的只有 `status.json`，每份只改自己那条 `current_task.state`，且三任务串行 |
| O3 store/domain 公开签名未冻结 | 写入 §14 规则 7 + **A 的验收 9**：A 的交接件必须列明全部公开函数签名（名称/参数/返回结构/异常），B 只靠该交接件对接 |
| O4 汇总显式 `localcontext()` | §13.2 规则 3、§14 规则 6、A 的 domain 硬规则与验收 7、B 的响应硬规则：`prec ≥ 40` |
| O5 `Cache-Control: no-store` | §13.1 + B 的路由要求与验收 5（两条路由的 200 响应都带） |
| O6 时钟回拨导致 `first_seen ≤ baseline` 漏计 | §17.4 记一句（数据仍在库，仅该轮增量偏小；NTP 下罕见，本轮不补偿） |
| O7 §15.4 措辞与 baseline 定义不一致 | 并入 F3 一并统一 |
| O8 左栏 40 页余量 2.3 倍 | §17.4 记一句（借款资产增长后可能触顶，护栏会如实显示，届时需调高上限或分段回补） |

### 未完成事项 / 交给 Bookkeeper 处理

1. **C（frontend）packet 需要一次 pre-dispatch packet correction**（本任务按纪律未动它）。F4 让 C 的 Goal 第 1 条出现措辞缺口：它只写了「`coverage.complete=false` 时追加『本地数据只到 <日期>』」，而该文案只适用于**起点截断**；**区间空洞**与 **`pending_tail_ms`** 各需一句。建议改为「按设计 §13.7『覆盖不完整文案』分情形渲染」，并把 §13.2 规则 13/14 的空态与三态判定表列入其验收。详见设计 §13.7 末尾的待办框。**此项不改变 C 的文件边界与交付范围。**
2. **三份实现 packet 的 `status_revision` 目前是 `3`**，而当前 status revision 已到 `4`。Bookkeeper 在实际路由每一份时须再次写入当时的实际 revision，否则目标终端会因 revision 不符而停机。
3. **重出计划评审**：修订后须按 §17.3 重新评审（或经 Human 认可缩小至修订增量）。§17.3 已新增三个必须确认的问题：F6(b) 偏离是否成立、分源 coverage 是否真的消除了单栏静默空洞且不会过度告警、空态与三态判定表加上 `scheduler_enabled` 后是否无歧义。评审模型须与 `anthropic`、`zhipu_glm`、`moonshot` 全部跨 provider（推荐 `deepseek`，即第一轮评审者，可复用其上下文；若 Human 要求换人则 `codex`/`grok`）。
4. **本任务未提交 commit**，五个产物留在工作树（三个已跟踪文件被修改、一个新建交接件、一个 status.json）。

### 命令与结果（离线，只读）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md` → PASS(absent)（Planner 自检，2026-08-04 13:25:57 CST；Bookkeeper 已于 13:10 CST 预检同一结果）。
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`。
- `git rev-parse HEAD` → `fcf333bc28c72d99711fa2556b736c0988c0e90f`（评审封存提交，晚于 `base_sha`）。
- `git diff --numstat docs/planning/2026-08-04-dual-ledger-flow-log-design.md` → `113 25`；`git diff -U0 … | grep '^@@'` 的最小起始行为 `-4`（我自己的定稿标记块）与 `-277,0`（修订记录纯追加），**§11 之前的草案散文无任何删除**。
- `date '+%Y-%m-%d %H:%M:%S CST'` → `2026-08-04 13:25:57 CST`。
- 未运行服务、未访问网络、未读取凭据、未提交 commit、未触碰 `backend/`、`frontend/`、C packet。

### 仓库内证据路径

- 修订后的设计：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（定稿 v1.2）
- 修订后的 A packet：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`
- 修订后的 B packet：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`
- 受理的评审：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`
- 只读证据：`reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`、`reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`；`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- 执行：Bookkeeper 核验并封存本次修订，按 §17.3（含新增的三个确认问题）起草重评审 packet，路由前为每份实现 packet 写入当时实际 `status_revision`，并在路由 C 之前按设计 §13.7 末尾待办框对 C packet 做一次 pre-dispatch correction。
- 关卡：重出的计划评审返回 `ACCEPT` 后，方可路由 `backend-ledger-store-fetch-v1`；三个实现任务串行 A → B → C，每份交付后按 `HIGH_RISK` 走 review-1 + review-2。
- 不能假设的事实：F6(b) 与 `coverage.complete` 尾部处理是**对评审推荐的具名偏离**，重评审未确认前不得当作已获认可；三份 packet 的 `status_revision` 仍是 `3`，与当前 revision `4` 不符，未更新不可路由；C packet 尚未按 F4 补齐覆盖文案；本任务未提交 commit，产物仅在工作树；`rework_count` 仍为 0（计划评审 REWORK 不计数）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: plan-revise-dual-ledger-flow-log-v1
执行结果: completed（完成）
结果摘要: 按计划评审 REWORK 的 F1–F6 修订设计为定稿 v1.2 并对齐 A/B 两份 packet：事务改为「run 记录必落库+明细按栏各自事务」；连续失败数改由 run 表实时算不加列；「成功 run」定义冻结含 startup_catchup/backfill 且两栏均 ok；coverage 改为分源记账+空洞列表，堵死空洞内查询被读成「没有流水」；冻结空库空态与前端三态判定表；manual 同样推进 coverage。O1-O8 一并落档。含两处具名偏离，待重评审确认。
产物: [docs/planning/2026-08-04-dual-ledger-flow-log-design.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json]
检查结果: [AC1 F1-F6 逐条修订且设计与 A/B packet 无自相矛盾: pass, AC2 对齐点仍单一（设计为权威）且 C packet 未被动过: pass, AC3 空态契约与三态判定表已写入 §13.2 规则 13/14: pass, AC4 修订记录追加 v1.2 行且草案 §1-§10 原文未改写（diff 删除行全在 §11 之后）: pass, AC5 观察项 O1/O2/O3/O4/O5/O6/O8 已落档、O7 并入 F3: pass, AC6 交接件与回执齐备、delivery_sha=none、status 仅改本任务状态: pass, AC7 未写业务代码、未启动终端、未执行实盘/网络/凭据操作: pass, 两处对评审推荐的偏离已在设计与 packet 中具名并列入 §17.3 重评审必答: pass]
阻塞项: [none；但三份实现 packet 的 status_revision 仍为 3（当前 revision 已 4），路由前须更新；C packet 需在路由前补 F4 覆盖文案]
本地北京时间: 2026-08-04 13:25:57 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md；docs/planning/2026-08-04-dual-ledger-flow-log-design.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json；执行：核验并封存本次修订，按 §17.3（含新增三个确认问题）起草重评审 packet，路由前补齐各 packet 的实际 status_revision 并对 C packet 做一次 pre-dispatch correction；关卡：重评审 ACCEPT 后方可路由 backend-ledger-store-fetch-v1
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 13:30:00 CST
- source_sha256（marker 前字节）：`5f5b65166ea24620061501782acc60effa93a1ef6d8e59b18f00c7148553e2e3`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：4（`current_task.id = plan-revise-dual-ledger-flow-log-v1`、`state = reported`，与交接件声明一致；除该状态外 status.json 字段未动；预检 `test ! -e` 于 2026-08-04 13:10 CST 通过，Planner 13:25:57 CST 复验一致）
- task_id / role / stage_id 与 `status.json` 一致：`plan-revise-dual-ledger-flow-log-v1` / `Planner` / `2026-08-04-dual-ledger-flow-log-v1`
- base_sha 核验：`git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在且等于 `status.json.base_sha`；HEAD `fcf333b` 晚于 base_sha，符合 SHA Discipline
- delivery_sha：`none`（文档修订，未提交；git status 为设计文档 + A/B packet + status.json 修改与新建交接件，均留在工作树交封存）
- 结论：**通过（verified）**。F1–F6 逐条修订且附落点；两处对评审推荐的具名偏离（F6(b) 截断「提交已拉行+coverage 只推进到已证明连续处+左栏记空洞」、`coverage.complete` 不含窗口尾部改用 `pending_tail_ms`）已在设计与 packet 具名并列入 §17.3 重评审必答；O1–O8 全部落档；草案 §1–§10 原文未改写（`git diff -U0` 删除行仅 §4 定稿标记块与 §10 修订记录追加）；C packet 未被动过；`rework_count` 仍为 0（计划评审 REWORK 不计数）。
- 后续状态：修订任务 → `verified`；重评审 packet `plan-review-r2-dual-ledger-flow-log-v1` 已备（deepseek，对象 = 修订增量，含 §17.3 新增三问）；三份实现 packet 的 `status_revision` 已由 3 更新为 4（路由前若 revision 再变须再同步）；C packet 的 F4 覆盖文案 pre-dispatch correction 已由 Bookkeeper 执行（见 C packet 与封存提交）。

## Errata (append-only)

（无。）
