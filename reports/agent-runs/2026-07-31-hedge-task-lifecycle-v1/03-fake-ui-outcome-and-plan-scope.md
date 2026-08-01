# 03-fake-ui-outcome-and-plan-scope —— fake UI 收口与方案阶段范围

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- 记录人：opus5（bookkeeper），2026-07-31
- 上游：`02-scope-decisions.md`（D1-D8）。本文件记 D9-D12，不重述 D1-D8。

## 1. fake UI 的收口方式

| # | 决策点 | Human 的选择 |
|---|---|---|
| D9 | fake UI 是否继续迭代 | **不再迭代**。Human 已查看交付 `63f5007` 的预览并认可展示形状，未提出形状修改。 |
| D10 | fake UI 是否跑那次 LOW_RISK 独立评审 | **不跑，当设计探针收**。代码留在分支 `stage/2026-07-31-hedge-task-lifecycle-v1`，**不单独合并 `main`**；真实实现将覆盖它，最终随真实交付一起过完整评审。 |

按 `AGENTS.md` §3 #7，未取得 `ACCEPT` 的交付即为非接受状态。fake UI 因此**形式上未获评审接受**，其身份是设计探针而非功能交付；它的价值（确定展示形状）已经取得，不需要也不应当单独进入 `main`。`fake-ui-positions-and-cards-v1` 的 `current_task.state` 停在 `verified`（Bookkeeper 核验通过），不再推进到评审。

先例：上一次同类设计探针 `5871791`（F10 任务卡内嵌日志 fake 原型）同样由 Human 直接作为设计探针接受，未走独立评审。

### 1.1 fake UI 交付的固定引用

- 交付 SHA：`63f5007`（`base_sha..delivery_sha` = `87ff428..63f5007`）
- 展示形状基准：该提交的预览区块 **即为真实实现的展示形状参照**
- 实现报告：`20-fake-ui-implementation.md`，其 §9 的接线风险清单是方案阶段的必读输入
- 已核验事实：两个真实渲染函数逐字未变、51169 文案与后端模板精确相等、`node frontend/self-check.js` EXIT=0 / 128 PASS、预览零网络请求

## 2. 真实实现的新增要求

| # | 决策点 | Human 的选择 |
|---|---|---|
| ~~D11~~ | ~~同一币种先正向后反向单独成案~~ | **已由 D13 撤销，见下。** |
| **D13** | 同币双向是否在本轮处理 | **移出本轮范围**（2026-07-31）。Human 将来通过「开单前校验当前持仓状态，若为反向则改走平仓逻辑」从**源头**消除该场景，因此不需要在展示层为它设计对账方式。 |

D13 取代 D11。原 D11 出自 Human 对「是否单独画一个 fake 场景」的回答（选「单独一个场景」），Bookkeeper 当时将其转写为真实实现的独立议题；Human 随后明确该问题不在本轮范围。**以 D13 为准。**

### 2.0 D13 的已核实前提

`service.create_task`（`service.py:523`）只校验 `coin` 与 `direction` 各自合法，**没有任何同币冲突检查**；`hedge_open_task` 表也无相关唯一约束。因此同币双向**在当前代码上是可达的** —— 今天就能给同一个币同时建正向与反向两张任务。Human 计划中的「反向开单改走平仓」校验落地后，该场景才从源头消失。

在此期间的展示口径**不作为设计问题处理**，直接套用已定的 D7（「都显示，标清楚」）：若出现，两行照实并列，**不做净额合并、不告警、不触发任何自动动作**。这不是新增范围，是把既有决策应用到一个情况上。

### 2.1 由 D13 派生的后续项（本轮不做）

- `[FUTURE]` 开单前校验当前持仓状态：若新任务方向与现有持仓相反，改走平仓逻辑而非开仓。Human 2026-07-31 提出，需独立 stage。它同时是同币双向的根治手段。该项涉及订单路径，属 `HIGH_RISK`。

### 2.1 多次开单的已核实事实（供方案阶段直接引用，不要重挖）

参考脚本 `币安套费率策略，逐仓杠杆.js` 的 `getOpenOrderInfo`（:3393）在同一币种再次开单时：合约腿与现货腿**各自按成交量加权平均**重算均价，数量直接相加，本金 `moveAccount` 累加，一个币只保留一条记录（`BINANCE_OPEN_ORDER_INFO[symbol]`，键只有 symbol，方向存在记录内部）。

本项目 `store.aggregate_positions`（`store.py:1934+`）**已经在做等价的累加，且做法更稳**：不在开单时改写记录，而是每次读取时从原始 attempt/leg 重新累加（`spot_avg = Σ名义额 / Σ数量`），并带 `spot_avg_price_incomplete` / `perp_avg_price_incomplete` 标记位；且它跨任务卡合并，同一币种开三张卡仍只出一行。

因此**「累加」本身不是缺口**。方案阶段需要处理的是脚本没有、本项目会撞上的三处：

1. **同币双向**（D11）：本地按 `(coin, direction)` 分桶出两行，币安 UM 只有一个净持仓 —— 两行如何挂到一个真实仓上。
2. **手工部分平仓后的偏离**：本地累加数量**只增不减**（脚本亦然）。手工卖掉一半现货后，本地记录仍是原数而真实余额减半。合并表恰好能暴露该差额，但差额如何呈现是新问题。
3. **分批开单中途失败**：十次计划成交七次时均价是这七次的加权（当前行为正确），但「计划 N / 成功 M」与均价的关系需在同一行内可读，避免被误读为十次的均价。

## 3. 方案阶段的角色路由

| # | 决策点 | Human 的选择 |
|---|---|---|
| D12 | 四项完整实现方案由谁出（D3 未覆盖此格） | **`claude_glm`（zhipu_glm）** |

理由（Human 采纳）：它刚完成 fake UI，对展示形状与接缝的认知最新最具体；其视角盲点由跨 provider 的 `deepseek` 计划评审拦截（§8 对 HIGH_RISK 的强制要求）；后续 review-1（`grok`/xai）与 review-2（`codex`/openai）**均未参与设计**，`agents/roles.md` Isolation 对「最终评审者尽量未参与设计」的偏好得以保持 —— 这一点是选它而非 `codex` 出方案的关键。

本 stage 完整路由（D3 + D12）：

| 环节 | 模型 | provider |
|---|---|---|
| 方案设计 | `claude_glm` | zhipu_glm |
| 计划评审（HIGH_RISK 强制，跨 provider 只读） | `deepseek` | deepseek |
| 实现 | `claude_glm` | zhipu_glm |
| review-1 | `grok` | xai |
| review-2 | `codex` | openai |

`grok` 担任 review-1 是 Human 批准的备选（Kimi 额度不可用），见 D3。

## 4. 下一步

准备 `plan-hedge-task-lifecycle-v1.dispatch.md`（Planner，`claude_glm`），产出 `10-design.md` / `11-adr.md` / `12-development-breakdown.md`，随后交 `deepseek` 计划评审。
