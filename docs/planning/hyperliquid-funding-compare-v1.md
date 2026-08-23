# Hyperliquid 费率对比行（前四列）设计方案

- 日期：2026-08-23
- stage：`2026-08-23-hyperliquid-funding-compare-v1`
- 角色：Planner（Opus 5）。本文件不授权实现、验收、合并或实盘。
- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- 证据：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/`

---

## 1. 产品目标

在既有「费率行情」表的**前四个费率列**内，每行下方增加一行 Hyperliquid 的同口径数值，
使币安与 Hyperliquid 的费率在同一位置直接可比。**只读展示，不触碰下单、保证金、账户。**

四列范围（表头顺序不变）：

| 列 | 币安（首行，现状不变） | Hyperliquid（第二行，新增） |
|---|---|---|
| 资金费率 | `futures.last_funding_rate` | `hyperliquid.funding_1h` |
| 结算时间 | `futures.next_funding_time` | 固定文案「每小时」 |
| 日费率 | `daily_funding_rate` | `hyperliquid.daily_rate` |
| 年化 24h | `annualized_funding_24h` | `hyperliquid.annualized_24h` |

「结算时间」第二行不显示 HL 的下一个整点时刻：HL 每小时结算、币安 4h/8h，
显示两个时刻会诱导「同时结算」的误读，而**错拍恰恰是跨所对比最需要看见的事实**。

## 2. 发布边界

**做**：
- 后端新增 Hyperliquid 公共行情源（`POST https://api.hyperliquid.xyz/info`，
  `metaAndAssetCtxs`，`dex=""` 与 `dex="xyz"` 各一次）。
- `build_rows` 每行新增 `hyperliquid` block（无对手为 `None`）。
- 前端四个单元格加第二行；筛选栏加「显示 HL 对比行」开关（默认开）。

**不做（非目标）**：
- 「近 24h」「年化 7D」「年化 30D」三列的 HL 第二行。HL `fundingHistory` 按 coin 单查、
  上限 500 条（= 20.8 天 < 30 天），做这三列等于把币安那套 `history_sweep_batch_size`
  游标再建一遍并令每 tick 请求量翻倍。**等前四列跑过一轮真实数据再评估。**
- `HL_SYMBOL_MAP` 别名表与乘数币映射。第一版只做同名 exact 匹配。
- `predictedFundings` 端点。理由见 §5。
- 任何下单、保证金、跨所对冲执行路径。
- main/xyz 之外的 HIP-3 dex（`flx`/`vntl`/`km`/`abcd`/`cash` 在架标的为 0；
  `hyna`/`para`/`mkts`/`io` 合计 42 个，按双边成交额全部不足量，见 §7 证据）。

## 3. 符号匹配规则（fail-closed）

沿用 `DEC-2026-08-07-003`：同名走 exact，不同名不显示，查不到就是查不到。

| 类别 | 数量 | 第一版处理 |
|---|---|---|
| 同名直接 join | **244**（main 166 + xyz 78） | 显示 |
| 需别名表 | 9（GOLD/SILVER/PLATINUM/PALLADIUM/BRENTOIL/SP500/KR200/SMSN/SKHX） | 显示 `—` |
| 需乘数映射 | 5（kPEPE/kSHIB/kBONK/kLUNC/kFLOKI） | 显示 `—` |
| **撞名，必须硬排除** | **2**（`xyz:BB`、`xyz:QNT`） | **DENY 常量，见下** |

`xyz:BB` 是黑莓、币安 `BB` 是 BounceBit；`xyz:QNT` 与币安 `QNT`（Quant）同理。
两者**恰好同名**，exact 匹配会把股票的费率显示成加密币的。必须显式排除：

```python
HL_SYMBOL_DENY = {
    "xyz:BB":  "币安 BB 是 BounceBit（加密），与黑莓无关",
    "xyz:QNT": "币安 QNT 是 Quant（加密），xyz:QNT 是股票",
}
```

这是本 stage **唯一**允许硬编码的映射常量，形制照抄 `SPOT_SYMBOL_DENY`。

## 4. 数据口径

- HL `funding` 字段是**每小时**费率的实时预估，与币安 `lastFundingRate` 同性质
  （均为本周期预估、结算前会漂移），归入同一刷新组。
- `daily_rate = funding × 24`；`annualized_24h = daily_rate × 365`。
- 币安侧年化沿用现有 `funding_interval_hours` 驱动的算法**不得改动**：实测 870 个合约中
  **122 个 4 小时、136 个 8 小时**，统一按 8h 折算会让那 122 个差一倍。
- HL 侧固定 1 小时，`funding_interval_hours` 恒为 1。

## 5. 为什么不用 `predictedFundings`

该端点一次返回 232 个币在 `BinPerp`/`HlPerp`/`BybitPerp` 三家的预测费率，
且官方维护了符号映射（含 `kPEPE` ↔ `1000PEPEUSDT`）。实测三条否决理由：

1. **不覆盖 xyz**。只有 main 的 232 条，本 stage 的 87 个 xyz 标的一个都没有。
   而 `metaAndAssetCtxs` 一个接口两个 POST 同时覆盖 main + xyz，`predictedFundings` 变纯冗余。
2. **映射有双向错误**。在架 171 个的判定里：`VINE` 假阳性（币安 `VINEUSDT` 已 `active=False`）、
   `HYPE` 假阴性（币安 `HYPEUSDT` 在架，且是 HL 第三活跃标的，24h $14.4 亿）。
   两个反向错误使总数凑巧等于自算的 171，**只比数量不比集合会误判为完全一致**。
3. **自家费率也非权威源直读**。其 `HlPerp` 与 `metaAndAssetCtxs.funding` 相比
   177 个中 54 个不同（BTC `2.25804e-05` vs `2.26198e-05`），属独立刷新的聚合快照。
   引入即造成同一数字两个来源。

保留用途：将来做乘数币映射时，作为 `--emit` 生成结果的人工复核参照。

## 6. 文件边界

| 文件 | 改动 |
|---|---|
| `backend/adapters/`（新增 HL 公共适配器） | 新文件，形制参照 `binance_public.py` |
| `backend/domain/normalize.py` | 新增 `HL_SYMBOL_DENY` 常量 |
| `backend/domain/snapshot.py` | `build_rows` 新增入参与 `hyperliquid` block |
| `backend/services/snapshot_service.py` | `base_raw` 新增 HL 源，挂入既有刷新组 |
| `backend/config.py` | HL base_url、超时 |
| `schemas/` | 快照 schema 增 `hyperliquid` block（可空） |
| `frontend/index.html` | 四个 `<td>` 加第二行 + 开关 |
| `backend/tests/` | 见 §8 |

**禁止触碰**：任何下单、保证金、借币、平仓路径；`SPOT_SYMBOL_MAP` 现有条目；
币安侧费率与年化的既有算法。

## 7. 已知风险

- `[展示]` **xyz 的 78 个在美股休市时段费率是死的**。采样于 2026-08-22 周六（纽约）时，
  币安侧 87 个中 83 个费率为 0、HL 侧大量钉在 `+0.0006%/h` 基线。UI 需能表达
  「这是休市读数」而非「数据坏了」。Human 2026-08-23 明示：**币圈不休息、休市反而可能
  出现高费率，因此 xyz 必须进第一版。**
- `[展示]` **表格行高翻倍**。现有表 15 列 870 行，四列加第二行后一屏可见标的数减半。
  缓解：默认开的显示开关。
- `[数据]` HL 标的漂移比币安快（xyz 半年内新增 101、下架 15）。exact 匹配 fail-closed
  意味着改名即静默消失，不会显示错值。
- `[成本]` 每次刷新增加 2 个 POST（实测 1.07 秒）。需确认不挤占既有 tick 预算。

## 8. 验收标准

1. `xyz:BB` 与 `xyz:QNT` 在 UI 上**不显示**任何 HL 数值（DENY 生效）。
2. `HYPE` 行显示 HL 第二行（证明未依赖 `predictedFundings` 的漏映射）。
3. 币安侧四列的数值与本 stage 前**逐格相同**（回归：现有算法零改动）。
4. 一个 4h 周期标的与一个 8h 周期标的的币安年化各自正确，未被统一成 8h。
5. HL 无对手的标的（`MNT`/`PURR`/`APEX`/`CASHCAT`/`kNEIRO` 等）第二行显示 `—`。
6. 关闭「显示 HL 对比行」开关后，表格回到本 stage 前的行高与内容。
7. HL 源请求失败时，四列首行（币安）**照常显示**，第二行降级为 `—`，不阻断快照发布。
8. `backend/tests/` 新增：DENY 排除、exact 匹配、1h 折算、HL 源缺失降级四类断言。
9. 前端 `self-check.js` 通过。

## 9. 决策点（待 Human 确认）

- **D1** 前四列范围与「结算时间」第二行用固定文案「每小时」——§1。
- **D2** 三列历史（近 24h/7D/30D）列为非目标，等第一版数据再评估——§2。
- **D3** 第一版不建别名表与乘数映射，14 个标的显示 `—`——§3。
- **D4** 不使用 `predictedFundings`——§5。
- **D5** 「显示 HL 对比行」开关默认开——§7。
