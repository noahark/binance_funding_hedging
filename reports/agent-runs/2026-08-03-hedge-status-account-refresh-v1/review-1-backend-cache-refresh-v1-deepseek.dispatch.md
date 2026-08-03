Identity:
- task_id: `review-1-backend-cache-refresh-v1-deepseek`
- target_role: `Reviewer`
- target_model: `deepseek`
- provider: `deepseek`
- status_revision: `3`
- required_skill: `agents/skills/code-reviewer.md`

Goal

以独立、只读方式审查后端缓存刷新交付的固定范围 `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2`。实现作者为 `claude_glm`（Zhipu），本评审为 DeepSeek provider，满足 Review-1 隔离。上一份 Kimi Review-1 包因 Human 报告无额度而未启动、无 handoff，保留为可追溯的未执行记录；本包是它的唯一替代。核对唯一 worker refresh cycle、精确 TTL 绕过、source_checked_at 契约、POST 的纯入队语义、状态钩子、schema/API seam、测试有效性与既有安全边界。`git diff --check` 报告的文档末尾空行可作为非功能观察评估，不得掩盖任何真实功能缺陷。

Allowed Files

- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/review-1-backend-cache-refresh-v1-deepseek.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Reviewer 与 Task Handoff Evidence Contract 章节
- `agents/skills/code-reviewer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`
- 固定 diff `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2` 及其触及的代码、schema、契约、测试与 pytest 证据

Acceptance Checks

1. 只审固定 diff，逐项对照 v4 设计与 backend dispatch；确认不越界到订单、借贷、凭证、部署或前端。
2. 验证三触发者共用 worker-only cycle、force 精确绕过、`RefreshResult`/`RefreshCacheCommand`、异常隔离和 accepted 合并窗口的事实性。
3. 验证五 key source 时间、PM/null、last-good、既有聚合时间、snapshot/positions meta、strict schema 和 API contract 的一致性。
4. 验证 POST 只入队/等待、GET pure-read、提交后的真实 `running → 非 running` 钩子、回调失败不回滚及 store 写路径覆盖。
5. 审查新增测试是否覆盖关键 seam；必要时仅复跑安全离线检查。所有发现按 `in-range`、`pre-existing-independent` 或 `pre-existing-release-critical` 分类；范围外必须附早于 base 的引入证据。

Stop

不得修改代码、测试、契约、status、PROJECT_STATE 或既有证据。完成后只创建规定 handoff：`delivery_sha` 填 `8b624f733362e3a523d7f06613534af4f2451ad2`，含明确 `ACCEPT` 或 `REWORK`、范围分类、证据、可执行修复要求与 Human Brief；然后停止，不启动后续模型。
