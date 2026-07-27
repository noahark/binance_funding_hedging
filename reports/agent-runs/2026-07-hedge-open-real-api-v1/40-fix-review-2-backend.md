# 40 — Review-2 REWORK 后端修复报告：Hedge Open Real API v1

> 模型：`glm-5.2[1m]`（Claude Code 会话，本任务唯一后端返工实现者）。
> 分支：`stage/2026-07-hedge-open-real-api-v1`。
> 数据包：`54-review-2-rework-backend.dispatch.md`，范围 = Review-2 的 P0/P1 后端缺陷修复 + 按用户批准的修正案（`15-immediate-loop-and-open-log-amendment.md`）与拆解（`16-replacement-development-breakdown.md`）重做节奏/错误模型。
> 本报告为后端返工的完整、未编辑产出。不 commit、不改 `status.json` / `70-handoff.md` / `50-review-2.md` / `15-*` / `16-*` / PRD / 设计 / ADR / 前端 / docs，不派发或评审其他模型。**绝不读取凭据、绝不连接 Binance、绝不发真实 POST。**

---

## 0. Session 元信息

- **Session ID**：`94305f00-bde4-4d80-a69e-091eddffcbe7`。
- **Session ID 来源**：`runtime_env`（harness scratchpad 路径；仅用于导航）。
- **原始输出路径**：`reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md`。
- **本地北京时间**：2026-07-24 17:20:27 CST（`date` 取得）。
- **下一步模型**：bookkeeper。
- **下一步任务**：reconcile backend + frontend 两侧 diff（R4-style），rerun integration evidence，fix Review-2 P2 main-sync SHA（fix 8）本身，recompute committed fingerprint，re-enter required committed review gates（`rework_count` 2 of 3）。

---

## 1. 修复范围与未改项

**修复（拆解 `16` §3.2 的 A-1 … A-9 + 修正案 I-1 … I-7）：**

| 项 | 要求 | 落点 |
| --- | --- | --- |
| A-1 / I-1 | `target_n` = 计划尝试组数硬上限；选择与发送前事务原子检查 `scheduled_attempt_count < target_n`；scheduler / fill-once / 任何并发共用同一每任务串行入口；失败/单腿绝不补发第 N+1 组 | store 资格规则 + `prepare_attempt` 重检 |
| A-2 | 每组先完整新鲜预检，再在一个事务里用本次精确 `q_common` / 仓位模式 / 过滤器 / 账户 / 余额 / 价格 / 限频快照 + 两腿 client ID + wire shape 持久化 attempt，之后才并发 POST | service `_dispatch_one_for_task` + `_resolve_fresh_preflight` |
| A-3 | 预检 fail-closed：账户/交易对状态、`dualSidePosition` 字面 false、价格/余额、NOTIONAL/MIN_NOTIONAL、`MARKET_LOT_SIZE` 逐约束回退 `LOT_SIZE`、当前订单限频事实缺一即拒；致命预检事实（余额不足/交易对不可用/仓位模式无效/过滤器违规）→ `stopped` + `stop_reason` + 日志 | domain `compute_preflight` 致命分类 + provider 完整性 |
| A-4 | 记录元数据与 wire 参数分离；两腿签名正文不含 `endpoint` 或其他内部字段；executor→client 全链路逐字段断言 | executor wire builders + 回归 #4 |
| A-5 / I-6 | 顺序组循环 + 独立对账：本任务未终态组只挡本任务下一组，绝不挡其他任务；Start 关 / done / 无 eligible 时仍轮询；仅明确 absent 业务码确认未受理；鉴权/签名/时间戳/权限/5xx/timeout 保持未知并按 client ID 查询、绝不重发；CANCELED/EXPIRED/REJECTED/FILLED 终结并保留部分成交 | service `tick` + `_reconcile_pending` + live executor 查询分类 |
| A-6 | 端到端保存实际累计 base/quote、均价、可得手续费、部分成交与 residual；持仓聚合纳入任何实际成交量（不看字面 FILLED） | store leg 字段 + `aggregate_positions` |
| A-7 / I-2 / I-4 / I-5 / I-7 | 错误矩阵：致命立停（additive `stopped` + nullable `stop_reason`）；非致命计数；阈值暂停；双腿受理清零；全进程 429 写延迟不改任何任务业务态；每个错误带机器可读 category/code + 安全中文原因 | store `_apply_task_counters` + live executor 分类 + service cooldown |
| A-8 | 按 `16` §5 冻结契约 additive 扩展 `GET /api/hedge-open-logs` 的 `entries` 投影（同路由、同 cursor/limit/next_cursor；logs/attempts 原样）；entries 含各状态 attempt 及任务事件，newest-first；`task_to_doc` 加 `stopped` + nullable `stop_reason` | service `_entries_projection` + `task_to_doc` |
| A-9 + `16` §3.3 | 两 worker 独立推进，但每任务永不启动 pair 2 直到 pair 1 终结；9 条确定性离线（fake-transport）回归 | service 资格/对账 + `test_hedge_review2_regressions.py` |

**未改（合同明确禁止 / 不在范围）：**

- `frontend/**`、`backend/services/binance_signing.py`、`backend/borrow_tasks/**`、`docs/**`、`reports/api-samples/**`、`status.json`、`70-handoff.md`、`50-review-2.md`、`15-*`、`16-*`、`60-test-output.txt`、环境/凭据文件、任何真实网络配置——**均未触碰**。
- `backend/app/server.py` **未改**（provider/service 构造签名不变，最小接线维持原状；完整 backend 套件 880 passed 证明接线无损）。
- 冻结 7 端点 allowlist 恰好 7 个，未增减；`hedge_open_tasks/**` 仍不导入任何网络/签名原语（`test_hedge_purity.py` AST 守卫通过）。
- disabled/record 默认语义（零真实 POST）、`quoteOrderQty` 禁止、并发同 `q_common`、durable-before-send、timeout→client-ID 查询不重发、live `fill-all` 禁同步 POST——全部保持。
- 绝不记录 API key / 签名 / 含密头（`test_hedge_executor.py` 的 no-secret-leak 证明保持）。

> **并行任务边界说明**：工作树中 `frontend/index.html`、`frontend/self-check.js`、`reports/.../40-fix-review-2-frontend.md` 是前端返工 owner（Task B / Claude Sonnet 5，按 `16` §7.2 与本任务并行）的改动，**非本会话所改**。`node frontend/self-check.js` 在本后端改动下仍全部通过，证明 §5 frozen `entries` 契约两侧对齐。

---

## 2. 逐项实现说明

### 2.1 A-1 / I-1：`target_n` 硬上限 + 每任务串行入口（`store.py` / `service.py`）

- `list_eligible_tasks()`（store）：资格 = `status=running` **且** `scheduled_attempt_count < target_n` **且** `NOT EXISTS (SELECT 1 FROM hedge_open_attempt WHERE task_id=t.id AND pair_outcome IS NULL)`（在途未决组守卫）。三个入口（scheduler `tick`、`fill-once`、`fill-all`）共用 `_dispatch_one_for_task` → `prepare_attempt`，无旁路。
- `prepare_attempt(...)`（store）：在同一发送前事务里**重检** `scheduled_attempt_count >= target_n` 与在途未决组守卫；命中即返回 `None`（零 attempt / 零 POST）。即失败 / 单腿 / fill-once / scheduler 任何路径都无法创建第 N+1 组。
- 验证：回归 #1（`target_n=1`，success / confirmed-failed / single-leg 三变体 + fill-once+scheduler）各得恰好 1 行 attempt、1 次 dispatch。

### 2.2 A-2：新鲜预检在前 → 单事务持久化 → 并发 POST（`service.py`）

- 新增 `_FreshPreflight` frozen dataclass + `_resolve_fresh_preflight(task) -> _FreshPreflight | None`：仅当 `_live_dispatch_capable()`（真实 POST）时取新鲜快照并 `compute_preflight`；返回 `None`（不可读 → fail-closed 重试）/ `fatal`（可读但违规 → 立停）/ `ok`（携带本次精确 `q_common` / 仓位模式 / 快照）。
- `_dispatch_one_for_task` 重写：live 路径**先**解析新鲜预检，再以新鲜 `q_common` 构建 wire shape 并 `prepare_attempt`（ADR-2 单事务：attempt + 2 client IDs + 2 wire shapes 在 POST 前提交）。dry-run 记录传输路径继续复用存储 `q_common`，从不 POST（既有 dry-run 测试零变更保持绿色）。
- 验证：回归 #2（create 时 grid step 0.1 → `q_common="0.5"`；send 前 fresh step 0.01 → `q_common="0.55"`；持久化 attempt 与 executor 收到的 `ctx.q_common` 均为 `"0.55"`）。

### 2.3 A-3：fail-closed 完整性 + 致命事实立停（`domain.py` / `hedge_preflight_provider.py`）

- domain：`PreflightSnapshot` 加 `symbol_tradable: bool = True`；新增 `REJECT_SYMBOL_UNAVAILABLE` / `REJECT_POSITION_MODE_INVALID` 并并入 `PREFLIGHT_FATAL_REASONS` + `REJECT_TO_STOP_REASON`（→ `STOP_REASON_SYMBOL_UNAVAILABLE` / `STOP_REASON_POSITION_MODE_INVALID`）。`compute_preflight` 在 step 检查前先判致命：`symbol_tradable=False` → 致命；`position_mode != BOTH`（`dualSidePosition` 非 false）→ 致命。step 不可读 / forward 缺价仍为 `REJECT_PREFLIGHT_INCOMPLETE`（fail-closed 重试，**非**致命，不 conflate 不可读与违规）。
- provider：`_read_position_mode` 保留真实模式——`dualSidePosition=True` → `POS_MODE_HEDGE`（下游致命），`is False` → `POS_MODE_BOTH`，缺失/歧义 → `None`（incomplete）；`_read_spot/perp_filters` 返回 `(filters, tradable)`，tradable = `status=="TRADING"`；`get_snapshot` 解包并设 `symbol_tradable = spot_tradable and perp_tradable`，且把 `rate_limit is None` 并入 fail-closed 守卫（clause 3：当前订单限频事实缺一即拒）。
- 致命路径：service `_stop_task_fatal_preflight`（`store.stop_task_fatal` + `record_task_event("task_stopped", ...)`，零 attempt / 零 POST）；incomplete 路径：`_record_preflight_incomplete`（`record_task_event("preflight_incomplete", ...)`，零 attempt / 零 POST / 零计数）。
- 验证：回归 #3a（不可读 step → 0 attempt / 0 POST / 0 fail / 0 dispatch / 仍 running + preflight_incomplete 事件）；#3b（余额不足 → `stopped` + `stop_reason=insufficient_balance` + task_stopped 事件 + 0 attempt）。

### 2.4 A-4：wire / 元数据分离（`executor.py`）

- `build_spot_order_params` 精确 7 键 `{symbol, side, type, quantity, sideEffectType, newClientOrderId, newOrderRespType}`；`build_perp_order_params` 精确 7 键（perp 以 `positionSide` 替 `sideEffectType`）。`endpoint` 与一切内部字段移出签名正文（仅记录在 leg 行元数据）。
- 验证：`test_hedge_executor.py` 两处 wire-shape 断言改为 `set(spot.keys())` / `set(perp.keys())` 精确等值、`endpoint not in`；回归 #4 以真实 `LiveHedgeExecutor` + 捕获型 `_CapturingClient` 断言 executor→client 递交的 body 恰为批准键、无 `endpoint` / 无任何密钥字段。

### 2.5 A-5 / I-6：顺序组循环 + 独立对账（`service.py` / `live_hedge_executor.py`）

- `tick()`：`_reconcile_pending(self._wall_us())` 在 `with self._lock` 块**最前**执行，先于 pacing / gate / eligible 检查（对账从不被放弃）。即使 Start 关 / done / 无 eligible，既有未终态腿仍按 client ID 轮询。
- `_reconcile_pending`：`list_non_terminal_legs` → `executor.query_leg`（从不重发）；verdict `None`（inconclusive）保持非终态继续轮询；明确 absent（`error_category="absent"`，404 / -2013）→ 终态确认未受理；`CANCELED`/`EXPIRED`/`REJECTED`/`FILLED` 终结并保留部分成交（`_query_verdict_terminal` + `resolve_leg_from_query` 透传 `error_code/error_category`）。
- live executor：`classify_query_response` 仅 `status==404 or code=="-2013"` → `LEG_REJECTED`+`absent`；鉴权/签名/时间戳/权限码（`AUTH_AMBIGUOUS_EXCHANGE_CODES`）与其余歧义 4xx → `None`（保持未知、按 client ID 查询）。
- 验证：回归 #5（Start 关时对账仍轮询并 resolve；query_calls>0）、#5b（auth-ambiguity `None` → 保持 unresolved 不重发；explicit absent → fail_count++）、#5c（`CANCELED` 带部分成交 → terminal=1 且 `cumulative_base_qty=0.2` 保留）。

### 2.6 A-6：实际成交 / 部分成交 / 手续费 / 残差（`store.py` / `executor.py` / `service.py`）

- `_simulate_leg`（executor）加 `cumulative_quote`（filled_qty * price，Decimal）；live path 的 `LegDispatch.cumulative_quote`（margin `cummulativeQuoteQty` / UM `cumQuote`）经 service `_dispatch_to_outcome` / `_reconcile_pending` 透传到 leg 行 `cumulative_quote_amt`。
- `aggregate_positions`（store）纳入任何 `_num(cumulative_base_qty) > 0` 的 leg（**不看字面 FILLED**）。
- 验证：回归 #6（spot NEW 部分成交 0.3 + perp FILLED 0.5 → entries/positions 投影携带 `cumulative_quote_amt=15000`、部分成交 `0.3`、非零 residual，且聚合纳入非 FILLED 的 spot 正向成交）。

### 2.7 A-7：错误矩阵（`store.py` / `live_hedge_executor.py` / `service.py`）

- store `_apply_task_counters`：fatal → `STATUS_STOPPED` + `stop_reason`，无计数变动；accepted → `accepted_pair_count++` / `success_count++` / consecutive 清零；confirmed-failed → `fail_count++` / `consecutive++`，达阈值 → `STATUS_PAUSED` + `PAUSE_REASON_CONSECUTIVE_SUBMISSION_FAILURE`；single-leg → advisory，计数不动。
- store `_outcome_error` / `finalize_attempt`：leg `error_category=="fatal"`（`FATAL_EXCHANGE_CODES`：-2010/-2019/-3041/-1013/-1100..-1270 过滤器族）→ outcome 致命 → 立停。
- live executor `classify_leg_response`：rate-limited（429 / -1003 / 418）→ `UNKNOWN_QUERYING` + `rate_limited` + `retry_after_seconds`（**非**业务裁决）；4xx 中 auth 码 → `UNKNOWN`+`auth`（保持未知查询）；致命码 → `REJECTED`+`fatal`；其余 → `REJECTED`（已知非致命计数）。
- service `_enter_rate_limit_cooldown(now, retry_after_seconds)`：有服务端 `Retry-After` 则精确遵循，否则 60s 兜底；**仅进程级写延迟**，从不改任何任务业务态，并记 `rate_limited` 事件（I-5）。
- 验证：回归 #7a（3 次非致命失败 → paused，fail_count=3，stop_reason=None）、#7b（致命 -2010 → stopped + exchange_fatal）、#7c（成功清零 consecutive）、#7d（429 → 仍 running / fail_count=0 / 进程级 cooldown 生效）。

### 2.8 A-8：§5 frozen `entries` 投影 + stopped 状态（`service.py` / `store.py`）

- `task_to_doc` 加 `"stop_reason": task["stop_reason"]`（additive I-4）；`filter_status_for_list` 接受 `stopped`。
- `_apply_task_counters` 在状态转移点（守卫去重）记 `task_stopped` / `threshold_paused` 事件；service 在 fatal 预检 / 429 / preflight-incomplete 处分别记对应事件，全部落 `hedge_open_log`（`attempt_id=NULL`，任务事件）。
- `_entries_projection`：合并每状态 attempt（`list_attempts_page`）+ 任务事件（`list_task_event_logs`，kinds = task_stopped/threshold_paused/preflight_incomplete/rate_limited），按 `(ts_us, id)` 降序、`limit` 截断。字段名**逐字**对齐 `16` §5：`entry_id` / `entry_type`（attempt | task_event）/ `task_id` / `coin` / `direction` / `attempt_seq` / `created_ts` / `submitted_ts` / `final_ts` / `q_common` / `planned_quote_amount` / `spot{...}`（含 fee_*）/ `perp{...}`（无 fee_*）/ `residual` / `overall_result` / `error_category` / `error_code` / `error_reason_zh` / `next_action`。task_event 行 attempt/leg 字段为 null（UI 渲染 —）。
- 验证：回归 #8（additive 键、每行恰为 §5 键集、newest-first、pre-orderId confirmed_failed 行、limit 分页）、#8b（task_event 行 leg 字段 null、overall_result=task_stopped）。

### 2.9 A-9 + §3.3 九条回归（`service.py` / `test_hedge_review2_regressions.py`）

- 每任务 worker 独立 dispatch（`_dispatch_eligible_concurrently`，R4-2 已有），但资格规则的在途未决组守卫保证每任务串行：本任务 pair 1 未终态时，pair 2 的 `prepare_attempt` 返回 None。
- 新增 `backend/tests/test_hedge_review2_regressions.py`（18 个测试函数，覆盖 §3.3 全部 9 项；fake live executor + fake provider，零网络 / 零签名）。验证：回归 #9（tick 1 两任务各得首对 = 独立；tick 2 后 A 仍 1 对、B 2 对 = 每任务串行且互不阻塞）。

---

## 3. 自测命令输出摘要（全部通过）

```text
# (1) focused 8 文件 + 新回归
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py \
  backend/tests/test_hedge_review2_regressions.py -q
→ 204 passed in 13.31s

# (2) 完整 backend 套件
.venv/bin/python -m pytest backend/tests -q
→ 880 passed in 44.45s

# (3) frontend self-check（本后端改动下仍全绿，证明 §5 契约两侧对齐）
node frontend/self-check.js
→ 全部自检通过（含开单日志 tab、entries 逐字渲染、stopped/paused 语义）

# (4) stage dispatch 协议校验
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
→ 55 passed in 0.92s

# (5) 空白/冲突检查
git diff --check
→ CLEAN
```

`hedge_open_tasks/**` 纯度守卫（`test_hedge_purity.py` AST）通过；no-secret-leak 守卫通过。

---

## 4. 发现 → 修复映射（带修正案 / 拆解条款）

| Review-2 发现 | 根因 | 修复 | 条款 |
| --- | --- | --- | --- |
| 第 N+1 组可能被补发 | 资格/发送前检查未统一以 `target_n` 为硬上限 | `list_eligible_tasks` + `prepare_attempt` 双重原子检查 `scheduled_attempt_count < target_n` + 在途守卫 | A-1 / I-1 / `16` §3.3 #1 |
| 发送用量可能用陈旧 `q_common` | dispatch 先持久化再用旧量 | live 路径 fresh-preflight-first，以新鲜 `q_common` 持久化 + 发送 | A-2 / `16` §3.3 #2 |
| 不可读预检事实被当过滤器违规致命停 | step 不可读与规则违规被 conflated | `REJECT_PREFLIGHT_INCOMPLETE`（重试）vs 致命 REJECT（立停）分离；provider 完整性 fail-closed | A-3 / I-7 / `16` §3.3 #3 |
| 交易对不可用 / 仓位模式无效未致命停 | provider 把 dual=True / 非 TRADING 坍缩成 None（丢失致命信号） | domain 新增两致命事实 + provider 保留真实模式/TRADING 状态 | A-3 / `16` §3.3 #3 |
| `endpoint` 等内部字段可能入签名正文 | wire builder 曾携带 endpoint | builder 精确批准键，executor→client 全链路断言 | A-4 / `16` §3.3 #4 |
| 对账被 Start/gate/eligible 放弃 | reconcile 排在 gate 检查之后 | reconcile 移到 tick 最前，无条件运行 | A-5 / I-6 / `16` §3.3 #5 |
| 歧义查询被当失败 / 部分成交丢失 | absent 与 auth-ambiguity 未分；CANCELED 未保留部分 | 仅明确 absent 确认失败；CANCELED/EXPIRED 终结并保留 cumulative | A-5 / I-6 / `16` §3.3 #5 |
| 部分成交 / 手续费 / residual 未端到端落库 | 缺 cumulative_quote / fee 持久化 | leg 加 cumulative_quote_amt / fee_*；聚合纳入正向成交量 | A-6 / `16` §3.3 #6 |
| 致命错误未立停 / 429 改业务态 / 错误无码 | 缺 stopped 状态、固定 cooldown、无错误分类 | additive stopped + retry-after cooldown + category/code/reason_zh | A-7 / I-2/I-4/I-5 / `16` §3.3 #7 |
| 开单日志缺权威时间线 | 仅 logs/attempts，无任务事件时间线 | additive §5 `entries`（逐字字段名） | A-8 / `16` §5 / §3.3 #8 |
| 跨任务串行被误作全局串行 / 每任务可并发 pair 2 | 资格规则缺在途守卫 | 每任务串行（在途守卫）+ 跨任务独立 worker | A-9 / `16` §3.3 #9 |

---

## 5. 剩余风险与限制

1. **live 路径仅 fake-transport 覆盖**：真实 POST（`APP_HEDGE_EXECUTOR=live` + 真实凭据 + Start + 首单）按合同**仍由人工单独授权，本数据包范围外**；9 条回归均为确定性离线 fake。真实交易所行为（断网恢复、新错误码、`Retry-After` 语义）需线上灰度验证。
2. **`planned_quote_amount` 恒为 null**：§5 允许可空；attempt 行不单独存 per-attempt 价格，故本字段本轮不计算（UI 渲染 —）。如需填充需在 attempt 行加价格列（domain schema 变更，超出 surgical 范围）——建议 bookkeeper 评估。
3. **rate_limited / preflight_incomplete 任务的 `overall_result`**：§5 枚举仅含 7 值，这两类任务事件的 `overall_result` 置 null（非 attempt 结果），`next_action=waiting_query`。若 bookkeeper 要求映射到枚举内某值，需升级 §5（不得本地改名）。
4. **429 cooldown 的进程级语义**：`_enter_rate_limit_cooldown` 是进程内状态（非持久化）；进程重启后冷却丢失（可接受：冷却是本地 fail-safe，非 Binance SLA）。
5. **`_apply_task_counters` 内记事件**：阈值暂停 / 致命停止事件在计数器事务内写入 `hedge_open_log`；转移守卫（`task["status"] != STATUS_PAUSED/STOPPED`）防重复。既有 store/service/api 测试断言不受影响（全绿）。
6. **前端并行 diff**：`frontend/**` 与 `40-fix-review-2-frontend.md` 非 本会话所改；bookkeeper 合并时需按 Task B 归属处理。

---

## 6. 更改的文件

**本会话所改（后端 + 直接相关测试）：**

- `backend/hedge_open_tasks/domain.py` — `PreflightSnapshot.symbol_tradable`；`REJECT_SYMBOL_UNAVAILABLE` / `REJECT_POSITION_MODE_INVALID` + `PREFLIGHT_FATAL_REASONS` / `REJECT_TO_STOP_REASON` 扩展；`compute_preflight` 致命分类；`STATUS_STOPPED` / `STOP_REASON_*` / `stop_reason_zh`（前序）；`_qty_bounds` 逐约束回退（前序）。
- `backend/hedge_open_tasks/executor.py` — wire builders 去 `endpoint`（A-4）；`_simulate_leg` 加 `cumulative_quote`；`AttemptOutcome` 加 `error_category/error_code/error_reason_zh`（前序）。
- `backend/hedge_open_tasks/service.py` — `_FreshPreflight` + `_resolve_fresh_preflight` + `_stop_task_fatal_preflight` + `_record_preflight_incomplete`；`_dispatch_one_for_task` fresh-preflight-first；`_dispatch_live` retry-after + 429 事件；`_dispatch_to_outcome` 携带 cumulative_quote + 致命检测；`_reconcile_pending` 透传 error；`_entries_projection` + `_attempt_to_entry` / `_event_to_entry` + 模块级 §5 投影辅助；`task_to_doc` 加 `stop_reason`；`tick()` reconcile 前置。
- `backend/hedge_open_tasks/store.py` — schema（task `stop_reason`、attempt/leg 错误列）+ `_migrate`；`list_eligible_tasks` / `prepare_attempt` 硬上限 + 在途守卫；`_apply_task_counters` fatal/pause + 事件记录；`resolve_attempt` / `finalize_attempt` 致命 + 错误持久化；`resolve_leg_from_query` 透传 error；`aggregate_positions` 纳入正向成交量；`stop_task_fatal` / `record_task_event` / `list_task_event_logs`。
- `backend/services/hedge_preflight_provider.py` — `_read_position_mode` 保留真实模式；`_read_spot/perp_filters` 返回 `(filters, tradable)`；`get_snapshot` 设 `symbol_tradable` + rate-limit fail-closed。
- `backend/services/live_hedge_executor.py` — `LegDispatch` / `LiveAttemptDispatch` 加 error/retry 字段；`classify_leg_response` / `classify_query_response` 错误矩阵分类；`_send_one_leg` / `dispatch` 透传 error + retry-after。
- `backend/tests/test_hedge_domain.py` — step-unreadable 断言改 `REJECT_PREFLIGHT_INCOMPLETE`。
- `backend/tests/test_hedge_executor.py` — 两处 wire-shape 精确键集断言、去 `endpoint`。
- `backend/tests/test_hedge_service.py` — `get_logs` 键集加 `entries`。
- `backend/tests/test_hedge_api.py` — `_TASK_KEYS` 加 `stop_reason`；`get_logs` 键集加 `entries`。
- `backend/tests/test_hedge_review2_regressions.py` — **新增**，18 个测试覆盖 §3.3 全部 9 项。

**本会话未改（明确）：** `backend/app/server.py`、`backend/services/binance_signing.py`、`frontend/**`、`docs/**`、`status.json`、`70-handoff.md`、`50-review-2.md`、`15-*`、`16-*`、`60-test-output.txt`。

**并行 Task B（非本会话）：** `frontend/index.html`、`frontend/self-check.js`、`reports/.../40-fix-review-2-frontend.md`。

---

实现完成，全部自测通过。按合同**停止**——不 commit、不改 status.json / 70-handoff.md、不派发、不评审，等待 bookkeeper reconcile。
