# ADR: Use Single-Owner Recorder Trial For Harness Manifest Sync

## Status

Accepted for this stage.

## Context

The independent task-branch mode has been enabled in the repository and its
dry-run fixture passes. The next low-risk test is a Harness-only single-owner
stage with a narrow metadata change.

## Decision

Use Claude-GLM as implementer and single-owner recorder for a one-file manifest
sync change. Use Kimi as cross-provider review-1. Codex remains the independent
bookkeeper/design session and will return for review-2.

## Consequences

- This stage exercises the single-owner `record-checkpoint` path on a real
  branch.
- Because the current script does not write top-level status in single-owner
  mode, GLM must explicitly record the checkpoint metadata in `status.json`
  after the recorder commit.
- If review-1 is not `ACCEPT`, the stage stops for human escalation or a scoped
  fix; it does not proceed to review-2.

## Alternatives Considered

- Standard serial stage without `record-checkpoint`: lower process value and
  does not test the new path.
- Double-owner task-branch mode: unnecessary for one manifest file and higher
  overhead.
- Modify recorder scripts first: out of scope because the requested stage is
  meant to test current single-owner behavior without changing protected
  Harness scripts.

本地北京时间: 2026-07-09 09:32:23 CST
下一步模型: claude_glm
下一步任务: implement manifest sync and run single-owner recorder
