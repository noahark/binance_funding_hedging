# 四项问题摸排报告 + collateral-cap 死区修复记录

- 日期：2026-08-07
- 执笔模型：**claude-opus-5**（Claude Opus 5）
- 性质：P1/P2 为**已交付修复**（含测试）；Q1–Q4 为**摸排落档，未改代码**
- **状态（2026-08-08）**：Q1 已修复并实盘验证（见 PROJECT_STATE 的
  symbol-identity-unification 条目）；Q2/Q3 未处理；**Q4 已交付（2026-08-07 晚）**。
  本文 Q1「影响」第 2 条含一处已订正的错误表述，详见该处订正块。
- **Q4 最终形态与本文推荐方案不同（Human 2026-08-07 晚定稿）**：前端**零请求**，
  全部沿用后端 account 缓存快照——USDT 用账户级 `total_available_balance_usdt`、
  标签「可转」，其余币用 `cross_margin_free`、标签「可用」。
  `GET /api/private-account/max-withdraw` 端点保留在后端，但**无前端消费者**。
  **勿按本文 Q4 推荐方案（前端实时请求 maxWithdraw）实施**；权威记录见
  `PROJECT_STATE.md` Current Status 的 Q4 `[RESOLVED]` 条目。连带地，下文 L350
  「grep 零命中、尚未实现」与 L354「白名单未有 maxWithdraw」两处现状描述已过时
  （端点已实现、白名单已收录），正文不再逐处订正。
- 环境证据取自本地运行中的服务（`127.0.0.1:8787`，进程启动 01:19:37）与 `data/*.sqlite3`

---

## 摘要

| # | 问题 | 根因一句话 | 状态 |
|---|---|---|---|
| P1 | 开单任务 `preflight_incomplete` | 缓存生产 1800s vs 消费 600s 错配，每周期 20 分钟死区 | ✅ 已修 |
| P2 | 手动「更新缓存」对 cap 列表无效 | `force_account_panels` 不覆盖 `restricted_asset` | ✅ 已修 |
| Q1 | bStock 现货展示不匹配 | `_merge_base_asset` 只剥 USDT，不加 bStock 的 `B` 后缀 | ✅ 已修+实盘验证 |
| Q2 | 流水勾选「划转」不回显 | 显示上限 20 条 + 全局时间序，TRANSFER 排在第 33 位 | 📋 待修 |
| Q3 | 多任务卡同时启动回显异常 | 错误提示只写 DOM 不入 state，任何重渲染即抹除 | 📋 待修 |
| Q4 | 统一账户可转出额不准 | `cross_margin_free` 非最大可转出，缺 `maxWithdraw` 数据源 | ✅ 已交付（2026-08-07 晚） |

---

# 第一部分：已交付修复

## P1 — 开单任务卡在 `preflight_incomplete`

### 现象

任务 `b044f490-4d61-480b-8f5a-425aaef3ea05`（THEUSDT，正向，200×10）暂停：

```
pause_reason    = preflight_incomplete
pause_reason_zh = 预检数据不完整（collateral_cap），任务已暂停（fail-closed，未发单）；请检查网络后手动恢复
日志 payload     = {"failed_read": "collateral_cap"}   ×2（17:44:08Z / 17:44:20Z）
```

### 根因

`collateral_cap`（平台抵押额度清单）的生产端与消费端周期错配：

| 端 | 位置 | 周期 |
|---|---|---|
| 生产：SnapshotService | `snapshot_service.py:1387` `GROUP_B_REFRESH_SECONDS` | **1800s** |
| 消费：preflight | `hedge_preflight_provider.py:57` `_CACHE_MAX_AGE_RESTRICTED_ASSET` | **600s** |

该项是原设计中唯一 fail-closed 的缓存项：超龄即返回 `None`，不降级、不猜路由，整个 preflight 失败。于是**每个 30 分钟周期里只有前 10 分钟能开单，后 20 分钟必然失败**。

实测对齐：缓存 `checked_at = 17:32:22Z`，任务发起 `17:44:08Z`，龄期 **11分46秒 > 600s**。

后台观测确认了 1800s 周期真实存在：

```
17:32:22Z → 18:02:41Z     间隔 30 分 19 秒
```

补充事实：当时 `THE` 的 `exceeded=false`（并未被限额），这单本可正常成交，纯粹被超龄缓存挡住。

### 修法（已实施）

`hedge_preflight_provider.py` `_read_collateral_cap_hit`：缓存缺失/超龄/结构不符时**实时重读一次**，实时读也失败才 fail-closed。

```python
cached = self._cached_restricted_asset()
if cached is not None:
    exceeded = cached.get("exceeded")
    if isinstance(exceeded, set):
        return spot_base_asset in exceeded
    self._degrade_note("restricted_asset", "bad shape -> 实时重读")
else:
    self._degrade_note("restricted_asset", "stale/missing -> 实时重读")
return self._read_collateral_cap_hit_live(spot_base_asset)
```

**为什么这不违反原设计的安全意图**：task 05 要防的是「用**陈旧**列表猜路由 → 选错 regular_spot → 裸空头」。实时读返回的是交易所当前真值，不是陈旧数据，因此该不变量完好；被去掉的只是死区。`_read_collateral_cap_hit_live` 本就是 `snapshot_reader=None` 时的既有路径，非新增通路。

### 契约测试的调整

原 `test_restricted_asset_stale_fails_closed_no_realtime` 冻结了旧行为，已替换为三条更强的用例：

| 新用例 | 断言 |
|---|---|
| `..._stale_falls_back_to_realtime_never_uses_stale_list` | 缓存说 LINK 打满、实时说没打满 → 结果按**实时**走 papi_margin |
| `..._stale_and_realtime_failure_still_fails_closed` | 实时读也失败 → 仍 `None` + `last_failed_read == "collateral_cap"` |
| `..._missing_falls_back_to_realtime` | 冷启动无缓存 → 实时读，不再一直 fail-closed |

第一条正是「陈旧列表绝不参与路由决策」的直接断言——比原测试更严格。

---

## P2 — 手动「更新缓存」按钮对 cap 列表无效

### 现象（实测）

```
BEFORE 17:55:31Z   checked_at = 2026-08-06T17:32:22Z
POST /api/public-market/cache-refresh
  → {"published": true, "account_panels": "complete"}
AFTER  17:55:42Z   checked_at = 2026-08-06T17:32:22Z   ← 未变
```

按钮**报成功**，账户面板确实刷新了，但 `collateral_cap` 纹丝不动——点完再去 Start 照样失败。这是 P1 里最坑的一环：唯一看起来对症的自救手段是无效的，而中文提示还把人往「检查网络」引。

### 根因

`force_account_panels` 只放宽 `panel_fetchers` 那五个账户源的 due；`restricted_asset` 是 `snapshot_service.py:1387` 的独立分支，仍走 1800s due（代码注释 `:1297` 已明确列出它属于「keep existing due behavior」）。

### 修法（已实施）

```python
if self._restricted_asset_client is not None and (
    force_account_panels
    or self._source_due("restricted_asset", now, GROUP_B_REFRESH_SECONDS)
):
```

**已查证的关键点**：`panel_fetchers` 里的私有源必须传 `fetcher(force=True)` 才能驱逐各自传输缓存，否则放开 due 也只拿到副本；而 `restricted_asset` 走 `_get_apikey_only()` 直发，**无传输层缓存**，放开 due 即真实重读，无需额外驱逐参数。

新增测试 `test_force_refreshes_restricted_asset_despite_due`：冷启动读 1 次 → 未到 due 不读 → force 后读第 2 次。

### P1/P2 验证结果

```
pytest backend/tests/          1520 passed
node frontend/self-check.js    EXIT=0
```

两条修复均按「先写复现测试 → 确认红 → 改 → 确认绿」的顺序完成。

> ⚠️ **改动需重启服务生效**。未重启，以免打断可能在跑的任务。

---

# 第二部分：摸排结论（未改代码）

## Q1 — 对冲开单持仓 bStock 现货展示不匹配

### 结论：确认存在——展示失真 + `drift` 监控盲区（**非**裸腿风险，见下方订正）

### 证据链

数据库里 `SNXXUSDT` 有一个**活跃周期**（`closed_at_us` 为 NULL）。三方对照：

| 环节 | 值 | 是否正确 |
|---|---|---|
| 下单记录 `hedge_open_leg.request_shape` | `{"symbol": "SNXXBUSDT", "side": "BUY", ...}` | ✅ 带 B |
| 交易所真实持仓 `balances_spot` | `{"asset": "SNXXB", "free": "1.0", "value_usdt": "10.33"}` | ✅ 带 B |
| 持仓面板 `/api/hedge-open-positions` | `spot_balance: null` | ❌ **读不到** |

接口实际返回：

```json
{"coin":"SNXXUSDT","direction":"forward","spot_balance":null,
 "spot_balance_value_usdt":null,"single_leg_exposure":false,"drift":false}
```

### 根因

`hedge_open_tasks/domain.py:1649` `_merge_base_asset` 只剥 USDT 后缀：

```python
return symbol[:-4] if symbol.endswith("USDT") and len(symbol) > 4 else symbol
```

`"SNXXUSDT"` → `"SNXX"`，而现货资产名是 `"SNXXB"` → `spot_by_asset` 查不到 → null。

**下单侧是对的**：`normalize.py:87` `resolve_spot_leg` 正确实现了 `bstock_b_suffix_alias`（`TRADIFI_PERPETUAL` 且 `base+"B"+quote` 可交易时命中）。问题只在持仓合并这条路径没复用该规则。

快照中现存 bStock 示例：`SNXXUSDT→SNXXBUSDT`、`AXTIUSDT→AXTIBUSDT`、`AMATUSDT→AMATBUSDT`（`asset_tag=BSTOCK`、`contract_type=TRADIFI_PERPETUAL`）。

### 影响

1. 现货余额/估值列对所有 bStock 恒为「暂无」
2. `drift`（「实际现货少于记账」的告警）失效：它的判定含 `real_spot is not None`，
   现货余额恒 null ⇒ `drift` 恒 false ⇒ **bStock 上「操作员手动减少了现货腿」检测不到**。

> **订正（2026-08-07，本文档执笔模型自校）**：本条原写「`single_leg_exposure` 与 `drift`
> 二者恒 false ⇒ 裸空不报警」，**该表述有误**。核查 `_merge_build_row`：
> `single_leg_exposure = bucket is not None and spot_qty > 0 and perp_qty == 0`，
> 仅取自任务记账，**不读 `real_spot`**，因此不受本 bug 影响、一直正常工作。当时观察到
> SNXX 行该标记为 false，是因为那笔任务两腿都已成交，并非失配所致。受影响的只有
> `drift`。相应地，下方「优先级建议」中把 Q1 排第一的理由里「资金安全/裸空不报警」
> 一半不成立——Q1 的真实性质是**监控盲区 + 展示失真**，而非裸空风险。

### 推荐修法

`_merge_base_asset` 拿不到 `contract_type`，不能自行判断 bStock。两个方案：

**方案 A（推荐）— 组合根传入映射，domain 保持纯函数**

`server.py:_hedge_open_positions` 已持有 snapshot，其 rows 里带 `base_asset` 与 `spot.symbol`/`spot.match_type`。构造 `{contract_symbol: spot_base_asset}` 映射传入 `merge_positions`，匹配时优先查映射、回退现规则。

- 优点：不改 domain 纯度；数据源是同一份快照，与下单侧同源，不会漂移
- 注意：快照未就绪时映射为空 → 回退现行为（现状不变，不引入新失败态）

**方案 B — `_merge_base_asset` 增加候选集**

返回 `[base, base+"B"]` 候选，按序命中。改动更小，但会让非 bStock 的普通币也去试 `B` 后缀，存在误匹配风险（如某币恰好存在 `XXXB` 资产），且丢失了「只有 TRADIFI_PERPETUAL 才允许 B 别名」的既有约束。**不推荐**。

### 建议验收

用现存的 `SNXXUSDT` 活跃周期直接验证：修复后 `spot_balance` 应为 `1.00000000`、`spot_balance_value_usdt` 约 `10.33`。另需补一条单测覆盖 bStock 的 `drift` 判定（`single_leg_exposure` 不受本 bug 影响，见上方订正）。

---

## Q2 — 流水日志勾选「划转」不回显

### 结论：数据在、筛选逻辑对，是**显示上限 20 条**把它挤掉了

### 证据

库里确有 2 条 TRANSFER：

```
income_type | n  | earliest             | latest
COMMISSION  | 43 | 2026-08-06 04:06:07  | 2026-08-06 17:50:04
REALIZED_PNL| 18 | ...
FUNDING_FEE |  6 | ...
TRANSFER    |  2 | 2026-08-06 04:06:25  | 2026-08-06 04:06:29
```

接口按 `time_ms` 降序返回 69 行，TRANSFER 位于下标 **37/38**。前端 `frontend/index.html:6308`：

```js
const FLOW_LOG_DEFAULT_DISPLAY_LIMIT = 20;
function flowLogSliceLatest(rows, limit) {
  return list.slice(0, lim);      // 取前 20 条，不按类型保底
}
```

按真实数据模拟各勾选组合：

| 勾选 | 筛选后条数 | TRANSFER 下标 | 前 20 条中可见 |
|---|---|---|---|
| 默认(资金费+手续费) + 划转 | 51 | [33, 34] | **0 条 ★看不到★** |
| 再加已实现盈亏 | 69 | [37, 38] | **0 条 ★看不到★** |
| 只勾划转 | 2 | [0, 1] | 2 条 ✅ |
| 资金费 + 划转 | 8 | [4, 5] | 2 条 ✅ |

即：**在默认勾选基础上加勾划转**（最自然的操作路径）必然看不到；把其他类型全取消反而能看到。状态栏计数会从 49 跳到 51，但表格纹丝不动——正是「勾了没反应」的观感。

### 推荐修法

按代价从低到高：

1. **提高上限并让它可见**（最小）：`FLOW_LOG_DEFAULT_DISPLAY_LIMIT` 提到 100，并在状态栏已有的「筛选后共 N 条」旁明确提示「仅显示最近 20 条」——当前文案说了「显示最近 X 条」但 X 是**截断后**的数量，读起来像全部。
2. **每类型保底配额**（推荐）：截断时保证每个被勾选类型至少保留 k 条（如 5 条），再按时间填满剩余名额。勾选任一类型必定看到该类型数据，符合「勾选=我要看这个」的直觉。
3. **按类型分组展示**：右栏改为按 income_type 分组、组内各自截断。改动最大，但对稀疏类型（TRANSFER 这种一天 2 条）最友好。

建议取 2，并顺带把状态栏文案改成「显示最近 20 / 筛选后共 51 条」的明确对照。

---

## Q3 — 多个任务卡同时启动时交互回显异常

### 结论：确认存在。核心是**错误提示只写 DOM、未纳入 state**，任何一次重渲染即丢失

### 机制

`frontend/index.html:5652` 点击处理：

```js
btn.addEventListener('click', async () => {
  let result = null;
  if (action === 'start') result = await startHedgeTask(id);
  ...
  if (result) showHedgeTaskActionError(id, result.ok ? '' : result.error);
});
```

`showHedgeTaskActionError` 直接写 DOM：

```js
const el = document.getElementById(`hedge-task-error-${id}`);
if (el) el.textContent = msg || '';
```

而 `renderHedgeTasks()`（`:5424`）整体重建列表：

```js
els.hedgeTaskList.innerHTML = emptyCard + tasks.map(renderHedgeTaskCard).join('');
bindHedgeTaskControls();
```

重渲染由三类事件触发，每类都会清空所有卡的错误提示：

| 触发源 | 频率 |
|---|---|
| 本卡 `mutateHedgeTask`（乐观更新 1 次 + `loadHedgeTasks` 1 次） | 每次操作 2 次 |
| **他卡** `mutateHedgeTask` | 每个并发操作 2 次 |
| 自动刷新 tick（`:6288`，`AUTO_REFRESH_MS = 60000`） | 每 60 秒 |

### 四个可观察后果

1. **他卡操作抹掉本卡错误**：任务 A 启动失败显示错误 → 点任务 B 启动 → A 的错误消失。用户无从得知 A 失败了。
2. **60 秒后自愈式消失**：即使不做任何操作，一分钟内错误提示自动没了。
3. **点击无任何反馈**：按钮不禁用、无 loading 态。`mutateHedgeTask` 串行 4 个请求（POST + 3 GET），本地实测 GET 各 1.5–5.2ms，窗口虽小但用户仍会因「没反应」重复点击。
4. **请求与重渲染放大**：N 张卡并发 = **3N 个 GET + 2N 次全量 DOM 重建**（每次 mutate 都完整重拉 tasks/positions/attempts）。

另：并发的 `loadHedgeTasks()` 各自全量覆盖 `state.hedgeTasks`，后返回者覆盖先返回者，列表可能短暂显示过期状态。

### 推荐修法

1. **错误入 state**（根治）：`state.hedgeTaskErrors = {taskId: msg}`，由 `renderHedgeTaskCard` 渲染。重渲染不再丢失；清除时机改为该任务下一次操作成功或用户手动关闭。
2. **按钮 pending 态**：`state.hedgeTaskPending = Set<taskId>`，操作期间该卡按钮 disabled + 文案改「启动中…」。既给反馈又天然防重复提交。
3. **收敛 mutate 的刷新**：`mutateHedgeTask` 末尾三个串行 GET 改为按需——启动/暂停只需 `loadHedgeTasks()`；positions/attempts 交给既有 60s tick 或合并为一次防抖刷新。可把 N 卡并发的 3N 请求降到 N。

1 和 2 是必须的；3 是明显收益但可择期。

---

## Q4 — 统一账户「最多可转出」字段缺失

### 结论：确认。当前用 `cross_margin_free` 当可转出额，**代码注释里已承认不准，但未接入正确数据源**

### 三个数对不上

| 口径 | 值 | 来源 |
|---|---|---|
| 划转界面显示「可用」 | **393.21754168** | `balances_unified[USDT].cross_margin_free` |
| PM 账户可用余额 | **192.50874725** | `pm_account.total_available_balance_usdt` |
| 币安界面「最多可转出」 | **222.xx** | 用户观察 |

三者都不同，说明「最多可转出」是交易所侧独立计算的量，本地任何现有字段都推不出来。

参考同期 PM 数据：`account_equity=331.31`、`initial_margin=138.79`、`maint_margin=24.85`、`total_debt=246.58`。可转出受 uniMMR、抵押率、负债共同约束，非简单减法。

### 现状

`frontend/index.html:3377` 注释已写明：

```js
// cross_margin_free 是**可用额而非最大可划转额**：转出还要过账户 uniMMR /
// 抵押约束，交易所可能拒绝一笔看似在可用额内的划转，最终以服务端校验为准。
```

且 `evaluateTransfer` 用这个偏大的数做超额拦截：

```js
const remain = sub8(row.available, amount);
if (remain !== null && remain.startsWith('-')) { ...超出可用数量... }
```

⇒ 用户输入 300（< 393 通过前端校验，但 > 222 实际不可转），前端放行、交易所拒绝。属于**前端校验形同虚设**的一类：拦不住真正该拦的，只在极端值上拦。

### 数据源

代码全仓 grep `maxWithdraw|maxTransferable|max_withdraw` → **零命中**，尚未实现。

币安 PAPI 对应端点为 `GET /papi/v1/margin/maxWithdraw`（参数 `asset`，返回 `{"amount": "..."}`），与**已实现**的 `/papi/v1/margin/maxBorrowable` 属同族。

`private_client.py` 白名单（`:62`）已有 `maxBorrowable` 未有 `maxWithdraw`：

```python
("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
```

### 推荐修法

1. **白名单加一条** `("GET", "/papi/v1/margin/maxWithdraw"): "https://papi.binance.com"`。
2. **照搬 `fetch_max_borrowable` 的模式**新增 `fetch_max_withdraw(asset, *, force=False)`（`private_client.py:300` 附近）：同样的 `_cached_get` + `_evict(force)` + `PrivateEndpointError` 分类。该函数已处理「正业务码 → 确认 0」「负系统码 → unknown」的区分，可直接复用其形状。
3. **按需读取而非全量轮询**：只在划转面板选中资产时读该资产一次（对应 `maxBorrowable` 的 `force=True` 选中路径），避免给 60s tick 增加固定请求。
4. **前端字段与文案**：`transferAssetRows` 的 `available` 改用 `max_withdraw`；读不到时**显示「—」并放行**（保持既有「绝不把不知道显示成数字」的原则），不要回退到 `cross_margin_free` 假装准确。选项文案 `可用 X` 改为 `最多可转出 X`。
5. **保留服务端为最终裁判**：前端校验只作为提前提示，`asset-transfer` 后端四态结论不变。

### 风险提示

按 `binance-papi-contract-traps` 的教训，**上线前必须实测确认该端点的真实返回形状**（字段名、是否需要 `isolatedSymbol`、错误码正负号），不要照文档假设。建议先只读打点一轮，与币安界面的 222.xx 对齐后再接入 UI。

---

## 附：优先级建议

| 序 | 项 | 理由 |
|---|---|---|
| — | ~~**Q1**~~ | **已完成**。原排第一的理由「唯一带资金安全性质（裸腿检测失效）」经订正**不成立**——真实性质是展示失真 + `drift` 盲区。即便如此仍值得先做：它是当时唯一有活跃周期正暴露其中的项 |
| 2 | **Q4** | 前端校验放行不可执行的划转，误导性强；但有服务端兜底，不会造成错误成交 |
| 3 | **Q3** | 高频交互缺陷，失败信息静默丢失会掩盖真实错误（含 P1 那类暂停原因） |
| 4 | **Q2** | 纯展示，有 workaround（只勾划转即可看到） |

Q1 与 Q3 有耦合：Q1 修好后 `drift` 才会真实报警（`single_leg_exposure` 本就正常，见上方订正），而该报警要在 UI 上稳定可见又依赖 Q3 的错误/状态入 state。建议同批处理。
