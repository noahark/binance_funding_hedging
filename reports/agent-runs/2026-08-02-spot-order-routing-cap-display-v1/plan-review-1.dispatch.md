Identity:
- task_id: plan-review-1
- target_role: Reviewer（HIGH_RISK 独立计划评审）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 1
- required_skill: agents/skills/code-reviewer.md

Goal

对 `docs/planning/spot-order-routing-v1.md` 的下单路由（A）和行情页展示（B）进行独立、只读的 HIGH_RISK 计划评审。确认它能在不触碰 Human 已定边界的前提下安全实现，特别审查“共用现货 base-asset 解析规则、绝不共用展示缓存数据”的接缝。计划作者是 Opus5，本次由 DeepSeek 提供跨 provider 独立性。

Allowed Files

- 无。只读；不得编辑代码、文档、状态、证据、凭证或 git 状态。

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`（§D 的六项 Human 裁定不得在无新事实证据时重开）
- `docs/planning/spot-order-routing-v1.review-opus5.md`
- `docs/planning/spot-order-routing-v1.review-opus5-r2.md`
- `reports/api-samples/2026-08-spot-order-routing-v1/`
- 仅在核验接缝时读取方案点名的源文件、契约、schema、前端及相应测试。

Acceptance Checks

- 核验 §D 的六项 Human 裁定均已忠实进入方案；没有把它们重述成未决问题。
- 核验 Bookkeeper 注记已解决证据目录的字面 `SPOT` blocker 矛盾，且 `PROJECT_STATE.md` 具备事实、影响、接受理由、观察方式、重审条件。
- 核验下单 attempt 的 endpoint、symbol、route 读取权威，普通现货 endpoint/host/params/查单/错误分类/限频和 PAPI 合约腿边界完整。
- 核验展示三态、时间戳、独立 `collateral_cap` 数据块与资产高亮位置；不得污染借贷状态列。
- 核验展示缓存不能被预检消费，且解析后的现货 base asset 规则在两条路径中只有一处实现。
- 核验公共契约解除 no-key 后的三条闸门、`margin_public.source` 真值更正和 v0.9 amendment 要求明确。
- 以正式 `[TASK_RESULT v2]` 收尾，并附 `评审结论: ACCEPT（接受） | REWORK（返工）`。若 REWORK，逐项标注范围分类、证据、可执行修复要求；若 ACCEPT，说明仍存的 Human 已接受风险和不在本轮的边界。

Stop

- 不得调用 Binance、读取或使用凭证、启动服务、执行交易相关 POST、变更 Start gate、提交或合并。
- 完成只读评审后停止；由 Human 将原始结果交回 Bookkeeper。评审 ACCEPT 不授权实现、开闸或实盘。
