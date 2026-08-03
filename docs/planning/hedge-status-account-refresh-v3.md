# 统一缓存刷新入口 v3（定时、手动、开单状态共用；待独立计划评审）

状态：已被 `hedge-status-account-refresh-v4.md` 取代，2026-08-03。本文保留为讨论记录；**不授权实现、开闸、使用凭证、发单、部署或实盘操作**。

本文取代 `hedge-status-account-refresh-v2.md`，是本轮唯一拟议详细设计。v1、v2 保留为讨论记录，不是实现依据。

基线：`main` `431d0d3d69eff7443f4ee19987fd253cf75e1175`。

---

## 1. 目标与边界

### 1.1 目标

把既有 snapshot 的约 60 秒后台刷新周期收敛为**唯一的缓存刷新管线**，并新增两个触发者：

```text
约 60 秒后台 tick ─┐
右上角「更新缓存」 ─┼→ 同一个 snapshot worker refresh cycle → assemble → validate → publish
开单任务离开 running ─┘
```

这样，后续缓存字段、错误处理、限流或发布问题只在这一条 refresh cycle 修改。

### 1.2 本轮交付

1. 既有 scheduled tick 改为调用一个共用 refresh-cycle helper；既有周期、TTL、组装与 publish 语义保持不变。
2. 增加右上角「更新缓存」按钮与固定 POST 接口；按钮可人工等待一轮刷新完成，再复用既有 GET 重读页面。
3. 每个真实 `running → 非 running` 的开单状态变更，在提交后把同一个刷新命令排入 snapshot worker。
4. 对账户面板源增加真实的 force 读取，使人工按钮和状态钩子不受约 60 秒账户缓存限制。

### 1.3 不在本轮

- 不做状态变更后的自动前端重拉、轮询、SSE、WebSocket 或跨 tab 同步；
- 不改变 Start gate、订单、查单、借币、划转、风险限制、凭证或账户路由；
- 不新增另一份账户缓存、第二个 worker 或第二条组装/发布管线；
- 不强制 Group B、Group C、借币利率、抵押额度或完整市场历史刷新；它们仍按既有 TTL 调度。

---

## 2. 现状与设计约束

1. `SnapshotService` 的 background worker 是 domain cache 和 `PublishedState` 的唯一写者；`GET /snapshot` 与 `GET /hedge-open-positions` 必须继续 pure read。
2. 既有 `_scheduled_tick()` 依次执行：刷新 due source、从 cache 组成 base、Group C 的既有 sweep、assemble、validate、publish。
3. Group A 账户面板包含 `price_map`、`unified_balances`、`um_positions`、`spot_balances` 及可选 `pm_account`。
4. 私有账户读取在 source TTL 外还有独立的 PrivateClient transport TTL；若不精确绕过它，按钮和状态钩子会重新读到旧数据。
5. 既有 scheduled 路径的部分源失败语义不在本轮改动；特别是已记录的 F4（UM 读取缺失可能显示为「交易所无仓」）仍是既有接受限制。本轮不承诺修复它，也不得把它描述成已解决。

---

## 3. 一个刷新周期，两个调用模式

### 3.1 共用入口

将 `_scheduled_tick()` 的主体收敛为内部 worker-only helper：

```text
_run_refresh_cycle(*, force_account_panels: bool) -> RefreshResult
```

它始终执行同一套顺序：

```text
_refresh_due_sources(now, force_account_panels=...)
→ _compose_base_raw()
→ 既有 _eligible_rows / _sweep_group_c / _all_valid_history
→ _assemble(... funding_history_overlay=..., collateral_cap_state=既有路径)
→ _validate
→ _publish_validated
```

不得为按钮或任务状态复制 `_assemble`、Group C overlay、校验或发布代码；也不得误用 `RefreshSymbolCommand` 的 `forced_overrides`，后者是单币 click 的 private-reuse 语义。

### 3.2 两个模式

| 调用者 | `force_account_panels` | 行为 |
| --- | --- | --- |
| 约 60 秒 scheduled tick | `false` | 与当前实现相同：全部 source 依自己的 TTL 判断是否 due。 |
| 人工按钮 / 状态钩子 | `true` | 完整执行同一 refresh cycle；仅账户面板组忽略 due 和 private transport TTL，其他 source 仍遵守现有 TTL。 |

这不是“调用完整 `_scheduled_tick()` 原样运行”：原样运行在账户数据尚未 due 时可能零读取，无法满足人工或任务结束后的即时更新。唯一新增分支是账户面板的 due 判定；其后面的组装、校验、发布和其他 source 行为全部共用。

### 3.3 force 的源范围

`force_account_panels=true` 时，本轮无条件读取：

- 公开 `price_map`；
- 私有 `unified_balances`；
- 私有 `um_positions`；
- 私有 `spot_balances`；
- 私有 `pm_account`（沿用既有 capability check）。

`PrivateClient` 的四个账户 fetcher 增加 `force=False` 关键字参数。`force=True` 只调用已有 `_evict` 删除**该 endpoint 的精确 transport-cache key**，随后走既有 GET-only whitelist、签名、审计和 429 处理；严禁 `_cache.clear()`。

一次 force 最多增加四个 signed GET 和一个既有公开 price GET，不产生 Binance 写请求。

### 3.4 时间戳和发布顺序

本设计复用既有 scheduled 管线：账户源成功写入 `_global_source_cache` 后，在同一 refresh cycle 内推进 `_account_checked_at`，之后才 assemble。因此本轮组装读到的就是新的 `checked_at`，不需要第二份时间状态或延迟到下一 tick。

validate 失败时，PublishedState 按既有规则保持 last-good；source cache 的成功写入也保持既有 scheduled 行为，不在 force 模式另造回滚语义。

---

## 4. 命令队列与 60 秒任务

### 4.1 命令类型与分派

新增 `RefreshCacheCommand`，与既有 `RefreshSymbolCommand` 共用 `_command_queue`。队列元素类型须扩为这两种 command（另加 stop sentinel），worker 按类型显式分派：

```text
RefreshSymbolCommand → _handle_refresh_command
RefreshCacheCommand  → _run_refresh_cycle(force_account_panels=True)
None                 → stop sentinel
queue timeout        → _run_refresh_cycle(force_account_panels=False)
```

symbol command 专属的 `done`、`refresh_status`、`_release_inflight` 收尾不得用于 cache command。任一种 command 内部异常不得杀死 worker；worker 必须继续处理下一条命令。

### 4.2 排队原则

采用简单 FIFO，不使用 v2 的 generation、tail refresh、按事件时间戳去重或“scheduled tick 已覆盖则跳过”优化。

- 每个真实状态离开 `running` 的事件排入一个 cache command；
- 每次人工按钮点击排入一个 cache command；
- 同一 worker 顺序处理，绝不并发读取；
- 已在队列中的 symbol refresh 与 cache refresh 按先到先服务，前后脚发生只会互相等待，不会互相污染。

这是 Human 明确接受的低频、可预期成本。若未来观察到队列堆积或 429，再基于真实证据增加合并规则；本轮不预设复杂优化。

### 4.3 与 scheduled tick 的关系

force 成功后更新的仍是既有 account-panel source timestamp。下一次约 60 秒 tick 因 source 未 due 而自然跳过该组。

若 scheduled tick 恰好先执行、随后才轮到 force command，则允许罕见的一轮重复账户读取；这比 v2 的跨时间戳优化简单，且不发生并发。

force 不新增 429 重试或自我重排。读取失败时沿用 PrivateClient 既有受限处理；下一次尝试仅来自新的按钮点击、状态事件或 scheduled tick。

---

## 5. 两个新增触发者

### 5.1 右上角「更新缓存」按钮

保留既有“手动刷新”按钮的 GET pure-read 语义，新增相邻的「更新缓存」按钮。

按钮只调用固定接口：

```text
POST /api/public-market/cache-refresh
```

HTTP handler 不执行上游 I/O、不写 cache；它创建 `RefreshCacheCommand` 并等待该命令在既有 `symbol_refresh_timeout_seconds` 的有界时间内完成：

- worker 成功 publish：返回成功；前端随后复用 `loadApi()` 与 `loadHedgePositions()` 显示新缓存；
- worker 刷新失败或 validate 未 publish：返回明确失败，前端保留当前页面，不伪装成刷新成功；
- 命令尚在排队而等待超时：返回 `202 queued`，前端只提示“缓存更新仍在排队”，不新增自动轮询。

按钮点击期间前端禁用该按钮，防止单一用户的重复点击。该按钮是人工操作后的有限同步，不改变任务状态变化后的自动前端行为。

### 5.2 开单任务状态钩子

唯一触发真值：

```text
old_status == running && new_status != running
```

覆盖 `paused`、`done`、`stopped`、`deleted` 和未来可写入的 `exposure_alert`；不覆盖创建/恢复到 running、同状态写入或写入失败。

Store 不 import SnapshotService，也不在锁内调用 callback。相关 public store 方法在自己的 SQL 事务内读取 old status、执行写入，并在**提交后**返回精确的 `StatusTransition(old_status, new_status, task)` 给 service：

| Store public 方法 | 内部状态写点 | 提交后的 service 观察 |
| --- | --- | --- |
| `set_task_status` | HTTP pause / delete | 比较 returned old/new |
| `pause_task` | 任务内 pause | 比较 returned old/new；`paused → paused` 为零触发 |
| `stop_task_fatal` | 致命预检 | 比较 returned old/new |
| `resolve_attempt` | `_apply_task_counters` | 比较 returned old/new |
| `finalize_attempt` | `_apply_task_counters` | 比较 returned old/new |
| `settle_attempt_no_counters` | `_apply_task_counters(skip_counters=True)` | 返回同状态，零触发 |

当且仅当该 returned transition 符合真值时，`HedgeOpenTaskService` 调用注入的 `request_cache_refresh(wait=False)`。这个调用只入队、吞掉异常；已经提交的任务状态绝不因刷新失败而回滚。

状态钩子不调用 HTTP endpoint，也不模拟点击前端按钮；它和按钮共享的是同一个内部 `RefreshCacheCommand` 提交接口。

---

## 6. 安全、限制与维护边界

- 所有新上游调用仍是现有 PrivateClient 的签名 GET 白名单；没有签名 POST、订单或资金操作。
- `GET /snapshot`、`GET /hedge-open-positions` 与既有手动刷新按钮继续 zero-upstream pure read。
- 本轮保留既有 partial-source scheduled 行为及 F4 已知限制；force 模式并不声称治愈该问题。
- snapshot key 与 hedge key 是否同账户是既有 private_account 显示前提，按 `pre-existing-independent` 记录，不作为本 stage 新阻塞。
- 运行期间不记录密钥、签名、完整账户数据、请求 query 或 headers；日志仅允许固定 command 状态和脱敏错误类别。

---

## 7. 测试与验收

### 7.1 必测

1. scheduled tick (`force=false`) 保持既有 due/TTL 行为；cache command (`force=true`) 在 source 与 PrivateClient transport cache 都新鲜时，仍实际执行四个账户 signed GET。
2. `force=true` 只删除四个精确 transport key，不影响其他 key，且永不调用 `_cache.clear()`。
3. force cycle publish 的 `private_account.checked_at` 是本轮新的值；同一周期保持 funding-history overlay、collateral-cap projection 及既有 assemble 输入，不退化完整 snapshot。
4. worker 显式分派两类命令；cache command 不进入 symbol handler；cache command 失败后 worker 存活并可处理随后 symbol / cache command。
5. FIFO：状态事件和人工按钮各自排入一条命令；与 symbol command 前后相邻时按队列顺序完成，无并发。
6. 五个 §5.2 真实状态写路径在 `running → 非 running` 时各触发一次；`running → running`、`paused → paused`、恢复 running、失败写入与 `settle_attempt_no_counters` 均零次。
7. refresh 出错、429、private disabled、worker 未启动、base 未就绪、validate 失败时，状态变更仍成功且不抛到 API。
8. POST cache-refresh 成功、失败、queued timeout 三种响应正确；GET endpoints 回归为零上游 I/O。

### 7.2 完成标准

- 60 秒、人工按钮、状态钩子使用同一 worker-only refresh cycle；
- 人工按钮和状态钩子真实绕过账户面板 TTL，下一次 GET 能读取已发布的新 cache；
- scheduled tick 不因 force 后的账户 source 再次 due；
- 无新增订单/资金写操作，无双缓存、双 worker、双 assemble/publish 实现；
- 不实现状态变化后的前端自动刷新。

---

## 8. 给独立评审者的检查清单

1. force 是否仅改 account-panel due 判定，其余工作是否仍复用 scheduled cycle？
2. PrivateClient force 是否真的绕过 transport TTL，并只 evict 精确 key？
3. source 成功时间、`checked_at` 与本轮 publish 的顺序是否一致？
4. cache command 的 worker 分派与异常收尾是否类型安全？
5. FIFO 是否足够表达本轮的低频成本假设，且没有隐藏的无限重试？
6. Store 返回的 transition 是否在提交后由 service 判断，且穷尽所有公共调用方？
7. 手动按钮是否只走 POST command，状态钩子是否避免经 HTTP 回环？
8. 文稿是否诚实保留 F4、凭证同账户和“无自动前端刷新”的既有限制？
