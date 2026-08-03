Identity:
- task_id: task-breakdown-1
- target_role: Planner
- target_model: Opus5
- provider: anthropic
- status_revision: 5
- required_skill: agents/skills/task-planner.md

Goal

将已获 DeepSeek ACCEPT 的 `spot-order-routing-v1` 方案拆成不重叠、可独立验收的后端与前端
实现任务，先写清两者共用的公共快照 v0.9 接口。目标是让 Claude-GLM 只做后端、Grok 只做
前端，二者不会对字段、三态、匹配口径或缓存边界各自猜测。

产出下列四个文件：

1. `implementation-interface-v0.9.md`：实现前约定，明确 `rows[].collateral_cap` 的完整形状、
   `ui_flags` 的精确值与何时出现、`checked_at` 格式/缺失规则、三态语义、bStock/现货 base asset
   匹配口径、展示“不按费率正负过滤”、以及展示缓存绝不供预检使用。它是实现输入；最终对外
   权威仍由后端任务写入 `docs/api/public-market-contract.md` 的 v0.9 amendment。
2. `implementation-backend-2.dispatch.md`：目标 `claude_glm`，只包含路由、Binance client、
   SnapshotService、schema/最终公共契约、后端测试；写明它先提交可供前端消费的固定 delivery SHA。
3. `implementation-frontend-1.dispatch.md`：目标 `Grok`，只包含静态 UI、fixture 与 self-check；
   必须以 backend-2 提交的 v0.9 contract 为输入，显示命中资产而不按正/负费率过滤，且不能触发
   Binance 或消费预检缓存。
4. `task-breakdown-1.md`：列出顺序、文件边界、各自测试、前后端接缝验收以及之后的固定
   `base_sha..delivery_sha` review-1 / review-2 路由。

已有 `implementation-backend-1.dispatch.md` 已被 Human 指令取代，不得修改或复用为新任务。
不得改写已 ACCEPT 的产品边界；若发现方案不足以定义接口，停止并将问题上交 Human。

Allowed Files

- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-backend-2.dispatch.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-frontend-1.dispatch.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/task-breakdown-1.md`

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/spot-order-routing-v1.md`（唯一详细产品设计）
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§D、§E 是已定 Human 裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-2.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-plan-review-2-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-backend-1.dispatch.md`（仅作被替代范围的参考）
- 仅为拆分边界而读取方案点名的后端、前端、契约、schema 与现有测试。

Acceptance Checks

- 接口约定不另造产品规则，且明确：`collateral_cap` 独立于 `margin_public` 和
  `negative_funding_status`；展示命中不看费率符号；未知不得显示为未满；展示缓存与开单预检不共用。
- 后端与前端 Allowed Files 互不重叠；共享 JSON 形状只在 `implementation-interface-v0.9.md` 中详细
  定义，最终公共权威明确指向后端交付的 `docs/api/public-market-contract.md` v0.9。
- backend-2 包含路由方向、普通现货 exact allowlist、endpoint 审计、数据契约/schema 和 fake
  transport/后端测试；frontend-1 包含资产列高亮、三态/时间戳、fixture、自检，且不改后端代码。
- frontend-1 明确在 backend-2 本地提交及 Bookkeeper 固定 SHA 后再启动；不得基于臆测或本地未提交
  字段开发。
- 两张 implementer dispatch 各有 exactly one `senior-developer.md` skill、明确测试命令、提交边界、
  无凭证/无 Binance/无真实 POST/不改 Start gate 的 Stop 条款。
- 在最终回执中列明四份产物与每个任务的启动顺序，使用合规 `[TASK_RESULT v2]` 收尾。

Stop

- 不得编辑方案、契约、schema、代码、状态、证据或现有 dispatch；不得调用 Binance、读取/使用凭证、
  启动服务、发单、提交或合并。
- 仅完成四份规划产物后停止，由 Human 将原始回执交回 Bookkeeper。拆分本身不授权任何实现或实盘。
