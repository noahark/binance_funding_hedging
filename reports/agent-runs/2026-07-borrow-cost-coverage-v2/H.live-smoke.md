# H Live Smoke（验收项 10）

执行：Fable5 bookkeeper，只读实盘 smoke
时间：2026-07-08 本地
服务：`python -m backend.app.server`，landed_sha `11c3935`，`BINANCE_PRIVATE_CHANNEL_ENABLED=true`，`APP_OFFLINE=false`
端点：`GET http://127.0.0.1:8787/api/public-market/snapshot`（只读；零下单/借还/划转）

## 核心指标（主修生效）

```text
private_channel:                 enabled
borrow_validation.chain_hit_tier:   1              (修复前=2 rate_history)
borrow_validation.chain_hit_source: next_hourly    (修复前仅 1 资产命中)
borrow_validation.coverage:      {probed:50, skipped:12, reason:rate_limit_budget}
```

## 80 个负费率行归类

| 类别 | 数量 | 判定 |
|---|---|---|
| next_hourly 有利率 | 62 | 主修生效 |
| └ 其中 error=borrowability_not_probed（有利率·可借性未探测） | 12 | 预算解耦生效：超 cap=50 但利率保留 |
| bStock 无利率（SAMSUNG/SKHYNIX/TTWO） | 3 | 设计禁借，应无 |
| CRYPTO 子集缺失无利率（error=None，未伪造） | 15 | 根因B，已 defer per-asset-cost-leg-v1 |
| legacy not_probed_this_round | 0 | 旧"截断清空利率"态消失 |

## 结论

三个修复目标实盘全部命中：①横杠→利率（62 行 next_hourly）；②预算截断不再清空利率（12 行有利率+borrowability_not_probed）；③子集缺失诚实留空不伪造（15 行 error=None）。无回归。根因B 的 15 个 CRYPTO 子集缺失为已知 defer 项。

抽样：`BLURUSDT next_hourly daily_borrow=0.00129864 net=0.08004630`；`OPGUSDT next_hourly daily_borrow=0.00191088 net=0.01634262`。
