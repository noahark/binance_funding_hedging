# User Authorization — Retain Review-1 ACCEPT Across the Bounded Fix Fingerprint

## Verbatim User Direction

> 这流程感觉有点太长了， 为了尾部 10% 的小问题，要再加 50% 的时间。能不能精简一下直接做 review2 就行

## Exact Authorized Scope

The user authorizes the Harness RC4 class-1 shortcut after the bounded
Review-2 findings and their mechanical test residual are closed:

- retain the existing schema-valid Kimi Review-1 round-2 `ACCEPT`;
- allow that Review-1 artifact's fingerprint to trail the next committed
  Boundary C fix fingerprint through
  `review_fingerprint_trails_status@review_1`;
- proceed directly to a fresh, correctly executed Review-2 after all tests,
  clean-worktree, committed fingerprint, reviewer identity and exception
  integrity gates pass.

This authorization does **not** waive Review-1's `ACCEPT` verdict, Review-2,
test failures, dirty worktree, fingerprint recomputation, provider isolation,
exception structure/integrity, or human verification of the validator's
PASS-with-exception banner. It does not authorize merge, deployment,
credential access, a real Binance request, global Start, live borrowing, or
stage acceptance.

The final `status.authorized_exceptions[]` record is intentionally deferred
until Fix-8 is complete and the new committed diff fingerprint exists. At that
point the record must be pinned to that exact fingerprint and sealed with the
SHA-256 of this committed evidence blob; it auto-expires on any later diff.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/review-1-fingerprint-exception-authorization.md
本地北京时间: 2026-07-21 22:55:21 CST
下一步模型: human operator → Claude-GLM / zhipu_glm / glm-5.2[1m]
下一步任务: execute Micro Fix-8; bookkeeper then commits and pins the RC4 exception to the resulting fingerprint before direct Review-2
