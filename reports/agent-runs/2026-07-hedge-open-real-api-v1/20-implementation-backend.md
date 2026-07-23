# 20 — Task A 实现报告：Hedge Open Real API v1（后端）

> 模型：`glm-5.2[1m]`（Claude Code 会话）。分支：`stage/2026-07-hedge-open-real-api-v1`。
> 数据包：`[HARNESS-EXECUTOR-CONTRACT v1]`，`task-A-claude-glm.prompt.md`。
> 本报告为 Task A 后端实现者的完整、未编辑产出。不 commit、不改 status.json、不改 70-handoff.md、不派发/评审其他模型。

---

## 0. Session 元信息

- **Session ID**：unavailable（glm-5.2[1m] runtime 未暴露 provider-native Session ID）。
- **Session ID 来源**：unavailable。
- **原始输出路径**：`reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md`。
- **本地北京时间**：2026-07-23 22:21 CST（`date` 取得）。
- **下一步模型**：bookkeeper。
- **下一步任务**：collect Task A report, reconcile the backend diff, and run integration evidence。

---

## 1. 实际改动的文件

### 1.1 修改的既有文件（Task A 范围内）

| 文件 | 性质 | 说明 |
|---|---|---|
| `backend/hedge_open_tasks/domain.py` | 改 | 接受态分类（`leg_is_accepted`/`classify_attempt`/`build_leg_exposure` 改为以 `orderId` 为信号）；`resolve_status_after_attempt` 新增 `failure_pause_threshold` 参数、`>=` 暂停、single-leg 改为 advisory；新增 `PAIR_SINGLE_LEG`/`ALL_PAIR_OUTCOMES`、`LEG_*` 派发态、`ATTEMPT_*` 重定义、Boundary C `BLOCK_*` 枚举。 |
| `backend/hedge_open_tasks/store.py` | 改 | 新增 `hedge_open_attempt`/`hedge_open_leg` 表与索引；`hedge_open_task` 加 5 列（`scheduled_attempt_count`/`accepted_pair_count`/`consecutive_submission_failures`/`failure_pause_threshold`/`pause_reason`）；durable-before-send `prepare_attempt`；`resolve_attempt`（per-leg terminal）/`_apply_task_counters`/`mark_leg_querying`/`finalize_attempt`/`resolve_leg_from_query`/`list_non_terminal_legs`；`list_eligible_tasks` 改为 `status=running AND success_count<target_n`；`_migrate` additive-forward + 回填 `failure_pause_threshold=3`。 |
| `backend/hedge_open_tasks/service.py` | 改 | durable-before-send + per-task 调度 `tick()`；`_dispatch_one_for_task`/`_dispatch_simulated`/`_dispatch_live`/`_reconcile_pending`/`_fresh_preflight_ok`/`_live_dispatch_capable`/rate-limit cooldown；live `fill-all` 禁同步 POST（仅 arm）；移除 `exposure_alert` 门控（§4.5）；`task_to_doc` 加 5 字段；新增 `credentials_present`。 |
| `backend/config.py` | 改 | 新增 `hedge_executor`（`disabled`/`live`，`from_env` 验证）+ 专用 `binance_hedge_api_key`/`binance_hedge_api_secret`（`repr=False`）。 |
| `backend/app/server.py` | 改 | `_build_hedge_service` 在 `live` 模式构造 `LiveHedgeExecutor`+`HedgePreflightProvider`+凭据并注入；新增 sanitized `hedge_open_execution_blocked` 生命周期事件。 |
| `backend/tests/test_hedge_domain.py` | 改 | 分类/exposure/状态机测试改为接受态语义、`>=` 阈值、advisory exposure。 |
| `backend/tests/test_hedge_store.py` | 改 | 旧 `apply_attempt_outcome` 改为 `prepare_attempt`+`resolve_attempt`（`_apply` helper）；新增 round-1 迁移兼容性测试。 |
| `backend/tests/test_hedge_service.py` | 改 | exposure 改 advisory、`>=` 暂停、default-off 注释更新。 |
| `backend/tests/test_hedge_api.py` | 改 | `_TASK_KEYS` 加 5 字段；exposure HTTP 测试改 advisory。 |
| `backend/tests/test_private_client.py` | 改 | urlopen 守卫 allowed 集加两个 hedge HTTP 客户端（§3.7 守卫扩展的必要部分）。 |

### 1.2 新建文件（Task A 范围内）

| 文件 | 说明 |
|---|---|
| `backend/services/hedge_open_live_client.py` | 唯一 hedge-open 出站 HTTP 表面：7 端点 ALLOWLIST（host 硬编码 `papi.binance.com`）、deny-by-default、单 signer（`binance_signing.signed_payload`）、单次传输无重试、可注入 `urlopen`。 |
| `backend/services/live_hedge_executor.py` | 类型化 live 执行器：`classify_leg_response`/`classify_query_response`（recon §3.3 阶梯）、并发双腿 `dispatch`、best-effort 单次 client-ID 查询（永不重发）、`query_leg`、`dispatch_to_outcome`、`leg_is_terminal_fill`。 |
| `backend/services/hedge_preflight_provider.py` | 只读预检数据源：公共 exchangeInfo（spot/perp）+ ticker price + 签名 PM 读（balance/positionSide/rateLimit）；任一缺口返回 `None`（fail closed）。 |
| `backend/tests/test_hedge_open_live_client.py` | 单签名/路径映射/单次传输/响应分类（13 用例）。 |
| `backend/tests/test_live_hedge_executor.py` | 分类阶梯/并发 dispatch/查询/rate-limit/无凭据 fail-closed（37 用例）。 |
| `backend/tests/test_hedge_purity.py` | hedge_open_tasks 纯度守卫 + 7 端点 allowlist 冻结 + gate-fires-before-signing。 |

### 1.3 未改动的允许文件

- `backend/hedge_open_tasks/executor.py`、`backend/hedge_open_tasks/scheduler.py`：未改。`executor.py` 的 `build_spot_order_params`/`build_perp_order_params`/`_client_order_ids`/`RecordTransportExecutor` 被 live executor 与 service 复用；per-task 每秒节奏在 `service.tick()` 内实现，无需改 scheduler。这是 surgical 选择。

### 1.4 不在 Task A 范围（明确声明）

`frontend/index.html`、`frontend/self-check.js`、`reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md` 在工作树中显示为已改动/未跟踪，但**这些属于 Task B（前端）**，**不是**本 Task A 的改动。Task A 严格遵守 prompt：禁止改动 `frontend/**`。本会话未对前端文件做任何修改。

---

## 2. schema / migration 选择

- **Additive-forward only**（breakdown §3.9）：`CREATE TABLE IF NOT EXISTS` 新增 `hedge_open_attempt`、`hedge_open_leg`；`hedge_open_task` 的 5 个新列通过 per-column guarded `ALTER TABLE ADD COLUMN`（带 `NOT NULL DEFAULT`）。
- **回填**：`failure_pause_threshold` 回填冻结默认 `3`；其余计数列回填 `0`；`pause_reason` 回填 `NULL`。
- **幂等**：`_migrate` 用 `PRAGMA table_info` 守卫，重复打开同一 DB 不报 double-ALTER（由 `test_migrate_adds_new_columns_to_round1_db_and_keeps_rows` 覆盖）。
- **旧数据保留**：round-1 的 `hedge_open_task`/`hedge_open_fill`/`hedge_open_log`/`hedge_open_settings` 表与既有行原样保留可读；旧 route 不删。
- **不可变 attempt + 可变 leg**：`hedge_open_attempt` 记录不可变核心（uuid/seq/direction/q_common/preflight 指纹/position 模式/pair_outcome/log_ref）；`hedge_open_leg` 记录可变核对（client_order_id/endpoint/request_shape/dispatch_state/order_id/exchange_status/累计 base/quote/fee/terminal）。

---

## 3. 已执行命令与原样结果摘要

### 3.1 编译验证

```text
$ .venv/bin/python -m py_compile backend/hedge_open_tasks/service.py   # OK
$ .venv/bin/python -m py_compile backend/hedge_open_tasks/{store,domain,executor,scheduler}.py  # OK
$ .venv/bin/python -m py_compile backend/services/{hedge_open_live_client,live_hedge_executor,hedge_preflight_provider}.py  # OK
$ .venv/bin/python -m py_compile backend/{config.py,app/server.py}     # OK
$ .venv/bin/python -c "from backend.app import server; from backend.app.server import _build_hedge_service"  # import OK
```

### 3.2 必须执行的测试命令（prompt 强制）

```text
$ .venv/bin/python -m pytest backend/tests -q
........................................................................ [  8%]
...（省略中间行）...
.............................................................          [100%]
856 passed in 43.31s
```

**全量 `backend/tests`：856 passed，0 failed。**

分文件明细（hedge 相关）：

```text
test_hedge_domain.py       54 passed
test_hedge_store.py        12 passed
test_hedge_executor.py     （既有，未改）通过
test_hedge_service.py      14 passed
test_hedge_api.py          23 passed
test_hedge_purity.py       9 passed   （新建）
test_hedge_open_live_client.py  13 passed  （新建）
test_live_hedge_executor.py     37 passed  （新建）
test_private_client.py     49 passed   （守卫扩展后）
```

### 3.3 默认关闭证明（内联）

```text
disabled mode OK: record executor, no dispatch, no creds -> real POST unreachable
live client empty creds OK: credentials_present=False -> adapter will not POST
live client fake creds OK: credentials_present=True (Start+preflight gate downstream)
DEFAULT-OFF PROOF: a real POST requires APP_HEDGE_EXECUTOR=live AND credentials AND Start AND fresh preflight
```

- 默认 `disabled`：`HedgeOpenTaskService` 用 `RecordTransportExecutor`（无 `dispatch` 方法）→ 真实 POST 不可达。
- `live` + 空凭据：`HedgeOpenLiveClient.credentials_present=False` → 执行器拒发；`hedge_open_execution_blocked` 事件触发。
- `live` + 假凭据：`credentials_present=True`，但真实 POST 仍被 durable Start gate + 新鲜预检 + per-send `_live_dispatch_capable` 三重门控。
- CI 从不构造 live executor（`_svc` 测试 helper 不注入），`test_full_scenario_makes_zero_urllib_calls` 用 monkeypatch 证明 hedge-open 全路径零 urlopen 调用。

---

## 4. 与冻结合同的映射

| 冻结合同条款 | 实现位置 | 证据 |
|---|---|---|
| 正向=margin MARKET BUY + UM MARKET SELL；反向反之；同 `q_common` 并发 | `domain.direction_to_leg_actions` + `executor.build_{spot,perp}_order_params` + `LiveHedgeExecutor.dispatch`（threading 双腿） | `test_direction_mapping_*`；`test_dispatch_*` |
| margin `sideEffectType=NO_SIDE_EFFECT`、UM `positionSide=BOTH`、开盘无 reduceOnly、无 quoteOrderQty | `domain.SIDE_EFFECT_NO_SIDE_EFFECT`；`build_*_order_params`（无 reduceOnly/quoteOrderQty） | `executor.py` record_payload shape；`test_post_*` |
| POST 前同事务落 attempt + 两个确定性 client ID | `store.prepare_attempt`（单 `with self._lock, self._conn:` 事务） | `test_apply_*`（经 `_apply` helper） |
| orderId=受理（非成交）；查询到终态 | `domain.leg_is_accepted`/`classify_attempt`；`store._apply_task_counters`（按 category 计数，不看 fill） | `test_classify_*`；`test_apply_success_*` |
| 两腿都 orderId 才 accepted pair + 清零连续计数；查询确认未受理才计失败；`>=` 阈值（默认 3）暂停 | `_apply_task_counters`（SUCCESS 重置 consecutive；FAILED++；`resolve_status_after_attempt` `>=`） | `test_apply_failed_at_threshold_pauses` |
| timeout/5xx 先按 origClientOrderId 查询，永不盲目重发 write POST | `LiveHedgeExecutor._send_one_leg`（unknown→单次 query）+ `query_leg`；client 单次传输无重试 | `test_dispatch_unknown_leg_*`；`test_single_transport_attempt_no_retry` |
| live 仅 `APP_HEDGE_EXECUTOR=live`+durable Start+fresh preflight 通过窄 adapter | `service._live_dispatch_capable`+`_fresh_preflight_ok`+`is_start_gate_on`；`server._build_hedge_service` | `test_live_mode_without_injected_executor_*`；默认关闭证明 |
| disabled/record 零网络写入；live fill-all 禁同步 POST | `RecordTransportExecutor.posted=False`；`post_fill_all` live 分支仅 arm | `test_full_scenario_makes_zero_urllib_calls`；`post_fill_all` 源码 |
| scheduler 每个 eligible running task 各自 dispatch，不只 eligible[0] | `service.tick()` 遍历 `list_eligible_tasks()` 全集 | `tick()` for-loop |
| 交换 rate-limit cooldown 作 shared safety gate | `service._in_rate_limit_cooldown`/`_enter_rate_limit_cooldown`（60s） | `RATE_LIMIT_COOLDOWN_US` |
| endpoint/参数/query 受 recon 事实约束 | `hedge_open_live_client.ALLOWLIST`（7 端点，recon §3.1/§3.2/§4.1） | `test_allowlist_is_exactly_the_frozen_seven_endpoints` |
| `hedge_open_tasks/**` 不引入签名/网络原语；唯一 signer | 包纯度（grep 证明）；`hedge_open_live_client` 复用 `binance_signing.signed_payload` | `test_hedge_domain_package_*`；`test_single_signer`（既有） |
| Decimal 固定小数串 + 各腿 filter 独立处理 | `domain.decimal_lcm`/`floor_to_grid`/`_check_common_quantity`；preflight 各腿 filter | `test_decimal_lcm_*`；`test_preflight_*` |
| 后端/前端共享 JSON 字段严格按 breakdown §3.4，不改字段名/不删旧字段 | `service.task_to_doc`（旧字段全保留 + 5 新字段） | `test_create_returns_201_exact_task_field_set_dry_run`（`_TASK_KEYS` 全集断言） |
| smooth/WebSocket 后续阶段 | 未实现（contract 允许；`mode=smooth` 在 create 拒绝） | `test_smooth_mode_rejected_as_invalid_field` |

---

## 5. 未解决问题 / 有意偏差

1. **预检 GET 端点归属（有意偏差 vs breakdown §4.3 字面）**：§4.3 字面说预检 provider "重用 `private_client.py`"，但 `private_client.py` 的 allowlist 冻结且缺 `/papi/v1/um/positionSide/dual`（weight 30）与 `/papi/v1/rateLimit/order`（weight 1）——这两端点对 live 预检必需。解决方案：让 hedge 自己的 live client（`hedge_open_live_client.py`）拥有这 3 个预检 GET 端点（复用唯一 signer `binance_signing`），preflight provider 通过注入的 live client 读取私有项、通过可注入 `urlopen` 读公共 exchangeInfo。这是与 §4.3 字面的有意偏差，已在本报告与 `hedge_open_live_client.py`/`hedge_preflight_provider.py` 模块 docstring 中记录。

2. **CI 不执行真实 POST（§3.7）**：无 PAPI PM testnet。CI 仅用 fake/record transport 证明行为；任何真实 POST/私有读/凭据访问/首个真实任务是本阶段之外的人工授权范畴。本 Task A 从未真实 POST、从未读取真实凭据、从未启用 Start/live。

3. **`_failed_outcome` 语义**：executor 抛异常（仅 record/disabled 路径，正常不触发）记为 `ATTEMPT_FAILED`（保留 round-1 containment 行为，会增加计数）。这是 containment 选择，非新行为。

4. **单腿暴露是 advisory（§4.5）**：`STATUS_EXPOSURE_ALERT` 仍保留于 `ALL_STATUSES`（向后兼容/列表过滤），但 `resolve_status_after_attempt` 不再设置它——single-leg exposure 记录 `leg_exposure` 但不冻结调度、不计入暂停阈值。task doc 的 `leg_exposure` 字段保留。

5. **`leg_exposure` 在后续 SUCCESS 后不清除**：`_apply_task_counters` 对 SUCCESS 不覆盖 `leg_exposure`，故最近一次单腿暴露的值保留到下次单腿事件覆盖。这是"最近一次单腿暴露快照"语义，非 bug；如需在 SUCCESS 时清除可后续调整。

---

## 6. git diff 概要

```text
$ git status --short
 M backend/app/server.py
 M backend/config.py
 M backend/hedge_open_tasks/domain.py
 M backend/hedge_open_tasks/service.py
 M backend/hedge_open_tasks/store.py
 M backend/tests/test_hedge_api.py
 M backend/tests/test_hedge_domain.py
 M backend/tests/test_hedge_service.py
 M backend/tests/test_hedge_store.py
 M backend/tests/test_private_client.py
 M frontend/index.html          # 不属 Task A（Task B）
 M frontend/self-check.js       # 不属 Task A（Task B）
?? backend/services/hedge_open_live_client.py
?? backend/services/hedge_preflight_provider.py
?? backend/services/live_hedge_executor.py
?? backend/tests/test_hedge_open_live_client.py
?? backend/tests/test_hedge_purity.py
?? backend/tests/test_live_hedge_executor.py
?? reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md  # 不属 Task A

$ git diff --stat（仅 Task A 的 backend 改动）
 backend/app/server.py                |  62 ++-
 backend/config.py                    |  31 ++
 backend/hedge_open_tasks/domain.py   | 185 ++++++---
 backend/hedge_open_tasks/service.py  | 359 ++++++++++++++---
 backend/hedge_open_tasks/store.py    | 750 +++++++++++++++++++++++++++++++----
 backend/tests/test_hedge_api.py      |  34 +-
 backend/tests/test_hedge_domain.py   |  99 +++--
 backend/tests/test_hedge_service.py  |  46 +-
 backend/tests/test_hedge_store.py    | 140 +++++--
 backend/tests/test_private_client.py |  19 +-
 10 files changed, ~1700 insertions(+), ~290 deletions(-)
```

新建 3 个 services 层模块 + 3 个测试文件（行数未计入 diff --stat 的 untracked 部分）。

---

## 7. 完成声明

完成 Task A 后端实现：默认关闭的真实 PAPI hedge-open 执行器（durable-before-send + 接受态分类 + client-ID 查询恢复 + per-task 每秒调度 + `>=` 阈值暂停 + live fill-all 禁同步 POST），保留 disabled/record 零网络写入与全部只读/borrow/round-1 行为。全量 `backend/tests` 856 passed。

完成后停止，等待 bookkeeper；未 commit、未改 status.json、未派发/评审其他模型。

---

*本地北京时间：2026-07-23 22:21 CST（`date` 取得）*
