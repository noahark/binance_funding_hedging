# Review-1 (task-level) — Task B (Frontend, Kimi-authored)

- Stage: `2026-07-public-market-ui-cn-v1`
- Reviewer: `reviewer_1` (fresh, read-only `glm-5.2[1m]` session, `code_reviewer` skill)
- Subject: Task B only — base `dba4c12` (H_A) → head `0fd0d17` (H_B)
- Date: 2026-07-04 CST

## Fresh-session disclosure

I am a brand-new, isolated session. I have NOT seen the controller transcript, the
Task A (backend) implementer transcript, or any prior review of this stage. I
worked only from the raw artifact paths listed in the task prompt. The stage
controller and the Task A implementer are also `claude_glm` (same provider);
this review is permitted because Task B was authored by `kimi` (provider-level
cross-review) and I am a fresh read-only session with no prior involvement in
Task B's direction, breakdown, design, or implementation
(`reviewer_prior_involvement: "none"`).

## Recomputed diff fingerprint

```bash
git diff --binary dba4c12ce61745ef393142af2255a3fc519bf4eb..0fd0d17e2835f445cee2195a8ba366df55084123 \
  -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
# -> 5552ed82f3bb57bdacb1d6f8c981cdc13829603ff865a6458547d6112f8e9835
```

Recomputed value:

```
0fd0d17e2835f445cee2195a8ba366df55084123:5552ed82f3bb57bdacb1d6f8c981cdc13829603ff865a6458547d6112f8e9835
```

Matches `status.json.tasks.B` expected value exactly. No mismatch.

## Diff scope (boundary check)

```bash
git diff --binary dba4c12..0fd0d17 --name-only -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json'
```

Returned exactly the 4 expected Task-B paths, no backend/schema/doc/raw-sample
boundary crossing:

- `frontend/index.html`
- `frontend/fixture/public-market-snapshot.json`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend.md`

## Artifacts inspected directly

- `reports/agent-runs/2026-07-public-market-ui-cn-v1/00-task.md` (Task B scope + UI rules)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/10-design.md` (column map, formatFundingRate algorithm, CN translations)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/11-adr.md` (ADR-3 string-shift rule)
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend.md` (Kimi's report)
- `frontend/index.html` (full read)
- `frontend/self-check.js` (full read)
- `frontend/fixture/public-market-snapshot.json` (full read)
- `schemas/api/public-market/snapshot.schema.json` (full read)
- `docs/api/public-market-contract.md` (lastFundingRate semantics section)
- Frozen Task-B diff `dba4c12..0fd0d17`

## Checkpoint results

### CP1 — Rate percent formatting is string-shift only (DECIMAL DISCIPLINE) — PASS

`formatFundingRate` (`frontend/index.html:586-600`) uses ONLY string manipulation:
regex split `^(-?)(\d+)\.?(\d*)$`, slice first-2 frac digits into integer part,
pad with `'00'`, trim leading zeros, trim trailing zeros from remaining frac,
`-0`/`+0` collapse to `'0%'`, empty/invalid → `'—'`. No `parseFloat` / `Number*100`
on the rate-percent path.

`grep -nE 'parseFloat|Number\(' frontend/index.html` returned 3 hits, all
justified and off the rate-percent path (allowed by ADR-3):

- L604 `Number(str)` — inside `formatPrice` (mark/index price thousands-separator); only used to NaN-guard and to format the integer part of *prices*, never the funding-rate percent.
- L607 `Number(intPart).toLocaleString('en-US')` — also inside `formatPrice`, thousands separator on price integer part.
- L612 `Number(str)` — inside `classForFundingRate`, used solely to pick a CSS sign class (`positive`/`negative`/`muted`); not a percent formatter.

Spot-check of `formatFundingRate` against the design table (executed in Node):

| input | expected | actual | |
|---|---|---|---|
| `"0.00010000"` | `+0.01%` | `+0.01%` | PASS |
| `"-0.00005000"` | `-0.005%` | `-0.005%` | PASS |
| `"0.00000000"` | `0%` | `0%` | PASS |
| `"-0.00000000"` | `0%` | `0%` | PASS |
| `"0"` | `0%` | `0%` | PASS |
| `"0.00008556"` | `+0.008556%` | `+0.008556%` | PASS |
| `""` | `—` | `—` | PASS |

(Extra check: fixture value `"0.00121150"` → `+0.12115%`, correctly
trailing-zero-trimmed per design rule 2 — the algorithm is behaving exactly as
specified.)

### CP2 — Column merge「资金费率/结算时间」 — PASS

`frontend/index.html:502` single merged header
`<th title="本周期实时预估 / 北京时间">资金费率/结算时间</th>`. Cell (L803)
renders `${rateText} / ${timeText}` where `rateText = formatFundingRate(row.futures.last_funding_rate)`
(string) and `timeText = formatBeijingShort(row.futures.next_funding_time)` (int
ms → Beijing `HH:mm`). Full settlement time + raw rate go into the cell `title`
attribute (L789-791): `北京时间 YYYY-MM-DD HH:mm:ss 结算 · 原始费率 {raw} · 预估值，结算时最终确定`.
Matches 10-design.md §1 exactly.

### CP3 — ui_flags de-noise — PASS

`renderTable` (L792-793) filters out `MARGIN_PUBLIC_UNVERIFIED` from inline
badges and renders the remaining flags via `badgeForUiFlag`. The
`MARGIN_PUBLIC_UNVERIFIED` semantics move to a single page-level note
(`renderWarnings` L668-673, `#margin-public-note`). `badgeForUiFlag` (L626-635):
`PERP_ONLY_NO_SPOT_LEG` → 「无现货腿」(muted), `TRADIFI_BSTOCK` → 「bStock」(accent),
unknown values pass-through with original enum in `title`. No fabricated/removed
flags beyond the 00-task / 10-design map.

### CP4 — warnings → neutral「数据说明」area — PASS

Panel title `<h2>数据说明</h2>` (L434), styled with neutral info classes (no
`.warning-item`/`.danger` coloring on this panel). Three fixed CN translations
hard-coded in `WARNING_CHINESE` (L656-660). English originals rendered into
`<details id="warnings-raw"><pre id="warnings-raw-content">` (L441-444,
L682). `WARNING_CHINESE[1]` reflects the NEW evidenced wording — 「表中资金费率
为本周期实时预估值，将于所示结算时间收取，结算前会漂移；已结算历史以
/fapi/v1/fundingRate 为准。」 — NOT the old "ambiguous" framing. Matches the
Task-A backend `CONTRACT_WARNINGS[1]` semantics (real-time estimate, drifts
until settlement, settled history from `/fapi/v1/fundingRate`).

### CP5 — English residue cleared — PASS (with P3 note)

- `<title>资金费率对冲工作台</title>` (L6) — was `费率行情 · Funding Hedge Workstation`.
- Page header `<h1>资金费率对冲工作台</h1>` (L421).
- Badges 公开数据 / 只读 / 手动刷新 (L425-427, btn L456).
- Route select + badge `MARGIN_SPOT_CANDIDATE` → 「杠杆现货候选」 (L478, L619).
- Main-table enum renderers (`badgeForRouteClass`, `badgeForAssetTag`,
  `badgeForNegativeFundingStatus`, `badgeForUiFlag`) all return CN labels;
  raw enum values go into `title=` attributes, not directly into the cell text.
  Technical terms USDT / bStock / API / symbol retained as required.

P3 observation (non-blocking, pre-existing, out of scope): the sidebar brand
wordmark `<span>Funding Hedge</span>` (L398) remains English. Verified via
`git show dba4c12:frontend/index.html` that this string is PRE-EXISTING (was at
L363 in base, unchanged in Task B) and is NOT in the 10-design.md §4 CN-ification
checklist (which lists only title / h1 / subtitle / 3 badges / PM rename). Per
surgical-changes discipline, leaving it untouched is correct. Flagged only so a
future stage can decide.

### CP6 — fixture.warnings[1] synced to backend — PASS

```bash
diff <(.venv/bin/python -c "from backend.config import Config; from backend.services.snapshot_service import SnapshotService; print(SnapshotService(Config(offline=True)).build_snapshot()['warnings'][1])") \
     <(.venv/bin/python -c "import json; print(json.load(open('frontend/fixture/public-market-snapshot.json'))['warnings'][1])")
# exit=0, no output → byte-identical
```

### CP7 — Same-origin data source; no forbidden interactions — PASS

`loadApi()` (L828-846) is the default and fetches the relative same-origin URL
`'/api/public-market/snapshot'` (L833). `loadFixture()` (L848-866) is bound only
to the manual 「加载离线 fixture」 button (L888). No order/buy/sell/borrow-action/
repay/transfer/open-position/account UI.

`grep -nE '下单|买入|卖出|借(币|入)|还款|划转|开仓|账户余额|持仓管理|place.?order|borrow|repay|transfer' frontend/index.html`
returned a single hit — L639 `case 'PRIVATE_BORROW_VALIDATION_REQUIRED': return '<span class="badge warn">需验证借币</span>';`
— which is a display label for the negative_funding_status enum (a *warning*
that borrow validation is required), NOT a borrow action. Allowed per prompt.

### CP8 — Schema compatibility — PASS

Frontend reads only schema-defined fields with correct types:
- `futures.last_funding_rate` (schema `decimal_string`, consumed as string by `formatFundingRate`).
- `futures.next_funding_time` (schema `integer, minimum: 0`, consumed as int ms by `formatBeijing`/`formatBeijingShort`, with `0` → `—`).
- `route_class`, `asset_tag`, `negative_funding_status` consumed via enum-specific badge functions; `ui_flags` is `string[]`.
- `mark_price` / `index_price` (decimal strings) via `formatPrice`.
- `validateContract` enforces `REQUIRED_ROW_FIELDS` + `futures.last_funding_rate`/`next_funding_time` presence before render.

### CP9 — self-check passes — PASS

`node frontend/self-check.js` → 14/14 PASS (transcript recorded in
`60-test-output.txt`), including the 7 funding-rate formatter cases, the
数据说明 entry-count assertion (`chineseItems.length === fixture.warnings.length`),
and the ui_flags mapping assertions (no inline `MARGIN_PUBLIC_UNVERIFIED`, enum
originals in `title`).

## Verdict

**ACCEPT.** All 9 checkpoints pass; fingerprint matches; no boundary crossing;
no blocking trigger (no `parseFloat`/`Number*100` on the rate-percent path, no
forbidden interaction, fixture byte-identical to backend, same-origin default,
no raw English enum emission in the main table). One P3 non-blocking
observation (pre-existing sidebar wordmark, out of Task-B scope).

## Residual risks

- Fixture-vs-live row count: the frozen fixture carries 6 rows while the live
  endpoint serves the full market. Rendering is row-count-agnostic
  (`renderTable` iterates `filteredRows()` with no hardcoded count; `colspan="7"`
  empty/blocked states use the merged-column count), so this is acceptable and
  non-blocking per the prompt's known-residual note.

## Findings (ordered)

- **P3** (informational, non-blocking, pre-existing): sidebar brand wordmark
  `<span>Funding Hedge</span>` (`frontend/index.html:398`) remains English. It
  is pre-existing (present at base `dba4c12` L363, untouched by Task B) and is
  not in the 10-design.md §4 CN-ification checklist, so leaving it unchanged is
  consistent with surgical-changes discipline. Surface for a future stage to
  decide; does not block Task B acceptance.
