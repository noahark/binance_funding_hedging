# 借币利率 / 可借性端点只读摸排报告 v2

模型：Kimi (`kimi-code/kimi-for-coding`)  
任务：私有账户 v1 方向阶段，只读实测六组借币利率/可借性相关端点，确定"开仓前借币日利率"主数据源及调用频率建议。  
样本目录：`reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/`  
证据文件：`sanitized/*.json` + `evidence-index.json` + `probe-script.py`  
执行约束：零下单、零借还、零划转、零业务代码修改、零 git 提交；仅落档脱敏报告与样本。

---

## 1. 摘要结论

### 1.1 推荐数据源链路（按优先级）

| 优先级 | 端点 | 用途 | 置信度 |
|---|---|---|---|
| ① | `GET /sapi/v1/margin/next-hourly-interest-rate` | **开仓前借币日利率主数据源** | 高 |
| ② | `GET /sapi/v1/margin/interestRateHistory` | 校验 / fallback / 对账 | 高 |
| ③ | `GET /sapi/v1/margin/crossMarginData` | 档位参考 fallback（本账户仅 VIP0） | 中 |
| ④ | `GET /sapi/v1/account/info` | VIP 档位匹配输入 | 高 |
| — | `GET /papi/v1/margin/maxBorrowable` | **仅验证"能不能借"**，不是利率来源 | 高 |
| — | `GET /papi/v1/margin/marginInterestHistory` / `GET /papi/v1/portfolio/interest-history` | **仅做事后 reconciliation**，不做开仓前输入 | 中 |

### 1.2 关键实测结论

1. **主数据源 = `next-hourly-interest-rate`**：一次调用可批量查询多个资产，返回 `nextHourlyInterestRate`（hourly），乘以 24 后与本账户 `interestRateHistory` 最新 `dailyInterestRate` 高度接近（误差 <10%，多数 <1%），说明该端点可直接作为统一账户下开仓前日利率估计。
2. **`interestRateHistory` 是单资产端点**，每资产权重 **60 (UID)**，批量探测成本高，仅作为 next-hourly 失败/缺失时的 fallback 与对账。
3. **`crossMarginData` 返回的是账户当前 VIP 档位的利率表**；本账户 VIP0，因此响应仅含 VIP0 行。它不应被视为"当前账户真实利率"，只能做 fallback reference。
4. **`maxBorrowable` 是统一账户实际可借性来源**：OPG/0G/AIGENSYN 当前返回 `51061`（可借资产不足），而 ALGO/DOGE/BTC/ETH/SOL 返回正额度；TSLAB 返回 `0`。
5. **bStock（TSLAB）不适合作为负费率借币套利腿**：next-hourly / interestRateHistory 均不支持 TSLAB，maxBorrowable 可借额度为 0。
6. **两历史扣息接口当前为空**：账户无活跃借币余额时，`marginInterestHistory` 返回 `{"total":0,"rows":[]}`，`portfolio/interest-history` 返回 `[]`。

---

## 2. 接口使用频率排序

> **调用频率 ≠ 数据优先级**。频率由权重成本、TTL 语义和探测必要性决定；优先级由数据质量（是否接近真实开仓成本）决定。

### 2.1 运行时调用频率（从高到低）

| 排序 | 端点 | 建议调用频率 | 实测单次权重 | 原因 |
|---|---|---|---|---|
| 1 | `/sapi/v1/account/info` | 1h TTL（或更长） | 2 IP | VIP 等级极少变化，极低成本 |
| 2 | `/sapi/v1/margin/next-hourly-interest-rate` | 1h TTL | 200 IP | 一次批量覆盖全部候选资产 |
| 3 | `/sapi/v1/margin/crossMarginData` | 1h TTL | 100 IP | fallback 利率表，全量一次 |
| 4 | `/papi/v1/margin/maxBorrowable` | 1h TTL，按候选资产 | 5 / asset | 可借性验证，需逐资产 |
| 5 | `/papi/v1/margin/marginInterestHistory` | 按需 / 每日一次 | 10 / call | 对账，仅在账户有借币余额时才有意义 |
| 6 | `/papi/v1/portfolio/interest-history` | 按需 / 每日一次 | 50 / call | 同上，且观察到 papi 子族可能有独立权重池 |
| 7 | `/sapi/v1/margin/interestRateHistory` | fallback 触发 | 60 UID / asset | 仅在 next-hourly 失败/缺失时启用 |

### 2.2 频率与优先级区别说明

- **数据优先级**：next-hourly 最高，因为它给出的是"下一小时预估利率"，最接近未来开仓成本；interestRateHistory 是已结算日利率，适合做校验；crossMarginData 是档位参考。
- **调用频率**：account.info / next-hourly / crossMarginData 虽然优先级不同，但都是 1h TTL 级低频调用；maxBorrowable 频率与候选资产数量成正比；interest histories 频率最低，因为它们只在有持仓时才有数据。
- **成本敏感点**：若用 interestRateHistory 替代 next-hourly 做批量探测，50 资产 × 60 = 3,000 UID weight/h，远高于 next-hourly 的 200 IP weight/h。

---

## 3. 六组接口实测矩阵

| # | 接口 | 调用参数 | 状态 / Binance code | 字段路径 | 单位 | 批量 | 统一账户适用性 | 权重 header | 建议用途 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `GET /sapi/v1/margin/next-hourly-interest-rate` | `assets=OPG,0G,...,TSLAB&isIsolated=false` | 200 | `[].asset` `[].nextHourlyInterestRate` | hourly | **是**，逗号分隔多资产 | 适用。响应资产与统一账户可借资产集一致（TSLAB 除外） | `X-SAPI-USED-IP-WEIGHT-1M: 200` | **主数据源**：hourly × 24 → daily |
| 2 | `GET /sapi/v1/margin/interestRateHistory` | `asset=<single>` | 200（TSLAB: 400 -11027） | `[].asset` `[].dailyInterestRate` `[].timestamp` `[].vipLevel` | daily | **否**，单资产 | 适用。返回 `vipLevel=0`，与本账户 VIP 一致 | `X-SAPI-USED-UID-WEIGHT-1M: +60 / asset` | fallback / 对账校验 |
| 3 | `GET /sapi/v1/margin/crossMarginData` | 无 | 200 | `[].vipLevel` `[].coin` `[].dailyInterest` `[].borrowable` `[].borrowLimit` | daily | 全量一次返回 | 返回账户当前 VIP 档位（本账户仅 VIP0） | `X-SAPI-USED-IP-WEIGHT-1M: 100` | fallback reference |
| 4 | `GET /sapi/v1/account/info` | 无 | 200 | `vipLevel` `isPortfolioMarginRetailEnabled` `isMarginEnabled` `isFutureEnabled` | — | 单账户 | 直接给出统一账户开关与 VIP | `X-SAPI-USED-IP-WEIGHT-1M: 2` | VIP 档位匹配 / 账户类型诊断 |
| 5 | `GET /papi/v1/margin/maxBorrowable` | `asset=<single>` | 200 或 400 `51061` | `amount` `borrowLimit` | 数量 | 否，逐资产 | 统一账户真实可借额度 | `X-MBX-USED-WEIGHT-1M: +5 / asset` | **可借性验证**，不是利率 |
| 6a | `GET /papi/v1/margin/marginInterestHistory` | `asset=OPG&size=5` / 无 asset | 200 | `total` `rows[].asset` `rows[].interest` ... | 历史利息 | 否 | 统一账户杠杆利息历史 | `X-MBX-USED-WEIGHT-1M: +10 / call` | 事后 reconciliation |
| 6b | `GET /papi/v1/portfolio/interest-history` | `asset=OPG&size=5` / 无 asset | 200 | `[]` | 历史利息 | 否 | 统一账户期货负余额收息历史 | `X-MBX-USED-WEIGHT-1M: +50 / call` | 事后 reconciliation |

### 3.1 权重说明与限频预算影响

- **sapi IP 池**（`api.binance.com`）：官方限额 12,000 / min / IP。next-hourly(200) + crossMarginData(100) + account.info(2) ≈ 302 / h，余量充足。
- **sapi UID 池**：官方限额 180,000 / min / UID。interestRateHistory 60 / asset；若 50 资产全量轮询 = 3,000 / h，仍在限额内，但成本显著。
- **papi IP/weight 池**（`papi.binance.com`）：maxBorrowable 5 / asset；50 资产 = 250 / h。marginInterestHistory 10 / call、portfolio interest-history 50 / call。注意 portfolio 子族观察到独立的 `X-MBX-USED-WEIGHT-1M` 计数（从 50 起跳而非继承 margin 子族的 255），说明 papi 内部可能存在按子服务划分的权重池；具体归属需要更多样本确认，预算时应按最悲观值估算。

---

## 4. 样本资产对比表

> 样本 9 个：OPG（正对照）、0G / AIGENSYN / ALGO（UI-gap 代表）、DOGE（rate_limit_budget 常见跳过资产）、BTC / ETH / SOL（高流动性对照）、TSLAB（bStock）。

| asset | next_hourly | next_hourly × 24 (daily) | interestRateHistory latest daily | crossMarginData VIP0 daily | maxBorrowable 是否可借 | 建议 borrow_rate_source |
|---|---|---|---|---|---|---|
| OPG | 0.00007592 | 0.00182208 | 0.00177362 | 0.00177362 | ❌ 51061 可借资产不足 | next_hourly（有 rate 但不可借） |
| 0G | 0.00006797 | 0.00163128 | 0.00178740 | 0.00178740 | ❌ 51061 可借资产不足 | next_hourly |
| AIGENSYN | 0.00014661 | 0.00351864 | 0.00374726 | 0.00374726 | ❌ 51061 可借资产不足 | next_hourly |
| ALGO | 0.00000450 | 0.00010800 | 0.00010853 | 0.00010853 | ✅ amount>0, limit>0 | next_hourly |
| DOGE | 0.00000396 | 0.00009504 | 0.00009449 | 0.00009449 | ✅ amount>0, limit>0 | next_hourly |
| BTC | 0.00000045 | 0.00001080 | 0.00001074 | 0.00001074 | ✅ amount>0, limit>0 | next_hourly |
| ETH | 0.00000256 | 0.00006144 | 0.00006142 | 0.00006142 | ✅ amount>0, limit>0 | next_hourly |
| SOL | 0.00000649 | 0.00015576 | 0.00015607 | 0.00015607 | ✅ amount>0, limit>0 | next_hourly |
| TSLAB | —（端点不支持） | — | —（400 -11027） | — | ✅ 200 但 amount=0, limit=0 | **不适用**（bStock 不可借） |

### 4.1 对应关系说明

- `next_hourly × 24` 与 `interestRateHistory.latest daily` 差距多数 <1%，仅 OPG/0G/AIGENSYN 等波动资产在 2–8% 之间，符合"预估利率 vs 已结算利率"的预期差异。
- `crossMarginData VIP0 daily` 与 `interestRateHistory.latest daily` **完全一致**（样本内），说明 interestRateHistory 返回的正是当前 VIP 档位的日利率历史。
- `maxBorrowable` 的不可借结论（51061）与 `crossMarginData.borrowable=true` 不矛盾：后者表示资产"理论上可借"，前者表示当前账户实际可借额度为 0（流动性枯竭）。

---

## 5. 与当前代码的差距

### 5.1 为什么当前可能"只有 OPGUSDT 查到真实日借币利率"

当前 `backend/services/private_client.py:fetch_cost_leg_chain` 实现（A1 假设）：

- tier① `next-hourly`：一次 comma-joined 调用覆盖全部候选资产。若本调用成功，所有资产都能拿到 hourly 并换算 daily。
- tier② `interestRateHistory`：**只探测 `borrow_assets[0]`**（代码第 329 行）。

因此，当 tier① 因网络/限频/参数错误失败时，系统会退到 tier②，而 tier② 只返回排序第一的那个资产（若此时第一为 OPG）的 daily rate，其他资产全部缺失。这就是"只有 OPGUSDT 查到真实日借币利率"的典型触发路径：

```
next-hourly 失败/为空
  └─> rate_history(OPG only) 命中
      └─> 仅 OPG 有 daily_interest_account，其余为 null
```

### 5.2 是否应把 interestRateHistory 从"只查第一个资产"改成"候选资产分批轮询"

**建议：不要改成全量轮询，改为 rotating probe queue（旋转探测队列）**。理由：

- **成本**：interestRateHistory 权重 60 / asset，50 资产 = 3,000 UID weight/h；若 next-hourly 已覆盖全部资产，再全量轮询是浪费。
- **收益**：实测 next-hourly × 24 与 interestRateHistory 日利率高度一致，全量轮询对提升精度帮助有限。
- **正确做法**：
  1. 正常情况仍用 next-hourly 一次覆盖全部候选；
  2. 仅在 next-hourly 失败/缺失时，启用 rotating probe queue：每轮从候选集中选 K 个资产查 interestRateHistory，多轮后覆盖全部；
  3. 或者 interestRateHistory 专门用于对账：每天抽 1–2 个高价值资产与 next-hourly 做差值监控。

---

## 6. 推荐后续实现

### 6.1 探测策略

1. **主链路（稳态）**：
   - 每 1h 调用一次 `next-hourly-interest-rate(assets=全部候选, isIsolated=false)`，权重 200。
   - 同时每 1h 调用 `account.info`（权重 2）和 `crossMarginData`（权重 100）作为 fallback 表。
   - 对负费率候选资产逐资产调用 `maxBorrowable`（权重 5 / asset），上限 50 资产。

2. **Rotating probe queue（降级链路）**：
   - 当 next-hourly 连续失败（2 次，含 429/-1003）或返回空时，启动旋转队列。
   - 每轮从候选集中按 abs daily rate 降序取 **top 5–10** 资产查询 `interestRateHistory`。
   - 队列按轮次推进，例如每 1h 推进 5 个资产，10 轮覆盖 50 个资产。
   - 记录每资产最后探测时间，避免重复。

3. **top-N + round-robin 结合**：
   - **top-N**：每次快照优先保证 abs daily rate 最高的 N 个资产有利率数据（N 默认 10）。
   - **round-robin**：在 top-N 之外，每轮额外探测 M 个较低优先级资产（M 默认 3–5），逐步扩大覆盖率。
   - 这兼顾了"机会质量"与"覆盖率"。

### 6.2 默认参数建议

| 参数 | 建议值 | 说明 |
|---|---|---|
| next-hourly TTL | 3600 s | 小时级利率预估无需过频 |
| crossMarginData TTL | 3600 s | 档位表小时级刷新足够 |
| account.info TTL | 3600 s（可更长） | VIP 极少变化 |
| maxBorrowable TTL | 3600 s | 可借额度小时级 |
| 默认 probe 数量 | 50 | 与现有 `borrow_check_max_calls` 对齐 |
| rotating queue 每轮资产数 | 5 | 控制 interestRateHistory 成本 |
| 失败重试 | 1 次有界退避（0.5s），429/-1003 触发 | 沿用现有 `PrivateClient` 逻辑 |

### 6.3 前端展示字段

建议新增/保留字段：

- `borrow_rate_source`: `next_hourly` / `rate_history` / `cross_margin_tier` / `vip0_reference` / `null`
- `daily_borrow_rate`: 8 位字符串
- `net_daily_yield`: 8 位字符串
- `borrow_validation.classic_margin.daily_interest_account`: 8 位字符串
- `borrow_validation.portfolio_account.max_borrowable_gt_zero`: bool（脱敏后的可借性）
- `borrow_validation.portfolio_account.borrow_limit_gt_zero`: bool
- `borrow_validation.error`: 如 `51061` 可借资产不足、`not_probed_this_round` 等
- UI 标注：
  - next_hourly 来源："预估日借币利率（小时预估 ×24）"
  - rate_history 来源："最近结算日利率"
  - cross_margin_tier / vip0_reference："档位参考利率"
  - maxBorrowable 51061："当前可借资产不足"
  - TSLAB / bStock："bStock 不支持借币套利"

---

## 7. 风险与未决问题

### 7.1 需要用户在交易所页面人工核对的事项

1. **next-hourly × 24 与 UI 借币日利率是否一致**：实测数学换算与 `interestRateHistory` 高度一致，但与 Binance 网页端"借币利率"显示是否一致，需要用户在 UI 上对比 OPG/ALGO/BTC 等资产。
2. **统一账户 vs 经典账户口径**：本账户 `isPortfolioMarginRetailEnabled=true`，确认是统一账户；若用户切换到经典账户，next-hourly 是否仍返回相同利率需要验证。
3. **VIP 档位扩展**：本账户 VIP0，crossMarginData 仅返回 VIP0。若用户升级 VIP，需确认 crossMarginData 是否自动返回当前 VIP 档位，或仍需显式传 `vipLevel` 参数。
4. **OPG/0G/AIGENSYN 的 51061 状态持续性**：当前这些资产"有利率但不可借"，需用户确认这是短期流动性枯竭还是长期状态。

### 7.2 接口可能存在的账户类型差异

- `/sapi/v1/margin/next-hourly-interest-rate` 文档未明确区分统一/经典账户；实测在统一账户下返回的资产集合与 `papi/v1/margin/maxBorrowable` 支持集一致（TSLAB 除外），推测已按统一账户口径返回，但仍需更多 VIP/账户类型样本验证。
- `/papi/v1/portfolio/interest-history` 与 `/papi/v1/margin/marginInterestHistory` 的归属边界尚未完全清晰：本账户两者均为空，无法判断哪个更贴近实际负余额扣息。建议后续在账户有真实借币余额时再次并抓比对。
- papi 子族权重池归属存在不确定性：`/papi/v1/portfolio/interest-history` 观察到与 `/papi/v1/margin/*` 不同的 `X-MBX-USED-WEIGHT-1M` 起始值，可能按 `margin` / `portfolio` 子服务分池计数。预算时应保守按独立池各 6,000/min 估算。

---

## 8. 证据清单

- `sanitized/next_hourly_batch.json`：批量 next-hourly 响应，8/9 资产命中，TSLAB 缺失。
- `sanitized/interest_rate_history_*.json`：9 资产日利率历史，TSLAB 报错 -11027。
- `sanitized/cross_margin_data.json`：408 行 VIP0 档位表。
- `sanitized/account_info.json`：vipLevel=0，统一账户开关 true。
- `sanitized/max_borrowable_*.json`：9 资产可借性状态（已脱敏）。
- `sanitized/margin_interest_history_*.json`、`sanitized/portfolio_interest_history_*.json`：历史扣息空响应。
- `evidence-index.json`：汇总矩阵与元数据。
- `probe-script.py`：可复现本次只读探测的脚本（不含密钥）。

所有样本已脱敏：未包含 API key、secret、签名串、完整账户余额、完整可借数量；`maxBorrowable` 的 `amount` / `borrowLimit` 仅保留字段存在性、类型、是否大于 0。

---

## §9 next-hourly 批量上限 / 服务内失效补测

> 探测时间：2026-07-07 14:07 UTC  
> 探测脚本：`reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/probe_next_hourly_batch_limit.py`  
> 执行约束：零下单、零借还、零划转、零业务代码修改、零 git 提交；样本已脱敏。

### §9.1 一句话结论（Gate B 答案）

**服务内一次性发 50 个资产的 `next-hourly-interest-rate` 会返回空，是因为 Binance 对该端点施加了硬上限：assets 参数中唯一资产数量不得超过 20。** 超过时接口返回 HTTP 500、Binance code=2、msg=`The size of assets should not larger than 20`，服务代码 `:319` 的 `except PrivateEndpointError: next_hourly = {}` 将其静默吞掉，导致上层只看到 `next_hourly` 为空并降级到 rate_history。

因此 **H1 成立**，H2/H3/H4 均被排除。

### §9.2 T1–T6 结果矩阵

#### T1 阶梯放大（定位数量上限）

| N | 状态 | Binance code | 返回数 / 请求数 | 权重增量 | 结论标签 | 样本 |
|---|---|---|---|---|---|---|
| 9 | 200 | — | 9/9 | +100 | SUCCESS | `next_hourly_batch_limit_t1_n09.json` |
| 20 | 200 | — | 20/20 | +100 | SUCCESS | `next_hourly_batch_limit_t1_n20.json` |
| 21 | 500 | 2 | 0/21 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n21.json` |
| 30 | 500 | 2 | 0/30 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n30.json` |
| 40 | 500 | 2 | 0/40 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n40.json` |
| 45 | 500 | 2 | 0/45 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n45.json` |
| 50 | 500 | 2 | 0/50 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n50.json` |
| 55 | 500 | 2 | 0/55 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n55.json` |
| 60 | 500 | 2 | 0/60 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n60.json` |
| 66 | 500 | 2 | 0/66 | +100 | LIMIT_HIT | `next_hourly_batch_limit_t1_n66.json` |

精确边界：**20 通过，21 失败**。

#### T2 复现服务失败（前 50 资产）

| 调用 | 状态 | Binance code | 返回数 | 结论 | 样本 |
|---|---|---|---|---|---|
| 服务口径前 50 | 500 | 2 | 0/50 | LIMIT_HIT | `next_hourly_batch_limit_t2_top50.json` |

与 T1 N=50 完全一致，确认服务调用失败机制。

#### T3 数量上限 vs 字符串长度

为排除「URL / query 长度上限」假设，构造 20 个唯一短名资产与 20 个唯一长名资产分别调用：

| 分组 | 资产数 | query 字节 | 状态 | 返回数 | 结论 | 样本 |
|---|---|---|---|---|---|---|
| 短名（0G,ID,LA,…,XLM） | 20 | 74 | 200 | 20/20 | SUCCESS | `next_hourly_batch_limit_t3_short_n20.json` |
| 长名（AIGENSYN,BANANA,…,ACH） | 20 | 109 | 200 | 20/20 | SUCCESS | `next_hourly_batch_limit_t3_long_n20.json` |

两组均成功，说明失败与资产名字符串长度无关；**决定因素是资产唯一计数**。

#### T4 权重 / 限频排查

连续 5 次调用前 50 资产：

| 第几次 | 状态 | code | 权重头 | 结论 |
|---|---|---|---|---|
| 1 | 500 | 2 | +100 | LIMIT_HIT |
| 2 | 500 | 2 | +100 | LIMIT_HIT |
| 3 | 500 | 2 | +100 | LIMIT_HIT |
| 4 | 500 | 2 | +100 | LIMIT_HIT |
| 5 | 500 | 2 | +100 | LIMIT_HIT |

5 次均稳定返回 500 code=2，未出现 429 或 -1003。**失败是参数性、确定性的，不是权重限频**。

#### T5 非法资产排查

将服务口径前 50 资产二分：

- 左半 25 个：500 code=2（因 25 > 20）
- 对这 25 个再二分：12 个成功，13 个成功

未定位到任何「单个非法资产导致整批 400」的情况，**排除 H4**。

#### T6 安全分批参数（实现输入）

| 参数 | 实测/建议值 | 说明 |
|---|---|---|
| `next_hourly_max_assets_per_call` | 20 | 实测硬上限 |
| `recommended_batch_size` | 15 | 留 25% 余量，避免 Binance 侧调整或重复资产导致意外越界 |
| `batches_to_cover_66` | 5 | `ceil(66 / 15)` |
| `weight_per_call_observed` | 100 | 本次探测每次调用实际消耗 100 IP weight（原 v2 报告观察到的 200 可能为同分钟内并发叠加） |
| `total_weight_per_snapshot` | 500 | 5 批 × 100 |

### §9.3 对实现方案的影响

1. **`fetch_cost_leg_chain` 必须将 66 个候选资产拆成 ≤20 的批次调用 next-hourly**，再把结果合并后再传入 `_select_chain_tier`。
2. 推荐批次大小 **15**（5 批覆盖全部 66 资产），单次快照增加约 500 IP weight，远低于 sapi 12,000/min 的 IP 上限。
3. 不需要把 `interestRateHistory` 改成全量轮询；在 next-hourly 分批修复后，rate_history 仅作为 fallback / 对账用途即可。
4. 服务内 `except PrivateEndpointError: next_hourly = {}` 的静默吞异常行为应被记录或改为可观测错误，否则未来 Binance 调整限制后难以定位。

### §9.4 新增证据清单

- `sanitized/next_hourly_batch_limit_t1_n*.json`：T1 阶梯放大样本。
- `sanitized/next_hourly_batch_limit_t2_top50.json`：服务口径前 50 复现失败。
- `sanitized/next_hourly_batch_limit_t3_short_n20.json`、`t3_long_n20.json`：长度控制。
- `sanitized/next_hourly_batch_limit_t4_repeat*.json`：重复调用权重/限频排查。
- `sanitized/next_hourly_batch_limit_t5_left_*.json`：二分搜索。
- `next_hourly_batch_limit_summary.json`：机器可读汇总。
- `evidence-index.json`：已追加本次条目。

---

本地北京时间: 2026-07-07 22:12:04 CST  
下一步模型: Claude/GPT  
下一步任务: 根据 Gate B 结论定稿 borrow-cost coverage v2 实现方案（next-hourly 分批合并 + 降级链路）
