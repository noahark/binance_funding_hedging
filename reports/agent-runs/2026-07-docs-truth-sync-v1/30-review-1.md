# Review-1 Report — 2026-07-docs-truth-sync-v1

Reviewer: Kimi (`kimi-code/kimi-for-coding`)  
Role: review-1 (cross-review isolation from implementer `claude_glm`)  
Provider: Moonshot  
Read-only: no files modified.

## Scope Reviewed

- Committed delivery range: `127a600281d60b7332be8aeb9552740a5e8c3254..c72987dc5cfe288e8df887cd14a965a48e93e3f3`
- `diff_fingerprint` (pre-review validated, used as-given):
  `c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`
- Delivery files under review (8):
  - `docs/api/public-market-contract.md`
  - `docs/product/PRD.md`
  - `docs/development/DEVELOPMENT_GUIDE.md`
  - `docs/planning/DECISIONS.md`
  - `docs/architecture/ARCHITECTURE.md`
  - `reports/follow-ups/README.md`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`
- Background/task artifacts read:
  - `00-task.md`, `10-design.md`, `12-development-breakdown.md`, `20-implementation.md`, `60-test-output.txt`, `62-validate-pre-review.txt`
- Truth references sampled:
  - `schemas/api/public-market/{snapshot,funding-history,symbol-snapshot}.schema.json`
  - `backend/app/server.py`, `backend/config.py`
  - `backend/tests/test_funding_history.py`, `backend/tests/test_funding_history_endpoint.py`
  - `scripts/service-control.py`, `frontend/index.html`

## Checklist Findings

### 1. Contract vs schema consistency — PASS

`docs/api/public-market-contract.md` now contains:

- `### GET /api/public-market/funding-history` with required fields matching `funding-history.schema.json` exactly:
  `schema_version`, `symbol`, `data_time`, `history_status`, `funding_history`, `annualized_funding_7d`, `annualized_funding_30d`.
- Explicit statement that `annualized_funding_24h` is **not** on this payload — consistent with schema (the field is absent).
- `### GET /api/public-market/symbol-snapshot` with required fields matching `symbol-snapshot.schema.json`:
  `schema_version`, `symbol`, `published_version`, `data_time`, `generated_at`, `refresh_status`, `warnings`, `row`.
  `refresh_status` enum `ok | partial | timeout` matches schema; `row` is a single projected snapshot row, never a `rows` array.
- `### Annualized funding fields (row-level, as-built)` describing `annualized_funding_24h/7d/30d` semantics matching `snapshot.schema.json#/$defs/row` descriptions (24h estimate-derived = `daily_funding_rate × 365`; 7d/30d settled calendar-window sums; null semantics; estimate/settled never mixed).
- Endpoint paths match `backend/app/server.py` route table (`/api/public-market/snapshot`, `/api/public-market/symbol-snapshot`, `/api/public-market/funding-history`).

No schema-nonexistent fields, endpoints, or parameters were introduced.

### 2. PRD as-built truthfulness — PASS

`docs/product/PRD.md`:

- Removed the "Manual open preview: simulation only" existing-UI language and replaced it with an as-built opening-spread display description using `opening_quotes` / `forward_spread_pct` / `reverse_spread_pct`.
- Added as-built mentions of the serial background refresh worker, `opening_quotes`, annualized funding columns, settled 7D/30D + estimate 24h, and the macOS launchd agent `com.aoke.funding-hedging.server` managed by `scripts/service-control.py`.
- Split "Technology Direction" into as-built (stdlib `http.server` + static frontend) vs future (asyncio / React / TS) layers.
- `frontend/index.html` confirms there is no order/open/borrow/transfer ticket; the only "开仓" reference is the `<th>开仓价</th>` / opening-spread column header.

### 3. Dead-link / retired wording — PASS

- `reports/follow-ups/README.md` no longer frames `docs/auto-review-pipeline.md` / `scripts/auto-review-runner.py` as current normative contract; it now reads "retired by DEC-2026-07-14-002" and "deleted".
- `docs/planning/DECISIONS.md` adds historical parentheticals to DEC-2026-07-14-001 Source entries pointing to the deleted files and to DEC-2026-07-14-002.

### 4. File boundaries — PASS

`git diff --name-only 127a600..c72987d` lists exactly 8 delivery files, all within the Allowed set. No Forbidden paths were touched:
`STAGE_INDEX.md`, `ROADMAP.md`, `harness-manifest.yaml`, `docs/harness-design.md`, `AGENTS.md`, `docs/planning/stage-branch-mode.md`, `docs/README`, `docs/architecture/ADR/`, and all `backend/` / `frontend/` / `schemas/` / `scripts/` code remain unchanged.

### 5. P1-9 bookticker living-docs normalization — PASS

- `70-handoff.md` and `20-implementation.md` no longer contain contradictory intermediate-state tokens (`Formal review has not started`, `pending`, `awaiting`, `waiting for`, etc.).
- `status.json` was not modified. A direct grep for pending/awaiting/waiting/not-started tokens in the current `status.json` returns no matches; the file records `status: accepted`, `user_acceptance: accepted_merged_and_pushed`, and complete `merge_result` / `review_2` ACCEPT data.

### 6. Adjudication of P1-9 boundary divergence — RESOLVED

Design P1-9 named `status.json` as a living-doc to normalize, but the implementer left it unchanged. Review-1 adjudicates:

- The bookticker stage `status.json` is a frozen accepted-stage audit record (`status: accepted`, `user_acceptance: accepted_merged_and_pushed`).
- It contains no contradictory intermediate-state tokens.
- Rewriting its historical notes would risk tampering with accepted-stage audit evidence.
- Therefore, leaving `status.json` untouched is the correct boundary decision; the living-doc normalization requirement is satisfied by updating the handoff and implementation reports while preserving the accepted record verbatim.

## Mechanical Assertions

All 6 acceptance assertions in `60-test-output.txt` passed:

1. `grep -c annualized docs/api/public-market-contract.md` = 7 (> 0).
2. Independent `funding-history` and `symbol-snapshot` endpoint section titles present in contract.
3. `reports/follow-ups/README.md` no longer contains "current normative" / "delivered on main" framing for auto-review-pipeline.
4. `docs/product/PRD.md` no longer contains "simulation-only" existing-UI wording.
5. `docs/development/DEVELOPMENT_GUIDE.md` documents `test_funding_history*.py`, `APP_BACKGROUND_REFRESH_*`, `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`.
6. No Forbidden paths appear in the diff.

`scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review` returned PASS with the expected fingerprint.

## Residual Risks / Notes

- This stage deliberately deferred `STAGE_INDEX.md`, `ROADMAP.md`, `harness-manifest.yaml`, `docs/harness-design.md`, `AGENTS.md`, `docs/planning/stage-branch-mode.md`, `docs/README`, and `docs/architecture/ADR/` to Stage B or the Harness track. Review-1 confirms none of these were touched.
- The current repository HEAD (`e5491a5`) includes two bookkeeper chore commits after the implementation head (`c72987d`). Those commits only add stage metadata (`status.json`, `70-handoff.md`, `62-validate-pre-review.txt`, `35-dispatch-review-1-kimi.md`) and do not alter the 8 delivery files. The review verdict uses the pre-review-validated fingerprint anchored at `c72987d`.

## Verdict

ACCEPT. The documentation backfill is consistent with schema, code, and frontend truth; file boundaries are respected; P1-9 normalization is complete; and the residual `status.json` boundary question is resolved in favor of preserving accepted-stage audit evidence.

当前 Session ID: unavailable (Kimi CLI provider-native Session ID not exposed to model at runtime)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md
本地北京时间: 2026-07-16 18:14:45 CST
下一步模型: review-2 (Codex/GPT primary; Claude Fable5/Opus4.8 fallback)
下一步任务: 执行 final review 并产出 schema-valid JSON verdict

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "first_reviewer",
  "model": "kimi",
  "verdict": "ACCEPT",
  "diff_fingerprint": "c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Kimi participated in the four-model read-only audit that informed the stage backlog, but did not author the stage design, development breakdown, implementation, or any fix. For review-1 cross-review isolation, provider identity is separate from the implementer claude_glm (Zhipu GLM).",
  "reviewed_artifacts": [
    "docs/api/public-market-contract.md",
    "docs/product/PRD.md",
    "docs/development/DEVELOPMENT_GUIDE.md",
    "docs/planning/DECISIONS.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/follow-ups/README.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/62-validate-pre-review.txt",
    "schemas/api/public-market/snapshot.schema.json",
    "schemas/api/public-market/funding-history.schema.json",
    "schemas/api/public-market/symbol-snapshot.schema.json",
    "backend/app/server.py",
    "backend/config.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "scripts/service-control.py",
    "frontend/index.html"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "P1-9 status.json left untouched as accepted-stage audit record",
      "file": "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
      "line": null,
      "evidence": "Design P1-9 named status.json for normalization, but the implementer did not modify it. Direct grep for pending/awaiting/waiting/not-started tokens in the current status.json returns no matches; the file records status=accepted, user_acceptance=accepted_merged_and_pushed, and complete merge_result/review_2 ACCEPT data.",
      "impact": "Low. The historical accepted-stage record is preserved without modification, avoiding audit-evidence tampering. The handoff and implementation reports were normalized instead.",
      "recommendation": "Review-1 accepts this boundary decision. No fix required."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Stage B will need to generate STAGE_INDEX.md/ROADMAP.md from status.json to avoid manual drift; this stage did not touch those files.",
    "Harness-track documentation changes (harness-design.md, AGENTS.md known-gaps, stage-branch-mode.md, docs/README) remain deferred to the template-repo-first Harness track."
  ],
  "next_action": "continue"
}
```
