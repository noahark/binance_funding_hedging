# Runner Host And Claude-GLM Tool Policy Repair

## Human Decision

The human operator approved the explicit `software_architect` design from the
preceding decision turn and fixed Kimi as the persistent runner host until an
explicit human instruction changes it. The approved Claude-GLM implementation
surface is exactly `Read`, `Glob`, `Grep`, `Edit`, and `Write`.

This artifact records a Harness prerequisite repair. Codex remains the
bookkeeper/designer and did not implement delivery code for
`T1-launchd-service`.

## Implemented Boundary

- `agents/registry.yaml` now maps Claude-GLM write calls to
  `implementation-v1` and read-only calls to `review-readonly-v1`.
- The PTY wrapper accepts only a frozen policy ID plus a runner-generated
  stage-local settings file. Normal policies use `dontAsk`, safe mode, disabled
  slash commands, and an empty strict MCP configuration.
- `implementation-v1` exposes only `Read,Glob,Grep,Edit,Write`;
  `review-readonly-v1` exposes only `Read,Glob,Grep`; both exclude and
  explicitly deny `Bash`.
- The runner derives bounded `Edit`/`Write` rules from the committed human
  authorization's `scope.allowed_pathspecs`, denies protected Harness/evidence/
  secret paths, and records the policy ID/path in new receipts.
- Historical receipts remain schema-valid without the additive policy fields.
- Frozen blocking checks and optional `mechanical_post_write.executable_paths`
  mode normalization remain deterministic runner operations. Models cannot
  supply or execute test, git, chmod, or next-hop commands.
- `status.json`, the workflow, registry, validator, and docs record Kimi as a
  host-only session. Any Kimi implementation/review route must use a fresh
  isolated session.

## Fail-Closed Checks

Before a call, runner preflight now rejects:

- a missing or drifted Kimi runner-host record;
- a Claude-GLM registry command without the frozen policy ID or
  `<tool-policy-file>` placeholder;
- `acceptEdits` or bypass permission flags on normal Claude-GLM routes;
- executable-mode paths outside the human authorization;
- malformed tool policies, Bash allow rules, unbounded/missing write rules, or
  read-only policies containing `Edit`/`Write`.

The wrapper separately rejects policy files outside the repository, malformed
Claude settings, Bash allow rules, policy/yolo mixing, and actual-model drift
from the registered `glm-5.2` model.

## Verification

```text
targeted policy/receipt/PTY/registry/mechanical/validator suite
Ran 58 tests
OK

test_harness_stage_lib + test_auto_review_runner + test_validate_stage_auto_review
Ran 170 tests
OK

runner receipt/tool-policy schema validation + historical receipt replay
PASS

scripts/validate-stage.py 2026-07-local-service-launchd-v1 --phase checkpoint
STAGE VALIDATION PASSED

git diff --check
PASS
```

No test invoked a model, read `.env`, expanded the provider alias, changed a
delivery file, or mutated a real LaunchAgent domain.

## Resume Boundary

No model was invoked while implementing or testing this repair. Authorization
v4 remains historical attempt-4 authority and cannot be reused. A new committed
human-approved v5 authorization is required before Kimi hosts another runner
attempt.

本地北京时间: 2026-07-13 18:09:22 CST
下一步模型: human
下一步任务: 审阅修复证据并决定是否签发 superseding authorization v5 后由 Kimi runner host 重试
