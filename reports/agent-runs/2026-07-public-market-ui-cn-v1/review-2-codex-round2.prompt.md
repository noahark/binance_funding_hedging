# Review-2 round 2 (stage-level, FINAL GATE) — public-market-ui-cn-v1 rework

You are Codex/GPT (`gpt5.5`, xhigh), acting as `reviewer_2` — the **final
review gate** for **rework round 2** — in **read-only** sandbox mode. Do not
modify any file.

Stage: `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation, public data only). This is a **rework round 2** of a stage whose
**round-1 final gate (you, Codex) returned REWORK** on exactly one P2:

> Manual refresh resets the displayed countdown target, but it does not
> reschedule the actual 60s auto-refresh interval, so the next automatic fetch
> can happen before the displayed "下次刷新" reaches zero. There was no
> `clearInterval`/reschedule anywhere in `frontend/index.html`.

Rework round 2 (`fix-start-prompt-ui-round2.md`, entered at `b20b219`) landed
`H_fix2` (`ee9296c`) — Kimi (Task B owner) added, in `loadApi()`'s `finally`,
**after** `nextRefreshAt = Date.now() + AUTO_REFRESH_MS`:
`if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);`
then `refreshState.refreshTimer = setInterval(() => { if (!refreshState.isRefreshing) loadApi(); }, AUTO_REFRESH_MS);`
keeping the 1s countdown timer independent. `startAutoRefresh()` is unchanged.

This round is **LOW complexity**: no logic/schema/payload change beyond that
one frontend behavior fix + its self-check coverage. The API payload (rows +
warnings) is **frozen**; only Task B's frontend timer behavior changed.

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the **prior direction synthesizer** for the covering
contract stage (`2026-07-public-market-contract-v2`), whose user-approved
direction synthesis covers Phase 1 public market. You therefore have **prior
direction-synthesis involvement**, not `none`.

You have **NO** stage-design, development-breakdown, implementation, or
fix-authorship involvement this stage or this round:
- Designer + breakdown author = Anthropic/Fable5.
- Task A implementer = `claude_glm` (round-0; unchanged this round).
- Task B implementer = `kimi` (round-0 + rework rounds 1 and 2).
- Task C integration = the stage controller (`claude_glm`), no product code.
- Rework round-2 reviewer_1 = fresh read-only Claude-GLM session (ACCEPT, findings empty).

The review-2 implementer/fix-author hard ban is satisfied. Per AGENTS.md, no
provider-unrelated decision model exists, so you review via the
**strong-reviewer disclosure override** — identical to round-0 / round-1 /
impl-v1 / bstock-alias-v1.

**You MUST set `reviewer_prior_involvement: "direction_synthesis"`** and
disclose the above in `reviewer_prior_involvement_notes`.

## Review subject (recompute this yourself — do not trust this summary)

Stage-level commit range (rework round 2):

- base_sha: `b84a34235aa5b37bb0ce83f23ac35e4e5e686899` (`H_intake`)
- head_sha: `ee9296c705d3590adb01bf2fff433e32e834523e` (`H_fix2`, rework round 2)

Recompute the stage `diff_fingerprint` from a clean shell in the repo root:

```bash
git diff --binary b84a34235aa5b37bb0ce83f23ac35e4e5e686899..ee9296c705d3590adb01bf2fff433e32e834523e -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Expected (recorded in `status.json.diff_fingerprint`):

```text
ee9296c705d3590adb01bf2fff433e32e834523e:f4637f8a13f8bd35ddc7ac0243fc9037afed9380442b630f2fd5518ae7be1d81
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

### NOTE on the stage diff scope (important — do not misread)

`b84a342..ee9296c` is a **wide** range. It legitimately contains, beyond the
product code, several classes of non-product files:

- **Round-0 / round-1 review evidence** (`30-review-1*.md`, `50-review-2*.md`,
  `review-*-*.raw-output.txt`, `review-*-*.prompt.md`) — historical review records.
- **`docs/parallel-development-mode.md`** — a DRAFT methodology doc from
  independent parallel commits (`6894577`/`eba5bc0`/`6e945c8`), explicitly marked
  non-normative. It is NOT part of this stage's Task A/B/C work and NOT Kimi's rework.
- **Task C controller evidence** (`60-test-output.txt`, `20-implementation*.md`,
  `11-adr.md`, `70-handoff.md`) and rework entries (`fix-start-prompt-ui-round{1,2}.md`).

The **product code** in this range is unchanged from round-1 except Task B
frontend (round-2 timer-sync). Verify the product-code boundary yourself:
`git show ee9296c --stat` (`H_fix2` relative to its parent `b20b219`) must be only
`frontend/index.html` + `frontend/self-check.js` + `20-implementation-frontend-rework2.md`.

### Task-level fingerprints (rework round 2)

- **Task A** (`b84a342..dba4c12`): `dba4c12:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318` — UNCHANGED. Round-0 Kimi ACCEPT retained.
- **Task B rework round-2 fix** (`7592b2c..ee9296c -- frontend/`): `ee9296c:f4073da548a299234daba3bc0296cf82433fd71438313f7fdba8943a93442226`.
- **Task B cumulative frontend** (`dba4c12..ee9296c -- frontend/`): `ee9296c:1ccb1c0d1ee3d0f059ecd90371019596a330ffc02754fe9b05f159828fb49d7a`.

## What to verify (each is a checkpoint)

### A. Hard constraints (security/safety — any breach is REWORK)

1. **No live HTTP during A/B/C or the rework.** No API key, signed endpoint,
   private account endpoint, user data stream, order/borrow/repay/transfer/websocket.
   `grep -RniE 'apikey|api_key|secret|signature|userDataStream|listenKey|/sapi/|/fapi/v1/order|websocket' backend frontend` (expect none functional).
2. **rows / API payload frozen.** The ONLY API-payload change in the whole stage
   is `warnings[1]` text (from round-0 Task A). The rework round-2 (Task B) does
   NOT touch the API payload. Confirm `classify.py` / `normalize.py` /
   `snapshot_service.py` / `schemas/**` are NOT in the rework round-2 diff
   (`7592b2c..ee9296c`). Task C asserts rows field-identical to `548ae0d` (647==647).
3. **Read-only inputs untouched.** `schemas/api/public-market/**` and
   `reports/api-samples/**` must NOT appear in the round-2 product diff
   (`git diff 7592b2c..ee9296c -- schemas/ reports/api-samples/` → empty). (Note:
   `docs/parallel-development-mode.md` IS in the wide stage range but is an
   independent parallel DRAFT methodology doc, not a contract/schema/api-sample.)
4. **Same-origin frontend; no forbidden interaction.** Default load + auto-refresh
   + manual refresh all fetch the relative `/api/public-market/snapshot`. No
   order/buy/sell/borrow-action/repay/transfer/open-position/account UI.

### B. THE ROUND-2 FIX — does it resolve YOUR round-1 P2?

5. **Timer reschedule present & correct** in `frontend/index.html` `loadApi`'s
   `finally`: AFTER `nextRefreshAt = Date.now() + AUTO_REFRESH_MS`,
   `if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);`
   then `refreshState.refreshTimer = setInterval(() => { if (!refreshState.isRefreshing) loadApi(); }, AUTO_REFRESH_MS);`.
   Order matters (clear + recreate must follow the nextRefreshAt reset).
6. **Countdown timer independent**: the only `clearInterval` in the file targets
   `refreshState.refreshTimer`, NEVER `refreshState.countdownTimer`.
   `grep -n 'clearInterval' frontend/index.html` → exactly the refreshTimer clear.
7. **startAutoRefresh() unchanged**: still creates the first 60000ms `refreshTimer`
   + the 1000ms `countdownTimer`; no `visibilitychange`/`requestIdleCallback`/
   retry/backoff added.
8. **Behavioral invariant**: after the fix, the actual next auto-fetch instant
   == `nextRefreshAt` == the moment the countdown display hits 0, for EVERY
   `loadApi()` completion (manual / auto / success / failure). Confirm the P2 you
   raised in round-1 is genuinely resolved (not just papered over).
9. **`formatFundingRate` / `formatBeijing*` UNCHANGED** (red line).
   `git diff 7592b2c..ee9296c -- frontend/index.html | grep -E '^[+-].*(formatFundingRate|formatBeijing)'` → empty.
10. **No reintroduction** of `#btn-offline` / `loadFixture()` / `'fixture'` branch.
11. **fixture unchanged**: `git diff 7592b2c..ee9296c -- frontend/fixture/` → empty.
12. **No new deps; no direct Binance.**

### C. Integration & test evidence

13. Re-run yourself: `node frontend/self-check.js` (expect **20/20 PASS** — round-1
    19 + round-2 timer-reschedule). Confirm the new assertion is a **genuine runtime
    mock** (mocked `setInterval`/`clearInterval` recording id+delay and observing
    cleared/recreated ids), NOT a source string/regex check.
14. `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q`
    (expect 54 passed; backend unchanged in round 2). Offline snapshot jsonschema VALID.
15. **Review-1 round-2 scrutiny**: fresh GLM ACCEPT (findings empty) on the round-2
    fix diff. Confirm the material claims hold independently.
16. **Prior verdicts still valid**: Task A backend unchanged -> round-0 Kimi ACCEPT
    stands; round-1 review-1 ACCEPT preserved under `review_1_round1`; round-1
    review-2 REWORK (the one you raised) preserved under `review_2_round1`; round-0
    verdicts under `_round0`. Only the round-2 verdict binds to the current head.

### D. Residuals (carry forward, do not block)

- Single mid-period lastFundingRate snapshot evidence (round-0 residual).
- Frontend tested on the frozen fixture; live endpoint serves the full market.
- Spec prose/table paren inconsistency (spec-side, not a product defect).
- `docs/parallel-development-mode.md` parallel DRAFT in the stage diff (independent commits, non-product).
- Wide range diff includes process bookkeeping commits (review records, rework entries).

If you find a genuine correctness/safety/boundary defect, or the round-1 P2 is
NOT actually resolved, return `REWORK` with a `fix_start_prompt`. Otherwise
return `ACCEPT`.

## Boundary (read-only)

You may read anything. You may NOT modify any file. You may NOT be swayed by
controller/review-1 narratives — recompute fingerprints and re-check rules
yourself against the raw code, the raw diff, and the frozen contract.

## Output contract (strict)

Emit your review narrative, then a single JSON verdict object that validates
against `schemas/review-verdict.schema.json`. Use:

- `schema_version`: `1`; `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `final_reviewer` (or `second_reviewer` if the schema enum requires it)
- `model`: `gpt5.5`; `verdict`: `ACCEPT`/`REWORK`/`BLOCKED`
- `diff_fingerprint`: your recomputed **stage-level** value (`ee9296c…:<sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`** (disclose in notes)
- `reviewed_artifacts`, `findings[]`, `required_fixes[]`, `residual_risks[]`, `next_action`

Emit the JSON verdict as the final block of your reply, fenced in ```json.
