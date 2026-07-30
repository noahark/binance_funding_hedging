# Audit Result — discarded failures, and the scope decision it forces

Codex (`openai`), read-only, transferred by the Human operator 2026-07-30 20:20 CST
against `70-exception-swallow-audit-codex.dispatch.md`. `评审结论: REWORK`, no files
modified, 55 targeted tests passed.

Format compliance: PASS. `rework_count` stays **2 of 3** — an audit is not a repair
round.

## The closed list

**8 class-(A) sites** (order / money / task-continuability), of which **2 are
already fixed and kept as the template**, **6 remain**, and **3 balance sites are
D-8-excluded**.

| Site | Discarded | Post-POST | Status |
|---|---|---|---|
| `service.py:1141` | inconclusive query → `continue` | yes | **unfixed** |
| `service.py:1178` | `resolve_leg_from_query` write → `continue` | yes | **unfixed** |
| `service.py:1205` | drain settlement | yes | fixed (F2) — template |
| `service.py:1242` | crash-gap settlement | yes | fixed (F2) — template |
| `service.py:1632` | dry-run `resolve_attempt` | **no** | **unfixed** |
| `service.py:1723` | `mark_attempt_rate_limited` | yes | **unfixed** |
| `service.py:1736` | pause-class `resolve_attempt` | yes | **unfixed** |
| `service.py:1758` | normal `resolve_attempt` | yes | **unfixed** |
| `service.py:1780` | `mark_leg_querying` | yes | **unfixed** |
| `live_hedge_executor.py:690-702` | send-thread exception reason | maybe | **unfixed** |
| `hedge_preflight_provider.py:263/267/270` | malformed balance row | no | D-8 excluded |

Class (B) — audit-only, correct as they are: `service.py:995/1024/1062` (worker exit
reason), `:1279` (F2's own guard), `:1811-1819` (`raw_persist_failed`).
Class (C) — deliberate degradation with a reason: `scheduler.py:48/52`,
`service.py:1401/1410/1628`, `store.py:479`, plus ~30 sites across `domain.py`,
`wire_constraints.py`, `executor.py`, `live_hedge_executor.py`,
`hedge_open_live_client.py`, `hedge_preflight_provider.py` that preserve the raw
result or return an incomplete state and end in an input error, an unknown value, or
a fail-closed preflight.

A5 discrepancy, both directions: of my 14 sites, **8 were misclassified by me** as
candidates (they are (B) or (C)); **6 were correctly (A)**; and Codex added **two**
I could not have found plus the three D-8 ones.

## Bookkeeper verification of the new claims

| Claim | Verdict | Evidence |
|---|---|---|
| `:1141` inconclusive query silently continues | **CONFIRMED, but not new** | `service.py:1141` — `if verdict is None: continue  # inconclusive — keep querying`. This is the previous stage's **already-deferred** follow-up `p1-inconclusive-query-raw-not-persisted`, deferred by Human scope decision on 2026-07-28. Codex re-found a known item, which is worth knowing when scoping it |
| `live_hedge_executor.py:690-702` loses the send-thread exception reason | **CONFIRMED, starkly** | `_run` catches `Exception as exc` and stores it in `errors[leg]`; `_error_leg(leg, errors.get(leg))` then **takes `exc` as a parameter and never uses it** (`:731-742`). The reason is dropped entirely and the leg becomes `UNKNOWN_QUERYING` with no `error_code`/`error_category`. An unused parameter in the signature makes this unarguable |
| `settlement_failed` is not on the `entries` timeline | **CONFIRMED** | `_ENTRY_EVENT_KINDS` (`service.py:61-67`) holds only `task_stopped`, `threshold_paused`, `task_paused`, `preflight_incomplete`, `rate_limited`. F2's event reaches the logs list but not the unified timeline |

### A correction to my own F2 verification

`46-bookkeeper-verification-task1c.md` called F2's fix "operator-visible" on the
grounds that it uses "the existing `record_task_event` channel the logs page already
reads". True as far as it goes — but I did not check `_ENTRY_EVENT_KINDS`, so I did
not know the event is absent from the `entries` timeline. Visible on the logs page,
absent from the timeline. Stated now rather than left implied.

### Why my own sweep could not have found the third shape

`690-702` is neither `except: pass` nor `except: continue` — it is "catch, convert to
a state, drop the reason". My regex family could not match it by construction. This
is direct support for Codex's A4 conclusion below.

## A4 — no reliable static guard, and I agree

Codex declined to propose a guard as a defence: one could flag
`except … pass/continue` directly wrapping a `self._store` state write, but it
cannot see `verdict is None`, a thread-exception conversion, a wrapper function, an
alias, or a set-flag-then-return:

```python
try:
    persist_state()
except Exception:
    deferred = True
if deferred:
    return
```

Its recommendation — a closed list plus per-class fault-injection tests plus cross
review, with a static check only as a reminder — is the right answer, and it is more
useful than the money-zero guard, which this stage's own author evaded four times.
A reasoned "no" was explicitly allowed by the packet and was the correct use of it.

## Human decision required — repair scope

`rework_count` is **2 of 3**. One formal round remains. That constrains what can
safely be attempted here.

The six unfixed sites are **not homogeneous**:

- **Five are one uniform change**: `:1178`, `:1723`, `:1736`, `:1758`, `:1780` — all
  are a swallowed `self._store.*` state write on the post-POST path, all fixable with
  the template F2 already established and reviewed twice (record the existing task
  event, do not fabricate a conclusion, do not resend, let the next round recover).
  Codex's own minimum-repair item 1 groups exactly these.
- **Three each need their own design decision**:
  - `:1141` needs a log-rate design ("避免每轮查询都刷日志") and was already
    Human-deferred once as `p1-inconclusive-query-raw-not-persisted`.
  - `:1632` is the dry-run path — **no order is placed** — so it is the lowest-risk
    of the eight, and its fix is about not leaving a PREPARED attempt forever.
  - `690-702` requires changing the internal `LegDispatch` data contract, which
    Codex itself says needs normal cross review.
- **Plus one product-semantics question**: should these events appear on the
  `entries` timeline, not only the logs page? That is operator-interface meaning and
  is Human's to decide, not an implementer's.

### Bookkeeper recommendation

**Repair the five uniform post-POST sites in this stage. Give the other three plus
the timeline question their own stage, with this audit as its ready-made plan.**

Reasoning:

1. The five are the highest-risk set (a real order with no recorded conclusion) and
   the cheapest to get right — one shape, one template, already reviewed twice.
2. The other three are three separate design problems. Folding them in would spend
   the last rework round on a widened scope containing a data-contract change and an
   unresolved UI question — which is how the previous stage reached round seven.
3. This is **not** the point-fixing that was just criticised. That criticism was
   fixing whichever sites a reviewer named while the full set was unknown. The full
   set is now enumerated and classified, and what is deferred is deferred with a
   named reason. Scoping from a closed list is the opposite of whack-a-mole, and this
   file is the record that proves which one happened.

The alternative — fix all six plus the contract change here — is defensible if Human
prefers one pass over two, accepting that the last rework round is spent on a wider
change and that `AGENTS.md:182` then routes any further finding to a Human choice of
narrow / redesign / accept / stop.

Either way: **`:1141`, `:1632`, `690-702` and the timeline question must not be
silently dropped.** Whatever is not repaired here goes to `PROJECT_STATE.md` at stage
close as an open item with this file as its evidence.
