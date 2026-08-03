Identity:
- task_id: review-2-reality-rerun
- target_role: Reviewer（Review-2 rerun / HIGH_RISK）
- target_model: Opus5
- provider: anthropic
- status_revision: 16
- required_skill: agents/skills/reality-checker.md

Goal

以**全新、只读会话**对固定交付区间
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..e99974ad934af5117b0c2385e5545f9861812d5d`
重跑 HIGH_RISK review-2：判断修复后是否真正实现 Human 已裁定的业务效果、证据是否足够、是否仍有
合并前必须交给 Human 的实际风险。实现/修复作者为 Claude-GLM（zhipu_glm）和 Grok（xai）；你是
Opus5（anthropic），provider 隔离成立。

**披露**：你曾参与本 stage 的方案整合与前后端任务拆分，也完成了上一轮 review-2。因此不得重开或
代替 Human 改写已定业务裁定，必须独立审查固定代码、契约、测试与实际效果，不能只复述自己先前的
规划或回执。该设计参与不改变你与实现作者 provider 隔离的事实。

上一轮 review-2 的两个 `in-range` 发现须复核为真正关闭：

1. `test_hedge_purity.py` 必须精确守住 12 条已授权 endpoint——7 条 PAPI 硬绑
   `https://papi.binance.com`、5 条普通 Spot / 名单 endpoint 硬绑 `https://api.binance.com`；必须仍有
   精确相等、长度、分组 host 和未知路径签名前 fail-closed 的保护，不能用缩小守卫或跳过测试掩盖。
2. `hedge_open_live_client.py` 的模块说明必须与运行事实相符：订单执行路径仍 default-off，展示 client
   由组合根独立注入、只读名单 GET；此次更正不得夹带运行时代码变动。

以小白话独立核验以下业务效果是否都成立：

1. 正费率方向现货买入：命中全平台 `maxCollateralExceededAsset` 名单的资产，或 bStock，走普通 Spot；
   其他走统一账户 PAPI。负费率方向现货卖出始终 PAPI，不因名单或 bStock 切到普通 Spot。
2. 普通 Spot 从预检、下单、查单到审计闭环，不携带统一账户的 `sideEffectType`，也不把 51169 当作原
   路径继续处理；leg.endpoint 是日后查单的唯一事实来源。
3. 行情页的名单高亮不看费率方向，显示在标的列；未满不冒充“可用”，读取失败明确未知、无现货腿不
   显示徽标，展示缓存绝不喂开单预检。
4. 不突破已定边界：不读取 `openLongRestrictedAsset`，不做普通 Spot 自动补腿或平仓，不新增运行时权限
   探测/环境变量，不改变 Start gate，无数据库迁移。要分清代码缺陷和 Human 接受的运营前提/非目标。
5. 开发与修复证据是否可信：全量 1215 pytest、前端 self-check、fake transport、精确 allowlist、公共
   契约 v0.9 是否足以支持进入 Human 最终技术决定；这不授权合并、部署或实盘。

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
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code-rerun.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-2-reality.opus5.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/fix-review-2-allowlist-guard-scan.claude-glm.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code-rerun-2.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-2-rework-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-fix-review-2-allowlist-guard-scan-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-1-rerun-2-verification.md`
- 仅从固定 Git 区间读取相关源码、测试、diff 与原始回执；不得以移动 HEAD 或未提交工作区代替。

Acceptance Checks

- 先执行并记录：`git rev-parse 1a55781a5f80ee5b3e15d7124003af2dda73f0d5`、
  `git rev-parse e99974ad934af5117b0c2385e5545f9861812d5d`、
  `git diff --check 1a55781a5f80ee5b3e15d7124003af2dda73f0d5..e99974ad934af5117b0c2385e5545f9861812d5d`。
- 独立追踪名单命中到实际请求、查单、展示的证据链，不得只采信设计或 review-1 摘要；必要时运行
  fake-transport 测试及 `node frontend/self-check.js`，不得读取真实凭证或向外网发请求。
- 重新运行或审计全量命令 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider`，
  并明确确认 12-endpoint 冻结守卫有效。
- 明确把代码缺陷与 Human 接受的本轮非目标/运营前提分开；若存在 release-critical 的既有风险，按范围
  规则附 base 前证据并上交 Human。
- 以完整 `[TASK_RESULT v2]` 返回，并含 `评审结论`、`问题记录`、`修复要求`。只有明确 `ACCEPT`
  才可由 Bookkeeper 向 Human 汇报最终技术结论。

Stop

- 不得修改任何文件、暂存、提交、推送、合并、部署、启动服务或改变 Start gate。
- 不得调用 Binance、使用/输出凭证、发单、转账或触发其他外部副作用。
- 不得重开 Human 已定的业务裁定；发现真实风险可报告，但不得自行扩大为新实现范围。
- 完成只读评审后停止；Human 将原始回执交回 Bookkeeper。review-2 未明确 ACCEPT 前，不授权合并、
  部署或实盘。
