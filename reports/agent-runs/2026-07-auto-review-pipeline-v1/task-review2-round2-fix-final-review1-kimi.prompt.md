<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  kimi / kimi-code/kimi-for-coding
adapter_cmd:   kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-round2-fix-final-review1-kimi.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.kimi.noninteractive_command; docs/model-adapters.md#Kimi
executor:      human
task:          re-review-1 of review-2 round-2 FINAL fix unit (FX1-FX7, rework 3/3)
review_range:  846bec036d62a3cdb243325f16977bd2c1396ade..a057d063523664a2fcfa8cc4db9e9af789f15730
diff_fingerprint: a057d063523664a2fcfa8cc4db9e9af789f15730:cd9756c95f45834c120b72fa16ffeec1a9f5fe7e3b86225ff05bb0a90a2a80c2
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       评审报告文本交回操作者（bookkeeper 落档为 30-review-1-review2-round2-final-fix.md + review-1-review2-round2-final-fix.verdict.json）
next_dispatch: bookkeeper（落档 + 若 ACCEPT 则准备 review-2 round 3 packet）
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Re-review-1（fix 单元，正式 review-1 轨）：review-2 round-2 FINAL fix FX1–FX7

你是本 stage 的 review-1 评审者（Kimi，fresh **read-only** session）。你在
stage `2026-07-auto-review-pipeline-v1`（分支 `stage/2026-07-auto-review-pipeline-v1`）
上评审 review-2 round-2 REWORK（gpt-5.6-sol record，5×P1+3×P2）触发的
**最后一格修复交付（rework 3/3）**。

角色规范：本 packet 对应 workflow review-1 节点（`workflows/templates/
stage-delivery.yaml` `review_1`，`skill: code_reviewer`）。先读
`agents/skills/code-reviewer.md` 并按该 skill 的评审纪律执行本任务。

## 评审范围（frozen）

- fix 单元 diff：`git diff 846bec036d62a3cdb243325f16977bd2c1396ade..a057d063523664a2fcfa8cc4db9e9af789f15730`
- 单元指纹（先自行复算核对，不符即 BLOCKED）：
  `a057d063523664a2fcfa8cc4db9e9af789f15730:cd9756c95f45834c120b72fa16ffeec1a9f5fe7e3b86225ff05bb0a90a2a80c2`
  公式：`head_sha + ":" + sha256(git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json')`
- 交付文件应恰好为：`scripts/auto-review-runner.py`、`scripts/stage-seal.py`、
  `scripts/tests/test_auto_review_runner.py`、`scripts/tests/test_stage_seal.py`
  + append-only `20-implementation.md`、`60-test-output.txt`。范围外任何改动
  = finding。

## Read First（顺序）

1. `agents/skills/code-reviewer.md`（本节点 skill——评审纪律）
2. `reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round2-gpt-5.6-sol.md`
   §Findings（修复权威：5×P1 + P2#1/P2#2；P2#3 已由 bookkeeper 在 aa9f7c1 清毕，不在本单元）
3. `reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-round2-fix-final-claude-glm.prompt.md`
   （修复规格：FX1–FX7 四段式 + 全局禁令 G1–G5——判"漂移"以此为准）
4. `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
   末段「Review-2 Round 2 Final Fix」（GLM 交付报告：逐项 disposition、
   红→绿证据、FX→测试映射、3 个 append 阻塞点）
5. `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`
   末两段（GLM required checks + bookkeeper 复验证据，含 8/8 破坏性验证与
   R1/R2 residual 注记）
6. 代码现状：`scripts/auto-review-runner.py`、`scripts/stage-seal.py`（改动
   函数全文通读，不只看 diff）

## 你要回答的问题（全部）

1. **逐项关闭**：FX1–FX7 是否逐项按 sol findings 原文 + packet 四段式规格
   关闭？（每项给 disposition：closed / partially / not closed + 依据）
2. **禁令遵守**：G1（真实对象测试）、G2（既有测试改动仅限 FX7 指名一处 +
   FX4 契约替换须有 blocker）、G3（每 hunk 可指认 FX 编号）、G4（红→绿
   证据）、G5（frozen 面未触碰）是否成立？
3. **阻塞点裁定复核**：GLM 的 3 个 append 阻塞点（FX4 既有测试契约替换、
   FX6 runtime caps 不绑定、FX6 max_stage_rework schema-frozen）与
   bookkeeper 的 ACCEPTED 裁定是否成立？若你认为任一裁定错误，作为
   finding 提出。
4. **residual 复核**：bookkeeper R1（seed receipt call_budget 方向与生产
   相反，判定为无行为影响）、R2（FX1 字符串级枚举 5/6，bookkeeper 探针补
   6/6）——是否同意其非 required 定性？
5. **回归**：全套件（预期 161）独立重跑；round-1 F2–F7 的负测试与
   TransitionTruthSourceTests 未被破坏。

## 只读硬规则

- 你对仓库**只读**：不得 `git add`/`commit`/`push`，不得修改任何文件，
  不得写 status/handoff/评审文件——落档由 bookkeeper 执行（AGENTS.md
  "Reviewers are read-only"）。
- 允许：只读 git 命令、跑测试与校验命令（`python3 -m unittest …`、
  `scripts/validate-stage.py … --phase checkpoint`、`git diff --check`）、
  在 tempfile 临时目录做任何实验。
- 不得 dispatch 其他模型；不得联网。

## Verdict 要求

报告末尾给单个 JSON 代码块，符合 `schemas/review-verdict.schema.json`：
- `model`：你的真实模型标识（如实填写）
- `reviewer_prior_involvement`：如实（你此前任本 stage review-1，评审过
  round-1 fix 单元；对本 FINAL fix 单元无 prior involvement——按 schema
  取值规则如实声明）
- `diff_fingerprint`：你自行复算核对过的单元指纹
- ACCEPT 判据：FX1–FX7 全部 closed 且无新增 P0/P1/P2 required finding
- REWORK 时必须含可执行 `fix_start_prompt`。**注意终格语义**：本 stage
  rework 账本已 3/3 耗尽——你的 REWORK 将由 bookkeeper 落档为
  `human_escalation_required`（不再有自动修复轮）。请勿因此软化判定：
  该 REWORK 就 REWORK，fail-closed 优先。

## 页脚（报告末尾）

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 落档 re-review-1 → 若 ACCEPT 出 review-2 round 3 packet；若 REWORK 落 human_escalation_required
```
