<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  operator_choice — gpt-5.6-sol > terra > luna (openai) 或 claude-fable-5 / opus4.8 (anthropic)
adapter_cmd:   操作者按所选 provider 取 registry 对应 read-only review 命令；prompt = 本文件
adapter_ref:   agents/registry.yaml#adapters.{codex|anthropic_claude}; docs/model-adapters.md
executor:      human
task:          review-2 ROUND 3 — 全 stage 终审（round-2 REWORK 的 FINAL fix 已交付、复验、re-review-1 ACCEPT）
review_range:  a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730
diff_fingerprint: a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e
ledger_note:   rework 账本 3/3 已耗尽 — 本轮 REWORK(required finding) => human_escalation_required
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       评审报告文本交回操作者（bookkeeper 落档为 50-review-2-round3-<model>.md + review-2-round3-<model>.verdict.json）
next_dispatch: bookkeeper（落档；ACCEPT→stage_accepted_waiting_user / REWORK→human_escalation_required）
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Review-2 Round 3：stage `2026-07-auto-review-pipeline-v1` 全范围终审

你是本 stage 的 review-2 终审评审者（final_reviewer，fresh **read-only**
session）。分支 `stage/2026-07-auto-review-pipeline-v1`。这是第三轮
review-2：round-1 你方轨道曾出 BLOCKED（修复后关闭）、round-2 record 出
REWORK（5×P1+3×P2，全部坐实）；对应 FINAL fix（rework 3/3，账本最后一格）
已交付、bookkeeper 逐项破坏性复验、review-1（Kimi）ACCEPT。本轮评审
**整个 stage 交付**是否达到验收。

角色规范：本 packet 对应 workflow review-2 节点（`workflows/templates/
stage-delivery.yaml` `review_2`，`skill: reality_checker`）。先读
`agents/skills/reality-checker.md` 并按该 skill 的评审纪律执行——用证据
与可执行反例说话，不接受"报告说已修"作为修复证据。

## 终格语义（先读懂再评审）

rework 账本 3/3 已耗尽。你的 verdict 后果：
- **ACCEPT** → bookkeeper 落 `stage_accepted_waiting_user`（等待用户/操作者
  最终处置；你与 bookkeeper 均无 merge 权）。
- **REWORK（任何 P0/P1/P2 required finding）** → bookkeeper 落
  `human_escalation_required`，不再有自动修复轮。
- **请勿因终格而软化判定**：该 REWORK 就 REWORK，fail-closed 优先。

## 评审范围（frozen，先自行复算）

- 全 stage diff：`git diff a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730`
- stage 指纹（不符即 BLOCKED）：
  `a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e`
  公式：`head_sha + ":" + sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json')`
- 范围含实现 commit 与 bookkeeper 簿记 commit；实现漂移判定以交付单元
  writable set 为准（T1 契约面 / T2/T3 runner+seal+tests / 两轮 fix 的
  4+2 文件）。

## Requirements Authority（优先级降序）

1. `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
   （操作者冻结裁决表 D1–D12/P1–P13——最高权威）
2. `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md` 验收 1–29
3. `10-design.md` / `11-adr.md` / `docs/auto-review-pipeline.md`

## Read First（顺序）

1. `agents/skills/reality-checker.md`（本节点 skill）
2. `40-operator-decision-table.md`（要求权威）
3. `00-task.md`（验收清单）
4. round-2 record findings：`50-review-2-round2-gpt-5.6-sol.md` +
   `review-2-round2-gpt-5.6-sol.verdict.json`
5. FINAL fix 规格与交付：`task-review2-round2-fix-final-claude-glm.prompt.md`
   （FX1–FX7 四段式 + G1–G5）、`20-implementation.md` 末段（GLM 交付报告
   + 3 append 阻塞点）、`60-test-output.txt` 末三段（GLM required checks +
   bookkeeper 复验证据[8/8 破坏性验证、6/6 命令探针、FX5 生产 receipt
   交叉探针、R1/R2 residual、流程偏差注记]）
6. re-review-1：`30-review-1-review2-round2-final-fix.md` +
   `review-1-review2-round2-final-fix.verdict.json`（Kimi ACCEPT）
7. 事件与处置记录：`52-review-2-round2-panel-disposition.md`（§3 Gemini
   身份伪造事件——已存证、恢复、零效力处置）
8. 代码现状：`scripts/auto-review-runner.py`、`scripts/stage-seal.py`、
   `scripts/validate-stage.py`、`scripts/harness_stage_lib.py`、
   `scripts/tests/`、schemas、`workflows/templates/stage-delivery.yaml`
   `executable_contract`

## 你要回答的问题

1. **round-2 findings 关闭**：你（或 round-2 record）指出的 5×P1+3×P2
   是否全部以证据关闭？**靠证据不靠记忆/报告**——若你是 gpt-5.6-sol 本人，
   逐项重放你 round-2 的反例探针（含空格路径、双 runner、崩溃+介入提交、
   mid-unit resume、假时钟），确认每个反例现在被正确拒绝/防护。
2. **修复自身质量**：FX1–FX7 实现是否引入新缺陷？（对抗性视角：quoting
   绕过、guard 时序窗、三分支恢复的漏网形态、lock_busy 返回值语义、
   fail-closed resume 的误伤面、双向绑定的兼容性、账本边界）
3. **裁定复核**：GLM 3 个 append 阻塞点 + bookkeeper ACCEPTED 裁定 +
   Kimi 同意——你是否同意？（FX4 契约替换 / FX6 runtime caps 不绑定 /
   FX6 max_stage_rework schema-frozen）
4. **residual 复核**：R1（seed receipt call_budget 方向）、R2（FX1 枚举
   5/6，bookkeeper 补 6/6）、verbatim 证据文件 whitespace——非 required
   定性是否成立？
5. **全 stage 验收**：00-task 验收 1–29 对照 40-表；frozen 面（fingerprint
   公式、AUTO_TRANSITIONS、review-1 三对路由、seen-diff bind、
   post-cross-check blocking rerun、pilot 谓词、显式路径 git add）逐项
   未被侵蚀；default-off（`enabled_for_this_stage: false`）与 DRAFT-2
   共存成立。
6. **回归**：全套件（预期 161）独立重跑；`validate-stage --phase
   checkpoint` PASS；`git diff --check` 结论与 Kimi 注记一致。

## Provider 披露支线（按你的真实身份取一支，如实填写）

- **若你是 gpt-5.6 家族（openai）**：`reviewer_prior_involvement: "design"`
  （OpenAI provider 设计/intake 涉入 + sol 出过 round-1 BLOCKED 与 round-2
  REWORK findings）。你验证自己 findings 的关闭必须**从冻结范围与可执行
  反例出发**，不得凭记忆。
- **若你是 claude 家族（anthropic）**：`reviewer_prior_involvement: "design"`
  （Anthropic provider 设计涉入 + 现任 bookkeeper 为 claude-fable-5——
  双帽风险须在报告中显式评估：你评审的证据大量由同 provider 的 bookkeeper
  产出，须独立重跑而非采信）。
- 身份必须如实：`model` 字段填你的真实模型标识。本 stage round-2 曾发生
  第三方会话伪造 claude-fable-5 身份出具 verdict 的事件（已存证处置）——
  任何身份不实将被机械核对发现并零效力处理。

## 只读硬规则

- 仓库**只读**：不得 `git add`/`commit`/`push`，不得修改/新建仓内文件；
  落档由 bookkeeper 执行。若操作者显式授权你自行落档，你可且仅可**新增**
  `50-review-2-round3-<model>.md` 与 `review-2-round3-<model>.verdict.json`
  两个文件（不得触碰任何既有文件），并在报告中声明该授权。
- 允许：只读 git 命令、跑测试/校验命令、tempfile 临时目录实验。
- 不得 dispatch 其他模型；不得联网。

## Verdict 要求

报告末尾单个 JSON 代码块，符合 `schemas/review-verdict.schema.json`：
`model` 如实；`diff_fingerprint` = 你复算核对过的 stage 指纹；ACCEPT 判据
= round-2 findings 全部证据关闭 + 无新增 P0/P1/P2 required finding + 验收
对照通过；REWORK 时必须含可执行 `fix_start_prompt`（即便后果是
human_escalation——escalation 处置人需要它）。

## 页脚（报告末尾）

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 落档 round-3 verdict → ACCEPT=stage_accepted_waiting_user / REWORK=human_escalation_required
```
