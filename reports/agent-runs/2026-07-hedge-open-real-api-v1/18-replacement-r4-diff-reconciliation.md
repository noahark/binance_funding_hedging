# Replacement Rework — R4 差异对账

## 对账范围

- 基线提交：`26bb7b40a61de13e2151f0ccca057810a4cd815e`。
- 收到的原始实现报告：
  - `40-fix-review-2-backend.md`（Claude-GLM）；
  - `40-fix-review-2-frontend.md`（Claude Sonnet 5）。
- 允许的实际源代码改动只落在两份 54/55 派发包授权的后端、前端文件及其测试中；未发现
  `docs/**`、凭据、借币模块、签名器或真实网络配置越界改动。
- `git diff --check` 通过。

## 已复跑的集成证据

| 检查 | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest backend/tests -q` | `880 passed in 44.46s` |
| `node frontend/self-check.js` | 通过 |
| `.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q` | `55 passed in 0.89s` |
| `git diff --check` | 通过 |

上述命令均为本地离线验证。未读取凭据、未连接 Binance、未调用 Start、未发出真实 POST。

## 阻断发现：P1 开单日志加载更多会重复

当前服务在 `service.get_logs()` 中把旧 `next_cursor` 从 legacy `logs` 计算，却把
`entries` 另行由 attempts 与 events 合并：

- `backend/hedge_open_tasks/service.py:544-553`：旧 `next_cursor` 只来自
  `list_logs_page()`；
- `service.py:583-595`：entries 的 attempts 会应用旧 cursor，但 task events 调用
  `list_task_event_logs(limit, ...)` 时没有 cursor；
- `store.py:1288-1307`：task events 每一页都取最新 `limit` 条；
- `frontend/index.html:3972-3984`：开单日志页将 `doc.next_cursor` 回传为下一页的
  `cursor`。

所以用户点击「加载更多」时，新的 task_event 可能在每一页重现。现有后端回归只验证
“单页长度不超过 limit”，前端 mock 也把 `next_cursor` 假定为 entries 的游标，因而没有
覆盖这条真实组合路径。

实际影响只限审计页面的显示正确性，不会新增、重发或改变任何订单；但日志页是用户要求的
失败审计入口，不能带着重复记录进入提交与复审。

## 处理决定

按 `17-opening-log-pagination-compatibility.md` 进行一个小的、加法式双侧修复：旧分页
完全保留；新开单日志改用独立的 `entries_limit`、`entries_cursor` 和
`entries_next_cursor`。这是对 16 §5 在异构数据源上的必要细化，而不是由实现者自行改写
冻结契约。

本次 R4 尚未创建 H_A/H_B 代码证据提交；当前未提交实现保持原样，等待 56/57 修复完成后
一起做最终对账、复跑、提交和重新 Review-1。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/18-replacement-r4-diff-reconciliation.md
本地北京时间: 2026-07-24 17:34:20 CST
下一步模型: human operator
下一步任务: execute packets 56 and 57; do not enable live trading
