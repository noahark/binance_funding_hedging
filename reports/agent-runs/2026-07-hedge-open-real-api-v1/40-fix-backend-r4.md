# 40 — Task A R4 修复报告：Hedge Open Real API v1（后端）

> 模型：`glm-5.2[1m]`（Claude Code 会话，Task A 后端原实现者）。
> 分支：`stage/2026-07-hedge-open-real-api-v1`。
> 数据包：`backend-r4-fix.prompt.md`（`[HARNESS-EXECUTOR-CONTRACT v1]`），范围 = bookkeeper `13-r4-diff-reconciliation.md` 的 R4-1 + R4-2 两项 P1。
> 本报告为 R4 修复的完整、未编辑产出。不 commit、不改 status.json / 70-handoff.md / 前端 / docs，不派发或评审其他模型。

---

## 0. Session 元信息

- **Session ID**：unavailable（glm-5.2[1m] runtime 未暴露 provider-native Session ID）。
- **Session ID 来源**：unavailable。
- **原始输出路径**：`reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md`。
- **本地北京时间**：2026-07-23 23:05:02 CST（`date` 取得）。
- **下一步模型**：bookkeeper。
- **下一步任务**：reconcile R4 fixes, rerun integration evidence, and create H_A/H_B commits。

---

## 1. 修复范围与未改项

**修复（bookkeeper `13-r4` 的两项 P1）：**

- **R4-1**：`/api/hedge-open-logs` 响应不暴露 attempt 时间线 → 在**同一响应**增量加 first-class `attempts` 数组，直接投影 durable `hedge_open_attempt` + 两条 `hedge_open_leg`，覆盖 PREPARED/UNKNOWN_QUERYING/ACCEPTED_OR_QUERYING/resolved。
- **R4-2**：`tick()` 串行同步 dispatch eligible task → 每个 eligible running task 在自己的 worker 上独立 dispatch，慢卡的 live preflight/POST/查询不阻塞他卡本 tick 提交。

**未改（prompt 明确不要改 / 不在 R4 范围）：**

- disabled/record 默认语义（零真实 POST）、`recvWindow` 数值、`quoteOrderQty` 禁止、fixed `q_common` 并发、failure threshold、live `fill-all` 禁同步 POST、filter/Decimal/no-resend 规则——全部保持。
- 不引入全局产品一对一秒锁；不增加 auto-repair/close/borrow/repay/transfer；不改变 timeout→client-ID 查询、durable-before-send。
- `backend/services/**` 未改（R4 两项均在 `backend/hedge_open_tasks/**` 内完成）。
- 前端、docs、status.json、70-handoff.md、`20-implementation-backend.md` 未改。工作树中 `frontend/**` 与 `20-implementation-frontend.md` 属 Task B，未触碰。

---

## 2. R4-1 逐项修复：attempt 时间线投影

### 2.1 store（`backend/hedge_open_tasks/store.py`）

新增 `list_attempts_page(limit, cursor_ts, cursor_id) -> list[(attempt, spot_leg, perp_leg)]`：

- newest-first，`ORDER BY created_at_us DESC, id DESC`，cursor 语义镜像 `list_logs_page`（`ts_us:row_id`），应用于 `(created_at_us, id)`。
- 每条附两条 leg（`ORDER BY leg ASC` → `{"spot": ..., "perp": ...}`），leg 缺失为 `None`。
- 覆盖 PREPARED/QUERYING/resolved：attempt 行在 durable-before-send 事务里已存在（早于任何 log 行），所以一个在途的 live pair（含 `UNKNOWN_QUERYING` leg）仍被投影。

### 2.2 service（`backend/hedge_open_tasks/service.py`）

新增模块级序列化函数（与 `task_to_doc`/`log_to_doc` 同一层，冻结字段名，Decimal 字符串）：

- `_leg_to_doc(leg)`：投影 §3.4 per-leg 形状 —— `client_order_id`、`order_id`、`status`（= `exchange_status`）、`cumulative_base_qty`、`cumulative_quote_amt`、`avg_price`（= `cumulative_quote_amt / cumulative_base_qty`，base 为 0 时 `None`）；spot leg 仅在已记录时携带 `fee_amount`/`fee_asset`。
- `attempt_to_doc(attempt, spot_leg, perp_leg)`：投影 §3.4 attempt 文档 —— `task_id`（additive，供 UI 关联）、`attempt_id`（= `attempt_uuid`，与 legacy log 的 `attempt_id` 同源）、`attempt_seq`、`direction`、`q_common`、`pair_outcome`、`spot`、`perp`、`residual`、`ts`。`residual = spot_base − perp_base`（Decimal 字符串，§3.3 "sign per direction" 作说明性注解，不引入方向取反，避免过度设计）。

`get_logs(cursor_str, limit_raw)` 改为返回三键：

```python
return 200, {
    "logs": [log_to_doc(r) for r in rows],              # legacy，不变
    "attempts": [attempt_to_doc(a, s, p) for (a, s, p) in attempt_rows],  # R4-1 增量
    "next_cursor": next_cursor,                          # 仍跟踪 logs（legacy 契约不变）
}
```

legacy `logs` 列表、`next_cursor`（基于 log 行 `ts_us`/`id`）、record-transport payload 语义全部不变。

### 2.3 API 形状（实际投影示例）

resolved attempt（record fill，forward，两腿 FILLED）：

```json
{
  "logs": [{"id": 1, "task_id": "T", "ts": "…Z", "attempt_id": "<uuid>",
            "kind": "record_transport", "payload": {"transport": "dry_run_record", "posted": false, …}}],
  "attempts": [
    {"task_id": "T", "attempt_id": "<uuid>", "attempt_seq": 1, "direction": "forward",
     "q_common": "0.5", "pair_outcome": "accepted_pair",
     "spot": {"client_order_id": "hgo-<uuid>-s", "order_id": "dryspot-<uuid>", "status": "FILLED",
              "cumulative_base_qty": "0.5", "cumulative_quote_amt": "0.5", "avg_price": "1"},
     "perp":  {"client_order_id": "hgo-<uuid>-p", "order_id": "dryperp-<uuid>", "status": "FILLED",
              "cumulative_base_qty": "0.5", "cumulative_quote_amt": "0.5", "avg_price": "1"},
     "residual": "0", "ts": "…Z"}
  ],
  "next_cursor": null
}
```

PREPARED/querying attempt（durable-before-send 后、resolve 前；无 log 行）：

```json
{"logs": [],
 "attempts": [
   {"task_id": "T", "attempt_id": "<uuid>", "attempt_seq": 1, "direction": "forward",
    "q_common": "0.5", "pair_outcome": null,
    "spot": {"client_order_id": "hgo-<uuid>-s", "order_id": null, "status": null,
             "cumulative_base_qty": "0", "cumulative_quote_amt": "0", "avg_price": null},
    "perp":  {"client_order_id": "hgo-<uuid>-p", "order_id": null, "status": null,
             "cumulative_base_qty": "0", "cumulative_quote_amt": "0", "avg_price": null},
    "residual": "0", "ts": "…Z"}],
 "next_cursor": null}
```

单腿 exposure（spot FILLED / perp REJECTED）→ `pair_outcome: "single_leg"`、`residual: "0.5"`（字符串，非 float）。

前端兼容性：`frontend/index.html` 的 `extractHedgeAttempts(doc)` 扫描 `doc.attempts`（也兼容 `fills`/`logs`/`entries`），条目含 `attempt_seq`/`pair_outcome`/`spot`/`perp` 即采纳，leg 渲染 `order_id`/`client_order_id`/`status`/`cumulative_base_qty`/`cumulative_quote_amt`/`avg_price`（+ spot `fee_*`）。本次后端投影字段与之逐字对齐；`node frontend/self-check.js` 的 attempt 时间线用例通过（见 §5）。

### 2.4 R4-1 测试

- `test_get_logs_includes_attempts_projection_for_record_fill`：record fill 后 `get_logs` 返回三键 `{logs, attempts, next_cursor}`；attempt 含全部冻结字段；两腿 FILLED + 累计/加权均价；`residual == "0"` 且为字符串；legacy log/cursor 不退化。
- `test_get_logs_attempts_includes_prepared_querying_attempt`：直驱 `store.prepare_attempt` 留一个 PREPARED attempt（无 log），`attempts` 仍投影（`pair_outcome is None`、leg `status/order_id is None`、`avg_price is None`、`residual == "0"`），`logs == []`。
- `test_get_logs_attempts_residual_is_signed_decimal_no_float`：单腿 spot fill → `residual == "0.5"`（字符串）、`pair_outcome == "single_leg"`。
- `test_logs_includes_additive_attempts_timeline`（HTTP）：`/api/hedge-open-logs` 响应含 `attempts` 数组，§3.4 字段逐字、`residual` 字符串、legacy `logs`/`next_cursor` 并存。

---

## 3. R4-2 逐项修复：每卡独立异步节拍

### 3.1 service（`backend/hedge_open_tasks/service.py`）

`tick()`：保留 due/Start/rate-limit 三道全局 gate 与 `_last_tick_mono` cursor 纪律不变；把原先对 eligible 的同步 for-loop：

```python
for task in eligible:
    try: self._dispatch_one_for_task(task, now_us)
    except Exception: pass
```

替换为并发 dispatch：

```python
self._dispatch_eligible_concurrently(eligible, now_us)
```

新增两个方法：

- `_dispatch_eligible_concurrently(eligible, now_us)`：为每个 eligible task 起一个 daemon worker 线程（`target=self._dispatch_one_for_task_contained`），全部 `start` 后再逐一 `join`。每个 task 在自己的 worker 上跑 `_dispatch_one_for_task`，所以**一个卡的慢 executor 调用（live preflight/POST/查询）不阻塞另一个卡本 tick 的提交**。join 保证本 tick 的所有 pair 提交完成后再进下一 tick（一 task 每秒一对，无同 task 跨 tick 重入）。
- `_dispatch_one_for_task_contained(task, now_us)`：per-task containment 包装，一卡异常绝不停 sibling 卡的 worker；dispatch 本体仍是 `_dispatch_one_for_task`（durable-before-send、no-resend 不变）。

### 3.2 不变量保持（关键）

- **无产品级全局一对一秒锁**：唯一的 global cadence 是 tick 入口的 Start gate + exchange rate-limit cooldown（safety gate），与 `05-cadence-resolution.md` 一致。
- **两腿在一对内并发不变**：单 task 内的双腿并发仍由 live executor 自己的 two-leg 线程负责（R4-2 只在 task 之间加并发，不动 pair 内并发）。
- **durable-before-send / no-resend 不变**：worker 调 `_dispatch_one_for_task` 时**不持有 service 锁**；store 自身 RLock 仍串行化其短事务（`prepare_attempt`/`resolve_attempt`），所以同一 task 不会被两个 worker 同时 prepare，durable-before-send 原子性保持；timeout→client-ID 查询（永不重发 write POST）路径未动。
- **tick 重入安全**：`tick()` 仍持有 `self._lock`（`threading.Lock`）至 worker join 完成，序列化 tick against itself，避免两个 scheduler tick 重叠导致同 task 重复 dispatch。
- **不增加** auto-repair/close/borrow/repay/transfer。

### 3.3 R4-2 测试（确定性，不访问网络、不依赖 sleep race）

`_BlockingExecutor`：record/dry-run transport，在 `execute()` 入口 `entered_count += 1` 后阻塞在 `release` Event 上（`release.wait(timeout=10)`），测试释放后才返回 success outcome。线程安全，两个 task worker 可同时阻塞。

- `test_tick_dispatches_eligible_tasks_concurrently`：两个 eligible running task，`tick()` 在后台线程跑（因 tick 会 join worker）。断言**两个 task 都进入 dispatch**（`entered_count >= 2`）发生在 `release.set()` **之前**——若 dispatch 串行，第一个 worker 会永远阻塞、第二个永远不进入，`entered_count` 卡在 1，超时 fail。释放后两 worker 完成、`tick()` 返回 True、两 task 各 `scheduled_attempt_count == 1`。这是确定性的并发证明（Event 为门，非 sleep race）。
- `test_tick_slow_card_does_not_block_other_card_submission`：路由 executor 让卡 1 阻塞、卡 2 走 fast executor。断言在卡 1 仍阻塞时，卡 2 已完成本 tick 提交（`scheduled_attempt_count == 1`）——证明慢卡不延迟他卡的同 tick 提交。释放卡 1 后两者皆完成。

---

## 4. 已执行命令与原样结果

### 4.1 编译

```text
$ .venv/bin/python -m py_compile backend/hedge_open_tasks/service.py backend/hedge_open_tasks/store.py
COMPILE OK
```

### 4.2 hedge 子集（先跑）

```text
$ .venv/bin/python -m pytest backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_store.py -q
.......................................................                  [100%]
55 passed in 13.11s
```

### 4.3 全量 backend（prompt 强制）

```text
$ .venv/bin/python -m pytest backend/tests -q
........................................................................ [  8%]
........................................................................ [ 16%]
........................................................................ [ 25%]
........................................................................ [ 33%]
........................................................................ [ 41%]
........................................................................ [ 50%]
........................................................................ [ 58%]
........................................................................ [ 66%]
........................................................................ [ 75%]
........................................................................ [ 83%]
........................................................................ [ 91%]
......................................................................   [100%]
862 passed in 43.74s
```

**全量 `backend/tests`：862 passed，0 failed。**（Task A 原实现基线 856 + R4 新增 6 个用例 = 862。）

### 4.4 前端 self-check（prompt 强制；前端属 Task B，本修复未改前端）

```text
$ node frontend/self-check.js
…（29 项 PASS，含）…
[PASS] attempt 时间线：logs 取数 + 两腿字段逐字渲染 + payload 内嵌兼容 + 非 attempt 忽略 + 缺腿降级
[PASS] attempt 时间线降级：空态 + 503 错误横幅 + 恢复
全部自检通过
```

`node frontend/self-check.js` 全部通过。后端 R4-1 投影与前端 `extractHedgeAttempts` 兼容（前端扫描 `doc.attempts`，字段逐字对齐）。

---

## 5. 改动文件（R4 修复实际增量）

| 文件 | R4 改动 |
|---|---|
| `backend/hedge_open_tasks/store.py` | 新增 `list_attempts_page`（跨 task 分页 + 两 leg 投影）。 |
| `backend/hedge_open_tasks/service.py` | 新增 `_leg_to_doc`/`attempt_to_doc`；`get_logs` 增量加 `attempts`；`tick` 改并发 dispatch + 新增 `_dispatch_eligible_concurrently`/`_dispatch_one_for_task_contained` + docstring。 |
| `backend/tests/test_hedge_service.py` | 新增 `import threading/time` + `AttemptOutcome`；4 个 R4 用例（3×R4-1 投影、2×R4-2 并发）+ `_BlockingExecutor`。 |
| `backend/tests/test_hedge_api.py` | logs 响应键集断言加 `attempts`；新增 `test_logs_includes_additive_attempts_timeline`。 |

`git diff --stat`（**累计**，含 Task A 原实现未提交改动，非纯 R4 增量）：

```text
 backend/hedge_open_tasks/service.py | 464 ++++++++++++++++++---
 backend/hedge_open_tasks/store.py   | 793 ++++++++++++++++++++++++++++++++----
 backend/tests/test_hedge_api.py     |  69 +++-
 backend/tests/test_hedge_service.py | 284 ++++++++++++-
 4 files changed, 1444 insertions(+), 166 deletions(-)
```

> 注：`git status` 中其余 modified/untracked（`domain.py`/`config.py`/`server.py`/`services/*`/`test_hedge_domain|store|private_client|purity|live_*`、`frontend/**`、`20-implementation-frontend.md`）是 Task A 原实现与 Task B 的产物，**不是本次 R4 修复的改动**。

---

## 6. 遗留问题 / 有意选择

1. **attempts 与 logs 共用同一 cursor 参数但基于不同表**：`attempts` 用 `list_attempts_page`（基于 `attempt.created_at_us`），`logs` 用 `list_logs_page`（基于 `log.ts_us`）。resolved attempt 的 `created_at_us` 与对应 log 的 `ts_us` 在同一 resolve 事务里都是 `now_us`，故对齐；PREPARED/querying attempt 无 log 但仍出现在 `attempts`。响应只暴露一个 `next_cursor`（跟踪 logs，legacy 契约不变），`attempts` 无独立 cursor——前端 `limit=100` 一次性消费最新 attempts。这是 prompt "legacy logs/cursor 不退化" 的有意选择。
2. **`residual` 符号**：采用 `spot_base − perp_base`（原始差，Decimal 字符串）。breakdown §3.3 的 "sign per direction" 作为说明性注解（forward 正残差 = 净多 spot 暴露），未引入方向取反，避免在 prompt 未明确符号约定时过度设计；如 review 要求按方向统一符号再调整。
3. **`tick()` join 慢卡会延迟本 tick 返回**：并发 dispatch 后 tick 仍 `join` 所有 worker（保证一 task 每秒一对、无重入），所以一个 live POST 超时（client timeout 10s）会让本 tick 最迟在超时后返回；下一 tick 因 `_last_tick_mono` cursor 仍按 1s due 检查，不会 burst。慢卡**不阻塞他卡本 tick 的提交**（他卡已在各自 worker 提交），仅影响本 tick 的返回时点——这是 R4-2 的要求与 join 语义的权衡。
4. **`backend/services/**` 未改**：R4-1（store+service 投影）与 R4-2（service 调度）均在 `backend/hedge_open_tasks/**` 内完成，无需动 services 层。

---

## 7. 完成声明

完成 bookkeeper R4 范围两项 P1 修复：

- **R4-1**：`/api/hedge-open-logs` 增量加 first-class `attempts` 时间线数组（投影 durable attempt + 两 leg，覆盖 PREPARED/QUERYING/resolved），冻结 §3.4 字段 + Decimal 字符串 + residual，legacy logs/cursor 不退化。
- **R4-2**：`tick()` 每个 eligible running task 在独立 worker 上并发 dispatch，慢卡不阻塞他卡本 tick 提交，保持 Start/rate-limit gate、durable-before-send、no-resend、pair 内双腿并发，不引入全局锁或 auto-remediation。

全量 `backend/tests` 862 passed；`node frontend/self-check.js` 全部通过（含 attempt 时间线用例）。从未真实 POST、从未读真实凭据、从未启用 live/Start。

完成后停止，等待 bookkeeper；未 commit、未改 status.json / 70-handoff.md、未派发或评审其他模型。

---

*本地北京时间：2026-07-23 23:05:02 CST（`date` 取得）*
