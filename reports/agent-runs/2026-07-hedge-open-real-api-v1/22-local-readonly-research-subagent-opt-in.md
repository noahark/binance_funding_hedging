# Local read-only research-subagent opt-in

## User-approved narrow exception — 2026-07-25

The user approved a Harness refinement because the blanket model-to-model ban
was blocking useful implementation research. Main commit
`9ebf4e1a0f394e8ad22ea219cdcfbe1476cae25e` changes the general Harness rule:
formal implementation/fix/review dispatch remains human-operated, while an
implementation/fix task may explicitly opt in to tightly bounded local
read-only research subagents.

This active stage needs that behavior. The main commit was merged into this
stage as `b02c92d20360094a67374bf80bcd588fb154db6c`; its only changes are
Harness rules/templates, not hedge product source or Binance behavior.

## Current-task opt-in

For the active Claude-GLM execution of packet 62 only, at most two runtime-
built-in, same-provider local research subagents are allowed:

1. one **Plan** helper to assess task-worker lifecycle/concurrency safety; and
2. one **Explore** helper to map the existing scheduling, reconciliation,
   store pause, and directly related test seams.

They are internal research helpers, not formal model dispatches. This document
supersedes only packet 62's blanket no-subagent sentence for the two helpers
above. All other packet 62 restrictions remain binding.

## Non-negotiable boundaries

- They may read only repository files within the active task scope and return
  notes to the parent GLM session.
- They may not write or create files, edit code/tests/docs/status/evidence,
  run write-capable commands, access credentials, connect to Binance or any
  network, invoke an adapter/terminal, start another subagent, perform review,
  produce a verdict, run acceptance, or claim formal evidence.
- The parent Claude-GLM session remains the only implementation author, test
  runner, report author, and accountable task executor. It must directly read
  the source it changes and run/record its own tests.
- The helpers' output is not a raw implementation/review artifact and cannot
  substitute for code diff, tests, implementation report, Review-1, Review-2,
  human dispatch receipt, or provider-isolation evidence.
- No reviewer, bookkeeper, direction-panel, or final-review session may use
  this exception. Formal Review-1/Review-2 remains human-operated in a fresh
  single reviewer session.

## Existing in-flight research disclosure

Before this opt-in was recorded, the human operator reported that the current
GLM task had started a Plan helper and an Explore helper for the exact two
read-only purposes above. Bookkeeper checked the stage worktree at that point:
it was clean at `7e72e6a`; no product/source/evidence file was written by those
helpers. The user has now explicitly approved continuing only under this
document's limits.

## Rebind and safety note

This Harness-only main sync changes the stage-wide committed fingerprint from
the prior `8af3f22:...` delivery anchor to the new merge anchor. It does not
invalidate the factual frontend source review by itself, but all future formal
review routing must use the recomputed committed range after the active backend
fix lands. No live mode, Start, credential access, Binance network request, or
real order is authorized.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/22-local-readonly-research-subagent-opt-in.md
本地北京时间: 2026-07-25 00:07:54 CST
下一步模型: Claude-GLM
下一步任务: complete packet 62 as the sole code/test/report author; local Plan/Explore helpers may remain read-only within this opt-in
