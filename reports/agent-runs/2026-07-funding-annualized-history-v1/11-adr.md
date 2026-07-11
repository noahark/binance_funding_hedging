# ADR: Funding Annualized History And Drawer

## ADR-1: Settled Windows Use Calendar Denominators

- Status: proposed for this stage package
- Decision: 7D and 30D annualization sums settled `funding_rate` values inside
  inclusive calendar windows and multiplies by `365 / N`. No observed-span
  denominator, mean-period formula, or current estimated rate is used.
- Rationale: funding intervals may change inside the window. Calendar
  denominators keep short listing histories conservative and comparable.
- Consequence: a row with no settled points is `null`; a row with only partial
  history can have a small non-null result rather than an inflated rate.

## ADR-2: Deep History Is Top-N And Independently Cached

- Status: proposed for this stage package
- Decision: request at most `Config.top_n` deep histories per cache cycle, with
  a per-symbol 1,800-second successful-result cache. Request failures degrade
  only the affected row.
- Rationale: the public `fundingRate` and `fundingInfo` endpoints share an IP
  budget. Polling the full universe every snapshot would breach the product's
  rate-budget constraint.
- Consequence: non-top-N rows retain 24h annualization and initially have
  empty history / `null` 7D/30D values. The review-feedback amendment adds
  selected-symbol enrichment through the same bounded cache, not full-universe
  polling.

## ADR-3: Additive Contract Now, Canonical Documentation Later

- Status: proposed for this stage package
- Decision: add the three fields as optional additive runtime-schema properties
  while requiring every current service output row to emit them. Require
  authentic raw evidence during implementation. Do not edit the canonical API
  contract during implementation; promote it only after review and explicit
  user approval.
- Rationale: the repository's canonical-doc gate prevents model drafts from
  being promoted before the user accepts the reviewed delivery.
- Consequence: frozen v0.1 snapshots remain schema-valid; the service-output
  guarantee is covered by Task A tests. `70-handoff.md` must name
  `docs/api/public-market-contract.md` and the raw sample path as a
  post-acceptance documentation obligation.

## ADR-4: Drawer Selection Uses A Same-Origin History Contract

- Status: proposed review-feedback amendment
- Decision: a Drawer selection whose snapshot row has no preloaded settled
  history calls a same-origin public endpoint for that single eligible symbol.
  It reuses the existing 30-minute successful-result cache and snapshot time
  boundary. Success distinguishes `available` from `empty`; upstream failure
  is an explicit HTTP 502 rather than an empty list.
- Rationale: top-N preload protects the shared public rate budget, but a blank
  Drawer for TST/RE means “not queried” rather than “no history.” A per-symbol
  request keeps the bounded policy while allowing the operator to inspect the
  row they selected.
- Consequence: this is a new API contract and needs a machine schema, server
  route tests, and post-review canonical API documentation promotion. It does
  not introduce a client-to-Binance path, private data, persistence, or a
  full-market background fetch.

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 确认三个 proposed ADR 可作为后续实现与审阅的约束。
```
