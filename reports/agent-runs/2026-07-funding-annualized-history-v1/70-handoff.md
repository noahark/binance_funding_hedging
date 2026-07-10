# Handoff: 2026-07-funding-annualized-history-v1

## Planning Checkpoint

- Current branch: `stage/2026-07-funding-annualized-history-v1`
- Stage branch base: `7bdc90496a9cf801ca2d10ebd3cdf0c8e165adc1`
- Planning package commit: `bf0e5f0`
- HEAD at command validation before this checkpoint record: `bf0e5f0`
- Git status at checkpoint: user-owned modifications remain in
  `reports/follow-ups/README.md` and
  `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`; this
  package does not overwrite, stage, or commit them.
- Code changes: none.
- Backend/frontend tests: not run; this checkpoint creates planning and
  dispatch-preparation artifacts only.
- Command checks: `jq empty status.json`, whitespace checks, and
  `python3 scripts/validate-stage.py 2026-07-funding-annualized-history-v1 --phase checkpoint`
  passed. Full output is in `60-test-output.txt`.

## Package Contents

- `00-intake.md`: MEDIUM classification and human approval gate.
- `00-task.md`: bounded outcome, file ownership, non-goals, and acceptance.
- `10-design.md` and `11-adr.md`: frozen math, caching, degraded-fetch, UX,
  and canonical-document boundaries.
- `12-development-breakdown.md`: serial Task A (Claude-GLM) then Task B (Kimi).
- `task-backend-claude-glm.prompt.md` and `task-frontend-kimi.prompt.md`:
  PASTE BODY artifacts for a human operator to put into the target interactive
  executor sessions. No dispatch command has been executed.
- Review-2 primary: an unrelated Anthropic Claude session; Codex/GPT is only a
  documented strong-reviewer fallback because it authored this package.
- Contract correction: the three annualized fields are optional schema
  properties to preserve frozen v0.1 validation, but are mandatory keys on
  current service output. The prior temporary authorization for legacy
  hand-authored row backfills is withdrawn; no such test changes are needed.

## Open Gates And Next Action

1. Task A is committed as `2e27efc` with review range
   `0206f8bf7236e807b4cd69d7beed02eb41e8ec60..2e27efcbed960206b43c25054bf6105224942439`.
   Its committed-state fingerprint is
   `2e27efcbed960206b43c25054bf6105224942439:85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb`.
2. Task A test evidence: `226 passed`; schema JSON and `git diff --check` pass.
   Option 3 is frozen: schema properties remain optional for v0.1 replay, while
   current service output always carries all three fields.
3. Task B is committed as `f9f86bb` and the Drawer DOM-order P0 is resolved;
   the detailed checkpoint is below.
4. The operator's session artifacts were preserved separately in
   `docs/2026-07-10-session-artifacts` commit `1ec2047`; this product stage
   worktree is now clean. No formal review verdict is claimed or prepared as
   passing.
5. No merge, canonical-doc promotion, or push is authorized.

## Review-Feedback Fix Package

Live acceptance found that the original global top-N preload made a selected
non-top-N row look as though it had no settled history. For example, TSTUSDT
and REUSDT were not in the live `abs(lastFundingRate)` top-20 set, so no deep
history request had occurred. The previous Drawer message incorrectly grouped
that state with a true empty window and an upstream failure.

The stage now has a planned serial amendment:

1. Task C, Claude-GLM: add a same-origin selected-symbol public history
   endpoint with cache reuse and explicit 400/404/502 semantics.
2. Task D, Kimi: consume that endpoint in the Drawer, distinguish loading /
   empty / retryable failure, remove the default route-class column, and widen
   the Drawer to 620px desktop width.

Task C is now committed; Task D remains the only implementation task before
formal review.

## Task C Checkpoint

- Task C committed range:
  `5a5b9f6a6d6af744e86061278461ab91356177a4..c2bb368d8235f8a8d69d8ebb19810a9c7657b41e`
- Task C diff fingerprint:
  `c2bb368d8235f8a8d69d8ebb19810a9c7657b41e:5ade324bb23600f51a75c97d48090660e124e75ef1ea6329c48a32ce4094c919`
- Added same-origin `GET /api/public-market/funding-history?symbol=...` and
  its machine schema. HTTP 200 distinguishes `available` from `empty`; HTTP
  400, 404, and 502 expose invalid, unknown, and upstream-unavailable cases.
- Independent evidence: 244 backend tests passed; offline HTTP route checks on
  temporary port 8790 returned 200/400/404; a no-credential live-public check
  on temporary port 8791 returned 179 SKLUSDT settled records with the 7D/30D
  values and no 24h estimate field.
- The primary worktree was concurrently switched to the auto-review document
  branch by another terminal. Task C was therefore first committed there as
  `d0734da`, then non-destructively cherry-picked to this stage as `c2bb368` in
  a temporary stage worktree. The auto-review branch and its untracked artifact
  were not modified.
- Task D Kimi PASTE BODY now contains the committed Task C range. Do not start
  formal review until Task D is committed and the combined range is rebound.

## Task D Local Rework

Kimi's initial Task D diff passed its self-check and the independent backend
regression, but bookkeeper inspection found a response-body race: the request
guard runs before `await res.json()` only. If the selected row changes while
the response body is parsing, the old symbol's result can still merge into the
new selected row. This is a scope-contained P1 and is not a formal review
verdict.

`task-drawer-history-race-fix-kimi.prompt.md` required Kimi to recheck active
request state after every await before mutation, validate the response symbol
and schema version, and add a delayed-body stale-response test. It was fixed in
`d21536a`; the detailed checkpoint follows. No formal review is prepared yet.

## Task D Checkpoint

- Task D committed range:
  `7480fdbffd13901e9a034b70dec237ac43c080f8..d21536aa8a221a065c4fbe2b7640e199addca7dc`
- Task D diff fingerprint:
  `d21536aa8a221a065c4fbe2b7640e199addca7dc:553e9a36f417d8c7986a26e1d3a5bc629b80958dfc0d979796e6ffb4123aa6a9`
- Default route-class table column is removed while its filter and API field
  remain. The Drawer now uses 620px desktop width, non-wrapping annualized
  labels, same-origin selected-symbol history loading, empty/failure/retry
  states, and table merge on successful history retrieval.
- Kimi's initial stale-response guard was strengthened after bookkeeper found a
  body-parsing race. The final self-check covers delayed `res.json()` selection
  changes, wrong-symbol rejection, and schema-version mismatch rejection.
- Independent verification: `node frontend/self-check.js` passed; backend
  suite passed 244 tests; `git diff --check` passed. The empty `EOF` heredoc
  artifact was removed before commit.
- An offline same-origin smoke at temporary port 8792 served the current page
  with the route header absent, 620px Drawer CSS and three-card grid present,
  and the selected-history endpoint returning HTTP 200. The server was stopped.
- Combined stage range is now
  `7bdc90496a9cf801ca2d10ebd3cdf0c8e165adc1..d21536aa8a221a065c4fbe2b7640e199addca7dc`;
  its fingerprint is
  `d21536aa8a221a065c4fbe2b7640e199addca7dc:378c060d86086d7d9a6c8eff94aad1e0998bdd014a255070eb1504fe3bca62a8`.

## Kimi Preflight Output

The raw Kimi output is preserved in
`review-1-task-a-kimi.preflight-blocked.raw-output.md`. It is not a formal
review-1 verdict because the packet's preflight had not passed.

- P0 is valid: the user-owned `reports/follow-ups/` worktree changes prevent a
  clean-worktree pre-review check.
- The recommendation to change the whole stage to `review_1` and set top-level
  review range metadata was deferred at the time because Task B was not
  implemented. Task B is now committed, but this output remains non-accepting
  because pre-review never passed.
- The generic `20-implementation.md` validator artifact will be created as a
  concise index of the preserved task reports after Task B, rather than changing
  `validate-stage.py` or copying a Task A-only report under a misleading name.
- The symbol-only history cache intentionally permits up to its documented
  1,800-second staleness. Its window drift is a residual risk to document at
  formal review, not a reason to key by exact millisecond bounds (which would
  defeat the cache). The `data_time_ms <= 0` guard remains a low-priority
  hardening candidate and has not been accepted as a Task A rework.

## Task B Blocking Fix

Bookkeeper static inspection found that the drawer markup followed the main
application script. That made `bindEvents()` dereference `null` drawer elements
in a real browser even though the self-check mock pre-created them. This
scope-contained Task B P0 was fixed in `f9f86bb` by moving the drawer markup
before the application script and adding a static DOM-order assertion.

## Task B Checkpoint

- Task B committed range:
  `744ce5f0b9445a891c1322bcb34e06ce94c83446..f9f86bb6bcc2040844ad55f4f85937e85d393e5d`
- Task B diff fingerprint:
  `f9f86bb6bcc2040844ad55f4f85937e85d393e5d:a3284786251694a44d2e3c9b6161f532dded1e1161ffa939bcd98fb84c446826`
- The combined stage range is
  `7bdc90496a9cf801ca2d10ebd3cdf0c8e165adc1..f9f86bb6bcc2040844ad55f4f85937e85d393e5d`;
  its fingerprint is
  `f9f86bb6bcc2040844ad55f4f85937e85d393e5d:379bbdac9bf58a9097a90051d4c9798ad24d9e9182466b07b7eaa9711e8c57d8`.
- `node frontend/self-check.js`, `python3 -m pytest backend/tests -q` (226
  passed), schema JSON parsing, and `git diff --check` passed.
- An offline server at port 8788 served the current annualized fields; the
  homepage contained the annualized columns and drawer markup before the
  application script. The server was stopped after verification.
- The stage worktree is clean. The next Harness step is to prepare the formal
  cross-review scope, set the appropriate review state, and run `pre-review`.

```text
本地北京时间: 2026-07-10 22:54:32 CST
下一步模型: bookkeeper
下一步任务: 为后端 A/C 和前端 B/D 准备 task-level review-1 packets，再运行 pre-review。
```
