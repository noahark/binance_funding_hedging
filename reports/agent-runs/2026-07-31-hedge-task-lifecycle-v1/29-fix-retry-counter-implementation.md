# 29-fix-retry-counter-implementation —— F1-F5 修复实现报告

- 任务：`fix-review1-retry-counter-v1`（实现者：deepseek；Human 决定改派）
- 分支：`stage/2026-07-31-hedge-task-lifecycle-v1`（开工时 `git branch --show-current` 确认）
- 评审来源：`28-review-1-codex-task3.md`（F1-F5，Bookkeeper 已逐条独立复验，`27-` §6.3）
- `rework_count`：保持 **1**（本 packet 为投递前修正，pre-dispatch packet correction 豁免）

## 1. F1 [P1] 机制替换：时间窗口 → 每腿内存重试计数器

**删除**：
- `domain.py` 的 `ABSENT_TOLERANCE_WINDOW_US`（连同「窗口」语义注释）；
- `service.py` 中全部基于 `dispatched_at_us` 的 `window_elapsed` 判定（`_reconcile_own_legs`）。

**新增**（`domain.py` 与既有常量同区）：
- `LEG_QUERY_MAX_RETRIES = 10`，对齐原 JS `getSpotOrderInfo(id, 10)`。

**实现**（`service.py`）：
- `self._leg_query_retries: dict[int, int]`（`hedge_open_leg.id -> 已查次数`，进程内存，先例同 `_rate_limit_stamp_pending`）；
- `_reconcile_own_legs`：每次 `query_leg` 后 `retries = get(leg_id, 0) + 1`、`retries_exhausted = retries >= LEG_QUERY_MAX_RETRIES`；
  - `verdict is None`（传输错误 / 5xx / 超时）未达上限 → 保持非终态继续查；达上限且 `drain_signal is None` → `SIGNAL_ORDER_STATE_UNKNOWN`（**产生点 1**，F4）；
  - 404 / -2013 未达上限 → `terminal = False`（终态收口推迟到上限）；达上限 → 判 `absent` 终态（`finalized`）；
  - 畸形 2xx（有 verdict 但 `dispatch_state == LEG_UNKNOWN_QUERYING`）达上限 → `SIGNAL_ORDER_STATE_UNKNOWN`（**产生点 2**，F4）；
  - 腿达终态 → `self._leg_query_retries.pop(leg_id)`（计数不泄漏）；
- `_run_task_worker` finally：worker 退出时 `_clear_task_leg_retries(task_id)` 清理该任务全部腿计数（含人工暂停遗留的非终态腿）。

**无锚点腿**：无 `dispatched_at_us` 的腿走完全相同的计数路径——`F1 从根上消失`（不再需要锚点即可数满并收口）。原注释「prior behaviour is unchanged」与事实相反（改动前 404 立即判 absent 终态），已随删除窗口逻辑一并订正。

**重启语义**：进程/service 重建后 dict 为空、从零重新数满 10 次；恢复路径只按既有 clientOrderId 重查、不重发。测试 `test_restart_resets_retry_counter_and_recovers_without_resend` 断言 `dispatch_calls` 不变 + 新预算下收口。

## 2. F2 [P1] inconclusive 收口不得复活 deleted/done/stopped

- 新增 `_signal_order_state_unknown_recovery(task, drain_signal, now_us)`：
  - `running` / `paused` → 走既有 `_pause_task_local`（人工暂停语义，kind 复用 `task_paused`）；
  - `deleted` / `done` / `stopped` → **不改状态**（粘性），只记录可见人工核对事件（kind `task_paused`，payload 含 reason / reason_zh / coin / direction / signal），腿保持非终态、永不重发。
- `store.py` 的 `pause_task` 未动（守卫在 service 层）。
- 测试：`test_inconclusive_cap_drain_keeps_non_running_status_sticky` 参数化三条（deleted / done / stopped），断言状态不变、`pause_reason is None`、腿非终态、`dispatch_calls == 1`、事件已记录。三条均可失败（破坏验证见 §6 之 4 同理；原实现无条件 pause → status 变 paused → 红）。

## 3. F3 [P1] 人工核对事件进入 entries 时间线

按 review-1 首选方案**复用既有 `task_paused` kind**（不新增 kind）：
- `_worker_round` 的 `SIGNAL_ORDER_STATE_UNKNOWN` 分支不再写 `kind="order_state_unknown"`；
- `_event_to_entry` 补全 `task_paused → overall_result="task_paused"`、`next_action="paused"` 映射（此前该 kind 落入 wait 分支、`overall_result=None`；顺带修正了既有 insufficient_funds / collateral_cap 暂停事件的错误投影），`error_reason_zh = payload["reason_zh"]` 保留；
- `_ENTRY_EVENT_KINDS` 已含 `task_paused`，白名单无需改动。
- API 层断言：`test_logs_entries_surfaces_order_state_unknown_manual_verification_event`（HTTP GET `/api/hedge-open-logs`，断言事件进入 entries、`overall_result=task_paused`、`next_action=paused`、`error_reason_zh` 为人工核对文案）。能失败（旧代码 kind 被过滤或映射为 wait）。

## 4. F4 [P2] 两个 signal 产生点各需独立测试

- 新增 `test_inconclusive_verdict_none_at_cap_pauses_manual_recovery`：10 次查询全返回 `None`（verdict is None 分支）→ 任务人工暂停（order_state_unknown）、腿非终态、失败计数不变、无重发。与既有畸形 2xx 测试（`test_inconclusive_at_retry_cap_pauses_for_manual_recovery_not_absent`）各自覆盖一个产生点。
- 破坏验证：删除任一产生点，只有对应测试转红（实际输出见 §6）。

## 5. F5 [P2] 迁移缺自动回归断言

`backend/tests/test_hedge_store.py` 新增三条（不碰 `store.py` 生产代码，迁移 SQL 语义保留）：
- `test_migrate_backfills_legacy_interval_default_and_is_idempotent`：旧默认 `1_000_000` → 打开 store → `500_000`；重开幂等；
- `test_migrate_preserves_custom_interval_value`：自定义 `250_000` 保留；
- `test_migrate_interval_seconds_api_shape`：`settings_to_doc(...)["interval_seconds"] == 0.5`。
- 破坏验证：删除 `_migrate` 回填 SQL → 两条测试转红（实际输出见 §6）。

## 6. 破坏验证实际输出（还原后全量复跑 1152 passed）

| 破坏 | 输出（实际） |
|---|---|
| F4 产生点 1：`verdict is None` 站点赋值为 `None` | `FAILED backend/tests/test_hedge_task_local.py::test_inconclusive_verdict_none_at_cap_pauses_manual_recovery`（1 failed） |
| F4 产生点 2：畸形 2xx 站点赋值为 `None` | `FAILED backend/tests/test_hedge_task_local.py::test_inconclusive_at_retry_cap_pauses_for_manual_recovery_not_absent`（1 failed） |
| F5：删除 `_migrate` 回填 SQL | `FAILED test_migrate_backfills_legacy_interval_default_and_is_idempotent`、`FAILED test_migrate_interval_seconds_api_shape`（2 failed, 1 passed；`preserves_custom` 不依赖回填 SQL，符合预期） |
| F1：无锚点腿不参与计数（复现 F1 根因） | `FAILED test_no_anchor_leg_404_confirms_absent_at_retry_cap`、`FAILED test_no_anchor_leg_inconclusive_pauses_at_retry_cap`（2 failed） |

注：F4 产生点 2 首次注入方式（`pass` + `if False:`）产生语法错误导致 `ERROR`，随后改用「赋值置 None」的干净破坏，以上为后者的输出。

## 7. 根因回应（原样引用并回应）

> 三条 P1 是同一个根因：**新增的收口路径没有与既有契约全面接线**——F1 未接「腿可能没有时间锚点」、F2 未接「任务状态有粘性」、F3 未接「任务级事件须进 entries」。

**回应**：三条 P1 均已接线并各有可失败测试；同族扫描清单见 §8（验收 7）。本次没有做点补丁——机制整体替换（F1）+ 状态守卫（F2）+ 事件契约补全（F3）+ 双产生点独立覆盖（F4）+ 迁移回归（F5），并交同族扫描清单。

## 8. 同族扫描清单（验收 7）

本轮新增三样东西——**重试计数机制、`SIGNAL_ORDER_STATE_UNKNOWN`、`PAUSE_REASON_ORDER_STATE_UNKNOWN`**——触碰的既有契约逐项标注：

| # | 既有契约 | 判定 | 说明 |
|---|---|---|---|
| 1 | entries 时间线（`_ENTRY_EVENT_KINDS` 白名单 + `_event_to_entry`） | **已正确接线** | F3：复用 `task_paused` kind；补全 `task_paused → overall_result/next_action=paused` 映射并保留 `reason_zh`；顺带修正既有同 kind 事件的错误投影 |
| 2 | 任务状态粘性（`STATUS_DELETED`/`DONE`/`STOPPED`） | **已正确接线** | F2：非运行态只记录事件、不改状态；running/paused 保持人工暂停语义 |
| 3 | worker 生命周期（`_run_task_worker` 退出 / `_recover_workers` 恢复 / `_pump_worker` 测试缝） | **已正确接线** | 退出清理计数；恢复从零重新数且不重发（重启测试） |
| 4 | 404 / -2013 absent 判定（mirror `_confirm_um_figures` 的「POST 刚接受时 404 是噪声」） | **已正确接线** | 未达上限 404/-2013 保持非终态；达上限判 absent；分类器（`live_hedge_executor.py`）未动 |
| 5 | 429 / rate_limited 处理 | **不适用** | 429 是 conclusive，不经计数收口；`kind="rate_limited"` 事件、settlement 计数豁免、`_rate_limit_stamp_pending` 全部未动 |
| 6 | 任务级事件 payload 形状（reason / reason_zh / coin / direction / signal） | **已正确接线** | running/paused 走 `_pause_task_local` 同形状；非运行态分支手动构造同形状 |
| 7 | `pause_reason_zh` 文案契约 | **已正确接线** | order_state_unknown 文案改为「10 次重试查询」，语义（核对后手动恢复、不重发）不变；51169 文案区（`COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`）未动 |
| 8 | `dispatched_at_us` 展示语义（`_attempt_to_entry` 的 `submitted_ts`） | **不适用** | 该字段仍用于最早下单时间展示；不再是收口判定锚点；无锚点腿 `submitted_ts` 为 None（既有行为） |
| 9 | `aggregate_positions` / 腿终态语义 | **不适用** | 未改终态判定本身，只改收口时机（计数达上限 vs 窗口耗尽） |
| 10 | store 层 / schema / 迁移 | **不适用** | 计数器纯内存，**未新增数据库列**；`_migrate` 回填 SQL 未动（F5 只加测试） |
| 11 | 前端 `HEDGE_PAUSE_REASON_LABELS` | **不适用** | 缺 order_state_unknown 标签是已记录的非阻塞后续项（packet 明确），`frontend/` 未动 |
| 12 | API 契约（task doc / settings doc / logs 响应） | **已正确接线** | task 投影字段未变；settings `interval_seconds` 形状未变（F5 加固）；logs/entries 结构未变 |
| 13 | entries 排序与分页（rank / cursor） | **不适用** | 事件仍 `_ENTRY_EVENT_RANK=1`，合并排序未变 |
| 14 | worker exit reason 枚举 | **不适用** | 未新增退出原因；`_worker_exit` 路径未动 |
| 15 | 恢复发现（`_recover_workers` drain-only fallback，paused/done/deleted/stopped） | **已正确接线** | 重启后仍被 drain；计数从零开始，符合重启语义 |

清单外未发现遗漏。

## 9. test_5b 最小适配（Human 授权）

packet 的「删除 `ABSENT_TOLERANCE_WINDOW_US`」+「全量全绿」与「不得改动 `test_hedge_review2_regressions.py`」直接冲突：该文件 `test_5b` 第 428 行 `clock.t += D.ABSENT_TOLERANCE_WINDOW_US` 是上一轮专为窗口机制加的适配行，机制替换后必然失败（删常量 → AttributeError；留常量 → 404 第 2 次查询不达上限、`fail_count == 1` 断言红）。

Human 2026-08-02 经 ask 裁定：**允许最小适配 test_5b**。适配内容：占位查询（None）把每条腿的计数推进到上限前一步，第 10 次查询为 404；核心断言 `fail_count == 1` 与「先歧义保持未知、后显式 404 确认失败」语义逐字不变。该文件其余部分未动。

## 10. 回归与边界

- 全量：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/ -q` → **1152 passed**（基线 1140 + 新增 12：task_local +8、store +3、api +1）。输出存 `64-fix-retry-counter-test-output.txt`。
- 边界：未改 `live_hedge_executor.py` / `frontend/` / 429 处理 / 51169 文案区 / `private_client.py`；未新增数据库列；500ms 默认、迁移 SQL 语义、抖动移除、`_confirm_um_figures` 语义未动。
- 改动文件：`backend/hedge_open_tasks/domain.py`、`backend/hedge_open_tasks/service.py`、`backend/tests/test_hedge_task_local.py`、`backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_api.py`、`backend/tests/test_hedge_review2_regressions.py`（仅 test_5b，Human 批准）。

## 11. `data/` 红线留痕（BK-T3-002 加严要求）

本轮运行过的、可能触及 `data/` 的命令清单：

- 全部测试运行：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/...`（含全量与单测）——全部使用 pytest `tmp_path`（系统临时目录），**无任何命令指向 `data/`**；
- 破坏验证：3 个内联 `python3 - <<EOF` 脚本——只改写 `backend/hedge_open_tasks/service.py` 与 `store.py` 源码（随后从 `/tmp/*.bak` 还原），**不触碰任何数据库**；
- 无 sqlite3 直接调用、无指向 `data/` 的探针或副本命令。

**结论**：本轮未写入 `data/` 下任何数据库；`git status --short data/` 为空。若 Bookkeeper 判定某次运行不确定，我可补充说明——但本轮所有命令路径均为源码或 tmp_path。
