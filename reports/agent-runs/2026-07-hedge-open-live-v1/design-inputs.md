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

## DI-3: Pending recon before design
- WebSocket facts (in progress, Sonnet 4.6) → `api-recon-websocket.prompt.md`.
- Order endpoints (papi spot margin market + UM perp market) + exchange filters
  (stepSize/minNotional) → separate recon still needed.
