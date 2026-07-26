# 71-fix-review-2-backend-r7 — 第七次有界后端修复实现报告

- **实现模型**: claude_glm（zhipu_glm）
- **执行者**: human_operator
- **日期**: 2026-07-26
- **授权**: 28-user-authorized-r7-repair.md §2（user-authorized SEVENTH bounded backend change）
- **范围（仅四项）**: Review-2 F1 + F2 + F4 + finding-6 validator coverage。**F3（人工 delete/pause 状态守卫）、F5（账户健康 / MIN_NOTIONAL）按用户裁定不做。**
- **起点**: packet 69 的固定指纹 `b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd`（packet 28 §4 记录）。bookkeeper 会在本修复后落新的 committed 指纹。

## 安全边界（全程成立，未违反任何一项）

零真实 POST、零凭据读取、零 Binance 连接、零 live 启用、零 Start 触发、零 commit、零评审派发、零自行验收判定。
未新增：全局守护 / 周期扫描器 / timer / 自动补腿 / 撤单 / 平仓 / 借还 / 转账 / WebSocket / 平滑开仓。
`frontend/**`、`docs/**`、PRD、`10-design`/`11-adr`、用户授权/修正案、`reports/api-samples/**`、`status.json`、`70-handoff.md`、契约文档、评审报告、`hedge_open_live_client.py`（七端点 allowlist 冻结）、`hedge_preflight_provider.py`、`scheduler.py`、`server.py`、环境/凭据/网络配置 —— **零改动**。

## 改动清单（13 文件；12 文件在 28 §4 允许清单内，`test_hedge_api.py` 为 R2-F1 必然连带 — 详见下节授权边界说明）

| 文件 | 增/删 | 修复项 |
| --- | --- | --- |
| `backend/hedge_open_tasks/domain.py` | +15 | F1（single_leg 参与暂停阈值） |
| `backend/hedge_open_tasks/store.py` | +52 | F1（single_leg 计数 + 计划组耗尽转 done）+ F4（`list_unsettled_terminal_attempts_for_task`） |
| `backend/hedge_open_tasks/service.py` | +61 | F1（done 后处理）/ F2（查询阶段限频暂停零重发）/ F4（`_recover_crash_gaps` + `_recover_workers` 扩展） |
| `backend/services/live_hedge_executor.py` | +38 | F2（查询分类 + typed rate-limit signal + 合并） |
| `backend/tests/test_hedge_domain.py` | +29 | F1 |
| `backend/tests/test_hedge_store.py` | +70 | F1 |
| `backend/tests/test_hedge_service.py` | +6 | F1 |
| `backend/tests/test_hedge_api.py` | +4 | F1 必然连带（超 §4 字面清单 — 见下节）† |
| `backend/tests/test_live_hedge_executor.py` | +36 | F2 |
| `backend/tests/test_hedge_review2_regressions.py` | +150 | F2（`test_7e`）+ F4（`test_10a/b/c/d`） |
| `scripts/validate-stage.py` | +114 | finding-6 validator |
| `scripts/tests/test_validate_stage_dispatch_protocol.py` | +123 | finding-6 回归（12 例） |
| `reports/.../60-test-output.txt` | +38（追加） | R7 原始自测输出 |

## ⚠️ 授权边界说明（`test_hedge_api.py` — 需 bookkeeper 裁定）

`backend/tests/test_hedge_api.py` 的改动（4 行：`test_injected_single_leg_exposure_is_advisory` 的 `consecutive_submission_failures` 断言 `0 → 1` + 一行注释）是 R2-F1 的**必然连带**，但**不在 28 §4「允许修改」清单（行 74-87）字面内**：

- F1（28 §2.1 授权）让非限频 single_leg 计入连续失败刹车 → 该 HTTP 层断言必须从旧行为的 `0` 更新为新行为的 `1`，否则 §5 自测命令（28 行 110 / dispatch 72 行 87 明确包含 `test_hedge_api.py`）会因这一处断言失败。
- 28 §4 允许清单列入 6 个 backend 测试文件（task_local / review2_regressions / service / store / domain / live_hedge_executor），**唯独未列 `test_hedge_api.py`**，而 §5 却要求跑它并全绿 —— 这是 packet 的内在疏忽（F1 必然影响该断言）。
- 改动仅断言值 `0 → 1` + 一行注释，无其他改动（`git diff backend/tests/test_hedge_api.py` 可核）。

本实现选择**保留该最小断言更新**，以同时达成「F1 修复目标」与「§5 自测全绿」两项硬要求。该改动是否被接受、或是否应同步扩展 §4 允许清单，**留待 bookkeeper 裁定**。若 bookkeeper 认定必须字面回退，则 F1 在 HTTP 层将留下 1 例预期连带失败（断言 `consecutive==0` vs 新行为 `1`），需 bookkeeper 同步更新该断言或扩展 §4 清单。

---

## 1. R2-F1 — single_leg 计入连续失败刹车，计划组耗尽转 done

### 缺陷（修复前）
- `domain.resolve_status_after_attempt` 的暂停阈值条件只认 `ATTEMPT_FAILED`，不含 `ATTEMPT_SINGLE_LEG_EXPOSURE` —— 单腿敞口无论多少次都不触发暂停刹车。
- `store._apply_task_counters` 的 single_leg 分支不增 `fail_count` / `consecutive_submission_failures`（固定保持原值）。
- 计划数耗尽（`scheduled_attempt_count >= target_n`）后，若最后一笔是 single_leg，task 不转 `done`，与 `entries.next_action=completed` 契约不一致。

### 反向回归（先证明缺陷会失败）
- `test_apply_single_leg_records_exposure_advisory`：断言 `fail_count==1`、`consecutive_submission_failures==1`。旧实现两值均为 0 → 断言失败。
- `test_apply_single_leg_at_threshold_pauses`：连续 3 次 single_leg 后断言 `status==PAUSED`。旧实现 consecutive 不增 → 始终 RUNNING → 失败。
- `test_apply_single_leg_drains_planned_to_done`（target_n=1）：唯一计划组以 single_leg 结算后断言 `status==DONE`。旧实现不转 done → 失败。

### 修复
- `domain.resolve_status_after_attempt`：阈值条件改为 `category in (ATTEMPT_FAILED, ATTEMPT_SINGLE_LEG_EXPOSURE)`。
- `store._apply_task_counters` single_leg 分支：`fail_count += 1`、`consecutive_submission_failures += 1`，与 confirmed failure 完全一致；429 仍走免计数路径不变。
- `store._apply_task_counters`：在 UPDATE 之前加 done 后处理 —— `not skip_counters and pair_outcome is not None and new_status == STATUS_RUNNING and scheduled_attempt_count >= target_n` 时置 `STATUS_DONE`。`pair_outcome is not None` 守卫保证**只有真实成交/失败的结算**（非 disabled、非未结算的 attempt）才可能完成任务（修复 `test_disabled_executor` 回归）。

### 修复后证据
上述三组反向回归转绿；`test_disabled_executor_*` 仍绿（done 后处理不被 disabled 注入触发）。

---

## 2. R2-F2 — 查询分类只认显式 404/-2013，查询阶段限频转暂停零重发

**本轮风险最高项**（packet 69 标注）：实盘限频必然触发，误判会把可能已成交的单当成未成交并继续开下一组。

### 缺陷（修复前）
- `classify_query_response` 对 2xx 缺少有效 orderId 返回 `LEG_REJECTED` —— 把"可能已接受但响应畸形"误判为"确认 absent"，会打开下一组、对可能已成交的腿再开单。
- `classify_query_response` 对查询 429 / Binance `-1003` / `418` 返回 `None` —— 吞掉限频事实，worker 会继续按 client-ID 轮询，直撞 IP ban。
- `_send_one_leg` 合并不保留查询阶段 surfacing 的 rate-limit signal。
- service 查询阶段遇到 429 不暂停、不退出。

### 反向回归（先证明缺陷会失败）
- `test_query_2xx_without_order_id_stays_unknown`：旧实现返回 `LEG_REJECTED` → 断言 `UNKNOWN_QUERYING` 失败。
- `test_query_rate_limited_keeps_unknown_with_rate_limited_signal`：旧实现返回 `None` → 断言"非 None + rate_limited=True"失败。
- `test_dispatch_post_unknown_query_throttled_preserves_rate_limited`：旧合并不带查询阶段 rate_limited → 断言 `dispatch.rate_limited is True` 失败。
- `test_7e_query_phase_rate_limit_pauses_keeps_pending_no_resend`（service 层）：查询阶段 429，断言本卡 `PAUSED` + `rate_limited`、未决腿保留、零重发、`query_calls` 不无限增长。旧实现不暂停/继续轮询 → 失败。

### 修复
- `live_hedge_executor.classify_query_response`：
  - 2xx 缺少有效 orderId → `_empty_dispatch(leg, LEG_UNKNOWN_QUERYING)`（保持未知，worker 继续 client-ID 查询，绝不重发、绝不判 absent）。
  - 仅 HTTP 404 / Binance `-2013` 视为确认 absent。
  - `_is_rate_limited` → 返回 typed signal `_empty_dispatch(leg, LEG_UNKNOWN_QUERYING, rate_limited=True, retry_after_seconds=...)`（不再返回 None）。
- `_send_one_leg` 合并：`rate_limited = verdict.rate_limited or resolved.rate_limited`，`retry_after_seconds` 同理 —— POST 歧义但 best-effort 查询 surfacing 的 429 端到端保留。
- `service._reconcile_own_legs`：查询 verdict 命中 rate_limited 时 `continue`（腿原样保留非 terminal，不 resolve、不 resend、不进 finalized），并置 `drain_signal = SIGNAL_RATE_LIMITED`。
- `service._worker_round`：`drain_signal == SIGNAL_RATE_LIMITED` → `_pause_task_local(PAUSE_REASON_RATE_LIMITED, kind="rate_limited")` 后 `return True`（退出；保留 pending 腿、零重发；交人工恢复）。

### 修复后证据
上述四组反向回归转绿；`test_7d`（调度阶段 429）等既有性质不变。

---

## 3. R2-F4 — 消除"两腿 terminal、pair_outcome 仍 NULL"的崩溃缝隙

### 缺陷（修复前）
崩溃发生在"两腿已 terminal、但 pair 结算（finalize/settle）未执行"的窗口：该 attempt **没有非 terminal 腿**（`list_non_terminal_legs_for_task` 返回空），所以 worker 的 drain 不作用于它；而 `prepare_attempt` 的在途守卫（`pair_outcome IS NULL`）阻止开下一组；真实成交也永远不上计数器。task 卡死、记账缺失。

### 反向回归（先证明缺陷会失败）
`_seed_crash_gap` helper 直接构造该缝隙（prepare 后把两腿 resolve 到 terminal、不调 finalize），共 6 例：
- `test_10a_crash_gap_terminal_legs_null_outcome_recovered`：断言缝隙被恢复成 `PAIR_ACCEPTED` + `accepted_pair_count==1` + 末组完成转 `DONE`。旧实现缝隙不 finalize → `pair_outcome` 仍 NULL → 失败。
- `test_10b_crash_gap_finalize_is_idempotent_no_recount`：第二轮不再重复计数。旧实现第一轮就不 finalize → 失败。
- `test_10c_crash_gap_recovered_preserves_terminal_task_status[paused/stopped/deleted]`：恢复不复活 task、不开新组。旧实现 → 失败。
- `test_10d_crash_gap_rate_limited_settles_without_counter`：429 缝隙走 `settle_attempt_no_counters`（免计数）。旧实现 → 失败。

### 修复（一次性恢复扫描，非周期 guardian）
- `store.list_unsettled_terminal_attempts_for_task(task_id)`：返回该 task 中"两腿都 terminal 但 `pair_outcome IS NULL`"的 attempt（`NOT EXISTS` terminal=0 腿），按 `attempt_seq, id` 排序。task-local（amendment 21：无全局扫描）。
- `service._recover_crash_gaps(task_id, now_us)`：遍历上述结果，幂等 finalize（rate_limited 走 `settle_attempt_no_counters`，否则 `finalize_attempt`）。`finalize`/`settle` 本身幂等（`pair_outcome` 已置则返回 None/False），故第二轮 no-op —— **不重发、不重复计数、不开新组**。
- `service._reconcile_own_legs`：移除"`if not legs: return`"早退，在末尾 `return drain_signal` 前调用 `_recover_crash_gaps`；`hasattr(query_leg)` 早退前也调用一次，保证 disabled executor 模式下缝隙仍被恢复。
- `service._recover_workers`：扩展非 RUNNING（paused/stopped/deleted/done）task 的恢复发现 —— 除"有非 terminal 腿"外，**也**对"有 terminal-but-unsettled 缝隙"的 task 启动 drain-only worker（Q2 drain-before-exit 后 finalize 缝隙再退出）。**这是 `start()` 的一次性恢复发现，不是周期 scanner/timer**（finding 4 约束）。

### 修复后证据
6 例反向回归转绿；`test_6a/6b/6c`（H-1 三防线：无全局 guardian / 单 task worker / 重启不复活）仍全绿。

---

## 4. finding-6 — validator 覆盖 dispatch 回执 pending 与根 status 阶段一致性

> 背景约束（packet 72 §7）：该 finding 的**簿记部分已由 bookkeeper 于 faa33b9 修复**（66/67/68 回执封存 + 根状态推进到 review_2）。本实现**只做 validator 与其测试**，不触碰 `status.json` / `70-handoff.md` / 任何 dispatch 回执。

### 实现
`scripts/validate-stage.py` 新增 `validate_dispatch_receipt_phase(root, stage_dir, status_doc)`（仅 `human-operator/v1` 阶段生效；读取 status.json dispatch 引用 + 回执 block，只读不改）：
- **(a)** 对 status.json 引用的每个 review dispatch（top-level/parallel task `review_1` + `review_2`），若回执 `status=pending` 且其声明的 `outputs` 文件已存在于磁盘 → 报错（回执未封存、产出已生成）。
- **(b)** 引入 `_STATUS_PHASE` / `_REVIEW_PHASE` 有序阶段模型；某 review 的 dispatch 文件已存在（即已进入该阶段）但根 status 仍停在更早阶段（例如 `review_2.dispatch_path` 存在而 `status=review_1`/`fixing`/`implementing`）→ 报错。`paused/blocked/abandoned/escalation/exhausted` 等冻结态豁免（不二次质疑已进入的阶段）。缺失的 dispatch 文件交给既有 `validate_review_artifacts`（不重复报）。
- 在 `main()` 的 `validate_common` 之后无条件调用（所有 phase）。

### 反向回归（先证明缺陷会失败）
`TestDispatchReceiptPhaseConsistency`（12 例）：修复前 `validate_dispatch_receipt_phase` 不存在 → `AttributeError` 全失败。覆盖：(a) pending+outputs 存在/缺失/placeholder/done；(b) review_2 派发但根 review_1/fixing/匹配/豁免；(a)+(b) 同时；legacy（无 dispatch_protocol）跳过；缺失 dispatch 文件不重复报。

### 修复后证据
12 例转绿；既有 55 例 validator 测试零回归（共 67 passed）。

### ⚠️ validator 在当前 stage 检出额外漂移（超出本修复修改权限）
以 `--phase checkpoint` 运行于当前 stage，F6 正确报告两条 finding-6(a) 漂移（**这正是 validator 应当自动检出的目标**，与 Review-2 Finding 5 同类）：

```
- tasks[frontend].review_1: dispatch receipt is status=pending but its declared outputs file already exists: .../59-review-1-frontend-r2.md
- review_2: dispatch receipt is status=pending but its declared outputs file already exists: .../69-review-2.md
```

- `dispatch 59`（frontend review_1）回执 `status=pending`、`started/completed` 空、`session_id=unavailable:pending human execution`，但 `59-review-1-frontend-r2.md` 已存在、`frontend.review_1.verdict=ACCEPT` 已记录。
- `dispatch 69`（review_2）同形：回执 pending 但 `69-review-2.md` 已存在、`review_2.verdict=REWORK` 已记录。

依据 packet 72 §7「**你不需要也不允许再改 status.json / 70-handoff.md / 任何 dispatch 回执**」，本实现**不封存这两条回执**，留交 bookkeeper：若它们确属已执行节点，应依据真实 operator 记录补齐为 completed（不得编造命令/时间/Session ID）；若属合法 pending（如尚未执行的派发），则其 outputs 引用与 verdict 记录需 bookkeeper 重新核对。(b) 未报错 —— 根 status 已正确推进到 `review_2`（faa33b9）。

---

## 全套自测结果（原始输出已追加到 `60-test-output.txt`）

| 命令（28 §5） | 结果 |
| --- | --- |
| 9 文件聚焦套件（含 `test_hedge_purity.py`） | **227 passed** |
| `backend/tests` 全量 | **918 passed** |
| `node frontend/self-check.js` | **全部自检通过** |
| `scripts/tests/test_validate_stage_dispatch_protocol.py` | **67 passed** |
| `git diff --check` | **clean（exit 0）** |

## 既有性质保持（H-1 三防线 + packet 62/63/65/67）
`test_6a/6b/6c`（H-1：无全局守护 / 单 task 本地 worker / 重启不复活非 RUNNING task）、`test_1`–`test_5`、`test_4b`、R1–R9 全绿（含于上面 918 / 227）。七端点 allowlist、`_ENTRY_EVENT_KINDS`、scheduler/server 均未变。

## 剩余风险
1. **dispatch 59/69 回执未封存**（见上节）：validator 现已能机器检出，需 bookkeeper 按真实记录处理；在它们被封存为 completed（或 outputs/verdict 被核对）前，当前 stage 的 `validate-stage.py` 会在 F6(a) 处报红。这**不**影响代码修复正确性，仅是簿记完整性。
2. **F3（状态守卫）/F5（账户健康）按用户裁定未做**：迟到 worker 结果覆盖人工 delete/pause 的低概率场景、以及 Spot NOTIONAL/MIN_NOTIONAL 与账户健康端点，留待实盘验证后再决策（用户原话方向）。
3. F4 恢复扫描仅在 worker 运行 / `start()` 一次性发现时触发；无任何常驻 guardian/timer（finding 4 约束已遵守）。

## 停止
实现完成，停止并等待 bookkeeper。未 commit、未派发评审、未自行宣称验收。
