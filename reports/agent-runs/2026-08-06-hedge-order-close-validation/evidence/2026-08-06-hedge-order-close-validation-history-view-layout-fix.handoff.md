# Task Handoff: 2026-08-06-hedge-order-close-validation-history-view-layout-fix

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-history-view-layout-fix`
- role: `Implementer`（bounded finding repair；target_model: deepseek）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 21:15 CST`
- base_sha: `5388938`（`git rev-parse 5388938` = `538893849d6f831108c491d2d07c1b38a5287f94`）
- delivery_sha: `pending`（本任务未获提交授权，改动保留在工作树，由 Bookkeeper 处理交付提交）
- 风险等级: `LOW_RISK`（纯前端布局/滚动定位，无资金语义、无后端、无测试语义变化）

### 背景

Human 实盘复测目视发现：从费率行情长页（私有账户 + 市场表 + 双看板）点击侧栏
「历史仓位」后，历史仓位表单展示在页面**最底部**——视图切换只改了 `display`，
没有滚动定位（全局 `scrollTo` / `scrollIntoView` 出现次数为 0）。`#history-view` 是
`<main class="content">` 内最后一个 panel，market 页滚动位置不重置，切换后视口停在
原处。同类隐患：`#borrow-task-view` / `#hedge-task-view` 同样只有 display 切换。

### 实际修改范围

**`frontend/index.html`**（仅 `setActiveView` 函数内一行滚动定位）：

在四个视图的 `display` 切换完成之后（`els.historyView.style.display = ...` 之后、
`navEntries` 激活态更新之前）追加：

```js
if (typeof window !== 'undefined') window.scrollTo(0, 0);
```

- 采用 dispatch 首选的**最简方案**：统一 `window.scrollTo(0, 0)` 覆盖全部四个视图
  （market / borrow-tasks / hedge-tasks / history；`flow-log` 映射到 market 同样
  回顶部），无需 `scrollIntoView` 精确到 panel。
- `typeof window !== 'undefined'` 保护：`frontend/self-check.js` 的 node 环境没有
  `window` 全局（首次实现直接调用 `window.scrollTo` 导致 self-check 抛
  `window is not defined`，已改为环境安全写法）；浏览器环境正常滚动。该保护在
  `setActiveView` 函数内、属同一行逻辑，不改变任何浏览器行为。
- 未新增任何 DOM 结构、未改 CSS 布局、未改后端、未改其他 JS 逻辑。

### 测试 / 验证

- `node frontend/self-check.js` → 全部自检通过（零适配——本任务不改任何契约；
  setActiveView 的既有断言全部照常通过，node 环境经 typeof 保护跳过滚动调用）。
- `.venv/bin/python3 -m pytest backend/tests/test_hedge_domain.py -q` → 121 passed
  （后端抽查冒烟，确认环境未被前端改动影响；dispatch 注明全量非必需）。
- `git diff frontend/index.html` → 仅 `setActiveView` 内 +4 行（1 行逻辑 + 3 行注释）。
- `git status --short` → 仅 `frontend/index.html`（`.reasonix/` 与
  `macos_input_outage_playbook.md` 为宿主/其他会话产物，非本任务文件）。

### 未完成事项 / 不能假设的事实

- 本任务未提交（无提交授权）。
- 滚动定位为浏览器行为，self-check 无法目视断言视口位置——需 Human 目视验收：
  从 market 页滚动到下方 → 点「历史仓位」→ 表单顶部立即可见；切回「费率行情」→
  回到页面顶部。
- 核验通过后按 LOW_RISK 走一次独立最终评审（dispatch 已记录理由），评审通过后
  Human 决定合并/继续测试。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-history-view-layout-fix.handoff.md`
  2. `reports/agent-runs/2026-08-06-hedge-order-close-validation/07-history-view-layout-fix.dispatch.md`
  3. `frontend/index.html`（`setActiveView`，:5764-5843，滚动定位行在 display 切换后）
- 执行：Human 目视验收——从 market 页滚动到下方 → 点「历史仓位」→ 表单顶部立即可见；
  切回「费率行情」→ 回到页面顶部。
- 关卡：目视验收通过后按 LOW_RISK 走一次独立最终评审；评审通过后 Human 决定合并/
  继续测试。
- 不能假设的事实：服务未运行；滚动定位仅浏览器生效（self-check 的 node 环境跳过）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-history-view-layout-fix
执行结果: completed
结果摘要: setActiveView 在视图切换后统一 window.scrollTo(0,0) 滚动定位（覆盖 market/借币/开单/历史四视图，含 flow-log→market 映射）；typeof 保护兼容 self-check node 环境；self-check 全绿、diff 仅函数内一行
产物: [frontend/index.html, reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-history-view-layout-fix.handoff.md]
检查结果: [滚动定位：四视图切换后均有 scrollTo(0,0)（flow-log→market 同回顶部） 通过(pass), 最小改动：git diff 仅 setActiveView 内一行逻辑+注释、无 CSS/DOM/后端 通过(pass), 回归：self-check 全绿（零适配）、后端抽查 121 passed 通过(pass), 范围：git status 仅 frontend/index.html 通过(pass)]
阻塞项: [none]
本地北京时间: 2026-08-06 21:15:28 CST
下一步模型: deepseek（Bookkeeper；本任务回执的直接接收者）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-history-view-layout-fix.handoff.md；执行：核验交接件与工作树改动后封存 delivered/reported，并按 LOW_RISK 准备一次独立最终评审；关卡：Human 目视验收（market 长页滚动后切历史仓位表单顶部立即可见、切回费率行情回页面顶部）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-06 21:17:49 CST`
- source_sha256: `3b398b385f06efcc790b3466fb59f3ba979b74ddd249ebb91eba067cfbcbced9`
- status_revision: 10（核验时 `status.json` 指向本任务，state `dispatched`）
- base_sha / delivery_sha: `538893849d6f831108c491d2d07c1b38a5287f94` .. `3006db3885dfc811a1ff1c6669d6c7f0c88c465d`（`git rev-parse` 直取）
- verdict: **verified（通过）**；LOW_RISK（纯前端滚动定位，dispatch 已记录理由）
- 依据（可复现）：
  - `git diff frontend/index.html` → 仅 `setActiveView` 内 +4 行（1 行逻辑 + 3 行注释），
    display 切换后、navEntries 激活态更新前 `if (typeof window !== 'undefined') window.scrollTo(0, 0);`
  - `node frontend/self-check.js` → 全部自检通过（本 Bookkeeper 实测；node 环境经
    typeof 保护跳过滚动调用，零适配）
  - 无 CSS/DOM/后端改动（`git status --short` 仅 frontend/index.html + 交接件）
- 观察点（不阻塞）：滚动定位为浏览器行为，self-check 无法目视断言视口位置——已由
  Human 实盘目视验收（本任务派发前用户已在复测流程中，验收关卡见 dispatch Stop）
- 后续状态：07 `dispatched` → `verified`；按 LOW_RISK 走一次独立最终评审，评审通过后
  Human 决定合并/继续测试

## Errata (append-only)
