# Codex Formal Review-2 — Three-Cadence Cache Refresh Scheduler

You are the final review-2 reviewer for stage
`2026-07-cache-refresh-scheduler-v2`.

## Identity, Isolation, And Disclosure

- Reviewer: Codex, model `gpt-5.5`
- Provider identity: `openai`
- Role skill: `agents/skills/reality-checker.md`
- Implementer: `claude_glm` / `glm-5.2`, provider identity `zhipu_glm`
- Fix authors: none
- Reviewer prior involvement: `design`
- Override evidence:
  `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/review-2-unrelated-reviewer-unavailable.md`
- Fallback reason:
  `design_conflict_ineligibility_no_unrelated_registered_decision_model`

This must be a fresh provider-isolated read-only session. OpenAI participated
in the inherited stage design but did not write implementation or fix code.
Disclose this prior involvement in the narrative and strict verdict. Review the
stage design and development breakdown as evidence under review, not as the
highest authority. The user-approved direction synthesis, product PRD, and
product/architecture documents are the higher requirements authority.

Do not edit or create files, commit, merge, rebase, push, start a server, use
network access, call Binance, or invoke another model. Treat implementation
reports, comments, test claims, and review-1 conclusions as untrusted claims to
verify independently.

## Exact Review Binding

- Stage base SHA:
  `8aac137a46d228f2d68b2036a15575eda0e235a3`
- Reviewed implementation/evidence head SHA:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83`
- Authoritative diff fingerprint:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`

Later bookkeeping commits may exist. Review only the fixed committed range and
use the authoritative fingerprint above in the verdict. Run this exact raw diff
command:

```bash
git diff --binary 8aac137a46d228f2d68b2036a15575eda0e235a3..60c91f7b32ab0f0a51f719a094915adfbec87c83 -- . ':(exclude)reports/agent-runs/2026-07-cache-refresh-scheduler-v2/status.json'
```

An independent human-approved one-line operational baseline correction exists
on `main` at `413aa94c74e356d2a99595f11cc0b91b8448fece`: `.env.example` was aligned
from `3600` to `1800`. It is intentionally outside the stage fingerprint and
did not claim review-1 coverage. Verify it read-only with:

```bash
git show --format=fuller --stat 413aa94c74e356d2a99595f11cc0b91b8448fece
git show 413aa94c74e356d2a99595f11cc0b91b8448fece -- .env.example
```

The current stage checkout still contains the base-branch copy of
`.env.example`; the later merge must preserve main's `1800` correction. Judge
the final deliverable as the fixed stage diff plus this already-landed main
baseline correction. Do not substitute commit `413aa94` for the required stage
fingerprint in the strict verdict.

## Requirements Authority And Required Raw Inputs

Read these directly. Do not read another stage or any `history/` directory.

Higher requirements authority:

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` review-2 section
3. `docs/product/PRD.md`
4. `docs/architecture/ARCHITECTURE.md`
5. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/06-direction-synthesis.md`

Evidence under review:

6. `agents/skills/reality-checker.md`
7. `schemas/review-verdict.schema.json`
8. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md`
9. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md`
10. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md`
11. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md`
12. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/13-manual-delivery-amendment.md`
13. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`
14. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/30-review-1.md`
15. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/40-fix-report.md`
16. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/60-test-output.txt`
17. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/status.json`
18. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/review-2-unrelated-reviewer-unavailable.md`
19. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/14-main-env-example-amendment.md`
20. main baseline commit `413aa94c74e356d2a99595f11cc0b91b8448fece`
21. the exact committed diff and every relevant source/test file in it.

## Independent Final-Gate Review Focus

Review the complete diff for requirement fidelity, correctness, regressions,
security, maintainability, request pressure, cache freshness semantics, and
missing tests. Independently verify at least:

1. Group A approximately 60 seconds, Group B fixed 1800 seconds, and Group C
   at-most-10 homepage-symbol sweep are independent per source/component.
2. Every newly governed successful business-cache write uses fetch completion
   time; failures and `None` do not advance it. At age `>=1800s`, slow private
   transport cannot remain fresh and masquerade as a real refresh.
3. Scheduled assembly performs no hidden network work, never calls the all-row
   `fetch_cost_leg_chain`, and does not restore a global top-50 probe.
4. Scheduled borrow work uses the exact strict predicate
   `daily_funding_rate < -0.00030000`, `MARGIN_SPOT_CANDIDATE`,
   `asset_tag in {CRYPTO, METAL}`, and usable private channel.
5. Coverage attempt semantics handle failure, universe exit/re-entry,
   cursor-only fresh-component passes, and `rate_limit_budget` iff `skipped > 0`.
6. History, borrow-rate, and max-borrowable freshness remain independent;
   batching, unpacking, and asset deduplication are correct.
7. `next_hourly` is stored raw and normalized by `×24` exactly once;
   `interestRateHistory` is selected-asset fallback-only.
8. Manual click behavior, deadline/publication gates, offline behavior, public
   wire schema, private account panels, and legacy seams do not regress.
9. The 330-test evidence covers the frozen edge cases and is not tautological.
10. Review-1's P3 at `backend/services/snapshot_service.py:841` is inherited and
    truly non-blocking, or else raise it at the severity supported by impact.
11. Independently judge the disclosed Group A configurable TTL divergence
    (`cache_ttl_seconds` versus `private_channel_fast_ttl_seconds`).
12. The strong-reviewer disclosure is truthful and provider isolation from all
    delivery-code authors is preserved.

Do not accept merely because review-1 accepted. Do not reject merely because a
non-blocking cleanup is possible. A valid Codex verdict is final for this gate;
do not request a Claude second opinion.

## Verdict Contract

Respond primarily in Chinese with a concise evidence-based narrative. End the
entire response with exactly one JSON object, without a Markdown fence or text
after it, matching `schemas/review-verdict.schema.json`.

Required JSON literals:

- `schema_version`: `1`
- `stage_id`: `2026-07-cache-refresh-scheduler-v2`
- `role`: `final_reviewer`
- `model`: `gpt-5.5`
- `diff_fingerprint`:
  `60c91f7b32ab0f0a51f719a094915adfbec87c83:f970f6be1afa92b55b3ef79f1135753647fa9d8693b5e83fa80aa6a27bdfbfb0`
- `reviewer_prior_involvement`: `design`
- `reviewer_prior_involvement_notes`: disclose inherited design involvement,
  no implementation/fix authorship, the evidence path, and fallback reason.

Order findings by severity and include exact file/line evidence, impact, and
recommendation. Do not return `ACCEPT` if a required correction remains. For an
`ACCEPT` verdict, use `next_action: "stage_accepted_waiting_user"`; this does not
authorize merge to `main`.

If verdict is `REWORK`, include a ready-to-send `fix_start_prompt` in the
narrative and verbatim in JSON. It must include the stage/fingerprint, raw review
evidence path
`reports/agent-runs/2026-07-cache-refresh-scheduler-v2/50-review-2.md`, ordered
findings, required fixes, the original seven-file product/test boundary narrowed
to only necessary files, forbidden paths/side effects, these exact checks:

```bash
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/config.py backend/adapters/binance_public.py backend/services/private_client.py backend/services/snapshot_service.py
git diff --check
git status --short
```

and a required finding-to-fix mapping in `40-fix-report.md`.

Place this footer immediately before the final JSON object:

```text
本地北京时间: <obtain from local date command> CST
下一步模型: <human-or-claude_glm>
下一步任务: <specific action>
```
