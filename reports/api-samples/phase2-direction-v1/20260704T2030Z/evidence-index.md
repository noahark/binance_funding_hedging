# Evidence index — phase2-direction-v1 (fundingInfo 归一化论据)

Captured: 2026-07-04 ~20:30 CST by Fable5, anonymous public GET (no key,
no signature), during Phase 2 direction drafting (DRAFT-2.1 §5/§6).

| file | source | sha256 |
|---|---|---|
| `fapi-v1-fundingInfo.json` | `GET https://fapi.binance.com/fapi/v1/fundingInfo` | `33f61539987942245c8df0c41f9b9ebf8da2dc9eb7946673f830acceefd53287` |

Supports: 结算间隔分布 711 条目 = 440×4h + 269×8h + 2×1h（fundingIntervalHours
字段），证明单期费率跨交易对不可比、日费率归一化为排名正确性必要条件。
实现阶段 H_intake 需重新实抓并冻结字段矩阵；本样本仅为方向论据。
