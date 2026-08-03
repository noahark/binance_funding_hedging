# 统一缓存刷新与面板新鲜度展示 v4（已批准实施）

状态：已批准进入 `2026-08-03-hedge-status-account-refresh-v1`。2026-08-03 的 Opus 5 独立计划评审只留下报价时间的事实性修正；Human 已明确确认该修正完成即接受计划，不要求额外复核。执行中 cache command 合并窗口按 Human 裁定保留为已知限制。作者：Codex / OpenAI。**本文不授权开闸、使用凭证、发单、部署或实盘操作**。

本文取代 `hedge-status-account-refresh-v3.md`，是本轮唯一拟议详细设计。v1、v2、v3 保留为讨论记录，不是实现依据。

基线：`main` `431d0d3d69eff7443f4ee19987fd253cf75e1175`。

---

## 1. 目标与边界

### 1.1 目标

既有约 60 秒 snapshot 后台刷新、右上角人工「更新缓存」按钮、开单任务离开 `running` 的状态钩子，共用**同一条** snapshot worker refresh cycle：

```text
约 60 秒 tick ─┐
人工「更新缓存」 ─┼→ 同一 worker refresh cycle → assemble → validate → publish
任务 running → 非 running ─┘
```

程序不猜测账户数据是否“足够新”，也不自动补救。它只发布每个账户源最后一次成功更新时间；操作者通过右上角的总览时间、各账户区域的数据源时间自行判断数据新鲜度。

### 1.2 本轮交付

1. 将 scheduled tick 的主体收敛为唯一 worker-only refresh-cycle helper。
2. 新增人工更新缓存的 POST 接口和相邻按钮；按钮等待本轮命令结束，随后复用现有 GET 刷新展示。
3. 任务真实 `running → 非 running` 后，在提交后提交同一个内部缓存刷新命令；不做自动前端重拉。
4. force 模式真实绕过账户面板 source TTL 和 private transport TTL。
5. 发布五个账户/估值源的独立成功更新时间；保留一个右上角总览时间，并在账户相关区域显示对应源时间。

### 1.3 不在本轮

- 不做任务状态变更后的自动页面刷新、轮询、SSE、WebSocket、跨 tab 同步或自动重试；
- 不改变 Start gate、订单、查单、借币、划转、风险限制、凭证或账户路由；
- 不新增第二份账户数据缓存、第二个 worker 或第二条 assemble/validate/publish 实现；
- 不强制 Group B、Group C、借币利率、抵押额度或完整市场历史刷新；它们仍遵守既有 due/TTL；
- 不修复既有 F4：UM 源本进程从未成功读取时，仍可能出现「交易所无仓」的旧显示限制。

---

## 2. 现状与约束

1. `SnapshotService` 的 background worker 是 domain cache 与 `PublishedState` 唯一写者；所有既有 GET 必须保持 zero-upstream pure read。
2. 既有 `_scheduled_tick()` 已按“刷新 due source → compose → Group C sweep → assemble → validate → publish”工作；本轮复用其完整后半段，不能复制组装管线。
3. 账户面板 Group A 的数据源为 `price_map`、`unified_balances`、`um_positions`、`spot_balances`，以及 capability 可用时的 `pm_account`。
4. 私有读取还有独立 PrivateClient transport TTL。只绕过 `_global_source_cache` 的 due 判断不足以得到新数据。
5. 既有 scheduled 路径允许部分 source 成功后发布混合 last-good 数据。本轮保持该语义：某源曾成功、后续读取失败时，页面继续使用旧值且其 source 时间不前进；只有进程内从未成功读取的 UM 才会落到空列表的既有限制。面板时间用于让操作者看见“旧数据仍在显示”，不把它伪装成 F4 的修复。

---

## 3. 唯一 refresh cycle

### 3.1 共用 helper

将 `_scheduled_tick()` 主体收敛为 worker-only：

```text
_run_refresh_cycle(*, force_account_panels: bool) -> RefreshResult
```

唯一顺序为：

```text
_refresh_due_sources(now, force_account_panels=...)
→ _compose_base_raw()
→ 既有 _eligible_rows / _sweep_group_c / _all_valid_history
→ _assemble（保留既有 funding-history overlay、collateral-cap projection）
→ _validate
→ _publish_validated
```

不得为按钮或状态钩子复制 `_assemble`、history overlay、校验或 publish；也不得误用单币 click 的 `forced_overrides`，它带有 private-reuse 语义。

### 3.2 两种调用模式

| 调用者 | `force_account_panels` | 行为 |
| --- | --- | --- |
| 约 60 秒 scheduled tick | `false` | 保持现状：所有 source 自己判断 due。 |
| 人工按钮 / 状态钩子 | `true` | 完整执行同一 cycle；仅账户面板组忽略 due 与 private transport TTL，其余 source 保持既有 due 行为。 |

原样调用今天的 `_scheduled_tick()` 不足够：账户 source 未 due 时会零读取，不能满足人工更新或任务结束后的实时缓存更新。唯一新增分支是账户面板的 due 判定；其他 source、组装和发布仍是同一实现。

### 3.3 force 的账户组

force 模式无条件尝试读取：

- 公开 `price_map`；
- 私有 `unified_balances`、`um_positions`、`spot_balances`；
- capability 可用时的私有 `pm_account`。

四个 PrivateClient fetcher 增加 `force=False` 关键字参数。`force=True` 仅以已有 `_evict` 删除 endpoint 的精确 transport-cache key，随后复用 GET-only whitelist、签名、审计及已有的受限 429 处理；严禁 `_cache.clear()`。

确定的新增成本为四个 signed GET 和一个公开 price GET。由于同一 cycle 仍运行既有 Group C，它会照现有各组件 TTL 推进 history cursor，并可能提前发起既有 history / borrow-rate / max-borrowable 请求；Human 明确接受该低频副作用，本轮不新增抑制逻辑。

### 3.4 `RefreshResult`：发布与账户刷新分开事实陈述

`RefreshResult` 是 command 的短生命周期结果，不是第二份 cache。它至少携带：

```text
published: bool
account_panels: complete | partial | not_attempted
```

- `complete`：本轮 force 下 `price_map`、`unified_balances`、`um_positions`、`spot_balances` 均成功，且 capability 存在时 `pm_account` 也成功；`price_map` 是估值数据，计入完整性；
- `partial`：账户组已尝试，但至少一个必需源未成功；
- `not_attempted`：private channel disabled、`classic_reference` 未就绪、worker 未运行，或该命令未实际走到账户面板读取；
- `published` 仅表达 snapshot 是否成功发布，绝不单独等价于账户数据已刷新。

既有 scheduled tick 不需要对外暴露该结果。人工按钮使用它如实提示；状态钩子只入队，不消费结果。

### 3.5 成功时间元数据

新增 worker-only 元数据 `source_checked_at`，只在一个账户/估值 source **成功取得并写入该 source cache**时更新为 UTC ISO-8601 时间；失败既不覆盖 last-good cache，也绝不推进时间；进程内未曾成功则为 `null`。

发布时，将下列只读元数据附入 `private_account.source_checked_at`：

```json
{
  "price_map": "2026-08-03T07:34:50Z",
  "unified_balances": "2026-08-03T07:34:50Z",
  "spot_balances": "2026-08-03T07:34:50Z",
  "um_positions": "2026-08-03T07:20:00Z",
  "pm_account": "2026-08-03T07:34:50Z"
}
```

这是固定形状：发布端总是输出以上五个 key，snapshot schema 将整个 object 列为 required，五个值的类型均为 `date-time | null`。`pm_account` capability 不存在时其值为 `null`，但 key 仍存在；`price_map` 即使不单独占一个账户区域，也必须保留，用于 complete 判断、估值时间和 partial 说明。`private_account.verified=false` 时也输出这个 object；`GET /hedge-open-positions` 的已有 `account` meta 同样透传完整 object。前端仅在对应账户区域可读时使用这些时间。

`private_account.checked_at` 与 `valuation.priced_at` 均保留既有兼容的账户聚合语义；它们只作为右上角的旧聚合总览时间，不得冒充某一账户源时间，更不得用于表示报价新鲜度。`price_map` 的成功时间唯一取自 `source_checked_at["price_map"]`，用于 partial 响应指出“报价源未更新”。

时间表示“本服务最近一次成功接纳该账户源结果的时间”，不是页面渲染时间、snapshot publish 时间，也不是 Binance 数据生效时间。

---

## 4. 命令队列与 60 秒任务

### 4.1 命令类型、完成信号与异常隔离

新增 `RefreshCacheCommand`，包含自己的 `done: Event`、`result: RefreshResult` 与固定 in-flight key。它与 `RefreshSymbolCommand` 共用 `_command_queue`，但类型、完成信号与清理逻辑互不混用：

```text
RefreshSymbolCommand → _handle_refresh_command
RefreshCacheCommand  → _run_refresh_cycle(force_account_panels=True)
None                 → stop sentinel
queue timeout        → _run_refresh_cycle(force_account_panels=False)
```

队列类型注解扩为两种 command 加 sentinel。symbol 专属的 `refresh_status`、`_release_inflight` 不得触碰 cache command。任一 command 异常都必须被类型安全地记录为该命令失败；worker 继续处理下一条命令。

### 4.2 简单排队与按钮去重

所有命令均由同一个 worker FIFO 串行处理，绝不并发调用上游。

- 状态钩子和人工按钮都提交 `RefreshCacheCommand`；
- 未完成的 cache command 存在时，新的人工按钮请求复用它，而不在队列中堆积多条；
- 状态变更发生在未完成 cache command 期间时，也复用该 command。这是 Human 接受的低频合并：若事件发生在该 command 的账户读取已经结束、但 command 尚未结束的短窗口内，它不会获得一条事件之后的额外读取，而是退回既有约 60 秒 tick 保证。人工点击命中同一窗口也只得到这条 command 的结果；页面显示实际 source 时间，不把它说成“本次点击之后读取”。
- 不使用 generation、tail refresh、按事件时间跳过或无限自排队。

force 成功后仍更新既有 account-panel source timestamp，所以下一个约 60 秒 tick 会自然跳过这组。若 scheduled tick 恰好先完成、随后才处理 force command，允许罕见的一轮重复读取；它不并发，也不自我重试。

---

## 5. 触发者与页面行为

### 5.1 人工「更新缓存」按钮

保留已有手动刷新按钮的 GET pure-read 含义，在右侧新增「更新缓存」按钮：

```text
POST /api/public-market/cache-refresh
```

HTTP handler 只提交或复用 `RefreshCacheCommand` 并有界等待其 `done`；不执行上游 I/O、不直接写 cache。新增独立的 `cache_refresh_timeout_seconds` 常量，避免与单币 click 的 timeout 耦合：

| 命令结果 | HTTP / 前端行为 |
| --- | --- |
| `published=true` 且 `account_panels=complete` | 提示“刷新周期已完成”；前端执行已有 `loadApi()` 与 `loadHedgePositions()`，随后恢复按钮，并以页面 source 时间作为实际读取证据。 |
| `published=true` 且 `account_panels=partial` | 提示“刷新周期已完成，但部分账户或估值源未更新（列出脱敏 source 名），请查看数据更新时间”；前端仍重读，以显示新旧时间；不得称账户缓存已完整更新。 |
| `published=true` 且 `account_panels=not_attempted` | 提示账户数据未刷新；前端可重读以展示已有时间，但不得显示成功。 |
| `published=false` / command failure | 明确失败，保留页面当前数据。 |
| 等待超时而 command 尚在排队或执行 | `202 queued`；取消 loading、提示仍在后台刷新；不新增自动轮询。 |

前端从点击开始置灰并显示 loading。`202`、失败或 command 结果处理完毕后恢复可点击状态。按钮只提供这一次人工同步；它不改变状态钩子的无前端联动原则。

该 POST 是 public-market 命名空间第一个写路由：它只有“入队或复用内部命令”的本地副作用，任何 Binance I/O 均只发生在 worker。新增 route、响应及 `private_account.source_checked_at` / positions account meta 的字段，必须同步记录在 `docs/api/public-market-contract.md` 与对应 JSON schema。

### 5.2 开单任务状态钩子

唯一触发真值：

```text
old_status == running && new_status != running
```

覆盖 `paused`、`done`、`stopped`、`deleted`、未来可写入的 `exposure_alert`；创建、恢复 running、同状态写入、写入失败均不触发。

Store 不 import SnapshotService，也不在锁内调用 callback。各 public mutator 在自己的 SQL 事务内读取 old status、完成写入，并在提交后向 service 返回附加的 `StatusTransition(old_status, new_status)`；保留原有 task / bool 等返回形状，避免不必要的全调用点替换：

| Store public 方法 | 内部状态写点 | service 提交后判断 |
| --- | --- | --- |
| `set_task_status` | HTTP pause / delete | returned old/new |
| `pause_task` | 任务内 pause | returned old/new；`paused → paused` 零触发 |
| `stop_task_fatal` | 致命预检 | returned old/new |
| `resolve_attempt` | `_apply_task_counters` | returned old/new |
| `finalize_attempt` | `_apply_task_counters` | returned old/new |
| `settle_attempt_no_counters` | `_apply_task_counters(skip_counters=True)` | returned 同状态，零触发 |

符合真值时，`HedgeOpenTaskService` 调用注入的 `submit_cache_refresh(wait=False)`；调用只入队或复用，吞掉异常，绝不回滚已经提交的任务状态。

状态钩子不调用 HTTP endpoint，也不模拟前端点击；它和按钮只共享内部 command 提交接口。它不会触发前端自动重读。

### 5.3 右上角总览与账户区域的新鲜度展示

API 一律传 UTC `Z` 时间，前端固定转换为北京时间（`Asia/Shanghai`），例如：

```text
资产更新时间 2026-08-03 15:34:50
```

现有 `#private-panel-subtitle` 不再保留在「私有账户」标题下。它移动到右上角 `#refresh-countdown` 的下一行，文案改为「账户资产更新时间」，仍读取兼容聚合字段 `private_account.checked_at`（无值时回退 `valuation.priced_at`）。它只表示旧有的账户总体快照时间，不能替代下面的 source 时间；两者文案不能相同。

各账户区域使用「数据源更新时间」这一不同文案：

| 区域 | 必需账户源 | 展示位置与时间 |
| --- | --- | --- |
| 统一账户余额 | `unified_balances` | 既有 `<h3>` 标题后：该源时间。 |
| 现货账户余额 | `spot_balances` | 既有 `<h3>` 标题后：该源时间。 |
| PM 账户字段 | `pm_account` | 在现有概览统计卡片区上方新增一行小字「PM 账户数据源更新时间」；只有 PM capability 可用时显示。它只描述 PM 字段，不声称整个概览区都来自 PM。 |
| 对冲开单持仓（UM 持仓为骨架） | `um_positions`、`unified_balances`、`spot_balances` | 既有 `<h3>` 标题后：三者中最早的时间。 |

多源区域仅在**所有必需源都有非 null 时间**时显示最早时间。单源为 null 时，显示「资产数据未就绪（该账户源未成功读取）」；多源任一必需源为 null 时，显示：

```text
资产数据未就绪（UM 持仓未成功读取）
```

不得把余下源的最早时间当成完整面板时间。可在标题下以小字列出各源时间，帮助操作者看出“余额新、UM 旧”的情况；不做程序自动判断或自动修复。`price_map` 不占账户标题，它的成功时间唯一通过 `source_checked_at["price_map"]` 与按钮 partial source 名可见；它失败时 `RefreshResult` 必为 `partial`。

---

## 6. 安全、限制与维护边界

- 新的上游读取仍全部通过现有 GET-only whitelist；没有签名 POST、订单或资金操作。
- 新 POST 只入队，GET 保持 pure-read；网络读取仍仅由 snapshot worker 执行。
- scheduled / force 的 partial-source 语义和 F4 既有限制保持；面板时间与按钮部分完成提示只提高可见性，不改变该限制。
- snapshot key 与 hedge key 是否同账户是既有 private_account 显示前提，记为 `pre-existing-independent`，不作为本 stage 新阻塞。
- 不记录密钥、签名、query、headers 或完整账户响应；日志仅允许固定 command 状态、账户组结果和脱敏失败 source 名。

---

## 7. 测试与验收

### 7.1 必测

1. scheduled (`force=false`) 保持 due/TTL；force command 在 domain 与 private transport cache 都新鲜时仍实际执行四个账户 signed GET 与一个公开价格 GET，且只 evict 精确 private key。
2. force cycle 不退化既有完整 assemble 输入：funding-history overlay、collateral-cap projection、Group C sweep 均保留。
3. 五个账户/估值 source 成功只推进自己的 `source_checked_at`；失败保留旧值及旧时间；从未成功为 null；PM capability 不存在时只允许 `pm_account=null`；`private_account.checked_at` 兼容行为不变。
4. `RefreshResult` 正确区分 publish 与 `complete` / `partial` / `not_attempted`；全部 source 失败、UM 单源失败、`price_map` 失败和 private disabled 均不得让按钮声称账户已完整更新。
5. cache command 有自己的 done/result；worker 正确分派两类命令，cache command 失败后 worker 仍可处理后续 symbol / cache command；worker 未运行时 POST 立即诚实失败。
6. 人工重复点击复用未完成 cache command；状态钩子在该命令期间复用它；覆盖“账户读取后、命令结束前”的已接受窗口：不加第二条读取，结果和页面 source 时间均如实呈现；无 FIFO 并发、无限自排队或 generation 机制。
7. 六个 §5.2 public mutator 对真实 `running → 非 running` 各触发一次；同状态、恢复 running、失败写入和 `settle_attempt_no_counters` 为零次。
8. POST 成功、partial、not_attempted、失败、queued timeout 的响应与按钮状态正确；GET `/snapshot`、`/hedge-open-positions` 仍零上游 I/O。
9. 前端：右上角显示旧聚合账户时间；私有账户标题下不再有同名时间；单源区域取本源时间，多源区域取必需源最早时间，任一 null 显示未就绪；PM 时间的 capability 隐藏规则及 UTC 到北京时间转换正确。
10. `source_checked_at` 的固定五 key 契约、schema、snapshot 和 positions account meta 一致；缺 schema 字段或错误 key 的发布在测试中必须校验失败，不能被 scheduled worker 静默掩盖；原有前端 self-check 回归通过。

### 7.2 完成标准

- 三个触发者仅共享一条 worker-only refresh cycle；
- 按钮以 cycle 完成、partial 或未尝试如实提示；`complete` 含价格表，不把同一 in-flight command 误说成点击之后的读取；
- 右上角显示旧聚合账户时间；账户区域显示自己依赖源的最后成功更新时间，缺源诚实显示未就绪；
- 任务状态变化不触发前端自动刷新；
- 无双缓存、双 worker、双 assemble/publish，无新增 Binance 写操作。

---

## 8. 给独立评审者的检查清单

1. 这是否真是一条 refresh cycle，仅 account-panel due 判定有 force 分支？
2. force 是否真实绕过 private transport TTL 且只 evict 精确 key？
3. Group C 游标推进与可能提前读取的成本是否写实并被明确接受？
4. `published` 与账户组 `complete` / `partial` / `not_attempted` 是否完全分离，按钮会不会撒谎？
5. `source_checked_at` 是否固定五 key、只表示源成功时间，且多源区域在缺源时不会编造完整时间？
6. cache command 的 Event、类型分派、异常隔离与 in-flight 复用是否能运行且不会杀死 worker？已接受的执行中合并窗口是否被准确陈述？
7. Store transition 是否提交后判断、保留现有返回形状，并穷尽所有状态写调用方？
8. POST route、契约、schema 与前端按钮是否一致，同时 GET 仍 pure-read？
9. 文稿是否诚实保留 F4（last-good 与冷启动的区别）、凭证前提、低频合并取舍和“无自动前端刷新”的边界？
