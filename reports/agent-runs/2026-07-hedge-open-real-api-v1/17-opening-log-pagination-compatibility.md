# 开单日志分页兼容修正

## 结论

在两侧 replacement rework（替换返工）完成后的 R4（落盘前跨任务对账）中，
bookkeeper 确认原先冻结的「复用 `cursor` / `limit` / `next_cursor`」表述不能同时
满足两个目标：

1. 旧的 `logs` / `attempts` 分页语义不能被破坏；以及
2. 新的异构 `entries`（尝试记录 + 任务事件）必须能逐页、无重复、无遗漏地展示。

原因不是前端文案，而是两类记录来自不同的持久化序列：旧日志使用
`hedge_open_log(ts_us, id)`，尝试记录使用 `hedge_open_attempt(created_at_us, id)`。
它们不能共用同一个两段式旧游标来可靠翻页。当前未提交实现尤其会在第二页再次取到
最新 task event（任务事件），使用户看到重复日志。

这是一个内部兼容性修正，不改变下单数量、下单节奏、风险策略、真实 API 权限或任何
Binance 请求。它属于 R4 发现的跨任务接口问题，不是新的正式 Review-2 REWORK
（需要返工）轮次；`rework_count` 保持 2。

## 绑定的加法式接口修正

`GET /api/hedge-open-logs` 保持原有参数和字段不变：

- 旧请求参数：`cursor`、`limit`；
- 旧响应字段：`logs`、`attempts`、`next_cursor`；
- 既有尝试时间线继续可以请求 `?limit=100`，不必迁移。

仅为开单日志页新增下列字段：

```text
请求：entries_limit=<1..100>、entries_cursor=<opaque cursor>
响应：entries（原 §5 的条目字段逐字不变）、entries_next_cursor
```

规则如下：

1. 首屏使用 `GET /api/hedge-open-logs?entries_limit=50`；加载更多仅携带上一次
   `entries_next_cursor`，即
   `?entries_limit=50&entries_cursor=<...>`。
2. `entries_next_cursor` 是不透明游标（opaque cursor，内部使用的翻页标记）；它必须
   从本页 `entries` 的统一排序位置派生，而不是从旧 `logs` 派生。
3. `entries` 由 attempt 与 task_event 合并后按稳定的 newest-first（最新在前）顺序
   翻页。连续页面合并后每个 `entry_id` 恰好出现一次，不能跳过，也不能重复。
4. 每个 entry 对象的字段名与
   `16-replacement-development-breakdown.md` §5 完全一致；本修正只允许在响应顶层
   额外增加 `entries_next_cursor`，不更改条目字段、Decimal 字符串或安全错误字段。
5. 缺少 `entries_next_cursor` 时，前端安全地视为没有更多新日志；不得退回使用旧的
   `next_cursor`，因为那会重新引入重复风险。

## 实现与验收边界

- 后端负责新的 entries 游标、稳定合并排序、`limit + 1` 的 has-more 判定、HTTP
  参数接线与离线回归。
- 前端只切换开单日志页到新的 entries 参数/字段并更新自检；借币日志、开单任务内的
  attempt 时间线和所有下单行为不改。
- 两个修复可并行，因为本文件已经冻结共享 seam（接缝）字段。
- 禁止真实网络、凭据读取、live、Start、真实 POST、WebSocket 或平滑开单代码。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/17-opening-log-pagination-compatibility.md
本地北京时间: 2026-07-24 17:34:20 CST
下一步模型: human operator
下一步任务: execute the bounded backend and frontend pagination repair packets after the bookkeeper checkpoint
