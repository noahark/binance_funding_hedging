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

## DI-2: Safety model — carry Boundary C posture
Dry-run/disabled executor default; `APP_HEDGE_EXECUTOR=live` gate; durable
SQLite; global Start; read-only preflight. (From intake; listed here so design
keeps it front-and-center.)

## DI-3: Pending recon before design
- WebSocket facts (in progress, Sonnet 4.6) → `api-recon-websocket.prompt.md`.
- Order endpoints (papi spot margin market + UM perp market) + exchange filters
  (stepSize/minNotional) → separate recon still needed.
