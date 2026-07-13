# Harness Adapter Repair — Absolute Claude-GLM Wrapper

## Human Decision

The operator directed this stage branch to adopt an absolute-path wrapper as
the formal `claude_glm` adapter repair after auto attempt 1 exited `127` before
model execution.

This is a Harness/runtime prerequisite repair, not delivery implementation for
`T1-launchd-service`. The delivery owner remains `claude_glm` / `zhipu_glm`.

## Implemented Repair

- Added executable `scripts/model-adapters/claude-glm-wrapper`.
- Updated `agents/registry.yaml` so every Claude-GLM command begins with
  `<repo>/scripts/model-adapters/claude-glm-wrapper`; the runner expands
  `<repo>` to the absolute repository path before invocation.
- Kept the existing provider/credential routing inside the user's interactive
  zsh profile. The wrapper never prints or records the alias expansion,
  environment, token, or credential.
- Isolated zsh startup and exit-hook stdout/stderr on separate file descriptors,
  restoring the runner-visible streams only for the actual Claude-GLM command.
- Updated `docs/model-adapters.md` and the production-registry runner tests.

The wrapper intentionally does not substitute Anthropic Claude when the
`claude-glm` alias is unavailable. It exits `127` and preserves the
`zhipu_glm` provider identity boundary.

## Verification

```text
/bin/sh -n scripts/model-adapters/claude-glm-wrapper
PASS

scripts/model-adapters/claude-glm-wrapper --version
2.1.207 (Claude Code)
PASS; no zsh startup/exit chatter in captured output

python3 -m unittest scripts.tests.test_auto_review_runner.ProductionRegistryCommandTests
Ran 7 tests
OK

python3 -m unittest scripts.tests.test_auto_review_runner
Ran 79 tests
OK

python3 scripts/validate-stage.py 2026-07-local-service-launchd-v1 --phase checkpoint
STAGE VALIDATION PASSED

git diff --check
PASS
```

No implementation/review model was invoked during this repair verification.
No real `launchctl` command ran and no delivery code changed.

## Resume Boundary

Auto attempt 1 remains terminal evidence and is not rewritten. The runner may
resume only after a committed `auto-run-authorization-v2.json` supersedes v1,
the status transitions from `awaiting_human` to `authorized`, and full preflight
runs again.

本地北京时间: 2026-07-13 14:12:23 CST
下一步模型: Codex bookkeeper
下一步任务: 提交 adapter repair checkpoint，然后创建并提交 superseding authorization v2
