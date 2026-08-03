# 计划评审 — 现货下单账户路由 v1

被审对象：`docs/planning/spot-order-routing-v1.md`（草稿，2026-08-02）
评审角色：独立计划评审（AGENTS.md §8「计划评审」），只读，跨 provider（Opus5）
评审时间：2026-08-02 20:43 CST
评审基线：`main` @ `01bb3b1`（工作树内该计划文档为未跟踪新增文件）

**评审结论：REWORK（返工）**

本轮不授权实现。verdict 返回 Planner，不触碰 `rework_count`（§8 计划评审豁免）。
本评审未使用任何凭证、未发任何单、未改动 Start gate。

---

## 0. 先说计划做对的部分（这些不必重做）

以下判断经代码核实成立，应在返工版本中原样保留：

1. **「不得由 leg 名称反推 endpoint」是真缺陷，且定位准确。**
   `backend/hedge_open_tasks/service.py:2181` 现为
   `endpoint = D.SPOT_ORDER_PATH if leg_name == "spot" else D.PERP_ORDER_PATH`；
   `backend/hedge_open_tasks/store.py:795/812` 在建腿时把常量直接写进 `endpoint` 列；
   `backend/services/live_hedge_executor.py:566/747` 用 `leg == "spot"` 选 POST/GET。
   计划 §4 的要求切中要害。
2. **「普通现货不发 `sideEffectType`」正确。** 该参数只属于 margin 下单接口。
3. **「用解析后现货 pair 的 base asset（`TSLAB`）而非合约 base（`TSLA`）」正确。**
   `hedge_preflight_provider.py:116-127` 的 `_bstock_spot_alias` 已按
   `base + "B" + quote` 解析，计划的推论与实现一致。
4. **「不新增数据库迁移」经核实成立。** 逐尝试的 JSON 载体
   `hedge_open_attempt.preflight_fingerprint`（`store.py:766-780` 每次 attempt 写入
   `snapshot_record`）与逐腿的 `hedge_open_leg.endpoint TEXT NOT NULL` 都已存在。
5. **「51169 不得自动补腿、不得复用被拒 leg 的 client ID」是正确的红线**，且与既有
   `collateral_cap → 任务暂停` 行为一致。
6. **「每次 live attempt 前重新读取并冻结」与既有机制对齐。**
   `service.py:1792 _resolve_fresh_preflight` 确实在每次 live 发送前重跑预检（A-2），
   任务级 `preflight_snapshot` 只是建单时的 dry-run 回退，计划没有踩错节奏。

---

## 1. P0 — 阻塞项

### P0-1 `restricted-asset` 的接口性质被写错，且从未被实际读取过一次

计划 §2.2 与 §3.4 把 `maxCollateralExceededAsset` 当作既有事实使用，但：

- **仓库全历史零证据。** `git log --all -S "restricted-asset"` 与
  `-S "maxCollateralExceeded"` 均无命中；`grep -rn` 全仓命中的唯一位置就是这份计划本身。
  没有任何原始响应样本落盘。
- **上一 stage 明确要求过这次侦察，而它从未发生。**
  `reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md`
  （commit `5fe1a6f`）在取消 T4 付费判别单时写道：
  > "Still unknown: whether *any* API surface exposes the cap or its current
  > utilisation. … this needs a targeted read-only recon, recorded as such and
  > not assumed either way."
  并规定「若存在端点 → 预检可获得真实闸门；若不存在 → 预检不得假装能看见」。
  该侦察的落盘目录 `reports/api-samples/2026-07-hedge-order-truth-v1/` 在全历史中不存在。
  本计划直接跳到了「端点存在且语义如此」的分支，没有补上那一步。
- **接口性质描述错误（两处）。** 按 Binance 官方文档
  （developers.binance.com，Get Margin Restricted Assets）：
  | 计划的说法 | 实际 |
  |---|---|
  | 「签名接口」 | **MARKET_DATA**：只需 `X-MBX-APIKEY` 头，**不签名**、无 `timestamp`/`recvWindow` |
  | 「动态**账户**/平台信号」 | **纯平台级**，无参数，与账户无关 |
  | （未提） | 权重 1（IP 维度），响应为
  `{"openLongRestrictedAsset":[...], "maxCollateralExceededAsset":[...]}` |

  后果不是学术性的：现有 `HedgeOpenLiveClient._get_signed`
  （`hedge_open_live_client.py:194-212`）**无条件**注入 `timestamp`+`recvWindow`+
  `signature`。把签名参数打到一个 MARKET_DATA 端点上是未经验证的行为；计划 §3 的
  「鉴权失败 → `preflight_incomplete`」也建立在错误的签名语义之上。
- **「命中 ⇒ 会 51169」这一对应关系仍是推论。** 它高度可信（`02-collateral-cap-finding.md`
  已确证 NOM 触顶平台抵押上限并解释了 51169 的非对称拒单），但从未被一次真实读取
  交叉验证过；也无人验证 bStock 的 base asset（`TSLAB` 这类）是否会出现在该名单里
  ——它们未必是全仓杠杆资产。

**要求：** 实现开始前补一次只读侦察（权重 1、无签名、无下单、无资金动作），把原始响应体
整体落盘到 `reports/api-samples/<stage>/`，并据此改写 §2.2、§3.4 的事实陈述。
这正是 `02-collateral-cap-finding.md` 已经写好的那一步，成本接近零。

### P0-2 API key 的现货交易权限从未校验，而两腿是并发发出的 —— 这会造出裸空

`live_hedge_executor.py:713-721` 用两个线程**并发**提交现货腿与合约腿，预检通过后无条件发出。

`/api/v3/order` 与 `/papi/v1/*` 的 API key 权限位不同。若该 key 未开启现货交易权限：

1. 现货 POST 返回 `-2015`；
2. `domain.py:362` 把 `-2015` 归入 auth 层 → `classify_leg_response`
   （`live_hedge_executor.py:388-392`）判为 **`LEG_UNKNOWN_QUERYING`**（不确定，需查单）；
3. 与此同时**合约腿 SELL 已经成交**；
4. 查单同样 `-2015` → 10 次重试耗尽 → `SIGNAL_ORDER_STATE_UNKNOWN` → 任务暂停，
   提示操作者「去交易所核实订单状态」。

净结果：**一条裸空 + 一条误导性的「订单状态未知」诊断**，而真实原因是一个静态的、
本可零成本预先查明的配置问题。这恰恰是本计划想要减少的那类事故（2026-07-27 的
51169 裸空同型）。

**要求：** 把现货交易权限纳入 §3.5 的预检。**不需要新增任何调用**——计划已经要读
`GET /api/v3/account` 取普通现货 USDT 余额，该响应自带 `canTrade` 与 `permissions`
字段。`canTrade` 非真或 `permissions` 不含现货交易时，按 `preflight_incomplete`
处理：零 attempt、零 POST。§7 需增加对应验收项。

---

## 2. P1 — 需在返工版本中解决

### P1-1 平单缺口：本轮开出的仓位，未来的平单能力平不掉

`PROJECT_STATE.md` 记录当前**不存在平单功能**。regular_spot 买入的现货落在**经典现货
钱包**，不在统一账户。将来的平单如果按现有路由走 PAPI margin SELL，会因该钱包无余额而失败。

计划 §1 的非目标只写了「普通现货 `SELL` 降级……反向方向继续走既有 PAPI 路径」——
说的是**负费率方向**，没有覆盖「正费率任务开出的 regular_spot 现货腿如何平掉」。
这是本轮交付主动创造的、跨 stage 的前向负债。

**要求：** 在 §1 显式写明「regular_spot 开出的现货腿，在平单能力按路由感知实现之前
无法自动平掉」，并作为具名条目写入 `PROJECT_STATE.md`（不是只留在计划文档的非目标列表里）。

### P1-2 记账归属：既有展示限制 B 对 regular_spot 行会反转（评审问题 4 的靶心）

`PROJECT_STATE.md` 已接受的限制 **B**：持仓表读的是**经典现货**账户，而对冲买进的是
**统一账户**，所以漂移标记「永久失效」。

本改动使这一前提对 regular_spot 行**反向成立**：这些腿真的会落进经典现货钱包，于是
持仓表会**看见**它们，并与操作者无关的既有现货库存**混在一起**。限制 B 从「永远不报」
变成「对一部分行会报，且可能因混入无关库存而报错」——这是展示语义的实质变化。

计划 §2.5 只说了「漂移检测不可作为本路由的对账正确性证明」，等于把它当成一个静态的
既有限制绕开了，没有指出本次改动改变了它。**这是评审问题 4 的答案：存在这样一条路径，
且计划没有覆盖它。**

**要求：** §2.5 改写为「本轮改变了限制 B 的成立方向」，说明混入无关库存的可能，
并同步更新 `PROJECT_STATE.md` 中限制 B 的措辞。展示代码本轮仍可不改。

### P1-3 路由回读的权威载体未定，而后台对账路径没有路由入口

计划 §3 只说「本次预检的不可变记录至少包含 …」，没有说**查单时从哪里读回**。这一步不明确，
§4 的「不得由 leg 名称反推」就无法落地。现状：

- `service.py:1280 _reconcile_own_legs` 只把 `leg["leg"]` 和 symbol 传给
  `executor.query_leg`；`live_hedge_executor.py:747` 据此二选一。路由没有入口。
- `service.py:2181` 由 leg 名反推 endpoint 写进 `hedge_open_raw_response`。

**建议（明确写进计划）：`hedge_open_leg.endpoint` 列是查单与原始响应记录的唯一权威**，
与既有 `service.py:48 _leg_query_symbol` 的纪律一致——那里已经刻意用 leg 自身持久化的
`request_shape.symbol`，而不是任务级快照。这样做还有两个好处：既不需要迁移（该列已是
`TEXT NOT NULL`），也天然免疫「同一任务两次 attempt 路由翻转」——`store.py:752-758`
的 in-flight 保证同一任务同时只有一个未结 pair，历史腿始终带着自己那次的 endpoint。

### P1-4 资金前置条件从未言明，该路径交付即处于静默失效态

经典现货钱包**默认是空的**——整个系统从未使用过它，而资金划转是本轮明确的非目标。
于是 §3.5 的「余额不足 → 零 attempt、零 POST」会是**默认结果**：功能上线后对每一个
bStock / 触顶任务都静默不发单，直到有人手工往现货钱包充 USDT。

计划全文没有一句话告诉操作者这件事，§7 也没有任何一条验收覆盖它。

**要求：** 在 §1 或 §3 写明这一运行前置条件；§7 增加一条「余额为零时的行为与
操作者可见的原因文案」验收。

---

## 3. P2 — 应处理，不单独阻塞

- **P2-1 `openLongRestrictedAsset` 被完全忽略。** 它与 `maxCollateralExceededAsset`
  在同一个响应体里，属同一限制家族。至少应**整体留存**原始响应，并在 §1 非目标里
  写明「本轮只按 `maxCollateralExceededAsset` 路由」及理由（本轮现货腿是
  `NO_SIDE_EFFECT` 不借币，与「开多受限」是否相关未经验证）。不写理由就是隐式遗漏。
- **P2-2 下单限频闸门是 PM 域的，不覆盖新路径。** 预检读的是
  `GET /papi/v1/rateLimit/order`（`hedge_open_live_client.py:277`），
  `/api/v3/order` 受现货账户自己的下单限额约束。`PROJECT_STATE.md` 的
  「≤5 个任务并发 / 每任务 4 req/s vs ~20/s 预算」也是按单 host 推的。
  计划 §3.3 笼统写「读取 PAPI 所需的既有账户事实（……限频……）」，对 regular_spot 是错的。
- **P2-3 新增了一个全局单点故障。** §3 步骤 4 对**每一次**开单强制读 restricted-asset，
  包括本来完全走 papi_margin 的普通币。sapi 故障或 api.binance.com 的 IP 权重封禁
  会停掉**所有**开单。这个 fail-closed 取舍是可辩护的（换来的是不再裸空），但计划把它
  当成显然正确直接略过了；它扩大了本轮的影响半径，应显式写明并由 Human 认可。
- **P2-4 错误码的 product 标签。** `live_hedge_executor.py:385`
  `product = D.PRODUCT_MARGIN if leg == "spot" else D.PRODUCT_UM`。
  今天行为无害——现货 API 的负数码由 `classify_exchange_code` 的 shared 层
  product-agnostic 处理，而 `MARGIN_BUSINESS_CODES` 只有 51169 一条。但把 regular_spot
  标成 `margin` 语义上是错的，且会把 51169 规则挂到一个不可能返回它的端点上。
  计划的字段清单里没有这一项。
- **P2-5 §4 的表没有 host 列。** `ALLOWLIST`（`hedge_open_live_client.py:57-65`）
  是 deny-by-default 的安全面，host 硬绑定且不可由调用方提供。新增
  `api.binance.com` 条目应在 §4 表中显式列出，§7 增加一条 allowlist/host 断言。
- **P2-6 §5 建议补一句消歧。** 51169 暂停后由人工恢复、下一个 pair 用**全新 client ID**
  经**全新预检**合法地路由到 regular_spot——这**不是**被禁止的「自动补腿」。
  现在的行文容易让实现者把两者混为一谈而过度收紧。

---

## 4. 逐条回答 §8 的六个评审问题

**Q1 「普通现货降级仅限正费率 BUY」是否是防止售出非策略库存的充分最小边界？**
作为**开单路径**的边界：是，理由也成立（普通现货不借币，自动 SELL 会处置与策略无关的
既有库存）。作为**系统**边界：不充分——它会造出未来平单能力平不掉的仓位（P1-1）。
边界本身不用改，但必须把这个前向负债写出来并入 `PROJECT_STATE.md`。

**Q2 `restricted-asset` 的成功/失败语义是否足以支撑「命中则普通、读取失败则不发单」？**
「读取失败 → 不发单」这一半：充分且正确。
「命中 → 普通」这一半：**尚不充分**。端点确实存在且很便宜（权重 1、IP 维度），但计划对它的
性质描述有两处错误（非签名、非账户级），且该端点**从未被读过一次**，命中与 51169 的对应
关系仍是推论（P0-1）。补一次只读侦察即可，这一步上一 stage 已经写好要求了。

**Q3 route、endpoint、symbol、实际 base asset 是否贯穿了全链路？**
**部分。** 计划点到了正确的接缝，载体也确实无需迁移（已核实）。但缺了两样：
一是**查单时从哪里读回路由**没有定（P1-3）；二是错误码 product 标签不在字段清单里（P2-4）。

**Q4 是否存在任一路径会把普通现货的余额/订单/成交误归为统一账户？**
**是，存在一条计划没有覆盖的。** 不在下单或查单路径上，而在**持仓展示**：既有的
经典现货读取会开始看见 regular_spot 的现货腿，并与无关库存混在一起（P1-2）。
下单/查单路径本身，只要按 P1-3 把 leg 行的 endpoint 定为权威，就能守住。

**Q5 `51169` 延后补腿的非目标是否足够明确？**
**是**，§5 的红线画得很干净（等待被拒 leg 的确定性结论、全新 client ID、逐一处理
已成交/部分成交/未知的合约腿、不得伪装成同一条 leg）。建议补 P2-6 的消歧句，
以免实现者把「人工恢复后的全新预检路由」误当成被禁止的行为。

**Q6 是否遗漏了会改变合约腿 PAPI 行为、开单闸门或历史订单查询的兼容性风险？**
合约腿的 PAPI 行为与历史订单查询：计划守住了（历史缺字段回退 `papi_margin` 是对的）。
但遗漏了三项系统级兼容风险：**API key 现货权限缺失会造裸空（P0-2）**、
**下单限频闸门不覆盖新路径（P2-2）**、**restricted-asset 成为所有开单的新单点故障（P2-3）**。

---

## 5. 返工要求（可执行）

1. 先做一次只读侦察，落盘 `GET /sapi/v1/margin/restricted-asset` 的完整原始响应到
   `reports/api-samples/<stage>/`；据此改写 §2.2、§3.4 的事实陈述（含权限类型、
   平台级语义、两个数组、bStock base asset 是否出现）。—— P0-1
2. §3.5 增加现货交易权限校验，复用已在读的 `GET /api/v3/account` 的
   `canTrade`/`permissions`，不通过即 `preflight_incomplete`；§7 增加对应验收项。—— P0-2
3. §1 增写平单前向负债，并同步 `PROJECT_STATE.md`。—— P1-1
4. §2.5 改写为「本轮改变了既有展示限制 B 的成立方向」，同步 `PROJECT_STATE.md` 限制 B。—— P1-2
5. §3 明确「`hedge_open_leg.endpoint` 是查单与原始响应记录的唯一权威载体」，
   与 `service.py:48` 的既有纪律一致。—— P1-3
6. §1/§3 写明「经典现货钱包需人工预先充值」这一运行前置条件；§7 增加零余额行为验收。—— P1-4
7. 处理 P2-1 ~ P2-6（多为补一句理由或补一条验收，不改变设计主线）。

修订后重新提交一次独立跨 provider 计划评审。任何评审都不授权实盘开闸或使用真实凭证。
