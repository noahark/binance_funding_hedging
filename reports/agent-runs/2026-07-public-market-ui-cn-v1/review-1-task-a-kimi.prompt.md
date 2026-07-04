# Review-1 (task-level) on Task A — lastFundingRate warning semantic amendment

You are Kimi (`kimi-2.7`), acting as `reviewer_1` with the `code_reviewer`
skill, in **read-only / plan mode**. Do not modify any files.

Stage: `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation; this stage is a contract-warning wording amendment + frontend
display polish; public data only, offline). You are reviewing **Task A only**
(the backend `CONTRACT_WARNINGS[1]` wording amendment + contract-doc paragraph +
tests). A separate review-1 covers Task B (frontend); do not opine on frontend
files.

## Review subject (recompute this yourself — do not trust this summary)

Task A is an owner-scoped commit. The task-level fingerprint recorded in
`status.json.tasks.A` uses base `b84a342` (H_intake base) and head `dba4c12`
(H_A). Recompute it yourself from a clean shell in the repository root:

```bash
git diff --binary b84a34235aa5b37bb0ce83f23ac35e4e5e686899..dba4c12ce61745ef393142af2255a3fc519bf4eb -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Expected `diff_fingerprint` (status.json.tasks.A):

```text
dba4c12ce61745ef393142af2255a3fc519bf4eb:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

## Two scope layers in the b84a342..dba4c12 range (read carefully)

`b84a342..dba4c12` spans two physical commits:

1. `d3d6e7c` (H_intake part 2) — `controller-start-prompt.md` +
   `task-b-kimi-frontend.prompt.md`. These are **intake/design dispatch prompts**
   (Fable5-prewritten), NOT Task A product code. They are recorded in
   `status.json.diff_fingerprint_note` as legitimate intake/design scope riding
   the stage diff. Do NOT treat them as Task A output and do NOT block on them.
2. `dba4c12` (H_A) — Task A's actual product + report files.

Task A's true scope is the single commit `dba4c12` (its parent is `d3d6e7c`):

```bash
git show --name-only --format= dba4c12
```

Expected (4 files): `backend/domain/snapshot.py`,
`backend/tests/test_snapshot.py`, `docs/api/public-market-contract.md`,
`reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-backend.md`.

If `dba4c12` touches anything else (frontend, schemas, classify/normalize/
snapshot_service, adapters, api-samples, agents/workflows/scripts), return REWORK
with a P1 boundary-crossing finding.

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-ui-cn-v1/00-task.md` (Task A scope, deliverables, acceptance — authoritative)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/10-design.md` (warning semantic intent)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/11-adr.md` (ADR-2: wording amended in lockstep)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-backend.md` (Task A report)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/60-test-output.txt` (rows-baseline check vs 548ae0d)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json`
- `backend/domain/snapshot.py` (CONTRACT_WARNINGS, build_rows, assemble_snapshot)
- `backend/tests/test_snapshot.py`
- `docs/api/public-market-contract.md` (lastFundingRate paragraph + Open Verification Items)
- `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/` (the live evidence the new wording cites; `evidence-index.md` sha256 + `verify-funding-semantics.py` PASS)
- The frozen Task-A product diff:
  `git diff --binary d3d6e7c..dba4c12` (product + report only, excludes the intake prompts)

## What to verify (Task A — each is a checkpoint)

1. **snapshot.py: single string change only.** `CONTRACT_WARNINGS[1]` is the ONLY
   change in snapshot.py. `build_rows`, `assemble_snapshot`, every other constant
   and function are byte-identical to the base. Confirm:
   `git diff d3d6e7c..dba4c12 -- backend/domain/snapshot.py` is exactly one
   `-`/`+` line pair (the warnings[1] string). Any logic change → REWORK.
2. **warnings[1] wording matches `00-task.md:51-57` verbatim** (English,
   contract-layer language): "premiumIndex.lastFundingRate is the real-time
   estimate for the CURRENT funding period and is charged at nextFundingTime;
   it drifts until settlement (mid-period divergence from settled history
   evidenced under reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/).
   Settled history comes from /fapi/v1/fundingRate; do not present the estimate
   as a settled value." The cited evidence path must match the actual capture dir.
3. **rows / API payload otherwise frozen.** The change is a constant string in a
   warnings list. Confirm `build_rows`/`assemble_snapshot` are untouched
   (checkpoint 1) so no row can have changed. Task C asserts rows are
   field-identical to the accepted `548ae0d` build (647==647, only warnings[1]
   differs); you may re-verify independently. Any rows drift → P0, REWORK.
4. **contract doc in lockstep.** `docs/api/public-market-contract.md`: the
   lastFundingRate funding-semantics paragraph is revised to the evidenced
   wording (citing the same evidence path), and the Open Verification Items entry
   for lastFundingRate semantics moves PARTIALLY RESOLVED → RESOLVED (citing
   `verify-funding-semantics.py` PASS). Other doc content unchanged. Confirm
   `git diff d3d6e7c..dba4c12 -- docs/api/public-market-contract.md` touches ONLY
   those two spots.
5. **Forbidden files untouched this stage.** Confirm:
   `git diff b84a342..dba4c12 -- backend/domain/classify.py backend/domain/normalize.py backend/services backend/adapters schemas/` is empty. Any hit → REWORK (boundary crossing).
6. **tests: assertion-only, no logic change.** `test_snapshot.py` adds assertions
   that warnings[1] contains "real-time estimate" and the evidence-path keyword;
   test count and all logic tests unchanged. Run:
   `.venv/bin/python -m pytest backend/tests -q` (expect 54 passed).
7. **No live HTTP / decimal discipline.** Offline-only; evidence captured at
   intake. `float(` audit clean:
   `grep -RnE '\bfloat\(' backend/domain backend/services` (expect none).

## Known non-blocking residuals (carry forward, do not block)

- The lastFundingRate evidence capture (`reports/api-samples/.../20260704T044945Z/`)
  is a single mid-period snapshot proving divergence + 15-min drift; it is
  read-only intake evidence, not re-fetched this stage.

If you find a genuine defect (snapshot.py has any change beyond the warnings[1]
string; wording diverges from 00-task.md; rows drift; contract doc out of sync;
forbidden file touched; boundary crossing), return `REWORK` with a
`fix_start_prompt`. Otherwise return `ACCEPT`.

## Disclosure: same stage, different task

You (Kimi) are the Task B implementer in this same stage, but you had no
involvement in Task A's design/breakdown/direction/implementation. Record
`reviewer_prior_involvement: "none"` and disclose the same-stage Task B
implementer fact in `reviewer_prior_involvement_notes`.

## Boundary (read-only)

You may read anything in the repository. You may NOT modify any file. You may
NOT be swayed by the controller's narrative — recompute the fingerprint and
re-check the rules yourself against the raw code and the evidence capture.

## Output contract (strict)

Write your review to `reports/agent-runs/2026-07-public-market-ui-cn-v1/30-review-1-backend.md` and end your reply with a single
JSON verdict object that validates against `schemas/review-verdict.schema.json`.
Read that schema. Use exactly:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `first_reviewer`
- `model`: `kimi-2.7`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED` if you cannot decide)
- `diff_fingerprint`: your recomputed Task-A value
- `reviewer_prior_involvement`: `none`
- `reviewer_prior_involvement_notes`: disclose you are the same-stage Task B implementer (Kimi), with no Task A design/breakdown/direction/implementation involvement.
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the single-snapshot-evidence note above
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries (`backend/domain/snapshot.py`
+ `docs/api/public-market-contract.md` + `backend/tests/**` + the backend report
only), forbidden paths, and the exact commands to run after the fix (pytest +
float audit).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
