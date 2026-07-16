# Review-1 Report — 2026-07-docs-truth-sync-v1 (round 2)

Reviewer: Kimi (`kimi-code/kimi-for-coding`)
Role: review-1 round 2 (cross-review isolation from implementer `claude_glm`)
Provider: Moonshot
Read-only: no files modified.

## Scope Reviewed

- Fixed delivery range: `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..a77a18aa069ecc236c8448b8bdced40ea53bdeb1`
- `diff_fingerprint` (bookkeeper pre-review PASS, used as-given):
  `a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9`
- Round 1 (`c72987d`) was ACCEPT by Kimi but REWORK by review-2 (Codex) for F1/F2/F3; claude_glm fixed and the new head is `a77a18a`. This report overwrites round-1's `30-review-1.md`; round-1 verdict is archived in `status.json.review_rounds[0]`.
- Delivery files changed by the fix (4):
  - `docs/api/public-market-contract.md`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`
- All 8 original delivery files remain within the Allowed set; no Forbidden path was touched.
- Background/task artifacts read:
  - `00-task.md`, `10-design.md`, `12-development-breakdown.md`, `20-implementation.md`
  - `40-fix-report.md` (fix mapping), `50-review-2.md` (Codex REWORK verdict)
  - `60-test-output.txt`, `62-validate-pre-review.txt`
- Truth references sampled:
  - `schemas/api/public-market/{snapshot,funding-history,symbol-snapshot}.schema.json`
  - `backend/services/snapshot_service.py`
  - `backend/tests/test_funding_history.py`, `backend/tests/test_funding_history_endpoint.py`, `backend/tests/test_symbol_snapshot_endpoint.py`
  - `backend/app/server.py`, `backend/config.py`, `scripts/service-control.py`, `frontend/index.html`

## Round-2 Fix Verification

### F1 — funding-history `empty` no longer over-claims upstream success — PASS

`docs/api/public-market-contract.md` now states:

> `funding_history`: newest-first settled records inside the inclusive 30-day window ending at `data_time`; each item `{funding_time (ms int ≥0), funding_rate (decimal string)}`. This payload is a **pure projection of the already-published snapshot row**: the endpoint issues no upstream fetch for this request — it reads `funding_history` straight from the published state and sets `history_status` to `empty` whenever that list has no entries. `empty` therefore means only "no settled records in the published row"; it **does not prove** that this request (or any prior fetch) succeeded.

This matches `snapshot_service.py:259-315` (`get_funding_history` / `_project_funding_history`), which performs zero upstream fetch and zero cache write, and `backend/tests/test_funding_history_endpoint.py:238-250` (`test_non_default_symbol_projects_when_present`), where an un-prewarmed symbol returns `200` / `history_status == "empty"` without any on-demand fetch.

The contract also discloses the deferred schema-prose drift at `funding-history.schema.json:34`, consistent with the docs-only boundary.

### F2 — symbol-snapshot `ok/partial/timeout` now covers actual service behavior — PASS

`docs/api/public-market-contract.md` now describes:

- `ok`: a fresh publication completed with no per-source `warnings`.
- `partial`: a fresh publication completed but at least one source emitted a `warnings` entry (`premium_refresh_failed:<symbol>`, `funding_history_unavailable:<symbol>`, `borrow_rate_refresh_failed:<asset>`, `max_borrowable_refresh_failed:<asset>`). A `partial` does NOT imply public/history figures are fresh.
- `timeout`: no fresh publication was produced; row is projected from the previously published (last-good) state. Triggers include shared deadline (`refresh_deadline_exceeded`), no live worker (`worker_not_running`), and assembly/validation failures (`assemble_failed`, `validation_crossed_deadline`). A `timeout` does not prove only a deadline expired.
- `warnings`: array of source-specific reason strings.

This matches `snapshot_service.py`:
- `:1527` — `cmd.refresh_status = "partial" if warnings else "ok"`.
- `:1420-1437` — premium/history failures append `premium_refresh_failed` / `funding_history_unavailable`.
- `:1446-1461` — borrow/max_borrowable failures append `borrow_rate_refresh_failed` / `max_borrowable_refresh_failed`.
- `:347-359` — worker not running → `timeout` + `worker_not_running`; deadline exceeded → `timeout` + `refresh_deadline_exceeded`.
- `:1397-1404, 1408-1411, 1465-1470, 1497-1502, 1514-1519, 1529-1533, 1535-1538` — base not ready, symbol not eligible, I/O post-deadline, assemble/validation failures all result in `timeout` without publishing.

And matches `backend/tests/test_symbol_snapshot_endpoint.py:252-270` (`test_history_failure_yields_partial_status`, `test_premium_failure_yields_partial_status`).

The contract also discloses the deferred schema-prose drift at `symbol-snapshot.schema.json:39`, consistent with the docs-only boundary.

### F3 — bookticker living-docs now historicized — PASS

`reports/agent-runs/2026-07-bookticker-open-columns-v1/{status.json,70-handoff.md,20-implementation.md}` no longer contain future/pending/current-tense wording that contradicts the accepted/merged/pushed state. Direct grep for the prior problematic phrases returns no matches in the fixed files.

Verified that only two `status.json` note fields were changed (lines 518 and 653); all audit facts remain unchanged:
- `status`: `accepted`
- `user_acceptance`: `accepted_merged_and_pushed`
- `merge_result.merged_back_sha`: `9abad62f...`
- `review_2.verdict`: `ACCEPT`
- `diff_fingerprint` and Session IDs preserved.

## Regression Check on Original 6 Acceptance Criteria

All original backfill acceptance criteria from round-1 remain satisfied and were not regressed by the fix:

1. `grep -c annualized docs/api/public-market-contract.md` = 7 (> 0). PASS.
2. Independent `funding-history` and `symbol-snapshot` endpoint section titles present. PASS.
3. `reports/follow-ups/README.md` no longer frames auto-review-pipeline as current normative contract. PASS.
4. `docs/product/PRD.md` no longer describes simulation-only manual-open as existing UI. PASS.
5. `docs/development/DEVELOPMENT_GUIDE.md` documents `test_funding_history*.py`, `APP_BACKGROUND_REFRESH_*`, `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`. PASS.
6. No Forbidden paths touched (diff contains only Allowed delivery files + stage metadata). PASS.

## Mechanical Verification

- `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review` (round 2): PASS with fingerprint `a77a18a:4185db38…`.
- Fix-author verification commands (re-run as spot-checks):
  - `python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json` — valid JSON.
  - `rg` for new semantics prose (`pure projection`, `does not prove`, `premium_refresh_failed`, `funding_history_unavailable`, `worker_not_running`, `warnings`) in contract — all present.
  - `rg` for old over-claim prose in contract — no matches.
  - `rg` for old future/pending prose in bookticker files — no matches.
  - `python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q` — 71 passed.
  - `git diff --check 127a600..a77a18a` — clean (no trailing whitespace/conflict markers).
  - `git diff --name-only 127a600..a77a18a` — only Allowed paths (contract + 3 bookticker living-docs + this stage's metadata; no backend/frontend/schema/script or deferred Harness-track files).

## Residual Risks / Notes

- `funding-history.schema.json:34` and `symbol-snapshot.schema.json:39` prose descriptions remain narrower than the as-built server/test behavior. The contract explicitly discloses this as a deferred schema-alignment item; this stage does not alter schemas, per its Non-Goals.
- Stage B / Harness-track files (`STAGE_INDEX.md`, `ROADMAP.md`, `harness-manifest.yaml`, `docs/harness-design.md`, `AGENTS.md`, `docs/planning/stage-branch-mode.md`, `docs/README`, `docs/architecture/ADR/`) remain untouched, as required.
- The current repository HEAD (`f9d6447`) includes bookkeeper chore commits after the implementation/fix head (`a77a18a`). Those commits only add stage metadata (`status.json`, `70-handoff.md`, `62-validate-pre-review.txt`, dispatch packets) and do not alter the 8 delivery files. The review verdict uses the pre-review-validated fingerprint anchored at `a77a18a`.

## Verdict

ACCEPT. F1, F2, and F3 from review-2 REWORK have been correctly addressed; the documentation now matches schema, server, and test truth; file boundaries are respected; and the residual schema-prose drift is properly disclosed as deferred.

当前 Session ID: unavailable (Kimi CLI provider-native Session ID not exposed to model at runtime)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md
本地北京时间: 2026-07-16 19:46:44 CST
下一步模型: review-2 (Codex/GPT primary; Claude Fable5/Opus4.8 fallback)
下一步任务: 执行 round-2 final review 并产出 schema-valid JSON verdict

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "first_reviewer",
  "model": "kimi",
  "verdict": "ACCEPT",
  "diff_fingerprint": "a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Kimi reviewed the prior round-1 fingerprint, which was superseded by review-2 REWORK and claude_glm fix. Kimi did not author this stage's design, development breakdown, implementation, or fixes. Provider (Moonshot) is isolated from implementer claude_glm (Zhipu GLM).",
  "reviewed_artifacts": [
    "docs/api/public-market-contract.md",
    "docs/product/PRD.md",
    "docs/development/DEVELOPMENT_GUIDE.md",
    "docs/planning/DECISIONS.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/follow-ups/README.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/62-validate-pre-review.txt",
    "schemas/api/public-market/snapshot.schema.json",
    "schemas/api/public-market/funding-history.schema.json",
    "schemas/api/public-market/symbol-snapshot.schema.json",
    "backend/app/server.py",
    "backend/services/snapshot_service.py",
    "backend/config.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "scripts/service-control.py",
    "frontend/index.html"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "F1/F2 contract wording now aligns with server/test truth; schema-prose drift disclosed as deferred",
      "file": "docs/api/public-market-contract.md",
      "line": null,
      "evidence": "Contract now describes funding-history as pure PublishedState projection and symbol-snapshot ok/partial/timeout with all source warnings and timeout triggers found in snapshot_service.py and test_symbol_snapshot_endpoint.py. Both schema files' narrower prose is explicitly disclosed as deferred contract-amendment items.",
      "impact": "Low. The docs-only fix correctly narrows human-readable contract to as-built behavior without altering schemas.",
      "recommendation": "No fix required. ACCEPT."
    },
    {
      "severity": "P3",
      "title": "F3 bookticker living-docs historicized without altering audit facts",
      "file": "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
      "line": null,
      "evidence": "status.json lines 518 and 653 now use past tense and reference completed review-2 ACCEPT and merge. All audit facts (SHA, fingerprint, Session ID, verdict, user_acceptance) remain unchanged.",
      "impact": "Low. Resolves the P1-9 contradiction noted by review-2 while preserving accepted-stage evidence integrity.",
      "recommendation": "No fix required. ACCEPT."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "funding-history.schema.json:34 and symbol-snapshot.schema.json:39 prose descriptions remain narrower than as-built behavior; alignment requires a separate contract-amendment stage with live/test evidence.",
    "Stage B will need to generate STAGE_INDEX.md/ROADMAP.md from status.json to prevent future drift; this stage did not touch those files.",
    "Harness-track documentation changes remain deferred to the template-repo-first Harness track."
  ],
  "next_action": "continue"
}
```
