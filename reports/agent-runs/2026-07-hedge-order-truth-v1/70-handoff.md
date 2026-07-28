# Handoff — Hedge Order Truth And Error Fidelity v1

## Recovery Header

```text
stage_id:        2026-07-hedge-order-truth-v1
status:          designing
stage_branch:    stage/2026-07-hedge-order-truth-v1
branch_base:     ecc38418f52b525eb61bf1c72b9b2b41c26130ef (local main)
current_branch:  stage/2026-07-hedge-order-truth-v1
head:            acfccbd (raw design artifacts archived) + this bookkeeping commit
worktree:        clean
rework_count:    0 / 3
design:          COMPLETE. Original received 14:45:33 (archived verbatim at
                 acfccbd) against the superseded packet; narrowly revised
                 17:29 on Fable 5. Both stale items closed and the diff
                 verified confined to the named sections. Two known
                 cosmetic residuals: status.design_staleness.known_residuals
                 (R-1 §0 stale T4 sentence, R-2 ADR numbers are topic-
                 sequential, not T-id aligned).
next_action:     bookkeeper transcribes file boundaries into status.tasks[0]
                 and prepares 13-implementation.dispatch.md for claude_glm
next_model:      claude_glm (glm-5.2[1m]) once that packet exists
blockers:        none
```

⚠️ **Live surface is OPEN this stage.** Service PID 96409 running in live mode,
durable Start gate `start_gate=1` (version 4), 3 paused cards in the database,
and a real naked SHORT 10000 NOMUSDT (orderId 888412130) outstanding with no
close function. The user was offered closing the gate and stopping the service
and chose to leave both. **No agent may create a card, press Start, place an
order, touch credentials, start/stop the service, or write to
`data/hedge-open-tasks.sqlite3`.** Read-only queries for evidence are fine.

## What this stage is

The previous stage made a real order succeed. This one makes the *record* of it
true. Four defects, three from the standing proposal and one found at intake,
all the same shape: a plausible value substituted for information the system
had or could have fetched.

| Id | Sev | What is wrong today |
| --- | --- | --- |
| T1 | P0 | A leg that filled 10000 NOMUSDT recorded a notional of `0` — Binance removed `cumQuote`/`avgPrice` from UM/CM responses on 2026-07-14 and `_decimal_str(None)` returns `"0"` |
| T2 | P1 | `51169` recorded `error_category = NULL` — the code tables hold only negative literals, so no margin-endpoint code can match |
| T3 | P1 | Binance's own words are discarded; there is no column for them and no raw payload is stored anywhere |
| T5 | P1 | The live exposure record is timestamped `1970-01-01` — `service.py:1688` hardcodes `0`; the dry-run path passes a real timestamp, which is why offline tests miss it |
| T4 | P2 | **Cause found 2026-07-28** — NOM is above Binance's platform-wide per-asset Maximum Collateral Limit, so buying it into a margin account is blocked. The paid discriminator is cancelled; remaining work is read-only recon. See `02-collateral-cap-finding.md` |

Primary evidence is `01-live-record-evidence.md` — raw rows read from the
production database at intake — plus `02-collateral-cap-finding.md` for T4's root
cause. Both outrank every narrative in this stage, including this file.

**This stage places no order.** T4's paid discriminator was cancelled on
2026-07-28 once the user's own Binance app and Binance's official FAQ established
the cause. T2 inherits a required verdict for `51169` as a result — see
`02-collateral-cap-finding.md` §Consequences.

## Routing, and the one thing to know about it

| Role | Provider | Model |
| --- | --- | --- |
| Designer + breakdown | `claude` | Fable 5 (Opus 4.8 on quota exhaustion) |
| Implementer | `claude_glm` | `glm-5.2[1m]` |
| Review-1 | `codex` | GPT-5 Codex |
| Review-2 | `codex` | GPT-5 Codex |
| Bookkeeper | `claude` | Opus 5 (no delivery code) |

**Review-1 and Review-2 are the same model this stage.** The user chose Codex
for Review-1; AGENTS.md then allowed only Codex-again or Claude at the final
gate, and Claude was needed for design. Every hard gate holds — both reviewers
are provider-isolated from the implementer and Review-2 has no design
involvement, so no waiver or disclosure override is claimed. What is lost is
independence: the final gate largely re-confirms its own earlier reading.

Full reasoning and the binding mitigations: `15-user-authorized-codex-review-1.md`.
The mitigations are not optional — whoever prepares the review packets must
apply them:

1. Two distinct fresh read-only sessions, no shared transcript.
2. Review-2's packet points at `00-task.md` as top authority, not `10-design.md`.
3. Review-2's packet discloses that Review-1 was the same provider and tells the
   reviewer to treat its own prior verdict as unproven.
4. Review-1's verdict is committed before Review-2 is dispatched.

## Settled decisions — do not re-litigate

- **`single_leg_exposure` stays ADVISORY** (user, 2026-07-28). A single-leg
  outcome does not pause the task, even though a real naked position resulted.
  T2 must not change this.
- **The live surface stays open** (user, 2026-07-28). Not a defect; not this
  stage's to close.
- **T4's paid discriminator is cancelled** (bookkeeper, 2026-07-28). The cause is
  established, so the order would spend money to confirm a known answer. The
  preflight still may not change until the read-only recon says whether any API
  exposes the collateral cap — and "deliberately not changed, here is why" is a
  complete T4 outcome.

## Open items the design must resolve

- T1: authoritative source for UM/CM fill figures, and **when** the read happens
  (today a leg is never queried after dispatch).
- T1(e) + T5(d): what to do about the historical rows already holding `0` and
  `1970`. Must be a tested one-off migration in code if anything — no manual SQL.
- T2: the structural rule for positive codes, and keeping unrecognised codes
  distinguishable from recognised ones.
- T3: storage shape, retention, redaction.
- Whether `p3-preflight-snapshot-key-contract-untested` (carried from the
  previous stage) is cheap enough to fold in.

## The design, and the one error in it

`10-design.md` / `11-adr.md` / `12-development-breakdown.md` are archived verbatim
at `acfccbd`. The work is strong — notably §6's historical-data migration
(rule-based rather than row-specific, refuses network backfill, turns a `FILLED`
leg's fake `0` notional into `NULL` because "we do not know" is the honest answer)
and §9's section-by-section review of the stale recon, which additionally caught
that the `DELETE` endpoints lost the same fields — relevant to the future close
stage.

It was produced 45 seconds before the packet revision that carried T4's root
cause, so two items **were** stale. Both were closed by the narrow revision of
17:29 (`status.design_staleness.resolution_summary`). What follows is what they
were and how they were fixed:

- **S-1, a factual error.** The design seeds `51169 → insufficient_funds`, calls
  it synonymous with UM's `-2019`, and maps it to
  `pause_reason=insufficient_margin`. `51169` is *not* this account's margin
  being short — NOM is above Binance's platform-wide per-asset collateral cap and
  adding balance does nothing. The operator copy that mapping produces means
  **保证金不足**, which is exactly the plausible-but-false substitution this stage
  exists to eliminate. Reasonable given the packet it had; wrong now.
  The *structure* of T2 — `(product, code)` keyed tables, gateway layer first,
  explicit `unclassified`, conservative seeding, attempt roll-up — is unaffected
  and good.
  **Fixed**: `51169` now has its own category `collateral_cap` with
  `pause_reason=collateral_cap_full`, frozen truthful Chinese copy, and a
  roll-up priority above `insufficient_funds`. The revision also added a safety
  argument the bookkeeper had missed: because the cap blocks only the forward
  spot leg while the perp leg still fills, retrying reproduces the 2026-07-27
  mechanism and **grows the naked short** — so pausing is loss-stopping, not
  merely budget-saving.
- **S-2, obsolete.** §5's paid discriminator procedure, plus two places telling
  the bookkeeper to request authorization for it.
  **Fixed**: §5 replaced by a read-only recon with a four-candidate endpoint
  table (every endpoint name marked unverified, each row stating what it cannot
  prove), a conditional preflight decision where "deliberately unchanged, and
  here is why" is a complete outcome, and the discipline that a negative search
  must be recorded so 「查过且没有」 stays distinguishable from 「没查」.

Everything else stands, unchanged and unreviewed by the revision.

## Two residuals to carry into every downstream packet

- **R-1** — `10-design.md` §0's overview still describes T4 as the cancelled
  paid experiment. §5 and `00-task.md` §T4 govern. Not fixed because the
  revision's diff was deliberately confined to §2/§5/§8/§11, and the bookkeeper
  does not edit design artifacts. Disclose so no reviewer files it as a finding
  and no implementer acts on it.
- **R-2** — `11-adr.md` numbers ADRs by topic, not by T-id. **T2's ADR is
  `ADR-T3`**; `ADR-T2` is T1's representation decision and `ADR-T4` is T3's
  persistence decision. This already misled the bookkeeper once.

## Sequence from here

1. ▶ Bookkeeper transcribes the breakdown's boundaries into
   `status.tasks[0].allowed_files` / `forbidden_files` and prepares
   `13-implementation.dispatch.md` for `claude_glm`, disclosing R-1 and R-2.
3. Human operator runs the implementation packet in Claude-GLM.
4. Bookkeeper verifies boundaries, commits evidence, computes the fingerprint,
   runs `scripts/validate-stage.py 2026-07-hedge-order-truth-v1 --phase pre-review`.
5. Review-1 (Codex, fresh read-only session) → Review-2 (Codex, second fresh
   session) → `stage_accepted_waiting_user`.
6. T4 needs no user authorization any more — its remaining work is a read-only
   recon for whether any API exposes the per-asset collateral cap.

Merge to `main` only after explicit user acceptance. Note `main` itself is not
pushed — the previous two stages are merged locally only.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/70-handoff.md
本地北京时间: 2026-07-28 07:26:35 CST
下一步模型: human operator
下一步任务: 在全新的 Claude Fable 5 终端执行 10-design-and-breakdown.dispatch.md
