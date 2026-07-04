# Review-1 (stage-level summary) — rework round 1 — 2026-07-public-market-ui-cn-v1

- **Stage**: `2026-07-public-market-ui-cn-v1`
- **Aggregate verdict (round 1)**: **ACCEPT** (`both_tasks_ACCEPT`, zero rework)
- **Stage diff_fingerprint** (bound): `7592b2c740975dc0a6ad2a4b3a17d5a8474494ff:4b8c8de25458e88a9dd8d5f8ab03db0f563305c59492fae548d69683978c4608`
- **Date**: 2026-07-04 CST (rework round 1/3)

## Round history

- **Round 0** (head `9b0e62c`): both tasks ACCEPT (Kimi→Task A; fresh GLM→Task B with 1
  non-blocking P3). Round-0 verdicts preserved verbatim under `status.json.review_1_round0`
  and in `30-review-1-backend.md` / `30-review-1-frontend.md`. Round 0 reached
  `stage_accepted_waiting_user`.
- **Round 1** (head `7592b2c`): user-directed rework (`fix-start-prompt-ui-round1.md`,
  entered at `a263ce6`) — P3 residuals + 4 UI decisions. **This summary** reflects round 1.

Round 1 is **Task-B-scoped** (frontend only). Task A (backend) is unchanged since
`dba4c12`, so its round-0 Kimi ACCEPT is **retained and not re-reviewed**. Only
Task B is re-reviewed, by a fresh read-only Claude-GLM session on the fix diff
`0fd0d17..7592b2c` (`frontend/**`).

## Task A — lastFundingRate warning semantic amendment (round-0 retained)

- **Verdict**: **ACCEPT (retained)** — `findings: []`
- **Reviewer**: Kimi `kimi-2.7` (round 0)
- **Fingerprint**: `dba4c12:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318`
- **Why retained**: Task A code (`snapshot.py` CONTRACT_WARNINGS[1] + contract doc +
  tests) is NOT in the rework round-1 diff; round-0 Kimi ACCEPT stands unchanged.
- **Report**: `30-review-1-backend.md` (round 0).

## Task B — Frontend rework round 1 (reviewer: fresh read-only Claude-GLM `glm-5.2[1m]`)

- **Verdict**: **ACCEPT** — `findings: []`, `required_fixes: []`
- **Recomputed fingerprint** (rework fix diff): `7592b2c:47cdfcc2a1716d929ad7098bf870b268b24d372085e837e932ae34bd8260e1a9`
  (`git diff --binary 0fd0d17..7592b2c -- frontend/ | shasum -a 256`) — matches
  `status.json.tasks.B.rework_round1.diff_fingerprint` ✓
- **Scope confirmed**: H_fix `7592b2c` touches only `frontend/index.html` +
  `frontend/self-check.js` + `20-implementation-frontend-rework1.md` (relative to
  its parent `a263ce6`); product-code boundary `frontend/**` intact; `backend/`,
  `schemas/`, `reports/api-samples/` untouched; `frontend/fixture/public-market-snapshot.json` unchanged.
- **4 rework changes verified**: (A) enum bilingual `ENGLISH(中文)` for route/asset/
  negative-funding-status columns + filter options (10 enums mapped; user's NEW
  decision superseding the round-1 pure-Chinese rule); (B) offline-fixture button +
  `loadFixture()` + `'fixture'` data-source branch removed; (C) 60s auto-refresh
  (aligned `Config.cache_ttl_seconds=60`) + countdown; (D) sidebar `Funding Hedge` → `资金费率对冲`.
- **Decimal discipline**: `formatFundingRate`/`formatBeijing*` unchanged; no
  `parseFloat`; the only `Number(` calls remain in `formatPrice`/`classForFundingRate`
  (ADR-3); the new countdown math is timestamp-only.
- **Checks rerun**: `node frontend/self-check.js` → **19/19 PASS** (round-0 14 +
  rework +5; Kimi's report said 18 by miscount, reviewer + controller confirm 19).
- **Round-0 P3 resolved**: the raw-enum emission + English sidebar wordmark are fixed.
- **Disclosure**: fresh isolated read-only session; cross-review (Task B authored by
  kimi) + fresh-session isolation (`reviewer_prior_involvement: none`).
- **Report**: `30-review-1-frontend-round1.md`; raw: `review-1-frontend-round1.raw-output.txt`.

## Aggregate (round 1)

| | verdict | fingerprint match | schema valid | findings |
|---|---|---|---|---|
| Task A (round-0 Kimi, retained) | ACCEPT | ✓ | ✓ | 0 |
| Task B (round-1 fresh GLM) | ACCEPT | ✓ | ✓ | 0 |

`both_schema_valid: true`, `both_fingerprints_match: true`, `findings_total: 0`,
`required_fixes_total: 0`. **Zero rework this round.**

Task C (controller integration verification, no product code) is **not** a
cross-review subject; it is covered by the stage-level review-2 final gate.

## Residual observations (non-blocking, carry forward)

1. Spec prose (`fix-start-prompt-ui-round1.md` "全角括号") contradicts its own table
   examples (half-width parens); implementation matches the tables byte-for-byte.
   Spec-side inconsistency, not a product defect.
2. The `0fd0d17..7592b2c` full-range diff includes `docs/parallel-development-mode.md`
   (DRAFT-1 methodology doc, marked non-normative) from independent parallel commits
   (`6894577`/`eba5bc0`) — NOT Kimi's rework. Product-code boundary + protected areas
   (`backend/`, `schemas/`, `reports/api-samples/`) intact.
3. Auto-refresh has no visibility-pause; acceptable per spec.

## Next

Stage-level **review-2** (final gate, rework round 1): Codex/GPT `gpt-5.5` (xhigh),
read-only, `reviewer_prior_involvement = direction_synthesis` (strong-reviewer
disclosure override), rebind to new head `7592b2c` (recompute stage fingerprint
`4b8c8de2…`). Anthropic/Fable5 is the stage designer → excluded; both implementers
hard-ban; Codex has no design/breakdown/code involvement this round. Then
`validate-stage --phase pre-accept` → `stage_accepted_waiting_user`. Controller does
NOT declare final acceptance.

本地北京时间: 2026-07-04 16:37 CST
下一步模型: Codex gpt-5.5 (review-2 final gate, rework round 1)
