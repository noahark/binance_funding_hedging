<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd: claude-glm --model glm-5.2 --permission-mode acceptEdits -p "$(cat <prompt-file>)"
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md
next_dispatch: none
authorization: user-authorized SIXTH bounded backend change; 27-user-authorized-r4-repair.md (scope = P2-1 + P2-2 only)
fallback_reason: none. Claude-GLM remains the backend owner across all five prior rounds. The user initially named Claude Sonnet 5 and, after the bookkeeper surfaced the review-routing consequence (an Anthropic fix author would empty the Review-1 cross-review pool: Anthropic barred as same-provider, claude_glm hard-barred as implementer, Kimi and Codex out of quota), selected Claude-GLM so Claude Opus 5 stays eligible for the next Review-1.
bookkeeper_note: PROMPT BODY is the reviewer's verbatim fix_start_prompt from 66-review-1-backend-r4.md. The single pinpoint substitution is item 2's authorization marker (was "needs user authorization first", now "authorized"), disclosed inline in the body. No reviewer evidence was summarized, reordered, or removed.
contract_doc_addendum: the body's forbidden-contract list reads "15/16/17/19/21/23/24/25/26" because 27-user-authorized-r4-repair.md did not exist when the reviewer wrote it. 27 is a contract document too and is equally forbidden to modify. This is mechanical routing metadata, deliberately kept out of the immutable body.
r10_checklist: task_prompt_path=67-fix-review-1-backend-r4.dispatch.md; self_tests_command per the body's "精确自测" block; next_dispatch_executor=human_operator; pass_branch=write 46-fix-review-1-backend-r4.md with actual test output and stop for bookkeeper; blocker_branch=stop and escalate, packet 67 may not expand beyond P2-1 + P2-2; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 2026-07-hedge-open-real-api-v1 的后端返工实现者（第 6 次有界变更）。禁止调用、启动或转派任何其他模型会话或 adapter。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start、绝不 commit、绝不改 status.json / 70-handoff.md / 任何契约文档（15/16/17/19/21/23/24/25/26 号）与任何评审报告（30/42/50/58/64/66 号）。

先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md（本评审全文，含 §4 两条 P2 的原始复现输出与末尾 JSON verdict）、26-user-authorized-settlement-and-pause-fix.md（用户第 5 次授权与 §10 验收条件）、21-task-local-runtime-and-manual-pause-amendment.md（运行时最高合同）、24-user-authorized-final-guardian-fix.md（H-1 边界）、15-immediate-loop-and-open-log-amendment.md（对账绝不放弃 + 错误矩阵）、44-fix-review-1-backend-r3.md（上一轮实现报告）、42-final-guardian-scanner-fix.md 与 40-fix-review-1-backend-r2.md（packet 62/63 必须保留的既有性质）。

被审指纹 9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c:fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db 是你的起点，bookkeeper 会在你完成后重算新指纹。

重要前提：**上一轮四项 P1/P2 的生产代码已被 Review-1 逐条重新验证为正确**（429 恢复清粘滞 + 逐次尝试 rate_limited 标记；人工 pause/delete 由本卡 worker drain 后退出且不开新组，已用真实线程独立复验；settle_attempt_no_counters 按两腿真实事实推导并落 leg_exposure；worker_active 三态 + last_worker_exit_reason）。**不要重做、不要重构、不要顺手改进这四项的生产语义。** 本次只做下面两件事。

绝对不能破坏的既有性质（全部有回归钉住）：live start() 只做一次 _recover_workers() 后返回且不启动 HedgeOpenScheduler；live tick() 是安全空操作；post_start 只启动指定卡；每卡一个有界 worker 只查自己的腿；同卡 pair 串行、双腿并发；跨卡隔离；target_n 原子硬上限；无 orderId 只按 clientOrderId 查询绝不重发（ADR-2）；store 锁内不调 executor；7 端点冻结 allowlist 与签名前置门；默认关闭；_ENTRY_EVENT_KINDS 不得新增 kind；frontend/** 零改动。**不得引入任何全局守护/周期扫描器/timer。**

必须修复两项：

1) 【P2-1，必做】R3 / R4 是空回归 —— 既没复现过旧缺陷，也钉不住新修复。证据：_pump_worker（service.py:942-964）这轮新增的 P3 改动在**每次调用开头无条件 ev.clear()**，而测试辅助 _step()（test_hedge_task_local.py:57-63）就是一次 _pump_worker 调用；R3/R4 的写法是 _step(1) → post_pause()/post_delete() → _step(3)，第二次 _step 把 post_pause 可能置位的 stop event 又清掉了。Review-1 实测（猴补丁，未改仓库文件）：把删掉的 _wake_worker 语义原样加回 post_pause 后，'stop_event set right after the regressed post_pause : True'，而 R3 四条断言 query_calls>=2(2) / both legs terminal / pair settled / no new pair opened **全部照样通过**；又重建修复前 seam 语义（_pump_worker 不注册 stop event + post_pause 调 _wake_worker），'stop_events registered at all : {}'，R3 **同样全绿**。这违反用户授权书 §10.1 的验收条件，并使本 stage 最危险的路径（人工暂停/删除不得丢弃在飞真实订单）在 905 个测试里没有任何有效护栏。修法：(a) 让 _pump_worker 不再吞掉 stop event —— 只在**首次注册**时创建并 clear，已存在则保持原状；或加一个仅测试使用的形参（如 reset_stop_event: bool = False），由确实需要重置的用例显式传入。(b) 给 R3 与 R4 各加一条直接断言：post_pause / post_delete 之后该卡的 stop event **未被置位**（svc._stop_events[tid].is_set() is False），并保留现有全部 drain 断言。(c) 可选加强：把 R3 再加一个真实线程版本 —— 用一个在首次 query_leg 上阻塞的 executor，确保 post_pause 落在两腿真在飞的时刻，再断言 worker 自行 drain 到终态、结算该组、scheduled_attempt_count 不增、最终退出且 last_worker_exit_reason == task_not_running。**不要改动 post_pause / post_delete / _worker_round 的生产语义。**

2) 【P2-2 —— 用户已于 2026-07-25 授权，见 27-user-authorized-r4-repair.md §4/§5.2；本条由待授权改为**必做**，这是 bookkeeper 对 reviewer 原文的唯一定点替换，Review-1 原始表述保留在 66-review-1-backend-r4.md 内】_recover_workers 的只对账兜底（service.py:1219）本轮从 (PAUSED, STOPPED) 扩到 (PAUSED, STOPPED, DELETED)，仍漏了 DONE。证据：resolve_attempt(leg_terminal=...)（store.py:892-924）在两腿都拿到 orderId、但其中一腿仍 NEW/PARTIALLY_FILLED 时，会先把该组判为 accepted 并把任务推到 done，同时按设计把那条腿留在 terminal=0（service._leg_terminal, service.py:1530-1538）。Review-1 离线实测（target_n=1，perp FILLED，spot 受理但 NEW，零网络）：派发后 'task status = done / leg spot order_id=s1 status=NEW terminal=0 cum_base=0 / non-terminal legs = 1'；同一 sqlite 换新实例 start() 后 'ensure_worker calls during recovery = [] / query_calls made = 0 / leg spot terminal=0 cum_base=0 / non-terminal legs still = 1'。而 aggregate_positions（store.py:1567-1576）只累加 exchange_status == FILLED 的腿，于是这笔真实成交的现货腿永久记 0，一组**已经对冲好的**仓位被永久显示成裸空头（position_qty=-0.5, spot_avg=0），不会自愈。修法：把 D.STATUS_DONE 加进 service.py:1219 的兜底元组（该 worker drain 完即因 status != RUNNING 退出，绝不开新组，与刚加的 DELETED 完全同构），并新增一条与 R5 同构的确定性回归：done 卡带受理但非终态的腿 → 新实例 start() 的一次恢复交接把它查到终态、dispatch_calls 不增（零重发）、status 仍为 done。

必须新增/加强的确定性回归（离线、fake transport、零 sleep race）：
- R3 / R4 各加「post_pause / post_delete 后 stop event 未被置位」断言，并确认在把 _wake_worker 语义放回去时这两条会**失败**（在实现报告里给出你自己的验证输出）；
- （可选）R3 的真实线程版本；
- 【随 P2-2】done 卡带非终态受理腿 → 重启一次 recovery → drain 到终态、零重发、status 仍 done。

允许修改：backend/hedge_open_tasks/service.py（仅 _pump_worker 的 stop-event 初始化 + _recover_workers 的兜底状态元组）、backend/tests/test_hedge_task_local.py、reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt（仅追加原始输出）、reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md（新建实现报告，不覆盖已有 40/41/42/44 号报告）。禁止修改：backend/hedge_open_tasks/{store.py,domain.py}、backend/services/**、backend/app/server.py、backend/hedge_open_tasks/scheduler.py、frontend/**、docs/**、PRD、10-design/11-adr、reports/api-samples/**、status.json、70-handoff.md、任何契约文档与评审报告、环境/凭据/网络配置文件。

精确自测（提交前全部跑绿，原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：
.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

基线参照（Review-1 本机实测）：十组聚焦 = 229 passed；backend/tests = 905 passed；前端自检全通过；Harness = 55 passed；git diff --check exit 0。新增回归后总数应上升。

把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md，列出 changed files、每条新增/加强回归「先证明它在缺陷存在时会失败 → 再验证修复后转绿」的**你自己的原始输出**、H-1 与 packet 62/63/65 既有性质未被破坏的证据、剩余风险。然后**停止等待 bookkeeper** —— 不 commit、不派发评审、不自行判定验收。成功标准：R3/R4 在 _wake_worker 语义被放回时会失败、在当前代码下全绿；【若已授权】done 卡恢复回归新增并全绿；backend/tests 全量、前端自检、Harness 协议套件全绿；test_6a/6b/6c 与 test_1–test_5、test_4b 仍全绿；frontend/** 零改动；未新增任何 entries 事件 kind、全局守护、周期扫描器或 timer；全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start。
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/67-fix-review-1-backend-r4.dispatch.md
本地北京时间: 2026-07-25 CST
下一步模型: human operator
下一步任务: deliver this prompt body to a fresh write-capable Claude-GLM session; GLM writes 46-fix-review-1-backend-r4.md and stops for the bookkeeper
