# Phase E Task 3 — Handoff Actor And Review-Route Dedup

## Identity

- task_id: `phase-e-task3-handoff-route-dedup`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `17`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Finish Task 3 with two pre-review wording corrections in `AGENTS.md`:

1. stop Default Delivery Flow from restating the review route owned by §8;
2. make `下一步模型` show the immediate next workflow actor instead of always
   showing Bookkeeper.

This is Human requirement refinement and pre-review correction, not a formal
`REWORK`. Keep `rework_count` at `0`.

## Allowed Files

Modify only:

```text
AGENTS.md
reports/agent-runs/2026-07-harness-v2-phase-e/status.json
```

Preserve every other uncommitted Task 3 modification exactly as found.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. current Phase E `status.json`;
5. the Bookkeeper section of `agents/roles.md`;
6. `agents/developer-discipline.md`;
7. `agents/skills/minimal-change-engineer.md`;
8. `reports/agent-runs/2026-07-harness-v2-phase-e/73-phase-e-task3-bookkeeper-verification.md`.

Do not scan business source, other Harness documents, unrelated stages,
credentials, runtime data, or historical branches.

## Required Changes

### A. Review Route Pointer

In `AGENTS.md` Default Delivery Flow, make the review step only point to §8
Review Rules. Remove the parenthetical copy of the `HIGH_RISK` and `LOW_RISK`
route. §8 remains the sole detailed route authority.

### B. Immediate Next Actor

In `AGENTS.md` Chinese Handoff Labels, keep the visible label `下一步模型` but
define its value by the current workflow transition:

- after an Implementer or Reviewer returns a task result, show the current
  `status.json.bookkeeper` in readable form because Bookkeeper is the immediate
  recipient;
- after Bookkeeper prepares a dispatch, show that active dispatch's
  `target_model` in readable form and state that Human starts it;
- while waiting for a Human decision, show `Human（决策者）`.

`下一步任务` must describe the action of that same immediate actor. Do not use a
later planned reviewer in `下一步模型`; it may appear in `下一步任务` only when it
is part of the concrete follow-on sequence.

These lines remain informational and do not authorize model launch. Do not add
`result_recipient`, a Bookkeeper provider, a session field, or another routing
file.

## Acceptance Checks

Run:

```text
git diff --check
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-e/status.json
rg -n "^5\\. Review routing follows §8 Review Rules\\.$" AGENTS.md
rg -n "Implementer or Reviewer|dispatch.*target_model|Human（决策者）" AGENTS.md
! rg -n "下一步模型.*reads the single model id|keeps the next planned reviewer separate" AGENTS.md
```

Also verify:

- the complete result protocol remains defined only in `AGENTS.md`;
- `status.json.bookkeeper` remains scalar `codex`;
- `rework_count` remains `0`;
- only the two allowed files change for this correction;
- `status.json` changes only this task from `dispatched` to `reported`;
- all prior Task 3 changes remain untouched;
- no commit, push, main update, model launch, service action, credential access,
  or live action occurs.

## Stop

Return one concise result through the Task Result Protocol in `AGENTS.md`.

- Keep the summary under 180 total characters.
- Use no more than four grouped check items.
- The task identifier is `phase-e-task3-handoff-route-dedup`.
- Because this is an Implementer result, `下一步模型` is Codex Bookkeeper via
  Human transfer.
- The next action is for Bookkeeper to preserve the raw result, verify the
  complete Task 3 diff, fix `delivery_sha`, and prepare Grok 4.5 review-1.
