# Task Handoff: P2-market-borrow-view-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `P2-market-borrow-view-plan-review`
- role: `Reviewer` (pre-implementation plan review, read-only)
- target_model: `opus5` / provider `anthropic`
- stage_id: `2026-08-29-market-borrow-view-button-v1`
- created_at: `2026-08-29 18:41:47 CST`
- base_sha: `7bb70a74e4e97a5c0b136bc6146167a360f0debb`
- delivery_sha: `none`

### Verdict

`ACCEPT（接受）`

方案为最小充分改动，可在当前前端接缝上无歧义执行。派单的八条验收检查全部 `pass`。计划对 `frontend/index.html` 现状的每一条引用均经源码逐条核对，无失实描述。附四条非阻塞观察（见下），不构成返工。

### Isolation

- P1 作者 `gpt-5.6-sol` / `openai`；本评审 `opus5` / `anthropic`，跨供应商且非本方案作者。
- 全程只读；唯一写入为本 create-only 交接文件。未修改计划、前端源码、自检、`status.json`、`PROJECT_STATE.md`、schema、配置或 git 历史；未提交、合并、部署，未启动下一模型。

### Fixed target verification (前置)

- `shasum -a 256 reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`
  → `eeea31bff46dac3b65b6ecdff4d8a4aef7f29d79cc51bd90570a8bd7e9f69ab4`，与派单期望**逐字符相等**。
- `git rev-parse HEAD` → `7bb70a74e4e97a5c0b136bc6146167a360f0debb`，与派单 `Repository baseline` 及 `status.json.base_sha` 一致。
- `test ! -e .../evidence/P2-market-borrow-view-plan-review.handoff.md` → 评审开始前成功（create-only 前提成立）。
- `status.json`：`revision 2` / `phase plan_review` / `current_task.id P2-market-borrow-view-plan-review` / `state dispatched`，与派单 `status_revision: 2` 一致。
- 工作区存在未提交的 stage 文件（`ACTIVE.json` 改动、本 stage 目录未跟踪）。计划文件本身未进入 git，故本次评审按派单以 SHA-256 锁定评审对象、以 committed `HEAD` 锁定代码基线，未移动 `HEAD`，符合 `AGENTS.md` §3 规则 6 对只读评审的约束。

### Verified code facts (逐条核对计划 §2 的引用)

| 计划断言 | 核对位置 | 结论 |
|---|---|---|
| `renderBorrowOpCell(row)` 在 `.borrow-op-inputs` 内渲染两输入 + `data-borrow-confirm` 按钮 | `frontend/index.html:3662-3680` | 属实 |
| `attachRowHandlers(tr)` 整行绑定抽屉 click/keydown，真实 DOM 分支以 `typeof tr.querySelector === 'function'` 守卫 | `frontend/index.html:3682-3712` | 属实 |
| `loadBorrowTasks()` 替换缓存后**市场视图下只更新导航数字**、不重绘市场表 | `frontend/index.html:5050-5064` | 属实（源码注释同义） |
| `mutateBorrowTask()` 落缓存后只重绘任务列表 | `frontend/index.html:5143-5158` | 属实 |
| `setActiveView('borrow-tasks')` 重置 `borrowTaskFilter='borrowing'`、先用缓存渲染再异步重拉、不强制改回任务页签 | `frontend/index.html:7848-7862` | 属实 |
| `sortTasksNewestFirst()` 为 `created_at` 降序、同值 `id` 降序 | `frontend/index.html:5382-5391` | 属实，与 D1.2 表述逐字吻合 |
| `renderTable()` 经 `captureMarketOpInputs()`/`restoreMarketOpInputs()` 保留输入 | `frontend/index.html` 同名函数存在 | 属实 |
| `isBorrowOpDisabledRow(row)` 短路输出 `—` | `frontend/index.html:3657-3665` | 属实，新按钮不会出现在禁用行 |
| `paused` 是现有合法筛选值 | `BORROW_TASK_FILTERS` `frontend/index.html:4943-4949` | 属实（含 `all/borrowing/paused/deleted/completed`） |
| `findBorrowTask(id)`、`setBorrowTab`、`setBorrowTaskFilter`、`renderBorrowTaskCard`、`escapeHtml`、`els.borrowTaskList` 均已存在 | `5015` / `5625` / `5357` / `5420` / `2148` | 属实，无需新建接缝 |
| CSS 变量 `--brand` `--brand-soft` `--line` `--surface-2` 可用 | `frontend/index.html` 变量定义 | 属实 |
| 自检既有「操作单元格两输入一按钮」断言存在，需被更新 | `frontend/self-check.js:3850,3876` | 属实，计划 §4 定位准确 |

补充核实两项计划未明写但影响判断的事实，均**支持**计划成立：

1. **任务 ID 确为字符串**：`mutateBorrowTask` 以 `typeof doc.id === 'string'` 守门（`frontend/index.html:5150`）。故 D1.3 把 ID 写入 DOM 属性、D4.1 再经 `findBorrowTask()`（内部 `t.id === id` 严格相等）回查，不存在字符串/数字比较失配。
2. **D3 的两个同步点确实覆盖全部现有可达路径**：市场行创建走 `createBorrowTask()` → `mutateBorrowTask()`（`5215-5229`），`startBorrowTask`/`pauseBorrowTask` 同样经 `mutateBorrowTask`；而 `ingestSnapshot()` 的 60s tick 仅在 `activeView === 'borrow-tasks'` 时重拉任务（`7983-7986`），市场视图下 `loadBorrowTasks()` 基本只在启动时执行一次。因此「启动竞态」由 `loadBorrowTasks` 同步点覆盖、「创建/暂停/完成」由 `mutateBorrowTask` 同步点覆盖，二者共同闭合，且不会引入周期性整表重绘。
3. `scrollIntoView` 目前在 `frontend/index.html` 与 `frontend/self-check.js` 中均为 **0 处**出现。计划 §4 已预先要求为 mock DOM 补 `scrollIntoView` 参数记录、`classList` 与任务卡属性查询，前瞻正确。

### Acceptance checks

1. `pass` — 显示谓词严格为 `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`（D1.1）；`completed`/`deleted`/未知状态/其他资产/空列表均隐藏，D1.3 无匹配返回 `null` 且只在有任务时生成按钮。
2. `pass` — D2 将按钮置于确认按钮右侧，仅新增 `.borrow-op-actions` 弹性容器，不改表格列数、输入语义；`isBorrowOpDisabledRow` 行继续只显示 `—`（见观察 A 的措辞说明）。
3. `pass` — D1.2 直接复用 `sortTasksNewestFirst()` 取首个，`created_at` 降序、同值 `id` 降序，与任务页现行口径同源，未引入第二套排序。
4. `pass` — D4 固定顺序覆盖视图重置、日志页签恢复（`setBorrowTab('tasks')`）、按目标状态筛选（不使用更宽的 `all`）、异步重绘（焦点 ID 跨重建）、安全属性比对查卡（不拼 CSS selector）、精确 `scrollIntoView({ behavior: 'smooth', block: 'center' })`、1.5s 聚焦及 reduced-motion 静态反馈。
5. `pass` — D5 要求 click 与 keydown 均在按钮自身首句 `stopPropagation()`，且明确**不调用** `preventDefault()`，保留原生 Enter/Space 激活；父 `.borrow-op-cell` 既有隔离保留。
6. `pass` — D3 复用 `renderTable()` 既有输入捕获/恢复完成投影，无新增 API、轮询、schema、存储、执行器、订单、借币或资金行为（见观察 B 的效率说明）。
7. `pass` — §5 八条用例落在真实接缝上：显示/隐藏、确定性目标、缓存投影及时性、执行中与暂停中跳转、日志页签恢复、滚动/聚焦生命周期、运行时事件隔离（实际调用 handler 并断言 `stopPropagation` 被调用、断言无 borrow POST），非仅子串比对；§4 已列出 mock DOM 需补能力，用例可执行。
8. `pass` — §1 边界、§4 文件清单、§6 验收口径、§7 停止点与后续路由（`ACCEPT` 后方可由 Bookkeeper 派 `kimi` 实现，允许文件仅两个前端文件与其交接）均明确且最小。

本评审未引入任何需经 `AGENTS.md` §1 Scenario Admission 的假设性阻塞情形。

### Non-blocking observations (不构成返工，实施时自行处理即可)

- **A. D2 示例 HTML 缺少父层级。** 现状确认按钮是 `.borrow-op-inputs`（`display:grid; justify-items:start`，`frontend/index.html:1120-1124`）的第 5 个 grid item。D2 的代码块只给出 `.borrow-op-actions` 及其两个子按钮，未画出它应嵌在 `.borrow-op-inputs` 之内。按 D2 正文「把原来的单个确认按钮**包进**一个新容器」且「两个输入、预览和错误容器均不变」，唯一自洽解读是原地包裹（新容器成为该 grid item，内部 flex 横排），布局成立。建议实现时按此解读，勿将容器提到 `.borrow-op-inputs` 之外，否则按钮会脱离输入组并落到预览/错误容器之前。
- **B. 正常路径下市场表会重绘两次。** `mutateBorrowTask()` 末尾 `await loadBorrowTasks()`（`frontend/index.html:5156`），若两处同步点都调 `renderTable()`，一次创建/暂停将触发两次整表重绘。D3 保留 mutation 侧同步点的理由（GET 失败时 POST 权威状态仍需投影）成立，属 fail-closed 取舍，不影响正确性；实现时可在不牺牲该兜底的前提下去重。
- **C. 措辞。** §4 写 `window.__appHelpers`，实际接缝为 `globalThis.__appHelpers`（`frontend/index.html:9574`）。浏览器内等价，但自检运行于 node，实现与自检应以 `globalThis` 为准。
- **D. 跳转时存在一次瞬时置顶。** `setActiveView()` 内含 `window.scrollTo(0, 0)`（`frontend/index.html:7817`）。D4 步骤 3 之后再执行步骤 6 的平滑滚动，用户将看到「瞬间回到顶部 → 平滑滚向目标卡」。顺序无误且视觉可接受（滚动过程本身即位置提示），计划未描述该交互，实现与自检知悉即可。

### Unfinished / authority boundary

- 本任务只产出计划评审结论，无实现、无提交、无 `delivery_sha`。
- 仅 Bookkeeper（`gemini-3.7-flash`，`agy` 窗口）可核验本交接并推进 `status.json`；本评审无权写入状态、派发实现或启动任何模型。
- `ACCEPT` 只解锁「准备实现派单」，不授权实现、commit、merge、部署或任何借币/订单/资金动作。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md`；`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md`；`reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json`
- 执行：Bookkeeper 核验本交接源区 SHA-256、`base_sha` 与 `status.json` 一致性及 `ACCEPT` 结构完整性，随后把 `current_task` 由 `dispatched` 推进为已核验，并准备由 `kimi` 执行的前端实现派单（允许文件仅 `frontend/index.html`、`frontend/self-check.js` 与该实现任务的交接文件）。
- 关卡：实现交付后仍须走本 stage 既定的 Review-1 / Review-2；实现派单须要求实现者对上列四条非阻塞观察逐条给出处理说明（采纳或说明理由），但它们不阻塞派发。
- 不能假设的事实：不能假设已有任何前端代码改动；不能假设 `delivery_sha` 存在；不能假设本评审授权提交、合并、部署或实盘操作；不能假设 Reviewer 有权改 `status.json`。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P2-market-borrow-view-plan-review
执行结果: completed（完成）
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md
修复要求: none
结果摘要: 计划 SHA-256 与基线 7bb70a7 均精确匹配。方案对前端现状的每条引用已逐条比对源码，无失实；八条验收检查全 pass，为最小充分且可无歧义执行的改动。附四条非阻塞观察（DOM 层级措辞、双同步点重复重绘、globalThis 措辞、跳转瞬时置顶），不阻塞实现。
产物: [reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md]
检查结果: [pass: 谓词严格且终态/异资产/空列表均隐藏; pass: 按钮位于确认右侧且不改列数与禁用行; pass: 1对多复用 sortTasksNewestFirst 无第二套排序; pass: 跳转覆盖页签恢复/状态筛选/异步重绘/安全查卡/平滑居中/1.5s 聚焦与 reduced-motion; pass: click 与 keydown 均 stopPropagation 且保留原生激活; pass: 缓存投影复用 renderTable 且零后端零轮询; pass: 自检八用例落在真实接缝且非子串假绿; pass: 范围/文件/停止点/后续路由最小明确]
阻塞项: [none]
本地北京时间: 2026-08-29 18:41:47 CST
下一步模型: Bookkeeper（gemini-3.7-flash，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md；reports/agent-runs/2026-08-29-market-borrow-view-button-v1/market-borrow-view.plan.md；reports/agent-runs/2026-08-29-market-borrow-view-button-v1/status.json；执行：核验本交接并推进 status.json，准备由 kimi 执行、仅限 frontend/index.html 与 frontend/self-check.js 的实现派单；关卡：实现交付后仍须走既定 Review-1 / Review-2
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-29 18:44:34 CST`
- verifier: `gemini-3.7-flash` (Bookkeeper, `agy` window)
- source_sha256: `f0e3c79cfed030a402392b7060621b6ce207b5e5cc98abd4d9f405c69b5257c3`
- matched_status_revision: `2`
- next_status_revision: `3`
- review_verdict: `ACCEPT`
- review_problems: `reports/agent-runs/2026-08-29-market-borrow-view-button-v1/evidence/P2-market-borrow-view-plan-review.handoff.md` (4 non-blocking observations)
- review_repair_requirements: `none`
- verification_verdict: `VERIFIED_PASS`
- checks:
  1. Base SHA `7bb70a74e4e97a5c0b136bc6146167a360f0debb` matches git HEAD and status.json.
  2. Plan review conducted by cross-provider reviewer `opus5` (`anthropic`) in fresh read-only session.
  3. Plan artifact `market-borrow-view.plan.md` exact SHA-256 `eeea31bff46dac3b65b6ecdff4d8a4aef7f29d79cc51bd90570a8bd7e9f69ab4` verified.
  4. Explicit `ACCEPT` review conclusion returned with all 8 acceptance checks passing.
  5. 4 non-blocking observations recorded for Implementer attention during P3.
  6. Handoff file created at deterministic path with complete source report, Human brief, and valid marker.

## Errata (append-only)

None at task verification.
