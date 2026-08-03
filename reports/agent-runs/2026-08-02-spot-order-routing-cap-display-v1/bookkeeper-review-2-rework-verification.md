# review-2-reality REWORK — Bookkeeper 核验

核验时间：2026-08-03 10:07 CST

## 裁定

Opus5 的 `REWORK` 格式完整。Bookkeeper 独立运行项目规定的全量命令：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
```

结果与评审一致：`2 failed, 1213 passed in 71.81s`。失败均在
`backend/tests/test_hedge_purity.py`：旧的 `_FROZEN_ALLOWLIST` 仍只含 7 条 PAPI endpoint，且 host
断言要求全部为 `https://papi.binance.com`，与本轮已授权的 5 条 `https://api.binance.com` endpoint
冲突。生产 `ALLOWLIST` 的 deny-by-default 与 host 硬绑定行为正确；破裂的是反扩张守卫测试。

同轮核实 F2：`backend/services/hedge_open_live_client.py` 模块 docstring 仍声称仅 live executor
才构造 client，实际 `backend/app/server.py::_build_restricted_asset_client` 会在 executor disabled 时为
展示路径独立构造该 client。功能正确，说明文字失真。

## 同根因刹车

上一轮的 `test_stub_signature_drift` 与本轮均属同一根因家族：
**「改共享常量/签名后 dispatch 清单外既有守卫测试失效」**。这是连续第二次 `REWORK`，故本轮
`rework_count` 从 1 增至 2，修复任务必须做穷举扫描，而非再次只点补丁。

F3（v0.9 的接口约定权威指向）为 Opus5 标注的低优先文档项，未纳入本轮阻塞修复；不改变产品行为，
留待阶段收尾的文档复核。
