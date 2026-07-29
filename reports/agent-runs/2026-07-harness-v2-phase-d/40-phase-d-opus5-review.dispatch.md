# Phase D Rehearsal — Opus 5 Review-2

## Identity

- task_id: `phase-d-review-2-opus5`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `4`
- required_skill: `agents/skills/reality-checker.md`

Human selected Opus 5 for the final review to conserve Fable5's separate paid
quota. The implementation provider was `zhipu_glm`; review-1 used `xai`.
Opus 5 has no implementation or fix authorship in this delivery.

## Goal

Perform the final read-only reality check for the Phase D Harness v2 rehearsal.
Review the fixed delivery range:

```text
base_sha: d69810a59c3da348e01ce84a46e411c6b7ed51ca
delivery_sha: 669491ff62e3636232ff5fa7ab4487cd8b767b77
```

Decide whether the low-risk delivery and the surrounding v2 flow are
acceptable: new-session recovery, progressive disclosure, provider isolation,
fixed review anchors, context budget, cold archive access, raw-result transfer,
and absence of unauthorized repository or live actions.

Two real rehearsal findings require explicit judgment:

1. GLM reported about 6.35KB startup and 18.25KB loaded-task context. Exact
   committed byte counts at its start were 11,678 bytes and a conservative
   21,641 bytes respectively. No context compaction occurred and both remain
   well below the approximate 8K/15K token budgets.
2. Both model outputs contained usable `TASK_RESULT v2`, but neither made
   `[/TASK_RESULT]` the final non-whitespace output. GLM added one sentence;
   Grok appended the retired v1 Session ID/next-model footer. Judge whether the
   minimum remedy is one explicit global output rule, whether a thin mechanical
   check is justified by this rehearsal, or whether no Harness change is
   needed.

The vendored web-QA commands in `reality-checker.md` do not apply to this
documentation-only Harness task. Do not run them.

## Allowed Files

Repository writes: none. This is a fresh read-only final review. Do not modify
files, status, Git refs, the worktree, services, runtime state, or credentials.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. `reports/agent-runs/2026-07-harness-v2-phase-d/status.json`;
6. the `Reviewer` section of `agents/roles.md`;
7. only the Project Harness Overrides at the top of
   `agents/skills/reality-checker.md`;
8. `agents/skills/UPSTREAM.md`;
9. `reports/agent-runs/2026-07-harness-v2-phase-d/10-upstream-cleanup-glm.dispatch.md`;
10. `reports/agent-runs/2026-07-harness-v2-phase-d/20-upstream-cleanup-glm-result.md`;
11. `reports/agent-runs/2026-07-harness-v2-phase-d/30-upstream-cleanup-grok45-review.dispatch.md`;
12. `reports/agent-runs/2026-07-harness-v2-phase-d/31-upstream-cleanup-grok45-review-result.md`;
13. the exact committed diff
    `d69810a59c3da348e01ce84a46e411c6b7ed51ca..669491ff62e3636232ff5fa7ab4487cd8b767b77`;
14. the exact cold archive ref
    `archive/2026-07-harness-v2-phase-c` only to verify that Phase C evidence is
    recoverable while its directory is absent from the normal worktree.

Do not scan unrelated completed stages, workflow YAML, registry, schemas,
business source, or moving `HEAD`.

## Acceptance Checks

- Recheck the fixed delivery and Grok review-1 `ACCEPT`.
- Confirm GLM (`zhipu_glm`), Grok 4.5 (`xai`), and Opus 5 (`anthropic`) are
  provider-isolated for their roles.
- Confirm the new GLM session recovered using only the dispatch-named v2 path,
  read no old workflow/registry/schema, and experienced no compaction.
- Confirm the corrected byte counts remain below the approximate token budgets;
  distinguish a reporting error from a budget failure.
- Confirm Phase C evidence is readable from the exact archive ref and absent
  from the normal worktree.
- Confirm no business code, main, push, deployment, service, credential, or
  live state was changed.
- Classify the trailing-output/legacy-footer issue as blocking or non-blocking
  and state the smallest evidence-based remedy.
- Decide whether current evidence justifies a Hook. Do not recommend one merely
  for hypothetical protection.
- Return `verdict: ACCEPT | REWORK`.
- Use
  `findings_path: reports/agent-runs/2026-07-harness-v2-phase-d/41-phase-d-opus5-review-result.md`.
- On `ACCEPT`, use `fix_requirements_path: none`.
- On `REWORK`, include concrete repair requirements in the result and use the
  same result path as `fix_requirements_path`.

## Stop

Return one complete `[TASK_RESULT v2]` block and stop. The closing
`[/TASK_RESULT]` line must be the final non-whitespace output. Do not append
prose, a Session ID footer, next-model instructions, Markdown fences, or any
other text. Do not start another model.
