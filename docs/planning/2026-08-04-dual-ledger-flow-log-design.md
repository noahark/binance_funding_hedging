# 双栏流水日志设计（借币利息 × 合约资金流水）

> **［定稿标记 · 2026-08-04 · Planner opus5 · stage `2026-08-04-dual-ledger-flow-log-v1`］**
> 本文件为 **定稿 v1.1**。§1–§10 为 2026-08-04 草案原文，**未作任何改写**；§11 起为定稿追加内容。
> 需求 1（按钮调整）见 **§11**；§7 的六个开放问题由 **§12** 逐条关闭；冻结的接口契约见 **§13**；
> 本地账本与数据库见 **§14**；定时刷新与增量统计见 **§15**；实现任务拆分见 **§16**；
> 风险与流程见 **§17**；Human 已拍板的全部产品决策汇总在 **§18**。
> **凡草案（§1–§10）与 §11–§18 冲突处，一律以 §11–§18 为准**——尤其 §5 的「本地缓存：可选 SQLite」
> 已被 §12 决议 5 升级为**必须的本地账本**，§4.4 的「窗口 ≤30 天」现在只约束**回补**、不约束**查询**。
> 本定稿**不授权实现、合并、部署或实盘操作**；实现开始前须先过 §17.3 的跨 provider 只读计划评审。

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
| 2026-08-04 | **定稿 v1.0**（Planner opus5）：追加顶部定稿标记与 §11–§16（需求 1、开放问题决议、冻结接口契约、任务拆分、风险与流程、Human 决策点）。§1–§10 原文未改写。 |
| 2026-08-04 | **定稿 v1.1**（Planner opus5，Human 需求细化后重出）：Q5 由「不落盘」**改为本地 SQLite 去重持久化**；Q2 加回自定义时间窗且不受 30 天限制；新增每小时整点后 1 分钟的定时刷新与「距上次刷新新增」增量统计（§15）与本地账本 schema（§14）；接口契约升为 `private-ledger/v2`（读本地库 + `POST refresh`，§13）；实现任务由两份改为三份（§16）。§1–§10 原文仍未改写；v1.0 追加章节整体重出，未提交过，故无勘误痕迹。 |

---

## 11. 需求 1 — 费率行情页按钮调整（Human 已拍板语义）

### 11.1 目标状态

| 元素 | 现状 | 定稿后 |
|---|---|---|
| `#btn-privacy`（显示金额/隐藏金额） | 私有账户面板 `.panel-header > .panel-actions`（`frontend/index.html:1127-1133`） | 移入 `.panel-title` 内，紧邻 `<h2>私有账户</h2>` 右侧同一行 |
| 新 `#btn-flow-log`（流水日志） | 不存在 | 占据原 `.panel-actions` 位置，点击展开/收起双栏流水日志 |

### 11.2 DOM 落点（冻结）

`.panel-title` 现为 `display: grid`（标题 + 副标题竖排），因此在其内部新增一个横向行容器承载标题与开关：

```html
<div class="panel-title">
  <div class="panel-title-row">
    <h2>私有账户</h2>
    <button class="privacy-toggle" id="btn-privacy" type="button" aria-pressed="false" title="切换金额显示">…</button>
  </div>
  <p class="subtitle source-checked-at" id="private-pm-source-time" style="display:none;"></p>
</div>
<div class="panel-actions">
  <button class="btn compact" id="btn-flow-log" type="button" aria-expanded="false" aria-controls="flow-log-panel">流水日志</button>
</div>
```

新增样式仅一条、且只服务此处：`.panel-title-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }`。

### 11.3 不变量

- `#btn-privacy` 的 **id、`aria-pressed`、`#privacy-label`、`#privacy-icon-path`、点击行为、localStorage 键 `funding_hedging_privacy_hidden`** 一律不变——本需求只搬位置。
- 既有 self-check 断言以 id 定位、不断言父元素（`frontend/self-check.js:156`、`:1499`），因此移动**不得**使其失效；新按钮须补断言。
- `#private-pm-source-time` 仍在 `.panel-title` 内、仍位于标题下方（v0.10/v4 §9.3 的位置约定不变）。
- 面板标题栏在窄屏的既有折行行为（`@media` 下 `.panel-header` 改竖排）不变。

---

## 12. §7 开放问题逐条决议（Human 已于 2026-08-04 全部拍板）

| # | 开放问题 | 决议 | 理由 |
|---|---|---|---|
| 1 | 右栏默认筛选是否维持「资金费+手续费」、盈亏/划转默认关？ | **维持**：`FUNDING_FEE` + `COMMISSION` 默认开；`REALIZED_PNL` / `TRANSFER` / 其他默认关、可勾选。**筛选纯前端**，切换不发请求。 | 明细来自本地库，一次读出全类型；按类型分别查询只会把简单的读放大成多次查询。 |
| 2 | 时间默认 7 天还是 30 天？ | **默认近 7 天**；另给 `近30天` 与 **`自定义`**（起止日期）。自定义窗**不再受 30 天限制**——上限只由本地已回补范围决定（见 §13.2 `coverage`）。 | 7 天首屏最快。30 天上限是**币安单次查询**的限制，只卡「回补」不卡「查询」；本地存了历史之后，自定义窗反而是低成本能力。 |
| 3 | 左栏是否在栏顶展示 `crossMarginInterest` 未结？ | **v1 不展示**。左栏顶只给「区间已计息累计（按币种）」，并固定附一行文案：**「这是所选区间的已计息累计，不等于当前未结利息；曾还息后两者必然分叉」**。 | `crossMarginInterest` **尚未进入已发布快照的 `private_account`**（仅 `crossMarginBorrowed` 在），展示它须改快照装配与契约，属另一交付范围。 |
| 4 | 是否需要按持仓 `symbol` / 借币任务过滤？ | **不做过滤器**。但「本次新增」的资金费**按合约分组展示**（§17.4），这是展示不是过滤。 | 任务归因需另绑借还与开平仓时段记录，属未被证明的需求；而按合约看资金费增量是对冲操作的实际视角。 |
| 5 | 是否落本地 DB？ | **落本地 SQLite 并按幂等键去重**（Human 2026-08-04 决定，**推翻本文件早先「不落盘」的推荐**）。库文件 `data/ledger-flow.sqlite3`，幂等键：利息 `txId`、合约流水 `(incomeType, tranId)`。 | 定时增量刷新与「距上次新增多少」的统计**只有存本地才算得出来**；页面读本地库从数秒降到毫秒；自定义窗不再受 30 天限制。 |
| 6 | 是否需要导出 CSV？ | **v1 不做**。 | 未被要求的能力；页面已可读。 |

### 12.1 §2 已拍板方向复核（不变）

§2 的六条全部维持：双栏分源、左 sapi `interestHistory` / 右 papi `um/income`、展示层统一时间倒序、右栏命名为「合约资金流水」不叫「资金费率日志」、右栏默认筛选资金费+手续费、汇总按币种分列且禁止把 BNB 手续费与 USDT 资金费相加。

### 12.2 对草案的收敛与推翻（说明）

- **§4.3 排序**：草案「展示层排序、禁止依赖接口返回顺序」针对**币安**返回顺序，仍成立。定稿把排序下沉到**数据库查询**（`ORDER BY` 时间倒序），前端按收到顺序渲染、不二次排序。
- **§4.1 窄屏**：草案「改为 Tab 切换」，定稿改为**上下堆叠单列**，不引入 Tab 状态机。
- **§5「本地缓存：可选 SQLite」**：由「可选」升级为**必须**（§12 决议 5），并从「缓存」升级为**账本**——它是页面明细与增量统计的唯一数据源，随之带来 §13.2 的覆盖范围诚实性硬约束。
- **§4.1 时间范围控件**：草案的「自定义」保留，且允许跨越 30 天。

---

## 13. 冻结接口契约（三个任务之间的唯一对齐点）

**总体形态变更（相对本文件早先版本）**：页面读的是**本地库**，不是每次点开都打币安。上游拉取由每小时的定时刷新负责（§17）。

### 13.1 路由

| 方法与路径 | 作用 | 上游 I/O |
|---|---|---|
| `GET /api/private-ledger/flow-log?start=<ms>&end=<ms>` | 读本地库：窗口内明细 + 汇总 + 覆盖范围 + 上次刷新状态 + 本次新增 | **零** |
| `POST /api/private-ledger/refresh` | 手动触发一次 `kind="manual"` 拉取 run | 有（只读签名 GET） |

- 均为同源、仅 `127.0.0.1`；`GET` 只在 `do_GET` 注册、`POST` 只在 `do_POST` 注册，其余方法落既有 404。
- `POST` 无请求体字段（任何 body 读完即丢弃），不接受时间窗参数——窗口由服务端按 §17.2 计算。

### 13.2 `GET flow-log` 的 200 响应（冻结）

```json
{
  "schema_version": "private-ledger/v2",
  "served_at_ms": 1785798060000,
  "window": { "start_ms": 1785193260000, "end_ms": 1785798060000 },
  "coverage": { "start_ms": 1783206000000, "end_ms": 1785798000000, "complete": true },
  "last_run": {
    "run_id": 128, "kind": "scheduled", "finished_at_ms": 1785798060000,
    "interest_status": "ok", "interest_error": null,
    "income_status": "ok", "income_error": null,
    "truncated": false, "consecutive_failure_count": 0
  },
  "delta": {
    "baseline_ms": 1785794460000, "complete": true,
    "interest_by_asset": [
      { "asset": "HOME", "interest_total": "0.00008975", "row_count": 1, "unparsed_row_count": 0 }
    ],
    "income_by_type_asset": [
      { "income_type": "FUNDING_FEE", "asset": "USDT", "income_total": "0.12340000", "row_count": 3, "unparsed_row_count": 0 }
    ],
    "funding_by_symbol": [
      { "symbol": "MUUSDT", "asset": "USDT", "income_total": "0.08000000", "row_count": 1 }
    ],
    "interest_new_row_count": 1,
    "income_new_row_count": 3
  },
  "today": {
    "day_start_ms": 1785772800000,
    "interest_by_asset": [ … ],
    "income_by_type_asset": [ … ]
  },
  "interest": {
    "rows": [
      { "tx_id": "2328408217636413776", "accrued_at_ms": 1785798000000, "asset": "HOME",
        "raw_asset": "HOME", "principal": "1.0", "interest": "0.00008975",
        "interest_rate": "0.00215396", "type": "PERIODIC", "isolated_symbol": null }
    ],
    "summary_by_asset": [
      { "asset": "HOME", "interest_total": "0.00017950", "row_count": 2, "unparsed_row_count": 0 }
    ],
    "row_count": 1006,
    "row_limit_applied": true
  },
  "um_income": {
    "rows": [
      { "tran_id": "123456789", "income_type": "FUNDING_FEE", "time_ms": 1785798000000,
        "symbol": "COOKIEUSDT", "income": "-0.00123000", "asset": "USDT",
        "info": "FUNDING_FEE", "trade_id": null }
    ],
    "summary_by_type_asset": [
      { "income_type": "FUNDING_FEE", "asset": "USDT", "income_total": "0.57738482", "row_count": 134, "unparsed_row_count": 0 }
    ],
    "row_count": 193,
    "row_limit_applied": false
  }
}
```

**字段硬规则：**

1. **所有 ID 一律字符串**。`txId` / `tranId` 是 19 位长整型（`2328408217636413776 > 2^53`），以 JSON number 下发会被浏览器 `JSON.parse` 静默改值，而它们是幂等键。入库也存 `TEXT`。
2. **金额与利率原样透传**币安返回的字符串：不 round、不 quantize、不转 float、不补零。**入库存 `TEXT`。**
3. **禁止用 SQL 的 `SUM()` / `AVG()` 聚合金额列**——SQLite 会把 TEXT 隐式转成浮点，静默丢精度。汇总一律把窗口内的行取到 Python 里用 `Decimal` 精确求和，输出 `format(total, 'f')`。
4. **缺失即 `null`**，绝不造 `0` / `""` / `—`。空串 `symbol`（`TRANSFER` 行）与空串 `trade_id` 归一化为 `null`。
5. **任一分组内出现无法解析的金额 → 该分组 `*_total` 为 `null` 且 `unparsed_row_count > 0`**；绝不用部分和冒充完整合计。此规则同样适用于 `delta` 与 `today`。
6. **排序即最终展示序**（时间倒序）：左栏 `ORDER BY accrued_at_ms DESC, tx_id DESC`；右栏 `ORDER BY time_ms DESC, income_type DESC, tran_id DESC`。前端不排序。
7. **`coverage` 是诚实性护栏，不是可选装饰**：`coverage.start_ms` 为本地已回补到的最早时刻；当 `window.start_ms < coverage.start_ms` 时 `coverage.complete` 必须为 `false`，前端**必须**显示「本地数据只到 <日期>」。**空结果绝不允许被呈现为「这段时间没有流水」。**
8. **`row_limit_applied`**：明细每栏最多返回 **500 行**（时间倒序取最新）；`row_count` 始终是窗口内**全量**条数，`summary` 也始终按**全量**计算，与截断无关。
9. `last_run.*_status` 三值：`ok` / `error`（`*_error` 为稳定短码）/ `disabled`（私有通道未启用）。短码集合：`interest_history_failed`、`um_income_failed`、`rate_limited`、`private_channel_disabled`。**不得**携带币安原始报文或 URL。
10. `delta.complete` 为 `false` 表示尚不足两次成功定时刷新、基准不可靠（首次启动的一小时内），此时前端显示「统计基准建立中」，**不显示可能误导的增量数字**。
11. `today.day_start_ms` 为**北京时间**当日 00:00；`today` 按流水**发生时间**归属，`delta` 按**入库时间**归属，两者口径不同、不得混用。

### 13.3 `GET flow-log` 的非 200

| 情况 | 状态码 | 响应体 |
|---|---|---|
| `start`/`end` 缺失、非纯数字或 `start >= end` | `400` | `{"error":"invalid_window","detail":"…"}` |
| 服务未装配 | `503` | `{"error":"flow_log_unavailable","detail":"flow-log service not configured"}` |

窗口长度**不再有 30 天上限**（读的是本地库）。

### 13.4 `POST refresh` 的响应

| 情况 | 状态码 | 响应体 |
|---|---|---|
| 完成（无论两栏成功与否） | `200` | `{"run_id":129,"kind":"manual","finished_at_ms":…,"interest_status":"ok","interest_error":null,"interest_new_row_count":2,"income_status":"ok","income_error":null,"income_new_row_count":0,"truncated":false}` |
| 已有拉取在飞行中 | `429` | `{"error":"flow_log_busy","detail":"另一次流水拉取正在进行"}` |
| 私有通道未启用 / 离线 | `409` | `{"error":"private_channel_disabled","detail":"私有只读通道未启用"}` |
| 服务未装配 | `503` | `{"error":"flow_log_unavailable","detail":"…"}` |

**手动刷新写入数据，但不移动 `delta.baseline_ms`**（§17.4）——它带进来的新行会计入下一次定时刷新的增量，不会被吞掉。

### 13.5 上游拉取（仅 §17 的 run 使用）

| 栏 | 端点 | 参数 | 停止条件 | 页数上限 |
|---|---|---|---|---|
| 左 | `GET /sapi/v1/margin/interestHistory`（`https://api.binance.com`） | `startTime`/`endTime`/`size=100`/`current=1..` | 累计行数 ≥ `total`，或本页 `rows` 为空 | **40 页** |
| 右 | `GET /papi/v1/um/income`（`https://papi.binance.com`） | `startTime`/`endTime`/`limit=1000`/`page=1..` | 本页行数 < `limit`，或本页为空 | **10 页** |

- 右栏**不传** `incomeType`、**不传** `symbol`（要全类型）。
- 任一页失败 → **该栏本次 run 记为 `error` 且该栏本次不写库**（半截账比没有账更危险）；另一栏不受影响。
- 达到页数上限仍未拉完 → run 记 `truncated=true`，页面必须显示覆盖可能不完整。
- 权重实测：sapi ≈ 1/次、papi ≈ 30/次。日常增量每小时约 1 次 papi + 1–2 次 sapi ≈ 32 权重/小时；30 天回补一次性约 17 sapi + 1 papi。

### 13.6 白名单新增（deny-by-default 不变）

```python
("GET", "/sapi/v1/margin/interestHistory"): "https://api.binance.com",
("GET", "/papi/v1/um/income"):              "https://papi.binance.com",
```

签名出口仍只有 `binance_signing`；审计日志仍只记 `(logical_endpoint, method, http_status, error, latency_ms)`。`backend/tests/test_private_client.py` 的白名单条数断言（现 13）与 base-url 集合断言须同步更新为 15。

新增 fetcher **不得**写 `PrivateClient.last_error`（那是快照 `borrow_validation` 的降级依据），失败以既有 `PrivateEndpointError` 上抛。

### 13.7 前端渲染契约

| 项 | 约定 |
|---|---|
| 容器 | `#flow-log-panel`，位于 `#private-panel` 之后、市场表面板之前，**仍在 `#market-view` 内**，默认 `display:none` |
| 打开方式 | 点 `#btn-flow-log` 展开/收起（同步 `aria-expanded`）；首次展开自动 `GET` 一次（近 7 天） |
| 常驻状态条 | 「本地数据：<coverage.start> 起 · 上次刷新：<last_run 时间>（成功/失败短码中文）· 每小时整点后 1 分钟自动刷新」；`coverage.complete=false` 时追加「本地数据只到 <日期>，更早的没有」 |
| 增量区块 | 「自 <baseline 时刻> 以来新增」：左栏按币种的新增利息；右栏按（类型，币种）的新增资金费/手续费；再加**按合约的资金费新增排行**。`delta.complete=false` 时改显「统计基准建立中」 |
| 参照区块 | 「今日累计」（北京时间当日，按发生时间）与当前窗口的区间累计（`summary_*`） |
| 时间窗 | `近7天` / `近30天` / `自定义`（起止日期）；自定义无 30 天上限 |
| 手动刷新 | `#flow-log-refresh` → `POST /api/private-ledger/refresh`，完成后重新 `GET`；进行中禁用按钮；`429` 显示「正在刷新，请稍候」 |
| 轮询 | 面板展开期间**允许且仅允许一个**流水日志专用 60 秒轮询定时器（纯本地读），**收起时必须 `clearInterval`**；除此之外不得新增任何定时器 |
| 加载中 | 栏内 skeleton；**保留上一次成功数据**不清空 |
| 三态 | 「该时间窗无记录」/ 「上次刷新失败：<中文>」/ 「私有通道未启用」必须可区分；一栏失败不影响另一栏 |
| 明细上限 | 后端最多返回 500 行/栏；`row_limit_applied=true` 时显示「共 N 条，显示最近 500 条」。前端**不做二次截断**、不重算汇总 |
| 金额遮蔽 | 复用 `state.privacyHidden`：隐藏态下利息、本金、`income`、所有汇总与增量一律 `****`；时间、类型、币种、`symbol` 不遮蔽 |
| 时间 | 一律 `formatBeijing(ms)` |
| 窄屏 | ≤900px 双栏改上下堆叠单列 |

**冻结的新 DOM id 集合**（self-check 须逐个注册）：

```text
btn-flow-log, flow-log-panel, flow-log-status-bar, flow-log-coverage-note,
flow-log-range-7d, flow-log-range-30d, flow-log-range-custom,
flow-log-custom-start, flow-log-custom-end, flow-log-custom-apply,
flow-log-refresh, flow-log-delta, flow-log-delta-interest, flow-log-delta-income,
flow-log-delta-symbols, flow-log-today, flow-log-filters,
flow-log-filter-funding, flow-log-filter-commission, flow-log-filter-realized,
flow-log-filter-transfer, flow-log-filter-other,
flow-log-interest-status, flow-log-interest-summary, flow-log-interest-body,
flow-log-income-status, flow-log-income-summary, flow-log-income-body
```

`type` / `incomeType` 中文文案沿用 §3.1 与 §3.2 两张对照表；资金费 `income > 0` 文案「收取」、`< 0`「支付」。

---

## 14. 本地账本与数据库（冻结）

库文件：`data/ledger-flow.sqlite3`（与既有 `borrow-tasks.sqlite3` / `hedge-open-tasks.sqlite3` 同目录，该目录已 gitignore）。连接模式沿用既有 store：`sqlite3.connect(path, check_same_thread=False)` + `threading.RLock`。

```sql
CREATE TABLE IF NOT EXISTS interest_rows (
  tx_id             TEXT PRIMARY KEY,
  accrued_at_ms     INTEGER NOT NULL,
  asset             TEXT NOT NULL,
  raw_asset         TEXT,
  principal         TEXT,
  interest          TEXT,
  interest_rate     TEXT,
  type              TEXT,
  isolated_symbol   TEXT,
  first_seen_run_id INTEGER NOT NULL,
  first_seen_at_ms  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interest_time  ON interest_rows(accrued_at_ms);
CREATE INDEX IF NOT EXISTS idx_interest_seen  ON interest_rows(first_seen_at_ms);

CREATE TABLE IF NOT EXISTS um_income_rows (
  income_type       TEXT NOT NULL,
  tran_id           TEXT NOT NULL,
  time_ms           INTEGER NOT NULL,
  symbol            TEXT,
  income            TEXT,
  asset             TEXT,
  info              TEXT,
  trade_id          TEXT,
  first_seen_run_id INTEGER NOT NULL,
  first_seen_at_ms  INTEGER NOT NULL,
  PRIMARY KEY (income_type, tran_id)
);
CREATE INDEX IF NOT EXISTS idx_income_time ON um_income_rows(time_ms);
CREATE INDEX IF NOT EXISTS idx_income_seen ON um_income_rows(first_seen_at_ms);

CREATE TABLE IF NOT EXISTS flow_refresh_runs (
  id                        INTEGER PRIMARY KEY AUTOINCREMENT,
  kind                      TEXT NOT NULL,      -- scheduled | manual | backfill | startup_catchup
  started_at_ms             INTEGER NOT NULL,
  finished_at_ms            INTEGER,
  window_start_ms           INTEGER NOT NULL,
  window_end_ms             INTEGER NOT NULL,
  interest_status           TEXT NOT NULL,      -- ok | error | disabled
  interest_error            TEXT,
  interest_fetched_row_count INTEGER NOT NULL DEFAULT 0,
  interest_new_row_count    INTEGER NOT NULL DEFAULT 0,
  income_status             TEXT NOT NULL,
  income_error              TEXT,
  income_fetched_row_count  INTEGER NOT NULL DEFAULT 0,
  income_new_row_count      INTEGER NOT NULL DEFAULT 0,
  truncated                 INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON flow_refresh_runs(finished_at_ms);

CREATE TABLE IF NOT EXISTS ledger_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- 约定 key：schema_version、coverage_start_ms、coverage_end_ms
```

硬规则：

1. **金额列一律 `TEXT`**，写入即原样字符串；**任何查询都不得对金额列使用 `SUM`/`AVG`/算术运算**。
2. **幂等写入**：利息 `INSERT ... ON CONFLICT(tx_id) DO NOTHING`；合约流水 `ON CONFLICT(income_type, tran_id) DO NOTHING`。**已存在的行绝不覆盖**——`first_seen_run_id` / `first_seen_at_ms` 必须保持首次入库时的值，否则增量统计会把旧行重复计入。
3. `first_seen_at_ms` 由服务端在写入事务内取一次统一时钟值，同一次 run 写入的所有行共用同一个值。
4. **永久保留，不做自动清理**（Human 2026-08-04 决定 N4）。体量估算：每小时几十行、一年约几十 MB。
5. 一次 run 的所有写入（明细 + run 记录 + `ledger_meta`）在**同一个事务**内提交；失败则整体回滚，只留 run 记录里的 `error`。

---

## 15. 定时刷新与增量统计（冻结）

### 15.1 节拍

- 每小时 **整点后 1 分钟**（`HH:01`）执行一次 `kind="scheduled"` run；利息与合约流水**共用同一次 run**。
- 实现方式：守护线程每 **20 秒**醒一次，判断「当前分钟 ≥ 1」且「当前自然小时还没有成功的 scheduled run」→ 立即执行。**不用 sleep 到精确时刻**——时钟跳变、机器休眠唤醒都会让精确定时失效，而"本小时是否已成功"这个判据天然幂等，也天然覆盖了漏跑补偿。
- 时钟：本地时钟（北京时间与 UTC 的整点对齐，差值为整小时，因此「整点后 1 分钟」两种时区含义一致）。
- 计息节拍是每小时整点（recon 实测相邻计息时间差恒为 3,600,000 ms）；资金费按各合约 4h/8h 结算，多数小时无新资金费行——这是正常的。

### 15.2 拉取窗口

```text
window_end   = now
window_start = max( coverage_end_ms - 3h , now - 30d )
首次（空库） = kind "backfill"，window_start = now - 30d
```

- **必须回拉 3 小时重叠窗口**：资金费会分批到账、也会晚到（原型脚本 `币安套费率策略，逐仓杠杆.js` 因此在发现新资金费后 `Sleep 10s` 再拉一次）。靠幂等键去重，重叠不会产生重复行。
- 若停机较久导致缺口 > 30 天，窗口截断为最近 30 天，并把 `coverage` 标为不连续（`coverage_start_ms` 不变、页面提示可能有缺口）。**不得**静默留下空洞。

### 15.3 失败与重试

- 某次 run 失败（任一栏 `error`）→ **5 分钟后重试，本小时最多重试 2 次**（共 3 次尝试）；仍失败则等下一个整点。
- 每次尝试都写一条 `flow_refresh_runs` 记录（含 `error` 短码），页面显示最近一次的状态与连续失败次数。
- 进程启动时：若「上次成功 run」距今超过 1 小时（或库为空），立即执行一次 `kind="startup_catchup"`（或 `backfill`）。
- **单飞**：`scheduled` / `manual` / `backfill` / `startup_catchup` 共用一把进程级锁，同一时刻只允许一个 run；`POST refresh` 抢不到锁即 `429`。
- 私有通道未启用或离线模式：**调度器不启动**；`GET flow-log` 仍可读本地历史，`last_run` 反映最后一次真实 run；库为空且从未成功 → 页面显示「私有通道未启用，本地无数据」。

### 15.4 「本次新增」的定义（Human 决策 N1 = 方案 c）

```text
baseline_ms = 倒数第二次成功 scheduled/startup_catchup run 的 finished_at_ms
本次新增    = 所有 first_seen_at_ms > baseline_ms 的行
```

- 口径是**入库时间**，不是发生时间：这正是「距上一次整点刷新以来，我们新知道了什么」。
- **手动刷新不移动 `baseline_ms`**（Human 决策 N6 = 方案 c）：手点带进来的行仍落在当前增量窗口内，下一次整点刷新才把基准前移。这样「我现在就要看最新的」不会把统计清零。
- 页面**必须把基准时刻写在标题上**（「自 10:01 以来新增」），否则这个数字无法自解释。
- 不足两次成功 scheduled run 时 `delta.complete=false`，前端显示「统计基准建立中」而**不显示数字**。
- 增量分组：利息按 `asset`；合约流水按 `(income_type, asset)`；**再加**资金费按 `symbol` 的分组（Human 决策 N2），且 `symbol` 分组内仍按 `asset` 分列，**永远不跨币种相加**。
- 稳定参照（N1 方案 c 的另一半）：同时展示「今日累计」（北京时间当日、按**发生时间**归属）与当前时间窗的区间累计。三个数字口径不同，页面必须各自标注清楚。

### 15.5 本轮不做（已记为后续项）

- **微信公众号通知**：本轮不做，也不预留接口。
- **开单任务状态联动**（`running` → 非 `running` 时顺带刷新一次流水）：本轮不做。代码里已有现成挂点 `HedgeOpenTaskService.configure_cache_refresh(...)`（现挂快照刷新），将来加第二个回调即可，不需要改结构。
- 跨币种折 USDT 的「总净利」。
- CSV 导出、按借币任务归因、`crossMarginInterest` 未结展示。

---

## 16. 实现任务拆分（三个任务，串行交付）

| 序 | 任务 | 角色/默认模型 | 文件边界 |
|---|---|---|---|
| A | `backend-ledger-store-fetch-v1` | Implementer / `claude_glm`（`zhipu_glm`） | `backend/services/private_client.py`、`backend/ledger_flow/__init__.py`（新）、`backend/ledger_flow/domain.py`（新）、`backend/ledger_flow/store.py`（新）、`backend/tests/test_ledger_flow_domain.py`（新）、`backend/tests/test_ledger_flow_store.py`（新）、`backend/tests/test_private_client.py` |
| B | `backend-ledger-schedule-api-v1` | Implementer / `claude_glm`（`zhipu_glm`） | `backend/ledger_flow/service.py`（新）、`backend/ledger_flow/scheduler.py`（新）、`backend/app/server.py`、`backend/services/snapshot_service.py`（仅加只读访问器）、`backend/tests/test_ledger_flow_service.py`（新）、`backend/tests/test_ledger_flow_api.py`（新）、`docs/api/public-market-contract.md` |
| C | `frontend-dual-ledger-flow-log-v1` | Implementer / `kimi`（`moonshot`） | `frontend/index.html`、`frontend/self-check.js` |

- **零重叠**：三份 Allowed Files 两两不相交。`backend/ledger_flow/__init__.py` 由 A 创建后**只放包 docstring**，B 与 C 都不得再改它；B 一律用子模块路径导入（`from ..ledger_flow import service as ledger_service`）。
- **串行**：A → B → C。B 依赖 A 的 store/domain 接口，C 依赖 B 交付的 HTTP 形状；C 的 self-check 用自带 fetch mock 复刻 §13.2 的形状，**不需要共享 fixture 文件**。
- 分层理由：`domain.py` 纯函数（归一化/去重/排序/汇总/窗口校验/增量计算），零 I/O、可离线全覆盖；`store.py` 只管 SQLite 与幂等写入；`service.py` 只管拉取编排、run 记录、重试与单飞；`scheduler.py` 只管节拍。`PrivateClient` 只加两个**单页** fetcher，分页循环不进客户端。

### 16.1 验收命令

```bash
# 任务 A
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q \
  backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_store.py \
  backend/tests/test_private_client.py

# 任务 B
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q \
  backend/tests/test_ledger_flow_service.py backend/tests/test_ledger_flow_api.py

# 任务 C
node frontend/self-check.js
```

全部离线运行：不启动服务、不访问网络、不读凭据；上游一律用桩客户端，SQLite 用临时库。

---

## 17. 风险判定与流程

### 17.1 风险等级

按 `AGENTS.md` §8，本功能展示资金流水、手续费与已实现盈亏，且新增**本地账本**与**定时上游拉取**，属账务/资金语义，判定为 **`HIGH_RISK`**：每个实现任务交付后须 review-1 加 review-2，provider 隔离按 `agents/roles.md`（review-1 与被审部分作者跨 provider；review-2 与交付区间内所有实现/修复作者跨 provider）。

### 17.2 安全边界（红线）

- 仅新增 **2 条只读 GET** 白名单路径；GET-only、deny-by-default、门禁先于签名构造、单一签名出口全部不变。
- 无下单、无借还、无划转、无 gate 改动、无凭据读写或落盘、无部署。
- 新增的 `POST /api/private-ledger/refresh` 只写**本地库**、只触发**只读**上游 GET；不接受任何影响资金行为的参数。
- 不改快照 JSON schema、不改 60 秒快照调度、不改 cache-refresh、不改持仓合并、不改任何既有端点行为。

### 17.3 实现前的独立计划评审（`AGENTS.md` §8「计划评审」）

- **对象**：本文件 §11–§17 与三份实现 dispatch。
- **要求**：fresh 只读会话；模型须与计划作者（`opus5` / `anthropic`）**以及**两个实现 provider（`zhipu_glm`、`moonshot`）全部跨 provider。
- **推荐模型**：`deepseek`（2026-08-03 同类计划评审有先例）；备选 `codex`（`openai`）或 `grok`（`xai`）。
- verdict 返回 Planner，**不触碰 `rework_count`**。
- 必须回答的问题：
  1. 「本次新增」按入库时间、且手动刷新不移动基准——这个口径在资金费**分批/延迟到账**下会不会给出误导数字？3 小时重叠窗口够不够？
  2. `coverage` 护栏是否足以防止「本地没拉到」被读成「交易所没发生」？
  3. 幂等键（`txId` / `(incomeType, tranId)`）与「已存在的行绝不覆盖」是否足以保证增量不重复计数？
  4. 定时线程「每 20 秒醒一次 + 本小时是否已成功」的判据，在重启、时钟跳变、休眠唤醒下是否有漏跑或重复跑？
  5. 三个任务的文件边界是否真的零重叠？B 对 A 的接口依赖是否已在 §14/§16 写死？
  6. 金额全程 TEXT + Python `Decimal`、禁止 SQL 聚合——是否有遗漏的精度泄漏点？
  7. 定时上游拉取相对既有「上游 I/O 归 snapshot worker」的约定是新增了一个独立调度线程（借币调度器已有同类先例），边界是否可接受？

### 17.4 已知代价与遗留（写明以免被当成缺陷）

- `PrivateClient.audit_log` 是**无上限列表**（既有行为）；每小时的 run 再追加约 2–18 条。属既有问题，本轮不修。
- 「当前未结利息」不在页面上（§12 决议 3），左栏累计与账户负债无法在本页对照。
- 若同时跑起两个服务进程，两者都会调度（幂等写入不会产生脏数据，但会重复消耗权重，并可能把同一小时的增量拆开）。既有借币服务用 sidecar owner 锁解决同类问题；本轮**不做**该机制，仅在此记录。
- `REALIZED_PNL` / `TRANSFER` 默认关闭，打开后仅为明细，**不进任何汇总与增量**。
- 本地库是**账本**不是**权威**：它只反映我们成功拉到的部分。任何对账争议以币安为准。

---

## 18. Human 已拍板的产品决策（2026-08-04）

| # | 决策点 | 结论 |
|---|---|---|
| Q1 | 右栏默认筛选 | 资金费 + 手续费默认开，盈亏/划转默认关 |
| Q2 | 默认时间窗 | 近 7 天；另给近 30 天与自定义（自定义不受 30 天限制） |
| Q3 | 左栏未结利息 | 不展示 |
| Q4 | symbol / 任务过滤 | 不做 |
| Q5 | 本地存储 | **存本地 SQLite 并按幂等键去重**（推翻早先「不落盘」的推荐） |
| Q6 | CSV 导出 | 不做 |
| N1 | 「本次新增」口径 | 方案 c：主位按刷新批次（入库时间），旁边加今日累计 / 区间累计参照 |
| N2 | 新增金额分组 | 按币种、按类型分列（硬约束）**加**资金费按合约排行 |
| N3 | 首次回补范围 | 30 天 |
| N4 | 本地保留期 | 永久保留，不自动清理 |
| N5 | 自定义窗是否可超 30 天 | 可以；超出本地覆盖范围时必须显式提示 |
| N6 | 手动刷新 | 保留按钮；手动刷新**不移动**增量统计基准 |
| N7 | 交付拆分 | 切三份：后端 A（拉取+库+去重）→ 后端 B（调度+增量+接口）→ 前端 |
| — | 其他默认（Human 未反对） | 回拉 3 小时重叠窗口；失败 5 分钟重试最多 2 次；重启超时补拉；利息也计入「本次新增」；金额全程 TEXT/`Decimal`；库文件 `data/ledger-flow.sqlite3`；本轮不做微信通知与开单任务联动 |
