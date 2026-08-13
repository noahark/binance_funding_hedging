# Identity

- task_id: `smooth-open-v1-repair-plan-opus5-r2`
- target_role: `Planner`
- target_model: `claude-opus-5`
- provider: `anthropic`
- status_revision: `28`
- required_skill: `agents/skills/task-planner.md`

# Goal

对上一轮未提交的平滑开单返修计划做一次四点微型返修，只关闭 Bookkeeper Verification 的 T1–T4。不得重新设计、重排或扩写其他内容；D15/D16、三项 Human 接受风险、五项必修根因、单 Implementer 路由与停止线均已通过本轮核验，不得重开。

这是首次交付后的第二个正式返修任务，`rework_count=2`。它只修计划内部矛盾，不授权代码实现、计划评审、安装依赖、联网、服务控制、凭证、任务、订单、push、merge、部署或实盘。

# Allowed Files

仅允许修改当前工作树中已有未提交改动的：

- `docs/planning/smooth-open-orders-v1.md`
- `docs/planning/smooth-open-orders-v1-development-checklist.md`

仅允许新建唯一交接件：

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r2.handoff.md`
- Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5-r2.handoff.md` 已通过。

预期的既有未提交文件只有上述两份 planning 文件与上一轮只读 handoff `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`；不得编辑上一轮 handoff。禁止修改任何源码、测试、其他文档、dispatch、status、ACTIVE、PROJECT_STATE、`.venv`；禁止 commit/amend/push/merge。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/16-smooth-open-v1-repair-plan-opus5-r2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Planner 与 Task Handoff Evidence Contract 两节
7. `agents/skills/task-planner.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`，只读其 Bookkeeper Verification 的 T1–T4
9. `docs/planning/smooth-open-orders-v1.md`
10. `docs/planning/smooth-open-orders-v1-development-checklist.md`
11. 为 T4 只读 `backend/tests/test_service_health.py` 中 `_build_hedge_service` 既有测试位置；不要扩展源码扫描。

启动核对：cwd `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`，分支 `smooth/v1-fullstack`，status revision `28`、本 task/model/provider 一致，`base_sha=e4027bd7c88e489b8024b531f40cf3cd53555485`，工作树已有变更恰为两份 planning 文件与上一轮 handoff，新 handoff 不存在。任一不一致即 blocked。

# Acceptance Checks

1. **T1 — 超长 threshold 契约**：只改清单 §12.3 必修 3 的确定性验收歧义。合法正负超长整数（30 位、100 位）必须在 domain 中正常规范化为两位小数字符串，并在注入 fake provider 的 API 创建路径正常被接受（不得因长度返回 400/500）；`-0` 归一 `0.00`、`.05` 归一 `0.05`。只有超过两位小数、科学记数、`%`、空值等格式非法输入才返回 400。不得新增长度上限、Decimal context 调整或新依赖。
2. **T2 — 展开日志刷新单一口径**：只更正设计 D12 与任务卡动态盘口段中两处旧句。新口径必须与 §9/§13/§16 一致：任务仍存在且日志展开时，无论 running/paused/deleted/done/stopped，均复用共享 2 秒 tick 刷新；收起或任务已不存在才停止。不得改变“不新增 timer”、后端 WS 评估独立于 UI 轮询、收起态 fill-once 额外 GET 等其他语义。
3. **T3 — 重启后的 smooth 门**：只更正设计 §6.1 的“仍需重新经过任务状态、Start gate 和现有 preflight 才可能发单”。D15 后应写为：首次未调度时先按 D16 在订阅/gate 恢复前设置杠杆，随后仍须任务状态、Start gate 与 `prepare_attempt` 原子复核；smooth 不再有每轮 fresh preflight。不要改停机计入五分钟、原 gate/deadline/force 恢复或 L1/L2 接受风险。
4. **T4 — 精确 Allowed Files**：只改清单 §12.2 测试列表，把每个测试路径写成完整仓库相对路径，并把模糊的“组合根离线断言所需的既有服务器测试文件”替换为唯一实际路径 `backend/tests/test_service_health.py`。不得顺手增加其他测试或生产文件。
5. 除 T1–T4 对应的四个文本单元外，不改变任何决策、风险、根因、实现要求、验收命令、角色、模型、rework 数、停止线或复核请求。`git diff --word-diff=plain` 应能清楚定位这四类更正，`git diff --check` 无输出。
6. 创建合规唯一 handoff，列出最终相对原 base 的累计文件范围与本轮精确更正；不提交、不改状态、不启动 Reviewer，返回 Human Brief 的 `[TASK_RESULT v2]`。

# Stop

四点文字修正、自检和唯一 handoff 完成后立即停止。不得实现代码、准备计划复核 dispatch、安装依赖、联网、启停服务、读取凭证、创建任务、下单、提交、push、merge、部署或实盘。
