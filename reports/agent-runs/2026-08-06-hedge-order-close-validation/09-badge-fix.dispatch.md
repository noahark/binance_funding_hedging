# 修复任务：dry-run 徽标警示色被 muted 覆盖（review-1 F-1，bounded repair）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景：review-1（opus5）审 `ee7ec4f..10f1f01` 四交付，唯一阻塞项 **F-1**（in-range）：
dry-run 徽标警示色未生效。事实链（Bookkeeper 已独立复核，三条证据全部属实）：

1. 元素初始 class：`frontend/index.html:1449`
   `<span class="badge muted" id="hedge-execution-badge">`
2. JS 只加不减：`:4508` `els.hedgeExecutionBadge.classList.toggle('warn', !liveMode);`
   —— 全文件无任何 `classList.remove('muted')`
3. CSS 声明顺序：`.badge.warn` 在 `:262`，`.badge.muted` 在 `:266`——
   同特异性（两个 class 选择器）下**后声明者胜出**，muted 覆盖 warn 全部三属性。

后果：dry-run/disabled 模式下徽标仍呈灰色，与 live 视觉无差别——dispatch 05
Goal 5 前半项（警示色）未达成。该 Goal 是「服务被误启动为 disabled 半小时、
记 4 笔假成交污染持仓口径（800/600 vs 真实 400/200）」事件的直接防复发措施，
防线在视觉主通道失效。按钮「（演习）」标注已生效（提示能力减半而非归零）。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-badge-fix`
- target_role: `Implementer`（bounded finding repair）
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 13
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

修复 F-1（一行核心改动）+ 防回归断言 + N-1 顺带（均极小，不扩范围）：

1. **主修复（推荐方案 a，最贴近意图）**：`:4508` 同处加同步互斥
   `els.hedgeExecutionBadge.classList.toggle('muted', liveMode);`
   —— live 时保留 muted（灰），dry-run/disabled 时移除 muted + 加 warn（警示色）。
   效果：dry-run 时元素 class 为 `badge warn`（无 muted），警示色生效；
   live 时 class 为 `badge muted`（无 warn），维持现状。
2. **防回归断言（self-check）**：扩展 `frontend/self-check.js` 的执行徽标测试
   （`:4808-4831`）——dry-run 时断言该元素 class **不同时包含** `muted` 与 `warn`
   （且含 `warn` 不含 `muted`），live 时断言含 `muted` 不含 `warn`；
   文本断言（dry-run/live 文案）保留不变。
3. **N-1 顺带（可选一行）**：`renderHedgeExecutionStatus` 的 `!doc` 早退分支
   （`:4497-4502`）同时 `classList.remove('warn')` + `add('muted')`，避免 settings
   加载失败后徽标残留上一次模式配色。若实现者认为该分支无必要改，可在交接件说明，
   不阻塞。

**禁止**：改 CSS 声明顺序方案（方案 b 会影响其他同时带 muted+warn 的徽标，需全局
确认——本任务不做）；改后端；改前端其他逻辑。

## Allowed Files

可修改：

- `frontend/index.html`（仅 `renderHedgeExecutionStatus` 内 1-2 行 class 操作）
- `frontend/self-check.js`（仅执行徽标测试块内新增 class 断言）

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md`（F-1 事实与修复要求）

禁止：

- 未授权提交、移动 HEAD、访问凭证、对实盘发单/划转/设杠杆；
- 改 CSS 声明顺序、改后端、改其他前端逻辑、改测试语义。

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-badge-fix.handoff.md`
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
9. review-1 handoff（`evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md`，F-1 见 §REWORK 发现）
10. `frontend/index.html`（`:1449` 元素、`:4494-4515` `renderHedgeExecutionStatus`）
11. `frontend/self-check.js`（`:4808-4831` 执行徽标测试）

## Acceptance Checks

1. **F-1 修复**：dry-run/disabled 时 `#hedge-execution-badge` class 不含 `muted`、
   含 `warn`（警示色生效）；live 时含 `muted`、不含 `warn`（灰，维持现状）。
2. **防回归**：self-check 新增断言覆盖上述两种状态的 class 互斥；
   `node frontend/self-check.js` 全绿。
3. **回归**：`python3 -m pytest backend/tests -q` 不受影响（可抽查，
   全量非必需——review-1 已复跑 1467 passed，本任务不碰后端）。
4. **最小改动**：`git diff` 仅 `frontend/index.html` 1-2 行 +
   `frontend/self-check.js` 断言行；无 CSS 顺序改动、无后端改动。
5. **范围**：`git status --short` 仅上述两文件（+ 交接件）。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：修复后回 review-1 复审（`AGENTS.md` §8：review-1 REWORK 返回 review-1；
复审范围仅 F-1 修复 + N-1，其余交付已通过无需重验）；或 Human 行使「已知风险
暂不修、允许合并」授权（需记录问题事实、影响、接受理由、观察方式、复看条件）。
