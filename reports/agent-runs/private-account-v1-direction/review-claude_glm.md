# 评审 — 私有账户数据接入 v1 方向草案 DRAFT-1

- **评审者**：claude_glm（zhipu / glm-5.2，fresh 独立会话）
- **评审对象**：`docs/private-account-v1-direction-draft.md`（DRAFT-1，Fable5 起草）
- **上游基线**：`docs/phase2-direction-draft.md`（FROZEN，Codex ACCEPT-FREEZE）
- **独立声明**：本评审未参考 GPT/Codex/Kimi 任一方评审；端点主张均基于
  `llms-full.txt` 原文行号核实（行号已逐一回读验证）。
- **本地北京时间**：2026-07-05 21:32 CST

## 总结论：**REWORK**（附必改清单）

DRAFT-1 的方向骨架健康（永久禁令继承清晰、端点行号引用全部正确、
契约 additive、隐私脱敏方向正确、§3.4 方向语义正确），但存在 1 项 P1
（成本腿依赖链未闭合，可能使 §1 目标 1「账户真实档位利率」落空）与
3 项 P2（成本腿单位口径、排序键推翻已冻结 ADR-3、脱敏字段清单缺失），
属方向可行性级别问题，须 REWORK 后再合成。

---

## 一、逐节裁定（§1-§8）

- **§1 背景与目标** — **REWORK**。目标 1（账户真实档位利率替代 VIP0 基准）
  的依赖链在 §3.1 未闭合（见重点②/P1）：E2 适用性未验证且 fallback 缺
  VIP 等级来源端点，目标 1 有落空退回 VIP0 的风险，与目标措辞自相矛盾。
  其余目标 2-4 合理。
- **§2 与冻结基线的关系** — **AGREE**。永久禁令不变、websocket 后置独立轮、
  本轮禁止实现 websocket 铺垫代码——边界清晰，与基线 §3.2 一致。
- **§3.1 账户真实借币利率** — **REWORK**。E1/E3/E4 端点族正确，但 E2 是
  `/sapi` 经典杠杆族（非 `/papi` 统一账户族），与基线 §4「统一账户走 /papi」
  的路径族结论存在张力；fallback「账户实际档位」的来源端点未列入候选
  （见 P1）。
- **§3.2 负费率候选借币验证全覆盖** — **AGREE**。bounded top-N → 全负费率
  `MARGIN_SPOT_CANDIDATE ∩ CRYPTO` 候选，直接修补 ADR-5 遗留（portfolio_account
  全 null）；bStock 维持不探测合理。限速预算留 O4 合理。
- **§3.3 持仓与余额（GET 轮询）** — **AGREE**。E3/E4 选型与行号正确
  （见行号核实表），60s 沿用不引新机制，零红线冲突。
- **§3.4 净收益测算** — **REWORK**。方向语义正确（见重点①），但成本腿
  「借币日利率」的单位归一化未写死（E2 是 hourly 利率，须 ×24；crossMarginData
  `dailyInterest` 口径须 discovery 确认），净收益两腿口径一致性无保障（P2）。
- **§3.5 排序** — **REWORK**。提议改 net_daily_yield 降序会推翻**已冻结的
  ADR-3**（排序列 = abs(daily) 降序），属耦合面变更，按 R3 须停手上报而非
  stage 内自决；且正/负费率行 net 公式不对称，单一排序键可比性存疑（P2/O1）。
- **§4 契约草案 v0.3** — **AGREE**。`net_daily_yield`、`daily_interest_account`、
  `private_account` 三态块均为 additive，schema 升级路径正确，旧前端优雅降级
  沿用合理。
- **§5 安全与隐私条款** — **REWORK**。新增隐私红线方向正确（数值脱敏、落档
  占位、UI 渲染才显真值），但脱敏**字段清单未列**（见 P2）；余额/持仓敏感度
  高于 Phase 2 的额度字段，须像 Phase 2 raw-field freeze 一样在 H_intake 冻结
  全数值字段清单。
- **§6 复杂度评级与执行方式** — **AGREE**。MILESTONE 申报合理（白名单翻倍 +
  账户敏感数据首次入 UI）；并行试运行 #2 + stage 分支制首跑承接 DEC-2026-07-05-001，
  与上一 stage 收口交接一致。
- **§7 开放问题** — **AGREE**（问题清单完整，逐一作答见下）。
- **§8 已识别后续方向** — **AGREE**。websocket 修正案与开仓规划后置合理，
  触发条件清晰。

---

## 二、行号引用核实（DRAFT-1 全部正确）

| 端点 | DRAFT 引用行号 | 原文回读 | 结论 |
|---|---|---|---|
| E1 `GET /papi/v1/margin/marginInterestHistory` | L186218 | L186218 `##### GET /papi/v1/margin/marginInterestHistory`「获取杠杆利息历史」Op `getMarginBorrowLoanInterestHistory` | ✅ 正确，papi 族 |
| E2 `GET /sapi/v1/margin/next-hourly-interest-rate` | L37035 / L151129 | L37035 changelog 中文「查询用户币种预估下小时利率」；L151129 英文「Get user the next hourly estimate interest」；标题行 L189205 | ✅ 正确，**sapi 经典杠杆族** |
| E3 `GET /papi/v1/balance` | L186080 | L186080「查询账户余额」Op `accountBalance`，隶属「Portfolio Margin REST API…通过 Binance 统一账户进行交易」 | ✅ 正确，papi 族 |
| E4 `GET /papi/v1/um/positionRisk` | L186324 | L186324「用户UM持仓风险」Op `queryUmPositionInformation` | ✅ 正确，papi 族 |

> 说明：首轮 grep `positionRisk` 因 `head -20` 截断未显示 L186292/L186324，
> 回读原文确认 L186324 引用无误。DRAFT-1 的行号引用纪律严谨，本轮未发现
> 张冠李戴。

---

## 三、重点核查

### ① §3.4 净收益公式方向语义 — **正确** ✅

- **负费率行**（fundingRate<0 → 空头付多头 → 多头收钱）：做多永续收
  `|fundingRate|` + 借币做空现货对冲 delta，借币有成本。
  `net = |daily_funding_rate| − 借币日利率`。✅ 方向与口径（日均）正确。
- **正费率行**（fundingRate>0 → 多头付空头 → 空头收钱）：做空永续收
  `fundingRate` + 做多现货对冲（用自有 USDT，无借币）。
  `net = daily_funding_rate`。✅ 方向正确。
- 唯一遗漏：正费率行做多现货占用 USDT 的**资金机会成本**未建模（§3.4
  仅声明「交易成本不建模」，但资金成本 ≠ 交易成本）。负费率行扣了借币
  成本、正费率行未扣资金成本，跨行 net 比较时正费率行系统性偏高（见 P3）。
  方向语义本身无误，记为设计假设级 P3。

### ② E1-E4 与统一账户（非 Pro）适配性 — **E1/E3/E4 ✅，E2 ⚠️ + fallback 未闭合**（P1）

- E1/E3/E4 均为 `/papi` 族，隶属「Portfolio Margin REST API…统一账户」
  （L186073-186075），与基线 §4 结论一致。✅
- **E2 是 `/sapi` 经典杠杆族**（标题行 L189205 隶属 `borrow-repay` 分组，
  Op `getFutureHourlyInterestRate`），**不是**统一账户 papi 族。DRAFT-1
  自标「需验证统一账户适用性」+ O5，态度诚实。
- 关键证据：统一账户**专用的**利率端点 `GET /sapi/v1/portfolio/interest-rate`
  **已被 deprecated**（L150993 原文「has be deprecated, users can query the
  Classic Portfolio…」）。因此 E2（next-hourly-interest-rate）是当前唯一可用
  的「预估下小时利率」端点——**DRAFT-1 不选 portfolio/interest-rate 是对的**，
  但 E2 对统一账户（非 Pro）的适用性仍属未验证项。
- **fallback 未闭合（P1 核心）**：DRAFT-1 §3.1 规定 E2 不适用时 fallback =
  crossMarginData VIP 利率表 + 「账户实际档位（档位来源由 discovery 确认）」。
  但「账户实际档位」的来源端点 DRAFT-1 **未列入候选**。原文回读确认
  `GET /sapi/v1/account/info`（L6704）返回「VIP 等级 / 是否开启杠杆帐户 /
  是否开启合约帐户」——这正是 fallback 所需的账户档位来源。DRAFT-1 既未
  列此端点，fallback 路线在 discovery 前是悬空的：若 E2 不适用且未预备
  VIP 等级端点，则「账户真实档位利率」（§1 目标 1）无可达路径，会退回
  VIP0 基准——与目标 1 措辞直接矛盾。

### ③ 安全/隐私条款漏洞 — **方向正确，字段清单缺失**（P2）

- §5「余额/持仓数值属敏感数据，落档样本与日志一律 capture-time 脱敏」方向
  正确，且与 Phase 2 脱敏政策（contract v0.2 §3 末「落档 JSON 不含 balance/
  free/locked/amount 等」）一致升级。
- audit log 继承 Phase 2 设计（`private_client.py` L131-139 仅记 sanitized
  path + status + latency，不记数值/凭据）✅，本轮 E3/E4 经同一 HMAC 出口，
  审计卫生自动继承。
- **漏洞（P2）**：E4 `positionRisk` 返回字段含 `entryPrice`/`markPrice`/
  `unRealizedProfit`/`positionAmt` 等，**组合可反推持仓规模与账户敞口**。
  §5 仅笼统说「余额/持仓数值」，未列具体脱敏字段清单。敏感度高于 Phase 2
  的额度字段（maxBorrowable/borrowLimit 是「额度」非「真实持仓」），须像
  Phase 2 raw-field freeze 一样在 H_intake 冻结「全数值字段 → 占位」映射表，
  并配单测断言落档 JSON 不含任一真实数值字段。
- 前端真实展示（§4 private_account 入 UI）+ 无 telemetry（前端为纯静态
  index.html，Phase 1-2 无外部上报）：风险低，记 P3。但 O2 隐私模式默认值
  应取「默认隐藏」（见 O2）。

### ④ 与永久禁令的隐性冲突 — **无冲突** ✅

- E1-E4 全部 GET 只读：E1 查利息历史、E2 查预估利率、E3 查余额、E4 查持仓
  风险——均无 order/borrow/repay/transfer/withdraw 执行语义，无 listenKey/
  user data stream/websocket。✅
- 白名单扩项保持 `(method, exact-path)` 二元组 + base_url 硬编码
  （`private_client.py` L41-46 anti-injection 模式），E1/E3/E4 →
  papi.binance.com、E2 → api.binance.com（**混族 base_url**，须 discovery
  逐端点冻结，记 P3）。
- 需警惕的命名陷阱（本轮未选，无冲突，仅提示）：L186300 `GET /papi/v1/margin/marginLoan`、
  L186312 `GET /papi/v1/margin/repayLoan` 字面似「借还币执行」，实为**查询**
  借还记录（GET）；真正永久禁止的是 L186225 等 `POST .../borrow-repay` 执行
  端点。本轮不选 query 版，无冲突。

---

## 四、开放问题逐一作答

- **O1 排序基准** — 建议**保持 abs 日费率降序，net_daily_yield 仅作辅助展示列**。
  理由：(a) 改 net 降序会推翻已冻结 ADR-3（耦合面变更，R3 须停手上报）；
  (b) 正费率行 net=daily（未扣资金成本）、负费率行 net=|daily|−借币成本
  （已扣），两行 net 语义不对称，混排可比性差；(c) net 高度依赖 E2/借币
  利率可用性（见 P1），在成本腿端点稳定前排序键绑 net 会使排名随成本腿
  可用性漂移。net 作辅助列既兑现「工具升级为决策依据」（§1 目标 4），
  又不破坏已冻结排序契约。

- **O2 隐私模式开关** — 建议**默认隐藏金额（占位），点击显真值**。
  理由：余额/持仓是敏感数据，安全默认 = 默认脱敏；本地单机场景可放宽，
  但「默认隐藏 + 显式点击」是更稳的默认值，且实现成本低（前端 toggle +
  CSS），不引入新刷新机制（§3.3 约束）。

- **O3 持仓展示范围** — 建议**仅 UM 永续持仓（E4）+ 余额列表（E3），不做
  现货折算**。理由：现货折算引入估值口径（用哪个价？mark/index/last？）、
  聚合粒度（跨账户子项？）等复杂度，超出本轮「GET 数据看板」目标；
  E3 余额已含各币种余额，E4 给 UM 敞口，足以支撑净收益决策语境。现货
  折算留开仓规划轮。

- **O4 限速预算** — 建议：探测集 = 全负费率 `MARGIN_SPOT_CANDIDATE ∩ CRYPTO`
  候选（当前市场约数十行，discovery 后冻结精确上限）；逐 asset 调
  maxBorrowable，**并发 ≤ 2** + 沿用 1h TTL 缓存 + 429/-1003 单次有界退避
  （继承 `private_client.py` L141-158）；bStock 排除（§3.2）。调用量上限
  = 负费率候选数（动态，非硬编码符号清单——遵守基线红线）。

- **O5 E2 统一账户适用性 fallback** — 建议**成立但须闭合**：(1) H_intake
  discovery 首先实测 E2 对统一账户（非 Pro）是否返回有效预估利率；
  (2) 若适用，成本腿用 E2 hourly × 24 归一化为日利率；(3) **若不适用，
  fallback = crossMarginData VIP 利率表 + `GET /sapi/v1/account/info`
  取账户 VIP 等级 → 匹配档位利率**——DRAFT-1 须将 `/sapi/v1/account/info`
  补入端点候选（见 P1 必改）；(4) 若 fallback 也不可达，**显式声明 §1
  目标 1 降级**（退回 VIP0 或「账户实际档位不可得」），不得静默退回而
  保留「账户真实档位利率」措辞。

---

## 五、新风险（P1/P2/P3）

### P1

- **[P1] §3.1 + §3.4 + O5：成本腿依赖链未闭合，§1 目标 1 有落空风险。**
  - 定位：`docs/private-account-v1-direction-draft.md` §3.1（E2 fallback
    「账户实际档位来源由 discovery 确认」）+ §1 目标 1。
  - 缺陷：fallback 所需「账户实际档位」来源端点未列入候选；原文
    `GET /sapi/v1/account/info`（llms-full.txt L6704，返回 VIP 等级）可用
    但 DRAFT 未提。E2（sapi 经典杠杆族）对统一账户（非 Pro）适用性未验证，
    若不适用且无 VIP 等级端点预备，目标 1 退回 VIP0，与措辞矛盾。
  - 建议修法：将 `/sapi/v1/account/info` 补为第 5 个候选端点（白名单扩至
    5 项签名 GET）；写死 E2 适用性 discovery 的判定标准与 fallback 触发
    条件；若 fallback 全程不可达，显式降级 §1 目标 1 措辞。

### P2

- **[P2] §3.4：成本腿单位口径未写死，净收益两腿口径一致性无保障。**
  - 定位：§3.4「`net_daily_yield = |daily_funding_rate| − 借币日利率`」。
  - 缺陷：funding 腿用 `daily_funding_rate`（已归一化日），但成本腿
    「借币日利率」来源未定——E2 是 **hourly** 利率须 ×24，crossMarginData
    `dailyInterest` 字段名含 daily 但实际口径须 discovery 确认。两腿若非
    同口径，net 系统性失真。
  - 建议修法：§3.4 写死成本腿单位归一化规则（E2→×24；或 crossMarginData
    口径以 discovery 实抓冻结），并在 ADR 记录。

- **[P2] §3.5 + O1：排序键改动推翻已冻结 ADR-3，且正负费率行 net 不对称。**
  - 定位：§3.5「候选 = net_daily_yield 降序」+ ADR-3（已冻结 abs daily 降序）。
  - 缺陷：(a) 排序列变更属耦合面，按 R3 须停手上报，不得 stage 内自决；
    (b) 正费率行 net 未扣资金成本、负费率行 net 已扣借币成本，单一 net
    排序键可比性差。
  - 建议修法：采纳 O1 建议（保持 abs 日费率排序 + net 辅助列）；若必须改
    排序键，先显式声明 ADR-3 修订并解决对称性。

- **[P2] §5：脱敏字段清单缺失，positionRisk 数值组合可反推规模。**
  - 定位：§5「余额/持仓数值…数值换占位」。
  - 缺陷：未列具体字段；E4 positionRisk 的 entryPrice/unRealizedProfit/
    positionAmt 组合可反推持仓规模与账户敞口。
  - 建议修法：H_intake discovery 后冻结「全数值字段 → 占位」映射表（仿
    Phase 2 raw-field freeze），配单测断言落档 JSON 不含任一真实数值字段。

### P3

- **[P3] §3.4：正费率行未扣资金机会成本，跨正负费率行 net 比较时正费率虚高。**
  建议在 ADR 记录「正费率行不计自有 USDT 资金机会成本」假设，UI net 列
  对正/负费率行标注不同口径提示。

- **[P3] §3.1：白名单扩项 base_url 混族（sapi=api.binance.com /
  papi=papi.binance.com），discovery 须逐端点冻结正确 base。** 现有
  `private_client.py` 已支持混族（L42-45），但 E1-E4 扩项时每端点 base
  须 discovery 实抓确认，避免签名/请求落错域。

---

## 六、REWORK 必改清单

1. **闭合成本腿依赖**（P1）：§3.1/§3.4/O5 补 `/sapi/v1/account/info` 为
   fallback 候选端点；写死 E2 适用性 discovery 判定标准与 fallback 触发
   条件；确保 §1 目标 1 在 E2 不适用时有可达路径，否则显式降级目标措辞。
2. **写死成本腿单位归一化**（P2）：§3.4 明确 E2 hourly→daily ×24 或
   crossMarginData 口径，保证净收益两腿同口径。
3. **明确排序键决策**（P2）：§3.5/O1 采纳「保持 abs 日费率排序 + net
   辅助列」；若改 net 排序须声明 ADR-3 修订（R3 停手）并解决正负费率对称性。
4. **补脱敏字段清单**（P2）：§5 列 balance/positionRisk 全数值字段，
   H_intake 冻结映射表 + 单测。

修完上述 4 项后，方向即可进入 Codex 合成。

---

本地北京时间: 2026-07-05 21:32 CST
模型身份: claude_glm（zhipu / glm-5.2，fresh 独立会话；未参考 GPT/Codex/Kimi 评审）
评审纪律: 禁止写文件、未改工作树、未发起任何签名请求；端点主张均引 `llms-full.txt` 原文行号并回读核实。
