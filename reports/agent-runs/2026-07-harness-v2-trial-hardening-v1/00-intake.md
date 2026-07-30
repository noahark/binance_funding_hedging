# Harness v2 Trial Hardening — Intake

## Human Decision

On `2026-07-30`, Human authorized a dedicated stage for the Harness problems
observed during the first live v2 product stage and required Opus 5 to
participate in solution design before any Harness modification begins.

## Isolation

- stage_id: `2026-07-harness-v2-trial-hardening-v1`
- branch: `codex/harness-v2-trial-hardening`
- worktree: `/Users/ark/Desktop/ai code/funding_hedging-harness-v2`
- base: `main@6471873815591b661ddfe9c3456ad6a7412ac653`
- Bookkeeper: `codex`
- first Planner: `opus-5` / `anthropic`
- review topology: `HIGH_RISK` because this stage changes Harness contracts

The product stage `2026-07-unknown-not-zero-v1` remains active in the separate
`/Users/ark/Desktop/ai code/funding_hedging` worktree. This Harness stage must
not modify, commit to, switch, merge, or synchronize that worktree or its stage
branch.

## Design-Only Gate

Until the product stage is accepted and merged:

- Opus 5 may produce only the bounded design artifact named by its dispatch.
- No active Harness authority, script, skill, product file, or canonical
  planning file may be modified.
- No implementation or fix task may be prepared or started.
- Before implementation, Bookkeeper must integrate the then-current `main`,
  reconcile any later trial findings, and send the design through an
  independent plan review.

## Evidence Snapshot

The current nineteen findings and six preserve rules are fixed at:

```text
git show be789d6:docs/planning/harness-v2-trial-findings-2026-07-30.md
```

This is a snapshot from the still-running product stage, not an instruction to
scan or modify that stage. Later findings are considered only at the explicit
pre-implementation reconciliation gate.

## Design Constraints

1. Preserve Harness v2 minimalism, progressive disclosure, and W1-W6.
2. Do not restore v1 workflow YAML, registry, verdict schema, adapter runbook,
   monolithic validator, session footer, or automatic stage machinery.
3. Keep each rule in its existing detailed authority. Executable enforcement
   may be a new file only when no existing authority can perform that unique
   executable duty.
4. Prefer two reviewable delivery batches: gate/mechanism gaps first, hygiene
   second.
5. Keep completed-stage bulk cleanup (`G11`) separate because it is destructive
   and already has a `PROJECT_STATE.md` owner.
6. Design must distinguish a real problem from a candidate fix; it may reject
   or reframe any proposed fix with evidence.

## Non-Goals

- No Harness implementation in this design task.
- No product code, runtime, service, credential, data, live, push, or main
  action.
- No attempt to finish or bookkeep the active product stage.
