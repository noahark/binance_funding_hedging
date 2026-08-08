# 现货下单账户路由 + 抵押额度展示 v1（待独立方案评审）

状态：草稿，2026-08-02。本文是后续实现的唯一详细说明；尚未授权改动、开闸、使用凭证或发单。

> **状态（2026-08-08）：该 stage（`2026-08-02-spot-order-routing-cap-display-v1`）已交付
> 并归档**，下单路由经实盘检验（含 COOKIEUSDT 单腿事故及其修复链）；证据见
> `archive/2026-08-02-spot-order-routing-cap-display-v1`，行为权威为
> `docs/api/public-market-contract.md`。正文定格在设计时，后续已被两处有意超越——
> **读正文前先看 `PROJECT_STATE.md`**：
> - §3 步骤 1 的现货 pair 解析机制已被 `SPOT_SYMBOL_MAP` 纯表取代
>   （`backend/domain/normalize.py:111`，2026-08-07）；
> - §6.4「预检必须每次自己新读」已被 task 05 的「预检读本地缓存（陈旧上限内）+
>   超龄/缺失实时重读」调整（stage `2026-08-06-hedge-order-close-validation` 及 `8ee6d3c`）。

修订史：

- 初稿（Planner）→ Opus5 计划评审 REWORK（12 项发现）
- 修订二稿（Planner，纳入 `restricted-asset` 真实侦察）→ Opus5 计划评审 r2 REWORK（10 项闭环，1 项阻塞）
- **本稿（2026-08-02，作者 Opus5）**：落实 Human 在
  `docs/planning/2026-08-02-decisions-routing-and-cap-display.md` 中的全部裁定，
  并合入"抵押额度已满上行情页"提案。
- **Bookkeeper 直接修订（2026-08-03，Human 明确授权）**：仅落实 DeepSeek `plan-review-1`
  已确认的两项 in-range 修复；原始回执见
  `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-1.deepseek.raw.md`。
- **Bookkeeper 接口裁定修订（2026-08-03，Human 明确授权）**：落实决策记录 §E-4 的展示失败、
  不适用与 SnapshotService 只读 client 边界；须经窄范围独立复核后才进入实现。

**作者身份提示：本稿由 Opus5 落笔，Opus5 因此不再具备本方案独立评审资格
（AGENTS.md §3.4）。后续的跨 provider 计划评审必须由其他 provider 执行。**

基线：`main` @ `1a55781`。

---

## 1. 目标与边界

策略的合约腿始终使用 Binance Portfolio Margin（PAPI）UM 接口。**正费率方向**的现货腿优先
使用 PAPI 全仓杠杆；已知不应使用 PAPI 的 bStock，或资产出现在 Binance 平台级"最大抵押额度
已满"名单时，改用普通现货账户。**负费率方向**始终保留既有 PAPI 路径，不读取该名单。

本轮是**一个 stage**，包含两个联动部分：

- **A · 下单路由**：使发单前已确定为普通现货的路径，从预检、提交、查单到审计闭环。
  只适用于正费率方向：普通现货 `BUY` + PAPI UM `SELL`。
- **B · 行情页展示**：把同一份"抵押额度已满"名单提到费率行情页，让操作者在**建任务之前**
  就看得见这个币会走哪条资金路径。

两部分共用同一数据源与同一条资产匹配规则，接缝本身即风险所在，故合并评审（见 §7）。

### 1.1 覆盖规模（不是边缘情形）

2026-08-02 实测（证据见 §2.2）：

| 量 | 值 |
| --- | --- |
| `maxCollateralExceededAsset` 名单规模 | 121 |
| 币安 `TRADING` 状态的 USDT 永续 | 679 |
| 其 base asset 命中该名单 | **114** |
| 占可交易全集 | **16.8%** |

命中含 `LINK`、`UNI`、`CAKE`、`COMP`、`VET`、`WBTC`、`FLOW`、`KAVA`、`ZRX`、`ETHFI`、
`GMX`、`ROSE`、`MANTA`、`ALT`、`BOME`、`PEOPLE` 等主流标的（`NOM` 亦在其中，
与 2026-07-28 事故对上），另加全部 bStock。

**约每六个可交易标的就有一个走普通现货路径。**因此 §2.7 的资金前置条件不是罕见兜底，
而是常态运维负担；本方案的取舍应在这个量级下评估，而非按"少数 bStock 加偶发触顶"评估。

### 1.2 不在本轮

- PAPI 现货订单已收到 `51169` 后，自动再发普通现货补腿；该能力必须在单独阶段处理
  已成交合约腿、全新 client ID、查单真相和暴露恢复，不能复用被拒 PAPI leg。
- 普通现货 `SELL` 降级。普通现货不借币，自动 SELL 可能卖出与策略无关的既有库存；
  反向方向继续走既有 PAPI 路径。
- 平仓能力。普通现货开出的现货腿会在未来平仓阶段按其已保存的实际 route 另行设计；
  本轮不设计、实现或验证平仓。
- **API key 交易权限的运行时探测。**Human 已裁定线上 API key、IP 白名单和账户权限是
  固定配置（依据与残余风险见 §2.6）；本轮不在每次下单前读取 `apiRestrictions`，
  也不把 `/api/v3/account.permissions` 的文字值当作 API key 权限闸门——该字段是
  账户级而非 key 级，且币安以 `TRD_GRP_*` 顶替 `SPOT` 字面值，字面匹配不可靠。
- **任何一致性检测或自动补救。**普通现货钱包与策略记录对不上时，本轮不检测、不告警、
  不补救（见 §2.5）。
- 接入 `/sapi/v1/margin/allPairs` 与 `/sapi/v1/margin/allAssets`。现有公开字段
  `isMarginTradingAllowed` 已能回答"支不支持全仓"；剩余缺口是"能不能借到、借得到多少"，
  那需要账户级签名接口，不在本轮。**后果：`negative_funding_status` 仍对全部可交易行停在
  `PRIVATE_BORROW_VALIDATION_REQUIRED`，本轮不改善借贷状态列。**
- `openLongRestrictedAsset`：不校验、不存储、不参与路由、预检或错误判断。
- 资金划转、借币、还币、订单闸门变更、实盘验证。
- 用未经证实的通用规则解释或自动处理 PAPI `51146`。当前已知 bStock 情形由产品类别
  前置路由规避；其他 symbol 的 `51146` 仍保留原始响应供后续取证。

---

## 2. 已知事实与设计后果

1. 当前真实下单、查单与 attempt endpoint 都硬编码为 PAPI margin
   （`hedge_open_tasks/domain.py:569-570`，写入点 `store.py:795/812`，
   原始响应记录 `service.py:2181` 由 leg 名反推）。普通现货不能只替换 POST，
   超时/异常后的查单与原始响应 endpoint 也必须跟随实际账户路径。

2. **`GET /sapi/v1/margin/restricted-asset` 的实测性质**（原始证据：
   `reports/api-samples/2026-08-spot-order-routing-v1/restricted-asset.raw.json`，
   2026-08-02 12:51:35Z）：

   | 项 | 实测值 |
   | --- | --- |
   | 类型 | 平台级 `MARKET_DATA` |
   | 鉴权 | 只带 `X-MBX-APIKEY`；**不签名**、无 `timestamp`/`recvWindow`、无参数 |
   | 权重 | 1（IP 维度，响应头 `x-sapi-used-ip-weight-1m: 1`） |
   | 响应 | `{"openLongRestrictedAsset": [], "maxCollateralExceededAsset": [...121 项]}` |
   | 账户绑定 | 无——同一结果对所有用户相同 |

   它是**时变的平台状态**，不能永久写入公共市场快照为"可用"或"不支持"的静态事实。

3. bStock 的合约与现货 symbol 不同。例如 `TSLAUSDT` 的现货为 `TSLABUSDT`。
   普通现货余额和限制名单必须使用**已解析现货 pair 的 base asset `TSLAB`**，
   不能从合约 symbol 推出 `TSLA`。
   已核实：名单 121 项**全部**存在于现货 `baseAsset` 全集（含 `1000CHEEMS` 与中文名资产
   `币安人生`），故命名口径与现货 base 同域，精确匹配即可，无需换算。

4. PAPI 的 `crossMarginFree` 不能用于判断普通现货账户可购买数量。
   普通路径需要一份同一预检周期内的、直接读取的标准 Spot account 余额。

5. **普通现货钱包的账面归属。**本轮 regular_spot 会让经典现货余额开始承载一部分策略仓位，
   同时它也可能混入非策略库存。

   本轮的处理是：**假设普通现货钱包只承载策略仓位。不实现任何一致性检测、告警或补救。**
   若出现账面对不上的情况，由 Human 观察后再决定是否需要处理。

   不作出"发现不一致即作为异常处理"这类承诺——`PROJECT_STATE.md` 已记录该观察面的
   三处失效（限制 B 漂移标记 *permanently inert*、限制 A 单腿标记条件过窄、
   F4 读不到账户仍谎报"交易所无仓"），把新规矩挂在坏仪表上只会产生虚假保障。
   本轮不修改展示语义。

6. **已接受的固定环境前提（Human 裁定）。**部署使用的 API key 已由 Human 配置 PAPI 与
   普通现货交易权限，且运行 IP 与账户权限不变。本轮不在运行时验证此项。

   **该前提破裂时的实际表现（必须让操作者事先知道）：**

   1. `/api/v3/order` 返回 `-2015`；
   2. `domain.py:362` 将 `-2015` 归入 auth 层 →
      `live_hedge_executor.py:388-392` 判为 `LEG_UNKNOWN_QUERYING`；
   3. **与此同时合约腿 SELL 已成交**（`live_hedge_executor.py:713-721` 两腿并发）；
   4. 查单同样 `-2015` → 10 次重试耗尽 → `SIGNAL_ORDER_STATE_UNKNOWN` → 任务暂停。

   **操作者看到的是「订单状态未知，去交易所核实」，而不是「权限问题」，同时账上有一条裸空。**

   变更 key、IP 白名单或账户权限前，必须重新评审该决定。

7. 普通现货钱包不会由本轮自动充值。运行前，操作者须手工准备普通现货 USDT；
   余额不足必须成为可见的预检原因，不能静默为"没有机会"。
   按 §1.1 的规模，这是常态负担而非偶发兜底。

---

## 3. 路由决策（唯一详细定义）

预检顺序如下；任一步无法读到所需事实，本次不创建 attempt、不提交任一腿。

1. 解析可交易的现货 pair：普通币精确匹配；`TRADIFI_PERPETUAL` 按既有 B-suffix 规则
   解析 bStock pair。
2. 从解析后的 pair 得到 `spot_symbol` 与 `spot_base_asset`。
3. 读取 PAPI 所需的既有账户事实（仓位模式、PAPI 下单限频、余额等）和公共过滤器/价格。
4. 由策略方向得出现货腿动作。若为负费率方向（现货 `SELL`），**不读取**
   `restricted-asset`，也**不选择** `regular_spot`；即使命中名单或为 bStock，仍保留既有
   `papi_margin` 路径，理由 `papi_default`，然后执行步骤 6。普通现货仅可用于正费率方向的
   现货 `BUY`。仅正费率方向**新鲜**读取平台级
   `GET /sapi/v1/margin/restricted-asset`，只带 `X-MBX-APIKEY`、不签名：
   - 若 `spot_base_asset` 在 `maxCollateralExceededAsset` → `regular_spot`，
     理由 `collateral_cap_precheck`；
   - 否则，若合约类别是 `TRADIFI_PERPETUAL` → `regular_spot`，理由 `tradifi_regular_spot`；
   - 否则 → `papi_margin`，理由 `papi_default`。

   未命中名单**只表示本次未观察到"平台额度已满"**，不表示 PAPI 现货一定可提交或
   不会返回 `51169`。
5. 选择 `regular_spot` 时，读取完整的标准 Spot account 余额快照，并读取其**标准 Spot
   下单限频**事实；用其中的可用 USDT 校验正费率 BUY 所需数量。余额不足、现货限频读数失败
   或其他所需账户读数失败时，不创建 attempt、不提交任一腿，并记录可区分"普通现货余额不足"
   与"限频/读取失败"的明确预检原因。
6. 选择 `papi_margin` 时，保留既有 PAPI 现货余额和数量校验。

正费率方向的 `restricted-asset` 读取失败、API-key 失败、限频、非预期结构或遗漏所需账户
读数，统一视为 `preflight_incomplete`。不得因读取失败猜测为普通现货或 PAPI 路径。

**这扩大了正费率开单对 `api.binance.com` 的依赖范围**：本来正费率纯走 papi_margin 的
普通币，现在也必须先读到该名单才能发单；负费率方向不增加这项读取。Human 接受此
fail-closed 取舍，以换取额度已满时不先发 PAPI 现货腿（后者会造成合约腿成交、现货腿被拒的
裸空）。

**§3 步骤 4 内的限制名单读取必须是本次预检周期内的新鲜读取，不得复用 §6 展示层的缓存**——
理由见 §6.4。

本次预检的不可变记录至少包含：

```text
spot_symbol
spot_base_asset
spot_order_route: papi_margin | regular_spot
spot_route_reason: papi_default | tradifi_regular_spot | collateral_cap_precheck
spot_endpoint
```

历史 attempt 缺少这些字段时，查询行为兼容为既有 `papi_margin`。

---

## 4. 执行和可追溯性

| Leg / route | Host | POST | 按 client ID 的 GET | 请求差异 |
| --- | --- | --- | --- | --- |
| PAPI 现货 | `papi.binance.com` | `/papi/v1/margin/order` | `/papi/v1/margin/order` | 保留 `sideEffectType=NO_SIDE_EFFECT` |
| 普通现货 | `api.binance.com` | `/api/v3/order` | `/api/v3/order` | 不发送 `sideEffectType` |
| 合约 | `papi.binance.com` | `/papi/v1/um/order` | `/papi/v1/um/order` | 现有合约参数不变 |

- 两腿只在上述预检完全成功后并发提交；普通现货不会改变合约腿账户或 endpoint。
- **`hedge_open_leg.endpoint` 是查单与原始 POST/GET 响应记录的唯一权威**；
  请求 shape 保存 symbol。后台 reconciliation 必须从该 leg 行读取 endpoint 与 symbol，
  **绝不得由 leg 名称或任务级 route 反推**。
  （该列已是 `TEXT NOT NULL`，逐腿一行；与既有 `service.py:48 _leg_query_symbol`
  用 leg 自身 `request_shape` 而非任务级快照的纪律一致。）
- 任何 POST 超时、5xx、格式异常响应仍遵循"先按本 leg 实际 endpoint 和 client ID 查询，
  绝不盲重发"。
- 普通现货市场订单沿用解析后的现货 filters、数量网格和最小名义金额校验；
  本策略为市价单，本轮无需新增限价 tick-size 决策。
- 普通现货 leg 使用独立的 `PRODUCT_SPOT` 错误分类；不得继承 margin 的产品专属
  `51169` 规则（现状 `live_hedge_executor.py:385` 为 `PRODUCT_MARGIN if leg == "spot"`）。
- `api.binance.com` 的普通现货下单、查单、账户与限频 endpoint 加入 deny-by-default
  allowlist，host 硬绑定、不得由调用方输入。**精确条目仅为以下五项，且都硬绑定
  `https://api.binance.com`：**

  ```text
  ("GET",  "/sapi/v1/margin/restricted-asset")
  ("POST", "/api/v3/order")
  ("GET",  "/api/v3/order")
  ("GET",  "/api/v3/account")
  ("GET",  "/api/v3/rateLimit/order")
  ```

  `restricted-asset` 的正费率预检读取和 §6 的展示读取都通过该 allowlist；未登记路径由
  client 拒绝，不能以直接请求或可配置 host 绕过。

---

## 5. `51169` 的本轮行为与后续接口

若 PAPI 现货路径在发单后确定收到 `51169`，本轮维持当前行为：保存原始响应、任务暂停、
不得自动向普通现货再发订单。`maxCollateralExceededAsset` 未命中不能证明容量充足，
仍可能发生这一动态竞态。

下一阶段的"51169 普通现货补腿"至少应新增独立、可审计的恢复状态；它必须等待被拒 PAPI leg
的确定性结论，并针对已成交/部分成交/未知的合约腿逐一处理。该阶段不得把普通现货 POST
伪装为同一个已拒 PAPI spot leg，也不得重用其 client ID。

本轮的人工恢复不受上述禁止自动补腿的限制：任务暂停后，操作者手动恢复时会以全新 client ID
和全新预检开始下一 pair；该预检可以合法选择 `regular_spot`。这不是在失败 attempt 内自动补单。

---

## 6. 行情页「抵押额度已满」展示

### 6.1 目的

现在的流程是反的：操作者先挑币、建任务，预检跑完才知道这个币要走另一套资金路径。
按 §1.1，16.8% 的标的会撞上这件事。本节让它在**建任务之前**就可见。

### 6.2 数据来源与刷新

同 §2.2 的 `GET /sapi/v1/margin/restricted-asset`：平台级、无参数、不签名、权重 1，
**一次调用覆盖全市场**（不是每币一次）——天生适合缓存。

- 挂进 `snapshot_service.py` 已有的三档业务缓存节奏
  （stage `2026-07-cache-refresh-scheduler-v2`）之一。名单变化是小时到天量级。
- **不新起调度器**：无独立生命周期，不新增结构（AGENTS.md §2）。
- SnapshotService 负责这条展示读取与缓存。它使用已有 hedge API key 的 exact-allowlist 只读
  client；该 client 在应用组合根创建，独立于 `APP_HEDGE_EXECUTOR` 与 private channel 开关。
  这不改变下单 Start gate，SnapshotService 也不得调用订单端点。

### 6.3 三态与字段

**对有可解析现货腿的行必须是三态，"读不到"绝不可渲染为"没满"。**

| 态 | 含义 | 渲染 |
| --- | --- | --- |
| 已满 | 本次读取命中名单 | 高亮标记 |
| 未满 | 本次读取成功且未命中 | 常态 + **截至时间** |
| **未知** | 读取失败（网络、限频、**鉴权失败**） | 明确的"未知"，不得等同于"未满" |

若某行没有可解析的可交易现货腿，则为**不适用**：不显示额度徽标，也绝不称为"未满"。它不属于
上述三态，因为没有可用于匹配的现货 base asset。

本项目已两次栽在"展示断言它并不知道的事"上（`PROJECT_STATE.md` 的 F4：账户读不到时
仍显示「交易所无仓」）。同样的错误在这里就是：接口挂了 → 界面显示"额度正常" →
操作者放心下单 → 撞 `51169`。

刷新时间戳必须露出——名单是时变的。
另：未命中**只表示未观察到额度已满**，不表示 PAPI 现货可用（与 §3 步骤 4 同一口径）。
**每次展示刷新失败都必须输出未知，即使内部保留上次成功值供下一次重试；不得把 last-good
输出为当前的已满或未满。**

**字段与渲染位置：**

| 层 | 方案 |
| --- | --- |
| 数据 | 新增独立块，如 `collateral_cap: { exceeded: true\|false\|null, checked_at }`。**不塞进 `margin_public`**——后者 `source` 现为 `"unverified"`，把已验证事实混入会使该块语义自相矛盾 |
| 标记 | `ui_flags` 加条目，沿用现有 `MARGIN_PUBLIC_UNVERIFIED` 的套路，前端按 flag 渲染 |
| 高亮 | 打在**资产**上——抵押额度是资产的属性，不是某条借贷路线的属性。**不按费率正负过滤**：任一行的解析后现货 base asset 命中名单即高亮；费率方向只影响 §3 的下单路由 |
| **不放** | **不进 `negative_funding_status`（借贷状态）列**。该列描述负费率方向（借币做空现货能否成立），抵押额度卡的是正费率方向（买现货进杠杆账户）；混在一列，操作者分不清提示在说买还是说卖 |

### 6.4 硬边界：展示缓存绝不能喂给下单预检

展示读缓存（可以是几分钟前的）；**§3 步骤 4 的预检必须每次自己新读一遍。**

若以"同一个接口，复用缓存省一次调用"为由打通两者，则一个三分钟前刚被打满的币会被判走
PAPI → 合约腿成交、现货腿被拒 → **裸空**。

方案 §8 已有"不得复用仪表盘的缓存余额作为开单预检"，本数据同此纪律。

### 6.5 共用规则，不共用数据

本 stage 合并的核心工程要求：

| 必须共用 | 必须隔离 |
| --- | --- |
| **解析现货 base asset 的规则**（普通币精确匹配、bStock 走 B-suffix 得 `TSLAB`）——实现为**一处**纯函数，§3 预检路由与 §6 展示标记都调它 | **缓存数据本身**（见 §6.4） |

同一条匹配规则写两遍必然漂移，项目已在 `2026-07-hedge-open-live-v1` 一轮内抓修过三次
跨 seam 漂移。这正是本 stage 不拆分的理由。

---

## 7. 公共快照契约变更

### 7.1 解除 no-key 限制（Human 裁定）

`docs/api/public-market-contract.md:85` 现文：

> `/sapi/v1/margin/allPairs` … require an API key … **Phase 1 forbids keys**, so they
> are not used.

`restricted-asset` 同属需要 key 的一类。**Human 裁定该限制解除。**
它本就是阶段性范围约束而非安全不变量：key 只在后端使用，浏览器从不直接调用币安（契约已明载）。

**替换为三条闸门，而非直接删除**（删禁令不换规则是范围悄悄扩张的口子）：

1. 允许在后端使用带 key 的接口；浏览器仍然从不直接调用币安。
2. **默认只限 `MARKET_DATA` 类**——带 key、不签名、平台级、无账户绑定。
   这保住一个要紧的不变量：**公共快照永远不承载账户数据**。
   将来若要接签名的 `USER_DATA` 接口（如账户级 `margin/available-inventory`），
   性质不同，须单独授权。
3. 每新增一个带 key 的数据源，须有 Human 显式授权并记录在该 stage 内。

### 7.2 须一并更正的文档真值

契约现把 `margin_public.source = "unverified"` 的**原因**写成"Phase 1 禁 key"。
限制解除后该原因失效；而本轮又不接 `allPairs`（§1.2），故真实原因是**"本轮未采用"**
而非"被禁止"。原因文字须同步更正，否则契约陈述一个不成立的理由。

### 7.3 新增的失败模式

公共快照过去对凭证问题免疫（完全不带 key）。接入后，**key 失效、被撤、IP 白名单变化
都会让这次读取失败**——这正是 §6.3 第三态"未知"必须存在的另一个理由。

IP 权重方面无实质变化：现有公开读取与下单路径本就共用 `api.binance.com` 的同一 IP 预算，
本次只增加权重 1 的一次调用。

### 7.4 加字段走现成路径

契约的 amendment 段落已排到 `v0.8`（`2026-08-02-frontend-display-tweaks-v1`）。
本轮走同一形状：**契约 `v0.9` amendment 段落 + `schemas/api/public-market/snapshot.schema.json`
字段**。

---

## 8. 实现范围

**下单路由（A）：**

- `backend/hedge_open_tasks/domain.py`：路由和按账户选择的预检事实、`PRODUCT_SPOT`；
- `backend/services/hedge_preflight_provider.py`：新鲜读取限制名单、普通现货余额与限频、
  bStock 实际 base asset；
- `backend/services/hedge_open_live_client.py`：受限 allowlist 内的普通现货下单、查单、
  账户与限频 GET，以及 `restricted-asset` 读取。须将以下 exact `(method, path)` 条目
  全部硬绑定至 `https://api.binance.com`：

  ```text
  ("GET",  "/sapi/v1/margin/restricted-asset")
  ("POST", "/api/v3/order")
  ("GET",  "/api/v3/order")
  ("GET",  "/api/v3/account")
  ("GET",  "/api/v3/rateLimit/order")
  ```

  正费率预检和展示读取均使用该管控；不登记的路径必须被拒绝。
- `backend/services/live_hedge_executor.py`：按冻结路线选择 POST/GET 和参数形状；
- `backend/hedge_open_tasks/service.py`、`backend/hedge_open_tasks/store.py`：
  attempt 的真实 endpoint 与原始响应审计。

**行情页展示（B）：**

- `backend/domain/snapshot.py`、`backend/services/snapshot_service.py`：名单缓存、
  三态/不适用派生、行标记；`backend/app/server.py`：只读名单 client 的组合根注入（不改 Start gate）；
- `docs/api/public-market-contract.md`：§7 的闸门替换、真值更正、`v0.9` amendment；
- `schemas/api/public-market/snapshot.schema.json`：新字段；
- 前端渲染（资产高亮 + 截至时间 + 未知态）。

以上模块已有的单元/集成测试文件。

**不得**复用仪表盘的缓存余额作为开单预检；**不得**打通 §6 缓存与 §3 预检；
不新增数据库迁移——`hedge_open_attempt.preflight_fingerprint`（逐尝试 JSON）与
`hedge_open_leg.endpoint`（`TEXT NOT NULL`，逐腿）已足以承载尝试级记录。

> 注：初稿的"不新增公共市场 wire 字段"在本稿**不再成立**——B 部分明确要新增。

---

## 9. 验收检查

1. `TSLAUSDT` 正确解析 `TSLABUSDT`，限制名单和普通账户余额按 `TSLAB` 判断。
2. bStock 和限制名单命中的正费率任务，现货用 `/api/v3/order`，合约仍用 `/papi/v1/um/order`。
3. 普通现货请求不含 `sideEffectType`；PAPI 现货请求保留它。
4. 普通现货的 POST 不确定时，初始查询与后台 reconciliation 都走 `/api/v3/order`，
   且 endpoint 取自 leg 行而非 leg 名称或任务级 route。
5. 普通现货路径读取完整余额快照；普通现货 USDT 为零/不足、限制名单读取失败、
   普通账户或现货限频读取失败时，零 attempt、零 POST，并留下能区分
   "余额不足"与"限频/读取失败"的可见记录。
6. 未命中限制名单的非 bStock 保持 PAPI 现货路径；历史 PAPI attempt 仍按原路径查询。
7. PAPI 现货 `51169` 不产生任何普通现货补单。
8. `restricted-asset` 只带 API key、不签名；本轮只读取 `maxCollateralExceededAsset`。
   未命中不得被断言为"PAPI 可用"。
9. 普通现货使用独立错误产品、固定 `api.binance.com` allowlist 和自身限频读数；
   不得复用 margin 的 `51169` 分类或 PAPI 限频事实。
10. **展示三态**：命中 → 已满；成功未命中 → 未满 + 截至时间；读取失败（含鉴权失败）
    → 未知，且此前有 last-good 也不得继续显示为已满/未满。无可解析现货腿 → 不适用、无徽标。
    **未知与不适用均不得渲染为未满。**
11. **展示缓存与预检隔离**：存在一个测试证明 §3 预检不读 §6 缓存
    （例如缓存标记为已满而预检新读为未满时，路由按新读结果走）。
12. **匹配规则单点**：现货 base asset 解析只有一处实现，§3 与 §6 都调用它。
13. 契约与 schema：no-key 限制已按 §7.1 换成三条闸门（而非仅删除）；
    `margin_public.source` 的原因文字已按 §7.2 更正；`v0.9` amendment 段落齐备。
14. 所有验证使用 fake transport；不使用真实凭证、不改变 Start gate、不做实盘调用。
15. **负费率方向**即使命中限制名单或为 bStock，仍走既有 PAPI 现货路径，且 fake transport
    证明该方向不读取 `restricted-asset`、不选择 `regular_spot`。
16. deny-by-default allowlist 含 §4 所列五条、全部硬绑定 `api.binance.com`；预检与展示的
    `restricted-asset` 读取均经此管控，未登记路径调用被拒。
17. **展示高亮不按费率正负过滤**：任一行的解析后现货 base asset 命中名单即高亮；方向仅影响
    §3 下单路由，不影响 §6 展示。

---

## 10. 交给独立评审的问题

**评审者不得为 Opus5**（本稿作者，见文首身份提示）。

1. "普通现货降级仅限正费率 BUY"是否是防止售出非策略库存的充分最小边界？
2. `restricted-asset` 是否被正确限定为"平台额度已满的单向分流信号"，
   而非 PAPI 支持或容量充足证明？将它作为全局 fail-closed 依赖的取舍，
   在 §1.1 的 16.8% 规模下是否仍可接受？
3. route、endpoint、symbol 和实际 base asset 是否贯穿预检、持久化、提交、查单、
   原始响应及后台 reconciliation？
4. §6.4 / §6.5 的"共用规则、不共用数据"边界是否足够明确，能防止实现期把展示缓存
   接进下单预检？
5. `51169` 延后补腿的非目标是否足够明确，能防止本轮隐式重发或产生未审计补单？
6. §2.6 的固定环境前提：其残余裸空风险、适用条件、破裂时的实际表现与重新评审触发条件，
   是否已记录到可供操作者据以行动的程度？
7. §7.1 的三条闸门是否足以替代被解除的 no-key 限制，防止后续 stage 的范围悄悄扩张？

---

## 11. 风险与下一步

这是订单路由变更叠加公共契约变更，属 **`HIGH_RISK`**（AGENTS.md §8）。
展示部分不因"只读"而单独降级——它与下单路由同属一个 stage，且是可能误导交易决策的展示面。

独立、跨 provider 的方案评审 ACCEPT 后，才可由 Human 建立正式 implementer dispatch；
实现后的交付仍须按固定 `base_sha..delivery_sha` 进行 review-1 与 review-2。
任何评审均不授权实盘开闸或使用真实凭证。

### 待 Bookkeeper 处理的两项记录收尾

以下两项属 Bookkeeper 域的产物，本稿作者未代为修改：

1. `reports/api-samples/2026-08-spot-order-routing-v1/spot-account-capability.json`
   现记 `blocker: true`（依据 `"SPOT" in permissions` 字面匹配）。该判定已被 §1.2 / §2.6
   的裁定推翻，须更正或加注，否则证据目录自相矛盾。
2. `PROJECT_STATE.md` 的 `[OPEN][ACCEPTED-CONFIGURATION-RISK]` 条目缺 AGENTS.md §8
   要求的"观察方式"要素，须补入 §2.6 所述的破裂表现链条。

**Bookkeeper completion note（2026-08-02）：**两项均已完成。原始
`spot-account-capability.json` 保持不改，其 `"SPOT"` 字面匹配 blocker 已由
`reports/api-samples/2026-08-spot-order-routing-v1/spot-account-capability.bookkeeper-note.json`
加注为 Human 的风险裁定，不再构成本阶段阻塞；`PROJECT_STATE.md` 已补入 §2.6 的
实际表现链条与人工观察规则。
