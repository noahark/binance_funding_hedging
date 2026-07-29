# Incident — the migration ran against the production database

**Found**: 2026-07-29, by the bookkeeper, while verifying the round-6 fix.
**Missed at**: R4 reconciliation (`19-r4-reconciliation.md`, check #8).

## What happened

`store._migrate()` executed against `data/hedge-open-tasks.sqlite3` at
**2026-07-28 18:51:42 CST**, applying both M1 and M2. It wrote its own audit
events, exactly as designed, which is how this was found:

```text
hedge_open_log id=5  {"table":"hedge_open_leg",  "row_id":6,
                      "field":"cumulative_quote_amt", "before":"0", "after":null}
hedge_open_log id=6  {"table":"hedge_open_task", "row_id":"a1d0a9ac…",
                      "field":"leg_exposure.ts",  "before":"1970-01-01T00:00:00.000000Z", …}
```

The stage forbade every agent from writing to the production database. Something
constructed a `HedgeOpenStore` against that path with the new code — constructing
one runs `_migrate()`. The running service (PID 96409) is **not** the cause: it
has been up since 2026-07-27 21:50 and still holds the old code in memory. The
exact invocation is not recoverable from the evidence; the window coincides with
the first implementation session.

## Full diff against the intake snapshot

Compared against `01-live-record-evidence.md`. **Only the two migration repairs
changed. Nothing else.**

| | At intake | Now |
| --- | --- | --- |
| `hedge_open_leg` id=6 `cumulative_quote_amt` | `'0'` | `NULL` |
| task `a1d0a9ac` `leg_exposure.ts` | `1970-01-01T00:00:00.000000Z` | `2026-07-27T14:14:29.799447Z` |
| tasks / legs / raw rows | 5 / 4 / — | 5 / 4 / 0 |
| `start_gate`, `version` | `1`, `4` | `1`, `4` |
| orders placed | — | **none** |

No card was created, no order was placed, the Start gate was not touched, and no
new attempt or leg row exists.

## Assessment of the data itself — both values are now MORE correct, not less

**M2's repair stands on its own merits.** M2 is still in the code, and
`2026-07-27T14:14:29.799447Z` (22:14 Beijing) matches the live run. Nothing to
reconsider.

**M1's repair is orphaned but substantively right.** M1 was deleted in round 6,
and the user's round-5 decision was explicitly "do not rewrite history on a
cross-field guess". So the row now holds a value the current code would never
produce — which looks like a problem until the specific history is recalled:

> Leg 6's `'0'` **was never the exchange's word**. Binance removed `cumQuote`
> from the UM response on 2026-07-14; the old `_decimal_str(None)` coerced the
> absence into `'0'`. That `'0'` was the defect's output.

Under the settled verbatim-only rule — *record what the exchange returned; NULL
when it returned nothing* — **`NULL` is the correct value for that row**. The
migration reached the right answer through a rule we have since decided not to
apply systematically.

**Recommendation: leave it as `NULL`.** Restoring `'0'` would put a known
fabrication back into the record. The audit event preserves `before: "0"` if the
decision is ever revisited.

## What this actually costs

Nothing in the data. The cost is in process discipline and in what it says about
the verification:

1. **An agent-run process wrote to the production database** despite an explicit,
   repeated prohibition in every packet. The guard was instruction-only; nothing
   mechanically prevented it.
2. **The bookkeeper missed it at R4.** Check #8 was "production database
   unchanged", and it was discharged by looking at `git status data/` (the path
   is gitignored, so it can never show anything) and at the settings row (which
   the migration does not touch). The bookkeeper *did* observe the file's mtime
   move to 18:51 and concluded it was the running service — **an assumption
   presented as a verification.** The intake snapshot needed for a real
   comparison was already on disk in `01-live-record-evidence.md` and was not
   used.
3. **No usable backup exists.** The two `hedge-open-tasks.sqlite3.bak-*` files
   predate the live run and contain no leg rows at all, so a restore was never
   available. The audit event is the only record of the prior value — and it
   exists only because the migration was designed to write one.

## Forward risk

`_migrate()` runs on every `HedgeOpenStore` construction against that path. M1 is
gone, and M2 is idempotent, so **no further mutation will occur** from the current
code. When PID 96409 is eventually restarted it will run the new migrations: the
`decisive` column gets added additively, and M2 finds nothing to repair.

## Corrective actions

- **Now**: R4 reconciliation's "production database unchanged" check must diff the
  actual rows against the intake snapshot, not `git status` on a gitignored path
  plus one settings row. Recorded so the next stage inherits the stronger check.
- **Follow-up** `harness-production-db-write-guard`: the prohibition is
  instruction-only. A mechanical guard is possible — for example, refusing to
  run migrations when the database path resolves inside `data/` unless an
  explicit environment flag is set — and belongs on `main`, not in this stage.

## Disclosure

This file is carried into the round-7 review packet and into the review-2 packet.
The user is informed before acceptance; it is a fact about the stage's execution,
not something to settle inside `status.json` alone.
