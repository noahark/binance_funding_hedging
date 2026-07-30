# Stage Close-out — 2026-07-unknown-not-zero-v1

Closed 2026-07-30 by Opus 5 (Bookkeeper) on Human's merge authorization
(「这次没问题就提交推送合并吧」). Both gates passed on the same sealed range.

```text
base_sha      ac8d493a903051394fc9fda3ca467590a6e2f837
delivery_sha  7bd2bcef7882a642f8bee64192770da924b7e5c6
review-1      ACCEPT  (Grok 4.5, xai)      — third pass
review-2      ACCEPT  (Codex, openai)      — third pass, design involvement disclosed
tests         1097 passed, measured independently three times
rework_count  2 of 3
```

## What was delivered

**Family 1 — a missing exchange figure is never a zero** (DEC-2026-07-30-001).
The root helper is restricted to quantities, a sibling preserves the unknown, the
duplicated leg-exposure rule is gone (the store delegates to `domain`), the
`prepare_attempt` SQL seed is `NULL`, the fill-row loop flags an incomplete notional
instead of averaging a missing price in as zero, and a static tripwire guards money
identifiers with three permanent meta-tests.

**Family 2 — a discarded state-write failure is a defect** (DEC-2026-07-30-002).
Seven sites now record instead of swallowing: two settlement paths
(`settlement_failed`) and five state writes (`state_write_failed` with an
`operation`). S2 additionally guarantees a 429 pair never settles as an ordinary
failure, whether or not its retried stamp succeeds.

**Row-mutating migrations no longer fire implicitly** (DEC-2026-07-30-003).

## What this stage proved about its own claims — kept deliberately

Four "exhaustive" claims were made and all four were wrong:

1. The plan's closed site list missed `prepare_attempt`'s SQL seed — found by the
   plan review.
2. The Bookkeeper's verification declared the discard family closed at three sites
   from a `grep … | head` truncated at ten lines. The real count was thirteen.
3. The plan's list also omitted `domain.py:947/950`, the balance path — found by
   review-2, and the most consequential of the three (a fatal stop with a false
   reason).
4. Review-2's own four-site P1 was not the whole family either; the exhaustive audit
   found eight class-(A) sites in three syntactic shapes.

The list was extended by every independent reader who looked. That is the honest
measure of how closed any such list is, and it is why the durable deliverables are the
tripwire, the paired regressions, and the fault-injection tests — not the tables.

The static tripwire is a **speed bump against accidental reintroduction, not a proof**:
five evasions are confirmed. For the discard family a static guard was judged
impossible and none was built; a reasoned "no" was preferred to a guard nobody could
trust.

## Human decisions, all recorded with reasons in `01-human-decisions.md`

D-1 branch · D-2 Grok 4.5 as review-1 (Kimi quota) · D-3 plan review by Codex ·
D-4 zero Planner skills was compliant (over-declaration withdrawn) · D-5 quantity out
of scope · D-6 Codex as review-2 with disclosed design involvement · D-7 `task2`
withdrawn into the Harness batch · D-8 F1 dropped, no follow-up filed ·
D-9 Harness batch held for Human's own vetting · D-10 five sites repaired, three
deferred, main line next.

## §9 close-out checklist

1. **Durable decisions promoted** — DEC-2026-07-30-001/002/003 in
   `docs/planning/DECISIONS.md`.
2. **Residuals and follow-ups moved** to `PROJECT_STATE.md` (2,035 bytes, within
   budget): the three deferred discard sites, the timeline question, S2's restart
   residual, the tripwire's evasions, and the `[HUMAN-OWNED]` Harness hold.
   **F1 has deliberately no entry** — D-8 filed no follow-up; that is a decision, not
   an omission, and `43-balance-shape-evidence.md` preserves the analysis in this
   archive.
3. **Last completed stage and archive ref recorded** in `PROJECT_STATE.md`.
4. **Evidence preserved** at tag `archive/2026-07-unknown-not-zero-v1`.
5. **Stage directory removed** from the normal worktree.
6. **`ACTIVE.json`** → `{"active": null}`, and it stays there: the next work is
   main-line live testing, and the Harness batch is Human-owned on another branch.

## Harness trial output

`docs/planning/harness-v2-trial-findings-2026-07-30.md` — 19 findings and 6 things
that must not be "improved" away, each with a verification command or file:line.
Human is vetting it with Codex on a separate branch. Two findings were exercised
twice each during this stage (G17, a mid-flight Human decision having nowhere to go),
and the highest-priority four share one cause: v2 kept v1's rules and deleted v1's
mechanisms.
