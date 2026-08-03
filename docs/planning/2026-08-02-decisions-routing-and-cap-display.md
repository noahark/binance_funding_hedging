# 决策记录 — 现货下单路由 v1 的裁定，及"抵押额度已满"上行情页的新提案

日期：2026-08-02
参与：Human（决策）、Opus5（计划评审）
基线：`main` @ `1a55781`（含刚合并的 `2026-08-02-frontend-display-tweaks-v1`）
用途：交 Codex 做独立评审的输入

## 0. 本文件的边界

本文只记录**决策**，不改方案正文。`docs/planning/spot-order-routing-v1.md` 的正文修改由
Planner 执行——Opus5 是该方案的评审者，若自行改写正文，下一轮就变成自己评审自己的交付
（AGENTS.md §3.4）。

关联文件：

- 方案正文：`docs/planning/spot-order-routing-v1.md`
- 评审 r1：`docs/planning/spot-order-routing-v1.review-opus5.md`（REWORK，12 项发现）
- 评审 r2：`docs/planning/spot-order-routing-v1.review-opus5-r2.md`（REWORK，10 项闭环）
- 侦察证据：`reports/api-samples/2026-08-spot-order-routing-v1/`

---

# A. 现货下单路由 v1 —— 对 r2 评审发现的裁定

## A-1 API key 现货交易权限：Human 裁定不做运行时探测【已定】

**评审发现（r2 P0-A）**：`spot-account-capability.json` 实测
`has_SPOT_permission: false` / `blocker: true`，与方案 §2.6「已配好权限」的前提矛盾；
评审建议补一次 `GET /sapi/v1/account/apiRestrictions` 消解歧义。

**Human 裁定：不追，维持不做运行时权限探测。** 理由：

1. `/api/v3/account.permissions` 是**账户级**，不是 **API key 级**，本就不能当密钥权限闸门；
2. 实测拿到 `TRD_GRP_236`，币安对部分账户用 `TRD_GRP_*` 顶替 `SPOT` 字面值，
   `has_SPOT_permission: false` 大概率是**字面匹配造成的虚惊**；
3. 为一个大概率虚惊的信号增加运行时探测不划算，Human 有权做此风险裁定
   （AGENTS.md §10）。

**评审方立场**：接受该裁定，不再重提。上一轮评审称「复用该响应即零成本完整修法」
是评审方说过头了——该字段覆盖不到 key 级，Planner 的技术反驳成立。

**仍需执行（记录完整性，非重开争议）：**

| 项 | 动作 |
|---|---|
| A-1-a | 更正 `spot-account-capability.json`：`blocker: true` 改掉或加注「该判定基于 `"SPOT" in permissions` 字面匹配，已知 `TRD_GRP_*` 会顶替 SPOT；Human 裁定不作为阻塞」。**不改则证据目录自相矛盾，下一位评审者必然重新提出。** |
| A-1-b | `PROJECT_STATE.md` 的 `[ACCEPTED-CONFIGURATION-RISK]` 条目补「观察方式」要素（AGENTS.md §8 要求接受记录含：问题事实／可能影响／接受理由／临时限制或观察方式／后续复看条件，现缺第四项）。 |

**A-1-b 的具体内容——前提破裂时系统的实际表现：**

1. `/api/v3/order` 返回 `-2015`；
2. `domain.py:362` 将 `-2015` 归入 auth 层 → `live_hedge_executor.py:388-392`
   判为 `LEG_UNKNOWN_QUERYING`；
3. 同时合约腿 SELL 已成交（`live_hedge_executor.py:713-721` 两腿并发）；
4. 查单同样 `-2015` → 10 次重试耗尽 → `SIGNAL_ORDER_STATE_UNKNOWN` → 任务暂停。

**操作者看到的是「订单状态未知，去交易所核实」，不是「权限问题」，同时账上有一条裸空。**
这句话必须进 §2.6 和 PROJECT_STATE 条目，否则接受的风险没有可观察的形态。

## A-2 §2.5 运行不变量：删掉检测承诺【已定】

**评审发现（r2 P2-A）**：§2.5 写「发现数量不一致即作为账户对冲异常由操作者观察和处理」，
但 PROJECT_STATE 已记录该观察面的三处失效（限制 B 漂移标记 *permanently inert*、
限制 A 单腿标记条件过窄、F4 读不到账户仍谎报「交易所无仓」）。等于把新规矩挂在坏仪表上。

**Human 裁定**：策略本身就是为对冲资金费率设计的，不应有其他敞口的币种进来影响仓位计算；
**本轮不做「发现对不上就当异常处理」，也不硬猜着实现补救**，先让 Human 观察实际会出现
什么样的对不上场景。

**要求 Planner 改写 §2.5 为：**

> 假设普通现货钱包只承载策略仓位。本轮不实现任何一致性检测、告警或补救；
> 若出现账面对不上的情况，由 Human 观察后再决定是否需要处理。

去掉「即作为账户对冲异常由操作者观察和处理」这类**没有执行者的承诺**。
评审方认为该裁定优于原评审要求：少一个无人看管的假仪表，比多一个好。

## A-3 `openLongRestrictedAsset` 存档：维持不存【已定】

**评审发现（r2 P2-C）**：项目自身对 `51146` 的纪律是「保留原始响应供后续取证」，
且该数组实测为空，整体留存成本≈0。

**Human 裁定**：无关紧要，后面用上了再说，大概率不会用。**维持 §3「不校验、不存储」。**
评审方接受，不再提。

## A-4 规模认知：16.8% 需写进方案【已定，待 Planner 执行】

**评审发现（r2 P1-A）**：方案通篇按"例外分支"行文，实测不支持该框架。

| 量 | 值 |
|---|---|
| `maxCollateralExceededAsset` 名单规模（2026-08-02 实测） | 121 |
| 币安 `TRADING` 状态的 USDT 永续 | 679 |
| 其 base asset 命中该名单 | **114** |
| 占可交易全集 | **16.8%** |

命中含 LINK、UNI、CAKE、COMP、VET、WBTC、FLOW、KAVA、ZRX、ETHFI、GMX、ROSE、
MANTA、ALT、BOME、PEOPLE 等主流标的（NOM 亦在其中，与 2026-07-28 事故对上），
另加全部 bStock。

**要求**：把该量级写进 §1/§2。不改设计，但 Human 的资金与运维取舍必须建立在
「约 1/6 可交易标的走这条路、资金长期分驻两个钱包」的认知上，而非「少数 bStock
加偶发触顶」。Human 已在本次讨论中知悉该数字。

## A-5 §7 验收清单编号损坏【已定，待 Planner 执行】

存在两个 `9.`（第 109、111 行），`10.`（第 110 行）夹在中间。
AGENTS.md §8 将「验收判据不清」列为 HIGH_RISK 触发条件之一。

另：第 111 条「不实现 API key 权限运行时检测」是一句"不做什么"的声明，
不是可验证检查项，应移至 §1 非目标。

## A-6 r2 中已闭环、无需再动的部分

r1 的 12 项发现中 10 项真闭环、1 项按决定收口。以下**不要在后续轮次里重开**：

平仓前向负债（§1）、路由回读权威载体（§4 第二条，写得比评审要求更准）、
现货钱包资金前置条件（§2.7 + §3.5 + §7.5）、限频闸门 PM 域问题（§3.5 + §4.6 + §7.9）、
全局单点故障的显式接受（§3）、错误码 `PRODUCT_SPOT`（§4.5）、
host 列与 allowlist 断言（§4 表 + §4.6 + §7.9）、51169 人工恢复消歧（§5 第三段）。

`restricted-asset` 的补证质量评审方评为范本：带响应头
`x-sapi-used-ip-weight-1m: 1`、`signed: false` 的请求形状、121 项完整响应体，
且 `NOM` 在名单内——把「命中即 51169」从推论变成有交叉验证的观察。

---

# B. 新提案 —— "抵押额度已满"上费率行情展示页

## B-1 提案与范围【Human 提出，已定范围】

**提案**：把 `restricted-asset` 的查询提到费率行情展示页，直接标记对应数据；
后端加接口定时查询更新缓存。

**评审方立场：赞成。** 理由：

1. 现在流程是反的——操作者先挑币、建任务，预检跑完才知道要走另一套资金路径；
   有 16.8% 的标的会撞上，提前标出来是实打实的决策价值。
2. 数据形状天生适合缓存：平台级、无参数、不签名、权重 1、**一次调用覆盖全市场**
   （不是每币一次）。

**范围裁定（Human）：只接 `restricted-asset`，不接 `allPairs` / `allAssets`。**
理由：现有公开数据够用，`isMarginTradingAllowed` 已经答出"支不支持全仓"，
为剩余边际信息多接两个接口不划算。

**评审方记录的残留**：跳过之后，`negative_funding_status` 仍会对全部可交易行停在
`PRIVATE_BORROW_VALIDATION_REQUIRED`——缺的那块是"能不能借到、借得到多少"，
而那本就需要账户级接口（`margin/available-inventory`，签名 + 权重 50）。
所以此取舍无实质损失，但**借贷状态列不会因本提案而变得有用**，不要对它有预期。

## B-2 契约的 no-key 限制：Human 裁定解除【已定】

`docs/api/public-market-contract.md:85` 现文：

> `/sapi/v1/margin/allPairs` … require an API key … **Phase 1 forbids keys**, so they
> are not used.

**Human 裁定：该限制解除。后续按需要，由 Human 逐个审核是否可以加入带 key 的数据源。**

裁定成立的依据：这条本来就是**阶段性范围约束**，不是安全不变量。key 只在后端使用，
浏览器从不直接调币安（契约已明载）；`restricted-asset` 是 `MARKET_DATA` 类
（带 key、不签名、平台级、无账户绑定、无参数、权重 1），不会把账户数据带进公共快照。

### 评审方建议：不要只删句子，要换成闸门

直接删掉禁令而不放替代规则，是范围悄悄扩张的典型路径。Human 的意图
（"后面按需审核"）需要写进契约本身，否则下一个 stage 无从判断该不该伸手。

建议把那句话替换为三条：

1. **允许**在后端使用带 key 的接口；浏览器仍然从不直接调用币安。
2. **默认只限 `MARKET_DATA` 类**——带 key 但不签名、平台级、无账户绑定。
   这条保住了一个要紧的不变量：**公共快照永远不承载账户数据**。
   若将来要接签名的 `USER_DATA` 接口（例如账户级的 `margin/available-inventory`），
   那是性质不同的一件事，须单独授权。
3. 每新增一个带 key 的数据源，**须有 Human 显式授权并记录在该 stage 内**。

### 顺带须修正的文档真值

契约现在把 `margin_public.source = "unverified"` 的**原因**写成"Phase 1 禁 key"。
限制解除后该原因失效——但本轮又裁定不接 `allPairs`（B-1），所以真实原因变成
**"本轮未采用"**而非"被禁止"。原因文字须同步更正，否则契约陈述一个不成立的理由。

### 加字段本身走现成路径

契约的 amendment 段落已排到 `v0.8`
（`2026-08-02-frontend-display-tweaks-v1`，新增
`private_account.balances_unified[].cross_margin_borrowed_value_usdt`）。
本提案走同一形状：**契约 `v0.9` amendment 段落 + snapshot schema 字段**——
刚跑通的常规动作，无需重新发明。

### 新增的一个失败模式

公共快照过去对凭证问题免疫（完全不带 key）。接入之后，**key 失效、被撤、IP 白名单变化
都会让这次读取失败**。这正是 B-3-2 的第三态"未知"必须存在的另一个理由：
它要覆盖的不只是网络故障，还有鉴权失败。绝不可退化成"未满"。

IP 权重方面无实质变化：现有公开读取与下单路径本就共用 `api.binance.com` 的同一 IP 预算，
本次只增加权重 1 的一次调用。

## B-3 三条必须守住的纪律【评审方要求，待 Planner 写入设计】

**B-3-1 展示缓存绝不能喂给下单预检。**
列表可以是几分钟前的；下单预检必须每次自己新读一遍（方案 §3 已如此规定）。
若有人以"同一个接口，复用缓存省一次调用"为由打通两者，则一个三分钟前刚被打满的币
会被判走 PAPI → 合约腿成交、现货腿被拒 → **裸空**。
方案 §6 已有「不得复用仪表盘的缓存余额作为开单预检」，本数据须原样再写一条。

**B-3-2 "读不到"必须是独立第三态，绝不可渲染为"没满"。**
本项目已两次栽在"展示断言它并不知道的事"上（PROJECT_STATE 的 F4：账户读不到时
仍显示「交易所无仓」）。同样的错误换个地方就是：接口挂了 → 界面显示"额度正常" →
操作者放心下单 → 撞 51169。
要求三态：**已满 / 未满（截至 HH:MM）/ 未知**，且刷新时间戳必须露出——名单是动态的。
另：未命中名单**只表示未观察到额度已满**，不表示 PAPI 现货可用
（与方案 §3.4、§7.8 及侦察 note 的 caveat 一致）。

**B-3-3 匹配必须用解析后的现货 base asset。**
实测核验：名单 121 项**全部**存在于现货 `baseAsset` 全集（含 `1000CHEEMS` 与
中文名资产 `币安人生`），命名口径干净，精确匹配即可。
但行模型顶层 `base_asset` 是**合约**的 base：bStock 的合约 base 是 `TSLA`、
现货是 `TSLAB`，必须用 `spot` 块解析出的 base 匹配。
这与下单路由 §2.3 是同一条纪律，两处须一致。

## B-4 放置建议【评审方建议，待 Human 确认】

**不建议放进「借贷状态」列。** 借贷状态描述的是**负费率方向**（借币做空现货能否成立），
抵押额度已满卡的是**正费率方向**（买现货进杠杆账户）。混在一列，操作者看一眼
分不清这个提示在说买还是说卖。

建议：

| 层 | 建议 |
|---|---|
| 数据 | **新增独立块**（如 `collateral_cap: { exceeded: true\|false\|null, checked_at }`），不塞进 `margin_public`——后者的 `source` 现为 `"unverified"`，把一个已验证事实混进去会让该块语义自相矛盾 |
| 标记 | `ui_flags` 加条目（沿用现有 `MARGIN_PUBLIC_UNVERIFIED` 的套路），前端按 flag 渲染 |
| 高亮 | 打在**资产**上——抵押额度是**资产的属性**，不是某条借贷路线的属性；Human 提出的这个位置是对的 |
| 若必须进状态列 | 放**正费率**那侧，不要进借贷状态列 |

## B-5 刷新机制建议【评审方建议】

**不要新起调度器。** `snapshot_service.py` 已有三档节奏的业务缓存
（stage `2026-07-cache-refresh-scheduler-v2`）；该名单变化是**小时到天**量级，
权重 1，挂进现有某一档即可。
AGENTS.md §2：没有独立生命周期就不新增结构。

## B-6 合并为一个 stage【Human 裁定】

**Human 裁定：行情页标记与下单路由做成一个 stage，不拆——本身就是联动的设计。**

评审方原建议拆分（展示只读、风险低、先上线还能观察名单变化频率）。
**Human 的理由更强，评审方撤回原建议**：两侧共用同一个数据源和同一条匹配规则，
而**接缝正是风险所在**，接缝要整体评审才有意义。项目已经吃过跨 seam 漂移的亏
（`2026-07-hedge-open-live-v1` 一轮内抓修三次）。若展示先落地为独立 stage，
B-3-1 那条"展示缓存不得喂预检"会变成一句没有对手方的空承诺。

### 由此产生的工程要求：共用规则，不共用数据

这是本裁定最重要的落地点，一个 stage 内最容易被揉混：

| 必须共用 | 必须隔离 |
|---|---|
| **解析现货 base asset 的那条规则**（B-3-3：普通币精确匹配、bStock 走 B-suffix 得 `TSLAB`）——实现为**一处**纯函数，预检路由与展示标记都调它 | **缓存数据本身**。展示读缓存（可以是几分钟前的）；预检每次自己新读。见 B-3-1：一旦打通，后果是裸空 |

一句话：**共用规则，不共用数据。**

### 由此产生的三个连带修改

1. **整个 stage 按 `HIGH_RISK` 走**（AGENTS.md §8）：含订单路由，需 review-1 + review-2。
   展示部分不因"只读"而单独降级。
2. **方案 §6 的「不新增公共市场 wire 字段」现在为假**，必须重写——本 stage 明确要新增。
3. **方案 §6 的文件范围须扩充**：`backend/domain/snapshot.py`、
   `backend/services/snapshot_service.py`、`docs/api/public-market-contract.md`、
   `schemas/api/public-market/snapshot.schema.json`、前端渲染，及对应测试。

---

# C. 待 Human 决定的遗留项

| # | 事项 | 评审方建议 |
|---|---|---|
| C-1 | ~~排期关系~~ | **已定：合并为一个 stage，见 B-6** |
| C-2 | B-4 的字段放置与高亮位置 | 见 B-4 表：数据放独立块、高亮打在资产上、不进借贷状态列 |
| C-3 | ~~行情页改动的风险分级~~ | **已定：合并后整个 stage 为 `HIGH_RISK`，见 B-6** |

---

# D. 给 Codex 评审的说明

**评审对象**：本决策记录 + `docs/planning/spot-order-routing-v1.md`（Planner 按 A 节修订后的版本）。

**已由 Human 裁定、不要重开的**：A-1（不做运行时权限探测）、A-2（不做一致性检测/补救）、
A-3（不存 `openLongRestrictedAsset`）、B-1 范围（只接 `restricted-asset`，不接
`allPairs`/`allAssets`）、B-2（解除 no-key 限制）、B-6（合并为一个 stage）。
这些是 Human 的风险与范围决定，不是遗漏。若认为某项裁定的**前提**有新证据不成立，
请指出该证据，而不是重述原论点。

**请重点看**：

1. A-1-a / A-1-b 是否已执行（证据目录自相矛盾、accepted-risk 缺观察方式）；
2. A-4、A-5 是否已落到方案正文；
3. **B-2 的解除方式**——是只删了禁令，还是换上了闸门（后端可用 key／默认限
   `MARKET_DATA` 类／每个新数据源需 Human 授权）？只删不换是范围扩张的口子。
   另：`margin_public.source = "unverified"` 的原因文字是否已从"被禁止"更正为"本轮未采用"；
4. B-3 三条纪律是否写进了设计，特别是 **B-3-1（展示缓存不得喂预检）**，
   这一条失守的后果是裸空；
5. **B-6 的「共用规则，不共用数据」**——现货 base asset 解析是否只有一处实现、
   两条路径都调它；缓存是否确实没有打通到预检；
6. 方案 §6 的「不新增公共市场 wire 字段」是否已改（合并后该句为假）、文件范围是否已扩充；
7. A-6 列出的已闭环项是否被无谓重开。

---

# E. Bookkeeper 记录的计划评审补充裁定（2026-08-02）

来源：Human 转交的 DeepSeek `plan-review-1` 原始评审回执，已原样封存于
`reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-1.deepseek.raw.md`。
以下两项为 Human 已定裁定，进入方案修订，不作为下一轮评审的未决问题。

## E-1 负费率方向不参与普通现货路由【已定】

负费率方向的现货腿为 `SELL`。该方向**不读取** `restricted-asset`，也**不选择**
`regular_spot`；即使命中名单或为 bStock，仍走既有 PAPI 路径。普通现货只可作为正费率
方向现货 `BUY` 的前置分流。平仓及普通现货 `SELL` 的设计留待以后。

## E-2 新端点保留 deny-by-default 管控【已定】

保留 `HedgeOpenLiveClient` 的 exact allowlist 与 host 硬绑定，不得为接入新路径而绕过它。
本轮须将下列 `(method, path)` 登记为 `https://api.binance.com`：

- `("GET", "/sapi/v1/margin/restricted-asset")`
- `("POST", "/api/v3/order")`
- `("GET", "/api/v3/order")`
- `("GET", "/api/v3/account")`
- `("GET", "/api/v3/rateLimit/order")`

预检读取与行情展示读取都必须受该 allowlist 管控，且调用方不能传入或覆盖 host。

## E-3 展示高亮不按费率方向过滤【已定】

命中 `maxCollateralExceededAsset` 的资产在行情页**一律高亮**，不因该行当前为正费率或负费率而
过滤。名单与高亮描述的是资产的抵押额度状态；费率方向只影响 §3 的下单路由。该裁定不改变
普通现货仅用于正费率 `BUY` 的边界，也不改变展示缓存与预检读取的隔离。

## E-4 接口细节的三项裁定【已定】

1. **展示刷新失败即未知。**不论此前是否有成功结果，只要本次名单读取失败，行情页发射并渲染
   「未知」；不得继续展示上次的已满/未满来掩盖本次失败。预检仍每次独立新读，不受展示状态影响。
2. **无可解析现货腿即不适用。**它不属于名单的已满/未满/未知三态，不显示额度徽标，也绝不称为
   「未满」。
3. **展示读取归 SnapshotService。**它使用已有 hedge API key 的、受 exact allowlist 和 host
   硬绑定保护的只读 client；client 在应用组合根创建，独立于 `APP_HEDGE_EXECUTOR` 与 private
   channel 开关。创建 client 不发请求、不改变 Start gate；SnapshotService 只可调用名单 GET，
   下单仍只由 live hedge executor 发起。
