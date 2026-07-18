# Review-1 — frontend-borrow-task-fake (combined F2 + F3, rebound first reviewer)

- Stage: `2026-07-borrow-task-ui-fake-v1`
- Reviewed range (fixed, not moving HEAD): `82db8414b97819b72294ba8eee33bd0b7ec0dfd4..9d53204d450ee0dc4519f52201b575e5b71e948b`
- Diff fingerprint (recomputed independently): `9d53204d450ee0dc4519f52201b575e5b71e948b:22dd12e96cfe49cc0578fb248a6fb91085cd22c817e28c113b82e75fd1913db5` — matches the dispatch packet and `status.json.tasks[frontend-borrow-task-fake-f2].diff_fingerprint`. The F2 range `82db8414..9d53204` is a superset that contains the F3 commit (`9d53204 fix(frontend): style borrow task actions`) and the F2 commit (`ddcecf5 feat(frontend): complete fake borrow task controls`), so a single fingerprint covers the combined F2+F3 frontend delivery.
- Reviewer: Claude-GLM / `zhipu_glm` / `glm-5.2`, fresh read-only session, not the Kimi implementation session. `reviewer_prior_involvement: none`. Per `workflows/templates/stage-delivery.yaml`, `review_1_identity_granularity: provider` and `review_1_provider_must_differ_from_implementer_provider: true` — satisfied (implementer provider `kimi` vs reviewer provider `zhipu_glm`).
- Scope: read-only. No edits to application code, no commits, no servers, no network product operations, no borrow/trading action. The only write performed was this raw output file.

## Rebound Context

This is the rebound review-1 for the combined frontend delivery. Round-1 (`30-review-1.md`, verdict ACCEPT, range `d9c2772..edb2002`) covered only the original v1 fake-task UI and is **superseded** as a formal gate by the user-approved `13-scope-amendment-v2.md` and `14-user-min-borrow-contract-amendment.md`. `status.json.blockers` records that the human operator must execute the rebound read-only cross-review packets (B1 by Kimi, combined F2+F3 by Claude-GLM) before review-2 can be prepared. This verdict covers only the F2+F3 frontend range; the backend B1 verdict is an independent packet by Kimi.

## Independence And Fingerprint Verification

- Implementer provider: `kimi` (F2 and F3, sessions `83684f19-df9d-44ba-885c-267a01656f75`). Reviewer provider: `zhipu_glm`. Provider-level cross-review isolation satisfied.
- I recomputed the fingerprint from the raw binary diff (excluding `status.json`):
  `sha256(git diff --binary 82db8414..9d53204 -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json')` = `22dd12e96cfe49cc0578fb248a6fb91085cd22c817e28c113b82e75fd1913db5`, prepended with `head_sha` `9d53204…e948b`. **Exact match** to dispatch and `status.json`.
- Drift check: `git diff --stat 9d53204..HEAD -- frontend/` is empty (subsequent commits `bf2e159`/`1b73d91` are stage-documentation only), so the reviewed diff is still the live frontend code on `stage/2026-07-borrow-task-ui-fake-v1`. Working tree clean.
- Test re-run (independent): `node frontend/self-check.js` → 75 `[PASS]` lines ending `全部自检通过`, `exit_code=0`; `git diff --check` → clean, `exit_code=0`. Matches `64-test-output-frontend-visual-fix.txt` (the latest, which also re-asserts #1–#74).

## Criteria Findings

### 1. Lifecycle button states and transitions — PASS

- The state machine is a pure-UI contract on `state.borrowTasks[].status ∈ {borrowing, paused, deleted, completed}`; new tasks default to `borrowing` (`createBorrowTask` adds `status: 'borrowing'`).
- Transitions are local, guarded, and side-effect-free:
  - `pauseBorrowTask` (`frontend/index.html:2166`): only `borrowing → paused`, else `{ok:false}`.
  - `startBorrowTask` (`:2174`): only `paused → borrowing`, else `{ok:false}`.
  - `deleteBorrowTask` (`:2184`): any non-`deleted` task → `deleted`; the object is **never** spliced from `state.borrowTasks`, so `completed → deleted` uses the same path. This matches "delete = fake stop then soft-delete"; with no scheduler in this fake the stop is a pure status semantics, which the code comment states honestly.
- Button enablement matrix (`renderBorrowTasks`, `frontend/index.html:2257–2260`):

  | status | 启动 (start) | 暂停 (pause) | 删除 (delete) | 编辑 (edit) |
  |---|---|---|---|---|
  | borrowing | disabled | enabled | enabled | enabled |
  | paused | enabled | disabled | enabled | enabled |
  | completed | disabled | disabled | enabled | disabled (readonly) |
  | deleted | disabled | disabled | disabled | disabled (readonly) |

  `startDisabled = status !== 'paused'`, `pauseDisabled = status !== 'borrowing'`, `deleteDisabled = status === 'deleted'`, `editDisabled = (status==='deleted' || status==='completed')` reproduce the breakdown §3.3 matrix **cell-for-cell**, including the Amendment v4 specifics: `borrowing` greys 启动, `paused` greys 暂停. Verified by self-check #68 (four-state cell assertions + illegal-transition guards: deleted cannot pause, borrowing cannot start, double-delete fails) and #69 (round-trip state field + badge flip + unchanged progress/target).

### 2. Soft deletion — PASS

- `deleteBorrowTask` writes `status:'deleted'` only; `state.borrowTasks` length is unchanged (verified: self-check #70 asserts the object is retained with `status=deleted` and array length does not shrink, including for a `completed` task deleted to `deleted`).
- Deleted tasks remain visible under 全部/已删除, are excluded from 借币中, and render an 已删除 badge; all lifecycle and edit controls on a deleted card are disabled. Confirmed by #70 (membership across filters) and #68 (deleted cell: all four controls disabled).

### 3. Filters and counts — PASS

- `#borrow-task-filters` renders 全部/借币中/已暂停/已删除/已完成 with per-filter counts and `aria-pressed` (`renderBorrowTaskFilters`, `frontend/index.html:2225`).
- 全部 is not a status; its count is `state.borrowTasks.length` and it displays every object including soft-deleted ones. Per-status counts derive from the single canonical array (no second list). Empty `borrowing`/`paused` filters render a `暂无「X」任务` empty state rather than a blank panel.
- Verified by #71: counts 全部(4)/借币中(1)/已暂停(0)/已删除(2)/已完成(1) against an injected set including two deleted and one completed; 已完成 renders a completed card; 已暂停 empty state renders; 已删除 membership is exact.

### 4. Edit validation and read-only behavior — PASS

- Each card exposes independent `task-edit-amount-<id>` / `task-edit-count-<id>` inputs prefilled with the **exact current values** via `escapeHtml(String(task.amountPerAttempt))` / `escapeHtml(String(task.successTarget))`, plus a 确认修改 button and a nearby `role="alert"` error container.
- `editBorrowTask` (`frontend/index.html:2194`) reuses the create-path validators (`parseBorrowAmount` finite >0, `parseSuccessTarget` integer >0), updates only `amountPerAttempt`/`successTarget`, **preserves `successCount`**, and recomputes the rendered total. Invalid inputs return `{ok:false}` before any mutation; deleted/completed edits are rejected with a local error and zero state change.
- Verified by #72: prefilled `value="1000"`/`value="10"`; valid edit 1000/10 → 250/7 yields `250 HOME/次`, `0 / 7 次成功`, `目标 1,750 HOME` with `successCount` still 0 and error cleared; invalid amount (`abc`) and non-integer target (`2.5`) leave values unchanged with a nearby error; deleted (id2) and completed (id901) edits fail with 只读 message and no field change.

### 5. Three-branch minimum-borrow placeholder (raw zero, escaping, empty input) — PASS

- `minBorrowPlaceholder(row)` (`frontend/index.html:1241`) reads `row.borrow_validation.classic_margin`:
  - `user_min_borrow` not a string / empty → `最小借币量 —` (covers all null gates: private channel closed, pair not listed, key/field missing);
  - raw string present but `user_min_borrow_value_usdt` not a string → `最小借币量 <raw> (≈ — USDT)`;
  - both strings present → `最小借币量 <raw> (≈ <val> USDT)`, **including raw `"0"` and value `"0.00"`** which take the two-value branch verbatim. The raw minimum `"0"` is correctly treated as a valid guidance string, not as a borrow instruction (existing 0-rejection validation is untouched).
- The placeholder is interpolated into `placeholder="${escapeHtml(minBorrowPlaceholder(row))}"` — the whole string is escaped, so even adversarial raw/value strings cannot break the attribute. The amount input carries **no `value` attribute** (stays empty); the rule does not touch task-list edit inputs (they keep their prefilled `value`, no `placeholder`), validation, task creation, or imply borrowability.
- Verified by #73: four rows assert `placeholder="最小借币量 0 (≈ 0.00 USDT)"`, `placeholder="最小借币量 0.001 (≈ — USDT)"`, `placeholder="最小借币量 —"`, `placeholder="最小借币量 2.5 (≈ 123.46 USDT)"`; each amount input tag contains no `value=`; the task edit input still has `value="250"` and no `placeholder`.

### 6. No fetch / timer / storage / real-borrow side effect — PASS

- All new functions are pure in-memory mutations on `state.borrowTasks` plus `renderBorrowTasks()` re-renders. I grepped the F2+F3 diff for `fetch(`, `setInterval`, `setTimeout`, `localStorage`/`sessionStorage`, `XMLHttpRequest`, `new Worker`, `navigator.send`, `importScripts`, `indexedDB`: the only `+`-line hits are inside self-check #74 where they are **asserted not to grow**. The product diff introduces **zero** new I/O surface. The pre-existing `fetch`/`setInterval`/`localStorage` sites identified in round-1 (`/api/public-market/snapshot`, 60s/1s timers, privacy-toggle key) are unchanged.
- Verified by #74: after pause/start/filter/edit the deltas in `fetchCallLog`, `intervalCalls`, and `localStorageData` key count are all zero; #65 (HOME task) already asserts zero fetch/interval growth at creation.

### 7. v1 regression coverage — PASS

- Existing #1–#67 stay green in both `62-test-output-frontend-v2.txt` and `64-test-output-frontend-visual-fix.txt`, covering the 13-column structure / `colspan=13`, the operation cell's exactly-two-inputs-plus-confirm with event isolation, HOME via the generic `base_asset` path (no fabricated `HOMEUSDT` row), the single 已借完 badge, sidebar nav + fake disclosure, and the drawer event handling. No regression to market-table or drawer behavior; the new column is still td 13 so the daily/net cell index extraction is unaffected.

### 8. F3 action styling (green start, neutral pause, red delete) — PASS

- Three reusable theme classes are added inside the existing visual system (`frontend/index.html:683–697`): `.btn.action-start` (green `--success-soft` background / `--success` text), `.btn.action-pause` (neutral `--surface-2` background / `--muted` text), `.btn.action-delete` (red `--danger-soft` background / `--danger` text). The three operation buttons carry the matching class (`:2275–2277`).
- Verified by #75: a `borrowing` card's 启动 is `action-start`, 暂停 is `action-pause`, 删除 is `action-delete`; a `paused` card keeps 暂停=`action-pause` and 启动=`action-start`. Semantic classes are present independent of the disabled state.

### 9. Explicit disabled grey override for borrowing-start and paused-pause — PASS

- `.btn:disabled` (`frontend/index.html:698`) sets `cursor:not-allowed; opacity:0.55;` and neutral `--line`/`--surface-2`/`--faint` border/background/color. Its specificity (one class + one pseudo-class = (0,2,0)) equals each `.btn.action-*` rule (two classes = (0,2,0)); because `.btn:disabled` is **source-ordered after** the three theme rules (683/688/693 vs 698), it wins the cascade for a disabled action button and presents a neutral grey regardless of the button's normal theme. This satisfies Amendment v4: "Disabled action buttons must have an explicit disabled presentation, independent of their normal action theme."
- Verified by #75: it asserts `html.indexOf('.btn:disabled') >= html.indexOf('.btn.action-start')` (disabled rule is not before the theme rules) and that a `borrowing` 启动 carries both `action-start` and `disabled`, while a `paused` 暂停 carries both `action-pause` and `disabled`.

## Non-blocking Findings (P3) And Residual Risks

These do not violate any acceptance criterion and do not block acceptance; they are recorded for review-2 awareness and for the implementer's optional follow-up.

1. **Unsubmitted task-list edits are reset when any task action re-renders the list (P3, UX — disclosed).** `renderBorrowTasks()` rebuilds `els.borrowTaskList.innerHTML` on every pause/start/delete/edit/filter action, so values typed into one card's edit inputs are wiped if the user acts on another card before clicking 确认修改. This is the same class as the round-1 P3-1 (60s table re-render clearing pending operation inputs), now amplified because list-scoped state actions also trigger a full list rebuild. It affects only unconfirmed intermediate input, never confirmed task state, and the implementer disclosed it in `22-implementation-frontend-v2.md` §7. Per the dispatch instruction this unsubmitted-input-reset disclosure is treated as a review consideration, not completed evidence; recorded here for review-2.
2. **Browser / DevTools Network manual check not executed (residual, test scope).** Both implementation reports (`22` §6, `23` §5) disclose that the browser-based visual/Network checks from breakdown §3.8 were not run (no browser in the execution environment). Behavior is covered by DOM-level self-check assertions (button matrix, filter counts/membership, edit round-trip, placeholder branches, zero fetch/timer registration) and by my code reading, but empirical browser confirmation — including the visible green/grey/red theming and greyed disabled state — remains a manual step for the operator/review-2.
3. **Mock-DOM event execution gap (residual, test scope).** Self-check asserts structural attributes and exercises the helper transition/edit functions directly; it cannot execute the real `bindBorrowTaskControls`/event-delegation listeners. I closed this gap by code reading: `bindBorrowTaskControls` (`:2295`) binds `[data-task-action]` and `[data-task-edit-confirm]` after each render, and filter buttons use container delegation (`:2407–2411`) so they survive re-renders. In a real browser, native behavior prevents `click` on a `disabled` button, so the disabled cells are inert.
4. **`escapeHtml` does not escape the single quote (residual, carried from round-1).** All attributes added this stage (`data-task-id`, `data-task-action`, `data-borrow-filter`, `data-task-edit-confirm`, `task-edit-*` ids) are double-quote-delimited and `escapeHtml` escapes `"`; their values are numeric ids or fixed token strings (`start`/`pause`/`delete`/filter keys), not external input, so there is no injection surface. Keep new row-derived attributes double-quoted if more are added.

## Verdict

All nine review criteria are satisfied against the raw diff, source, the recomputed fingerprint, and an independent re-run of `node frontend/self-check.js` (75/75 PASS) plus `git diff --check` (clean). No P0/P1/P2 issues. The single P3 is a non-blocking UX note with an optional future mitigation and is honestly disclosed. **ACCEPT** for the F2+F3 frontend range; this packet proceeds to review-2 once the independent B1 (backend) review-1 verdict is also recorded.

当前 Session ID: unavailable (Claude-GLM reviewer runs through the Claude Code harness; this runtime does not expose a provider-native GLM Session ID to the reviewer. The operator may add the verified ID to `status.json.session_receipts`.)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/32-review-1-frontend.md
本地北京时间: 2026-07-19 00:38:13 CST
下一步模型: bookkeeper (Codex/GPT)
下一步任务: 记录 F2+F3 rebound review-1 ACCEPT 凭证；待 B1 rebound review-1 (Kimi) verdict 落定后整合两 packet，prepare review-2

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-borrow-task-ui-fake-v1",
  "role": "first_reviewer",
  "model": "glm-5.2",
  "verdict": "ACCEPT",
  "diff_fingerprint": "9d53204d450ee0dc4519f52201b575e5b71e948b:22dd12e96cfe49cc0578fb248a6fb91085cd22c817e28c113b82e75fd1913db5",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-task.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/11-adr.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/13-scope-amendment-v2.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/14-user-min-borrow-contract-amendment.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/23-implementation-frontend-visual-fix.md",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/62-test-output-frontend-v2.txt",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/64-test-output-frontend-visual-fix.txt",
    "reports/agent-runs/2026-07-borrow-task-ui-fake-v1/30-review-1.md",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff --binary 82db8414b97819b72294ba8eee33bd0b7ec0dfd4..9d53204d450ee0dc4519f52201b575e5b71e948b -- . ':(exclude)reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json'"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "Unsubmitted task-list edits are cleared when any task action re-renders the list",
      "file": "frontend/index.html",
      "line": 2237,
      "evidence": "renderBorrowTasks() rebuilds els.borrowTaskList.innerHTML on every pause/start/delete/edit/filter action; each card's task-edit-amount/count inputs are recreated with value reset to the current task field, so values typed into one card are lost if the user acts on another card before clicking 确认修改.",
      "impact": "Minor UX surprise in the fake prototype: a user mid-edit on one card can lose uncommitted amount/count input when pausing/starting/deleting/editing/filtering another. It never affects confirmed task state and violates no acceptance criterion. Disclosed by the implementer in 22-implementation-frontend-v2.md §7; same class as round-1 P3-1.",
      "recommendation": "Optional, not required for acceptance: localize per-card re-render or stage uncommitted edit values so they survive a sibling action; or document that in-card edits are transient until confirmed."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Browser-based visual checks and the DevTools Network panel confirmation from breakdown §3.8 were not executed (no browser in the execution environment); behavior is covered by DOM-level self-check assertions and code reading, but empirical browser confirmation of the green/grey/red theming and greyed disabled state remains a manual step for the operator/review-2.",
    "Self-check cannot execute the real bindBorrowTaskControls listeners or the filter event-delegation handler; transitions/edits are tested via helpers and the binding path was verified by code reading. Native disabled-button behavior makes the disabled cells inert in a real browser.",
    "escapeHtml escapes &, <, >, \" but not the single quote; all attributes added this stage are double-quote-delimited with numeric-id or fixed-token values, so there is no injection surface. Keep new row-derived attributes double-quoted if more are added.",
    "The 每 30 秒尝试一次 and 0 / N task strings are presentational only and imply no scheduler; correctly disclosed by the 前端演示 / 未发起真实借币请求 disclaimers."
  ],
  "next_action": "continue"
}
```
