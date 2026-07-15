# Claude Final Review-2 — Funding History Refresh-Ahead

You are the final review-2 decision reviewer for stage
`2026-07-history-refresh-ahead-v1`.

## Identity And Eligibility

- Reviewer provider: Anthropic Claude
- Model: `claude-fable-5`
- Provider identity: `anthropic`
- Role: final reviewer using `agents/skills/code-reviewer.md`
- Reviewer prior involvement in this stage: `none`
- Implementation author: Claude-GLM / `zhipu_glm`; this is a different provider
  identity from Anthropic
- Stage designer/bookkeeper: Codex / `openai`; no Anthropic design involvement
- Review-1: Kimi / `moonshot_kimi`, schema-valid `ACCEPT`

Use a fresh read-only/plan session. Do not edit/create files, commit, merge,
rebase, push, start services, use external networks, call Binance, or invoke
another model. Model/report claims are not evidence; inspect the fixed committed
range and raw artifacts directly.

Codex is the configured primary review-2 provider but is ineligible as the stage
designer while an unrelated registered decision provider is available. Claude
is selected under the documented `anti_self_review_ineligible` fallback and has
no prior involvement requiring a disclosure override.

## Exact Review Binding

- Base SHA: `12b8e1c1ea5d86bf692bbba2183de08ee9429af4`
- Reviewed implementation/evidence head SHA:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601`
- Authoritative diff fingerprint:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`

Later bookkeeping/review commits may exist. Review only this fixed range:

```bash
git diff --binary 12b8e1c1ea5d86bf692bbba2183de08ee9429af4..2cb72fd870b1ef29cc4787e7dff102ab56bf8601 -- . ':(exclude)reports/agent-runs/2026-07-history-refresh-ahead-v1/status.json'
```

Independently recompute the fingerprint and bind the final verdict to the exact
authoritative value above, never moving `HEAD`.

## Requirements Authority And Raw Inputs

The user's approved scope in `00-intake.md` and `00-task.md` is the top-level
requirement. The design/ADR are evidence under review, not authority over the
user's decision.

Read directly:

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` review-2 section
3. `agents/skills/code-reviewer.md`
4. `schemas/review-verdict.schema.json`
5. `reports/agent-runs/2026-07-history-refresh-ahead-v1/00-intake.md`
6. `reports/agent-runs/2026-07-history-refresh-ahead-v1/00-task.md`
7. `reports/agent-runs/2026-07-history-refresh-ahead-v1/10-design.md`
8. `reports/agent-runs/2026-07-history-refresh-ahead-v1/11-adr.md`
9. `reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md`
10. `reports/agent-runs/2026-07-history-refresh-ahead-v1/30-review-1.md`
11. `reports/agent-runs/2026-07-history-refresh-ahead-v1/60-test-output.txt`
12. the exact committed diff and relevant source/test files.

Do not read any `history/` directory or rely only on the Kimi conclusion.

## Frozen User Scope

- Funding history alone becomes refresh-due 300 seconds before publication
  expiry: default 1500 refresh-due / 1800 publish-expiry.
- Borrow-rate, max-borrowable, Group B, private transport TTLs, coverage ledger,
  and `-0.00030000` exit/re-entry behavior remain unchanged.
- No config default/env, frontend, API/schema, manual refresh, candidate
  selection, cursor-size, or trading change.
- Inherited pre-fetch history timestamp P3 remains explicitly out of scope.

## Final Review Focus

Verify independently:

1. Refresh and publication TTLs are actually separated; `_all_valid_history()`
   did not inherit the 1500 threshold.
2. Both `_history_is_fresh()` and `_fetch_history_for()` use the same derived
   refresh threshold, so 1500 reaches real public I/O and 1499 reuses cache.
3. Early refresh failure preserves the old successful cache through 1799 and
   does not introduce false freshness or cache overwrite.
4. Successful early refresh removes the normal-success empty window after the
   original 1800 boundary.
5. Borrow-rate/max-borrowable remain at 1800; Group B, private transport,
   coverage/re-entry, cursor pressure, API/schema/frontend/manual/trading paths
   are untouched.
6. Clamp behavior for configured TTL `<=300` is consistent with the approved
   formula and does not create an acceptance-blocking correctness or pressure
   regression.
7. The five tests and bookkeeper adversarial reproduction are meaningful and
   the recorded 37/335 passing evidence is credible.
8. Kimi review-1 JSON is schema-valid, fingerprint-bound, provider-isolated,
   and contains no unresolved finding—but do not defer your own judgment to it.

## Verdict Contract

Respond primarily in Chinese with a concise evidence-based final-review
narrative. End the entire response with exactly one JSON object, no Markdown
fence and no text after it, matching `schemas/review-verdict.schema.json`.

Required JSON literals:

- `schema_version`: `1`
- `stage_id`: `2026-07-history-refresh-ahead-v1`
- `role`: `final_reviewer`
- `model`: `claude-fable-5`
- `diff_fingerprint`:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`
- `reviewer_prior_involvement`: `none`

Return `ACCEPT` only if no required correction remains. For an `ACCEPT`, set
`next_action` to `stage_accepted_waiting_user`.

If verdict is `REWORK`, include a ready-to-send `fix_start_prompt` in both the
narrative and JSON. Preserve stage/fingerprint, raw review path
`reports/agent-runs/2026-07-history-refresh-ahead-v1/50-review-2.md`, ordered
findings, required fixes, narrowed original three-file boundary, forbidden
paths/side effects, exact commands below, and required finding-to-fix mapping in
`40-fix-report.md`:

```bash
python3 -m pytest backend/tests/test_background_worker.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/services/snapshot_service.py backend/tests/test_background_worker.py
git diff --check
git status --short
```

Place this footer immediately before the final JSON object:

```text
本地北京时间: <from local date command> CST
下一步模型: <human-or-claude_glm>
下一步任务: <specific action>
```
