Identity:
- task_id: review-1-code-rerun-2
- target_role: Reviewer（Review-1 rerun / HIGH_RISK）
- target_model: DeepSeek
- provider: deepseek
- status_revision: 15
- required_skill: agents/skills/code-reviewer.md

Goal

以**全新、只读会话**重跑 HIGH_RISK review-1，审查固定交付区间
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..e99974ad934af5117b0c2385e5545f9861812d5d`。
DeepSeek（deepseek）与该区间的实现/修复作者 Claude-GLM（zhipu_glm）和 Grok（xai）provider 隔离。

Opus5 的 review-2 曾给出 `REWORK`。本次修复必须关闭两个 `in-range` 发现：

1. `backend/tests/test_hedge_purity.py` 的冻结守卫必须精确锁住已授权的 12 条 endpoint——7 条
   `https://papi.binance.com` PAPI endpoint 和 5 条 `https://api.binance.com` 普通 Spot / 名单 endpoint；
   必须保留精确相等、长度 12、按组硬绑定 host，以及未知 path 签名前 fail-closed。
2. `backend/services/hedge_open_live_client.py` 仅模块 docstring 可改，须如实表述订单 client 仍
   default-off、而展示 client 可由组合根独立注入且只能读名单 GET；不得改变运行时代码。

这是根因 **「改共享常量/签名后 dispatch 清单外既有守卫测试失效」** 的第二次正式返工后的
穷举修复。复核修复回执所列六组共享面扫描，确认没有通过缩小守卫、跳过测试或遗漏同类 fake 来掩盖
问题。重新审查完整固定区间，确认此前通过的路由方向、普通现货 endpoint/审计权威、allowlist 与缓存
隔离、SnapshotService 组合根与四态展示、v0.9 contract/schema/前端接缝，以及无真实请求/凭证/DB
migration/Start gate 变更，均未回退。

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
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code-rerun.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-2-reality.opus5.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/fix-review-2-allowlist-guard-scan.claude-glm.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-2-rework-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-fix-review-2-allowlist-guard-scan-verification.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
- `docs/planning/spot-order-routing-v1.md`
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- 仅从固定 Git 区间读取源文件、测试和 diff；不得以移动 HEAD 或未提交工作区代替该区间。

Acceptance Checks

- 先执行并记录：`git rev-parse 1a55781a5f80ee5b3e15d7124003af2dda73f0d5`、
  `git rev-parse e99974ad934af5117b0c2385e5545f9861812d5d`、
  `git diff --check 1a55781a5f80ee5b3e15d7124003af2dda73f0d5..e99974ad934af5117b0c2385e5545f9861812d5d`。
- 明确核验 `3a07f4a..e99974a` 仅改两份 dispatch-approved 文件；allowlist 守卫精确等于 12 条、PAPI/Spot
  host 分组正确、未知路径仍拒绝，且 client 的改动仅为模块 docstring。
- 核验六组共享面（`ALLOWLIST`、`get_snapshot`、`query_leg`、`prepare_attempt`、`_persist_leg_raw`、
  `build_rows`）的扫描结论，并以静态检索或同等可复现检查验证没有遗漏的受影响 fake 或冻结守卫。
- 运行并通过：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
```

- 对完整固定区间和受影响测试做可复现只读检查；测试必须为 fake transport，不得读取真实凭证或向外网发请求。
- 以完整 `[TASK_RESULT v2]` 返回，并含 `评审结论`、`问题记录`、`修复要求`；仅明确 `ACCEPT`
  才可重新投递 Opus5 的 review-2。

Stop

- 不得修改任何文件、暂存、提交、推送、合并、部署、启动服务或改变 Start gate。
- 不得调用 Binance、使用/输出凭证、发单、转账或触发其他外部副作用。
- 不得审查移动 HEAD、未提交工作区或任务回执代替固定 Git 区间。
- 完成只读评审后停止；Human 将原始回执交回 Bookkeeper。review-1 未明确 ACCEPT 前，不得重跑 review-2；
  review-2 未明确 ACCEPT 前，不授权合并、部署或实盘。
