# 私有账户数据接入 v1 — 方向草案 DRAFT-2

状态：DRAFT-2（已吸收 5 模型独立评审，待 Codex 合成）。
决策背景：用户 2026-07-05 决定私有能力两步走——本轮 **GET-only 账户数据
接入**；websocket 实时订阅后置（措辞见 §8，按 Codex P2 修正）。
起草：Fable5（designer）。上游基线：`docs/phase2-direction-draft.md`
（FROZEN，Codex ACCEPT-FREEZE）。

修订记录：
- DRAFT-1（2026-07-05 21:10）：初稿。
- DRAFT-2（2026-07-05 晚）：吸收 5 份独立评审（Codex REWORK / GLM REWORK /
  Kimi REWORK / Opus4.6 REWORK / Gemini3.1-Pro ACCEPT，落档
  `reports/agent-runs/private-account-v1-direction/review-*.md`）。
  主要修点：①成本腿依赖链闭合（四级 fallback + `borrow_rate_source`）；
  ②排序改净收益需显式修订 ADR-3（快照级 sort_basis，非静默变更）；
  ③字段级脱敏清单机制 + 本地日志红线；④限速预算写死；⑤契约字段矩阵、
  耦合面、wire 版本口径补全。评审小组构成与披露：GPT/Codex、GLM、Kimi、
  Gemini3.1-Pro、Claude Opus4.6（与 designer 同 provider，已披露；方向
  评审非 review-2 门，不触发排除规则）。

## 1. 背景与目标

Phase 2 私有通道目前只做「验证性查询」。本轮升级为**账户级数据服务**：

1. 借币成本腿接入**账户级利率**（可达性依赖 §3.1 验证链；若全链不可达，
   本目标显式降级为「基准利率 + 明确标注」，**不得静默退回 VIP0 而保留
   "真实档位"措辞**——GLM/Codex P1）；
2. 负费率候选借币验证**全覆盖**（ADR-5 修订）；
3. 持仓与余额 **GET 轮询**展示；
4. **净收益测算**：工具从数据看板升级为决策依据。

## 2. 与冻结基线的关系

- 继承 Phase 2 基线全部安全条款，**永久禁令不变**（POST/PUT/DELETE、
  交易语义端点、下单/借还执行/划转/提现、listenKey/user data stream/
  websocket）。
- 本轮为 Phase 2 下游增量，**不是基线修正**；禁止实现任何 websocket
  铺垫代码。

## 3. 功能范围

### 3.1 账户借币利率（成本腿验证链，H_intake 全部实测）

候选端点（行号 = llms-full.txt；GLM/Opus 已回读核实全部准确）：

| # | 端点 | 族/base_url | 用途 |
|---|---|---|---|
| E1 | `GET /papi/v1/margin/marginInterestHistory`（L186218） | papi | **仅事后对账**（reconciliation），不作净收益输入（Codex P2） |
| E1b | `GET /papi/v1/portfolio/interest-history`（L186318） | papi | 统一账户负余额收息历史——discovery 与 E1 并抓比对，确定统一账户真实 borrow cost 落在哪类（Kimi P1-2） |
| E2 | `GET /sapi/v1/margin/next-hourly-interest-rate`（L37035/L151129/L189205） | **sapi**（api.binance.com） | 预估下小时利率，成本腿首选；经典杠杆族，统一账户适用性 = BLOCKER 级实测项 |
| E2b | `GET /sapi/v1/margin/interestRateHistory`（L150993 指定为已弃用 portfolio/interest-rate 的替代） | sapi | fallback 二级 |
| E5 | `GET /sapi/v1/account/info`（L6704，返回 VIP 等级） | sapi | fallback 三级的档位来源（GLM P1 修复） |

**成本腿四级 fallback（顺序固定，每级触发条件 discovery 写死）**：

1. E2 适用 → 成本 = hourly × 24（**单位归一化写死**，GLM P2）；
   `borrow_rate_source = "next_hourly"`。
2. E2 不适用 → E2b 最新点；`borrow_rate_source = "rate_history"`。
3. 再不可 → crossMarginData VIP 利率表 + E5 取账户 VIP 档位；
   `borrow_rate_source = "cross_margin_tier"`。
4. 档位不可得 → VIP0 基准 + UI 显著标注「基准利率（可能低于实际）」；
   `borrow_rate_source = "vip0_reference"`，§1 目标 1 记为降级达成。

任何一级的口径（hourly/daily、单位、字段名）以 discovery 实抓样本冻结；
base_url 逐端点冻结（papi/sapi 混族，GLM P3）。

### 3.2 负费率候选借币验证全覆盖（ADR-5 修订）

- 探测范围显式定义（Opus P3）：当前快照中
  `daily_funding_rate < 0 ∧ route_class == MARGIN_SPOT_CANDIDATE ∧
  asset_tag == CRYPTO` 的全部行，按 baseAsset 去重。bStock 仍不探测。
- **限速预算写死**（五家收敛）：单轮 maxBorrowable 调用上限默认 **50**
  （`Config` 可配）；候选超限按 abs(daily_funding_rate) 降序截断；
  并发 ≤ 2 + 请求间隔 ≥ 200ms；1h TTL 缓存沿用；429/-1003 有界退避沿用。
- **coverage 状态强制**：被截断/失败的候选数量写入快照 `warnings` 与
  borrow_validation coverage 字段，**禁止静默截断后仍标 verified**
  （Codex/Kimi）。

### 3.3 持仓与余额（GET 轮询）

- E3 `GET /papi/v1/balance`（L186080）、E4 `GET /papi/v1/um/positionRisk`
  （L186324），均 papi 族。
- 展示范围（O3 收敛裁定）：UM 永续持仓 + 余额**分列展示**，不做现货
  折算（估值口径留开仓规划轮）；symbol 行联动标注只给「有持仓/方向」
  （小圆点/多空标识），**不带数量与盈亏**（Kimi P3-2）。
- 前端沿用 60s 刷新；**后端 E3/E4 缓存 TTL ≤ 60s**，与 borrow_validation
  的 1h TTL 相互独立（Opus P2）。

### 3.4 净收益测算

- **负费率行**：`net_daily_yield = |daily_funding_rate| − 借币日利率`
  （借币做空现货 + 做多永续收费率）。
- **正费率行**：`net_daily_yield = daily_funding_rate`（现货多 + 永续空，
  无借币腿）。
- 五家确认方向语义正确。**记录 ADR 假设**（GLM/Gemini）：一阶近似——
  正费率行假定现货用自有资金（不计 USDT 借贷/资金机会成本）、忽略
  手续费与保证金占用；UI 对正/负费率行的 net 口径给差异提示。
- 成本腿单位一律归一化为日利率后相减；Decimal 字符串、string-shift
  展示、禁 float（基线红线）。
- 每行携带 `borrow_rate_source`；成本腿不可得 → `net_daily_yield = null`。

### 3.5 排序（显式修订 ADR-3，非静默变更）

- 采纳多数意见（Codex/Kimi/Opus/Gemini）改**净收益优先**，同时吸收 GLM
  的程序与对称性异议：
  1. 本节构成对已冻结 **ADR-3 的显式修订提案**，随本方向轮报用户批准，
     不在 stage 内自决（R3 合规）；
  2. **快照级单一排序基准**：私有通道可用且成本腿 source ≠ vip0_reference
     以外均可 → 全表按 `net_daily_yield` 降序（null 末尾、symbol 升序
     tie-break）；私有通道不可用/降级 → 整表回退 abs(daily_funding_rate)
     降序（Phase 2 现行为）。当轮实际基准写入快照顶层 `sort_basis` 字段，
     前端照实标注，**不做行级混合排序**；
  3. 正/负费率行 net 口径不对称按 §3.4 的 ADR 假设记录 + UI 提示处理。

## 4. 契约草案 v0.3（要点；字段矩阵 stage design 冻结）

- rows 新增：`net_daily_yield`（string|null）、`borrow_rate_source`
  （enum: next_hourly / rate_history / cross_margin_tier / vip0_reference，
  nullable）。
- `borrow_validation.classic_margin` 新增 `daily_interest_account`
  （string|null；来源 = §3.1 验证链，链全断则该字段恒 null——不移除，
  语义即"账户级利率不可得"，回应 Kimi P2-3）。
- 顶层新增 `sort_basis`（enum: net_daily_yield / abs_daily_funding_rate）。
- 顶层新增 `private_account` 块（三态语义同 borrow_validation；
  `checked_at` = 请求成功时刻，与 borrow_validation.checked_at 同义）。
  **E3/E4 字段映射矩阵**（字段名/raw JSON path/类型/nullable/是否脱敏）
  由 H_intake discovery 实抓后在 stage design 冻结（Kimi P2-4/Opus 建议 A）。
- **版本口径**（Codex P3）：契约文档升 v0.3；wire `schema_version` 保持
  `public-market-snapshot/v1` 不变（全部变更 additive、可缺失、旧前端
  优雅降级）。
- 耦合面如实全列（Kimi P3-3）：Task B 消费 = `net_daily_yield`、
  `borrow_rate_source`、`sort_basis`、`private_account` 块、
  `borrow_validation` 扩展字段 + rows 有序性。R9 packet 逐项列出。

## 5. 安全与隐私条款

- 白名单扩项：E1、E1b、E2、E2b、E3、E4、E5（全部签名 GET；最终以
  discovery 后 status.json 为准）。**扩项检查清单**（Opus P2）：每端点
  须有 ①llms-full.txt 行号 ②H_intake 脱敏实抓样本 ③响应字段敏感性分类
  ④deny-by-default 门控单测。
- Phase 2 全部红线继续适用（单一 HMAC 出口、deny-by-default、GET-only、
  key 卫生、审计日志无 query、降级）。
- **字段级脱敏清单机制**（五家收敛，取代 DRAFT-1 的原则性表述）：
  H_intake discovery 后冻结「全数值字段 → 占位」映射表（仿 Phase 2
  raw-field freeze），至少涵盖：`balances[].free/locked/total…`、
  `um_positions[].positionAmt/entryPrice/markPrice/unRealizedProfit/
  liquidationPrice…`、`max_borrowable/borrow_limit`（已有）、
  `daily_interest_account` 与 `net_daily_yield`（可反推 VIP 档位，
  Opus）；配**单测断言**：落档 JSON/fixture/报告不含任一真实数值，
  且脱敏样本仍过 schema 校验（Kimi）。
- **本地日志红线**（Gemini P3）：后端/网关禁止记录 snapshot 响应体；
  前端禁止 console.log 输出账户级真实数据。
- **隐私模式**（O2 收敛）：默认隐藏金额/仓位数量，点击显示；开关偏好可
  存 localStorage（仅布尔偏好，金额永不持久化）；落档/日志脱敏不受
  开关影响。

## 6. 复杂度评级与执行方式

- **MILESTONE**（白名单 4→11 端点 + 账户敏感数据首次入 UI + ADR-3 修订）。
- 流程：本 DRAFT-2 → Codex 合成 → 用户批准（含 ADR-3 修订与排序基准）
  → stage design。
- stage 执行 = 并行模式试运行 #2（独立 bookkeeper）+ stage 分支制首跑。
- 拆分预判：Task A 后端（验证链/契约 v0.3/净收益/探测扩围/脱敏机制）、
  Task B 前端（私有面板/净收益列/sort_basis 标注/隐私模式/三态展示）；
  耦合面 = §4 末列出的全部字段。

## 7. 开放问题裁定记录（原 O1-O5，已全部收敛）

- O1 排序：见 §3.5（净收益优先 + 快照级回退 + ADR-3 显式修订）。
- O2 隐私模式：默认隐藏，见 §5。
- O3 持仓范围：UM 持仓 + 余额分列，不折算，见 §3.3。
- O4 限速预算：上限 50/优先级/节流/coverage，见 §3.2。
- O5 成本腿 fallback：四级链 + borrow_rate_source，见 §3.1。

## 8. 已识别后续方向（本轮不展开）

1. **实时订阅（websocket）**：属 Phase 2 基线永久禁令范围。**若用户
   未来决定修改永久禁令，须独立 MILESTONE 修订轮 + 用户显式批准**
   （措辞按 Codex P2 修正，不预设"解禁"为默认方向）。触发条件 =
   实际持仓后轮询延迟成为痛点。
2. **开仓规划**：依赖 bStock 1:1 等价性、时段、非 USDT 计价、估值
   口径等未决项。

---

本地北京时间: 2026-07-05 22:30 CST
起草: Fable5 (anthropic/claude-fable-5)；DRAFT-2 已吸收 5 模型评审，
待 Codex 合成 → 用户批准（注意：批准范围含 ADR-3 排序修订）
