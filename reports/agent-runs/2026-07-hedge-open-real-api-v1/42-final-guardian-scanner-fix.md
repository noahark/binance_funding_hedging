# 42-final-guardian-scanner-fix（packet 63 · 守护扫描器移除）

执行调度：`63-final-guardian-removal.dispatch.md`（stage `2026-07-hedge-open-real-api-v1` 用户 2026-07-25 批准的一次、且仅一次极小第 4 次修复；只处理 H-1）。
实现者：GLM `glm-5.2[1m]`（唯一后端修复实现者，HARNESS-EXECUTOR-CONTRACT v1）。
业务权威：`21-task-local-runtime-and-manual-pause-amendment.md`（运行时最高合同）+ `24-user-authorized-final-guardian-fix.md`（本次唯一额外授权与最终业务边界）。
H-1 证据：`23-packet-62-reconciliation-hold.md`（packet 62 reconciliation hold，明确 H-1 的精确代码证据）。
packet 62 基线：`40-fix-review-1-backend-r2.md` + `62-review-1-backend-r2-task-local.dispatch.md`（任务本地有界 worker 返工，已完成且必须保留）。

按合同：**只改 dispatch 允许的 `backend/hedge_open_tasks/service.py` 与 `backend/tests/test_hedge_task_local.py`；未读凭据、未连 Binance、未发真实 POST、未启 live/Start、未 commit、未改 status.json/70-handoff/契约文件/23/24/62/63。**

---

## 1. 改动边界：继承自 packet 62 vs 本包直接改动

工作区当前 diff 含两类改动，必须区分清楚（packet 62 的任务本地 worker 返工从未提交，其全部改动仍在工作区；本包在其上做增量修复）。

### 1.1 继承自 packet 62（**未触碰、保留**）

这些是 packet 62 已完成且 dispatch 明令「不要破坏」的语义，本包一行未改：

- 全局守护/全局对账扫描/全局 429 冷却的移除（`RATE_LIMIT_COOLDOWN_US` 等）。
- 每任务一个有界 worker：`ensure_worker` / `_run_task_worker` / `_worker_round` / `_reconcile_own_legs` / `_pump_worker` 测试 seam / `_dispatch_live` 信号路由。
- 任务本地暂停：`_pause_task_local`、`pause_task`、`settle_attempt_no_counters`、`pause_reason_zh`、SIGNAL_* / PAUSE_REASON_INSUFFICIENT_* 常量。
- 双向 `est_price` fail-closed（domain.py）、Q6 命门（store 不持有 executor）、429 先 drain 后退、未确认 `-2010` → fatal stop、重启恢复仅查 clientOrderId 不重发。
- review2 17 用例迁移到 `_step`/`_pump_worker` 同步 seam。

### 1.2 本包直接改动（**H-1 唯一修复**，仅 4 处定点编辑）

| 文件 | 改动 | 性质 |
| --- | --- | --- |
| `backend/hedge_open_tasks/service.py` `start()` | live-capable 时一次性 `_recover_workers()` + `return`（不启动 scheduler）；dry-run 仍 `_scheduler.start()` | 核心修复 |
| `backend/hedge_open_tasks/service.py` `tick()` | live 分支由 `self._recover_workers(); return False` 改为纯 `return False`；docstring 同步 | 核心修复 |
| `backend/hedge_open_tasks/service.py` `_recover_workers()` docstring | 注明由 `start()` 一次性调用、不再由周期 tick 驱动 | 文档订正 |
| `backend/tests/test_hedge_task_local.py` | `test_5` 的 `svc2.tick()` → `svc2.start()`；新增 `test_6a/6b/6c` | 回归更新+新增 |

**未改 `scheduler.py`、`server.py`、`store.py`、`domain.py`、`executor.py`、`live_hedge_executor.py` 或任何 frontend/契约文件。** `server.py:773 hedge_open_service.start()` 的生产调用点与 `stop()` 的 finally 清理均与本改动兼容（见 §3、§7），无需也不允许改动。

---

## 2. H-1 的准确复现

packet 62 正确移除了旧的「同步全局对账阻塞派发」缺陷，但**真实模式仍保留常驻 `HedgeOpenScheduler` daemon 线程**：

```text
service.start()                         # service.py:386 self._scheduler.start()
  -> HedgeOpenScheduler.start()         # scheduler.py:25-32 daemon 线程
  -> daemon loop                        # scheduler.py:41-57 周期 self._tick()
  -> service.tick() 每个 cadence
  -> [live 分支] self._recover_workers()# service.py:1072-1074
  -> 扫描全部 RUNNING，再扫 PAUSED/STOPPED 的非终态腿任务，按需 ensure_worker
```

该 daemon 本身不直接同步下单（故不重建 packet 62 已修的「A 查询阻塞 B 派发」），但它是**一个持续发现全部任务、间接拉起会下单/查询子线程的长期守护**，违反 amendment 21 / 用户授权：真实开单只允许「一次启动恢复」或「人工恢复指定任务」，不能有长期扫描全部任务的守护进程。

---

## 3. 启动恢复的精确路径（修复后）

`start()` 现按 executor 能力分流（`_live_dispatch_capable() == mode=="live" 且 executor 有 dispatch`）：

```text
service.start()
  if _live_dispatch_capable():          # 真实模式
      self._recover_workers()           # 一次性恢复发现，见下
      return                            # 不启动 HedgeOpenScheduler
  self._scheduler.start()               # dry-run(record/disabled)：保留周期 record tick
```

`_recover_workers()`（实现未改，仅改调用点）做**一次性** handoff：

1. 遍历 `list_tasks(RUNNING)`：对缺 worker 的任务 `ensure_worker(tid)`（单临界区 + store 原子 in-flight 守卫，复用既有 worker）。
2. 遍历 `list_tasks(PAUSED)` / `list_tasks(STOPPED)`：对仍有非终态腿的任务启动 drain-only worker（Q2 drain-before-exit）。
3. 返回。**不启动任何 timer/daemon/poller/全局队列消费者。**

**保留 packet 62 安全性质**：pending pair 只按保存的 clientOrderId 查询、绝不重发 POST（`_reconcile_own_legs` 只调 `query_leg`）；paused/stopped mid-pair 的任务得到 drain-only worker。`test_5`（现经 `svc2.start()`）仍断言零第二次 write、`query_calls>=2`、对账到终态。

`stop()` 不变且兼容：`self._scheduler.stop()` 对未启动的 scheduler 安全（仅 set stop event + join None）；随后唤醒所有 task-local worker 退出。

---

## 4. live tick 为何不会扫描（修复后）

`tick()` live 分支现为**安全空操作**：

```python
def tick(self):
    if self._live_dispatch_capable():
        return False          # 不调 _recover_workers、不枚举任务、不拉起 worker
    ...                       # dry-run 同步 record tick 路径不变
```

- **结构性保证**：live tick 早返回，绝不触达 `_recover_workers()`、`list_tasks()`、`ensure_worker()`。即便未来有人意外调用 `tick()`，也不会变成守护扫描。
- **无替代守护**：本包**未新增**任何 timer/daemon/poller/全局队列消费者/长期 coordinator。live 模式下 `HedgeOpenScheduler` 根本不被启动（`_scheduler._thread is None`），因此连「周期调用 tick」的载体都不存在。
- **dry-run 不受影响**：record/disabled executor 的同步 record tick（pacing on 1s cadence、无全局冷却、无全局对账）路径完全保留，相关 `test_hedge_service.py` 用例（dry-run）全绿。

`test_6b` 用 spy 同时覆盖三条防线（`_recover_workers` / `store.list_tasks` / `ensure_worker`）：连续 5 次直接 `svc.tick()` 后三者计数均为 0，两张 RUNNING 任务卡始终无 worker。

---

## 5. 人工 Start 仍只启动指定任务（修复后，未改）

`post_start(task_id)` / `post_fill_once` / `post_fill_all` 的 live 路径**一行未改**，仍只 `ensure_worker(task_id)`：

```python
def post_start(self, task_id):
    ...
    updated = self._store.set_task_status(task_id, STATUS_RUNNING, ...)
    if self._live_dispatch_capable():
        self.ensure_worker(task_id)     # 仅本任务，绝不全局 dispatch
    return 200, task_to_doc(updated)
```

`test_6c` 证明：`post_start(A)` 后 A 有 live worker（被 hold 在 dispatch 可观测），B（同为 RUNNING）无 worker——Start(A) 不扫描、不拉起 B。跨任务联动未随本次修复回归。

429/余额暂停、失败阈值、target_n 上限、双腿并发、单任务 pair 串行、预检、签名、wire 参数、日志、API 字段、UI、dry-run 业务语义**均未改动**。

---

## 6. 每项新测试（确定性、离线、零网络/零 sleep race）

| 测试 | 验证项 | 模式 |
| --- | --- | --- |
| `test_5`（更新） | 启动恢复现由 `start()` 触发；新实例同 DB 仅查 clientOrderId、零第二次 write、对账到终态、任务 done | 新实例同 DB + holding/accepted fake executor |
| `test_6a_live_start_does_one_recovery_handoff_and_does_not_start_scheduler` | live `start()` 恰好一次 `_recover_workers`、scheduler 未启动（`_thread is None`）、durable RUNNING 任务被交给自己的有界 worker | spy（recover / scheduler.start）+ holding executor |
| `test_6b_live_tick_is_a_safe_noop_no_scan_no_worker` | 连续 5 次 live `tick()` 不调 `_recover_workers`、不枚举 `list_tasks`、不 `ensure_worker`；两张 RUNNING 卡始终无 worker | spy ×3 |
| `test_6c_manual_post_start_launches_only_the_named_task` | `post_start(A)` 只拉起 A、不拉起 B | holding executor + Event 屏障 |

复跑的 packet 62 关键任务本地测试（`test_1`–`test_5`、`test_4b`）与本包新增一并绿，证明本次改动**未恢复**全局查询/双 POST/跨任务联动。

---

## 7. 与生产接线（`server.py`，未改）的兼容性

`server.py:773 hedge_open_service.start()`（启动）+ `server.py:790 hedge_open_service.stop()`（finally 清理）：

- **dry-run**：`start()` 启动 scheduler → 周期 record tick → 卡片推进（行为不变）。
- **live**：`start()` 一次性恢复 handoff、不启 scheduler；worker 退出后仅由人工 Start/recover 重启。`stop()` 安全（scheduler 未启动亦无副作用，并唤醒 worker）。

无需改 `server.py`，且 dispatch 禁止改之。

---

## 8. 自测结果（原始输出已追加 `60-test-output.txt`）

| 命令 | 结果 |
| --- | --- |
| CMD#1 三聚焦文件（task_local + service + review2） | **48 passed** in 1.43s |
| CMD#2 `backend/tests -q`（全量，含新增 3 用例） | **897 passed** in 45.30s |
| CMD#3 `node frontend/self-check.js` | 全部自检通过，exit 0 |
| CMD#4 `scripts/tests/test_validate_stage_dispatch_protocol.py` | **55 passed** in 0.73s |
| CMD#5 `git diff --check` | exit 0（无空白错误） |

---

## 9. 剩余风险（如实记录）

1. **worker 退出后无自动重启**：live 模式下，恢复 worker 因 Start gate 关 / 预检不完整 / target 达成 / done/paused/stopped 退出后，**不再**由周期 tick 自动重启——这是 H-1 修复的预期语义（无守护扫描），需操作员人工 Start/recover 重启。dry-run 不受影响（仍由 scheduler record tick 推进）。
2. **启动恢复仅一次**：`start()` 每次调用做一次 handoff（`_recover_workers` 幂等：复用既有 live worker）；生产仅 boot 调用一次。多次调用安全但非「全局周期扫描」。
3. **跨进程恢复仍同进程模拟**：`test_5` 用同进程新实例 + 同 DB 模拟旧 worker 消失；真正的多进程并发仍靠 `prepare_attempt` 原子 in-flight 守卫 + clientOrderId 查询不重发保证，未做跨进程集成测试（与 packet 62 同）。
4. **手动 pause 的在飞腿**：`post_pause` set stop_event 使 worker 下一轮顶退出（非 drain 路径）；其在飞腿由**下一次人工 Start/recover**（不再由 tick）启动 drain-only worker 收尾——正确性保留，但退出当下不立即 drain（与 packet 62 同，因人工 pause 语义即「尽快停」）。
5. **交易所外部 IP/account 429**（packet 62 既述，未变）：本应用不因 A 的 429 主动联动 B/C；但 Binance 外部限频仍可能独立拒绝其它请求，应用层无法保证。

---

实现完成，全部自测通过。按合同**停止**——不 commit、不改 status.json / 70-handoff.md / 契约文件、不派发评审、不自行判定验收，等待 bookkeeper 重算指纹、做差异核对并安排重新的 Review-1。

---

当前 Session ID: unavailable (Claude Code / glm-5.2 harness 不暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md
本地北京时间: 2026-07-25 19:29:28 CST
下一步模型: bookkeeper
下一步任务: recompute the changed-file fingerprint, reconcile the packet-63 final guardian-scanner fix against packet 62, and schedule a renewed backend Review-1
