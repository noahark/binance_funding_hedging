# 44-fix-review-1-backend-r3（packet 65 · Review-1 后端第 5 次有界返工）

执行调度：`65-fix-review-1-backend-r3.dispatch.md`（stage `2026-07-hedge-open-real-api-v1` 用户授权的第 5 次、严格有界的后端返工）。
实现者：GLM `glm-5.2[1m]`（唯一后端返工实现者，HARNESS-EXECUTOR-CONTRACT v1；禁止调用/启动/转派其它模型或 adapter）。
业务权威：`26-user-authorized-settlement-and-pause-fix.md`（用户 2026-07-25 第 5 次授权，§4 固定业务规格、§6 的 R1–R8、§9 原始 reviewer `fix_start_prompt`，用户已在 §4.4 选定 **A：加字段**）+ `21-task-local-runtime-and-manual-pause-amendment.md` + `15-immediate-loop-and-open-log-amendment.md`。
P1 证据：`64-review-1-backend-r3.md`（Reviewer Opus 5 REWORK + 末尾 schema-valid JSON verdict + 完整 `fix_start_prompt`）。
前序实现：`40-fix-review-1-backend-r2.md`、`42-final-guardian-scanner-fix.md`（packet 62/63 已实现且必须保留）。

按合同：**只改 dispatch 允许的后端文件 + 本报告 + 60-test-output.txt（仅追加）；未读凭据、未连 Binance、未发真实 POST、未启 live/Start、未 commit、未改 status.json / 70-handoff.md / 任何 PRD/设计/ADR/契约文档（15/16/17/19/21/23/24/25/26）、未改 frontend/** / scheduler.py / server.py / 环境配置；未新增全局守护、周期扫描器、timer、自动补单/撤单/平仓/借还/转账、WebSocket 或平滑开仓。**

---

## 1. 改动文件（git status / diff --stat 实测）

| 文件 | 性质 | 说明 |
| --- | --- | --- |
| `backend/hedge_open_tasks/domain.py` | 改 | 新增 `WORKER_EXIT_*` 稳定机器枚举（8 个）+ `ALL_WORKER_EXIT_REASONS` 元组（P2-2） |
| `backend/hedge_open_tasks/store.py` | 改 | schema 加 `last_worker_exit_reason TEXT`（task）/ `rate_limited INTEGER NOT NULL DEFAULT 0`（attempt）+ 加性迁移 + 读取；`set_task_status` 转 RUNNING 清粘滞 pause_reason/pause_reason_zh/last_worker_exit_reason（P1-1）；`_apply_task_counters` 加 `skip_counters` 早分支（仅推导 pair_outcome + 写 leg_exposure，不动计数/阈值/状态/事件）（P2-1）；重写 `settle_attempt_no_counters` 由两腿真实事实推导 accepted/single_leg/confirmed_failed；新增 `mark_attempt_rate_limited` / `set_worker_exit_reason` |
| `backend/hedge_open_tasks/service.py` | 改（调度层核心） | `task_to_doc` 加派生 `worker_active`（三态）+ `last_worker_exit_reason`；新增 `_worker_active_for` / `_doc`，9 处调用改走 `_doc`；`post_pause`/`post_delete` 移除 `_wake_worker` 中断（P1-2：worker 自行 drain 完再退），删孤儿 `_wake_worker`；`ensure_worker` 启动时清 exit_reason；`_run_task_worker` 异常路径写 `worker_error`；`_pump_worker` 与真实 worker 共享 stop-event 初始化（P3）；新增 `_worker_exit` helper，`_worker_round` 各退出分支写稳定 reason；`_reconcile_own_legs` 改读 **逐次尝试** `rate_limited` 标志（P1-1）；`_recover_workers` drain-only 回退加 `STATUS_DELETED`（P1-2）；`_dispatch_live` 429 分支 `mark_attempt_rate_limited` |
| `backend/services/live_hedge_executor.py` | **未改** | attempt 标记/分类无需调整（429 leg 分类、`error_category` 已由 packet 62 就位） |
| `backend/tests/test_hedge_task_local.py` | 改 | 新增 R1–R8 八个确定性离线回归 + 4 个构造 helper；`test_5` / `test_r5` 的 recovery 断言改用 `ensure_worker` spy，消除“drain worker 在 start() 内已退出”的快照 race（zero sleep race） |
| `backend/tests/test_hedge_api.py` | 改 | 冻结字段集 `_TASK_KEYS` 加 `worker_active` + `last_worker_exit_reason` |
| `reports/.../60-test-output.txt` | 追加 | packet 65 五条自测命令真实原始输出 |

未触动：`test_hedge_store.py` / `test_hedge_service.py` / `test_hedge_review2_regressions.py` / `test_hedge_domain.py` / `test_hedge_purity.py` —— `skip_counters` 默认 `False`、字段用 `.get()` 容错，既有用例无需适配（全部继续通过）。

---

## 2. 修复项逐条（根因 → 修复 → 代码位置）

### P1-1　429 恢复后粘滞 pause_reason / “本组不计失败”误依赖任务级字段

- **根因**：(a) `set_task_status(RUNNING)` 不清 `pause_reason`/`pause_reason_zh`，人工恢复后旧 429 原因粘在卡上；(b) `_reconcile_own_legs` 用 `task.pause_reason == RATE_LIMITED` 决定是否走 `settle_attempt_no_counters` —— 一旦恢复清了 pause_reason，429 那组的 drain 就误走 `finalize_attempt`，**消耗连续失败计数**，下一组即使两腿 FILLED 也可能被旧粘滞字段连累。
- **修复**：
  1. `store.set_task_status`：转 `RUNNING` 时一次性清 `pause_reason = NULL, pause_reason_zh = NULL, last_worker_exit_reason = NULL`（store.py `set_task_status`）。
  2. 把“本组不计失败”的决定改为 **逐次尝试事实**：`_dispatch_live` 命中 429 时 `mark_attempt_rate_limited(attempt_id)` 写 attempt 行的 `rate_limited` 列；`_reconcile_own_legs` 改读 `get_attempt(attempt_id).rate_limited`，与任务级 pause_reason 解耦（service.py `_reconcile_own_legs` / `_dispatch_live`）。
- **结果**：恢复清字段后，429 那组仍按自身限频事实走 no-counter 结算；下一组两腿 FILLED 正确成为 `accepted_pair` 并 +1 计数（R1）；后续 3 次确认失败仍触发阈值暂停（R2）。

### P1-2　人工 pause/delete 必须由本任务 worker 排空在飞订单；DELETED 卡重启也恢复

- **根因**：`post_pause`/`post_delete` 调 `_wake_worker`（set stop_event），**中断** worker —— 在飞订单未 drain 到终态 worker 就退了；`_recover_workers` 的 drain-only 回退集合是 `(PAUSED, STOPPED)`，不含 `DELETED`，DELETED 卡带非终态腿在进程重启时无人恢复。
- **修复**：
  1. 移除 `post_pause`/`post_delete` 的 `_wake_worker` 调用，并删除因此成为孤儿的 `_wake_worker` 方法。worker 不再被中断：下一轮 `_worker_round` 先 `_reconcile_own_legs` 把在飞腿查到终态并结算（Q2 drain-before-exit），再因 `status != RUNNING` 退出 —— **不开新组**。
  2. `_recover_workers` drain-only 回退改为 `(PAUSED, STOPPED, DELETED)`，DELETED 卡带非终态腿在一次性 startup handoff 被各自 drain worker 恢复（service.py `_recover_workers`）。
- **结果**：pause（R3）/ delete（R4）后 worker 仍把两腿查到终态、结算、退出，`scheduled_attempt_count` 不增；DELETED 卡重启由一次性 recovery drain 到终态、零重发、状态保持 DELETED sticky（R5）。

### P2-1　`settle_attempt_no_counters` 必须由两腿真实事实推导结果

- **根因**：旧实现无脑写 `PAIR_CONFIRMED_FAILED`，既不区分 accepted/single_leg，也不写 single_leg 的 advisory `leg_exposure`。
- **修复**：`settle_attempt_no_counters` 改读两腿完整 row，按 `order_id` 存在性推导分类（两腿有=SUCCESS、一腿=SINGLE_LEG、都无=FAILED），single_leg 调 `_exposure_from_legs` 构造 exposure，再经 `_apply_task_counters(..., skip_counters=True)` 拿到真实 `pair_outcome` 并写 `leg_exposure`；`_apply_task_counters` 新增 `skip_counters` 早分支：仅推导 pair_outcome + 写 leg_exposure，**不动** accepted/success/fail/consecutive/status/pause_reason/stop_reason/事件（store.py `_apply_task_counters` / `settle_attempt_no_counters`）。
- **结果**：429 落一腿 + 另一腿 FILLED → `pair_outcome == single_leg`、`leg_exposure` 非空、`fail_count` 不变（R6）。

### P2-2（用户选定 A）　后端权威可观测字段 `worker_active` / `last_worker_exit_reason`

- **修复**：
  - `worker_active`：后端派生三态。`_worker_active_for` 在 **非** live-dispatch-capable（dry-run/record/disabled）时返回 `None`（不适用，绝不是 False）；live 时在 `_workers_lock` 下返回 `bool(thread is not None and thread.is_alive())`。`task_to_doc` 经新 `_doc` wrapper 注入。
  - `last_worker_exit_reason`：可空加性 SQLite 列。`_worker_round` 各退出分支经 `_worker_exit` 写稳定枚举（`stopped_event`/`task_missing`/`task_not_running`/`start_gate_off`/`target_reached`/`preflight_incomplete`/`preflight_fatal`）；`_run_task_worker` 异常路径写 `worker_error`；`ensure_worker` 启动 + `set_task_status(RUNNING)` 进入时清空（都幂等）。
  - 两键加入 `_TASK_KEYS` 冻结字段集；**不新增 entries 事件类型、不动前端**（domain.py `WORKER_EXIT_*`；store.py schema/migrate/读写；service.py `_worker_active_for`/`_doc`/`_worker_exit`/`_worker_round`/`ensure_worker`/`_run_task_worker`；test_hedge_api.py `_TASK_KEYS`）。
- **结果**：preflight 不完整 → worker 退出（task 仍 RUNNING）记 `preflight_incomplete`；worker 持有 executor 存活期间 `worker_active is True`，退出后 `is False`；人工 Start 重新进入 RUNNING 清空（R7）；dry-run 卡 `worker_active is None`（R8）。

### P3　`_pump_worker` 与真实 worker 共享 stop-event 初始化

- **修复**：`_pump_worker` 开头在 `_workers_lock` 下注册并 clear per-task stop_event（与 `ensure_worker` 一致），使 pause/delete drain 路径在测试 seam 下不因 `service.stop()` 残留的 set 状态短路（service.py `_pump_worker`）。

---

## 3. R1–R8：旧代码缺口 → 修复后证据（全部 zero network / zero sleep race）

| # | 测试 | 旧代码缺口 | 修复后证据（断言） |
| --- | --- | --- | --- |
| R1 | `test_r1_rate_limit_resume_next_pair_counts_and_clears_pause` | 恢复后 pause_reason 粘滞；reconcile 依赖任务级 pause_reason → 429 组误增 fail_count，下组计数错乱 | 恢复后 `pause_reason is None`；429 组 `fail_count==0` 且 `pair_outcome==confirmed_failed`；下组两腿 FILLED → `accepted_pair_count==1`、`success_count==1`、存在 `pair_outcome==accepted_pair` |
| R2 | `test_r2_rate_limit_resume_then_three_confirmed_fails_triggers_threshold` | 同 R1，且无法证明阈值仍生效 | 429 恢复后 3 次确认失败 → `status==paused`、`pause_reason==consecutive_submission_failure`、`fail_count==3`、`consecutive==3` |
| R3 | `test_r3_pause_drains_inflight_to_terminal_and_settles_no_new_pair` | `post_pause` 用 `_wake_worker` 中断 worker，在飞腿不 drain | pause 后 worker 仍 `query_calls>=2`、两腿 `terminal`、该组 `pair_outcome` 非 NULL、`scheduled_attempt_count` 不增（pair2 未派发） |
| R4 | `test_r4_delete_drains_inflight_to_terminal_and_settles_no_new_pair` | 同 R3（delete） | delete 后同构断言；`status==deleted` sticky |
| R5 | `test_r5_deleted_card_nonterminal_legs_recovered_on_restart` | `_recover_workers` 回退不含 `STATUS_DELETED`，DELETED 卡非终态腿重启无人恢复 | 新实例 `start()` 一次性 recovery 经 spy 命中 `ensure_worker(doc)`；两腿 drain 到终态；`dispatch_calls==1`（零重发）；`query_calls>=2`；`status==deleted` sticky |
| R6 | `test_r6_rate_limit_one_leg_other_filled_single_leg_exposure` | `settle_attempt_no_counters` 总写 confirmed_failed，不推导 single_leg / 不写 leg_exposure | 429 一腿 + 另一腿 FILLED → `pair_outcome==single_leg`、`leg_exposure` 非空（`leg=="spot"`）、`fail_count==0` |
| R7 | `test_r7_live_worker_active_tri_state_and_exit_reason` | 无 `worker_active` / `last_worker_exit_reason` 字段 | 子A preflight 不完整→worker 退出、`worker_active is False`、`last_worker_exit_reason=="preflight_incomplete"`、task 仍 RUNNING；子B worker 持有 executor 阻塞期间 `worker_active is True`（Event 同步，非 sleep race）；子C 人工 Start 后 `last_worker_exit_reason is None` |
| R8 | `test_r8_dry_run_worker_active_is_none_not_false` | dry-run 无该字段（或误报 False） | record/disabled 卡 `worker_active is None`（不是 False） |

测试均用 `_pump_worker` seam（同步、无 pacing 等待）或真实线程 + `threading.Event`/`join` 同步驱动；**无 sleep race**。

---

## 4. 迁移幂等性

两列均为**加性前向迁移**，经 `_migrate` 的 `PRAGMA table_info` 守卫：

- `hedge_open_task.last_worker_exit_reason TEXT`（默认 NULL）
- `hedge_open_attempt.rate_limited INTEGER NOT NULL DEFAULT 0`

`_migrate` 仅在列缺失时 `ALTER TABLE ... ADD COLUMN`，已存在则跳过 → 旧库二次打开幂等、新库一次到位。`test_5`/`test_r5`（同 DB 跨实例）与全量 905 用例隐式覆盖。

---

## 5. H-1 / packet 62 / 63 不回归

- **H-1 固化保留**：live `start()` 仍是“一次 `_recover_workers()` 后返回”，不启动 `HedgeOpenScheduler`；live `tick()` 仍是安全空操作；人工 Start 仍只启动命名 task。本次仅向 `_recover_workers` 的 drain-only 回退集合**追加** `STATUS_DELETED`，未动 `start()`/`tick()`/`post_start` 的启动拓扑 —— `test_6a`/`test_6b`/`test_6c` 全部继续通过。
- **packet 62/63 行为保留**：`test_1`–`test_4b`、`test_5`（race 已修）全部通过；每任务单有界 worker、同卡 pair 串行、两腿并发、跨卡互不阻塞、对账绝不放弃、先持久后发送（ADR-2）、`target_n` 原子硬上限、无 orderId 只按 clientOrderId 查询且永不重发、store 锁内不调/不持有 executor（Q6）—— 均未触动。
- **`-2010` 未确认仍 fatal stop**：`test_4b` 继续通过（fatal 路径未改）。

---

## 6. worker 字段范围：只后端、前端是 follow-up

`worker_active` / `last_worker_exit_reason` 仅由后端 `task_to_doc` 注入 task API 文档。**前端未动**（`frontend/**` 在合同禁止清单内）：任务卡暂不渲染这两个字段，属明确的后续 follow-up，不在本包范围。冻结字段集 `_TASK_KEYS` 已包含两键，故 wire 契约对前端已是“可选读取、缺失降级”安全。

---

## 7. 剩余风险

- **`worker_active` 是尽力派生快照**：反映 `_workers` 注册表在调用瞬间的存活状态，真实生产 worker 的启动/退出时序由 OS 调度；并发 Start 由 `_workers_lock` 串行化，仍是 best-effort 观测，非强一致锁。
- **`test_5`/`test_r5` race 已用 `ensure_worker` spy 消除**（不再依赖“drain worker 是否已在 `start()` 内退出”的快照），但根本上 recovery worker 的异步退出意味着 `worker_active` 在 `start()` 返回后可能已转 `False` —— 这正是字段的设计语义（瞬时观测），而非缺陷。
- **未引入**任何全局守护 / 周期扫描器 / timer / 自动补单撤单平仓借还转账 / WebSocket / 平滑开仓（合同遵守）。

---

## 8. 精确自测（原始输出已追加 `60-test-output.txt`）

| 命令 | 结果 |
| --- | --- |
| CMD #1 指定十组测试（task_local/service/review2/store/domain/api/purity/open_live_client/live_hedge_executor/hedge_executor） | **229 passed** |
| CMD #2 `pytest backend/tests -q`（全量） | **905 passed** |
| CMD #3 `node frontend/self-check.js` | **全部自检通过** |
| CMD #4 `scripts/tests/test_validate_stage_dispatch_protocol.py` | **55 passed** |
| CMD #5 `git diff --check` | exit 0（无空白错误） |

---

实现完成，全部自测通过。按合同**停止**——不 commit、不改 status.json / 70-handoff.md / 契约文件、不派发评审、不自行判定验收，等待 bookkeeper 重算 changed-file 指纹、reconcile 本次 packet-65 返工、并调度更新后的 Review-1。

---

当前 Session ID: unavailable (Claude Code / glm-5.2 harness 不暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md
本地北京时间: 2026-07-25 CST
下一步模型: bookkeeper
下一步任务: recompute the changed-file fingerprint, reconcile the packet-65 Review-1 backend r3 rework, and dispatch the updated Review-1
