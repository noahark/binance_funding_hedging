# Review-1 (task-level) on Task A — Backend Snapshot Service

You are Kimi (`kimi-2.7`), acting as `reviewer_1` with the `code_reviewer`
skill, in **read-only / plan mode**. Do not modify any files.

Stage: `2026-07-public-market-impl-v1` (Binance public-market snapshot
workstation, Phase 1, public data only). You are reviewing **Task A only**
(the backend snapshot service). A separate review-1 covers Task B (frontend);
do not opine on frontend files.

## Review subject (recompute this yourself — do not trust this summary)

Task A is a single owner-scoped commit range:

- base_sha: `32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c` (`H_intake`, the task base)
- head_sha: `a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72` (`H_A`)

Recompute the fingerprint yourself from a clean shell in the repository root:

```bash
git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json' | shasum -a 256
```

The expected `diff_fingerprint` recorded in `status.json.tasks.A` is:

```text
a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72:5148a4734c59cdd4c50e8388464a0b7867d772f8b61054c8eb82a173263d1e93
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

Confirm the diff contains only Task-A files (21 expected: 19 under `backend/**`
plus `20-implementation-backend.md` and `60-test-output.txt`):

```bash
git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72 --name-only -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'
```

If any frontend, schema, doc, or raw-sample path appears, return REWORK with a
P1 finding (boundary crossing).

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-impl-v1/00-task.md` (Task A scope, behavior rules, acceptance)
- `reports/agent-runs/2026-07-public-market-impl-v1/10-design.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/11-adr.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-impl-v1/status.json`
- `backend/config.py`, `backend/adapters/binance_public.py`,
  `backend/domain/{classify,normalize,snapshot}.py`,
  `backend/services/snapshot_service.py`, `backend/app/server.py`,
  `backend/tests/**`
- `schemas/api/public-market/snapshot.schema.json` (read-only contract)
- `docs/api/public-market-contract.md` (read-only contract)
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json` (frozen 6-symbol sample)
- The frozen diff:
  `git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..a40b204658cfbe6df2cdeeee27ec5fc8f2bd4d72 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'`

## What to verify (Task A behavior rules — each is a checkpoint)

1. **Eligible filter**: only `status=="TRADING"` and `contractType in
   {PERPETUAL, TRADIFI_PERPETUAL}` become rows. No non-TRADING / non-perpetual
   leakage (`test_no_non_trading_or_non_perpetual_leakage`).
2. **asset_tag**: TRADIFI_PERPETUAL→BSTOCK, PERPETUAL→CRYPTO; independent of
   route_class. The 6 frozen curated symbols match
   `(route_class, asset_tag, negative_funding_status)` exactly
   (`test_classification_matches_frozen_six`).
3. **route_class**: spot+`isMarginTradingAllowed`→MARGIN_SPOT_CANDIDATE; spot
   no-margin→SPOT_ONLY_CANDIDATE; no spot→PERP_ONLY_EXCLUDED.
   `margin_public.source` is always `"unverified"`.
4. **negative_funding_status priority**: explicit ordered sequence
   PERP_ONLY→DISABLED_PERP_ONLY, BSTOCK→DISABLED_BSTOCK,
   SPOT_ONLY→DISABLED_SPOT_ONLY, default→PRIVATE_BORROW_VALIDATION_REQUIRED.
   Order is not interchangeable. MSTR/TSLA (PERP_ONLY+BSTOCK) must resolve to
   DISABLED_PERP_ONLY (priority 1 wins over 2).
5. **Decimal discipline**: ranking uses `Decimal`; every decimal field
   serialized as a string straight from raw JSON. `float()` must not appear on
   any price/rate/quantity path. Run:
   `grep -RnE '\bfloat\(' backend --include='*.py'` (expect none outside tests).
6. **funding_history top-N**: default N=20 (must not be changed). Top-N bounds
   LIVE `/fapi/v1/fundingRate` volume; offline uses all frozen fixtures. The
   default-20 is design-confirmed.
7. **summary == aggregation over rows**: counts computed FROM rows, never
   independently (`test_summary_aggregates_from_rows`).
8. **Three contract warnings** preserved verbatim (margin unverified;
   `lastFundingRate` settled-vs-estimate ambiguity; BSTOCK no spot leg).
9. **Validation gate**: every served snapshot is jsonschema-validated; on
   failure the server returns 503 (never serves invalid).
10. **Reproducible offline output**: `data_time` matches the frozen sample
    (`2026-07-03T05:11:29Z`); the 6 curated symbols align.
11. Re-run the test suite yourself if you can:
    `.venv/bin/python -m pytest backend/tests -q` (expect 39 passed) and
    `.venv/bin/python backend/tests/smoke_server.py` (expect SMOKE OK; this
    needs the sandbox network disabled for loopback).

## Known non-blocking residuals (carry forward, do not block)

- The **live HTTP path is not exercised this stage** — all tests and the smoke
  are offline against frozen fixtures. Live request counts / rate-limit
  headroom (≈23 calls/refresh, <1% of weight ceilings) are design figures from
  public docs + the top-N design, not measured. This is an accepted limitation
  for an offline-tested implementation stage, not a defect.
- The **server smoke is single-process** (background thread + same-process
  urllib) because the Harness sandbox blocks cross-process loopback TCP. It
  exercises the real handler and socket; this is an environment constraint.

If you find a genuine correctness/safety defect (e.g. float on a decimal path,
wrong classification priority, summary drift, boundary crossing, a served
invalid snapshot), return `REWORK` with a `fix_start_prompt`. Otherwise return
`ACCEPT`.

## Boundary (read-only)

You may read anything in the repository. You may NOT modify any file. You may
NOT be swayed by the controller's narrative — recompute the fingerprint and
re-check the behavior rules yourself against the raw code and the frozen
samples.

## Output contract (strict)

Write your review to `30-review-1-backend.md` and end your reply with a single
JSON verdict object that validates against `schemas/review-verdict.schema.json`.
Read that schema. Use exactly:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-impl-v1`
- `role`: `first_reviewer`
- `model`: `kimi-2.7`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED` if you cannot decide)
- `diff_fingerprint`: your recomputed Task-A value
- `reviewer_prior_involvement`: `none` (you did not design, synthesize, or break
  down this stage; you are the cross-task reviewer. Note: you are the Task B
  implementer in this same stage, but you had no involvement in Task A's
  design/breakdown/direction — disclose this in
  `reviewer_prior_involvement_notes`.)
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the live-HTTP and single-process-smoke notes above
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries (`backend/**` + the
backend report only), forbidden paths, and the exact commands to run after the
fix (pytest + smoke).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
