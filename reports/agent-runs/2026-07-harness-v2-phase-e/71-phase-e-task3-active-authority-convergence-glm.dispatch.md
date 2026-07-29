# Phase E Task 3 — Active Authority Convergence

## Identity

- task_id: `phase-e-task3-active-authority-convergence`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `16`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Resolve the remaining active Harness authority conflicts found after Task 2.
Consolidate only definitions that can currently make models take different
actions. Do not perform a broad wording cleanup.

The finished state must have:

1. one active detailed model-routing authority;
2. one current v2 branch/SHA/merge policy;
3. one exact dispatch-packet shape;
4. one minimal `current_task.state` vocabulary;
5. an explicit relationship between the generic skill limit and the stricter
   Implementer rule;
6. clearly separate Human-authorization sensitivity and review-topology risk;
7. one Harness-change-only single-authority principle.

Do not add a validator, schema, YAML workflow, Hook, registry, compatibility
layer, or new permanent authority document.

## Allowed Files

Modify only:

```text
AGENTS.md
agents/roles.md
agents/skills/complexity-evaluator.md
docs/development/DEVELOPMENT_GUIDE.md
docs/planning/DECISIONS.md
docs/planning/stage-branch-mode.md
reports/agent-runs/2026-07-harness-v2-phase-e/status.json
```

In `status.json`, change only this task from `dispatched` to `reported` after
all checks pass.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. current Phase E `status.json`;
6. `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. `agents/skills/complexity-evaluator.md`;
10. `docs/development/DEVELOPMENT_GUIDE.md`;
11. `docs/planning/DECISIONS.md`;
12. `docs/planning/stage-branch-mode.md`;
13. `reports/agent-runs/2026-07-harness-v2-phase-e/69-opus5-authority-duplication-audit.md`;
14. `reports/agent-runs/2026-07-harness-v2-phase-e/70-phase-e-task3-human-authorization.md`.

Do not scan business source, runtime data, credentials, unrelated stages,
repository-external files, or historical branches.

## Required Changes

### A. Harness Single Authority

Add one compact rule to `AGENTS.md` Harness Design Principle:

- During a Harness change, each rule, field shape, state vocabulary, routing
  mapping, or numeric limit has one detailed active authority.
- Other active files may point to it or give a scoped one-line reminder, but
  must not copy a field list, enum set, numeric limit, or full workflow.
- When a Harness modification encounters another independently executable
  definition, consolidate it within the authorized scope or report it.
- This requirement applies when modifying Harness contracts, not to ordinary
  product tasks.

Do not create a recurring audit step or another document for this rule.

### B. Model Routing

`agents/roles.md` remains the sole active detailed routing and provider
authority.

- In `AGENTS.md`, remove concrete default model assignments from Role Routing
  and Default Delivery Flow. Point to `agents/roles.md` without restating model
  names.
- In `docs/development/DEVELOPMENT_GUIDE.md`, replace the detailed `Model
  Routing` section with a short pointer to `agents/roles.md`. Do not preserve a
  second active route table or model-specific exception there.
- In `docs/planning/DECISIONS.md`, preserve decision history but add one clear
  notice before the log: historical Harness routing/workflow decisions are not
  active runtime authority after Harness v2; current behavior comes only from
  `AGENTS.md`, `agents/roles.md`, active `status.json`, and the active dispatch.
  Do not rewrite historical decision rows.
- Keep the current routing in `agents/roles.md`: GLM backend, Kimi frontend,
  Kimi preferred review-1 for GLM, Human-approved Grok 4.5 fallback, Opus 5
  default review-2, and Fable5 only by explicit Human choice.

### C. V2 Branch, SHA, And Merge Policy

The active v2 rule lives in `AGENTS.md`:

- Harness v2 does not require automatic `stage/<stage-id>` branch creation or
  a mandatory branch name.
- Human selects the branch/worktree for the bounded work.
- Formal review remains anchored only to committed
  `base_sha..delivery_sha`.
- Merge to `main` remains forbidden without explicit Human authorization.

Mark `docs/planning/stage-branch-mode.md` prominently at the top as
`SUPERSEDED BY HARNESS V2 — HISTORICAL EVIDENCE ONLY`. State that its
`head_sha`, fingerprint, validator, YAML, `70-handoff`, automatic stage-branch,
and merge mechanics are not active instructions. Preserve the historical body
unchanged.

The notice in `docs/planning/DECISIONS.md` must also make
`DEC-2026-07-05-001` historical rather than current operational authority.

### D. Dispatch Packet Shape

The Bookkeeper section of `agents/roles.md` remains the only exact packet
shape:

```text
Identity: task_id, target_role, target_model, provider, status_revision,
          required_skill (zero or one)
Goal
Allowed Files
Inputs
Acceptance Checks
Stop
```

- In `AGENTS.md`, describe the dispatch only by responsibility and point to the
  Bookkeeper section for the exact shape. Do not enumerate a partial field set.
- In `agents/roles.md` Shared Rules, point to the exact Bookkeeper shape instead
  of listing a shorter subset.
- Keep startup mismatch checks in `AGENTS.md`; those are safety behavior, not a
  second packet schema.

### E. Skill Cardinality

Define the relationship only in `agents/roles.md`:

- Generic dispatch: zero or one `required_skill`.
- Implementer dispatch: exactly one, selected from its implementation or
  bounded-repair skill.
- Planner and Reviewer may use zero or one as their role section requires.

Make clear that the Implementer rule is a stricter role-specific specialization
of the generic limit, not a conflict. `AGENTS.md` may retain only the generic
startup instruction to load at most one dispatch-named skill.

### F. Current Task State

Define the full active vocabulary once in the Bookkeeper section of
`agents/roles.md`:

- `dispatched`: the active packet is ready or executing;
- `reported`: the implementer recorded that its raw result has returned;
- `verified`: Bookkeeper independently verified the raw result and evidence.

Do not keep `running` as a fourth state; v2 does not need a separate running
write. An implementer may move only `dispatched` to `reported`. Bookkeeper may
move `dispatched` or `reported` to `verified` after raw evidence arrives.
Unknown values are non-advancing and require Human clarification.

Update the short writer-boundary sentence in `AGENTS.md` and Implementer
behavior in `agents/roles.md` to match, without copying the full state
definitions outside the Bookkeeper section.

### G. Two Different Risk Concepts

Keep two deliberately different authorities in `AGENTS.md`:

1. Safety Kernel: actions requiring explicit Human authorization.
2. Review Rules: task changes requiring review-1 plus review-2.

Label them so no model treats the lists as the same classification. The Review
Rules section alone defines `LOW_RISK` and `HIGH_RISK` review routing. Include
Harness safety/workflow contract changes and an unclear acceptance oracle in
`HIGH_RISK`.

Remove the duplicate domain list and routing rules from
`agents/skills/complexity-evaluator.md`. The skill becomes an optional analysis
aid that applies the two authoritative `AGENTS.md` sections and reports a
recommendation; it must not own another classification list or review route.

In Default Delivery Flow, point to Review Rules instead of repeating the
low/high review route.

## Acceptance Checks

Run:

```text
git diff --check
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-e/status.json
rg -n "single detailed active authority|ordinary product tasks" AGENTS.md
rg -n "SUPERSEDED BY HARNESS V2|HISTORICAL EVIDENCE ONLY" docs/planning/stage-branch-mode.md
rg -n "historical Harness routing/workflow decisions|not active runtime authority" docs/planning/DECISIONS.md
rg -n "dispatched|reported|verified|Unknown" agents/roles.md
! rg -n "\\brunning\\b" AGENTS.md agents/roles.md
! rg -n "Claude-GLM owns|Kimi owns|Grok is excluded|Fable5.*Opus4\\.8" AGENTS.md docs/development/DEVELOPMENT_GUIDE.md
! rg -n "LOW_RISK.*documentation|HIGH_RISK.*orders|require review-1 and review-2" agents/skills/complexity-evaluator.md
```

Also verify:

- detailed model routing appears only in `agents/roles.md`;
- the exact dispatch shape appears only once, in the Bookkeeper section;
- Shared Rules and `AGENTS.md` point to it without partial enumeration;
- `current_task.state` has exactly the three defined values;
- Human authorization and review topology are visibly separate concepts;
- historical decision rows and the historical stage-branch body are preserved;
- no consistent reminder outside these conflicts is broadly rewritten;
- no business source, runtime data, credentials, service, `main`, remote, or
  live state changes;
- only the seven allowed files change;
- no commit, push, merge, model launch, or cross-model dispatch occurs.

## Stop

Return one concise result through the Task Result Protocol in `AGENTS.md`.

- The result summary must be under 220 total characters.
- Use no more than six grouped check items.
- The task identifier is `phase-e-task3-active-authority-convergence`.
- The next model is Codex Bookkeeper via Human transfer.
- The next action is for Bookkeeper to preserve the raw result, verify the
  fixed Task 3 diff, and prepare Grok 4.5 review-1 only after verification.
