Identity:
- task_id: `review-2-backend-cache-refresh-v1`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `4`
- required_skill: `agents/skills/reality-checker.md`

Goal

对固定交付范围 `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2` 做独立 Review-2：判断它是否实现 Human 批准的缓存刷新实际效果、是否会改变 60 秒更新的上游成本、按钮与状态钩子是否如实、以及是否具备进入前端接线任务的条件。实现作者为 `claude_glm`/Zhipu，Review-1 为 DeepSeek；本 reviewer 为 Anthropic，符合与所有实现/修复作者隔离。披露：Opus5 曾参与本功能的实现前计划评审，但未实现或审查此代码；请独立检查源码与证据，不以旧计划意见代替实际效果。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-2-backend-cache-refresh-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/review-2-backend-cache-refresh-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 章节
- `agents/skills/reality-checker.md`
- `docs/planning/hedge-status-account-refresh-v4.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md`
- 固定 diff `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2`、原始 pytest 证据与 `PROJECT_STATE.md` 的既有限制

Acceptance Checks

1. 对照 Human 批准的 v4，确认功能实际实现“一个刷新周期、三个触发者、账户源时间可见、无状态变更前端自动刷新”的边界，而非只满足单元测试。
2. 审查强制刷新与约 60 秒 tick 的共存、429/上游成本、in-flight 合并窗口、partial/未尝试语义与操作员可见性是否诚实并与 Human 已接受取舍一致。
3. 审查 POST、worker、schema、任务状态变更和现有 Start gate/F4/私有通道风险的真实影响；确认没有引入订单、借贷、凭证、部署或实盘副作用。
4. 评估交付和 Review-1 的非阻塞观察是否应改变发布准备度。所有发现按 `in-range`、`pre-existing-independent` 或 `pre-existing-release-critical` 分类，范围外必须附早于 base 的引入证据。

Stop

不得修改代码、测试、契约、status、PROJECT_STATE 或既有证据。完成后只创建规定 handoff：`delivery_sha` 填 `8b624f733362e3a523d7f06613534af4f2451ad2`，含明确 `ACCEPT` 或 `REWORK`、范围分类、事实证据、可执行修复要求与 Human Brief；然后停止，不启动后续模型。
