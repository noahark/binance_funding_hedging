# PASTE BODY: Review-1 Task B Frontend Table And Initial Drawer

You are a fresh, read-only Claude-GLM review session. Review only Task B of
stage `2026-07-funding-annualized-history-v1`. Do not modify files, create a
commit, invoke another model, or return a `-p` launch command.

You must not be the Claude-GLM implementation session that authored backend
Tasks A/C. This packet reviews only Kimi-owned frontend Task B, not backend
code or later Task D changes.

## Exact Review Range

```text
base_sha: 744ce5f0b9445a891c1322bcb34e06ce94c83446
head_sha: f9f86bb6bcc2040844ad55f4f85937e85d393e5d
diff_fingerprint:
f9f86bb6bcc2040844ad55f4f85937e85d393e5d:a3284786251694a44d2e3c9b6161f532dded1e1161ffa939bcd98fb84c446826
```

Inspect exactly:

```bash
git diff --binary 744ce5f0b9445a891c1322bcb34e06ce94c83446..f9f86bb6bcc2040844ad55f4f85937e85d393e5d -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json'
```

Do not substitute moving `HEAD` or treat later Task C/D commits as reviewed
Task B code.

## Read Before Reviewing

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`
- `20-implementation-frontend.md`
- `60-test-output.txt`
- `task-frontend-kimi.prompt.md`
- changed `frontend/index.html`, `frontend/self-check.js`, and fixture files

## Verify

1. The table adds clear estimate 24h versus settled 7D/30D values without
   changing route/version, trading surfaces, or private-account behavior.
2. The original Drawer markup precedes the main script, opens by row click and
   keyboard, and closes by close button, backdrop, and Escape.
3. The Drawer uses the snapshot only; it does not call Binance from the browser.
4. Null rendering, newest-first history, refresh selection behavior, DOM order,
   and self-check coverage are credible for this fixed range.
5. Flag defects in this fixed Task B range only. Do not turn later Task D
   improvements into Task B findings.

## Response

List concise P0-P3 findings first. End with one strict JSON object matching
`schemas/review-verdict.schema.json`, no text after it. For `REWORK`, include a
complete `fix_start_prompt` with this exact range, raw artifact paths, Task B
file boundaries, required tests, and no unrelated changes.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "glm-5.2",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "f9f86bb6bcc2040844ad55f4f85937e85d393e5d:a3284786251694a44d2e3c9b6161f532dded1e1161ffa939bcd98fb84c446826",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["<each path actually reviewed>"],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_escalation_required"
}
```
