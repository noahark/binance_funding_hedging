# Hyperliquid 费率对比行 rev3 — 设计复评（第二轮）dispatch（Codex / OpenAI）

## Identity

- task_id: `hyperliquid-funding-compare-design-recheck2-codex`
- target_role: `Reviewer / Design Recheck`
- target_model: `codex`
- provider: `openai`
- status_revision: `4`
- required_skill: `agents/skills/software-architect.md`
- 前序: rev1 评审（`REWORK`，F1–F5）→ rev2 复评（`REWORK`，N1–N3）

## Goal

验证 rev3 是否闭合 N1–N3。**仍是设计评审，本 stage 零实现代码。**

## 固定范围与 SHA

- base_sha：`25cc8fe4e31194261dd48415f085bc6f9fda062d`
- **delivery_sha：`fe91abb69e236e9ef110ca354b8773dfcb042773`**（权威值；`status.json.delivery_sha` 同值）
- rev2 对照 SHA：`2645bb2211895323f72187ff6499af57310192c6`
- 修订 diff：`git diff 2645bb2211895323f72187ff6499af57310192c6..fe91abb69e236e9ef110ca354b8773dfcb042773`
  （单文件，+106 / −25）
- 评审对象恰好一个文件：`docs/planning/hyperliquid-funding-compare-v1.md`

**范围外**：`status.json`、`ACTIVE.json`、本 dispatch、任何 delivery_sha **之后**的控制提交。
`HEAD` 前移是预期的，一律以固定 `delivery_sha` 为准。

## 隔离披露

- 设计作者：Opus 5 / Anthropic。Reviewer：Codex / OpenAI。跨 provider 成立。
- **披露**：你是 rev1、rev2 两轮 finding 的提出者。本轮存在确认偏误风险，
  且 rev3 对 N1 **采用了与你建议不同的方案**（见下），请按方案本身的有效性判定，
  不要因为「不是我建议的做法」而降低或提高标准。

## N1 采用了替代方案，需你判定是否等效或更优

你建议：冻结 `hyperliquid_source_unavailable` 与 `hyperliquid_funding_invalid:<key>`
两个 warning token，前端消费源失败 token 显示「HL 数据暂不可用」。

**rev3 改为**（Human 2026-08-23 提出，Planner 采纳）：快照顶层新增单一字段
`hyperliquid_data_time`，前端在**既有** `market-snapshot-meta`（市场表下方
「生成时间 · 数据时间」那一行）追加「HL 数据时间」，复用**既有** `isStaleTime()`
与 `.stale-time` 类（`color: var(--danger); font-weight: 700`，项目已三处使用）。

理由（§6.2 与 D8）：

1. token 只能表达二元的「挂/没挂」；时间戳表达三态（正常 / 陈旧 / 取不到）。
   对 60 秒刷新的费率数据，「这是什么时候的」与「有没有」同等重要——
   五分钟前的费率照样会让人做错判断，token 说不出这件事。
2. 你指出的核心问题「无匹配 vs 源失败不可区分」由此解决：
   行内 `—` + 时间戳正常 = HL 无此标的；行内 `—` + 时间戳标红 = HL 源不可用。
3. 零新增 UI 组件、零新增词汇表，全部复用现成机制。

**另**：你的 N1-2（单币非法值专属 token）rev3 **简化为整源失败**，
理由是与 §6.1 已定的「main+xyz 原子组」保持一致——既然一个 dex 的 POST 失败就整组作废，
源返回非法值同样说明这一批不可信。一个机制覆盖全部失败态。

请判定：该替代方案是否**等效或更优**地闭合 N1？若认为存在 token 方案能覆盖而
时间戳方案覆盖不到的场景，请具体指出。

## 逐条验证

| finding | rev3 修订 | 需你判定 |
|---|---|---|
| N1 三态不可区分 | §6.2 `hyperliquid_data_time` + `.stale-time`；A7/A8/A9 改断言时间戳；新增反向 oracle A9b | 是否闭合？假绿断言是否消除？ |
| N1-2 单币非法值 | §5 rev3：简化为整源失败 | 简化是否可接受？ |
| N2 offline | §6.3：零网络、恒 `null`、与源失败共用时间戳表达；明确 block 非 required | 是否闭合？`hyperliquid` block 非 required 是否足以保住既有 offline fixture 的 schema 校验？ |
| N3 A13 oracle | 限定「一次成功刷新恰好两次、任一次刷新最多两次、失败时第二个不再发出」 | oracle 是否唯一？ |
| §8 表述过宽 | 收窄为「类别校验只拦跨类别撞名；同类别同名仍需人工收录 DENY」 | 收窄是否准确？ |

## Allowed Files

Reviewer 完全只读，除下面唯一 create-only handoff 外零写入：

- **唯一允许新建**：
  `reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck2-codex.handoff.md`
- 该路径开始前不存在（Bookkeeper 预检 2026-08-23 CST：ABSENT）。
- 不得修改设计稿、`status.json`、`ACTIVE.json`、前两份 handoff、任何源码或测试。

## Verdict

`ACCEPT` / `REWORK`，逐条对应 N1（含替代方案判定）、N1-2、N2、N3、§8 收窄。

**若仍为 `REWORK`，请额外回答一个问题**：剩余 finding 是否**必须在设计阶段**解决，
还是可以在实现后的代码评审阶段解决？本设计稿已从 140 行增至 307 行，
而其描述的实现预计约 200 行。Planner 需要判断继续修订设计的边际收益。

## Stop Point

写完 handoff 即停。不实现、不改设计稿、不推进 stage 状态。

reply_to: claude
After emitting the normal console receipt, send that same receipt once to the
reply_to window per this file, then stop.
