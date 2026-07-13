# Handoff — 2026-07-local-service-launchd-v1

## Recovery Header

- Active phase: PTY route repair committed; superseding authorization v4 prepared and awaiting commit
- Next action: validate and commit v4, then resume the auto runner
- Read-set: = status.current_inputs
- Open blockers: committed v4 authorization
- Do-not-read: reports/agent-runs/**/history/** unless auditing the named repair snapshots

## Current State

- Stage: `2026-07-local-service-launchd-v1`
- Status: `human_escalation_required`
- Branch: `stage/2026-07-local-service-launchd-v1`
- HEAD: `5e80e039f6b12c06f94a996b4525b64861121e1b`
- Git status: authorization v4 and synchronized checkpoint pending commit
- Bookkeeper: Codex/OpenAI; designer and Harness prerequisite author, not delivery implementer or fix author
- Parallel mode: disabled
- Auto-review pipeline: enabled; attempt 3 stopped fail-closed
- Dispatch mode: `auto_review`
- Runner state: `awaiting_human`
- Usage: `model_calls_used=3`, `auto_code_changes_used=0`

## Artifact Index

- Intake/task/design: `00-intake.md`, `00-task.md`, `10-design.md`, `11-adr.md`
- Development breakdown: `12-development-breakdown.md`, validated by `13-software-architect-amendment.md`
- Adapter repair: `14-harness-adapter-repair.md`
- V3 prerequisite repair: `15-v3-prerequisite-repair.md`
- Implementation: `20-implementation.md`; delivery implementation still pending
- Current authorization pointer: `auto-run-authorization-v4.json`; prepared, not yet committed
- PTY route repair: `16-claude-glm-pty-route-repair.md`
- Latest runner receipt: `runner-3-implementation.receipt.json`
- Latest raw output: `runner-3-implementation-T1-launchd-service-attempt1.raw-output.md`
- Latest escalation: `80-escalation-unroutable_fix-20260713T075606Z.md`
- Historical repair snapshots: the four exact named files under `history/` referenced by `status.json`
- Review 1: pending Grok 4.5 auto gate
- Review 2: human-started and pending
- Tests: `60-test-output.txt`
- Machine state: `status.json`

## Findings And Repairs

- The absolute repository wrapper fixed the original exit-127 resolution error; attempt 2 reached the GLM gateway and received API `529` / error `1305` overload.
- The legacy `claude-glm` alias includes bypass permission policy. The wrapper now removes that alias-level token in memory without logging or rewriting the profile. Normal implementation explicitly uses `acceptEdits`; review uses `plan`; yolo remains an explicit registry route.
- Runner raw evidence now merges stderr and uses receipt-sequence-unique paths, preventing later attempts from overwriting prior bytes.
- Terminal escalation navigation now carries the last receipt/raw/verdict paths.
- Stage validation now fails on discontinuous mode history or a final transition that does not match current state. The duplicate v2 row was removed only after exact pre-repair snapshots entered `history/`.
- Targeted and full focused suites passed: 44 and 111 tests. No model was invoked during repair.
- Attempt 3 verified those repairs in the real runner path: stderr is retained, the raw path is sequence-unique, and escalation navigation is populated. The provider again returned API `529` / error `1305` before any delivery code change.
- Route comparison isolated the stable difference: attempts 2 and 3 were `entrypoint=sdk-cli` synthetic zero-token failures, while manual session `fdda0f8b-8332-448e-ab92-464a4b592545` was a real `entrypoint=cli` success.
- The new registered PTY wrapper removes `-p`, supplies a true terminal, requires a final persisted `entrypoint=cli` assistant turn, exits the TUI, and returns control to the unchanged auto runner. Fake end-to-end coverage passed; no real model was called during repair.
- Real `launchctl` mutation remains explicitly unauthorized.

## Blockers

- Commit the schema-valid superseding v4 authorization. Scope and budgets stay unchanged; usage remains `model_calls_used=3`, `auto_code_changes_used=0`.

## Next Action

After the authorization commit is clean, the auto runner performs the real PTY call. On success it continues through the frozen blocking checks, embedded cross-check, seal, and Grok review-1; it does not promote a manual session.

本地北京时间: 2026-07-13 16:28:13 CST
下一步模型: Codex bookkeeper
下一步任务: 校验并提交 superseding authorization v4
