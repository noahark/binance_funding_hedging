# Review-1 (task-level) on Task B — Frontend Market Table

You are a **fresh, read-only Claude-GLM session** (`glm-5.2[1m]`), acting as
`reviewer_1` with the `code_reviewer` skill, in **read-only / plan mode**. Do
not modify any files.

> FRESH-SESSION RULE (critical): You must be a brand-new session. You must NOT
> be the stage-controller transcript and must NOT be the Task A (backend)
> implementer transcript. Those transcripts are NOT review evidence and must
> not be fed to you. Review only from the raw artifacts below. If you are
> unsure whether you are a fresh session, stop and flag it.

Stage: `2026-07-public-market-impl-v1`. You are reviewing **Task B only** (the
frontend market table, Kimi-authored). A separate review-1 covers Task A
(backend); do not opine on backend files.

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

- base_sha: `fc018eaae463053f500e9bd412c5f74356de7f20` (the Task-A checkpoint; immediately precedes H_B)
- head_sha: `c1e33b6f1bbb4e67f71db8552a49b35d43700414` (`H_B`)

Recompute the fingerprint yourself from a clean shell in the repository root:

```bash
git diff --binary fc018eaae463053f500e9bd412c5f74356de7f20..c1e33b6f1bbb4e67f71db8552a49b35d43700414 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json' | shasum -a 256
```

The expected `diff_fingerprint` recorded in `status.json.tasks.B` is:

```text
c1e33b6f1bbb4e67f71db8552a49b35d43700414:4bebeb5229021546f78a60fd0effa3f92cb565d3873cdb70795f954a1fb46bde
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

Confirm the diff contains only Task-B files (4 expected: `frontend/index.html`,
`frontend/fixture/public-market-snapshot.json`, `frontend/self-check.js`,
`20-implementation-frontend.md`):

```bash
git diff --binary fc018eaae463053f500e9bd412c5f74356de7f20..c1e33b6f1bbb4e67f71db8552a49b35d43700414 --name-only -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'
```

If any backend, schema, doc, or raw-sample path appears, return REWORK with a
P1 finding (boundary crossing).

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-impl-v1/00-task.md` (Task B scope + UI rules)
- `reports/agent-runs/2026-07-public-market-impl-v1/20-implementation-frontend.md` (Kimi's report)
- `reports/agent-runs/2026-07-public-market-impl-v1/status.json`
- `frontend/index.html`, `frontend/self-check.js`,
  `frontend/fixture/public-market-snapshot.json`
- `schemas/api/public-market/snapshot.schema.json` (the shape the frontend consumes)
- `docs/api/public-market-contract.md` (UI copy / display requirements)
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json` (the frozen sample the fixture must match)
- The frozen diff:
  `git diff --binary fc018eaae463053f500e9bd412c5f74356de7f20..c1e33b6f1bbb4e67f71db8552a49b35d43700414 -- . ':(exclude)reports/agent-runs/2026-07-public-market-impl-v1/status.json'`

## What to verify (Task B — each is a checkpoint)

1. **Same-origin data source**: the default/initial load fetches
   `/api/public-market/snapshot` (relative, same-origin). Confirm `loadApi()` is
   the default path and `loadFixture()` is only a manual fallback (not the
   default). The formal page must NOT hardcode an external host.
2. **Fixture is offline/test only**: `frontend/fixture/public-market-snapshot.json`
   must be byte-identical to the frozen normalized sample. Verify:
   `diff reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json frontend/fixture/public-market-snapshot.json`
3. **No forbidden interactions**: no order / buy / sell / borrow-functionality /
   repay / transfer / open-position ticket / account-balance / position-management
   UI. The ONLY acceptable "borrow" string is the
   `PRIVATE_BORROW_VALIDATION_REQUIRED` enum rendered as a status badge (e.g.
   "需验证借币") — that is a display label, not a borrow action. Grep:
   `grep -nE '下单|买入|卖出|借(币|入)|还款|划转|开仓|账户余额|持仓管理|place.?order|borrow|repay|transfer' frontend/index.html`
   and justify each hit.
4. **UI copy**: data-source label and the funding-rate column copy match the
   contract (e.g. "最近更新的资金费率" semantics for `lastFundingRate`; the
   contract warns this is "most recently updated", not guaranteed settled).
5. **Schema compatibility**: the frontend reads only fields that exist in
   `snapshot.schema.json` with the right types (decimal fields are strings;
   `funding_time` is int; enum values for route_class / asset_tag /
   negative_funding_status).
6. **No planning-calculator / manual-open / order button / account / position
   entry** this stage (hard constraint).
7. **Rendering correctness**: run the self-check yourself:
   `node frontend/self-check.js` (expect 10 PASS, including "无交易按钮/开仓票据").
8. **Scaling note (informational)**: the fixture has 6 rows; the live endpoint
   serves 688. Confirm the rendering logic is row-count-agnostic (no hardcoded
   row-count assumption that would break on 688 rows). This is informational;
   flag as P2/P3 if a hardcoded count exists.

## Known non-blocking residuals (carry forward, do not block)

- The frontend is tested with the 6-row frozen fixture; the live endpoint
  serves the full 688-row market. As long as rendering is row-count-agnostic
  (checkpoint 8), this is acceptable for this stage.

If you find a genuine defect (forbidden interaction present, fixture diverges
from the frozen sample, non-same-origin default, hardcoded external host,
schema-incompatible field access, boundary crossing), return `REWORK` with a
`fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

You may read anything. You may NOT modify any file. You may NOT consult the
controller or Task-A implementer transcripts. Recompute the fingerprint and
re-check the UI rules yourself from the raw code and the frozen sample.

## Output contract (strict)

Write your review to `30-review-1-frontend.md` and end your reply with a single
JSON verdict object that validates against `schemas/review-verdict.schema.json`.
Read that schema. Use exactly:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-impl-v1`
- `role`: `first_reviewer`
- `model`: `glm-5.2[1m]`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed Task-B value
- `reviewer_prior_involvement`: `none`
- `reviewer_prior_involvement_notes`: disclose that you are a fresh read-only
  `claude_glm` session and that the controller and Task A implementer share
  your provider (cross-review + fresh-session isolation justify this review).
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the 6-row-fixture-vs-688-row-live note above
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries (`frontend/**` + the
frontend report only), forbidden paths, and the exact commands to run after the
fix (`node frontend/self-check.js`).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
