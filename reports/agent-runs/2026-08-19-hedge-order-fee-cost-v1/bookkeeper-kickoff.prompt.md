你是本阶段 Bookkeeper。Human 指定：窗口 `agy`，模型 `gemini-3.7-flash`（原文「gemini-3.7 Flash」），`bookkeeper_label=agy`。

立即只做开阶段，不要实现、不要评审、不要改业务代码、不要 merge/push/下单/重启服务/部署。

工作目录必须换成（主仓保持 main，不要在主仓切分支）：

/Users/ark/Desktop/ai code/funding_hedging-order-fee-cost-v1

当前分支：`stage/2026-08-19-hedge-order-fee-cost-v1`
intake 提交：`58fe08267946ebb3e5b5697c2a6f310d781495e1`

按这个顺序读：
1. AGENTS.md
2. reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/00-intake.md
3. reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md
4. reports/agent-runs/ACTIVE.json
5. PROJECT_STATE.md
6. agents/roles.md 的 Bookkeeper 节

然后：
- 创建本 stage 的 status.json（schema v2 顶层字段一套，不得增删键）。stage_id 必须等于目录名 `2026-08-19-hedge-order-fee-cost-v1`。bookkeeper=`gemini-3.7-flash`，bookkeeper_label=`agy`。所有 SHA 用 git rev-parse 实值。
- 把 reports/agent-runs/ACTIVE.json 写成指向本 stage。
- 第一份 dispatch 必须是 HIGH_RISK 跨 provider 只读计划评审，verdict 回到你准备实现包；不触碰 rework_count。评审者不能是设计作者 Grok/xAI，也不能是你自己评。建议 opus5（claude 窗口）或 Codex。
- 用中文向 Human 说明：阶段已打开、下一步是谁启动计划评审。

已拍板口径不要重开：四列冻价、持仓只加开仓费、历史加开+平、净盈亏这轮不扣手续费、不回补历史、缺数不当 0。细节以 10-design.md 为准。
