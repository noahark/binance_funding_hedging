# 20 — Implementation (stage summary)

Stage: `2026-07-public-market-impl-v1`
Status: `implementing` (both product tasks implemented; integration + reviews
pending). This file is the stage-level summary and points to the per-task
implementation reports; it does not replace them and does not declare final
acceptance (controller never accepts; `can_accept_final: false`).

Per-task detail:
- Task A (backend): `20-implementation-backend.md`
- Task B (frontend): `20-implementation-frontend.md` (Kimi-authored)
- Task C (integration): evidence in `60-test-output.txt` Section 4 + any
  `integration-snapshot-*.json`.

## Objective

Implement the public-market snapshot workstation against the frozen
`2026-07-public-market-contract-v2` contract (head `a25e431`,
`diff_fingerprint` `53484d21…`): a backend that serves a schema-validated
snapshot from public Binance data, and a frontend that renders it same-origin.
Public data only; 127.0.0.1 binding; no API key / signature / private endpoint
/ order / borrow / repay / transfer / websocket.

## Tasks and owners

| Task | Owner | Scope | Commit | Status |
|---|---|---|---|---|
| A — backend snapshot service | Claude-GLM (`claude_glm`) | `backend/**` | `H_A` `a40b204` | implemented_pending_review_1 |
| B — frontend market table | Kimi (`kimi-2.7`) | `frontend/**` | `H_B` `c1e33b6` | implemented_pending_review_1 |
| C — integration verification | Claude-GLM (controller) | reports only | `H_C` (pending) | not_started |

Breakdown author / stage designer of record: Claude/Fable5 (`anthropic`,
`fable5-detail-breakdown.md`) — design involvement, disclosed for review-2.

## Commit history (serialized by controller)

```
32f6f0f  H_intake   stage evidence (task base)
a40b204  H_A        backend snapshot service (Task A)
fc018ea  checkpoint Task-A fingerprint recorded in status.json (controller evidence; status.json excluded from fingerprints)
c1e33b6  H_B        frontend market table (Task B)
???????  H_C        integration evidence + final status/handoff (Task C) [pending]
```

Controller evidence commits (e.g. the checkpoint) may interleave between task
commits; each task's `base_sha` is the immediately preceding commit, so its
`base..head` diff contains only that task's files. `status.json` is excluded
from every fingerprint.

## Task-level fingerprints

Both recomputed independently from raw `git diff` (not controller summaries):

| Task | base_sha | head_sha | diff_fingerprint | diff files |
|---|---|---|---|---|
| A | `32f6f0f…155c` | `a40b204…4d72` | `a40b204…4d72:5148a473…1e93` | 21 (19 backend + 2 reports) |
| B | `fc018ea…7f20` | `c1e33b6…0414` | `c1e33b6…0414:4bebeb52…6bde` | 4 (3 frontend + 1 report) |
| C | (H_B) | (H_C) | (pending) | (reports only) |

Stage-level top-level fingerprint (`base_sha=H_intake`, `head_sha=H_C`) is
filled in `status.json` after `H_C`. Same formula at both scopes (ADR-6).

## File manifest

Backend (`H_A`, 19 files): `backend/{config.py, adapters/binance_public.py,
domain/{classify,normalize,snapshot}.py, services/snapshot_service.py,
app/server.py}` + 7 `__init__.py` + tests (`conftest.py`, `smoke_server.py`,
`test_{classify,negative_schema,normalize,snapshot}.py`).

Frontend (`H_B`, 4 files): `frontend/index.html`, `frontend/fixture/public-market-snapshot.json` (byte-identical to the frozen normalized sample),
`frontend/self-check.js`, `20-implementation-frontend.md`.

## Architecture (summary)

- Backend: layered `adapters → domain → services → app`; stdlib
  `http.server.ThreadingHTTPServer` on 127.0.0.1 (no FastAPI, ADR-1).
  Pipeline: fetch → filter TRADING perpetuals/TRADIFI → normalize/classify →
  assemble (summary aggregated FROM rows) → jsonschema-validate before serving
  (503 on failure). Same-origin `/api/public-market/snapshot` + static
  `frontend/` host. Top-N funding_history default 20 (live-only bound); offline
  uses frozen fixtures. Decimal discipline (no `float()`).
- Frontend: single-page table; default `fetch('/api/public-market/snapshot')`;
  offline fixture is a manual fallback only. No trade/open/account/position UI.

## Test evidence

- Backend (`60-test-output.txt` Sections 1–3): 39 pytest passed (offline frozen
  fixtures); `float()` audit clean; single-process `http.server` smoke
  (schema-valid snapshot 688 rows, index 27982 B, fixture 8900 B).
- Frontend (`20-implementation-frontend.md` + `self-check.js`): Node self-check
  10 PASS (default API fetch, warnings render, PERP_ONLY_EXCLUDED
  default-hidden, BSTOCK badge, contract copy, NO trade button/open ticket).
- Integration (Task C, `60-test-output.txt` Section 4): pending — see below.

## Contract-v2 alignment

- `schema_version = "public-market-snapshot/v1"`; the three contract warnings
  preserved verbatim; field names/shapes validated against
  `schemas/api/public-market/snapshot.schema.json`.
- Offline backend output reproduces the frozen normalized sample's `data_time`
  and the 6 curated symbols' `(route_class, asset_tag, negative_funding_status)`
  tuples.
- Frontend fixture is byte-identical to the frozen normalized sample.

## Hard-constraints compliance

- No API key / signature / private account / user-data stream / order / borrow
  / repay / transfer / websocket. Public unauthenticated GET endpoints only.
- `schemas/**`, `docs/api/public-market-contract.md`, raw samples read-only and
  untouched (verified by diff scope).
- Backend writes only `backend/**`; frontend writes only `frontend/**`.
- No planning-calculator UI, manual-open ticket, order button, account-status,
  or position management.
- `funding_history` default top-N = 20 (unchanged).
- Formal page loads data same-origin from `/api/public-market/snapshot`;
  fixture is for offline/test only (manual fallback in the UI).

## Known limitations (stated honestly)

- **Live HTTP path not exercised this stage.** All backend tests and the smoke
  are offline against frozen fixtures. Live request counts / rate-limit
  headroom (≈23 calls/refresh, <1% of weight ceilings) are design figures from
  public docs + the top-N design, not measured.
- **Server smoke is single-process.** The Harness sandbox blocks loopback TCP
  between separate processes, so `smoke_server.py` runs the real `http.server`
  in a background thread and connects via `urllib` from the same process
  (sandbox network disabled). Equivalent real HTTP; committed and reproducible.
- Controller == Task A implementer (both `claude_glm`); mitigations recorded in
  `status.json.evidence_policy` (reviewers recompute fingerprints from raw
  diffs; Task B review-1 uses a fresh read-only Claude-GLM session).

## Acceptance (stage-level, not declared here)

Stage acceptance requires (per `validate-stage.py`): tests pass, task-level
review-1 ACCEPT for A and B, stage-level review-2 ACCEPT, jsonschema valid,
and `review_X.diff_fingerprint == status.diff_fingerprint` at both scopes. The
controller does not advance the stage to accepted; that gate is `pre-accept`
after reviews.
