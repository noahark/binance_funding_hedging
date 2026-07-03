# Review-2 (stage-level, FINAL GATE) — public-market-impl-v1

You are Claude/Fable5 (claude-fable-5), acting as `reviewer_2` — the **final
review gate** — in **read-only** sandbox mode. Do not modify any file.

Stage: `2026-07-public-market-impl-v1` (Binance public-market snapshot
workstation, Phase 1, public data only). This is the implementation stage built
on the frozen, user-accepted contract stage `2026-07-public-market-contract-v2`.

You review the **whole stage implementation** (Task A backend + Task B frontend
+ Task C integration), not a single task. Review-1 (two task-level verdicts,
both ACCEPT) already ran; you may read those verdicts but you are NOT bound by
them — re-verify the material claims yourself.

## Disclosure: prior design/breakdown involvement (strong-reviewer override)

You (Claude/Fable5) are the **prior stage designer and development breakdown
author** for this implementation stage (`fable5-detail-breakdown.md`). You
therefore have **prior design/breakdown involvement**, not `none`.

You have **NO** implementation or fix-authorship involvement this stage:
- Task A backend implementer = `claude_glm` (glm-5.2[1m]).
- Task B frontend implementer = `kimi` (kimi-2.7).
- Task C integration = the stage controller (`claude_glm`), no product code.

You did not write any delivery code in this stage, so the review-2
implementer/fix-author hard ban is satisfied. Per AGENTS.md, because the primary
review-2 decision model (Codex/GPT) is unavailable (403 subscription not found /
402 payment required) and no other provider-unrelated decision model exists for
this stage, you review via the **strong-reviewer disclosure override**.

**You MUST set `reviewer_prior_involvement: "design_breakdown"`** and disclose
the above in `reviewer_prior_involvement_notes`.

Per AGENTS.md, treat the **user-approved direction synthesis, the PRD, and the
frozen contract** (`docs/api/public-market-contract.md`,
`schemas/api/public-market/snapshot.schema.json`, frozen samples) as the
**top-level requirements**. The Fable5 design/breakdown artifacts are **reviewed
evidence, not the highest authority** — if design and contract disagree, the
contract wins.

## Review subject (recompute this yourself — do not trust this summary)

The stage-level commit range:

- base_sha: `32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c` (`H_intake`)
- head_sha: `ce004892231db40bf5d8ebb39ac4a4e56d0703b4` (`H_C`)

Recompute the stage `diff_fingerprint` from a clean shell in the repo root:

```bash
git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..ce004892231db40bf5d8ebb39ac4a4e56d0703b4 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json' | shasum -a 256
```

Expected (recorded in `status.json.diff_fingerprint`):

```text
ce004892231db40bf5d8ebb39ac4a4e56d0703b4:7fdbbf17ec989f5da63d38e9b26a5aaff57fdfb2fd73564a0a1be06deb27ce0e
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

Also recompute and confirm the **task-level boundaries** (each task's diff must
contain only its owner's files; `status.json` excluded):

- Task A (`32f6f0f..a40b204`): expect `5148a473…1e93`, 21 files all under
  `backend/**` + the backend report + test-output.
- Task B (`fc018ea..c1e33b6`): expect `4bebeb52…6bde`, 4 files all under
  `frontend/**` + the frontend report.
- Task C (`c1e33b6..ce00489`): expect `378c91d7…3d5d`, stage summary +
  test-output Section 4 + integration sample + handoff; **no product code**.

Any cross-task leakage (backend file in Task B's diff, frontend file in Task A's
diff, product code in Task C's diff) is a P1 finding — return REWORK.

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-impl-v1/00-task.md` (scope, behavior rules, acceptance)
- `reports/agent-runs/2026-07-public-market-impl-v1/10-design.md`,
  `11-adr.md`, `fable5-detail-breakdown.md` (design/breakdown — evidence, not top authority)
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation.md` (stage summary),
  `20-implementation-backend.md`, `20-implementation-frontend.md`
- `reports/agent-runs/2026-07-public-market-impl-v1/30-review-1.md` (aggregate),
  `30-review-1-backend.md`, `30-review-1-frontend.md` (review-1 verdicts — scrutinize, don't trust)
- `reports/agent-runs/2026-07-public-market-impl-v1/60-test-output.txt` (raw test evidence)
- `reports/agent-runs/2026-07-public-market-impl-v1/status.json`
- `backend/**` (config, adapters/binance_public, domain/{classify,normalize,snapshot}, services/snapshot_service, app/server, tests/**)
- `frontend/index.html`, `frontend/self-check.js`, `frontend/fixture/public-market-snapshot.json`
- `schemas/api/public-market/snapshot.schema.json` (read-only contract / top authority)
- `docs/api/public-market-contract.md` (read-only contract / top authority)
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json` (frozen 6-symbol sample)
- The frozen stage diff:
  `git diff --binary 32f6f0f7e7a2406cc01e5364ef3557dbfcd2155c..ce004892231db40bf5d8ebb39ac4a4e56d0703b4 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'`

## What to verify (each is a checkpoint)

### A. Hard constraints (security/safety — any breach is REWORK)

1. **No API key, signed endpoint, private account endpoint, user data stream.**
   Grep the diff + `backend/**`: `grep -RniE 'apikey|api_key|secret|signature|userDataStream|listenKey|/sapi/|/dapi/v1/order|/fapi/v1/order' backend` (expect none functional).
2. **No order / borrow-action / repay / transfer / websocket.** The ONLY
   acceptable "borrow" string is the `PRIVATE_BORROW_VALIDATION_REQUIRED` enum
   rendered as a display badge. No websocket client anywhere.
3. **Read-only inputs untouched.** Confirm the stage diff does NOT modify
   `schemas/api/public-market/**`, `docs/api/public-market-contract.md`, or
   `reports/api-samples/public-market-contract-v2/**`. `git diff --name-only
   32f6f0f..ce00489` must not list any of those paths.
4. **Same-origin formal page.** The frontend default load fetches the relative
   `/api/public-market/snapshot`; the fixture is a manual offline fallback only,
   byte-identical to the frozen normalized sample.
5. **funding_history default top-N=20** unchanged.

### B. Contract alignment (contract > design when they disagree)

6. Backend output and frontend consumption both conform to
   `snapshot.schema.json` (decimal fields are strings; `funding_time`/`next_funding_time`
   int; enums for route_class/asset_tag/negative_funding_status).
7. The three contract warnings are preserved verbatim (margin unverified;
   `lastFundingRate` settled-vs-estimate ambiguity; BSTOCK no spot leg).
8. The 6 frozen curated symbols align on `(route_class, asset_tag, negative_funding_status)`.

### C. Backend behavior rules

9. Eligible filter (`status=="TRADING"` && `contractType in {PERPETUAL, TRADIFI_PERPETUAL}`); no leakage.
10. `asset_tag` (TRADIFI→BSTOCK, PERPETUAL→CRYPTO) independent of route_class.
11. `route_class` three-case rule; `margin_public.source == "unverified"` always.
12. `negative_funding_status` ordered priority (PERP_ONLY→DISABLED_PERP_ONLY
    beats BSTOCK→DISABLED_BSTOCK beats SPOT_ONLY→DISABLED_SPOT_ONLY beats
    default PRIVATE_BORROW_VALIDATION_REQUIRED). MSTR/TSLA → DISABLED_PERP_ONLY.
13. **Decimal discipline**: ranking via `Decimal`; decimal fields serialized as
    strings from raw JSON. `float()` must NOT appear on any price/rate/quantity
    path. `grep -RnE '\bfloat\(' backend --include='*.py'` (expect none outside tests).
14. `summary` aggregated FROM rows, never independently.
15. Validation gate: every served snapshot is jsonschema-validated; 503 on failure.

### D. Frontend rules

16. Same-origin default; fixture offline-only and byte-identical; no forbidden
    interaction; no planning-calculator / manual-open ticket / order button /
    account / position UI; row-count-agnostic rendering.

### E. Integration & test evidence

17. `60-test-output.txt` Section 4: backend HTTP `/api/public-market/snapshot`
    schema-valid (688 rows), frontend index served, contract aligned, data_time
    reproducible.
18. Re-run the suites yourself:
    - `.venv/bin/python -m pytest backend/tests -q` (expect 39 passed)
    - `.venv/bin/python backend/tests/smoke_server.py` (expect SMOKE OK; needs
      sandbox network disabled for loopback)
    - `node frontend/self-check.js` (expect 10 PASS)
19. Review-1 scrutiny: both review-1 verdicts are ACCEPT — confirm the material
    claims (fingerprints, boundaries, no forbidden interaction, decimal
    discipline) hold independently. Do not rubber-stamp.

### F. Known non-blocking residuals (carry forward, do not block)

- The **live HTTP path is not exercised this stage** (offline frozen fixtures).
  Live request counts / rate-limit headroom are design figures, not measured.
- The **server smoke is single-process** (sandbox blocks cross-process loopback).
- The **frontend is tested on the 6-row fixture**; the live endpoint serves 688
  rows. Rendering is row-count-agnostic; no pagination/virtualization yet.

If you find a genuine correctness/safety/boundary defect, return `REWORK` with a
`fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

You may read anything in the repository. You may NOT modify any file. You may
NOT be swayed by controller or review-1 narratives — recompute fingerprints and
re-check rules yourself against the raw code, the raw diff, and the frozen
contract.

## Output contract (strict)

Emit your review narrative, then a single JSON verdict object that validates
against `schemas/review-verdict.schema.json` (you are invoked with
`--output-schema`, so your final output must be that schema-valid JSON). Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-impl-v1`
- `role`: `second_reviewer`  *(if the schema enum requires `final_reviewer`,
  use that instead — read the schema and use the value it allows for review-2)*
- `model`: `claude-fable-5`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed **stage-level** value
  (`ce00489…03b4:<your sha256>`)
- `reviewer_prior_involvement`: **`design_breakdown`** (NOT none — you are the
  prior stage designer/breakdown author; disclose in notes)
- `reviewer_prior_involvement_notes`: disclose prior design/breakdown authorship
  (`fable5-detail-breakdown.md`), no implementation/fix authorship, Codex/GPT
  unavailable (403/402), strong-reviewer override invoked, hard ban satisfied.
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the live-HTTP / single-process-smoke / 6-vs-688-row notes
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries, forbidden paths, and the
exact post-fix commands (`pytest`, `smoke_server.py`, `node frontend/self-check.js`).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
