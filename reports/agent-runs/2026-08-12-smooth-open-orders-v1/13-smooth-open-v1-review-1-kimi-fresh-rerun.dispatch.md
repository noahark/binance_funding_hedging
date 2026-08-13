# Identity

- task_id: `smooth-open-v1-review-1-kimi-fresh-rerun`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `23`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在一个**新建或重置后的 Kimi CLI 会话**中，对平滑开单 V1 固定区间 `e955bdd300d214c5c3ad5c1acd629c0d21080165..24074b144dcdb745c511d866a75528a8930e8475` 从零重跑正式 Review-1。不得继续使用此前执行“平滑开单设计独立只读评议”和 task `smooth-open-v1-review-1-kimi` 的旧 Kimi session，也不得依赖该旧 Review-1 的结论；旧 verdict 因 session isolation 不合规而 non-accepting，代码没有因此发生变化。

实现作者 provider 为 `openai`，本 Reviewer provider 为 `moonshot`，满足跨 provider 与非自审。只检查实现正确性、资金/并发契约、测试与集成接缝，不重做产品设计；只使用固定 SHA，不用移动 HEAD 替代。

# Allowed Files

完全只读，唯一写权限是创建：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-1-kimi-fresh-rerun.handoff.md`（create-only）
- Bookkeeper 已执行并通过：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-1-kimi-fresh-rerun.handoff.md`

禁止修改源码、测试、设计、现有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md` 或其他文件；禁止 commit、amend、push、merge、安装依赖、联网、读取凭证、控制服务、行情/账户/订单调用、下单与部署。结束时 tracked worktree 必须干净，除唯一 handoff 外不得有新文件。

# Inputs

新会话严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/13-smooth-open-v1-review-1-kimi-fresh-rerun.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Reviewer、Review-1、Task Handoff Evidence Contract
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`
9. `docs/planning/smooth-open-orders-v1.md`
10. `docs/planning/smooth-open-orders-v1-development-checklist.md`
11. `docs/planning/ccxt-bookticker-recon-2026-08-13.md`
12. Git 固定区间的原始提交、diff、产品源码和测试。

不要读取旧的 `smooth-open-v1-review-1-kimi.handoff.md` 作为审查输入。启动时核对 stage/task/model/provider/revision 23、固定 base/delivery SHA 与新 handoff 不存在；任一不符即 non-accepting。handoff 必须明确声明本任务在新建/重置后的 Kimi 会话启动、没有继承旧审查对话；Bookkeeper 将在 Human 启动前后单独核验 Herdr session 已变化。

# Acceptance Checks

1. 核对 `base..delivery` 的实际实现文件均属原 Allowed Files，禁止的 executor/live client/preflight/scheduler/snapshot、既有禁止测试和状态文件没有实现提交改动；控制提交仅作上下文。
2. 审查公共盘口 provider 的单 event-loop 线程、多 key/双 watcher 隔离、引用计数、generation 失效、异常重连、raw `b/B/a/A` Decimal、`contractSize == 1` fail-closed、回调、release/close/join 竞态与零残留。
3. 审查 signed 阈值、严格 `spread > threshold`、两腿各 `>=80%`、完整 5 分钟 gate，以及 `open/force/prepare` 的事务复核。市场与 manual 竞态必须最多创建一次 attempt；`成交1次` 只能放行当前 seq，不能产生 gate 外额外成交。
4. 审查四条 running→非 running 写路径、非空 sentinel、系统 pause/fatal stop 清 gate、resume 为同一未调度 seq 重开完整窗口、结算不复活；Condition+wake_version 必须无忙循环、无丢唤醒/死锁。
5. 确认 smooth 只决定进入时机，两腿并发提交、同步等返回、单腿、查单和结算复用既有立即链；provider 缺失、Start gate、timeout、API 400/409、fill-once/fill-all 分流均 fail-closed 且不破坏 immediate/close。
6. 核对前端阈值位置/默认 `0.05`/负数与零、既有任务卡字段/日志/错误、盘口失效 `—`、双向开单率与覆盖、当前 gate_seq POST、无 fill-all、复用既有 2 秒日志刷新且无新 timer。
7. 检查测试能真实抓住 provider 生命周期、gate 原子性、pause/resume、并发最多一次、API/UI。可复跑新增 57、核心 502、executor 75、字段绑定 12 和前端 self-check；全后端已裁定的唯一基线失败是 `test_private_client.py::test_urlopen_only_in_designated_http_clients` 报 `public_ip_service.py`，只有失败对象或数量改变才作为本轮问题。
8. 每条阻塞发现给文件/行、可复现证据、实际影响、最小修复要求，并按 `in-range | pre-existing-independent | pre-existing-release-critical` 分类。`pre-existing-*` 必须同时早于 base 且文件不在本次 delivery；新假设阻塞须满足 `AGENTS.md` §1。无范围内阻塞问题才可明确 `ACCEPT`。

# Stop

完成独立只读审查后，只创建唯一 handoff。按 Task Handoff Evidence Contract 写固定 base/delivery SHA、审查证据、发现分类和完整 `[TASK_RESULT v2]`；Review 结论只能是明确 `ACCEPT（接受）` 或 `REWORK（返工）`。`下一步模型` 写 `Bookkeeper（codex）`；下一步任务为读取新 handoff、核验 source SHA-256/session freshness/固定区间/verdict 并推进；关卡为 ACCEPT 后准备独立 Review-2，REWORK 则准备原 Implementer 修复。输出 `[/TASK_RESULT]` 后停止，不启动下一模型。
