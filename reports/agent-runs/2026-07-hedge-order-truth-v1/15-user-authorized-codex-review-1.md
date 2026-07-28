# User Authorization — Codex As The Review-1 Gate

## Why this record exists

`agents/registry.yaml` registers the Review-1 cross-review pool as
`review_1_cross_review_pool: [kimi, claude_glm]`. Codex is not in it, and
`model_policies` records `codex_eligible_for_implementation_or_fix: false` —
Codex is registered as a *decision* model, not a Review-1 gate.

AGENTS.md permits a model outside the registered pool to take Review-1 only on
an explicit stage-level user enablement. This file is that enablement, and it
mirrors the treatment Grok required in
`2026-07-hedge-open-live-hardening-v1/15-user-authorized-grok-review-1.md`.

## The authorization

- **Authorizer**: user
- **At**: 2026-07-28
- **Decision**: Review-1 for this stage runs on `codex`.
- **Verbatim**: 「开吧，review-1 用 codex」

## Why the pool could not supply the gate anyway

- `kimi` — quota has not recovered (unchanged since 2026-07-27).
- `claude_glm` — is this stage's implementer, so it is barred from reviewing its
  own code. That ban has no override.

With both registered pool members unusable, Review-1 had to come from outside
the pool regardless. The user's choice of Codex is therefore not a substitution
for an available pool member.

## The forced consequence, presented before the decision

AGENTS.md allows only two decision models at the final gate: Codex and Claude.
The strong-reviewer disclosure override — the mechanism that would let Claude
review a stage it designed — is admissible **only** when the other decision
model fails a runner-level availability check. Codex is available, so that
override cannot be opened.

So with Codex at Review-1, Review-2 was constrained to either:

1. **Claude**, which then requires Claude *not* to be the stage designer; or
2. **Codex again**, accepting that the final gate is no longer independent.

The bookkeeper put three concrete routings to the user and recommended the
first (grok designs, Claude takes the final gate — four roles, four providers,
zero overlap, no waiver of any kind).

**The user chose option 2: Claude designs, Codex walks both gates.**

## Resulting routing

| Role | Provider | Model |
| --- | --- | --- |
| Designer + breakdown author | `claude` | Claude Fable 5 (Opus 4.8 on quota exhaustion) |
| Implementer | `claude_glm` | `glm-5.2[1m]` |
| Review-1 | `codex` | GPT-5 Codex |
| Review-2 | `codex` | GPT-5 Codex |
| Bookkeeper | `claude` | Claude Opus 5 (writes no delivery code) |

## Compliance check by the bookkeeper

Every hard gate holds:

- Review-1 is provider-isolated from the implementer: `codex` ≠ `zhipu_glm`. ✓
- Review-2 is provider-isolated from every implementation and fix author:
  `codex` ≠ `zhipu_glm`. ✓
- Review-2 has no design involvement (`claude` designed), so **no**
  strong-reviewer disclosure override is needed and none is claimed. ✓
- Neither reviewer is the implementer or fix author. ✓
- AGENTS.md and `scripts/validate-stage.py` impose no constraint on Review-1 and
  Review-2 sharing a provider identity. ✓

No authorized exception, waiver, or disclosure override is required by this
routing.

## Disclosed cost, accepted by the user

The final gate is **not an independent second pair of eyes this stage.** Codex
will have already formed and published a verdict on the same diff at Review-1,
so Review-2 substantially re-confirms its own earlier reading rather than
challenging it. The failure mode this arrangement cannot catch is a defect that
Codex is systematically blind to — it will pass both gates.

That is a real reduction in review strength relative to the previous stage,
where Grok/Claude at Review-1 and Codex at Review-2 were three distinct
providers. It was stated plainly before the user chose, and the user chose it.

## Required mitigations

These are binding on the bookkeeper when it prepares the two packets:

1. **Two distinct fresh read-only sessions.** Review-1 and Review-2 must not
   share a session, transcript, or tool state. Review-2 must be started clean,
   with no reference to the Review-1 session's reasoning beyond the committed
   artifact.
2. **Review-2's packet points at `00-task.md` as the top authority**, not at
   `10-design.md`. That authority-order point is exactly what let Codex catch
   the previous stage's blocking finding after Review-1 had filed the same fact
   as an accepted residual risk.
3. **Review-2's packet must state that Review-1 was performed by the same
   provider** and instruct the reviewer to treat its own prior verdict as
   unproven. A gate that assumes its predecessor was right adds nothing.
4. The Review-1 verdict is committed evidence before Review-2 is dispatched, so
   the second reading is against the record, not against memory.

## Fallback if a Codex verdict is invalid

A missing verdict, or one failing `schemas/review-verdict.schema.json`, is
non-accepting evidence. Retry that gate once. If it fails again, fall back for
that gate to `claude` (Fable 5 → Opus 4.8), recording the fallback reason and
the invalid-output evidence path.

Note the asymmetry: the Claude fallback is admissible for **Review-1** without
qualification, because AGENTS.md constrains designer overlap only at Review-2.
If the fallback is needed for **Review-2**, Claude's design involvement makes it
admissible only under the strong-reviewer disclosure override, which then *is*
available because Codex will have failed a runner-level check — the exact
condition the override exists for. Record `reviewer_prior_involvement` and the
evidence path in that case.

Pre-authorized here so the stage does not stall waiting on the user.
