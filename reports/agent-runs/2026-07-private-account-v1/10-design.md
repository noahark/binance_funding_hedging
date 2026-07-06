# 10-design — 2026-07-private-account-v1（权威规格）

冲突裁决顺序：本文件 > 00-task > 方向基线（FROZEN）> 摸排报告。
实现细节冲突时以本文件为准；本文件未覆盖处按方向基线。

## §1 契约 v0.3（Task A 交付；wire `schema_version` 保持 v1，全部 additive）

### §1.1 rows 新增字段

- `net_daily_yield`：string|null。Decimal 运算、`quantize(Decimal('1E-8'))`、
  负零归一化为 `"0.00000000"`；禁 float。语义 = 机会质量评分（§0 定位）：
  - `daily_funding_rate < 0` 行：`abs(daily_funding_rate) − daily_borrow_rate`
    （可为负，如实输出）；`daily_borrow_rate` 不可得 → null。
  - `daily_funding_rate ≥ 0` 行：`= daily_funding_rate`（无借币腿）。
  - `daily_funding_rate` 为 null 行：null。
- `borrow_rate_source`：enum `next_hourly | rate_history | cross_margin_tier
  | vip0_reference` | null。仅负费率行按四级链取值；正费率行与不可得行
  = null。

### §1.2 排序与 sort_basis（ADR-3 修订，用户已批准）

- 顶层 `sort_basis`：enum `net_daily_yield | abs_daily_funding_rate`。
- **快照级单一基准**：私有成本腿可用（含 vip0_reference 档）→
  `net_daily_yield`：按 net 值降序、null 末尾、symbol 升序 tie-break；
  私有通道 disabled/error → `abs_daily_funding_rate`：Phase 2 现行为
  （全序回归测试必须保留）。
- 前端零排序逻辑（Phase 2 红线沿用），按 payload 顺序渲染并标注
  sort_basis。

### §1.3 成本腿四级链与 daily_interest_account

- `borrow_validation.classic_margin` 新增 `daily_interest_account`：
  string|null，账户级借币**日**利率。
- 四级链（顺序固定；每级"命中"定义按 H_intake 附录冻结的字段判定）：
  1. E2 返回有效预估利率 → `daily = hourly × 24`（Decimal）→
     source=`next_hourly`；
  2. E2b 最新点（同资产）→ 按其口径归一化为日 → source=`rate_history`；
  3. crossMarginData 利率表 + E5 的 VIP 等级选档 → source=`cross_margin_tier`；
  4. VIP 等级不可得 → VIP0 档（Phase 2 现行为）→ source=`vip0_reference`。
- 链判定在**快照级**做一次（不逐行探测利率端点）；逐资产利率从
  命中级别的数据源查表。全链断 → `daily_interest_account=null`、
  负费率行 net=null、source=null。

### §1.4 private_account 块（顶层，三态语义同 borrow_validation）

```json
"private_account": {
  "verified": false,
  "balances_unified": [{"asset": "", "total_balance": ""}],
  "balances_spot":    [{"asset": "", "free": "", "locked": ""}],
  "um_positions":     [{"symbol": "", "position_side": "", "position_amt": "",
                        "entry_price": "", "mark_price": "",
                        "unrealized_profit": "", "liquidation_price": ""}],
  "total_value_usdt": null,
  "valuation": {"price_source": "api_v3_ticker_price", "priced_at": null},
  "checked_at": null,
  "error": null
}
```

- 数值全部 string（Decimal 语义）；env 缺失/失败 → verified=false、
  三数组空、total null、error 填原因——公开快照照常渲染。
- **防重复计算（硬规则，测试必断言）**：
  `total_value_usdt = Σ(balances_unified 折算) + Σ(balances_spot 折算)`；
  统一账户余额已含 U 本位/币本位/全仓杠杆，**禁止**任何子账户再加一遍；
  `um_positions` 是敞口视图，其名义价值**禁止**计入 total。
- 折算：非稳定币按 `/api/v3/ticker/price`（摸排 §C：单 symbol weight=1，
  全量 weight=2——取**全量一次**建价格 map）折 USDT；USDT/USDC 按 1；
  无价格的资产计 0 并入 warnings。raw 字段 → 契约字段映射以 H_intake
  附录冻结（E3 响应结构文档未全列，以实抓为准）。

### §1.5 coverage / warnings

- `borrow_validation` 探测范围：当前快照 `daily_funding_rate < 0 ∧
  route_class==MARGIN_SPOT_CANDIDATE ∧ asset_tag==CRYPTO`，按 baseAsset
  去重；上限 `Config.borrow_check_max_calls`（默认 50）；超限按 abs
  日费率降序截断。
- 顶层 warnings 追加条目 + `borrow_validation` 块内
  `coverage: {"probed": n, "skipped": m, "reason": "rate_limit_budget"}`；
  被截断行 verified=false 且 error=`"not_probed_this_round"`——
  **禁止静默截断装 verified**。

### §1.6 缓存

- E3/E4/E6 + 价格 map：TTL ≤ 60s（与前端刷新对齐）。
- 利率链（E2/E2b/E5/crossMarginData）与 maxBorrowable：1h TTL 沿用。
- 两组 TTL 相互独立；429/-1003 单次有界退避沿用。

## §2 端点矩阵（12 签名 + 公开；权重列 = 摸排文档值，H_intake 实测冻结）

| # | method path | base_url | 权重(文档) | 用途 |
|---|---|---|---|---|
| W1-W4 | 既有白名单 4 项 | 既有 | 见摸排 §A | 不变 |
| E1 | GET /papi/v1/margin/marginInterestHistory | papi | 未见,实测 | 事后对账（本轮仅 discovery 采样，不进快照装配） |
| E1b | GET /papi/v1/portfolio/interest-history | papi | 未见,实测 | 同上，与 E1 比对归属 |
| E2 | GET /sapi/v1/margin/next-hourly-interest-rate | api(sapi) | 见摸排 | 成本腿链① |
| E2b | GET /sapi/v1/margin/interestRateHistory | api(sapi) | 见摸排 | 链② |
| E5 | GET /sapi/v1/account/info | api(sapi) | 见摸排 | 链③ VIP 档位 |
| E3 | GET /papi/v1/balance | papi | 未见,实测 | 统一账户余额 |
| E4 | GET /papi/v1/um/positionRisk | papi | 未见,实测 | UM 持仓 |
| E6 | GET /api/v3/account (omitZeroBalances=true) | api | 20(L23011) | 现货余额 |
| P5 | GET /api/v3/ticker/price（公开，全量） | api | 2 | 估值价格 map |

- E1/E1b 为 **discovery-only**：H_intake 采样比对后，本轮快照装配
  **不调用**（净收益输入只用链①-④）；其白名单条目仍登记（discovery
  脚本经同一出口）。
- H_intake 交付「冻结预算表」：三场景（初始化 / 稳态 60s / 探测 1h
  上限 50）× 实测权重 vs 官方限额；**既有 `/fapi/v1/fundingRate`
  top-N 调用计入稳态场景**（与 fundingInfo 共享 500/5min/IP，摸排
  L49242）。
- **§2.A 字段矩阵附录**（bookkeeper 据实抓补写）：E2/E2b/E5/E3/E4/E6
  每端点 raw 字段 → 契约字段 → 类型 → 是否进 git 脱敏。

## §2.A H_intake 冻结附录（bookkeeper 据 live capture 补写）

> 署名：bookkeeper（claude_glm fresh 专职会话）。证据 =
> `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/`（sha256 全表
> + 实测 weight 头见该目录 `evidence-index.md`）。**冻结**契约：实现阶段不得超表
> 调用、不得改字段映射；变更走 R3 升级。G2 阻断门 E3/E4/E6 实测全 200 PASS。

### §2.A.1 实测限频权重（G3；单次调用）

权重取自响应头：`X-MBX-USED-WEIGHT(-1M)` = api/papi IP 池；
`X-SAPI-USED-IP-WEIGHT-1M` = sapi 单接口 IP 池；`X-SAPI-USED-UID-WEIGHT-1M` =
sapi 单接口 UID 池。**api 与 papi 是独立 X-MBX 池**（实测 account=24 <
positionRisk=25 的非单调性证实，不可能共池）。

| 端点 | 池 | 实测单次 | 文档值 | 备注 |
|---|---|---|---|---|
| `/api/v3/ticker/price` 全量（P5） | api IP | **4** | 2(L23025) | 实测高于文档；估值价格 map |
| `/api/v3/account` E6（omitZero=true） | api IP | **20** | 20(L23011) | 一致 |
| `/sapi/v1/margin/allPairs` W1 | sapi IP | **1** | 未见 | |
| `/sapi/v1/margin/allAssets` W2 | sapi IP | **1** | 未见 | |
| `/sapi/v1/margin/crossMarginData` W3 | sapi IP | **50** | 未见 | 链③档表，偏重 |
| `/sapi/v1/account/info` E5 | sapi IP | **1** | 未见 | VIP/账户开关 |
| `/sapi/v1/margin/next-hourly-interest-rate` E2 | sapi IP | **100** | 未见 | **最重**；链①；必带 `isIsolated=false` |
| `/sapi/v1/margin/interestRateHistory` E2b | sapi **UID** | **60** | 未见 | 链②；走 UID 池 |
| `/papi/v1/balance` E3 | papi IP | **20** | 未见 | 统一账户余额 |
| `/papi/v1/um/positionRisk` E4 | papi IP | **5** | 未见 | 本账户空仓 |
| `/papi/v1/margin/maxBorrowable` W4 | papi IP | **5/次** | sapi 同名 750 UID(L36814) | **papi 版远低于 sapi 版**；借币探测 |
| `/papi/v1/margin/marginInterestHistory` E1 | papi IP | **10** | 未见 | discovery-only，不进装配 |
| `/papi/v1/portfolio/interest-history` E1b | papi IP | **50** | 未见 | discovery-only，不进装配 |

> papi 单次权重由累计头增量推导（balance 为 papi 首调用≈20；后续 delta：
> positionRisk≈5 / maxBorrowable≈5 / marginInterestHistory≈10 / portfolio≈50）。

### §2.A.2 三场景预算 vs 官方限额（冻结；实现不得超表）

官方限额（摸排 §B）：api REQUEST_WEIGHT **6000/min/IP**；sapi 单接口 IP
**12000/min/IP**、UID **180000/min/UID**；fapi fundingRate/fundingInfo **500/5min/IP**。

**场景 1 · 初始化一轮**（冷启全量；E1/E1b discovery-only 不计入装配）：

| 池 | 调用（各 1 次） | 合计 | 限额 | 余量 |
|---|---|---|---|---|
| api IP | ticker/price(4) + account(20) | 24 | 6000/min | 99.6% |
| sapi IP（逐端点独立限） | allPairs 1 / allAssets 1 / crossMarginData 50 / E5 1 / E2 100 | 每端点 ≤100 | 12000/min·端点 | >99% |
| sapi UID | E2b 60 | 60 | 180000/min | >99.9% |
| papi IP | balance(20) + positionRisk(5) | 25 | 账户 IP 权重 | 充裕 |

**场景 2 · 稳态每 60s 一轮**（E3/E4/E6 + price map TTL≤60s；利率链 W3/E5 与
maxBorrowable TTL 1h，不每轮触发）：

| 池 | 每分钟调用 | 合计/min | 限额 | 余量 |
|---|---|---|---|---|
| api IP | ticker/price(4) + account(20) | 24 | 6000 | 99.6% |
| sapi IP（E2 端点） | next-hourly 100 | 100 | 12000 | 99.2% |
| papi IP | balance(20) + positionRisk(5) | 25 | — | 充裕 |

> 既有 fapi 公开调用（premiumIndex / fundingInfo / **fundingRate top-N**）沿用
> Phase 2 预算，与 fundingInfo 共享 fapi 500/5min/IP；**本轮新增端点不含 fapi**，
> Phase 2 该池预算不变。

**场景 3 · 借币探测每 1h 一轮**（上限 `borrow_check_max_calls=50`，并发≤2、
间隔≥200ms、1h TTL）：

| 池 | 每小时调用 | 合计/h | 限额 | 余量 |
|---|---|---|---|---|
| papi IP | maxBorrowable 5×50=250 + 稳态 balance/positionRisk 25×60=1500 | ≤1750/h | 峰值/min ≈ 250(burst)+25(steady)=275 | 远低于 6000/min 等价限 |

**结论**：三场景全部极宽松。**最紧端点 = E2 next-hourly（sapi IP 100/次）与 W3
crossMarginData（50/次）**，均单次级、远低于 12000/min。**papi maxBorrowable 5/次**
（vs sapi 同名 750 UID），借币探测 50 次/小时完全可行。

### §2.A.3 字段矩阵（G4）：raw path → 契约字段 → 类型 → 进 git 脱敏

**E2 `/sapi/v1/margin/next-hourly-interest-rate`**（链①，实测 200）：
raw `[{asset:STRING, nextHourlyInterestRate:STRING}]`（请求必带 `assets` + `isIsolated=false`，
缺 isIsolated → -3026）→ 契约 `borrow_validation.classic_margin.daily_interest_account`
= `nextHourlyInterestRate × 24`（Decimal）；`borrow_rate_source="next_hourly"`。
类型 STRING；脱敏：**是**（利率）。

**E2b `/sapi/v1/margin/interestRateHistory`**（链②，实测 200）：
raw `[{asset:STRING, timestamp:LONG, dailyInterestRate:STRING, vipLevel:INT}]` →
契约 `daily_interest_account` = `dailyInterestRate`（**已是日利率，无需 ×24**）；
`source="rate_history"`（取最新点）。脱敏：dailyInterestRate **是**；vipLevel → `<ID>`。

**E5 `/sapi/v1/account/info`**（链③ VIP 选档，实测 200）：
raw `{vipLevel:INT, isMarginEnabled:BOOL, isFutureEnabled:BOOL, isOptionsEnabled:BOOL,
isPortfolioMarginRetailEnabled:BOOL}`（实测 `isPortfolioMarginRetailEnabled=true`
确认统一账户）→ 契约：`vipLevel` 用于 W3 crossMarginData 选档（链③）。脱敏：
vipLevel → `<ID>`（账户状态）；布尔不脱敏。

**E3 `/papi/v1/balance`**（统一账户余额，实测 200）：
raw `[{asset:STRING, totalWalletBalance:STRING, crossMarginAsset:STRING,
crossMarginBorrowed:STRING, crossMarginFree:STRING, crossMarginInterest:STRING,
crossMarginLocked:STRING, umWalletBalance:STRING, umUnrealizedPNL:STRING,
cmWalletBalance:STRING, cmUnrealizedPNL:STRING, updateTime:LONG, negativeBalance:STRING}]`
→ 契约 `private_account.balances_unified[].{asset, total_balance←totalWalletBalance}`。
脱敏：所有 `*Balance/*PNL/*Borrowed/*Free/*Locked/*Interest/negativeBalance` →
`<AMOUNT>`。**防重复计算硬规则（§1.4）**：`total_value_usdt` 只折算
`totalWalletBalance`（已含 um/cm/crossMargin 全部子项），子项禁止再加；
`negativeBalance`/`um_*/cm_*` 仅敞口视图，不计入 total。

**E4 `/papi/v1/um/positionRisk`**（UM 持仓，实测 200 但本账户空仓 → `[]`）：
raw 字段（recon §A-E4 + changelog，live 未观测）：`{symbol, positionAmt, entryPrice,
breakEvenPrice, liquidationPrice, unRealizedProfit, marginType, isolatedWallet,
notional, ...}` → 契约 `private_account.um_positions[].{symbol, position_amt←positionAmt,
entry_price←entryPrice, unrealized_profit←unRealizedProfit,
liquidation_price←liquidationPrice, ...}`。脱敏：所有数值串 → `<AMOUNT>`。
**Task A 待确认**：`position_side`（LONG/SHORT）在 papi positionRisk 无直接字段，
需据 `positionAmt` 符号或改取 fapi/um `positionSide`——持仓出现时实测复核（R3 升级口）。

**E6 `/api/v3/account`**（现货余额，实测 200）：
raw `{makerCommission:INT, takerCommission:INT, ..., commissionRates:{maker,taker,
buyer,seller:STRING}, canTrade/canWithdraw/canDeposit:BOOL, accountType:STRING,
balances:[{asset:STRING, free:STRING, locked:STRING}], permissions:[STRING], uid:INT}`
→ 契约 `private_account.balances_spot[].{asset, free, locked}`。脱敏：balances.free/
locked → `<AMOUNT>`；`uid` → `<ID>`；`commissionRates.*` → `<AMOUNT>`；
maker/takerCommission（INT 基点费率档）低敏不脱敏。

**W4 `/papi/v1/margin/maxBorrowable`**（既有，实测 200）：
raw `{amount:STRING, borrowLimit:STRING}` → 契约 `borrow_validation.portfolio_account
.{max_borrowable←amount, borrow_limit←borrowLimit}`。脱敏：**是**。

**E1/E1b**（discovery-only，本轮空数组，不进快照装配）：E1 `{total:INT, rows:[]}`、
E1b `[]`；归属比对本轮无数据，留作后续对账。

### §2.A.4 脱敏标记表（驱动 backend 落档扫描测试 §3.3）

进 git 的样本/报告/fixture 数值脱敏规则（运行时页面真实展示不受限）：
- 数值串（Decimal-shaped string）→ `<AMOUNT>`：所有 balance/amount/rate/price/qty/
  interest/pnl/borrow 字段。
- 账户标识整型 → `<ID>`：`uid`、`vipLevel`。
- 不脱敏：asset/symbol/accountType 等枚举串、布尔开关、makerCommission 等基点 INT、
  permissions 数组、timestamp(updateTime) LONG。
- URL 一律剥 query（只留 logical path）；key/secret/signature/recvWindow/timestamp
  永不落档。

### §2.A.5 成本腿四级链实测命中（10-design §1.3）

- **tier ① `next_hourly` 命中**（实测 200）：E2 带 `isIsolated=false` 返回有效
  `nextHourlyInterestRate` → `daily = hourly × 24`（Decimal），source=next_hourly。
- tier ② `rate_history` 亦可用：E2b `dailyInterestRate` 已是日利率，取最新点，
  source=rate_history。
- tier ③ `cross_margin_tier`：W3 VIP 表 + E5 vipLevel 选档。
- tier ④ `vip0_reference`：全断回退（Phase 2 行为）。
- 快照级探测一次定档；逐资产利率从命中级别数据源查表（§1.3）。

## §3 Task A 规格（后端）

### §3.1 允许文件

`backend/adapters/binance_public.py`（+ticker 全量拉取）、
`backend/services/private_client.py`（+8 白名单与 fetch 方法）、
`backend/services/snapshot_service.py`、`backend/domain/snapshot.py`、
`backend/config.py`（borrow_check_max_calls 等）、`backend/tests/**`、
`schemas/api/public-market/snapshot.schema.json`、
`docs/api/public-market-contract.md`（v0.3 amendment，引 H_intake
证据路径）、本 stage 报告文件。**禁**：classify.py、normalize.py、
frontend/**、scripts/**（discovery 脚本属 bookkeeper）。

### §3.2 架构约束（§3.6 基线成文化）

沿现有结构：`fetch_raw()` 聚合公开拉取建 map 组 → `build_rows` 合约
主循环 lookup 匹配 → 排序后才对候选集发私有签名调用。新增私有调用
一律走 private_client 单一出口；**禁止在行循环内发起 HTTP**。

### §3.3 安全测试（负向单测，每项必有）

- 8 个新端点的 deny-by-default 三态（白名单内 GET 通过 / 白名单外
  path raise / 非 GET raise，签名构造前拦截）；
- 单一 HMAC 出口 grep 断言更新后仍过；
- 落档扫描测试：`reports/**` 与 `backend/tests/fixtures/**` 中新增
  文件不含真实数值字段（按 §2.A 脱敏标记表驱动）；
- 降级矩阵：env 缺失 / E3 失败 / E6 失败 / 链全断 四态快照均 schema PASS。

### §3.4 计算测试向量（全部 Decimal 字符串断言）

1. daily=`-0.00060000`, 借币日率=`0.00020000` → net=`0.00040000`,
   source 按命中级；
2. daily=`-0.00060000`, 借币日率=`0.00080000` → net=`-0.00020000`
   （负净收益如实输出）；
3. daily=`0.00030000` → net=`0.00030000`, source=null；
4. hourly=`0.00000500` → 日=`0.00012000`（×24 归一化）；
5. 链全断：daily=`-0.00060000` → net=null, source=null；
6. daily=null → net=null。

### §3.5 排序测试向量

- sort_basis=net：AUSDT(net `0.00040000`) 排 BUSDT(daily abs 更大但
  借币贵，net `0.00010000`) 之前——**核心断言：净收益反超原始费率
  排名**；null 末尾；symbol tie-break。
- 私有通道 disabled：sort_basis=abs_daily_funding_rate，Phase 2 全序
  测试逐位回归（96 测试零回归）。

### §3.6 交付物

实现 + 测试 + `20-implementation-backend.md`（改动清单/测试原始输出/
自查表）→ 执行任务书末尾 R10 收尾段。

## §4 Task B 规格（前端）

1. **净收益列**：`net_daily_yield` string-shift 展示（复用
   formatFundingRate 逻辑，函数体禁改）；null → `—`；负值红色；
   `borrow_rate_source` 以徽标/悬浮展示（vip0_reference 档显著标注
   「基准利率」）。
2. **sort_basis 标注**：表头或页顶显示当前排序基准；**零排序逻辑**
   红线沿用（按 payload 顺序渲染）。
3. **私有面板**（新区块）：综合资产总览（total_value_usdt + 折算
   时点）→ 分账户明细（统一/现货两组）→ UM 持仓表（方向/数量/开仓价/
   标记价/未实现盈亏）；verified=false 时整面板显示「私有通道未启用」
   占位，不白屏。
4. **隐私开关**：默认隐藏金额类数值（占位 `****`），点击眼睛图标
   切换；偏好存 localStorage（仅布尔）；隐藏态不进 DOM 之外的任何
   输出。
5. **行联动**：有 UM 持仓的 symbol 行加方向标识（多/空小标），
   不显示数量与盈亏。
6. **降级**：新字段全缺失（旧后端）→ 现有页面行为不变。
7. self-check 新断言：净收益列存在与格式 / null→— / sort_basis 标注 /
   渲染顺序==fixture 顺序（用 §3.5 净收益反超用例）/ 私有面板三态 /
   隐私开关默认隐藏 / 无排序控件 DOM / 格式化函数体未变 / 中文口径
   （枚举三列「英文(中文)」保持）。
8. 交付 `20-implementation-frontend.md` → 执行 R10 收尾段。

## §5 设计期 fixture（两任务共用，Task A 产出后 H_intake 附录可替换）

bookkeeper 在 H_intake 后基于实抓脱敏样本生成
`backend/tests/fixtures/private-account-v1-design.json`（含：正费率行、
负费率可借行、负费率不可借行、net 反超用例对、not_probed 行、
private_account 三态样本）。Task B 开发自测用该 fixture。

本地北京时间: 2026-07-06 00:30 CST（Fable5 起草；§2.A 附录与冻结
预算表由 bookkeeper 据 H_intake 实抓补写并署名）
