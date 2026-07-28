# R4 Boundary Reconciliation — `backend`

Performed by the bookkeeper, 2026-07-28, on the range
`ecc3841..HEAD` of `stage/2026-07-hedge-order-truth-v1`.

**Verdict: PASS on all nine planned checks**, with one bookkeeper error found
and recorded below (§Errata). The error is in the commit *history*, not in the
delivered code.

## Errata — the bookkeeper committed the implementer's work by accident

**What happened.** Three bookkeeping commits swept up the implementer's
in-progress delivery code, because the bookkeeper ran `git add -A` while a
Claude-GLM session was concurrently writing to the same worktree:

| Commit | Message describes | Actually also contains |
| --- | --- | --- |
| `5aceca9` | recording the context-budget incident | 3 backend files, +179/−42 |
| `8bd03e8` | recording the reading-scope harness gap | 8 backend files, +869/−73 |
| `ca3cf1f` | dispatching the harness fix to codex | 7 backend files, +687/−60, **plus `20-implementation.md` and `60-test-output.txt`** |

**This is the bookkeeper's error, not the implementer's.** The implementer's
report states 「未 commit」 and that is true — it never committed. The bookkeeper
did, three times, without noticing.

**It explains the implementer's headline finding.** The report says W1/W2/W3
「在基线之前已实现」 and that this stage's real work was only W4+W5+W6. That
conclusion is **wrong**, but the observation behind it was **correct and
well-reported**: diffing against `HEAD`, the implementer genuinely saw its own
earlier W1–W3 work already committed, because the bookkeeper had committed it
minutes earlier under a docs message. The implementer flagged it as a risk for
the bookkeeper to check rather than quietly assuming — that is exactly the right
behaviour, and it is what surfaced this error.

**Consequences, and what is NOT affected:**

- The delivered code is complete and correct in the range. `git status` is clean,
  so `HEAD`'s tree is the implementer's final state; nothing was lost or
  truncated mid-write.
- The `diff_fingerprint` is computed over `base_sha..head_sha`, so how the
  intermediate commits sliced the work does not affect it.
- Reviewers are required by AGENTS.md to use the status-recorded
  `<base_sha>..<head_sha>` range and never a moving `HEAD`, so they will see the
  complete delivery diff regardless of the misleading intermediate messages.
- What *is* damaged is the readability and honesty of the history: three commit
  messages describe bookkeeping and silently carry hedge implementation.

**Decision: history is not rewritten.** Rewriting would invalidate shas already
recorded in `status.json` and cited in later commit messages (`acfccbd`,
`9e50228`, …), and the harness treats committed state as evidence. This errata
is the correction of record instead, and both review packets must carry it so a
reviewer reading commit-by-commit is not misled.

**Harness follow-up filed**: `bookkeeper-add-all-during-live-implementer`.

## Two implementer statements corrected

1. **§0 "key finding"** — W1/W2/W3 did not predate the baseline. They are this
   stage's work; the bookkeeper committed them early. Verified: at `ecc3841`,
   `domain.py` had all-negative code tables and no `collateral_cap`, and
   `service.py` passed a hardcoded `0` to `build_leg_exposure`. Those were the
   defects; they cannot have been fixed before the baseline.
2. **T2(c) verdict-change list** — the report states 「本阶段未改
   classify_exchange_code … 零变化」 and therefore omits the required list. That
   premise is the same artifact. The list is reconstructed by the bookkeeper from
   the range diff:

| Code | Product | Before (`ecc3841`) | After | Direction |
| --- | --- | --- | --- | --- |
| `51169` | margin | unlisted → non-fatal counter, `error_category` NULL | `collateral_cap` → task-local pause, `pause_reason=collateral_cap_full` | **stricter** |
| every negative code | both | (unchanged) | (unchanged) | none |

Recorded-value change that is **not** a verdict change: a business code matching
no rule now records `error_category="unclassified"` instead of NULL. Control flow
is identical to today's default branch (known non-fatal, counted); the value is
recorded so an unrecognised code stops being indistinguishable from a recognised
one. Locked by `test_classify_negative_codes_keep_verdict_on_both_products`.

## The nine planned checks

Planned in `17-context-guard-note.md` **before** the evidence arrived, so the
verification could not be steered by the report's narrative.

| # | Check | Result |
| --- | --- | --- |
| 1 | No forbidden path touched | **PASS** — 0 hits across `hedge_open_live_client.py`, `binance_signing.py`, `wire_constraints.py`, `scheduler.py`, `server.py`, `config.py`, `test_hedge_purity.py`, `test_hedge_open_live_client.py`, `frontend/`, `schemas/`, `scripts/`, `docs/`, `data/` |
| 2 | Frozen Chinese copy byte-identical + asserted verbatim | **PASS** — `domain.py` `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE` matches `10-design.md` §2(d) character for character, including the segment breaks; `test_hedge_domain.py` asserts it verbatim with `{asset}`→`NOM` |
| 3 | `51169` → `collateral_cap`, `insufficient_margin` off its path | **PASS** — `MARGIN_BUSINESS_CODES = {"51169": ERROR_CATEGORY_COLLATERAL_CAP}`; `insufficient_margin` survives only as the unrelated pre-existing constant and in comments forbidding its use here |
| 4 | Roll-up priority includes `collateral_cap` in position | **PASS** — `fatal 6 > auth 5 > collateral_cap 4 > insufficient_funds 3 > unclassified 2 > absent 1`, exactly §2(e) |
| 5 | No path can still store a fabricated `"0"` | **PASS** — `FILL_FIGURES_SOURCE` is an explicit per-product table; `_quote_decimal` returns `None` for missing and never coerces; UM POST quote is hard `None`; store's `_leg_final_fields` implements the NULL contract and the old `not in (None,"","0",0)` check that treated a literal `"0"` as absent is gone; migration M1 converts the existing fake `0` row to NULL. `executed_qty` deliberately keeps its `"0"` default, justified in-code: an accepted-but-unfilled leg genuinely has zero executed quantity — a true value, not a substituted one. Accepted. |
| 6 | T5 regression drives the **live** path | **PASS** — `test_4d_live_single_leg_exposure_timestamp_is_settlement_wall_clock` runs through `_live_svc`/`_step` into `service._dispatch_to_outcome`, asserts `ts == us_to_iso(settled_ts)` and explicitly `!= "1970-01-01T00:00:00.000000Z"`; its docstring states why an `executor.py`-only test would not satisfy T5 |
| 7 | Negative-code regression matrix exists and covers what it claims | **PASS** — `test_classify_negative_codes_keep_verdict_on_both_products`, parametrized across both products |
| 8 | Production database untouched | **PASS** — `data/` is gitignored so it could never be committed; substantively unchanged vs the intake capture: `start_gate=1`, `version=4`, 5 task rows, 4 leg rows. The file mtime moved because the live service (PID 96409) is running, not because an agent wrote to it. |
| 9 | Implementer did not commit; `status.json` / `70-handoff.md` untouched by it | **PASS on the implementer's part** — it committed nothing and edited neither file. Both files differ from base only through the bookkeeper's own edits. See §Errata for who did commit. |

## Independent test verification

Not accepted on the report's word. The bookkeeper re-ran the full suite on the
delivered tree:

```text
.venv/bin/python -m pytest backend/tests -q
1061 passed in 50.47s
```

Matches the report's claim of 1061. The specified sub-suite's 316 is a subset of
this run.

## Safety

No order placed, no card created, no Start toggled, no credentials touched, no
service started or stopped, no production-database write. The live surface is
unchanged from intake: service PID 96409 still running, `start_gate` still `1`,
the naked SHORT 10000 NOMUSDT still outstanding.

## Outstanding, carried into review

- **W0 has not been done.** T1's core assumption — that the order-detail GET
  still carries `cumQuote`/`avgPrice` — remains **unverified**. The
  implementation is built to the documented shape with the NULL representation as
  the backstop, and says so. Reviewers must treat it as an assumption, not a
  fact.
- Residual **R-1** (`10-design.md` §0 still describes the cancelled T4
  experiment) and **R-2** (ADR numbers are topic-sequential, so T2's ADR is
  `ADR-T3`) still apply and belong in both review packets.
