# Handoff — 2026-07-local-service-launchd-v1

## Recovery Header

- Active phase: testing complete; P2 attempt 2 and all deterministic checks pass, pending evidence seal/new fingerprint
- Next action: Codex bookkeeper commits the verified repair, recomputes fingerprint, and prepares a fresh complete review-2 packet
- Read-set: = status.current_inputs
- Open blockers: repair is not yet sealed to a committed head/fingerprint; fresh review-2 `ACCEPT` remains required before push/merge
- Do-not-read: reports/agent-runs/**/history/** unless auditing the named repair snapshots

## Current State

- Stage: `2026-07-local-service-launchd-v1`
- Status: `testing`
- Branch: `stage/2026-07-local-service-launchd-v1`
- Review snapshot HEAD: `85ab5011e4b99fe464d9e1996ad455fdbc389206`
- Fingerprint: `85ab5011e4b99fe464d9e1996ad455fdbc389206:116eabe6e42623ee5f6cb84e9dfe470c2edeaf8ee649877c981244d530b3e778`
- Git status: attempt-1 failure evidence is committed at `0803ef1`; verified attempt-2 delivery changes and raw evidence are pending the repair evidence commit
- Bookkeeper: Codex/OpenAI; designer and Harness prerequisite author, not delivery implementer or fix author
- Parallel mode: disabled
- Auto-review pipeline: disabled after explicit human mode flip; v5 is historical and must not be reused
- Runner host: Kimi, host-only session; switching requires explicit human instruction
- Dispatch mode: `human_dispatch`
- Runner state: `null`
- Usage: `model_calls_used=5`, `auto_code_changes_used=0`

## Artifact Index

- Intake/task/design: `00-intake.md`, `00-task.md`, `10-design.md`, `11-adr.md`
- Development breakdown: `12-development-breakdown.md`, validated by `13-software-architect-amendment.md`
- Adapter repair: `14-harness-adapter-repair.md`
- V3 prerequisite repair: `15-v3-prerequisite-repair.md`
- Implementation: `20-implementation.md`; delivery implementation still pending
- Historical last auto authorization: `auto-run-authorization-v5.json`; committed, consumed, and no longer active after the human mode flip
- Historical Kimi runner-host dispatch: `19-kimi-runner-host-dispatch.md`; do not rerun
- Attempt-5/manual-takeover report: `21-auto-v5-interruption-manual-takeover.md`
- Interrupted session metadata: `runner-5-interrupted-transcript-metadata.json`
- Manual implementation prompt/policy/dispatch: `manual-implementation-T1-launchd-service.*`
- Attempt-1 operator-forwarded report: `manual-fix-T1-launchd-service-attempt1.operator-forwarded-output.md`
- Narrow attempt-2 prompt: `manual-fix-T1-launchd-service-attempt2.prompt.md`
- Attempt-2 operator-forwarded report: `manual-fix-T1-launchd-service-attempt2.operator-forwarded-output.md`
- Formal review-1 prompt/dispatch: `manual-review-1-T1-launchd-service.prompt.md`, `manual-review-1-T1-launchd-service.dispatch.md`
- PTY route repair: `16-claude-glm-pty-route-repair.md`
- PTY probe result: `17-claude-glm-pty-probe-result.md`
- Kimi host/tool policy repair: `18-runner-host-tool-policy-repair.md`
- Tool-policy repair commit: `bfbc2ee394bcf40f422f8a826e4acfb99648642e`
- Latest runner receipt: `runner-4-implementation.receipt.json`
- Latest raw output: `runner-4-implementation-T1-launchd-service-attempt1.raw-output.md`
- Latest escalation: `80-escalation-recoverable_resume_unverifiable_unit-20260713T104052Z.md`
- Historical repair snapshots: the four exact named files under `history/` referenced by `status.json`
- Pre-review repair prompt: `manual-fix-T1-launchd-service-pre-review.prompt.md`
- Review 1: `ACCEPT`; schema-valid Kimi verdict bound to the frozen fingerprint; one accepted P3, no required fixes
- Review 2: schema-valid `BLOCKED`; actual identity `anthropic`/`claude-opus-4-8`, prior involvement `breakdown`; canonical raw/verdict recovered from Claude session `cced0347-7f53-4626-958b-ecffba5d10b6`; zellij forwarding corrupted only the copied representation
- Review-2 coverage audit: incomplete against the prompt minimum read set; the blocking verdict is retained, but a fresh complete review is mandatory after fixes and this verdict cannot authorize acceptance
- Real launchd acceptance: FAIL; plist loaded, five exit-126 attempts, macOS Desktop TCC denied working-directory/script access; failed job stopped, plist retained
- Human runtime decision: keep the Desktop checkout, do not add privacy expansion, use human-started `scripts/run-server.sh` for local startup/visible acceptance, and do not require a repeat launchd test from this protected path
- P2 attempt 1: exact raw output at `manual-fix-T1-launchd-service-review2-P2-attempt1.raw-output.md`; all frozen checks pass, but the independent final-sleep probe fails
- P2 attempt 2: exact raw output at `manual-fix-T1-launchd-service-review2-P2-attempt2.raw-output.md`; tool audit is Read/Edit only; 88 targeted tests, 301 backend tests, all other frozen checks, and final-sleep probe pass
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
- The operator approved the explicit `software_architect` design. Registry write routes now use `implementation-v1` (`Read,Glob,Grep,Edit,Write`) and read-only routes use `review-readonly-v1` (`Read,Glob,Grep`); both use `dontAsk`, exclude Bash, and load a runner-generated stage-local path policy.
- The PTY wrapper uses safe mode, disables slash commands, supplies an empty strict MCP configuration, validates policy location/shape, and rejects actual-model drift. New Claude-GLM receipts bind the policy ID and evidence path while historical receipts remain valid.
- Runner preflight rejects Kimi host drift, legacy `acceptEdits`/bypass normal routes, malformed policies, unsafe pathspecs, and executable-mode paths outside authorization. Blocking tests, git, and optional exact-path `0755` normalization remain deterministic runner work.
- Focused and full tests passed without a model call or delivery-code change. No real `launchctl` mutation occurred.
- Real `launchctl` mutation remains explicitly unauthorized.
- Auto attempt 5 reached real `glm-5.2` through `entrypoint=cli` and `dontAsk`, completed 27 Read + 3 Glob calls, and made no writes before ending without a final turn.
- Because the call occurred before the runner lifetime ended, cumulative usage is corrected from 4 to 5 even though no sequence-5 receipt/raw output exists. No evidence artifact is fabricated.
- A second runner lifetime stopped on the overbroad historical-receipt resume guard. The human chose the frozen manual mode-flip path instead of another auto authorization.
- The manual packet uses a fresh foreground PTY session, explicitly invokes `senior_developer`, keeps Bash unavailable, and narrows writes to five delivery files; `scripts/run-server.sh` is read-only.

## Blockers

- No open delivery-code or deterministic-test finding. P2 attempt 2 removes the
  final extra sleep and adds direct restart-timeout coverage.
- The verified worktree must be committed and rebound to a new fingerprint.
- The recovered review-2 did not inspect the complete mandatory artifact set.
  After the runtime decision and repair, review-2 must run again from the new
  committed fingerprint with full coverage.

## Next Action

Codex bookkeeper commits the verified two-file repair plus raw evidence, records
the new `head_sha` and `diff_fingerprint`, runs `pre-review` validation, and
prepares a fresh review-2 prompt that explicitly requires the complete artifact
read set omitted by the prior Opus attempt. The human then dispatches that
packet; no bookkeeper model invocation occurs.

The user has authorized commit, push, and merge only after all hard gates pass.
The authorization is not currently executable because review-2 remains
`BLOCKED` and P2 is unimplemented.

The old `manual-review-2-T1-launchd-service.opus-json-retry.prompt.md` is
superseded and must not be dispatched.

本地北京时间: 2026-07-13 23:07:07 CST
下一步模型: Codex bookkeeper
下一步任务: 封存修复、重算 fingerprint 并准备 fresh complete review-2
