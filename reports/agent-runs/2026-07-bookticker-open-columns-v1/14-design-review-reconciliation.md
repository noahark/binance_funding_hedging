# Design Review Reconciliation

## Inputs

- Claude development breakdown and design review:
  `12-development-breakdown.md`
  - Provider/model: Anthropic Claude / `opus4.8`
  - Verdict: `READY`
  - Findings: P0 none, P1 none, seven P2 implementation constraints
- Grok advisory raw transcript:
  `13-design-review-grok.raw.md`
  - Provider/model: xAI Grok / `grok-build`
  - Verdict: `REVISE`
  - Findings: three P1 and five P2

Grok remains advisory evidence and does not replace formal review-1/review-2.
The raw export is preserved without rewriting; this file records only the
bookkeeper disposition and design amendments.

## Claude Disposition

Claude's seven P2 constraints are accepted as implementation requirements:

1. Decimal expression order and final-only HALF_UP quantize.
2. Capability-check the new pair seam for legacy stubs.
3. Inject opening-quote states in `frontend/self-check.js` rather than changing
   the forbidden backend fixture.
4. Reconcile every numeric frontend column index after the 12-column layout
   change.
5. Treat `fresh` as usable-window state and expose `updated_at`/age guidance.
6. Let symbol-snapshot inherit the shared row schema; do not edit its schema.
7. Treat zero books as incomplete and never use them as denominators.

These constraints are already detailed in `12-development-breakdown.md` and
remain binding for Task A and Task B.

## Grok Finding Disposition

### P1 — Percentage unit formatter

Accepted. `00-task.md` and `10-design.md` now prohibit reusing
`formatFundingRate` for `*_spread_pct`. Task B must use an independent formatter
and lock `-0.04 -> -0.04%` plus `0.00 -> 0.00%` in self-check.

### P1 — Stale must be recomputed during every assembly

Accepted. `10-design.md` now defines monotonic `pair_age`, `usable`, and `stale`
projection on every assembly. The test must cross `119.9 -> 120.0` after one
success without injecting another failed fetch.

### P1 — Incomplete direction independence

Accepted. `10-design.md` now includes the minimum truth table for forward-only,
reverse-only, all-four, missing/zero leg, and never-succeeded states.

### P2 — UI age wording

Accepted. The UI guidance now says the source refreshes about every 60 seconds,
may retain last-good for at most about two cycles (120 seconds by default), and
is not an execution guarantee.

### P2 — Discovery double-source sketch conflict

Accepted. `10-design.md` explicitly supersedes the early discovery sketch;
`book_ticker_pair` is the only locally publishable source.

### P2 — JSON number coercion

Accepted. Adapter normalization accepts price values only when the raw JSON
value is a string. `str(number)` coercion is forbidden and requires a negative
test.

### P2 — Human-readable contract boundary

Accepted. `docs/api/public-market-contract.md` is added to Task A's allowed
files for the additive `opening_quotes` contract.

### P2 — `updated_at` on usable incomplete rows

Accepted. `fresh` and `incomplete` retain the pair completion time;
`unavailable` alone has null time, while `stale` retains last success time but
publishes no usable prices/spreads.

## Decision

All Grok P1/P2 findings are resolved by bounded design clarification. No finding
requires changing the user-frozen formulas, 60-second due cadence, 120-second
hard usability cutoff, public/private boundary, read-only product boundary, or
owner routing. The stage may proceed to Task A dispatch after status/handoff and
the implementation prompt are prepared.

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md
本地北京时间: 2026-07-15 17:29:32 CST
下一步模型: codex_bookkeeper
下一步任务: 更新 stage 状态并准备 Task A claude_glm implementation dispatch packet
