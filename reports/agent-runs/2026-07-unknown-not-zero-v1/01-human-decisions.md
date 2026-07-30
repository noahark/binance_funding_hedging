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
