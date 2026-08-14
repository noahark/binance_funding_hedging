# Task Handoff: 01-plan-review

## Source Report (author-only; immutable after task end)
- task_id / role / target model: 01-plan-review / Planner（跨 provider 只读计划评审）/ gpt-5.6-sol（openai）
- stage_id / created_at: 2026-08-14-smooth-close-orders-v1 / 2026-08-14 13:55:54 CST
- base_sha / delivery_sha: c6748c17f5fea77aa8393fc05257857f9ec185f8 / none

范围：只读审阅 `docs/planning/smooth-close-orders-v1.md`、其开单镜像设计和 dispatch 指定的代码/前端证据；未启动服务、未创建任务、未发单，未修改代码、状态或既有证据。HEAD 是 `51e84c6ccfae65d0b3bdae908e7cec9bc0775bd6`，高于本 stage 的 committed base；本任务无 delivery commit。

评审结论：**REWORK**。R1 是 in-range 的计划缺口：C6 要求“备料失败 → deleted + 安全中文原因”，并要求与人工软删除可区分，但计划没有定义原因的持久化来源和区分规则。当前 `HedgeOpenStore.set_task_status(..., deleted, ...)` 只写状态/清 gate；`post_delete` 使用它。`frontend/index.html::renderHedgeTaskCard` 对 `deleted` 没有专属原因行；现有 `pauseReasonLine` 是泛用 `pause_reason` 投影，且人工从 paused 删除时可残留旧暂停原因。因此仅“在 deleted 卡新增一行”不能保证自动失败原因可见，也可能把人工删除误表述为备料失败。

五项重点结论：

1. **备料陈旧风险：通过。**设计 §5 已完整覆盖代码中 fresh preflight 会提供、而 smooth 准备后不再读取的事实：共同网格量/filters、路由、余额/保证金、仓位模式、合约可平量、交易所规则与限频。`service.py::_resolve_fresh_preflight`、`_close_um_position_error` 和 `_ensure_close_spot_balance` 是这些事实的现有证据。人工平仓/余额挪用/路由变化均属已列冻结事实；未找到另一个有当前代码依据而未列出的平滑发单前拦截。关闭平仓闸门与放行竞态是 §5 已具名继承的 L1，非本轮新增阻塞。
2. **暂停后人工平仓：通过（接受的残余风险）。**`domain.py::resolve_status_after_attempt` 对 single-leg 和 confirmed failure 均按 `>= failure_pause_threshold` 暂停；close 建卡固化为 1 后，人工平仓导致合约 reduceOnly 拒绝、现货腿成交的首次单腿会停住，不会连续派发。它不撤销已经产生的一次单腿，设计 §5.2 已准确声明该代价。
3. **方向翻转：通过。**forward close 传 reverse：`spot.bid - perp.ask`，覆盖用 `spot.bid_qty/perp.ask_qty`；reverse close 传 forward：`perp.bid - spot.ask`，覆盖用 `perp.bid_qty/spot.ask_qty`。这分别匹配 close 的 SELL spot + BUY perp、BUY spot + SELL perp。`compute_opening_spread_pct` 的第二参数是分母，四种 open/close 组合均保持正确价格与数量档位。
4. **deleted 可辨性/中文原因：不通过（R1）。**详见上述计划缺口及下列修复要求。
5. **资金安全、可测试性与复杂度：除 R1 外通过。**未见新的、当前代码可证的资金安全缺口；C4 的陈旧事实和 C8 的单腿处置均已明确。验收矩阵已覆盖 fake provider/clock、调用顺序、零联网、竞态和重启缝；无需新增第二个 dispatcher、状态列或预检机制。R1 只需现有 task 原因投影上的窄语义补齐。

### R1 — deleted 原因无持久化/来源语义（in-range，阻塞）

- 证据锚点：`backend/hedge_open_tasks/store.py::set_task_status` 对非 running 状态不写 `pause_reason` / `pause_reason_zh`；`backend/hedge_open_tasks/service.py::post_delete` 直接调用它。`frontend/index.html::renderHedgeTaskCard` 仅为 `stopped` 建 `stopReasonLine`，其 `pauseReasonLine` 没有区分 deleted 来源。
- 实际影响：平滑 close 的备料失败若仅置 `deleted`，卡片不能稳定展示中文原因；若复用已有暂停字段而不规定来源，人工从暂停状态软删除的卡也会携带旧原因。Human 无法可靠判断“系统因备料失败自动删除（零订单）”还是“人工删除”，违反 C6 的安全操作目的。
- 不是假设：上述状态写入和 UI 渲染为当前静态代码路径；C6 与验收矩阵第 6 项明确要求该信息可见。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md；docs/planning/smooth-close-orders-v1.md；backend/hedge_open_tasks/store.py；backend/hedge_open_tasks/service.py；frontend/index.html
- 执行：Bookkeeper 核验本计划评审为 REWORK；Planner 仅修订设计，明确 R1 的既有字段复用、自动/人工删除来源、原子条件写和验收。
- 关卡：修订后重新进行跨 provider 只读计划评审；通过前不得派发 P1/P2 实现。
- 不能假设的事实：不得新增状态列或第二套下单/备料路径；不得把人工软删除卡说成备料失败；不得以未持久化的日志替代任务卡原因。

## Human Brief / Console Receipt Source (author-only; immutable after task end)
[TASK_RESULT v2]
任务 ID: 01-plan-review
执行结果: completed（完成）
结果摘要: 计划评审完成但结论 REWORK：C6 未定义“备料失败自动 deleted”原因的持久化与人工删除区分，当前代码无法保证中文原因可见。其余四项重点通过；方向翻转、阈值 1 单腿刹车和陈旧风险表达正确。
产物: [reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md]
检查结果: [pass：Identity/阶段/修订/分支与HEAD核对；pass：只读，无源码或状态修改；pass：备料陈旧风险与当前预检路径核对；pass：单腿阈值1与结算逻辑核对；pass：四种方向价格/数量档位核对；fail：C6 deleted原因的持久化和人工删除区分缺失；pass：handoff符合创建路径与结构]
阻塞项: [R1：设计须规定自动备料失败写入既有原因字段的唯一 machine-readable code 与中文文案、仅自动路径的条件写、人工删除清除/不带该 code、deleted UI 专属标签及相应 API/前端测试]
本地北京时间: 2026-08-14 13:55:54 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验并转交计划返工）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md；执行：核验REWORK并准备仅修订设计的返工dispatch；关卡：修订后跨provider计划评审ACCEPT，方可派发实现
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md
修复要求: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/01-plan-review.handoff.md
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: 3ef332b1fdf100d75e187cf62ebb771cd011ba822e69c4bee9a6e35d4aed9be3
- 核验时间: 2026-08-14 15:10:45 CST
- 核对 status revision: 3
- 依据: handoff 形式与结构合规，包含明确的评审结果（REWORK）及合规证据（R1 及其代码路径）。由于是正式结论，符合只读评审要求。预检文件不存在条件满足。
- 后续状态: 验证通过（verified）。按 AGENTS.md §8 计划评审的规则，本次 REWORK 不触碰 rework_count，其值保持 0。任务已由 Planner（anthropic）执行了返工（r2 稿已合入 f43706d）。准备推进至第二次计划评审。

## Errata (append-only)
