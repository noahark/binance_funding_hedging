# 40-fix-review-1-backend-r2（packet 62 · 任务本地有界 worker 返工）

执行调度：`62-review-1-backend-r2-task-local.dispatch.md`（stage `2026-07-hedge-open-real-api-v1` 第三次、也是最后一次有界后端返工）。
实现者：GLM `glm-5.2[1m]`（唯一后端返工实现者，HARNESS-EXECUTOR-CONTRACT v1）。
业务权威：`21-task-local-runtime-and-manual-pause-amendment.md`（用户 2026-07-24 批准）+ 用户 2026-07-25 三条编码约束。
P1 证据：`58-review-1-backend-r2.md`（Reviewer Claude Sonnet 5，REWORK）。

按合同：**只改 dispatch 允许的后端文件；未读凭据、未连 Binance、未发真实 POST、未启 live/Start、未 commit、未改 status.json/70-handoff/契约文件。**

---

## 1. 改动文件（git status / diff --stat 实测）

| 文件 | 性质 | 说明 |
| --- | --- | --- |
| `backend/hedge_open_tasks/domain.py` | 改 | P1#1 双向 est_price fail-closed；新增 SIGNAL_* / PAUSE_REASON_INSUFFICIENT_* 常量、`is_insufficient_funds_code`、`pause_reason_zh` |
| `backend/hedge_open_tasks/service.py` | 改（调度层核心） | 取消全局守护/全局对账扫描/全局 429 冷却；改为任务本地有界 worker（`ensure_worker`/`_run_task_worker`/`_worker_round`/`_reconcile_own_legs`）；新增 `_pump_worker` 测试 seam；429/余额类信号路由到本任务暂停 |
| `backend/hedge_open_tasks/store.py` | 改 | 新增 `pause_task`、`list_non_terminal_legs_for_task`、`settle_attempt_no_counters`；schema 加 `pause_reason_zh` 列 + 读取/迁移 |
| `backend/services/live_hedge_executor.py` | 改 | `classify_leg_response` 把确认的余额类（`-2019`/`-3041` 无歧义、`-2010` 仅当 msg 确认）标 `error_category="insufficient_funds"`；429 leg 分类不变 |
| `backend/tests/test_hedge_review2_regressions.py` | 改 | 17 用例触发方式 `svc.tick()` → 同步 `_step`（`_pump_worker` seam）；`test_7d` 改 429→paused+drain+计数不变 |
| `backend/tests/test_hedge_task_local.py` | **新增** | 5 个确定性行为回归（A 查询阻塞→B 派发；并发 Start→单 worker/单 reservation；A 429→暂停+计数不变+B 派发；A 余额/保证金不足→暂停+B 派发；重启恢复新实例同 DB 仅查 clientOrderId 不重发）+ `-2010` 未确认→fatal stop |
| `backend/tests/test_hedge_domain.py` | 改 | 反向/正向 `est_price=None`/零/负 → `REJECT_PREFLIGHT_INCOMPLETE` |
| `backend/tests/test_hedge_purity.py` | 改 | Q6 命门静态守卫：store 不调用/不持有 executor |
| `backend/tests/test_hedge_api.py` | 改 | 冻结字段集加 `pause_reason_zh` |
| `reports/.../60-test-output.txt` | 追加 | 5 条自测命令真实原始输出 |

**未改 `backend/app/server.py`**：Start/recover→worker 接线与启动恢复发现均已就绪（见 §7），强制改动会违反 dispatch「仅最小接线」限制与 surgical 原则。

---

## 2. 旧缺口如何确定性复现并修复

### 2.1 P1#1：反向 est_price 静默放行（58 号 P1）

**旧缺口**：`compute_preflight` 仅在 forward 分支隐式依赖 est_price；反向分支从不校验，forward 的 minNotional 路径在 `est_price=None` 时静默跳过 notional——一个缺失/零/负价格被静默放行，无法 size notional/USDT 需求。

**复现（domain 单测，零 attempt/POST/计数）**：
```
test_preflight_missing_est_price_fails_closed_both_directions[forward|reverse]
test_preflight_non_positive_est_price_fails_closed[0|-1]
```
**修复**：在 `compute_preflight` 方向分支**之前**统一加 `if snapshot.est_price is None or <= 0: REJECT_PREFLIGHT_INCOMPLETE`（domain.py:744）。两方向一视同仁，balance 闸门永不触及（`balance_ok` 留 `None`）。

### 2.2 全局守护/全局对账阻塞（58 号 P1 reconcile 阻塞派发）

**旧缺口**：`tick()` 作为常驻扫描器，先逐腿查询所有任务 pending legs，再派发新单——一个任务的慢/卡 `query_leg` 阻塞另一个任务的 reserve/submit。

**复现（行为回归，Event 屏障，非 sleep race）**：`test_1_task_a_query_blocked_does_not_block_task_b`——A 的 `query_leg` 被 gate 阻塞（`a_querying` Event 确认 A 已进入对账查询），B 在主线程经 `_pump_worker` seam 同步派发自己的一组并成功受理。

**修复**：删除全局 `_reconcile_pending` 扫描、`_dispatch_eligible_concurrently`（live）、全局 429 冷却 `_in_rate_limit_cooldown`/`_enter_rate_limit_cooldown`/`RATE_LIMIT_COOLDOWN_US`、`service._lock` 死重量。改为**每任务一个有界 worker**，只查本任务两腿（`list_non_terminal_legs_for_task(task_id)`），executor 调用绝不持 store 锁/事务。

### 2.3 余额类 stopped 过严 + 429 联动（21 号）

**旧缺口**：余额不足归 fatal stopped；429 设进程级冷却，可能联动其他任务。

**复现**：`test_3`（429）/`test_4`（余额·保证金不足）/`test_4b`（未确认 -2010）。
**修复**：见 §3 错误矩阵。

---

## 3. 每个任务本地暂停原因（21 号错误矩阵，worker 内路由）

worker 在派发（`_dispatch_live`）与对账（`_reconcile_own_legs`）两路径检测信号，信号经 `_worker_round` 路由到 `_pause_task_local`（`pause_task` + `record_task_event`，**仅本任务**）：

| 信号来源 | pause_reason | pause_reason_zh | 计数 | worker 行为 |
| --- | --- | --- | --- | --- |
| 确认 429/Retry-After（leg `rate_limited`） | `rate_limited` | 触发交易所限频（429），任务已暂停，请等待限频解除后手动恢复 | **不消耗**（`settle_attempt_no_counters`） | **先 drain 后退**：pause 后 `return False` 继续循环，把在飞腿查到终态、`settle_attempt_no_counters` 清 in-flight 守卫，own 空后因 status≠RUNNING 退出 |
| `-2019` 保证金不足（无歧义） | `insufficient_margin` | 保证金不足，任务已暂停，请补充后手动恢复 | resolve 一次（两腿终态后单次结算） | 本任务暂停，退出 |
| `-3041` PM 档位 / msg 确认的 `-2010` | `insufficient_balance` | 账户可用余额不足，任务已暂停，请补充后手动恢复 | 同上 | 本任务暂停，退出 |
| 可用数量不足 | `insufficient_available_qty` | 可用数量不足，任务已暂停，请补充后手动恢复 | 同上 | 本任务暂停，退出 |
| **未确认 `-2010`**（msg 不含余额关键词）/ symbol/mode/filter/min-notional | —（`stopped`） | stop_reason_zh | fatal stop | `stop_task_fatal`，本任务停止 |
| 已知非致命 pair 终态失败 | —（计数） | — | 两腿均终态后结算一次，连续失败计数；达阈值仅本任务 paused | 继续下一组或阈值暂停 |

**关键约束落实**：
- **用户约束 1（429 先 drain 后退）**：429 信号走 `pause_task + return False`（不 exit），由 Q2 循环结构保证 drain 完才退。`test_3` 提供 absent 查询 verdict，断言 429 对在飞腿 drain 到终态、`fail_count==0`、worker 退出。
- **用户约束 2（-2010 看具体原因）**：`is_insufficient_funds_code` 仅在 `-2019`/`-3041` 或 `-2010`+msg 正则命中 `insufficient (available )?balance` 时确认；否则落 fatal。`test_4b` 断言未确认 `-2010` → `STATUS_STOPPED`+`EXCHANGE_FATAL`，**宁可硬停，绝不误判为可恢复的余额暂停**。

---

## 4. worker 退出/恢复行为（有界生命周期，无死循环）

`_worker_round` 返回 True=退出、False=继续，顺序（**Q2：先 drain 后判退**）：
1. stop_event 已 set → 退出（`post_pause`/`post_delete`/`stop` 唤醒）。
2. `_reconcile_own_legs`：查本任务非终态腿到终态；429/余额信号 → 本任务 pause + `return False`（drain）。
3. own 非空 → `return False`（继续 drain，循环层 pacing）。
4. own 空：status≠RUNNING → 退出；Start gate 关 → 退出；`scheduled>=target_n` → 退出；否则派发下一组。

**退出条件覆盖**：done/paused/stopped/deleted、gate 关、预检不完整（fail-closed）/预检致命、target 达成。**无全局常驻扫描器**。

**恢复发现（一次性）**：
- **手动 Start/recover**：`server.py` Start action → `service.post_start` → `set RUNNING` + `ensure_worker`（live）→ 立即返回。
- **启动/重启**：`server.py:773 hedge_open_service.start()` → `HedgeOpenScheduler.start()`（daemon 线程）→ 周期 `tick()` → live 模式 `_recover_workers()`：为缺 worker 的 RUNNING 任务、以及任意 status 但仍有非终态腿的 paused/stopped 任务启动 drain worker（Q2 drain-before-exit）。

**重启恢复不重发（用户约束 3）**：`test_5` 用**新建 service/store 实例 + 同一临时 SQLite 文件 + 共享同一 fake executor 计数器**，模拟旧 worker 进程消失后新服务接管：svc1 经 `_pump_worker` 持久化 UNKNOWN 对（含 clientOrderId）后销毁；svc2 `tick()` 触发恢复发现启动 drain worker，仅按保存的 clientOrderId 查询（`query_calls>=2`）将对账到 FILLED 终态，**`dispatch_calls` 不增（零第二次 write）**，任务 done。

---

## 5. 跨任务隔离证据

- **结构性**：每 worker 经 `list_non_terminal_legs_for_task(task_id)` 只查本任务腿；executor 调用不持任何 store 锁/事务（Q6）。无全局扫描、无全局冷却、无跨任务状态写入。
- **行为证据**：
  - `test_1`：A 的 `query_leg` 被 gate 阻塞期间，B 仍及时 reserve+submit（A 不阻塞 B）。
  - `test_2`：6 并发 Start 经 Barrier 同时释放，`ensure_worker` 单临界区 + store 原子 in-flight 守卫 → 峰值并发派发==1、reservation 唯一、`attempts==target_n`（非 N×）。
  - `test_3`/`test_4`：A 因 429/余额不足 paused 后，B 仍完整派发至 done。
  - `test_hedge_review2_regressions.test_9`：A 在飞对不前进时，B 不被阻塞地前进；每任务串行（pair N 终态前不开 N+1）。

---

## 6. Q2 孤儿化对账不变式（最高风险，已钉死）

worker 循环**先 drain 后判退**：429/人工暂停 mid-pair 时，在飞腿始终被查到终态才退；恢复发现覆盖「任意 status 但有非终态腿」的任务。`test_7d`/`test_3` 提供查询 verdict 使 429 对 drain 到 absent 终态、`settle_attempt_no_counters` 清守卫且不计数。

## 7. Q6 命门（executor 绝不在持 store 锁时调用）

- 结构：store 无 executor 参数/引用；executor 调用全在 service worker 的短事务**之间**。
- 静态守卫（`test_store_never_invokes_or_holds_an_executor`）：store.py 无 `.dispatch(`/`.query_leg(`/`.query(` 调用、无 `self._executor`。（`.execute` 被排除——与 SQLite cursor `.execute()` 同名。）
- 既有守卫仍生效：`test_hedge_domain_package_*` 断言包不 import live 适配器/网络/签名原语。

---

## 8. 确定性回归覆盖（dispatch item 4，全部新增并通过，零 sleep race/零网络）

| dispatch item | 测试 | 模式 |
| --- | --- | --- |
| A query_leg gate 阻塞 → B reserve/submit | `test_1` | 真实 daemon 线程 + Event 屏障 + 同步 seam |
| 并发 Start → 单 worker/单 reservation | `test_2` | Barrier + 计数 executor + gate |
| A 429 → paused + 计数不变 + B 派发 | `test_3` | 同步 `_pump_worker` |
| A 余额/保证金不足 → paused + B 派发 | `test_4`（param -2019/-3041） | 同步 seam |
| pending pair 恢复 → 仅查 clientOrderId、无第二次 write | `test_5` | **新实例同 DB** + 恢复发现 |
| 反向缺失价格预检拒绝 | `test_preflight_missing_est_price_fails_closed_*` | domain 单测 |
| （约束 2）未确认 -2010 → fatal stop | `test_4b` | 同步 seam |

review2 17 用例（`test_1`–`test_9`）全部迁移到 `_step`/`_pump_worker` 同步 seam；`test_7d` 由「RUNNING+全局冷却」改为「PAUSED+rate_limited+fail_count==0+drain」。

---

## 9. 剩余风险（如实记录）

1. **交易所外部 IP/account 429**：本应用不因 A 的 429 主动暂停/停止/计数/延迟 B/C；但 Binance 外部账户/IP 限频仍可能独立拒绝其它请求（应用外事实），无法在应用层保证。
2. **P2 实时订单计数/权重响应头**：本轮**未实现**（dispatch 40 行、61 号明确）。当前 429 仅由 leg 层 `rate_limited` 信号驱动本任务暂停，未消费 `X-MBX-USED-WEIGHT` 等响应头做主动节流。
3. **跨进程恢复仅同进程模拟**：`test_5` 用同进程新实例 + 同 DB 模拟旧 worker 消失；真正的多进程并发仍靠 `prepare_attempt` 原子 in-flight 守卫 + clientOrderId 查询不重发保证，但未做跨进程集成测试。
4. **resume 活性延迟**：worker 退出后由下一次 `tick()` 恢复发现或手动 Start 重启；`post_start` 已清理/覆盖过期 worker 条目，tick 兜底。
5. **手动 pause 的在飞腿**：`post_pause` set stop_event 使 worker 在下一轮顶退出（非 drain 路径）；其在飞腿由后续 `tick()` 的 `_recover_workers`（任意 status+非终态腿）启动 drain-only worker 收尾——正确性保留，但退出当下不立即 drain（与 429 的「先 drain 后退」不同，因人工 pause 语义即「尽快停」）。

---

## 10. 自测结果（原始输出已追加 `60-test-output.txt`）

| 命令 | 结果 |
| --- | --- |
| CMD #1 显式测试列表（9 文件） | **211 passed** |
| CMD #2 `backend/tests -q`（全量，含新增 `test_hedge_task_local.py`） | **894 passed** |
| CMD #3 `node frontend/self-check.js` | 全部 PASS，exit 0 |
| CMD #4 `scripts/tests/test_validate_stage_dispatch_protocol.py` | **55 passed** |
| CMD #5 `git diff --check` | exit 0（无空白错误） |

---

实现完成，全部自测通过。按合同**停止**——不 commit、不改 status.json / 70-handoff.md / 契约文件、不派发评审、不自行判定验收，等待 bookkeeper 重算指纹并 reconcile。

---

当前 Session ID: unavailable (Claude Code / glm-5.2 harness 不暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md
本地北京时间: 2026-07-25 00:30:00 CST
下一步模型: bookkeeper
下一步任务: recompute the changed-file fingerprint, reconcile the packet-62 task-local worker rework, and run integration tests
