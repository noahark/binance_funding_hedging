# 方向草案 — Hedge Open Real API v1

**方向面板成员：`glm52`**（model `glm-5.2[1m]`，provider `claude_glm` / zhipu_glm，经 Claude Code 运行）。

## 0. 方法与身份声明

- 我是 dispatch `direction-panel-dispatch.md` 中注册的 `glm52` 成员，独立撰写本草案。
- **只读执行**：未编辑任何源码，未访问凭据，未发送订单，未启动服务，未发起任何 Binance 私有请求，未调用或中继到其他模型。
- 未读取 `direction-drafts/` 下其他成员的草案（该目录当前为空），以保持独立性。
- **事实与设计选择的标注约定**：`【事实】` = 有原始证据（recon 报告 / 公开样本 / 已接受的 round-1 设计 / dispatch 冻结输入）支撑的陈述；`【设计选择】` = 我在本阶段建议的、可由后续 synthesis / breakdown 调整的方案；`【需澄清】` = 与冻结输入或既有证据存在张力、需要人或 synthesis 拍板的点。

---

## 1. 阶段定位与边界

`【事实】` 本阶段从已接受的 `2026-07-hedge-open-live-v1` round 1（durable immediate-open 骨架 + dry-run record transport）继续。round-1 已落地并经 review-2 ACCEPT：

- 后端模块 `backend/hedge_open_tasks/`（domain/store/service/executor + 持久 SQLite + 固定 1s 调度线程 + 默认 `DisabledHedgeExecutor` + dry-run record transport）。
- 已冻结的 API 契约（`POST/GET /api/hedge-open-tasks`、`pause/start/delete/fill-once/fill-all`、settings/badge、logs、positions）。
- 前端已接入该真实 API（backend 770+ 测试通过、frontend self-check 通过）。

`【事实】` round-1 明确**未交付**（`80-user-acceptance.md` 记录）：DI-6 订单模型重建、真实只读 preflight、真实 live executor、用户级 numeric 风控、smooth WebSocket gate、F-003..F-006、`both_mismatched_contract_gap` 表示。

`【事实】` 本阶段冻结输入（dispatch Frozen Inputs + `status.json.scope_decisions`）规定：

- Regular Portfolio Margin，immediate mode only（smooth WS 为下一阶段）。
- 前端输入 = 每次 attempt 的固定基础币数量（`single_amount`）+ attempt 次数（`target_n`）。
- 两方向均把 `single_amount` floor 到 spot MARKET 与 UM MARKET filter 的公共 Decimal 网格 → `q_common`。
- 持久化 attempt 后**并发**提交两腿：forward = margin `BUY MARKET quantity=q_common` + `NO_SIDE_EFFECT`，配 UM `SELL MARKET quantity=q_common`；reverse = margin `SELL quantity=q_common` + `NO_SIDE_EFFECT`，配 UM `BUY MARKET quantity=q_common`。
- **无产品 numeric amount/count/margin cap**；Binance filters、可用余额/账户状态、rate limit、`APP_HEDGE_EXECUTOR=live`、durable Start gate、首活人工授权仍为强制。
- 两腿都成交**不做** executed-quantity equality check；单腿/部分/超时/未知结果暂停并核对；无 auto-borrow/repay/close/repair。
- 进入 live executor 前必须解决 F-003..F-006。

`【设计选择】` 本阶段交付物边界（bounded stage）：真实 PAPI order adapter（gated）+ 真实只读 preflight + 真实 live executor（gated）+ F-003..F-006 修复 + 数量/分类模型的最终形态。**不含** smooth WS gate、不含 PM-Pro 适配、不含任何产品级 numeric 上限字段、不含 auto 修复/平仓/借贷。

---

## 2. 冻结输入的事实核对与内部一致性审查（本草案的核心贡献）

### 2.1 核心判断：frozen input「两腿 quantity=q_common 并发」在 API 能力内可行且自洽

`【事实】` recon §1.1：PAPI `POST /papi/v1/margin/order` MARKET BUY 接受 `quantity`（基础币）**或** `quoteOrderQty`（报价币），二者互斥、不可同传。**`quantity` 路径对 margin BUY 是合法的。**

`【事实】` recon §1.2：PAPI `POST /papi/v1/um/order` MARKET 只接受 `quantity`（基础币），不支持 `quoteOrderQty`。

因此：forward margin BUY 传 `quantity=q_common` 完全合法；两腿语义同为「基础币数量」，可预对齐到公共网格、可并发提交。**frozen input 在 API 层自洽。** 这实际上等于**回到 round-1 已被接受的 ADR-2 模型**（两腿 `quantity=q_common` + common grid + 同一 base 数量），只是本阶段要把它接到真实 POST、补上真实 preflight 与 reconciliation。这一判断是后续设计的安全基石。

### 2.2 必须标记的内部不一致：recon 正文 vs 最新冻结决策

`【事实】` recon 文件（`order-model-and-live-seams-recon.md`）的**核心叙事**——「正向必须用 `quoteOrderQty` + 两腿必须串行」——建立在一个**已被 supersede** 的前提上：DI-6 中用户曾陈述「spot market BUY 只能传 `quoteOrderQty`」，recon 据此推导出串行与派生流程。

`【事实】` 最新冻结决策（`00-intake.md` / `01-design-discussion.md` 的 "User Execution Decision Update"、`status.json.scope_decisions.forward_execution_policy`）已把正向改回 `quantity=q_common` 并发。`status.json.api_recon.design_caveat` 已明确标注："The raw recon's serial proposal was superseded by the user's explicit concurrent fixed-base-quantity design decision."

`【需澄清 / 建议标记】` 由于 recon 正文未随决策反转而更新，以下结论在当前模型下**失效或需重新评估**，存在误导 implementer / reviewer 使用串行逻辑的风险：

- §2.3「正向 quote-buy 串行派生流程」、§2.4 末段「顺序依赖：正向开仓两腿不能并发」→ **不再适用**（两腿并发、都发 `q_common`）。
- B-1「正向开仓两腿必须串行」→ **不再适用**。
- B-4「正向 UM 数量损耗（从 `executedQty` 派生 floor）」→ **不再适用**（UM 直接发 `q_common`）。
- C-1/C-2/C-4/C-6「正向 quoteOrderQty 重建清单」→ **不再适用**。
- §1.3 冲突解决表「用户决策正向 BUY 用 `quoteOrderQty`」一行 → 已被反转。

`【事实】` recon 的**事实证据部分仍有效且必须保留**：§1 参数矩阵、§2.1 公开样本 filters（BTCUSDT）、§2.2 逐腿序列化规则（spot SELL + UM 两向）、§2.4 反向 q_common 公共网格、§3 端点/权重/超时核对序列、§4 签名/时间同步/限频行为。

`【设计选择】` 我不替换 recon 内容（只读 + 不悄悄替换冻结假设）。建议 bookkeeper 在进入 implementer 前，于 recon 文件顶部或 `02-api-recon-intake.md` 增加一段**适用范围说明**，逐条点明哪些结论被 concurrent 模型 supersede，避免实现/评审误用串行逻辑。这是 evidence 一致性收尾，不是冻结假设本身不安全。

### 2.3 DI-6 用户陈述与 API 事实的差异（记录，不替换）

`【需澄清】` DI-6 称「a spot market BUY can **only** pass `quoteOrderQty`」；API 事实是 `quantity` 对 margin BUY 同样合法。差异可能源于当时特定账户/UI 观察或对「想固定 USDT 金额」的需求表述。因最新决策已回到 `quantity` 路径，此差异**不影响当前 stage**；但应记录：若未来 forward 又要固定 USDT 金额而改用 `quoteOrderQty`，recon §2.3 串行模型可复活——届时需重新评估。

### 2.4「无产品 numeric cap」与控制平面字段列表的张力

`【事实】` frozen input / `scope_decisions.numeric_risk_caps`：无产品级 amount/count/margin/notional 上限。

`【事实】` `01-design-discussion.md` 的 "Proposed Delivery Shape" 仍列出 `max_margin_fraction`、`max_task_notional_usdt`、`max_attempt_notional_usdt`、`max_open_attempts`、账户累计 notional cap 等 numeric 字段。这些与冻结决策冲突（design discussion 是较早草稿，被 User Decision Update supersede，但清单仍在文件中）。

`【设计选择】` 既然无产品 numeric cap，则「限制」应**降级为事实性强制约束**（正是 frozen input 列为 mandatory 的集合）：Binance filters、可用余额/账户状态、rate limit、durable Start gate、`APP_HEDGE_EXECUTOR=live`、首活人工授权。本阶段**不引入** `max_margin_fraction` 等未被要求的产品级 numeric 配置项（遵循冻结输入 + Simplicity First）；仅保留一个单一、可观察的账户级门禁：`accountStatus == NORMAL`（否则拒绝创建/启动 task），以及 per-attempt 的余额 / filters / rate-limit 前置校验。

### 2.5 「两腿并发 + 不做 equality check」是否 unsafe

`【需澄清】` 这是唯一需要主动界定边界、否则可能变 unsafe 的冻结假设。两腿都发 `q_common`，**意图**成交相等，但市价单可能部分成交、或被 `maxQty` 截断、或流动性不足，导致实际成交量不等。frozen input 选择「both filled 时不 pause、只记录 amounts + residual」。

`【设计选择】` 为让该假设保持安全，**分类口径必须严格**（见 §6）：

- 仅当两腿 `status == FILLED` **且** 各自 `executedQty` 在精度容差内 `== q_common` 时，才算「both filled」→ 走 BALANCED，记录 residual（通常≈0），不 pause。
- 任一腿 `status != FILLED`、或 `executedQty < q_common`（超精度容差）、或超时/未知 → 不属「both filled」，走 PARTIAL / SINGLE_LEG / UNKNOWN → `exposure_alert` + pause + 核对。

只要「filled」的语义如此界定，「both filled 不做 equality check」就是安全的（残余由 residual 字段显式记录，而非被吞掉）。这与 round-1 要修复的 `both_mismatched_contract_gap` 信息丢失直接对应。

---

## 3. 数量与 Decimal 行为（q_common）

基于 recon §2 事实（BTCUSDT 公开样本，2026-07-23）：

`【事实】`

- spot 有效 step：`MARKET_LOT_SIZE.stepSize=0`（零值=约束关闭）→ fallback `LOT_SIZE.stepSize=0.00001`。
- UM 有效 step：`MARKET_LOT_SIZE.stepSize=0.001`（启用）。
- 公共网格 = decimal `lcm(0.00001, 0.001) = 0.001`；`q_common = floor(single_amount / 0.001) * 0.001`。
- min/max：UM `MARKET_LOT_SIZE [0.001, 120]`；spot `MARKET_LOT_SIZE.maxQty=122.02726120`、`LOT_SIZE.maxQty=9000`。实质上界由 UM 的 `120` 约束（取两腿 max 之严者）。各腿 `q_common >= 各自 minQty`。
- notional：spot `NOTIONAL.minNotional=5`（`applyMinToMarket=true`）；UM `MIN_NOTIONAL=50`。每腿用保守价格估 notional，`>= 各自门槛`。

`【设计选择】`

- 全程 `Decimal` 定点；`q_common` floor 用定点运算，不得用 float。
- 每腿序列化十进制定点字符串，精度 ≤ 各 leg 精度（spot base `baseAssetPrecision=8`；UM 以 `stepSize` 为准，`0.001`→3 位），**不得**用 `quantityPrecision` 代替 filter，**不得**用科学记数法。
- filters 每 attempt 重读（带缓存 + 刷新），**绝不硬编码**。
- F-003（`MARKET_LOT_SIZE`/`LOT_SIZE` 按 constraint fallback + 零值字符串归一为「禁用」）必须先修，是 q_common 正确的前提。
- `quoteOrderQtyMarketAllowed` 不再是 forward 阻塞项（forward 已改用 `quantity`），preflight 可降级为信息字段（备未来 quote-buy 路径）。

---

## 4. read-only preflight（精确输入）

`【设计选择】` 在 global Start 与每个 task 首次 attempt 前（新鲜 TTL 内）执行；任何一项失败即阻断 Start：

1. **exchangeInfo**（两市场公开端点 `api.binance.com/api/v3/exchangeInfo`、`fapi.binance.com/fapi/v1/exchangeInfo`）→ filters 版本 + 计算 `q_common` + min/max/notional（F-003）。
2. `GET /papi/v1/um/positionSide/dual` → 持仓模式（单向 `BOTH` / 对冲），snapshot 进 task，**flow 中不改**。
3. `GET /papi/v1/account` → `accountStatus == NORMAL`、`uniMMR` 在安全水位；否则拒绝。
4. `GET /papi/v1/balance` → forward 需 `crossMarginFree(USDT)` 充足（按 `q_common × N × 保守价` 估）；reverse 需 `crossMarginFree(base) >= q_common × N`；`maxBorrowable` **仅校验、不算可卖量**。
5. `GET /papi/v1/rateLimit/order` → 持久化限频快照（F-004），取最严限制；429/418 停止排队、保留未发 task。
6. `GET /papi/v1/um/positionRisk` → 持仓核对基线（reconciliation 对照）。

`【设计选择】` server 计算 + 强制；browser 只展示有效值与拒绝理由（沿用 round-1 stage-1 的不足余额 modal 契约）。preflight 快照写入 attempt 不可变记录（见 §5）。

---

## 5. durable attempt / state transitions

`【设计选择】` 每次 attempt，**任何 POST 之前**必须先落库不可变记录（F-005：durable attempt 真正发生在 send 之前）：

```
attempt_id        : 序列/UUID
margin_client_id  : 从 attempt_id 派生的唯一 newClientOrderId
um_client_id      : 从 attempt_id 派生的唯一 newClientOrderId
direction         : forward | reverse
symbol            : e.g. BTCUSDT
q_common          : 定点基础币量
preflight_snapshot: { balance, filters_version, position_mode, rate_limit, account_status, timestamp }
status            : PENDING
```

`【设计选择】` 状态机（attempt 级）：

```
PENDING → DISPATCHED(两 POST 已发) → RECONCILING(超时/部分/未知)
        → { BALANCED | SINGLE_LEG | PARTIAL | UNKNOWN }
```

task 级 `status` 沿用 round-1 五态：`running | paused | done | exposure_alert | deleted`。

`【设计选择】` 单腿 / 部分 / 超时 / 未知 → `exposure_alert` + `leg_exposure` + pause，记录两腿真实态，**禁止** auto-repair / auto-close / auto-borrow / auto-repay（F-006 + frozen input）。

`【需澄清】` round-1 的 `fail_count > 3` 终止（`10-design.md` §7 step5）。这与「无产品 numeric cap」**不冲突**——`fail_count > 3` 是**机制性失败熔断**（连续失败止损），不是 amount/notional/margin/count 的产品上限。建议保留为安全熔断，并在文档/字段命名上明确其为「连续失败熔断」而非「产品 numeric cap」。

---

## 6. 并发提交与 reconciliation

`【设计选择】`

- 持久化 attempt 后，asyncio **并发**提交两 POST（round-1 已有并发骨架，dry-run 下已验证调度形状）。
- 两腿 `newOrderRespType=RESULT`、唯一 `newClientOrderId`（派生自同一 `attempt_id`）。forward margin BUY `sideEffectType=NO_SIDE_EFFECT`、无 `reduceOnly`、永不 `MARGIN_BUY`/`AUTO_REPAY`；reverse 同样 `NO_SIDE_EFFECT` 且**不自动借款**。
- `positionSide`：forward = um `SELL`（单向 `BOTH` / 对冲 `SHORT`）；reverse = um `BUY`（`BOTH` / `LONG`）。模式来自 preflight，flow 中不改。

`【事实】` reconciliation（recon §3.3）——不信任 POST 返回：

- 超时 / 5xx / 断连 / non-`FILLED` → 标记 unknown，**不重发同一 client_id**。
- 按 client_id 查 `GET /papi/v1/margin/order` + `GET /papi/v1/um/order`，再 `margin/myTrades` + `um/userTrades` + `um/positionRisk` 建立真实成交 / 价格。
- HTTP 503「Unknown error」= 执行态未知、**可能已成功** → 必查、不重试；503「Service Unavailable」= 失败、可退避；`-1008` Request throttled = 失败、降并发后重试。
- 每步查询结果回写 attempt 记录。

`【设计选择】` 分类（严格口径，承接 §2.5）：

| 分类 | 条件 | 处置 |
|---|---|---|
| `BALANCED` | 两腿 `FILLED` 且各自 `executedQty ≈ q_common`（精度容差内） | 记录两腿 actual filled/quote/fees + residual（`spot_filled − um_filled`，带符号）；不 pause；`success_count++` |
| `PARTIAL` | 任一腿 `FILLED` 但 `executedQty < q_common`（超容差），另一腿 FILLED | `exposure_alert` + pause + 记录 |
| `SINGLE_LEG` | 一腿 FILLED、另一腿 REJECTED/EXPIRED/zero/unknown | `exposure_alert` + pause + 记录 |
| `UNKNOWN` | 查询仍超时/未决 | `exposure_alert` + pause + 人工核查 |

`【设计选择】` both-filled 表示：**替换** round-1 的 `both_mismatched_contract_gap`（信息丢失）。新表示同时承载两腿 actual_filled_qty、actual_quote、fees、带符号 residual，状态仍为 `BALANCED`（不因成交数量不等而 pause，除非落入 PARTIAL/SINGLE_LEG/UNKNOWN）。这正是 frozen input「both filled 不做 equality check、记录 amounts + residual」的可审计落地。

---

## 7. real-POST gate proof（可测试的 fail-closed）

`【设计选择】` live POST 必须同时满足（frozen input + round-1 ADR-5）：

1. `APP_HEDGE_EXECUTOR=live`（进程启动时）。
2. durable global Start gate ON。
3. 新鲜 preflight（TTL 内）。
4. rate-limit 通过（F-004）。
5. `accountStatus == NORMAL` + 余额充足。
6. 首活 task 的人工授权（独立人工动作，**非** config flag）。

`【设计选择】` 测试断言：任一 gate 缺失 → 无任何真实 POST 可达（仅 record transport）。real PAPI adapter 作为独立、gated 的 transport 注入；默认 executor 仍为 `DisabledHedgeExecutor`，record transport 保留。CI **永不**发真实 Binance 请求；只测 record transport + disabled/gated 路径 + fail-closed。无凭据进入 source/artifacts/logs；record transport 只记 param 形状，不记 secret/signature。

---

## 8. API / UI contract

`【设计选择】` 沿用 round-1 已冻结契约（**不改动**，降低 FE/BE 协同风险）：`POST/GET /api/hedge-open-tasks`、`<id>/{pause|start|delete|fill-once|fill-all}`、settings/badge、logs、positions。

本阶段增量：

- execution badge 增加：live/dry-run + Start gate 态 + `accountStatus` + 首活授权态。
- create 输入：`single_amount`（base qty / attempt）+ `target_n`（attempt count）+ `mode=immediate`；**不**新增 numeric cap 字段。
- positions / `leg_exposure` 增加两腿 `actual_filled` + 带符号 `residual` 展示（替代 `both_mismatched_contract_gap`）。
- 平滑开单（`mode=smooth`）UI 预留但禁用，提示「下一阶段」。
- 不足余额、`accountStatus != NORMAL`、preflight 失败：沿用 round-1 modal 契约 + 真实拒绝理由。

`【需澄清】` 本阶段不引入产品级 numeric 上限 UI（遵循无 cap 决策）。若未来要加，须单独用户批准，不在本 stage。

---

## 9. tests

`【设计选择】`

- **纯 domain**：`q_common` floor + 零 stepSize fallback（F-003）、每腿定点序列化、notional 校验、并发 attempt 状态机分类（BALANCED/PARTIAL/SINGLE_LEG/UNKNOWN）、residual 计算、`fail_count>3` 熔断。
- **executor**：record transport 记录正确 params（两腿 `quantity=q_common`、`NO_SIDE_EFFECT`、`RESULT`、派生 client_id）；fail-closed（gate 缺失无 POST）；429/418/503-unknown 分类。
- **reconciliation**：client_id 查询序列、不重发、超时→unknown→查→分类、partial 识别。
- **硬规则**：**无任何测试发起真实 Binance 请求**；真实 order-response 样本仅来自后续 human-authorized 真实单，永不伪造。
- F-003..F-006 各配回归测试（round-1 已列为 follow-up，本阶段清账）。

---

## 10. file / task split（建议，非冻结）

`【设计选择】` 仅给结构建议，具体 owner 划分与文件边界由后续 development breakdown author 裁定：

- **backend**（`hedge_open_tasks/`）：domain（`q_common` + F-003 normalize + 分类 + residual）、preflight（真实只读 GET 集合 + TTL + `accountStatus` 门禁）、executor（真实 PAPI adapter gated + record transport）、reconcile（client_id 查询序列 + 503 分类）、store（持久化先于 send + 限频 F-004）。
- **frontend**：badge / positions / `leg_exposure` 展示 + create 输入 + 禁用 smooth。
- **fix 子任务**：F-003..F-006 可作为独立 fix 或并入 preflight/executor。

`【事实】` 按仓库路由，backend 归 Claude-GLM、frontend 归 Kimi；具体混合拆分由 breakdown author 按 dominant workload 决定，本草案不越界。

---

## 11. residual risks / open items

1. **recon evidence 过时**（§2.2）：recon 正文仍含 quoteOrderQty 串行结论，需 bookkeeper 加适用范围说明，否则误导实现/评审。最高优先。
2. **PARTIAL 口径定义**（§6）：`executedQty < q_common` 的「精度容差」需在 breakdown 固定一个明确阈值（建议：逐腿按各自 stepSize 的 sub-step 判定），否则 BALANCED/PARTIAL 边界模糊。
3. **`fail_count > 3` 语义**（§5）：保留为机制性失败熔断，但须在字段/文档命名上与「产品 numeric cap」明确区分，避免与「无 cap」冻结输入混淆。
4. **positionSide 单向假设**：PRD + frozen 假设 one-way（`BOTH`）。若账户实际为对冲模式，preflight 应拒绝并提示用户切换；**flow 中绝不改模式**。
5. **PM-Pro 兼容**（recon B-6 / inference）：frozen 假设 regular PM。若用户账户实为 PM-Pro，`/papi/v1/` 路径行为可能不同；本阶段不做 PM-Pro 适配，若适用需用户纠正假设。
6. **真实 order-response 样本缺失**（recon）：无 PAPI testnet。real adapter 的真实响应样本只能在首活 human-authorized 后采集；此前用 official schema + record transport 验证，不伪造样本。
7. **restart 恢复**：immediate 模式无 WS gate，但重启后 `PENDING`/`DISPATCHED` 的 attempt 需扫描并按 client_id reconcile，**不自动重发**。
8. **并发跨腿滑点**：两腿同时市价，极端流动性下可能一腿被 `maxQty` 截断或部分成交 → residual / PARTIAL。frozen 已选择 both-filled 不 pause，但 residual 须 UI 可见，由 PARTIAL 口径兜底（见 #2）。
9. **sideEffectType PAPI 权重未实测**（recon B-5）：本阶段固定 `NO_SIDE_EFFECT`，UID 权重影响暂不涉及；记录为 open item。

---

## 12. 对 frozen input 的总判断

- frozen inputs 总体**安全且自洽**：`quantity=q_common` 并发回到 round-1 已被 review-2 ACCEPT 的 ADR-2 模型，且 `quantity` 对 margin BUY 是 API 合法路径。
- 唯一需主动处理的是 **recon evidence 的叙述性过时**（基于已 supersede 的 `quoteOrderQty` 串行）——`status.json.api_recon.design_caveat` 已标注；建议 bookkeeper 在 implementer 前补一段适用范围说明。这是 evidence 一致性问题，**不是**冻结假设本身不安全。
- 「两腿并发 + both-filled 不做 equality check」在严格分类口径（§2.5/§6）下保持安全；否则可能变 unsafe——这是本草案最重要的边界提醒。
- 我**不建议**悄悄替换任何冻结输入；所有张力均以【需澄清】标记，交还 synthesis / 用户。

---

当前 Session ID: unavailable（Claude Code 运行时未向 glm-5.2[1m] 暴露 zhipu_glm provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/glm52.md
本地北京时间: 2026-07-23 16:22:52 CST
下一步模型: bookkeeper
下一步任务: archive this raw direction draft; do not implement code
