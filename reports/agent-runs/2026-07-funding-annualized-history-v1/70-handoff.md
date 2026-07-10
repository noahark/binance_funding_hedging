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
4. The current worktree contains user-owned changes outside this stage. They
   prevent a formal `pre-review` clean-worktree validation until the user
   resolves them. No formal review verdict is claimed or prepared as passing.
5. No merge, canonical-doc promotion, or push is authorized.

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
- Formal pre-review remains blocked by user-owned worktree changes:
  `reports/follow-ups/README.md`,
  `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md`,
  `reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md`,
  `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`, and
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/`.

```text
本地北京时间: 2026-07-10 19:41:35 CST
下一步模型: human / bookkeeper
下一步任务: 先解决用户自有工作区改动；随后由 bookkeeper 运行 pre-review 验证并准备正式交叉评审。
```
