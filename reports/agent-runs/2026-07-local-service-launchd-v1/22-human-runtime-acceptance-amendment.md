# Human Runtime Acceptance Amendment — Desktop Checkout

## Human Decision

The human operator made the following explicit decision on 2026-07-13:

- the repository stays at its current path under `~/Desktop`;
- no repository move, runtime copy, or broad macOS privacy grant will be added
  in this stage;
- routine local startup and visible acceptance on this machine will be performed
  by the human through the existing Bash launcher, `scripts/run-server.sh`;
- inter-model exchange through transcript Session IDs is deferred to another
  stage and does not change this stage's Harness.

## Effect On The Review-2 P1

The real exit-126 evidence remains true: a background LaunchAgent cannot access
this TCC-protected checkout. The human accepts that environment limitation and
does not require real launchd acceptance from the current Desktop path before
this stage can complete.

This is a runtime acceptance decision, not a claim that the failed launchd test
passed. The launchd controller remains a delivered macOS utility for an
eligible, non-TCC-protected checkout. The current machine's supported operating
path is the human-started Bash launcher. No code may silently relocate the
repository or request broader filesystem authority.

## Remaining Required Repair

The Opus review-2 P2 remains mandatory because it is an isolated correctness
problem in shipped controller behavior: `install` and `restart` must not report
success merely because `launchctl bootstrap` returned zero. They must perform a
bounded post-bootstrap readiness check and return nonzero with a fixed,
redacted diagnostic when readiness is not reached.

This repair is limited to:

```text
scripts/service-control.py
scripts/tests/test_service_control.py
```

The repair must not change repository location behavior, `scripts/run-server.sh`,
backend/frontend code, plist paths, `.env` handling, or the known real launchd
evidence.

## Completion Route

1. Human dispatches the bounded P2 repair to the existing eligible
   `claude_glm` / `zhipu_glm` fix provider.
2. Codex bookkeeper runs the frozen deterministic test set and commits the
   bounded repair evidence.
3. The human performs Bash startup/visible acceptance when requested; models do
   not start the local service in place of the human.
4. A fresh, complete review-2 inspects the amended requirements, new committed
   range, raw evidence, tests, and source files.
5. Push and merge remain forbidden until that new review-2 returns schema-valid
   `ACCEPT`; explicit user merge authority is already recorded but is
   conditional on the hard review gate.

本地北京时间: 2026-07-13 22:21:30 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched fix author）
下一步任务: 仅修复 install/restart 的有界 post-bootstrap readiness 校验
