# Handoff — 2026-07-local-service-launchd-v1

## Recovery Header

- Active phase: attempt 4 verified PTY `entrypoint=cli`; stopped fail-closed at an interactive Bash permission boundary
- Next action: human decides the explicit PTY tool-permission policy before any v5 authorization
- Read-set: = status.current_inputs
- Open blockers: `acceptEdits` can pause on Bash permission confirmation; no unattended completion/final turn
- Do-not-read: reports/agent-runs/**/history/** unless auditing the named repair snapshots

## Current State

- Stage: `2026-07-local-service-launchd-v1`
- Status: `human_escalation_required`
- Branch: `stage/2026-07-local-service-launchd-v1`
- HEAD: `0ea40b046d68994f4fdbadd2c58f67fcb8853c6b` (`bookkeeper(launchd): record PTY route probe result`)
- Git status: synchronized SHA checkpoint pending commit; sequence-4 evidence itself is committed
- Bookkeeper: Codex/OpenAI; designer and Harness prerequisite author, not delivery implementer or fix author
- Parallel mode: disabled
- Auto-review pipeline: enabled; attempt 4 stopped fail-closed after PTY route success and permission interaction
- Dispatch mode: `auto_review`
- Runner state: `awaiting_human`
- Usage: `model_calls_used=4`, `auto_code_changes_used=0`

## Artifact Index

- Intake/task/design: `00-intake.md`, `00-task.md`, `10-design.md`, `11-adr.md`
- Development breakdown: `12-development-breakdown.md`, validated by `13-software-architect-amendment.md`
- Adapter repair: `14-harness-adapter-repair.md`
- V3 prerequisite repair: `15-v3-prerequisite-repair.md`
- Implementation: `20-implementation.md`; delivery implementation still pending
- Current authorization: `auto-run-authorization-v4.json`; committed and schema-valid
- PTY route repair: `16-claude-glm-pty-route-repair.md`
- PTY probe result: `17-claude-glm-pty-probe-result.md`
- Latest runner receipt: `runner-4-implementation.receipt.json`
- Latest raw output: `runner-4-implementation-T1-launchd-service-attempt1.raw-output.md`
- Latest escalation: `80-escalation-unroutable_fix-20260713T084312Z.md`
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
- Attempt 4 proved the PTY route with real `glm-5.2`: eight model records, four Bash tool uses, three results, no synthetic response, and no API 529. The fourth Bash call remained unresolved under `acceptEdits`; no final turn or delivery write occurred.
- The bookkeeper did not approve the pending Bash command or enable yolo. It stopped only the stuck Claude child after the diagnostic objective was met; the runner then wrote a normal sequence-4 receipt and escalation.
- Real `launchctl` mutation remains explicitly unauthorized.

## Blockers

- Decide a bounded explicit permission policy for Bash/tool execution in the PTY auto adapter. Manual clicks cannot be treated as automatic evidence.
- Any further model call requires a new/superseding authorization; v4 cannot be reused.

## Next Action

Human decides whether to authorize a bounded tool allowlist design or another explicit route. Do not issue v5 with the unchanged `acceptEdits` PTY command because it can block indefinitely before review-1.

本地北京时间: 2026-07-13 16:47:39 CST
下一步模型: human
下一步任务: 决定 PTY auto adapter 的显式工具权限策略，再决定是否签发 v5
