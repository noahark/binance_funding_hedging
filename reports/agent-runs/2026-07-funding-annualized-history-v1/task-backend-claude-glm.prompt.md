# PASTE BODY: Task A Backend Contract And Settled-History Enrichment

You are the executor in an existing interactive Claude-GLM session. Perform
the work in this repository. Do not start another model terminal, do not return
a `-p` launch command, and do not delegate the task. Do not commit; the
bookkeeper owns commits and stage state.

Read `AGENTS.md` and these stage artifacts first:

- `reports/agent-runs/2026-07-funding-annualized-history-v1/00-task.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/10-design.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/11-adr.md`
- `reports/agent-runs/2026-07-funding-annualized-history-v1/12-development-breakdown.md`
- `reports/follow-ups/2026-07-funding-annualized-history-drawer.md`

Implement Task A only. You own the public adapter, configuration, snapshot
service/domain math, schema, backend tests, and raw public evidence. The three
new row fields are additive decimal-string-or-null schema properties. Do not
add them to the row schema's `required` array: frozen v0.1 snapshots must remain
valid. Instead, prove that every current service output row emits all three
keys:

- `annualized_funding_24h`
- `annualized_funding_7d`
- `annualized_funding_30d`

Freeze these behaviors:

1. Use Decimal-only value paths and fixed eight-place decimal strings. 24h is
   `daily_funding_rate * 365`; it remains estimate-derived.
2. 7D/30D use only settled `funding_history` entries in inclusive calendar
   windows ending at the snapshot premium-index time. Sum the period rates and
   multiply by `365 / N`; do not use average interval, observed-span
   denominators, or `lastFundingRate`. Empty window means `null`.
3. For top-N symbols only, request `/fapi/v1/fundingRate` with `symbol`,
   `startTime=t_end-30d`, `endTime=t_end`, and `limit=1000`. Preserve a
   dedicated per-symbol successful-result cache through
   `Config.funding_history_cache_ttl_seconds`, default 1,800 seconds and
   configured by `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`, without changing the
   existing 60-second whole-snapshot cache. Return history newest first.
4. An individual history request failure must yield empty history, null 7D/30D,
   and warning `funding_history_unavailable:<symbol>` without failing the full
   snapshot. Do not cache failed requests.
5. Capture an authentic multi-week public raw response under
   `reports/api-samples/2026-07-funding-annualized-history-v1/`. Do not claim a
   synthetic fixture is raw evidence. If authentic evidence cannot be captured,
   finish the code/tests but record the evidence blocker honestly.

Allowed files are the Task A list in `00-task.md`; do not edit outside it.
In particular, do not change canonical docs, frontend files, frozen contract-v2
samples, route/version/sort behavior, private-channel behavior, or stage
`status.json`/`70-handoff.md`.

Add focused deterministic coverage in the new
`backend/tests/test_funding_history.py` and
`backend/tests/fixtures/funding-history/**`: 24h/7D/30D vectors, negative and
empty windows, inclusive boundaries, mixed 1h/4h timestamps, eight-place
serialization, newest-first ordering, exact request parameters, top-N cap,
cache TTL, per-symbol degradation, optional-schema compatibility for a legacy
row, and always-present current-service fields. Update
`backend/tests/test_config.py` for the TTL default/override/invalid input and
`backend/tests/test_snapshot.py` only where the output shape needs adjustment.

Run:

```bash
python3 -m pytest backend/tests -q
python3 -m json.tool schemas/api/public-market/snapshot.schema.json >/dev/null
git diff --check
```

Write `20-implementation-backend.md` with changed files, test output summary,
raw-evidence path, and any blocker. End your report with the required local
timestamp footer. Do not report completion until the specified tests pass or a
specific blocker is recorded.
