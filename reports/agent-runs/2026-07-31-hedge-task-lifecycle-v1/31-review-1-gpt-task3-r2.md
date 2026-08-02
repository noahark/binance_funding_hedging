# 31-review-1-gpt-task3-r2 —— review-1 复审（GPT）

## 评审元数据

- 任务：`review-1-gpt-task3-r2`
- 评审角色：Reviewer / review-1，REWORK 后第 2 轮
- provider：openai
- 固定区间：`9faa716396cbbe67ebeec272ad6b3dd443bba583..f70e6ca20ac283e78db8d14a78efe4018d3564c1`
- 受审交付：`f70e6ca20ac283e78db8d14a78efe4018d3564c1`
- 当前工作区 `HEAD`：`165598e3978aabf19bd6f670281fc53691e82660`；评审未移动 `HEAD`，所有结论只基于固定区间及只读运行结果。
- 风险：`HIGH_RISK`（订单状态判定、人工暂停、实盘发布门）。

## 总结

评审结论为 `REWORK`。F1 的计数机制在顺序执行、无锚点腿、重启恢复和正常 worker 退出场景下成立；F2 的三种终态测试也通过。但两处并发接缝仍未修复：旧 worker 的计数清理可与同任务新 worker 重入交错而提前清零；F2 使用 worker 开始时取得的旧任务快照，删除任务在查询期间变为 `deleted` 后仍可能被无条件写回 `paused`。两者均为本次交付触碰的 `in-range` 生命周期/安全问题，阻塞接受。

## F1-F5 逐条结论

| 项 | 结论 | 独立判断与证据 |
|---|---|---|
| F1 | **部分修复** | `domain.py:548` 的 `LEG_QUERY_MAX_RETRIES=10`，`service.py:1309-1311` 按 leg ID 计数；404/-2013 只在第 10 次收口，inconclusive 在第 10 次转人工核对；无 `dispatched_at_us` 的 404 与 inconclusive 测试均通过。重启测试证明计数清零且不重发。未修复项见下方 F1-P1：worker 清理与重入存在竞态，且 `close()` 可在 worker 清理前关闭 store，使清理被吞掉。 |
| F2 | **部分修复** | `_signal_order_state_unknown_recovery` 对调用时快照中的 `deleted/done/stopped` 只记事件不改状态，三态参数化测试通过；但 `_worker_round` 在 `service.py:1220-1225` 先取 task 再执行外部查询，`service.py:1246` 将旧快照传入恢复函数，`store.py:1765-1769` 的 `pause_task` 仍无条件写 `paused`。查询期间发生 `post_delete`（`service.py:687-696`）即可复活已删除任务。见下方 F2-P1。 |
| F3 | **已修复** | 复用 `task_paused`，并在 `service.py:934-947` 补全 `overall_result=task_paused`、`next_action=paused`；API entries 用例独立通过，`reason_zh` 保留。 |
| F4 | **已修复** | `verdict is None` 与畸形 2xx 两个 signal 产生点各有独立测试；实现报告与 Bookkeeper 原始破坏输出均显示删除任一点会使对应测试失败。 |
| F5 | **已修复** | 旧默认回填、幂等、自定义值保留和 `interval_seconds` 形状均有测试；实现报告/Bookkeeper 破坏输出显示删除迁移回填 SQL 会使两项测试失败。 |

## F1-P1：worker 清理和同任务重入存在提前清零竞态（in-range）

代码路径如下：

1. `_run_task_worker` 的 `finally` 在 `service.py:1147-1149` 先从 `_workers` 删除当前线程。
2. 之后才在 `service.py:1150-1155` 调用 `_clear_task_leg_retries`。
3. `ensure_worker` 在 `service.py:1090-1113` 看到 registry 已无该 task 后可以立即启动新 worker。
4. 新 worker 的 `service.py:1309-1310` 将新查询次数写入 `_leg_query_retries`；旧 worker 随后在 `service.py:1164-1166` 按同一 task 枚举 legs 并 `pop`，会把新 worker 的计数提前清零。

这不是多任务的 key 冲突：不同任务的 leg ID 是独立的；问题是同一 task 的 worker handoff 没有与计数清理原子化。生产入口 `post_start`、`post_fill_once`、`post_fill_all` 和 `_recover_workers` 都可以在 registry 空窗内触发 `ensure_worker`。结果是该 leg 可能重新获得完整 10 次预算，延迟本应到达的收口，甚至在反复重入时失去预算上限。

另外，`close()` 在 `service.py:508-510` 只调用 `stop()` 后立即关闭 store。worker 仍可能在 `finally` 进入 `_clear_task_leg_retries`；`service.py:1167-1168` 把关闭 store 的异常吞掉后，该 service 实例的计数会残留。这是同一清理覆盖问题的关闭路径表现。

修复要求：将 worker handoff 与旧计数清理串行化（例如在持有 `_workers_lock` 的清理/交接区间内完成，或使用 worker generation 防止旧 worker 清理新 worker 的计数）；并为 `close()` 等退出路径提供确定的 join/清理顺序。新增一个可控 barrier 的并发回归：阻塞旧 worker 清理、启动同 task 新 worker、让新 worker 写入查询计数，断言旧 worker 不能删除新计数，并断言新 worker 仍按剩余预算收口。

## F2-P1：状态守卫使用旧快照，删除期间仍可写回 paused（in-range）

`_worker_round` 在 `service.py:1220` 读取 task 后，于 `service.py:1225` 调用 `_reconcile_own_legs`。该函数会在没有 store 锁的情况下调用 executor；因此 HTTP `post_delete` 可以在查询期间把同一 task 改成 `deleted`。查询达到 inconclusive 上限后，`service.py:1246` 仍把最初的 `running` 快照传给 `_signal_order_state_unknown_recovery`，`service.py:1613-1616` 遂调用 `_pause_task_local`；最终 `store.pause_task` 的 `UPDATE`（`store.py:1765-1769`）没有状态条件，会把 `deleted` 改成 `paused`。

当前三态测试是在 drain 前直接设置状态，无法覆盖这个时间窗，因此它们不能证明“状态粘性”对并发状态变更成立。`post_delete` 的注释还明确要求 worker 不被中断、继续 drain，这使该交错是设计允许的正常入口，而非仅测试缝隙。

修复要求：在应用 `SIGNAL_ORDER_STATE_UNKNOWN` 前重新读取权威 task 状态，或让 store 层采用仅在当前状态为 `running/paused` 时才更新的条件写；若条件更新未命中，仍只记录事件、不改状态。保留三种静态状态测试，并增加在 executor 查询阻塞期间执行 `post_delete` 的并发回归，断言最终状态仍为 `deleted`、腿非终态、无重发且 entries 有人工核对事件。

## 四项重点

### 1. F1-F5 是否真正修复

F3、F4、F5 达到要求；F1、F2 的顺序路径已修复但并发语义未闭合，故不能称“真正修复”。本次独立运行：

- F1/F2/F4/F5 关键用例：`13 passed in 4.80s`；
- F3 API entries 用例（获准本地临时 socket 后）：`1 passed in 0.60s`；
- 原始全量回归证据 `64-fix-retry-counter-test-output.txt`：`1152 passed`。

这些结果证明新增断言可执行，但没有覆盖上述两个竞态；不得用全绿回归替代并发边界判断。

### 2. F3 顺带修复的范围定性和消费者行为

`_event_to_entry` 的缺少 `task_paused` 映射由 base 中早已存在的 `8af3f22d` 引入；在 base `9faa716` 上的 `git blame` 仍显示该映射缺陷来自 `8af3f22d`，早于本次 base。因此该缺陷本身标注为 **`pre-existing-release-critical`**：它影响 `insufficient_*` / `collateral_cap_full` 这类资金/安全相关暂停事件在统一 entries 时间线中的结果语义；不是本次 F3 新引入，且其修复是 F3 接线不可分离的必然结果，不另立返工项。当前 delivery 已将其修好，不留下该发布风险。

行为确实改变，但属于既有错误投影的纠正：

- `task_paused` 事件在 entries 中由 `overall_result=None`、`next_action=waiting_query` 改为 `overall_result=task_paused`、`next_action=paused`；`reason_zh` 保持原 payload 值。
- entries API 及使用该投影的前端会得到正确的暂停语义；entries 字段形状、排序、分页不变。
- 原始 `logs`/SQLite 事件行和其它非 entries 读取方不改变；没有新增 kind 或改变 429 行为。

### 3. 同族扫描清单是否穷尽

`29-` §8 的 15 项清单覆盖了静态契约，并正确覆盖了 entries、状态、404、429、payload、文案、API、恢复和 schema 边界。但它**不穷尽**运行时接缝：

- 清单 #3 将 worker 生命周期标为已正确接线，却没有单列“registry 删除 → 计数清理 → 新 worker handoff”的并发契约，遗漏 F1-P1；
- 清单 #2 将状态粘性标为已正确接线，却只验证已有状态快照，遗漏“查询期间状态变更后仍使用旧快照”的契约，遗漏 F2-P1。

清单中 #5（429）、#8（展示用 dispatched 时间）、#10（没有新增 schema 列）、#11（明确排除的前端标签）、#13（排序分页）、#14（未新增 worker exit 枚举）按本次静态范围可标为不适用；#10 不能替代运行时 persistence/recovery 检查，但该部分应与 #15 分开审查。修复 dispatch 必须把上述两个并发接缝加入同族清单，并为清单外站点给出不适用理由。

### 4. BK-T3-002 发布门

发布门**维持原判，未解除**。本轮只读检查显示：

- `data/hedge-open-tasks.sqlite3` mtime 仍为 `2026-08-01 23:45:48 +0800`；
- 只读查询 `interval_us` 仍为 `500000`；
- `git status --short data` 无输出；
- `d8522df..f70e6ca` 没有 `data/` 文件变化。

这证明本轮没有新增写入，但不能抹除 2026-08-01 的历史实盘库写入事故。即使修复后 review-1/review-2 通过，合并、部署或实盘启用仍须 Human 单独裁定。

## 其它验收与边界

- 固定 `base_sha..delivery_sha` 已核验，未移动 `HEAD`。
- `live_hedge_executor.py`、`frontend/` 无区间改动；429 逻辑和 51169 文案区未改。
- `test_hedge_review2_regressions.py` 的区间差异仅为 `test_5b` 驱动方式调整；Human 授权事实已由 `30-` §7 确认，核心 `fail_count == 1` 断言未改。
- 区间 `git diff --check` 唯一报告的是早期控制报告 `23-cadence-implementation.md:82` 的尾随空格，属于控制提交上下文，不是本次受审代码或测试交付；未据此提出产品返工。

## 评审闭环

评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/31-review-1-gpt-task3-r2.md
修复要求: reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/31-review-1-gpt-task3-r2.md#F1-P1-worker-清理和同任务重入存在提前清零竞态-in-range；reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/31-review-1-gpt-task3-r2.md#F2-P1状态守卫使用旧快照删除期间仍可写回-paused-in-range
