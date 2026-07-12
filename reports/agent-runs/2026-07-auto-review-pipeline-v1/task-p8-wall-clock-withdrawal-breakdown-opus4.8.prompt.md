<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude-opus-4-8 / anthropic（Fable5 quota exhausted per operator report）
adapter_cmd:   claude --model opus4.8 --permission-mode plan -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-p8-wall-clock-withdrawal-breakdown-opus4.8.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude.fallback_read_only_review_command; docs/model-adapters.md#Claude
executor:      human
task:          HIGH development breakdown — operator-approved withdrawal of mandatory P8 total wall-clock budget
skill:         task_planner（workflows/templates/stage-delivery.yaml development-breakdown）
inputs:        54-p8-wall-clock-withdrawal-operator-decision.md; 15-p8-wall-clock-withdrawal-design-amendment.md; 00-task.md; 10-design.md; 11-adr.md; current code/tests
outputs:       报告文本交回操作者；bookkeeper verbatim 落档为 12-p8-wall-clock-withdrawal-development-breakdown-opus4.8.md
next_dispatch: bookkeeper prepares bounded Claude-GLM implementation packet; bookkeeper/this packet must not execute it
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Development Breakdown — Remove Mandatory Total Wall-Clock Budget

你是本 stage 的 development breakdown author（Claude Opus 4.8，fresh
read-only/plan session）。按 `agents/skills/task-planner.md` 与 workflow 的
development-breakdown 节点工作。你不写代码、不改仓库、不 dispatch 模型、
不 commit；只返回完整 breakdown 文本，由 human operator 交给 bookkeeper
原样落档。

## Authority

1. 人类操作者决定：
   `reports/agent-runs/2026-07-auto-review-pipeline-v1/54-p8-wall-clock-withdrawal-operator-decision.md`
2. 设计修订：
   `reports/agent-runs/2026-07-auto-review-pipeline-v1/15-p8-wall-clock-withdrawal-design-amendment.md`
3. 已修订 stage 设计：`00-task.md`、`10-design.md`、`11-adr.md`
4. 原冻结 40-table 仅作历史证据；P8 wall-clock 部分已被上述人类决定取代。
5. 其余 AGENTS/workflow/schema/frozen D/P 决策仍有效。

背景：review-2 round 3 发现 wall-clock deadline 未在 seal commit 前执行，
但操作者随后确认总 runner-session wall-clock 本身不适合正常持续数小时的
长任务，正式撤销该要求。处置是**完整删除总会话时钟合同**，不是给旧时钟
补 guard，也不是把字段改成超大默认值或 optional 第二协议。

## Required Breakdown

输出必须包含：

1. 单一 Claude-GLM implementation task 的精确 writable set、read-only set、
   forbidden set；逐文件解释为什么需要改。
2. 完整删除矩阵：authorization schema、status/runtime fields、runner 方法与
   调用点、fixtures/tests、docs/examples/metrics 中每个规范依赖。
3. 明确保留矩阵：`max_model_calls`、adapter-specific timeout、rework/auto
   change caps、nullable `expires_at` call/commit guards、operator stop、
   transitions、receipt、seal/fingerprint、provider isolation、review/merge gates。
4. 测试矩阵：
   - stale auth 含 `wall_clock_seconds` 必须因 additionalProperties false 被拒；
   - fake clock 前进数小时但其他边界正常时 full run 完成；
   - individual adapter timeout 仍 fail closed 且计 call；
   - non-null expires_at 仍在 calls/commits 前生效；
   - manual/default-off/FX1–FX7 全回归。
5. 对现有测试的逐项处置：哪些删除、哪些改名、哪些替换；禁止仅放宽断言。
6. exact commands：全 suite、targeted tests、py_compile、validator checkpoint、
   git diff --check、forbidden product path、normative wall-clock residue scan。
7. 风险点和 review-1 focus，尤其区分 total-session clock 与 per-adapter
   timeout / expires_at。
8. 实现报告和测试证据必须 append 到 `20-implementation.md` /
   `60-test-output.txt`，implementer 不得改 status/handoff/review/packet。

## Non-Goals

- 不修改 product/backend/frontend/API。
- 不修改 fingerprint、seen-diff、AUTO_TRANSITIONS、review routing、seal
  commit protocol、call/rework ledger、pilot/default-off、merge gate。
- 不顺手修 round-3 的两个 P3 hygiene 项，除非它们与 wall-clock 删除发生
  同一行不可分割冲突；否则留 follow-up。
- 不重置 `rework_count=3`，不称为 rework 4。
- 不执行模型生成的命令或 next hop。

## Output Footer

报告末尾使用执行时本地 `date` 得到：

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched implementation）
下一步任务: 按 breakdown 冻结 implementation packet；移除总会话 wall-clock，保留单次 adapter timeout 与其他边界
```
