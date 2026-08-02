# F4 Stage Closure Record

Date: 2026-08-02
Stage: `2026-08-02-hedge-f4-account-availability-v1`
Bookkeeper: `codex`
Base: `54438aa94f1ba56acf42d77a4244d59676b6f3e4`

## Closure decision

Human reprioritized the work and closed this stage before the planner task was
started. There is no product delivery and no `delivery_sha`. The F4 fix remains
an accepted limitation and is deliberately deferred; this closure is not an
implementation acceptance.

## Receipt absorbed from Opus5

- F4 A-4 must say: `verified=true` plus a successful UM-side read, no matching
  UM position, and an existing task bucket is the condition for `no_um`.
  “Account-side successfully read” is defined at UM granularity.
- The next F4 packet must include `backend/domain/snapshot.py`; the reported
  root-cause sites are the `verified` calculation near `:1098` and the
  `or []` loss of missing/unknown UM data near `:1120`.
- The operator rule is changed in `PROJECT_STATE.md`: an exchange-side
  “no position” result is never proof that the position is gone; verify on
  Binance. The banner covers only two of the three paths, so its absence proves
  nothing.
- Archive `49-` remains a hard pre-live gate, with a follow-up to add coverage
  for the third path. It is not executed by this closure.
- `docs/planning/ROADMAP.md` now records that F4 is fully specified and
  plan-reviewed, deliberately not implemented, with this closure/archive as
  the restart pointer.

The later Opus5 report was transferred by Human in the conversation; this
record preserves the actionable receipt and closure decision used here.

## Parallel-stage boundary

The separate worktree retains its own active pointer for
`2026-08-02-frontend-display-tweaks-v1` and is not modified by this closure.
This worktree's `ACTIVE.json` is therefore set to `{"active":null}`; the null
is local to this checkout, not a claim that the parallel worktree is closed.
