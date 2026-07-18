# Live Public Sample Analysis

Collection: `reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`

| Symbol | Spot exchangeInfo | Spot bookTicker | Futures bookTicker |
|---|---|---|---|
| AERGOUSDT | BREAK, margin=false | bid/ask 0 | positive bid/ask |
| XMRUSDT | BREAK, margin=false | bid/ask 0 | positive bid/ask |
| LITUSDT | BREAK, margin=false | bid/ask 0 | positive bid/ask |

The raw sample proves the contract-relevant fact: a symbol can remain present in spot
`exchangeInfo` while not being a currently tradable spot leg. It also proves that symbol presence
plus `isMarginTradingAllowed=false` is insufficient for route classification.

Collection used public unsigned GET endpoints only. No API key, credential, account data, order,
or side effect was involved.

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/05-live-sample-analysis.md
本地北京时间: 2026-07-18 12:23:14 CST
下一步模型: claude_glm
下一步任务: 使用已固化 raw sample 验证实现语义
