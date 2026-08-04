# Evidence index — 2026-08-um-income-funding-recon-v1

| 项 | 值 |
|---|---|
| collection | `2026-08-um-income-funding-recon-v1` |
| timestamp | `20260804T0015Z` |
| mode | signed GET only |
| authority | `recon.md` |

## Captures

| file | purpose |
|---|---|
| `recon.md` | 完整摸排：原始脚本、papi/fapi、手续费、累计口径 |
| `sanitized/um-income-shape.json` | 响应字段与 type 样例 |
| `sanitized/funding-fee-summary.json` | 30d 资金费分页/累计结构 |
| `sanitized/commission-and-feeBurn.json` | COMMISSION + commissionRate + feeBurn |
| `sanitized/fapi-rejected.json` | 本 Key 调 fapi -2015 |
| `sanitized/prototype-mapping.json` | 旧脚本接口 → 统一账户映射 |

## Headline numbers (live)

| metric | value |
|---|---|
| open UM positions | 8 |
| um/income 30d all types | 193 rows |
| FUNDING_FEE 30d | 134 rows |
| COMMISSION 30d | 55 rows (all BNB) |
| REALIZED_PNL / TRANSFER | 2 / 2 |
| sort order | ascending by `time` |
| limit max | 1000 |
| default window | ~7d |
| weight | ~30 IP per call |
| fapi /fapi/v1/income | 401 -2015 |
| feeBurn | true |
| sample commissionRate | maker 0.000200 / taker 0.000500 |

## Non-goals

- 未改产品代码、未扩 WHITELIST、未落全量 raw 流水。
- 未摸排现货/杠杆 myTrades 手续费（UM 以外的 COMMISSION 源）。
- 未验证 income async 下载接口。
