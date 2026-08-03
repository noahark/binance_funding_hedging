Identity:
- task_id: review-1-code
- target_role: Reviewer（Review-1 / HIGH_RISK）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 10
- required_skill: agents/skills/code-reviewer.md

Goal

对已固定的 HIGH_RISK 交付区间
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..0ef805303eb1cd1a9b33938d9e1df491a4b461f1`
做独立、只读的 review-1。交付包含 Claude-GLM（zhipu_glm）的后端路由与公共契约、Grok（xai）的
行情页展示；你是 DeepSeek（deepseek），与两位实现作者 provider 隔离。

核验代码、契约、schema、测试与前后端接缝是否忠实实现已接受方案。重点检查：

1. 仅正费率现货 BUY 新读 `maxCollateralExceededAsset`；命中额度名单或 bStock 才走
   `regular_spot`，负费率现货 SELL 不读名单且永远保留 PAPI；不读不存
   `openLongRestrictedAsset`。
2. 普通现货下单/查单是否都使用固定 `api.binance.com` 标准 Spot endpoint、无
   `sideEffectType`、独立 `PRODUCT_SPOT` 错误分类；每条 leg 的持久化 endpoint 是否是查单和
   原始响应记录的唯一权威；PAPI 合约腿是否未改变。
3. allowlist 是否 deny-by-default、五条 method/path 是否精确且 host 不可覆盖；
   restricted-asset 是否只带 API key、不签名；展示缓存和每次预检新读是否严格隔离。
4. SnapshotService 组合根注入是否独立于 executor/private channel、构造不发请求、不改 Start gate；
   `collateral_cap` 的已满/未满/未知/不适用、失败即未知、checked_at 与 ui_flags 是否一致。
5. v0.9 contract/schema 是否 additive 且相互一致；前端是否只消费可选字段、在标的列高亮、使用
   `collateral_cap.asset`（bStock 如 TSLAB）、不按费率方向过滤，也不影响排序、过滤或开单按钮。
6. 测试是否真能覆盖上述路径、没有真实 Binance 调用、凭证暴露、DB migration 或 Start gate 变化。

所有发现必须按 `AGENTS.md` §8 标为 `in-range`、`pre-existing-independent` 或
`pre-existing-release-critical`；后两类若主张范围外，必须附早于 base 的 `git blame` 或
`git log -L` 证据。没有明确、可复现的问题则返回 `ACCEPT`。

Allowed Files

- 无；本任务只读，不得修改、暂存、提交或生成仓库文件。

Inputs

- `AGENTS.md`
- `agents/roles.md` Reviewer section
- `agents/skills/code-reviewer.md`
- `PROJECT_STATE.md`
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-implementation-backend-2-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-implementation-frontend-1-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/implementation-backend-2.claude-glm.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/implementation-frontend-1.grok.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- 仅从固定 Git 区间读取相关源文件、测试与 diff；不得以移动 HEAD 或未提交工作区代替该区间。

Acceptance Checks

- 先执行并记录：`git rev-parse 1a55781a5f80ee5b3e15d7124003af2dda73f0d5`、
  `git rev-parse 0ef805303eb1cd1a9b33938d9e1df491a4b461f1`、
  `git diff --check 1a55781a5f80ee5b3e15d7124003af2dda73f0d5..0ef805303eb1cd1a9b33938d9e1df491a4b461f1`。
- 对固定区间和受影响的测试做可复现的只读检查；可运行任务卡已有 fake-transport pytest 命令及
  `node frontend/self-check.js`，但不得读取真实凭证或向外网发请求。
- 以完整 `[TASK_RESULT v2]` 返回，并含 `评审结论`、`问题记录`、`修复要求`；`REWORK` 必须提供
  可执行的最小修复要求，`ACCEPT` 才可进入 review-2。

Stop

- 不得修改任何文件、暂存、提交、推送、合并、部署、启动服务或改变 Start gate。
- 不得调用 Binance、使用/输出凭证、发单、转账或触发其他外部副作用。
- 不得审查移动 HEAD、未提交工作区或任务回执代替固定 Git 区间。
- 完成只读评审后停止；Human 将原始回执交回 Bookkeeper。review-1 未明确 ACCEPT 前，不得启动
  review-2。
