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
- Consequence: non-top-N rows retain 24h annualization but return empty
  history and `null` 7D/30D values until selected for enrichment.

## ADR-3: Additive Contract Now, Canonical Documentation Later

- Status: proposed for this stage package
- Decision: add the three required additive fields to the runtime schema and
  require authentic raw evidence during implementation. Do not edit the
  canonical API contract during implementation; promote it only after review
  and explicit user approval.
- Rationale: the repository's canonical-doc gate prevents model drafts from
  being promoted before the user accepts the reviewed delivery.
- Consequence: `70-handoff.md` must name `docs/api/public-market-contract.md`
  and the raw sample path as a post-acceptance documentation obligation.

```text
本地北京时间: 2026-07-10 13:13:36 CST
下一步模型: human
下一步任务: 确认三个 proposed ADR 可作为后续实现与审阅的约束。
```
