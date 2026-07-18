# Review-1 — frontend-borrow-task-fake (first reviewer)

- Stage: `2026-07-borrow-task-ui-fake-v1`
- Reviewed range (fixed, not moving HEAD): `d9c2772b7725bc794224a99c70505526eaedf295..edb20022e3490b89a805fa6eda374574523317e2`
- Diff fingerprint (recomputed independently): `edb20022e3490b89a805fa6eda374574523317e2:e3e97e020a81270214b15ccf349a969f159f831c72047d24ddffe2b7b1bcf133` — matches `status.json` and the dispatch packet.
- Reviewer: Claude-GLM / `zhipu_glm` / `glm-5.2`, fresh read-only session, not the Kimi implementation session. `reviewer_prior_involvement: none`.
- Scope: read-only. No edits to application code, no commits, no servers, no network product operations, no borrow/trading action. The only writes performed were this raw output file and the `status.json.session_receipts` receipt.

## Independence And Fingerprint Verification

- Implementer provider: `kimi`. Reviewer provider: `zhipu_glm`. Provider-level cross-review isolation satisfied (review-1 rule `review_1_provider_must_differ_from_implementer_provider`).
- I recomputed the fingerprint from the raw binary diff (excluding `status.json`):
  `sha256(git diff --binary d9c2772..edb2002 -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json')` = `e3e97e02…cf133`, prepended with `head_sha` = `edb20022…317e2`. Exact match.
- Drift check: `git diff --stat edb20022..HEAD -- frontend/` is empty, so the reviewed diff is still the live code on `stage/2026-07-borrow-task-ui-fake-v1`. Working tree clean.
- Test re-run (independent): `node frontend/self-check.js` → 86 `[PASS]` lines, `全部自检通过`, `exit_code=0`; `git diff --check d9c2772..edb2002` → clean, `exit_code=0`. Matches `60-test-output.txt` verbatim.

## Criteria Findings

### 1. 13th 「操作」column placement and 13-column alignment — PASS

- Header: `<th>借贷状态 / 资产</th>` is immediately followed by `<th>操作</th>` (`frontend/index.html:842` region), so 操作 is strictly right of the borrow-status/asset column.
- `renderRowHtml` emits exactly 13 `td` per data row (`frontend/index.html:1496–1565`): symbol, mark/index, forward opening, reverse opening, funding rate, settle time, daily rate, ann 24h, ann 7D, ann 30D, net yield, borrow status/asset, operation.
- Blocked state and empty state both use `colspan="13"` (`frontend/index.html:1464`, `1479`). The empty-state row still has exactly one `<td>`. All rows/states align to 13 columns.

### 2. Operation control = exactly two editable inputs + confirm; interactions do not open the drawer — PASS (verified on the real DOM path, not only assertions)

- The operation cell renders exactly two `<input>` (`borrow-amount-<symbol>` 单次借币数量, `borrow-count-<symbol>` 成功借币次数), each with a `<label for>`, plus one 确认 `<button data-borrow-confirm>`, plus a nearby `borrow-error-<symbol>` container with `role="alert" aria-live="polite"` (`frontend/index.html:1554–1563`).
- Event isolation is wired into the real render path: `renderTable()` calls `bindRowSelection()` (`frontend/index.html:1489`), which selects every `tr.selectable` and calls `attachRowHandlers(tr)` on each (idempotent via the `data-bound` marker, `frontend/index.html:1599–1607`). `patchRow` re-binds only the freshly inserted row (`frontend/index.html:1634`). So in a real browser every visible row gets the isolation handlers — this is not dead code.
- `attachRowHandlers` binds the row `click`/`keydown(Enter|Space)` → `openDrawer` (`frontend/index.html:1571–1577`), then on the operation cell adds `click` and `keydown` `stopPropagation`, and on the confirm button adds `click` `stopPropagation` + `submitBorrowTask(symbol)` (`frontend/index.html:1578–1597`). Net effect: clicking the inputs, labels, or the cell, or pressing keys inside the inputs, does not bubble to the row handler; clicking 确认 calls `submitBorrowTask` and does not open the drawer. `stopPropagation` does not call `preventDefault`, so text entry in the inputs is unaffected.
- The mock DOM `tr` lacks `querySelector`, so the binding is guarded by `if (typeof tr.querySelector === 'function')`; the self-check exercises creation/validation/display through `__appHelpers` and asserts `stopPropagation` is present. That is an honest, adequate substitution given the mock environment, and I confirmed by code reading that the real-DOM binding path is correct.

### 3. Amount finite > 0, success target positive integer, invalid stays local — PASS

- `parseBorrowAmount` (`frontend/index.html:~2020`) rejects empty/whitespace, `NaN`, `Infinity`, `<= 0`; only finite `> 0` numbers pass. `parseSuccessTarget` (`~2030`) additionally requires `Number.isInteger` and `> 0`, so `2.5`, `0`, negatives, and non-numerics are rejected.
- `createBorrowTask` returns `{ok:false, error}` before touching `state.borrowTasks` on any invalid input (`~2038–2042`); `submitBorrowTask` writes the error string into the nearby `borrow-error-<symbol>` container via `textContent` (no innerHTML → no XSS) and creates no task. Verified by self-check #64/#66 across the bad-input matrix and the UI submit path.

### 4. Valid confirmation only creates a browser-memory fake task from `base_asset`; no fetch / private API / persistence / retry / backend / external effect — PASS

- `createBorrowTask` only pushes `{id, asset: row.base_asset, amountPerAttempt, successTarget, successCount: 0}` onto `state.borrowTasks` (an in-memory array seeded as `[]` in the initial state object). No `fetch`, no signed/private API call, no `localStorage`, no `setInterval`/retry loop, no backend or fixture change.
- I grepped all `fetch(` and `setInterval` call sites: `frontend/index.html:1665` (`/api/public-market/symbol-snapshot`) and `:2157` (`/api/public-market/snapshot`) are pre-existing public read endpoints; the `setInterval` sites at `:1248` (60s auto-refresh), `:1251` (1s countdown), and `:2176` (60s auto-refresh) are pre-existing. None were introduced or repurposed by this stage. `localStorage` is only the pre-existing privacy-toggle key (`:975`, `:984`).
- Self-check #65 asserts zero growth in `fetchCallLog` and `intervalCalls` after creating a HOME task, and that every interval is 60000 or 1000. Confirmed.

### 5. 「借币任务」navigation, task counts, fake disclosure; `HOME` via generic `base_asset`; no fake market row — PASS

- Sidebar adds a `借币任务` nav button (`id="nav-borrow-tasks"`) after `费率行情` with a count badge (`id="borrow-task-count"`) initialized to `0` via `updateBorrowTaskNav()` in `init`. `setActiveView` toggles `#market-view` / `#borrow-task-view` display and the nav `active`/`aria-current` state, and re-renders the task list when entering the borrow view.
- The borrow-task view carries a top warn banner ("前端演示…未发起真实借币请求…刷新页面后消失") and each task card carries a `前端演示` badge plus a strong `未发起真实借币请求` disclaimer. Self-check #63/#65 assert the empty state, count, disclosure strings, and view restoration.
- `HOME` is supported generically: the asset is taken from `row.base_asset`, and self-check #65 mutates only `rows[0].base_asset = 'HOME'` in memory while keeping `symbol = AUSDT`; it asserts the task asset is `HOME` and that the rendered output contains no `HOMEUSDT` market row. No fixture or market row is fabricated.

### 6. Duplicate 「已借完」in the max-borrowable subline removed; status badge 「可借 0(已借完)」retained — PASS

- `maxBorrowableSubline` no longer emits the standalone `已借完` `zeroTag`; it returns only `可借: <max_borrowable> (<value> USDT)` (`frontend/index.html:1176–1183`).
- The exhausted status badge `可借 0(已借完)` is still produced by `badgeForNegativeFundingStatus` when `pa.max_borrowable === '0'` under a verified `PRIVATE_BORROW_VALIDATION_REQUIRED` (`frontend/index.html:1283–1285`). Self-check #67 asserts `已借完` occurs exactly once in the cell and that both `可借 0(已借完)` and `可借: 0` are present.

### 7. Maintainability, actual event behavior, security/XSS, test adequacy, regression — PASS (with non-blocking notes)

- **Actual event behavior**: verified above that the isolation handlers are attached to every rendered row in the real DOM, so the "controls do not open the drawer" guarantee holds in the browser, not only in the structural assertion.
- **Security / XSS**: all row-derived values are escaped. Display text uses `escapeHtml(row.base_asset)` / `escapeHtml(row.symbol)`; attribute values (`id="borrow-amount-…"`, `data-borrow-confirm="…"`, `aria-label`) are double-quoted and `escapeHtml` escapes `"`. The nearby error is set via `textContent`. In the task card, `asset` is escaped and `amountText`/`totalText` come from `formatTaskAmount`, which only emits digits, `,`, and `.` (or the literal `—`); `successCount`/`successTarget`/`task.id` are numbers. No injection surface. (Note: `escapeHtml` does not escape the single quote `'`, but no attribute in this file is single-quote-delimited, so it is not exploitable here — recorded as residual only.)
- **Test adequacy**: existing 12-column assertions were consistently upgraded to 13 (header order, per-row td count, empty-state colspan, the `tdCount < 13` cell-extraction loop, the `requiredHeaders`/`taskCHeaders` lists). New blocks #62–#67 cover operation-cell structure/isolation, navigation/empty-state/restore, validation matrix, the memory-only HOME task with zero-fetch/zero-timer assertions and the `HOMEUSDT` prohibition, the UI submit path with nearby-error clear-on-valid, and `已借完` uniqueness. The single uncovered axis — real-DOM event execution — is an inherent mock-DOM limitation, honestly disclosed in `20-implementation.md`, and the binding path is verifiably correct by inspection.
- **Regression**: no change to `formatFundingRate`/`formatBeijing*`/`formatUsdt2` semantics; the drawer open/close/backdrop/Escape/refresh-keep paths are untouched; the daily-cell (td 6) and net-cell (td 10) index extraction still resolves correctly because the new column is td 13. No regression observed in existing table or drawer behavior.

## Non-blocking Findings (P3) And Residual Risks

These do not violate any acceptance criterion and do not block acceptance; they are recorded for the implementer's optional follow-up and for review-2 awareness.

1. **Operation inputs are reset on table re-render (P3, UX).** `renderTable()` rebuilds `els.tableBody.innerHTML` on every 60s auto-refresh, manual refresh, and filter change (`frontend/index.html:1487`). The `borrow-amount` / `borrow-count` inputs are part of that HTML, so any values a user has typed are cleared when a refresh fires before they click 确认. Task persistence (the criterion that is actually required) is unaffected because `ingestSnapshot` does not touch `state.borrowTasks`. Optional mitigation: preserve pending input values across re-renders, or visually note that entries are transient.
2. **Focusable controls nested inside a `role="button"` row (P3, a11y).** The `<tr>` carries `role="button" tabindex="0"` (`frontend/index.html:1541`); this stage added focusable `<input>`/`<button>` descendants inside it. Interactive descendants inside a `role="button"` element are technically invalid ARIA and may confuse assistive tech. The row role is pre-existing; the new controls each have their own labels/`aria-label`. Optional mitigation: re-scope the row activation or move the operation controls out of the button-affordance row in a later a11y pass.
3. **Mock-DOM event coverage gap (residual, test scope).** Self-check asserts `stopPropagation` textually and tests the helper paths, but cannot execute the real `attachRowHandlers` listeners. I closed this gap by code reading (the binding is wired through `bindRowSelection`/`patchRow`), but a future browser-driven check would make it empirical.
4. **Future-backend semantics shown as fixed strings (residual, by design).** The "每 30 秒尝试一次" and `0 / N` strings are presentational only and do not reflect any scheduler; correctly disclosed by the disclaimers. No action needed this stage.

## Verdict

All seven review criteria are satisfied against the raw diff, source, and re-run test evidence. No P0/P1/P2 issues. The two P3 items are non-blocking UX/a11y notes with optional mitigations. **ACCEPT**, proceed to review-2.

当前 Session ID: unavailable (Claude-GLM reviewer runs through the Claude Code harness; this runtime does not expose a provider-native GLM Session ID to the reviewer. The operator may add the verified ID to `status.json.session_receipts`.)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/30-review-1.md
本地北京时间: 2026-07-18 21:06:20 CST
下一步模型: bookkeeper (Codex/GPT)
下一步任务: 记录 review-1 ACCEPT 凭证,推进 review-2 (codex, reality_checker)

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-borrow-task-ui-fake-v1",
  "role": "first_reviewer",
  "model": "glm-5.2",
  "verdict": "ACCEPT",
  "diff_fingerprint": "edb20022e3490b89a805fa6eda374574523317e2:e3e97e020a81270214b15ccf349a969f159f831c72047d24ddffe2b7b1bcf133",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/60-test-output.txt",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff --binary d9c2772b7725bc794224a99c70505526eaedf295..edb20022e3490b89a805fa6eda374574523317e2 -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json'"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "Operation inputs are cleared whenever the table re-renders",
      "file": "frontend/index.html",
      "line": 1487,
      "evidence": "renderTable() rebuilds els.tableBody.innerHTML on the 60s auto-refresh, manual refresh, and filter changes; the borrow-amount/borrow-count <input> elements live inside that HTML, so pending entries are wiped if a refresh fires before 确认 is clicked.",
      "impact": "Minor UX surprise in the fake prototype: a user mid-entry can lose typed amount/count on a 60s poll. Does not affect task persistence (ingestSnapshot does not touch state.borrowTasks) and violates no acceptance criterion.",
      "recommendation": "Optional: preserve pending input values across re-renders (e.g., a per-symbol staging object read on render), or add a small note that entries are transient. No fix required for acceptance."
    },
    {
      "severity": "P3",
      "title": "Focusable controls nested inside a role=\"button\" table row",
      "file": "frontend/index.html",
      "line": 1541,
      "evidence": "The <tr> keeps role=\"button\" tabindex=\"0\"; this stage added focusable <input>/<button> descendants (borrow-amount, borrow-count, 确认) inside that row.",
      "impact": "Interactive descendants inside a role=\"button\" element are technically invalid ARIA and may confuse screen-reader users. The row role is pre-existing; each new control has its own label/aria-label.",
      "recommendation": "Optional: in a later a11y pass, re-scope row activation (e.g., move the row trigger off role=button or relocate the operation controls). No fix required for acceptance."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "escapeHtml escapes &, <, >, \" but not the single quote; no attribute in this file is single-quote-delimited, so it is not exploitable in the current code, but keep attributes double-quoted if new row-derived attributes are added.",
    "Self-check cannot execute real-DOM attachRowHandlers listeners; event isolation is covered textually and via helper paths. The real binding path was verified by code reading (bindRowSelection/patchRow wire attachRowHandlers to every rendered row).",
    "The 每 30 秒尝试一次 and 0 / N task strings are presentational only and imply no scheduler; this is correctly disclosed by the 前端演示 / 未发起真实借币请求 disclaimers."
  ],
  "next_action": "continue"
}
```
