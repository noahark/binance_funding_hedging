# 28-review-1-codex-task3 —— review-1（codex）

## 评审元数据

- 任务：`review-1-codex-task3`
- 评审者：codex（provider：openai）
- 分支：`stage/2026-07-31-hedge-task-lifecycle-v1`
- 固定区间：`9faa716396cbbe67ebeec272ad6b3dd443bba583..d8522dfd6f4a3fa64c27d383a900a8e7f84df7fc`
- 当前工作区 `HEAD`：`10b4c2e9fd7089caaf0d0b57c14b8f7010c81714`；评审期间未移动 `HEAD`，受审源码均由固定 Git 对象读取。
- 风险：`HIGH_RISK`（订单状态判定、资金可见性、实盘写路径）。

## 总结

评审结论为 `REWORK`。已提交代码对带有 `dispatched_at_us` 的正常新路径实现了 500ms 节奏、404 容忍及 inconclusive 人工暂停；但历史/崩溃间隙无时间锚点会永久重查，inconclusive 收口会把 deleted/done/stopped 任务改回 paused，且新暂停事件不会进入统一 entries 时间线。这些是本交付引入或触碰的高风险接缝问题。

## 重点判断

### 1. 容忍窗口与资金可见性

对带时间锚点的腿，`service.py:1264-1268`、`:1297-1305` 的窗口判断符合 D20：窗口内 404/`-2013` 保持非终态，窗口耗尽后才确认 `absent`；窗口耗尽的 `verdict is None` 或 `UNKNOWN_QUERYING` 不会写成 `absent`，而是保留腿并请求人工核对。非终态腿不会被 `aggregate_positions` 当作已确认成交，故窗口内会有预期的暂时可见性滞后，但没有因此制造一条假的 absent 终态；恢复仍按已保存 clientOrderId 查询，不重发。

这项结论只对有 `dispatched_at_us` 的腿成立。无锚点路径见 F1；非运行态任务的恢复路径见 F2。

### 2. `PAUSE_REASON_ORDER_STATE_UNKNOWN`

后端已加入 `ALL_PAUSE_REASONS`、`pause_reason_zh` 和 API task projection；该分支不调用计数结算，因此不会增加 `skip_counters` 或失败计数。带锚点的 running/paused 任务恢复会继续使用 clientOrderId，不会重发。

但新增事件 kind 与 entries 过滤契约未接通，见 F3。现有前端 `HEDGE_PAUSE_REASON_LABELS`（`frontend/index.html:3629-3631`）没有该值，会按既有“未知值原样展示”规则显示 `order_state_unknown`，而不是后端的中文文案；这属于非阻塞的前端后续项，不能掩盖 F3 的后端日志缺口。

### 3. BK-T3-002 实盘库写入

我采信 `27-bookkeeper-verification-task3-500ms.md:3` 的事实核验：`data/hedge-open-tasks.sqlite3` 在开发期间从 `1_000_000` 变为 `500_000`，且实现者关于长驻服务自动应用新代码的归因已被证伪。写入值正确，当前证据未显示任务、订单、持仓或资金数据被改动，但 packet 明确禁止写入 `data/`，写入者和具体触发过程仍未完全确定。

结论：这不构成我本次代码 F1-F5 之外的“代码修复”发现，但构成独立的发布门。即使代码返工后 review-1 通过，也不得自动合并、部署或启用实盘；Human 必须先在 `PROJECT_STATE.md` 记录基础上明确接受或拒绝该过程违规，并补齐后续观察/防护决定。

### 4. 两个 `SIGNAL_ORDER_STATE_UNKNOWN` 产生点

`service.py:1274-1275` 处理 `verdict is None`（传输错误、5xx、超时），`:1351-1358` 处理带对象但 `dispatch_state == UNKNOWN_QUERYING` 的畸形 2xx。两者不是重复保险，而是两种不同输入形状，应各自有独立断言。Bookkeeper 的“单点破坏仍全绿、同时破坏才失败”只能证明现有测试被另一条路径遮蔽，不能证明任一站点可删除；当前新增测试主要覆盖畸形 2xx，缺少窗口耗尽后 `verdict is None` 的独立断言，见 F4。

## 问题记录（REWORK，均为 `in-range`）

### F1 — [P1] 无 `dispatched_at_us` 的在途腿永不耗尽窗口

范围：`in-range`。

证据：

- `service.py:1264-1268` 只有在 `dispatched_at_us is not None` 时才把窗口置为耗尽；注释称无锚点“保留旧行为”。
- `service.py:1303-1305` 却会把所有窗口未耗尽的 `absent` 强制改为 `terminal=False`。
- `service.py:1274-1275` 与 `:1351-1358` 的人工收口也都要求 `window_elapsed`，因此无锚点腿既不会判 absent，也不会进入 `SIGNAL_ORDER_STATE_UNKNOWN`。
- 当前实现可复现输出：

  ```text
  {"status": "running", "fail_count": 0, "pause_reason": null, "terminal": [0, 0], "window_us": 5000000}
  ```

  探针在临时 SQLite 中将两条非终态腿的 `dispatched_at_us` 置空，推进时钟超过 5 秒，再注入两个 404；任务仍 running、两腿仍非终态，后续会无限重查。

影响：这不仅覆盖旧库行，也覆盖 `prepare_attempt` 已落库、但进程在 `resolve_attempt`/`mark_leg_querying` 前崩溃的真实 crash gap。它违背“同一窗口收口”并让人工无法获得明确的未知状态。

修复要求：为无锚点腿定义明确且可终止的 fail-closed 行为：可使用已持久化且可靠的 attempt 时间作为锚点，或直接将其转入 `SIGNAL_ORDER_STATE_UNKNOWN`/人工暂停；不得让 404 永久保持非终态，也不得将未知直接判为 absent。补充无锚点、时钟超过窗口、404 与 inconclusive 两类测试，并证明恢复仍不重发。

### F2 — [P1] inconclusive 收口会复活 deleted/done/stopped 任务

范围：`in-range`。

证据：

- `service.py:1197-1207` 对 `SIGNAL_ORDER_STATE_UNKNOWN` 无条件调用 `_pause_task_local`。
- `store.py:1765-1769` 的 `pause_task` 无条件写入 `status = paused`。
- 探针分别将有在途腿的任务置为 `deleted`、`done`、`stopped`，推进到窗口后注入畸形 2xx，输出为：

  ```text
  {"before": "deleted", "after": "paused", "pause_reason": "order_state_unknown"}
  {"before": "done",    "after": "paused", "pause_reason": "order_state_unknown"}
  {"before": "stopped", "after": "paused", "pause_reason": "order_state_unknown"}
  ```

影响：删除、完成、致命终止是既有生命周期语义；启动恢复明确会对这些状态做 drain-only 处理。新分支在窗口耗尽后把它们改成可重新启动的 paused，破坏状态粘性并可能改变后续操作面。现有测试只覆盖 `post_delete` 后的 absent 收口，没有覆盖 inconclusive 收口。

修复要求：保留 `deleted`、`done`、`stopped` 的原状态；这些状态仍可保留非终态腿并记录可见人工核对事件，但不得通过 `pause_task` 改成 paused。对 running/paused 继续使用人工暂停语义。为三种非运行态分别增加窗口耗尽 inconclusive 测试，断言状态不变、腿非终态、无重发。

### F3 — [P1] `order_state_unknown` 暂停事件被 entries 时间线过滤

范围：`in-range`。

证据：

- `service.py:1204-1206` 写入事件 kind `order_state_unknown`。
- `_ENTRY_EVENT_KINDS`（`service.py:84-90`）没有该值；`_entries_page`（`:841-842`）按该集合过滤。
- 探针显示 SQLite 中确有 `event_kinds: ["order_state_unknown"]`，但 `svc.get_logs(None, None)["entries"]` 只有 unresolved attempt，没有该人工暂停事件。

影响：高风险订单状态不明时，任务卡可能有 pause_reason，但统一日志/entries 时间线没有“为何暂停、要求人工核对”的审计记录；操作人员和 review-2 无法从既有日志契约重建这次安全收口。

修复要求：优先让该路径复用已有 `task_paused` kind，确保现有 entries 映射为 `overall_result=task_paused`、`next_action=paused` 并保留 `reason_zh`；或新增 kind 时同步加入 `_ENTRY_EVENT_KINDS` 与 `_event_to_entry` 的明确映射。增加 API entries 断言，确认事件可见且显示人工核对语义。

### F4 — [P2] 两个 signal 站点缺少独立的 `verdict is None` 测试

范围：`in-range`。

当前实现逻辑本身区分了传输无结论与畸形 2xx，但新增 `test_inconclusive_past_window_pauses_for_manual_recovery_not_absent` 使用的是两个 `LEG_UNKNOWN_QUERYING` 对象，未覆盖 `verdict is None` 分支。单点破坏全绿的现象正是此覆盖缺口，不能作为“双保险成立”的充分证据。

修复要求：新增一条窗口耗尽后 `query_leg` 返回 `None` 的独立测试，断言任务人工暂停、腿非终态、失败计数不变、无重发；保留现有畸形 2xx 测试，确保删除任一 signal 产生点都会使对应测试失败。

### F5 — [P2] 既有数据库迁移没有自动回归断言

范围：`in-range`。

`store.py:523-535` 的 SQL 语义正确，Bookkeeper 的临时副本实测也证明了旧默认 `1_000_000` 回填到 `500_000`、自定义 `250_000` 保留且幂等。但 `backend/tests/test_hedge_store.py` 的新增/既有迁移测试只在没有 settings 行时让新 store seed 默认值，未构造“已有 settings 行为 1 秒”和“已有自定义值”的场景；完整 1140 测试因此无法在迁移被删掉时转红。

修复要求：在允许的 `backend/tests/test_hedge_store.py` 中加入旧默认回填、自定义值保留、重开幂等和 `interval_seconds` API 形状测试；至少让删除 `HedgeOpenStore._migrate` 的回填 SQL 使测试失败。

## 非阻塞观察与已通过项

- 固定区间内未改 `backend/services/live_hedge_executor.py`、`frontend/`、`private_client.py`、`data/`；429/rate_limited 既有站点未被改写；`test_hedge_review2_regressions.py` 只增加受限授权的时钟推进。
- 受审区间的全量回归：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/ -q` → `1140 passed in 57.46s`。聚焦后端链路 145 passed；API 测试 35 passed。沙箱第一次运行 API 因禁止临时 socket bind 失败，提升权限后的只读重跑通过。
- 404 窗口内保持非终态、窗口耗尽后 anchored 404 确认 absent，以及 anchored inconclusive 转人工暂停的真断言均通过；实现报告中的破坏验证也证明了新增断言不是空转。
- 默认 500ms、迁移回填、移除抖动、`_confirm_um_figures` 语义对齐和固定边界检查通过；但以上通过项不抵消 F1-F5。

## 修复要求总表

1. 修复 F1：无时间锚点不得无限重查，且不得把未知判作 absent；补测试。
2. 修复 F2：inconclusive drain 不得把 deleted/done/stopped 改成 paused；补三种状态测试。
3. 修复 F3：人工暂停事件必须进入统一 entries 时间线并保留 `reason_zh`；补 API entries 测试。
4. 修复 F4/F5：分别为 `verdict is None` 和既有 settings 迁移补独立、可失败的自动测试。
5. 修复后由 Bookkeeper 更新状态与返工计数，重新封存新的固定提交区间，再按 HIGH_RISK 路由 review-1 → review-2；BK-T3-002 仍需 Human 单独裁定。

评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/28-review-1-codex-task3.md
修复要求: reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/28-review-1-codex-task3.md#修复要求总表
