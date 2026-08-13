# Identity

- task_id: `smooth-open-v1-repair-plan-opus5`
- target_role: `Planner`
- target_model: `claude-opus-5`
- provider: `anthropic`
- status_revision: `27`
- required_skill: `agents/skills/task-planner.md`

# Goal

对平滑开单 V1 做一次最小增量计划修订，把 Review-2 后的 Human 最终取舍写入现有设计权威，并形成一份可供后续跨 provider 窄范围计划复核的单 Implementer 返修清单。只处理下列已决定内容，不从头重写设计、不重新讨论已关闭项目：

1. **Human 接受、不修**：Start 总开关/`service.stop()` 与本轮 reserve→dispatch 的竞态；上一轮查单耗时可能让下一 gate 少于完整 5 分钟；行情表重绘可能把尚未提交的 threshold 输入复位为 `0.05`。把三项写成这次交付的具名已知限制、实际影响、临时操作方式和重开条件，不再列为本轮验收失败。
2. **本轮必须修**：provider 并发冷启动僵尸订阅；`APP_OFFLINE=true` 仍构造真实公共 WebSocket provider；无限长度合法 signed 大整数 threshold 在 `Decimal.quantize` 逃逸；provider 持续异常/无效快照无等待热循环；暂停/删除任务仍 drain/settle 在途订单时展开日志停止刷新。
3. **Human 新需求**：平滑模式建任务时的首次完整 preflight 保留；任务开始执行且首轮尚未调度时，先完成该任务唯一一次杠杆设置，成功后才允许订阅 WebSocket、建立或恢复 gate、第一次计算滑点。每轮 WebSocket 滑点严格 `>` threshold 且两腿一档数量各 `>=80%` 后，删除 `_dispatch_one_for_task` 中对 smooth 的每轮联网 fresh preflight，直接复用任务已固化的 `q_common`、`position_side_mode`、`preflight_snapshot`/route，原子 reserve 本轮后进入既有异步两腿下单、同步等返回、查单、结算与单腿暂停链。立即模式的 fresh preflight 和杠杆设置时机完全不变。不得把杠杆设置提前到建卡时；盘口通过到异步两腿提交之间不得再发生任何联网读取、交易所设置或其他阻塞调用。

这是 HIGH_RISK 的计划修订，不授权实现、安装 CCXT、联网、启动/停止服务、读取凭证、创建任务、下单、push、merge、部署或实盘。完成后须先由 provider 非 `anthropic` 的 fresh Reviewer 做一次只查本增量的计划复核；`ACCEPT` 前不得准备或启动实现。

# Allowed Files

仅允许修改：

- `docs/planning/smooth-open-orders-v1.md`
- `docs/planning/smooth-open-orders-v1-development-checklist.md`

仅允许新建唯一交接件：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`
- Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md` 已通过。

禁止修改源码、测试、其他文档、已有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、`.venv`；禁止 commit/amend/push/merge。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/15-smooth-open-v1-repair-plan-opus5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Planner 与 Task Handoff Evidence Contract 两节
7. `agents/skills/task-planner.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`，以 Bookkeeper Verification 中的后续证据和 Human 决策为准
9. `docs/planning/smooth-open-orders-v1.md`
10. `docs/planning/smooth-open-orders-v1-development-checklist.md`
11. 只读核对以下当前实现锚点：`backend/services/best_bid_ask_provider.py` 的 `start/subscribe/_watch`；`backend/hedge_open_tasks/domain.py::validate_slippage_threshold_pct`；`backend/hedge_open_tasks/service.py::_ensure_smooth_subscriptions/_wait_for_smooth_gate/_dispatch_one_for_task/post_pause/post_delete`；`backend/app/server.py::_build_hedge_service`；`frontend/index.html::loadHedgeTasks/refreshExpandedRunningHedgeLogs`；对应 smooth/provider/frontend 测试。

启动核对：cwd 为 `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`，分支为 `smooth/v1-fullstack`，status revision `27`、本 task_id/model/provider 一致，`base_sha=bfb633799ed904ba6d8364bffef7f048d77137dd`，唯一 handoff 路径不存在。任一不一致即停止并返回 blocked handoff。

# Acceptance Checks

1. **只修既有权威**：在两份现有 planning 文件中用最小增量明确“旧 Review-2 ACCEPT 未被 Bookkeeper 采用”、Human 接受三项限制、五项必须修复和 smooth-only fresh-preflight 删除；不得新建第三份设计/风险/修复权威。
2. **三项接受风险写完整但不扩修复**：
   - Start OFF/stop 可能落在行情放行与 reserve/dispatch 之间，导致关闸后仍真实发单、错误转模拟并消耗一次，或快速 OFF→ON 复用旧 gate；Human 本轮接受，不加新的准入锁/stopping 状态/store gate 复核。
   - 新 gate 可能使用上一轮结算前捕获的旧 `now_us`，因此等待时间缩短；Human 本轮接受，不改时钟获取点。
   - 60 秒整表刷新或单行重绘可能把未提交的 threshold 恢复为 `0.05`；Human 本轮接受，不扩 capture selector。临时操作方式是点击平滑开单前重新确认输入框；重开条件是 Human 实际受影响或要求持久保值。
3. **provider 冷启动根因修复**：所有并发 `start/subscribe` 调用者等待同一个 ready 结果；loop 未 ready/启动失败不得登记可见 state；订阅两侧必须“全部成功才记 task subscriptions”，部分成功须 release 回滚，失败后可重试。不得新增第二个 event loop、manager 或后台监督器。
4. **离线零网络**：`APP_OFFLINE=true` 时组合根固定注入 `market_provider=None`，即使已安装 ccxt 也不得构造 provider、启动线程或 subscribe；补组合根测试证明零构造/零订阅。非 offline 且 ccxt 缺失的既有 400 行为不变。
5. **threshold 字符串规范化**：保持“无产品最大值、最多两位小数、拒绝科学记数/NaN/Infinity/%”契约；不得用 Decimal 默认 context 对任意长度输入 `quantize`。计划指定最小字符串规范化方案和正负超长整数 domain/API 回归，错误仍为 400 而非 500。
6. **provider 防自旋**：异常和立即返回无效快照两条失败分支在重试前都有一个简单固定最小等待；不得发明指数退避、重试状态机或新配置。确定性测试以短窗口断言 watch/callback 次数有界，并验证 close 可立即打断等待。
7. **非 running 展开日志继续刷新**：只要任务仍存在且日志已展开，共享 2 秒 tick/既有 `loadHedgeTasks` 链继续取日志；paused/deleted/done/stopped 在途 drain/settle 的新增 attempt/腿状态最终可见。不得新增 timer；同步修正当前“暂停后不得请求日志”的错误 self-check。
8. **smooth-only 删除每轮 fresh preflight**：
   - create-task 首次 preflight、固化数据、regular-spot 预划转、缺腿/乘数合约拒绝全部保留；immediate 每轮 fresh preflight 逐字保持。
   - 对 live smooth 且 `scheduled_attempt_count == 0` 的任务，把既有 `_set_leverage_before_open` 从 gate 通过后的 `_dispatch_one_for_task` 移到 `_worker_round` 的任何 `_ensure_smooth_subscriptions`、`open_smooth_gate`、已有 gate 恢复和第一次 `_smooth_eval` 之前。成功后才开始监听/判断盘口；失败沿用现有 `leverage_set_failed` 暂停、中文日志、零 gate、零订阅、零 attempt、零订单。后续轮次不重复设置；若首轮尚未产生 attempt 就因失败或进程重启重新启动，可在新的执行入口幂等重试，但仍必须发生在任何 gate/订阅之前，不新增持久化列或新状态机。
   - smooth 的 market/manual/timeout 三种 gate 通过后，不调用 `HedgePreflightProvider.get_snapshot`，直接用 task 固化的 `q_common`、`position_side_mode`、`preflight_snapshot` 和 route 构造既有请求；随后仍由 `prepare_attempt` 原子复核 task 状态、target、无在途 pair、当前 gate seq 与 pass reason，再调用既有 `_dispatch_live` 两腿异步提交。
   - 不复制 executor，不新建 smooth 下单实现，不改 `live_hedge_executor.py`、live client 或 preflight provider；单腿/429/余额拒绝/查单/结算仍走原链并按既有原因暂停。
   - 明确接受的代价：等待期间余额、交易规则、position mode、rate-limit 或路由事实变化不再被每轮预检拦截，可能双腿拒绝或单腿；单腿由现有任务卡告警、暂停与 Human 人工核对收口。不得把该接受风险包装成 fail-closed。
   - `_dispatch_one_for_task` 对 smooth 不得再次设置杠杆；immediate 仍按现状在自己的首个 attempt 前设置。smooth 从任何一次 gate 判定通过到 `prepare_attempt`/`_dispatch_live` 之间不得再有网络读取、杠杆设置、sleep 或其他人为等待。计划须增加顺序型回归，用 spy 明确断言 `set_leverage → subscribe/open gate → market evaluation → prepare → dispatch`，且 market pass 后 leverage/preflight 调用数均不再增加。
9. **单一返修任务边界**：计划仍使用原实现作者 `gpt-5.6-sol`/provider `openai`/reasoning `xhigh`、同一 worktree/branch，`rework_count=1`。建议 Allowed Files 只含上述根因所需的 provider/domain/service/server/frontend 与对应测试、自检、唯一 fix handoff；不得修改 store、executor、live client、preflight provider、snapshot、requirements 或无关模块。列出逐项确定性回归、核心回归、全后端既存白名单勘误、前端 self-check 与 diff/scope 检查。
10. **窄计划复核请求**：在清单中给出 copy-ready 的只读复核正文，只检查三项 Human 接受风险是否被错误重新纳入、五项修复是否覆盖根因、smooth-only preflight 删除是否准确保留 create/immediate/原子 reserve/单腿后续，以及 smooth 杠杆是否严格前移到订阅与首次 gate 判断之前、gate 通过后是否再无联网读取或设置。目标 reviewer provider 必须非 `anthropic`，结论仍为 `ACCEPT | REWORK`。
11. `git diff --check` 无输出，变更只有两份 Allowed planning 文件；创建合规唯一 handoff，返回 Human Brief 的 `[TASK_RESULT v2]`。不提交、不改状态、不启动下一模型。

# Stop

完成两份计划的最小增量改稿、窄复核请求、唯一 handoff 与自检后停止。不得实施代码、准备正式实现 dispatch、安装依赖、联网、启停服务、读取凭证、创建任务、下单、提交、push、merge、部署或实盘。
