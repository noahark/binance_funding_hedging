Identity:
- task_id: plan-rework-1
- target_role: Planner
- target_model: Opus5
- provider: anthropic
- status_revision: 2
- required_skill: agents/skills/task-planner.md

Goal

修订 `docs/planning/spot-order-routing-v1.md`，仅闭环已被独立计划评审确认的两项 in-range 缺陷：

1. 路由只在正费率方向（现货 `BUY`）读取 `restricted-asset` 并可能选择 `regular_spot`。
   负费率方向（现货 `SELL`）不得读取名单、不得选择普通现货；即使 bStock 或命中名单，仍走
   既有 PAPI 路径。平仓仍留给后续阶段。
2. 保持 HedgeOpenLiveClient 的 deny-by-default allowlist，不得绕过；为本轮新使用的端点明确
   登记并硬绑定 `https://api.binance.com`：
   `("GET", "/sapi/v1/margin/restricted-asset")`、
   `("POST", "/api/v3/order")`、
   `("GET", "/api/v3/order")`、
   `("GET", "/api/v3/account")`、
   `("GET", "/api/v3/rateLimit/order")`。
   预检与展示两条读取都受该 allowlist 管控；不得把 host 交给调用方。

这些是 Human 已定裁定，不得重新打开。修订后准备再次由非 Anthropic provider 执行只读、跨
provider 的计划评审；本任务本身不授权实现。

Allowed Files

- `docs/planning/spot-order-routing-v1.md`

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（尤其 Bookkeeper 补充裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-1.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-plan-review-1-verification.md`
- 仅为定位修订而读取方案点名的 `backend/hedge_open_tasks/domain.py` 与
  `backend/services/hedge_open_live_client.py`。

Acceptance Checks

- §3 在读取限制名单之前明确按方向分支：仅正费率/现货 BUY 可读取名单及选
  `regular_spot`；负费率/现货 SELL 不读取名单、不选 `regular_spot`、维持既有 PAPI。
- §9 新增可验证检查：负费率方向即使命中名单或为 bStock，仍走既有 PAPI 路径。
- §4 和 §8 明确上述五个 `(method, path)` 均为 `api.binance.com` 的 exact allowlist 条目，
  host 硬绑定；`restricted-asset` 的预检与展示读取均不绕过该管控。
- §9 新增可验证检查：allowlist 含上述五条，未登记路径调用被拒。
- 不改写或重开已有六项 Human 裁定；不改范围、不加实现设计，不修改任何代码、契约、schema、
  状态、原始证据或凭证。
- 在最终回执中说明具体修改位置，并以合规 `[TASK_RESULT v2]` 收尾。

Stop

- 不得调用 Binance、读取或使用凭证、启动服务、发单、修改 Start gate、提交或合并。
- 完成方案的最小修订和自校验后停止；由 Human 将原始回执交回 Bookkeeper。下一次独立计划
  评审必须使用非 Anthropic provider；其 ACCEPT 前不授权实现、开闸或实盘。
