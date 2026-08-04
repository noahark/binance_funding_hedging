# 双栏流水日志设计（借币利息 × 合约资金流水）

| 项 | 值 |
|---|---|
| 状态 | **设计草案**（未实现；供跨模型评审） |
| 日期 | 2026-08-04 |
| 产品 | funding_hedging 本地工作站 |
| 性质 | 只读展示 + 可选本地缓存；**不**下单、不借还、不改 gate |
| 前置证据 | 见 §8 |

## 1. 目标

在「流水日志」区域用**左右两栏**分别展示两类账本：

| 栏 | 科目 | 数据源 |
|---|---|---|
| **左栏** | 借币利息计息流水 | `GET https://api.binance.com/sapi/v1/margin/interestHistory` |
| **右栏** | 合约（UM）资金流水：资金费、手续费、划转、已实现盈亏等 | `GET https://papi.binance.com/papi/v1/um/income` |

两栏均按**时间倒序**（新 → 旧）展示。

### 1.1 要解决的问题

- 对冲策略需要同时看见「借息成本」与「资金费入账」，但两套接口字段、节拍、币种不同。
- 避免把利息与合约损益硬揉成一条混合流水导致列空、科目混淆。

### 1.2 非目标（本设计不包含）

- 不实现自动对冲、不据此触发借还/下单。
- 不做跨币种自动折 USDT 后的「真实净利」总账（可作为后续增强）。
- 不拉现货/杠杆 `myTrades`（UM 以外的手续费源）。
- 不使用经典 `GET /fapi/v1/income`（本账户 PM 只读 Key 实测 `-2015`；统一账户用 papi）。
- 不把公开 `fundingRate` / `premiumIndex` 当作入账金额。

---

## 2. 设计结论（已拍板方向）

1. **双栏分开展示**，不要单表混源。
2. 左栏专用 **sapi interestHistory**；右栏专用 **papi um/income**。
3. **展示层统一时间倒序**；不信任 API 原生顺序（见 §4.3）。
4. 右栏产品名称为 **「合约资金流水」**（或「UM 损益流水」），**不要**默认标题写成「资金费率日志」——同接口含手续费/划转/盈亏。
5. 右栏默认筛选：`FUNDING_FEE` + `COMMISSION`；`REALIZED_PNL` / `TRANSFER` 默认关、可勾选打开。
6. 汇总按**币种分列**；禁止把 BNB 手续费与 USDT 资金费静默相加。

---

## 3. 数据源契约

### 3.1 左栏 — 借币利息

| 项 | 约定 |
|---|---|
| Method/Path | `GET /sapi/v1/margin/interestHistory` |
| Host | `https://api.binance.com` |
| Auth | USER_DATA 签名 |
| 响应外壳 | `{ "total": int, "rows": [ ... ] }` |
| 幂等键 | `txId` |
| 金额字段 | `interest`（本次计息） |
| 时间字段 | `interestAccuredTime`（ms；官方拼写 Accured） |
| 分页 | `current` 从 1；`size` 默认 10、**最大 100** |
| 时间窗 | 默认约 7 天；`startTime`/`endTime` 单窗 **≤30 天** |
| 权重（实测） | 约 **+1 / call**（sapi IP） |
| 与 papi E1 关系 | `GET /papi/v1/margin/marginInterestHistory` 本账户同页数据等价，但权重更高；**批量优先 sapi** |

#### 左栏行字段（展示 + 入库）

| JSON 字段 | 中文 | 列表默认展示 | 备注 |
|---|---|---|---|
| `interestAccuredTime` | 计息时间 | 是 | 格式化为本地/北京时间 |
| `asset` | 资产 | 是 | 币种 |
| `interest` | 本次利息 | 是 | 主金额；字符串 Decimal |
| `principal` | 计息本金 | 是 | 计息时本金，非当前余额 |
| `interestRate` | 日利率 | 可选 | 非年化 |
| `type` | 类型 | 是 | 见枚举 |
| `txId` | 流水 ID | 否（可详情） | 幂等 |
| `rawAsset` | 原始资产 | 否 | 一般与 asset 同 |
| `isolatedSymbol` | 逐仓对 | 否 | 全仓通常无 |

#### `type` 展示文案

| 值 | 中文标签 |
|---|---|
| `PERIODIC` | 小时计息 |
| `ON_BORROW` | 借入首息 |
| `PERIODIC_CONVERTED` | 小时息(BNB) |
| `ON_BORROW_CONVERTED` | 借入首息(BNB) |
| `PORTFOLIO` | 负余额日息 |

#### 与「当前未结利息」的区分

| 口径 | 来源 | 用途 |
|---|---|---|
| 历史计息流水 | 本接口 `Σ interest` | 左栏明细 + 区间累计 |
| 当前未结利息 | `GET /papi/v1/balance` → `crossMarginInterest` | 栏顶可选标签，**不是**流水行 |

曾还息后：`Σ history` 可 **>** `crossMarginInterest`。禁止假设二者恒等。

---

### 3.2 右栏 — 合约资金流水

| 项 | 约定 |
|---|---|
| Method/Path | `GET /papi/v1/um/income` |
| Host | `https://papi.binance.com` |
| Auth | USER_DATA 签名 |
| 响应外壳 | **数组** `[ ... ]` |
| 幂等键 | `(incomeType, tranId)` |
| 金额字段 | `income`（正入账 / 负支出） |
| 时间字段 | `time`（ms） |
| 分页 | `page` + `limit`，**limit 最大 1000** |
| 时间窗 | 默认约 7 天；历史约近 3 个月（以交易所为准） |
| 权重（官方/实测） | 约 **30 / call** |
| 原生排序 | **升序**（旧→新）；展示必须本地倒序 |

#### 右栏行字段

| JSON 字段 | 中文 | 列表默认展示 | 备注 |
|---|---|---|---|
| `time` | 时间 | 是 | |
| `incomeType` | 类型 | 是 | 标签 + 中文 |
| `symbol` | 合约 | 是 | TRANSFER 可能为 `""` |
| `income` | 金额 | 是 | 正绿负红（或产品统一色） |
| `asset` | 结算资产 | 是 | 资金费多为 USDT；手续费可能 BNB |
| `info` | 附加 | 否/详情 | 资金费常为 `FUNDING_FEE` |
| `tranId` | 事务 ID | 否 | 幂等 |
| `tradeId` | 成交 ID | 否 | 资金费常空；手续费常有 |

#### `incomeType` 与默认筛选

| 值 | 中文 | 默认显示 | 计入栏顶「资金费净」 | 计入栏顶「手续费」 |
|---|---|---|---|---|
| `FUNDING_FEE` | 资金费 | **开** | 是（按 asset 汇总，通常 USDT） | 否 |
| `COMMISSION` | 手续费 | **开** | 否 | 是（按 asset，常 BNB） |
| `REALIZED_PNL` | 已实现盈亏 | **关** | 否 | 否 |
| `TRANSFER` | 划转 | **关** | 否 | 否 |
| `COMMISSION_REBATE` 等 | 返佣/其他 | **关** | 否 | 否（若打开则单独或归其他） |

资金费行：`income > 0` 文案「收取」；`< 0`「支付」。

---

## 4. UI 布局

### 4.1 骨架

```text
┌─ 流水日志 ──────────────────────────────────────────────────────────┐
│ 时间范围: [ 近7天 ▼ | 近30天 | 自定义 ]   [刷新]                      │
│ （两栏共用同一时间窗；后端各自请求对应接口）                              │
├─────────────────────────────┬────────────────────────────────────────┤
│ 借币利息流水                 │ 合约资金流水                            │
│ 源: interestHistory          │ 源: um/income                           │
│                              │ 筛选: ☑资金费 ☑手续费 □已实现盈亏 □划转  │
│ 汇总: 按 asset 的 Σinterest  │ 汇总: 资金费净(USDT) / 手续费(BNB…)     │
│ [可选] 未结: balance…        │                                        │
├─────────────────────────────┼────────────────────────────────────────┤
│ 时间↓ | 资产 | 利息 | 本金 | 类型 │ 时间↓ | 类型 | 合约 | 金额 | 资产   │
│ …明细倒序…                  │ …明细倒序…                             │
└─────────────────────────────┴────────────────────────────────────────┘
```

窄屏：改为 **Tab 切换**（利息 | 合约流水），字段与筛选不变。

### 4.2 空态 / 加载 / 错误

| 状态 | 行为 |
|---|---|
| 加载中 | 栏内 skeleton；不清除上一成功快照（可选 last-good） |
| 空列表 | 「该时间窗无记录」；与接口失败区分 |
| 401/签名失败 | 栏级错误条；不假装无流水 |
| 429 / -1003 | 栏级「限频，请稍后刷新」；可指数退避一次 |
| 部分失败 | 一栏失败不影响另一栏已成功数据 |

### 4.3 排序规则（硬约束）

1. 拉取并合并该时间窗内全部页后，在应用层：
   - 左：`sort by interestAccuredTime DESC`，同时间可按 `txId` 稳定次序
   - 右：`sort by time DESC`，同时间按 `(incomeType, tranId)` 稳定次序
2. **禁止**依赖接口返回顺序作为展示顺序。

### 4.4 时间窗（硬约束）

- UI **共用**一个时间范围控件。
- 左栏：窗口长度 **≤30 天**；若产品要「近 90 天」，必须滑动多窗拼接（对用户可透明）。
- 右栏：可单请求覆盖更长窗（受交易所约 3 个月数据与 limit/page 限制）。
- 默认建议：**近 7 天**（与两接口默认语义一致，请求量小）。

---

## 5. 后端/客户端职责（实现时）

> 本节为设计约束，非本轮交付代码。

| 职责 | 约定 |
|---|---|
| 签名出口 | 仅 `binance_signing` + 既有 private 客户端模式 |
| 白名单 | 需新增：`GET /sapi/v1/margin/interestHistory`；`GET /papi/v1/um/income`（当前均未在装配路径使用；E1 papi 利息仅 whitelist 无 fetcher） |
| 拉全 | 左：`current` 循环至 `len >= total`；右：`page` 循环至本页 `< limit` |
| 本地缓存 | 可选 SQLite；upsert 键见 §3 |
| 刷新 | 手动刷新 + 可选定时（须计入权重：income≈30/次） |
| Decimal | 金额全程字符串/Decimal；禁 float 累加 |
| 密钥 | 沿用私有只读通道；不落盘、不打日志 |

可选后续：`GET /papi/v1/um/feeBurn`、`GET /papi/v1/um/commissionRate` 仅用于解释「手续费为何是 BNB / 费率多少」，不进流水表。

---

## 6. 汇总公式（栏顶）

```text
左_区间累计(asset) = Σ rows.interest  where asset = A

右_资金费净(asset) = Σ income  where incomeType = FUNDING_FEE and asset = A
右_手续费(asset)   = Σ income  where incomeType = COMMISSION and asset = A
```

- 不在 v1 自动做「资金费净 − 借息折 U − 手续费折 U」总净利。  
- 若未来做总净利，必须：明示汇率源与时点、分项可展开、失败则不展示假 0。

---

## 7. 开放问题（供评审模型 / Human）

1. 右栏默认筛选是否维持「资金费+手续费」、盈亏/划转默认关？  
2. 时间默认 7 天还是 30 天？  
3. 左栏是否在栏顶展示 `crossMarginInterest` 未结？  
4. 是否需要按当前持仓 `symbol` / 借币任务过滤右栏/左栏？  
5. 是否落本地 DB，还是仅会话内内存 + 手动刷新？  
6. 是否需要导出 CSV？

---

## 8. 证据与对照文档

| 文档 | 内容 |
|---|---|
| `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md` | 借币利息 live recon：sapi≡papi、分页、累计 vs 未结 |
| `reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md` | UM income live recon：FUNDING/COMMISSION/…、fapi -2015、feeBurn |
| 原始策略 | `币安套费率策略，逐仓杠杆.js` → 历史用 `/fapi/v1/income`，PM 应改为 papi |
| 代码现状 | `backend/services/private_client.py`：E1/E1b 仅白名单；**无** interestHistory(sapi) / um/income |
| 产品缺口 | `docs/product/PRD.md` / ROADMAP：funding / fee / borrow-interest accounting 未实现 |

---

## 9. 评审检查清单（给其他模型）

请评审时明确回答：

- [ ] 双栏分源是否合理？有无必须合并为单时间线的硬需求？  
- [ ] 接口选择（sapi interestHistory + papi um/income）是否同意？  
- [ ] 右栏默认筛选与命名是否足够防误解？  
- [ ] 排序/时间窗/幂等/币种隔离约束是否有遗漏或冲突？  
- [ ] 与现有私有通道白名单、限频、安全门禁是否冲突？  
- [ ] 是否存在资金语义错误（把未结当累计、BNB 与 USDT 混加、用费率代替入账等）？  
- [ ] 最小实现切片建议（仅 UI 假数据 / 只读拉 7 天 / 含缓存）？

评审结论请标注：`ACCEPT` / `REWORK` + 具体修改点；本文件为设计草案，**不**授权实现或实盘写入。

---

## 10. 修订记录

| 日期 | 说明 |
|---|---|
| 2026-08-04 | 初稿：双栏流水日志设计，基于同日利息与 income 实盘 recon 与 Human 确认方向 |
