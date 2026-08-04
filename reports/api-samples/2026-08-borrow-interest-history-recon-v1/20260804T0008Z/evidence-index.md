# Evidence index — 2026-08-borrow-interest-history-recon-v1

| 项 | 值 |
|---|---|
| collection | `2026-08-borrow-interest-history-recon-v1` |
| timestamp | `20260804T0008Z` |
| mode | signed GET only（私有只读 Key） |
| authority | `recon.md` |

## Captures

| file | purpose |
|---|---|
| `recon.md` | 完整摸排经验、传参/出参、累计口径、实现建议 |
| `sanitized/e1-page-shape.json` | E1 / sapi interestHistory 分页响应形状 |
| `sanitized/e1b-empty.json` | portfolio interest-history 空响应 |
| `sanitized/balance-interest-fields.json` | balance 上借款/未结利息字段 |
| `sanitized/sapi-vs-papi-compare.json` | 两接口同页等价 |
| `sanitized/rate-model-check.json` | `principal × dailyRate / 24 ≈ interest` |

## Headline numbers (live)

| metric | value |
|---|---|
| interestHistory 7d `total` / fetched | 1006 / 1006 |
| interestHistory 30d `total` / fetched | 1647 / 1647 |
| types (7d) | PERIODIC 940, ON_BORROW 66 |
| charge interval | 3600000 ms (1h) |
| E1b 30d | `[]` |
| papi vs sapi same page | txId/interest equal |
| sapi weight | +1 / call |
| papi E1 weight (observed) | ~+10 / call |
| size max | 100 (`size=200` → -1102) |

## Non-goals of this capture

- 未落库、未改产品代码、未开新 stage。
- 未抓取全量 raw ledger（避免账户金额全量落盘）；以脱敏形状 + recon 结论为准。
- 未验证 loan/repay 历史与任务归因。
