# Stage Intake: 2026-07-auto-review-pipeline-v1

## 用户指令

操作者明确要求：以
`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
为冻结方向，开启独立 Harness 修订 stage
`2026-07-auto-review-pipeline-v1`，不得实施或混入产品 stage 内容。

该决策表状态为 `FROZEN — POST DUAL REVIEW`，已合并 GPT/Codex 与 Claude
Fable 5 的 `ACCEPT-with-edits`，并明确授权下一步起草本 intake。

## 分类

- Complexity: `HIGH`
- Direction panel required now: `false`
- Existing synthesis covers this work: `true`
- User approved lightweight route: `false`
- HIGH direction-panel override: `true`
- Lightweight skip allowed: `true`（仅表示已有冻结综合覆盖，不降低 stage 复杂度）

## 方向与路由依据

- 冻结主输入：
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
- 决策链：design note → Fable 5 review → Codex review → divergence response →
  operator/Grok arbitration → GPT/Fable dual review → patch merge。
- 决策表已覆盖 D1–D12、P1–P13、单一 rework ledger、pilot gate、runner
  权限、隔离、fallback 与非目标；重新运行 direction panel 会重复已完成的
  多模型方向工作。
- 用户本轮“根据 40 表开 stage”的指令，作为 HIGH stage 跳过新 panel、直接
  进入 stage design 的明确 operator override。

## 复杂度理由

- 本 stage 修改 Harness 顶层权限与调度契约：model dispatch、bookkeeper/runner
  职能、review-1 路由、状态/validator 门、worktree 隔离及 rework 预算。
- 影响 `AGENTS.md`、workflow、registry、validator、adapter 文档、parallel-mode
  契约及新 runner/seal scripts，属于跨权威层的控制面变更。
- 需要 deterministic tests、legacy human-dispatch 回归、auto-mode fail-closed
  fixtures 与两个后续 pilot；因此不得按 LOW/MEDIUM 处理。

## 冻结目标

1. 新增默认关闭、stage opt-in 的 auto-review pipeline。
2. 唯一自动 dispatcher/mechanical writer 为 deterministic、non-LLM runner。
3. 实现者/评审者不得调用同伴模型、修改权威 status/handoff 或 commit。
4. embedded cross-check 在 seal 前执行；seen-diff bind 使用 patch byte-equality，
   不新增 fingerprint 协议。
5. review snapshot 使用现行 committed-range `diff_fingerprint`，公式零改动。
6. auto-mode review-1 使用 Grok（opt-in）；按冻结 review unit 与作者 provider
   集合执行隔离与 fallback。
7. stage 单一 `max_rework_per_stage=3`；review-1/test automatic code-changing
   retries 合计最多消耗 2，至少保留 1 给 review-2 REWORK。
8. review-2、产品/凭据 gates 与 merge-to-main 均保持人工门。
9. 先通过 docs-only pilot 与小型真实 pilot，才允许讨论默认值翻转。

## 初始范围

允许在 stage design 中进一步收窄的 Harness-only 边界：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `agents/developer-discipline.md`
- `agents/skills/` 中与 implementer/reviewer/runner 契约直接相关的文件
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- new `docs/auto-review-pipeline.md`
- `scripts/validate-stage.py`
- new deterministic `scripts/stage-seal.py` 与 runner
- Harness templates、manifest 与上述脚本的 deterministic tests/fixtures
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/`

## 禁止范围 / Non-goals

- 不修改 `backend/**`、`frontend/**` 或任何 runtime/product delivery。
- 不修改 public API、wire schema、资金费率语义或产品 PRD。
- v1 不修改 `schemas/review-verdict.schema.json` 的 verdict/role/fix prompt
  结构；P6 按冻结 runner routing 处理。
- 不修改现行 `diff_fingerprint` 算法，不新增 worktree fingerprint。
- 不把未接受的 auto pipeline 用于本 stage 自举；本 stage 继续使用当前
  DRAFT-2 human-dispatch/review gates。
- 不隐式启用任何既有或在途 stage。

## 必须在 stage design 冻结的剩余形状

- `auto_review_pipeline` opt-in/status 字段及版本。
- auto-run authorization artifact 的必填字段。
- D5 从 auto-mode fail-closed 转为 human-dispatch 的显式 mode-flip 字段。
- P8 call-count / wall-clock 的每 stage 配置与计数规则。
- serial/parallel review-unit machine shape、作者 provider 集合与 completeness
  predicate。
- runner RECEIPT、raw stdout、verdict JSON、`80-*.md` escalation 的精确路径。
- v1 multi-owner fix 采用串行写入还是 isolated task worktrees 后集成。
- 本 stage 自身的 implementer、review-1 与独立 review-2 路由。

## 人工门

- 本 intake 不授权实现或模型 dispatch；stage design、ADR、development
  breakdown 与 dispatch packet 完成后再进入实现。
- Codex/GPT 与 Claude provider 都参与过本方向决策；review-2 选人必须在设计中
  处理 prior-involvement，不能伪装成 `none`。
- 任何凭据、expanded alias、环境 dump、token 或 secret 不得落档。
- `review-2 ACCEPT` 仅进入 `stage_accepted_waiting_user`；合回 `main` 仍需用户
  明确验收。

## Stage 分支与设计输入导入

- Stage branch: `stage/2026-07-auto-review-pipeline-v1`
- Created from `main`: `45c21ee010fd3f2892a6677f58d5c8b02c2fbb0b`
- Frozen docs source branch: `docs/2026-07-auto-review-pipeline`
- Frozen docs source commit: `1997a65ccc66b40aa877781b55aaf807ea469dd6`
- H_intake 仅导入 auto-review 设计/评审链；排除同一 docs 历史中的 funding
  follow-up 文件及其 README 条目。

## 路由决定

- Current node: `stage-branch-intake`
- Next node: `stage-design`
- After design: `development-breakdown`（HIGH 必需）
- Implementation dispatch: 尚未授权
- Auto-review mode for this bootstrap stage: `disabled`

## Bookkeeper

- Provider/model/session: current Codex/GPT session (`openai`)
- Independent from future implementers: `true`
- Also implementer: `false`
- Disclosure: Codex authored prior design reviews and this intake; it is design
  involvement for later reviewer selection, not delivery-code authorship。

## Parallel Mode

- Uses current `docs/parallel-development-mode.md`: `false` at intake
- R10 dispatch tail required: `false` at intake
- R4 diff reconciliation required: `false` at intake
- Stage design must choose the implementation topology; the unaccepted target
  auto pipeline cannot self-host this bootstrap stage。

## Evaluator

- Provider: `codex`
- Model: current Codex/GPT session
- Skill: `complexity_evaluator` / `task_planner`
- Route deviation: registry 默认 complexity evaluator 为 Claude-GLM；本 stage
  的 `HIGH` 已由 operator 指令、冻结 decision table 与 GPT/Fable 双评审预先
  确定。再次人工 dispatch GLM 只会重复已冻结结论，因此由当前 Codex
  bookkeeper 如实记录分类，不额外启动 evaluator。

本地北京时间: 2026-07-11 11:30:02 CST
下一步模型: Codex/GPT（stage designer）
下一步任务: 根据冻结 decision table 起草 `00-task.md`、`10-design.md` 与 `11-adr.md`，随后交独立 development breakdown。
