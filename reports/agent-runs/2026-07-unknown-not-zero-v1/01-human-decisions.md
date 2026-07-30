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

## D-4 Planner skill compliance — deviation, disclosed

`roles.md:47-50` requires the Planner to select at most one skill. `00-plan.md`
was produced without loading one. Both candidates were read afterwards:

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

Recorded as a real deviation, not waived. Its practical effect on this plan is
assessed as nil, and the plan-review packet asks Codex to test that claim rather
than take it. The underlying v2 issue — a named planning skill that is mostly
non-applicable vendored boilerplate, which makes "read one skill" a compliance
ritual — is recorded in `00-plan.md` §9 as a trial observation.
