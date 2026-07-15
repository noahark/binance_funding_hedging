# Claude-GLM Implementation Prompt

You are the implementation author for stage
`2026-07-cache-refresh-scheduler-v2` on branch
`stage/2026-07-cache-refresh-scheduler-v2`.

## Read Set

Read only these project instructions and active inputs before coding:

1. `AGENTS.md`, implementation rules only;
2. `agents/developer-discipline.md`;
3. `agents/skills/senior-developer.md`;
4. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md`;
5. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md`;
6. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md`;
7. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md`;
8. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/13-manual-delivery-amendment.md`;
9. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/status.json`;
10. the seven allowed source/test files below and directly imported code needed
    to understand them.

Do not scan `reports/agent-runs/`, do not read any `history/` directory or any
other stage, and do not use prior Claude memory or another Session. The v1
auto-review passages in `12-development-breakdown.md` are superseded by
`13-manual-delivery-amendment.md`.

## Task

Implement the approved three-cadence cache refresh scheduler exactly as frozen
in the task, design, ADR, and breakdown:

- Group A fast sources: 60 seconds;
- Group B shared/unified sources: fixed 1800 seconds;
- Group C: every 30 seconds inspect at most 10 homepage symbols, with history,
  borrow rate, and max-borrowable freshness tracked independently;
- slow private transport TTL default/effective maximum: 1800 seconds;
- scheduled borrow universe uses strict
  `daily_funding_rate < -0.00030000`, `MARGIN_SPOT_CANDIDATE`, and
  `asset_tag in {CRYPTO, METAL}`;
- no scheduled global top-50 cap;
- scheduled Group C uses only the narrow next-hourly, selected-asset fallback,
  and max-borrowable seams; do not reuse `fetch_cost_leg_chain` there;
- preserve wire schemas, frontend behavior, manual click refresh, single-writer
  publication, and current failure/empty-response semantics.

## Allowed Writes

- `backend/config.py`
- `backend/adapters/binance_public.py`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_config.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_private_client.py`
- `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`

Do not edit any other file. In particular, do not edit or create files under
`frontend/**`, `schemas/**`, `docs/**`, Harness files, `status.json`,
`70-handoff.md`, `30-review-1.md`, `40-fix-report.md`, or `50-review-2.md`.
Do not commit, merge, rebase, push, start a server, use background processes,
or make live Binance/network calls.

If implementation genuinely requires `backend/domain/snapshot.py`, another
backend file, or a new file, stop before editing it and report the exact reason
and proposed minimal expansion in `20-implementation.md`.

## Execution Discipline

Before editing, inspect the current code and write a short implementation plan
in your response. Then implement the minimum change. Do not refactor unrelated
code. Maintain current naming and error semantics.

Run focused tests while iterating:

```text
python3 -m pytest backend/tests/test_config.py
python3 -m pytest backend/tests/test_background_worker.py
python3 -m pytest backend/tests/test_private_client.py
```

Then run the final blocking command:

```text
python3 -m pytest backend/tests
```

Update `20-implementation.md` with the exact diff summary, design decisions,
commands/results, remaining work, and boundary confirmations. Do not claim
success if tests fail or no delivery-code diff exists. Finish by telling the
human that implementation is ready for the bookkeeper to inspect; do not launch
review or another model.
