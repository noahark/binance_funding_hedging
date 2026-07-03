# 20-implementation.md — Stage 2026-07-public-market-bstock-alias-v1

Consolidated implementation record. Per-task detail lives in
`20-implementation-backend.md` (Task A) and `20-implementation-frontend.md`
(Task B). This stage closes impl-v1 post-review P1 finding
`bstocks_b_suffix_spot_margin_alias` by amending the frozen
`public-market-snapshot/v1` contract and repairing the backend/frontend so a
TRADIFI futures symbol joins its `B`-suffixed bStock spot/margin leg. impl-v1's
review-2 against the OLD frozen contract is NOT altered.

## What the amendment does (the 6 user points)

1. `TRADIFI/BSTOCK` joins its spot leg via `baseAsset + "B" + quoteAsset`
   (`TSLAUSDT` -> `TSLABUSDT`). Implemented in
   `backend/domain/normalize.py:resolve_spot_leg`.
2. `spot.match_type` exposes the match source (`exact_symbol` /
   `bstock_b_suffix_alias` / `null`). Added to schema + filled by `build_rows`.
3. bStock positive-funding rows become candidates: alias spot pair with
   `isMarginTradingAllowed=true` -> `MARGIN_SPOT_CANDIDATE`,
   `positive_funding_enabled=true`, `asset_tag` stays `BSTOCK`.
4. bStock negative-funding stays disabled: the unchanged
   `negative_funding_status` priority ranks `asset_tag=BSTOCK` ahead of the
   candidate route -> `DISABLED_BSTOCK` (cannot borrow).
5. Collateral ratio stays dynamic/unknown; no ratio is hard-coded;
   `margin_public.source` stays `"unverified"`.
6. `classify.py` is NOT touched; the alias join alone satisfies points 3-4 via
   the existing classifier.

## Task A — contract amendment + backend (owner Claude-GLM, H_A=1f94c84)

- `schemas/api/public-market/snapshot.schema.json`: nullable `spot.match_type`
  enum (not `required`, so the frozen curated sample stays backward-valid).
- `docs/api/public-market-contract.md`: post-review note -> Frozen amendment
  rule; response-shape `match_type`; enum; unchanged-priority note; Open
  Verification Item RESOLVED (amended).
- `backend/domain/normalize.py`: `resolve_spot_leg` pure helper
  (exact -> TRADIFI-only B alias -> none).
- `backend/domain/snapshot.py`: `build_rows` uses `resolve_spot_leg`, fills
  `match_type`, updates `CONTRACT_WARNINGS[2]`. `classify.py` untouched.
- `backend/tests/**` + `backend/tests/fixtures/bstock-alias-raw/**`: synthetic
  fixture (4 cases) + 13 new tests; classify priority regression-asserted.

Detail + raw output: `20-implementation-backend.md`.

## Task B — frontend display (owner Kimi, H_B=5968c49)

- `frontend/index.html`: symbol cell renders the actual spot leg
  (`现货腿: TSLABUSDT` + `B 后缀别名` badge) only when
  `spot.match_type==="bstock_b_suffix_alias"` and `spot.symbol` differs from the
  futures symbol. exact_symbol / no-leg rows unchanged.
- `frontend/fixture/public-market-snapshot.json`: `match_type` on every row;
  TSLAUSDT demo row converted to an alias-joined `MARGIN_SPOT_CANDIDATE`
  (`DISABLED_BSTOCK`, positive rate); MSTRUSDT kept as the no-alias PERP_ONLY
  control; summary counts + `warnings[2]` synced.
- `frontend/self-check.js`: default rows 3->4; new alias assertions; BSTOCK
  still 2; all prior assertions retained. `node frontend/self-check.js` passes.

Detail + raw output: `20-implementation-frontend.md`.

## Task C — integration verification (controller, no product code, H_C)

`task-c-integration-check.py` loads the synthetic fixture, runs the service
domain pipeline (filter -> `build_rows` -> `assemble_snapshot`), schema-validates,
and asserts all four alias cases. It dumps
`integration-snapshot-bstock-alias.json`. Result: ALL PASS (raw output in
`60-test-output.txt` Section 4).

## Boundary compliance

- Task A wrote only `snapshot.schema.json`, `docs/api/public-market-contract.md`,
  `backend/domain/{normalize,snapshot}.py`, `backend/tests/**`,
  `backend/tests/fixtures/bstock-alias-raw/**`, `20-implementation-backend.md`,
  `60-test-output.txt`. `classify.py`, `config.py`, frozen samples untouched.
- Task B wrote only `frontend/**` + `20-implementation-frontend.md`. No
  backend/schema/docs changes (verified by the controller via `git status`).
- Task C wrote no product code; only stage evidence
  (`60-test-output.txt` Section 4, this file, `integration-snapshot-bstock-alias.json`,
  `task-c-integration-check.py`).

## Hard constraints honored

- No API key / signed / private / user-data-stream / order / borrow / repay /
  transfer / websocket. Tests offline only; no live HTTP this stage.
- `reports/api-samples/public-market-contract-v2/**` read-only (the curated spot
  fixture has no bStock, which is why a synthetic fixture is used for tests).
- `classify.py` logic and `negative_funding_status` priority unchanged
  (regression-asserted, not modified).
- No collateral ratio hard-coded; `margin_public.source` stays `"unverified"`.
- `funding_history` default top-N=20 unchanged.
- Formal page still same-origin `/api/public-market/snapshot`.

## Verification summary (raw in 60-test-output.txt)

- Backend: 52 passed; `float()` clean; smoke OK (rows=688, warnings=3,
  frozen data_time unchanged).
- Frontend: `node frontend/self-check.js` all PASS (controller re-ran).
- Integration: Task C check ALL PASS; assembled snapshot schema-valid with
  `match_type`; all four alias cases asserted.

## Stage-level diff_fingerprint

Single protocol, two scopes (per-task + stage top-level). Filled at H_C:
- base_sha: `d240e43` (H_intake)
- head_sha: `<H_C>`
- diff_fingerprint: `head_sha + ':' + sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json')`

Per-task fingerprints (authoritative in `status.json.tasks.{A,B}`):
- Task A: `1f94c84:fe6d0bd9d16ea2e75c54b59ed9469f206c5e733dc4d159ba35c959d63ad4c815`
- Task B: `5968c49:8c5d685eb8a51ea3261cb85cda97cfa000b2fb66ccddf49d3b0f0031a4b7c7d0`
