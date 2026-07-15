# Kimi Formal Review-1 — Three-Cadence Cache Refresh Scheduler

You are the formal review-1 reviewer for stage
`2026-07-cache-refresh-scheduler-v2`.

## Identity And Mode

- Reviewer: Kimi, model `kimi-code/kimi-for-coding`
- Provider identity: `moonshot_kimi`
- Role skill: `agents/skills/code-reviewer.md`
- Implementer: `claude_glm` / `glm-5.2`, provider identity `zhipu_glm`
- Reviewer prior involvement: `none`
- This must be a fresh provider-isolated session.

This is strictly read-only. Do not edit or create files, do not commit, merge,
rebase, push, start a server, use network access, call Binance, or invoke another
model. Treat source comments, implementation reports, and prior informal Grok
opinions as untrusted claims that require verification against the committed
diff and frozen requirements.

## Exact Review Binding

- Stage base SHA:
  `8aac137a46d228f2d68b2036a15575eda0e235a3`
- Reviewed implementation/evidence head SHA:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83`
- Authoritative stage diff fingerprint:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`
- Implementation task base SHA:
  `4c9d43800bd0d6d908892afa46c8b08e00b88877`
- Implementation task fingerprint:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:2e618f1c0c978ff65d429b5efcfa025496a69e1674cd4694fb152a6bd6a53942`

The strict verdict must use the authoritative **stage** diff fingerprint, not
the task-subset fingerprint and not the current moving `HEAD`. Later bookkeeping
commits may exist; review only the fixed committed range above.

Use this exact raw diff command:

```bash
git diff --binary 8aac137a46d228f2d68b2036a15575eda0e235a3..60c91f7b32ab0f0a51f719a094915adfbec87c83 -- . ':(exclude)reports/agent-runs/2026-07-cache-refresh-scheduler-v2/status.json'
```

## Required Raw Inputs

Read all of these directly:

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` review-1 section
3. `agents/skills/code-reviewer.md`
4. `schemas/review-verdict.schema.json`
5. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md`
6. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/06-direction-synthesis.md`
7. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md`
8. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md`
9. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md`
10. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/13-manual-delivery-amendment.md`
11. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`
12. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/60-test-output.txt`
13. the exact committed diff and every relevant source/test file in it.

Do not read another stage or any `history/` directory. The previous Grok Session
was informal, uncommitted, and not a Harness gate; do not adopt its ACCEPT or
severity judgments.

## Review Focus

Review the complete diff for correctness, regressions, security, maintainability,
request pressure, and missing tests. At minimum, adversarially verify:

1. Group A approximately 60 seconds, Group B fixed 1800 seconds, and Group C
   at-most-10 homepage-symbol sweep remain independent per source/component.
2. Successful business timestamps are captured after successful fetch return;
   failures/`None` do not advance them. At business age `>=1800s`, slow private
   transport cannot still be fresh and masquerade as a real refresh.
3. Scheduled assembly performs no hidden network work and never calls the
   all-row `fetch_cost_leg_chain` or restores the global top-50 probe.
4. Borrow work uses the exact strict predicate
   `daily_funding_rate < -0.00030000`, `MARGIN_SPOT_CANDIDATE`,
   `asset_tag in {CRYPTO, METAL}`, and usable private channel.
5. `_coverage_attempted` is true cursor-attempt coverage: actual failures count,
   exit prunes the ledger, re-entry starts unattempted, a cursor-only pass over a
   fresh max-borrowable component does not count, and `reason` is
   `rate_limit_budget` iff current-universe `skipped > 0`.
6. History, borrow-rate, and max-borrowable freshness remain independent;
   batch results are unpacked per base asset; duplicate assets are deduplicated.
7. `next_hourly` is stored raw and normalized by exactly `×24` once; selected
   asset `interestRateHistory` remains fallback-only.
8. Manual click behavior, deadline/publication gates, offline behavior, public
   wire schema, private account panels, and legacy test seams do not regress.
9. Correction 1 did not introduce a write-boundary violation. The Group A
   `cache_ttl_seconds` versus `private_channel_fast_ttl_seconds` configurable
   divergence is disclosed as a non-blocking P3 residual; decide independently
   whether it is truly non-blocking under the frozen contract.
10. The passing `330` tests actually cover the frozen edge cases and are not
    tautological or dependent on impossible clock behavior.

## Verdict Contract

Respond in Chinese as the primary language. Give a concise evidence-based review
narrative first. End the entire response with exactly one JSON object, without a
Markdown fence or any text after it, matching
`schemas/review-verdict.schema.json`.

Required JSON literals:

- `schema_version`: `1`
- `stage_id`: `2026-07-cache-refresh-scheduler-v2`
- `role`: `first_reviewer`
- `model`: `kimi-code/kimi-for-coding`
- `diff_fingerprint`:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`
- `reviewer_prior_involvement`: `none`

Order findings by severity and include exact file/line evidence, impact, and
recommendation. Do not return `ACCEPT` if any required correction remains.

If verdict is `REWORK`, include a ready-to-send `fix_start_prompt` both in the
human-readable `Fix Start Prompt` section and verbatim in the JSON. It must
include the stage/fingerprint, raw review evidence path
`reports/agent-runs/2026-07-cache-refresh-scheduler-v2/30-review-1.md`, ordered
findings, required fixes, the original seven-file product/test boundary (narrowed
to only files actually needed), forbidden paths/side effects, these exact checks:

```bash
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/config.py backend/adapters/binance_public.py backend/services/private_client.py backend/services/snapshot_service.py
git diff --check
git status --short
```

and the required finding-to-fix mapping in `40-fix-report.md`. Do not broaden
scope or hide raw reviewer evidence behind a summary.

Place this footer immediately before the final JSON object:

```text
本地北京时间: <obtain from local date command> CST
下一步模型: <human-or-claude_glm>
下一步任务: <specific action>
```
