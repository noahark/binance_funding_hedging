# Human Decisions And Routing — 2026-07-30

`status.json` holds exactly the v2 minimal field set (`roles.md:178-203`), so
routing decisions that have no field there are recorded here instead.

## D-1 Work branch

`stage/2026-07-unknown-not-zero-v1`, created from this stage's bookkeeping head.
v2 §9 leaves branch selection to Human; Human selected a dedicated branch so
`main` stays clean and the review range is separable. Pinned into
`10-unknown-not-zero-glm.dispatch.md`.

## D-2 Review-1 model: Grok 4.5

Kimi is the preferred cross-provider review-1 for `claude_glm` implementation
(`roles.md:132-133`), but Human reports its quota has still not recovered
(unavailable since 2026-07-27, three stages running). Human approved the
registered fallback, Grok 4.5 (`roles.md:134`).

Provider isolation holds: implementer `claude_glm` = `zhipu_glm`, review-1
Grok 4.5 = `xai`.

Carried risk from the previous stage: `2026-07-hedge-open-live-hardening-v1`
recorded a Grok misjudgement (`grok 漏判`) and a registry model-id drift. The
registry file itself no longer exists in v2, so the drift item is moot, but the
review-1 packet must give Grok the closed site list and exact line ranges rather
than an open-ended "audit the diff" instruction.

## D-3 Plan review by Codex, before implementation

Human asked for an independent read of the plan before GLM starts. v2 defines no
plan/design review gate — see `06-v2-gap-plan-review.md`. This is therefore a
Human-requested advisory review that gates nothing mechanically and that
Bookkeeper must not present as a v2 gate result.

Consequence for the endgame, so it is decided once and not re-litigated:
reviewing the plan is design involvement (`roles.md:125`), so Codex becomes a
less independent review-2 candidate. Recommended final routing:

| Role | Model | Provider | Note |
|---|---|---|---|
| Planner + Bookkeeper | Opus 5 | anthropic | Same session; disclosed in `00-plan.md` |
| Plan advisory review | Codex / GPT-5 | openai | D-3; read-only, gates nothing |
| Implementer | `claude_glm` | zhipu_glm | Backend default |
| Review-1 | Grok 4.5 | xai | D-2 |
| Review-2 | Fable 5 (recommended) | anthropic | Only model with neither design nor implementation involvement; needs Human's paid-quota selection. Codex with disclosure is the fallback |

Provider isolation from the implementer holds for every reviewer listed.

## D-7 `task2-same-family-rework-rule` withdrawn from this stage — 2026-07-30

Human decided to withdraw task2 and fold it into the Harness fix batch tracked by
`docs/planning/harness-v2-trial-findings-2026-07-30.md`.

Reason: task2 edits `AGENTS.md` §8, and the findings collected during this stage
added three more §8-area rules — G12 (the same brake), G15 (whether a pre-review
Bookkeeper rejection consumes rework budget), G16 (an implementer's channel to
contest an acceptance check). Two separate edits to one section would likely see
the second rewrite the first, and each contract edit is `HIGH_RISK` requiring two
reviews.

Withdrawn, not cancelled. This stage's scope is now `task1` only: the code family
closed plus the static guard.

### Sequencing note — status.json deliberately not revised for this

`status.json` stays at **revision 8** with `current_task = review2-task1-codex`.
The review-2 packet carries `status_revision: 8`, and `AGENTS.md:45` tells a
started terminal to stop if the revision differs. Bumping the revision to record a
scope change that does not touch review-2's range (`ac8d493..851dd08`, which never
contained task2) would risk halting a running final review for no benefit.

`40-review-2-codex.dispatch.md` settled-ground item 7 therefore still reads
"task2 is still pending and outside this range". That sentence is now stale in one
direction only — the operative instruction, *do not file the stage as incomplete*,
is more true after the withdrawal than before. The packet was left untouched
because editing a possibly-executing dispatch is worse than a stale sentence that
errs safe.

The scope change lands in `status.json` at the next revision after review-2
returns. Recorded as Harness finding G17.

## D-6 Review-2 is Codex, with disclosed design involvement — 2026-07-30

Human selected Codex over Fable 5 and over a second Grok round.

Disclosure required by `agents/roles.md:125-127`: **Codex ran this stage's plan
review** (`task0-plan-review`, verdict `REWORK`), so it has prior design
involvement in the artifact it is now asked to finally review. Human was told
this and chose it anyway, for the reason that it is uniquely placed to judge
whether its own four findings were actually resolved rather than papered over.

What still holds, unwaived:

- Provider isolation from every implementation and fix author: implementer is
  `claude_glm` = `zhipu_glm`; Codex = `openai`. `roles.md:123-124` satisfied.
- Fresh read-only session, no shared transcript with the plan review.

What is lost, stated plainly: independence at the final gate. Codex will partly be
confirming its own earlier reading. Mitigations carried into the packet, following
the precedent set for the previous stage's same-provider review pair:

1. The packet names `00-plan.md` (the requirement) as top authority, not any
   design narrative.
2. The packet tells Codex to treat its own round-0 verdict as **unproven** and to
   re-derive rather than recall.
3. Review-1's verdict was committed (`c29cd9d`) before this packet was prepared.
4. The residual risks review-1 found are disclosed in the packet rather than left
   for Codex to rediscover, so its round is spent on release readiness rather than
   on re-running review-1.

## D-5 Unknown quantity stays out of scope — 2026-07-30

The plan review (J2) escalated to Human whether unknown **quantity** joins the
stage. Human was given the decisive fact — `cumulative_quote_amt` is nullable so
the amount fix costs two SQL literals, while `cumulative_base_qty` is
`TEXT NOT NULL DEFAULT '0'` so the quantity fix costs a live-table rebuild — and
decided: **amount only, quantity out, no follow-up filed**. Rationale recorded in
`00-plan.md` §3. Reopening it needs a new Human decision, not an implementer's or
a reviewer's judgement.

## D-4 Planner skill: zero skills, a compliant choice — corrected 2026-07-30

**Correction.** The first version of this entry called the missing skill a rule
violation. It is not. `roles.md:21-25` — "Planner and Reviewer follow zero or one
as their own section states" — and `roles.md:47` — "Select **at most** one skill"
— both permit zero. The plan review (J7) caught the over-declaration and it is
withdrawn. What remains true and is not withdrawn: the plan was checked against
`software-architect.md` **after** it was written, not before.

`00-plan.md` was produced without loading a skill. Both candidates were read
afterwards:

- `agents/skills/task-planner.md` — vendored web-agency PM role. Its concrete
  guidance is Laravel/Livewire/FluxUI, `ai/memory-bank/site-setup.md` paths,
  Playwright screenshot capture, and 30-60 minute task sizing. None of it applies
  to this repository. Its one transferable rule — no gold-plating, quote the
  actual requirement — the plan already follows (§3 non-goals, §4c
  audited-unchanged).
- `agents/skills/software-architect.md` — closer in spirit ("no architecture
  astronautics", "name the trade-off", "prefer reversible decisions"). Checked
  the plan against it after the fact: §3 names non-goals, §6 names the accepted
  DDL residual, §7 names the review-2 independence trade-off. The one gap it
  would have caught is now fixed by the D4 blocker rule in the dispatch
  (do not change the domain contract; report a blocker instead).

The plan review was asked to test the "practical effect is nil" claim rather than
take it, and largely upheld it: the review found no plan defect traceable to the
missing skill. Its four substantive findings (S4, D5's looseness, the M1 error,
the quantity scope question) are all evidence-and-code errors, not
design-methodology errors — which is worth knowing, because it says the missing
skill was not the hole. **The hole was verifying claims about the code from
previous stage documents instead of from the code**, and no skill would have
fixed that.

The underlying v2 issue — a named planning skill that is mostly non-applicable
vendored boilerplate, which makes "read one skill" a compliance ritual — is
recorded in `00-plan.md` §9 as a trial observation.

## D-8 F1 dropped; only F2 and F3 repaired — 2026-07-30

Review-2 returned three findings. Human decided: **F1 is ignored, with no
follow-up filed** — 「后续遇到问题再具体情况具体分析解决」. F2 and F3 are repaired in
this stage.

F1 is the balance-missing→fabricated-zero path that permanently stops a task with
a false reason (`41-review-2-codex-result.md` §F1). Human's judgement, recorded
without hedging: the trigger needs a malformed or truncated balance response, the
failure is fail-closed (it stops a task; it never places an order or moves money),
and the cost of a domain-contract change on a fatal-stop admission path is not
worth paying speculatively. No `PROJECT_STATE.md` entry is created, by decision.

`43-balance-shape-evidence.md` is kept anyway — not as a follow-up, but so that
whoever meets this in the field does not repeat the investigation. It also records
that the Bookkeeper's claim "this cannot be determined from the repository" was
**wrong**: Human pointed out the account-balance panel already carries the data,
and it does. The request for an authorized live `get_balance` read is withdrawn.

F3 was done by the Bookkeeper rather than dispatched: `00-plan.md` §1 and §5 were
the Bookkeeper's own overstatements and are corrected in place, and an erratum is
appended to `20-task1-glm-result.md` **without editing the implementer's delivered
prose** — this harness does not rewrite delivered evidence.

F2 goes to `claude_glm` as `task1c-f2-settlement-visibility`
(`44-f2-repair-glm.dispatch.md`). It then re-enters review-1 and returns to
review-2, per `AGENTS.md:181`, because it touches `service.py` which was forbidden
in the reviewed range.
