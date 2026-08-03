# Intake: Harness 任务交接件与证据落档

日期：2026-08-03

## Human 授权

- 已授权在 `stage/2026-08-03-harness-task-handoff-evidence-v1` 实施 R4 设计。
- 指定 `claude_glm`（Zhipu GLM）为实现者；Human 自行启动其终端。
- 本 stage 仅改 Harness 契约，不改产品代码、不部署、不触碰实盘、资金、凭据或
  `PROJECT_STATE.md`。
- 合并到 `main` 仍须在两层正式评审 ACCEPT 后另获 Human 授权。

## 计划依据

- 设计：`docs/planning/harness-task-handoff-evidence-design-2026-08-03.md`（R4）
- 独立计划评审：`evidence/01-deepseek-r4-plan-review.raw.md`
- 评审结论：DeepSeek 明确 `ACCEPT`；DeepSeek 与提案作者 Codex 属不同 provider。

## 本 stage 范围

1. 落实每任务交接件、评审者 create-only 例外和 Bookkeeper 同文件核验。
2. 维持既有控制台 `TASK_RESULT v2` 字段与闭合格式，规范其从交接件简报派生的内容。
3. 移除正常路径中 Human 在模型间复制原始回执的依赖，保留不可推进的
   `SOURCE_REPORT_MISSING` 故障降级。
4. 不引入黑板、全量 stage 汇总、终端逐字捕获或 `status.json` schema 变更。
