# Design Inputs — Hedge Open Live v1

Running notes captured before formal stage design, so decisions are not lost.
These are inputs to `10-design.md`; nothing here is frozen until the design +
review gates run.

## DI-1: Spot bookTicker has no exchange timestamp — timestamp policy

**Fact (to be confirmed by the websocket recon, Sonnet 4.6 in progress).** Spot
`<symbol>@bookTicker` does not return `E`/`T` event timestamps, whereas USDⓈ-M
perp `bookTicker` does.

**User's existing solution (2026-07-22).** On receiving a spot push, stamp the
**local receive time** into `E`/`T` so the spot message has the same shape as
the perp message; use it for price-freshness checks. Structural uniformity is
good and is retained.

**Bookkeeper/designer refinement to settle at design time.** The
smooth-open gate has TWO distinct time uses; they should not share one field
blindly:

1. **Cross-leg alignment** (`|t_spot − t_perp| <= 200ms`, the "期现延迟" gate):
   this must compare same-reference-frame times. If spot uses *local receive
   time* but perp uses the *exchange event time* `E` (server-emit time), the two
   are not同源 — the difference then absorbs network latency + clock skew rather
   than the true spot-vs-perp generation gap. Recommendation: for cross-leg
   alignment, stamp a **local receive time on BOTH legs** and compare those;
   this measures "how close together the two books actually arrived here", which
   is the real synchronization signal.
2. **Per-leg staleness** (is one book too old?): use the **exchange** timestamp
   where available (perp `E`/`T`): `now_local − E_perp`. Spot has no exchange
   timestamp, so spot staleness can only be approximated by local
   receive-interval.

**Net:** keep the uniform `E`/`T` shape, but make the field's provenance
explicit (`spot: local-recv`, `perp: exchange`), and drive the 200ms cross-leg
gate off a **both-legs-local-receive** timestamp. Confirm with the user at
design time; then record as an ADR.

## DI-2: Safety model — carry Boundary C posture
Dry-run/disabled executor default; `APP_HEDGE_EXECUTOR=live` gate; durable
SQLite; global Start; read-only preflight. (From intake; listed here so design
keeps it front-and-center.)

## DI-3: Pending recon before design
- WebSocket facts (in progress, Sonnet 4.6) → `api-recon-websocket.prompt.md`.
- Order endpoints (papi spot margin market + UM perp market) + exchange filters
  (stepSize/minNotional) → separate recon still needed.
