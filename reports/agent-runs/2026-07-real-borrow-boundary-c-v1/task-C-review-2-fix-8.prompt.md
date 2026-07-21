[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

Task: Boundary C Micro Fix-8 — close the single mechanical test-fixture residual left by Fix-7.

Context:
- Stage: `2026-07-real-borrow-boundary-c-v1`.
- Fix-7 source changes closed the three Review-2 P1 safety findings, but its full backend run ended with exactly two failures in `backend/tests/test_borrow_executor.py`.
- Raw implementer report: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md` (Fix-7 section).
- Raw test log: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt` (Fix-7 section).
- Independent intake: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md` (Fix-7 intake addendum).
- Source review: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/50-review-2.md`.
- Read `AGENTS.md`, the four artifacts above, and `backend/tests/test_borrow_executor.py` before editing.

Finding to close:
- `BK-R2-FIX7-001` (mechanical test-fixture residual, not a new product finding):
  `test_full_scenario_makes_zero_urllib_calls` and
  `test_poisoned_env_secrets_never_leak` still call
  `svc.put_settings({"interval_seconds": "1"})`. Fix-7 correctly made every
  sub-2-second interval fail closed, so both helpers now stop before exercising
  their actual zero-network / no-secret-leak assertions.

Required edit:
1. In `backend/tests/test_borrow_executor.py`, change those two fixture settings
   from `"1"` to the valid frozen boundary `"2"`.
2. In `test_full_scenario_makes_zero_urllib_calls`, also change its fake-clock
   progression from `t * 1_000_000` to `t * 2_000_000`, so all five queued
   executor categories are still exercised under the new two-second interval.
   Do not weaken or delete the `urlopen` tripwire, poisoned-secret assertions,
   result-category checks, or any other guard.
3. Append a Micro Fix-8 section to `40-fix-report.md` mapping
   `BK-R2-FIX7-001` to the three mechanical literal changes and actual tests.
4. Append actual command output to `60-test-output.txt`; do not overwrite any
   prior evidence.
5. Fill `task-C-review-2-fix-8.dispatch.md` receipt and stop for bookkeeper.

Allowed files — exact:
- `backend/tests/test_borrow_executor.py`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md` (append only)
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt` (append only)
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-review-2-fix-8.dispatch.md` (receipt only)

Forbidden:
- Every other file, including all product source, frontend, schemas, Harness,
  workflow, `status.json`, `70-handoff.md`, `ACTIVE.json`, and raw review files.
- Any real/authenticated/production-reachable Binance request, credential read
  or logging, second POST, hidden retry, retry-anyway, force-clear, deployment,
  commit, push, merge, review dispatch, or model/adapter relay.
- Do not address the two Review-2 P3 observations.

Exact verification commands (all local/fake-only):
1. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_executor.py -q -p no:cacheprovider`
2. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider`
3. `node frontend/self-check.js`
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest scripts/tests -q -p no:cacheprovider`
5. `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py`
6. `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-validate-all-stages-compare.py --repo-root .`
7. `git diff --check`

Success criteria:
- `test_borrow_executor.py` is all green and still exercises all five fake
  categories without `urllib` access.
- Full backend, frontend self-check, Harness tests, py_compile, compare sentinel
  and diff check are green.
- The implementation diff outside this exact Micro Fix-8 boundary is unchanged.
- Stop after report/log/receipt updates. Do not commit or dispatch reviewers.

## Bookkeeper Mechanical Routing Metadata

- Target: original implementer/fix author `claude_glm` / `zhipu_glm` / `glm-5.2[1m]`.
- Executor: `human_operator`; this session must not invoke another model.
- This residual does not increment formal `rework_count`.
- After successful bookkeeper intake and a new committed fingerprint, the user
  has authorized the narrow RC4 Review-1 fingerprint exception route directly
  to a correctly executed Review-2; this implementer must not prepare or run
  that review.
- Append the required six-line runtime footer to the new Micro Fix-8 report
  section, using a verified Session ID/source or an explicit unavailable reason.

