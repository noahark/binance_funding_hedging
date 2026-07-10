# PASTE BODY: Review-1 For Task A Backend Contract And Settled History

You are a fresh, read-only Kimi review session for Task A of stage
`2026-07-funding-annualized-history-v1`. Review the committed range below; do
not modify any file, create a commit, invoke another model, or return a `-p`
launch command.

## Review Gate

This packet is prepared for formal review-1, but it becomes formal Harness
evidence only after the human operator confirms that the bookkeeper has passed:

```text
scripts/validate-stage.py 2026-07-funding-annualized-history-v1 --phase pre-review
```

If that gate has not passed, state that the preflight is blocked and do not
claim an ACCEPT/REWORK gate verdict. Do not review or comment on unrelated
uncommitted files under `reports/follow-ups/`.

## Exact Review Range

```text
base_sha: 0206f8bf7236e807b4cd69d7beed02eb41e8ec60
head_sha: 2e27efcbed960206b43c25054bf6105224942439
diff_fingerprint:
2e27efcbed960206b43c25054bf6105224942439:85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb
```

Inspect exactly:

```bash
git diff --binary 0206f8bf7236e807b4cd69d7beed02eb41e8ec60..2e27efcbed960206b43c25054bf6105224942439 -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json'
```

Do not substitute a moving `HEAD` or include later checkpoint commits.

## Required Raw Artifacts

Read these before reviewing the diff:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/20-implementation-backend.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/60-test-output.txt`
- `reports/api-samples/2026-07-funding-annualized-history-v1/20260710T061419Z/capture.md`
- `reports/api-samples/2026-07-funding-annualized-history-v1/20260710T061419Z/raw/fapi-v1-fundingRate-BTCUSDT-limit1000.json`
- changed backend, schema, and test files in the fixed range

## Task A Requirements To Verify

1. `annualized_funding_24h` is estimate-derived:
   `daily_funding_rate * 365`, Decimal-only, fixed eight-place string.
2. 7D and 30D annualization sum settled history inside inclusive calendar
   windows and multiply by `365 / N`; no interval-mean formula, observed-span
   denominator, float path, or `lastFundingRate` mixing.
3. The three annualized fields are optional schema properties to preserve
   `public-market-snapshot/v1` frozen-v0.1 compatibility, but every current
   `SnapshotService` output row emits all three keys as decimal strings or
   `null`.
4. Live deep history is only for `Config.top_n`, uses safe query construction
   with `symbol`, `startTime=t_end-30d`, `endTime=t_end`, and `limit=1000`, and
   uses a dedicated successful-result cache with default 1,800-second TTL.
5. A failed history request affects only that row: empty history, null 7D/30D,
   `funding_history_unavailable:<symbol>`, no snapshot-wide failure, and no
   failed-result cache entry.
6. No route/version/sort/private-channel/trading behavior changes. Raw evidence
   is authentic public data; synthetic fixtures are only supplemental tests.
7. Tests substantiate boundary handling, mixed intervals, negative rates,
   top-N cap, cache behavior, failure retry, optional-schema legacy replay, and
   current-output field presence.

You may run read-only verification commands such as the recorded backend tests
or JSON validation, but do not change the worktree.

## Required Response

First provide concise findings ordered P0 through P3, with file and line
evidence. Then end with one strict JSON object matching
`schemas/review-verdict.schema.json` and no text after it:

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "2e27efcbed960206b43c25054bf6105224942439:85c780708fe546a32f6ef2120841c0176aab313adf81f6d82da82e48fdfdddfb",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["<each path actually reviewed>"],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_escalation_required"
}
```

For `REWORK`, include a complete `fix_start_prompt` in that JSON: it must name
the fixed range and raw review path, preserve the Task A file boundaries, list
each finding and required fix, prohibit unrelated changes, require the backend
test/schema/diff commands, and require a `40-fix-report.md` finding-to-fix
mapping.
