# 统一现货符号解析器改造方案（Q1 开单/平单/展示三环合一）

- 日期：2026-08-07
- 性质：设计方案 + 实施记录（Human 直接指示，无 dispatch 包）
- 触发：`docs/planning/issue-triage-2026-08-07.opus5.md` Q1 + Human 要求支持 `BONK`（现货）/ `1000BONK`（合约）类标的

---

## 1. 背景与目标

「合约符号 → 现货符号 / 现货 base asset」的映射目前在三个环节各自实现，规则不一致：

| 环节 | 现状 | 问题 |
|---|---|---|
| 开单 / 预检 / 快照 | `normalize.py:resolve_spot_leg`（规则 + 交易所真值确认，`exact` → bStock `B` 后缀） | 已是共享解析器；不认识 1000x；B 后缀被 gate 在 `TRADIFI_PERPETUAL` |
| 平单（close） | `service.py:1634/1731` 用 `_merge_base_asset(coin)` 剥 USDT | bStock（SNXXUSDT→SNXX，实际资产 SNXXB）与 1000x（1000BONKUSDT→1000BONK，实际 BONK）都会用错资产名查余额/划转/算利息 |
| 展示（merge） | `hedge_open_tasks/domain.py:_merge_base_asset` 只剥 USDT | 不认 B 后缀、不认 1000x → `spot_balance`/`unified_balance`/`drift` 失配（Q1；MUUUSDT 挂账案例同源） |

**目标**：单一解析器 + 各环节消费同一份「交易所真值」，支持三类映射：
- 普通：`BTCUSDT` ↔ 现货 `BTCUSDT`（base `BTC`）
- bStock：`SNXXUSDT` ↔ 现货 `SNXXBUSDT`（base `SNXXB`）
- 乘数：`1000BONKUSDT` ↔ 现货 `BONKUSDT`（base `BONK`）

**不做**：静态「每标的一行」的 map/枚举表（几百个合约无法人肉维护、新币上架要发版、表达不了同名冲突）。枚举的正确用途是 `match_type` 常量（跨环节一致引用 + 测试断言）。

## 2. 设计：扩展 `resolve_spot_leg` 候选链

候选按序试配，每个候选必须过 `_tradable_spot`（现货 `status == "TRADING"`）才命中；顺序即优先级：

| 序 | 候选（现货交易对符号） | `match_type` | 说明 |
|---|---|---|---|
| 1 | `base + quote` | `exact_symbol` | 普通币；也保证「恰好存在同名现货」时优先 |
| 2 | `base + "B" + quote` | `bstock_b_suffix_alias` | **放开 TRADIFI gate 到所有合约类型**（见 §4.2 行为变更） |
| 3 | base 以字面 `"1000"` 开头：`base[4:] + quote` | `multiplier_strip_alias` | 只剥字面 `1000`，不做通用数字剥除 |

候选 4（剥 1000 后再试 `+B`，即 `1000XXXB`）**不做**——币安不存在 1000x bStock，无证据不做（YAGNI），方案记录在案。

`normalize.py` 新增模块级字符串常量（项目风格与 `D.TASK_TYPE_OPEN` 一致）：

```python
SPOT_MATCH_EXACT      = "exact_symbol"
SPOT_MATCH_BSTOCK     = "bstock_b_suffix_alias"
SPOT_MATCH_MULTIPLIER = "multiplier_strip_alias"
```

返回形状不变：`(spot_obj | None, match_type | None)` → 开单/预检/快照三处既有调用方**零改动**。

## 3. 各环节接入

### 3.1 开单 / 预检 / 快照（normalize.py → 自动覆盖）

`resolve_spot_leg` 扩展后，`hedge_preflight_provider.py:435`、`snapshot.py:215` 自动获得 1000x 能力（现货腿正确解析为 `BONKUSDT`，`spot.get("baseAsset") == "BONK"`）。

**快照输出增量**：`snapshot.py` rows 的 `spot` block 增加 `"base_asset"` 字段（`spot.get("baseAsset")`，即已解析的现货真值，如 `SNXXB` / `BONK`），供展示环复用。纯增量字段，前端/self-check 不受影响。

### 3.2 平单（service.py close 路径）

`_ensure_close_spot_balance`（:1634）与 `_finalize_close` 利息统计（:1731）改为**消费开单时已解析并落库的真值**：

```python
spot_sym = D.spot_order_symbol(task["coin"], task.get("preflight_snapshot"))
if isinstance(spot_sym, str) and spot_sym.endswith(D.QUOTE_ASSET):
    base_asset = D.base_asset(spot_sym)      # SNXXBUSDT -> SNXXB, BONKUSDT -> BONK
else:
    base_asset = D._merge_base_asset(task["coin"]) or task["coin"].replace("USDT", "")
```

`task.preflight_snapshot.spot_symbol` 是开单时 `resolve_spot_leg` 的真值（已随任务落库，`spot_order_symbol` 即为此设计），平单环直接消费，不重新发明规则。

### 3.3 展示（merge 层 + server.py 组合根）

- `merge_positions(positions, private_account, asset_map=None)`：新增可选参数 `asset_map: {coin: base_asset}`（来自快照 rows 的 spot.base_asset 真值）。
- `_merge_build_row` 的 base_asset 解析：`asset_map.get(coin) or _merge_base_asset(coin)`——快照就绪时有真值，未就绪/无 spot 时回退现状（不引入新失败态）。
- `server.py:_hedge_open_positions`（组合根，已持有 snapshot）：构造 `asset_map = {r["symbol"]: r["spot"]["base_asset"] for r in rows if r.get("spot", {}).get("base_asset")}`，传入 merge；周期统计（:1085）的 base_asset 同样改用 asset_map。
- domain merge 保持纯函数（映射由组合根注入），符合 ADR-001。

## 4. 行为变更声明（评审/Bookkeeper 须知）

### 4.1 1000x「诚实不对齐」→ 快照真值对齐

`_merge_base_asset` 原设计「1000PEPEUSDT 不对齐 PEPE」是 non-goal #5（`02-scope-decisions.md §2.3`），并被 `test_positions_merge.py:73/333` 冻结。Human 明确要求支持 BONK → **推翻该决策**：asset_map 提供时 1000x 对齐，不提供时仍回退现规则（测试环境/离线场景行为不变）。

### 4.2 B 后缀别名从 `TRADIFI_PERPETUAL` 放开到所有合约

`test_normalize.py:113` 冻结的「普通 PERPETUAL 不触发 B 别名」随之更新。安全性论证：误配被「exact 优先 + TRADING 真值确认」双重约束，币安现货 `base+"B"` 命名即 bStock/代币化惯例；顺带解决 PROJECT_STATE 挂账的 **MUUUSDT → MUBUSDT 案例**（2026-08-05 记录）。

## 5. 测试计划（先红后绿）

- `test_normalize.py`：新增 1000x 剥离用例（BONK）；更新 :113 为「PERPETUAL 的 B 后缀可命中且 exact 优先」。
- `test_snapshot.py`：1000x resolve + `spot.base_asset` 字段断言。
- `test_positions_merge.py`：`:73/333` 1000x 用例改为「asset_map 提供时对齐」；新增 bStock（SNXXB）/ 1000x（BONK）asset_map 对齐 + 无 asset_map 回退 + 周期统计 base 用例。
- `test_hedge_api.py`：merge wire 若断言 base 相关字段，同步核对。

## 6. 范围外（记录不实现）

- multiplier 数量换算：drift / single_leg 比较的是任务记录的**现货买入量** vs 现货余额，同数量域（现货腿本来就是 BONK），无需换算；未来若做「合约名义 vs 现货余额」对冲完整性检查才需要 `1000BONK 合约 1 个 = BONK 现货 1000 个`。
- MUU 开单侧验证：MUU 案例仅展示侧实测过；放开 gate 后开单侧规则已覆盖，但无实盘证据，留待真单验证。
- `02-scope-decisions.md §2.3` 文档修订：列为后续项（本次以本方案 + 代码注释为准）。

## 7. 实施结果（2026-08-07，Human 直接指示）

**已实施**：

1. `normalize.py`：`resolve_spot_leg` 候选链扩展为 `exact_symbol → bstock_b_suffix_alias（放开 TRADIFI gate）→ multiplier_strip_alias（字面 1000 剥离）`，全部过 TRADING 真值确认；新增三个 `SPOT_MATCH_*` 常量。
2. `snapshot.py`：rows `spot` block 新增 `base_asset` 字段（resolve 后的现货真值，如 `SNXXB`/`BONK`）。
3. `hedge_open_tasks/domain.py`：`merge_positions(..., asset_map=None)` + `_merge_build_row` 用 `asset_map.get(coin) or _merge_base_asset(coin)`（纯函数不变，映射由组合根注入）。
4. `server.py` `_hedge_open_positions`：从 snapshot rows 构造 asset_map 传入 merge；周期统计 base_asset 同样优先 asset_map。
5. `service.py` 平单环两处（`_ensure_close_spot_balance` 划转资产名、`_finalize_close` 利息资产名）：消费开单时落库的 `preflight_snapshot.spot_symbol` 真值取 baseAsset，无快照回退旧规则。
6. `hedge_preflight_provider.py`：`_bstock_spot_alias` 替换为 `_spot_alias_candidates`（B 后缀 + 1000x 剥离，与 resolve_spot_leg 候选链一致），开单 filters 读取与 `check_symbol_legs` 探测两处同步扩展。
7. schema：`spot.base_asset` 字段（**可选**，不进 required，向后兼容旧校验数据）；`match_type` enum 增 `multiplier_strip_alias`。

**实施中发现的事实修正**：PROJECT_STATE 挂账的「MUUUSDT」为笔误——exchangeInfo 样本（`reports/agent-runs/2026-07-public-market-bstock-alias-v1`）确认真实合约是 **MUUSDT**（TRADIFI_PERPETUAL，baseAsset=`MU`），`MU+"B"+"USDT" = MUBUSDT` 完全符合 base+"B" 规则；且它是 TRADIFI，原 gate 本可覆盖，展示侧失配才是根因。真实案例已加测试 `test_resolve_spot_leg_bstock_alias_mu_case`。

**测试**：后端全量 1529 passed（原 1520 + 新增/更新 9 项）；`frontend/self-check.js` EXIT=0。

**未实施 / 遗留**：P1/P2 修复（opus5 2026-08-07 报告）仍在工作树未提交、服务未重启；本次改动与 P1/P2 改动同处工作树（`hedge_preflight_provider.py` 同文件不同区域），提交时需按 hunk 区分。
