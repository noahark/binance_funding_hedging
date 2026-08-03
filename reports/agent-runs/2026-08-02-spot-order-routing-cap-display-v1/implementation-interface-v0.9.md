# 实现前接口约定 — 公共快照 v0.9 `collateral_cap`

阶段：`2026-08-02-spot-order-routing-cap-display-v1`
作者：Opus5（Planner，task-breakdown-1）
日期：2026-08-03
基线：`main` @ `1a55781`

## 0. 本文地位

本文是 **实现输入**，不是对外权威。它把已获 DeepSeek `ACCEPT` 的方案
`docs/planning/spot-order-routing-v1.md` §6/§7 与决策记录 §B/§E 中已经定死的规则，收敛成
后端与前端在动手前必须一致同意的**精确 JSON 形状与渲染真值表**，使
`implementation-backend-2`（Claude-GLM）与 `implementation-frontend-1`（Grok）不必各自猜。

权威顺序（高到低）：

1. `AGENTS.md`
2. `docs/planning/spot-order-routing-v1.md` + `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（已 ACCEPT 的产品边界）
3. **后端交付写入的 `docs/api/public-market-contract.md` v0.9 amendment + `schemas/api/public-market/snapshot.schema.json`（对外最终权威）**
4. 本文

本文与第 2 层冲突时以第 2 层为准，并须停下上报，不得就地改写产品边界。本文的形状被后端
写进第 3 层之后，第 3 层即成为前端唯一可依赖的对外契约；本文不再是可引用的对外定义。

本文的接口级裁定以 Human 决策记录 §E-4 为准；§9 列出其落点与方案依据。

---

## 1. 数据源（单一）

| 项 | 值 |
| --- | --- |
| 端点 | `GET https://api.binance.com/sapi/v1/margin/restricted-asset` |
| 鉴权 | 只带 `X-MBX-APIKEY`，**不签名**，无 `timestamp`/`recvWindow`/参数 |
| 类型 | 平台级 `MARKET_DATA`，无账户绑定，一次调用覆盖全市场 |
| 权重 | 1（IP 维度） |
| 本轮读取的字段 | **仅** `maxCollateralExceededAsset`（字符串数组） |
| 明确不读不存 | `openLongRestrictedAsset`（决策 §A-3） |

同一端点在本 stage 有**两条互不相通的调用路径**：

- **展示路径**（§6）：SnapshotService 缓存，供行情页；
- **预检路径**（§3）：每次开单预检**新鲜读取**，不读缓存。

两条路径共用 allowlist 登记与同一条资产匹配规则，**不共用缓存数据**（§7 硬边界）。

---

## 2. `rows[].collateral_cap` 完整形状

新增**独立块**，与 `margin_public`、`negative_funding_status` **完全独立**：不塞进
`margin_public`（其 `source` 为 `"unverified"`，混入已验证事实会使该块语义自相矛盾），
不进 `negative_funding_status`（那是负费率借币方向，抵押额度卡的是正费率买入方向）。

```json
"collateral_cap": {
  "exceeded": true,
  "asset": "TSLAB",
  "checked_at": "2026-08-03T04:15:22Z"
}
```

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `exceeded` | `true \| false \| null` | 三态权威值。`true`=本次读取命中名单；`false`=本次读取成功且未命中；`null`=本次读取不知道。无可解析现货腿另见不适用规则 |
| `asset` | `string \| null` | **用于判定的已解析现货 base asset**（bStock 为 B-suffix pair 的 base，如 `TSLAB`）。无可解析现货腿时为 `null` |
| `checked_at` | `string \| null` | 本次成功读取完成的 UTC 时刻，格式 `YYYY-MM-DDTHH:MM:SSZ`。全表同值：当前全局读取失败时为 `null`；不适用行携带同一全局值但前端不渲染额度徽标 |

**后端发射规则：**

- 每一行**始终**发射 `collateral_cap` 键（沿用 v0.8 `cross_margin_borrowed_value_usdt`
  「producer 总是发键，值可为 null」的先例）。缺键只可能来自 v0.1–v0.8 历史/冻结样本。
- `checked_at` 是**平台级读取的属性**，同一份快照内**全表所有行取同一个值**。后端不得逐行
  另打时间戳；前端不得据此推断行间差异。
- 语义与契约既有口径一致：`checked_at` 是**请求成功完成时刻**，不是名单生效时刻。

**schema 片段**（加入 `$defs/row.properties`，**不**加入 `$defs/row.required`；`additionalProperties`
保持 `false`，故必须登记该 property）：

```json
"collateral_cap": {
  "type": "object",
  "additionalProperties": false,
  "required": ["exceeded", "asset", "checked_at"],
  "properties": {
    "exceeded": { "type": ["boolean", "null"] },
    "asset":    { "type": ["string", "null"] },
    "checked_at": { "type": ["string", "null"] }
  }
}
```

历史冻结样本（v0.1–v0.8）不含该键，因其为 optional 故仍须校验通过——这是后端测试的红线之一。
`schemas/api/public-market/symbol-snapshot.schema.json` 经共享 row `$ref` 自动继承，**不改那个文件**。

`summary` 不新增任何计数；`warnings` 不新增条目；`schema_version` 保持
`public-market-snapshot/v1`（纯 additive）。

---

## 3. 三态真值表（唯一定义）

四种可能组合；前三种是有现货腿行的三态，第四种为不参与判定的不适用：

| # | `exceeded` | `asset` | `checked_at` | `ui_flags` | 语义 | 前端渲染 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `true` | 非 null | 非 null | 含 `COLLATERAL_CAP_EXCEEDED` | 该资产在最近一次成功读取中命中名单 | **高亮**「抵押额度已满」 |
| 2 | `false` | 非 null | 非 null | 不含抵押额度类 flag | 该次读取成功且未命中 | 常态（无徽标）+ 页面级截至时间 |
| 3 | `null` | 非 null | `null` | 含 `COLLATERAL_CAP_UNKNOWN` | **本次**名单读取失败（网络 / 限频 / **鉴权失败** / 未配置 key / offline） | 明确「未知」，**绝不可呈现为未满** |
| 4 | `null` | `null` | 与全表 `checked_at` 相同 | 不含抵押额度类 flag | 该行无可解析的可交易现货腿，判定**不适用** | 不显示任何抵押额度徽标 |

**不存在第五种组合。** 后端必须保证 `exceeded`、`asset`、`checked_at`、`ui_flags` 四者一致
（后端测试须锁定这一点）；前端遇到表外组合按**未知**处理（fail-closed）。

**未命中（态 2）的口径**：只表示**本次未观察到平台额度已满**，不表示 PAPI 现货一定可提交、
不表示不会返回 `51169`。与 §3 预检口径完全一致，UI 文案不得暗示「可用 / 充足 / 正常」。

**刷新失败时的行为（Human 决策 §E-4）：**

内部缓存可保留 last-good 仅供下一次刷新重试，但**不得**把它投影到本次行情页。任意一次失败
刷新都发射态 3（未知），清空输出 `checked_at`；不能以旧时间或旧名单将本次失败伪装为已满/未满。
§3 开单预检仍永远自己新读一遍，展示缓存绝不参与路由。

---

## 4. `ui_flags` 精确值与出现条件

`ui_flags` 是 `rows[]` 已有的字符串数组（现有值：`MARGIN_PUBLIC_UNVERIFIED`、
`PERP_ONLY_NO_SPOT_LEG`、`TRADIFI_BSTOCK`）。本轮**只新增两个值**：

| flag | 出现条件 | 不出现条件 |
| --- | --- | --- |
| `COLLATERAL_CAP_EXCEEDED` | 真值表态 1（`asset` 非 null 且命中名单） | 其余全部 |
| `COLLATERAL_CAP_UNKNOWN` | 真值表态 3（`asset` 非 null 且本次读取未知） | 其余全部 |

- **不新增** `COLLATERAL_CAP_NOT_EXCEEDED` 或 `..._NOT_APPLICABLE`：同一事实写两处必然漂移
  （本项目已在 `2026-07-hedge-open-live-v1` 一轮抓修三次跨 seam 漂移）。「无 flag + `exceeded=false`」
  即未满，「无 flag + `asset=null`」即不适用。
- flag 是 `collateral_cap` 块的**严格派生**，由后端在同一处计算；`collateral_cap` 块是权威。
- 追加在既有 flag 之后。前端**必须**用 `includes()` 判断，不得依赖顺序或下标。
- schema 中 `ui_flags` 为 `items: {type: string}`，无 enum，**不需要 schema 改动**。

---

## 5. 匹配口径（一处实现，两处调用）

这是本 stage 不拆分评审的核心理由（决策 §B-6「共用规则，不共用数据」）。

- **判定输入 = 已解析现货 pair 的 base asset**，即 `resolve_spot_leg()`
  （`backend/domain/normalize.py`）返回的现货记录的 `baseAsset`。
- **绝不使用行顶层 `base_asset`**（那是**合约** base）。bStock：合约 `TSLAUSDT` → 现货
  `TSLABUSDT` → 判定用 `TSLAB`，**不是** `TSLA`。
- 解析规则实现为**一处纯函数**，§3 预检路由与 §6 展示标记**都调用它**。禁止在展示侧或预检侧
  各写一份等价逻辑（即使行为暂时一致）。
- **精确匹配**：区分大小写、不做归一化、不剥离 `1000x` 类倍率前缀、不做任何换算。实测 121 项
  全部落在现货 `baseAsset` 全集内（含 `1000CHEEMS` 与中文名资产 `币安人生`），无需换算。
- 无可解析的可交易现货腿（`resolve_spot_leg` 返回 `(None, None)`）→ `asset: null` → 真值表态 4。

---

## 6. 展示不按费率正负过滤（已定裁定 §E-3）

任一行只要其**已解析现货 base asset** 命中名单，即为态 1 并高亮。以下字段**一律不参与**该判定，
后端与前端都不得据其过滤：

`daily_funding_rate` 正负 / `positive_funding_enabled` / `route_class` /
`negative_funding_status` / `asset_tag`。

费率方向只影响 §3 的**下单路由**（普通现货仅用于正费率 `BUY`），不影响 §6 展示。

---

## 7. 硬边界：展示缓存绝不供预检使用

| 必须共用 | 必须隔离 |
| --- | --- |
| §5 的现货 base asset 解析规则（一处纯函数） | **缓存数据本身** |
| `HedgeOpenLiveClient` 的 deny-by-default allowlist 登记与 host 硬绑定 | 两条调用路径的存储与生命周期 |

具体禁令（后端实现必须满足，且须有测试证明）：

1. `hedge_preflight_provider` / `live_hedge_executor` / `hedge_open_tasks/*` 的任何路径
   **不得**读取 SnapshotService 的名单缓存，**不得**为取该名单而持有 SnapshotService 实例。
2. 预检的新读结果**不得**回填展示缓存（否则展示时间戳被下单频率带偏，并形成隐式共享通道）。
3. 必须存在一个测试：展示缓存标记为「已满」而预检新读为「未满」时，路由按**新读**结果走
   （方案 §9 #11）。
4. 展示读取失败**不得**降级为「按预检的某次结果显示」。

失守后果（方案 §6.4）：三分钟前刚被打满的币被判走 PAPI → 合约腿成交、现货腿被拒 → **裸空**。

---

## 8. 前端消费规则

**必须：**

- `collateral_cap` 按**可选/additive** 处理：加入 `OPTIONAL_*` 一类的可选字段处理，
  **不得**加入 `REQUIRED_ROW_FIELDS`（加入会让不含该键的冻结离线快照直接报错）。
- 渲染判定按下列**有序**规则（与 §3 真值表等价，含 fail-closed 兜底）：

  1. 行内无 `collateral_cap` 键 → 不适用（历史/冻结载荷），不显示徽标；
  2. `ui_flags` 含 `COLLATERAL_CAP_EXCEEDED` → **已满**；
  3. `ui_flags` 含 `COLLATERAL_CAP_UNKNOWN` → **未知**；
  4. `collateral_cap.asset == null` → 不适用，不显示徽标；
  5. `collateral_cap.exceeded === false` 且 `checked_at` 为非空字符串 → **未满**（常态，无徽标）；
  6. 其余任何组合 → 按**未知**处理，绝不按未满。

- 高亮**打在资产上**：渲染进「标的」列单元格（该列已含 symbol 与 `base_asset/quote_asset`）。
- 截至时间必须露出：在市场表上方的摘要/表头区**一处**展示「抵押额度名单截至 `<北京时间>`」
  （全表同值，逐行重复无信息量）；徽标的 `title` 也带该时间。`checked_at` 为 `null` 时该处
  显示「未知」，不得显示为空或当前时间。
- 时间格式沿用既有做法：`formatBeijing(new Date(iso).getTime())`（既有先例见
  `frontend/index.html` 私有面板 `checked_at` 渲染）。
- 文案中文优先；bStock 行的提示须体现实际判定资产（`collateral_cap.asset`，如 `TSLAB`），
  不得写成合约 base（`TSLA`）。

**禁止：**

- 进入「借贷状态 / 资产」列（决策 §B-4、方案 §6.3）。
- 把 `exceeded === null`、缺键或表外组合渲染成「未满 / 正常 / 充足 / 可用」。
- 用 `collateral_cap` 改变**排序、过滤、可开单判断、按钮启用/禁用状态**——本轮是**纯展示**。
- 前端自行推导现货 base asset（必须用后端给的 `collateral_cap.asset`）。
- 调用币安或任何外域、新增 `fetch` 目标、新增定时器（self-check 已锁 60000 / 1000 / 2000 三种）。
- 修改 `backend/tests/fixtures/**`（含 `private-account-v1-design.json`）——用 self-check 内存注入，
  与既有 `opening_quotes` 注入同法。

---

## 9. 本文所做的接口裁定（含依据）

以下五项是方案未逐字写死、但两端必须一致的接口细节。每项标注依据，均**未新增产品规则**；
若评审认为任一项越界，按发现处理，本文即时更正。

| # | 裁定 | 依据 |
| --- | --- | --- |
| I-1 | 任意展示刷新失败 → 未知；last-good 只留作内部重试，不投影到页面 | Human 决策 §E-4；与方案 §6.3「读取失败 → 未知」一致，预检仍独立新读 |
| I-2 | 无可解析现货腿 → 态 4「不适用」（`asset=null`、无 flag、不显示徽标），而非未满 | Human 决策 §E-4；匹配输入不存在，且不适用不属于有现货腿行的三态 |
| I-3 | 块内增加 `asset` 字段 | §6.5 要求匹配规则单点实现；不给出判定资产，前端要么二次推导（制造第二处实现，正是本 stage 要防的漂移），要么把 bStock 显示成 `TSLA`（展示断言了错的事实）。`asset` 只是把已算出的结果暴露出来，**不参与、也不得参与路由** |
| I-4 | 只加两个 flag，不加「未满 / 不适用」flag | 避免同一事实两处表达；`collateral_cap` 块是权威，flag 是派生 |
| I-5 | `checked_at` 全表同值，且截至时间在页面一处露出 | 它是平台级单次读取的属性；§6.3 只要求「时间戳必须露出」，未要求逐行展示 |

---

## 10. 展示读取的前置条件与已知降级（必须让 Human 知道）

`restricted-asset` 需要 `X-MBX-APIKEY`。应用组合根使用已有 hedge API key 构造受 exact allowlist
保护的只读 client 并注入 SnapshotService；这与 `APP_HEDGE_EXECUTOR` 和 private channel 开关无关。
创建 client 本身不发请求，不改变 Start gate；SnapshotService 只可调用名单 GET。

因此：**离线模式或 hedge API key 缺失/失效时，行情页该列全表为「未知」（态 3）。** 这是诚实
降级，不是缺陷。本轮不新增开关、环境变量或配置项；若实现需要，停止并上报。

方案 §7.3 已记录由此产生的新失败模式：公共快照过去对凭证问题免疫，接入后 key 失效、被撤、
IP 白名单变化都会让这次读取失败——这正是第三态必须存在的理由之一。

---

## 11. 非目标（防镀金，两个实现任务都适用）

- 不新增行情页过滤器、排序基准、`summary` 计数或 `warnings` 条目。
- 不改 `negative_funding_status`（仍对全部可交易行停在 `PRIVATE_BORROW_VALIDATION_REQUIRED`）。
- 不接 `/sapi/v1/margin/allPairs`、`/sapi/v1/margin/allAssets`、`margin/available-inventory`。
- 不做 API key 权限运行时探测（决策 §A-1）。
- 不做普通现货钱包一致性检测、告警或补救（决策 §A-2）。
- 不做 `51169` 自动补腿（方案 §1.2 / §5）。
- 不新增数据库迁移、不新增调度器、不改 Start gate、不改现有公共端点形状。
- 不因 `collateral_cap` 禁用任何开单/借币入口。
