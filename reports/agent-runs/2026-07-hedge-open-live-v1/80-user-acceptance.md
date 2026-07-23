# User Acceptance / Release Decision — Hedge Open Live v1 (Round 1)

## Decision
The user (repo owner) **accepts round 1** and **authorizes a no-fast-forward
merge to LOCAL main (not pushed)**.

- User statement (2026-07-23): "开始执行吧" (accept + authorize merge).
- This follows the full review discipline — NOT a waiver:
  - review-1 cross-review both ACCEPT: hedge-fe (Claude-GLM), hedge-be (Kimi,
    round-2 after fix-1).
  - **review-2 final ACCEPT** (Codex/GPT, unrelated reviewer, round-2 after
    fix-2 + fix-3), 0 findings.
  - `scripts/validate-stage.py --phase pre-accept` → PASS (the review-1 fingerprint
    trail is covered by the top-level review-2 at head 02bcc24; no
    authorized_exception was needed).

## Accepted content
- Stage branch: `stage/2026-07-hedge-open-live-v1`
- Base SHA: `6639b0025682f406f9a726104ef8d3b9e6f8fadd`
- Accepted product head: `02bcc24abe134dcdb0541af462cea765ffc5cbdf`
- diff_fingerprint:
  `02bcc24abe134dcdb0541af462cea765ffc5cbdf:1b771bc938a907d3cd024421dc35d070f821f57a312296ae9b88dee7d2c95bbf`
- Round-1 scope: immediate open only (1 fill/sec, no websocket), **dry-run record
  transport — no real Binance order in any path**. New backend `hedge_open_tasks`
  module + API; frontend wired to the real API. Backend 790 passed, frontend
  self-check 108.

## This is a dry-run SKELETON acceptance — explicitly NOT accepting the order model
The following are **deferred to the next real-API round** and are NOT validated
by this acceptance (recorded so the next session does not treat them as done):
- **DI-6 order-parameter model rebuild**: spot market BUY must use `quoteOrderQty`
  (total USDT); contract buy/sell + spot sell use `quantity`. The current
  DI-4/ADR-2 model ("both legs `quantity=q_common` + common grid + qty equality")
  is **wrong for forward opens** (legs' units differ). The dry-run record
  transport currently records incorrect forward-leg params, but performs no real
  POST, so no harm yet. Must be redesigned per direction (spot buy =
  `quoteOrderQty` from amount×price; others = `quantity`) with the amount→notional
  conversion and frontend input semantics.
- Real preflight (exchangeInfo/balance/positionSide/rateLimit) + real live
  executor (`APP_HEDGE_EXECUTOR=live`), and the user's margin / open-amount /
  count risk controls (user: "直接上真实 api,通过保证金和开单金额和次数控制风险").
- Smooth-open websocket basis gate (DI-1), dry-run demo preflight provider,
  review follow-ups F-003..F-006, and a representation for both-filled-but-
  quantity-mismatched exposure (both_mismatched_contract_gap).
- Symbol-matching 1000x-prefix work (separate item, docs/symbol-mismatch-analysis.md).

## Authorized / not authorized
- **Authorized:** accept round 1; no-ff merge of the stage branch into LOCAL
  `main`.
- **NOT authorized (still needs explicit later user action):** `git push`; any
  real Binance order/websocket/credential; enabling `APP_HEDGE_EXECUTOR=live` +
  the global Start gate + creating the first real hedge task. Nothing real is
  live.

当前 Session ID: unavailable (Claude Code runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/80-user-acceptance.md
本地北京时间: 2026-07-23 10:12:22 CST
下一步模型: bookkeeper (self) — merge to local main, then next stage = real-API round
下一步任务: record acceptance, no-ff merge to local main (no push), update ACTIVE/handoff/memory for a fresh session
