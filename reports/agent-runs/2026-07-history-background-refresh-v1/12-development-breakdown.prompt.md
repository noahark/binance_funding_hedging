# Claude Opus 4.8 Development Breakdown Start Prompt

You are the development-breakdown author for stage
`2026-07-history-background-refresh-v1`.

The human operator explicitly selected **Anthropic Claude Opus 4.8** for this
breakdown, overriding the workflow's normal Fable5-first preference for this
single node.

## Role And Skill Activation

Before doing substantive work, read these files completely:

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml`
3. `agents/registry.yaml`
4. `agents/skills/task-planner.md`
5. `reports/agent-runs/2026-07-history-background-refresh-v1/status.json`
6. `reports/agent-runs/2026-07-history-background-refresh-v1/70-handoff.md`
7. `reports/agent-runs/2026-07-history-background-refresh-v1/00-intake.md`
8. `reports/agent-runs/2026-07-history-background-refresh-v1/00-task.md`
9. `reports/agent-runs/2026-07-history-background-refresh-v1/10-design.md`
10. `reports/agent-runs/2026-07-history-background-refresh-v1/11-adr.md`
11. `docs/product/PRD.md`
12. `docs/architecture/ARCHITECTURE.md` when present

Activate and declare:

```text
Skill applied: task_planner (read_write_docs)
已应用技能: 任务规划者（读写文档模式）
```

## Authority And Current Design

The current worktree versions of `00-intake.md`, `00-task.md`, `10-design.md`,
and `11-adr.md` are the active requirements. They supersede the earlier committed
drafts at `010ec85` and `efffe78`. Do not revive old alternatives unless the
current design explicitly retains them.

The design has completed two independent software-architect reviews:

- Grok 4.5 session `019f56b9-214f-7ce1-ab71-705954fd21d4`:
  `ACCEPT_WITH_AMENDMENTS`
- Claude Opus 4.8 session `215b0aa9-4d63-48f6-9b3d-2a9f6cc83b48`:
  `ACCEPT_WITH_AMENDMENTS`

Those amendments are already applied to the current worktree. Re-read the
current artifacts; do not rely on prior session memory or summaries.

## Scope Of This Task

Create exactly:

```text
reports/agent-runs/2026-07-history-background-refresh-v1/12-development-breakdown.md
```

Do not modify:

- `00-intake.md`, `00-task.md`, `10-design.md`, or `11-adr.md`
- `status.json` or `70-handoff.md` (the bookkeeper is the single writer)
- source code, tests, schemas, samples, canonical docs, Harness files, or Git
- any implementation/review/fix report

Do not commit, push, merge, rebase, run another model, or execute implementation.

## Required Breakdown Content

Produce an implementation-ready MEDIUM-stage breakdown that a bounded
implementer can execute without making product or architecture decisions.

At minimum include:

### 1. Frozen Product Semantics

- Full snapshot endpoint is a pure read of canonical `PublishedState`.
- Default prewarm is the valid-rate subset:
  `route_class != PERP_ONLY_EXCLUDED` and
  `abs(daily_funding_rate) > 0.00030000`.
- Null/invalid-rate rows may remain visible but are intentionally not prewarmed;
  they retain one-shot click refresh.
- A click is one `RefreshSymbolCommand`, not a subscription, watched set,
  priority record, or separate interest TTL.
- Click refreshes selected-symbol public fields, complete 30-day history,
  selected-base-asset actual rate, and selected-base-asset max-borrowable.
- Click never fetches balances, positions, account valuation, unrelated assets,
  or a full-universe public snapshot.
- Backend publishes the complete canonical state; click response contains only
  one row projection from that same `published_version`.
- Frontend patches only the row/drawer, applies a one-second non-clickable guard,
  ignores activation while in flight, and relies on <=60s full poll for global
  ordering/summary reconciliation.

### 2. Ownership And Task Shape

Determine and justify the smallest owner split under `AGENTS.md` dominance rules.
The expected default is one backend-dominant bounded implementation owned by
`claude_glm`, including light `frontend/index.html` / `frontend/self-check.js`
integration, with Kimi as review-1. If you recommend a different split, cite the
specific workload evidence and dependency boundary.

Parallel mode and auto-review mode are both disabled. Do not add R1-R10 parallel
machinery.

### 3. Exact Allowed And Forbidden Files

Narrow the preliminary boundaries in `00-task.md`. For every allowed production,
test, schema, and sample path, state why it is needed. Explicitly forbid trading
execution, canonical docs, Harness files, credentials, balances/positions/
valuation evidence, unrelated UI, and unrelated account behavior.

### 4. Data And Concurrency Model

Specify concrete data structures and ownership for:

- `PublishedState` fields and monotonic `published_version`
- worker-owned base state
- worker-owned per-symbol history state
- worker-owned selected-asset borrow state
- one serial worker lifecycle
- scheduled 30s tick and 60s base cadence
- deterministic <=10 history sweep/cursor
- command queue, completion signal, bounded in-flight coalescing
- no request-thread cache mutation
- atomic full-state publication and last-good retention

Avoid a generic scheduler, thread pool, watched set, priority queue/ledger,
business-wide lock, disk persistence, or delta merge.

### 5. Bootstrap And Timeout Contract

Freeze the design defaults:

- construction starts no worker;
- explicit start/stop lifecycle;
- offline and disabled kill switch start no worker;
- worker performs immediate no-sleep base publication;
- before that publication, snapshot/symbol reads return brief 503;
- no request waits for deep-history sweep;
- symbol refresh timeout is configurable, default 30s;
- timeout never replaces last published state.

### 6. Public Adapter Contract

Specify the exact per-symbol public calls/helpers required for click refresh.
Click must use a per-symbol premium-index path plus complete 30-day history and
reuse current worker-owned exchange/spot/funding-interval metadata. It must not
invoke full `fetch_raw()` solely for one row.

State request parameters, time-window boundary, error degradation, cache update,
and exact tests/mocks. If a contract assertion depends on current Binance public
behavior, require a raw public sample under:

```text
reports/api-samples/2026-07-history-background-refresh-v1/
```

### 7. Private Force-TTL Contract

Design the smallest `PrivateClient` API that supports one-shot exact-key bypass:

- force selected asset's maxBorrowable cache entry once;
- force selected asset's actual-rate entry/batch once;
- reuse valid classic/VIP/account-tier/shared references;
- never clear the full private cache;
- never call balance/position/account-valuation methods from click refresh;
- reuse the last published account panel and non-selected rows' borrow fields;
- retain single HMAC exit, exact GET whitelist, sanitized audit, rate-limit
  backoff, timeout, and last-good degradation.

Define the cache/coalescing key (`symbol` vs base asset) and justify it. Require
sanitized signed-call evidence without credentials, signatures, full query,
headers, balances, or positions.

### 8. Compatibility Endpoint

The existing funding-history endpoint must become a pure projection from
`PublishedState`. It must perform zero upstream fetches and zero cache writes.
Specify its available/empty/unavailable compatibility semantics and tests so it
cannot become a second cache producer.

### 9. New Row-Snapshot Contract

Specify the proposed route and complete response shape for
`public-market-symbol-snapshot/v1`, including:

- schema version
- symbol
- `published_version`
- data/generated time
- warnings/failure metadata
- exactly one row
- no full `rows` array

Define invalid/ineligible/timeout/upstream-degraded HTTP semantics. The row and
canonical full snapshot must be provably from the same publication.

Because this is a contract amendment, require raw public samples plus sanitized
signed evidence before formal review.

### 10. Failure Matrix

Turn the truth table in `10-design.md` into exact implementation and test rules:

- public/history/borrow all succeed;
- history succeeds, borrow fails;
- borrow succeeds, history fails;
- public refresh fails with eligible last-good base;
- no eligible last-good row;
- all selected sources fail;
- command timeout;
- rate limit/auth/service failure.

Distinguish schema-complete publication with per-source last-good fallback from
publishing a half-assembled object.

### 11. Frontend Integration

Specify exact state and DOM changes for:

- every row click invokes the symbol-snapshot endpoint, including preloaded rows;
- one-second non-clickable guard against accidental double-click;
- ignore activation while request is in flight;
- stale response identity/request-id guard;
- replace only selected row in frontend state;
- patch only that DOM row and drawer;
- apply selected-row visibility changes locally;
- no click-time full snapshot fetch or full-table render;
- accept <=60s temporary global ordering/summary staleness;
- later deliberate click after completion creates a new command.

### 12. Exact Tests And Evidence

List exact commands after inspecting the repository. Include at least backend
pytest, frontend self-check, schema validation, HMAC/security grep tests, stage
validator, and any focused new test commands. Map every acceptance criterion to
one test/evidence artifact. Include selected-set-size and
`ceil(N/10)*30s < 1800s` observation/limitation.

### 13. Risk And Review Focus

Call out the highest-risk implementation seams:

- accidental second cache writer
- click path re-entering full account panels
- over-broad private cache invalidation
- click-time full `fetch_raw()`
- row/full version mismatch
- partial failure erasing last-good data
- thread lifecycle/test nondeterminism
- full-table frontend rerender regression
- raw/signed evidence leakage

### 14. Implementation Dispatch Readiness

End with a checklist stating whether the breakdown is implementation-ready and
list any remaining human decision. Do not silently invent product decisions. If
the active design contains a true conflict that prevents a safe breakdown, stop
with `BLOCKED` and cite exact file/line evidence; otherwise resolve implementation
detail within the frozen design.

## Output Rules

- Write developer-ready tasks with exact files, dependencies, forbidden paths,
  contracts, test commands, evidence, risks, and acceptance criteria.
- Keep tasks realistically bounded and avoid speculative abstractions.
- Record author identity:
  - provider: Anthropic
  - model: Opus 4.8
  - skill: `task_planner`
  - mode: `read_write_docs`
- This is design involvement and must be disclosed for review-2 routing.
- Use Chinese as the primary operator-facing language. When English prose or a
  technical term is necessary, include concise Chinese translation/explanation
  on first use. Preserve exact identifiers, paths, commands, JSON, and code.
- End the document with a local Beijing-time footer generated from `date`:

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Codex bookkeeper
下一步任务: 验收 12-development-breakdown.md，更新 status/handoff，并准备 claude_glm 实现分发包
```

Do not merely answer in chat. Create the required
`12-development-breakdown.md` file, then report the path and a concise summary.
