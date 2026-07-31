# Intake brief — 给 opus5（bookkeeper 接管）

- stage: `2026-07-31-hedge-task-inline-log-v1`
- from: claude_glm（前任 bookkeeper；实现阶段将以 implementer 身份回到 claude-glm 终端）
- 日期: 2026-07-31
- 状态: Human 已指定你（opus5）从 claude_glm 接管本 stage 的 bookkeeper。`status.json`
  已更新 `bookkeeper: opus5`（revision 2）。本 brief 与 `00-task.md`、`status.json`
  均**未提交**，留给你 intake 定稿后一并提交。

## 这个 stage 是什么

- **范围**：开单任务卡内嵌可展开日志（前端为主）+ 修复 F10（worker 退出条件与 done
  判定口径分裂，导致任务卡「重启不生效」）。两者同源——日志要展示的「进展 N/计划」
  口径正是 F10 的病根。
- **风险**：HIGH_RISK（读订单/attempt 数据 + 改调度/完成判定语义，AGENTS §8）。
- **base_sha**：`42de1aff364e7c979d2fbb5dc56f1dec65287cc7`（fast-fix 产物封存后的 HEAD）。
- 已由 claude_glm 起草：`00-task.md`（dispatch packet draft）、`status.json`。

## Human 已定的 model 分配（intake）

| 角色 | model | provider |
|---|---|---|
| bookkeeper | opus5（你） | anthropic |
| implementer | claude-glm | zhipu |
| review-1 | grok | xai |
| review-2 | codex | （codex） |

- **计划评审**（HIGH_RISK，§8，实现前必做）：须是与 implementer **不同 provider**（≠ zhipu）
  的独立只读终端。Human 未指定，**由你建议**。注意 §3 #4「author 不能 review 自己的交付」
  ——若你 intake 定稿了 packet，计划评审就不能再用 opus5，应建议第三方（如 kimi/moonshot，
  或由 grok/codex 的独立 session 兼任，只要 ≠ implementer 且未参与 packet 定稿）。

## Human 授权你决定的两件事

4. **ACTIVE.json 切换**：当前指向 fast-fix（`2026-07-hedge-fast-fix-v1`）。是否切到本
   stage、让 fast-fix 暂 idle？（两个 stage 并行在历史上出现过，但 ACTIVE.json 是单一
   active pointer，由你定。）
5. **packet 定稿**：`00-task.md` 的 Goal / Acceptance / F10 修法方向（A 或 B，见下）是否
   调整。

> F10 两个修法方向（findings.md 记录，由你定稿时择一）：
> - **A**：worker 退出线改用 `accepted >= target_n`（与 done 判定同口径），失败调度不再
>   永久消耗退出配额；
> - **B**：维持「scheduled = 计划次数」语义，但 scheduled 用尽且未达 accepted 时进明确
>   终态并在「启动」给反馈，而非静默重启无效。

## 你的下一步（bookkeeper 职责；AGENTS §4 / §5 / §6，roles.md Bookkeeper 段）

1. 按 §4 startup 读完权威文件：`AGENTS.md` → `ACTIVE.json` → `PROJECT_STATE.md` →
   本 stage `status.json` → `00-task.md` → `agents/roles.md` Bookkeeper 段。
2. Intake：决策 4、5；定 F10 方向；指定计划评审 provider；定稿 `00-task.md`。
3. 更新 `status.json`（revision 3）反映 intake 定稿；`next` 指向「Human 启动计划评审」。
4. 提交 stage 起始（`status.json` + 定稿 `00-task.md` + 本 brief）。`base_sha` 不变。
5. 准备「计划评审」只读终端的 prompt（指向 `00-task.md`）+ implementer（claude-glm）的
   dispatch；**不要自己启动终端**（§3 #2，由 Human 启动）。
6. 向 Human 报告：packet 定稿要点 + 计划评审/实现终端的启动建议，等 Human 决策。

## 关键背景（供你 intake 时参考）

- **F10 诊断**：`reports/agent-runs/2026-07-hedge-fast-fix-v1/findings.md`（F10 行）。根因
  `service.py:1116`（worker 退出看 `scheduled_attempt_count >= target_n`）vs
  `domain.py:1087`（done 看 `accepted >= target_n`）。
- **fake UI 原型**（已验收，真实版替换其假数据）：commit `5871791`。
- **本 stage 由 fast-fix `2026-07-hedge-fast-fix-v1` 承接而来**：fast-fix 仍在
  `awaiting_findings`（未关闭），其最新提交是 `42de1af`（即本 stage base）。
