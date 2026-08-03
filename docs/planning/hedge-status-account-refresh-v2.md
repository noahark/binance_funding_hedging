# 开单任务离开 running 时刷新账户缓存 v2（后端-only，待独立计划评审）

状态：已被 `hedge-status-account-refresh-v3.md` 取代，2026-08-03。本稿保留为讨论记录；**不授权实现、开闸、使用凭证、发单、部署或实盘操作**。

本文取代 `hedge-status-account-refresh-v1.md` 作为拟议实现的详细设计。v1 保留为 Grok 初稿与讨论记录，不是本轮实现依据。

基线：评审时 `main` HEAD（当前 `431d0d3d69eff7443f4ee19987fd253cf75e1175`）。

---

## 1. 目标与边界

### 1.1 唯一目标

当任一开单任务在数据库中**实际成功**从 `running` 变成任意非 `running` 状态后，后端主动请求一次账户源数据刷新；刷新成功才组装、校验并发布新的 `PublishedState`。

这样，现有的下一次只读 `GET /api/public-market/snapshot` 或
`GET /api/hedge-open-positions` 会读到新缓存。**本轮不保证浏览器立刻重拉或立刻重绘。**

### 1.2 本轮包含

- 后端状态迁移的精确触发；
- snapshot worker 内账户源的真实强制读取、组装、校验与发布；
- 与既有约 60 秒 Group A 调度共用缓存和去重；
- 无网络 mock 测试。

### 1.3 本轮明确不包含

- 前端轮询、重试、页面刷新、WebSocket、SSE 或任何新的浏览器行为；
- 对外 refresh HTTP 接口；
- 开单状态机、Start gate、下单、查单、借币、划转或凭证配置改动；
- 强制刷新借币利率、抵押额度、经典参考表、公开行情或 `price_map`。

`price_map` 继续走既有调度。因此本轮保证余额、借款字段、UM 持仓和 PM 汇总是新读；不单独承诺估值价格的即时性。

---

## 2. 现状与问题

1. `SnapshotService` 的 background worker 是 domain cache 和 `PublishedState` 的唯一写者；HTTP GET 均为只读。这一边界必须保留。
2. Group A 账户源目前约 60 秒 due 后读取：`unified_balances`、`um_positions`、`spot_balances`、`pm_account`；其结果进入 `_global_source_cache`，再由 `_assemble` / `_validate` / `_publish_validated` 发布。
3. 私有读取还存在独立的 60 秒传输缓存。仅跳过 snapshot 的 due 检查，仍会得到旧数据；force 必须同时绕过该精确传输缓存。
4. 部分账户源失败时沿用普通 scheduled 路径直接发布，会重现已知 F4：UM 读取缺失却可能被页面解释为「交易所无仓」。本轮 force 不得制造这个错误结论。

---

## 3. 触发契约

### 3.1 触发真值

只在同一 SQLite 事务中确认的下列事实发生后触发：

```text
old_status == running && new_status != running
```

具体目标状态包括 `paused`、`done`、`stopped`、`deleted` 及未来可写入的 `exposure_alert`。

不触发创建即 `running`、恢复到 `running`、`running → running`、`paused → paused`、写入未命中或异常。

### 3.2 覆盖写路径

| 触点 | 覆盖的业务路径 |
| --- | --- |
| `set_task_status` | HTTP pause / delete |
| `pause_task` | 429、不足、抵押满、`order_state_unknown` 等任务内暂停 |
| `stop_task_fatal` | 致命预检停止 |
| `_apply_task_counters` | 结算产生的 done、阈值 pause、致命 stopped |

`settle_attempt_no_counters` 不改 task status，故不触发。

### 3.3 回调边界

`HedgeOpenStore` 增加一个可选、纯进程内的 status-transition callback。它在 SQL 事务**提交后且离开 store lock 后**携带 `(old_status, new_status)` 调用。

`HedgeOpenTaskService` 注册自己的薄包装：仅在 §3.1 成立时调用构造时注入的 `request_account_panels_refresh` callback，并吞掉 callback 任何异常。Store 不 import SnapshotService、不执行网络调用，也不持有 snapshot 引用。

这避免 service 在事务前读取陈旧 task 后错误判断，同时保证账户刷新故障绝不回滚或改变已提交的任务状态。

---

## 4. Snapshot 强制刷新命令

### 4.1 内部接口

`SnapshotService` 新增：

```text
request_account_panels_refresh() -> None
```

- 仅同进程调用；不新增 HTTP route；
- 非阻塞、不得向开单路径抛错；
- worker 未运行、private channel disabled，或尚无 `classic_reference` 时静默 no-op；
- 请求方不写 cache、不 publish。

新增 `RefreshAccountPanelsCommand`，与既有 `RefreshSymbolCommand` 使用同一个串行 queue。worker 是唯一执行账户 I/O、写 domain cache 和 publish 的主体。

### 4.2 合并规则：不漏事件，也不堆叠请求

维护受短锁保护的单调 `requested_generation`、`served_generation` 与 `command_outstanding`：

1. 每个合格状态迁移递增 `requested_generation`。
2. 没有 account command 在队列或执行中时，只入一个命令。
3. 命令开始时记录当前 generation 并执行一轮；在开始前到达的多个事件由这一轮共同覆盖。
4. 执行期间若有新事件，当前轮结束后把一个后续命令放到 queue **尾部**；不直接在 worker 内循环，避免饿死已排队的 symbol refresh。
5. 没有未服务 generation 时清除 `command_outstanding`。

这不是固定时间 debounce：首个事件立即获得排队机会。多个任务同时离开 `running` 可以共享一次真实读取；发生在读取中的新事件至少由后续一轮覆盖。

### 4.3 与 60 秒调度的去重

每个 account command 记录其入队的 `requested_monotonic`。worker 取到命令后，先检查四个账户源的 `_global_source_cache` 成功时间戳：

```text
unified_balances, um_positions, spot_balances, pm_account
```

若四项时间戳均不早于 `requested_monotonic`，说明既有 scheduled tick 已在事件之后完整刷新过该组；命令视为已覆盖，跳过账户 GET。

否则执行 force。force 成功后以同一完成时刻写回这四项 source timestamp，因此之后 scheduled tick 会视它们为未 due，约 60 秒内不会再读取。

两类工作共享同一 worker，绝不并发发请求。此规则处理「60 秒 tick 恰好先跑、状态事件随后入队」的重复读取窗口。

### 4.4 真正 force 的账户源

为 `PrivateClient` 增加下列形态：

```text
fetch_unified_balances(*, force=False)
fetch_um_positions(*, force=False)
fetch_spot_balances(*, force=False)
fetch_pm_account(*, force=False)
```

`force=True` 只通过已有 `_evict` 删除该 endpoint 的精确 transport-cache key，随后复用原来的 GET-only 白名单、签名、审计与 429 处理；禁止 `_cache.clear()`。

一次真实 force 最多四个 signed GET。它不调用任何 Binance 写接口。

### 4.5 原子成功与失败策略

worker 先在局部变量中读取四项账户源：

- **四项均成功**：以局部 overrides 组装 snapshot，完成 schema validate 后，再一次性写四项 domain cache、推进 `_account_checked_at`、发布 `PublishedState`。
- **任一项失败**：不写这四项 domain cache、不推进 `_account_checked_at`、不 publish；保留完整 last-good published state。仅记录脱敏的失败 source 名称。
- `base_raw` 不可用或 validate 失败：同样不写 domain cache、不 publish。

force 组装需要新增局部 override 参数或专用 helper；不得先改 `_global_source_cache` 再在验证失败时试图回滚。

这条 all-or-nothing 规则只约束**本新增 force 命令**，不改变既有 60 秒 scheduled 路径的语义；它防止本轮在交易刚结束时发布半套账户数据。

### 4.6 429 / 限流

- force 不增加自定义重试；仍只使用 PrivateClient 现有的受限 429 / `-1003` 处理。
- force 因 429 或其他读取失败时，按 §4.5 保留旧发布状态；不为同一失败自动立即补刷。
- 之后只由新的状态事件或既有 scheduled tick 再尝试。

因此正常场景中事件刷新是把下一次 Group A 读取提前，而不是在 60 秒读取之外再平行增加一组请求。

---

## 5. 运行前提与安全

1. `BINANCE_API_KEY` / `BINANCE_API_SECRET` 所读取的账户，必须与
   `BINANCE_HEDGE_API_KEY` / `BINANCE_HEDGE_API_SECRET` 的开单账户是同一个
   Binance 统一账户（可为同账户不同 read-only key）。否则刷新成功也可能读到另一账户。
2. 不记录密钥、签名、请求参数或完整账户响应；日志只允许固定事件名与失败 source。
3. 不改变 GET pure-read 契约、Start gate、订单、仓位或风险限制。

---

## 6. 测试与验收

### 6.1 必测

1. 四个 `force=True` 读取在 transport cache 已命中时仍各执行一次底层 signed GET；不影响其他 cache key。
2. §3.2 的四条写路径从 `running` 离开时各触发一次；所有非合格转移均为零次。
3. 四项读取成功后，`PublishedState.private_account` 和 `/hedge-open-positions` 的 account meta 使用新数据与新 `checked_at`。
4. 任一项（特别是 `um_positions`）失败时，published object/version、四项 domain cache 与 `checked_at` 全部保持原样。
5. 60 秒 tick 在事件后先完整成功时，account command 不再读取；force 先成功时，下一 tick 不因该组再次读取。
6. 多个同时事件合并；读取中到达的新事件在 queue 尾部补一轮，且不抢占已入队 symbol command。
7. private disabled、worker 未启动、base 未就绪、validate 失败和 429 均不影响任务状态写入。
8. 回归：`GET /snapshot` 与 `GET /hedge-open-positions` 不触发任何上游 I/O。

### 6.2 完成标准

- 每个真实 `running → 非 running` 事件，都在其后获得一轮成功发布或明确的安全降级；
- 成功发布不包含本轮读取失败导致的缺失 UM / 余额 / PM 数据；
- 无新 Binance 写请求、无对外 refresh API、无前端改动；
- 同时事件和 60 秒 tick 不产生并发账户读取或无意义重复读取。

---

## 7. 给独立评审者的检查清单

1. 四条写路径是否穷尽所有真实 `running → 非 running` 状态写入？
2. callback 是否确实在提交后、store lock 外调用，且 callback 故障不会影响状态迁移？
3. generation 合并是否会漏掉执行期间的新事件，或饿死 symbol command？
4. 60 秒 tick 覆盖判定是否按四个 source 的成功时间戳，而非模糊的全局时间？
5. `force=True` 是否绕过了 private transport TTL，且只删除精确 key？
6. all-or-nothing 是否阻止 UM 失败时发布「无仓」错觉？
7. 是否仍保持 GET pure-read、snapshot 单一写者、无签名写操作？
8. 账户读取凭证与开单账户一致性前提是否已由 Human 确认？

## 8. 需要 Human 裁定

唯一业务前提：用于 snapshot 私有读取的 key 与用于开单的 key 是否确定属于同一统一账户？

在该前提未确认前，本设计只能保证「刷新了 snapshot key 所属账户」，不能保证是开单实际发生的账户。
