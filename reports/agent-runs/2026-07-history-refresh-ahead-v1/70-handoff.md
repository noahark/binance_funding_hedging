# Handoff

## Recovery Header

- Active phase: `review_1` (dispatch ready)
- Next action: human executes `review-1-kimi.prompt.md` in a fresh read-only
  Kimi session and returns the complete output
- Read-set: = `status.current_inputs`
- Open blockers: human review-1 dispatch required by Harness
- Do-not-read: `reports/agent-runs/**/history/**`, other stages, retired model
  sessions, prior v2 implementation/review transcripts

## Current State

- Stage: `2026-07-history-refresh-ahead-v1`
- Status: `implementing`
- Branch: `stage/2026-07-history-refresh-ahead-v1`
- Baseline: `12b8e1c1ea5d86bf692bbba2183de08ee9429af4`
- HEAD: `5ca9852296b3ba3259c5f36cc227802572ea347e`
- Git status: exactly three allowed implementation files modified; evidence
  commit pending
- Bookkeeper/designer: Codex / OpenAI; no code authorship
- Implementer: Claude-GLM / `zhipu_glm`, implementation complete
- Review-1: Kimi
- Review-2: Claude provider, planned due Codex design involvement
- Parallel mode: disabled

## Frozen Scope

- History refresh-due: default 1500 seconds.
- History publication expiry: unchanged 1800 seconds.
- Borrow-rate/max-borrowable: unchanged 1800 seconds.
- Threshold re-entry behavior: explicitly deferred.
- Allowed implementation files: `backend/services/snapshot_service.py`,
  `backend/tests/test_background_worker.py`, `20-implementation.md`.

## Blocker

Codex/GPT and Claude provider sessions must not execute model dispatch. The human
must run the prepared prompt in a fresh Claude-GLM implementation terminal and
return the raw result/worktree for bookkeeper verification.

The user explicitly chose to continue without rotating the credential mentioned
in the prior checkpoint. No credential value is stored in repository artifacts.
The shared worktree now contains exactly the three frozen files. Bookkeeper
verification passed: focused 37 tests, full backend 335 tests, py_compile,
diff-check, and an extra failed-early-refresh retention check at 1500/1799/1800.

Reviewed implementation head:
`2cb72fd870b1ef29cc4787e7dff102ab56bf8601`

Authoritative fingerprint:
`2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`

Clean-worktree `pre-review` validator and independent fingerprint recomputation:
PASS after binding commit `6b12335`.

本地北京时间: 2026-07-15 12:15:56 CST
下一步模型: human
下一步任务: 在 fresh Kimi 终端执行 review-1-kimi.prompt.md 并回传完整输出
