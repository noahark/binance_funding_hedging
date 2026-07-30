# Bookkeeper Verification — task1b-d5-repair

Verified 2026-07-30 by Opus 5 (Bookkeeper), by running the repaired detector, not
from the implementer's report.

Range `ad2c501..fa9d278`; implementation `851dd08`, ledger `fa9d278`.

**Verdict: VERIFIED.** All three findings repaired. One correction to my own
previous verification is recorded below — the implementer was right to contest an
acceptance check and I was wrong to write it.

---

## 1. The repair, independently confirmed

I ran the delivered detector over ten shapes of my own construction, plus the real
pre-fix trees. All ten behaved as the specification requires:

| Shape | Expected | Result |
|---|---|---|
| `avg_price = D.Decimal(x or "0")` — no `_num(` present | flag | flag ✓ |
| `quote = leg.get("cumulative_quote_amt", "0")` | flag | flag ✓ |
| `quote = _num(q) or "0"` (the line the old test exempted) | flag | flag ✓ |
| `b["spot_notional"] += q * _num(...)` — S2's shape | flag | flag ✓ |
| `self.avg_price = _num(v)` — attribute target | flag | flag ✓ |
| single-line `INSERT INTO … cumulative_quote_amt … '0'` (R3a) | flag | flag ✓ |
| `filled_qty = _num(leg_outcome.get("filled_qty"))` | silent | silent ✓ |
| `base = D.Decimal(leg.get("cumulative_base_qty") or "0")` | silent | silent ✓ |
| `price = _decimal_str(v, default=None)` | silent | silent ✓ |
| a `# money-zero-ok:` marked line | silent | silent ✓ |

Pre-fix `store.py` now yields six hits — `1336` (S1), **`1926` and `1930` (S2, the
finding)**, `1946` (the known blunt-rule false positive, R3b), `748` and `765`
(S4). S2 is visible; that was R2's whole point.

Current tree: **0 hits** across `store.py`, `service.py`, `domain.py` and
`services/live_hedge_executor.py`. The guard passes on the tree it guards without
the rule having been weakened to achieve it — verified by the fact that the ten
shapes above still fire.

| Check | Result |
|---|---|
| Full suite | **1090 passed**, 0 failed. The `p3-flaky-oversized-body-test` flake did not fire this run |
| File boundary | Only `test_hedge_purity.py`, `23-task1b-glm-result.md`, `status.json`. `store.py` untouched, as the implementer said and as the repair scope required |
| `status.json` | One line, `state: dispatched → reported` |

## 2. Correction — my V1 evidence was wrong, and the implementer was right to say so

`21-bookkeeper-verification.md` §2 V1 asserted, as the measured consequence of the
inverted pattern, that "the r6 defect category is not covered — 0 hits on pre-fix
`service.py`, which holds seven such sites". The repair dispatch then made a
non-empty hit list over that file an acceptance check.

Both were wrong, verified now:

- All seven `or "0"` sites in pre-fix `service.py` (`:214`, `:252`, `:253`, `:284`,
  `:310`, `:774`, `:775`) read `cumulative_base_qty` and assign to `base` /
  `spot_base` / `perp_base`. That is **quantity**, which D5 point 3 excludes from
  the money set by design and which Human's decision D-5 keeps out of scope.
- r6's actual money site was repaired last stage at `34ad0ca` (2026-07-29). This
  stage's baseline `c4ca4f4` already carries the correct
  `raw_quote = …; if raw_quote is None:` form at `:215-216`, `:285-286`, `:311-312`.
  The r6 defect **cannot** appear in this stage's pre-fix tree, so no detector could
  find it there.

My acceptance check was therefore satisfiable only by mis-flagging a quantity site
— i.e. by introducing a false positive to please a Bookkeeper. The implementer
refused, stated the disagreement objectively in its result, supplied alternative
proof (four synthetic shapes exercising the repaired rule), and did not silently
comply. **That is the correct behaviour and it is worth recording as such**, since
the cheaper path — quietly widening the money-name list until my check went green —
would have damaged the guard while producing exactly the evidence I asked for.

What survives of V1, unchanged: the code defect was real. `or "0"` and
`.get(…, "0")` were implemented as suppressors against a dispatch that named them
as patterns to flag, with a test asserting the inversion. It mattered
prospectively rather than retrospectively — the next money site written in that
shape would have passed silently — and it is now fixed. My finding was right; the
consequence I attached to it was not.

V2 (S2 invisible) needed no correction: it was reproduced on the real pre-fix tree
before and after, and is now covered.

## 3. R3 disposition

- **R3a fixed**: the SQL anchor now starts at the `'0'` line itself, so a
  single-line `INSERT` is caught. Confirmed by my own probe.
- **R3b left in place with a stated reason**: the detector still flags the
  already-correct `None if quote_raw is None else _num(quote_raw)` form. That form
  no longer exists in the tree (D2 replaced it with `_num_or_none`), so the false
  positive is inert today. Accepted — a blunt rule with a visible allow-list is what
  the dispatch asked for, and narrowing it further would risk the R1 hole reopening.

## 4. Sealed for review-1

`delivery_sha = 851dd08` — the last implementation commit, not the ledger commit
that follows it (`roles.md:258-259`).

Review-1 routes to Grok 4.5 (`xai`), Human-approved fallback under D-2 because
Kimi's quota has not recovered. Provider isolation from the implementer
(`zhipu_glm`) holds. Packet: `30-review-1-grok45.dispatch.md`.
