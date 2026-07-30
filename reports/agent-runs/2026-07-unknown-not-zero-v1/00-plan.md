# Stage Plan — Unknown Is Not Zero (v1)

Planner: Opus 5 (same session as Bookkeeper — disclosed; see §7 routing).
Human product decision: 2026-07-30. Prepared 2026-07-30 12:36 CST at `ac8d493`.

## 1. Why this stage exists

The previous stage (`2026-07-hedge-order-truth-v1`) ran seven review-1 rounds and
still closed on `REWORK`. Every round found the same defect family — a missing
exchange figure silently rendered as `0` — at a different layer: wire (r4),
migration (r5), API projection (r6), reconciled exposure (r7). The rounds fixed
call sites; none touched the helper that produces the zero. So the eighth site
was always going to exist.

This stage closes the family instead of a site, and adds the two cheap guards
whose absence let the last stage go wrong in the first place.

## 2. Goal

1. **One rule, enforced mechanically**: a figure the exchange did not return is
   `NULL`/`None` everywhere a human or a downstream calculation reads it as
   money. A real `"0"` from the exchange stays zero.
2. **One implementation of that rule**, not two that drift.
3. **A tripwire** so a new money-figure site cannot reintroduce the coercion
   while the suite stays green.
4. **Row-mutating migrations cannot fire implicitly** — the 2026-07-28 incident
   where an agent session silently rewrote two production rows must be
   structurally impossible, not forbidden by prose.

## 3. Non-goals (explicit, do not expand)

- Quantity semantics. `filled_qty` / `cumulative_base_qty` defaulting to `"0"`
  stays out, on two grounds — the second one is the real one:
  1. A leg that was never sent, or was accepted and not yet filled, genuinely
     has zero fill. That was decided deliberately last stage
     (`store.py:803-806`, `live_hedge_executor.py:107`).
  2. **`cumulative_base_qty` is `TEXT NOT NULL DEFAULT '0'`**
     (`store.py:91`), while `cumulative_quote_amt` is nullable
     (`store.py:92`). Making the quantity honest therefore costs a live-table
     schema rebuild (`CREATE new / INSERT SELECT / DROP / RENAME`) on the same
     production database that already took one unintended write this month.
     Making the amount honest costs two SQL literals.
  Human decided this boundary on 2026-07-30, after the plan review escalated it
  (J2) and was given the `NOT NULL` fact above: amount only, quantity excluded,
  no follow-up filed. If the field ever shows unknown quantity actually misleads
  an operator, it becomes its own stage with its own migration review. The implementer records the audit of
  these sites so 「查过且如此」 stays distinguishable from 「没查」.
- The close/平单 capability. Separate future stage; Human deprioritised it.
- Frontend. No UI change is needed: the API already emits `null` correctly on
  the paths fixed in r6; this stage makes the remaining paths agree.
- The 39 stale completed-stage directories still in `reports/agent-runs/`
  (v2 §9.5 wants them out of the normal worktree). Recorded as a follow-up.
- Any DDL gating. Only row mutation is gated; see §6 residual risk.

## 4. Exhaustive site audit (the whole point — closed list)

Swept `backend/hedge_open_tasks/*.py`, `backend/services/live_hedge_executor.py`,
`backend/services/hedge_open_live_client.py` for `_num(`, `_decimal_str(`,
`or "0"`, `, "0")`, `Decimal(0)`.

### 4a. MUST FIX — money/price figures that fabricate a zero

| # | Site | What happens | Evidence |
|---|---|---|---|
| S1 | `store.py:1336-1337` `_exposure_from_legs` | `_num(NULL quote)` → `Decimal(0)`, then `price = str(0/base)` = `"0E+1"` | Confirmed P1, review-1 r7, `43-review-1-r7.md`; bookkeeper reproduced the chain |
| S2 | `store.py:1926` and `:1930` | `q * _num(avg_price)` on the FILLED fill-row path: a `NULL` `avg_price` adds `0` notional and sets **no** incomplete flag, while the adjacent leg-row path at `:1946-1958` handles the identical case correctly and flags it | Same function, two policies. `avg_price` is written verbatim and is nullable (`store.py:1606`, `executor.py:193/209/236`, `live_hedge_executor.py:467/474`); UM POST carries no `avgPrice` since 2026-07-14, so a live `FILLED` leg with `NULL avg_price` is reachable, not hypothetical |
| S3 | `store.py:292-296` `_num` | The source: `None → Decimal(0)`, and `InvalidOperation → Decimal(0)` — an unparseable present value also becomes zero | Root of S1/S2 and of r4/r5/r6 |
| S4 | `store.py:748` and `:765` `prepare_attempt` | Both PREPARED legs are inserted with the SQL literal `cumulative_quote_amt = '0'` — a figure the system authors for itself before any exchange contact. The dispatch-state update at `store.py:1155` **never overwrites either figure column**, so a leg that has been sent, holds a real `order_id` and sits at `exchange_status = NEW` still carries that self-authored zero; `list_attempts_page` deliberately projects in-flight legs to the UI (`store.py:1366-1372`). When a drain query returns inconclusive the service does `continue` with no update, so the seeded zero can outlive a real fill we failed to read | **Found by the plan review (J1), not by this plan's own sweep.** Bookkeeper confirmed the column mapping at `store.py:743-758` / `:759-775` and the three update paths at `:1089`, `:1155`, `:1538`. This is the family at its source, not at a projection — and it is why the "exhaustive" claim below had to be tested by someone else |

### 4b. MUST DEDUPLICATE — one rule, two implementations

`store._exposure_from_legs` (`store.py:1324-1343`) is a hand copy of
`domain.build_leg_exposure` (`domain.py:1017-1053`); its own docstring says
"mirrors". The domain copy is correct (`price = None` when `avg_price is None`);
the store copy is S1. Two copies of one rule is why the fix took a seventh round.

### 4c. AUDITED, DELIBERATELY UNCHANGED — record, do not edit

| Site | Why it stays |
|---|---|
| `live_hedge_executor.py:111,129` `_decimal_str(executedQty)` default `"0"` | Quantity, with a written justification (`:107`). Non-goal §3 |
| `service.py:214,252,253,284,310,774,775` `or "0"` | All `cumulative_base_qty` — quantity. Non-goal §3 |
| `domain.py:1050` `leg.get("filled_qty", "0")` | Quantity |
| `executor.py:180` `(filled_qty * price) if price is not None else Decimal(0)` | Dry-run record transport only; `price` is non-optional in the simulated path |
| `store.py:1911-1915,1964-1965` `Decimal(0)` | Accumulator seeds and a guarded divisor, not substituted exchange figures |

If the implementer finds a money-figure site not in 4a, it must be reported as a
blocker, not fixed silently — the closed list is the deliverable.

**Standing of this list after review.** The first version of §4 missed S4, and an
independent sweep found it (`07-plan-review-verdict.md`). The list is therefore
"exhaustive as far as two independent sweeps reach", not proven closed. That is
precisely why §5's guard, not this table, is the durable deliverable.

## 5. Guard to add (this is what prevents round 8)

A static tripwire in `backend/tests/test_hedge_purity.py`, mirroring that file's
existing import/allowlist guards. The plan review (J4) rejected the first
version of this section as prose two implementers could read two ways, and S4
proved a SQL literal escapes every pattern it described. The rule is therefore
specified exactly, in the dispatch's D5, over these scopes:

- `backend/hedge_open_tasks/**` and `backend/services/live_hedge_executor.py`
  (r4's layer, previously excluded);
- both Python coercions **and** SQL literals in an `INSERT`/`UPDATE` naming a
  money column;
- an exact inline allow-list marker format, where the guard also asserts each
  marker still sits on a known justified site, so an allow-list entry cannot
  silently widen to cover a new one;
- the guard is a pure function over source text, so it carries its own
  meta-tests proving it fires.

Honest coverage statement, to be preserved rather than inflated: this guard
reaches the r4, r6, r7 and S4 defect categories. It **cannot** reach r5, whose
defect was over-nulling a real exchange `'0'` — no static pattern can tell a
fabricated zero from a real one at rest. That case is covered only by the paired
regressions required in §8.

## 6. Database write guard (C2)

`HedgeOpenStore.__init__` (`store.py:311`) calls `_migrate()`, which performs
additive DDL **and** one row-mutating repair. Constructing a store against
`data/hedge-open-tasks.sqlite3` therefore rewrote production rows on 2026-07-28
with no caller intending it (`42-production-db-write-incident.md`).

**Corrected fact, from the plan review (J5).** The first version of this section
said M1 and M2 both survive. Only **M2** does — the `leg_exposure.ts`
`1970 → real timestamp` UPDATE at `store.py:472-478`. M1 was deleted deliberately
at `95ac1a5` during the previous stage's round-5 fix, and `grep -n "M1"` on
`store.py` now returns nothing. The error came from carrying the pair out of the
previous stage's design documents instead of re-reading the code — the same
staleness species that stage was penalised for. The packet now warns the
implementer explicitly not to recreate M1.

Fix: split M2's row mutation out of construction. DDL stays automatic (a database
must be usable); M2 runs only under an explicit opt-in argument that defaults to
off and that no production caller passes — it has already been applied. A test
asserts a repairable row survives a default construction untouched.

Residual risk, stated accurately rather than strongly:

- Additive DDL (`ALTER TABLE … ADD COLUMN`) still runs at construction, so D6
  buys "no semantic row rewrite", **not** "never writes the file". Any claim of
  the latter is false and must not appear in the delivery report.
- The `hedge_open_leg` rebuild (`CREATE new / INSERT SELECT / DROP / RENAME`,
  `store.py:379-420`) is guarded by a `PRAGMA table_info` probe on
  `cumulative_quote_amt.notnull` (`store.py:367-378`) and no-ops once the column
  is nullable — production was migrated on 2026-07-28, so it cannot fire there.
  It **would** fire against a legacy database. Both the plan review and the first
  version of this section overstated it as unconditional; this is the accurate
  reading, verified in the code.

## 7. Risk class, tasks, routing

`HIGH_RISK` by AGENTS.md §8: money/PnL meaning and accounting. Review-1 **and**
review-2 required for both tasks.

| Task | Scope | Role/model |
|---|---|---|
| `task1-unknown-not-zero` | §4a + §4b + §5 + §6, backend only | Implementer `claude_glm` (backend default) |
| `task2-same-family-rework-rule` | One rule in AGENTS.md §8: two consecutive `REWORK` rounds on the same root cause forbid another point fix and require one exhaustive root-cause pass | Implementer `claude_glm` (contract edit, as in phase E) |

Task 2 is deliberately narrow because v2 already closed half of the original
complaint: `AGENTS.md:182` now caps `rework_count` at three and routes past it to
a Human choice, which removes the "amended criteria" bypass the last stage used
to reach round 7. What v2 still lacks is the same-root-cause brake.

Sequential, task 1 first. Review routing at dispatch time:

- Review-1: cross-provider vs `zhipu_glm` → Kimi preferred (`roles.md:132-133`),
  Grok 4.5 the Human-approved fallback if Kimi quota is still unavailable.
- Review-2: default is Opus 5 (`roles.md:142`), but Opus 5 planned this stage and
  is its Bookkeeper, so `roles.md:125` ("prefer a final reviewer that did not
  plan the stage") points elsewhere. Human decision required before review-2.
  Provider isolation from the implementer holds for every candidate.

## 8. Acceptance criteria (stage level)

1. Every §4a site returns/stores `None`, never a coerced zero, when the exchange
   figure is absent; a real `"0"` still stores zero. Regression tests exist per
   site, deterministic, temp-SQLite only, **each site paired**: one case for the
   missing figure and one for a real exchange `'0'`. The pairing is what covers
   the r5 category the §5 guard cannot reach.
2. An in-flight leg — dispatched, real `order_id`, `exchange_status = NEW`, no
   resolution yet — reports an unknown notional, not zero (S4's live consequence).
3. Only one implementation of the leg-exposure rule remains.
4. The §5 guard ships with meta-tests proving it fires on a Python coercion, on a
   SQL money literal, and on a site in `backend/services/**`.
5. Default `HedgeOpenStore` construction mutates no existing row, and the report
   claims only that — not "never writes".
6. Full `backend/tests` suite green (baseline: 1071 passed at `3113a5d`).
7. No network, credentials, service control, or write to `data/**` at any point.

## 9. v2 trial observations (Human asked for stability feedback)

Appended as they occur.

- Startup path worked as written: `AGENTS.md` → `ACTIVE.json` →
  `PROJECT_STATE.md` was enough to resume with no active stage. Read cost well
  under the 8K target.
- Friction: `PROJECT_STATE.md` carried a live risk (naked short, no close
  function) that Human resolved manually outside any stage. v2 gives Bookkeeper
  the write authority but no packet-triggered moment to refresh it; it only got
  corrected because Human said so in conversation.
- Friction: v2 removed `validate-stage.py`, so nothing mechanically checks
  status/evidence shape. This stage's own §5 tripwire is the same idea applied
  to product code — worth noting that the Harness deleted its version of it in
  the same week.
- Friction: `base_sha` is defined as "committed HEAD immediately before preparing
  the packet" (`roles.md:223`), which is anti-self-reference but not
  review-range purity — so `base_sha..delivery_sha` will contain this stage's
  bookkeeping commits alongside the implementation. The review packets must say
  so explicitly. Candidate v2 wording fix: define `base_sha` as the commit the
  implementer starts from.
- Gap: v2 has no plan/design review step at all. Written up separately in
  `06-v2-gap-plan-review.md` with a recommended one-sentence §8 fix, prompted by
  Human asking where a pre-implementation Codex review fits.
- Friction: the named Planner skill `agents/skills/task-planner.md` is vendored
  web-agency boilerplate (Laravel, FluxUI, Playwright, `ai/memory-bank/` paths).
  Requiring a Planner to load one skill is currently closer to a compliance
  ritual than to help. `software-architect.md` is genuinely applicable; the
  Planner-skill menu should say which is the default for a backend defect stage.
  See `01-human-decisions.md` §D-4 for the disclosed deviation.
- Friction: v2 dropped `docs/model-adapters.md`, so how to launch each model
  terminal is now undocumented and lives only with the Human operator.
- Friction: `status.json`'s field set is exactly fixed, with no field for routing
  decisions (review-1 model, branch, disclosed deviations). They went into
  `01-human-decisions.md`. This is probably the right call, but the contract
  should name where such decisions live, or each stage invents a filename.
- Friction: `PROJECT_STATE.md` has a hard 2 KB budget and was already at 2 KB.
  Recording one new fact required trimming two existing entries. The budget is
  right, but there is no stated rule for what gets evicted first.
