[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

Task: Boundary C formal review-2 bounded repair for the original Claude-GLM/zhipu_glm fix author.

Authoritative raw review and verdict JSON: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/50-review-2.md (the final JSON object in that file is the raw verdict JSON).
Reviewed fingerprint: 87c19273c3f488cf6d9ca80f8541704bb198cb81:29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162.
Read before editing: AGENTS.md; reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md; 10-design.md; 11-adr.md; 12-development-breakdown.md; 40-fix-report.md; 50-review-2.md; and the affected source/tests below. The user-approved direction, PRD, and Architecture remain higher authority than stage design evidence.

Ordered findings to repair:
1. P1, backend/borrow_tasks/domain.py:175. The parser explicitly has no product minimum and accepts 0.5 seconds, while 00-task.md:35-37 and 12-development-breakdown.md:514,545-553 freeze a 2-second capacity floor. backend/tests/test_borrow_api.py:192-200, backend/tests/test_borrow_scheduler.py:155-167, frontend/index.html:964, and frontend/self-check.js:3074-3103 codify the invalid sub-floor value. Impact: live POST cadence can exceed the reserved half-IP budget and trigger a shared-IP 429/418 ban. Enforce interval_seconds >= 2 in the backend authority; make 1.999/0.5 fail with invalid_interval and 2/2.0 succeed; remove misleading UI examples and tests.
2. P1, backend/services/live_borrow_executor.py:185. Known-code classification runs before the 2xx branch, so HTTP 200 {"code":-51006} is known_rejection instead of unknown. The same ordering can treat a 5xx carrying a listed code as definitely rejected. 00-task.md:161-168 requires every 2xx without a valid normalized tranId and possibly accepted 5xx to be unknown. Impact: the task can return to rotation and issue a second borrow POST after an ambiguous response. Classify every 2xx first (valid tranId => success, otherwise unknown), keep 5xx unknown, and limit known_rejection to the three archived codes on a definite 4xx response after rate-limit handling.
3. P1, backend/borrow_tasks/store.py:583-607. insert_pending_attempt selects live_authorized but never checks it when live_gates=True. A fake-only reproduction with status=borrowing, live_authorized=0, execution_enabled=1 created a pending attempt. This violates 00-task.md:155-160 and 12-development-breakdown.md:288-305,569-571. Impact: an unauthorized/inconsistent persisted task can pass the final intent-before-send gate and reach a real POST. Recheck task["live_authorized"] == 1 inside the same transaction and prove the failed predicate creates zero attempt rows and zero executor POSTs.

Required changes:
- Implement all three fail-closed corrections without changing the frozen endpoint, signer, credential, retry, reconciliation, or result contracts.
- Add targeted regression tests for the exact reproduced cases: sub-2 interval rejection and 2-second boundary acceptance; HTTP 200 and 5xx with each known code remain unknown while 4xx known codes remain known_rejection; live_authorized=0 aborts the atomic insert and produces zero transport calls.
- Update the interval UI copy/local behavior and frontend self-check so it no longer offers or accepts 0.5 seconds.
- Preserve the existing non-catch-up scheduler, one-shot POST, unknown latch, cooldown/manual-rearm, migration, ownership, and read-only PrivateClient behavior.
- Record a finding-to-change/test mapping in 40-fix-report.md and append exact command output to 60-test-output.txt. Do not rewrite or hide the raw review.

Allowed files:
- backend/borrow_tasks/domain.py
- backend/borrow_tasks/store.py
- backend/services/live_borrow_executor.py
- backend/tests/test_borrow_domain.py
- backend/tests/test_borrow_api.py
- backend/tests/test_borrow_scheduler.py
- backend/tests/test_borrow_store.py
- backend/tests/test_live_borrow_executor.py
- frontend/index.html
- frontend/self-check.js
- schemas/api/borrow-tasks/scheduler-settings.schema.json only if needed to keep the output contract truthful
- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md
- reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt

Forbidden:
- Every file not listed above, especially signer/transport/credential configuration, other Binance routes, Harness/workflow/validator files, status.json, 70-handoff.md, and 50-review-2.md.
- Any real/authenticated/production-reachable Binance request, credential read or logging, second POST, hidden retry, retry-anyway path, force-clear, scope expansion, deployment, commit, push, merge, or model/adapter relay.
- Do not address the two nonblocking P3 observations (raw_body retained in memory and missing dedicated borrow variables in .env.example) in this bounded safety fix unless the human/bookkeeper separately scopes them.

Exact verification commands (fake/recording only):
1. PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py -q -p no:cacheprovider
2. PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q -p no:cacheprovider
3. PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
4. node frontend/self-check.js
5. PYTHONDONTWRITEBYTECODE=1 python3 -m pytest scripts/tests -q -p no:cacheprovider
6. PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
7. PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-validate-all-stages-compare.py --repo-root .
8. git diff --check

Success criteria:
- All three P1 reproductions fail closed and their positive-control cases still pass.
- All listed suites pass with no network and no repository cache artifacts.
- No credential/signature/full private body enters logs or reports.
- The diff remains inside the allowed files and the report maps each review finding to code and test evidence.
- Stop after self-tests, diff inspection, 40-fix-report.md and 60-test-output.txt updates. Do not commit. Hand control to the bookkeeper for audit, fingerprinting, committed evidence, and re-review.

## Bookkeeper Mechanical Routing Metadata

- Target: original implementer/fix author claude_glm / zhipu_glm / glm-5.2[1m].
- Executor: human_operator; this model session must not dispatch another model.
- Dispatch receipt: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-review-2-fix-7.dispatch.md.
- Append the required six-line runtime footer to the new Fix-7 section in 40-fix-report.md; record a verified Session ID and source when exposed, otherwise an explicit unavailable reason.
- Stop for bookkeeper after the reviewer-prescribed fake-only commands, report/test-log updates, and receipt fill. Do not commit, merge, deploy, read credentials, or contact Binance.
