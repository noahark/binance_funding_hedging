# Review-1 round 2 (task-level, Task B rework) — public-market-ui-cn-v1

You are a **FRESH, read-only Claude-GLM session** (`glm-5.2[1m]`) acting as
`reviewer_1` for **Task B rework round 2**. You have NO prior involvement in
this stage's Task B direction/breakdown/design/implementation/rework — you are
a fresh isolated context (`reviewer_prior_involvement: none`). You may read
anything in the repository; you may modify NOTHING except your own review
report file.

## Context

Stage `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation, public data only). Round-1 (head `7592b2c`) review-1 = ACCEPT
(fresh GLM) but review-2 (Codex `gpt-5.5` xhigh) returned **REWORK** on exactly
**one P2**: manual refresh resets the countdown display (`nextRefreshAt`) but
NOT the actual 60000ms auto-refresh interval — there was no
`clearInterval`/reschedule anywhere in `frontend/index.html`, so a manual
refresh at T+50s reset the displayed target to T+110s while the original
interval still fired at T+60s. Rework round 2 (`fix-start-prompt-ui-round2.md`,
entered at `b20b219`) landed `H_fix2` (`ee9296c`) to fix exactly that one defect.

- **Task B (frontend)** was reworked again by `kimi` — this is what you re-review.
- **Task A (backend)** is UNCHANGED since `dba4c12` — round-0 Kimi ACCEPT is
  retained and NOT re-reviewed.
- You re-review ONLY the Task B round-2 fix diff (not the whole stage).

## Review subject (recompute this yourself — do not trust this summary)

- base_sha: `7592b2c740975dc0a6ad2a4b3a17d5a8474494ff` (round-1 H_fix head = round-2 base)
- head_sha: `ee9296c705d3590adb01bf2fff433e32e834523e` (H_fix2, rework round 2)

Recompute the round-2 fix fingerprint from a clean shell in the repo root:

```bash
git diff --binary 7592b2c740975dc0a6ad2a4b3a17d5a8474494ff..ee9296c705d3590adb01bf2fff433e32e834523e -- frontend/ | shasum -a 256
```

Expected (recorded in `status.json.tasks.B.rework_round2.diff_fingerprint`):

```text
ee9296c705d3590adb01bf2fff433e32e834523e:f4073da548a299234daba3bc0296cf82433fd71438313f7fdba8943a93442226
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

## The round-2 fix (verify it resolves the review-2 round-1 P2)

The P2 being fixed: `startAutoRefresh()` created one 60000ms `setInterval`; the
manual-refresh path (`btnRefresh` → `loadApi`) only reset `nextRefreshAt` in
`loadApi`'s `finally`, never `clearInterval`/reschedule → the countdown display
and the actual next fetch diverged.

Required fix (per `fix-start-prompt-ui-round2.md`):

1. `frontend/index.html` `loadApi()` `finally`: **after**
   `refreshState.nextRefreshAt = Date.now() + AUTO_REFRESH_MS;`, add
   `if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);`
   then
   `refreshState.refreshTimer = setInterval(() => { if (!refreshState.isRefreshing) loadApi(); }, AUTO_REFRESH_MS);`
2. The 1s `countdownTimer` is kept **independent** (not cleared/recreated, not
   merged into the same interval).
3. `startAutoRefresh()` first-create logic **unchanged** (still creates the
   first 60000ms timer + the 1000ms countdown timer).
4. **No** `visibilitychange` / `requestIdleCallback` / retry / backoff added.
5. `frontend/self-check.js`: inject `setInterval`/`clearInterval` mocks (record
   `id`+`delay`, return incrementing integer id), and assert that a manual
   refresh clears the old 60000ms timer, creates a new one, and leaves the
   1000ms countdown timer untouched.

## Checkpoints (each must hold; any breach → REWORK)

1. **fingerprint matches** `f4073da5…`.
2. **fix present & correct**: `loadApi` `finally` contains
   `clearInterval(refreshState.refreshTimer)` + a new `setInterval(..., AUTO_REFRESH_MS)`
   AFTER the `nextRefreshAt` reset (order matters).
3. **countdown independent**: `clearInterval` in `frontend/index.html` targets
   only `refreshState.refreshTimer` (in `finally`), NEVER `refreshState.countdownTimer`.
4. **startAutoRefresh unchanged**: still creates the first `refreshTimer` (60000ms)
   and `countdownTimer` (1000ms); only `loadApi`'s `finally` gained the reschedule.
5. **Red line**: `formatFundingRate` / `formatBeijing*` UNCHANGED.
   `git diff 7592b2c..ee9296c -- frontend/index.html | grep -E '^[+-].*(formatFundingRate|formatBeijing)'` → empty.
6. **No reintroduction**: no `#btn-offline` / `loadFixture()` / `'fixture'` branch.
7. **Same-origin fetch** preserved; no new deps; no direct Binance.
8. **fixture unchanged**: `git diff 7592b2c..ee9296c -- frontend/fixture/` → empty.
9. **No boundary crossing**: `git diff 7592b2c..ee9296c --stat` → only
   `frontend/index.html` + `frontend/self-check.js`. `backend/`, `schemas/`,
   `docs/`, `reports/api-samples/` NOT in the diff.
10. **self-check 20/20 PASS** — run `node frontend/self-check.js` yourself; confirm
    the new timer-reschedule assertion is a genuine RUNTIME mock (mocked
    `setInterval`/`clearInterval` + observing cleared/recreated ids), NOT a
    string/regex assertion on the source.
11. **Decimal discipline**: the fix touches timestamps only; no `parseFloat`;
    no new `Number(` on any rate path.
12. **No forbidden interaction**: no order/buy/sell/borrow/repay/transfer/account UI.

## Read (do not rely on summaries)

- `git diff --binary 7592b2c..ee9296c -- frontend/` (the round-2 fix diff)
- `frontend/index.html`, `frontend/self-check.js`
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/fix-start-prompt-ui-round2.md` (the rework spec)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/50-review-2-round1.md` (the REWORK that triggered this round)
- `docs/api/public-market-contract.md`, `schemas/api/public-market/snapshot.schema.json` (read-only contract)

## Output contract

Write your review to this absolute path:
`/Users/ark/Desktop/ai code/funding_hedging/reports/agent-runs/2026-07-public-market-ui-cn-v1/30-review-1-frontend-round2.md`

Then emit a single JSON verdict object (validates against
`schemas/review-verdict.schema.json`) as the final block of your reply,
fenced in ```json. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `first_reviewer`
- `model`: `glm-5.2[1m]`
- `verdict`: `ACCEPT` / `REWORK` / `BLOCKED`
- `diff_fingerprint`: your recomputed round-2 fix value (`ee9296c…:<sha256>`)
- `reviewer_prior_involvement`: `none` (fresh session)
- `reviewed_artifacts`, `findings[]`, `required_fixes[]`, `residual_risks[]`, `next_action`

If `verdict` is REWORK, include `fix_start_prompt` with raw paths, ordered
findings, required fixes, allowed/forbidden paths, and the exact post-fix
commands (`node frontend/self-check.js`).

End your reply with:
`本地北京时间: <now> CST`
`下一步模型: Claude-GLM (controller)`
`下一步任务: 汇总 review-1 round-2，调度 review-2 Codex rebind 新 head ee9296c`
