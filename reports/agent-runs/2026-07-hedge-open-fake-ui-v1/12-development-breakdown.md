# Development Breakdown — Hedge Open Fake UI v1

Breakdown author: Claude / Opus 4.8 (via Claude Code), provider `anthropic`.
This is a design-involvement artifact for review-2 disclosure. The author is
NOT an implementer or fix author.

Single bounded task, single owner. Not parallel mode (one disjoint front-end
task, no second implementation task to run concurrently).

## Owner split

| Task | Owner | Domain |
|---|---|---|
| Hedge Open fake UI (T1+T2+T3) | **Kimi** | front-end only |

Backend / Claude-GLM: not involved. No backend, schema, or docs change.

## Allowed files (hard boundary)

- `frontend/index.html` — inline `<script>`, DOM markup, CSS.
- `frontend/self-check.js` — new deterministic assertions only.

## Forbidden files

- `backend/**`, `schemas/**`, `docs/**`, `scripts/**`, `workflows/**`,
  `agents/**`, `reports/**` (bookkeeper owns stage evidence), `AGENTS.md`,
  root config, `.env*`, fixtures under `backend/tests/**`.
- Any new dependency, build step, framework, or external asset. Vanilla JS +
  existing inline patterns only.

## Frozen contracts (implement exactly; do not invent alternates)

- Column names, order, and the name-only rename: design §1. Operation columns
  go **immediately after** `借币`, order `正向开单` then `反向开单`.
- Direction/basis convention and 0.05% threshold: ADR-2 + design §4.3 (locked;
  do not change sign or leg mapping).
- Both direction cells always clickable; highlight recommended by funding sign
  only: ADR-3 / design §1.2.
- Task object, Fill object, localStorage keys: design §4. Use these exact field
  names so stage 2 can reuse them.
- Leg-risk + `>3`-fail policy: ADR-4 / design §5.
- Position aggregation math: design §3.

## Test evidence (required before stop)

- `node frontend/self-check.js` must print all existing `[PASS]` lines plus the
  new assertions in design §6, and exit 0. Paste full output into
  `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt` (the
  bookkeeper collects it; the implementer includes the run in its report).
- Because self-check parses the FIRST inline `<script>` block, keep all new
  logic inside that same block; do not add a second `<script>` that would
  escape the harness.

## Risk points (review focus)

1. **self-check coupling**: the harness extracts the first `<script>` via a
   non-greedy regex. New code must stay in that block and must not break the
   existing 90+ `[PASS]` assertions (column split, ordering, formatting,
   same-origin/timer guards). Regression here is the top risk.
2. **Column ordering**: `assertOrder`/column-presence assertions are strict.
   The rename must not disturb the estimate columns' existing semantics, and
   the two new columns must land after `借币`, not before.
3. **Timer discipline**: the existing harness proves zero-task timers and
   guards `setInterval`. The fake engine's drift/1s-fill loops must be mockable
   and must not introduce un-cleared timers or cross-origin `fetch`.
4. **Basis sign correctness**: forward vs reverse leg/price mapping is easy to
   flip; assert both explicitly (design §6.2/§4.3).
5. **Persistence determinism**: fail-injection must be seedable so the `>3`-fail
   and single-leg-exposure assertions are deterministic in self-check.
6. **Scope creep**: no real websocket, no backend stub, no order path, no new
   files. Reverse open does NOT auto-borrow — it only checks fake quota.

## Cross review routing

- review-1: Claude-GLM (`zhipu_glm`) — cross-provider isolation from Kimi
  (`moonshot`). Read-only, schema-valid verdict.
- review-2: GPT/Codex first; unavailable this round (no quota) → Claude
  (`anthropic`) strong-reviewer fallback with design-involvement disclosure
  (the breakdown author is Claude). Runner-level unavailability of the unrelated
  decision model must be recorded before the override is used.

## Dispatch

- Implementation prompt: `task-hedge-open-fake-ui-kimi.prompt.md` (carries the
  `[HARNESS-EXECUTOR-CONTRACT v1]` preamble + R10 dispatch tail).
- Executor: human operator only. The bookkeeper prepares the packet; it does
  not launch Kimi.
