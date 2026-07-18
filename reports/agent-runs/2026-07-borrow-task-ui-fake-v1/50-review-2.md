# Review-2 — Final Gate — Opus 4.8

Stage: `2026-07-borrow-task-ui-fake-v1`
Reviewer: Anthropic Opus 4.8, read-only.
Verdict: **ACCEPT** (no unresolved P0/P1/P2; five P3 findings recorded).

## 0. Reviewer Prior Involvement Disclosure

The Anthropic provider authored this stage's development breakdown
(`12-development-breakdown.md`, via `claude-fable-5`). Per
`workflows/templates/stage-delivery.yaml` (`"Breakdown is design involvement for
review-2 disclosure purposes."`), that is disclosable prior involvement, so this
verdict sets `reviewer_prior_involvement: "breakdown"`.

No Anthropic model wrote any reviewed delivery or fix code in this stage. The
reviewed code authors are `zhipu_glm` (backend task
`backend-minimum-borrow-contract-b1`) and `moonshot_kimi` (frontend tasks
`frontend-borrow-task-fake-f2` / visual fix F3), confirmed independently from
`status.json.implementers = ["claude_glm", "kimi"]` and the per-task `owner`
fields. `status.json.fix_authors` is empty. The gate
`review_2_provider_must_differ_from_any_code_author_provider` therefore holds:
`anthropic` ∉ {`zhipu_glm`, `moonshot_kimi`}.

The override route itself is disclosed in
`66-review-2-strong-reviewer-override.md`: Codex/GPT is the recorded stage
designer (`status.json.designer = "codex"`), the user selected Opus 4.8 instead
of the designer for the final gate, and
`review_2_design_conflict_override_allowed: true` permits this. I reviewed the
breakdown as evidence under review, not as a requirement source; the requirement
sources I treated as binding were `00-task.md` and its amendments v2/v3/v4,
`13-scope-amendment-v2.md`, `14-user-min-borrow-contract-amendment.md`,
`docs/product/PRD.md`, and `docs/architecture/ARCHITECTURE.md`.

## 1. Range And Fingerprint Verification

I never moved `HEAD` (working tree stayed at `9c206bb`, branch
`stage/2026-07-borrow-task-ui-fake-v1`) and reviewed exactly the committed range.

```
git diff --binary d9c2772b7725bc794224a99c70505526eaedf295..9d53204d450ee0dc4519f52201b575e5b71e948b \
  -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json' | shasum -a 256
a51dccee4055065ceece4ee3cee037909c096da4cf36a55144d945e757d025f3
```

This matches the required fingerprint
`9d53204d450ee0dc4519f52201b575e5b71e948b:a51dccee4055065ceece4ee3cee037909c096da4cf36a55144d945e757d025f3`
byte for byte. Commits after `9d53204d` were treated as evidence only and no
delivery-code judgement rests on them.

Range scope: 37 files, +2985/−66. Delivery code is confined to
`backend/domain/snapshot.py`, `backend/services/private_client.py`,
`schemas/api/public-market/snapshot.schema.json`, the four backend test/fixture
files, `frontend/index.html`, `frontend/self-check.js`, and the raw sample at
`reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json`.
Every one of those is on the `00-task.md` allowed list. The remaining changed
paths are stage evidence under `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/`
plus `reports/agent-runs/ACTIVE.json`; those are bookkeeper-authored orchestration
artifacts, which `AGENTS.md` ("Orchestrator And Bookkeeper") places under the
bookkeeper's write authority rather than the implementer file boundary. No
`docs/**`, `workflows/**`, `agents/**`, or unrelated `backend/**` path was
touched. Diff scope is clean.

## 2. Independent Deterministic Checks

All three were run by me at the fixed head, read-only. No credentials, no live
Binance call, no borrow/repay/transfer/order request, no background loop.

| Check | Result |
|---|---|
| `python3 -m pytest backend/tests -q` | **394 passed in 16.56s** |
| `node frontend/self-check.js` | **28 `[PASS]` blocks, 全部自检通过** |
| `git diff --check <base>..<head>` | exit 2 — one trailing-whitespace hit, see P3-1 |

The test evidence in the stage files is factual, not fabricated. `61-test-output-backend.txt`
claims `394 passed in 16.26s`; I independently reproduce 394 passed. `64-test-output-frontend-visual-fix.txt`
claims the full self-check block list ending in `[PASS] 操作按钮绿/灰/红主题与
borrowing/paused 禁用态显式呈现`; my run reproduces exactly that list, in order,
including the F3 visual-theme assertion. `61-test-output-backend.txt` also records
matching SHA-256 digests for the source and stage copies of the raw sample; I
verified independently that the two files are byte-identical (`diff` reports no
difference) and that the copy has 409 records, 409 of which carry `userMinBorrow`,
all with the raw value `"0"` and first record `{"assetName": "BTC", ..., "userMinBorrow": "0"}`.
That is precisely what `14-user-min-borrow-contract-amendment.md` froze as the
required raw evidence.

## 3. Requirement-By-Requirement Findings

### 3.1 Fake borrow-task UI and the no-side-effect boundary

This is the highest-risk property of the stage — the whole point is that nothing
real happens — so I verified it by exhaustive grep over the delivered file rather
than by trusting the self-check.

`frontend/index.html` contains exactly two `fetch(` call sites (lines 1730 and
2354), both to `/api/public-market/...` snapshot endpoints that predate this
stage. It contains exactly three `setInterval` call sites (1313, 1316, 2373), all
belonging to the pre-existing 60-second refresh and countdown. It contains exactly
two `localStorage` accesses (1028, 1037), both the pre-existing privacy toggle.
There is no `setTimeout`, no `XMLHttpRequest`, no `sendBeacon`, and no `WebSocket`
anywhere in the file. Consequently no borrow-task code path — creation, pause,
start, delete, edit, filter, or view switch — can issue a network request, start
a retry timer, or persist anything. The requirement holds structurally, not just
by assertion.

The self-check's own no-side-effect block (`frontend/self-check.js` §74) is a real
before/after comparison against mocked `fetch`/`setInterval`/`localStorage`, not a
cosmetic assertion; it snapshots `fetchCallLog.length`, `intervalCalls.length`, and
`Object.keys(localStorageData).length`, exercises pause/start/filter/edit, and
re-compares. That is sound. Its one coverage gap is recorded as P3-3.

Task creation (`createBorrowTask`) reads `row.base_asset` from the snapshot row,
with no special-casing anywhere, so `HOME` flows through the same generic path as
any other asset — the `HOMEUSDT` row is never fabricated, satisfying the
Non-Goal. Validation is correct: amount must parse to a finite `> 0` number,
count must be an integer `> 0`, and both reject blank/whitespace input; a failure
returns before any state mutation and `submitBorrowTask` writes the message into
the row-local `#borrow-error-<symbol>` element. Event isolation is real: the
operation cell stops propagation for both `click` and `keydown`, and the confirm
button additionally calls `stopPropagation()` before submitting, so operating the
cell cannot open the market detail drawer.

Two inputs plus one confirm button per row, the new `操作` header after
`借贷状态 / 资产`, and `colspan` raised from 12 to 13 in both the blocked and
empty-state branches — all present and consistent.

### 3.2 Lifecycle, editing, soft deletion, filters, disabled matrix, themes

The state machine matches `13-scope-amendment-v2.md` exactly. New tasks are
`borrowing`. `pauseBorrowTask`/`startBorrowTask` are guarded inverse transitions
that touch only `status`, never `successCount`. `deleteBorrowTask` sets
`status = 'deleted'` and — critically for the 已删除 filter to be meaningful —
never removes the object from `state.borrowTasks`; it also accepts a `completed`
task, as the amendment requires. `editBorrowTask` refuses any status other than
`borrowing`/`paused`, so deleted and completed tasks are genuinely read-only at
the state layer and not merely visually disabled; on success it preserves
`successCount` and the displayed total is recomputed from the new
`amountPerAttempt * successTarget`.

The disabled matrix in `renderBorrowTasks` is derived directly from status
(`startDisabled` when not `paused`, `pauseDisabled` when not `borrowing`,
`deleteDisabled` when `deleted`, `editDisabled` when `deleted` or `completed`)
and the self-check walks all four states cell by cell. Filters derive both
membership and counts from the authoritative `state.borrowTasks` array, with
`all` including soft-deleted tasks.

On the v4 visual fix specifically, I checked the CSS cascade myself rather than
relying on the self-check's string ordering test. `.btn.action-start`,
`.btn.action-pause`, and `.btn.action-delete` each have specificity (0,2,0), and
`.btn:disabled` also has (0,2,0) — so the disabled presentation wins only because
it is declared *after* the three theme rules. It is, and the self-check pins that
ordering with an `indexOf` comparison. Green/grey/red themes and an explicit
disabled presentation independent of theme are both satisfied.

### 3.3 No duplicate 已借完; minimum-borrow placeholder

`maxBorrowableSubline` no longer emits the `已借完` badge; the sub-line is now
just `可借: <amount>(≈ … USDT)`. The status badge path
(`badgeForNegativeFundingStatus`) is untouched, so `可借 0(已借完)` is retained
exactly once. Confirmed by the dedicated self-check block.

`minBorrowPlaceholder` implements the three frozen branches correctly, including
the raw-zero case: `"0"` is a string and not empty, so it takes the full branch
and renders `最小借币量 0 (≈ 0.00 USDT)` rather than being swallowed by a
falsy check — this is the exact trap the amendment called out, and the
implementation avoids it by testing `typeof raw !== 'string' || raw === ''`
instead of truthiness. The output is passed through `escapeHtml` before being
interpolated into the `placeholder="…"` attribute. The input carries no `value`
attribute (self-check asserts the absence), so the field stays empty and is
guidance only; validation, task creation, and the task-list edit inputs are
untouched by it — the self-check verifies the edit inputs still have `value=`
prefill and no `placeholder`.

### 3.4 Backend `userMinBorrow` contract

`private_client.fetch_classic_reference` adds `user_min_borrow_by_name` as a
plain `assetName → x.get("userMinBorrow")` mapping. No `bool()`, `float()`, or
`Decimal()` coercion — the raw decimal string survives verbatim, and a record
missing the field maps to `None`. This mirrors `asset_borrowable_by_name`
structurally, which is what the amendment demanded.

`assemble_borrow_validation` gates the field identically to `asset_borrowable`,
and I checked all four branches rather than the happy path only:

- classic reference unavailable → the early-return dict hard-codes both fields to
  `None`;
- `pair_listed` false/absent → `user_min_borrow = None`, and the valuation helper
  short-circuits on `None` so the value is `None` too;
- `borrowability_truncated` → the branch retains both fields alongside
  `asset_borrowable` and the interest fields, clearing only `portfolio_account`;
- normal → both fields populated.

`_user_min_borrow_value_usdt` (`backend/domain/snapshot.py:803`) is a deliberate
sibling of `_max_borrowable_value_usdt`, not a reuse of it: same stablecoin
short-circuit and same `<ASSET>USDT` price routing, but quantized to
`Decimal("0.01")` with `ROUND_HALF_UP` and formatted with `format(..., "f")` so no
scientific notation can leak. It carries the same negative-zero normalization
(`if value == 0: value = Decimal(0)`) that `_quantize_rate` uses, which is not
redundant — without it a negative-zero product would render `-0.00` and be
cosmetically wrong. The eight-decimal `max_borrowable_value_usdt` path is
untouched and there is a test asserting both precisions coexist
(`"60.00000000"` vs `"60.00"` from the same inputs).

Schema: both fields added as required with `additionalProperties: false` intact,
typed `decimal_string | null`. The test suite covers the positive path, the
missing-required-field negative, and the undeclared-property negative — genuine
negative schema coverage, not just a happy-path validate. `test_phase2_borrow_sort.py`
asserts the offline/classic-ref-`None` branch emits both as `None`, and the
design fixture was updated across all six rows including the two null-branch rows.
Half-up rounding is pinned at the boundary (`1.005 → "1.01"`, `55.555 → "55.56"`)
and a regex asserts exactly two decimals.

### 3.5 Escalation judgement on the known P3s and residual risks

The dispatch asked me to decide independently whether any prior P3 or residual
risk deserves elevation. My judgement: **none of them are P0/P1/P2 for this
stage**, but two need to be carried forward explicitly.

The whole-view rerender that clears unsubmitted edits (Review-1 P3, and the same
class as the 60-second market-table rerender) stays P3 here. Nothing is lost but
uncommitted keystrokes, no confirmed state is affected, and no acceptance
criterion is violated. I am not elevating it — but I do want it on record that
this defect changes character the moment this UI is wired to real borrowing: a
60-second timer silently clearing a half-typed borrow amount is a materially
worse problem when the next keystroke sequence sends a real order. It should be
fixed before, not after, the backend stage.

The `role="button"` row with focusable descendants also stays P3, with the same
caveat. It was already an ARIA violation before this stage; this stage put two
text inputs and a confirm button inside that button-role row on every data row,
so the affected surface grew substantially. Screen-reader users cannot reliably
reach the new operation controls. Not blocking for a fake prototype, but it is
now the largest accessibility debt in the file and should be resolved in the next
UI stage rather than accumulating further.

The unexecuted browser/DevTools visual verification is an acceptable gap here
because the properties in question (theme classes, disabled attributes, cascade
order) are all statically decidable, and I decided them myself in §3.2 by reading
the CSS specificity and declaration order rather than trusting the DOM-level
assertion alone.

The all-zero `userMinBorrow` sample is a fact about Binance's current response,
not a shortfall by the implementer; the amendment explicitly permitted synthetic
supplementation, and synthetic non-zero coverage exists. No elevation.

## 4. Findings (all P3, none blocking)

**P3-1 — `git diff --check` is not clean over the reviewed range.**
`reports/agent-runs/2026-07-borrow-task-ui-fake-v1/29-kimi-frontend-f2.dispatch.md:29`
has trailing whitespace, so `git diff --check <base>..<head>` exits 2. The stage
evidence is not wrong: `60/62/64-test-output*.txt` and `67-pre-review-validation-review2.txt`
all record the *worktree* form `git diff --check` (exit 0), which is what the
implementer acceptance criterion means and which I also reproduce as clean. The
range form is what the dispatch asked me to run, and it flags a bookkeeper-authored
dispatch document, not delivery code. No product behavior is affected.

**P3-2 — `formatTaskAmount` renders sub-1e-6 amounts as `0`.**
`frontend/index.html:2142` builds the display string via
`String(Number(value.toPrecision(12))).split('.')`. For values where JavaScript
switches to exponential notation, that split produces no fractional part and
`Number("1e-7").toLocaleString('en-US')` collapses to `"0"`. I reproduced it:
`formatTaskAmount(1e-7)` and `formatTaskAmount(5e-7)` both return `"0"`. Such an
amount passes `parseBorrowAmount` (finite and `> 0`), so a valid task can render
as `0 <ASSET>/次` and `目标 0 <ASSET>` while `amountPerAttempt` holds the correct
value in memory. Display-only, unreachable for realistic borrow amounts, and
harmless in a fake prototype — but it becomes a misreporting bug the moment the
displayed figure describes a real borrow. The `toPrecision(12)` normalization
that fixes float tails (`0.1*3 → 0.3`, verified) is otherwise correct.

**P3-3 — the no-side-effect assertion covers `setInterval` but not `setTimeout`.**
`frontend/self-check.js:34` mocks `setInterval`/`clearInterval` and the §74 block
compares `intervalCalls.length` before and after. `setTimeout` is deliberately
left native (the harness awaits on it), so a retry loop built on `setTimeout` or
`requestAnimationFrame` would not be caught by the "零定时器" assertion. The
property itself currently holds — I confirmed by grep that `index.html` contains
no `setTimeout` at all — so this is an assertion-coverage gap, not a live defect.
It matters for the next stage, where a scheduler is the explicit subject.

**P3-4 — `submitBorrowTask` looks up element IDs with the unescaped symbol.**
`frontend/index.html:2129` composes `borrow-amount-${symbol}` from the raw symbol,
while `renderRow` emits the ID as `borrow-amount-${escapeHtml(row.symbol)}`. The
snapshot schema constrains `symbol` only to `{"type": "string", "minLength": 1}`,
so a symbol containing `&`, `<`, `>`, or `"` would desynchronize the two forms and
`getElementById` would return `null`. The failure mode is benign — the helper
passes `''` and the user sees the ordinary validation error — and there is no
injection surface, since every new attribute is double-quoted and escaped. Purely
a consistency nit at present.

**P3-5 — `status.json` top-level identity fields under-report the stage.**
`implementer` is the single value `"kimi"` although `implementers` correctly lists
`["claude_glm", "kimi"]`, and top-level `review_1` is all-`null` although both
per-task `review_1` objects are complete, fingerprinted, ACCEPT, and correctly
provider-isolated (B1 by `claude_glm` reviewed by `moonshot_kimi`; F2/F3 by `kimi`
reviewed by `claude_glm`). This is the aggregation defect already disclosed in
`66-review-2-strong-reviewer-override.md` and slated for a separate Harness
repair. I record it as a finding rather than waiving it, because
`review_2_provider_must_differ_from_any_code_author_provider` is machine-checked
against these fields: an automated gate reading top-level `implementer` alone
would not see `zhipu_glm` as a code author. I established provider isolation from
the per-task records instead, and it holds. `status.json` is excluded from the
reviewed diff, so this is a bookkeeping correction, not a delivery-code change.

## 5. Verdict Rationale

Every frozen requirement across `00-task.md` and amendments v2/v3/v4 is met.
The no-side-effect boundary — the property that actually protects the user's
account in this stage — holds structurally and I verified it independently of the
self-check. The backend contract preserves raw strings, mirrors the
`asset_borrowable` gates across all four branches, hits exactly two decimals with
`ROUND_HALF_UP`, leaves the eight-decimal contract alone, and is backed by real
negative schema coverage and byte-identical raw sample evidence. Test evidence in
the stage files is factual and reproducible. Diff scope is clean.

The five findings are all P3: one whitespace hit in a bookkeeper document, one
display edge case unreachable for realistic values, one assertion-coverage gap on
a property that currently holds, one naming-consistency nit with a benign failure
mode, and one bookkeeping aggregation defect already disclosed and scheduled for
repair. None is a correctness defect in delivered product behavior, and none
requires rework before acceptance.

Two items must not be lost when this UI is connected to real borrowing: the
rerender-clears-input class of defect (P3 here, materially riskier there) and the
`role="button"` nesting violation (now spanning every data row).

ACCEPT. Merging to `main` still requires explicit user acceptance per
`review_2_accept_does_not_merge_main` and `merge_to_main_requires_user_acceptance`.

当前 Session ID: unavailable (Claude Code session; no provider-native Session ID exposed to the model)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/50-review-2.md
本地北京时间: 2026-07-19 02:14:07 CST
下一步模型: 无（等待用户验收决定）
下一步任务: 用户审阅 Review-2 ACCEPT 后决定是否合并 main

{"schema_version":1,"stage_id":"2026-07-borrow-task-ui-fake-v1","role":"final_reviewer","model":"opus4.8","verdict":"ACCEPT","diff_fingerprint":"9d53204d450ee0dc4519f52201b575e5b71e948b:a51dccee4055065ceece4ee3cee037909c096da4cf36a55144d945e757d025f3","reviewer_prior_involvement":"breakdown","reviewer_prior_involvement_notes":"Disclosed under 66-review-2-strong-reviewer-override.md. The Anthropic provider authored 12-development-breakdown.md (via claude-fable-5), which stage-delivery.yaml classifies as design involvement for review-2 disclosure purposes. No Anthropic model wrote any reviewed delivery or fix code: the reviewed code authors are zhipu_glm (backend-minimum-borrow-contract-b1) and moonshot_kimi (frontend-borrow-task-fake-f2 and the F3 visual fix), confirmed from status.json.implementers and per-task owner fields, with status.json.fix_authors empty. review_2_provider_must_differ_from_any_code_author_provider therefore holds. The override route is the design-conflict-ineligibility path permitted by review_2_design_conflict_override_allowed, since status.json.designer is codex and the user selected Opus 4.8 instead of the designer for the final gate. The breakdown was reviewed as evidence under review, not treated as a requirement source.","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","schemas/review-verdict.schema.json","schemas/api/public-market/snapshot.schema.json","docs/product/PRD.md","docs/architecture/ARCHITECTURE.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/21-implementation-backend.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/23-implementation-frontend-visual-fix.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/31-review-1-backend-retry-1.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/32-review-1-frontend-retry-1.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/31-review-1-backend.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/32-review-1-frontend.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/60-test-output.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/61-test-output-backend.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/62-test-output-frontend-v2.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/64-test-output-frontend-visual-fix.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/65-pre-review-validation-f3.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/66-review-2-strong-reviewer-override.md","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/67-pre-review-validation-review2.txt","reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json","backend/services/private_client.py","backend/domain/snapshot.py","backend/tests/test_private_client.py","backend/tests/test_private_account_v1.py","backend/tests/test_phase2_borrow_sort.py","backend/tests/fixtures/private-account-v1-design.json","frontend/index.html","frontend/self-check.js","reports/api-samples/2026-07-borrow-task-ui-fake-v1/sapi-v1-margin-allAssets.json","reports/api-samples/2026-07-private-account-v1/20260705T232800Z/sapi-v1-margin-allAssets.json","git diff --binary d9c2772b7725bc794224a99c70505526eaedf295..9d53204d450ee0dc4519f52201b575e5b71e948b -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json'"],"findings":[{"severity":"P3","title":"git diff --check is not clean over the reviewed commit range","file":"reports/agent-runs/2026-07-borrow-task-ui-fake-v1/29-kimi-frontend-f2.dispatch.md","line":29,"evidence":"git diff --check d9c2772b..9d53204d exits 2 with 'trailing whitespace' at 29-kimi-frontend-f2.dispatch.md:29. The stage evidence (60/62/64-test-output*.txt, 67-pre-review-validation-review2.txt) records the worktree form 'git diff --check' at exit 0, which this reviewer also reproduces as clean; the two forms simply check different things.","impact":"No product behavior affected. The flagged line is in a bookkeeper-authored dispatch document, not delivery code, and is outside the implementer file boundary. It only means the range form of the check required by the review dispatch is not clean.","recommendation":"Bookkeeper may strip the trailing whitespace in a follow-up evidence commit, and future acceptance criteria should state which form of git diff --check is normative."},{"severity":"P3","title":"formatTaskAmount renders amounts below 1e-6 as 0","file":"frontend/index.html","line":2142,"evidence":"formatTaskAmount does String(Number(value.toPrecision(12))).split('.'); for exponential-notation values there is no fractional part and Number('1e-7').toLocaleString('en-US') yields '0'. Reproduced directly: formatTaskAmount(1e-7) === '0' and formatTaskAmount(5e-7) === '0'. Such a value passes parseBorrowAmount (finite, > 0), so the task is created with the correct in-memory amountPerAttempt while the card renders '0 <ASSET>/次' and '目标 0 <ASSET>'.","impact":"Display-only and unreachable for realistic borrow amounts; in-memory state stays correct and no acceptance criterion is violated in this fake prototype. It would become a misreporting defect once the displayed figure describes a real borrow.","recommendation":"Format via toLocaleString with maximumFractionDigits, or handle the exponential-notation branch explicitly, before this view is connected to real borrowing."},{"severity":"P3","title":"No-side-effect self-check covers setInterval but not setTimeout","file":"frontend/self-check.js","line":34,"evidence":"The harness mocks setInterval/clearInterval and the §74 block compares intervalCalls.length before and after every new task action, but setTimeout is left native because the harness awaits on it. A retry loop built on setTimeout or requestAnimationFrame would not trip the '零定时器' assertion. The property itself currently holds: grep confirms frontend/index.html contains no setTimeout, no XMLHttpRequest, no sendBeacon and no WebSocket, and its only setInterval sites (1313, 1316, 2373) are the pre-existing refresh/countdown timers.","impact":"Assertion-coverage gap rather than a live defect; the no-timer property is true today by independent inspection. The gap matters for the next stage, where a real scheduler is the subject.","recommendation":"Mock setTimeout (and ideally requestAnimationFrame) with a passthrough counter so the zero-timer assertion covers every scheduling primitive before the scheduler stage."},{"severity":"P3","title":"submitBorrowTask composes element IDs from the unescaped symbol","file":"frontend/index.html","line":2129,"evidence":"submitBorrowTask builds `borrow-amount-${symbol}` / `borrow-count-${symbol}` / `borrow-error-${symbol}` from the raw symbol, while renderRow emits those IDs as `borrow-amount-${escapeHtml(row.symbol)}`. snapshot.schema.json constrains rows[].symbol only as {\"type\":\"string\",\"minLength\":1}, so a symbol containing & < > or \" would desynchronize the two forms and getElementById would return null.","impact":"Benign failure mode: the helper passes '' and the user sees the ordinary validation error. No injection surface exists, since every attribute added this stage is double-quoted and escaped. Not reachable with real Binance symbols.","recommendation":"Use the same escaped form on both sides, or constrain rows[].symbol in the schema, so the ID producer and consumer cannot drift."},{"severity":"P3","title":"status.json top-level identity fields under-report implementers and review-1","file":"reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json","line":null,"evidence":"Top-level implementer is the single value 'kimi' while implementers correctly lists ['claude_glm','kimi'], and top-level review_1 is all-null while both per-task review_1 objects are complete, fingerprinted, ACCEPT and provider-isolated (B1 owned by claude_glm reviewed by moonshot_kimi; F2/F3 owned by kimi reviewed by claude_glm). This is the aggregation defect disclosed in 66-review-2-strong-reviewer-override.md.","impact":"review_2_provider_must_differ_from_any_code_author_provider is machine-checked against these fields, so an automated gate reading top-level implementer alone would not see zhipu_glm as a code author. This reviewer established provider isolation from the per-task records instead, and it holds. status.json is excluded from the reviewed diff, so this is a bookkeeping correction rather than a delivery-code change.","recommendation":"Carry it into the planned Harness repair: make the validator aggregate per-task owners and reviewers, and have the bookkeeper populate the top-level fields consistently rather than leaving them single-valued or null."}],"required_fixes":[],"residual_risks":["The whole-view rerender that clears unsubmitted edits (Review-1 P3, same class as the 60-second market-table rerender) remains P3 for this fake prototype, but changes character once the UI is wired to real borrowing: a timer silently clearing a half-typed borrow amount is materially worse when the next keystrokes send a real order. It should be fixed before the backend stage, not after.","The tr carries role=\"button\" with focusable descendants; this stage added two text inputs and a confirm button inside that row on every data row, so the pre-existing ARIA violation now spans the whole table and screen-reader users cannot reliably reach the new operation controls. Not blocking for a fake prototype, but it is now the largest accessibility debt in frontend/index.html and should be resolved in the next UI stage.","Browser visual and DevTools Network checks were never executed. Acceptable here because the properties at stake are statically decidable: this reviewer verified CSS specificity (.btn:disabled and .btn.action-* are both (0,2,0), so the disabled rule wins only by being declared later, which it is) and confirmed the absence of every network/timer/persistence primitive by grep over the delivered file.","All 409 raw-sample userMinBorrow values are the factual \"0\", so non-zero valuation is covered only by synthetic in-test inputs, exactly as 14-user-min-borrow-contract-amendment.md permits. The stage copy of the sample is byte-identical to the source capture.","_user_min_borrow_value_usdt inherits the pre-existing behavior that Decimal accepts 'NaN'/'Infinity' strings; a hypothetical non-numeric-but-Decimal-parseable userMinBorrow could produce a value that fails the schema's decimal_string pattern. This is the same exposure the existing _max_borrowable_value_usdt / _quantize_rate path already carries, so it is not a regression introduced by this stage.","The borrow-task nav badge counts state.borrowTasks.length, which includes soft-deleted tasks. This is self-consistent with the frozen rule that 全部 includes every in-memory task, but updateBorrowTaskNav is only called on creation, so a future hard-delete path would silently desynchronize the badge."],"next_action":"stage_accepted_waiting_user"}