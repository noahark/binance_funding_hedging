# 方向综合 — Hedge Open Real API v1

## 综合结论（待用户批准）

本阶段交付真实 Portfolio Margin immediate 开仓的完整、受门控执行链：固定基础币数量、每秒一组并发双腿市价单、`orderId` 后的持续订单查询，以及可审计的累计均价与数量记录。

这不是 smooth/WebSocket 阶段，不做自动补腿、自动撤单替换、自动平仓、自动借币/还币或成交偏差修复。实现真实 PAPI POST adapter 不授权启用 live，也不授权第一笔真实订单。

本综合以用户在 2026-07-23 的最新执行政策为准；它覆盖原方向稿中“partial、残差或未决上一单必须立即阻断下一组”的建议。

## 已采纳的执行合同

### 1. 输入与数量

- 前端输入为 `single_amount`（每一组的基础币数量）和 `target_n`（计划发送的组数）。
- 后端用两市场有效 MARKET filters，以 Decimal 定点数向下取整出共同合法数量 `q_common`。若取整后不满足任一交易所 min/max/notional，拒绝该组，不发送 POST。
- 每个方向的两腿都发送同一个 `q_common`：

  | 方向 | PAPI margin | PAPI UM |
  | --- | --- | --- |
  | 正向 | BUY MARKET `quantity=q_common`，`NO_SIDE_EFFECT` | SELL MARKET `quantity=q_common` |
  | 反向 | SELL MARKET `quantity=q_common`，`NO_SIDE_EFFECT` | BUY MARKET `quantity=q_common` |

- 本阶段不使用 `quoteOrderQty`。它是 Binance 的接口能力，但不是本阶段的下单合同。

### 2. 一秒节拍与下单受理

1. 每个计划时点先取得当前 filters、账户/余额、持仓模式和限频等只读快照，并执行现有 Start/executor/rate-limit 门控。
2. 生成两个确定性 client order ID；在任何 POST 之前，把 attempt、快照、请求参数形状和两腿 ID 事务性写入 SQLite。
3. 同一组两腿并发提交。每一秒创建下一组，不因上一组尚在查询、实际成交量不同、partial 状态或 residual 而等待。
4. 一条腿返回 `orderId`，即记为该订单已被 Binance 受理；保存 `orderId` 并开始独立查询。

`target_n` 表示计划发送的组数，不因成交偏差或已知失败悄悄补发额外组。这样“次数”仍由操作者输入决定。

### 3. 查询、失败与暂停

- 有 `orderId` 的订单持续查询到 Binance 返回终态，并保存状态、实际基础币成交量、累计 quote 金额、手续费（若提供）和时间。
- HTTP 超时、断连或模糊响应不能直接算失败、更不能重发。必须先用已持久化 client order ID 查询，以排除“交易所已接受但响应丢失”。
- 交易所确认的终态拒绝/取消/过期，或按 client ID 确认订单不存在，才是**已确认失败**。
- 一组两腿均取得 `orderId`，视为一次已受理成功，重置连续失败计数；已确认失败组递增该计数。
- `consecutive_failure_pause_threshold` 是可配置变量，默认 **3**；达到 3 次已确认连续失败后暂停之后的开单。后续可改为 1 或 2，不改变数量和保证金的产品上限政策。
- 任何未知订单保持可见、可查询，不自动撤单、补单、平仓或修复。

### 4. 成交记录与均价

成交数量/价值不是当前调度门槛。两腿实际成交不完全相等是预期内的小偏差，只记录、不特殊处理。

每条腿持续累计：

```text
cumulative_base_qty
cumulative_quote_amount
weighted_average_price = cumulative_quote_amount / cumulative_base_qty
```

前端显示每组和累计的买卖数量、买卖均价、订单状态与可见 residual，供人工查看和后续打磨；不会由 residual 触发本阶段自动动作。

## 从旧策略借鉴的部分

`币安套费率策略，逐仓杠杆.js` 中可复用的业务思想是：下单返回 `orderId` 后再查询订单，并按累计成交量/成交额计算加权均价。

不继承旧脚本的顺序开两腿、超时撤单再市价补单、自动借币/还币或逐仓账户流程。这些行为与本阶段 Portfolio Margin、并发双腿和“无自动修复”边界冲突。

## 必须交付的工程边界

- F-003：按每个约束处理 `MARKET_LOT_SIZE`、`LOT_SIZE` 与零值禁用回退；spot/UM 各自序列化 Decimal。
- F-004：持久化并执行 Binance 限频；429/418 仍阻止继续发送，不能因一秒节拍绕过交易所限制。
- F-005：attempt 和两个 client ID 必须在 POST 前 durable commit；重启后能继续查询而绝不盲发重复订单。
- F-006：live 模式没有同步循环式 `fill-all`。计划任务由一秒 scheduler 执行；任何可能立即发送订单的手动入口必须经过同一 executor/Start 门控。
- 使用 regular Portfolio Margin、USDT、one-way position mode（`positionSide=BOTH`）；检测到 hedge mode 或账户不健康则拒绝发送，不在流程中切换账户模式。
- 自动化测试只用 fake/record transport。PAPI 没有可用于此合同的 testnet；任何真实 POST、private API 读取、凭据访问或第一笔 real task 都是后续单独的人类授权。

## 与 PRD 的对齐

用户于 2026-07-23 批准本方向并授权重构 canonical PRD。新的 PRD 已以固定基础数量 +
计划次数、无产品金额/次数/保证金上限、无自动重算次数为当前 immediate 合同；旧的
total-notional/rounds、2% uplift、可配置 notional cap 和 manual-close-first-live-open
门槛均不再适用。手动平仓仍是后续产品能力，但不是本阶段或首笔经人工授权的 real open
的前置条件。

## 方向面板证据与分歧处理

- Claude Opus 4.8、GLM-5.2、Kimi K3、GPT-5 Codex 的原稿均已保留在 `direction-drafts/`。
- Grok 无额度，已有 `grok-build.unavailable.md`，没有伪造其意见。
- 全体稿件同意 quantity 并发、Decimal/filter、POST 前持久化、client-ID 查询、真实 adapter 受门控。
- 原稿中“partial/单腿/unknown 立即暂停”和“此前未决 attempt 阻止下一组”的意见，因与用户的每秒节拍政策冲突而未采纳；未知响应仍必须查询，防止重复下单。

## 用户批准记录

用户于 2026-07-23 批准本综合进入详细设计，并授权 PRD 重构与删除旧的 Manual Close
Design Gate。本阶段按固定 `q_common`、每秒一组、`orderId` 查询、默认连续 3 次已确认
失败暂停、成交偏差仅记录的合同推进；真实启用与第一笔订单仍是独立人类动作。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md
本地北京时间: 2026-07-23 19:37:27 CST
下一步模型: bookkeeper
下一步任务: begin detailed stage design from the approved direction
