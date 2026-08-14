# Task Handoff: 02-plan-review-2

## Source Report (author-only; immutable after task end)
- task_id / role / target model: 02-plan-review-2 / Planner（跨 provider 只读计划评审）/ gpt-5.6-sol（openai）
- stage_id / created_at: 2026-08-14-smooth-close-orders-v1 / 2026-08-14 15:14:33 CST
- base_sha / delivery_sha: f43706d735b87b5a22fd0d5aeb1ac205bed6623d / none

范围：只读审阅 r2 设计、第一次计划评审 handoff、开单镜像设计，以及 dispatch 指定的 service/store/domain/snapshot/frontend 证据。未启动服务、未创建任务、未发单，未修改源码、状态或既有证据。当前 HEAD 为 `4d2318efd83649e8265b3e25dea524be6ac7f353`；本任务无 delivery commit。

评审结论：**REWORK**。R2 是 r2 新引入的 in-range 资金移动并发缺口：C5/C13 把 forward smooth-close 的预检、余额查询和 `universal_transfer` 前移到同步 `POST /start`，但未规定同一任务的并发启动串行化。服务由 `ThreadingHTTPServer` 提供，现有 `post_start` 无 CAS、版本参数或任务级锁；`_ensure_close_spot_balance` 是“读普通现货余额 → 计算差额 → 划转”的 read-then-act 序列。两个并发 `/start` 可在任一请求写入 `q_common` 前都读到相同余额并各自划转同一差额，造成重复资金划转。前端按钮禁用只覆盖当前页面，不能约束并发 HTTP 请求。

重点结论：

1. **第一轮 R1：已实质消解。**C6 删除了“备料失败 → deleted”的机制，改用当前 immediately-close 已存在的 `paused + pause_reason/pause_reason_zh`。`store.pause_task` 已原子写入这两个字段，`task_to_doc` 透传，`frontend/index.html::renderHedgeTaskCard` 已无条件渲染“暂停原因”。因此不存在原先的 deleted 原因持久化或与人工软删除混淆问题；这不是给 deleted 换标签。
2. **C13/C14：R2 不通过。**同步备料、末步写入 `q_common` 与崩溃后的余额复查能解决 r1 的“先写 q_common 再划转”问题，但没有线性化并发 `post_start`。这使 C13 的真实划转出现重复执行窗口，详见 R2。
3. **C15：通过。**当前 `send_qty` 在 `q_common is None` 时回退 `single_amount` 是现实风险；r2 明确禁止无有效数量时订阅、建 gate、manual/timeout 放行，并有可执行的零 attempt/executor 断言。
4. **C16：通过。**方向翻转、读模型、审计、覆盖率及两处文案均已列为独立调用点与验收；forward close 使用 `spot.bid/perp.ask` 和对应 bid/ask quantity，reverse close 使用 `perp.bid/spot.ask` 和对应 bid/ask quantity，数学和吃单档位一致。
5. **陈旧风险与单腿刹车：通过（已知代价）。**冻结的 filters、余额/保证金、position mode、路由、可平量及限频均在 §5 具名；人工平仓和部分成交积累的单腿均由 smooth-close 阈值 1 在首次后暂停，且文档明确恢复前须人工核对。immediate close 保持每轮三道门和阈值 3。

### R2 — 同一任务并发启动可重复划转（in-range，阻塞）

- 证据锚点：`backend/app/server.py::build_server` 直接构造 `ThreadingHTTPServer`；`backend/hedge_open_tasks/service.py::post_start` 读取 task 后直接状态写入，没有版本/CAS/任务级锁；`_ensure_close_spot_balance` 先 `query_spot_free`、计算 `diff`，再调用 `universal_transfer`。现有 `backend/tests/test_hedge_task_local.py::test_2_concurrent_start_yields_one_worker_one_reservation` 只证明 `ensure_worker` 去重，未串行化 `post_start` 的新备料段。
- 实际影响：两个同任务的 `/start` 请求可同时观察普通现货余额不足，各自成功调用 `universal_transfer('PORTFOLIO_MARGIN_MAIN', base, diff)`；若统一账户余额足够，普通现货账户被重复备币。该外部资金划转发生在 C13 新增的同步路径内，不能由之后的单 worker 或 `q_common` 写入撤销。
- 修复要求：r2 必须在 C5/C13/C14 规定一个**同任务、`smooth + close + q_common` 为空的启动备料临界区**。进入临界区后重新读取 task；成功备料并持久化 q_common 后，竞争请求只复用已备料结果，绝不再预检/查仓/划转。失败请求释放临界区并维持 paused/中文原因；不新增任务状态或数据库列。实现可使用服务内受控互斥，但不得把数据库事务跨越交易所 I/O。新增并发验收：用两个 `post_start` 线程和余额读取 barrier 强制两请求竞争，断言 forward smooth close 的 `universal_transfer` 恰好 1 次、`q_common`/running 结果一致、worker 至多 1 个；保留 C14 的崩溃后余额足够时不二次划转断言。
- 为什么本轮必须修：C13 新增了启动端的真实 transfer；在现有多线程 HTTP 服务上并发请求是直接可达路径，且一次成功的多余转账没有自动回退。不是未来扩展或偏好问题。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md；docs/planning/smooth-close-orders-v1.md；backend/app/server.py；backend/hedge_open_tasks/service.py；backend/tests/test_hedge_task_local.py
- 执行：Bookkeeper 核验 REWORK；Planner 仅修订设计，补齐 R2 的备料临界区语义和并发验收。
- 关卡：修订后再次进行跨 provider 只读计划评审；ACCEPT 前不得派发 P1/P2 实现。
- 不能假设的事实：前端单页禁用不构成 API 并发互斥；`ensure_worker` 的去重不保护 preflight/划转；不得新增任务状态、数据库列、跨交易所 I/O 的数据库事务或第二套备料链。

## Human Brief / Console Receipt Source (author-only; immutable after task end)
[TASK_RESULT v2]
任务 ID: 02-plan-review-2
执行结果: completed（完成）
结果摘要: r2 已实质消解上一轮 deleted 原因 R1；但 C13 将备料划转置入可并发 /start，当前多线程服务与读后划转序列可重复转币，结论 REWORK。C15/C16、方向、陈旧风险和阈值1单腿刹车均通过。
产物: [reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md]
检查结果: [pass：Identity/阶段/修订/分支与HEAD核对；pass：只读，无源码或状态修改；pass：R1因C6改为现有paused原因通道而消解；fail：C13/C14缺同任务并发启动的划转临界区；pass：C15无q_common不放行可测；pass：C16方向/展示调用点完整；pass：陈旧风险与阈值1单腿处置复核；pass：handoff符合创建路径与结构]
阻塞项: [R2：设计须定义smooth-close首次启动备料的同任务临界区、竞争请求重读复用结果与双线程单次universal_transfer验收；修订后需再次计划评审]
本地北京时间: 2026-08-14 15:14:33 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验并转交计划返工）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md；执行：核验REWORK并准备仅修订设计的返工dispatch；关卡：修订后跨provider计划评审ACCEPT，方可派发实现
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md
修复要求: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/02-plan-review-2.handoff.md
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: 327fbb57ff3a360a7d68011f1edf3709948e044f9e58a1ec8b3881337e6d48ef
- 核验时间: 2026-08-14 15:57:00 CST
- 核对 status revision: 4
- 依据: handoff 形式结构合规，包含明确评审结果(REWORK)与阻塞发现 R2（并发 post_start 可重复划转）。任务无非法越权修改。预检(test ! -e)通过。特别记录：本次 REWORK 的阻塞项 R2，经 Human 决策并未在 r3 中通过代码修复，而是被具名接受为残余风险结案（r3 §5.6 已补充理由和后果边界）。
- 后续状态: 验证通过（verified）。按 AGENTS.md §8 计划评审规则，rework_count 不递增，保持为 0。Planner 已完成 r3 返工并提交至 177f806，当前推进至 03-plan-review-3 任务。

## Errata (append-only)
