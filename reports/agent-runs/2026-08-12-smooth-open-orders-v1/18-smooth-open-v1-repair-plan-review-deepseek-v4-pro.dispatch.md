# Identity

- task_id: `smooth-open-v1-repair-plan-review-deepseek-v4-pro`
- target_role: `Reviewer`
- target_model: `deepseek-v4-pro`
- provider: `deepseek`
- status_revision: `30`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

对平滑开单 V1 首轮交付后的返修计划做一次跨 provider、窄范围、只读计划复核，给出明确 `ACCEPT` 或 `REWORK`。只判断当前计划能否准确、可执行地覆盖 Human 已冻结的五项必修、D15/D16 与三项接受风险；不重做首轮整体设计评审，也不评审尚未实现的代码。

累计计划主体最初由 Opus 5（provider `anthropic`）修订，最后两处残留契约与记账口径由 Human 明确要求当前 Codex（provider `openai`）直接更正；DeepSeek（provider `deepseek`）与两者均跨 provider。已准备但未启动的 Opus r3 packet 已被 revision 30 取代，没有 r3 handoff，不得假设 Opus 执行过它。

`rework_count=3` 已达上限。本复核即使 `ACCEPT`，也只把决定交回 Human；未经 Human 按 `AGENTS.md` §8 选择缩窄、重设计、接受限制或停止，不得准备代码实现。本任务不授权实现、依赖安装、联网、服务控制、凭证、任务、订单、commit、push、merge、部署或实盘。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-review-deepseek-v4-pro.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改计划、源码、测试、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`；不得调用其他模型或执行任何外部动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-review-deepseek-v4-pro.handoff.md
exit 0（路径不存在，可由本复核创建）
```

# Inputs

固定受审范围：

- `base_sha`: `e4027bd7c88e489b8024b531f40cf3cd53555485`
- `delivery_sha`: `3905e45b665c6cefc5e5aee804021629f231501e`
- 计划主体：`git diff e4027bd7c88e489b8024b531f40cf3cd53555485..3905e45b665c6cefc5e5aee804021629f231501e -- docs/planning/smooth-open-orders-v1.md docs/planning/smooth-open-orders-v1-development-checklist.md`

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/18-smooth-open-v1-repair-plan-review-deepseek-v4-pro.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `30`、本 task_id 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`，以 Bookkeeper Verification 的拒收证据与 Human requirement change 为准
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r2.handoff.md`，只读 Bookkeeper Verification 与 Errata，确认 r2 拒收和 Human direct correction 边界
10. 用 `git show 3905e45b665c6cefc5e5aee804021629f231501e:docs/planning/smooth-open-orders-v1.md` 读取设计，重点 D8、D12、D15、D16、§6.1、§6.5、§8.4、§9、§13、§16
11. 用 `git show 3905e45b665c6cefc5e5aee804021629f231501e:docs/planning/smooth-open-orders-v1-development-checklist.md` 读取清单，重点 §0、§12、§13、§14
12. 需要核验证据锚点时，只读固定 delivery 树中的 `backend/services/best_bid_ask_provider.py`、`backend/hedge_open_tasks/domain.py`、`backend/hedge_open_tasks/service.py`、`backend/app/server.py`、`frontend/index.html`、`frontend/self-check.js` 与 §12.2 列出的测试文件；不得扫描无关阶段或运行时数据

固定范围中的 dispatch/status/handoff 属控制与来源上下文，不是计划交付主体。代码事实只用于核验计划的证据锚点和 Allowed Files，不评审首轮代码交付本身。

# Acceptance Checks

1. **三项 Human 接受风险没有被重新纳入**：L1（Start OFF/stop 与 reserve→dispatch 竞态）、L2（新 gate 可能不足完整 5 分钟）、L3（行情表重绘复位未提交 threshold）必须作为具名限制写清实际影响、临时操作和重开条件，不得成为待修项或验收失败项；计划不得要求为它们新增准入锁、`stopping` 状态、store 侧复核、时钟改动或前端 capture selector 扩展。
2. **五项必修覆盖真实根因且能测红错误实现**：核对 provider 并发冷启动僵尸订阅、`APP_OFFLINE` 仍构造 provider、超长 signed 阈值异常逃逸、持续失败零等待热循环、非 running 展开日志停止刷新。不得引入第二个 event loop/manager/监督器、指数退避、重试状态机、新配置或新 timer。特别核对超长阈值契约唯一口径：合法正负 30/100 位整数正常规范化并由 API 接受 `201`，格式非法值才 `400`，不得以长度设上限。
3. **D15 准确删除 smooth 每轮 fresh preflight**：保留 create-task 首次完整 preflight、固化数据、regular_spot 预划转、缺腿/1000x 拒绝；immediate 与 close 的每轮 fresh preflight、immediate 杠杆时机保持不变。smooth 复用固化数量/position mode/route，仍走既有 `prepare_attempt` 原子复核、两腿异步提交、查单、结算和单腿暂停链；放弃的余额、规则、position mode、限频、路由变化拦截必须如实列为 Human 接受代价，不能包装成 fail-closed，也不能暗含修改 store/executor/live client/preflight provider。
4. **D16 顺序与放行后零联网可执行**：live smooth 且首轮未调度时，唯一一次杠杆设置必须早于任何订阅、gate 建立/恢复与首次滑点计算；失败时零订阅、零 gate、零 attempt、零订单。不得提前到建卡，不得在 `_dispatch_one_for_task` 对 smooth 再设置。顺序型回归必须能证明 `set_leverage → subscribe/open gate → market evaluation → prepare → dispatch`，且 market/manual/timeout 放行后没有 leverage、fresh preflight、网络读取或 sleep。
5. **计划内部与范围自洽**：§12.2 Allowed Files 足以完成五项必修和 D15/D16；测试路径真实存在；T2/T3/T4 已关闭。两份计划中合法超长值 `201`/格式非法 `400` 不再互相矛盾；历史 §1–§11 不得覆盖活动 §12；活动 `rework_count=3` 与 status 一致，任何当前文字都不得声称计划复核后可绕过 Human 上限选择自动派发实现。
6. 新假设场景须满足 `AGENTS.md` §1 Scenario Admission，给出当前证据与本轮实际影响；偏好、未来扩展及 L1/L2/L3 不得阻塞。若五组均满足且无当前证据支持的范围内缺口，返回 `ACCEPT`；`REWORK` 必须逐条给出 `in-range` 分类、证据和可执行修复要求。计划复核本身不再增加 `rework_count`。
7. 创建唯一 handoff，包含完整 Source Report、Required Reading、Human Brief 与 marker；`base_sha`/`delivery_sha` 使用本 packet 固定值。返回合规 `[TASK_RESULT v2]`，明确 `评审结论: ACCEPT（接受） | REWORK（返工）`、`问题记录`、`修复要求`。`ACCEPT` 不授权实现或任何外部动作。

# Stop

完成固定范围的只读计划复核、创建唯一 handoff 并返回结果后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得修改受审内容或状态，不得准备/启动实现，不得安装依赖、联网、控制服务、读取凭证、创建任务、下单、提交、合并、推送或部署。
