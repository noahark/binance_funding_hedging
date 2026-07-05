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
