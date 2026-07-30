# Plan Review Verdict — task0-plan-review (Codex / GPT-5.6-terra)

Raw result transferred by the Human operator 2026-07-30 13:01 CST, from a fresh
read-only Codex session run against `05-plan-review-codex.dispatch.md`.
`评审结论: REWORK`. This review gates nothing mechanically (v2 has no plan-review
step — `06-v2-gap-plan-review.md`); it corrects the plan before implementation.

## Bookkeeper verification — verified against the code, not accepted on the reviewer's word

| Claim | Verdict | Evidence |
|---|---|---|
| **J1 / S4** — `prepare_attempt` writes `cumulative_quote_amt = '0'` for both PREPARED legs; not in §4a or §4c | **CONFIRMED, and worse than stated** | `store.py:743-758` and `:759-775`. Column list `… cumulative_base_qty, cumulative_quote_amt, fee_amount, fee_asset, dispatched_at_us, last_query_at_us, terminal` maps to literals `'0', '0', NULL, NULL, NULL, NULL, 0` — the reviewer's mapping is exact. See "Why worse" below |
| **J5** — M1 no longer exists; the plan's "M1/M2" is a factual error that could induce its recreation | **CONFIRMED** | `grep -n "M1"` in `store.py` returns nothing. `git show 95ac1a5` deletes `m1_rows`, the `UPDATE … SET cumulative_quote_amt = NULL`, and its audit-log block. Only M2 (the `leg_exposure.ts` UPDATE at `store.py:472-478`) survives. Planner error: the "M1/M2" pair was carried from the previous stage's design documents instead of re-read from the code — the same species of staleness that stage was penalised for |
| **J5** — construction still executes a `DROP TABLE` + `RENAME` leg-table rebuild | **OVERSTATED — both by the reviewer and by `00-plan.md` §6** | `store.py:367-378`: the rebuild is guarded by a `PRAGMA table_info` probe on `cumulative_quote_amt`'s `notnull` flag and no-ops once the column is nullable. Production was migrated 2026-07-28, so it cannot fire there. It *would* fire on a legacy database. The reviewer's underlying point survives intact: additive DDL (`ALTER TABLE … ADD COLUMN`) does write to the file, so D6 must claim "no semantic row rewrite", never "never writes" |
| **J7** — zero skills is compliant for a Planner, so D-4's "violation" is wrong | **CONFIRMED** | `roles.md:21-25` — "Planner and Reviewer follow zero or one as their own section states"; `roles.md:47` — "Select at most one skill". Zero is inside the contract. D-4 is corrected to a compliant choice with its reasoning, and the substantive point stands: the plan was checked against `software-architect.md` after the fact, not before |
| **J3** — keep D4 (delete the mirrored builder), keep the negative-timestamp regression | **AGREED** | No change needed |
| **J4** — D5 is prose, not a rule; misses `backend/services/**` and SQL literals | **CONFIRMED by S4 itself** | A SQL literal `'0'` is invisible to every pattern `00-plan.md` §5 described. D5 is rewritten as an executable rule with its own meta-tests |
| **J6** — file boundary sufficient, acceptance checks insufficient | **AGREED** | The checks are extended per §Revisions |

### Why S4 is worse than the review states

The seeded `'0'` is not merely cosmetic on a PREPARED leg, because **one of the
three leg-update paths never overwrites it**:

- `store.py:1089` (attempt close from outcome) writes `cumulative_quote_amt` — may be `NULL`;
- `store.py:1538` (`resolve_leg_from_query`) writes it — may be `NULL`;
- `store.py:1155` (dispatch-state update) writes `dispatch_state`, `order_id`,
  `exchange_status`, and the timestamps — **and does not touch either figure column**.

So a leg that has been sent, has a real `order_id`, and sits at `exchange_status
= NEW` carries `cumulative_quote_amt = '0'` that the system authored itself.
`list_attempts_page` deliberately projects in-flight legs to the UI
(`store.py:1366-1372`), so an operator reads a self-authored zero notional as if
the exchange had reported it. And when a drain query comes back inconclusive the
service does `continue` with no update (the deferred follow-up
`p1-inconclusive-query-raw-not-persisted`), so the seeded zero can outlive a real
fill that we simply failed to read.

This is the same defect family as r4/r6/r7, at its **source** rather than at a
projection. It is the strongest finding in this review and it invalidates the
plan's central exhaustiveness claim, which is exactly what the review was asked
to test.

## The scope question the review escalated (J2), resolved by a schema fact

The review asked Human to decide whether unknown **quantity** joins the stage.
One fact settles the cost side and was not in the review:

- `cumulative_quote_amt TEXT` — **nullable already** (`store.py:92`). Making the
  seeded quote honest is a two-literal change, no migration.
- `cumulative_base_qty TEXT NOT NULL DEFAULT '0'` — **NOT NULL**
  (`store.py:91`). Making the seeded quantity honest requires a schema
  migration: another `CREATE new / INSERT SELECT / DROP / RENAME` rebuild of the
  live table, on a production database that already suffered one unintended
  write this month.

Bookkeeper recommendation to Human: **keep quantity out**, and replace the
current justification with this one. "The previous stage decided it" is a weak
reason; "the column is `NOT NULL`, so honesty costs a live-schema rebuild, and a
not-yet-sent leg genuinely has zero fill" is a real one. Quantity honesty becomes
its own stage if the field ever shows it matters.

## Revisions applied to the plan and the packet

1. **S4 added to §4a** as a must-fix: `store.py:748` / `:765` seed
   `cumulative_quote_amt = NULL` instead of `'0'`. New deliverable **D7**.
2. **D5 rewritten** as an executable rule with an exact allow-list marker format,
   scope extended to `backend/services/live_hedge_executor.py`, SQL-literal
   detection added, and three meta-tests proving the guard fires. Honest coverage
   statement recorded: it reaches r4, r6, r7 and S4; it cannot reach r5, whose
   defect was over-nulling a real `'0'` — no static pattern can decide that.
3. **D6 corrected to M2 only**, with an explicit warning not to reintroduce M1,
   and the residual restated as "no semantic row rewrite" rather than "no write".
4. **§3 non-goals** rewritten with the `NOT NULL` reasoning above.
5. **Acceptance checks** extended: a regression asserting an in-flight
   (dispatched, `order_id` present, unresolved) leg projects an unknown notional
   rather than zero.
6. **`01-human-decisions.md` D-4 corrected** from "deviation" to "compliant
   zero-skill choice", keeping the after-the-fact check disclosure.

## What the review says must not be weakened, carried into every later round

Real exchange `"0"` stays distinct from a missing figure; D2's incomplete flag for
a missing average price; D4's blocker rule against changing the domain contract;
M2 not running by default; and the `data/**` / network / service-control ban.

## rework_count stays 0

`AGENTS.md:182` — `rework_count` counts formal `REWORK` repair rounds for the
current task and explicitly excludes pre-dispatch packet correction. Task 1 has
never been started; this is packet correction before dispatch, not a repair
round. Recording it as a rework round would spend a third of task 1's budget
before any code exists.
