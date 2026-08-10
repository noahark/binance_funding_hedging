# Evidence index — 2026-08-margin-account-flow-recon-v1

| 项 | 值 |
|---|---|
| collection | `2026-08-margin-account-flow-recon-v1` |
| timestamp | `20260810T062742Z` |
| mode | signed GET only（无下单/划转/改 gate） |
| authority | `recon.md` |

## Captures

| file | purpose |
|---|---|
| `recon.md` | 完整摸排：目标 path 404、可用替代源、字段、与互转对照、展示建议 |
| `probe-summary.json` | 首轮探测矩阵（含 papi 404 / sapi 200） |
| `deep-summary.json` | 深挖 capital-flow / asset-transfer 摘要 |
| `raw-meta/*.meta.json` | 每探针 status/latency/headers/body_bytes（无 body） |
| `sanitized/papi_marginAccountFlow__*.json` | 目标 path 各参数 404 |
| `sanitized/alt__*.json` | 近义 path 探测 |
| `sanitized/capital_flow_*.json` | capital-flow 形状、type 过滤、本地 tranId 命中 |
| `sanitized/capital_flow_type_enum_probe.json` | type 枚举是否被 API 接受 |
| `sanitized/asset_transfer_*.json` | 万向划转历史双向形状与命中 |
| `sanitized/sapi_asset_transfer__*.json` | 首轮 asset/transfer（含缺 type 400） |

## Headline numbers (live)

| metric | value |
|---|---|
| `papi .../marginAccountFlow` | **404**（全参数） |
| `sapi .../margin/capital-flow` 7d | **149** rows |
| 其中 `TRANSFER` 7d | **24** |
| 本地互转 tranId 命中 capital-flow | 4/4 抽查成功（含今日两笔 10U） |
| `asset/transfer` MAIN→PM 30d | ~10 rows |
| `asset/transfer` PM→MAIN 30d | ~11 rows |
| capital-flow 行字段 | `id, tranId, timestamp, asset, type, amount` |
| asset/transfer 行字段 | `timestamp, asset, amount, type, status, tranId` |
| capital-flow 文档 weight | 100 IP |
| capital-flow 时间窗 | 近 90 天；单次 start/end ≤7 天 |

## Non-goals

- 未改产品代码、未扩 WHITELIST、未落 raw 全量金额 body。  
- 未做 UI / 未定产品筛选默认。  
- 未测逐仓 `symbol` 分支。
