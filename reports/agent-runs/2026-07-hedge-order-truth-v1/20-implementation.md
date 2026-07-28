# 20-implementation — hedge-order-truth-v1（执行报告）

执行指令：`reports/agent-runs/2026-07-hedge-order-truth-v1/13-implementation.dispatch.md`
执行者：Claude-GLM（backend 唯一执行者）
基线 commit：`9e50228 chore(hedge): set file boundaries and prepare the implementation dispatch`
本地时间：2026-07-28 18:52 CST

> 实盘交易界面处于开启状态（服务 PID 96409 live 模式，Start gate 开，存在真实 SHORT 10000 NOMUSDT）。本阶段全程未发任何真实 POST、未触 Start、未访问凭据、未启动/停止服务、未写生产库、未 commit。所有测试离线确定性（fake urlopen / fake executor / 临时 SQLite）。

---

## 0. 关键状态修正（评审必读）

dispatch 把 W1–W6 列为本阶段顺序步骤。但以 `git diff HEAD`（HEAD = `9e50228`）实测核对，**W1（T2 分类）、W2（T5 时间戳守卫）、W3（T3 raw 表 + 服务层 raw 捕获）的代码在基线 commit `9e50228` 之前已实现并落盘**：

- `9e50228` 本身只改了 `13-implementation.dispatch.md` 与 `status.json`（2 文件，316 行，无代码）。
- HEAD 的 `domain.py` 已含 `classify_exchange_code` + `MARGIN_BUSINESS_CODES`（`51169 → collateral_cap`）+ `build_leg_exposure` 的 `ts_us <= 0` 守卫。
- HEAD 的 `store.py` 已含 `hedge_open_raw_response` 表（4 处引用）。
- HEAD 的 `test_hedge_task_local.py` 已含 `test_4d`（W2 时间戳）、`test_4e/4f/4g`（W3 raw 捕获/隔离）。
- `domain.py`、`test_hedge_task_local.py`、`test_hedge_service.py`、`test_hedge_domain.py` 相对 HEAD **零改动**（`git diff --stat HEAD` 不含这四个文件）。

因此本阶段**工作区实际新增的代码**集中在 **W4（T1 成交数据来源）+ W5（ADR-T6 历史数据迁移）+ W6（preflight 键名契约测试）**，外加为支撑 T1 NULL 合约而对 store schema / `_leg_final_fields` / `aggregate_positions` 的收紧。改动共 7 个文件：

```
 backend/hedge_open_tasks/service.py       |  34 ++++-
 backend/hedge_open_tasks/store.py         | 227 +++++++++++++++++++++++++++---
 backend/services/live_hedge_executor.py   | 207 +++++++++++++++++++++++----
 backend/tests/test_hedge_api.py           |   1 +
 backend/tests/test_hedge_executor.py      |  61 ++++++++
 backend/tests/test_hedge_store.py         | 118 ++++++++++++++++
 backend/tests/test_live_hedge_executor.py |  99 +++++++++++++
 7 files changed, 687 insertions(+), 60 deletions(-)
```

下文按 dispatch 的 W1–W6 框架陈述，对 W1–W3 标注「基线已就位 / 工作区无改动 / 测试通过」，对 W4–W6 详述实际改动。

---

## 1. 各步做了什么

### W1 — T2 分类重构（基线已就位，本阶段工作区无代码改动）

`classify_exchange_code(product, code, msg)`（`domain.py:432`）两层分类在基线已实现，本阶段未修改任何分类表或判定函数：

- `AUTH_AMBIGUOUS_EXCHANGE_CODES`（`-1000/-1021/-1022/-1099/-2011/-2014/-2015/-2017/-2018`）→ `auth`
- `is_insufficient_funds_code`（`-2019/-3041` 无条件；`-2010` 需消息确认）→ `insufficient_funds`
- `FATAL_EXCHANGE_CODES`（`-2010` 未确认 / `-1013` / `-1100…` 系列）→ `fatal`
- `MARGIN_BUSINESS_CODES = {"51169": collateral_cap}`；`UM_BUSINESS_CODES = {}`
- 兜底：`code is None → None`（NULL）；有 code 无规则 → `unclassified`

`live_hedge_executor.classify_leg_response` / `classify_query_response` 在基线已调用 `D.classify_exchange_code` 并把 `error_category` 透传到 `LegDispatch`。`git diff HEAD -- backend/services/live_hedge_executor.py` 中**无任何 classify / error_category / collateral_cap / 51169 相关 hunk**。运行 `test_hedge_task_local.py` 中 51169 相关用例通过。

### W2 — T5 时间戳统一（基线已就位，本阶段工作区无代码改动）

`build_leg_exposure` 的 `ts_us <= 0` 守卫（`domain.py:1038-1039`，`raise invalid_field(...)`）在基线已实现。`test_4d_live_single_leg_exposure_timestamp_is_settlement_wall_clock` 在基线已存在并通过。`domain.py` 相对 HEAD 零改动。

### W3 — T3 raw 持久化（基线已就位 + 本阶段为 T1 扩展 confirm 源）

基线已含 `hedge_open_raw_response` 表与 `service._persist_leg_raw`，以及 `test_4e/4f/4g`（51169 POST raw、drain query raw、raw 失败隔离）。

本阶段为 T1 的 UM inline-confirm GET 增加第三种 raw 来源（W4 的一部分，见下）：

- `LegDispatch.confirm_raw_response: Optional[dict]`（`live_hedge_executor.py`，新增字段）。
- `service._dispatch_live` 在 perp POST raw（`source="order_post"`）之后追加 `_persist_leg_raw(..., "order_confirm", perp.confirm_raw_response, ...)`（`service.py` diff）。
- 三次交互（两腿 POST、UM confirm GET、drain query GET）现在用 `source ∈ {order_post, order_confirm, order_query}` 区分；raw 持久化失败仍走既有 `raw_persist_failed` 事件，与业务写控制流隔离（未改）。

### W4 — T1 成交数据来源（本阶段核心）

币安 2026-07-14 变更后 UM POST RESULT body 不再携带 `cumQuote/avgPrice/cumBase`（仅余 `orderId/status/executedQty`）；margin POST RESULT 仍携带 `cummulativeQuoteQty`。T1 按产品分流成交金额来源：

**`live_hedge_executor.py`（+207/-60）：**

- 新增 `FILL_FIGURES_SOURCE = {"spot": "post_response", "perp": "order_detail_query"}`。
- 新增 `_post_figures(body, leg)`：margin 腿从 POST RESULT 读 `cummulativeQuoteQty`；UM 腿 POST 仅证明 acceptance，`quote=None`（不取金额）。
- 新增 `_query_figures(body, leg)`：margin 读 `cummulativeQuoteQty`；UM 读 `cumQuote`，回退 `cummulativeQuoteQty`。
- `LegDispatch.cumulative_quote: str → Optional[str]`（NULL 合约：NULL=未知，`"0"`=真零，永不把缺失强转为 0）。
- `_empty_dispatch` / `_error_leg` 的 `cumulative_quote="0" → None`（不再用占位 0）。
- `classify_leg_response` 2xx 用 `_post_figures`；`classify_query_response` 2xx 用 `_query_figures`。
- 新增 `_confirm_um_figures(symbol, client_order_id, post_verdict)`：UM 腿 ACCEPTED 后立即 `query_um_order` 取权威 figures；confirmed ACCEPTED 且 `cumulative_quote is not None` → 合并权威 figures；否则保持 POST acceptance + `cumulative_quote=None`（非终态，下轮 drain）；404 视为噪声不覆盖 acceptance；`confirm_raw` 始终携带。
- `leg_is_terminal_fill` 收紧：UM（`leg != "spot"`）FILLED 需 `cumulative_quote is not None` 才 terminal。

**`store.py`（+227）：**

- schema：`cumulative_quote_amt TEXT NOT NULL DEFAULT '0'` → `cumulative_quote_amt TEXT`（放宽 NOT NULL，支持 NULL）。
- `_leg_final_fields` 重写为 NULL 合约三层：present verbatim / `"0"` 保留 / `filled_qty>0 且 avg_price 可用` 派生 / 否则 `None`。
- `aggregate_positions`：NULL quote 跳过 notional，并置 `spot_incomplete` / `perp_incomplete`；position dict 导出 `spot_avg_price_incomplete` / `perp_avg_price_incomplete`。

**`service.py`（+34）：**

- `_leg_terminal` 收紧：UM FILLED 需 `cumulative_quote is not None`（与 executor 侧对称）。

**测试：**

- `test_live_hedge_executor.py`（+99）T1 组 7 个：`test_post_margin_2xx_carries_quote_from_post_result`、`test_post_um_2xx_carries_no_quote_acceptance_only`、`test_post_um_2xx_carries_post_raw_response`、`test_dispatch_um_accepted_confirms_figures_inline`、`test_dispatch_um_confirm_inconclusive_keeps_nonterminal_quote_none`、`test_dispatch_um_confirm_404_does_not_overturn_post_acceptance`、`test_dispatch_um_confirm_carries_confirm_raw_response`。
- `test_hedge_store.py`：`test_leg_final_fields_t1_null_contract`（present / `"0"` / 派生 / None / no-fill 五态）、`test_aggregate_positions_skips_null_quote_and_flags_incomplete`。
- `test_hedge_api.py`：`_POSITION_KEYS` 增 `spot_avg_price_incomplete` / `perp_avg_price_incomplete`（additive，对齐 design §1(d)/§7）。

### W5 — ADR-T6 历史数据迁移（本阶段实现）

`store.py` `_migrate` 增 M1/M2 两条规则式迁移（幂等，二次运行 no-op）：

- **表重建**（SQLite 不能 ALTER 放宽 NOT NULL）：`PRAGMA table_info` 守卫 `leg_quote_notnull` → `CREATE hedge_open_leg__new (cumulative_quote_amt TEXT)` → `INSERT SELECT` → `DROP` → `RENAME` → 重建 `idx_hedge_open_leg_attempt` / `idx_hedge_open_leg_query`。
- **M1**：`FILLED + cumulative_base_qty > 0 + cumulative_quote_amt = '0'` 的 leg 行 → `UPDATE ... = NULL`，每行写一条 `data_migration` 审计（`field="cumulative_quote_amt", before="0", after=None`）。
- **M2**：`leg_exposure.ts == "1970-01-01T00:00:00.000000Z"` 的 task → 解析 JSON，取该 task 该 leg 的 `dispatched_at_us`（JOIN attempt DESC LIMIT 1），`expo["ts"] = us_to_iso(dispatched_at_us)`；`price` 保持 `None`（不推导）；写 `data_migration` 审计（`field="leg_exposure.ts"`）。
- `__init__(db_path, *, executor_mode_snapshot="disabled", now_us=0)` 增 `now_us` 参数作为迁移审计 `ts_us` 来源；`service.__init__` 调整 clock 设置顺序（clock 先于 store 构造），传入 `now_us=self._wall_us()`。

**测试：** `test_hedge_store.py::test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent` —— 旧 schema + 两行同形 fixture（FILLED+base>0+quote='0' 的 perp leg + leg_exposure ts=1970 的 task），断言迁移后 `quote=NULL`、`ts=us_to_iso(dispatched_at_us)`、`price=None`、两条 `data_migration` 审计（fields 恰为 `{cumulative_quote_amt, leg_exposure.ts}`），二次重开为 no-op（事件数仍为 2）。

### W6 — preflight snapshot 键名契约测试（本阶段实现）

`compute_preflight`（`domain.py:818`）写 `{leg}_step / {leg}_min_qty / {leg}_max_qty`；`executor._leg_qty_filters`（`executor.py:367`）读同名键。新增 `test_hedge_executor.py::test_preflight_snapshot_keys_and_qty_filters_reader_agree`：构造 spot（MARKET 全启用）+ perp（MARKET 全禁用、LOT 提供 step+min、max 禁用）的 snapshot，断言每条腿每个键的 writer↔reader 对称（非 None 键值相等；None 键 reader 省略即 disabled，绝不强转为 0），并固定 spot/perp 的 kwargs 字典。钉住 domain↔executor 这个 seam 不漂移。

---

## 2. 测试节选与完整计数

确定性命令（`.venv/bin/python`，非系统 `python3`）。

**指定套件**（含必跑禁改的 `test_hedge_open_live_client.py` / `test_hedge_purity.py`）：

```
316 passed in 20.04s
```

**全仓回归** `backend/tests`：

```
1061 passed in 50.72s
```

完整原始输出见同目录 `60-test-output.txt`（两条命令依次 tee）。`test_hedge_purity` 未因新增 import 变红（本阶段未在 `hedge_open_tasks/**` 包内新增对 `services` 的依赖；新增的 `_leg_qty_filters` import 在测试文件侧）。

关键新测试逐一通过：

```
test_hedge_store.py::test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent   PASSED
test_hedge_store.py::test_leg_final_fields_t1_null_contract                        PASSED
test_hedge_store.py::test_aggregate_positions_skips_null_quote_and_flags_incomplete PASSED
test_hedge_executor.py::test_preflight_snapshot_keys_and_qty_filters_reader_agree  PASSED
test_live_hedge_executor.py::test_dispatch_um_accepted_confirms_figures_inline     PASSED
test_live_hedge_executor.py::test_dispatch_um_confirm_404_does_not_overturn_post_acceptance PASSED
（T1 组 7 个全绿）
```

---

## 3. T2(c) 判定变化清单

**结论：本阶段工作区未修改任何错误分类逻辑或分类表，故除 51169 外没有任何码的判定在本阶段发生变化；51169→collateral_cap 的映射本身也在基线 `9e50228` 之前已实现，本阶段无变化。**

依据（实测，非推测）：`git diff HEAD -- backend/services/live_hedge_executor.py backend/hedge_open_tasks/domain.py` 中不存在任何触及 `classify_exchange_code`、`AUTH_AMBIGUOUS_EXCHANGE_CODES`、`FATAL_EXCHANGE_CODES`、`INSUFFICIENT_FUNDS_CODES`、`MARGIN_BUSINESS_CODES`、`UM_BUSINESS_CODES`、`error_category` 透传或 404/`-2013` absent 分支的 hunk。各码判定逐项核对：

| 码 | 基线判定 | 本阶段判定 | 变化 |
|---|---|---|---|
| `51169`（margin） | `collateral_cap` | `collateral_cap` | 无（基线已映射） |
| `-2019 / -3041` | `insufficient_funds` | `insufficient_funds` | 无 |
| `-2010`（消息确认） | `insufficient_funds` | `insufficient_funds` | 无 |
| `-2010`（消息未确认） | `fatal` | `fatal` | 无 |
| `-1013 / -1100…` 系列 | `fatal` | `fatal` | 无 |
| `-1000/-1021/-1022/-1099/-2011/-2014/-2015/-2017/-2018` | `auth` | `auth` | 无 |
| 404 / `-2013`（query 路径） | `absent` | `absent` | 无 |
| 其他未识别码 | `unclassified` | `unclassified` | 无 |
| `code is None` | `None`（NULL） | `None`（NULL） | 无 |

**评审该看的相关语义变化（不属于 error_category 判定，但同属本阶段交付）：** W4 把 `_empty_dispatch` / `_error_leg` 的 `cumulative_quote` 占位值从 `"0"` 改为 `None`。这不改变任何码的 `error_category` 判定，但改变了「拒单/未知腿的成交金额」从「占位 0」变为「NULL=未知」，使拒单腿不再带一个与真零不可区分的金额。这是 T1 NULL 合约的一部分，与 T2 的分类判定正交。

---

## 4. T5(c) `leg_exposure.price` 是否因 T1 恢复（实测陈述）

**实测结论：`leg_exposure.price` 的字段来源是 `avg_price`，不是 `cumulative_quote`；T1 对 `cumulative_quote` 的修复不直接恢复 `leg_exposure.price`，但 T1 同时修复了 `avg_price` 的来源，故当响应携带 `avgPrice` 时 `price` 会获得真实值，缺失时为 `None`（不强转为 0）。历史迁移 M2 不推导 `price`，保持 `None`。**

依据：

1. `build_leg_exposure`（`domain.py:1048-1053`）：
   ```python
   return {
       "leg": "spot" if spot_accepted else "perp",
       "qty": str(leg.get("filled_qty", "0")),
       "price": str(leg.get("avg_price")) if leg.get("avg_price") is not None else None,
       "ts": us_to_iso(ts_us),
   }
   ```
   `price` 取自 `leg["avg_price"]`，与 `cumulative_quote` 无关。
2. `dispatch_to_outcome`（`live_hedge_executor.py:463-476`）构造 `spot_leg/perp_leg` 时 `"avg_price": spot.avg_price`，即来自 `LegDispatch.avg_price`。
3. T1 的 `_post_figures` / `_query_figures` 同时返回 `avg_price`：margin 从 POST RESULT 的 `avgPrice` 取；UM 从 inline-confirm GET 的 `avgPrice` 取。T1 前 UM POST 不带 `avgPrice`，UM 单腿敞口的 `price` 恒为 `None`；T1 后当 confirm GET 返回 `avgPrice` 时 `price` 获真实值，仍缺失时为 `None`。
4. M2 历史迁移（`store.py`）显式只改 `expo["ts"]`，`price` 保持 `None`——历史行的 `avg_price` 已无法恢复，不强推（与「宁可显式未知」一致）。测试 `test_migrate_m1_m2_repair_defect_rows_audit_then_idempotent` 断言 `expo["price"] is None`。

---

## 5. W0 假设状态

**W0（签名只读 GET 证明订单详情仍携带 `cumQuote`/`avgPrice`）样本未到达。** T1 的 UM 金额链路（`_query_figures` 读 `cumQuote` 回退 `cummulativeQuoteQty`、`_confirm_um_figures` inline confirm）按 design §1(b)/§1(c) 文档形状实现，**该假设当前未经验证**。NULL 表示法（`cumulative_quote is None` = 未知，`leg_is_terminal` 据此保持非终态 drain）就是「假设错了」的兜底：若实测证明订单详情 GET 也不携带这些字段，UM 腿会持续 `cumulative_quote=None`、永不 terminal、worker 一直 drain——这是显式失败，不会落一个与真实值不可区分的替代值。

按 dispatch line 167-171 的处置：W0 未到 → 按文档形状实现并在本报告显式标注假设未验证（本节即此）。若 W0 后续到达且证明 GET 也无这些字段：停止 T1，交回 bookkeeper 走 userTrades 契约修订。

---

## 6. 风险（评审该看）

1. **W0 假设未验证（最高）**：UM inline-confirm GET 是否真返回 `cumQuote`/`avgPrice` 仅基于 design 推断，无签名样本。若假设错，UM 腿 `cumulative_quote` 恒 None → 永不 terminal → worker 无限 drain（显式失败，非静默错误，但仍需 W0 落地确认或转 userTrades）。
2. **历史迁移未经生产库验证**：M1/M2 仅在测试临时库（`tmp_path`）验证。生产库 `data/hedge-open-tasks.sqlite3` 的迁移由 bookkeeper 执行（本阶段禁写生产库）；表重建路径（CREATE/INSERT SELECT/DROP/RENAME）在并发打开的连接下需 bookkeeper 确认时序。
3. **UM inline confirm 增加 GET 次数**：每条 UM 腿 POST acceptance 后多一次 `query_um_order`，占用 UM rateLimit/order 配额。design §1(b) 已将其列为非终态 drain 的一部分，但生产流量下需观察。
4. **`-2010` 双登记**（既有，非本阶段引入）：`-2010` 同时在 `INSUFFICIENT_FUNDS`（消息确认）与 `FATAL_EXCHANGE_CODES`（fallback）。`classify_exchange_code` 先查 `is_insufficient_funds_code` 再查 `FATAL`，语义正确，但评审需确认该顺序在所有路径成立（domain.py:463-466，本阶段未改）。
5. **基线归因**：W1–W3 在基线 `9e50228` 之前已实现，本报告对其只做「验证通过」陈述；若 bookkeeper 期望 W1–W3 也在本阶段交付物内，需核对更早 commit 的归因（超出本阶段 diff 范围）。

---

```
当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md
本地北京时间: 2026-07-28 18:52 CST
下一步模型: bookkeeper
下一步任务: R4 边界核对 + 证据 commit + 指纹 + pre-review 校验，然后派 review-1(codex)
```

---

# 追加章节：Review-1 P1 修复（31-fix-review-1.dispatch.md，rework_count 1/3）

## 背景

`30-review-1.md`（codex）P1 finding，经 bookkeeper 独立确认：当一条腿的 POST 返回 `LEG_UNKNOWN_QUERYING` 时，`LiveHedgeExecutor._send_one_leg` 会**立即**做一次 order-detail GET 来定夺该腿命运。修复前，这个即时 fallback GET 的响应被 `classify_query_response` 解析后**丢弃**——返回的 `LegDispatch` 只保留 POST 的 `raw_response`，`resolved.raw_response`（实际决定该腿命运的 GET body）没有出口。因此 `service._dispatch_live` 只写三条 raw 行（spot `order_post` / perp `order_post` / perp `order_confirm`），从未把这条即时 GET 以 `source=order_query` 落库。

这正是 T3「查询订单详情的全量信息落库」最该兜住的硬场景：POST 没给出确定结论，**GET 是唯一记录**，丢了它就等于这条腿的真相不可读。drain 路径（`service.py` reconcile）早已用 `source="order_query"` 正确持久化同类 GET（见 `service.py:1147`），本修复只是让 dispatch 路径**跟随既有模式**，不发明第二套。

## 改了什么（最小范围，3 文件 +144/-3）

1. **`backend/services/live_hedge_executor.py`**
   - `LegDispatch` 新增 `query_raw_response: Optional[dict] = None` 字段，承载 UNKNOWN-POST 即时 fallback GET 的 sanitized body（`source=order_query`）。与既有 `raw_response`（POST，`source=order_post`）、`confirm_raw_response`（UM accepted 后取金额的 confirm GET，`source=order_confirm`）三者语义分离、一一对应 service 的三种 raw 行。
   - `_send_one_leg` 的 UNKNOWN 分支（line 567 附近）返回的 `LegDispatch` 增加 `query_raw_response=resolved.raw_response`。`raw_response` 仍 = `verdict.raw_response`（POST body），`confirm_raw_response` 仍 = `verdict.confirm_raw_response`。**GET 不覆盖 POST，POST 不丢失**。

2. **`backend/hedge_open_tasks/service.py`**
   - `_dispatch_live` 在既有三条 `_persist_leg_raw`（spot/perp `order_post` + perp `order_confirm`）之后，增加 spot 与 perp 各一条 `source="order_query"` 的 `_persist_leg_raw`，读 `getattr(leg, "query_raw_response", None)`。`_persist_leg_raw` 对 `None` 是 no-op，所以**只有真正发生即时 fallback GET 的腿**才会写 `order_query` 行（POST 已经确定的腿，如本测试里的 perp，不会多写）。

3. **`backend/tests/test_hedge_task_local.py`**
   - 新增 `test_4h_dispatch_unknown_post_fallback_query_persists_post_and_query_raw`（service 级，接在 `test_4f` 之后）。用真实 `LiveHedgeExecutor` + 新增最小 `_LiveWireClient`（镜像 PAPI client 的 POST/GET 接口）+ `_wire_resp`（让 `raw_body` 为真实 JSON 文本）。脚本：spot POST 500（UNKNOWN）→ 即时 GET 200 FILLED；perp POST 200 FILLED（ACCEPTED）→ confirm GET 200 FILLED。断言：
     - spot 的 raw 行 source 集合 == `{order_post, order_query}`；POST 行 `http_status==500`，GET 行 `http_status==200`、`business_code is None`、`business_msg is None`、`client_order_id is not None`、`body` 含 `"status": "FILLED"`（GET 的 body/code/msg 均可从库检索）。
     - perp 的 raw 行 source 集合 == `{order_post, order_confirm}`（**无 `order_query`**：perp 的 POST 已经确定，即时 fallback GET 从未对其触发）。
     - 订单判定不变：spot 腿被即时 GET 定夺为 FILLED 且带权威金额（`exchange_status==FILLED`、`cumulative_quote_amt=="25000"`、`terminal==1`）。

## 不变性确认（reviewer #3 要求）

本修复是**纯增量**：被丢弃的 GET 业务字段本就已用于定夺（`_send_one_leg` 的 UNKNOWN 分支 `resolved.*` 业务字段在修复前后完全相同），修复只是补一个被丢的 raw 副本 + 一条持久化调用。因此：

- **订单判定**：不变。`resolved.dispatch_state / order_id / exchange_status / executed_qty / cumulative_quote / avg_price / error_code / error_category` 在修复前后逐字相同；`leg_is_terminal`、attempt success/failed 分类、spot/perp FILLED 判定路径均未触碰（`_leg_terminal`、`_send_one_leg` 的 confirm 分支、`classify_query_response`、`classify_leg_response` 均未改）。
- **重发规则**：不变。仍「UNKNOWN 即时 query 一次，永不 resend」，未 POST 的腿不进 drain（drain 用 `executor.query_leg`，与本次新增的 `query_raw_response` 字段无关）。
- **限频规则**：不变。`rate_limited` / `retry_after_seconds` 的合并逻辑（`verdict.rate_limited or resolved.rate_limited`、`verdict.retry_after_seconds or resolved.retry_after_seconds`）未改，amendment-21 task-local pause 行为不受影响。
- **raw 写失败行为**：不变。新增的 `order_query` 持久化走**同一个** `_persist_leg_raw` → `store.append_raw_response`，享有既有的绝对控制流隔离（自己的短事务，失败 swallowed + best-effort `raw_persist_failed` 事件，绝不回滚或阻断已 commit 的业务写）。

## 测试证据

`60-test-output.txt`（本阶段分隔标题之后）：
- 指定套件（9 套件，含必跑禁改的 `test_hedge_open_live_client` / `test_hedge_purity`）：**317 passed**（基线 316 + test_4h）。
- 全仓 `backend/tests`：**1062 passed in 50.92s**（基线 1061 + test_4h），无 failed/error。

解释器 `.venv/bin/python`（3.11.15），全程离线确定性（fake client / fake provider / 临时 SQLite），未发任何真实 POST、未访问凭据、未动 PID 96409、未写生产库、未 commit。

---

```
当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md（追加章节）/60-test-output.txt
本地北京时间: 2026-07-28 21:52 CST
下一步模型: bookkeeper
下一步任务: 核验修复、重算指纹、重跑 pre-review，然后重派 review-1
```

---

## 修复章节 — Review-1 Round 3（两个 P1，按用户决定收窄），2026-07-29

执行 dispatch `35-fix-review-1-r3.dispatch.md`（rework 3/3，用户授权的最后一轮）。本轮**不改任何业务判定语义**：两个 P1 都只在存储层 / 持久化调用上做最小增量。

### 改了什么

**Finding 1（P1-1）— drain 的限频查询从未落库**：`_reconcile_own_legs`（`service.py`）里 `if getattr(verdict, "rate_limited", False):` 分支设 `drain_signal` 后直接 `continue`，**早于**循环体下方的 `_persist_leg_raw(..., "order_query", ...)`。而 `classify_query_response`（`live_hedge_executor.py:400-406`）对 429 / -1003 / 418 返回的是**带 `raw_response` 的确定判定**，证据存在却被丢。

修复：在该分支 `continue` 之前，用既有的 `_persist_leg_raw` 落库（`source="order_query"`）。**未改**该分支的 pause 语义、非终态腿处理、永不重发保证；持久化调用本身享有绝对控制流隔离（`_persist_leg_raw` swallow 全部异常），因此不可能改变这三者。

**Finding 2（P1-2）— 重复的相同查询响应让 raw 表无界增长**：畸形 2xx（无 `orderId`）返回 UNKNOWN 判定 → `_query_verdict_terminal` 为 False → 腿保持非终态 → drain 每个 worker 轮重新查询 → 每轮写一条最多 `BODY_MAX_BYTES` 的行。无界，且与 ADR-T4 声明的「每次 attempt 2–6 行」矛盾。

修复：按用户规则（2026-07-28/29）——**每条腿每个 `source` 只存第一条 raw 行**。

### 选用的去重机制及理由

去重放在 **`store.append_raw_response`（`store.py`）自己的短事务内**：写之前先 `SELECT id ... WHERE attempt_id=? AND leg=? AND source=? LIMIT 1`，命中则直接返回既有行 id、不插入。

- **放在存储层、在该方法自己的 `with self._lock, self._conn:` 事务内**，使「存在性检查 + 插入」原子且与业务写彻底隔离（dispatch 硬约束：绝不触碰业务写）。
- **纯应用层 check-then-insert，无 schema 变更**：不加 digest 列、不加 UNIQUE 索引、不加迁移（dispatch 明令禁止；bookkeeper 提议的 digest 方案被用户否决——Binance order-detail 体含 `updateTime` 等轮间会变的字段，「内容相同」常常为假，digest 既过度又未必能 bound）。
- **跳过不是错误**：命中既有行时正常返回（返回既有 id），不抛异常，故调用方不会记 `raw_persist_failed`。
- `order_post` / `order_confirm` 本就每腿一次，实际只有会重复的 `order_query` 受影响——正是 Finding 2 的症状。

### 已知代价（用户明确接受，记此以免被当成新发现）

- 一条腿的首条 `order_query` 若是无意义 poll，其后的 `429` 不再落库（用户原话：「429 就 429，遇到问题我们再分析问题」）。腿行业仍记录结局（`exchange_status` / `cumulative_quote_amt` / `order_id`），业务真相完整；丢失的只是那最后一次读取的交易所原文。
- 一旦某腿已有 `order_query` 行，**决定性**那条查询的原文不再保留。

### 不变性确认（reviewer #3 要求）

- **订单判定**：不变。`classify_query_response` / `classify_leg_response` / `_send_one_leg` / `_query_verdict_terminal` / `resolve_leg_from_query` 的返回值与判定路径逐字未改（`live_hedge_executor.py` 本轮**零改动**，明令锁定）。畸形 2xx 分支仍返回带 raw 的 UNKNOWN 判定。
- **重发规则**：不变。仍是「UNKNOWN 即时 query 一次、drain 持续 query、永不 resend POST」；去重只跳过存储插入，不跳过 `resolve_leg_from_query`，腿仍被持续 re-query。
- **限频 pause 行为**：不变。Finding 1 只在 rate-limited 分支 `continue` 前补一条持久化调用；`drain_signal` 合并、`_pause_task_local(kind="rate_limited")`、R2-F2「pause 本任务并退出、腿保持非终态、不回环进限频」均未触碰。
- **raw 写失败隔离**：不变。两条修复路径都走**同一个** `_persist_leg_raw` → `store.append_raw_response`，享有既有的绝对控制流隔离（自己的短事务，失败 swallowed + best-effort `raw_persist_failed` 事件，绝不回滚或阻断已 commit 的业务写）。

### 新增测试（`test_hedge_task_local.py`，仅两条，不搭套件）

1. `test_4i_drain_rate_limited_query_persists_order_query_row`：UNKNOWN pair 的两条 drain GET 返回 429 → 每条腿落**恰好一条** `order_query` 行（带 429 body）、任务仍 `rate_limited` pause、腿仍非终态、`dispatch_calls==1`（无重发）。
2. `test_4j_repeated_malformed_2xx_drain_grows_one_row_per_leg`：连续多轮畸形 2xx drain 响应 → 每条腿**恰好一条** `order_query` 行（不是每轮一条）、腿仍非终态、`query_calls>2`（仍被持续 re-query）。

既有 `test_4f` / `test_4h` 契约仍成立（与新测试同批跑过），raw 写失败仍不改业务结果（既有 `test_4g` 覆盖）。**未**加「内容变化的响应写第二条行」的测试——按本规则它本来就不写，这是设计。

### 测试证据

`60-test-output.txt`（本轮覆盖后追加）：

- 指定套件（9 套件，含必跑禁改的 `test_hedge_open_live_client` / `test_hedge_purity`）：**319 passed**（基线 317 + test_4i + test_4j）。
- 全仓 `backend/tests`：**1064 passed in 54.11s**（基线 1062 + test_4i + test_4j），无 failed / error / skip。

解释器 `.venv/bin/python`，全程离线确定性（fake client / fake provider / 临时 SQLite），未发任何真实 POST、未访问凭据、未动 PID 96409、未写生产库 `data/hedge-open-tasks.sqlite3`、未 commit。改动文件仅 `backend/hedge_open_tasks/{service,store}.py` 与 `backend/tests/test_hedge_task_local.py`（均在允许边界内），`live_hedge_executor.py` 等锁定文件零改动。

---

```
当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md（追加章节）
本地北京时间: 2026-07-29 00:19:15 CST
下一步模型: bookkeeper
下一步任务: 核验修复、重算指纹、重跑 pre-review，然后重派 review-1
```
