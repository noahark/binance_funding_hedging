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
| F8 | fixed | LOW | 借币 `-2019` 无中文说明，只见 known_rejection | `binance_error_codes` 增加 2019→保证金不足（仅展示映射） |
| F9 | fixed | LOW | 总资产估值用钱包毛额，缺权益/负债/风险 | 60s `GET /papi/v1/account` + 概览卡：权益/负债/杠杆/uniMMR 等 |
| F10 | deferred | HIGH | 任务卡「重启不生效」：worker 以「已调度次数 ≥ 计划次数」为退出线（`hedge_open_tasks/service.py:1116`），失败的尝试永久吃掉调度配额；而 done 判定看「成功受理 ≥ 计划次数」（`hedge_open_tasks/domain.py:1087`）。两口分裂→失败后卡在 running + worker 已退出，`post_start` 重启又撞同一退出线，无效。且 `计划次数 < 暂停阈值`（如本例 1 < 3）时永远触发不了连续失败暂停，任务悬空既不 done 也不 paused。实例 COOKIEUSDT：计划 1 / 已调度 1 / 已受理 0 / 连续失败 1 | 未修（本 fast-fix 不动 HIGH_RISK）。待立独立修复 stage 走 §8 review-1+review-2；方向 A = worker 退出改用 `accepted` 口径，方向 B = scheduled 用尽未达 accepted 时进明确终态且「启动」给反馈而非静默重启 |

状态：`open` | `in_progress` | `fixed` | `wontfix` | `deferred`
