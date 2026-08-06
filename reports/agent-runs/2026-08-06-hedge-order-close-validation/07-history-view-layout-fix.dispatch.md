# 实施任务：历史仓位视图切换后无滚动定位（表单落在页面底部）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景（Human 实盘复测目视发现，2026-08-06）：
从费率行情页（长页，含私有账户 + 市场表 + 双看板）点击侧栏「历史仓位」后，
历史仓位表单展示在页面**最底部**——视图切换只改了 `display`，**没有滚动定位**：
`frontend/index.html` 全局 `scrollTo` / `scrollIntoView` 出现次数为 **0**。
`#history-view` 是 `<main class="content">` 内最后一个 panel（`:1481`），market 页
滚动位置不重置，切到历史仓位时视口停在原处，表单在底部不可见/需手动滚动。

同类隐患：`#borrow-task-view` / `#hedge-task-view` 同样只有 display 切换，
从长页滚动到下方再切换也会出现同类问题（Human 暂未报告，一并修）。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-history-view-layout-fix`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 10
- required_skill: `agents/skills/minimal-change-engineer.md`
- 风险等级: `LOW_RISK`（纯前端布局/滚动定位，无资金语义、无后端、无测试语义变化；
  dispatch 记录理由：本项不含 §8 HIGH_RISK 任何类别）

## Goal

切换视图时把视口滚动到**目标视图顶部**，使「历史仓位」等独立面板在点击侧栏后
立即可见。最小实现：

1. `setActiveView`（`frontend/index.html:5764`）在 `display` 切换之后、
   `navEntries` 激活态更新前后任一位置，追加滚动定位：
   - 切到 `history` → `els.historyView.scrollIntoView({ block: 'start' })`
     （或 `window.scrollTo(0, 0)` 等价方案，二选一，实现者自选）；
   - 切到 `borrow-tasks` / `hedge-tasks` → 同样滚动到对应视图顶部
     （`els.borrowTaskView` / `els.hedgeTaskView`，或统一 `window.scrollTo(0, 0)`）；
   - 切回 `market` → 同样滚动到页面顶部（`window.scrollTo(0, 0)`）。
2. **不新增任何 DOM 结构、不改 CSS 布局、不改后端**——纯一行/几行 JS。
3. 若统一用 `window.scrollTo(0, 0)` 即可覆盖全部四个视图（market 长页也回到顶部），
   这是最简方案，优先；`scrollIntoView` 仅在需要「精确到某 panel 顶部」时使用。

## Allowed Files

可修改：

- `frontend/index.html`（仅 `setActiveView` 内滚动定位行）

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

禁止：

- 未授权提交、移动 HEAD、访问凭证、对实盘发单/划转/设杠杆；
- 改 CSS 布局、改 DOM 结构、改其他 JS 逻辑；
- 为省事删减测试覆盖（本任务无新增测试，靠 self-check + 目视）。

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-history-view-layout-fix.handoff.md`
（Bookkeeper 预检 `test ! -e` 通过，路径不存在；已存在则任务失败）

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `frontend/index.html`（`:5764-5838` `setActiveView`、`:1481` `#history-view`、
   `:1191` `#market-view`、`:1378` `#borrow-task-view`、`:1431` `#hedge-task-view`）

## Acceptance Checks

1. **滚动定位**：`setActiveView` 内对四个视图（market / borrow-tasks / hedge-tasks /
   history）切换后均有滚动定位（`scrollTo(0,0)` 或对应 view `scrollIntoView`）；
   切到 `history` 后视口顶部即表单头部。
2. **最小改动**：`git diff` 仅 `setActiveView` 函数内几行；无 CSS/DOM/后端改动。
3. **回归**：`node frontend/self-check.js` 全绿（本任务不改契约，应零适配通过）；
   全量 `python3 -m pytest backend/tests -q` 不受影响（可抽查，非必需）。
4. **范围**：`git status --short` 仅 `frontend/index.html`（+ 交接件）。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：Human 目视验收——从 market 页滚动到下方 → 点「历史仓位」→ 表单顶部
立即可见；切回「费率行情」→ 回到页面顶部。核验通过后按 LOW_RISK 走一次独立
最终评审（dispatch 已记录理由），评审通过后 Human 决定合并/继续测试。
