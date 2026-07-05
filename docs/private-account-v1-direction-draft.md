# 私有账户数据接入 v1 — 方向草案 DRAFT-1

状态：DRAFT-1（待多模型评审）。
决策背景：用户 2026-07-05 决定私有能力两步走——本轮 **GET-only 账户数据
接入**；websocket 实时订阅（持仓/订单/余额推送）后置为独立的基线修正轮。
起草：Fable5（designer）。上游基线：`docs/phase2-direction-draft.md`
（FROZEN，Codex ACCEPT-FREEZE）。

## 1. 背景与目标

Phase 2 已建立私有只读通道（单一 HMAC 出口 + 四端点 deny-by-default
白名单），但目前只做「验证性查询」（maxBorrowable bounded top-N，且
VIP0 基准利率）。本轮把私有通道升级为**账户级数据服务**，四个目标：

1. 借币成本用**账户真实档位利率**替代 VIP0 基准；
2. 负费率候选的借币验证**全覆盖**（解决 ADR-5 遗留：portfolio_account
   全 null）；
3. 持仓与余额的 **GET 轮询**展示（websocket 的八成价值、零红线冲突）；
4. **净收益测算**：资金费收入腿 − 借币成本腿，工具从数据看板升级为
   决策依据。

## 2. 与冻结基线的关系

- 继承 Phase 2 基线全部安全条款，**永久禁令不变**：任何 POST/PUT/DELETE、
  交易语义端点、下单/借还币执行/划转/提现、listenKey/user data stream、
  websocket。
- websocket 实时化 = 已识别的后续方向（§8），需独立的基线修正轮
  （多模型评审 + Codex 合成 + 用户批准）才能部分解禁。**本轮禁止实现
  任何 websocket 铺垫代码。**

## 3. 功能范围

### 3.1 账户真实借币利率

候选端点（H_intake discovery 必须逐一实测验证；失败 = BLOCKED 升级用户，
禁止静默降级或换端点）：

- **E1** `GET /papi/v1/margin/marginInterestHistory`（llms-full.txt
  L186218）：已发生利息（事后视角，校验用）。
- **E2** `GET /sapi/v1/margin/next-hourly-interest-rate`（L37035、
  L151129）：预估下小时利率（事前视角，净收益的成本腿输入）。
  **需验证统一账户适用性**；不适用时 fallback = 既有 crossMarginData
  VIP 利率表 + 账户实际档位（档位来源由 discovery 确认）。

### 3.2 负费率候选借币验证全覆盖（ADR-5 修订）

- 探测范围：bounded top-N → **全部负费率 MARGIN_SPOT_CANDIDATE ∩ CRYPTO
  候选**（负费率套利需借币做空现货，可借性是硬前提）。
- 限速预算：沿用 1h TTL 缓存 + 429/-1003 退避，增加批量节流；调用量
  上限为开放问题 O4。bStock 仍不探测（维持基线）。

### 3.3 持仓与余额（GET 轮询）

- **E3** `GET /papi/v1/balance`（L186080）：统一账户余额。
- **E4** `GET /papi/v1/um/positionRisk`（L186324）：UM 永续持仓。
- 展示：前端私有面板 + 持仓与对应 symbol 行联动标注；沿用 60s 自动
  刷新节奏，不引入新的刷新机制。

### 3.4 净收益测算（方向语义必须写死）

- **负费率行**（借币做空现货 + 做多永续收费率）：
  `net_daily_yield = |daily_funding_rate| − 借币日利率`。
- **正费率行**（现货做多 + 做空永续收费率，无借币腿）：
  `net_daily_yield = daily_funding_rate`。
- 交易成本（手续费/滑点）本轮**不建模**，留给开仓规划轮。
- 全程 Decimal 字符串运算，string-shift 展示，禁 float（基线红线）。

### 3.5 排序

现状 = abs 日费率降序。候选 = net_daily_yield 降序（null 末尾、symbol
升序 tie-break 沿用）。倾向改为净收益降序（排名依据仍对用户可见），
交评审裁定（O1）。

## 4. 契约草案 v0.3（要点；细节 stage design 冻结）

- rows 新增：`net_daily_yield`（string|null）。
- `borrow_validation.classic_margin` 新增 `daily_interest_account`
  （真实档位），保留 `daily_interest_vip0` 作基准对照。
- 顶层新增 `private_account` 块（三态语义沿用 borrow_validation 风格）：
  `{"balances": [...], "um_positions": [...], "checked_at": null,
  "error": null}`。
- schema 升 v0.3；全部新字段可缺失，旧前端不白屏（优雅降级沿用）。

## 5. 安全与隐私条款

- 白名单扩项（最终以 H_intake discovery 后的 status.json 为准）：
  E1-E4 四个签名 GET。扩项走既有契约修正流程（附脱敏 raw 样本）。
- Phase 2 全部红线继续适用：单一 HMAC 出口、deny-by-default
  `(method, exact-path)`、GET-only、key 片段零出现、审计日志无完整
  query、env 缺失优雅降级。
- **新增隐私红线**：余额/持仓数值属敏感数据——落档样本与日志一律
  capture-time 脱敏（数值换占位、保留字段名与类型）；真实数值只允许
  出现在本地页面渲染。是否加页面「隐私模式」开关 = O2。

## 6. 复杂度评级与执行方式

- **MILESTONE**（白名单翻倍扩项 + 账户敏感数据首次入 UI）：方向面板
  多模型评审 → Codex 合成 → 用户批准 → stage design。
- stage 执行 = **并行模式试运行 #2**（独立 bookkeeper，v0.3 角色规则）
  + **stage 分支制首跑**（bookkeeper 起手建 `stage/<stage-id>`）。
- 拆分预判：Task A 后端（端点接入/契约 v0.3/净收益/探测扩围）、
  Task B 前端（私有面板/净收益列/三态展示）；耦合面 = v0.3 新字段。

## 7. 开放问题（评审重点）

- **O1** 排序基准：保持 abs 日费率 vs 改净收益降序？
- **O2** 隐私模式开关：默认隐藏金额，点击显示？
- **O3** 持仓展示范围：仅 UM 永续持仓，还是也含现货余额折算？
- **O4** 负费率全覆盖的限速预算：单轮探测调用量上限、缓存粒度？
- **O5** E2 统一账户适用性的 fallback 路线是否成立？

## 8. 已识别后续方向（本轮不展开）

1. **websocket 实时化修正案**：解禁 listenKey + 只读数据流消费（订单/
   借还/划转执行仍永久禁止），独立方向轮，触发条件 = 用户实际持仓后
   轮询延迟成为痛点。
2. **开仓规划**：依赖 bStock 1:1 等价性、现货时段 vs 7×24、非 USDT
   计价等未决项，需先行方向盘对齐。

---

本地北京时间: 2026-07-05 21:10 CST
起草: Fable5 (anthropic/claude-fable-5)；DRAFT-1 待 GPT/GLM/Kimi 独立评审
