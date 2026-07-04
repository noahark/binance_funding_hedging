# Review-2 round 1 (stage-level, FINAL GATE) — public-market-ui-cn-v1 rework

- **Stage**: `2026-07-public-market-ui-cn-v1`
- **Reviewer**: Codex/GPT `gpt5.5` (xhigh), `final_reviewer`, read-only sandbox
- **Verdict**: **REWORK** — 1× P2 finding, `next_action: fix`
- **Stage diff_fingerprint** (recomputed & matched): `7592b2c740975dc0a6ad2a4b3a17d5a8474494ff:4b8c8de25458e88a9dd8d5f8ab03db0f563305c59492fae548d69683978c4608`
- **Disclosure**: `reviewer_prior_involvement: direction_synthesis` (strong-reviewer override)
- **Date**: 2026-07-04 16:59 CST

## Reviewer narrative (Codex final message)

> Verdict: REWORK.
>
> Most hard checks passed: fingerprint matches, frontend-only product scope
> holds for `H_fix`, no payload/schema drift in the rework, self-check passes,
> backend tests pass with capture disabled in this read-only sandbox, and
> same-origin fetch is preserved. I found one blocking frontend behavior defect:
> manual refresh resets the displayed countdown target, but it does not
> reschedule the actual 60s auto-refresh interval, so the next automatic fetch
> can happen before the displayed "下次刷新" reaches zero.

## Finding (P2, blocking)

**Manual refresh resets the countdown display but not the actual auto-refresh
timer** — `frontend/index.html:635`.

- `startAutoRefresh()` (L635-639) creates one `setInterval(loadApi, 60000)`
  (`refreshTimer`) + one `setInterval(updateCountdown, 1000)` (`countdownTimer`).
- The manual-refresh handler (`btnRefresh` L901) only calls `loadApi()`.
- `loadApi()`'s `finally` block (L875-878) sets `refreshState.nextRefreshAt =
  Date.now() + AUTO_REFRESH_MS` and calls `updateCountdown()`, but there is **no
  `clearInterval`/timer reschedule anywhere in the file** (controller grep
  confirmed: zero `clearInterval`/`clearTimeout` in `frontend/index.html`).
- **Consequence**: a manual refresh at T+50s resets the displayed countdown
  target to T+110s, but the original interval still fires at T+60s → the UI can
  show "下次刷新" with ~50s remaining while an automatic refresh fires
  immediately. This violates **user decision C** ("手动刷新按钮保留：点击立即
  fetch 并将倒计时重置为 60") — the reset is display-only, not aligned with the
  actual next auto-fetch.

## Independent re-verification (by Codex, controller-confirmed)

- **Fingerprints**: stage `b84a342..7592b2c` = `4b8c8de2…` (matches
  `status.json.diff_fingerprint`); task A `8afc3dcf` (unchanged), task B rework
  fix `47cdfcc2…`, cumulative frontend `9caf18e6…` — all recomputed & matched.
- **Product scope**: `H_fix` (`git show 7592b2c --stat`) = only
  `frontend/index.html` + `frontend/self-check.js` + rework1 report. Backend /
  schemas / api-samples untouched.
- **Hard constraints**: no live HTTP, no API key/signed/private/order paths;
  rows / API payload frozen (only `warnings[1]` text from round-0 Task A);
  same-origin fetch preserved.
- **Decimal discipline**: `formatFundingRate`/`formatBeijing*` unchanged; no
  `parseFloat`; `Number(` only in `formatPrice`/`classForFundingRate`.
- **Tests**: self-check 19/19; backend pytest 54 passed (capture-disabled,
  read-only sandbox); offline snapshot schema VALID (647 rows, 3 warnings).
- **Controller due-diligence**: grep confirmed zero `clearInterval`/`clearTimeout`
  in `frontend/index.html` → finding holds.

## Required fixes

1. In `frontend/index.html`, make the actual auto-refresh timer use the same
   `nextRefreshAt` target shown in the countdown. Minimal fix: in `loadApi`'s
   `finally` block, after setting `nextRefreshAt`, `clearInterval(refreshState.refreshTimer)`
   and recreate the 60000ms timer; keep the 1s countdown interval separate.
2. Preserve same-origin `fetch('/api/public-market/snapshot')`; do not reintroduce
   `btn-offline`/`loadFixture`/`'fixture'` branch; do NOT modify
   `formatFundingRate`/`formatBeijing`/`formatBeijingShort`; no backend/schema/
   docs-contract/api-samples changes.
3. Extend `frontend/self-check.js` to cover the manual-refresh timer reset
   (mock `setInterval`/`clearInterval`; assert a manual refresh invalidates the
   old 60s timer and schedules a new one).
4. Rerun: `node frontend/self-check.js`;
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q`;
   offline snapshot jsonschema validation.

## Residual risks (carry forward)

- Single mid-period lastFundingRate snapshot evidence (drift); accepted residual.
- Frontend self-check on frozen fixture; live endpoint serves full market.
- Spec prose/table paren inconsistency (spec-side).
- `docs/parallel-development-mode.md` in the wide stage diff is an independent
  non-product methodology doc.
- Live worktree has untracked review-2 capture files; controller commits evidence
  before pre-accept.

## JSON verdict

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-public-market-ui-cn-v1",
  "role": "final_reviewer",
  "model": "gpt5.5",
  "verdict": "REWORK",
  "diff_fingerprint": "7592b2c740975dc0a6ad2a4b3a17d5a8474494ff:4b8c8de25458e88a9dd8d5f8ab03db0f563305c59492fae548d69683978c4608",
  "reviewer_prior_involvement": "direction_synthesis",
  "findings": [
    {
      "severity": "P2",
      "title": "Manual refresh resets the countdown display but not the actual auto-refresh timer",
      "file": "frontend/index.html",
      "line": 635,
      "evidence": "startAutoRefresh creates one 60000ms setInterval (L635-639); btnRefresh (L901) only calls loadApi(); loadApi finally updates nextRefreshAt (L877) but there is no clearInterval/timer reschedule anywhere (grep confirmed). A manual refresh at T+50s resets the countdown target to T+110s while the original interval still fires at T+60s.",
      "impact": "UI can show 'next refresh' with ~50s remaining while an automatic refresh fires immediately. Violates user decision C (manual refresh resets the 60s countdown): reset is display-only, not aligned with the actual next auto-fetch.",
      "recommendation": "Reschedule the auto-refresh timer whenever loadApi completes (incl. manual refresh + failure), so displayed nextRefreshAt and actual next fetch share the same 60s target."
    }
  ],
  "required_fixes": [
    "frontend/index.html: in loadApi finally after setting nextRefreshAt, clearInterval(refreshTimer) + recreate 60000ms timer; keep 1s countdown interval separate.",
    "Preserve same-origin fetch; no btn-offline/loadFixture reintroduction; no formatFundingRate/formatBeijing changes; no backend/schema/docs/api-samples changes.",
    "frontend/self-check.js: add manual-refresh timer-reset coverage (mock setInterval/clearInterval).",
    "Rerun: node frontend/self-check.js; pytest backend/tests; offline snapshot jsonschema."
  ],
  "residual_risks": [
    "lastFundingRate single mid-period snapshot (drift); accepted residual.",
    "Frontend self-check on frozen fixture; live endpoint full market.",
    "Spec prose/table paren inconsistency (spec-side).",
    "docs/parallel-development-mode.md independent non-product doc in stage diff.",
    "Live worktree has untracked review-2 capture; commit before pre-accept."
  ],
  "next_action": "fix"
}
```

---

Raw output: `review-2-codex-round1.raw-output.txt`; dispatch prompt:
`review-2-codex-round1.prompt.md`. The verdict was emitted by Codex and is
internally consistent with `schemas/review-verdict.schema.json`.

## Next

**Rework round 2 (2/3)**: dispatch Kimi (Task B owner) per
`fix-start-prompt-ui-round2.md` to sync the auto-refresh timer with the
displayed countdown, add self-check coverage. Then re-review-1 (fresh GLM) +
re-review-2 (Codex rebind) + pre-accept → `stage_accepted_waiting_user`.

本地北京时间: 2026-07-04 17:00 CST
下一步模型: Kimi (rework round 2, Task B timer sync)
