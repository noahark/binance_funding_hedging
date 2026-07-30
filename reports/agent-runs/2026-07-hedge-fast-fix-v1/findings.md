# Findings backlog — 2026-07-hedge-fast-fix-v1

格式：Human 报一条，记一条；修复后改状态。

| ID | 状态 | 风险 | 描述 | 修复摘要 |
|----|------|------|------|----------|
| F1 | fixed | LOW | 持仓均价 `formatMockPrice` 用 `toFixed(4)` 截断原生小数 | `formatHedgeDecimal` 字符串优先、去尾零；持仓表均价/数量走该路径 |
| F2 | fixed | LOW | 持仓方向无颜色区分 | 正向 `.positive`（绿），反向 `.negative`（红） |
| F3 | fixed | LOW | 开单价差率始终 0%：后端 `open_basis_rate` 写死 `"0"`，与均价精度无关 | 前端用 spot/perp 均价按方向现算展示（不改后端） |
| F4 | fixed | LOW | 借币确认 / 立即开单无二次确认 | 复用 hedge 确认弹框；确认前零 POST |
| F5 | fixed | LOW | 行情自动刷新整表重绘冲掉操作列输入 | `captureMarketOpInputs` / `restoreMarketOpInputs` |
| F6 | fixed | LOW | 立即开单创建慢时导航数字无反馈 | 创建中徽标 spinner，回显后恢复 running 计数 |
| F7 | fixed | LOW | 立即开单卡「立即成交所有」与启动功效重合 | 仅 `mode===smooth` 展示该按钮；立即开单隐藏 |

状态：`open` | `in_progress` | `fixed` | `wontfix` | `deferred`
