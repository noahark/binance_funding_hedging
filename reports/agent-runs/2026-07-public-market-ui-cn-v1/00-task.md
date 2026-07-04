# Stage Task: 2026-07-public-market-ui-cn-v1

Authoritative for file boundaries and acceptance in this stage. Authored by
Fable5 (anthropic/claude-fable-5) as designer/breakdown author. When this file
and the user's decisions in intake disagree, the user's decisions win; surface
the conflict, do not silently pick.

## Goal

1. Task A — 合约 warning 语义修订（claude_glm）：把 `lastFundingRate`
   的 warning 从「语义未证实」升级为实证措辞（证据已随 H_intake 落盘），
   涉及 `backend/domain/snapshot.py:CONTRACT_WARNINGS[1]` 与
   `docs/api/public-market-contract.md` 对应段落。**不改任何逻辑**。
2. Task B — 前端中文化与展示整合（kimi）：合并「资金费率/结算时间」列、
   提示标记中文化降噪、warnings 改中性数据说明样式、清除英文残留。
3. Task C — 集成验证（controller，无产品代码）。

## Non-goals（本阶段禁止）

- 任何签名/私有端点、key、order/borrow/repay/transfer/websocket。
- 任何新的 live HTTP（证据已在 H_intake 抓齐；A/B/C 全程离线）。
- `classify.py` / `normalize.py` / `snapshot_service.py` 逻辑改动。
- `schemas/**` 改动（本次 warning 措辞升级不涉及 schema 字段）。
- 后端 `warnings` 数组以外的 API 载荷变化（rows 结构零改动）。
- `funding_history` top-N、路由分类、负费率优先级改动。
- 新前端依赖、构建工具；页面保持单文件 + same-origin fetch。

## Ownership and file boundaries

| Path | Owner | Rule |
|---|---|---|
| `backend/domain/snapshot.py` | claude_glm (A) | 仅 `CONTRACT_WARNINGS[1]` 字符串 |
| `docs/api/public-market-contract.md` | claude_glm (A) | 仅 lastFundingRate 段落 + Open Verification Items 对应项 |
| `backend/tests/**` | claude_glm (A) | warning 文本断言同步 |
| `frontend/**` | kimi (B) | claude_glm 不得改动 |
| `reports/api-samples/2026-07-public-market-ui-cn-v1/**` | H_intake 已落盘 | 阶段内只读 |
| `reports/api-samples/<其他>/**` | frozen | 只读 |
| `reports/agent-runs/2026-07-public-market-ui-cn-v1/**` | controller | 各任务写各自报告 |
| `agents/`, `workflows/`, `scripts/`, `schemas/` | untouched | 问题走 escalation |

边界越界即 REWORK，与代码质量无关。

## Task A — 合约 warning 语义修订（claude_glm, `senior_developer`）

Scope: `backend/domain/snapshot.py`（仅 warnings[1] 字符串）、
`docs/api/public-market-contract.md`、`backend/tests/**`、
`20-implementation-backend.md`。

Deliverables:

- `CONTRACT_WARNINGS[1]` 替换为（英文，合约层语言与另两条一致）：
  "premiumIndex.lastFundingRate is the real-time estimate for the CURRENT
  funding period and is charged at nextFundingTime; it drifts until settlement
  (mid-period divergence from settled history evidenced under
  reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/).
  Settled history comes from /fapi/v1/fundingRate; do not present the estimate
  as a settled value."
- 合约文档同段落同步修订（引用同一证据路径），Open Verification Items 里
  「lastFundingRate 语义」项标记为 resolved（引用证据），其余项不动。
- 测试：若现有测试钉住 warnings 文本则同步；新增断言 warnings[1] 包含
  "real-time estimate" 与证据路径关键词。逻辑测试零改动。

Acceptance: `pytest backend/tests -q` 全绿；`git diff` 中 `snapshot.py` 仅
warnings[1] 一处字符串变化；`float(` 审计 clean。

## Task B — 前端中文化与展示整合（kimi, `minimal_change_engineer`）

Scope: `frontend/**` + `20-implementation-frontend.md`。依赖 Task A 完成
（warnings[1] 新文案确定后，前端中文翻译以其为准）。

Deliverables（细则见 `10-design.md`，含精确映射表与格式化算法）:

1. 表格第 4/5 列合并为「资金费率/结算时间」，单元格 `+0.01% / 16:00`；
   完整信息进 tooltip。**费率百分比转换必须字符串移位，禁止
   `parseFloat/Number × 100`**；负零归一为 `0%`。
2. 「UI 标记」列改名「提示标记」；行内 badge 仅保留 `PERP_ONLY_NO_SPOT_LEG`
   →「无现货腿」、`TRADIFI_BSTOCK`→「bStock」；`MARGIN_PUBLIC_UNVERIFIED`
   移为页面级说明一条（所有行恒真，不做逐行 badge）。
3. warnings 区改为中性「数据说明」样式（非报错观感），展示固定中文翻译
   三条；英文原文放 `<details>` 折叠或 title。
4. 清除英文残留：`<title>` 与页头「Funding Hedge Workstation」、
   Public Only / Read-only / Manual Refresh 等全部中文化；保留 USDT / bStock /
   API / PM 技术词；「PM 现货候选」改「杠杆现货候选」。
5. `fixture/public-market-snapshot.json` 与 `self-check.js` 同步：新增
   格式化函数断言（移位、裁尾零、负零、零值、缺失 next_funding_time）。

Acceptance: `node frontend/self-check.js` 全 PASS（含新断言）；页面经
`http://127.0.0.1:8787/` 目视验证列合并与中文文案；无直接 Binance 调用。

## Task C — 集成验证（controller，无产品代码）

离线构建快照 → 断言 warnings[1] 为新文案、rows 结构与前一验收版逐字段一致
（除无 API 变化预期外发现任何 rows 差异即 BLOCKED）→ `pytest` + `self-check`
输出留档 `60-test-output.txt` → `20-implementation.md`。

## Reviews

- review-1：Task A → Kimi；Task B → 全新只读 Claude-GLM 会话（不复用
  controller/Task A transcript）。
- review-2（终审）：Codex/GPT gpt-5.5，`reviewer_prior_involvement=
  direction_synthesis`（strong-reviewer disclosure override，与前两阶段同径）。
  注意：本阶段 designer=anthropic/Fable5，Anthropic 因设计参与被排除出
  review-2 池；两实现方 hard-ban；Codex 无本阶段设计/拆分/代码参与。

## Fingerprint protocol（不变，单一协议）

```text
diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")
```

Commit 序列：H_intake（本提交：intake/task/design/status/证据）→ H_A →
H_B → H_C。controller 串行提交，各任务 diff owner-scoped。

## ADR

本阶段无新架构决策（沿用单文件前端 + stdlib server + 既有 badge 体系），
不设 `11-adr.md`；展示格式规范属设计细则，见 `10-design.md`。

本地北京时间: 2026-07-04 12:55 CST
下一步模型: Claude-GLM (controller)
下一步任务: 提交 H_intake 后按 controller-start-prompt.md 派发 Task A。
