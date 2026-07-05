# 私有账户数据接入 v1 — DRAFT-1 独立评审

评审者：Claude Opus 4.6（Anthropic）  
评审对象：`docs/private-account-v1-direction-draft.md`（DRAFT-1）  
基线：`docs/phase2-direction-draft.md`（FROZEN，Codex ACCEPT-FREEZE）  
契约参考：`docs/api/public-market-contract.md` v0.2 + `schemas/api/public-market/snapshot.schema.json`

---

## 逐节评审

### §1 背景与目标 — AGREE

四项目标清晰且有业务价值。目标 1（真实档位利率）与目标 4（净收益测算）直接
解决 ADR-5 遗留的"VIP0 基准 ≠ 账户真实成本"问题。目标 2（全覆盖借币验证）
是负费率策略可执行性的必要前置。目标 3（持仓余额 GET 轮询）遵循"零红线冲突"
原则合理。

### §2 与冻结基线的关系 — AGREE

永久禁令维持不变，websocket 后置为独立基线修正轮——与基线 §3.2 永久禁止条款
一致。"本轮禁止实现任何 websocket 铺垫代码"表述足够刚性。

### §3 功能范围 — REWORK（两项须澄清/修正）

**§3.1 真实借币利率：REWORK**

- E1 `GET /papi/v1/margin/marginInterestHistory`（L186218）——`llms-full.txt`
  原文确认存在于 Portfolio Margin REST API 区块（L186073 起），Operation ID
  `getMarginBorrowLoanInterestHistory`，描述为"获取杠杆利息历史"。作为已发生
  利息的事后校验端点，语义正确。**AGREE**。
- E2 `GET /sapi/v1/margin/next-hourly-interest-rate`（L37035, L151129, L189205）
  ——该端点属于**经典杠杆 `/sapi` 族**（详细规格见 L189205 起
  `borrow-repay` 分类），Operation ID `getFutureHourlyInterestRate`。草案正确
  标注"需验证统一账户适用性"，但存在以下问题：
  1. **E2 是 `/sapi` 端点，不是 `/papi`**。DRAFT-1 §3.1 将 E1 标为 `/papi`，
     E2 标为 `/sapi`，但 §5 安全/白名单扩项（E1-E4 四个签名 GET）暗示全部
     走统一通道。需明确：E2 是否走 `api.binance.com`（sapi）还是
     `papi.binance.com`？当前 `private_client.py` 白名单中 sapi 端点走
     `api.binance.com`，papi 走 `papi.binance.com`（L41-46），E2 作为 sapi
     端点应走前者——但草案未显式标注 base_url 归属。
  2. **统一账户下 `/sapi` 利率端点的可用性是核心风险**。文档 L189205
     仅显示端点标题和 Operation ID，未展示参数/响应详情。该端点出现在
     经典杠杆（Margin Account/Trade）API 规格中，而非 Portfolio Margin
     `/papi` 区块。统一账户用户调用 `/sapi` 杠杆端点是否返回有效数据？
     草案已识别此问题（"fallback = crossMarginData VIP 利率表 + 账户实际
     档位"），但 fallback 路径本身引入了新的问题——账户 VIP 档位来源未
     指定任何具体端点。
  3. **草案引用了 L37035/L151129 两处 changelog 条目 + L189205 规格条目作为
     E2 的证据**，行号经核实**全部准确**。

  **要求**：E2 的白名单归属（sapi base_url）和 fallback 链（VIP 档位来源端点）
  须在 stage design 前明确。H_intake discovery 必须将 E2 统一账户适用性验证
  列为 BLOCKER 级实抓项。

**§3.2 全覆盖借币验证：AGREE**

从 bounded top-N 扩展到全部负费率 MARGIN_SPOT_CANDIDATE ∩ CRYPTO 候选，
直接回应 ADR-5 观察（bounded top-N 全不可借）。限速预算交 O4 讨论合理。

**§3.3 持仓与余额：AGREE**

- E3 `GET /papi/v1/balance`（L186080）——原文确认"查询账户余额"，Operation ID
  `accountBalance`，位于 Portfolio Margin REST API `account` 分类。✓
- E4 `GET /papi/v1/um/positionRisk`（L186324）——原文确认"用户UM持仓风险"，
  Operation ID `queryUmPositionInformation`。✓
- 60s 自动刷新沿用现有节奏，不引入新刷新机制。合理。

**§3.4 净收益测算：AGREE（公式方向语义正确）**

- **负费率行**：借币做空现货 + 做多永续收费率。当费率为负时，做多永续方
  **收取**资金费（做空方支付做多方），因此
  `net = |daily_funding_rate| − 借币日利率` 正确——收入腿是绝对值
  （负费率的绝对值 = 做多方收入），成本腿是借币利率。
  **语义验证通过**。
- **正费率行**：现货做多 + 做空永续收费率。做空方收取资金费，无借币腿，
  `net = daily_funding_rate` 直接就是收益。正确。
- Decimal 字符串运算 + 禁 float——与基线红线一致。
- 交易成本不建模——合理，留后续轮。

**§3.5 排序：AGREE**

净收益降序替代 abs 日费率降序作为新排序基准是自然演进。null 末尾 +
symbol 升序 tie-break 沿用现有全序约定。交 O1 评审裁定合理。

### §4 契约草案 v0.3 — AGREE（一项建议）

- `net_daily_yield`（string|null）新增合理。
- `daily_interest_account` 新增 + 保留 `daily_interest_vip0` 对照合理。
- `private_account` 新块——三态语义沿用 `borrow_validation` 风格，一致。
- schema 升 v0.3；全部新字段可缺失 + 优雅降级——正确。

**建议**：`private_account` 块的 JSON 结构仅示意
`{"balances": [...], "um_positions": [...], "checked_at": null, "error": null}`，
缺少字段级类型定义。`balances` 数组元素和 `um_positions` 数组元素的字段名、
类型、脱敏规则应在 stage design 时冻结（参照 v0.2 中 `borrow_validation` 的
详细规格）。此处不构成 REWORK，但 stage design 必须补全。

### §5 安全与隐私条款 — REWORK（一项必改 + 一项建议）

**REWORK 项：数值脱敏的边界定义不足**

草案说"落档样本与日志一律 capture-time 脱敏（数值换占位、保留字段名与类型）；
真实数值只允许出现在本地页面渲染"。这比基线 §3.5 的脱敏政策更严格（基线主要
关注 uid/email/balance 等标识字段），但边界定义不够：

1. **`net_daily_yield` 是否属于敏感数值？** 它由 `|funding_rate|` − 借币利率
   计算，其中 funding_rate 是公开数据，但 `daily_interest_account`（真实档位
   利率）可推断用户 VIP 等级。如果 `net_daily_yield` 落档不脱敏，则间接泄露
   VIP 档位。草案应明确：`net_daily_yield` 和 `daily_interest_account` 均为
   敏感字段，落档时脱敏。
2. **`borrow_validation` 既有字段的脱敏状态未重申**。基线已有
   `daily_interest_vip0`（VIP0 公开数据，不敏感）、`max_borrowable` /
   `borrow_limit`（账户级，敏感），v0.3 新增字段应对齐声明。

**要求**：§5 须增加一个"敏感字段清单"，列出所有落档需脱敏的字段路径，
至少包括：`private_account.balances[].free/locked/...`、
`private_account.um_positions[].positionAmt/...`、
`borrow_validation.portfolio_account.max_borrowable/borrow_limit`（已有）、
`borrow_validation.classic_margin.daily_interest_account`（新）、
`net_daily_yield`（新，因可推断 VIP 档位）。

**建议**：O2（隐私模式开关）与此紧密相关——即使前端渲染真实值，也应考虑
页面截图/录屏场景。建议默认隐藏金额，点击显示。

### §6 复杂度评级与执行方式 — AGREE

MILESTONE 评级正确（白名单翻倍扩项 + 账户敏感数据首次入 UI）。并行模式
试运行 #2 + stage 分支制首跑合理。Task A/B 拆分预判清晰，耦合面 = v0.3 新
字段。

### §7 开放问题 — 逐项建议

见下文"开放问题建议"节。

### §8 已识别后续方向 — AGREE

websocket 实时化和开仓规划均合理后置。触发条件明确。

---

## 重点核查

### ① 净收益公式方向语义（§3.4 负费率=借币做空现货腿）

**结论：正确。**

- 负费率场景：funding_rate < 0 → 做多永续方收取资金费（收入 = |rate|），
  同时需借币做空现货对冲（成本 = 借币日利率）。
  `net = |daily_funding_rate| − daily_interest` 正确反映净收益。
- 正费率场景：funding_rate > 0 → 做空永续方收取资金费，现货做多无借币。
  `net = daily_funding_rate` 正确。
- 边界：funding_rate = 0 时 net = 0（负费率公式）或 0（正费率公式），一致。
  `daily_interest` 缺失时 `net_daily_yield = null`，安全降级。

### ② E1-E4 候选端点与统一账户（非 Pro）的适配性

**结论：E1/E3/E4 适配性高；E2 有风险。**

| 端点 | 族 | llms-full.txt 位置 | 统一账户适配性 |
|------|-----|---------------------|----------------|
| E1 `/papi/v1/margin/marginInterestHistory` | papi | L186218 | ✓ 原生 Portfolio Margin 端点 |
| E2 `/sapi/v1/margin/next-hourly-interest-rate` | sapi | L37035, L151129, L189205 | ⚠ 经典杠杆端点，统一账户可用性须实测 |
| E3 `/papi/v1/balance` | papi | L186080 | ✓ 原生 Portfolio Margin 端点 |
| E4 `/papi/v1/um/positionRisk` | papi | L186324 | ✓ 原生 Portfolio Margin 端点 |

E2 是唯一的 `/sapi` 端点。文档（L189205）将其归类在 Margin Account/Trade
API 的 `borrow-repay` 子分类下，非 Portfolio Margin 区块。统一账户用户是否
能调用此端点并获得有效的预估利率**需要 H_intake discovery 实测**。草案已正确
识别此风险并提供了 fallback 方案。

**但 fallback 方案本身有缺口**："crossMarginData VIP 利率表 + 账户实际
档位"——账户实际 VIP 档位的来源端点未指定。`/papi` 族中似乎没有专门的
VIP 等级查询端点（llms-full.txt Portfolio Margin 区块无 vipLevel 相关端点）。
可能需要 `/sapi/v1/account/apiRestrictions`、`/api/v3/account` 等端点获取
VIP 等级，但这些可能不在当前安全白名单的预期范围内。

### ③ 安全/隐私条款漏洞

**发现两个问题（含上文 §5 REWORK 项）：**

1. **数值脱敏边界不清**（已在 §5 详述）——`net_daily_yield` 可推断 VIP
   档位，应列入敏感字段。
2. **E3/E4 响应可能包含意外敏感字段**——`/papi/v1/balance` 返回完整的账户
   余额（含 free/locked/各币种数量），`/papi/v1/um/positionRisk` 返回完整
   持仓（含 positionAmt/entryPrice/unrealizedProfit 等）。草案说"落档脱敏"
   但未列出这些端点的完整响应字段清单。H_intake discovery 的脱敏规则应基于
   实际响应结构定义，而非假设。**建议**：stage design 的端点矩阵必须列出
   E3/E4 的完整响应字段 + 逐字段脱敏规则。

### ④ 与永久禁令的隐性冲突

**结论：未发现冲突。**

- 四个新端点全部是 GET（只读查询），不涉及任何交易语义。
- E1（利息历史）：查询而非执行。
- E2（预估利率）：查询而非执行。
- E3（余额）：查询而非执行。
- E4（持仓风险）：查询而非执行。
- 不涉及 POST/PUT/DELETE、order/borrow/repay/transfer/withdraw/listenKey/
  websocket。
- 唯一需注意的是 E1 端点名含 "marginInterest" 字样，但其 Operation ID 明确
  为 `getMarginBorrowLoanInterestHistory`（GET 查询历史），非借还操作。

---

## 开放问题建议

### O1：排序基准——保持 abs 日费率 vs 改净收益降序？

**建议：改净收益降序。**

理由：净收益是最终决策指标。一个高费率但借币成本更高的标的，排在前面会误导。
`net_daily_yield` 为 null 的行（无借币利率数据）排末尾，用户知道这些行的
净收益尚不可评估。同时保留 `daily_funding_rate` 列让用户可见原始费率。

**实现注意**：如果同时存在正费率行和负费率行，需要明确正费率行的
`net_daily_yield`（无借币成本，= `daily_funding_rate`）和负费率行的
`net_daily_yield`（= `|rate| − interest`）在同一排序空间内的比较语义。
建议统一为"越大越好"降序。

### O2：隐私模式开关——默认隐藏金额，点击显示？

**建议：是，默认隐藏。**

理由：
1. 余额/持仓是账户最敏感的数据，不应在共享屏幕/截图场景下默认暴露。
2. 银行/券商 App 的通行做法是"眼睛图标"切换显隐。
3. 用户偏好应持久化到 localStorage。
4. 不增加复杂度：一个 CSS class 切换 + 一个 localStorage key。

### O3：持仓展示范围——仅 UM 永续持仓，还是也含现货余额折算？

**建议：本轮仅 UM 永续持仓 + USDT/USDC 等稳定币余额。**

理由：
1. E4 (`positionRisk`) 只返回 UM 持仓，与本项目核心场景（资金费率套利）
   直接相关。
2. E3 (`balance`) 返回统一账户全币种余额，但现货持仓折算涉及价格转换
  （需引入额外的公允价格源），本轮不建模交易成本更不应引入折算。
3. 展示 USDT/USDC 等计价币余额有决策价值（可用保证金参考），不需折算。
4. 其他币种余额作为"持仓总览"可在后续开仓规划轮补全。

### O4：负费率全覆盖的限速预算

**建议：单轮探测上限 50 次调用，缓存 1h TTL，批量间隔 200ms。**

理由：
1. 截至当前市场，MARGIN_SPOT_CANDIDATE ∩ CRYPTO 负费率候选通常在 20-40
   个范围（取决于市场周期）。50 次上限有余量。
2. `/papi/v1/margin/maxBorrowable` 每次调用传单个 asset，weight 需在
   H_intake discovery 确认（可能是 5-10 weight/call）。50 × 10 = 500
   weight 在 Binance 1200/min 限额内可控。
3. 1h TTL 与现有 borrow_validation 缓存一致。
4. 200ms 间隔 = 5 req/s，远低于 Binance burst 限制。
5. 如果实际候选数超过 50，应按 abs(daily_funding_rate) 降序截断，并在
   `warnings` 中记录被截断的数量。

### O5：E2 统一账户适用性的 fallback 路线是否成立？

**建议：fallback 路线部分成立，但需补充 VIP 档位来源。**

理由：
1. `crossMarginData` 返回 asset × VIP 分档费率表——数据源可靠，当前已在
   白名单内。
2. 但 fallback 需要"账户实际 VIP 档位"来选取正确的利率行。草案未指定
   VIP 档位的查询端点。
3. 可能的 VIP 档位来源：
   - `/sapi/v1/account/apiTradingStatus`（`llms-full.txt` 待查）
   - 用户手动配置（最保守，零额外端点）
   - `/papi/v1/account`（统一账户信息，可能含 VIP 字段，L186086）
4. **建议的 fallback 链**：
   - 优先：E2 直接返回账户级预估利率 → 使用。
   - 次选：E2 不可用 → `/papi/v1/account` 取 VIP 档位 → crossMarginData
     查利率表 → 选对应档位行。
   - 最保守：VIP 档位不可查 → 使用 VIP0（当前行为）+ 在 UI 标注
     "基准利率（可能低于实际）"。
5. **H_intake discovery 应同时验证**：(a) E2 对统一账户是否返回数据；
   (b) `/papi/v1/account` 响应中是否包含 VIP 等级字段。

---

## 新发现风险

### P1 — E2 fallback 链 VIP 档位缺口

- **定位**：§3.1 第二段，E2 fallback 描述。
- **缺陷**：fallback 路线声明"crossMarginData VIP 利率表 + 账户实际档位
  （档位来源由 discovery 确认）"，但未指定任何候选端点来获取 VIP 档位。
  如果 discovery 无法确认档位来源，fallback 退化为 VIP0——与 Phase 2 行为
  相同，目标 1（真实档位利率）实质未达成。
- **建议修法**：在 §3.1 明确列出至少一个 VIP 档位候选端点（如
  `/papi/v1/account`），并声明：如果所有候选均不返回 VIP 信息，则 fallback
  到 VIP0 + 在 `net_daily_yield` 行标注"成本基于 VIP0 基准利率"。

### P2 — 白名单扩项从 4→8 端点的安全 review 负担

- **定位**：§5 白名单扩项。
- **缺陷**：当前白名单 4 端点（`private_client.py` L41-46），本轮扩至 8
  端点（E1-E4 + 现有 4 个）。白名单翻倍是 MILESTONE 评级的核心原因之一，
  但草案未提及 review-1/review-2 对扩项的具体检查清单。
- **建议修法**：stage design 中为白名单扩项定义检查清单：每个新端点须有
  (a) llms-full.txt 行号引用；(b) H_intake 脱敏实抓样本；(c) 响应字段
  敏感性分类；(d) deny-by-default 门控单测。这与基线 §3.3 技术门对齐，
  但应在 design 阶段显式列出而非留给实现发现。

### P2 — `private_account` 块的缓存策略未声明

- **定位**：§3.3 + §4。
- **缺陷**：E3/E4 的刷新频率说"沿用 60s 自动刷新节奏"（前端），但后端
  缓存策略未声明。`borrow_validation` 已有独立 1h TTL，E3/E4 数据（余额/
  持仓）的变化频率远高于借币参考数据——用户可能在 1h 内有新仓位。
- **建议修法**：§3.3 或 §4 声明 E3/E4 后端缓存 TTL（建议 ≤ 60s，与前端
  刷新对齐），并明确与 borrow_validation 1h TTL 的独立性。

### P3 — §3.2 全覆盖探测的定义模糊

- **定位**：§3.2"全部负费率 MARGIN_SPOT_CANDIDATE ∩ CRYPTO 候选"。
- **缺陷**："负费率"指的是当前快照时刻 `last_funding_rate < 0` 的行，
  还是"历史上曾出现过负费率"的行？前者随市场变化，后者需要额外的历史
  数据源。草案语义倾向前者（当前快照），但未显式说明。
- **建议修法**：§3.2 开头明确：探测范围 = 当前快照中
  `daily_funding_rate < 0 且 route_class == MARGIN_SPOT_CANDIDATE 且
  asset_tag == CRYPTO` 的全部行。

---

## 总结论：REWORK

### 必改清单

| # | 节 | 问题 | 要求 |
|---|-----|------|------|
| 1 | §3.1 | E2 fallback 链 VIP 档位来源缺失 | 列出至少一个候选端点 + 最终 fallback 声明 |
| 2 | §5 | 数值脱敏敏感字段清单缺失 | 增加逐字段脱敏声明（含 `net_daily_yield`、`daily_interest_account`、E3/E4 响应数值字段） |

### 建议改进（非 REWORK blocker）

| # | 节 | 建议 |
|---|-----|------|
| A | §4 | `private_account` 块的 balances/um_positions 字段级定义留 stage design 补全 |
| B | §3.3 | E3/E4 后端缓存 TTL 声明 |
| C | §3.2 | "全覆盖"探测范围显式定义 |
| D | §5 | 白名单扩项 review 检查清单 |

---

模型身份：Claude Opus 4.6（Anthropic，通过 Antigravity CLI 执行）  
本地北京时间: 2026-07-05 22:00 CST
