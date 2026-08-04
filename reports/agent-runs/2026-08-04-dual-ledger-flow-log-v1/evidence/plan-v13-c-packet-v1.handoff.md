# Task Handoff: plan-v13-c-packet-v1

## Source Report (author-only; immutable after task end)

- task_id: `plan-v13-c-packet-v1`
- role: `Planner`
- target model: `opus5`（provider `anthropic`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 20:26:11 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`（取自 `status.json.base_sha`，`git rev-parse --verify` 通过）
- delivery_sha: `none`（本任务无 delivery commit；两份文档修订留在工作树，按 dispatch 由 Bookkeeper 封存）

### 任务背景与范围

任务 B 已核验封存（`delivery_sha=550f8b7`，31 passed + 194 回归，契约 v0.12）。按 Human 2026-08-04 的两个 UI 决策（**流水日志改独立展示页**、**两栏各默认展示最新 20 条**）与「先联调后统一评审」的流程调整，本任务在路由 C 之前做权威准备：把设计定稿从 v1.2 推到 **v1.3**，并把 C packet 从「嵌入面板 + 展开/收起 + 假数据」的旧版**整份重写为真实数据版**。**未写任何业务代码。**

### 实际修改范围（两个文件，均在 Allowed Files 内）

**1. `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`：v1.2 → v1.3**

| 位置 | 改动 |
|---|---|
| 顶部定稿标记 | v1.2 → v1.3；写明本轮只改 UI 布局与展示条数，`§13.1–§13.6`/`§14`/`§15.1–§15.4` 一字未动，A、B 已交付实现不受影响 |
| §10 修订记录 | 追加 v1.3 行（四项改动 + 不改契约的声明） |
| §11.1 | `#btn-flow-log` 由「展开/收起」改为「切换到独立页 `setActiveView('flow-log')`」；新增 `#nav-flow-log` 侧栏入口行 |
| §11.2 | 冻结的 DOM 片段改为 `aria-controls="flow-log-view"`、去掉 `aria-expanded`；新增一段 ARIA 语义说明（独立页用 `aria-current="page"`） |
| §13.2 规则 8 | 追加「前端默认只渲染最新 20 条」的展示层说明，并写死它**不改变** `row_count` / `summary_*` / `row_limit_applied` 任何语义；三个数字（20 / 500 / 全量）必须可区分 |
| §13.7 | 新增「布局形态」段落（含独立页的理由）；表格 `容器` / `打开方式` 两行改写为 `容器` / `导航入口` / `视图切换` / `进入视图` 四行；`时间窗` 行补请求语义与北京日界；`轮询` 行改为按视图生命周期并禁止叠加定时器；`明细上限` 行改写为 `明细展示条数`（20 条 + 右栏「筛选后取前 20」+ 三数字文案 + 不做加载更多）；冻结 id 集合新增 `nav-flow-log`、`flow-log-view`；末尾 v1.2 待办框改为「已落实」 |
| §15.1 | 追加一行指针：前端 60 秒轮询不是本节的后端节拍，权威在 §13.7；两者互不替代 |
| §17.4 | 「C packet 尚未按 F4 补齐覆盖文案」标记为已闭合 |

草案 §1–§10 原文未改写（§10 仅按前三版惯例追加一行修订记录）。

**2. `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`：整份重写为真实数据版**

旧版是「嵌入 `#market-view` + 点按钮展开/收起 + 首次展开 GET」的布局，与 Human 决策和已验收的 fake v2 实现都不符；重写后：

- **Identity**：`target_model` `kimi` → `grok`（provider `xai`，Human 显式启用 Grok 实现例外，与 fake v1/v2 同一模型）；`required_skill` 仍为 `agents/skills/senior-developer.md`；`status_revision` 留 `PENDING` 占位（见下「交 Bookkeeper 处理的三件事」）。
- **Goal 第 0 节**：明确起点是已验收的 fake v2 独立页，列出必须原样保留的清单（独立视图与导航、`setActiveView` 互斥、需求 1 按钮落位、冻结 id 全集、双栏标题、五筛选、两个元数据区块、窄屏堆叠、隐私遮蔽、20 条），并写明「不要重做布局」。
- **第 1 节**：假数据 → 真实后端（`GET flow-log` + `POST refresh` 后重新 GET）；删除 `buildFlowLogFakePayload` / `flowLogFakePayload` / 两个 fake helper seam；**移除全部 FAKE 痕迹**（横幅 DOM + CSS 类 + 副标题 + 「刷新（演示）」按钮文案 + 失效注释），改由 §13.7 状态条与覆盖提示承担。
- **第 2 节（12 条展示硬规则）**：把 v1.2 遗留的「覆盖文案只写了起点截断」缺口补齐——状态条主文案按 §13.2 规则 14 **顺序取第一个命中**、`pending_tail_ms` 是独立附注、覆盖提示只要 `complete=false` 就必须渲染且分 (a)/(b) 两种成文、`complete=false` 时全页禁用「该时间窗无记录」类措辞；另含增量自解释与 `delta.complete=false` 零数字、三口径标注、不排序/不重算/不做算术（`Number()` 仅用于正负号着色）、缺失渲染 `—` 且 ID 不得数值化、20 条与三数字文案（右栏取前 20 在筛选之后）、筛选零请求且不改汇总、时间窗请求语义与北京日界、轮询生命周期、加载与全部错误码文案、隐私遮蔽、时间与文案表。
- **第 3 节**：明确**允许**改 `setActiveView` 的 `flow-log` 分支（加载 + 轮询管理），其余三个分支一字不改——旧 packet 的「不动 `setActiveView`」在独立页下已不成立。
- **第 4 节（self-check）**：点名两个会直接让自检炸掉的机关——fetch mock 兜底会 `throw Unexpected fetch URL`（`frontend/self-check.js:835`），必须为两条新路由加 mock；98b 的三处 fake 断言必须反转或删除（`:5380` FAKE 横幅、`:5387` 禁止 fetch private-ledger、`:5423` `getFlowLogFakePayload`）。另列 9 组必须覆盖的断言（含**不要**断言「全局只有一个 60000 定时器」，因为既有市场自动刷新就是 60000ms）。
- **第 5 节红线 + Stop**：不改后端与契约、不启动服务、不发真实请求、**不得触发真实 `POST /refresh`**（联调与真实拉取由 Human 之后单独主持并授权）。
- **Allowed Files / Inputs / Acceptance Checks**：文件边界不变（`frontend/index.html` + `frontend/self-check.js` + handoff + selfcheck.txt + `status.json` 仅改本任务状态）；Inputs 增加契约 v0.12、B 交接件、fake v2 交接件；验收改为 8 条真实版检查。

### 结论与判断依据

- 设计 v1.3 与 fake v2 **实现现状**逐项核对一致（`frontend/index.html:1213` 侧栏入口、`:1263-1266` `#btn-flow-log` 属性、`:1363-1364` `#flow-log-view` 包裹 `#flow-log-panel`、`:5854-5890` `setActiveView` 四视图互斥、`:6017` `FLOW_LOG_DEFAULT_DISPLAY_LIMIT = 20`、`:6250-6254` 取前 20），因此 C 不需要返工布局，只换数据源与错误/空态。
- 设计 v1.3 与契约 v0.12 无冲突：v1.3 未触碰任何 wire 字段、状态码或数据语义，只改前端渲染与展示条数；`row_limit_applied` 的语义在规则 8 里被显式保护。
- 「取前 20」与旧 §13.7「前端不做二次截断」原文冲突，已在规则 8 与 §13.7 明细行里**显式区分**：不做二次截断指的是**不重算汇总、不改 `row_count` 语义**，展示层取前 N 是另一回事且必须在文案上讲清三个数字。这是本轮唯一一处与 v1.2 原文的语义张力，已就地消解，未留两套说法。

### 未完成 / 不属于本任务

- 未写业务代码；未动 `backend/`、`frontend/`、A/B packet 与任何 evidence。
- 未提交（`delivery_sha=none`）；两份文档修订留工作树。
- 未路由 C、未启动任何终端、未做前后端联调。

### 交 Bookkeeper 在路由 C 之前处理的三件事

1. **`status_revision` 占位必须填实**：C packet 的 Identity 写的是 `<PENDING — Bookkeeper 路由本任务时填入当时的 status.json.revision；未填不得投递>`。原因是本任务完成后 Bookkeeper 还要封存并起新 revision，Planner 此刻无法知道投递时的值；照 `AGENTS.md` §4「Stop if stage, task, target model, or revision differs」，填错比留空更危险。
2. **handoff 路径需复跑预检**：C 的 `evidence/frontend-dual-ledger-flow-log-v1.handoff.md` 先前 `test ! -e` 记录是 2026-08-04 12:55 CST 的 `PASS(absent)`；packet 已整份重写，Allowed Files 那一行留了位置要求路由前复跑并写入结果与时间。
3. **§16 拆分表与实际路由不一致（本任务无权改）**：设计 §16 的表格仍写任务 C 的默认实现者是 `kimi`（`moonshot`），而 Human 已决定路由 `grok`（`xai`）。§16 不在本任务 Allowed Files 内，故**未改动**；模型路由的权威是 dispatch 与 `agents/roles.md`（Grok 实现须 Human 或 dispatch 显式启用，本次已在 packet Identity 记录）。Bookkeeper 决定是更正 §16 还是仅在路由记录中说明。**连带影响**：C 交付后统一评审的 provider 隔离要同时避开 `zhipu_glm`（A、B 作者）与 `xai`（C 作者），候选池比原计划窄，宜在准备 review packet 前先确认额度。

### 命令与结果（全部只读/离线；未启动服务、未访问网络、未读凭据、未执行实盘操作）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v13-c-packet-v1.handoff.md` → `PASS(absent)`（2026-08-04 20:26 CST，与 Bookkeeper 20:15 CST 预检一致）
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`
- `git rev-parse HEAD` → `11da7930c9f3ae0ab10904ce77514d1f162ea731`（B 封存后的簿记提交）
- `git status --short` → 仅两个 `M`：设计文档与 C packet，无其他改动
- `date '+%Y-%m-%d %H:%M:%S CST'` → `2026-08-04 20:26:11 CST`

### 仓库内证据路径

- 设计定稿 v1.3：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`
- 重写后的 C packet：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`
- 接口权威：`docs/api/public-market-contract.md`（v0.12 amendment）
- 后端实际交付：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`
- C 的起点实现：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v2.handoff.md`、`frontend/index.html`、`frontend/self-check.js`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v13-c-packet-v1.handoff.md`；`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- 执行：Bookkeeper 核验本交接件与两份文档修订、封存本轮修订提交，并在路由 C 前处理上面「交 Bookkeeper 处理的三件事」（填 `status_revision`、复跑 `test ! -e`、裁定 §16 与 provider 隔离）
- 关卡：Human 启动 C 终端（`grok` / `xai`）→ C 交付后前后端联调（离线部分免授权；连币安的真实 `POST /api/private-ledger/refresh` 须 Human 单独授权）→ 联调通过后按 `HIGH_RISK` 统一走 review-1 + review-2（覆盖 A+B+C）
- 不能假设的事实：本任务无 delivery commit（`delivery_sha=none`，修订留工作树）；C packet 的 `status_revision` 仍是占位、未填不得投递；设计 §16 的实现者列仍写 `kimi`、与实际路由 `grok` 不一致且本任务无权更正；v1.3 未改任何接口契约与数据语义，C 的响应消费一律以契约 v0.12 与 B 交接件为准；前端「取前 20」是展示层行为，`row_count` / `summary_*` / `row_limit_applied` 的语义未变。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: plan-v13-c-packet-v1
执行结果: completed（完成）
结果摘要: 设计定稿升 v1.3：流水日志确认为独立展示页（侧栏入口+setActiveView 互斥，不再嵌市场页展开）、两栏各默认显示最新 20 条且不改 row_count/summary/row_limit_applied 语义、轮询改按视图生命周期、§10 追加修订记录、v1.2 遗留的 C packet 待办标记闭合。C packet 整份重写为真实数据版：接 GET flow-log 与 POST refresh、删全部假数据与 FAKE 横幅、补齐覆盖护栏两种文案与空态三态判定、self-check 改真实断言。未写代码、未提交。
产物: [docs/planning/2026-08-04-dual-ledger-flow-log-design.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v13-c-packet-v1.handoff.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json]
检查结果: [AC1 设计v1.3(§13.7独立页布局+默认20条+按视图轮询+§10修订记录行齐备): pass, AC1b 草案§1–§10原文未改写(§10仅追加一行修订记录，沿用v1.0/v1.1/v1.2惯例): pass, AC1c 受影响章节一致(§11.1/§11.2按钮与ARIA、§13.2规则8展示条数、§15.1前端轮询指针、§17.4待办闭合): pass, AC2 C packet与设计v1.3+契约v0.12三方一致(响应字段/空态/状态码/排序去重全部按v0.12消费): pass, AC2b fake v2硬规则保留且FAKE横幅要求移除(冻结id全集含nav-flow-log与flow-log-view、双栏标题、五筛选、隐私、窄屏、需求1按钮落位): pass, AC2c 真实数据源+60秒轮询+错误空态判定表+self-check更新要求齐备，文件边界仍为index.html+self-check.js+evidence: pass, AC3 交接件与回执(Source Report+Human Brief+合规TASK_RESULT v2+三行中文交接，delivery_sha=none，status仅改本任务状态): pass, AC4 未写业务代码/未动A·B文件/未启动终端/未执行实盘·网络·凭据操作: pass]
阻塞项: [none；三项交 Bookkeeper 路由前处理：(1) C packet 的 status_revision 是 PENDING 占位必须填实际值 (2) C 的 handoff 路径 test ! -e 需复跑并记录时间 (3) 设计 §16 拆分表仍写 C 的实现者为 kimi 与实际路由 grok 不一致（§16 不在本任务 Allowed Files，未改动），且统一评审的 provider 隔离须同时避开 zhipu_glm 与 xai]
本地北京时间: 2026-08-04 20:26:11 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-v13-c-packet-v1.handoff.md；docs/planning/2026-08-04-dual-ledger-flow-log-design.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/frontend-dual-ledger-flow-log-v1.dispatch.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json；执行：核验并封存设计 v1.3 与重写后的 C packet，路由 C 前填实 status_revision、复跑 test ! -e、裁定 §16 与 provider 隔离；关卡：Human 启动 C 终端（grok/xai）→ 前后端联调（真实 POST refresh 须 Human 单独授权）→ 联调通过后统一 review-1 + review-2（A+B+C）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 20:32:00 CST
- source_sha256（marker 前字节）：`c34806cda62256a0bbc288a404bf76be48bb1b21f6bc2ed36db9ee583ed3a3ef`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：12（`current_task.id = plan-v13-c-packet-v1`、`state = reported`，与交接件声明一致；预检 `test ! -e` 于 2026-08-04 20:15 CST 通过，Planner 20:26 CST 复验一致）
- task_id / role / stage_id 与 `status.json` 一致；base_sha `dc4cc6d` 存在且等于 status.json 值；HEAD `11da793` 晚于 base_sha，符合 SHA Discipline
- delivery_sha：`none`（文档修订未提交；git status 为设计文档 + C packet + status.json 修改与新建交接件，均留在工作树交封存）
- 结论：**通过（verified）**。设计 v1.3：§13.7 独立页布局（`#nav-flow-log` / `#flow-log-view` / `setActiveView` 互斥）、默认 20 条（`row_count`/`summary_*`/`row_limit_applied` 语义显式保护）、按视图生命周期轮询、§10 修订记录行齐备、草案 §1–§10 未改写、未改任何接口契约与数据语义；C packet 整份重写为真实数据版（grok/xai 且 Human 显式启用记录在 Identity、删假数据与 FAKE 横幅、接 GET flow-log + POST refresh、覆盖护栏两种文案 + 空态三态判定、self-check 真实断言、文件边界不变）。
- **三项路由前事项裁定**：
  1. **C packet `status_revision`**：占位符已由 Bookkeeper 填为实际值 `13`（本封存提交后的 status.json revision）；若 Human 启动前 revision 再变须再同步。
  2. **C handoff 预检复跑**：`evidence/frontend-dual-ledger-flow-log-v1.handoff.md` 与 `.selfcheck.txt` 于 2026-08-04 20:32 CST 复跑 `test ! -e` → 均 `PASS(absent)`，结果已写入 C packet Allowed Files。
  3. **§16 与 provider 隔离裁定**：设计 §16 表格 C 行仍写 `kimi`（`moonshot`）为默认实现者——这是 `agents/roles.md` 的前端默认路由；本 stage Human 2026-08-04 显式指派 `grok`（`xai`）实现前端（fake v1/v2 与 C 同一模型，`agents/roles.md`「Grok implementation only when the human or dispatch explicitly enables it」已满足）。Bookkeeper 裁定：**不改 §16 表格原文**（Planner 产物、非本次授权范围），在 §16 表格后追加一行显著路由勘误标注（本块对应的勘误行已追加至设计 §16）；模型路由权威为 C packet Identity 与 `agents/roles.md`。**统一评审 provider 隔离**：review-1 须避开 `zhipu_glm`（A、B 作者）与 `xai`（C 作者）→ 候选 `moonshot`（kimi）、`deepseek`、`openai`（codex）；review-2 须与所有实现作者（`zhipu_glm`、`xai`）跨 provider → 候选 `anthropic`（opus5，注意其为本 stage 计划/设计作者，设计参与须披露）、`openai`、`deepseek`。具体评审模型在联调通过后路由评审时再定并记录。
- 后续状态：本任务 → `verified`；任务 C `frontend-dual-ledger-flow-log-v1` 已路由（grok/xai，status_revision=13）；Human 启动 C 终端 → C 交付后前后端联调（离线部分免授权；真实 `POST /refresh` 须 Human 单独授权）→ 联调通过后统一 review-1 + review-2（A+B+C，provider 隔离按本块裁定）。

## Errata (append-only)

（无。）
