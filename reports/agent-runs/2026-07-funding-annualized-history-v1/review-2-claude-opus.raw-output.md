# Review-2 Raw Output: Independent Final-Reviewer Audit

Reviewer: fresh, unrelated Anthropic Claude session (`anthropic/claude-opus-4-8`),
read-only, no prior involvement in this stage.
Stage: `2026-07-funding-annualized-history-v1`
Role: `final_reviewer` (review-2 gate).

Taking over the review-2 gate because the Codex/GPT strong-reviewer fallback is
quota-exhausted. Per `70-handoff.md`, review-2 primary was always specified as
"an unrelated Anthropic Claude session"; this session is exactly that and is the
more-independent choice (GPT authored the planning package). This session
authored none of Task A/B/C/D implementation or fixes, none of the
direction/breakdown/design, and none of the four review-1 outputs.

## Method

Independent recomputation, no trust of narration:

- Recomputed all five diff fingerprints with the schema algorithm
  (`git diff --binary <base>..<head> -- . ':(exclude).../status.json' | shasum -a 256`).
- Re-read the load-bearing code, not just the reviewers' claims.
- Re-ran the frontend self-check and the backend suite on the reviewed head.

## Fingerprint integrity — ALL MATCH

| Range | Expected | Recomputed |
|---|---|---|
| Combined `7bdc9049..d21536aa` | `378c060d…` | `378c060d…` ✓ |
| Task A `0206f8bf..2e27efc` | `85c78070…` | `85c78070…` ✓ |
| Task B `744ce5f0..f9f86bb` | `a3284786…` | `a3284786…` ✓ |
| Task C `5a5b9f6..c2bb368` | `5ade324b…` | `5ade324b…` ✓ |
| Task D `7480fdb..d21536aa` | `553e9a36…` | `553e9a36…` ✓ |

No range tampering. Every review-1 output reviewed the committed range it claims.

## Independent verification of review-1 verdicts

- **Task A (kimi) ACCEPT — CONCUR.** No P0/P1. P2 (cache keyed by symbol only)
  confirmed at `snapshot_service.py:305,318`; `70-handoff.md` records this as an
  intentionally accepted ≤1,800s staleness bound, not a rework. P3
  (`data_time_ms=0` → negative startTime) confirmed as a low-priority hardening
  candidate. Documented residual risks, not blockers.
- **Task B (claude-glm) REWORK — CONCUR (blocking).** Confirmed at
  `self-check.js:441`: regex `/<th[^>]*>([^>]*)\/>th>/g` tail `/>th>` never
  matches `</th>`, so `headers` is always `[]`, `bad` always `undefined`, and the
  throw at line 445 never fires. `node frontend/self-check.js` prints
  `全部自检通过` **because** this AC5 negative-guard no-ops. The independent 5b
  positive check (lines 330-334) still validates annualized header copy and the
  shipped product headers are correct — so this is a **test-integrity defect
  only**, but a self-check that silently disables an AC guard cannot pass the
  gate. This is the one open item blocking stage acceptance.
- **Task C (kimi) ACCEPT — CONCUR.** No findings; endpoint + schema + tests match
  the `13-review-feedback-fix.md` contract. Backend suite re-run: `244 passed`.
- **Task D (claude-glm) ACCEPT — CONCUR.** All findings P3, non-blocking. P3-1
  (`badgeForRouteClass` orphan) confirmed via grep: definition-only at
  `index.html:1045`, zero call sites — a surgical-changes cleanup miss, not a
  gate blocker.

## Re-run evidence (reviewed head)

- `node frontend/self-check.js` → `全部自检通过` (passes because of the #11 defect above).
- `python3 -m pytest backend/tests -q` → `244 passed`.

## Verdict

The stage has three sound ACCEPTs and one sound, blocking REWORK (Task B). It is
**not acceptable as-is**. review-2 returns **REWORK / next_action=fix**:

1. Apply the bounded `frontend/self-check.js` #11 regex fix (verbatim
   `fix_start_prompt` in `review-1-task-b-claude-glm.rework.raw-output.md`).
2. Re-review Task B in a fresh read-only session to ACCEPT on the new committed
   Task B range.
3. Rebind the combined stage range/fingerprint and re-run review-2 on the final
   clean range. The current `378c060d…` predates the fix and cannot be the
   accepted range.

This is review evidence only. No `status.json` mutation, no commit, no
canonical-doc promotion, no merge, and no final acceptance are performed here —
those remain the bookkeeper's and the user's actions.

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-funding-annualized-history-v1",
  "role": "final_reviewer",
  "model": "anthropic/claude-opus-4-8",
  "verdict": "REWORK",
  "diff_fingerprint": "d21536aa8a221a065c4fbe2b7640e199addca7dc:378c060d86086d7d9a6c8eff94aad1e0998bdd014a255070eb1504fe3bca62a8",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Fresh, unrelated Anthropic Claude session (claude-opus-4-8) taking over the review-2 gate because the Codex/GPT strong-reviewer fallback is quota-exhausted. This session is the review-2 primary the stage handoff named ('an unrelated Anthropic Claude session'); it authored none of Task A/B/C/D implementation or fixes, none of the direction/breakdown/design, and none of the four review-1 outputs.",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-a-kimi.raw-output.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-b-claude-glm.rework.raw-output.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-c-kimi.raw-output.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-d-claude-glm.raw-output.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/70-handoff.md",
    "reports/agent-runs/2026-07-funding-annualized-history-v1/status.json",
    "frontend/self-check.js",
    "frontend/index.html",
    "backend/services/snapshot_service.py",
    "backend/tests",
    "schemas/review-verdict.schema.json",
    "scripts/validate-stage.py"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "Concur with Task B review-1 REWORK: self-check #11 header-discrimination regex is a dead assertion (gate integrity defect)",
      "file": "frontend/self-check.js",
      "line": 441,
      "evidence": "Independently confirmed on the reviewed head. Line 441 reads matchAll(/<th[^>]*>([^<]*)\\/>th>/g) (\\u003e/\\u003c escaped). The tail \\/>th> (/>th>) can never match a real closing tag </th>, so headers is always [], nonSettledHeaders always [], bad always undefined, and the throw at line 445 never fires. Running `node frontend/self-check.js` prints 全部自检通过 precisely because this AC5 negative-guard no-ops. The independent positive check at 5b (lines 330-334) still validates the annualized header copy, and the shipped product headers are correct; the defect is test-integrity only.",
      "impact": "The only self-check guarding that non-annualized columns (资金费率/日费率/...) do NOT carry 已结算/预测 labels is silently disabled. A future regression mislabeling those columns would pass the frontend gate with false assurance. No product/runtime defect; the gate lies.",
      "recommendation": "Apply the bounded fix already written in review-1-task-b-claude-glm.rework.raw-output.md .fix_start_prompt: change the regex to /<th[^>]*>[\\s\\S]*?<\\/th>/g, keep the 年化 7D/30D exclusion, add a positive assertion that headers.length equals the rendered <th> count so it cannot silently empty again, and verify the check THROWS when 已结算/预测 is injected into a non-annualized header. Scope strictly to frontend/self-check.js."
    }
  ],
  "required_fixes": [
    "Resolve the open Task B review-1 REWORK: apply the bounded frontend/self-check.js #11 regex fix (see the verbatim fix_start_prompt in review-1-task-b-claude-glm.rework.raw-output.md), re-run node frontend/self-check.js, then re-review Task B (fresh read-only session) to ACCEPT on the new committed Task B range before any review-2 ACCEPT of the whole stage.",
    "After the Task B fix is committed, rebind the combined stage range and diff_fingerprint and re-run review-2 (this gate) on the final clean range; the current fingerprint d21536aa...:378c060d... predates the Task B fix and cannot be the accepted range."
  ],
  "residual_risks": [
    "Task A P2 (backend/services/snapshot_service.py:305,318): funding-history cache is keyed by symbol only, not (symbol,start_ms,end_ms); up to the documented 1,800s TTL a later snapshot with an advanced t_end_ms can reuse an earlier 30-day window. Independently confirmed; handoff records this as an intentionally accepted staleness bound, not a rework. Track as documented residual risk.",
    "Task A P3 (snapshot_service.py:114): data_time_ms=0 from an empty/time-less premium_index yields a negative deep-history startTime; low-priority hardening candidate, degrades a row rather than failing the snapshot. Not accepted as a Task A rework.",
    "Task D P3-1 (frontend/index.html:1045): badgeForRouteClass is now an orphan (definition only, zero call sites) after the route-class column removal; violates surgical-changes cleanup but non-blocking. Independently confirmed via grep. Recommend removing in the Task B fix pass or a later cleanup, not as a gate blocker.",
    "Task D P3-2..P3-5: colspan=12 placeholder lacks a direct assertion; getSnapshot __appHelpers hook unused; redundant post-await isActive guards in the 502/!res.ok branches; test 53 stale-isolation assertion is imprecise vs test 54. All non-blocking readability/test-strength nits.",
    "Frontend self-check runs in a Node mock and cannot verify real-browser layout (620px drawer overflow, label wrapping) or exhaustively exercise event-loop races; source-string assertions only."
  ],
  "fix_start_prompt": "You are a bounded Task B fix session for stage 2026-07-funding-annualized-history-v1, closing the open review-1 REWORK confirmed by review-2. Fix exactly ONE defect. Do not touch product/UI code, backend, schema, fixture values, canonical docs, status.json, or unrelated files; do not create a commit or invoke another model. Authoritative, verbatim fix instructions live in reports/agent-runs/2026-07-funding-annualized-history-v1/review-1-task-b-claude-glm.rework.raw-output.md under .fix_start_prompt (base_sha=744ce5f0b9445a891c1322bcb34e06ce94c83446, head_sha=f9f86bb6bcc2040844ad55f4f85937e85d393e5d). Defect: frontend/self-check.js test #11 (line 441) regex /<th[^>]*>([^<]*)\\/>th>/g has tail /> th> that never matches </th>, so `headers` is always [], the AC5 negative label-guard is a dead assertion, and node frontend/self-check.js prints 全部自检通过 unconditionally. Required fix: replace the regex with /<th[^>]*>[\\s\\S]*?<\\/th>/g so it matches real <th ...>...</th> including the title attribute; keep the 年化 7D/30D exclusion and the find(bad) logic. Success criteria: (1) node frontend/self-check.js prints 全部自检通过 and #11 still PASSes on the real headers; (2) headers.length asserts equal to the rendered <th> count, and injecting 已结算/预测 into a non-annualized header (e.g. 资金费率/日费率) makes #11 THROW, then revert the injection; (3) git diff --check passes and the diff is limited to frontend/self-check.js; (4) python3 -m pytest backend/tests -q stays at 244 passed (do not touch it). Do not expand into Task D changes and do not chase the P3 residual risks here. After the fix is committed on a new Task B range, re-review Task B (fresh read-only session) and then re-run review-2 on the recomputed combined stage fingerprint before any ACCEPT.",
  "next_action": "fix"
}
```

```text
本地北京时间: 2026-07-10 23:35 CST
下一步模型: bookkeeper（记录本 review-2 REWORK 到 status.json）→ human operator 派 Task B 定界修复
下一步任务: 录入 review-2 REWORK 证据；派发 review-1-task-b 的 fix_start_prompt（仅改 frontend/self-check.js）；Task B 重评 ACCEPT 后重算合并指纹并重跑 review-2。
```
