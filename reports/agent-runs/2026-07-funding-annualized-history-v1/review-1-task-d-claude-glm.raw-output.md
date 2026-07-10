# Raw Claude-GLM Output: Task D Review-1 Accept

Produced by a fresh, read-only Claude-GLM (`glm-5.2`) first-reviewer session on
2026-07-10. Reviewed only frontend Task D of stage
`2026-07-funding-annualized-history-v1`. The reviewer had no prior involvement
in this stage's direction, breakdown, design, or implementation, and was not
the session that authored backend Tasks A/C.

Range integrity verified before review: the recorded `diff_fingerprint`
`d21536aa8a221a065c4fbe2b7640e199addca7dc:553e9a36f417d8c7986a26e1d3a5bc629b80958dfc0d979796e6ffb4123aa6a9`
was recomputed with `scripts/validate-stage.py`'s algorithm and **MATCH**ed the
committed diff `7480fdb..d21536aa` excluding `status.json`. File boundary is
clean: only `frontend/index.html`, `frontend/self-check.js`, and the Task D
implementation report changed; no backend/schema/canonical-doc/handoff/private
files were touched. `node frontend/self-check.js` was re-run against the review
head in a throwaway worktree and passed every assertion, including both the
fetch-boundary and response-body race tests.

## Verify checklist (all satisfied)

1. The default `route_class` column (`<th>` and `<td>`) is removed; the
   `#filter-route` filter, its `<option>`s, the `route_class` entry in
   `REQUIRED_ROW_FIELDS`, and the visible `negative_funding_status` column
   remain. `colspan` went 13→12 in both blocked and empty placeholders; every
   `getRowCell` index (daily 5→4, annualized 6/7/8→5/6/7, net 9→8,
   negative-status 11→10) and the cost-leg `tdCount` (5/9→4/8) were updated
   consistently; table `min-width` 1080→980 matches the 12-column layout.
2. Drawer uses `width: min(620px, 100vw)`, the annualized grid uses
   `repeat(3, minmax(0, 1fr))`, and `.annualized-card .label` has
   `white-space: nowrap`; the narrow-viewport path takes full width rather
   than horizontal overflow.
3. The browser calls only the same-origin `/api/public-market/funding-history`
   endpoint with `encodeURIComponent(symbol)`. Loading, available (merged into
   row + table), empty (no-records copy), upstream-502 (retryable failure), and
   retry states all have correct, distinct semantics; empty is never labeled as
   failure and 502 is never labeled as "no history".
4. A successful merge is limited to the requested symbol. The `isActive()`
   guard (request id + `drawerOpen` + `selectedSymbol === symbol`) runs after
   every async boundary, including immediately after `await res.json()`. A
   wrong-symbol, `schema_version`-mismatched, or shape-invalid response is
   rejected as `history_response_invalid` and never mutates any row.
5. Existing click/Enter/Space selection, Escape/backdrop/close, refresh-retains
   /symbol-disappears-closes behavior (coordinated with `closeDrawer()` in both
   `render()` and `ingestSnapshot()`, which keeps the fetch guard sound),
   privacy behavior, and no-trading constraints remain intact. Self-check
   covers both the fetch-boundary and response-body races.

## Findings summary (all P3, non-blocking)

- **P3-1** `badgeForRouteClass` (index.html:1045) is now an orphan after the
  route-class `<td>` removal — zero call sites, not exposed on `__appHelpers`.
  Dead code created by this task's change; should be removed per surgical-changes.
- **P3-2** The blocked/empty placeholder `colspan="12"` has no direct
  self-check assertion; test 5c only verifies the thead `<th>` count is 12.
- **P3-3** `getSnapshot: () => state.snapshot` was exposed on `__appHelpers`
  but is never referenced by self-check (tests use `ingestSnapshot`).
- **P3-4** Redundant `if (!isActive()) return` inside the 502 and `!res.ok`
  branches of `fetchHistory` — no `await` separates them from the prior guard.
- **P3-5** Test 53's stale assertion uses `-0.02%` (not a BUSDT-response-
  specific value); less precise than test 54's race assertion.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "glm-5.2",
  "verdict": "ACCEPT",
  "diff_fingerprint": "d21536aa8a221a065c4fbe2b7640e199addca7dc:553e9a36f417d8c7986a26e1d3a5bc629b80958dfc0d979796e6ffb4123aa6a9",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/13-review-feedback-fix.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-frontend-history-fix.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/task-drawer-history-refinement-kimi.prompt.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/task-drawer-history-race-fix-kimi.prompt.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-d-claude-glm.prompt.md",
    "frontend/index.html",
    "frontend/self-check.js",
    "schemas/review-verdict.schema.json",
    "scripts/validate-stage.py"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "badgeForRouteClass becomes an orphan function",
      "file": "frontend/index.html",
      "line": 1045,
      "evidence": "After Task D removed <td>${badgeForRouteClass(row.route_class)}</td>, the only occurrence of badgeForRouteClass in the whole file is its definition at line 1045; grep shows zero call sites and it is not exposed on __appHelpers, so self-check cannot reach it either.",
      "impact": "No functional impact; leftover dead code that violates the surgical-changes rule that orphans created by a change should be removed with it.",
      "recommendation": "Remove the badgeForRouteClass definition, and any constant/map referenced only by it."
    },
    {
      "severity": "P3",
      "title": "blocked/empty placeholder colspan lacks a self-check",
      "file": "frontend/self-check.js",
      "line": null,
      "evidence": "Test 5c asserts only that the thead <th> count equals 12; the two <td colspan=\"12\"> placeholders for blocked and empty states in index.html have no assertion covering them.",
      "impact": "If the column count changes again, colspan could drift without a test failure; only placeholder cross-column visuals are affected, so risk is low.",
      "recommendation": "Add an assertion on colspan=12 for the blocked and/or empty placeholder rows in a test that constructs those states."
    },
    {
      "severity": "P3",
      "title": "getSnapshot testability hook is unused",
      "file": "frontend/index.html",
      "line": 1839,
      "evidence": "__appHelpers gained getSnapshot: () => state.snapshot, but self-check never calls it; the race test uses ingestSnapshot to re-render.",
      "impact": "No functional impact; an unused exposure surface.",
      "recommendation": "Remove it if no planned use exists, or add an assertion that exercises it so the exposure is not dead."
    },
    {
      "severity": "P3",
      "title": "redundant guard inside 502/!res.ok branches of fetchHistory",
      "file": "frontend/index.html",
      "line": 1404,
      "evidence": "if (!isActive()) return runs right after await fetch; the subsequent res.status===502 and !res.ok branches each repeat if (!isActive()) return with no await between them.",
      "impact": "No bug; a minor readability blemish only.",
      "recommendation": "Drop the in-branch redundant guards and keep the single guard immediately after await fetch."
    },
    {
      "severity": "P3",
      "title": "stale-response isolation assertion is imprecise",
      "file": "frontend/self-check.js",
      "line": null,
      "evidence": "Test 53 checks ausdtDrawerBodyStale.includes('-0.02%') to detect BUSDT pollution of the AUSDT drawer, but -0.02% is not a value specific to the BUSDT response; test 54's race assertion (full drawer-body equality + BUSDT 7d cell must not contain -0.260714%) is far more precise.",
      "impact": "The test still passes, but it is a weaker proof of isolation strength.",
      "recommendation": "Assert that the AUSDT drawer does not contain a BUSDT-response-specific value (e.g. -0.260714% or its funding_time)."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "The frontend self-check runs in a node mock environment and cannot measure real browser layout: whether the 620px Drawer truly avoids overflow on a narrow viewport and whether the three labels truly do not wrap is only guaranteed indirectly via source-CSS string-include assertions, with no pixel-level render verification.",
    "The stale-response and response-body races are simulated via mock timing that covers the known boundaries; real browser event-loop timing is more complex and extreme races cannot be exhaustively exercised in the self-check.",
    "The mock fetch has no encodeURIComponent edge case for symbols containing special characters; only plain symbols (BUSDT/CUSDT/DUSDT) are exercised."
  ],
  "next_action": "continue"
}
```
