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
  was a deliberate decision last stage ("an accepted not-yet-filled leg
  genuinely executes zero", `store.py:803-806`, `live_hedge_executor.py:107`).
  It stays. The implementer records the audit of these sites so
  「查过且如此」 stays distinguishable from 「没查」.
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

## 5. Guard to add (this is what prevents round 8)

A static tripwire in `backend/tests/test_hedge_purity.py`, mirroring that file's
existing import/allowlist guards: no assignment or dict value whose target names
a money figure (`price`, `avg_price`, `notional`, `quote`, `cumulative_quote*`)
may be produced by a zero-defaulting helper (`_num(`, `or "0"`, `, "0")`) in
`backend/hedge_open_tasks/**`. Justified exceptions require an inline
allow-list marker naming the reason, so an exception is visible in review rather
than invisible in behaviour.

## 6. Database write guard (C2)

`HedgeOpenStore.__init__` (`store.py:311`) calls `_migrate()`, which performs both
additive DDL **and** two row-mutating repairs (M1 `'0'→NULL`, M2 `1970→real ts`,
`store.py:400-440`). Constructing a store against `data/hedge-open-tasks.sqlite3`
therefore rewrote production rows on 2026-07-28 with no caller intending it
(`42-production-db-write-incident.md`).

Fix: split row mutation out of construction. DDL stays automatic (a database must
be usable); M1/M2 run only under an explicit opt-in argument that defaults to off
and that no production caller passes — they have already been applied. A test
asserts a repairable row survives a default construction untouched.

Residual risk, accepted and to be recorded: additive DDL — including the
`hedge_open_leg` table rebuild — still runs on construction. Gating it would make
the database unopenable by design and is out of scope.

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
   site, deterministic, temp-SQLite only.
2. Only one implementation of the leg-exposure rule remains.
3. The §5 tripwire fails on a deliberately reintroduced coercion (the implementer
   demonstrates this, then reverts the probe).
4. Default `HedgeOpenStore` construction mutates no existing row.
5. Full `backend/tests` suite green (baseline: 1071 passed at `3113a5d`).
6. No network, credentials, service control, or write to `data/**` at any point.

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
