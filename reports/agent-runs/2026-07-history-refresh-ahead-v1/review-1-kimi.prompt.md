# Kimi Formal Review-1 — Funding History Refresh-Ahead

You are the formal review-1 reviewer for stage
`2026-07-history-refresh-ahead-v1`.

## Identity And Mode

- Reviewer: Kimi, model `kimi-code/kimi-for-coding`
- Provider identity: `moonshot_kimi`
- Role skill: `agents/skills/code-reviewer.md`
- Implementer: Claude-GLM / `glm-5.2`, provider identity `zhipu_glm`
- Reviewer prior involvement: `none`
- Use a fresh provider-isolated session.

This review is strictly read-only. Do not edit/create files, commit, merge,
rebase, push, start services, access external networks, or invoke another model.
Treat implementation comments/reports as claims to verify against raw committed
evidence.

## Exact Review Binding

- Base SHA: `12b8e1c1ea5d86bf692bbba2183de08ee9429af4`
- Reviewed implementation/evidence head SHA:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601`
- Authoritative diff fingerprint:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`

Later bookkeeping commits may exist. Review only the fixed committed range:

```bash
git diff --binary 12b8e1c1ea5d86bf692bbba2183de08ee9429af4..2cb72fd870b1ef29cc4787e7dff102ab56bf8601 -- . ':(exclude)reports/agent-runs/2026-07-history-refresh-ahead-v1/status.json'
```

Recompute the SHA-256 fingerprint independently. The verdict must use the exact
authoritative fingerprint above, never moving `HEAD`.

## Required Raw Inputs

Read directly:

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` review-1 section
3. `agents/skills/code-reviewer.md`
4. `schemas/review-verdict.schema.json`
5. `reports/agent-runs/2026-07-history-refresh-ahead-v1/00-intake.md`
6. `reports/agent-runs/2026-07-history-refresh-ahead-v1/00-task.md`
7. `reports/agent-runs/2026-07-history-refresh-ahead-v1/10-design.md`
8. `reports/agent-runs/2026-07-history-refresh-ahead-v1/11-adr.md`
9. `reports/agent-runs/2026-07-history-refresh-ahead-v1/20-implementation.md`
10. `reports/agent-runs/2026-07-history-refresh-ahead-v1/60-test-output.txt`
11. the exact committed diff and relevant source/test files.

Do not read any `history/` directory or adopt conclusions from another stage's
review transcript.

## Frozen User Requirements

- Only funding history becomes refresh-due 300 seconds before publication
  expiry: default 1500 refresh-due / 1800 publish-expiry.
- Borrow-rate, max-borrowable, Group B, private transport TTLs, coverage ledger,
  and `-0.00030000` exit/re-entry behavior remain unchanged.
- No config default/env, frontend, API/schema, manual refresh, candidate
  selection, cursor-size, or trading changes.
- The inherited pre-fetch history timestamp P3 remains explicitly out of scope.

## Review Focus

Adversarially verify at minimum:

1. `_history_is_fresh()` and `_fetch_history_for()` use the same derived
   `max(0, publication_ttl - 300)` refresh threshold.
2. `_all_valid_history()` still uses the full configured publication TTL; a
   direct global TTL change did not move the visible gap to 1500 seconds.
3. At 1500 seconds the cache-reuse guard reaches real public history I/O rather
   than returning the old cache entry.
4. Failed early refresh does not overwrite the old successful cache and it
   remains publishable through 1799 seconds under existing retry semantics.
5. Borrow-rate and max-borrowable do not become due at 1500 seconds; the shared
   `component_ttl`, Group B, private transport TTLs, coverage/re-entry semantics,
   and at-most-10-symbol cursor remain unchanged.
6. The five new tests are deterministic and non-tautological, including the
   1499/1500 boundary, 1800 publication boundary, success continuity, and
   private-call isolation.
7. The clamp behavior for configured TTL values at or below 300 seconds is
   safe and consistent with the frozen formula; flag material request-pressure
   or correctness issues if present.
8. The committed diff contains no hidden API, schema, frontend, config, manual
   refresh, or trading behavior changes.

## Verdict Contract

Respond primarily in Chinese with a concise evidence-based narrative. End the
entire response with exactly one JSON object, no Markdown fence and no text
after it, matching `schemas/review-verdict.schema.json`.

Required JSON literals:

- `schema_version`: `1`
- `stage_id`: `2026-07-history-refresh-ahead-v1`
- `role`: `first_reviewer`
- `model`: `kimi-code/kimi-for-coding`
- `diff_fingerprint`:
  `2cb72fd870b1ef29cc4787e7dff102ab56bf8601:a1406bde574ed193c12ee826f56102e99d6db029f6742d4412b44fea344b1ef3`
- `reviewer_prior_involvement`: `none`

Order findings by severity with exact file/line evidence, impact, and
recommendation. Do not return `ACCEPT` when any required correction remains.

If verdict is `REWORK`, include a ready-to-send `fix_start_prompt` in both the
human narrative and JSON. It must preserve the stage/fingerprint, raw review
path `reports/agent-runs/2026-07-history-refresh-ahead-v1/30-review-1.md`, ordered
findings, required fixes, the original three-file boundary narrowed as needed,
forbidden paths/side effects, exact commands below, and a required finding-to-fix
mapping in `40-fix-report.md`:

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
