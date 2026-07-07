# Evidence Index: Private Account UI Polish V1

Stage: `2026-07-private-account-ui-polish-v1`

## Public ticker price sample

- File: `api-v3-ticker-price.json`
- Endpoint: `GET https://api.binance.com/api/v3/ticker/price` (no API key)
- Captured: copied from prior v0.3 stage evidence due to network constraints
- Source: `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/api-v3-ticker-price.json`
- Source git blob: `2d3bfcae319ea8329da9b16204e7f76f74da057b`
- Local sha256: `72bee62112c743de881d906e33aae80d706dbe4088b159180dc30f7750ae2786`

This sample grounds the v0.4 additive contract amendment for per-balance
`value_usdt` fields: the backend uses the same P5 `/api/v3/ticker/price` price
map for both `total_value_usdt` and the new row-level valuations.

本地北京时间: 2026-07-07 01:26:48 CST
下一步模型: Kimi
下一步任务: 继续实现并运行测试，捕获 60-test-output.txt
