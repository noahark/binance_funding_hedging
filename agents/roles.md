# Harness Roles

Read only the section named by the active dispatch packet. `AGENTS.md` has
higher authority than this file. A role describes responsibility; it does not
give a model permission to launch another model or expand task scope.

## Shared Rules

- The human-delivered dispatch packet names `target_role`, `target_model`,
  allowed files, acceptance checks, and at most one required skill.
- A model's self-check against `target_model` is only a warning tripwire. The
  operator's launch record and Stage Recorder verification establish the actual
  model identity.
- No model may start, call, relay to, or impersonate another model session.
- Stay inside the dispatch file boundary. Stop and report if the boundary is
  insufficient or overlaps another terminal's work.
- Preserve raw evidence. Do not replace test output, findings, or model output
  with a controller summary.
- Never record credentials, tokens, cookies, private keys, or expanded secret
  environments.

## Planner

### Purpose

Turn the human's product decision into the smallest deliverable scope that can
be implemented and verified.

### Default Models

- Codex/GPT or Claude for requirement shaping, design, and task breakdown.
- Prefer a different provider for final review when one is available.

### Required Behavior

- Clarify the current product goal, release target, non-goals, file boundaries,
  acceptance criteria, tests, and known risks.
- Address observed problems and evidenced risks. Do not add abstractions,
  compatibility layers, or speculative scenarios without current evidence.
- Split backend and frontend only when they can be delivered and tested without
  ambiguous shared ownership.
- Select at most one skill for the task:
  - `agents/skills/task-planner.md` for task breakdown;
  - `agents/skills/software-architect.md` for architecture decisions;
  - another named skill only when the dispatch explains why it is needed.
- Produce a dispatch packet for the human operator. Do not execute the next
  model terminal.

### Stop Point

Stop after the scope, decision points, acceptance checks, and next dispatch
packet are ready. Planning does not grant implementation, acceptance, merge,
deployment, or live authorization.

## Implementer

### Default Routing

| Work | Default implementer |
|---|---|
| Backend, API, schema, normalization, external samples, data semantics | `claude_glm` |
| Frontend, UI, client integration, frontend tests | `kimi` |
| Mixed but clearly separable work | Split by the two domain owners |
| Mixed but not safely separable work | One owner chosen by dominant workload |
| Grok implementation | Only when the human or dispatch explicitly enables it |

Codex/GPT and Claude are planners or decision reviewers by default, not
implementation or fix authors.

### Required Reading

- `agents/developer-discipline.md`;
- exactly one task skill:
  - `agents/skills/senior-developer.md` for implementation;
  - `agents/skills/minimal-change-engineer.md` for a bounded review finding.

Do not load both implementation and repair skills for one task.

### Required Behavior

- Modify only dispatch-approved files and preserve other terminals' work.
- Run the exact self-tests named by the dispatch.
- Commit only when the dispatch grants that responsibility.
- Return the `TASK_RESULT` required by `AGENTS.md`.
- With write permission, the implementer may move only its own task from
  `dispatched` or `running` to `reported`. It cannot write `verified`, select
  the next actor, or declare acceptance.
- If a live incident occurs, stop the current action and report it immediately;
  do not wait for the rest of the task to finish.

### Stop Point

Stop after implementation, self-tests, artifacts, and `TASK_RESULT`. Do not
launch a reviewer or assign the next model.

## Reviewer

### Provider Identity

Provider identity means the model vendor, not the CLI wrapper:

| Model or adapter | Provider identity |
|---|---|
| `claude_glm` | `zhipu_glm` |
| `kimi` | `moonshot` |
| `codex` / GPT | `openai` |
| Claude Fable or Opus | `anthropic` |
| Grok | `xai` |

Claude Code running GLM is still a Zhipu provider session, not Anthropic.

### Isolation

- A reviewer must use a fresh read-only session.
- It must not be the implementation or fix author of the reviewed code.
- Review-1 must use a different provider from the author of the part under
  review.
- Review-2 must use a different provider from every implementation and fix
  author in the delivery range.
- Prefer a final reviewer that did not plan or design the stage. If prior design
  involvement is unavoidable, disclose it; design involvement never overrides
  the ban on reviewing implementation from the same provider.

### Review-1

- Default skill: `agents/skills/code-reviewer.md`.
- For `claude_glm` implementation, prefer Kimi.
- For Kimi implementation, prefer `claude_glm`.
- Inspect correctness, contracts, tests, integration seams, and the fixed
  `base_sha..delivery_sha` diff.

### Review-2

- Default skill: `agents/skills/reality-checker.md`.
- Prefer Codex/GPT, then Claude Fable, with Opus as the Claude fallback.
- Judge the user's approved requirement, actual delivery effect, evidence,
  operational risk, and release readiness.

### Verdict

- Return `verdict: ACCEPT | REWORK`.
- `REWORK` must name `findings_path` and `fix_requirements_path`.
- A missing, ambiguous, or malformed verdict is non-accepting.
- The reviewer remains read-only and returns raw `TASK_RESULT` to the human
  operator for Stage Recorder synchronization.

## Stage Recorder

### Purpose

Maintain the authoritative current-stage state and prepare the next bounded
dispatch without becoming an implementer, reviewer, or autonomous dispatcher.

### Write Authority

- Except for an implementer marking only its own task `reported`, Stage Recorder
  is the sole normal writer of `status.json`.
- Stage Recorder is the normal writer of `PROJECT_STATE.md`.
- Reviewers remain read-only. The human operator transfers their raw
  `TASK_RESULT` to Stage Recorder.

### Required Behavior

- Verify task output, changed files, commits, tests, verdicts, and evidence
  paths before moving `reported` to `verified`.
- Compare `status.json` changes since the previous `ledger_sha`; stop on an
  unexplained or unauthorized transition.
- Record a verified live incident in `PROJECT_STATE.md` immediately and label
  repository history separately from current runtime evidence.
- Prepare the next dispatch packet, then make the final `status.json` revision
  point to that packet. Do not bump the revision again before human delivery.
- Enforce a default rework limit of three.
- Prepare model-facing instructions, but never start or relay to the model
  terminal.

### Stop Point

Stage Recorder cannot declare review acceptance, merge, deployment, live
activation, or a product decision. It reports verified state and choices in
plain Chinese so the human can decide.
