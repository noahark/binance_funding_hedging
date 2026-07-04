# Evidence Index — lastFundingRate 语义（2026-07-public-market-ui-cn-v1）

Capture: 2026-07-04T04:49:45Z（响应头 Date 校准，ms=1783140585000），北京时间
12:49 CST——处于结算周期中段（本周期 00:00→08:00 UTC）。

Anonymous public GET only（无 key、无签名、无私有端点、无 order/borrow/repay/
transfer/websocket）；headers 已核查无鉴权信息。

## Raw files (sha256)

| file | sha256 |
|---|---|
| raw/fapi-v1-premiumIndex.json | 874ae3b12c16a4b1a20bf4a5331c65c60cf31ea53186103a933d6b8b7146c7a9 |
| raw/fapi-v1-fundingRate-BTCUSDT-limit3.json | 140989c0f6477f23f251c37f51b004b008a1801da6082fbf076720968da4b371 |
| raw/fapi-v1-fundingRate-ETHUSDT-limit3.json | c5d4cfd03ca2a2df63fc11c786388b676c3d4de122e4d29dc11d3b8f640e4e29 |
| raw/fapi-v1-fundingRate-SOLUSDT-limit3.json | 56ea04f6f5925baedad18fde874a0428c13d35b91b50bc98d0f52b79036254db |
| raw/fapi-v1-fundingRate-TSLAUSDT-limit3.json | ab491bdcb142cfd993fe0d4f0ce2e1e25303262ee671ca5d98d39586381e586a |

（校验命令：`shasum -a 256 raw/*.json`。）

## What it proves

`verify-funding-semantics.py`（离线重放，exit 0 = PASS，输出留档
`verify-output.txt`）：周期中段 ETHUSDT/SOLUSDT 的
`premiumIndex.lastFundingRate` 与 `/fapi/v1/fundingRate` 最新**已结算**记录
不相等——证明该字段不是已结算历史的回显，而是**本周期的实时预估值**，将于
`nextFundingTime` 结算收取。BTCUSDT 钉在利率钳制默认值 0.0001、TSLAUSDT 为 0，
两者相等属预期（无区分度样本）。

辅助佐证：SOLUSDT 在 04:34Z 的会话内即席检查值为 0.00006456，本次 04:49Z 抓取
为 0.00006761——15 分钟内漂移，直接观察到「结算前持续变化」。

## What it does NOT prove

- 预估值收敛到最终结算值的精确规则（时间加权平均细节）——展示层不依赖此点。
- 非 8h 结算间隔品种的行为（本次样本均为 8h）。

## Grounded amendment wording

`CONTRACT_WARNINGS[1]` / 合约文档从「语义未证实，勿标注」升级为：
「premiumIndex.lastFundingRate 是本资金费率周期的实时预估值，将于
nextFundingTime 结算收取，结算前会随溢价指数漂移；已结算历史以
/fapi/v1/fundingRate 为准。」
