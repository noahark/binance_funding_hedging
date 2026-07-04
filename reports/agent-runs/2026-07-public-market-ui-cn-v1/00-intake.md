# Stage Intake: 2026-07-public-market-ui-cn-v1

前置：`2026-07-public-market-impl-v1` 与 `2026-07-public-market-bstock-alias-v1`
均已获用户最终验收（accepted，commit `6d8c0c4`）。

## 来源

用户 2026-07-04 提出 5 点产品口径（GPT 给出建议稿，Fable5 完成 review 与实证，
用户确认后指示开工）：

1. 路由分类含义确认（无代码改动，仅口径确认——已确认）。
2. `premiumIndex.lastFundingRate` 语义：**已实证**为本周期实时预估值（将于
   `nextFundingTime` 结算收取，结算前漂移），不是已结算历史。证据已抓取落盘：
   `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
   （周期中段 ETHUSDT/SOLUSDT 与已结算历史不等；离线验证脚本 PASS）。
3. 前端「最近更新的资金费率」+「下一次结算时间」合并为「资金费率/结算时间」
   一列，格式 `+0.01% / 16:00`（北京时间 HH:mm，裁尾零）。
4. 「UI 标记」列改中文提示标记；`MARGIN_PUBLIC_UNVERIFIED`（全行恒出现）降为
   页面级说明，避免 648 个重复 badge。
5. **UI 设计以中文为主**（用户长期决策）：仅保留必要技术词（USDT、bStock、
   API 等），枚举值不得英文直出。

## 本阶段做什么

- Task A（claude_glm）：合约 warning 语义修订——`CONTRACT_WARNINGS[1]`（backend）
  与 `docs/api/public-market-contract.md` 对应段落，从「语义未证实」升级为
  实证措辞（证据即上述 api-samples，H_intake 已随本阶段落盘）。
- Task B（kimi）：前端中文化 + 费率/结算时间合并列 + 提示标记降噪 +
  warnings 展示改中性「数据说明」样式。
- Task C（controller）：集成验证，无产品代码。

## 设计与拆分作者

designer / breakdown author：**anthropic / claude-fable-5**（本阶段可达；
此前各阶段的「Fable5 unavailable」记录自 2026-07-04 起不再适用）。
方向依据：用户本轮对话中的明确决策（5 点口径 + 开工指令），无需新方向盘。

本地北京时间: 2026-07-04 12:55 CST
下一步模型: Claude-GLM (controller)
下一步任务: 按 00-task.md / controller-start-prompt.md 执行 H_A 起的交付流程。
