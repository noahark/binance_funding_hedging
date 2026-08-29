# Task Handoff: P3-market-borrow-view-implementation

## Source Report (author-only; immutable after task end)

- task_id: `P3-market-borrow-view-implementation`
- role: `Implementer`
- target_model: `kimi` / provider `moonshot`
- stage_id: `2026-08-29-market-borrow-view-button-v1`
- created_at: `2026-08-29 19:11:22 CST`
- base_sha: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`（与 `git rev-parse HEAD` 逐字一致，工作区仅两个允许文件被修改）
- delivery_sha: `pending`

### 任务背景与范围

按定档方案 `market-borrow-view.plan.md`（P2 评审 `ACCEPT`，含 4 条非阻塞观察）在市场表借币列实现「查看借币」跳转按钮。纯前端，零后端/schema/存储/外部请求/资金动作。修改范围严格限于派单允许的两个文件：

- `frontend/index.html`（修改）
- `frontend/self-check.js`（修改）

### 实际修改

`frontend/index.html`：

1. CSS：`.borrow-op-actions`（flex 容器，`align-items:center; gap:var(--space-1); flex-wrap:wrap`）加在 `.borrow-op-inputs` 规则旁；`@keyframes borrow-task-focus-pulse` + `.borrow-task-card.borrow-task-focus`（1.5s ease-out，`--brand`/`--brand-soft`/`--line`/`--surface-2` 脉冲）+ `@media (prefers-reduced-motion: reduce)` 下 `animation:none; outline:2px solid var(--brand)` 静态反馈，加在 `.borrow-task-card` 规则旁。
2. `state` 新增 `borrowTaskFocusId: null`（短生命周期焦点字段）；模块级唯一 `borrowTaskFocusTimer`。
3. `latestActiveBorrowTaskForAsset(asset)`：严格 `t.asset === asset && (t.status === 'borrowing' || t.status === 'paused')`，复用 `sortTasksNewestFirst` 取首个，无匹配返回 `null`。
4. `renderBorrowOpCell(row)`：`isBorrowOpDisabledRow` 短路不变（仍 `—`）；确认按钮包进 `.borrow-op-actions`，有匹配活动任务时紧跟 `data-borrow-view-task="<task-id>"`（`escapeHtml`）的「查看借币」按钮，`aria-label="查看 <base> 借币任务"`。
5. `attachRowHandlers(tr)`：真实 DOM 分支新增 `[data-borrow-view-task]` 绑定——click 首句 `stopPropagation()` 后读属性调 `viewBorrowTask`；keydown 对所有按键 `stopPropagation()`，**不** `preventDefault()`，保留原生 Enter/Space 激活。父 `.borrow-op-cell` 既有隔离不动。
6. `renderBorrowTaskCard()`：`String(task.id) === state.borrowTaskFocusId` 时输出 `borrow-task-card borrow-task-focus`，异步重拉重建卡片后焦点不丢。
7. D3 同步点：`loadBorrowTasks()` 缓存替换后与 `mutateBorrowTask()` 返回文档落缓存后，均在 `state.snapshot && !state.blocked` 时调用 `renderTable()`（自带输入捕获/恢复）。
8. `findBorrowTaskCardEl(taskId)` + `viewBorrowTask(taskId)`：按 ID 重读缓存校验目标仍 `borrowing/paused`（否则直接返回）→ 记焦点并清旧定时器 → `setActiveView('borrow-tasks')` → `setBorrowTab('tasks')` → `setBorrowTaskFilter(task.status)` → 从 `els.borrowTaskList.querySelectorAll('.borrow-task-card[data-task-id]')` 按 `getAttribute` 比对查卡（不拼 selector）→ `scrollIntoView({ behavior:'smooth', block:'center' })` → 1500ms 后清焦点字段并移除仍在 DOM 中的目标卡聚焦类，重复点击先取消旧定时器。
9. `globalThis.__appHelpers` 新增最小接缝：`latestActiveBorrowTaskForAsset`、`viewBorrowTask`、`getBorrowTaskFocusId`。

`frontend/self-check.js`：

1. mock DOM 补最小能力：`makeElement.querySelectorAll` 新增 `.borrow-task-card[data-task-id]` 解析（`borrowCardRegistry`，带 `classList`/`scrollIntoView` 参数记录/`getAttribute`）；`_makeTrEl` 新增 `querySelector`，仅识别 `[data-borrow-view-task]` 并写入 `viewBtnRegistry`（symbol → 最新一次渲染绑定的真实 listeners），其余选择器返回 `null`（confirm/输入框绑定行为与此前一致）。
2. 用例 62 扩展：无任务缓存时仍恰好 1 按钮、`.borrow-op-actions` 容器恒在、不出现 `data-borrow-view-task`。
3. 新增 62c-1..62c-7 七组用例（对应计划 §5 用例 1–7）：显示谓词五形态、1 对多确定性（created_at 最新 → id 降序 → 终态不抢占）、缓存投影及时性与输入保留、执行中跳转四断言 + 滚动参数 + 聚焦类、暂停跳转（先置日志页签）、事件隔离（真实 handler + stopPropagation/preventDefault 记录 + 抽屉状态不变 + 零 borrow POST）、聚焦生命周期（CSS 1.5s/reduced-motion outline 静态断言 + 重复聚焦末次为准 + 真实 1500ms 定时清理）。用例 8 即全量回归本身。
4. 块尾还原现场：空任务缓存 + 市场视图，不影响后续借币任务测试块。

### P2 四条非阻塞观察的处理

- **A（D2 父层级）**：采纳——`.borrow-op-actions` 原地嵌在 `.borrow-op-inputs` 内（成为第 5 个 grid item），预览/错误容器位置不变。
- **B（双同步点重复重绘）**：采纳 fail-closed 取舍——`mutateBorrowTask` 与 `loadBorrowTasks` 两个同步点都保留，一次创建/暂停正常路径重绘两次；`renderTable` 有输入捕获/恢复，无用户可见副作用，未做去重以免牺牲 GET 失败时 POST 权威状态的投影兜底。
- **C（globalThis 措辞）**：采纳——实现与自检均以 `globalThis.__appHelpers` 为准。
- **D（跳转瞬时置顶）**：知悉不改——`setActiveView` 内既有 `window.scrollTo(0,0)` 先于平滑滚动，顺序符合 D4，自检在 node 环境无 `window`，该路径由 `typeof` 守卫跳过。

### 命令与结果

- `node frontend/self-check.js` → exit 0，`[PASS]` 176 项，`[FAIL]` 0 项，末行「全部自检通过」（含新增 7 条「查看借币」用例与既有同源白名单/定时器白名单/localStorage 白名单）。
- `node -e "new Function(<内联脚本>)"` 语法检查通过（自检首步亦含此检查）。
- `git rev-parse HEAD` → `7bb70a74e4e97a5c0b136bc6146167a360f0debb` = base_sha；`git status --porcelain` 确认本人改动仅 `frontend/index.html` 与 `frontend/self-check.js`（`ACTIVE.json` 改动与 stage 目录未跟踪为 Bookkeeper 既有工作）。
- `test ! -e reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md` → 写入前成功（create-only 前提成立）。

### 未完成事项 / 权限边界

- 未 commit、未 merge、未部署、未启动评审会话；`status.json` 未触碰（本派单未授权）。
- 交付提交后 `delivery_sha` 由 Bookkeeper 解析填写。
- 实现交付后仍须走本 stage 既定 Review-1 / Review-2。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md`；`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`；`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
- 执行：Bookkeeper 核验本交接源区 SHA-256、base_sha 与 status.json 一致性及回执结构，确认 `node frontend/self-check.js` 可复现全绿，随后把 `current_task` 由 `dispatched` 推进为已核验并准备 Review-1 / Review-2 派单。
- 关卡：Review-1 / Review-2 双评审；合并、部署须 Human 另行授权。
- 不能假设的事实：不能假设已存在任何提交（delivery_sha 为 pending）；不能假设本交接授权 commit/merge/部署；不能假设 `status.json` 已被本任务更新；自检 mock DOM 仅识别 `[data-borrow-view-task]` 与 `.borrow-task-card[data-task-id]` 两个新选择器，其余行内选择器仍返回 null。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P3-market-borrow-view-implementation
执行结果: completed（完成）
结果摘要: 市场表借币列已实现「查看借币」按钮：仅 borrowing/paused 任务显示，1 对多按 created_at 最新/id 降序确定目标；点击/键盘触发跳借币任务视图、回任务页签、按目标状态筛选、平滑居中并 1.5 秒聚焦；click/keydown 均 stopPropagation 且保留原生激活；缓存两处同步点投影市场表且保留输入。P2 四条观察逐条处理。自检 176 项全过、0 失败。
产物: [reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md]
检查结果: [pass: 按钮只在 borrowing/paused 行出现于确认右侧，空/completed/deleted/异资产隐藏; pass: 跳转切视图/回任务页签/按目标状态筛选/scrollIntoView smooth center/1.5s 聚焦（含 reduced-motion 静态反馈）; pass: click 与 keydown 均 stopPropagation、无 preventDefault、不开行抽屉、零 borrow POST; pass: 整表重绘保留借币数量/次数输入; pass: node frontend/self-check.js 全量 176 项通过、0 失败（含白名单）; pass: 交接文件已建于确定性路径、delivery_sha pending、含源报告与 Human 简报]
阻塞项: [none]
本地北京时间: 2026-08-29 19:11:22 CST
下一步模型: Bookkeeper（gemini-3.7-flash，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P3-market-borrow-view-implementation.handoff.md；reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json；reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md；执行：核验本交接源区 SHA-256 与 base_sha、复跑 node frontend/self-check.js，推进 status.json 并准备 Review-1/Review-2 派单；关卡：Review-1/Review-2 双评审，合并与部署须 Human 另行授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 核验后追加）

## Errata (append-only)

None at task end.
