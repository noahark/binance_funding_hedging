Identity:
- task_id: interface-amendment-review-1
- target_role: Reviewer（HIGH_RISK 接口修订复核）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 7
- required_skill: agents/skills/code-reviewer.md

Goal

以全新、只读、跨 provider 会话复核 Human 的 §E-4 三项接口裁定及其在方案、实现前接口约定和
backend-2 任务卡中的同步。审查范围只限展示失败真值、不适用、以及 SnapshotService 的只读 client
组合根路径；不得重新打开已 ACCEPT 的下单路由、常规展示边界或 Human 已定裁定。

Allowed Files

- 无。只读；不得编辑代码、文档、状态、证据、凭证或 git 状态。

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/spot-order-routing-v1.md`（§6、§8、§9）
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§E-4）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-backend-2.dispatch.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/task-breakdown-1.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-task-breakdown-1-boundary-audit.md`
- 仅为核验组合根与既有安全边界读取 `backend/app/server.py`、`backend/config.py`、
  `backend/services/snapshot_service.py`、`backend/services/hedge_open_live_client.py` 及相关测试。

Acceptance Checks

- §E-4 与三个实现输入一致：任意展示刷新失败输出未知，不投影 last-good；无可解析现货腿是不适用、
  不显示徽标、不称未满；两者均不改变每次预检的新鲜读取。
- `collateral_cap` 真值表保持：有现货腿行仅已满/未满/未知三态；不适用在三态外，`asset=null`、
  无抵押额度 flag，前端表外组合仍 fail-closed 为未知。
- SnapshotService 负责缓存/展示；应用组合根使用已有 hedge API key 创建受 exact allowlist 与 host
  硬绑定保护的 client 注入它，独立于 `APP_HEDGE_EXECUTOR`、private channel 与 Start gate。该服务
  仅可调用不签名的 restricted-asset GET；下单 client 在非 live 时不得发送订单。
- backend-2 的 Allowed Files 和 Stop 允许实现该组合根注入，但不允许新环境变量、配置项、订单开关、
  真实请求或前端改动。
- 明确检查该修订没有放宽 §3 预检、把展示缓存接回预检、改变负费率 PAPI 边界，或将额度状态放入
  `negative_funding_status`。
- 以合规 `[TASK_RESULT v2]` 收尾，并附 `评审结论: ACCEPT（接受） | REWORK（返工）`；每个 REWORK
  发现标注范围分类与可执行修复要求。明确 ACCEPT 前，不得启动任何 implementer。

Stop

- 不得调用 Binance、读取或使用凭证、启动服务、执行订单相关 POST、变更 Start gate、提交、合并或推送。
- 仅完成只读复核后停止；由 Human 将原始结果交回 Bookkeeper。ACCEPT 不授权实盘。
