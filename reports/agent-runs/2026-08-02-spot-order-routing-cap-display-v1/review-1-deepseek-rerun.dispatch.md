Identity:
- task_id: review-1-code-rerun
- target_role: Reviewer（Review-1 rerun / HIGH_RISK）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 12
- required_skill: agents/skills/code-reviewer.md

Goal

以**全新、只读会话**重跑 HIGH_RISK review-1，审查固定交付区间
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`。
DeepSeek（deepseek）与两位实现作者 Claude-GLM（zhipu_glm）和 Grok（xai）provider 隔离。

上一轮唯一 `in-range` 根因是 `test_stub_signature_drift`：生产调用增加 `direction` / `endpoint`，
两个旧回归文件的 fake 未同步，导致 77 failed。修复提交 `3a07f4a` 只应改两份测试文件，并应让其显式
接受、转发新增参数且补齐同根因的 `prepare_attempt(... spot_endpoint=...)` fake 调用。

重新审查**完整固定区间**，确认该根因已消除且没有回退上一轮已通过的六项：路由方向、普通现货
endpoint/审计权威、allowlist 与缓存隔离、SnapshotService 组合根与四态展示、v0.9 contract/schema/
前端接缝、无真实请求/凭证/DB migration/Start gate 变更。

所有发现必须按 `AGENTS.md` §8 标为 `in-range`、`pre-existing-independent` 或
`pre-existing-release-critical`；后两类主张范围外时必须附早于 base 的 `git blame` 或 `git log -L`
证据。没有明确、可复现的问题则返回 `ACCEPT`。

Allowed Files

- 无；本任务只读，不得修改、暂存、提交或生成仓库文件。

Inputs

- `AGENTS.md`
- `agents/roles.md` Reviewer section
- `agents/skills/code-reviewer.md`
- `PROJECT_STATE.md`
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/fix-review-1-test-stubs.claude-glm.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-1-rework-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-fix-review-1-test-stubs-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- 仅从固定 Git 区间读取源文件、测试和 diff；不得以移动 HEAD 或未提交工作区代替该区间。

Acceptance Checks

- 先执行并记录：`git rev-parse 1a55781a5f80ee5b3e15d7124003af2dda73f0d5`、
  `git rev-parse 3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`、
  `git diff --check 1a55781a5f80ee5b3e15d7124003af2dda73f0d5..3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`。
- 明确核验 `0ef8053..3a07f4a` 只改两份测试文件、77 个 TypeError 根因被消除、14 文件回归命令可全绿。
- 对完整固定区间和受影响测试做可复现只读检查；可运行 fake-transport pytest 与
  `node frontend/self-check.js`，但不得读取真实凭证或向外网发请求。
- 以完整 `[TASK_RESULT v2]` 返回，并含 `评审结论`、`问题记录`、`修复要求`；仅明确 `ACCEPT`
  才可进入 Opus5 的 review-2。

Stop

- 不得修改任何文件、暂存、提交、推送、合并、部署、启动服务或改变 Start gate。
- 不得调用 Binance、使用/输出凭证、发单、转账或触发其他外部副作用。
- 不得审查移动 HEAD、未提交工作区或任务回执代替固定 Git 区间。
- 完成只读评审后停止；Human 将原始回执交回 Bookkeeper。review-1 未明确 ACCEPT 前，不得启动 review-2。
