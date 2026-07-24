<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md
next_dispatch: none
supersedes: none; final bounded backend repair from 58-review-1-backend-r2.md
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable; reviewer-provided fix_start_prompt preserved below） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 2026-07-hedge-open-real-api-v1 的返工实现者（后端）。禁止调用、启动或转派任何其他模型/adapter。先逐字读取本文件 reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md（含最后 JSON verdict），以及 15-immediate-loop-and-open-log-amendment.md、16-replacement-development-breakdown.md（§2.1 I-7、§3.2 A-3/A-5）；固定被审指纹 8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320 不得作为你的提交基线——你将在其之上继续修改，bookkeeper 会在你完成后重算新指纹。

必须修复两项：

1) backend/hedge_open_tasks/domain.py：compute_preflight 对 est_price 缺失/不可读（None 或 <=0）的完整性要求必须与开单方向无关。当前只有 DIR_FORWARD 分支在 est_price 缺失时返回 REJECT_PREFLIGHT_INCOMPLETE（约677-689行），DIR_REVERSE 分支（约692-703行）完全不检查 est_price，且 _check_common_quantity（约552-578行）的 minNotional 校验在 est_price 为 None 时被整段跳过而非拒绝。修复：让价格完整性检查在方向分支之前统一执行，或让 _check_common_quantity 在价格缺失时返回一个会被上层识别为 REJECT_PREFLIGHT_INCOMPLETE 的显式信号，确保反向任务在价格不可读时同样 fail-closed（零 attempt、零 POST、零失败计数）。新增确定性单测：反向方向 + est_price=None 的 PreflightSnapshot → compute_preflight 结果必须是 REJECT_PREFLIGHT_INCOMPLETE。

2) backend/hedge_open_tasks/service.py：_reconcile_pending 当前是 tick() 持有服务锁期间的同步串行循环（对每条非终态腿逐条阻塞查询），且是调度线程唯一驱动源，查询超时仍是 10 秒（hedge_open_live_client.py DEFAULT_TIMEOUT_SECONDS）。多条待对账腿或慢查询会导致本次 tick 耗时线性增长，期间任何任务（含零未决腿的任务）都无法获得新的一组下单，违反 amendment 'reconciliation ... never blocks another task's dispatch'。修复：把非终态腿对账改造为有限并发（可参照已有的按任务并发范式 _dispatch_eligible_concurrently）并设置耗时预算，使一次 tick 的对账阶段不会因待对账腿数量或查询延迟而线性拖慢同一批次或后续批次的新组派发。新增确定性回归：注入一个需要显式信号才返回的慢速 query_leg，让某任务的对账长时间挂起，断言另一个零未决腿、本应立即可派发的任务仍能在合理短时间内的后续 tick 中拿到新的一组，不等待慢查询。

可选（P2，不单独构成阻断，但请勿在报告中再次描述为'已完全解决'）：在 hedge_open_live_client.py 中捕获交易所返回的实时订单计数/权重响应头（如可得），为未来主动频率门禁积累事实基础；若本轮不实现，请在修复报告的剩余风险中明确写出这仍是已知限制。

允许修改：backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}，backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}，backend/app/server.py（仅为独立恢复职责所需的最小接线），直接相关 backend/tests/test_hedge_*.py 与 test_live_hedge_executor.py。禁止修改：frontend/**、docs/**、PRD、设计/ADR、status.json、70-handoff.md、50-review-2.md、本评审文件 58-review-1-backend-r2.md、15/16/17/19 号契约文档、环境/凭据文件、任何真实网络配置。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live/Start。

精确自测（在提交前全部跑绿，并把原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_review2_regressions.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md（新文件，不覆盖已有 40/41 号报告），列出 changed files、每条新增回归测试先复现旧缺陷再验证修复的证据、剩余风险，然后停止等待 bookkeeper；不得提交、不得派发评审、不得自行判定验收。成功标准：上述两条新增测试先能在修复前的代码路径上复现所述缺口（或以清晰推导说明为何在当前代码上必然复现），修复后全部转绿，完整 backend/frontend 回归通过，且没有任何真实 POST/私有网络。
```

执行路由说明（不改写上方评审原文）：本次只授权两项 P1 修复。实时订单计数/权重响应头（P2）不进入本次最后一次返工，必须在报告「剩余风险」中如实保留。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/61-review-1-backend-r2-rework.dispatch.md
本地北京时间: 2026-07-24 22:35:36 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session
