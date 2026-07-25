# 46-fix-review-1-backend-r4（packet 67 · Review-1 后端第 6 次有界返工）

执行调度：`67-fix-review-1-backend-r4.dispatch.md`（stage `2026-07-hedge-open-real-api-v1` 用户授权的第 6 次、严格有界的后端返工）。
实现者：GLM `glm-5.2[1m]`（唯一后端返工实现者，HARNESS-EXECUTOR-CONTRACT v1；禁止调用/启动/转派其它模型或 adapter）。
业务权威：`27-user-authorized-r4-repair.md`（用户 2026-07-25 第 6 次授权，§5 = P2-1 + P2-2 两项必做，§8 验收条件）+ `26-user-authorized-settlement-and-pause-fix.md`（§10.1 验收条件）+ `21-task-local-runtime-and-manual-pause-amendment.md` + `15-immediate-loop-and-open-log-amendment.md`。
P1 证据：`66-review-1-backend-r4.md`（Reviewer Opus 5 REWORK + 末尾 schema-valid JSON verdict + 完整 `fix_start_prompt`）。
前序实现：`44-fix-review-1-backend-r3.md`、`42-final-guardian-scanner-fix.md`、`40-fix-review-1-backend-r2.md`（packet 62/63/65 已实现且必须保留）。

重要前提（来自 dispatch 原文，逐字遵守）：**上一轮四项 P1/P2 的生产代码已被 Review-1 逐条重新验证为正确**（429 恢复清粘滞 + 逐次尝试 rate_limited；人工 pause/delete 由本卡 worker drain 后退出且不开新组；settle_attempt_no_counters 按两腿真实事实推导并落 leg_exposure；worker_active 三态 + last_worker_exit_reason）。**本次不重做、不重构、不改进这四项的生产语义，只做下面两项。**

按合同：**只改 dispatch 允许的 `service.py`（仅 `_pump_worker` 的 stop-event 初始化 + `_recover_workers` 的兜底状态元组）+ `test_hedge_task_local.py` + 本报告 + `60-test-output.txt`（仅追加）；未读凭据、未连 Binance、未发真实 POST、未启 live/Start、未 commit、未改 status.json / 70-handoff.md / 任何契约文档（15/16/17/19/21/23/24/25/26/27）与评审报告（30/42/50/58/64/66）、未改 store.py / domain.py / backend/services/** / scheduler.py / server.py / frontend/** / 环境配置；未新增全局守护、周期扫描器、timer、自动补单/撤单/平仓/借还/转账、WebSocket 或平滑开仓。**

---

## 1. 改动文件（git status / diff --stat 实测）

| 文件 | 性质 | 说明 |
| --- | --- | --- |
| `backend/hedge_open_tasks/service.py` | 改（仅两处） | (a) `_pump_worker`：去掉每次开头无条件 `ev.clear()`，只在**首次注册**时创建 `threading.Event()`（已存在则保持原状）—— 修复 P2-1 的空回归根因。(b) `_recover_workers`：只对账兜底元组从 `(PAUSED, STOPPED, DELETED)` 扩到 `(PAUSED, STOPPED, DELETED, DONE)` —— P2-2。`post_pause`/`post_delete`/`_worker_round`/`ensure_worker` 的**生产语义一行未动**（`ensure_worker` 的 `ev.clear()` 是生产路径，拉起新 worker 时清旧标志，保留）。 |
| `backend/tests/test_hedge_task_local.py` | 改 | R3 / R4 各加一条 `svc._stop_events[tid].is_set() is False` 断言（post_pause / post_delete 后）；新增 helper `_accepted_done_with_nonterminal_perp` 与回归 `test_r9_done_card_nonterminal_accepted_leg_recovered_on_restart`（与 R5 同构，done 卡带 accepted+NEW 腿）。 |
| `reports/.../60-test-output.txt` | 追加 | packet 67 五条自测命令真实原始输出 + P2-1 / P2-2 两组反向验证（猴补丁，零仓库文件）输出。 |
| `reports/.../46-fix-review-1-backend-r4.md` | 新建 | 本报告（未覆盖 40/41/42/44 号既有报告）。 |

未触动：`store.py` / `domain.py` / `live_hedge_executor.py` / `scheduler.py` / `server.py` / `frontend/**` / 任何契约文档与评审报告 / `status.json` / `70-handoff.md`。`diff --stat` 仅 `service.py +27/-10`（含注释）、`test_hedge_task_local.py +90`。

---

## 2. 修复项逐条（根因 → 修复 → 代码位置）

### P2-1　R3 / R4 是空回归：`_pump_worker` 每次开头吞掉 stop event

- **根因**（reviewer `66` §4 P2-1 / 授权书 `27` §5.1）：`_pump_worker`（service.py 的 test seam）在**每次调用开头无条件 `ev.clear()`**；而测试辅助 `_step()`（test_hedge_task_local.py:57-63）就是一次 `_pump_worker` 调用，R3/R4 的写法是 `_step(1) → post_pause()/post_delete() → _step(3)`，第二次 `_step` 把 pause 可能置位的 stop event **又清掉了**。于是无论 `post_pause` 是否中断 worker（即缺陷在不在），R3/R4 的 drain 断言都照样通过 —— 既没复现旧缺陷，也钉不住新修复，违反用户授权书 §10.1。
- **修复**（不动生产语义）：
  1. `_pump_worker` 不再吞 stop event —— 只在**首次注册**时创建 `threading.Event()`（新建即 cleared），已存在则**保持原状**（service.py `_pump_worker`）。这样若 `post_pause`/`post_delete` 真的置位了 stop event，下一轮 `_worker_round` 第一行 `stop_event.is_set()` 即短路退出、不 drain，drain 断言随之失败。
  2. R3 / R4 各加一条直接断言：`post_pause` / `post_delete` 之后该卡 stop event **未被置位**（`svc._stop_events[doc["id"]].is_set() is False`），与现有全部 drain 断言并存（test_hedge_task_local.py R3 / R4）。
  3. **未做** reviewer 的可选 (c)（R3 真实线程版）—— 真实线程路径 reviewer 已在 `66` §3.2 用真实 worker 独立复验为正确，且当前 seam 修复 + 新断言已让同步回归有效；真实线程版属增强、非必需，按"Surgical Changes / 最小修改"原则不加。
- **为什么 `ensure_worker` 的 `clear()` 不动**：`ensure_worker`（service.py）是**生产路径**，每次拉起一个**新** worker 线程时清掉可能残留的 stop 标志是其正确语义（reviewer `66` §3.4 已验证锁序与正确性）；只有 test seam `_pump_worker` 的 `clear()` 才是遮蔽缺陷的元凶。

### P2-2　`_recover_workers` 只对账兜底漏 `STATUS_DONE`：达标那一组的真实成交腿重启后永不对账

- **根因**（reviewer `66` §4 P2-2 / 授权书 `27` §5.2）：`_recover_workers` 的只对账兜底本轮从 `(PAUSED, STOPPED)` 扩到 `(PAUSED, STOPPED, DELETED)`，仍不含 `DONE`。而 `resolve_attempt(leg_terminal=...)`（store.py）在两腿都拿到 orderId、但其中一腿仍 `NEW`/`PARTIALLY_FILLED` 时，会**先把该组判 accepted 并把任务推到 done**，同时按设计把那条腿留在 `terminal=0`（service `_leg_terminal`：accepted 但未 FILLED 故意保持非终态待轮询）。在途中重启，该腿再无人查询；`aggregate_positions` 只累加 `exchange_status == FILLED` 的腿，于是这笔真实成交腿永久记 0，一组**已经对冲好的**仓位被永久显示成裸空头，不会自愈。
- **修复**：把 `D.STATUS_DONE` 加进 `_recover_workers` 的兜底元组（service.py `_recover_workers`）。该 worker drain 完即因 `_worker_round` 的 `status != RUNNING` 检查退出（service.py:1010-1011），**绝不开新组**，与上一轮新加的 `DELETED` 完全同构。
- **幂等性核验**：dispatch 达标的 done 卡，其 attempt 在派发时已由 `resolve_attempt` 落 `pair_outcome = accepted_pair`；重启 drain 把该腿查到终态后，`_reconcile_own_legs` 末尾对它再调 `finalize_attempt`，而 `finalize_attempt`（store.py:1000-1001）在 `pair_outcome is not None` 时直接 `return None` —— **不重复计数、不重复改状态**。R9 钉住这条（`accepted_pair_count == 1`）。

---

## 3. R3 / R4 加强 + R9 新增：「缺陷存在时会失败 → 修复后转绿」的**本机原始输出**

全部用一次性猴补丁脚本（`/tmp/r3r4_check.py`、`/tmp/r9_check.py`）在独立进程内 monkeypatch service 方法，**未改任何仓库文件**，原始输出已追加到 `60-test-output.txt`。

### 3.1 P2-1：R3 / R4（把删掉的 `_wake_worker` 中断语义放回 post_pause / post_delete）

| 断言 | [A] 修复后 seam + 缺陷（应 FAIL） | [B] 修复前 seam（每次 clear）+ 缺陷（drain 空回归，应 PASS） |
| --- | --- | --- |
| stop_event set right after post_pause/post_delete | True（缺陷确实置位） | True |
| `query_calls >= 2` | **False (0)** —— worker 被中断不 drain | True (2) —— clear 后 worker 照常 drain |
| both legs terminal | **False** | True |
| pair settled | **False** | True |
| no new pair (scheduled unchanged) | True | True |
| **stop_event NOT set（新 P2-1 断言）** | **False** | **False** —— 新断言即使在旧 seam 下也能抓住 |

读法：
- **[A]**（当前代码 + 缺陷）：四条断言同时 False —— **R3/R4 在 `_wake_worker` 中断被放回时会失败**（用户授权书 §10.1 / `27` §8.1 达成）。
- **[B]**（修复前 seam + 缺陷）：drain 三条断言 vacuously True（reviewer `66` §4 发现的空回归），**唯独新加的 stop_event 断言仍 False** —— 证明 (a) seam 修复与 (b) 新断言**两层防护缺一不可**：(a) 让 drain 断言也能抓，(b) 即使有人把 seam 退回旧状仍有一道直接观测。
- 修复后 + 正常（不置位）：由 pytest 钉住（R3/R4 全绿，见 §6）。

### 3.2 P2-2：R9（done 卡带 accepted+NEW 腿 → 重启一次 recovery）

| 观测 | [REGRESSED] 兜底 = (PAUSED, STOPPED, DELETED)（应 FAIL） | [FIXED] 兜底 = (PAUSED, STOPPED, DELETED, DONE)（应 GREEN） |
| --- | --- | --- |
| done 卡建成（status / perp terminal 重启前） | done / 0 | done / 0 |
| recovery 是否为该 done 卡调 ensure_worker | **False (`ensured=[]`)** | **True** |
| `query_calls` after start() | **0** | 1 |
| perp terminal / exchange_status after start() | **0 / NEW** | **1 / FILLED** |
| 重启后非终态腿 | **[perp]（仍在）** | [] |
| status after start() | done（无人动） | done（sticky） |

读法：[REGRESSED] 完整复现 reviewer `66` §4.2 的离线实测（recovery 不拉 worker、腿永久停在 NEW）—— **R9 在 `STATUS_DONE` 不在兜底时会失败**；[FIXED] 一次恢复交接把 accepted+NEW 腿查到 FILLED、零重发、status 仍 done —— R9 全绿（`27` §8.2 达成）。

---

## 4. H-1 / packet 62 / 63 / 65 既有性质不回归

- **P2-1 seam 改动的影响面已核**：`_stop_events` 的 `.set()` 全仓只在 `service.stop()`（进程关停，service.py:412-418）；`.clear()` 只剩 `ensure_worker`（生产，保留）与 `_pump_worker`（本次改为首次注册才建）。test_5 / R5 都在 `svc1.stop()` 后 `del svc1`、换**新实例**（新实例 `_stop_events` 为空），不受 seam 改动影响；其余 `_step` 用例同实例内从不 `stop()`。905 → 906 全量用例隐式覆盖。
- **P2-2 兜底改动的影响面已核**：`_recover_workers` 仍被 `start()` **一次**调用、`tick()` 在 live 仍是安全空操作（service.py）、`post_start` 仍只启动命名卡 —— H-1 三防线（`test_6a/6b/6c`）本轮全绿。新加的 `DONE` 分支与 `DELETED` 同构：worker drain 完即因 `status != RUNNING` 退出，不开新组、不重发（ADR-2）、store 锁内不调 executor（Q6）。
- **packet 62/63/65 行为保留**：`test_1`–`test_5`、`test_4b`、R1–R8 本轮全绿（task_local 19 passed）；429 恢复清粘滞 + 逐次尝试 `rate_limited`、`settle_attempt_no_counters` 推导 single_leg + leg_exposure、`worker_active` 三态 + `last_worker_exit_reason`、每任务单有界 worker、同卡 pair 串行 / 双腿并发 / 跨卡隔离、对账绝不放弃、先持久后发送、`target_n` 原子硬上限、无 orderId 只按 clientOrderId 查询且永不重发 —— 均未触动。
- **`-2010` 未确认仍 fatal stop**：`test_4b` 继续通过（fatal 路径未改）。
- **契约面**：`_ENTRY_EVENT_KINDS` 逐字未动；`frontend/**` / `scheduler.py` / `server.py` / `backend/services/**` / `store.py` / `domain.py` 本次**零改动**（`git diff --stat` 仅 service.py + test_hedge_task_local.py）。

---

## 5. 剩余风险

- **`_pump_worker` 去 clear 后，"同实例先 `service.stop()` 再 `_pump_worker`"会短路**：这是 seam 的预期新行为（让中断语义可被观测）；当前无测试采用此模式（test_5/R5 均换新实例），且生产路径 `ensure_worker` 仍 clear。若未来有测试需要在此模式下重置，可按授权书 §5.1 备选方案加 `reset_stop_event` 形参（本次未加，遵循最小修改）。
- **R9 的 done 卡恢复只覆盖 accepted+NEW 一腿**：`finalize_attempt` 对已 resolved attempt 的幂等性已用 R9 的 `accepted_pair_count == 1` 钉住；但若一张 done 卡在重启前**两腿都非终态**（更罕见），drain 后 `finalize_attempt` 仍走 `pair_outcome is not None → return None` 的幂等分支，不重复计数（同一机制，已核）。
- **P3-1 / P3-2 / P3-3 为 follow-up，不在本次范围**（授权书 `27` §5.3）：`settle_attempt_no_counters` 不落 attempt 级错误列（仅可观测性，`classify_query_response` 永不产 `fatal`，无安全后果）；人工 Start 撞 worker 退出窗口的极窄 race（已被 `worker_active` 可见化）；`post_start` 响应混用派发前后快照（纯展示层）。
- **未引入**任何全局守护 / 周期扫描器 / timer / 自动补单撤单平仓借还转账 / WebSocket / 平滑开仓（合同遵守，`grep Thread(|Timer(|while True` 在 hedge 路径命中数不变）。

---

## 6. 精确自测（原始输出已追加 `60-test-output.txt`）

| 命令 | 结果 | 基线 |
| --- | --- | --- |
| CMD #1 十组聚焦 | **230 passed** in 15.03s | 229（+1 R9） |
| CMD #2 `pytest backend/tests -q`（全量） | **906 passed** in 45.65s | 905（+1 R9） |
| CMD #3 `node frontend/self-check.js` | **全部自检通过**（13 项 PASS） | 通过 |
| CMD #4 `scripts/tests/test_validate_stage_dispatch_protocol.py` | **55 passed** | 55 |
| CMD #5 `git diff --check` | exit 0（无空白错误） | exit 0 |

新增回归后总数如预期上升（+1：R9）。R3/R4 加强断言在当前代码下全绿、在 `_wake_worker` 语义放回时失败（§3.1）。

---

实现完成，全部自测通过，反向验证闭环。按合同**停止**——不 commit、不改 status.json / 70-handoff.md / 契约文件、不派发评审、不自行判定验收，等待 bookkeeper 重算 changed-file 指纹、reconcile 本次 packet-67 返工、并调度更新后的 Review-1。

---

当前 Session ID: unavailable (Claude Code / glm-5.2 harness 不暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md
本地北京时间: 2026-07-26 CST
下一步模型: bookkeeper
下一步任务: recompute the changed-file fingerprint, reconcile the packet-67 Review-1 backend r4 rework, and dispatch the updated Review-1
