# 00-intake：2026-08-19-hedge-order-fee-cost-v1

Human 2026-08-19 要求正式开阶段：把对冲成交的交易手续费按成交当时价格冻成成本，展示在持仓表和历史仓位。本文件是 Planner（Grok 4.6 / xAI）写给 Bookkeeper 的开阶段包。设计正文只在 `10-design.md`。

## 授权与身份（Human 当场指定）

| 项 | 决定 |
|---|---|
| Bookkeeper 模型 ID | `gemini-3.7-flash`（Human 原文「gemini-3.7 Flash」） |
| Bookkeeper 窗口 | `agy`（`bookkeeper_label=agy`，不是 pane ID，不是 `-review`） |
| 设计作者 | Grok 4.6（本会话，provider `xai`）。Bookkeeper 不得改写已拍板口径，不得自己实现 |
| 工作树 | `/Users/ark/Desktop/ai code/funding_hedging-order-fee-cost-v1` |
| 分支 | `stage/2026-08-19-hedge-order-fee-cost-v1` |
| 打开时 HEAD | `6ba28b0896eb872424655503365c3864541b0e8d`（即本分支起点；`base_sha` 以你开阶段时 `git rev-parse HEAD` 为准） |
| 主仓 | `/Users/ark/Desktop/ai code/funding_hedging` 保持 `main`。**不要**在主仓切分支 |
| 下单 / 凭据 / 重启服务 / 部署 / merge / push | **禁止**，除非 Human 另授 |
| 风险类 | **HIGH_RISK**（账务含义、成交写入、持仓/历史净成本展示）。实现前必须跨 provider 只读计划评审 |

`HERDR.md` 写 agy 窗口预期跑 `gemini-3.1-pro`。本阶段以 Human 当场指定的 `gemini-3.7-flash` 为准，写入 `status.json.bookkeeper`。若本窗口实际模型不同，按 `agents/roles.md` 记真实模型 ID，并在开阶段记录里写明与 Human 指定的差异，不要自行改窗口。

## 产品一句话

成交当时扣掉的手续费必须按**当时价格**冻成 USDT 成本。不能用今天的 BNB 价去乘去年扣掉的 BNB。持仓表看开仓成本；历史仓位看开+平合计。这轮**不改**净盈亏公式。

## 已拍板（不要重开讨论）

见 `10-design.md` §3。摘要：

1. 订单腿表加 4 列：`fee_bnb_qty` / `fee_bnb_price` / `fee_other_qty` / `fee_other_asset`。停写旧的 `fee_amount` / `fee_asset`，不删列。
2. 手续费来自成交明细（`commission` + `commissionAsset` 标量；数组的是成交列表）。下单 `RESULT` 回包没有 `fills`。
3. BNB 价只在写入时取一次：先用进程内 `price_map` 的 `BNBUSDT`，没有再公开拉一次；再没有则数量照记、价格留空。禁止为折 U 阻塞成交记录。禁止新建「全局 BNB 价」。
4. 持仓表：开仓腿折 U 成本，独立列，缺数显示「—」。历史仓位：关仓时冻开+平合计。
5. 净盈亏本轮仍是 `资金费 − 利息折U`，不扣手续费（现有仓全无手续费，扣进去会整列变「暂无」）。
6. 不回补历史成交。不把手续费写进已废弃的 `hedge_open_fill`。

## Bookkeeper 立即要做

1. 在本工作树读：`AGENTS.md` → 本文件 → `10-design.md` → `ACTIVE.json` → `PROJECT_STATE.md` → `agents/roles.md` 的 Bookkeeper 节。
2. 确认 cwd 就是本工作树、当前分支是 `stage/2026-08-19-hedge-order-fee-cost-v1`。
3. 建 `status.json`（schema v2 规定字段，不得增删顶层键）。`stage_id` 必须与目录名一致。`bookkeeper=gemini-3.7-flash`，`bookkeeper_label=agy`。`base_sha` / `ledger_sha` 用 `git rev-parse` 实值。
4. 写 `reports/agent-runs/ACTIVE.json` 指向本 stage。
5. **第一份 dispatch 必须是跨 provider 只读计划评审**（HIGH_RISK），verdict 回到 Planner/Bookkeeper 准备实现包；**不触碰 `rework_count`**。评审者不得是本设计作者（xAI / Grok），也不得由 Bookkeeper 自己评。建议 `opus5`（`claude` 窗口）或 Codex。
6. 计划评审通过、Human 同意实现后，再拆实现包：后端默认 `claude_glm`，前端默认 `kimi`（API 契约先冻结再拆，前端不得猜测字段）。
7. 不要实现、不要改业务代码、不要 merge/push、不要下单、不要重启服务。

## 主仓注意

主仓 `ACTIVE.json` 仍是 `{"active": null}`，直到你在**本工作树**写入并提交状态。提交只落本 stage 分支。未授权推送 origin。
