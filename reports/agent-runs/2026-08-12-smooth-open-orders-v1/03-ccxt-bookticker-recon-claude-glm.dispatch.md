Identity:
- task_id: ccxt-bookticker-recon-claude-glm
- target_role: Implementer
- target_model: claude-glm
- provider: zhipu_glm
- status_revision: 4
- required_skill: agents/skills/senior-developer.md

Goal

Run a bounded, read-only reconnaissance and executable public-market proof for
the exact CCXT/CCXT Pro capabilities needed by the frozen smooth-open design.
Determine whether one spot watcher and one USDⓈ-M perpetual watcher based on
`watchBidsAsks` can be the V1 `BestBidAskProvider`, and leave evidence precise
enough for the later integration plan. This task does not integrate CCXT into
the product and does not touch any private, account, or order capability.

Allowed Files

- docs/planning/ccxt-bookticker-recon-2026-08-13.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md (create-only; preflight `test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md` returned 0 before dispatch)

Inputs

- AGENTS.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/03-ccxt-bookticker-recon-claude-glm.dispatch.md
- reports/agent-runs/ACTIVE.json
- PROJECT_STATE.md
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json
- agents/roles.md (Implementer section and Task Handoff Evidence Contract)
- agents/developer-discipline.md
- agents/skills/senior-developer.md
- docs/planning/smooth-open-orders-v1.md (especially D1-D2, D7-D8, sections 4-6, 11, and Human 2026-08-13 in section 12)
- reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md
- reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md
- backend/adapters/binance_public.py
- backend/hedge_open_tasks/scheduler.py
- backend/hedge_open_tasks/service.py

Authorized External Scope

- Human explicitly authorized this CCXT public-market reconnaissance.
- You may read current official CCXT documentation/source/PyPI metadata and
  official exchange public-market documentation.
- You may create an isolated temporary virtual environment outside the repo,
  install the selected exact `ccxt` package version there, and connect without
  credentials to public spot, USDⓈ-M, and one secondary exchange market-data
  endpoint when needed for the proof.
- Do not inspect or load `.env`, shell credential variables, browser sessions,
  key files, or application credentials. Do not connect private/user streams or
  call order, account, balance, position, borrow, repay, transfer, or signed
  endpoints. Do not install into the repository/production virtual environment,
  start this service, deploy, push, or alter live gates.

Acceptance Checks

- pass: record the exact tested Python version, package name/version, import
  form, installation command, license, relevant installed dependencies, and
  authoritative links/commit or release identifiers. State whether CCXT Pro is
  included in the tested `ccxt` package and whether a paid/separate package is
  required for this use.
- pass: prove from the tested runtime—not documentation alone—the appropriate
  spot and USDⓈ-M client classes/options, unified symbol(s), and
  `exchange.has['watchBidsAsks']` values. Show whether `watchBidsAsks([symbol])`
  is genuinely supported on both and identify the underlying Binance channel
  from tested output/source evidence.
- pass: the isolated proof concurrently receives multiple public updates for
  one ordinary spot/perpetual pair through two independently owned asyncio
  watcher tasks. Capture normalized bid/ask/bidVolume/askVolume, local receive
  monotonic/wall time, exchange timestamp when present, and a minimal raw-info
  field summary without recording secrets or an excessive market dump.
- pass: demonstrate that delayed consumption/cancellation/failure of one
  watcher does not stop the other watcher from receiving subsequent updates;
  distinguish what the executable proof establishes from what is only inferred
  from CCXT source. Do not invent a production manager or recovery framework.
- pass: compare normalized quantities with Binance raw `B`/`A` (or the current
  official raw equivalents), inspect `market.contractSize`, and give an
  evidence-backed rule for when spot/perpetual top-level quantities are in the
  same base-asset unit as the design's `q_common`. Explicitly cover the ordinary
  linear contract used in the proof, non-1/unknown `contractSize`, and why the
  existing 1000x-symbol block remains necessary. If equality/units cannot be
  proven, return that limitation rather than assuming it.
- pass: document actual cancellation and `close()` behavior and the relevant
  exception/reconnect contract of the tested version. State the smallest
  integration consequence for the planned single event-loop thread and two
  independent watcher owners, including what must be fail-closed; do not write
  production integration code.
- pass: inspect one plausible secondary exchange adapter only far enough to
  show which unified capability checks, market type/symbol/contract metadata,
  and per-exchange proof would be required later. Do not claim that Binance
  proof alone proves another exchange works and do not broaden into a generic
  exchange framework.
- pass: compare CCXT findings with the existing native Binance bookTicker
  reconnaissance, list each confirmed match, contradiction, and unresolved
  item, then conclude one of: `continue-with-ccxt`, `use-native-binance-fallback`,
  or `blocked-pending-evidence`, with concrete reasons and reopen conditions.
- pass: the Chinese report separates observed runtime facts, authoritative
  source facts, and design recommendations. It names the exact minimum fields
  the later adapter must preserve and flags any CCXT normalization that could
  change precision, units, timestamps, or freshness semantics.
- pass: the proof script is public/read-only, deterministic in bounds (explicit
  overall timeout and finite samples), closes every client in `finally`, and
  contains no keys, signed calls, private endpoints, product imports, daemon,
  service integration, dependency-file edit, or order-related API call. Save
  the exact command and raw output; `python -m py_compile` and `git diff --check`
  pass.
- pass: create the deterministic handoff required by the Task Handoff Evidence
  Contract, mark only this task `reported` in status revision 4, and make one
  delivery commit containing only Allowed Files; do not push.

Stop

Stop after the public proof, Chinese reconnaissance report, raw evidence,
handoff, reported status, and one local delivery commit. Do not modify the
frozen smooth-open design, frontend/backend production code, schemas, API
contracts, dependency manifests, services, credentials, or live data. Do not
implement the provider, watcher manager, gate, executor, or review another
model. If public network/package access or a required runtime fact cannot be
obtained, record exact attempts and return blocked rather than replacing proof
with speculation.
