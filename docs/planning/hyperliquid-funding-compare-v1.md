# Hyperliquid 费率对比行（前四列）设计方案

- 日期：2026-08-23
- stage：`2026-08-23-hyperliquid-funding-compare-v1`
- 角色：Planner（Opus 5）。本文件不授权实现、验收、合并或实盘。
- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- 修订：**rev2**，按 Codex 设计评审 `REWORK` 的 F1–F5 最小修订。
  评审记录：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md`
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
- `null` 的两种成因必须可区分（项目活约束：「读不到」不得假装「知道没有」）：
  - **无匹配**：该币安标的在 HL 无对手 / 被 DENY / 类别不一致 → `hyperliquid: null`，
    且本轮 HL 源**成功**。
  - **源失败**：见 §6 失败语义 → `hyperliquid: null`，且快照带可见 warning。
- HL 返回的 `funding` 非法（缺字段、非数值、无法转 Decimal）→ **该条 match fail-closed**
  置 `null`，不影响同批其他标的。

## 6. 刷新与失败语义（rev2 新增，评审 F1）

**这是 rev1 最严重的缺口**：现有 Group A/B 是 success-only cache
（`snapshot_service.py:_refresh_due_sources` 原文 "Timestamps advance only on success (FR-2)"），
`_compose_base_raw` 冷启动等 A+B 都成功才发布。两种朴素实现各违反一条既有约束：

- 把 HL 塞进 premium 源 → HL 失败会让币安冷启动**发不出快照**；
- 做独立源但沿用 success-only 投影 → HL 失败时展示**无时效标记的旧值**。

**本设计选定**：

1. HL 是**独立 source_id**，60s 组，与 `premium_index` 同频但**独立失败**——
   一方失败不抑制另一方重试，也不阻断快照发布。
2. **main + xyz 为原子组**：两次 POST 任一失败、或任一返回 shape 非法 →
   本轮 HL **全部** `null` + 追加可见 warning，**不投影 warm last-good**。
   （per-dex 部分成功是另一个设计选择，本 rev 明确不做。）
3. 币安四列首行在任何 HL 失败下**照常显示**。
4. 冷启动时 HL 未成功过 → 全部 `null` + warning，不阻断发布。

## 7. 文件边界

| 文件 | 改动 |
|---|---|
| `backend/adapters/`（新增 HL 公共适配器） | 新文件，形制参照 `binance_public.py` |
| `backend/domain/normalize.py` | 新增 `HL_SYMBOL_DENY` 常量 |
| `backend/domain/snapshot.py` | `build_rows` 新增入参与 `hyperliquid` block |
| `backend/services/snapshot_service.py` | 新增独立 HL source_id + 失败语义（§6） |
| `backend/config.py` | HL base_url、超时 |
| `schemas/api/public-market/snapshot.schema.json` | 新增 `hyperliquid` block（可空） |
| `frontend/index.html` | 四个 `<td>` 加第二行 + 开关 |
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
  fail-closed，改名或新撞名均静默消失而非显示错值（rev1 仅靠静态 DENY 无法支撑此结论）。
- `[成本]` 每次刷新增加 2 个 POST（实测 1.07 秒）。需确认不挤占既有 tick 预算。

## 9. 验收标准（rev2 重写，评审 F2/R7）

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
| A7 | HL 源**冷启动失败** → 四列首行照常、第二行 `—`、快照带 warning、不阻断发布 | §6 D-fail |
| A8 | HL **success → failure** → 第二行转 `—` 且带 warning，**不得显示上一轮旧值** | §6 no-last-good |
| A9 | HL 返回非法 `funding` → 该标的 `null`，同批其他标的不受影响 | §5 |
| A10 | 三个数值字段均为 **decimal string**，schema 校验通过 | §5 wire |
| A11 | 结算时间第二行文案恒为「每小时」，不显示时刻 | **D1** |
| A12 | 9 个别名 + 5 个乘数币标的第二行为 `—` | **D3** |
| A13 | adapter 全程仅发出两次 `metaAndAssetCtxs` POST，零次 `predictedFundings` | **D4** |
| A14 | 「显示 HL 对比行」默认开；关闭后行高与首行内容恢复本 stage 前状态 | **D5** |
| A15 | 第二行带 `HL` / `HL·xyz` 来源标签，且不参与筛选/排序/借币/开单 | §1 R1 |
| A16 | `frontend/self-check.js` 通过（含新增 subline 的 15 列断言修订） | §7 |

## 10. 决策点（待 Human 确认）

- **D1** 前四列范围与「结算时间」第二行用固定文案「每小时」——§1 / A11。
- **D2** 三列历史列为非目标（HL 最坏每 tick 新增 20 请求，总量 10→30）——§2。
- **D3** 第一版不建别名表与乘数映射，14 个标的显示 `—`——§3 / A12。
- **D4** 不使用 `predictedFundings`——§6 说明 + A13。
- **D5** 「显示 HL 对比行」开关默认开——§8 / A14。
- **D6**（rev2 新增）HL 失败采用 **main+xyz 原子组 + 不投影 last-good**，
  而非 per-dex 部分成功——§6 / A7 A8。
- **D7**（rev2 新增）`HL·xyz` 标签**不加**休市提示语——§1。

## 11. rev1 → rev2 修订对照

| finding | 修订 |
|---|---|
| F1 失败语义未定义 | 新增 §6 完整失败语义；验收 A7/A8/A9 |
| F2 验收 5 不可执行 | §9 说明行基底事实，A6 替换为 Binance-only fixture；D1–D5 各补断言 A11–A14 |
| F3 静态 deny 不足 | §3 新增类别校验为第 4 步；A2 synthetic 测试 |
| F4 wire 契约缺失 | 新增 §5；Decimal 字符串、`isDelisted` 过滤、DENY 先于 raw name、非法值 fail-closed |
| F5 事实标签与文件边界 | §4 分母改 258 样本口径；全文加采样时点声明；§7 补 `self-check.js` 与 `public-market-contract.md` |
| R2 成本数字 | §2 改为「最坏 +20 请求、总量 10→30」 |
| F4 附带的休市提示语 | **不采纳**，理由记入 §1 与 D7 |
