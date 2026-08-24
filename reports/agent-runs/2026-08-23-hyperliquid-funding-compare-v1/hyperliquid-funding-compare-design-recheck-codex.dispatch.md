# Hyperliquid 费率对比行 rev2 — 设计复评 dispatch（Codex / OpenAI）

## Identity

- task_id: `hyperliquid-funding-compare-design-recheck-codex`
- target_role: `Reviewer / Design Recheck`
- target_model: `codex`
- provider: `openai`
- status_revision: `3`
- required_skill: `agents/skills/software-architect.md`
- 前序: `hyperliquid-funding-compare-design-review-codex`（verdict `REWORK`，F1–F5）

## Goal

验证 rev2 设计稿是否闭合你在 rev1 提出的 F1–F5，以及 rev2 新增内容是否引入新问题。
**仍是设计评审，本 stage 零实现代码。**

## 固定范围与 SHA

- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- **delivery_sha：`2645bb2211895323f72187ff6499af57310192c6`**（权威值；与 `status.json.delivery_sha` 一致）
- rev1 对照 SHA：`6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`
- 修订 diff：`git diff 6ee75b0c1eb405fa2bf79a0a7aad4814142800d5..2645bb2211895323f72187ff6499af57310192c6`
- 分支：`2026-08-23-hyperliquid-funding-compare-v1`

**评审对象恰好一个文件**：`docs/planning/hyperliquid-funding-compare-v1.md`（rev2 全文重写）。
证据文件 `evidence/hl-binance-pairing-20260823.json` 与 `evidence/pairing-probe.py` 自 rev1 未变。

**范围外**：`status.json`、`ACTIVE.json`、本 dispatch 自身、以及任何在 delivery_sha
**之后**的控制提交。`HEAD` 会因这些控制提交前移，**这是预期的**——一律以固定
`delivery_sha` 为准，不评审 `HEAD`、不评审未提交工作树。

## 隔离披露

- 设计作者：Opus 5 / Anthropic。本 Reviewer：Codex / OpenAI。跨 provider 成立。
- **披露**：你是 rev1 的评审者，F1–F5 由你提出。本轮验证你自己的 finding 是否闭合，
  存在确认偏误风险。请对 rev2 **新增**的 §5/§6/§9 从头验证，不要因为「是按我的建议写的」
  就降低标准。

## 逐条验证

| finding | rev2 声称的修订 | 需你判定 |
|---|---|---|
| F1 失败语义 | 新增 §6：独立 source_id、main+xyz 原子组、任一失败全 `null` + warning、不投影 last-good、币安照常发布 | 是否真的同时满足「失败即 `—`」与「Binance 照常显示」？冷启动路径是否与 `_compose_base_raw` 的 A+B 等待相容？ |
| F2 验收不可执行 | §9 说明行基底事实；A6 换为 Binance-only fixture；A11–A14 覆盖 D1–D5 | A1–A16 是否条条可执行？是否仍有 oracle 不清晰项？ |
| F3 静态 deny 不足 | §3 匹配第 4 步类别校验（main→`PERPETUAL`、xyz→`TRADIFI_PERPETUAL`）；A2 synthetic 测试 | 类别校验是否足以让**新**撞名 fail-closed？有无绕过路径？ |
| F4 wire 契约 | 新增 §5：decimal string、`isDelisted` 过滤、DENY 先于 raw name、非法值 fail-closed、区分两种 `null` | 契约是否完整？两种 `null` 的可区分性在 wire 上是否真的成立？ |
| F5 事实与文件边界 | §4 分母改 258 样本口径；全文顶部采样时点声明；§7 补 `self-check.js`、`public-market-contract.md` | 是否还有未标注时点的数字？文件清单是否仍有遗漏？ |
| R2 成本数字 | §2 改为「最坏 +20 请求、总量 10→30」 | 数字是否正确？ |

## 明确不采纳项（需你判定是否可接受）

rev2 **拒绝**了 F4 附带的一条建议：xyz 第二行加静态提示「非美股交易时段读数可能退化」。

理由（记入 §1 与新增决策点 D7）：Human 2026-08-23 明确「股市休息币圈不休息，休市反而
会有高费率出现」，这正是 xyz 必须进第一版的产品理由；挂退化提示会诱导使用者忽略该时段，
与产品目标相反。rev2 改为中性来源标签 `HL·xyz`，不含价值判断。

请判定：这个拒绝是否可接受？若你认为仍需某种提示，请给出**不带价值判断**的最小替代方案。

## Allowed Files

Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：

- **唯一允许新建**：
  `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md`
- 该路径开始前不存在（Bookkeeper 预检 2026-08-23 CST：ABSENT）。
- 不得修改设计稿、`status.json`、`ACTIVE.json`、rev1 handoff、任何源码或测试。

## Verdict

`ACCEPT` / `REWORK`，逐条对应 F1–F5 + R2 + 不采纳项，并明确列出：
- 哪些 finding **确认闭合**、哪些**未闭合**；
- rev2 新增内容是否引入**新** finding；
- 若 `ACCEPT`，声明设计可进入实现 dispatch 准备。

## Stop Point

写完 handoff 即停。不实现、不改设计稿、不推进 stage 状态。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.
