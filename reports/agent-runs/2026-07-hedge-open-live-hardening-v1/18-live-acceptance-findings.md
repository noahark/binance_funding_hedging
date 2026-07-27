# Live Acceptance Findings — 2026-07-27, during stage review_2

The user restarted the service in `live` mode to accept the UI work by hand,
opened the Start gate through the new S3 control, and ran a real NOMUSDT task.
This file records what that run proved and what it exposed. It is written by the
bookkeeper **after** the pinned range `6c5b170..319d831` was frozen and after
both Review-1 gates returned ACCEPT; **no delivery code was changed**, so the
fingerprint both gates reviewed is untouched.

## What the run proved works

- **S1's P0 fix is confirmed in production.** clientOrderId
  `hgd1a45d5b7df0423a8840d72556767f82s` / `…p` is 35 chars and passed Binance's
  format validation on both legs — the `-4015` that blocked every order on
  2026-07-27 morning is gone. The perp leg actually filled.
- **S3's write path works end to end.** The gate was opened through the new
  control (`hedge_open_settings.version` went 3 → 4), not by direct SQL. The CAS
  behaved.
- **The settings contract holds on the wire**: `GET /api/hedge-open-settings`
  returns `{"executor_mode":"live","start_gate":…,"interval_seconds":1,"version":…}`
  — the additive `version` field is live, not just green in tests.

## What it exposed — four defects, none inside this stage's five items

### F-1 (P0 for accounting) `cumQuote` / `avgPrice` were removed by Binance

**Not** an unfilled field, and **not** a timing problem. Binance's Portfolio
Margin changelog, announced 2026-07-13 and **effective 2026-07-14**:

> The `cumBase`, `cumQuote` and `avgPrice` fields will be removed from the
> responses of the following endpoints: POST `/papi/v1/um/order`,
> POST `/papi/v1/cm/order`, DELETE `/papi/v1/um/order`, DELETE `/papi/v1/cm/order`

Source: `https://developers.binance.com/docs/derivatives/portfolio-margin/change-log`
(verified by the bookkeeper on 2026-07-27).

The first real order ran on 2026-07-27, 13 days after the removal. Chain:

```
reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md:98
  records UM RESULT as containing cumQuote / avgPrice   <- true when captured
    -> live_hedge_executor.py:240-247 reads them
    -> Binance removes the fields 2026-07-14
    -> body.get("cumQuote") is None
    -> _decimal_str(None) returns its default "0"        <- SILENT
    -> DB stores quote 0, avg_price NULL; UI shows 0
```

Evidence in `data/hedge-open-tasks.sqlite3`: perp leg `exchange_status=FILLED`,
`cumulative_base_qty=10000`, `cumulative_quote_amt=0`,
`dispatch_state=TERMINAL_RECORDED`, and `last_query_at_us - dispatched_at_us = 0`
(never queried after the POST).

**Impact is not cosmetic**: the position table's spot/perp average price and
unrealised PnL are all derived from `cumulative_quote_amt`. Every one of those
figures is wrong whenever a leg fills.

**Secondary cause worth fixing with it**: `_decimal_str(value, default="0")`
(`live_hedge_executor.py:136-143`) makes "the field is absent" indistinguishable
from "the value is genuinely zero". Had absence produced `None`, the system could
have noticed the contract drift on the first fill instead of storing a plausible
zero. Same shape as the S5 lesson: a silent downgrade hid a real defect.

### F-2 (P1) The error-code table cannot match margin-leg errors at all

Binance uses **positive** codes on margin endpoints and **negative** codes on
UM/CM — a deliberate product-line distinction (confirmed with Binance support).
Evidence from our own DB:

```
COOKIEUSDT (UM leg,     /papi/v1/um/order)     error_code = '-4015'
NOMUSDT    (margin leg, /papi/v1/margin/order) error_code = '51169'
```

`_business_code` is `str(body.get("code"))` and does **not** drop the sign — the
positive value is what Binance actually sent.

But `FATAL_EXCHANGE_CODES`, `INSUFFICIENT_FUNDS_CODES` and
`AUTH_AMBIGUOUS_EXCHANGE_CODES` (`domain.py:306-353`) are entirely negative
string literals. So **no margin-leg error code can ever match any of them** —
this is not a missing entry for 51169, it is the whole table being blind to one
product line. Every margin rejection falls through to the documented default,
*"an unlisted 4xx defaults to a known non-fatal rejection (counter)"*
(`domain.py:302-303`), so it neither stops nor pauses the task.

Observed consequence: `error_category` is NULL on the rejected leg, and the task
settled to `done` with a live single-leg exposure outstanding.

### F-3 (P1) Binance's error message is never persisted

`_business_msg()` exists (`live_hedge_executor.py:77-82`) and extracts `msg`,
but `hedge_open_leg` has **no** column for it and `hedge_open_log` records only
the request params, never the response. The exchange's own words — the single
most useful artefact when diagnosing a real rejection — are discarded.

This is why answering "why did the spot leg fail" required going to Binance
support rather than reading our own records.

### F-4 (P2, open) `51169` root cause is still undetermined

`51169` = `MARGIN_TRADE_COEFF_INSUFFICIENT`. Per Binance support, **COEFF is the
collateral/haircut coefficient**: the check is on *discounted effective margin*,
not nominal balance. So "I clearly had enough USDT" and this rejection are not
contradictory.

**Ruled out**: NOMUSDT not being margin-tradable. Public `exchangeInfo` reports
`isMarginTradingAllowed: true` with `MARGIN` in permissions, identical to
BTCUSDT and COOKIEUSDT. The bookkeeper's earlier hypothesis was **falsified**.

**Still unproven**: that the concurrent UM fill consumed the margin the spot leg
needed. Binance support called it "high probability" but had already answered
"not documented" to the question of which balance field is actually checked, so
that is inference, not fact. Our own preflight gate uses `crossMarginFree`
(`domain.py:794`) and support explicitly would not confirm that is the field
Binance validates against.

**Also established**: PAPI has **no test-order endpoint**. The bookkeeper checked
the official Portfolio Margin trade documentation — neither
`/papi/v1/margin/order/test` nor `/papi/v1/um/order/test` exists. A "dry validate
before sending" strategy is therefore unavailable and must not be designed
around.

**The one clean discriminator** (for the next stage, needs user authorization):
place a single margin BUY on NOMUSDT with **no concurrent UM order**. Success ⇒
concurrency contention is real. Same 51169 ⇒ it is the coefficient or wallet
placement, unrelated to concurrency. That order buys only; it creates no new
naked exposure.

## Outstanding real-money position

The perp leg filled: **SHORT 10000 NOMUSDT**, orderId `888412130`, unhedged. The
spot leg was rejected, so `residual = -10000`. The system has no close
functionality (that is the third stage of the hedge programme and is not built),
so unwinding it is a manual action on Binance by the user.

Note this settled to `done` rather than pausing, which is **correct per the
frozen design**: `single_leg_exposure` is ADVISORY — recorded, never a gate
(`domain.py:96-99`). Whether that remains the right product decision now that a
real naked position has occurred is a question for the user, recorded here
rather than decided by the bookkeeper.

## Effect on this stage

**None of F-1..F-4 is inside this stage's five items**, and no delivery code was
touched while diagnosing them. The pinned range, the fingerprint, and both
Review-1 ACCEPTs stand. The user decided: **Review-2 proceeds as planned**, and
F-1..F-4 plus the new persistence requirement open a separate stage. The Review-2
packet discloses this run so the final gate judges with full information.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md
本地北京时间: 2026-07-27 22:10:00 CST
下一步模型: human operator
下一步任务: 在只读 Codex 会话执行 50-review-2.dispatch.md；F-1..F-4 已归入新 stage 提案
