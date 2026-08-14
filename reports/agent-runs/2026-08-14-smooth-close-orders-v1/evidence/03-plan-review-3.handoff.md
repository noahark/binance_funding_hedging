# Task Handoff: 03-plan-review-3

## Source Report (author-only; immutable after task end)

- task_id: 03-plan-review-3
- role: Planner（跨 provider 只读计划评审）
- target_model: gpt-5.6-sol / provider openai
- stage_id: 2026-08-14-smooth-close-orders-v1
- created_at: 2026-08-14 16:02:17 CST
- base_sha: 177f806a589279b4a3fca0e8325dbb999a5d9157
- delivery_sha: none（只读计划评审）
- status_revision: 5
- review_verdict: ACCEPT

### Scope and Evidence Read

- 任务包、活动阶段、项目状态、阶段 `status.json`、Reviewer/Planner 路由和 `agents/skills/task-planner.md`；身份、revision、分支和 HEAD 均与 packet 一致。
- 设计 r3：`docs/planning/smooth-close-orders-v1.md`（177f806，尤其 §5.6、§8、§12）。
- 前两轮评审与其 Bookkeeper 核验：`evidence/01-plan-review.handoff.md`、`evidence/02-plan-review-2.handoff.md`。
- 当前实现锚点：`backend/app/server.py`（`ThreadingHTTPServer`）、`backend/app/service.py`（`post_start`、`_worker_round`、`_wait_for_smooth_gate`、`_dispatch_one_for_task`、`put_close_gate`、备料划转）、`backend/app/store.py`（smooth gate、任务状态条件更新）、以及前端任务卡/启动操作和既有测试。

### Review Conclusion

**ACCEPT。** r3 对两轮 REWORK 的处理、所列代码事实与计划测试之间一致，具备进入实现的可执行性。

1. **R2 的 Human 接受完整且边界与代码相符。** 当前 `ThreadingHTTPServer` 允许同一任务的两个 `post_start` 并发进入备料；现有前端禁用只能覆盖当前页面，因此它不能当作互斥。r3 §5.6 没有把 C14 误称为防重复划转：C14 只保证最多一个请求将 `q_common` 和 `running` 持久化，并防止 deleted/paused 被复活；两个请求在条件写之前都可能调用同一内部 `universal_transfer`，该残余风险被明确保留。现有划转路径是同一账户的 unified 到 normal spot 补币，且订单派发在其后依赖已持久化的 `q_common`；据此，§5.6 所述“多余币留在 normal spot、没有额外订单或 q_common 数量影响”的边界成立。代码不能证伪 Human 的单一操作者、数秒内不双启动这一运行前提，故不得仅因未加互斥再次阻塞。

2. **C14 消解了 deleted 任务复活的已证实竞态。** 备料完成后的 `paused AND q_common IS NULL` 条件写，配合命中失败后的 reload 分支，可区分 deleted/done、仍 paused 且已有 q、以及已 running；不会再以无条件 `set_task_status(RUNNING)` 覆盖删除或暂停。§8 的注入点（删除/暂停发生在备料与条件写之间）和“无 q、无 running、无 worker”的断言可直接证明该修复，而非只测正常路径。

3. **C10 与 C15 防止“测试绿而功能死”。** 当前 store 的两个 smooth-gate 方法硬编码 `task_type == open`，r3 要同时改掉两处并以 `q_common` 作为共同准入。§8 10a 同时覆盖 close task 的 open/force 成功和缺 q 拒绝，能使“启动成功但 gate 永远不开、零订单”的回归失败。C15 对缺 q 的 running task 明确暂停、保留既有 `preflight_incomplete` 中文原因并退出 worker；其测试覆盖 manual/timeout 路径、无 prepare/executor 和有界轮次，避免仅 return 造成紧循环或静默失活。

4. **其余 r3 修订有对应的资金与时序证据。** C5 把 Start/Close gate 拦截放在备料前，并以零 snapshot/持仓/划转验收副作用；C12 补齐 close gate 的唤醒、等待检查/清 gate、派单准入、重新启用 worker 与退出清 gate；C13 在备料中禁用任务卡全部控制，同时仍由 C14 作为服务端最终状态保护；C17 按 `q_common` 派生展示，避免把即时模式的每轮状态误呈为一次性备料完成。其余微秒级 gate 边界与已接受 open L1 同类，未发现新增、可准入的资金或订单缺口。

### Residual-risk Observation (non-blocking)

R2 的接受应在以下事实变化时重新提交 Human 复看：允许多操作者、自动化或跨页并发启动；观测到重复备料划转；或需要把“重复启动”支持为常规操作。它们会否定或扩大 §5.6 的单一操作者运行边界；当前代码和已记录前提均未显示该变化。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/03-plan-review-3.handoff.md`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json`；`docs/planning/smooth-close-orders-v1.md`。
- 执行：Bookkeeper 核验本 handoff、将第三次计划评审结果写入阶段路由，并在既有授权下交接 P1 实现任务。
- 关卡：Bookkeeper 核验通过后，Human 启动 packet 已指定的实现模型；实现交付须按固定 `base_sha..delivery_sha` 进入 HIGH_RISK 双正式评审。
- 不能假设的事实：R2 未获得代码互斥修复；它仅在 §5.6 记录的单一操作者前提与边界内由 Human 接受，实施不得把该接受扩大为并发安全保证。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 03-plan-review-3
执行结果: completed（完成）
结果摘要: r3 计划评审接受：R2 的 Human 残余风险接受与现有并发/划转代码事实相符；C14、C10/C15、C5/C12/C13/C17 均有可执行且能防伪通过的验收证据。
产物: [reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/03-plan-review-3.handoff.md]
检查结果: [pass 身份、revision、分支与 HEAD 匹配；pass R2 接受前提和残余边界与代码相符；pass C14 条件写防 deleted/paused 复活；pass C10/C15 close gate 与 fail-closed 验收可检出功能死；pass C5/C12/C13/C17 的资金、闸门与展示覆盖；pass 全程只读且仅创建允许 handoff]
阻塞项: [none]
本地北京时间: 2026-08-14 16:02:17 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验本次评审回执）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/03-plan-review-3.handoff.md；执行：核验评审结果并更新阶段路由；关卡：核验通过后由 Human 启动已准备的 P1 实现任务。
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: ce283ed5ea6e6d4c828c7f884fabc2cb2aba99d93cc72c60ed622a7ed769ea24
- 核验时间: 2026-08-14 16:13:35 CST
- 核对 status revision: 5
- 依据: handoff 结构合规，结论明确为 ACCEPT，无阻塞项。任务只读，符合跨 provider 隔离要求，未越权修改。预检（test ! -e）合规通过。
- 后续状态: 验证通过（verified）。结论为 ACCEPT，按 AGENTS.md §8，rework_count 不触碰，保持为 0。根据 Human 决策，现推进至前端 fake 样式实现，待页面验收通过后再启动后端 P1。

## Errata (append-only)
- 2026-08-14 16:13:35 CST by Bookkeeper:
  - 1. 三轮计划评审的实际执行模型是 `gpt-5.6-terra` 而非 packet/handoff 记载的 `gpt-5.6-sol`；由于 provider 仍为 `openai`，跨 provider 隔离结论不受影响。后续 packet 将统一使用实际的 target_model 值。
  - 2. 03 handoff 的 Scope 段所列 `backend/app/service.py`、`backend/app/store.py` 两个路径在仓库中不存在（实际为 `backend/hedge_open_tasks/service.py` 与 `backend/hedge_open_tasks/store.py`）；所述代码事实经 Planner 复核成立，仅此处的路径标注有误。
  - 3. 03 handoff 的 role 记为了 Reviewer，而 packet Identity 中为 Planner；两处描述不一致，以 packet 规定的 Planner 角色为准。
