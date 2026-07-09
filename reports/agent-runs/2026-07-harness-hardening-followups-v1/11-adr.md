# ADR: Harness Hardening Follow-ups

## Status

Accepted for implementation.

## Context

Review-2 for `2026-07-harness-friction-fixes-v1` accepted the stage but left 5
P2 hardening findings. The user explicitly requested merging that stage to
`main`, then opening a narrow Harness-only follow-up stage to fix those items.

## Decisions

1. Use a new stage branch rather than patching the already accepted stage range.
   This keeps review fingerprints honest and avoids silently changing accepted
   delivery behavior after review-2.
2. Classify this stage as `LOW` because all work is directly enumerated by
   accepted review findings, has no product semantics, and has a narrow file
   boundary.
3. Skip direction panel and development breakdown. The final review findings
   and this design document provide the bounded implementation contract.
4. Keep GLM as implementation owner for Harness script/template changes.
   Codex/GPT remains bookkeeper/designer and does not implement delivery code.
5. Keep the committed-state fingerprint protocol unchanged.

## Consequences

- The implementation should be small and reviewable.
- Any change beyond the 5 accepted criteria is out of scope.
- If the implementer discovers a larger workflow redesign is needed, this stage
  should stop and record a blocker rather than expanding scope.

本地北京时间: 2026-07-09 21:10:45 CST
下一步模型: claude_glm
下一步任务: implement within the accepted decisions
