[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

## Bookkeeper intake routing note

本 prompt 保留 Kimi 工件中的三项 P1、原始证据、边界与测试要求。该 Kimi
attempt 的 JSON 本身 schema-valid，但本地 Session registry 证明所报 session
创建于本轮之前，不满足 fresh-session 硬门禁，因此它不作为正式 review-1 gate
verdict，formal rework_count 保持 0。Bookkeeper 已在固定 head 上独立复核
F1/F2/F3 均成立，本轮作为 pre-formal intake correction 执行；修复后必须生成
新 committed fingerprint，并由真正 fresh 的 Kimi 会话重新执行 formal
review-1。不得据此声明 review 或 acceptance。

# Task C — Review-1 REWORK Fix（三项 P1）

你是 Task C 原实现者：claude_glm / provider identity zhipu_glm / glm-5.2[1m]。

- Stage: 2026-07-real-borrow-boundary-c-v1
- 被审 diff fingerprint: 61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984
- Raw review（含完整 findings 与证据）: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md
- 本轮为 pre-formal bookkeeper correction（formal rework_count 仍为 0；max 3）。

## 必读

1. AGENTS.md
2. agents/developer-discipline.md
3. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md
4. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md（scope 与 AC 7/12/13）
5. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md（D9）
6. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md（ADR-001、ADR-006）
7. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md（§5.3、§6）
8. backend/borrow_tasks/store.py、backend/borrow_tasks/service.py、backend/services/live_borrow_executor.py、frontend/index.html、frontend/self-check.js
9. reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt

## Findings 与 required fixes（按序）

### F1 (P1) — 过期「不发起真实借币」文案与 live 执行状态矛盾

证据：frontend/index.html:942（subtitle）、:953（静态 banner）、:2548（任务卡 note 模板）均为静态文案且无任何 JS 改写，声称「本阶段不发起真实借币（执行未启用）」/「所有尝试结果均为『执行未启用』」；live+已启动时与同屏执行徽标（模式 live · 已启动）直接矛盾。
违反：00-task.md scope「Replace stale 'execution disabled/no real borrow' copy」；10-design.md D9；12-development-breakdown.md §6；AC #12。
必修：删除/改写这三处文案，使其不再声称「不发起真实借币」；保留仍属实的陈述（浏览器不调度、不模拟、不签名、不请求 Binance）；文案与执行模式语义一致（中性静态文案或从已加载的 execution-status 投影派生）；不得新增浏览器侧调度/签名；在 frontend/self-check.js 增补对应断言且不放宽任何守卫。

### F2 (P1) — 创建路径缺少提交前的目标总量与当前间隔确认展示

证据：frontend/index.html:1709-1717 操作列仅有数量输入、次数输入与确认按钮；createBorrowTask（:2362-2371）形状校验后直接 POST；创建前不展示 amount×count 目标总量，也不展示当前全局间隔（间隔仅在借币任务视图设置行 :2453-2457 显示，不在行情表创建路径）。
违反：00-task.md scope「Show amount × count = maximum target quantity and current interval before creating an immediately runnable task」；D9 与 §6 的 pre-create confirmation text；AC #12「confirms target total and interval before create」；ADR-001「The pre-submit UI must display asset, amount, successful count, target total, and interval」。
必修：在行情表创建路径提交 POST 前展示资产、数量、次数、计算所得 amount×count 最大目标总量与当前全局间隔（用已加载的 scheduler settings 渲染；沿用 multiplyDecimalString / BigInt 精度纪律，禁止 float）；不得引入新的任务状态机或浏览器调度；在 frontend/self-check.js 增补断言且不放宽 timer/fetch-method 守卫。

### F3 (P1) — 崩溃孤儿 pending attempt 永不进入有界 reconciliation

证据：backend/borrow_tasks/store.py:761-776 list_due_reconciliations 要求 outcome='resolved' AND result_category='unknown' AND reconcile_next_at_us IS NOT NULL；崩溃孤儿（insert_pending_attempt 提交后、resolve_attempt 前进程退出）永远保持 outcome='pending' 且 reconcile_next_at_us=NULL；reconcile_next_at_us 的全部写入仅在 unknown resolve 分支（:640-642）与 advance_reconciliation；启动恢复（:195-201）只重新标记任务 blocked。现有测试仅断言 blocked（test_borrow_store.py:65-76），无孤儿进入 reconciliation 的证据。
违反：11-adr.md ADR-006「Pending/orphan/unknown attempts remain blocked and enter bounded reconciliation」；00-task.md Goal「reconcile ambiguous attempts through the verified loan record API」；AC #7（unresolved task 的唯一解决路径是 +5/+15/+60/+300/+900s 有界 reconciliation）；AC #13 与 20-implementation.md 宣称的「restart-orphan recovery」名不副实。
必修：在启动恢复中（幂等）把孤儿 pending attempt 作为 response-less unknown 纳入 reconciliation 调度（reconcile_step=0，reconcile_next_at_us 锚定 now+RECONCILE_DELAYS_SECONDS[0]，reason 标记如 crash_orphan_responseless，outcome 收尾为 resolved/unknown），使其走既有 _reconcile_pass；唯一 CONFIRMED 匹配且 attribution_is_unique 通过才可 resolve_reconciliation_success，且该函数须同时把原为 pending 的 attempt 行收尾（outcome/result_category/finished_at_us）；无匹配/多候选/跨任务歧义/五次读尽继续 blocked。严禁第二次 POST、严禁 force-clear 或 retry-anyway 路由。
新增测试：重启后孤儿进入调度并在唯一匹配时计数成功；无匹配耗尽保持 blocked；重复启动幂等不重复排程；孤儿路径零第二次 POST。

## File boundaries（原 Task C 冻结边界，本轮只允许触碰与三项 finding 直接相关的文件）

允许：
- frontend/index.html、frontend/self-check.js
- backend/borrow_tasks/store.py、backend/borrow_tasks/service.py（保持 network/signing-free）
- backend/services/live_borrow_executor.py（仅当 F3 的 finalize 语义需要）
- backend/tests/test_borrow_store.py、backend/tests/test_borrow_scheduler.py、backend/tests/test_live_borrow_executor.py、backend/tests/test_borrow_api.py（仅确有必要）
- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md（新建）
- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt（append only）
可选（P3，非门禁）：backend/services/portfolio_margin_borrow_client.py 移除未使用的 raw_body 字段；.env.example 增补 BINANCE_BORROW_API_KEY/BINANCE_BORROW_API_SECRET 文档行。
禁止：status.json、70-handoff.md、ACTIVE.json、00-task/10-design/11-adr/12-breakdown、bookkeeper audit、30-review-1.md、canonical docs、Harness/workflow/validator、unrelated stage、reports/agent-runs/_proposals/**；不 commit/push/merge，不 dispatch 任何模型。

## 安全约束

- 严禁真实、认证或 production-reachable Binance 请求；全部 transport 练习继续用 injected fake/recording transport + dummy credentials。
- 不读取 .env、key file、cookie、credential store 或 expanded alias environment。
- 禁止新增第二次 POST、隐藏 retry、retry-anyway/force-clear 路由；禁止弱化 exact-path/HMAC/urlopen/AST/UI 守卫。

## 完成验证（fake-only；每条真实输出追加到 60-test-output.txt，不覆盖既有内容）

python3 -m pytest backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_live_borrow_executor.py -q
python3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
git diff --check

## 收尾

新建 reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md，逐项映射 F1/F2/F3（及可选 P3）→ root cause → changed files → tests → result；把上述命令真实输出追加到 60-test-output.txt；回填本轮 dispatch receipt；然后停止，交回 bookkeeper；不得宣称 review 或 acceptance。
