# 私有账户数据接入 v1 方向草案评审 — Kimi-2.7

## 总体结论

**REWORK**。DRAFT-1 的方向（GET-only 账户数据接入、真实利率、借币验证扩围、净收益测算）整体正确，且与 Phase 2 冻结基线的永久禁令无冲突。但 **§3.1 借币利率端点选型在统一账户（非专业版）前提下的适用性与 fallback 链存在重大不确定性**，可能直接导致 `net_daily_yield` 计算错误；§3.2 全探测扩围缺少 concrete 限速预算；§5 隐私脱敏规则仍停留在原则层，缺少可执行的字段级落档规则。上述问题必须在 DRAFT-2 中给出 discovery 验证方案与明确数值/字段约束，否则不应进入 stage design。

---

## 逐节评审（§1–§8）

### §1 背景与目标
**AGREE**。四项目标与 Phase 2 遗留缺口（ADR-5 `portfolio_account` 全 null、VIP0 基准偏差、私有数据未入 UI）对应清楚，websocket 后置也合理。

### §2 与冻结基线的关系
**AGREE**。永久禁令不变、websocket 铺垫代码本轮禁止的表述与 Phase 2 基线一致。本轮本质上是 Phase 2 的下游阶段，不是基线修正。

### §3 功能范围

#### §3.1 账户真实借币利率
**REWORK**。E1、E2 在统一账户（非专业版）下的语义与可用性未经充分论证：
- E2 `/sapi/v1/margin/next-hourly-interest-rate` 属于 classic margin 族（llms-full.txt L37035、L151129 均标注为 margin 接口），其是否反映统一账户真实 borrow cost 需要实测；
- fallback "crossMarginData VIP 利率表 + 账户实际档位" 并未解决统一账户问题，因为 crossMarginData 同样是 classic margin 数据；
- llms-full.txt L150993 明确 `GET /sapi/v1/portfolio/interest-rate` 已 deprecated，推荐改用 `GET /sapi/v1/margin/interestRateHistory` 查 classic portfolio margin 负余额利率；
- E1 `/papi/v1/margin/marginInterestHistory`（L186218，"获取杠杆利息历史"）与 `/papi/v1/portfolio/interest-history`（L186318，"统一账户期货负余额收息历史"）是两类利息，统一账户下实际 borrow cost 可能落在后者或 margin/interestRateHistory，而非 E1/E2。

因此 "真实档位利率" 的数据源不能仅凭 E2 + crossMarginData 推断， discovery 必须实测比较 E1、E2、`/sapi/v1/margin/interestRateHistory` 最新点，才能确定成本腿输入。

#### §3.2 负费率候选借币验证全覆盖
**AGREE with concern**。从 bounded top-N 扩到全部负费率 `MARGIN_SPOT_CANDIDATE ∩ CRYPTO` 符合目标，但缺少 concrete 限速预算（见 O4 与 findings P2-1）。在给出单轮/每小时调用上限、批量策略之前，该扩围存在触发 429 或暴露 key 的风险。

#### §3.3 持仓与余额（GET 轮询）
**AGREE**。E3 `/papi/v1/balance`、E4 `/papi/v1/um/positionRisk` 文档定位清晰（llms-full.txt L186080、L186324），均为 GET 只读，与永久禁令无冲突。60s 刷新复用现有节奏合理。

#### §3.4 净收益测算
**AGREE**。方向语义正确：
- 负费率 → 永续多头收资金费 + 借币做空现货 → 成本为借币日利率 → `net_daily_yield = |daily_funding_rate| − 借币日利率`；
- 正费率 → 做空永续收资金费 + 现货多头（无需借币）→ `net_daily_yield = daily_funding_rate`。

该公式为一阶近似（假设等名义本金、忽略保证金占用与手续费），作为方向草案可接受；交易成本不建模也符合本轮 scope。Decimal string 运算、string-shift 展示与基线一致。

#### §3.5 排序
**AGREE**。提出 `net_daily_yield` 降序作为候选并交评审裁定合理。建议默认采用 net_daily_yield 降序，null 末尾 + symbol 升序 tie-break，并在 UI 同时保留 abs(日费率) 作为参考列（O1 详细建议见后）。

### §4 契约草案 v0.3
**AGREE with concern**。新增 `net_daily_yield`、`private_account` 块、扩展 `borrow_validation.classic_margin` 的方向正确，且保持向后兼容。但：
- `daily_interest_account`（"真实档位"）的来源未明确：若来自 crossMarginData 按用户 VIP 等级过滤，则需额外端点获取 VIP 等级，当前白名单未包含；
- `private_account` 块只有三态语义示例，缺少 E3/E4 字段映射矩阵；
- 未说明 `private_account.checked_at` 语义。

建议在 DRAFT-2 中补全字段矩阵与来源端点，否则 stage design 无法冻结 schema。

### §5 安全与隐私条款
**AGREE with concern**。白名单扩项、GET-only、审计日志、key 片段零出现等条款继承得当。新增隐私红线方向正确，但停留在"capture-time 脱敏"原则，缺少：
- 字段级 redaction 清单（哪些字段替换为 0/"REDACTED"）；
- 脱敏后样本仍需满足 schema 的断言；
- `private_account` 块落档样本的脱敏规则。

### §6 复杂度评级与执行方式
**AGREE with concern**。MILESTONE 评级与并行模式试运行 #2 合理，但需承认 Task B 对 Task A 的耦合不止两个公开字段：Task B 将消费 `net_daily_yield`、`private_account.balances/um_positions` 及 borrow_validation 的扩展字段，耦合面比 Phase 2 大。R9 dispatch packet 必须把这些字段全部纳入。

### §7 开放问题
**AGREE**。O1–O5 覆盖了排序、隐私、持仓范围、限速、E2 fallback 等关键决策点。

### §8 已识别后续方向
**AGREE**。websocket 实时化与开仓规划作为独立后续方向，与本轮 scope 切分清楚。

---

## 重点核查

### ① 净收益公式的方向语义（§3.4）
**正确**。负费率时做多永续、借币做空现货；正费率时做空永续、现货做多。公式方向与资金费收取/支付机制一致。只需在 DRAFT-2 中注明"一阶近似、忽略交易成本与保证金占用"。

### ② E1–E4 与统一账户（非专业版）的适配性
- **E3 `/papi/v1/balance`、E4 `/papi/v1/um/positionRisk`**：文档定位与统一账户一致，适配。
- **E1 `/papi/v1/margin/marginInterestHistory`**：文档描述为"杠杆利息历史"，统一账户下是否就是真实 borrow cost 需实测；可能需同时考察 `/papi/v1/portfolio/interest-history`（统一账户期货负余额收息历史）。
- **E2 `/sapi/v1/margin/next-hourly-interest-rate`**：classic margin 端点，统一账户适用性高度不确定；fallback 链需要把 `/sapi/v1/margin/interestRateHistory` 纳入。

**结论**：E3/E4 可直接采用；E1/E2 必须在 discovery 中通过实抓与跨端点比对验证，不能静默假设 classic margin 数据等同于统一账户 borrow cost。

### ③ 安全/隐私条款漏洞
- **账户数值脱敏**：有原则无字段清单。需明确 `free`、`locked`、`amount`、`borrowLimit`、`maxBorrowable`、`positionAmt`、`entryPrice`、`unRealizedProfit` 等字段的 redaction 方式。
- **审计日志**：private_client.py 当前只记录 sanitized path，不记录 query string/headers/key，符合要求。但 `private_account` 块相关后端日志是否也遵守同等清理需写入条款。
- **隐私模式开关**：建议默认隐藏金额（O2 详细建议见后）。

### ④ 与永久禁令的隐性冲突
**未发现冲突**。E1–E4 均为 GET 只读；净收益测算、持仓/余额展示均不产生 order/borrow/repay/transfer/websocket/listenKey。需确保实现阶段不引入任何 POST/PUT/DELETE 铺垫代码（如 websocket 连接初始化）。

---

## 开放问题建议（O1–O5）

### O1 排序基准：保持 abs 日费率 vs 改净收益降序？
**建议：默认 net_daily_yield 降序，null 末尾 + symbol 升序 tie-break；保留"日费率"列作为可见参考。**
理由：本轮核心目标就是把工具从"数据看板"升级为"决策依据"，净收益直接反映策略吸引力。但 net_daily_yield 为 null 时（借币验证失败或 E2 缺失）回退到 abs(日费率) 降序，避免白屏或误导。

### O2 隐私模式开关：默认隐藏金额，点击显示？
**建议：默认隐藏金额，提供页面级"显示金额"切换；切换状态仅存于前端内存（不持久化到 URL/localStorage，避免残留）。**
理由：余额/持仓属高敏感数据，默认隐藏可降低肩窥与录屏泄露风险。切换不持久化可减少本地痕迹。

### O3 持仓展示范围：仅 UM 永续持仓，还是也含现货余额折算？
**建议：仅展示 E4 UM 永续持仓；E3 余额单独展示，不做"折算"到 symbol 行。**
理由：现货余额折算涉及保证金计算与跨资产换算，超出本轮 scope；单独展示 balances 与 positions 足够支撑决策参考，且避免错误折算。

### O4 负费率全覆盖的限速预算：单轮探测调用量上限、缓存粒度？
**建议：
- 单轮上限：默认 50 个 `maxBorrowable` 调用（可配置）；
- 优先级：按 abs(daily_funding_rate) 降序选取负费率 `MARGIN_SPOT_CANDIDATE ∩ CRYPTO`；
- 缓存：1h TTL，与 classic_margin 参考一致；
- 超限行为：落 warning 并跳过低优先级候选，不得静默截断后返回"verified"。**

理由：全市场负费率候选可能达数十至上百，无上限会冲击 weight limit 与签名频率。

### O5 E2 统一账户适用性的 fallback 路线是否成立？
**建议：当前 fallback 不成立，需修订为三级验证链：**
1. 实测 E2 是否返回统一账户可用利率；
2. 若 E2 不可用或数值与统一账户实际利息不符，试用 `/sapi/v1/margin/interestRateHistory` 最新点；
3. 若仍不可得，回退到 `crossMarginData` VIP0 并显式标记 `net_daily_yield` 为估算值，同时落 warning。

理由：llms-full.txt 显示 portfolio/interest-rate 已 deprecated，统一账户真实利率不能默认等于 classic margin next-hourly rate。

---

## Findings

### P1-1 E2 端点适用性与 fallback 链错误
- **severity**: P1
- **file**: `docs/private-account-v1-direction-draft.md` §3.1
- **evidence**: E2 `/sapi/v1/margin/next-hourly-interest-rate` 为 classic margin 接口（llms-full.txt L37035、L151129）；统一账户（非专业版）的真实 borrow cost 可能来自 `/sapi/v1/margin/interestRateHistory`（L150993 替代已弃用的 `/sapi/v1/portfolio/interest-rate`）或 `/papi` 利息历史，而非 E2。
- **impact**: 若 E2 不反映统一账户利率，`net_daily_yield` 与排序将系统性错误，误导交易决策。
- **recommendation**: DRAFT-2 中明确 E2 必须经 discovery 实测验证；fallback 链加入 `/sapi/v1/margin/interestRateHistory` 最新点；若均不可得则回退 VIP0 并标记估算。

### P1-2 E1 可能捕获错误利息类型
- **severity**: P1
- **file**: `docs/private-account-v1-direction-draft.md` §3.1
- **evidence**: `/papi/v1/margin/marginInterestHistory`（L186218）描述为"杠杆利息历史"，而 `/papi/v1/portfolio/interest-history`（L186318）描述为"统一账户期货负余额收息历史"。统一账户下的 borrow cost 可能以后者形式记录。
- **impact**: 用 E1 作为"已发生利息校验"可能校验的是 classic margin 利息，而非统一账户实际成本。
- **recommendation**: discovery 同时抓取 E1 与 `/papi/v1/portfolio/interest-history`，比较字段与数值；在字段矩阵中明确"统一账户实际 borrow cost"对应哪个 raw JSON path。

### P2-1 全探测扩围缺少限速预算
- **severity**: P2
- **file**: `docs/private-account-v1-direction-draft.md` §3.2 / O4
- **evidence**: "全部负费率 MARGIN_SPOT_CANDIDATE ∩ CRYPTO 候选"数量未界定，每个候选触发一次签名 `maxBorrowable`。
- **impact**: 无上限调用会导致 429、-1003、IP 限频，甚至触发风控。
- **recommendation**: 给出单轮上限（如 50）、优先级策略（abs 日费率降序）、缓存 TTL（1h）与超限 warning 语义。

### P2-2 隐私脱敏缺少字段级规则
- **severity**: P2
- **file**: `docs/private-account-v1-direction-draft.md` §5
- **evidence**: 条款仅说"数值换占位"，未列出 E3/E4 中哪些字段必须 redact，也未要求脱敏样本通过 schema 断言。
- **impact**: 样本/日志可能泄露余额、持仓、可借额度。
- **recommendation**: 制定字段 redaction 清单（如 `free/locked/amount/borrowLimit/maxBorrowable/positionAmt/entryPrice/unRealizedProfit` 等替换为 0 或 "REDACTED"），并要求脱敏脚本 + 单测断言归档 JSON 不含真实数值。

### P2-3 `daily_interest_account` 来源未明确
- **severity**: P2
- **file**: `docs/private-account-v1-direction-draft.md` §4
- **evidence**: 草案提出 `borrow_validation.classic_margin.daily_interest_account`（真实档位），但未说明如何获取用户 VIP 等级，当前白名单亦无对应端点。
- **impact**: stage design 无法冻结字段来源与类型。
- **recommendation**: 要么在 discovery 中确认 VIP 等级来源端点并加入白名单，要么将 `daily_interest_account` 从 v0.3 移除、defer 到后续阶段。

### P2-4 `private_account` 块缺少字段矩阵
- **severity**: P2
- **file**: `docs/private-account-v1-direction-draft.md` §4
- **evidence**: 仅给出三态语义示例 `{"balances": [...], "um_positions": [...], "checked_at": null, "error": null}`，未列出字段名、类型、raw JSON path、nullable。
- **impact**: 前端无法安全消费，stage design 无法冻结 schema。
- **recommendation**: 补充 E3/E4 字段映射矩阵，包括 `asset`/`coin`、`balance`/`free`/`locked`、`positionAmt`/`entryPrice`/`markPrice`/`unRealizedProfit`/`positionSide` 等，并标注哪些字段必须脱敏。

### P3-1 `private_account.checked_at` 语义未说明
- **severity**: P3
- **file**: `docs/private-account-v1-direction-draft.md` §4
- **evidence**: `private_account` 块示例含 `checked_at`，但未说明其含义。
- **recommendation**: 明确 `checked_at` = 请求成功时刻（与 `borrow_validation.checked_at` 一致）。

### P3-2 持仓联动标注可能泄露仓位大小
- **severity**: P3
- **file**: `docs/private-account-v1-direction-draft.md` §3.3
- **evidence**: "持仓与对应 symbol 行联动标注"未限定标注粒度。
- **recommendation**: 明确联动仅展示"有持仓 / 方向"（如小圆点或多空标识），不展示数量、成本、盈亏。

### P3-3 并行模式耦合面描述偏小
- **severity**: P3
- **file**: `docs/private-account-v1-direction-draft.md` §6
- **evidence**: 文本称 Task B 对 Task A 的依赖"仅两个公开数据字段 + rows 有序性"，但 Task B 还将消费 `net_daily_yield`、`private_account` 块及 borrow_validation 扩展字段。
- **recommendation**: 在 §6 与 R9 dispatch packet 中如实列出全部耦合字段。

---

## 总体 Verdict

**REWORK**

**required fixes**:
1. §3.1 必须给出 E1/E2 在统一账户（非专业版）下的 discovery 验证方案，fallback 链须纳入 `/sapi/v1/margin/interestRateHistory` 并说明与 `/papi/v1/portfolio/interest-history` 的关系；不得默认 classic margin 数据等同于统一账户 borrow cost。
2. §3.2 / O4 必须给出负费率候选全探测的 concrete 限速预算：单轮调用上限、优先级、缓存 TTL、超限 warning。
3. §5 必须给出字段级隐私脱敏清单与单测断言要求。
4. §4 必须补全 v0.3 字段矩阵：`private_account` 块字段映射、`daily_interest_account` 来源与 VIP 等级获取方式、新增字段 nullable 规则。
5. §6 必须修正 Task A/B 耦合面描述，纳入 `net_daily_yield`、`private_account`、borrow_validation 扩展字段。
6. O1 必须给出默认排序决策（建议 net_daily_yield 降序，null 回退 abs 日费率）。

---

## 给 Fable5 的修订启动文案

请基于 DRAFT-1 出 DRAFT-2，重点修订以下内容：

1. **§3.1 借币利率端点**：
   - 明确 E2 `/sapi/v1/margin/next-hourly-interest-rate` 仅为 classic margin 候选，统一账户适用性需 discovery 实测；
   - 在 fallback 链中加入 `/sapi/v1/margin/interestRateHistory` 最新点；
   - 说明 E1 `/papi/v1/margin/marginInterestHistory` 与 `/papi/v1/portfolio/interest-history` 的区分，要求 discovery 同时抓取并比对，以确定统一账户真实 borrow cost。

2. **§3.2 / O4 限速预算**：
   - 给出单轮 `maxBorrowable` 调用上限（建议默认 50）；
   - 优先级按 abs(daily_funding_rate) 降序；
   - 缓存 TTL 1h；
   - 超限时落 warning，不得静默返回 verified。

3. **§5 隐私脱敏**：
   - 列出 E3/E4 必须 redact 的字段清单；
   - 要求脱敏脚本与单测断言：归档 JSON 不得包含真实余额/持仓/可借额度数值。

4. **§4 契约 v0.3 字段矩阵**：
   - 补全 `private_account` 块字段（来源 E3/E4、raw JSON path、类型、nullable、是否脱敏）；
   - 明确 `daily_interest_account` 的 VIP 等级来源，若无法确认则移除该字段；
   - 说明 `private_account.checked_at` 语义。

5. **§6 耦合面**：
   - 修正 Task B 依赖为 `funding_interval_hours`、`daily_funding_rate`、`net_daily_yield`、`private_account` 块、borrow_validation 扩展字段；
   - 在 R9 dispatch packet 中列明全部耦合字段。

6. **O1 排序**：默认 `net_daily_yield` 降序，null 回退 `abs(daily_funding_rate)` 降序。

修订后由 Codex 做 synthesis/ratification，用户批准后进入 stage design。

---

模型身份：Kimi-2.7（本地 Kimi Code 默认模型）  
本地北京时间: 2026-07-05 21:28:29 CST  
建议下一步调用模型：Claude-GLM 或 GPT/Codex 进行独立评审（与本轮互不参考），三份评审齐后由 Fable5 吸收出 DRAFT-2。
