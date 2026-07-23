# Design Inputs — Hedge Open Live v1

Running notes captured before formal stage design, so decisions are not lost.
These are inputs to `10-design.md`; nothing here is frozen until the design +
review gates run.

## DI-1: Spot bookTicker has no exchange timestamp — timestamp policy

**Fact (to be confirmed by the websocket recon, Sonnet 4.6 in progress).** Spot
`<symbol>@bookTicker` does not return `E`/`T` event timestamps, whereas USDⓈ-M
perp `bookTicker` does.

**User's decision (2026-07-22, FINAL — carries into ADR).** Stamp **local
receive time** into spot `E`/`T` (spot has no exchange timestamp); keep the
perp's **exchange-native `E`/`T`**. Same message shape downstream, but different
provenance by design: `spot = local-recv`, `perp = exchange`.

**Rationale (real production failure).** The perp websocket has been observed
pushing **stale prices — seconds to ~1 minute old**. Using the perp's exchange
`E` makes such stale data FAIL the ≤200ms gate (`spot-local − old perp-E` = a
large gap), which is exactly the intended defense. Stamping *local receive
time* on the perp leg would DEFEAT this — a 1-minute-old price stamped "now"
looks fresh and would pass. So the earlier "both-legs-local-receive" idea is
**withdrawn**. The ≤200ms gate thus does double duty in one check: perp
staleness + rough cross-leg alignment.

**Completion point to settle at design (not a reversal).** Because the gate
subtracts spot-local from perp-exchange-`E` directly, it implicitly assumes the
**local clock is aligned with Binance's server clock**; a fixed clock skew leaks
straight into the 200ms judgment (a drifting clock would make the gate
always-pass or always-fail). Mitigation to bake into the design: keep NTP
synced, optionally calibrate against Binance server time (`/time` / serverTime),
and **monitor + log the local-vs-server offset** so clock drift is detected
rather than silently skewing the gate. Record the whole DI-1 as an ADR at
design time.

**Recon update (2026-07-22, Sonnet 4.6 —
`reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md`).**
- Spot `@bookTicker` has NO `E`/`T` (official sample, confirmed). Perp
  `@bookTicker` `E`/`T` is changelog-inferred, not yet a real sample.
- New option surfaced: spot `@depth5@100ms` **does carry an `E`** (exchange
  time), so spot could get an exchange timestamp after all — at the cost of a
  ≤100ms push-granularity lag (Sonnet suggests tightening the gate to 150ms).
- Two candidate policies now on the table:
  - **A (Sonnet-recommended): both legs exchange-`E`.** spot `@depth5@100ms` `E`
    vs perp `@bookTicker` `E`; `|E_perp − E_spot| ≤ 150ms`. Cleanest reference
    frame (no local-clock dependence). Cost: spot loses realtime bookTicker,
    gains 100ms granularity. **Precondition: depth5 actually carries `E` —
    unconfirmed.**
  - **B (user's DI-1): spot local-recv / perp exchange-`E`.** Keeps spot
    realtime bookTicker; defends perp staleness via perp `E`. Cost: mixes
    reference frames → depends on local-clock alignment (NTP/serverTime).
- **Key clarification for the decision:** defending against *stale perp pushes*
  (the user's real-world failure) does NOT require the spot leg's timestamp
  source at all — it is achieved by a **per-leg `now_local − E_perp`
  freshness check on the perp leg**. So both A and B can defend against perp
  staleness. The real A-vs-B choice is about the **spot stream** (realtime
  bookTicker + local ts, vs depth5@100ms + exchange E) and reference-frame
  purity. To be decided by the user at/before design.
- Open real-sample items (Hard Gate — need real captures, user may already have
  them from production): perp `@bookTicker` real JSON (confirm `e`/`E`/`T`);
  spot `@depth5@100ms` `E` presence; perp host `/public` migration.

**DECISION LOCKED (2026-07-22, user) — this is the smooth-open time-gate ADR.**
- **Option B chosen.** Spot `@bookTicker` (realtime) + **local-receive
  timestamp**; perp `@bookTicker` + **exchange `E`/`T`**. Gate:
  `|E_perp − t_spot_local| ≤ 200ms`. This cross-leg check already rejects a
  stale perp push (old `E_perp` → large gap) — the intended defense — so no
  separate perp-staleness rule is strictly required, though a per-leg
  `now_local − E_perp` check may be added as belt-and-suspenders.
- **Perp `@bookTicker` carries `E`/`T`: confirmed by the user from production
  use.** Closes the changelog-inferred open item; no separate real sample
  needed for this.
- **Perp WS host `/public` is already in use in the user's code** (old `/ws`
  retired): confirmed.
- **Config to bake into the design:** NTP / Binance `serverTime` calibration +
  monitor & log the local-vs-server clock offset, so `t_spot_local` and
  `E_perp` share one clock and drift is detected rather than silently skewing
  the 200ms gate.
- Option A (depth5 exchange-E) is **not** taken; `depth5`-carries-`E` is parked,
  not a blocker.

## DI-2: Safety model — carry Boundary C posture
Dry-run/disabled executor default; `APP_HEDGE_EXECUTOR=live` gate; durable
SQLite; global Start; read-only preflight. (From intake; listed here so design
keeps it front-and-center.)

## DI-3: Recon status
- WebSocket facts — **DONE** (Sonnet 4.6), see DI-1 DECISION LOCKED and
  `reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md`.
- Order endpoints + filters — **DONE** (GPT/Codex), see DI-4 and
  `reports/api-samples/2026-07-hedge-open-live-v1/order-endpoints-filters-recon.md`.

## DI-4: Order/execution contract (from GPT recon — design inputs, "directly usable")
Source: `order-endpoints-filters-recon.md` (papi base `https://papi.binance.com`;
endpoints cross-verified against official SDK `@binance/derivatives-trading-
portfolio-margin` v6.0.0; filters backed by real public exchangeInfo samples).

- **Endpoints:** spot leg `POST /papi/v1/margin/order`, perp leg
  `POST /papi/v1/um/order` (both weight 1, signed TRADE). Use
  `newOrderRespType=RESULT`, a unique `newClientOrderId` per leg.
- **Quantity:** both legs `quantity=q` (base coin) — NOT `quoteOrderQty`. Align
  both legs on a common filter grid (decimal `lcm(step_spot, step_um)`) to one
  `q_common`; reject if below any min / above any max. **Never round the two
  legs independently — that manufactures directional exposure.**
- **sideEffectType (reverse "no auto-borrow"):** `NO_SIDE_EFFECT` for BOTH
  directions' spot leg. papi enumerates only `NO_SIDE_EFFECT`/`MARGIN_BUY`/
  `AUTO_REPAY` — there is NO `AUTO_BORROW_REPAY`. Reverse preflight must confirm
  `crossMarginFree(base) >= q`; `maxBorrowable` is NOT proof of sellable amount.
- **positionSide:** query `GET /papi/v1/um/positionSide/dual` (never change
  mode in the flow). Direction map: forward = spot `BUY` + um `SELL`
  (`positionSide` BOTH one-way / SHORT hedge); reverse = spot `SELL` + um `BUY`
  (BOTH / LONG). No `reduceOnly` on opens.
- **Filters:** papi has NO exchangeInfo — read public
  `api.binance.com/api/v3/exchangeInfo` (spot) + `fapi.binance.com/fapi/v1/
  exchangeInfo` (perp) per symbol, don't hardcode. Honor
  `LOT_SIZE`/`MARKET_LOT_SIZE` (a 0 field = that limit disabled) / spot
  `NOTIONAL`(minNotional, applyMinToMarket) / perp `MIN_NOTIONAL`. Decimal
  fixed-point `floor(q/step)*step`.
- **Balance/quota:** `/papi/v1/balance` (`crossMarginFree` etc), `/account`,
  `/margin/maxBorrowable` (verify only), `/um/positionRisk`.
- **Single-leg exposure (matches our locked policy):** don't trust the POST
  return alone; on timeout/5xx/non-`FILLED`, query
  `margin/order`+`um/order`+`myTrades`+`userTrades`+`positionRisk` by client id;
  one leg `FILLED` + other not = single-leg risk → stop, record both legs, NO
  auto-hedge/close. Never re-send the same client id.
- **Rate limit:** both weight 1 → one hedge = 2 order events; read
  `/papi/v1/rateLimit/order`; on 429 stop and keep unsent tasks, don't retry to
  accelerate.
- **Dry-run:** no PAPI testnet exists; use a **record transport** (log the
  would-send signed requests + filter versions + preflight snapshot + client
  ids, no network POST). Any minimal real PAPI validation needs separate human
  authorization. This matches the Boundary C posture (DI-2).
- **Open real-sample item (Hard Gate):** the real order-response JSON must come
  from a later human-authorized real order; not fabricated. Does not block
  design (design uses the official response schema + record transport).

## DI-5: Dry-run demo preflight deferred (user decision 2026-07-23)
The round-1 server wires `DisabledPreflightProvider` (zero network), so `q_common`
is unknown and a created immediate task stays idle (no fills, `公共网格量=—`),
and the global Start gate defaults off — both are the safest defaults. Page-level
演练 of immediate open → fills → positions → exposure-alert therefore shows
nothing out of the box. **User decided (2026-07-23) to NOT add a demo/mock
preflight provider this round; it is deferred to the next round that wires real
data** (mock filters or real public `exchangeInfo` + read-only balance),
alongside the live-round follow-ups F-003..F-006. Round-1 dry-run stays
"idle but safe".

## DI-6: Order-parameter model defect — spot market BUY needs quoteOrderQty (real-API round rebuild)
User clarification (2026-07-23): a **spot market BUY can only pass
`quoteOrderQty` (total USDT)**, while contract buy/sell and spot sell pass
`quantity`. Therefore:
- **Forward** (buy spot + sell perp): spot leg = `quoteOrderQty` (USDT amount),
  perp leg = `quantity`. The two legs' units differ, so the executed base qty
  cannot be pre-aligned — **common-grid rounding (ADR-2) and executed-qty equality
  do NOT hold for forward opens**.
- **Reverse** (sell spot + buy perp): both legs = `quantity`, can align.

So the current DI-4 / ADR-2 model ("both legs `quantity=q_common` + common grid +
executed-qty equality") is **wrong for forward opens**. The current dry-run record
transport records incorrect forward-leg params, but performs no real POST, so no
harm yet. **Deferred to the real-API round** (user: "直接上真实 api"): redesign
order params per direction (spot buy = `quoteOrderQty` derived from amount×price;
others = `quantity`), the amount→notional conversion, the frontend input
semantics, and real preflight/executor + the user's margin/amount/count risk
controls. This round's **fix-3 only removes the executed-qty check** in
`classify_attempt` (both legs filled → success), matching the user's "暂时不做
成交数量校验"; the order-parameter rebuild is explicitly NOT in this round.
