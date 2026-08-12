# 平滑开单 V1：四路独立设计评议汇总

日期：2026-08-12
性质：Human 指示的并行只读设计评议；**不是正式 plan-review、Review-1 或 Review-2，不产生 ACCEPT，不授权实现或外部操作。**
被评文档：`docs/planning/smooth-open-orders-v1.md` 初稿（378 行）。

## 1. 参与者与总体意见

| 窗口 | 实际模型 | 总体意见 |
|---|---|---|
| `claude` | Claude Opus 5 / xhigh | 需有限修订后进入正式计划评审；明确确认单 worker + `prepare_attempt` 硬门可以封住 10/10 多单 |
| `grok` | Grok 4.6 / xhigh | 主框架成立；要求把等待唤醒、数量量纲、现有入口封口和 gate/attempt 原子关系写成不变量 |
| `kimi` | Kimi K2.7 Coding Highspeed | 可进入正式计划评审，但需先钉死 gate 持久化与 CCXT volume/contractSize 的 P0 证据 |
| `claude-glm` | Claude Code + GLM-5.2 / xhigh | 可进入正式计划评审，建议先做三类非推倒修订：gate/attempt 原子恢复、smooth 入口、coverage 分母 |

四家均未反对以下产品主线：`BookTicker/watchBidsAsks`、方向开单率严格大于 signed threshold、双腿一档 80% 机会过滤、每轮 5 分钟超时回退立即开单、两腿仍并发、单腿/查单/结算复用立即链、`成交1次` 只放行当前 gate、任务卡沿用 2 秒展开日志读链。

## 2. 共识问题与处理

| 共识问题 | 证据/影响 | 最终处理 |
|---|---|---|
| gate wait 未定义会使当前 `_worker_round` 在无在途 legs 时忙循环 | 当前 worker 只有存在非终态 legs 才 pace；smooth gate 等待发生在无 legs 时 | 增加每 task `threading.Condition + wake_version`；WS、force、pause/delete、Start gate、stop、deadline 唤醒；禁止 busy loop |
| Python 服务为同步线程模型，CCXT Pro 为 asyncio，桥未定义 | 当前 backend 无 asyncio runtime；worker 是 `threading.Thread` | 增加进程级专用 event-loop 线程，独占 CCXT clients/watchers；锁保护 immutable snapshot；close 时 cancel/close/join |
| gate claim 和 `prepare_attempt` 分两步存在 crash 中间态 | claim 后崩溃可留下 consumed-without-attempt | 删除单独 consumed/claim 持久化状态；pass_reason、attempt、计数递增、gate 清理在一个 store 事务中完成 |
| coverage 分母在 gate 前没有 fresh preflight 结果 | dispatch 内才会重取 fresh q_common；每个 WS tick 跑 private preflight 会放大已知权重风险 | 明确机会过滤分母为建卡固化 `task.q_common`，两腿相同；接受 fresh dispatch 可能变化的近似，不在 tick 重跑 preflight |
| 合约 BookTicker 数量单位不能凭字段名猜 | 当前 preflight 没有 contractSize；1000x 换算是已知资金风险且仍被封禁 | P0 必须证明普通可达 symbol 的 qty 与 q_common 同量纲并断言 `contractSize == 1`；不明/非 1 invalid；禁止本轮通用乘法或恢复 1000x |
| `成交1次` 只写 force 时，running 但 worker 丢失会无人消费 | 当前 UI 已能显示 running + worker inactive | force 持久化成功后幂等 `ensure_worker` 并 notify；仍不由 HTTP 线程直接 dispatch |
| 收起日志后 gate seq 可能陈旧 | 2 秒只刷新已展开任务日志，任务列表不在该 tick 内 | 点击前先 GET 当前日志/smooth_market，再 POST 该 seq；期间推进则 409；paused/无 seq 禁用 |
| 当前 smooth 入口仍全被挡住，fill-all 一旦上线会出现 | `create_task` immediate-only、按钮 disabled/`smooth_next_round`；`showFillAll` 对 smooth 为 true | P2 同一交付解除 create/UI 冻结、接入 gate；smooth fill-all 不展示/拒绝，防止只开按钮绕过门 |
| 现有开单率函数不应复制 | `compute_opening_spread_pct` 已含 Decimal、两位舍入、负零处理 | 实现直接调用该函数；文档公式只留在现状解释，不再给第二套实现伪代码 |
| 仓库没有任何运行时依赖清单 | 直接把 CCXT 安进当前实盘 `.venv` 不可回滚且越权 | P0 仅在隔离临时 venv，经 dispatch 明确授权公共网络/候选安装；成功后另行批准唯一 pinned runtime requirements |

## 3. 各家特有提醒

### Claude

- 指出停机超过原 deadline 后恢复会立刻形成 timeout；这相对 immediate 不是新增资金风险，但必须写清操作效果。
- 建议 Binance 原生 bookTicker 作为首选、CCXT 作为需证明的方案；由于 Human 已把 CCXT Pro 作为统一公共订阅方向，本轮不改变 D1，而以隔离 P0 + 原生 adapter fallback 管理风险。
- 建议 contractSize 在可达 V1 symbol 上只断言 1，不实现换算；已采纳。

### Grok

- 强调同一交付必须同时封住 `create_task`、fill-once、fill-all、非 live/tick 直发入口，不能先放开 smooth 再补 gate。
- 强调 service recovery 与 Human pause/resume 是两种语义：前者续原 deadline/force，后者清 gate 并重开完整窗口；已写入。
- 建议 `smooth_gate_seq` 同时出现在 task 与日志读模型，按钮没有活动 seq 时禁用；已采纳。

### Kimi

- 建议给 task 写完整 gate schema，并把 pass_reason 放 attempt；已采纳精简版本：deadline 派生、不重复落列，也不增加任务级 last-pass。
- 建议删去动态读模型重复的 selected direction；task 已固有 direction，已删除。
- 提醒现有 logs API 只返回 attempts；P2 必须扩展同一路由并让 DOM patch 同时更新盘口块，已保留为明确任务。

### Claude-GLM

- 精确指出 `claim → prepare` crash 窗口不造成多单但恢复语义不清；已通过同事务消除。
- 指出 `renderOpeningQuotesCell` 只可复用 formatter/颜色，不能声称整 cell 可直接复用；已更正。
- 指出 `showFillAll` 不是“预留”而是已经按 smooth 条件启用，只因 smooth task 当前不可创建才没出现；已在现状与 P2 中显式列出删除要求。

## 4. 评议后冻结的新增实现不变量

1. 没有单独 `consumed` 状态：gate 只有活动或由 attempt 的存在证明已消费。
2. `smooth_pass_reason` 只随 attempt 写入，不在 task 重复保存“最近一次”。
3. HTTP force 可以唤醒/恢复 worker，但永远不能直接发单。
4. 盘口每 tick 只做内存 Decimal 计算，不跑 private preflight、不写 SQLite。
5. 1000x 乘数币的当前 fail-closed 不能被 BookTicker contractSize 逻辑绕开。
6. 进程停机时间计入已持久化的 5 分钟窗口；恢复后的 timeout 仍须经过全部现有立即安全门。
7. P0 不是实盘 `.venv` 安装；生产依赖落地需要后续明确授权。

## 5. 本轮未做

- 没有让四个评议模型修改文件或状态；
- 没有安装 CCXT、连接 Binance WebSocket、读取凭证、启动服务或下单；
- 没有把本轮意见冒充正式计划评审 verdict；
- 没有创建实现 dispatch 或修改 `status.json`。
