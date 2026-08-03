# review-1-code REWORK — Bookkeeper 核验

核验时间：2026-08-03 08:14 CST

## 裁定

DeepSeek 的发现为 `in-range`，接受返工：生产代码在本交付把
`PreflightProvider.get_snapshot` 从 `(coin)` 改为 `(coin, direction)`，把
`LiveHedgeExecutor.query_leg` 从 `(leg, symbol, client_order_id)` 改为
`(leg, symbol, client_order_id, endpoint)`；两个旧测试文件中的 fake 没有同步，导致其回归集整体
TypeError。base 上的 `git blame` 显示 fake 均早于 base，本区间的调用签名改变是破裂原因。

独立复现命令：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  backend/tests/test_hedge_task_local.py \
  backend/tests/test_hedge_review2_regressions.py -q
```

结果：`77 failed, 1 passed`；首个错误为
`TypeError: get_snapshot() takes 2 positional arguments but 3 were given`，发生在
`backend/hedge_open_tasks/service.py:607` 调用旧 fake 时。

## 状态变更

- 原始 review 回执封存于 `evidence/review-1-code.deepseek.raw.md`。
- `rework_count` 从 0 增至 1，根因为 `test_stub_signature_drift`。
- 原 `delivery_sha` 保留为 `0ef8053`，直到修复提交经 Bookkeeper 核验后才替换。
- 仅允许 Claude-GLM 修改两份测试文件；review-1 必须在新 SHA 上重跑，review-2 保持未启动。
