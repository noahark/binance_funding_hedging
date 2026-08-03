Identity:
- task_id: plan-review-2
- target_role: Reviewer（HIGH_RISK 独立计划复审）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 3
- required_skill: agents/skills/code-reviewer.md

Goal

以全新、只读会话复审 `docs/planning/spot-order-routing-v1.md`。本稿原作者为 Opus5（Anthropic），
且已由 Codex（OpenAI）按 Human 明确指令直接完成两项最小修订；DeepSeek 与两位作者均跨
provider。本次确认上次 `plan-review-1` 的两项 in-range 缺陷已经闭环，且没有破坏既有 Human
裁定或安全边界。

Allowed Files

- 无。只读；不得编辑代码、文档、状态、证据、凭证或 git 状态。

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§D、§E 均为 Human 已定裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/plan-review-1.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-plan-review-1-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-direct-plan-rework-1.md`
- 仅在核验接缝时读取方案点名的源文件、契约、schema、前端及相应测试。

Acceptance Checks

- §3 明确仅正费率/现货 BUY 可读取 `restricted-asset` 并选 `regular_spot`；负费率/现货 SELL
  不读取名单、不选普通现货，即使命中名单或为 bStock 仍走既有 PAPI；§9 有对应可验证检查。
- §4、§8、§9 对下列五个 exact allowlist 条目、`https://api.binance.com` 硬绑定、预检和展示
  都受管控、未登记路径拒绝，表述一致：
  `("GET", "/sapi/v1/margin/restricted-asset")`、
  `("POST", "/api/v3/order")`、`("GET", "/api/v3/order")`、
  `("GET", "/api/v3/account")`、`("GET", "/api/v3/rateLimit/order")`。
- 复核 §D、§E 的所有 Human 裁定没有被重开，且 §1.2 的普通现货 SELL 非目标、§6 缓存隔离、
  endpoint 唯一权威、展示三态、契约三闸门与 v0.9 amendment 均未回退。
- 按 `AGENTS.md` §8 标注每项发现的范围分类。以合规 `[TASK_RESULT v2]` 收尾，并附
  `评审结论: ACCEPT（接受） | REWORK（返工）`；只有明确 ACCEPT 才允许 Bookkeeper 准备实现
  dispatch。

Stop

- 不得调用 Binance、读取或使用凭证、启动服务、执行交易相关 POST、变更 Start gate、提交或合并。
- 完成只读复审后停止；由 Human 将原始结果交回 Bookkeeper。无论 verdict 如何，均不授权实盘。
