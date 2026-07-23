# 方向草稿 — Hedge Open Real API v1（独立 panel 稿）

模型：Claude Opus 4.8（Claude Code 运行时）。角色：direction-panel 独立成员，只读。
本稿不修改源码、不访问凭据、不下单、不起服务、不发 Binance 私有请求；仅写入本草稿文件。
本稿是独立方向意见，不是已批准的 `10-design.md` 或 ADR，也不替代 `06-direction-synthesis.md`。

---

## 0. 阅读与前置声明（事实 vs 设计选择）

- **事实（facts）**：来自 supplied-doc / official-doc / 公开只读样本，见
  `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`。
- **设计选择（design choices）**：本稿的取舍与推荐，可被用户否决。
- **冻结输入（frozen）**：dispatch §Frozen Inputs 与 `00-intake.md` / `01-design-discussion.md`
  中用户已定的决策。我不静默替换任何冻结项；仅在 §2 显式标注我判断为不安全或自相矛盾之处。

一句话立场：**本轮用户的执行决策（两腿都传基础币 `quantity=q_common`、并发派单）
实际上把 recon 里最重的几个阻塞项（B-1 串行、B-3 `quoteOrderQtyMarketAllowed`、
B-4 UM 数量损耗）全部消解了**——因为不再用 `quoteOrderQty`、不再从现货 `executedQty`
事后派生 UM 腿。剩下的真实危险集中在**单腿敞口窗口**和**正向 BUY 的 USDT 花费不可预知**
这两点上。方向应围绕这两点收口，而不是重演 recon 的 quote-buy 串行分析。

---

## 1. 与 recon 的关系：哪些结论本轮已作废

recon 的核心结论建立在「正向 BUY 传 `quoteOrderQty`」这一**旧工作规则**之上。
用户在 `00-intake.md`「User Decisions Recorded 2026-07-23」与
`01-design-discussion.md`「User Execution Decision Update」中已明确**覆盖**它：
两个方向、两条腿一律传基础币 `quantity=q_common`，`quoteOrderQty` 退出本阶段执行契约。

| recon 阻塞项 | 本轮状态 | 依据 |
|---|---|---|
| B-1 正向必须串行 | **消解**：两腿都用 `quantity`，可预对齐 → 可并发 | 用户执行决策 + PAPI margin MARKET 支持 `quantity`（事实，L37463） |
| B-3 `quoteOrderQtyMarketAllowed` 可变需 fail-closed | **不适用**：本阶段不使用 `quoteOrderQty` | 同上 |
| B-4 UM 数量从 `executedQty` 取整损耗 | **消解**：UM 腿用预定 `q_common`，不再事后派生 | 同上 |
| B-2 单腿敞口窗口 | **仍在**（并发下窗口更小但非零） | 本稿 §5/§6/§11 |
| B-5 `sideEffectType` PAPI 权重不确定 | **仍在但无影响**：本阶段固定 `NO_SIDE_EFFECT`（UID 权重 6） | recon §4.4 |
| B-6 PM-Pro 兼容未验证 | **仍在**：本阶段目标为常规 PM，PM-Pro 越界 | recon §5，`02-api-recon-intake.md` |

**事实校正（重要）**：`01-design-discussion.md`「Carried Facts」第 1–2 条与「Order-intent model」
表格里仍写着「正向现货必须 `quoteOrderQty`、`q_perp` 保守派生、两腿不能预对齐」——**这段已被
同一文档后半的「User Execution Decision Update」推翻，属于文档内部的陈旧残留**。合成稿
（`06-direction-synthesis.md`）应以后者（并发 `q_common`）为准，并显式作废前者，避免下游实现按
过时的 quote-buy 模型编码。这是我作为独立评审识别到的**文档内部不一致**，按 packet 要求指出但不替用户改定。

---

## 2. 我判断为不安全或需用户显式确认的冻结假设

不静默替换，仅标注供合成/用户裁决：

1. **正向 BUY 用基础币 `quantity` + `NO_SIDE_EFFECT`，USDT 花费不可预知（关键风险）。**
   - 事实：MARKET BUY 传 `quantity=q_common` 时，成交花费的 USDT 由订单簿即时决定，preflight 时未知。
   - 风险：若可用 USDT 不足以吃满 `q_common`，现货 BUY 可能**被拒/部分成交**，而 UM SELL 并发已成交
     → 裸空永续单腿敞口。冻结输入允许「无自动修复」，但这把风险前移到 **preflight 的 USDT 余量估计**上。
   - 我的设计选择：preflight 用**保守价**（如 `ask × (1+buffer)`，buffer 建议 0.5%–1%，作为可配置项）
     估算 `q_common × N` 轮的 USDT 需求，并对照 `crossMarginFree(USDT)`；不足则拒绝 Start，套用 stage-1 余额不足模态文案。
   - 需用户确认：buffer 取值（这是 preflight 保守度，不是产品数值上限，故不违反「无数值上限」冻结项）。

2. **「both filled 不做数量相等校验」在本模型下是安全的，但要防被误用。**
   - 事实：两腿都是 MARKET + 同一 `q_common`，正常流动性下两腿都会足额成交 `q_common`，敞口天然对齐。
   - 因此「不做相等校验」在这里合理（差异只来自手续费与极端部分成交）。**但**：一旦某腿部分成交而另一腿足额，
     就不是「both filled」而是 partial → 必须落入暂停/核对分支。设计上要保证 `classify_attempt` 的
     「both filled = success」**只在两腿 status 均为 FILLED 且成交量均 == 下单量**时成立，否则一律进核对。

3. **并发派单 + 无自动修复 = 敞口检测责任全压在核对与人工上。**
   - 冻结项明确「single-leg/partial/timeout/unknown 暂停并核对；不 auto-borrow/repay/close/repair」。
   - 我认同这个安全姿态，但要求状态机把「both_mismatched_contract_gap」这个 round-1 遗留的信息丢失点
     替换为**同时展示两腿真实成交量 + 残余敞口**的可复核表示（呼应 dispatch 的 F 项）。

4. **本阶段是否真的写入 live POST 代码。**
   - 冻结/intake：里程碑「包含真实 PAPI 下单适配器」，但「实际激活与首笔实盘是独立人工动作」。
   - 我的推荐（见 §7）：**本阶段写入受闸门保护的 live POST 适配器并证明其不可达**，激活留作独立人工步。
     Codex 的 `01-design-discussion.md`「Recommended Direction」倾向「先做 production-parity dry-run、
     把 POST 适配器放到单独激活 stage」。两者可调和，但**若用户希望缩小本阶段面**，把 POST transport 也推迟、
     本阶段止于「真实只读 preflight + record transport 的 production-parity dry-run」是更保守的合法替代。
     这是一个**需用户拍板的范围决策**（intake「Human Gates」已列为待决），我不替其选定。

---

## 3. 只读 preflight（read-only 输入清单）

在**全局 Start** 和**每个 task 首次 attempt 之前**执行，任一失败 fail-closed 阻断 Start：

| 顺序 | 端点 | 权重 | 用途 | 关键字段 |
|---|---|---|---|---|
| 1 | 现货 `GET api.binance.com/api/v3/exchangeInfo?symbol=X` | — | 现货 filters | `LOT_SIZE`/`MARKET_LOT_SIZE`/`NOTIONAL`(minNotional, applyMinToMarket) |
| 2 | UM `GET fapi.binance.com/fapi/v1/exchangeInfo`（按 symbol 过滤） | — | UM filters | `LOT_SIZE`/`MARKET_LOT_SIZE`/`MIN_NOTIONAL` |
| 3 | `GET /papi/v1/um/positionSide/dual` | 30 | 确认单向/双向；**不在流程内切换** | `dualSidePosition` |
| 4 | `GET /papi/v1/account` | 20 | 账户健康 | `accountStatus==NORMAL`、`uniMMR`、`totalAvailableBalance` |
| 5 | `GET /papi/v1/balance` | 20 | 余额 | 正向查 `crossMarginFree(USDT)`；反向查 `crossMarginFree(base)` |
| 6 | `GET /papi/v1/rateLimit/order` | 1 | 下单限频快照 | `rateLimitType`/`interval`/`limit`（F-004 持久化） |

- **`maxBorrowable` 仅作核验，绝不当作可卖量**（承接 ADR-3）。反向只卖「借币系统已借到、当前 `crossMarginFree(base)` 覆盖」的量；**不 auto-borrow**。
- PAPI 无独立 exchangeInfo，filters 必须从各市场公开端点读取，不硬编码（事实，recon §3.4）。
- preflight 快照（filters 版本、余额、持仓模式、限频、时间戳）随 attempt 不可变持久化，供事后核对与复核。
- 时间同步：签名请求 `timestamp` 必传；`recvWindow ≤ 5000ms`；用 `/papi/v1/time` 或 NTP 校准并**监控本地-服务器偏移**
  （偏移监控本轮即使不做平滑 WS 也应落地，为下阶段 DI-1 门做准备——这是设计选择，非强制）。

---

## 4. Decimal 与 filter 行为（q_common 共同网格）

全程 **Decimal 定点**，逐腿按各自 filter 序列化，禁止科学记数法、禁止用 `quantityPrecision` 代替 filter（事实，recon §2.2.3）。

1. **每腿有效数量步长**：`MARKET_LOT_SIZE` 若启用则用之；**字段为 0 视为该约束关闭**，回退 `LOT_SIZE`（F-003；事实，recon §2.2）。
   - 样本：现货 `MARKET_LOT_SIZE.stepSize=0` → 回退 `LOT_SIZE.stepSize=0.00001`；UM `MARKET_LOT_SIZE.stepSize=0.001`。
2. **共同网格 = 两腿有效步长的较粗者（且互为整数倍时取 max）**：`lcm(0.00001, 0.001)=0.001`（0.001 是 0.00001 的 100 倍，整除）。
   `q_common = floor(single_amount / 0.001) * 0.001`。
3. **逐腿 min/max/notional 复核**（取整后再查，顺序不可颠倒，F-003）：
   - `q_common ≥ max(现货有效 minQty, UM MARKET_LOT_SIZE.minQty)`；
   - `q_common ≤ min(现货有效 maxQty, UM MARKET_LOT_SIZE.maxQty)`；
   - 现货 `NOTIONAL`：`q_common × 保守价 ≥ minNotional`（BTCUSDT=5，`applyMinToMarket=true`）；
   - UM `MIN_NOTIONAL`：`q_common × markPrice ≥ 50`。
   - 样本上 **UM 约束通常最紧**（minQty 0.001、min_notional 50 主导），preflight 计算即可暴露不可行。
4. 任一复核失败 → 拒绝该 attempt，不发任何腿。**两腿共享同一 `q_common`，绝不逐腿独立取整**（承接 ADR-2 的正确内核）。
5. 序列化：数量为定点字符串，精度 ≤ 相应 `baseAssetPrecision`；正向 BUY 与反向 SELL 现货腿的 `sideEffectType=NO_SIDE_EFFECT`。

方向映射（承接冻结表）：

| 方向 | margin 现货腿 `/papi/v1/margin/order` | UM 永续腿 `/papi/v1/um/order` |
|---|---|---|
| forward | `BUY` MARKET `quantity=q_common` `NO_SIDE_EFFECT` | `SELL` MARKET `quantity=q_common` `positionSide=BOTH`(单向)/`SHORT`(双向) |
| reverse | `SELL` MARKET `quantity=q_common` `NO_SIDE_EFFECT` | `BUY` MARKET `quantity=q_common` `positionSide=BOTH`/`LONG` |

两腿 `newOrderRespType=RESULT`；`newClientOrderId` 由单一 `attempt_id` 派生、逐腿唯一；开仓不传 `reduceOnly`；永不 `MARGIN_BUY`/`AUTO_REPAY`。

---

## 5. 持久 attempt 与状态转移

**在任何 POST 之前**（F-005：真正的「先持久后发送」），写入不可变 attempt 记录：

```
attempt_id, margin_client_id, um_client_id, direction, symbol,
q_common, preflight_snapshot{filters_version, balance, position_mode, rate_limit, ts},
status=PENDING
```

状态机（承接 ADR-4、locked policy）：

1. `PENDING` → 全部闸门 + preflight 通过 → 并发提交两腿（§6）。
2. 两腿均 `FILLED` 且成交量均 == `q_common` → `balanced`，`success_count++`。记录两腿真实
   成交量/均价/手续费（如返回）与残余（正常为 0，仅手续费差异）。
3. 任一腿 timeout/5xx/断连/非 `FILLED`/部分成交 → `unknown` 分支：**不重发该 client_id**，
   按 client_id 查 `margin/order`+`um/order` → 必要时 `margin/myTrades`+`um/userTrades` → `um/positionRisk`，
   确定真实成交量与持仓。
4. 一腿 FILLED + 另一腿 REJECTED/EXPIRED/部分/零/unknown → `single_leg_exposure`：置 `leg_exposure`（JSON），
   status → `exposure_alert`，**暂停本 task 且暂停全局派单**；落两腿真实态。**不 auto-hedge / 不 auto-close / 不 auto-repair**。
5. 两腿都 FILLED 但成交量不等（极端部分成交下才可能）→ `mismatch_exposure`：以**同时展示两腿真实成交量 + 残余敞口**
   的结构记录，暂停核对。**这替换 round-1 的 `both_mismatched_contract_gap` 信息丢失表示**（dispatch F 项）。
6. 累计 `fail_count > 3` → 终止计划、暂停、不再发。

HTTP 503 语义（事实，recon §3.3）：`503 Unknown error` = **执行态未知、可能已成功**，必须查询、禁止直接重试；
`503 Service Unavailable` / `-1008 throttled` = 失败可退避。这些分支直接决定第 3 步走向。

---

## 6. 并发派单与核对

- **并发**：attempt 持久化后，两腿 MARKET 同时提交（如 asyncio gather 或双线程）。两腿权重各 1 → 一次对冲 = 2 个 order event。
- **限频**（F-004）：持久化 `rateLimit/order` 快照，最紧者生效；触发 429/418 → 停止排队、保留未发 task、**不加速重试**。
- **核对（reconciliation）以持久化的 client_id 为唯一锚点**：任何歧义响应都不信 POST 返回本身，按 §5 第 3 步查订单/成交/持仓。
  同一 client_id 永不重发（防重复下单）。
- **敞口的真相来源**是 `um/positionRisk` + 两腿成交历史，而非 POST 返回。核对结果每步都回写 attempt 记录。
- F-006：live 模式下移除 round-1 的 fill-all 空转；每个手动动作（fill-once/fill-all/start）都要**重新对照全局 Start 闸门与 executor 模式**再执行。

---

## 7. 真实 POST 闸门与证明

真实 POST 需**同时**满足（承接 ADR-5，收紧）：

1. 进程启动即 `APP_HEDGE_EXECUTOR=live`；否则装配 `DisabledHedgeExecutor`（record transport）。
2. 持久化**全局 Start 闸门 = ON**。
3. 新鲜 preflight 通过且在短 TTL 内。
4. 服务端计算的闸门/风控通过（余量、filters、限频、账户健康）。
5. task 级**显式确认**（首次实盘 attempt 的人工 acknowledgement）。
6. **人工批准的首笔实盘流程**（不能由 config flag 推断）。

**闸门证明（必须有测试）**：
- 断言 `APP_HEDGE_EXECUTOR` 未设 **或** Start 闸门 OFF 时，**任何路径都到不了网络 POST**（仅 record transport）。
- record transport 记录**将要发送的已签名参数形状（无 secret/无签名串）**、filters 版本、preflight 快照、client_ids；不发网络。
- 源码/工件/日志中**无凭据**。
- 真实订单响应样本**仅**来自后续人工授权的实盘，绝不伪造（Hard Gate follow-up）。

**范围推荐**：本阶段写入受上述 6 闸保护的 live 适配器**并证明其不可达**，把「激活 + 首笔实盘」留作独立人工步。
若用户偏保守，可把 POST transport 也推迟到单独激活 stage，本阶段止于 production-parity dry-run——见 §2.4，属用户范围决策。

---

## 8. API / UI 契约

**API**（承接 round-1，字段名冻结 + 本轮增量）：
- `POST /api/hedge-open-tasks`（create：coin, direction, mode=immediate, single_amount(base), target_n）
- `GET /api/hedge-open-tasks`（list，可按 status 含 `deleted` 过滤）
- `POST /api/hedge-open-tasks/<id>/{pause|start|delete|fill-once}`（live 下 `fill-all` 语义受 F-006 约束或下线）
- `GET /api/hedge-open-settings`（executor 模式 + Start 闸门徽标）
- `GET /api/hedge-open-logs`（分页）
- `GET /api/hedge-open-positions`（由 fills 聚合）
- 增量：attempt/leg 的真实成交量、残余敞口、preflight 快照引用、限频快照。

**UI**（承接 stage-1，中文优先）：
- 立即开单 = 真实 create；平滑开单 present-but-disabled + 「下一轮」提示。
- 执行徽标：dry-run vs live + Start 闸门态。
- 余额不足走真实 preflight 结果 + stage-1 方向化模态文案。
- `exposure_alert` / `mismatch_exposure` / 终止态必须可渲染，且 `mismatch_exposure` 展示**两腿真实量 + 残余**，不再谎报某腿缺失。
- **服务端是风控唯一权威**：浏览器只显示有效限制与拒绝原因，不参与计算（承接 `01-design-discussion.md` control-plane 立场）。

---

## 9. 测试策略

硬规则：**CI 中任何测试都不发真实 Binance 请求**；live executor 永不对网络执行，只测 record transport 与 disabled/gated 路径。

覆盖点：
1. q_common 共同网格：零值 stepSize 回退、`floor` 取整、逐腿 min/max/notional 复核、UM 主导拒绝（F-003）。
2. 方向映射与 `sideEffectType=NO_SIDE_EFFECT`、`positionSide` 快照、无 `reduceOnly`。
3. 状态机全分支：balanced / single_leg_exposure / mismatch_exposure / unknown(503 三态) / `fail_count>3` 终止。
4. **先持久后发送**：attempt 在 POST 前落库（F-005，用可注入的失败点验证）。
5. **闸门不可达证明**：`APP_HEDGE_EXECUTOR` 未设或 Start OFF → 无网络 POST（§7）。
6. 限频快照持久化 + 429/418 停派（F-004）。
7. 可注入 dry-run 结果：强制单腿失败/敞口，端到端跑通 `exposure_alert` 与终止路径（承接 round-1 injectable seam，test/ops-only，绝不影响 live）。
8. preflight 只读断言：不触发任何写端点、无凭据入日志。

---

## 10. 文件 / 任务拆分

复用 `borrow_tasks` 模块形（ADR-1），后端在 `backend/hedge_open_tasks/`：
- `domain.py`（纯逻辑：q_common 网格、filter 解析、状态分类）——**backend owner**
- `store.py`（durable SQLite：attempt/fill/settings/logs，先持久后发送）——backend owner
- `executor.py`（disabled 默认 + gated live + record transport + 真实 PAPI 适配器）——backend owner（真实资金面，评审重点）
- `service.py`（编排、调度线程、全局 Start、preflight 只读）——backend owner
- API handlers 接入现有 server——backend owner
- 前端接线（`fill-all`/live 徽标/exposure 展示/mismatch 结构）——frontend owner

按 `AGENTS.md` 域路由：后端/契约/schema/normalization = Claude-GLM；前端/UI/集成 = Kimi。
本里程碑后端占绝对主体（真实下单核心 + 风控 + 状态机），前端多为展示接线——
**是否走 `docs/parallel-development-mode.md` 并行拆分**由 breakdown 阶段按工作量决定；
若前端仅轻量接线，可整包给后端 owner，前端做小幅展示补丁（这是 breakdown 的判断，不在本方向稿定死）。

---

## 11. 残余风险

1. **正向单腿敞口（最高）**：现货 BUY 因 USDT 不足被拒/部分，而 UM SELL 已成 → 裸空永续。缓解：保守 USDT 余量 preflight（§2.1）+ 检测暂停，不自动补。
2. **反向单腿敞口**：现货 SELL 已成、UM BUY 失败 → 裸卖现货（可能动用已借基础币）。同样仅报警暂停。
3. **无 PAPI testnet（事实）**：dry-run 只能 record transport；真实响应样本必须后续人工授权采集，绝不伪造。
4. **filters 漂移**：exchangeInfo 逐 attempt 读取或带刷新缓存，避免用陈旧网格发单。
5. **时钟偏移**：即便本轮只做 immediate，签名时间窗与后续平滑门都依赖本地-服务器偏移监控；建议本轮先落偏移日志。
6. **B-5 PAPI 权重不确定 / B-6 PM-Pro 未验证**：本阶段 `NO_SIDE_EFFECT` 无权重影响、目标常规 PM；PM-Pro 若适用需另行验证。
7. **文档陈旧残留**（§1 校正）：若合成/实现误用 `01-design-discussion.md` 前半的 quote-buy 模型，会实现出与冻结决策矛盾的正向下单参数。

---

## 12. 需用户拍板的开放项（不替其选定）

1. **范围**：本阶段是否即写入受闸门保护的 live POST 适配器（我推荐：是，但激活独立），还是止于 production-parity dry-run。
2. **保守度参数**：正向 USDT 余量 buffer 取值（preflight 保守度，非产品数值上限）。
3. **`fill-all` 在 live 下的去留**（F-006）：下线，还是保留但每轮重校 Start 闸门。
4. **首笔实盘流程清单**：谁、何时、以何规模、如何记录——必须人工批准，不能由 flag 推断。
5. **反向可卖量来源确认**：确认反向只卖借币系统已借、`crossMarginFree(base)` 覆盖之量，永不 auto-borrow。

---

当前 Session ID: unavailable（Claude Code 运行时未向本模型暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/direction-drafts/claude-opus-4-8.md
本地北京时间: 2026-07-23 16:21:28 CST
下一步模型: bookkeeper
下一步任务: archive this raw direction draft; do not implement code
