# Review-2 round 1 (stage-level, FINAL GATE) — public-market-ui-cn-v1 rework

You are Codex/GPT (`gpt5.5`, xhigh), acting as `reviewer_2` — the **final
review gate** for **rework round 1** — in **read-only** sandbox mode. Do not
modify any file.

Stage: `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation, public data only). This is a **rework round 1** of a stage that
already passed round-0 (review-1 + review-2 Codex ACCEPT + pre-accept, head
`9b0e62c`) and stopped at `stage_accepted_waiting_user`. The user then directed
a rework (`fix-start-prompt-ui-round1.md`, entered at `a263ce6`) to fix P3
residuals + apply 4 UI decisions; the stage head advanced to `7592b2c`.

This is **LOW complexity**: no logic change, no schema change, no structural
change to the API payload — the ONLY changes since round-0 are Task B frontend
display/i18n/behavior (enum bilingual display, offline-button removal, 60s
auto-refresh, sidebar CN). The API payload (rows + warnings) is **frozen**;
only Task B's frontend rendering changed.

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the **prior direction synthesizer** for the covering
contract stage (`2026-07-public-market-contract-v2`), whose user-approved
direction synthesis covers Phase 1 public market. You therefore have **prior
direction-synthesis involvement**, not `none`.

You have **NO** stage-design, development-breakdown, implementation, or
fix-authorship involvement this stage or this round:
- Designer + breakdown author = Anthropic/Fable5.
- Task A implementer = `claude_glm` (round-0; unchanged this round).
- Task B implementer = `kimi` (round-0 + rework round 1).
- Task C integration = the stage controller (`claude_glm`), no product code.
- Rework round-1 reviewer_1 = fresh read-only Claude-GLM session.

The review-2 implementer/fix-author hard ban is satisfied. Per AGENTS.md, no
provider-unrelated decision model exists, so you review via the
**strong-reviewer disclosure override** — identical to round-0 / impl-v1 /
bstock-alias-v1.

**You MUST set `reviewer_prior_involvement: "direction_synthesis"`** and
disclose the above in `reviewer_prior_involvement_notes`.

## Review subject (recompute this yourself — do not trust this summary)

Stage-level commit range (rework round 1):

- base_sha: `b84a34235aa5b37bb0ce83f23ac35e4e5e686899` (`H_intake`)
- head_sha: `7592b2c740975dc0a6ad2a4b3a17d5a8474494ff` (`H_fix`, rework round 1)

Recompute the stage `diff_fingerprint` from a clean shell in the repo root:

```bash
git diff --binary b84a34235aa5b37bb0ce83f23ac35e4e5e686899..7592b2c740975dc0a6ad2a4b3a17d5a8474494ff -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Expected (recorded in `status.json.diff_fingerprint`):

```text
7592b2c740975dc0a6ad2a4b3a17d5a8474494ff:4b8c8de25458e88a9dd8d5f8ab03db0f563305c59492fae548d69683978c4608
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

### NOTE on the stage diff scope (important — do not misread)

`b84a342..7592b2c` is a **wide** range. It legitimately contains, beyond the
product code, several classes of non-product files:

- **Round-0 review evidence** (`30-review-1*.md`, `50-review-2.md`,
  `review-*-*.raw-output.txt`, `review-*-*.prompt.md`) — these commits landed
  AFTER the round-0 fingerprint head `9b0e62c`, so they ride into this stage
  diff because the head advanced past them. They are historical review records,
  not product code.
- **`docs/parallel-development-mode.md`** (+177) — a DRAFT-1/2 methodology doc
  from independent parallel commits (`6894577`/`eba5bc0`), explicitly marked
  non-normative. It is NOT part of this stage's Task A/B/C work and NOT Kimi's
  rework.
- **Task C controller evidence** (`60-test-output.txt`, `20-implementation*.md`,
  `11-adr.md`, `70-handoff.md`) and the rework entry (`fix-start-prompt-ui-round1.md`).

The **product code** in this range is unchanged from round-0 except Task B
frontend. Verify the product-code boundary yourself:
`git show 7592b2c --stat` (H_fix relative to its parent `a263ce6`) must be only
`frontend/index.html` + `frontend/self-check.js` + `20-implementation-frontend-rework1.md`.

### Task-level fingerprints (rework round 1)

- **Task A** (`b84a342..dba4c12`): `dba4c12:8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318` — UNCHANGED from round-0 (backend not in the rework diff). Round-0 Kimi ACCEPT retained.
- **Task B rework fix** (`0fd0d17..7592b2c -- frontend/`): `7592b2c:47cdfcc2a1716d929ad7098bf870b268b24d372085e837e932ae34bd8260e1a9`.
- **Task B cumulative frontend** (`dba4c12..7592b2c -- frontend/`): `7592b2c:9caf18e6e9e7f67b28698cd0df6cad9e22d181fd9236e81be33d07e9e3f9f8e6`.

## What to verify (each is a checkpoint)

### A. Hard constraints (security/safety — any breach is REWORK)

1. **No live HTTP during A/B/C or the rework.** No API key, signed endpoint,
   private account endpoint, user data stream, order/borrow/repay/transfer/websocket.
   `grep -RniE 'apikey|api_key|secret|signature|userDataStream|listenKey|/sapi/|/fapi/v1/order|websocket' backend frontend` (expect none functional).
2. **rows / API payload frozen.** The ONLY API-payload change in the whole stage
   is `warnings[1]` text (from round-0 Task A). The rework round-1 (Task B) does
   NOT touch the API payload at all. Confirm `classify.py` / `normalize.py` /
   `snapshot_service.py` / `schemas/**` are NOT in the rework diff
   (`0fd0d17..7592b2c`). Task C asserts rows field-identical to `548ae0d` (647==647).
3. **Read-only inputs untouched.** `schemas/api/public-market/**` and
   `reports/api-samples/**` must NOT appear in the stage diff. (Note:
   `docs/parallel-development-mode.md` IS in the stage diff but is an independent
   parallel DRAFT methodology doc, not a contract/schema/api-sample — judge
   whether this is a boundary breach or acceptable parallel work.)
4. **Same-origin frontend; no forbidden interaction.** Default load fetches the
   relative `/api/public-market/snapshot`; the new auto-refresh calls the same.
   No order/buy/sell/borrow-action/repay/transfer/open-position/account UI.

### B. Rework round-1 changes (Task B) — the core of this round

5. **`formatFundingRate` / `formatBeijing*` UNCHANGED** (red line).
   `git diff 0fd0d17..7592b2c -- frontend/index.html | grep -E '^[+-].*(formatFundingRate|formatBeijing)'` → empty.
6. **Decimal discipline.** No `parseFloat`; the only `Number(` calls are in
   `formatPrice` / `classForFundingRate` (ADR-3, off the rate-percent path); the
   new countdown math `Math.ceil((nextRefreshAt - Date.now())/1000)` is
   timestamp-only, NOT a rate path.
7. **4 rework changes correctly implemented**: (A) enum bilingual `ENGLISH(中文)`
   for route/asset/negative-funding-status columns + filter options (10 enums;
   user's NEW decision superseding round-1 pure-Chinese rule — keeping English
   enum visible is CORRECT); (B) offline-fixture button + `loadFixture()` +
   `'fixture'` branch removed (fixture file + self-check data-source usage retained);
   (C) 60s auto-refresh + countdown; (D) sidebar `Funding Hedge` → `资金费率对冲`.
8. **fixture unchanged**: `git diff 0fd0d17..7592b2c -- frontend/fixture/public-market-snapshot.json` → empty.
9. **No new deps; no direct Binance.**

### C. Integration & test evidence

10. Re-run yourself: `node frontend/self-check.js` (expect 19/19 PASS — round-0
    14 + rework +5); `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p
    no:cacheprovider backend/tests -q` (expect 54 passed); offline snapshot
    jsonschema VALID (647 rows, 3 warnings).
11. **Review-1 round-1 scrutiny**: fresh GLM ACCEPT (findings empty) on the
    rework fix diff. Confirm the material claims hold independently.
12. **Round-0 verdicts still valid**: Task A backend unchanged -> round-0 Kimi
    ACCEPT stands; round-0 stage verdict (head 9b0e62c) preserved under
    `review_1_round0` / `review_2_round0`, NOT bound to the current head.

### D. Residuals (carry forward, do not block)

- Single mid-period lastFundingRate snapshot evidence (round-0 residual).
- Frontend tested on the frozen fixture; live endpoint serves the full market.
- Spec prose/table paren inconsistency (spec-side, not a product defect).
- `docs/parallel-development-mode.md` parallel DRAFT in the stage diff
  (independent commits, non-product).
- Auto-refresh has no visibility-pause (per spec).

If you find a genuine correctness/safety/boundary defect (product code changed
beyond Task B frontend; rows drift; parseFloat/Number*100 on the rate path;
forbidden interaction; read-only contract/schema/api-sample modified), return
`REWORK` with a `fix_start_prompt`. Otherwise return `ACCEPT`.

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
- `diff_fingerprint`: your recomputed **stage-level** value (`7592b2c…:<sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`** (disclose in notes)
- `reviewed_artifacts`, `findings[]`, `required_fixes[]`, `residual_risks[]`, `next_action`

Emit the JSON verdict as the final block of your reply, fenced in ```json.
