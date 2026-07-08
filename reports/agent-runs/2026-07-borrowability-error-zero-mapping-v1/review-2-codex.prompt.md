# Review-2 Prompt (round 2) — Codex/GPT — 2026-07-borrowability-error-zero-mapping-v1

You are the final reviewer (review-2) for this Harness stage. This is **round 2**:
your round-1 verdict was BLOCKED **solely on a stale Harness gate state** (untracked
review-1 raw output, status still `review_1`, `30-review-1.md` not committed,
`pre-review` failing). You already cleared the code itself. The bookkeeper has since
resolved every gate item; this dispatch asks you to confirm the clean state and issue
a final verdict.

Reviewer identity:

- provider: `codex`
- provider_identity: `openai`
- role: `final_reviewer`
- reviewer_prior_involvement: `none` (isolated from implementer=zhipu_glm,
  designer/bookkeeper=anthropic, review-1=moonshot_kimi)

Hard rules:

- Read-only. Do not modify files, do not commit, do not call external APIs, no private credentials.
- Review the exact committed range and fingerprint below; do not review a moving HEAD.
- Your final output must end with one strict JSON object matching `schemas/review-verdict.schema.json` (role `final_reviewer`). Do not wrap it in a code fence.

Committed review range (unchanged from round 1 — the bookkeeper's review-1 landing
commits are AFTER head_sha and are excluded from the fingerprint):

```text
base_sha=41c6ba542e040cb3d1e82c046d9a9406bd11860d
head_sha=ea631bf1dbf23662db37f491d92cb3f10685d720
diff_fingerprint=ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa
```

```text
git diff --binary 41c6ba542e040cb3d1e82c046d9a9406bd11860d..ea631bf1dbf23662db37f491d92cb3f10685d720 -- . ':(exclude)reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json'
```

## Gate items you flagged in round 1 — now resolved (please re-verify)

1. `review-1-kimi.raw-output.md` committed; working tree clean. Verify:
   `git status --porcelain` is empty.
2. `30-review-1.md` landed (Kimi ACCEPT, fingerprint-matched, provider-isolated).
3. `status.json.status` = `review_2`; `review_1.status` = `accepted` / verdict `ACCEPT`.
4. `python3 scripts/validate-stage.py 2026-07-borrowability-error-zero-mapping-v1 --phase pre-review` => **PASSED** (rerun it; store nothing, just confirm).

Bookkeeper resolution recorded in
`reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/review-2-codex.round1.raw-output.md`
(commit landing the gate fixes: `10618a3`).

## Artifacts to (re)inspect

- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/{00-task,10-design,11-adr,12-development-breakdown,20-implementation,30-review-1,60-test-output,70-handoff}.md`
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/status.json` (incl. `scope_amendments` SCOPE-001/002, `bookkeeper_verification`)
- `reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/review-1-kimi.raw-output.md`
- product files: `backend/services/private_client.py`, `backend/domain/snapshot.py`, `backend/services/snapshot_service.py`, `backend/tests/{test_private_client,test_private_account_v1,test_phase2_borrow_sort}.py`, `backend/tests/fixtures/private-account-v1-design.json`, `schemas/api/public-market/snapshot.schema.json`, `docs/api/public-market-contract.md`, `frontend/index.html`, `frontend/self-check.js`
- `schemas/review-verdict.schema.json`

## Final-reviewer checks

- Confirm the frozen fingerprint recomputes to the value above.
- Confirm review-1 was ACCEPT, schema-valid, provider-isolated, against the same fingerprint.
- Confirm no open P0/P1; the code items you already cleared in round 1 (51061→"0",
  positive/negative code classification with `:238` preserved, ≈USDT 8dp valuation
  no-float, frontend three-state, additive schema/contract) remain as reviewed.
- Confirm reviewer isolation (openai vs zhipu_glm/anthropic/moonshot_kimi); no design-conflict override needed.

## Final JSON requirements

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-borrowability-error-zero-mapping-v1",
  "role": "final_reviewer",
  "model": "codex/gpt-5",
  "verdict": "ACCEPT|REWORK|BLOCKED",
  "diff_fingerprint": "ea631bf1dbf23662db37f491d92cb3f10685d720:31efea285e557d074f8f49d30146b07a285e3ecdb1a19d776b170479983251aa",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": ["..."],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "open_p0_p1": 0,
  "next_action": "stage_accepted_waiting_user|fix|human_escalation_required"
}
```

Save your raw output to
`reports/agent-runs/2026-07-borrowability-error-zero-mapping-v1/50-review-2.md`.

本地北京时间: 2026-07-09 07:20:00 CST
下一步模型: codex（review-2 round 2）
下一步任务: 复验干净 gate + 冻结区间，出 final verdict JSON。
