# Second Reinspection (T1 after Correction Round 2): Fable5

Outcome: **R2-1/R2-2 主体关闭 — 剩两处 node-graph 闭合残留，CORRECTION ROUND 3（最小修正）后方可 seal**

Date: 2026-07-11
Inspector: Claude Fable 5 (anthropic/claude-fable-5)
角色说明：自本文件起，Fable5 会话接任本 stage bookkeeper（前任 Codex/GPT 会话
quota 耗尽）。接任者非实现者；此前涉入（intake/设计评审、breakdown、二审）已在
status.json 披露，dispatch 仍由人工执行，本会话只准备不执行。

## 1. 前提事实

- Round2 packet（`task-T1-correction-round2-claude-glm.prompt.md`）已由人工
  执行，GLM 修复与证据落于 `20-implementation.md` round2 段与
  `60-test-output.txt` round2 块。
- 前任 bookkeeper 在会话内完成过 round2 验收但**未落档**（quota 耗尽）。
  口头/会话内验收不作为证据；本文件为独立重做的复验，全部反例与断言由本
  会话重写重跑，不复用 GLM 的临时脚本。

## 2. 独立复验结果（HEAD 6546bc9 + 工作树 T1 交付）

**冻结套件复跑全 PASS**：json.tool×3 EXIT:0、validator checkpoint
PASS（status=fixing）、`git diff --check` EXIT:0、`formal-1` 负扫 EXIT:1
（无匹配）、YAML parse PASSED。

**Schema 正反例（16 例，独立重写，Draft202012Validator）全部符合预期**：

- receipt：Grok primary / Kimi serial fallback / GLM serial fallback 三正例
  0 错（T1-R2-1 关闭）；kimi noninteractive、expanded/secret ref、adapter/ref
  mismatch、缺五 evidence 键（B1）、`bookkeeper_decision` 转移（A2）、绝对
  路径与 `..` 遍历路径共 7 负例全部报错。
- authorization：正例 0 错；绝对 approval_evidence_path、遍历 supersedes、
  空 task_ids、rework≠3、缺 expires_at 共 5 负例全部报错（A4 关闭）。

**结构断言**：`allowed_next_transitions`（9 值）与 receipt 非空枚举集合相等
（A2 闭环）；`state_transitions` 恰 8 项且 from/event/to 结构化（对应
10-design 八行）；`review_1_routes` 三对 ref 与 receipt oneOf 三对一致；
`pilot_predicate` 8 键精确值齐；docs 词汇段 "or Grok" 已移除（R2-C2）；
seal receipt 命名 `runner-<seq>-seal.receipt.json` 在 docs §8 与 README 双
落点（A3），附"非 adapter receipt、不入 P11 分母"说明。

**结论：24- 的 T1-R2-1 / T1-R2-2 主体均已关闭，v2 已关闭面无回归。**

## 3. 残留（round3 必修，两处，均为 node-graph 闭合）

机器化闭合检查（target ∈ node_transitions 键集 ∪ {completed_review_1,
human_escalation_required}）发现两类未解析 target：

1. **R3-1**：`node_transitions.embedded_cross_check` 的三个 event
   （ran/skipped/unavailable）target 为
   `identical_post_cross_check_blocking_rerun`（与 `frozen_nodes_and_order`
   一致），但接收键名为 `post_cross_check_blocking`——同一节点两个名字，
   图不闭合，T3 runner 加载器须特判别名。
2. **R3-2**：`node_transitions.review_1.invalid_json.after_retry_limit` 的
   target `serial_unit_fallback` 无接收键定义。其语义可由
   `review_1_routes.serial_fallback` 与相邻
   `serial_fallback_unavailable: human_escalation_required` 行拼出，但
   "拼出"正是 R2-2 所禁止的 runner 猜测。

两处均为命名/闭合级修正，语义无争议，不触碰任何冻结决策。修正在 seal 前
完成的理由：pre-seal correction 不消耗正式 rework 账本；带病进 review-1
若被 REWORK 则消耗 1/3 账本且需重新 seal。

P3 级备注（**不修**，防止过度改动）：`review_1_fixed_transitions` 与
`activation_predicate` 两个散文块与 round2 新增的结构化版本并存——结构化
版本是权威，散文块按 R2-C3 "note 可保留"规则留存；round3 不得动它们。

## 4. 处置

- `task-T1-correction-round3-claude-glm.prompt.md` 已准备（writable 仅
  `workflows/templates/stage-delivery.yaml` + 两个 evidence append），交人工
  执行。
- round3 返回后由本 bookkeeper 复跑闭合断言与冻结套件；通过即进入 seal
  （T1 delivery commit → head/fingerprint → `--phase pre-review` → 人工
  Kimi review-1 packet）。
- `rework_count` 保持 0（全部为 pre-seal inspection 循环）。

本地北京时间: 2026-07-11 16:22:49 CST
下一步模型: human operator → Claude-GLM
下一步任务: 人工执行 T1 correction round 3（两处 node-graph 闭合修正）；不得 commit 或派发 Kimi
