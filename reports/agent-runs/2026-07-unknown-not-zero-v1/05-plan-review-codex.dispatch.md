# Dispatch — task0-plan-review

```text
Identity:
  task_id:         task0-plan-review
  target_role:     Reviewer
  target_model:    codex (GPT-5 class)
  provider:        openai
  status_revision: 3
  required_skill:  none
```

Standing on: `roles.md` Shared Rules allow a generic dispatch to name zero
skills. Neither reviewer skill fits — `code-reviewer.md` reviews code and
`reality-checker.md` reviews a delivery diff, and there is no code and no delivery
yet. The criteria below replace a skill; do not substitute one.

**This review gates nothing.** v2 defines no plan-review step (see
`06-v2-gap-plan-review.md`). Human requested it. Your verdict routes back to the
Planner, not to `rework_count`, and it is not a v2 gate result. Say what you find
anyway, at full severity.

## Goal

Read the plan and the implementation packet that has been prepared from it, and
answer one question: **will this stage close the defect family, or will it produce
an eighth site?**

The stage exists because the previous one ran seven review-1 rounds finding the
same defect — a missing exchange figure rendered as `0` — at a different layer
each round, and closed on `REWORK`. The plan's central claim is that its §4 site
list is **exhaustive**. Test that claim first and hardest; everything else is
secondary.

Required judgements, each with evidence or an explicit "cannot determine from the
artifacts":

**J1 — Exhaustiveness.** Is `00-plan.md` §4a (three must-fix money sites) plus
§4c (five audited-unchanged sites) actually the closed set for
`backend/hedge_open_tasks/**` and `backend/services/live_hedge_executor.py`? Run
your own independent sweep; do not verify the plan's list by re-reading the plan.
Name any money-figure site it missed, with file and line. A single miss here is
the finding that matters most in this review.

**J2 — Are the non-goals honest?** §3 excludes quantity semantics
(`filled_qty` / `cumulative_base_qty` defaulting to `"0"`) on the grounds that the
previous stage decided it deliberately. Is that exclusion defensible, or does a
`NULL` quantity produce an operator-visible falsehood of the same kind the stage
claims to eliminate? If the latter, say so — the Planner will take it to Human as
a scope decision rather than fixing it silently.

**J3 — Is D4 the right call?** The dispatch orders `store._exposure_from_legs`
deleted in favour of `domain.build_leg_exposure`. Weigh that against `AGENTS.md`
§1 (smallest sufficient change, no speculative machinery): is deduplication
justified by the evidence that drift already caused the confirmed defect, or is
the point fix sufficient and the deletion scope creep? Also assess the behaviour
change the dispatch discloses: `build_leg_exposure` raises on `ts_us <= 0` where
the store copy silently emitted a 1970 timestamp — is introducing a raise on the
reconcile path acceptable, and is the disclosed blocker rule (do not change the
domain contract) a sufficient guard?

**J4 — Is D5 specified tightly enough to be implementable and to actually bite?**
The tripwire is described in prose (`00-plan.md` §5, dispatch D5), not as an exact
pattern. Can two competent implementers read it the same way? Would the described
guard have caught the four historical sites (r4 wire, r5 migration, r6 API
projection, r7 exposure)? Note that r6's site is in `service.py` and r4's is in
`backend/services/**`, while D5 scopes the guard to
`backend/hedge_open_tasks/**` — state whether that scope is a real hole.

**J5 — Is D6 sufficient for the incident it cites?** Gating only row-mutating
migrations while additive DDL — including a `hedge_open_leg` table rebuild
(`DROP TABLE` + `RENAME`) — still runs at construction. `00-plan.md` §6 accepts
that as a residual. Is the residual correctly stated, and does the gate actually
prevent a repeat of the 2026-07-28 incident, in which a session constructed a
store against `data/hedge-open-tasks.sqlite3` and rewrote two production rows?

**J6 — Packet integrity.** Is the dispatch's Allowed Files list sufficient to
deliver D1-D6 without a scope blocker? The previous stage lost rounds to exactly
this. Are the Acceptance Checks falsifiable, or can a plausible-looking
implementation pass them while leaving a coerced zero in place?

**J7 — Process deviations.** `01-human-decisions.md` §D-4 discloses that the
Planner produced the plan without loading a required skill, and asserts the
practical effect is nil. Test that assertion against
`agents/skills/software-architect.md` and `agents/skills/task-planner.md`. Also
check the disclosed Planner/Bookkeeper same-session overlap and the proposed
review-2 routing against `roles.md` isolation rules.

## Allowed Files

**None.** You are read-only: no edit, no commit, no branch, no test run that
writes, no network, no credentials, no service control, no read or write of
`data/**`. Reading the repository and running read-only `git`/`grep`/`rg` is
expected and required for J1.

Do not write your findings into the repository. Return them in your terminal
output; Human transfers them to Bookkeeper (`roles.md:173-174`).

## Inputs

| Path | Range | Why |
|---|---|---|
| `AGENTS.md` | whole (12.7 KB) | §1 minimality, §3 safety kernel, §8 review routing are the yardsticks for J3/J7 |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/00-plan.md` | whole | The artifact under review |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/10-unknown-not-zero-glm.dispatch.md` | whole | The artifact under review |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/01-human-decisions.md` | whole | Routing and the disclosed deviation (J7) |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/06-v2-gap-plan-review.md` | whole | Why this task exists |
| `agents/roles.md` | Planner and Reviewer sections | J7 |
| `agents/skills/software-architect.md`, `agents/skills/task-planner.md` | whole | J7 |
| `backend/hedge_open_tasks/**`, `backend/services/live_hedge_executor.py` | your own sweep | J1 — you must look at the code, not only the plan |
| `git show 3113a5d:reports/agent-runs/2026-07-hedge-order-truth-v1/status.json` | `review_1`, `stage_followups` | Optional, for J4's historical-site check. Archived evidence; read only if needed |

The stage is at `main` head; the branch `stage/2026-07-unknown-not-zero-v1` points
at the same commit and contains no implementation yet.

## Acceptance Checks

Your output must contain:

1. One explicit verdict per judgement J1-J7, each either evidence-backed or
   marked as undeterminable, with the reason.
2. For J1, your own sweep commands and their raw output — not a restatement of
   the plan's table.
3. Findings ordered by severity, each naming file and line where applicable, and
   each stating whether it must be fixed **before** the implementation dispatch or
   can be handled during it.
4. An explicit statement of anything in the plan you believe is **right** and
   should not be weakened by a later round. The previous stage lost work to
   fixes that collided with each other; the Planner needs to know what is load
   bearing.
5. The `[TASK_RESULT v2]` block from `AGENTS.md` §7, including the review-closure
   lines (`评审结论` / `问题记录` / `修复要求`) and the three Chinese handoff
   lines. Since you write no file, use `问题记录: none（结论在终端输出）`.
   `下一步模型: opus5（记账人，Human 转交结果）`.

`评审结论: ACCEPT` here means "the plan will close the family as written";
`REWORK` means it will not, and the required fixes are yours to name.

## Stop

Stop after the verdict. Do not implement, do not prepare another packet, do not
launch another model, do not write to the repository.
