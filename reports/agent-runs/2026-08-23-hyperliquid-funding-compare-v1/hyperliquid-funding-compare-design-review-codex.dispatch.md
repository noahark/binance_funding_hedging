# Hyperliquid 费率对比行 v1 — 设计评审 dispatch（Codex / OpenAI）

## Identity

- task_id: `hyperliquid-funding-compare-design-review-codex`
- target_role: `Reviewer / Design Review-1`
- target_model: `codex`
- provider: `openai`
- status_revision: `2`
- required_skill: `agents/skills/software-architect.md`

## Goal

对**设计方案**（尚无实现）做独立只读评审，判断该方案是否为满足 Human 产品目标的
最小可交付范围，边界、口径、风险是否成立。**这是设计评审，不是代码评审——本 stage
目前零实现代码。**

## 固定范围与 SHA

- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- **delivery_sha：`6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`**（权威值；与 `status.json.delivery_sha` 一致）
- 固定 diff：`git diff 25cc8fe4e31194261dd48415f085bc6f9fda062d..6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`
- 分支：`2026-08-23-hyperliquid-funding-compare-v1`

**评审范围恰好三个文件**（该 diff 的其余两项是控制文件，见下）：

| 文件 | 角色 |
|---|---|
| `docs/planning/hyperliquid-funding-compare-v1.md` | **主评审对象** |
| `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hl-binance-pairing-20260823.json` | 证据：258 个配对的原始采样 |
| `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/pairing-probe.py` | 证据：可重跑的生成脚本 |

**范围外（控制/ledger 提交，针对它们的发现记为范围外）**：

- `reports/agent-runs/.../status.json` 与 `reports/agent-runs/ACTIVE.json`——虽落在上述 diff 内，
  属 stage 控制文件，不是交付内容。
- 本 dispatch 文件自身（提交于 `08a657b`，在 delivery_sha **之后**）。
- 本次 packet 勘误提交（`status.json` revision 1→2 填入 delivery_sha、本节重写），同样在 delivery_sha 之后。

`HEAD` 会因上述控制提交前移，**这是预期的**。评审一律以固定 `delivery_sha` 为准，
不评审 `HEAD`、不评审未提交工作树。

## 隔离披露

- 设计作者：Opus 5 / Anthropic（provider `anthropic`）。
- 本 Reviewer：Codex / OpenAI（provider `openai`）。跨 provider，隔离成立。

## 必须逐条核实的事实断言

设计稿中下列断言均由 Opus 5 实测得出。**请独立复核，不要采信转述**——采样脚本已随附，
可自行重跑（只读公共 API、无凭证、无下单）：

1. HL `metaAndAssetCtxs` 两次 POST（`dex=""` / `dex="xyz"`）覆盖 main 177 + xyz 101 个在架标的。
2. 同名 exact 可匹配币安 UM 的是 244 个（main 166 + xyz 78）。
3. `xyz:BB` / `xyz:QNT` 与币安加密标的**恰好同名**且指向不同资产。
4. 币安 UM 的 `fundingIntervalHours` 实测 122 个 4 小时、136 个 8 小时（非统一 8h）。
5. `predictedFundings` 的三条否决理由（设计稿 §5）：不覆盖 xyz、`VINE`/`HYPE` 双向错误、
   `HlPerp` 与 `metaAndAssetCtxs` 177 中 54 个不同。
6. HL `fundingHistory` 按 coin 单查、上限 500 条（= 20.8 天 < 30 天）——这是三列历史
   被列为非目标的依据。
7. xyz 在美股休市时段费率退化（采样时币安侧 87 中 83 个为 0）。

## 重点评审问题

- **R1 范围**：前四列是否为满足「统一口径好对比」的最小范围？是否有更小的做法？
  「结算时间」第二行用固定文案「每小时」而非显示 HL 下一整点，理由是否成立？
- **R2 边界**：三列历史（近 24h / 7D / 30D）列为非目标是否正确？成本论证是否充分？
- **R3 fail-closed**：第一版只做 exact、14 个标的显示 `—`，是否与 `DEC-2026-08-07-003`
  的既有哲学一致？`HL_SYMBOL_DENY` 只硬编码 2 条是否够（有无遗漏的撞名）？
- **R4 口径**：HL `funding` 与币安 `lastFundingRate` 归为同一刷新组是否成立（两者是否
  真的同性质）？`daily_rate = funding × 24` 对 HL 是否正确？
- **R5 风险**：§7 的四条风险是否有遗漏？特别是 HL 源失败时的降级路径（验收 7）。
- **R6 文件边界**：§6 的改动清单是否完整？有无遗漏的消费点（参考本仓库教训：
  `docs/planning/leg-unit-size-conversion-2026-08-15.CLOSED-lessons.md` 记录过
  「封存的改动清单已知不完整」）。
- **R7 验收标准**：§8 的九条是否可执行、是否覆盖 §9 的五个决策点？

## Allowed Files

Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：

- **唯一允许新建**：
  `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-review-codex.handoff.md`
- 该路径开始前不存在（Bookkeeper 预检 2026-08-23 CST：ABSENT）。若开始时已存在即任务失败。
- 不得修改设计稿、`status.json`、`ACTIVE.json`、任何源码或测试。

## Verdict

给出 `ACCEPT` / `REJECT`，逐条对应 R1–R7，并明确列出：
- 哪些事实断言你**独立复核通过**、哪些**未能复核**或**复核不一致**；
- 若 `REJECT`，给出最小修正建议，不要扩大范围。

## Stop Point

写完 handoff 即停。不实现、不改设计稿、不推进 stage 状态。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.
