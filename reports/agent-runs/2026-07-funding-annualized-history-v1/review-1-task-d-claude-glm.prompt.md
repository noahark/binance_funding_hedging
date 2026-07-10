# PASTE BODY: Review-1 Task D Drawer History And Table Refinement

You are a fresh, read-only Claude-GLM review session. Review only frontend
Task D of stage `2026-07-funding-annualized-history-v1`. Do not modify files,
create a commit, invoke another model, or return a `-p` launch command.

You must not be the Claude-GLM implementation session that authored backend
Tasks A/C. This packet reviews only Kimi-owned frontend Task D.

## Exact Review Range

```text
base_sha: 7480fdbffd13901e9a034b70dec237ac43c080f8
head_sha: d21536aa8a221a065c4fbe2b7640e199addca7dc
diff_fingerprint:
d21536aa8a221a065c4fbe2b7640e199addca7dc:553e9a36f417d8c7986a26e1d3a5bc629b80958dfc0d979796e6ffb4123aa6a9
```

Inspect exactly:

```bash
git diff --binary 7480fdbffd13901e9a034b70dec237ac43c080f8..d21536aa8a221a065c4fbe2b7640e199addca7dc -- . ':(exclude)reports/agent-runs/2026-07-funding-annualized-history-v1/status.json'
```

## Read Before Reviewing

- `AGENTS.md`
- `00-task.md`, `10-design.md`, `11-adr.md`, `12-development-breakdown.md`,
  `13-review-feedback-fix.md`
- `20-implementation-frontend-history-fix.md`
- `60-test-output.txt`
- `task-drawer-history-refinement-kimi.prompt.md`
- `task-drawer-history-race-fix-kimi.prompt.md`
- changed `frontend/index.html` and `frontend/self-check.js`

## Verify

1. The default route-class column is removed but the route filter and required
   payload field remain; table counts/indexes are correct.
2. Drawer width/grid prevent the three annualized labels from wrapping without
   causing narrow-view overflow.
3. The browser calls only the same-origin selected-history endpoint. Loading,
   available, empty, upstream failure, and retry states have correct semantics.
4. Successful response merge is limited to the requested selected symbol. The
   request guard runs after every async boundary, including `res.json()`, and
   wrong symbol/schema responses cannot mutate the selected row.
5. Existing keyboard/backdrop/Escape/refresh behavior, privacy behavior, and
   no-trading constraints remain intact. Self-check covers the important races.

## Response

List concise P0-P3 findings first. End with one strict JSON object matching
`schemas/review-verdict.schema.json`, no text after it. For `REWORK`, include a
complete `fix_start_prompt` preserving Task D boundaries and test commands.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "first_reviewer",
  "model": "glm-5.2",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "d21536aa8a221a065c4fbe2b7640e199addca7dc:553e9a36f417d8c7986a26e1d3a5bc629b80958dfc0d979796e6ffb4123aa6a9",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["<each path actually reviewed>"],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_escalation_required"
}
```
