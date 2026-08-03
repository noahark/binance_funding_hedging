# 开单任务离 running 触发账户面板强制刷新 v1（待独立方案评审）

状态：已被 `hedge-status-account-refresh-v2.md` 取代，2026-08-03。本稿保留为 Grok 初稿与讨论记录；**尚未授权改动、开闸、使用凭证或发单**。

修订史：

- 初稿（Grok）：基于现状代码与 Human 产品裁定整理，供跨 provider 计划评审。

**作者身份提示：本稿由 Grok 落笔。后续的跨 provider 计划评审必须由其他 provider 执行（AGENTS.md §3.4 / §8 计划评审）。**

基线：以评审时 `main` HEAD 为准；本文引用的模块与行为以当前 as-built 代码为证据，不依赖未合并分支。

---

## 1. 目标与边界

### 1.1 要解决的问题

开单任务（`hedge-open-tasks`）在 `status=running` 期间会提交现货 + UM 对冲腿。任务状态一旦离开 `running`（人工暂停/删除，或 worker 自动完成/暂停/致命终止），操作者需要**尽快**在 UI 上看到：

- 统一账户（PAPI）余额与借款相关字段  
- 经典现货账户余额  
- UM 持仓  

今日这些字段只来自 snapshot 后台 worker 的 **Group A 账户面板**（默认约 60s 到期才拉），经 `PublishedState.private_account` 发布后，由：

- `GET /api/public-market/snapshot`（主页面余额/私有面板）  
- `GET /api/hedge-open-positions`（开单持仓表：任务记账 ∪ `private_account`）  

只读消费。**主页面「手动刷新」仅再 GET 已发布快照，不触发上游账户拉取。**

结果：成交已发生，页面仍可能展示最多约 60s 的旧账户视图；worker 自动改状态时前端甚至没有立刻重拉持仓的路径。

### 1.2 产品裁定（Human）

1. **触发策略**：任务 `status` 从 `running` 变为**任意其他状态**时，触发一次账户面板强制刷新。  
   理由：任意离 `running` 的迁移都**可能**伴随仓位成交或余额变动（成功完成、单腿、fatal、手动暂停/删除时在途腿 drain 后结算等）。  
2. **不复用**主页面手动刷新按钮 / `GET /snapshot` / `symbol-snapshot` 作为「主动更新」通道（语义不符，见 §2）。  
3. 目标是操作者**下单后尽快看到数据变化**，因此除后端变新外，必须有前端重读联动（§5）。

### 1.3 本轮交付

| 部分 | 内容 |
|------|------|
| **A · 后端 force 入口** | `SnapshotService` 新增「强制刷新账户面板 + 组装 + publish」命令；复用现有 PrivateClient / 源缓存 / assemble / publish，不新建第二套账户模型。 |
| **B · 开单挂钩** | 所有 `running → 非 running` 的写库路径统一挂钩，触发 A（带 debounce）。 |
| **C · 前端联动** | 用户操作路径加强；worker 自动改状态路径增加检测并重拉持仓（及可选主快照）。 |

### 1.4 不在本轮

- 不改变开单状态机词汇、`pause_reason` / `stop_reason` 集合、结算计数语义。  
- 不改变 Start gate、凭证、执行器模式、下单/查单路径。  
- 不新增 WebSocket / SSE 推送总线。  
- 不把 `GET /api/public-market/snapshot` 或手动刷新改为带副作用的 force-refresh。  
- 不强制刷新 Group B（借币利率链、`account_info` 等）与抵押额度展示源（`restricted_asset`）；与「成交后看仓位/余额」无关。  
- 不新增开单专用第二份 `private_account` 缓存。  
- 不做平仓、划转、自动对账修复、多进程水平扩展下的全局 debouncer。  
- 不在本轮做实盘发单验证（实现后的只读 smoke 另列验收；live 操作仍须 Human 单独授权）。

---

## 2. 现状证据（as-built）

### 2.1 状态写出口（开单）

权威状态：`backend/hedge_open_tasks/domain.py`  
`running | paused | done | stopped | deleted | exposure_alert`  
（`exposure_alert` 为死状态：当前无写入路径，本方案不复活。）

| 写路径 | 典型 `running →` | 实现 |
|--------|------------------|------|
| 人工 pause | `paused` | `service.post_pause` → `store.set_task_status` |
| 人工 delete | `deleted` | `service.post_delete` → `store.set_task_status` |
| 任务内暂停（429 / 不足 / 抵押满 / order_state_unknown） | `paused` | `service._pause_task_local` → `store.pause_task`（条件写：仅 `running\|paused`） |
| 预检致命 | `stopped` | `service._stop_task_fatal_preflight` → `store.stop_task_fatal` |
| 结算致命 / 连续失败达阈值 / 达标 done / 计划组用尽 done | `stopped` / `paused` / `done` | `store._apply_task_counters`（`finalize_attempt` / `resolve_attempt`） |

粘性：`deleted` / 已 `done` / 已 `stopped` 不会被 stale pause/stop 复活（条件写 + 结算内 `resolve_status_after_attempt`）。

### 2.2 账户数据真源

| 源 ID | 上游 | 调度 |
|-------|------|------|
| `unified_balances` | private E3 族 | Group A，`cache_ttl_seconds`（默认 60s）due 才拉 |
| `um_positions` | private E4 | 同上 |
| `spot_balances` | private E6 | 同上 |
| （可选）`price_map` | 公开 ticker | 同组，估值用 |

写入：`SnapshotService._refresh_due_sources` → `_global_source_cache`。  
组装：`_gather_private_inputs_scheduled` → `assemble_private_account` → `_assemble`。  
发布：`_publish_validated` → `PublishedState`（原子替换）。

架构红线（`snapshot_service` 文件头）：

- Live：**仅**串行 background worker 可写 domain cache / publish。  
- 请求线程只读，或提交 one-shot 命令（现有：`RefreshSymbolCommand`）。  
- 开单 worker **不得**直接写 `_global_source_cache`。

### 2.3 现有「刷新」入口为何不可当 force

| 入口 | 行为 | 能否强制账户更新 |
|------|------|------------------|
| 前端「手动刷新」→ `GET /snapshot` | pure read 已发布状态 | 否 |
| `GET /symbol-snapshot` | 点选刷新费率/借币相关；**复用** last `private_account` | 否（契约禁止点选重拉余额/持仓） |
| `GET /hedge-open-positions` | 任务桶 + 已发布 `private_account` 合并 | 否 |
| 后台 60s tick | due 才拉面板 | 被动，非事件驱动 |

### 2.4 前端持仓重读时机（今日）

| 时机 | `loadHedgePositions` |
|------|----------------------|
| `mutateHedgeTask`（pause/start/delete/fill-*）成功后 | 是 |
| 主快照 60s tick 且当前在开单页 | 是 |
| 进入开单页 | 是 |
| worker 自动 `done` / 阈值暂停 / 429 暂停 / fatal `stopped` | **否（无即时路径）** |

无推送；状态变化靠轮询或用户操作后的 GET。

---

## 3. 方案总览

```text
开单写状态：running → 其他
        │
        ▼
  request_account_panels_refresh()   ← SnapshotService 新薄入口（命令入队）
        │
        ▼
  snapshot 串行 worker（与现有 tick / symbol-command 同队列）
        │
        ├─ 无条件 fetch：unified / um / spot（+ 可选 price_map）
        ├─ 写入 _global_source_cache + _account_checked_at
        ├─ _assemble（cache-only 拼全量 snapshot，private 用新面板）
        ├─ schema validate
        └─ _publish_validated  →  PublishedState.private_account 更新

前端：
  · 用户 mutate 后：loadHedgePositions（+ checked_at 重试）
  · worker 改状态：开单页检测 running→* 后 loadHedgePositions
  · 可选：loadApi() 同步主页面余额面板
```

**原则：复用拉数/组装/发布；新建唯一合法 force 入口；publish 必须发生，否则对外 GET 仍读旧态。**

---

## 4. 后端设计

### 4.1 新入口（复用管线，不新键第二缓存）

在 `SnapshotService` 增加内部/同进程可调用 API（名称可实现时微调，语义固定）：

```text
request_account_panels_refresh(*, reason: str) -> None
```

语义：

1. **非阻塞**（对开单热路径）：将命令放入 snapshot 串行 worker 队列后立即返回。  
2. Worker 处理时执行 **force 一轮**账户面板刷新（忽略 due/TTL）。  
3. 刷新成功后执行与 `_scheduled_tick` 后半段等价的 **assemble + validate + publish**（可用「仅账户脏」的轻量组装，但必须更新 `PublishedState.private_account` 与顶层相关字段；不得只写 cache 不 publish）。  
4. 任一面板 fetch 失败：该 source 不推进成功时间戳（对齐 FR-2）；其余成功源仍可写入；assemble 使用 last-good 混合规则与今日 scheduled 路径一致（失败源保持旧 cache 或空，由现有 `assemble_private_account` 三态处理）。  
5. private channel 关闭 / offline / 无 classic_ref：**no-op 成功**（不报错拖垮开单），可选记 debug 级原因。  
6. `reason` 仅用于日志/诊断（如 `hedge_status:running_to_paused`），不进 wire 契约。

#### 4.1.1 复用清单

| 复用 | 说明 |
|------|------|
| `PrivateClient.fetch_unified_balances` 等 | 现有白名单签名 GET |
| `_global_source_cache` | 同一源 ID，不新增 key 名空间（除非实现需要内部 command 队列结构） |
| `assemble_private_account` / `_assemble` / `_validate` / `_publish_validated` | 与 tick 同源 |
| 串行 worker 队列模式 | 对齐 `RefreshSymbolCommand` 的「请求方入队、worker 独占写」 |

#### 4.1.2 明确不复用

| 不复用 | 原因 |
|--------|------|
| `get_snapshot` / HTTP GET snapshot | pure read |
| `get_symbol_snapshot` / click 路径 | 契约：不重拉 private_account |
| 开单 executor / live hedge client | 执行与只读通道隔离 |
| 修改 `cache_ttl_seconds` 全局为更短 | 用事件驱动 force，不改变常态权重 |

### 4.2 Debounce / 合并

多任务同时离 `running`、或同一任务短时间多次写状态时：

- 进程内 **debounce 窗口默认 1.0s**（实现常量，可配置但本轮可不暴露 env）。  
- 窗口内多次 `request_account_panels_refresh` **合并为一次** worker 执行。  
- 窗口结束后若仍有 pending，再跑一轮（尾触发），保证最后一次迁移后仍会刷。  
- 单次 force 在飞时：新请求只置 pending 标志，结束后若 pending 再跑一次（避免并行双 fetch）。

目的：保护 private 权重与 snapshot worker 延迟，而非限制产品语义。

### 4.3 开单挂钩点（必须穷举）

**目标：**凡使 `status` 从 `running` 变为其他值的成功写库，都调用一次 `request_account_panels_refresh`。  
**禁止：**在每个业务分支复制粘贴一长段 refresh 逻辑；应在**写库成功且 old→new 跨越 running 边界**的单点辅助函数中调用。

推荐形状（示意）：

```text
def _notify_status_left_running(old_status, new_status, *, reason: str) -> None:
    if old_status == STATUS_RUNNING and new_status != STATUS_RUNNING:
        snapshot_service.request_account_panels_refresh(reason=reason)
```

挂钩位置（实现时以 code search 复核，下列为权威清单草案）：

| # | 位置 | 备注 |
|---|------|------|
| H1 | `store.set_task_status` | 覆盖 post_pause / post_delete；若 start 把状态设回 running **不**触发 |
| H2 | `store.pause_task` | 仅当 `applied=True` 且更新前为 running（条件写命中） |
| H3 | `store.stop_task_fatal` | 仅当 rowcount>0 且更新前为 running |
| H4 | `store._apply_task_counters` | 当 `task["status"]==running` 且 `new_status!=running`（含 fatal/阈值 pause/done） |

注意：

- `settle_attempt_no_counters`（429 结算）**不改 status**；暂停已由 H2 覆盖。  
- `preflight_incomplete` / start_gate_off / worker_exit **不改 status** → **不触发**（符合「仅 status 离 running」）。  
- 创建任务直接为 running：**不触发**。  
- `running → running`（幂等 set）：**不触发**。

依赖注入：`HedgeOpenService` 持有可选 `SnapshotService` 引用或 callback；store 层宜通过 **service 在写后观察** 或 **store 回调**，避免 store 直接 import 网络栈。优先：

1. Service 在 `post_pause` / `post_delete` / `_pause_task_local` / `_stop_task_fatal_preflight` 写后调用；**且**  
2. 结算路径在 `finalize_attempt` / resolve 返回后由 service 比较前后 status；**或**  
3. store 返回 `(task, status_changed_from_running: bool)`  

评审要求：**不得漏掉 `_apply_task_counters` 内的 done/threshold pause/fatal**（这些不经过 post_*）。

### 4.4 与 snapshot worker 的并发

- 开单 worker 与 snapshot worker 并行：force 命令只入队，不阻塞开单 drain（除 debounce 外）。  
- publish 与 GET 读者：保持现有原子引用替换；读者永远完整旧态或完整新态。  
- 不在 force 路径持有 hedge store 锁。

### 4.5 契约与 HTTP

本轮 **不新增** 对外 force-refresh HTTP（除非评审后 Human 要求调试口）。  
`public-market-contract.md`：**不改变** `GET /snapshot` pure-read 语义。  
可选后续（非本轮）：运维用 `POST /api/.../account-panels/refresh`，需单独授权与鉴权讨论。

若实现选择暴露内部 `checked_at` 已有字段：前端用 `account.checked_at`（positions 响应里已有 `account` meta）判断是否已推进；**不新增** wire 字段亦可完成 §5 重试（比较操作前缓存的 `checked_at`）。

### 4.6 失败与降级

| 情况 | 行为 |
|------|------|
| private 关闭 / 无 key | no-op |
| 部分面板 5xx/超时 | 成功源更新；失败源保留 last-good；publish 仍可进行；`verified` 逻辑跟现网 assemble |
| snapshot worker 未启动 | 命令丢弃或记一次 warning；不得抛穿到开单 API 500 |
| assemble/validate 失败 | **不**替换 PublishedState（对齐 tick：validate 失败不动 last-good） |

开单状态迁移 **不因** refresh 失败而回滚。

---

## 5. 前端设计

### 5.1 目标

后端 publish 变新后，操作者在开单页（及可选主页面私有面板）**主动再拉一次**，无需傻等 60s tick。

### 5.2 用户操作路径（已有 + 加强）

`mutateHedgeTask` 已在成功后调用 `loadHedgeTasks` + `loadHedgePositions` + `loadHedgeAttempts`。

加强：

1. 记录 mutate 前的 `state.hedgeAccountMeta.checked_at`（若有）。  
2. `await loadHedgePositions()`。  
3. 若新 `checked_at` 未变（仍等于操作前）且 private 预期可用：在 **300–800ms** 后再拉 1–2 次（应对 force 异步未完成的竞态）。  
4. 重试用尽仍旧：保留展示，不报错打断（账户刷新失败不应伪装成任务失败）。

可选：同路径调用一次 `loadApi()`，使主页面余额面板同步；**默认建议：仅当 `activeView === 'market'` 或私有面板可见时**再 `loadApi`，避免开单页每次 pause 都打全量 snapshot。开单持仓表只依赖 positions 即可。

### 5.3 Worker 自动改状态路径（新增）

无推送前提下，最小方案：

- 当开单页激活 **且**（存在 `status===running` 的任务 **或** 最近一次列表中曾有 running 刚消失）时，启用 **短轮询** `loadHedgeTasks`（建议间隔 **3s**，上限可讨论 2–5s）。  
- 比较前后任务 map：`id → status`。若任一 id 满足 `prev===running && next!==running`：  
  - 立即 `loadHedgePositions()`（同样可带 checked_at 短重试）；  
  - 取消「仅有 running 才轮询」时，在触发后再保持一轮 3s 轮询以免漏掉 publish 竞态。  
- 无 running 且无 pending 迁移观察时：**停止**短轮询，回到仅 60s 主 tick 顺带刷新。  
- 短轮询 **不是**执行时钟；注释须写明与 §3.11 显示刷新策略一致。

替代方案（若评审更偏好）：不在前端轮询，而在任务列表/日志 API 增加 `account_refresh_generation`——本轮不采用，避免扩契约。

### 5.4 明确不改

- 不修改手动刷新按钮语义（仍只 `loadApi` → GET snapshot）。  
- 不把 force 伪装成用户点击手动刷新。  
- 不为账户刷新新增独立导航页。

---

## 6. 时序与竞态

### 6.1 期望时序（人工 pause）

```text
T0  POST .../pause → status=paused，入队 force（debounce）
T0  响应 200 Task
T0+ 前端 loadHedgePositions  → 可能仍旧 private_account
T0+1s worker force fetch+publish
T0+1.3s 前端重试 loadHedgePositions → 新 checked_at / 新仓位余额
```

### 6.2 期望时序（worker 达 done）

```text
T0  finalize → status=done，入队 force
T0+ 短轮询 loadHedgeTasks 发现 running→done
T0+  loadHedgePositions（+ 重试）
```

### 6.3 交易所可见性

Binance 侧极短延迟可能导致 force 仍读到旧仓位。本轮：

- **不**做复杂对账循环；  
- 依赖 debounce 尾触发 + 前端 1–2 次重试；  
- 若仍旧，操作者可等待下一次 60s tick 或再次手动 GET（仍只读；若需再 force，下一次离 running 事件才会再触发——**运行中多次成交但保持 running 不在本触发集合内**，见 §7 已知限制）。

---

## 7. 已知限制与接受项

| ID | 限制 | 处理 |
|----|------|------|
| L1 | **保持 `running` 的中间成交**（未达 target）不触发本方案 | Human 已选「仅离 running」；中间成交仍靠 60s tick。若实盘后不够用，另开「pair 结算成功也 refresh」修订，不在本轮偷偷扩大。 |
| L2 | 无多 tab / 多浏览器推送 | 每客户端自管轮询；可接受 |
| L3 | force 与 60s tick 重叠可能多打一轮 private GET | debounce + 串行 worker 可接受 |
| L4 | `exposure_alert` 死状态 | 不写入则不触发；不复活 |
| L5 | 删除任务后持仓表仍可能显示历史桶 + 新账户 | 既有 D15 语义；本方案只刷新账户侧 |
| L6 | 前端短轮询增加 `GET /hedge-open-tasks` 频率 | 仅开单页 + 有 running 时；只读、无执行副作用 |

---

## 8. 安全与权重

- 仅签名 **GET** 白名单路径；不引入新 POST 到 Binance。  
- 不在日志打印密钥、完整账户 JSON 可按现网脱敏级别。  
- 权重：账户三件套按现网 E3/E4/E6；debounce 合并是主要保护。  
- 与开单查单 500ms cadence 并存：force 走 snapshot worker，不挤占开单 store 锁。  
- Start gate / live 发单权限：**本方案只读**，不放宽任何执行闸门。

---

## 9. 测试计划

### 9.1 后端单测

1. `request_account_panels_refresh`：mock PrivateClient，断言三源写入 cache 且 publish 后 `get_snapshot().private_account.checked_at` 推进。  
2. private 关闭：no-op，不抛。  
3. validate 失败：PublishedState 不变。  
4. debounce：窗口内 N 次请求只产生 1 次 fetch（或 1+尾 1）。  
5. 挂钩：  
   - `set_task_status(running→paused)` 调用 refresh；  
   - `running→running` 不调用；  
   - `pause_task` applied 自 running 调用；  
   - `_apply_task_counters` 导致 done / threshold pause / fatal 调用；  
   - `settle_attempt_no_counters` 不调用。  
6. 开单 API 在 refresh 抛错时仍 200（pause/delete）。

### 9.2 前端 self-check

1. `mutateHedgeTask` 成功后仍调用 positions；mock 第一次旧 `checked_at`、第二次新，断言重试。  
2. 任务列表轮询模拟 `running→done` 触发 `loadHedgePositions`。  
3. 无 running 时不启动短轮询（或启动后停止）。

### 9.3 不测 / 另授

- 实盘下单后肉眼确认：需 Human 授权与只读/受控环境。  
- 不在本轮改 contract schema 的 snapshot 字段集。

---

## 10. 实现分期建议

| 步 | 内容 | 风险 |
|----|------|------|
| P0 | SnapshotService force 命令 + debounce + 单测 | 中（worker 队列） |
| P1 | 开单全挂钩 + 单测穷举 | 中（漏挂钩） |
| P2 | 前端 mutate 重试 + worker 短轮询 | 低 |
| P3 | （可选）开单页顺带 `loadApi` 策略 | 低 |

P0+P1 无前端也可改善「下一拉即新」；P2 才满足「操作者主动立刻看到」。

---

## 11. 验收标准（计划评审 / 实现后）

1. 任意代码路径使任务 `running→非 running` 后，snapshot worker 在 debounce 窗口后执行账户三源 force 拉取（private 开启时），并成功 publish 或安全降级。  
2. `GET /snapshot` 与 `GET /hedge-open-positions` 在 publish 后读到同一代 `private_account`（`checked_at` 一致语义）。  
3. 用户 pause/delete 后，前端在重试策略内取得更新后的持仓合并表（private 可用时）。  
4. worker 自动 done/paused/stopped 时，开单页短轮询能触发 positions 重拉。  
5. `GET /snapshot` 仍为零上游 pure read；手动刷新语义不变。  
6. 开单状态迁移不因 refresh 失败而失败。  
7. 无新增实盘写操作；无凭证出进程。

---

## 12. 开放问题（请评审表态）

| # | 问题 | 初稿倾向 |
|---|------|----------|
| Q1 | force 是否包含 `price_map`？ | 倾向 **包含**（估值与合并展示一致性）；可砍以省 1 次公开 GET |
| Q2 | debounce 1.0s 是否合适？ | 1.0s；可改为 0.5–2s |
| Q3 | 前端短轮询 3s 是否可接受？ | 可；仅开单页+有 running |
| Q4 | 是否要在「pair 结算成功但仍 running」也 refresh？ | **本轮否**（Human 已定离 running）；列为 L1 后续 |
| Q5 | store 内挂钩 vs service 观察？ | 倾向 **service/callback**，store 保持无网络 |
| Q6 | 是否需要对外 HTTP force 调试口？ | **本轮否** |

---

## 13. 文档与后续

实现合并后：

- 在 `docs/api/public-market-contract.md` **仅当**有对外语义变化时修订；纯内部 hook **可只**在 DEVELOPMENT 或本文件「as-built 注记」中留指针。  
- `PROJECT_STATE.md`：若引入运行时行为，合并后由 Bookkeeper 记一条操作者可见说明（离 running 会触发账户只读刷新）。  
- 不修改 ADR 借币/开单状态机，除非评审要求新 ADR；本方案可记为 additive 运维体验，不改资金控制面。

---

## 14. 评审检查清单（给 Codex）

请重点审查：

1. 挂钩清单 H1–H4 是否穷尽所有 `running→*` 写库路径；有无遗漏（含 dry-run 同步 fill-all 循环）。  
2. 串行 worker 入队是否违反 snapshot 单一写者；有无死锁/重入。  
3. debounce 与「最后一次迁移必须刷到」是否成立。  
4. validate 失败不覆盖 published 是否与 tick 一致。  
5. 前端竞态重试是否足够；短轮询是否误成执行时钟。  
6. L1（running 中成交不刷）是否与产品预期冲突。  
7. 安全：无新签名写、无 GET 副作用污染 contract。  
8. 测试是否可在无网络下用 mock 闭合。

评审结论请使用仓库计划评审习惯：`ACCEPT` / `REWORK`，发现标注 `in-range` / `pre-existing-*`，REWORK 须可执行修复要求。

---

## 附录 A · 模块触点（预期改动面）

| 区域 | 文件（预期） | 动作 |
|------|----------------|------|
| Snapshot | `backend/services/snapshot_service.py` | 新 command + force 面板 + debounce + publish |
| 开单 service/store | `backend/hedge_open_tasks/service.py`, `store.py` | 挂钩 / 回调 |
| 装配 | `backend/app/server.py` 或服务构造处 | 注入 SnapshotService → HedgeOpenService |
| 前端 | `frontend/index.html` | mutate 重试 + 短轮询 |
| 测试 | `backend/tests/test_*.py`, `frontend/self-check.js` | §9 |
| 契约 | 默认不改；除非 Q6 变成要做 | — |

## 附录 B · 与相关文档关系

| 文档 | 关系 |
|------|------|
| `docs/api/public-market-contract.md` | snapshot pure-read、private_account、symbol-snapshot 不重拉账户 —— 本方案遵守 |
| `docs/architecture/ARCHITECTURE.md` | 单一后端快照边界 —— force 仍在 SnapshotService 内 |
| 开单状态机 / amendment 21 | 不改状态语义，只加副作用钩子 |
| `PROJECT_STATE.md` 中 order_state_unknown 等 | 离 running 暂停时同样 force，利于操作者对照交易所 |

---

**文末：本文不授权实现、合并、部署或实盘。Human 接受计划评审结论后，再拆 dispatch 实现包。**
