# Handoff

## Recovery Header

- Active phase: `implementing` (dispatch prepared, human execution pending)
- Next action: human starts a fresh Claude-GLM terminal with
  `implementation-claude-glm.prompt.md`
- Read-set: = `status.current_inputs`
- Open blockers: human model dispatch required by Harness
- Do-not-read: `reports/agent-runs/**/history/**`, other stages, retired model
  sessions, prior v2 implementation/review transcripts

## Current State

- Stage: `2026-07-history-refresh-ahead-v1`
- Status: `implementing`
- Branch: `stage/2026-07-history-refresh-ahead-v1`
- Baseline: `12b8e1c1ea5d86bf692bbba2183de08ee9429af4`
- Git status: stage intake/design/dispatch artifacts pending commit
- Bookkeeper/designer: Codex / OpenAI; no code authorship
- Implementer: Claude-GLM / `zhipu_glm`, human dispatch pending
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

本地北京时间: 2026-07-15 10:44:33 CST
下一步模型: human
下一步任务: 在 fresh Claude-GLM 终端执行 implementation-claude-glm.prompt.md
