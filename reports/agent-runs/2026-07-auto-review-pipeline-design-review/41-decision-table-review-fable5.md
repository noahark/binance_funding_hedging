# Review: Operator Decision Table (Fable5)

Status: **DECISION-TABLE REVIEW — ACCEPT-with-edits**
Date: 2026-07-11
Reviewer: Claude Fable 5 (anthropic/claude-fable-5)
Reviewed document: `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
Cross-checked against: 设计 note、我的首轮评审、`30-review-codex.md`、
`31-divergence-response-fable5.md`（四份本轮均完整重读）。

Pre-stage design review，无 delivery diff、无 schema-bound verdict JSON。
按 §G 要求的五项输出逐项作答。

---

## 1. Verdict

**ACCEPT-with-edits。** 三个 minimal patch（一个硬矛盾、两个措辞/常数
对齐），修完即可直接写 `00-intake.md`，无需再回到讨论轮。

## 2. Consistency check：是否干净解决了源文档间冲突？

**是。** 三处真分歧的裁决与 `31-divergence-response-fable5.md` 的合成
立场逐一对得上，且对 Codex 立场的取舍属操作者职权、已显式记录：

- **D1 = B + seen-diff bind**：等于 Codex #1 次序 + 我的让步条件，双方
  收敛点原样入表。✅
- **D2 = 拓扑分裂 C**：serial per-task / parallel tip-once，加"serial
  tip ≠ last task head 时对集成 range 补一次 formal"——这正是我首轮
  D3 的例外条款，比我的分歧回应更完整。✅
- **D4/§C = 单账本 + auto ≤2 + review-2 保底**：采我方案，明确否决
  Codex 答8 的无保底 3 cycle。表格 supersede，无残留歧义。✅
- 其余 D3/D5/D6/D7/D8/D10/D11/D12、P1–P12 均与两份评审的共识面或已
  声明的让步一致；P6（fix_start_prompt 域拆分路由 + unroutable →
  escalation）正确吸收了我指出的双方共同缺口。✅

词汇锁定（runner / embedded cross-check / seal / seen-diff bind /
code-scope）定义自洽，且遵守了"不引入 formal-1、不与 validator
`--phase pre-review` 撞名"两条。✅

## 3. Holes（会阻塞 00-intake 的欠规格项）

只有一个真正阻塞项（E1，下节作为 patch 给出）。两个非阻塞项建议留给
stage design 而非改表：

- （非阻塞）**auto-run authorization 的产物形状**：D11/§D 定义了这道
  人工门，但未定授权记录落在哪（建议 `00-intake.md` 一节 +
  `status.json.auto_run_authorization` 机械字段）。intake 起草时定即可。
- （非阻塞）**D5 的 "fall back to human dispatch" 是一次模式翻转**：
  exclusive worktree 不可得时回退人工 dispatch，等于 stage 的
  `auto_review_pipeline.enabled` 中途变化，需要 status 里有记录字段。
  同上，intake/设计阶段定形状即可。

## 4. Contradiction scan

**发现一处硬矛盾（D7 × D2），两处轻微不一致：**

**E1（硬）：D7 的 fallback cross-pool 在 D2 的 parallel tip-once 情形下
不存在合法评审者。** Tip-once 的被审 diff 同时含 GLM（后端）与 Kimi
（前端）两个 provider 的代码；AGENTS 硬门"reviewer 不得是被审代码的
implementer，无豁免"在 provider 粒度下使 cross-pool 两名成员**双双
不合格**——这正是我首轮论证 Grok 能审全 tip 的同一条理由，反向成立。
而 P9 又禁止 runner 自动调用高端模型，Codex/Claude 也不能补位。
即：**parallel tip-once + Grok 失效 → 表内写的 fallback 路径是空集。**
Serial per-task 情形 fallback 成立（task 级 diff 单 provider，另一家
可审），矛盾仅存在于 tip-once 分支。

**E2（轻）：seen-diff bind 在 §D 流程中的位置与其定义矛盾。** 词汇表
定义 bind 是"cross-check 所见 code-scope diff 与 **sealed** base..head
code-scope diff 的哈希相等"，但 §D 把它画在 re-run blocking 与 seal
**之前**——此时 sealed diff 尚不存在，按图实现会退化为工作树自比对
（恒真）。正确语义：cross-check 时**捕获**哈希，seal 时**断言**相等。
另 D3 允许跳过 cross-check，跳过时 bind 应显式记 N/A 而非静默缺失。

**E3（轻）：§C 的 invalid-JSON 重试数与现行契约常数漂移。**
表写 "retries ≤ 2 per attempt"（= 每次评审最多 3 次调用），现行
AGENTS/registry/模板三处都是 `invalid_json_max_attempts_per_model: 2`
（= retry 一次、共 2 次）。修订 stage 有权改这个常数，但决策表必须
二选一：对齐现行值，或显式标注"本表有意将常数从 2 提为 3"。静默
漂移会在 validator 与 runner 之间埋不一致。

其余行两两互检及对照三条铁律（指纹零改动 / review-2 人工 / runner
唯一 dispatch）未发现冲突；P3 的 grok-build plan-mode 与 registry
现状（`optional_review_command`，900s）核对相符。

## 5. Minimal patch list

1. **[D7] 补 tip-once fallback 分支**：行尾追加——
   "For parallel tip-once review-1, the Kimi↔GLM cross-pool is
   ineligible (both providers authored tip code); Grok unavailable or
   repeated invalid JSON at tip-once → `human_escalation_required`
   (operator may execute a manual review-1 dispatch), never an
   automated high-end substitution."
2. **[Vocabulary / §D] 修 seen-diff bind 语义与位置**：词汇表改为
   "hash captured at cross-check time, asserted equal at seal
   (fail-closed)"；§D 流程行改为在 seal 步内标注
   `+ assert seen-diff bind`，并加一行 "cross-check skipped (D3) →
   bind recorded N/A"。
3. **[§C] 对齐 invalid-JSON 常数**：改为
   "invalid JSON: ≤1 retry per model per review attempt
   (`invalid_json_max_attempts_per_model: 2`, unchanged), do NOT
   charge rework"——或保留 3 次但加一行显式声明这是对现行常数的
   有意变更，且修订 stage 需同步 AGENTS/registry/模板三处。

以上三条均为对本表的文字级修补，不推翻任何 D/P 决策。修补后本表可
作为 `2026-07-auto-review-pipeline-v1` 的 `00-intake.md` 直接输入。

---

```text
本地北京时间: 2026-07-11 10:50:04 CST
下一步模型: GPT/Codex（按 §G 的双评审安排出具另一份表评审）；之后 operator 合并 patch
下一步任务: operator 采纳/驳回上述 3 个 patch → 更新 40-operator-decision-table.md → 开 Harness 修订 stage intake
```
