# Decisions

Status: draft

This file records approved product, business, financial, and technical decisions.

Draft decisions belong in `reports/agent-runs/<stage-id>/` until user approval.

## Decision Log

| ID | Date | Decision | Owner | Source |
|---|---|---|---|---|
| DEC-2026-07-03-001 | 2026-07-03 | Archive the Grok public-market implementation and restart Phase 1 from the approved PRD with a contract-first split: Claude-GLM owns backend Binance public API contract discovery and backend implementation; Kimi owns frontend UI and integration against the frozen backend contract; Grok is excluded from core backend and contract work for this phase. | User / Codex | `reports/archives/2026-07-03-grok-public-market-discovery/`, `reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md` |
| DEC-2026-07-05-001 | 2026-07-05 | Adopt stage-branch mode: from the next stage onward, the bookkeeper creates `stage/<stage-id>` at H_intake, all stage commits and fingerprints anchor to the branch, and the branch merges back to main only after user acceptance; Harness/template syncs stay on main. Execution deferred until the in-flight stage `2026-07-phase2-borrow-sort-v1` completes (its fingerprints are bound to main commits). The rule change lands template-first (ai_project_harness) with GPT review, then syncs down. | User / Fable5 | `docs/planning/stage-branch-mode.md` |
