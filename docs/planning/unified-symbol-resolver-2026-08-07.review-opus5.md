# 评审：统一现货符号解析器（d717595）

- 日期：2026-08-07
- 评审模型：**claude-opus-5**（Claude Opus 5）
- 被评审对象：commit `d717595` + `docs/planning/unified-symbol-resolver-2026-08-07.md`
- 触发：本模型 `issue-triage-2026-08-07.opus5.md` Q1

## 判定：**REWORK**

方案主体设计良好，1000x 支持与 asset_map 注入均正确且有测试。但 §4.2「放开 TRADIFI gate」引入一个**贯穿开单/预检/展示/平单全链路的资金安全级误配**，且该变更的唯一举证动机在实施过程中已被作者自己证伪。其余部分建议保留。

---

## 一、阻断级缺陷：合约 `B` 被解析到 `BB`(BounceBit) 的现货对

### 实证

用仓内 exchangeInfo 样本（`reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/`）对全部 **776 个 USDT 合约**跑新旧规则对比：

```
=== 新增命中：B 后缀别名（非 TRADIFI）——放开 gate 的全部影响面 ===
   合约 BUSDT   ctype=PERPETUAL   base=B   旧=None → 新=BBUSDT (bstock_b_suffix_alias)
   小计: 1

=== 新增命中：1000x 剥离 ===
   1000SHIB/1000XEC/1000LUNC/1000PEPE/1000FLOKI/1000BONK   小计: 6

=== 回归丢失（新版解析不到而旧版能）=== 0
```

放开 gate 的**全部**收益面是 1 条，而这 1 条是错的：

| | 合约 | baseAsset | 现货 | 现货 baseAsset |
|---|---|---|---|---|
| 用户想对冲 | `BUSDT` | **`B`** | 无同名现货对 | — |
| 规则解析到 | — | — | `BBUSDT` | **`BB`**（BounceBit） |

`B` 和 `BB` 是两个都在 TRADING 的独立币种（样本中合约侧 `BUSDT`/`BBUSDT` 并存，baseAsset 分别为 `B`/`BB`）。

复现（当前 HEAD 代码）：

```python
spot = {'BBUSDT': {'symbol':'BBUSDT','baseAsset':'BB','status':'TRADING'}}
resolve_spot_leg('PERPETUAL', 'B', 'USDT', spot)
# → ({'symbol':'BBUSDT','baseAsset':'BB',...}, 'bstock_b_suffix_alias')
# 期望 (None, None)
```

### 影响路径（全链路，非仅展示）

`_spot_alias_candidates` 同步放开了 gate，因此误配不止于展示：

1. **开单**：`_read_spot_filters_with_alias` 候选 `[BUSDT, BBUSDT]` → 探测到 `BBUSDT` → 现货腿 filters 取自 BounceBit → **现货腿会真实下单买 BB**，而合约腿开的是 B 的空单 ⇒ 两个币各自裸敞口，完全没有对冲
2. **预检**：`check_symbol_legs` 把 B 误判为「有现货腿」，本该拦下的标的被放行
3. **展示**：用 BB 余额匹配 B 持仓
4. **平单**：划转/利息资产名取 `BB`

### 为什么作者的安全论证不成立

方案 §4.2 称「误配被『exact 优先 + TRADING 真值确认』双重约束」。在本例中两个约束**都通过了**：

- exact `BUSDT` 现货确实不存在 ⇒ 正常进入别名分支
- `BBUSDT` 确实 `TRADING` ⇒ 别名正常命中

两条约束都不针对「别名指向的是不是同一个资产」，因此无法阻止此类冲突。

### 补救方案的可行性验证

考虑过增加「候选现货的 `baseAsset` 必须等于 `base + "B"`」这一校验，实测**无效**：

```
合约base  现货base   base+"B"   该校验
SNXX     SNXXB     SNXXB      放行 ✓
MU       MUB       MUB        放行 ✓
B        BB        BB         放行 ✗ ← B+"B" 恰好等于 "BB"
```

字符串层面无法区分。可靠的区分特征只有 `contractType == TRADIFI_PERPETUAL`——这正是原 gate。

### 关键：放开 gate 的动机已被作者自己证伪

方案 §4.2 举的唯一实例是 `MUUUSDT`。而作者在 §7「实施中发现的事实修正」里已查明：

> 真实合约是 **MUUSDT**（TRADIFI_PERPETUAL，baseAsset=MU）…**且它是 TRADIFI，原 gate 本可覆盖，展示侧失配才是根因**

本次评审独立复核，确认此结论正确（样本中 `MUUSDT` 的 `contractType` 为 `TRADIFI_PERPETUAL`）。

⇒ **收益 = 0**（全部真 bStock 在旧 gate 下已正常解析，扫描的「新增命中」里不含任何 SNXX/AXTI/AMAT/MU）
⇒ **代价 = 1 个真实资金安全误配**

作者发现动机不成立后，仍保留了 gate 放开，属逻辑不一致。

### 建议修法

**恢复 `TRADIFI_PERPETUAL` gate**（`normalize.py:resolve_spot_leg` 与 `hedge_preflight_provider.py:_spot_alias_candidates` 两处）。MU 案例的真实根因是展示侧失配，已由本 commit 的 asset_map 独立修好，与 gate 无关。

配套测试调整：
- `test_resolve_spot_leg_bstock_alias_for_perpetual_when_tradable`（虚构 `FOO`）应删除或反转为「普通 PERPETUAL 不触发别名」
- **新增真实冲突用例**（当前缺失，是 1529 passed 未能发现此缺陷的原因）：

```python
def test_resolve_spot_leg_must_not_alias_b_to_bounce_bit():
    # 真实冲突：合约 BUSDT(baseAsset=B) 与现货 BBUSDT(baseAsset=BB, BounceBit)。
    # base+"B"+quote 恰好撞上另一个币，字符串层面不可区分 —— 只能靠 TRADIFI gate。
    spot = {"BBUSDT": {"symbol": "BBUSDT", "baseAsset": "BB", "status": "TRADING"}}
    obj, mt = resolve_spot_leg("PERPETUAL", "B", "USDT", spot)
    assert obj is None and mt is None
```

---

## 二、评审方对自己 Q1 报告的更正

`issue-triage-2026-08-07.opus5.md` Q1「影响」第 2 条称 bStock 失配会导致 `single_leg_exposure` 失效、裸空不报警。**该表述有误，特此更正。**

核查 `_merge_build_row`（`domain.py:1793`）：

```python
spot_qty = _merge_num(row.get("spot_qty")) or Decimal(0)
perp_qty = _merge_num(row.get("perp_qty")) or Decimal(0)
row["single_leg_exposure"] = bucket is not None and spot_qty > 0 and perp_qty == 0
```

`single_leg_exposure` 仅取自任务记账（`spot_qty`/`perp_qty`），**不读 `real_spot`**，因此不受 base_asset 解析影响，bStock 上一直正常工作。当时观察到 SNXX 行 `single_leg_exposure: false`，是因为该任务两腿都已成交，而非失配所致。

真正受影响的只有 `drift`：

```python
row["drift"] = (recorded_spot is not None and recorded_spot > 0
                and real_spot is not None and real_spot < recorded_spot)
```

`real_spot` 为 `None` 时 `drift` 恒 `False` ⇒ **bStock 上「操作员手动减少了现货腿」检测不到**。这仍是真实缺陷，但严重性低于原报告表述（属监控盲区，不是裸空不报警）。Q1 的优先级建议相应下调，但仍应修复。

---

## 三、认可保留的部分

| 项 | 评价 |
|---|---|
| 1000x 剥离 | **正确**。扫描确认恰好命中 SHIB/XEC/LUNC/PEPE/FLOKI/BONK 六个，与既有 follow-up 记录的清单完全一致；`exact` 优先于 strip 有测试保护（`test_..._multiplier_exact_beats_strip`）；只剥字面 `1000` 不做通用数字剥除，克制得当 |
| asset_map 注入 | **设计正确**。映射由组合根构造、domain 保持纯函数，符合 ADR-001；缺失时回退旧规则，不引入新失败态 |
| 数量域论证（§6） | **经核实成立**。`drift` 比较的是 `spot_qty`（现货买入量）vs `real_spot`（现货余额），1000BONK 合约的现货腿本就是 BONK，同域，确实无需乘数换算 |
| 平单环消费落库真值 | **方向正确**。复用开单时 `resolve_spot_leg` 的结果而非重新发明规则，符合单一真值源 |
| 回归面 | 扫描确认 **0 条丢失** |
| schema 处理 | `spot.base_asset` 设为可选、不进 required，向后兼容旧校验数据，稳妥 |

---

## 四、次要观察（非阻断）

1. **asset_map 冷启动闪烁**：快照未就绪时 map 为空 ⇒ bStock 回退到错误 base ⇒ `drift` 会在「快照就绪/未就绪」之间跳变。回退策略本身合理（不引入新失败态），但建议 `drift` 在 base 来源不可信时输出「未知」而非 `False`，避免风险标记假阴性。

2. **`server.py:1024` 可能写入 `None` 键**：`asset_map[_r.get("symbol")] = ...` 未校验 symbol 非空。实际无害（`None` 键不会被真实 coin 命中），但建议与值一样做 truthy 校验。

3. **`service.py` 调用私有函数**：平单环回退分支调用 `D._merge_base_asset`（下划线前缀）。既有代码已有此模式（`server.py` 同样调用），非本次引入，可留作后续清理。

4. **文档 §7 与代码不一致**：§7 已记录「MU 是 TRADIFI，原 gate 本可覆盖」，但 §4.2 的行为变更声明未相应撤回。修复 gate 后需同步订正这两节。

---

## 五、复核清单（修复后）

- [ ] `resolve_spot_leg` 恢复 TRADIFI gate；`_spot_alias_candidates` 同步
- [ ] 新增 `B`→`BB` 真实冲突用例，确认拦截
- [ ] 重跑 776 合约扫描：`newly_b` 应为 **0**，`newly_mult` 仍为 **6**，`lost` 为 **0**
- [ ] 用现存 `SNXXUSDT` 活跃周期验证 `spot_balance` = `1.00000000`、`spot_balance_value_usdt` ≈ `10.33`
- [ ] 补 bStock 的 `drift` 判定用例（当前 asset_map 路径无 drift 专项覆盖）
- [ ] 方案文档 §4.2 与 §7 订正

---

---

# 实施记录（2026-08-07，Human 拍板：改用显式映射表）

评审提出的修法是「恢复 TRADIFI gate」。Human 提出更彻底的方向——**把特殊匹配做成固定映射表，查不到就用原 symbol**——并授权实施。已按此落地。

## 为什么表优于恢复 gate

两者都能消除 `B`→`BB`，但失败模式不同，这是决定性的：

| | 失败模式 | 后果 |
|---|---|---|
| 规则（含 gate） | **fail-open**：规则外的新命名会被猜中 | 可能下单到错误的币 |
| 表 | **fail-closed**：未收录即无现货腿 | 该标的不可对冲，不会错腿 |

对冲下单链路上，「宁可没有腿，不可要错腿」。表是唯一能表达「B 这个币没有现货腿」的结构——任何字符串规则都推不出这个结论。

## 实测数据（2026-08-07 最新 exchangeInfo）

评审时基于 7-03 样本估算表约 21 行，**实测为 71 行**，且增长很快：

| | 2026-07-03 样本 | 2026-08-07 实测 |
|---|---|---|
| TRADIFI 合约 | 118 | 152 |
| 其中有现货腿（进表） | 15 | **65** |
| 乘数映射（进表） | 6 | 6 |
| 无现货腿（不进表） | 103 | 248 |

一个月内 bStock 可对冲标的从 15 涨到 65。**这是纯表方案的主要代价**，已用生成脚本 + CI 校验抵消（见下）。

顺带发现旧规则的第二个缺陷：`base[4:]` 硬剥 4 字符，对 `1000000MOG`/`1000000BOB` 会剥成 `000MOG`。当前因这些币无现货对而侥幸没暴露，规则本身是错的。新的生成脚本按前缀长度降序匹配（`1000000`→`100000`→`10000`→`1000`）。

## 改动清单

| 文件 | 改动 |
|---|---|
| `backend/domain/normalize.py` | 新增 `SPOT_SYMBOL_MAP`（71 条）+ `SPOT_SYMBOL_DENY`；`resolve_spot_leg` 改为 `exact → 查表 → (None, None)`，删除全部字符串猜测 |
| `backend/services/hedge_preflight_provider.py` | `_spot_alias_candidates(coin)` 改为查同一张表（签名去掉不再需要的 `perp_symbol`），三处调用点同步 |
| `scripts/check-spot-symbol-map.py` | 新增：`--emit` 生成表字面量、`--verify` 校验（退出码 0/1） |
| `backend/tests/test_normalize.py` | 删除断言猜测规则的虚构 `FOO` 用例；新增 `B`→`BB` 拦截、表外不猜、表形状不变量、deny/map 不重叠、实盘标的覆盖 |

`SPOT_SYMBOL_DENY` 记录已人工确认「形似现货对属于别的币」的合约（当前只有 `BUSDT`），仅供校验脚本消费，使其不把同一条反复报成待确认项。解析器不需要它——表里没有就是没有。

## 维护流程

```bash
python scripts/check-spot-symbol-map.py --verify   # 定期/CI：退出码 0=一致
python scripts/check-spot-symbol-map.py --emit     # 有 MISSING 时重新生成，粘回 normalize.py
```

`--verify` 报三类问题：`STALE`（表内映射的现货已下架）、`MISSING`（新上架标的未收录，该标的当前无法对冲）、`SUSPECT`（非 TRADIFI 却存在 `base+"B"` 现货对——**绝不自动收录**，必须人工确认）。

表由脚本生成而非手敲，新增标的的操作是「跑脚本 → 粘贴」，不是人肉比对。

## 验证

```
pytest backend/tests/                             1533 passed
node frontend/self-check.js                       EXIT=0
check-spot-symbol-map.py --verify                 退出码 0（71/71 一致，已确认拒绝 1 条）
```

端到端解析（最新交易所数据）：

```
SNXXUSDT       base=SNXX        -> SNXXBUSDT   base=SNXXB   bstock_b_suffix_alias
THEUSDT        base=THE         -> THEUSDT     base=THE     exact_symbol
1000BONKUSDT   base=1000BONK    -> BONKUSDT    base=BONK    multiplier_strip_alias
MUUSDT         base=MU          -> MUBUSDT     base=MUB     bstock_b_suffix_alias
BUSDT          base=B           -> None                     ← 误配已消除
1000000MOGUSDT base=1000000MOG  -> None                     ← 现货确实不存在
```

## 保留自 d717595 的部分

asset_map 组合根注入、快照 `spot.base_asset` 字段、平单环消费落库真值、schema 的可选字段与 enum 扩展——均未改动，评审认可的设计全部保留。被替换的只有「字符串猜测」这一层。

## 对 d717595 方案文档的影响

`unified-symbol-resolver-2026-08-07.md` 的下列内容已被取代，建议标注：

- §1「**不做**静态 map/枚举表」——已推翻。该判断基于「几百个合约无法维护」，但例外表只需 71 行且由脚本生成
- §2 候选链表格与 §4.2「放开 TRADIFI gate」——规则已整体移除
- §7 第 1、6 条实施描述

---

## 附：与本模型 P1/P2 修复的关系

方案 §7 提到两者同处工作树。经核对，`hedge_preflight_provider.py` 上两处改动区域不重叠（本 commit 改 `_spot_alias_candidates` 与两处调用点，P1 改 `_read_collateral_cap_hit` 及其 docstring），无冲突。P1/P2 的测试在本 commit 后仍全绿（1529 passed 已包含）。
