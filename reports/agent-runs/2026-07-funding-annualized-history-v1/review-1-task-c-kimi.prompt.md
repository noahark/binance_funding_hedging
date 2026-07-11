# PASTE BODY: Review-1 Task C Selected-Symbol History Endpoint

You are a fresh, read-only Kimi review session. Review only backend Task C of
stage `2026-07-funding-annualized-history-v1`. Do not modify files, create a
commit, invoke another model, or return a `-p` launch command.

You must not be the Kimi implementation session that authored frontend Tasks
B/D. This packet reviews only Claude-GLM-owned backend Task C, not frontend
code or the later Task D integration.

## Exact Review Range

```text
base_sha: 5a5b9f6a6d6af744e86061278461ab91356177a4
head_sha: c2bb368d8235f8a8d69d8ebb19810a9c7657b41e
diff_fingerprint:
c2bb368d8235f8a8d69d8ebb19810a9c7657b41e:5ade324bb23600f51a75c97d48090660e124e75ef1ea6329c48a32ce4094c919
```

Inspect exactly:

```bash
git diff --binary 5a5b9f6a6d6af744e86061278461ab91356177a4..c2bb368d8235f8a8d69d8ebb19810a9c7657b41e -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json'
```

## Read Before Reviewing

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `00-task.md`, `10-design.md`, `11-adr.md`, `12-development-breakdown.md`,
  and `13-review-feedback-fix.md`
- `20-implementation-backend-history-fix.md`
- `60-test-output.txt`
- `task-history-endpoint-claude-glm.prompt.md`
- changed server/service/domain/test files and
  `schemas/api/public-market/funding-history.schema.json`

## Verify

1. Endpoint is same-origin, public read-only, validates malformed and ineligible
   symbols as 400/404, and does not expose credentials or invoke private APIs.
2. It uses the current snapshot eligibility and time boundary, reuses the
   successful per-symbol cache, keeps top-N preload intact, and avoids a
   full-universe fetch.
3. HTTP 200 distinguishes `available`/`empty`; failed upstream is 502 and is
   not cached. Settled fields use the existing Decimal window semantics and
   records are newest first.
4. Server routing, response schema, unit tests, and offline/live smoke evidence
   substantiate the behavior without changing the existing snapshot wire route.

## Response

List concise P0-P3 findings first. End with one strict JSON object matching
`schemas/review-verdict.schema.json`, no text after it. For `REWORK`, include a
complete `fix_start_prompt` preserving Task C boundaries and test commands.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "c2bb368d8235f8a8d69d8ebb19810a9c7657b41e:5ade324bb23600f51a75c97d48090660e124e75ef1ea6329c48a32ce4094c919",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["<each path actually reviewed>"],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_escalation_required"
}
```
