# Review-1 round 1 (task-level, Task B rework) — public-market-ui-cn-v1

You are a **FRESH, read-only Claude-GLM session** (`glm-5.2[1m]`) acting as
`reviewer_1` for **Task B rework round 1**. You have NO prior involvement in
this stage's Task B direction/breakdown/design/implementation/rework — you are
a fresh isolated context (`reviewer_prior_involvement: none`). You may read
anything in the repository; you may modify NOTHING except your own review
report file.

## Context

Stage `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation, public data only). Round-0 (head `9b0e62c`) already passed
review-1 (a fresh GLM session, ACCEPT with 1 P3) + review-2 (Codex ACCEPT) +
pre-accept, then stopped at `stage_accepted_waiting_user`. The user then
directed a **rework round 1** (`fix-start-prompt-ui-round1.md`, entered at
`a263ce6`) to fix P3 residuals + apply 4 UI decisions.

- **Task B (frontend)** was reworked by `kimi` — this is what you re-review.
- **Task A (backend)** is UNCHANGED since `dba4c12` — round-0 Kimi ACCEPT is
  retained and NOT re-reviewed.
- You re-review ONLY the Task B rework (the fix diff), not the whole stage.

## Review subject (recompute this yourself — do not trust this summary)

- base_sha: `0fd0d17e2835f445cee2195a8ba366df55084123` (round-0 Task B head)
- head_sha: `7592b2c740975dc0a6ad2a4b3a17d5a8474494ff` (H_fix, rework round 1)

Recompute the rework fix fingerprint from a clean shell in the repo root:

```bash
git diff --binary 0fd0d17e2835f445cee2195a8ba366df55084123..7592b2c740975dc0a6ad2a4b3a17d5a8474494ff -- frontend/ | shasum -a 256
```

Expected (recorded in `status.json.tasks.B.rework_round1.diff_fingerprint`):

```text
7592b2c740975dc0a6ad2a4b3a17d5a8474494ff:47cdfcc2a1716d929ad7098bf870b268b24d372085e837e932ae34bd8260e1a9
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

## The 4 rework changes (verify each was implemented correctly)

**A. Enum bilingual display** (USER's NEW decision 2026-07-04, **supersedes**
the round-1 pure-Chinese rule — keeping the English enum visible is now
CORRECT, not a defect): route / asset-tag / negative-funding-status columns +
their filter `<option>`s → `ENGLISH(中文)` (full-width parens). 10 enums mapped:

| enum | display |
|---|---|
| MARGIN_SPOT_CANDIDATE | `MARGIN_SPOT_CANDIDATE(杠杆现货候选)` |
| SPOT_ONLY_CANDIDATE | `SPOT_ONLY_CANDIDATE(仅现货候选)` |
| PERP_ONLY_EXCLUDED | `PERP_ONLY_EXCLUDED(仅合约，排除)` |
| CRYPTO | `CRYPTO(加密货币)` |
| BSTOCK | `BSTOCK(美股代币)` |
| UNKNOWN | `UNKNOWN(未知)` |
| PRIVATE_BORROW_VALIDATION_REQUIRED | `PRIVATE_BORROW_VALIDATION_REQUIRED(需私有借币验证)` |
| DISABLED_BSTOCK | `DISABLED_BSTOCK(禁用:bStock 不可借)` |
| DISABLED_SPOT_ONLY | `DISABLED_SPOT_ONLY(禁用:无杠杆)` |
| DISABLED_PERP_ONLY | `DISABLED_PERP_ONLY(禁用:无现货腿)` |

`<option>` `value` unchanged. 提示标记 column (`badgeForUiFlag`) unchanged per spec.

**B. Remove offline-fixture button**: `#btn-offline`, `loadFixture()`, the
`'fixture'` data-source branch, and the "如需离线自检..." prompt copy all
removed. `frontend/fixture/public-market-snapshot.json` + self-check's
data-source usage RETAINED.

**C. 60s auto-refresh**: `AUTO_REFRESH_MS = 60000` (aligned with backend
`Config.cache_ttl_seconds=60`); countdown `下次刷新: Xs` near the market table;
manual refresh retained and resets the countdown.

**D. Sidebar**: `Funding Hedge` → `资金费率对冲`.

## Checkpoints (each must hold; any breach → REWORK)

1. **fingerprint matches** the value above.
2. **Red line**: `formatFundingRate` / `formatBeijing*` UNCHANGED.
   `git diff 0fd0d17..7592b2c -- frontend/index.html | grep -E '^[+-].*(formatFundingRate|formatBeijing)'` → empty.
3. **Decimal discipline**: NO `parseFloat` anywhere; the only `Number(` calls
   are in `formatPrice` / `classForFundingRate` (ADR-3, off the rate-percent
   path); the new countdown math `Math.ceil((nextRefreshAt - Date.now())/1000)`
   is timestamp-only, NOT a rate path.
   `grep -nE 'parseFloat|Number\(' frontend/index.html`.
4. **No new deps**: `git diff 0fd0d17..7592b2c -- frontend/index.html | grep -E '^\+.*<(script|link)|^\+.*import '` → empty.
5. **No direct Binance**; auto-refresh calls `loadApi()` → same-origin
   `/api/public-market/snapshot`. `grep -niE 'binance|fstream' frontend/index.html` (explanatory text only).
6. **fixture unchanged**: `git diff 0fd0d17..7592b2c -- frontend/fixture/public-market-snapshot.json` → empty.
7. **No boundary crossing**: `git diff 0fd0d17..7592b2c --stat` → only
   `frontend/index.html` + `frontend/self-check.js`. `backend/`, `schemas/`,
   `docs/`, `reports/api-samples/` NOT in the diff.
8. **badgeFor\* maps** cover all 10 enums; default `map[x] || x` wrapped in
   `escapeHtml` (defensive, acceptable).
9. **self-check 18/18 PASS** — run `node frontend/self-check.js` yourself.
10. **warnings text frozen**: rework did NOT touch `WARNING_CHINESE` /
    `fixture.warnings[1]`; backend `build_snapshot()['warnings'][1]` remains
    byte-identical (rework is frontend-only).
11. **No forbidden interaction**: no order/buy/sell/borrow-action/repay/transfer/account UI.

## Read (do not rely on summaries)

- `git diff --binary 0fd0d17..7592b2c -- frontend/` (the fix diff)
- `frontend/index.html`, `frontend/self-check.js`, `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/fix-start-prompt-ui-round1.md` (the rework spec)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/30-review-1-frontend.md` (your round-0 verdict; the P3 you raised is now resolved by this rework)
- `docs/api/public-market-contract.md`, `schemas/api/public-market/snapshot.schema.json` (read-only contract)

## Output contract

Write your review to this absolute path:
`/Users/ark/Desktop/ai code/funding_hedging/reports/agent-runs/2026-07-public-market-ui-cn-v1/30-review-1-frontend-round1.md`

Then emit a single JSON verdict object (validates against
`schemas/review-verdict.schema.json`) as the final block of your reply,
fenced in ```json. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `first_reviewer`
- `model`: `glm-5.2[1m]`
- `verdict`: `ACCEPT` / `REWORK` / `BLOCKED`
- `diff_fingerprint`: your recomputed rework value
- `reviewer_prior_involvement`: `none` (fresh session)
- `reviewed_artifacts`, `findings[]`, `required_fixes[]`, `residual_risks[]`, `next_action`

If `verdict` is REWORK, include `fix_start_prompt` with raw paths, ordered
findings, required fixes, allowed/forbidden paths, and the exact post-fix
commands (`node frontend/self-check.js`).

End your reply with:
`本地北京时间: <now> CST`
`下一步模型: Claude-GLM (controller)`
`下一步任务: 汇总 review-1 round-1，调度 review-2 Codex rebind 新 head`
