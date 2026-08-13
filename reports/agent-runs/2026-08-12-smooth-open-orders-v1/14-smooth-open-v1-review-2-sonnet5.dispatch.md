# Identity

- task_id: `smooth-open-v1-review-2-sonnet5`
- target_role: `Reviewer`
- target_model: `sonnet5`
- provider: `anthropic`
- status_revision: `25`
- required_skill: `agents/skills/reality-checker.md`

# Goal

在新建或 `/clear` 后的 fresh Sonnet 5 对话中，对平滑开单 V1 固定区间 `e955bdd300d214c5c3ad5c1acd629c0d21080165..24074b144dcdb745c511d866a75528a8930e8475` 执行正式 Review-2：从 Human 已定需求出发，判断实际效果、证据、资金/运行风险和发布准备度，而不是重复 Review-1 的逐行检查。

实现与唯一交付作者是 `gpt-5.6-sol`/provider `openai`；Review-1 是 fresh Kimi/provider `moonshot` 且已 `ACCEPT`。本 Review-2 使用 provider `anthropic`，与全部实现/修复作者隔离。计划细拆曾由 Opus 5/provider `anthropic` 编写和返修，但 Sonnet 5 本会话未参与实现或修复；按默认 Review-2 路由使用 Sonnet 5，并披露该同 provider 设计背景。

# Allowed Files

完全只读，唯一允许写入：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`（新建、create-only）
- Bookkeeper 已执行并通过：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`

禁止修改任何源码、测试、文档、已有 evidence、dispatch、状态或项目文件；禁止 commit/amend/push/merge、安装 CCXT、联网、读取凭证、控制服务、行情/账户/订单请求、下单、部署或实盘启用。可运行现有离线测试；结束时 tracked worktree 必须干净，除唯一 handoff 外不得出现新文件。

# Inputs

fresh 对话按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/14-smooth-open-v1-review-2-sonnet5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Reviewer、Review-2、Task Handoff Evidence Contract
7. `agents/skills/reality-checker.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-1-kimi.handoff.md`（以最后一条 Human fact correction 为准）
10. `docs/planning/smooth-open-orders-v1.md`
11. `docs/planning/smooth-open-orders-v1-development-checklist.md`
12. `docs/planning/ccxt-bookticker-recon-2026-08-13.md`
13. Git 固定区间原始 diff、实现源码、测试与必要的既有调用链。

启动核对 task/stage/model/provider/revision 25、固定 base/delivery SHA、Review-1 已 verified、唯一 handoff 不存在；不得用移动 HEAD 替代审查范围。任一不符即 non-accepting。

# Acceptance Checks

1. **需求到实际效果**：逐项核对两个独立 spot/perp `watchBidsAsks` 一档订阅、signed 阈值默认 `0.05` 且严格 `>`、两腿各 `>=80%`、每轮完整 5 分钟、超时复用立即成交、`成交1次` 只放行当前 gate、两腿异步提交并同步等返回、单腿/查单/结算复用立即链。任何悄悄放宽、次数超额或方向/数量口径错误均阻塞。
2. **真实运行链路**：从 `server.py` 组合根追到 provider、service、store、executor seam 与 API/UI，确认不是“单测里存在但生产没接上”。CCXT 缺失时新建 smooth 必须明确 400，既存任务只能 manual/timeout fail-closed；安装后只能公共行情、无需凭证，provider 生命周期与服务 stop 能干净收尾。
3. **时间与并发结果**：判断 pause/resume、Start gate、进程重启、行情断开/重连、manual 与 market 同时通过、deadline 边界是否会缩短窗口、重复 attempt、额外下单、丢唤醒、忙循环或卡死；必须以当前代码和测试锚点说明。
4. **人机交互效果**：页面上阈值输入位置、负数/零、任务卡保留立即开单全部信息/日志/错误原因、动态盘口与双向开单率、失效显示、2 秒既有刷新、fill-once seq 绑定和无 fill-all，应满足 Human 实际操作判断需要且不恢复已知布局回归。
5. **证据可信度**：核对 fake provider/clock/executor 是否足以证明无真实订单和原子次数；新增 57、核心 502、executor 75、字段绑定 12、前端 self-check 证据是否覆盖关键风险。全后端唯一 `public_ip_service.py` 白名单失败已由 Bookkeeper 判定为 packet 基线勘误；除非失败对象或数量变化，不再标 `contested` 或据此 REWORK。handoff 里的隔离公开行情实测只能按其实际证明范围使用，不得推导为生产安装或实盘订单验证。
6. **发布准备度与剩余动作**：明确区分“代码可进入 Human 合并决策”与“已可上线”。当前生产环境没有获批安装 `ccxt==4.5.64`，也未获批合并、服务重启、部署或真实任务；评审必须说明 ACCEPT 后仍需 Human 分别授权哪些动作、建议的最小上线前/上线后只读或小额验证，以及 fail-closed 回滚边界。检查活文档是否需要 Bookkeeper 在阶段收尾同步，并具体点名，不要自行改文档。
7. **发现纪律**：每条正式发现给文件/行、可复现证据、实际影响、最小修复要求，并按 `in-range | pre-existing-independent | pre-existing-release-critical` 分类。`pre-existing-*` 必须有早于 base 的引入提交且文件不在 delivery；新假设阻塞须满足 `AGENTS.md` §1。偏好、未来扩展、已被 Human 接受的市场权衡或无当前证据的可能性不得 REWORK。
8. **最终判定**：只有实际需求、资金/次数语义、运行接线、证据或发布安全存在当前范围内阻塞问题时返回 `REWORK`；否则返回明确 `ACCEPT`，同时列出不阻塞但 Human 在合并/安装/启用前必须知道的真实剩余风险。ACCEPT 不授权任何外部动作。

# Stop

完成只读 Review-2 后，只创建唯一 handoff。按 Task Handoff Evidence Contract 写固定 base/delivery SHA、实际审查证据、发现分类、发布建议与完整 `[TASK_RESULT v2]`；必须明确 `评审结论: ACCEPT（接受） | REWORK（返工）`、问题记录与修复要求，并以 `[/TASK_RESULT]` 作为最终非空输出。

`下一步模型` 写 `Bookkeeper（codex）`；下一步任务写为读取本 handoff、核验 source SHA-256/固定区间/发现分类/verdict/发布边界并推进状态；关卡为 ACCEPT 后向 Human 汇报最终合并与运行选择，REWORK 则按范围和风险路由原 Implementer 修复。不得自行修改状态、启动修复、合并、安装、控制服务或实盘验证。
