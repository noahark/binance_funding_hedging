# Task Handoff: P3-borrow-card-market-nav-implementation

## Source Report (author-only; immutable after task end)

- task_id: `P3-borrow-card-market-nav-implementation`
- role: `Implementer`
- target_model: `kimi` / provider `moonshot`
- stage_id: `2026-08-29-borrow-card-market-nav-v1`
- created_at: `2026-08-29 20:57:12 CST`
- base_sha: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`（与 `git rev-parse HEAD` 逐字一致，工作区仅两个允许文件被修改）
- delivery_sha: `pending`

### 任务背景与范围

按定档方案 `borrow-card-market-nav.plan.md`（P2 评审 `ACCEPT`，含 4 条非阻塞观察）在借币任务卡右上角实现「行情 ↗」反向定位按钮与智能解阻导航。纯前端，零后端/schema/存储/外部请求/资金动作。修改范围严格限于派单允许的两个文件：

- `frontend/index.html`（修改，+129 行）
- `frontend/self-check.js`（修改，+343 行）

### 实际修改

`frontend/index.html`：

1. CSS：`tbody tr.selected` 规则旁新增 `@keyframes market-row-focus-pulse` + `tbody tr.market-row-focus > td { animation: ... 1.5s ease-out }`；`.borrow-task-head` 规则旁新增后代选择器 `.borrow-task-head .borrow-market-nav { margin-left:auto; flex:0 0 auto; }`（不改共享的 `.borrow-task-head` 本体，观察 C）。
2. `state` 新增 `marketRowFocusSymbol: null`；模块级唯一 `marketRowFocusTimer`。
3. `marketRowForBorrowAsset(asset)`：严格 `row.base_asset === asset`，快照缺失/rows 非数组返回 `null`，同资产多行取 `Array.find` 首行（D1）。
4. `renderBorrowTaskCard()`：`.borrow-task-head` 最近结果徽标后追加「行情 ↗」按钮；有匹配市场行时可用，无匹配时同位置 `disabled` + `aria-disabled="true"` + `title="当前行情快照无对应币种"`（D2）。
5. `bindBorrowTaskControls()`：新增 `[data-borrow-market-asset]` 绑定——click 首句 `stopPropagation()` 后按资产重新解析并调 `viewBorrowAssetInMarket()`；keydown 对所有按键 `stopPropagation()`，不 `preventDefault()`（D5）。
6. `renderRowHtml()`：`String(row.symbol) === state.marketRowFocusSymbol` 时根 `<tr>` 追加 `market-row-focus`，焦点跨 60s 快照等既有重绘保持（D4）。
7. `viewBorrowAssetInMarket(asset)` 固定顺序（D3）：无匹配返回 `{ ok:false, reason:'market_row_not_found' }` 且不切视图/不改筛选 → 任何修改前以 `displayRows().some(...)` 计算 `alreadyVisible` → 记焦点并清旧定时器 → `setActiveView('market')` → 已可见则不动任何 `state.filters`/DOM 控件/不调用 `renderTable()`；被筛掉则一次性放开六项实际隐藏条件并同步控件（search/assetTag/routeClass 置 `''`，`showPerpOnly=true`，`hideLowDailyRate/hideLowNetYield=false`）后单次 `renderTable()` → `marketRowElForSymbol()` 以 `tr.selectable[data-symbol="${CSS.escape(symbol)}"]` 安全查行 → 显式 `classList.add('market-row-focus')`（覆盖已可见未重绘路径）→ `scrollIntoView({behavior:'smooth', block:'center'})` → 1500ms 后仅在焦点仍为本次目标时清状态并按同一安全 selector 移除类。
8. `globalThis.__appHelpers` 新增最小接缝：`marketRowForBorrowAsset`、`viewBorrowAssetInMarket`、`getMarketRowFocusSymbol`、`getMarketFilters`（观察 D，自检以 `globalThis` 为准）。

`frontend/self-check.js`：

1. mock DOM 补最小能力：`marketRowFocusRegistry`（symbol → classList/scrollIntoView 记录，挂在 `_makeTrEl` 上，跨新建对象一致）；`borrowMarketNavBindings`（`[data-borrow-market-asset]` 每次 querySelectorAll 重建注册，供事件隔离用例调用真实 handler）；`makeElement.querySelectorAll` 新增该选择器分支。
2. 新增 62d-1..62d-8 八组用例（对应计划 §5 用例 1–8）：DOM/布局/disabled 降级/CSS `margin-left:auto`；严格解析三态；已可见保持（state 与 8 个 DOM 控件逐项不变 + tbody 未重绘 + 滚动聚焦，含观察 A 回归断言「借币视图下市场表 DOM 已含目标行」）；隐藏行放开六项同步；PERP-only 保底（内存 fixture 置 `PERP_ONLY_EXCLUDED` + `showPerpOnly=false`，断言转 true 且行真实渲染，排除只清搜索的假绿）；缺失目标 fail-closed；事件隔离与零 POST/零 borrow 请求/不开抽屉；聚焦生命周期（1.5s 动画、reduced-motion outline、重绘保持、末次为准、真实 1500ms 定时清理）。

### P2 四条非阻塞观察的处理

- **A（已可见路径的隐含前提）**：采纳——62d-3 内置回归断言「处于借币视图时 `els.tableBody` 已含目标行」，把「有快照时市场表 DOM 必已渲染」钉成回归。
- **B（stopPropagation 是防御性冗余）**：知悉——按派单 Check 6 与计划 D5 实现，与相邻 `[data-task-action]` handler 风格不同是有意为之，未据此推断既有冒泡缺陷。
- **C（`.borrow-task-head` 是共享 class）**：采纳——新样式只用后代选择器 `.borrow-task-head .borrow-market-nav`，开单卡不受影响；自检断言该选择器存在。
- **D（globalThis 措辞）**：采纳——实现与自检均以 `globalThis.__appHelpers` 为准。

### 实现中发现并处理的两处既有测试交互（据实记录）

1. 新增的 `@media (prefers-reduced-motion: reduce)` 块若独立放在市场表 CSS 区，会成为文件中第一个该 media 块，使上一 stage 62c-7 的 `indexOf` 切片断言落空。处理：把市场行 reduced-motion 规则并入既有（借币卡聚焦）media 块，文件保持单一 media 块，两 stage 断言均成立。
2. 自检中既有用例并非全部复位筛选（`hide-low-net-yield` 等在更早用例被置 false 后未恢复）。62d 块尾按「进入本块前的 ambient 快照」恢复筛选，而不是按初始默认值硬恢复，避免下游用例（占位符 73 等）因 ambient 变化失败。

### 命令与结果

- `node frontend/self-check.js` → exit 0，`[PASS]` 184 项，`[FAIL]` 0 项，末行「全部自检通过」（含新增 8 条「行情 ↗」用例与既有同源白名单/定时器白名单/localStorage 白名单）。
- `node -e "new Function(<内联脚本>)"` 语法检查通过（自检首步亦含此检查）。
- `git rev-parse HEAD` → `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0` = base_sha；`git status --porcelain` 确认本人改动仅 `frontend/index.html` 与 `frontend/self-check.js`（`ACTIVE.json` 改动与本 stage 目录未跟踪为 Bookkeeper 既有工作）。
- `test ! -e reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md` → 写入前成功（create-only 前提成立）。

### 未完成事项 / 权限边界

- 未 commit、未 merge、未部署、未启动评审会话；`status.json` 未触碰（本派单未授权）。
- 交付提交后 `delivery_sha` 由 Bookkeeper 解析填写。
- 实现交付后仍须走本 stage 既定 Review-1 / Review-2。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md`；`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json`；`reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md`
- 执行：Bookkeeper 核验本交接源区 SHA-256、base_sha 与 status.json 一致性及回执结构，确认 `node frontend/self-check.js` 可复现全绿，随后把 `current_task` 由 `dispatched` 推进为已核验并准备 Review-1 / Review-2 派单。
- 关卡：Review-1 / Review-2 双评审；合并、部署须 Human 另行授权。
- 不能假设的事实：不能假设已存在任何提交（delivery_sha 为 pending）；不能假设本交接授权 commit/merge/部署；不能假设 `status.json` 已被本任务更新；自检 ambient 筛选非初始默认值，任何后续改筛选的用例须按 ambient 快照恢复。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P3-borrow-card-market-nav-implementation
执行结果: completed（完成）
结果摘要: 借币任务卡右上角已实现「行情 ↗」按钮：严格 base_asset 匹配、无匹配 disabled 降级；已可见时筛选与控件逐项保留不重绘，被筛掉时六项隐藏条件全放开并同步 DOM（含 showPerpOnly=true 保底）；切市场视图平滑居中并 1.5 秒聚焦（reduced-motion 有静态反馈）；click/keydown 均 stopPropagation 且无 preventDefault。P2 四条观察逐条处理。自检 184 项全过、0 失败。
产物: [reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md]
检查结果: [pass: 每张借币卡右上角渲染按钮、无匹配资产 disabled+title 降级; pass: 已可见时 state.filters 与全部筛选 DOM 控件逐项不变且不重绘; pass: 隐藏时六项条件放开且 state/DOM 同步（含 showPerpOnly=true）、目标行进入 DOM; pass: 切市场视图+scrollIntoView smooth center+1.5s 聚焦且 reduced-motion 静态 outline; pass: click/keydown 均 stopPropagation、无 preventDefault、零 POST/零 borrow 请求、不开抽屉; pass: node frontend/self-check.js 全量 184 项通过、0 失败（含白名单）; pass: 交接文件已建于确定性路径、delivery_sha pending、含源报告与 Human 简报]
阻塞项: [none]
本地北京时间: 2026-08-29 20:57:12 CST
下一步模型: Bookkeeper（gemini-3.7-flash，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/evidence/P3-borrow-card-market-nav-implementation.handoff.md；reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/status.json；reports/agent-runs/2026-08-29-borrow-card-market-nav-v1/borrow-card-market-nav.plan.md；执行：核验本交接源区 SHA-256 与 base_sha、复跑 node frontend/self-check.js，推进 status.json 并准备 Review-1/Review-2 派单；关卡：Review-1/Review-2 双评审，合并与部署须 Human 另行授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-29 21:00:59 CST`
- verifier: `gemini-3.7-flash` (Bookkeeper, `agy` window)
- source_sha256: `e0a32bd2383738a050b79a880c5bcca7f62815f6ae6f0be8eef128c46cc42a58`
- matched_status_revision: `3`
- next_status_revision: `4`
- base_sha: `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0`
- delivery_sha: `1de91864ab2446f51668b0c356d17da1a6575de6`
- verification_verdict: `VERIFIED_PASS`
- checks:
  1. Base SHA `341aef6aeab417b3d2e83bd6f5ec1bed90b048b0` verified.
  2. Delivery commit `1de91864ab2446f51668b0c356d17da1a6575de6` sealed with product changes strictly confined to `frontend/index.html` and `frontend/self-check.js`.
  3. `node frontend/self-check.js` independently executed: 184 tests passed, 0 failures.
  4. Handoff file created at deterministic path with complete source report, Human brief, and valid marker.

## Errata (append-only)

None at task verification.
