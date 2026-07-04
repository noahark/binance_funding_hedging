# 夜间采集落档说明

本次采集由 Kimi 在 2026-07-04 夜间执行，目标是为后续 GPT/Claude 整理提供结构化的币安 API 样本与项目接口矩阵。

## 落档位置

```text
reports/api-samples/night-collection-2026-07-05/20260704T155543Z/
```

## 文件清单

| 文件 | 说明 |
|---|---|
| `raw/*.json` | 各端点原始 JSON 响应（已脱敏） |
| `raw/*.headers` | 公开端点响应头（仅保留安全字段） |
| `manifest.json` | 采集元数据：端点、时间、状态、sha256 |
| `evidence-index.md` | 样本索引与 sha256 清单 |
| `endpoint-matrix.md` | 项目代码中所有 Binance REST 端点的入参出参矩阵 |
| `collect.py` | 采集脚本（可复用） |
| `sanitize_and_index.py` | 脱敏与索引生成脚本 |

## 采集范围

- **公开端点**（无需 API key）：`/fapi/v1/exchangeInfo`、`/fapi/v1/premiumIndex`、`/fapi/v1/fundingInfo`、`/api/v3/exchangeInfo`、`/fapi/v1/fundingRate`（BTC/ETH/SOL/XRP/DOGE/BNB，limit=20）。
- **私有只读白名单端点**（经 `backend/services/private_client.py` 单一 HMAC 出口）：`/sapi/v1/margin/allPairs`、`/sapi/v1/margin/allAssets`、`/sapi/v1/margin/crossMarginData`、`/papi/v1/margin/maxBorrowable`（BTC/ETH）。

## 安全与脱敏

- 所有落档 URL 已剥离 query string。
- 未落档任何 key/secret/signature/recvWindow/timestamp。
- `maxBorrowable` 账户级金额字段已替换为 `<AMOUNT>` / `<LIMIT>` 占位符。
- `backend/tests/test_private_client.py` 16 项测试全部通过。

## 给 GPT/Claude 的整理建议

1. 先读 `evidence-index.md` 了解本次采集的端点和文件对应关系。
2. 读 `endpoint-matrix.md` 了解项目代码中的接口调用点与入参出参。
3. 读根目录 `reports/api-samples/api-samples-index.md` 了解历史样本归档。
4. 如需对比历史合约，可查看 `public-market-contract-v2/20260703T051738Z/`。

## 注意事项

- `api-v3-exchangeInfo.json` 约 28 MB，读取时注意上下文窗口。
- 环境变量 `BINANCE_API_KEY` / `BINANCE_API_SECRET` 仅用于采集，未写入任何文件。
- 采集时间：2026-07-04T15:56:44Z（UTC）。

---

本地北京时间: 2026-07-05 00:00:55 CST
下一步模型: GPT / Claude
下一步任务: 整理本目录下的 evidence-index.md、endpoint-matrix.md 与 raw 样本，提炼对后续开发有用的接口契约与字段说明。
