# 私有账户数据接入 v1 — 方向基线（FROZEN）

状态：**FROZEN 方向基线**（2026-07-05）。Codex 合成 ACCEPT-FREEZE
（原文逐字落档 `reports/agent-runs/private-account-v1-direction/
codex-synthesis.raw-output.md`）+ 用户批准「批准 DRAFT-3」。
**用户批准范围**：①方向冻结；②ADR-3 排序基准修订（abs 日费率 →
net_daily_yield 优先 + 降级回退）；③综合资产视图纳入；④隐私按自用
工程卫生执行。
Codex 非阻塞提醒（stage design 落实）：E6 须同时引用 endpoint spec 与
omitZeroBalances changelog；现货估值 price source 须冻结。
起草：Fable5（designer）。上游基线：`docs/phase2-direction-draft.md`
（FROZEN）。

修订记录：
- DRAFT-1（2026-07-05 21:10）：初稿。
- DRAFT-2（2026-07-05 22:30）：吸收 5 份独立评审（Codex/GLM/Kimi/Opus4.6
  REWORK + Gemini3.1-Pro ACCEPT，落档 `reports/agent-runs/
  private-account-v1-direction/review-*.md`）。
- DRAFT-3（2026-07-05 23:00）：吸收用户与 GPT 的 8 点问答（用户逐条批示）：
  ①新增 §0 定位声明（成本腿/净收益 = 展示与决策参考，非开单结算）；
  ②§5 隐私降级为**自用工程卫生**（脱敏只管进 git 的产物）；③§3.3 改为
  **综合资产视图**（统一账户 + 现货账户 + 持仓敞口，含防重复计算规则）；
  ④新增 §3.6 数据获取架构（参照遗留脚本 map 组模式）与**全端点限频预算
  总表**（H_intake 硬交付，禁止开发中途加端点）；⑤§8 websocket 改记
  「用户已表态的后续路线」+ 新增部署后续方向。

## 0. 定位声明（本轮产出物的语义边界）

- **成本腿与 `net_daily_yield` = 展示 + 决策参考 + 未来开仓规划的前置
  输入**，不是本轮实际开单的成本/收益结算。`net_daily_yield` 的准确
  语义是「当前机会质量评分」：解决"负费率机会看着高、扣掉借币利率后
  还有没有价值"。
- 实际开仓收益（手续费、返佣、BNB 抵扣、滑点、成交均价、仓位规模、
  持仓时间、结算次数）留给后续开仓规划轮，届时复用本轮字段。

## 1. 背景与目标

1. 借币成本腿接入**账户级利率**（§3.1 验证链；全链不可达则显式降级
   标注，不得静默退回 VIP0 而保留"真实档位"措辞）；
2. 负费率候选借币验证**全覆盖**（ADR-5 修订）；
3. **综合资产视图**：统一账户 + 现货账户 + UM 持仓敞口（GET 轮询）；
4. **净收益测算**（按 §0 定位）。

## 2. 与冻结基线的关系

继承 Phase 2 基线全部安全条款，**永久禁令本轮不变**（POST/PUT/DELETE、
交易语义端点、下单/借还执行/划转/提现、listenKey/user data stream/
websocket）。本轮为 Phase 2 下游增量，非基线修正；禁止 websocket
铺垫代码。websocket 的后续路线见 §8（用户已表态，另开修正轮）。

## 3. 功能范围

### 3.1 账户借币利率（成本腿验证链，H_intake 全部实测）

候选端点（行号 = llms-full.txt，GLM/Opus 已回读核实）：

| # | 端点 | 族 | 用途 |
|---|---|---|---|
| E1 | `GET /papi/v1/margin/marginInterestHistory`（L186218） | papi | 仅事后对账，不作净收益输入 |
| E1b | `GET /papi/v1/portfolio/interest-history`（L186318） | papi | 统一账户负余额收息历史；与 E1 并抓比对，确定统一账户真实 borrow cost 归属 |
| E2 | `GET /sapi/v1/margin/next-hourly-interest-rate`（L37035/L151129/L189205） | sapi | **成本腿首选**（开仓前估算）；统一账户适用性 = BLOCKER 级实测 |
| E2b | `GET /sapi/v1/margin/interestRateHistory`（L150993 官方指定替代已弃用端点） | sapi | fallback 二级 / 校验 |
| E5 | `GET /sapi/v1/account/info`（L6704，含 VIP 等级） | sapi | fallback 三级档位来源 |

**四级 fallback（顺序固定，触发条件 discovery 写死）**：
① E2 适用 → hourly × 24（单位归一化写死），`borrow_rate_source =
"next_hourly"`；② E2b 最新点 → `"rate_history"`；③ crossMarginData VIP
表 + E5 档位 → `"cross_margin_tier"`；④ VIP0 基准 + UI 显著标注 →
`"vip0_reference"`（§1 目标 1 记降级达成）。各级口径与 base_url 以
discovery 实抓冻结。

### 3.2 负费率候选借币验证全覆盖（ADR-5 修订）

- 范围：当前快照 `daily_funding_rate < 0 ∧ MARGIN_SPOT_CANDIDATE ∧
  CRYPTO`，按 baseAsset 去重；bStock 不探测。
- 限速预算：单轮 maxBorrowable 上限默认 **50**（可配）、超限按 abs
  日费率降序截断、并发 ≤ 2、间隔 ≥ 200ms、1h TTL、有界退避沿用。
- **语义澄清（用户问 5）**：限速只约束**私有签名探测调用量**，页面
  展示不减——全市场行照常展示，未验证行标「未验证/待下轮」；coverage
  与截断数写入 warnings，禁止静默截断装 verified。

### 3.3 综合资产视图（用户批示 6，改自 DRAFT-2 的"不折算"）

- 数据源：
  - **E3** `GET /papi/v1/balance`（L186080）：**统一账户**余额——已含
    U 本位、币本位、全仓杠杆账户的全部资产总和；
  - **E6** `GET /api/v3/account`（L22771 在案，spot 族，签名 GET，
    建议带 `omitZeroBalances`）：**现货账户**余额与持有标的；
  - **E4** `GET /papi/v1/um/positionRisk`（L186324）：UM 永续持仓。
- **防重复计算规则（硬约束）**：
  1. 资产总值 = 统一账户余额（E3）+ 现货账户余额（E6）——两个钱包
     互斥不相交，**禁止**再把 U 本位/币本位/全仓杠杆资产单独加一遍
     （E3 已含）；
  2. UM/CM 持仓是**敞口视图**，其保证金已计入 E3 余额，**禁止**把
     持仓名义价值计入资产总值；
  3. 折算：非稳定币资产按 USDT 估值汇总，价格源用既有行情快照或
     现货 ticker（口径与更新时点 stage design 冻结）。
- 展示：综合资产总览（按 USDT 折算）+ 分账户明细 + UM 持仓敞口；
  symbol 行联动标注只给「有持仓/方向」。前端沿用 60s 刷新；后端
  E3/E4/E6 缓存 TTL ≤ 60s，与 borrow_validation 1h TTL 独立。

### 3.4 净收益测算

- 负费率行：`net = |daily_funding_rate| − 借币日利率`；正费率行：
  `net = daily_funding_rate`（五家评审确认方向语义正确）。
- ADR 记录一阶近似假设（正费率行自有资金、不计手续费与保证金占用）
  + UI 口径提示；Decimal 字符串、string-shift、禁 float；成本腿不可得
  → `net_daily_yield = null` + `borrow_rate_source` 说明原因。

### 3.5 排序（显式修订 ADR-3）

净收益优先 + 快照级回退（同 DRAFT-2）：私有成本腿可用 → 全表
`net_daily_yield` 降序；不可用/降级 → 整表回退 abs 日费率降序。当轮
基准写入顶层 `sort_basis`，前端照实标注，不做行级混排。**本节 = ADR-3
显式修订提案，随本方向轮报用户批准。**

### 3.6 数据获取架构与全端点限频预算（用户批示 5，H_intake 硬交付）

- **架构约束（参照遗留脚本模式**，`币安套费率策略，逐仓杠杆.js`
  L2706/L2730/L2824/L3303**）**：初始化阶段并行拉取合约/现货/杠杆
  **公开**市场数据建独立 map 组；主循环 = 合约市场 map 匹配对冲标的
  （现货/杠杆做 lookup）；**私有签名调用只发生在匹配后的候选集上**。
- **全端点清单（本轮涉及的全部调用，一次性暴露；开发中途新增端点 =
  R3 级升级，禁止顺手加）**：

| 类别 | 端点 | 状态 |
|---|---|---|
| 公开-合约 | `/fapi/v1/exchangeInfo`、`/fapi/v1/premiumIndex`、`/fapi/v1/fundingInfo` | 既有 |
| 公开-现货/估值 | `/api/v3/exchangeInfo`、现货 ticker（估值价格源，stage design 定具体端点） | 既有/新增 |
| 私有-既有白名单 | `/sapi/v1/margin/allPairs`、`/sapi/v1/margin/allAssets`、`/sapi/v1/margin/crossMarginData`、`/papi/v1/margin/maxBorrowable` | 既有 4 项 |
| 私有-本轮新增 | E1、E1b、E2、E2b、E5、E3、E4、E6 | 新增 8 项 |

- **限频预算表 = H_intake 硬交付**：discovery 对上表**每个端点**记录
  文档权重值 + 实抓响应头用量（`X-MBX-USED-WEIGHT-*` /
  `X-SAPI-USED-*-WEIGHT-*`），按「初始化一轮 + 稳态每 60s 一轮 +
  borrow 探测每 1h 一轮」三种场景合计，与官方限额对比给出安全余量
  结论；预算表进 stage design 冻结，实现阶段不得超表调用。

## 4. 契约草案 v0.3（要点；字段矩阵 stage design 冻结）

- rows 新增：`net_daily_yield`、`borrow_rate_source`（含义见 §0/§3.1）。
- `borrow_validation.classic_margin` 新增 `daily_interest_account`
  （链全断则恒 null）。
- 顶层新增：`sort_basis`；`private_account` 块（统一账户余额 + 现货
  余额 + UM 持仓 + 综合折算值；三态语义；`checked_at` = 请求成功时刻）。
- coverage/warnings：借币验证覆盖状态（哪些已验证、哪些因限速/失败
  未验证）。
- 版本口径：契约文档 v0.3；wire `schema_version` 保持 v1（additive、
  可缺失、旧前端优雅降级）。
- 耦合面全列（R9 packet 逐项）：`net_daily_yield`、`borrow_rate_source`、
  `sort_basis`、`private_account`、borrow_validation 扩展、rows 有序性。

## 5. 安全与隐私（按用户批示 4 降级为**自用工程卫生**）

- 白名单扩项：本轮新增 8 项签名 GET（4 → 12），扩项检查清单沿用
  （行号引用 / 脱敏实抓样本 / 字段敏感性分类 / deny-by-default 单测）。
- Phase 2 安全红线**不降级**：单一 HMAC 出口、deny-by-default、
  GET-only、key 片段零出现、审计日志无 query、优雅降级。
- **隐私边界收窄（明确降级）**：字段级脱敏**只约束进 git 的产物**
  （落档样本、报告、测试 fixture——脱敏映射表仍在 H_intake 冻结 +
  单测断言）；**本地/自部署运行时页面真实展示不受限**。
- 保留为工程卫生（非审计体系）：后端/网关不记 snapshot 响应体、
  前端不 console.log 账户数据、隐私模式开关（默认隐藏金额，点击
  显示，偏好可存 localStorage）。
- 部署语境说明：系统将部署 AWS 日本 + 域名转发 + 登录限制（用户
  决策）；**部署本身不在本轮 scope**，其安全面（key 上云存放、访问
  控制）见 §8 后续方向。

## 6. 复杂度评级与执行方式

- **MILESTONE**（白名单 4→12 + 账户敏感数据首次入 UI + ADR-3 修订 +
  综合资产估值口径首次引入）。
- 流程：DRAFT-3 → Codex 合成 → 用户批准（批准范围含 ADR-3 修订）→
  stage design。
- stage 执行 = 并行模式试运行 #2（独立 bookkeeper）+ stage 分支制首跑。
- 拆分预判：Task A 后端（验证链/契约/净收益/探测扩围/资产聚合/限频
  预算落地）、Task B 前端（私有面板/综合资产视图/净收益列/sort_basis
  标注/隐私开关）；耦合面 = §4 清单。

## 7. 开放问题裁定记录（O1-O5 已收敛）

O1 排序 → §3.5；O2 隐私模式 → §5；O3 持仓范围 → §3.3（已按用户批示
升级为综合资产视图）；O4 限速 → §3.2/§3.6；O5 成本腿 fallback → §3.1。

## 8. 已识别后续方向（本轮不展开）

1. **只读账户 websocket 修正案**（用户已表态要走此路线）：独立修正轮
   解禁 listenKey + user data stream 的**只读监听**（订单/余额/持仓
   事件）；下单、借还、划转等执行动作**仍永久禁止**。触发 = 本轮交付
   后由用户启动修正轮。
2. **部署轮**：AWS 日本 + 域名转发 + 登录限制；需评估 key 云端存放、
   访问控制、HTTPS 与登录方案。
3. **开仓规划**：手续费/滑点/仓位规模/结算次数建模，依赖 bStock 等
   价性、时段、非 USDT 计价、估值口径等未决项。

---

本地北京时间: 2026-07-05 23:05 CST
起草: Fable5 (anthropic/claude-fable-5)；DRAFT-3 = 5 模型评审 + 用户
8 点批示的合并吸收，待 Codex 合成 → 用户批准（含 ADR-3 修订）
