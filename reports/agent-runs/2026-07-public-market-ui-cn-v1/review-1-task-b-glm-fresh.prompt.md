# Review-1 (task-level) on Task B — Frontend Chinese-first + funding column merge

You are a **fresh, read-only Claude-GLM session** (`glm-5.2[1m]`), acting as
`reviewer_1` with the `code_reviewer` skill, in **read-only / plan mode**. Do
not modify any files.

> FRESH-SESSION RULE (critical): You must be a brand-new session. You must NOT
> be the stage-controller transcript and must NOT be the Task A (backend)
> implementer transcript. Those transcripts are NOT review evidence and must
> not be fed to you. Review only from the raw artifacts below. If you are
> unsure whether you are a fresh session, stop and flag it.

Stage: `2026-07-public-market-ui-cn-v1`. You are reviewing **Task B only** (the
frontend, Kimi-authored). A separate review-1 covers Task A (backend); do not
opine on backend files.

## Disclosure: same provider as controller / Task A implementer

The stage controller and the Task A (backend) implementer are also
`claude_glm`. You share their provider. This review is permitted because
review-1 uses provider-level cross-review (Task B implementer is `kimi`, so a
`claude_glm` reviewer is the cross-review), AND you are a fresh read-only
session with no prior involvement in Task B's design/breakdown/direction or
implementation. Record `reviewer_prior_involvement: "none"` and disclose the
same-provider fact in `reviewer_prior_involvement_notes`.

## Review subject (recompute this yourself — do not trust this summary)

Task B is a single owner-scoped commit range:

- base_sha: `dba4c12ce61745ef393142af2255a3fc519bf4eb` (H_A; immediately precedes H_B)
- head_sha: `0fd0d17e2835f445cee2195a8ba366df55084123` (H_B)

Recompute the fingerprint yourself from a clean shell in the repository root:

```bash
git diff --binary dba4c12ce61745ef393142af2255a3fc519bf4eb..0fd0d17e2835f445cee2195a8ba366df55084123 -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Expected `diff_fingerprint` (status.json.tasks.B):

```text
0fd0d17e2835f445cee2195a8ba366df55084123:5552ed82f3bb57bdacb1d6f8c981cdc13829603ff865a6458547d6112f8e9835
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

Confirm the diff contains only Task-B files (4 expected: `frontend/index.html`,
`frontend/fixture/public-market-snapshot.json`, `frontend/self-check.js`,
`20-implementation-frontend.md`):

```bash
git diff --binary dba4c12..0fd0d17 --name-only -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json'
```

If any backend, schema, doc, or raw-sample path appears, return REWORK with a
P1 finding (boundary crossing).

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-ui-cn-v1/00-task.md` (Task B scope + UI rules — authoritative)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/10-design.md` (column map + formatFundingRate string-shift algorithm + warnings CN translation)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/11-adr.md` (ADR-3: rate percent string-shift only)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend.md` (Kimi's report)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/60-test-output.txt` (self-check 14/14)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json`
- `frontend/index.html`, `frontend/self-check.js`,
  `frontend/fixture/public-market-snapshot.json`
- `schemas/api/public-market/snapshot.schema.json` (the shape the frontend consumes)
- `docs/api/public-market-contract.md` (UI copy / display requirements)
- The frozen Task-B diff:
  `git diff --binary dba4c12..0fd0d17 -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json'`

## What to verify (Task B — each is a checkpoint)

1. **Rate percent formatting is string-shift only (DECIMAL DISCIPLINE — hard rule).**
   `formatFundingRate` must shift the decimal by string manipulation (regex
   split sign/int/frac; first-2 frac digits into the integer part; pad; trim
   trailing zeros; normalize leading zeros; `-0`→`0`). `parseFloat` / `Number*100`
   on the funding rate is FORBIDDEN. Read `formatFundingRate`, then:
   `grep -nE 'parseFloat|Number\(' frontend/index.html` — justify every hit
   (`formatPrice` mark/index thousands-separator and `classForFundingRate` CSS
   sign-class are NOT rate-percent formatting and are allowed; any use on the
   funding-rate percent path is P0 REWORK). Spot-check outputs:
   `"0.00010000"`→`+0.01%`, `"-0.00005000"`→`-0.005%`, `"0.00000000"`→`0%`,
   `"0.00008556"`→`+0.008556%`, `""`→`—`.
2. **Column merge「资金费率/结算时间」.** Table cols 4/5 merged; cell renders
   `+0.01% / 16:00` (rate + HH:mm Beijing next-funding); full settlement time in
   tooltip. Confirm the merged column reads `lastFundingRate` (string) +
   `nextFundingTime` (int ms → Beijing).
3. **ui_flags de-noise.** Inline badges only for `PERP_ONLY_NO_SPOT_LEG`→「无现货腿」
   and `TRADIFI_BSTOCK`→「bStock」; `MARGIN_PUBLIC_UNVERIFIED` moved to a single
   page-level note (not a per-row badge). No fabricated/removed flags beyond the
   00-task.md / 10-design.md map.
4. **warnings → neutral「数据说明」area.** Three fixed CN translations; English
   originals behind `<details>`/title (not an error-styled block). The CN
   translation of warnings[1] must reflect the NEW evidenced wording (real-time
   estimate — NOT the old "most recently updated"/"ambiguous" framing).
5. **English residue cleared.** `<title>`, page header, "Public Only"/"Read-only"/
   "Manual Refresh" badges all CN; technical terms (USDT, bStock, API, symbol)
   retained; 「PM 现货候选」→「杠杆现货候选」. The main table must NOT emit raw
   English enums directly (technical terms excepted).
6. **fixture.warnings[1] synced to backend.** Verify byte-identity:
   ```bash
   diff <(.venv/bin/python -c "from backend.config import Config; from backend.services.snapshot_service import SnapshotService; print(SnapshotService(Config(offline=True)).build_snapshot()['warnings'][1])") \
        <(.venv/bin/python -c "import json; print(json.load(open('frontend/fixture/public-market-snapshot.json'))['warnings'][1])")
   ```
   (expect no output / identical). If they differ → P1 REWORK.
7. **Same-origin data source; no forbidden interactions.** Default load fetches
   `/api/public-market/snapshot` (relative, same-origin); `loadFixture()` is a
   manual fallback only. No order/buy/sell/borrow-action/repay/transfer/
   open-position/account UI. Grep:
   `grep -nE '下单|买入|卖出|借(币|入)|还款|划转|开仓|账户余额|持仓管理|place.?order|borrow|repay|transfer' frontend/index.html`
   and justify each hit (the `PRIVATE_BORROW_VALIDATION_REQUIRED` / 「需验证借币」
   badge is a display label, allowed; a borrow ACTION is not).
8. **Schema compatibility.** Frontend reads only fields that exist in
   `snapshot.schema.json` with correct types (decimal fields are strings;
   `nextFundingTime` is int ms; enums for route_class / asset_tag /
   negative_funding_status).
9. **self-check passes.** Run: `node frontend/self-check.js` (expect 14 PASS,
   including the 7 funding-rate formatter cases, 数据说明 entry count, and the
   ui_flags mapping assertions).

## Known non-blocking residuals (carry forward, do not block)

- The frontend is tested with the frozen fixture; the live endpoint serves the
  full market. As long as rendering is row-count-agnostic (no hardcoded
  row-count assumption), this is acceptable.

If you find a genuine defect (parseFloat/Number*100 on the rate percent path;
forbidden interaction; fixture diverges from backend warnings[1]; non-same-origin
default; main table emits raw English enums; boundary crossing), return `REWORK`
with a `fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

You may read anything. You may NOT modify any file. You may NOT consult the
controller or Task-A implementer transcripts. Recompute the fingerprint and
re-check the UI rules yourself from the raw code.

## Output contract (strict)

Write your review to `reports/agent-runs/2026-07-public-market-ui-cn-v1/30-review-1-frontend.md` and end your reply with a single
JSON verdict object that validates against `schemas/review-verdict.schema.json`.
Read that schema. Use exactly:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `first_reviewer`
- `model`: `glm-5.2[1m]`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed Task-B value
- `reviewer_prior_involvement`: `none`
- `reviewer_prior_involvement_notes`: disclose you are a fresh read-only
  `claude_glm` session; the controller and Task A implementer share your
  provider (cross-review + fresh-session isolation justify this review).
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the fixture-vs-live row-count note
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries (`frontend/**` + the
frontend report only), forbidden paths, and the exact commands to run after the
fix (`node frontend/self-check.js`).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
