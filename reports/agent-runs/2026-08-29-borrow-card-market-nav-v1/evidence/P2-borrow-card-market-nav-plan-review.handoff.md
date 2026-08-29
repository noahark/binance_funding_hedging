# Task Handoff: P2-borrow-card-market-nav-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `P2-borrow-card-market-nav-plan-review`
- role: `Reviewer` (pre-implementation plan review, read-only)
- target_model: `opus5` / provider `anthropic`
- stage_id: `2026-08-29-borrow-card-market-nav-v1`
- created_at: `2026-08-29 20:28:44 CST`
- base_sha: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`
- delivery_sha: `none`

### Verdict

`ACCEPT（接受）`

计划最小、内部自洽，可在已核实的前端接缝上无歧义实现，八条验收检查全部 `pass`。计划对现状的每一条引用均经源码逐条比对，无失实。核心风险项（隐藏条件枚举完整性）经**独立重新枚举**确认无遗漏。附四条非阻塞观察，不构成返工。

### Isolation

- P1 计划作者与本评审非同一模型；本评审 `opus5` / `anthropic`，跨供应商，未参与该计划撰写。
- 全程只读；唯一写入为本 create-only 交接文件。未修改计划、`frontend/index.html`、`frontend/self-check.js`、P1 证据、`status.json`、`PROJECT_STATE.md`、schema、配置或 git 历史；未提交、合并、部署，未启动下一模型。

### Fixed target verification (前置)

- `shasum -a 256 reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
  → `cc87b1e2d8669a93aae3d3a415ed3dd83464780b52cd570ae866b2935e405791`，与派单期望**逐字符相等**，packet 未过期。
- `git rev-parse HEAD` → `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`，与派单 `Baseline source revision` 及 `status.json.base_sha` 一致。
- `test ! -e .../evidence/P2-borrow-card-market-nav-plan-review.handoff.md` → 评审开始前成功。
- `status.json`：`revision 2` / `phase plan_review` / `current_task.id P2-borrow-card-market-nav-plan-review` / `state dispatched`，与派单 `status_revision: 2` 一致。
- 工作区仅有未提交的本 stage 目录与 `ACTIVE.json` 改动（Bookkeeper 准备产物）。计划文件未入 git，故按派单以 SHA-256 锁定评审对象、以 committed `HEAD` 锁定代码基线，未移动 `HEAD`。

### 核心核实：隐藏条件枚举完整性（派单 Review Check 4）

本项是计划成立与否的唯一硬依赖：若 `filteredRows()` 存在计划未列出的隐藏条件，导航后目标行仍可能不可见，「100% 可见」承诺即落空。**未采信计划的自述**，对 `filteredRows()` 逐行独立枚举（`frontend/index.html:3365-3381`）：

| # | 源码条件 | 计划是否列出 |
|---|---|---|
| 1 | `q && !symbol.includes(q) && !base_asset.includes(q)` | ✅ `search` |
| 2 | `state.filters.assetTag && row.asset_tag !== …` | ✅ `assetTag` |
| 3 | `state.filters.routeClass && row.route_class !== …` | ✅ `routeClass` |
| 4 | `!state.filters.showPerpOnly && row.route_class === 'PERP_ONLY_EXCLUDED'` | ✅ `showPerpOnly` |
| 5 | `hideLowDailyRate && absDailyRateAtOrBelowThreshold(...)` | ✅ `hideLowDailyRate` |
| 6 | `hideLowNetYield && netYieldAtOrBelowThreshold(...)` | ✅ `hideLowNetYield` |

函数体内**再无其他 `return false` 分支**，`if (!state.snapshot) return []` 是前置而非行级筛选，且该情形已由 D3.1 fail-closed 覆盖。**计划枚举完整，无遗漏。**

两个「不应重置」的判断亦经源码确认，计划结论正确：

- `displayRows()`（`3383-3394`）在 `filteredRows()` 之后仅分组重排并 `openable.concat(rest)`，**保留全部行**，不新增隐藏条件 → `preferOpenable` 确实不必重置。
- `showHl` 唯一消费点为 `hlSublines(row)`（`3588`），只决定行内子行文本，不参与行过滤 → 确实不必重置。

第 4 项方向性尤其关键：条件为 `!showPerpOnly && PERP_ONLY_EXCLUDED`，因此放开必须置 `true`（而非直觉上的 `false`）。计划 D3.5 表格与 §6 均写 `true`，方向正确。

### Verified code facts (逐条核对计划 §2 的引用)

| 计划断言 | 核对位置 | 结论 |
|---|---|---|
| `.borrow-task-head` 依次为资产标题、状态徽标、最近结果徽标，可在末尾追加 | `frontend/index.html` 借币卡模板 | 属实（`<h3>` + status badge + `${latestBadge}`） |
| `.borrow-task-head` 为 flex 容器，`margin-left:auto` 可右推 | `frontend/index.html:1250-1254` | 属实（`display:flex; align-items:center; gap:…`） |
| `bindBorrowTaskControls()` 在列表重建后绑定卡片控件 | `frontend/index.html:5551-5569` | 属实，含 mock 守卫 `typeof … querySelectorAll !== 'function'` |
| `setActiveView('market')` 只切视图并置顶，不重置筛选、不重绘市场表 | `frontend/index.html` setActiveView market 分支 | 属实（仅 `loadPnlSeries()` 与 `window.scrollTo(0,0)`） |
| 市场行根节点为 `tr.selectable[data-symbol]` | `frontend/index.html:3660` | 属实 |
| `patchRow()` 已证明 `CSS.escape(symbol)` 同形选择器可用 | `frontend/index.html:3816` | 属实 |
| self-check mock 支持同形选择器 | `frontend/self-check.js:52-53` | 属实，且已 polyfill `global.CSS = { escape: … }`，无需新增依赖 |
| `renderTable()` 经 `captureMarketOpInputs()`/`restoreMarketOpInputs()` 保留输入 | `renderTable()` 首行 | 属实 |
| 上一轮已有 `borrowTaskFocusId + 单 timer + render 带 class` 聚焦模式 | `renderBorrowTaskCard()` 内 `focusClass` | 属实，本轮平行新增市场行状态而不抽象成跨视图框架，取舍合理 |
| `renderRowHtml(row, umPositions)` 为行 HTML 生成点 | `frontend/index.html:3616` | 属实，可承载焦点 class |

补充核实一项计划未显式记录、但决定 D3.4 成立与否的前提，结果**支持**计划：`ingestSnapshot()` 无条件调用 `applyFiltersAndRender()`，后者无条件调用 `renderTable()`，且 `renderTable()` 为纯同步 DOM 写入。因此只要 `state.snapshot` 存在，市场表 DOM 必已渲染（即便当前停留在借币视图）；而快照缺失或 `state.blocked` 时 `state.snapshot` 为 `null`，D3.1 已 fail-closed 返回。故「已可见分支不重绘、直接查 DOM」不会落空，D3.5 重绘后同步查询亦必然命中。

### Acceptance checks

1. `pass` — D2 将按钮追加于徽标之后并以 `margin-left:auto` 右对齐（容器确为 flex）；无匹配时同位置保留 `disabled` + `aria-disabled="true"` + `title` 说明，属 graceful 降级而非隐藏；资产经 `escapeHtml()`，`aria-label` 完整。
2. `pass` — D1 严格 `row.base_asset === asset`，`Array.find` 取快照首行为确定性结果，无大小写归一、无 symbol 拼接、无别名推断、无网络兜底；快照缺失或 rows 非数组返回 `null`。
3. `pass` — D3.2 明确在**任何修改前**以 `displayRows().some(...)` 计算 `alreadyVisible`；D3.4 在该分支不动任何 `state.filters`、不动任何筛选 DOM 控件、不调用 `renderTable()`，搜索框/两下拉/四 checkbox 及 `preferOpenable`、`showHl` 全部原样保留。
4. `pass` — 见上「核心核实」：六项隐藏条件与源码逐条对应且完整，`showPerpOnly=true` 闭合 `PERP_ONLY_EXCLUDED` 可见性缺口，`preferOpenable` 与 `showHl` 经证据确认无需触碰。
5. `pass` — D3 顺序固定（解析 → 计算可见性 → 记录焦点并清旧 timer → `setActiveView('market')` → 分支内**至多一次** `renderTable()` → `CSS.escape` 安全查行 → 显式加 class → `scrollIntoView({behavior:'smooth',block:'center'})`）；D4 经 `renderRowHtml()` 使焦点跨 60s 快照重绘存活，重复点击先 `clearTimeout` 且仅末次生效，1500ms 后按同一安全 selector 清理，`prefers-reduced-motion` 保留静态反馈，且明确不覆盖持久 `.selected` 语义。
6. `pass` — D5 click/keydown 均首句 `stopPropagation()` 且明确**不调用** `preventDefault()`，保留原生 Enter/Space 激活；动作仅读本地状态与改 DOM，无 fetch、无 borrow POST、无行抽屉、无订单/持仓/资金路径。已按派单要求不以「借币域标签」本身推定资金变更，实际计划效果为纯读取与视图切换。
7. `pass` — §5 八条用例运行真实 handler 并断言 state 与 DOM 控件逐项同步；用例 5 用 `PERP_ONLY_EXCLUDED` + `showPerpOnly=false` 的内存 fixture 断言 checkbox/state 转 `true` 且行真实渲染，明确排除「只清搜索」的假绿；用例 6 覆盖 no-match fail-closed；mock 仅需补按钮注册、`classList`、`scrollIntoView` 记录，`CSS.escape` 已存在，零依赖 harness 成立。
8. `pass` — §1/§4/§7 将实现范围限定为 `frontend/index.html`、`frontend/self-check.js` 与实现任务交接；无后端/schema/store/API 改动；§2 末句明确拒绝抽象为跨视图导航框架，符合最小改动。

本评审未引入任何需经 `AGENTS.md` §1 Scenario Admission 的假设性阻塞情形。

### Non-blocking observations (不构成返工)

- **A. D3.4 依赖一个未写明的前提。** 「已可见即不重绘、直接查 DOM」成立的前提是「有快照时市场表 DOM 必已渲染」，该前提当前由 `ingestSnapshot → applyFiltersAndRender → renderTable`（无条件、同步）保证，本评审已验证。但计划未记录这条依赖。若日后有人为省开销把 `renderTable()` 改成「仅市场视图激活时执行」（与 `loadBorrowTasks()` 现有的视图条件重绘同型的优化），该路径会**静默失效**：不报错、不滚动、无聚焦。建议实现时在自检用例 3 内顺带断言「处于借币视图时 `els.tableBody` 已含目标行」，把该前提钉成回归。
- **B. `stopPropagation()` 在此处是防御性冗余，非缺陷修复。** `bindBorrowTaskControls()` 现有的 `[data-task-action]` / `[data-task-edit-confirm]` handler 均未调用它，因为借币任务卡不存在卡片级点击处理器（与市场表 `tr` 的 `openDrawer` 不同）。计划的要求满足派单 Check 6 且无害，实现者知悉它与相邻代码风格不同即可，不必据此推断存在既有冒泡缺陷。
- **C. `.borrow-task-head` 是共享 class。** 开单任务卡复用同一 class（内含 `task.coin` 与开单/平仓徽标）。计划 CSS 使用后代选择器 `.borrow-task-head .borrow-market-nav`，仅在按钮存在时生效，不波及开单卡；实现时勿将新样式直接加在 `.borrow-task-head` 自身。
- **D. 措辞。** §4 写 `window.__appHelpers`，实际接缝为 `globalThis.__appHelpers`。浏览器内等价，但自检运行于 node，实现与自检应以 `globalThis` 为准。

### Unfinished / authority boundary

- 本任务只产出计划评审结论，无实现、无提交、无 `delivery_sha`。
- 仅 Bookkeeper（`gemini-3.7-flash`，`agy` 窗口）可核验本交接并推进 `status.json`；本评审无权写状态、派发实现或启动模型。
- `ACCEPT` 只解锁「准备实现派单」，不授权实现、commit、merge、部署或任何借币/订单/资金动作。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md`；`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`；`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`
- 执行：Bookkeeper 核验本交接源区 SHA-256、`base_sha` 与 `status.json` 一致性及 `ACCEPT` 结构完整性，随后推进 `status.json`，并准备由 `kimi` 执行的前端实现派单（允许文件仅 `frontend/index.html`、`frontend/self-check.js` 与该实现任务的交接文件）。
- 关卡：实现交付后仍须走本 stage 既定的 Review-1 / Review-2；实现派单宜要求实现者对上列四条非阻塞观察逐条给出处理说明（尤以观察 A 的回归断言为宜），但它们不阻塞派发。
- 不能假设的事实：不能假设已有任何前端代码改动；不能假设 `delivery_sha` 存在；不能假设本评审授权提交、合并、部署或实盘操作；不能假设 Reviewer 有权改 `status.json`。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P2-borrow-card-market-nav-plan-review
执行结果: completed（完成）
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md
修复要求: none
结果摘要: 计划 SHA-256 与基线 341aef6 均精确匹配。独立重新枚举 filteredRows() 确认隐藏条件正好六项、计划无遗漏，且 showPerpOnly 需置 true 的方向正确；displayRows 只重排、showHl 只管子行，确不需重置。八条验收检查全 pass。附四条非阻塞观察。
产物: [reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md]
检查结果: [pass: 按钮右上角布局/无匹配 disabled 降级/可访问性完整; pass: 严格 base_asset 匹配且无别名与网络兜底; pass: 已可见分支修改前判定并原样保留全部筛选与控件; pass: 六项隐藏条件经独立枚举确认完整且 showPerpOnly=true 闭合 PERP-only 缺口; pass: 固定顺序/至多一次重绘/CSS.escape 安全查行/1.5 秒聚焦跨重绘存活; pass: click 与 keydown 隔离且零 POST 零请求零抽屉; pass: 自检覆盖 PERP-only 保底与 no-match fail-closed 且零依赖; pass: 范围仅两前端文件并明确拒绝抽象为导航框架]
阻塞项: [none]
本地北京时间: 2026-08-29 20:28:44 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md；reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md；reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json；执行：核验本交接后推进 status.json，准备由 kimi 执行、仅限 frontend/index.html 与 frontend/self-check.js 的实现派单；关卡：实现交付后仍须走既定 Review-1 / Review-2
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-29 20:31:12 CST`
- verifier: `gemini-3.7-flash` (Bookkeeper, `agy` window)
- source_sha256: `31ad4363fdbe32b3700f6d3c5d876f2e3044157853163f9c192a23cead74af28`
- matched_status_revision: `2`
- next_status_revision: `3`
- review_verdict: `ACCEPT`
- review_problems: `reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P2-borrow-card-market-nav-plan-review.handoff.md` (4 non-blocking observations)
- review_repair_requirements: `none`
- verification_verdict: `VERIFIED_PASS`
- checks:
  1. Base SHA `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0` matches git HEAD and status.json.
  2. Plan review conducted by cross-provider reviewer `opus5` (`anthropic`) in fresh read-only session.
  3. Plan artifact `borrow-card-market-nav.plan.md` exact SHA-256 `cc87b1e2d8669a93aae3d3a415ed3dd83464780b52cd570ae866b2935e405791` verified.
  4. Explicit `ACCEPT` review conclusion returned with all 8 acceptance checks passing.
  5. 4 non-blocking observations recorded for Implementer attention during P3.
  6. Handoff file created at deterministic path with complete source report, Human brief, and valid marker.

## Errata (append-only)

None at task verification.
