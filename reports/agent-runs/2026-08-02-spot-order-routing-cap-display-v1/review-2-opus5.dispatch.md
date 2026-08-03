Identity:
- task_id: review-2-reality
- target_role: Reviewer（Review-2 / HIGH_RISK）
- target_model: Opus5
- provider: anthropic
- status_revision: 13
- required_skill: agents/skills/reality-checker.md

Goal

以全新、只读会话对固定交付区间
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`
做 HIGH_RISK review-2：判断它是否真正实现 Human 已裁定的业务效果、证据是否足够、是否存在上线前
必须说明的实际风险。实现作者为 Claude-GLM（zhipu_glm）和 Grok（xai）；你是 Opus5（anthropic），
provider 隔离成立。

**披露**：你曾参与本 stage 的方案整合与前后端任务拆分。因此不得重开或代替 Human 改写已定业务
裁定，也不得只复述自己的规划；必须独立审查固定代码、契约、测试与实际效果。此设计参与不改变你
与实现作者 provider 隔离的事实。

以小白话核验以下效果是否都真的成立：

1. 正费率方向现货买入：被全平台 `maxCollateralExceededAsset` 名单限制的资产，或 bStock，走普通
   Spot；其他走原有统一账户 PAPI。负费率方向现货卖出始终 PAPI，不因名单或 bStock 切到普通 Spot。
2. 普通 Spot 路径从预检、下单、查单到审计完整，且不会携带统一账户的 `sideEffectType` 或错误地把
   51169 当作原路径继续处理；leg.endpoint 确实是日后查单的唯一事实来源。
3. 行情页只用名单做展示：任何费率方向命中都在标的列高亮；未满不冒充“可用”，读取失败明确未知，
   无现货腿不显示徽标；展示缓存绝不喂开单预检。
4. 本轮边界没有被偷偷突破：不读取 `openLongRestrictedAsset`，不做普通 Spot 自动补腿、不做平仓、
   不新增运行时权限探测或环境变量、不改变 Start gate、无数据库迁移。要明确指出仍留下的实际操作
   前提或风险，但不要把 Human 已接受的非目标误记成代码缺陷。
5. 开发与修复证据是否可信：569 回归、前端 self-check、fake transport、精确 allowlist、公共契约
   v0.9 是否足以支撑当前阶段进入 Human 最终决定，而不授权合并、部署或实盘。

所有发现必须按 `AGENTS.md` §8 标为 `in-range`、`pre-existing-independent` 或
`pre-existing-release-critical`；后两类若主张范围外，须附早于 base 的 `git blame` 或 `git log -L`
证据。所有发现都在范围外时仍返回 `ACCEPT`，并将事项清楚交给 Human。

Allowed Files

- 无；本任务只读，不得修改、暂存、提交或生成仓库文件。

Inputs

- `AGENTS.md`
- `agents/roles.md` Reviewer section
- `agents/skills/reality-checker.md`
- `PROJECT_STATE.md`
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-implementation-backend-2-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-implementation-frontend-1-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-1-rework-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-fix-review-1-test-stubs-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-1-rerun-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code-rerun.deepseek.raw.md`
- 仅从固定 Git 区间读取相关源码、测试、diff 与原始回执；不得以移动 HEAD 或未提交工作区代替。

Acceptance Checks

- 先执行并记录：`git rev-parse 1a55781a5f80ee5b3e15d7124003af2dda73f0d5`、
  `git rev-parse 3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`、
  `git diff --check 1a55781a5f80ee5b3e15d7124003af2dda73f0d5..3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`。
- 独立追踪从“名单命中”到“实际发哪个请求、怎样查单、页面怎样显示”的证据链，不得仅采信设计或
  review-1 摘要；必要时运行 fake-transport 测试与 `node frontend/self-check.js`，不得读取真实凭证
  或向外网发请求。
- 明确把“代码缺陷”与“Human 接受的本轮非目标/运营前提”分开；若存在 release-critical 的既有风险，
  按范围规则附 base 前证据并上交 Human。
- 以完整 `[TASK_RESULT v2]` 返回，并含 `评审结论`、`问题记录`、`修复要求`。只有明确 `ACCEPT`
  才会交由 Bookkeeper 向 Human 汇报最终技术结论。

Stop

- 不得修改任何文件、暂存、提交、推送、合并、部署、启动服务或改变 Start gate。
- 不得调用 Binance、使用/输出凭证、发单、转账或触发其他外部副作用。
- 不得重开 Human 已定的业务裁定；发现真实风险可报告，但不得将其自行扩大为新实现范围。
- 完成只读评审后停止；Human 将原始回执交回 Bookkeeper。review-2 未明确 ACCEPT 前，不授权合并、
  部署或实盘。
