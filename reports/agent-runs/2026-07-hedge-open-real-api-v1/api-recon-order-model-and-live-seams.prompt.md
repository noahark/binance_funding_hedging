# PAPI Hedge-Open Real API Recon — Human-Executed Research Packet

You are an independent **read-only API researcher**. Do not edit source code,
access credentials or environment files, submit any Binance order, connect to a
private user stream, or invoke another model/adapter. A human operator executes
this packet and archives your raw answer unchanged.

## Objective

Establish the exact facts needed for a Portfolio Margin immediate hedge open:

- forward: PAPI margin MARKET BUY + PAPI UM MARKET SELL;
- reverse: PAPI margin MARKET SELL + PAPI UM MARKET BUY;
- real POST adapter will be implemented later, but no order is authorized in
  this research;
- smooth WebSocket mode is out of this stage;
- no product numeric caps, but Binance filters/balances/account state, rate
  limits, Start gate, and idempotent reconciliation are mandatory.

Read first:

- `llms-full.txt` (primary supplied Binance corpus);
- `reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md`;
- `reports/agent-runs/2026-07-hedge-open-live-v1/design-inputs.md` §DI-6;
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-intake.md,01-design-discussion.md}`.

Use current official Binance docs and official SDK/OpenAPI only to resolve a
conflict. Label every statement as supplied-doc fact, official-current-doc fact,
official-SDK/OpenAPI fact, public read-only sample, inference, or open item.

## Required Findings

1. Produce an exact `type=MARKET` parameter matrix for PAPI margin BUY/SELL and
   PAPI UM BUY/SELL: `quantity` vs `quoteOrderQty`, both-at-once behaviour,
   symbol-level capability field, units/precision, `newOrderRespType=RESULT`,
   and PAPI-specific `sideEffectType` values. Resolve—not assume—the conflict:
   generic spot docs say `quantity` or `quoteOrderQty`; the user reports PAPI
   margin BUY must use total-USDT `quoteOrderQty`.
2. Capture/document a public spot and UM exchange-info sample for one USDT
   symbol. Specify per-leg validation and serialization for `MARKET_LOT_SIZE`,
   `LOT_SIZE`, `NOTIONAL`/`MIN_NOTIONAL`, `PRICE_FILTER`, zero values,
   apply-to-market flags, base/quote precision hints, fixed-point strings, and
   no scientific notation. Explain quote-buy execution quantity and how to
   derive UM sell `quantity` from one user-entered USDT amount without a false
   forward common grid.
3. Verify the PAPI paths, exact query keys, weights, response fields, and
   retention limits for order-by-client-ID, margin/UM trades, UM position risk,
   balance, account, position mode, max borrow, and order rate limit. Specify
   the durable record written before either POST and the timeout/5xx/disconnect
   reconciliation sequence. Verify PAPI test endpoint/testnet status without
   confusing normal spot/UM testnet with Portfolio Margin.
4. Verify signing time endpoint/base, `recvWindow`, TRADE permission, relevant
   PM account status/risk fields, rate-limit headers/429/418 behaviour, and any
   PM/PM-Pro or account-mode compatibility check needed before a task.
5. List factual blockers needing a new user decision. Do not propose auto-borrow,
   auto-repay, auto-close, auto-repair, mode switching, transfers, or a silent
   fallback from `quoteOrderQty` to `quantity`.

## Deliverable

Write Chinese. Lead with a concise verdict, then answer the five items with
tables. Give direct official URLs, useful `llms-full.txt` line ranges, and
sanitized public snippets/sample paths. Separate facts from inference. End with
a checklist of changes required from the old `q_common` model.

Save raw output unchanged to:

`reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`

当前 Session ID: unavailable (research model must report its own runtime evidence)
Session ID 来源: unavailable
原始输出路径: reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md
本地北京时间: 2026-07-23 13:55:36 CST
下一步模型: human operator
下一步任务: execute this research packet in an independent model session and archive the raw output unchanged
