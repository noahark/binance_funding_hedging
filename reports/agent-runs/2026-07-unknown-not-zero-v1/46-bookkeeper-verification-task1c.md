# Bookkeeper Verification — task1c-f2-settlement-visibility

Verified 2026-07-30 by Opus 5 (Bookkeeper) by reading the diff, running the suite,
and **mutation-testing the fix**. Nothing taken from the implementer's report.

GLM range `be789d6..e865011`; implementation `7cadb88`, ledger `e865011`.

**Verdict: VERIFIED.** F2 is repaired at both sites, the tests genuinely bite, and
no forbidden file or product semantics were touched.

## 1. The fix

Both bare `except Exception: pass` sites now call a new
`_record_settlement_failure` (`service.py:1256-1290`), which writes a
`settlement_failed` event through the existing `record_task_event` channel with a
payload of exactly `{attempt_id, error_type, error}`.

| Requirement | Result | Evidence |
|---|---|---|
| R1 — stop discarding, operator-visible | PASS | `service.py:1205-1210` (drain) and `:1242-1247` (crash-gap). Existing event channel, no new table or API field |
| R2 — worker survives; recording cannot become the new failure | PASS | Still catches at both sites. The inner guard (`:1285-1290`) wraps **only** the audit write, with a comment saying so — not a second blanket guard around business logic |
| R3 — no new product semantics | PASS | `grep -rn settlement_failed backend/ frontend/ schemas/` → one non-test occurrence, the event kind itself (`service.py:1271`). `git diff` over `frontend/` and `schemas/` is empty. No new pause reason, status, or operator copy |
| `ts_us <= 0` raise preserved | PASS | `domain.py:1039` unchanged; the 1970 behaviour was not restored |
| Payload carries no secrets | PASS | Three keys only, asserted by the test as `set(payload) <= {...}` |
| Scope | PASS | GLM touched `service.py`, `test_hedge_task_local.py`, its result file, and `status.json` (one field). Nothing forbidden |

`task_id` is a parameter of `_recover_crash_gaps` (`service.py:1220`), so the
crash-gap call site resolves — a plausible `NameError` that a review might have
assumed rather than checked.

## 2. Mutation testing — the tests actually bite

The implementer's report explained why the drain test asserts `len(events) >= 2`
("fixing only one site would leave 1"). Rather than accept that reasoning, I
reverted each site in turn and ran the tests:

| Mutation | Result |
|---|---|
| Revert **drain** site to `except: pass` | `test_drain_settlement_failure_is_recorded_not_swallowed` **FAILS** at the assertion; the crash-gap test still passes (correct isolation) |
| Revert **crash-gap** site to `except: pass` | **BOTH** tests fail — the drain test's `>= 2` requires both sites, exactly as the report claimed |

Tree restored to `7cadb88` after each mutation; `git status` clean.

So the `>=` assertions are weaker than `==` but are sufficient: each site is
individually load-bearing for at least one test. Verified rather than argued.

The tests drive the **real service path** (`svc._pump_worker`) with an injected
zero clock (`_live_svc(..., clock=_Clock(0))`), and assert the four things the
dispatch required: the exception does not escape, an event names the `ts_us`
failure, the worker continues to the next round, and `pair_outcome is None` — the
attempt stays unsettled, with the comment "still unsettled — no fabrication". That
last one matters: a tidier test would have fabricated a settlement.

## 3. Test suite, measured independently

```text
1092 passed in 51.82s
```

Baseline 1090 + 2 new. The `p3-flaky-oversized-body-test` flake did not fire.

## 4. Negative result, stated as a negative

`service.py` still contains three bare `except Exception: pass` blocks
(`:995`, `:1024`, `:1062`) plus one at `:1401` carrying a `pragma: no cover`. I
checked each rather than assuming they were the same defect: **all three wrap
`set_worker_exit_reason`**, a best-effort audit write, and `:1024`'s sits inside
the worker's last-resort containment whose own comment states the durable state is
authoritative.

That is the same *legitimate* shape as the new inner guard — narrow, around an
audit write only — not the F2 shape of a blanket guard around business logic. So
the F2 defect class is clear in `service.py`. 查过且没有, not 没查.

## 5. Route

`AGENTS.md:181` — this repair touches `service.py`, forbidden in the reviewed
range, so it re-enters **review-1** (Grok 4.5, cross-provider vs `zhipu_glm`) and
then returns to **review-2** (Codex, disclosure per D-6).

New delivery range for both reviews:

```text
base_sha     ac8d493a903051394fc9fda3ca467590a6e2f837
delivery_sha 7cadb88da501cc024a8f15fd5de067ee80679c07
```

`rework_count` stays **1** — this is the repair of that round's findings, not a new
round. It advances to 2 only if a reviewer returns `REWORK` again.

Both review packets are narrowed to the F2 change plus regression integrity;
everything already settled is carried forward as do-not-re-litigate, including
F1's exclusion by decision D-8 and F3 being already corrected.
