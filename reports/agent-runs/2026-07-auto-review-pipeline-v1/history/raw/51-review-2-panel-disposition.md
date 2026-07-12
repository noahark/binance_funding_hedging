# Review-2 Parallel Panel — Bookkeeper Disposition (Fable5)

Date: 2026-07-11
Context: 操作者对 review-2 采取并行 panel 分发（其权利：review-2 是人工
门），三个模型同时评审同一 stage 范围
`a385c7a..4c668bb`（指纹 `4c668bb…:54186cec…`）。三份产出已 verbatim
落档。本文件是 bookkeeper 对三份的规则地位分析、独立复现记录与处置。

## 1. Panel 结论一览

| 评审者 | verdict | 深度 | 规则地位 |
|---|---|---|---|
| gpt-5.6-sol (openai, xhigh) | **BLOCKED** — 7×P1 + 1×P2，均带行号/反例 | 深（复算指纹×4、110 测试、temp-repo 反例） | override 适格者（design 涉入已披露）；其自判"证据不足不能发 accepting gate"合规 |
| grok-4.5 (xai) | ACCEPT — P0–P2 无，仅 residual | 中（40 表逐条+验收 1–28+簿记抽查） | **不可作 record**：非注册决策模型，且自报 direction_synthesis 涉入（40 表 synthesizer），而 override 名单仅限 Codex/Claude |
| Gemini 3.1 Pro (google) | ACCEPT | 浅（reviewed_artifacts 仅 4 个文档，未触任何 `scripts/` 代码，未跑命令） | 唯一零涉入者但**本份不可作 record**：verdict 字段错误（`prior_involvement` 填 `design` 系误解——其无涉入应为 `none`；`model` 名非机械标识），且深度不足以支撑终审 |

三份没有一份可直接作为 review-2 record：sol 自判 BLOCKED，grok 资格双重
不合，gemini 浅审+字段错误。

## 2. 关键事实变化：Gemini 本次实际可达

Gemini 出了报告 = 本次调用成功。这削弱了
`review-2-unrelated-reviewer-unavailable-evidence.md` 的
service_unavailable 陈述（其为操作者经验陈述而非本次事实），同时坐实了
sol 的程序性 finding：**override 证据必须是 runner 级失败 artifact
（时间戳/命令/退出码/原始输出），操作者陈述不合 AGENTS.md 的证据形式
要求**。该证据文件保留为历史记录，不再作为 override 依据引用。

## 3. Sol substantive findings 的独立复现（bookkeeper，3/3 抽验 + P2 全部坐实）

- **F3 占位符断层：坐实。** `auto-review-runner.py:764` 仅替换
  `@PROMPT@`/`@REPO@`；真实 `agents/registry.yaml` 命令用
  `<prompt-file>`/`<repo>`（:54-58 等）。生产 adapter 将收到字面占位符。
  测试用合成 `@PROMPT@` 模板掩盖了断层。
- **F5 账本不联动：坐实。** `_charge_auto_change` 只增嵌套
  `auto_code_changes_used`；`grep rework_count scripts/auto-review-runner.py`
  零命中——顶层权威账本 runner 从不更新，违反 D4 单账本。
- **F4 verdict 字节重写：坐实。** `_store_verdict` 注释声称 "store the
  accepted bytes unaltered"，实现却 `json.dumps(verdict)` 重序列化——
  存的不是被接受的原始字节 span，违反 P3/验收 13。
- **P2 status 残段：坐实（bookkeeper 自查遗漏）。**
  `status.json` `model_routing.implementation.status`（:58）仍为
  `T1_correction_round2_ready_for_human_dispatch`、
  `model_routing.review_1.status`（:67）仍为
  `blocked_on_T1_correction_and_seal`——上次状态同步修复（d9f1f68）漏了
  `model_routing` 块。
- 其余四个 P1（authorization 实绑定、exclusive lock 与 H_snapshot 崩溃
  窗口、restart 幂等/错误停机、expires_at 每 call 检查）带精确行号与
  temp-repo 反例方法，按同等可信度进入修复清单，修复轮逐条验证。

**结论：sol 的 substantive findings 客观成立，与其评审资格争议无关。
fail-closed：这些 P1 不能带进 accepted。**

## 4. 处置

1. **修复轮（必然）**：基于 sol §Findings + §Required disposition 起草
   fix packet（Claude-GLM；范围跨 T2/T3 交付文件 + status 残段由
   bookkeeper 自修；含每条 finding 的确定性负测试）。修复构成
   code-changing fix → 正式 `rework_count` 2/3（packet bind 时记账）。
   修复后全套重验 → 受影响单元 re-seal → **re-review-1**（代码变更）→
   重回 review-2。
2. **资格线（并行）**：在重回 review-2 前，由操作者执行一次真正的
   runner 级 Gemini 可用性检查并留原始 artifact（命令/时间戳/退出码/
   raw 输出）。PASS → Gemini 为可用无关决策模型（但其深审能力局限已被
   本轮演示，操作者可令其做 record 而以高端深审作 corroborating panel）；
   FAIL → 该 artifact 即为合规 override 证据，GPT/Claude 依 override
   出 record。
3. grok/gemini 两份保留为 panel 补充证据（verbatim），不推进任何状态。
4. `review_2` 状态块记录 panel 事实与三份产出路径；顶层 status 在 fix
   packet bind 时转 `fixing`。

本地北京时间: 2026-07-11 21:45:00 CST
下一步模型: human operator（批准修复轮 dispatch）→ Claude-GLM
下一步任务: bookkeeper 起草 review-2 fix packet 与 status 残段自修；操作者批准后人工执行
