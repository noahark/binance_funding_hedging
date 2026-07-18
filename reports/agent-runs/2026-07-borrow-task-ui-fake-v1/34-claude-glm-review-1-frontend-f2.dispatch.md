# Claude-GLM Review-1 Dispatch — Task F2 Frontend Borrow-Task UI

You are the formal Review-1 reviewer for frontend Task F2 in stage `2026-07-borrow-task-ui-fake-v1`. You are read-only: do not edit files, run write-capable commands, commit, update status/handoff, or invoke external services.

Review the committed range only:

```text
base_sha: 82db8414b97819b72294ba8eee33bd0b7ec0dfd4
head_sha: ddcecf5533352c25886aeadfdc233a826603ba7b
diff_fingerprint: ddcecf5533352c25886aeadfdc233a826603ba7b:c58dec3deda3453b000d9749488ff80f6d7eef8d4beb48fbae4507293e9387d0
```

Read raw artifacts before forming a verdict:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` (review-1 section)
- `schemas/review-verdict.schema.json`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md` (§3)
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/62-test-output-frontend-v2.txt`
- the actual diff `git diff 82db8414b97819b72294ba8eee33bd0b7ec0dfd4..ddcecf5533352c25886aeadfdc233a826603ba7b --` and relevant changed frontend/self-check files

Verify, rather than trust claims: full lifecycle button matrix and illegal transitions; soft-delete visibility; filter/count source; edit validation, current-value preload, success-count retention and readonly behavior; exact three-branch placeholder guidance including raw zero, escaping and empty input value; v1 regressions (13 columns, drawer isolation, HOME path, borrowed-out label); no fetch/timer/localStorage/scheduler/real borrow effect; quality of DOM-level coverage. Treat the unperformed browser visual check and the disclosed uncommitted-input reset behavior as explicit review considerations, not as completed manual evidence.

Write your full raw review narrative to `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/32-review-1-frontend.md`. Include concrete findings with severity P0–P3, file/line evidence, impact, and recommendation.

End the review file with the mandatory navigation footer, immediately followed by one strict JSON object valid against `schemas/review-verdict.schema.json`. Use:

- `schema_version: 1`
- `stage_id: "2026-07-borrow-task-ui-fake-v1"`
- `role: "first_reviewer"`
- `model: "glm-5.2"`
- the exact `diff_fingerprint` above
- `reviewer_prior_involvement: "none"`

For `REWORK`, provide a complete `fix_start_prompt` in the JSON: it must retain raw artifact paths, all findings, F2-only allowed/forbidden boundaries, exact tests (`node frontend/self-check.js`, `git diff --check`), and success criteria. Do not leave the verdict JSON invalid or omit it.

当前 Session ID: unavailable (to be recorded by Claude-GLM/operator after execution)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/34-claude-glm-review-1-frontend-f2.dispatch.md
本地北京时间: 2026-07-18 23:13:00 CST
下一步模型: Claude-GLM
下一步任务: 对 F2 已提交前端范围做只读正式 review-1，并写出 strict JSON verdict
