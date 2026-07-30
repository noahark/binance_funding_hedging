# v2 Gap — No Plan Or Design Review Step

Recorded 2026-07-30 by Bookkeeper, prompted by Human asking where a pre-implementation
Codex review fits in v2.

## The finding

v2 has no plan/design review gate. `AGENTS.md` §6 Default Delivery Flow goes
straight from step 1 (Human + Planner decide the goal) to step 3 (the dispatched
implementer implements). §8 Review Rules classifies **task changes** and routes
review-1/review-2 at the delivery boundary only; nothing reviews the plan that
produced the task. `agents/roles.md` Planner has a Stop Point but no reviewer
downstream of it.

So the artifact with the highest leverage over cost — the plan that decides what
the implementer will and will not touch — is the only artifact in the flow that
nothing independent reads before money is spent on implementation and two
reviews.

## Why this is not theoretical

The previous stage is the case study. `2026-07-hedge-order-truth-v1` produced its
design 45 seconds before the packet revision carrying T4's root cause, so the
design shipped with a factual error (`51169` mapped to `insufficient_funds`,
which would have printed 保证金不足 to the operator for a condition that has
nothing to do with margin). It was caught by the bookkeeper reading the design
against the intake evidence, not by any defined step — pure luck of sequencing.
It was recorded in that stage's `status.json` as `design_staleness`.

v1 at least had design-review stages by convention (`2026-07-auto-review-pipeline-design-review`,
`2026-07-harness-v2-rebuild-design`). v2 dropped the convention without
replacing it.

## Options, for a future Harness edit

1. **Do nothing; keep it ad hoc.** Human asks for a plan read when it feels
   warranted, as happened here. Cost: it depends on Human noticing, and the
   result gates nothing.
2. **Add a conditional gate to §8.** For `HIGH_RISK` work only, the plan gets one
   independent read before the implementation dispatch. Cheapest defensible
   version: reuse the Reviewer role, no new file, one sentence in §8, and the
   verdict routes back to the Planner rather than to `rework_count`.
3. **Fold it into the Planner Stop Point.** `roles.md` Planner must hand its plan
   to one independent model before Bookkeeper prepares the implementation packet.

Recommendation: option 2, because it is one sentence in the authority that
already owns review routing (§8), it fires only where the cost is justified, and
it does not create a second routing authority — which AGENTS.md §2 forbids.

Not actioned in this stage. `task2-same-family-rework-rule` is already a §8 edit,
so this is the natural companion, but folding it in now would widen a scope Human
has not approved. Filed for Human's decision at task 2 dispatch time.
