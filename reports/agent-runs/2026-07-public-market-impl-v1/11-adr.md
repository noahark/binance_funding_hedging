# ADR: 2026-07-public-market-impl-v1

## ADR-1: HTTP framework — standard-library `http.server`, not FastAPI/uvicorn

- Context: Task A needs a tiny local server on `127.0.0.1` serving one JSON
  endpoint and static frontend assets. The breakdown permits either
  FastAPI+uvicorn or the standard library.
- Decision: standard-library `http.server.ThreadingHTTPServer`.
- Rationale: zero extra runtime dependencies; the server is single-host,
  low-concurrency, local-only; keeps the dependency surface to `jsonschema`
  only. Simpler supply-chain and reproducibility.
- Tradeoff: no async, no auto OpenAPI; acceptable for Phase 1 public snapshot.

## ADR-2: `funding_history` top-N default = 20

- Context: `/fapi/v1/fundingRate` is per-symbol; calling it for every futures
  symbol is unbounded.
- Decision: rank by `abs(last_funding_rate)`, fetch history for the top-20 only
  (configurable), others get `[]`.
- Rationale: bounds request volume; default confirmed in this round's design. Do
  not change the default without an explicit user change.

## ADR-3: Offline mode reads the frozen raw-sample directory

- Context: tests and CI must be offline; the normalized sample is frozen.
- Decision: offline mode reads
  `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/` (a
  read-only reference to frozen evidence). Tests do not duplicate these files.
- Rationale: reuse frozen evidence without duplication; keeps the raw→normalized
  mapping provably consistent with the frozen sample. Reading frozen evidence is
  compliant (read-only); nothing under that path is modified.

## ADR-4: Do not reuse the archived Grok backend

- Context: `backend/` previously held a Grok-authored implementation (commit
  `c53664e`) that was removed by `11d5504 Reset ... to contract-first`; only
  `__pycache__` residue remains, including `planning.py` and `constraint_guard`
  artifacts that are out of scope this stage (forbidden planning calculator).
- Decision: implement Task A from scratch; do not restore or trust Grok residue.
- Rationale: Grok is excluded from core work this stage; the archived code is
  explicitly "not trusted as active base." A clean implementation also avoids
  pulling in forbidden planning logic.

## ADR-5: Same-origin static hosting of the frontend

- Context: the frontend must consume `GET /api/public-market/snapshot` and avoid
  CORS.
- Decision: the backend statically hosts `frontend/` at `/` on the same
  `127.0.0.1` port. The controller adds only the static-host route; it does not
  edit frontend contents.
- Rationale: same-origin fetch, no CORS, one process. Keeps the boundary clean
  (backend owns the route, frontend owns the page).

## ADR-6: Two fingerprint scopes, one protocol

- Context: three tasks (A/B/C) each need a reviewable commit range, but
  `validate-stage.py` binds review-2/pre-accept to a single top-level
  `diff_fingerprint`.
- Decision: record task-level `base_sha`/`head_sha`/`diff_fingerprint` in
  `status.json.tasks.<id>` for task-level review-1, and a stage-level top-level
  triple covering the whole stage diff for review-2/pre-accept. Same formula,
  same `status.json` exclusion. No second protocol.
- Rationale: satisfies both the per-task review boundary and the validator's
  single-fingerprint acceptance check without inventing a new scheme.

本地北京时间: 2026-07-03 20:30:00 CST
下一步模型: Claude-GLM (controller)
下一步任务: Build `status.json` with task records A/B/C.
