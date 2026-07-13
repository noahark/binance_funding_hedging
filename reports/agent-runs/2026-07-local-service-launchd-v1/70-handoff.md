# Handoff — 2026-07-local-service-launchd-v1

## Recovery Header

- Active phase: interrupted attempt evidence and explicit human mode flip committed; manual Claude-GLM implementation packet ready
- Next action: human executes the fresh foreground Claude-GLM dispatch packet, then returns control to Codex for tests
- Read-set: = status.current_inputs
- Open blockers: none before human model dispatch; delivery implementation itself is pending
- Do-not-read: reports/agent-runs/**/history/** unless auditing the named repair snapshots

## Current State

- Stage: `2026-07-local-service-launchd-v1`
- Status: `implementing`
- Branch: `stage/2026-07-local-service-launchd-v1`
- HEAD: `ca88a74bb96cc27ea051b18fb8ebf0d02f6fddbb` (`bookkeeper(launchd): switch interrupted pilot to manual dispatch`) before this synchronized post-commit checkpoint
- Git status: clean immediately after the manual-mode-flip checkpoint; synchronized post-commit checkpoint pending commit
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
- PTY route repair: `16-claude-glm-pty-route-repair.md`
- PTY probe result: `17-claude-glm-pty-probe-result.md`
- Kimi host/tool policy repair: `18-runner-host-tool-policy-repair.md`
- Tool-policy repair commit: `bfbc2ee394bcf40f422f8a826e4acfb99648642e`
- Latest runner receipt: `runner-4-implementation.receipt.json`
- Latest raw output: `runner-4-implementation-T1-launchd-service-attempt1.raw-output.md`
- Latest escalation: `80-escalation-recoverable_resume_unverifiable_unit-20260713T104052Z.md`
- Historical repair snapshots: the four exact named files under `history/` referenced by `status.json`
- Review 1: pending fresh Kimi manual cross-review after implementation/tests
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

- The human operator must execute `manual-implementation-T1-launchd-service.dispatch.md`. Until the model returns, delivery implementation and frozen tests remain pending.

## Next Action

The checkpoint is committed and the worktree is clean. The human executes `manual-implementation-T1-launchd-service.dispatch.md` once in a fresh foreground terminal. On return, Codex inspects the bounded diff, runs all frozen checks, records the implementation evidence commit, and prepares fresh Kimi manual review-1.

本地北京时间: 2026-07-13 18:59:18 CST
下一步模型: Claude-GLM / GLM-5.2（human dispatch）
下一步任务: 执行 manual-implementation-T1-launchd-service.dispatch.md 并返回 exit code/session id
