# Hyperliquid 费率对比行（前四列）设计方案

- 日期：2026-08-23
- stage：`2026-08-23-hyperliquid-funding-compare-v1`
- 角色：Planner（Opus 5）。本文件不授权实现、验收、合并或实盘。
- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- 修订：**rev3**，按 Codex 复评 `REWORK` 的 N1–N3 最小修订。
  评审记录：`.../evidence/hyperliquid-funding-compare-design-review-codex.handoff.md`（rev1，F1–F5）、
  `.../evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md`（rev2，N1–N3）
- 证据：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/`

> **采样时点声明（贯穿全文）**：本文出现的一切市场计数与比例，均为
> **2026-08-23 CST（纽约 2026-08-22 周六，美股休市）** 的采样值，不是稳定契约。
> 引用时必须带时点；实现与测试不得把它们写成常量断言。

---

## 1. 产品目标

在既有「费率行情」表的**前四个费率列**内，每行下方增加一行 Hyperliquid 的同口径数值，
使币安与 Hyperliquid 的费率在同一位置直接可比。**只读展示，不触碰下单、保证金、账户。**

| 列 | 币安（首行，现状不变） | Hyperliquid（第二行，新增） |
|---|---|---|
| 资金费率 | `futures.last_funding_rate` | `hyperliquid.funding_1h` |
| 结算时间 | `futures.next_funding_time` | 固定文案「每小时」 |
| 日费率 | `daily_funding_rate` | `hyperliquid.daily_rate` |
| 年化 24h | `annualized_funding_24h` | `hyperliquid.annualized_24h` |

「结算时间」第二行不显示 HL 的下一个整点时刻：HL 每小时结算、币安 4h/8h，
显示两个时刻会诱导「同时结算」的误读，而**错拍恰恰是跨所对比最需要看见的事实**。

**第二行的展示约束**（rev2，评审 R1）：

- 第二行必须带来源标签：main 显示 `HL`，xyz 显示 `HL·xyz`。
- 第二行**不参与**现有筛选、排序、借币、开单的任何逻辑；它是纯展示投影。
- `HL·xyz` 标签**不附加任何价值判断文案**。评审曾建议加「非美股交易时段读数可能退化」，
  **本设计不采纳**：Human 2026-08-23 明确「股市休息币圈不休息，休市反而会有高费率出现」，
  这正是 xyz 必须进第一版的理由；挂退化提示会诱导使用者忽略该时段，与产品目标相反。
  休市造成的数值特征由使用者自行判读，UI 只保证数值真实且标明来源。

## 2. 发布边界

**做**：
- 后端新增 Hyperliquid 公共行情源（`POST https://api.hyperliquid.xyz/info`，
  `metaAndAssetCtxs`，`dex=""` 与 `dex="xyz"` 各一次）。
- `build_rows` 每行新增 `hyperliquid` block（契约见 §5）。
- 前端四个单元格加第二行；筛选栏加「显示 HL 对比行」开关（默认开）。

**不做（非目标）**：
- 「近 24h」「年化 7D」「年化 30D」三列的 HL 第二行。成本论证见下。
- `HL_SYMBOL_MAP` 别名表与乘数币映射。第一版只做同名 exact + 类别校验。
- `predictedFundings` 端点。理由见 §6。
- 任何下单、保证金、跨所对冲执行路径。
- main/xyz 之外的 HIP-3 dex（`flx`/`vntl`/`km`/`abcd`/`cash` 在架标的为 0；
  `hyna`/`para`/`mkts`/`io` 合计 42 个，按双边成交额全部不足量）。

**三列历史的成本（rev2 勘正，评审 R2）**：HL `fundingHistory` 按 coin 单查、
单次上限 500 条（实测 BTC 40 天请求返回 500 行、首末相差 499 小时 ≈ 20.8 天；
省略 `coin` 返回 HTTP 422）。30 天 = 720 个小时结算点 > 500，故**每标的至少两页**。
沿用现有 `history_sweep_batch_size=10` 的游标，HL 最坏每 tick 新增 **20 次请求**，
历史请求总量由 **10 变 30**（非笼统「翻倍」）。等前四列跑过一轮真实数据再评估。

## 3. 符号匹配规则（fail-closed）

沿用 `DEC-2026-08-07-003`：同名走 exact，不同名不显示，查不到就是查不到。

**匹配顺序（rev2，评审 F3/F4）**：

1. 先按**完整 HL key**（含 dex 前缀，如 `xyz:BB`）查 `HL_SYMBOL_DENY`，命中即丢弃。
2. 过滤 `isDelisted == true` 的 HL 标的。
3. 取 raw name（剥 dex 前缀）与币安 symbol 做 exact 比对。
4. **类别校验**（本 rev 新增）：`main` 只允许匹配币安 `contractType == "PERPETUAL"`，
   `xyz` 只允许匹配 `contractType == "TRADIFI_PERPETUAL"`。类别不一致即丢弃。

第 4 步是本 rev 的核心修订。rev1 只靠静态 DENY 两条，无法支撑「漂移不会显示错值」的结论——
`xyz:BB`（黑莓 vs BounceBit）与 `xyz:QNT`（vs Quant）已经证明该缺陷家族可达，
将来新增一个与加密币同名的 xyz 标的会被 exact 静默误配。类别校验让**这一类**问题
自动 fail-closed，不依赖枚举。DENY 保留为显式回归防线。

| 类别 | 数量（2026-08-23 采样） | 第一版处理 |
|---|---|---|
| 同名 + 类别一致 | **244**（main 166 + xyz 78） | 显示 |
| 需别名表 | 9（GOLD/SILVER/PLATINUM/PALLADIUM/BRENTOIL/SP500/KR200/SMSN/SKHX） | 显示 `—` |
| 需乘数映射 | 5（kPEPE/kSHIB/kBONK/kLUNC/kFLOKI） | 显示 `—` |
| 同名但类别不一致 | 2（`xyz:BB`、`xyz:QNT`） | 类别校验拦下 + DENY 双保险 |

```python
HL_SYMBOL_DENY = {
    "xyz:BB":  "币安 BB 是 BounceBit（加密），与黑莓无关",
    "xyz:QNT": "币安 QNT 是 Quant（加密），xyz:QNT 是股票",
}
```

这是本 stage **唯一**允许硬编码的映射常量，形制照抄 `SPOT_SYMBOL_DENY`。

## 4. 数据口径

- HL `funding` 是**每小时**费率的实时预估（HL 官方文档：funding 每小时支付），
  与币安 `lastFundingRate`（本周期实时预估、结算前会漂移）同性质。
- `daily_rate = funding × 24`；`annualized_24h = daily_rate × 365`。
- **全部计算走 Decimal 字符串规则**，复用 `backend/domain/snapshot.py` 既有 helper。
  证据脚本 `pairing-probe.py` 用 float 仅为摸排便利，**实现不得照抄**。
- 币安侧年化沿用现有 `funding_interval_hours` 驱动的算法**不得改动**：
  本次 **258 个已配对样本**中 **122 个 4 小时、136 个 8 小时**，统一按 8h 折算会让那 122 个差一倍。
  （rev1 曾写「870 个合约中」，分母错误：币安 active USDT swap 实测 696，
  而 `/fapi/v1/fundingInfo` 只返回发生 cap/floor/interval 调整的 symbol，其行数不是全市场分母。）
- HL 侧固定 1 小时。

## 5. `hyperliquid` block 契约（rev2 新增，评审 F4）

```
hyperliquid: null | {
    dex:           "main" | "xyz",
    funding_1h:    decimal string,
    daily_rate:    decimal string,
    annualized_24h: decimal string,
}
```

- 三个数值一律 **decimal string**，与 `schemas/api/public-market/snapshot.schema.json`
  既有 wire 风格一致；禁止 JSON number/float。
- `null` 的两种成因必须可区分（项目活约束：「读不到」不得假装「知道没有」）。
  **区分手段是 §6 的 `hyperliquid_data_time` 字段，不是 warning 文本**：
  - **无匹配**：该币安标的在 HL 无对手 / 被 DENY / 类别不一致 → `hyperliquid: null`，
    **且 `hyperliquid_data_time` 有值**（本轮 HL 源成功）。
  - **源失败**：→ 全部行 `hyperliquid: null`，**且 `hyperliquid_data_time` 为 `null`**。
- HL 返回的 `funding` 非法（缺字段、非数值、无法转 Decimal）→ **整源判失败**
  （rev3 修订，见下），不做单标的放行。

**rev3 修订**：rev2 曾规定非法 `funding` 只让该条 match 置 `null`、不影响同批其他标的。
这与 §6 已定的「main+xyz 原子组」自相矛盾——既然一个 dex 的 POST 失败就整组作废，
源返回非法值同样说明这一批不可信，没有道理单独放行其余标的。
统一为**整源失败**后，全部失败态共用一个可观察信号（时间戳），
不需要维护第二套 warning token 词汇表。

## 6. 刷新、失败语义与新鲜度信号（rev3 重写）

**rev1 的最严重缺口**：现有 Group A/B 是 success-only cache
（`snapshot_service.py:_refresh_due_sources` 原文 "Timestamps advance only on success (FR-2)"），
`_compose_base_raw` 冷启动等 A+B 都成功才发布。两种朴素实现各违反一条既有约束：

- 把 HL 塞进 premium 源 → HL 失败会让币安冷启动**发不出快照**；
- 做独立源但沿用 success-only 投影 → HL 失败时展示**无时效标记的旧值**。

**rev2 的残留缺口**（复评 N1）：rev2 只写「带 warning」。但
`backend/domain/snapshot.py` 的 `warnings = list(CONTRACT_WARNINGS) + extra` 意味着
**每份快照的 warnings 数组永远非空**（三条固定契约文本），
「断言 warnings 非空」在 HL 成功时同样成立，是**假绿断言**；
且 `frontend/index.html:validateContract` 只校验 `Array.isArray(snapshot.warnings)`，
**首页从不渲染 warnings 内容**，HL 挂掉在页面上与「HL 没有这个币」完全同形。

### 6.1 刷新契约

1. HL 是**独立 source_id**，60s 组，与 `premium_index` 同频但**独立失败**——
   一方失败不抑制另一方重试，也不阻断快照发布。
2. **main + xyz 为原子组**：两次 POST 任一失败、任一返回 shape 非法、
   或任一标的 `funding` 无法转 Decimal → 本轮 HL **整源失败**。
   （per-dex 部分成功是另一个设计选择，本 rev 明确不做。）
3. 整源失败时：全部行 `hyperliquid: null`，**不投影 warm last-good**。
4. 币安四列首行在任何 HL 失败下**照常显示**。
5. 冷启动时 HL 未成功过 → 全部 `null`，不阻断发布。

### 6.2 新鲜度信号（rev3 新增，替代 warning token）

快照顶层新增**一个字段**：

```
snapshot.hyperliquid_data_time: null | ISO 8601 字符串
```

- **有值**：本批 HL 数据的采集时刻，HL 源本轮成功。
- **`null`**：从未成功过，或本轮整源失败（含 offline，见 §6.3）。

前端在既有 `market-snapshot-meta`（市场表下方「生成时间 · 数据时间」那一行）
**追加** `· HL 数据时间: <值>`，并**复用既有 `isStaleTime()` 与 `.stale-time` 类**
（`color: var(--danger); font-weight: 700`，项目已在三处使用）。

三态由此在同一处可见：

| 状态 | 显示 |
|---|---|
| 正常 | `HL 数据时间: 11:24:03` |
| 陈旧（取到了但超过 stale 阈值） | 同行标红 |
| 从未取到 / 本轮整源失败 | `HL 数据时间: —` 且标红 |

**这是本设计对「无匹配 vs 源失败」的唯一区分手段**：

- 行内 `—` + 时间戳正常 → HL 无此标的；
- 行内 `—` + 时间戳标红 → HL 源不可用，全表 HL 值均不可信。

选择时间戳而非 warning token 的理由：token 只能表达二元的「挂/没挂」，
而对 60 秒刷新的费率数据，**「这是什么时候的」与「有没有」同等重要**——
五分钟前的费率照样会让人做错判断，token 说不出这件事。
且本方案零新增 UI 组件、零新增词汇表，复用现成机制。

### 6.3 offline 零网络路径（rev3 新增，复评 N2）

`get_snapshot` 的 offline 分支走 `build_snapshot()` 同步 frozen-fixture 组装
（原文 "Offline synchronous build from frozen fixtures (zero network)"），
**不经过 `_refresh_due_sources`**，worker 也不启动。故：

- offline 下**零次 HL 网络请求**；
- 每行 `hyperliquid: null`；
- `hyperliquid_data_time` 恒为 `null` → 前端显示 `—` 且标红。

**offline 不需要独立信号**：它与「源失败」共用同一个时间戳表达，语义一致
（都是「当前拿不到 HL 数据」），无需新增 fixture、状态或抽象。
`hyperliquid` block 在 schema 中**必须可空且非 required**，
否则既有 offline fixture 会直接打挂 schema 校验。

## 7. 文件边界

| 文件 | 改动 |
|---|---|
| `backend/adapters/`（新增 HL 公共适配器） | 新文件，形制参照 `binance_public.py` |
| `backend/domain/normalize.py` | 新增 `HL_SYMBOL_DENY` 常量 |
| `backend/domain/snapshot.py` | `build_rows` 新增入参与 `hyperliquid` block |
| `backend/services/snapshot_service.py` | 新增独立 HL source_id + 失败语义（§6） |
| `backend/config.py` | HL base_url、超时 |
| `schemas/api/public-market/snapshot.schema.json` | 新增 `hyperliquid` block（可空） |
| `frontend/index.html` | 四个 `<td>` 加第二行 + 开关 + `market-snapshot-meta` 追加 HL 数据时间（§6.2） |
| **`frontend/self-check.js`** | **rev2 补入**：现有 `headerCount !== 15` 断言与 161 处市场表回归会因新增 subline 失效，必须同步 |
| **`docs/api/public-market-contract.md`** | **rev2 补入**：v0.17 as-built 活契约，须登记新 row block、空值与失败语义 |
| `backend/tests/` | 见 §9 |

若实现采用依赖注入而非在 `SnapshotService` 内部构造 HL 客户端，须**显式追加**
`backend/app/server.py` 到本清单，不得在实现时临时决定。

**禁止触碰**：任何下单、保证金、借币、平仓路径；`SPOT_SYMBOL_MAP` 现有条目；
币安侧费率与年化的既有算法。

## 8. 已知风险

- `[展示]` **xyz 的 78 个在美股休市时段费率退化**。2026-08-23 采样（纽约周六）时
  币安侧 87 个中 83 个费率为 0（Codex 独立复测同一现象为 80/87，比例会漂移）。
  **不加 UI 提示语**，理由见 §1。
- `[展示]` **表格行高翻倍**。现有表 15 列，四列加第二行后一屏可见标的数减半。
  缓解：默认开的显示开关。
- `[数据]` HL 标的漂移比币安快（xyz 半年内新增 101、下架 15）。exact + **类别校验**
  fail-closed。**表述收窄（rev3）**：类别校验只自动拦截**跨类别**撞名
  （xyz 股票 vs 币安加密，即 BB/QNT 那一类）；**同类别同名**的撞名
  （如 main 新上一个与币安不同资产的同名加密币）**它挡不住**，仍需人工发现后收录 DENY。
  rev2 曾笼统写「新撞名均静默消失」，不成立。
- `[成本]` 每次刷新增加 2 个 POST（实测 1.07 秒）。需确认不挤占既有 tick 预算。

## 9. 验收标准（rev3 修订，评审 F2/R7 + 复评 N1/N2/N3）

**行基底事实**：`build_rows` 只遍历币安 `futures_symbols`。HL 有而币安没有的标的
（`MNT`/`PURR`/`APEX`/`CASHCAT`/`kNEIRO`，实测币安 UM 均不存在）**根本不产生行**，
不可用作「第二行显示 `—`」的验收对象。rev1 的验收 5 因此不可执行，本 rev 已替换。

| # | 断言 | 覆盖 |
|---|---|---|
| A1 | `xyz:BB` / `xyz:QNT` 不显示任何 HL 数值 | DENY |
| A2 | **synthetic**：构造一个类别不一致的新撞名 fixture，验证被拦下——证明不依赖 BB/QNT 枚举 | F3 |
| A3 | `HYPE` 行显示 HL 第二行 | 未依赖 `predictedFundings` 的漏映射 |
| A4 | 币安侧四列数值与本 stage 前**逐格相同** | 回归 |
| A5 | 一个 4h 与一个 8h 周期标的的币安年化各自正确，未被统一成 8h | 口径 |
| A6 | **Binance-only fixture symbol**（HL 侧无此标的）→ `hyperliquid == null`，UI 显示 `—` | **替代 rev1 验收 5** |
| A7 | HL 源**冷启动失败** → 四列首行照常、第二行 `—`、`hyperliquid_data_time == null`、**页面 HL 数据时间显示 `—` 且带 `stale-time` 类**、不阻断发布 | §6.2 |
| A8 | HL **success → failure** → 第二行转 `—`、时间戳转 `null` 并标红，**不得显示上一轮旧值也不得保留上一轮时间戳** | §6.1-3 |
| A9 | HL 返回非法 `funding`（无法转 Decimal）→ **整源失败**，与 A7 同一 oracle（时间戳 `null` + 标红） | §5 rev3 / §6.1-2 |
| A9b | **反向 oracle**：HL 源成功且仅部分标的无匹配时，`hyperliquid_data_time` **有值且不标红** | 复评 N1-4 |
| A9c | **offline**（`APP_OFFLINE=true`）：零次 HL 网络请求、每行 `hyperliquid: null`、时间戳 `null` 且标红、schema 校验通过 | §6.3 / 复评 N2 |
| A10 | 三个数值字段均为 **decimal string**，schema 校验通过 | §5 wire |
| A11 | 结算时间第二行文案恒为「每小时」，不显示时刻 | **D1** |
| A12 | 9 个别名 + 5 个乘数币标的第二行为 `—` | **D3** |
| A13 | **一次成功的 HL 刷新恰好发出两次** `metaAndAssetCtxs` POST（`dex=""` 与 `dex="xyz"` 各一次）；任一次刷新**最多**两次；**所有路径** `predictedFundings` 调用为零。首个 POST 失败时第二个**不再发出**（原子组已判失败） | **D4** / 复评 N3 |
| A14 | 「显示 HL 对比行」默认开；关闭后行高与首行内容恢复本 stage 前状态 | **D5** |
| A15 | 第二行带 `HL` / `HL·xyz` 来源标签，且不参与筛选/排序/借币/开单 | §1 R1 |
| A16 | `frontend/self-check.js` 通过（含新增 subline 的 15 列断言修订 + HL 数据时间元素断言） | §7 |

## 10. 决策点（待 Human 确认）

- **D1** 前四列范围与「结算时间」第二行用固定文案「每小时」——§1 / A11。
- **D2** 三列历史列为非目标（HL 最坏每 tick 新增 20 请求，总量 10→30）——§2。
- **D3** 第一版不建别名表与乘数映射，14 个标的显示 `—`——§3 / A12。
- **D4** 不使用 `predictedFundings`——§6 说明 + A13。
- **D5** 「显示 HL 对比行」开关默认开——§8 / A14。
- **D6**（rev2 新增）HL 失败采用 **main+xyz 原子组 + 不投影 last-good**，
  而非 per-dex 部分成功——§6 / A7 A8。
- **D7**（rev2 新增）`HL·xyz` 标签**不加**休市提示语——§1。复评已 `ACCEPT` 该拒绝。
- **D8**（rev3 新增）失败信号采用 **`hyperliquid_data_time` 时间戳 + 既有 `.stale-time` 红色高亮**，
  而非 warning token 词汇表；非法 `funding` 归入整源失败而非单标的放行——§5 / §6.2 / A7–A9c。

## 11. 修订对照

| finding | 修订 |
|---|---|
| F1 失败语义未定义 | 新增 §6 完整失败语义；验收 A7/A8/A9 |
| F2 验收 5 不可执行 | §9 说明行基底事实，A6 替换为 Binance-only fixture；D1–D5 各补断言 A11–A14 |
| F3 静态 deny 不足 | §3 新增类别校验为第 4 步；A2 synthetic 测试 |
| F4 wire 契约缺失 | 新增 §5；Decimal 字符串、`isDelisted` 过滤、DENY 先于 raw name、非法值 fail-closed |
| F5 事实标签与文件边界 | §4 分母改 258 样本口径；全文加采样时点声明；§7 补 `self-check.js` 与 `public-market-contract.md` |
| R2 成本数字 | §2 改为「最坏 +20 请求、总量 10→30」 |
| F4 附带的休市提示语 | **不采纳**，理由记入 §1 与 D7（复评已 ACCEPT） |

### rev2 → rev3（复评 N1–N3）

| finding | 修订 |
|---|---|
| N1 失败/无匹配/非法值不可区分 | §6.2 新增 `hyperliquid_data_time` 字段 + 复用既有 `.stale-time` 红色高亮，三态同处可见；A7/A8/A9 改为断言时间戳而非 warning 数组；新增反向 oracle A9b。**未采用 warning token 方案**，理由见 §6.2 与 D8 |
| N1-2 单币非法值专属 token | **简化为整源失败**（§5 rev3 修订）：与「main+xyz 原子组」保持一致，一个机制覆盖全部失败态，不引入第二套词汇表 |
| N2 offline 无契约 | §6.3 新增；A9c 验收；明确 `hyperliquid` block 在 schema 中非 required |
| N3 A13 oracle 不唯一 | A13 限定「一次成功刷新恰好两次、任一次刷新最多两次、失败时第二个不再发出」 |
| 复评提醒：§8「新撞名均」表述过宽 | §8 收窄为「类别校验只拦跨类别撞名，同类别同名仍需人工收录 DENY」 |
