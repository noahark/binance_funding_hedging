# Handoff

## Recovery Header

- Active phase: `implementation_dispatch_ready`
- Next action: human executes the frozen Claude-GLM command in a fresh terminal
- Read-set: = status.current_inputs
- Open blockers: none
- Do-not-read: `reports/agent-runs/**/history/**`, other stages, v1 runner Sessions, prior Claude memory

## Current State

- Stage: `2026-07-cache-refresh-scheduler-v2`
- Status: `implementing`
- Branch: `stage/2026-07-cache-refresh-scheduler-v2`
- Branch base: `main@8aac137`
- Dispatch packet commit: `201b3bb`; a subsequent status-only commit binds the implementation task base
- Git status: clean before final handoff/base binding; no delivery-code changes
- Bookkeeper: OpenAI Codex / GPT-5; not implementer or fix author
- Implementer: fresh human-started `claude_glm` / `glm-5.2`
- Parallel mode: disabled
- Dispatch mode: manual human execution

## Artifact Index

- Intake: `00-intake.md`
- Task: `00-task.md` (migrated approved v1 content)
- Direction synthesis: skipped lightweight route in `06-direction-synthesis.md`
- Design: `10-design.md` (migrated approved v1 content)
- ADR: `11-adr.md` (migrated approved v1 content)
- Breakdown: `12-development-breakdown.md` plus v2 process override in `13-manual-delivery-amendment.md`
- Implementation prompt: `implementation-claude-glm.prompt.md`
- Implementation report: `20-implementation.md`
- Review 1: not started; planned fresh read-only Kimi
- Fix report: not started
- Review 2: not started
- Test output: `60-test-output.txt`
- Status JSON: `status.json`

## Frozen Product Decisions

- Slow private TTL: 1800 seconds, effective scheduled value `<=1800`.
- Scheduled source fetch and cache-only assembly stay separate.
- Borrow work is homepage-only with strict rate threshold and no global top-50.
- Low-rate rows outside the homepage threshold do not receive scheduled borrow checks.

## Blockers

- None.
- Stop for human scope approval if a file outside the frozen write boundary is required.

## Next Action

The human starts Claude-GLM with `implementation-claude-glm.prompt.md`. The
implementer writes code/tests and `20-implementation.md` only, runs the frozen
tests, and returns control without committing or dispatching review.

本地北京时间: 2026-07-14 22:51:18 CST
下一步模型: human → claude_glm
下一步任务: 在全新 Claude-GLM 终端执行冻结实现提示
