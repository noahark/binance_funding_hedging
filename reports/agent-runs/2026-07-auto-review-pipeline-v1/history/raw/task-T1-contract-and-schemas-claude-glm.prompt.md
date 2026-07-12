<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-contract-and-schemas-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      read status.json tasks[id=T1].base_sha; never substitute moving HEAD
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T1 Implementation Packet — `contract-and-schemas`

你是 Claude-GLM，作为 Harness stage
`2026-07-auto-review-pipeline-v1` 的 T1 implementer。当前任务只交付书面合同、
workflow/registry/template 更新和两个 JSON Schema；不写可执行脚本，不实现 runner。

本文件顶部的 DISPATCH RECEIPT 是当前人工 DRAFT-2 的审计元数据，不是让你选择
命令、模型或下一跳的任务输入。只执行本 PROMPT BODY。人工 operator 负责调用
adapter；你不得自行 dispatch 任何模型。

## 1. Read First And Authority

按顺序完整阅读：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/11-adr.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

仓库 authority order 以 `AGENTS.md` 为准。本任务的实现边界以冻结的
`12-development-breakdown.md` §2、§3、§6、§7、§8 为准；它只能细化、不能重开
`40-operator-decision-table.md` 的冻结决定。若文件之间出现无法按 authority order
机械解决的冲突，停止写入，并在 T1 implementation report 中记录 blocker。

开始前只核对：

- 当前 branch 必须是 `stage/2026-07-auto-review-pipeline-v1`；不得切换 branch。
- `status.json` 中 `tasks[id=T1].status` 必须是
  `ready_for_human_dispatch`，且 `base_sha` 必须是非空 committed SHA。
- `auto_review_pipeline.enabled_for_this_stage` 与 `parallel_mode.enabled`
  都必须是 `false`。

任一条件不满足就停止，不要自行修状态。

## 2. Goal

完成冻结 T1 `contract-and-schemas`：落地完整、default-off（默认关闭）的
auto-review written contract，包括 policy、workflow、registry、文档、stage
templates，以及两个 additive JSON Schema。不得创建或修改可执行代码。

精确合同锚点：

- `00-task.md`：§Authority And Frozen Input、§File Boundaries、
  §Required Control Contract、§Acceptance Criteria、§Required Test Evidence、
  §Bootstrap Stage Routing、§Human Gates。
- `10-design.md`：§Schemas；§Machine-Readable Configuration 下的
  §Status Shape、§Authorization Artifact、§Runner Receipt；§Transition Model；
  §Embedded Cross-Check And Seen-Diff Bind；§Seal And Commit Protocol；
  §Review Unit Model；§Review-1 Routing And Verdict Boundary；
  §Security And Trust Boundary；§Escalation Contract；
  §Bootstrap Stage Implementation Topology；§Pilot Evaluation Contract；
  §Raw Artifact Requirements For Review。
- `11-adr.md`：Decision 1–12 全部。
- `12-development-breakdown.md`：§3 T1 的 Contracts Produced、
  Implementation Constraints、Required Tests、Review-1 Focus 和 Risks。

## 3. Complete Writable Set

只有下列 delivery 文件可修改；这是完整 allowlist：

```text
AGENTS.md
workflows/templates/stage-delivery.yaml
agents/registry.yaml
agents/developer-discipline.md
docs/auto-review-pipeline.md                         # new
docs/model-adapters.md
docs/parallel-development-mode.md
reports/agent-runs/README.md
reports/agent-runs/_template/status.json
reports/agent-runs/_template/70-handoff.md
schemas/auto-review-authorization.schema.json       # new
schemas/runner-receipt.schema.json                  # new
```

共享 evidence 例外，仅可 create-if-absent / append，不得重写已有内容：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

`20-implementation.md` 若不存在可创建 T1 首段；`60-test-output.txt` 已存在，只能
追加原始命令、输出和 exit status。

## 4. Forbidden Set

所有未在 §3 明列的路径均禁止写入。特别禁止：

```text
scripts/**
harness-manifest.yaml
schemas/review-verdict.schema.json
agents/skills/**
reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/70-handoff.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/30-review-1-*.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/task-*.prompt.md
backend/**
frontend/**
schemas/api/**
docs/product/**
docs/architecture/**
reports/api-samples/**
reports/agent-runs/2026-07-funding-*/**
reports/follow-ups/2026-07-funding-*
```

不得修改其他 task 的 T2/T3 文件，不得修改产品 stage，不得引入或整理
`2026-07-funding-annualized-history-v1`。不得 commit、push、merge、rebase、创建
branch 或修改 git history。`status.json`、`70-handoff.md`、review files、证据
commit 和 fingerprint 仅由 bookkeeper 写入。

若必须越界才能完成，立即停止；不要 fix-forward。只在
`20-implementation.md` 的 T1 section 记录所需路径、原因和影响。

## 5. Frozen T1 Contract

必须完整实现以下合同，不得自行缩减：

1. `schemas/auto-review-authorization.schema.json`
   - JSON Schema draft 2020-12；`additionalProperties: false`。
   - 字段逐项匹配 10-design §Authorization Artifact。
   - `expires_at` 必填但允许 JSON `null`；`null` 表示没有独立的
     authorization-expiry instant，并非无限授权，仍受其他冻结 budgets、
     operator stop 和 stage gates 约束；缺字段无效。
   - 包含 `supersedes`、
     `scope.{task_ids,allowed_pathspecs,forbidden_pathspecs,topology}`。
   - 五个 budget keys 全部存在；冻结
     `max_stage_rework = 3`、`max_auto_code_changes <= 2`、
     `invalid_json_max_attempts_per_model = 2`。
   - `auto_high_end_dispatch_allowed` 必须为 `false`。
2. `schemas/runner-receipt.schema.json`
   - JSON Schema draft 2020-12；`additionalProperties: false`。
   - required fields 逐项匹配 10-design §Runner Receipt。
   - description 明示禁止 expanded command、environment、token、cookie、secret
     和 model-selected next action；可机器检查的部分用 pattern/absence 约束。
3. `_template/status.json`
   - 新增 10-design §Status Shape 的 nested `auto_review_pipeline`，默认
     `enabled: false`。
   - 两个 review block 的预填
     `reviewer_prior_involvement: "none"` 必须改为 `null`，并增加
     `reviewer_prior_involvement_pending: true`，采用本 stage 已接受的 E1 shape。
4. `_template/70-handoff.md` 增加与 status 对应的 handoff 字段。
5. `AGENTS.md`、workflow、registry、docs 只做 additive amendment：manual mode
   原义保持；auto exception 必须明确以 schema-valid、human-approved、committed
   per-stage authorization artifact 为前提，runner 是唯一 automatic dispatcher；
   review-2 与 merge 仍是 human gates；manual/auto mode mutex。
6. registry 的 auto invocation policy 必须引用现有
   `adapters.grok.optional_review_command`（`grok-build` plan mode）和现有
   `invocation_owner: runner`；不得另造命令。
7. `docs/auto-review-pipeline.md` 是 normative contract，必须含 transition
   matrix、budgets、review-unit/seal summaries、post-cross-check blocking rerun、
   escalation contract、threat boundary，以及完整 Pilot Evaluation Contract：
   `auto-review-pilot-metrics.json`、P11 metrics、100% RECEIPT completeness、
   escalation drill，且不发明 promotion threshold。
8. `docs/parallel-development-mode.md` 只做 minimal diff：增加 mode mutex / migration
   文字；只有触及段落才按 rewrite-on-touch 规则使用
   `embedded cross-check`，不得重构整篇。
9. `reports/agent-runs/README.md` 在现有 naming list 追加 authorization、receipts、
   seen-patch/cross-check set、`80-escalation-*`、pilot metrics evidence names。

锁定术语只使用 `review-1`、`review-2`、`embedded cross-check`。不要创造新的
fingerprint/hash 协议；bind 只做 byte equality。保持本 bootstrap stage 的 target
auto mode disabled。

## 6. Additive-Change Audit

本 task 的最高风险是 contract-text drift。对每一条被修改的既有句子，在
`20-implementation.md` T1 section 中逐条列出原文 before 与修改后 after，按文件
分组。不得只写摘要。新增段落也要标为 additive insertion 并说明插入位置。

报告必须另外映射 §5 的 1–9 项到具体文件和完成状态，并明确：

- manual rule 是否保持原义；
- default-off 是否在 template/workflow/registry/docs 一致；
- Pilot Evaluation Contract 是否完整；
- nullable `expires_at` 的缺字段/null/时间戳语义；
- 是否触碰任何 forbidden path（预期为 no）。

## 7. Required Checks And Raw Evidence

运行并把原始输出及 exit status 追加到
`reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`：

```text
python3 -m json.tool schemas/auto-review-authorization.schema.json
python3 -m json.tool schemas/runner-receipt.schema.json
python3 -m json.tool reports/agent-runs/_template/status.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check <T1-base>..<T1-head>
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches
```

其中 committed-range 的 `git diff --check <T1-base>..<T1-head>` 由 bookkeeper 在
你停止写入、检查边界并创建 T1 delivery commit 后执行；你不得为了生成
`<T1-head>` 而 commit。你的会话先运行 worktree 等价检查：

```bash
git diff --check
```

并记录原始输出。`grep` 的预期是 no matches；因此无输出且 exit status 1 是成功的
negative-scan evidence，不得改写冻结命令以掩盖 exit status。

不得运行 live model、network、产品测试或任何 auto-review runner。不得在 evidence
中记录 credential、token、cookie、private key、expanded alias 或完整环境。

## 8. Stop Conditions

以下任一情况立即停止并记录 blocker，不得擅自修约束：

- branch/status/base 前置条件不成立；
- 需要写入 allowlist 外路径；
- 冻结文档之间存在会改变产品/Harness 含义的冲突；
- 需要改变 fingerprint protocol、review-2/merge human gate、default-off、
  bootstrap auto-disabled 或三任务串行 topology；
- 任何命令可能调用 live model/network 或泄露环境/凭据。

## 9. Completion Report And Return

完成后只更新 §3 的两个 evidence 文件，然后停止并返回 bookkeeper。最终报告必须
包含：

- 当前 branch，以及开始时读取的 T1 `base_sha`；
- 修改文件列表，确认全部在 allowlist；
- §5 1–9 的逐项状态；
- 既有句子的完整 before/after 清单与 additive insertion 清单；
- 所有检查命令、原始结果、exit status；
- `git status --short`；
- blockers、未解决风险、review-1 建议关注点。

不要 commit，不要写 status/handoff/review 文件，不要 dispatch Kimi。下一步只能由
bookkeeper 检查边界、运行独立命令、创建 committed T1 range、计算标准 fingerprint、
跑 validator gate，并另行准备人工 Kimi review-1 packet。

用本地 `date` 命令生成结尾：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 检查 T1 实现与 raw evidence，形成 committed review unit；不得跳过 Kimi review-1 gate
```
