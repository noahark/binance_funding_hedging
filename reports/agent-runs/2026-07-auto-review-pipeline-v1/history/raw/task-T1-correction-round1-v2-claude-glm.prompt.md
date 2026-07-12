<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round1-v2-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      a385c7ad77da1611c6e952b2219aee56b49f442f
supersedes:    task-T1-correction-round1-claude-glm.prompt.md (never executed)
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T1 Merged Correction Round 1 v2 — `contract-and-schemas`

你是原 T1 Claude-GLM implementer 的 fresh bounded correction session。本 packet
合并 bookkeeper T1-B1–B5 与 Fable5 第二轮 inspection 的已裁决项。旧
`task-T1-correction-round1-claude-glm.prompt.md` 从未执行且已 superseded；只执行
本 v2 PROMPT BODY。当前仍是人工 DRAFT-2 流程，不得 dispatch 任何模型。

## Read First

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/11-adr.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/21-bookkeeper-inspection-T1.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/22-second-inspection-T1-fable5.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/23-T1-inspection-merge.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

若 Fable5 原始建议与 `23-T1-inspection-merge.md` 的 bookkeeper disposition
不同，以 merge disposition 为本修正轮边界；不得自行重开 Authority Order 或
stage-branch 例外设计。

开始前必须确认：

- branch 为 `stage/2026-07-auto-review-pipeline-v1`；
- T1 base 仍为 `a385c7ad77da1611c6e952b2219aee56b49f442f`；
- task status 为 `correction_round1_v2_ready_for_human_dispatch`；
- `correction_packet_revision` 为 `round1-v2`；
- auto/parallel mode 均为 false。

任一不符即停止并在 report 追加 blocker；不得自行改 status。

## Complete Writable Set For This Correction

只允许修改以下 delivery 文件：

```text
schemas/runner-receipt.schema.json
schemas/auto-review-authorization.schema.json
workflows/templates/stage-delivery.yaml
docs/auto-review-pipeline.md
AGENTS.md
docs/parallel-development-mode.md
reports/agent-runs/README.md
```

只允许 append 以下 evidence：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

其他全部只读。特别禁止 live `status.json`、`70-handoff.md`、inspection/packet、
review files、`scripts/**`、`harness-manifest.yaml`、`agents/registry.yaml`、其他
T1 文件、T2/T3 文件、产品/runtime 与 funding-stage 路径。不得 commit、push、
merge、rebase、创建/切换 branch。

## C1 — Receipt required/null-able evidence keys

在 `schemas/runner-receipt.schema.json` 顶层 `required` 增加：

```text
review_unit_id
task_id
prompt_path
raw_output_path
verdict_path
```

这些 key 必须始终存在；不适用时为 JSON `null`。非 null 字符串必须非空。
`prompt_path`、`raw_output_path`、`verdict_path` 必须为安全 repo-relative path，
拒绝 absolute path、`..` traversal、CR/LF/control-character 字符串。

## C2 — Exact registry-reference enforcement

`adapter.registry_command_ref` 必须：

1. 是 anchored `agents/registry.yaml#adapters.<id>.<command-key>` reference；
2. 与 `adapter.id` 一致；
3. 与 `node` 所允许的现有 registry command key 一致。

通过 `allOf` + `if/then`、`oneOf` 或等价 draft-2020-12 约束锁定现有 refs：

- implementation/fix owner 使用该 adapter 的现有 noninteractive/write command
  reference；
- embedded cross-check / serial review-1 fallback 使用现有 read-only/embedded
  reference；
- Grok review-1 使用
  `agents/registry.yaml#adapters.grok.optional_review_command`。

Yolo、availability probe、任意同-prefix key、expanded command、shell 片段、空白/
newline 或 secret-like arbitrary value 都必须 schema-invalid。不要复制 expanded
command，不要发明新 registry key。

## C3 — Executable workflow contract and transition/schema alignment

保持 manual guards/text 原义。在现有
`stage-delivery.yaml:auto_review_pipeline` 内 additive 补齐：

1. activation predicate：仅 `enabled=true`、committed schema-valid human
   authorization、stage/branch/scope/budget exact checks、parallel mutex 通过时，
   才启用 auto exception；否则 manual human-dispatch/bookkeeper rules 原样生效。
2. authorized exception：runner 是 sole automatic dispatcher 与 sole mechanical
   writer；implementer/fix/reviewer models 永不 commit、永不写 authoritative
   status/handoff；review-2/merge 不变。
3. frozen nodes/order：preflight → implementation → initial blocking → embedded
   cross-check（run/skip/unavailable）→ identical post-cross-check blocking rerun →
   seal → review-1；所有 next hop 只来自 workflow mapping。
4. P7：initial blocking failure 只允许一次 automatic fix 并 charge shared ledger；
   同一 blocking set 复测仍失败即 `human_escalation_required` + `80-*.md`，不得
   第二次 blocking fix。
5. review-1 fixed transitions：schema-valid ACCEPT、REWORK fix、invalid JSON
   retry/fallback、unavailable/tip-once escalation；model text 不得选择路径。
6. completion predicate：每个 required unit 均 schema-valid ACCEPT，且 verdict
   fingerprint 等于 unit fingerprint，才进入 `completed_review_1`。
7. pilot/default-flip predicate：两个 pilot 类型、均到
   `stage_accepted_waiting_user`、最终 Grok schema-valid verdict、100% adapter-call
   RECEIPT、escalation shape/drill；不增加 Grok-rate threshold，不自动 flip。

Workflow auto block 必须提供一个 machine-readable
`allowed_next_transitions` list。`runner-receipt.schema.json` 非 null
`next_transition.enum` 必须与该 list 集合逐项相等；删除没有 auto-mode 出处的
`bookkeeper_decision`。历史 manual `bookkeeper-decision` node 不是 auto 出处。

同时冻结表示约定：transition matrix 中 `disabled` 是概念态，机器表示严格为
`enabled=false + dispatch_mode=human_dispatch + runner_state=null`，不是第六个
`runner_state` value。

## C4 — Normative P7 prose and disabled representation

在 `docs/auto-review-pipeline.md` blocking/rework 正文明确：一次 initial blocking
failure 可派发一次 automatic fix 并 charge ledger；重跑相同 blocking set 仍失败
必须写 escalation 并停止。aggregate auto change cap≤2 不代表可做两次 blocking
fix。同步引用 workflow mapping。

在 transition/status 正文加一句：`disabled` 是概念态，实际 JSON 表示为
`enabled:false`、`dispatch_mode:human_dispatch`、`runner_state:null`。

## C5 — Authority/vocabulary rewrite-on-touch

不要把 `docs/auto-review-pipeline.md` 提升进 AGENTS Authority Order；A1 已在 merge
记录为需 operator/design amendment 的候选，本轮不得改变 conflict precedence。

只做不改变语义的锁词替换，并在 report 逐句 before/after：

- `AGENTS.md` 当前第 37、115、286、423 行附近 advisory-pass 历史名称改为
  `embedded cross-check`；其中 Authority Order 句只换术语，不加新 authority。
- `docs/parallel-development-mode.md` 已触及 §6 内第 329、336 行附近两处历史
  “预审”表述改为 `embedded cross-check`；不批量改其他未触及 section。
- validator `--phase pre-review` 的机械名称保持不变。

## C6 — Seal receipt normative path

在 `docs/auto-review-pipeline.md` §8 和 `reports/agent-runs/README.md` 同步冻结：

```text
runner-<seq>-seal.receipt.json
```

必须说明：它是 deterministic seal evidence，shape 由 T2 seal contract 实现；
它不是 model-adapter invocation receipt，不使用
`schemas/runner-receipt.schema.json`，也不计入 P11 expected adapter calls /
schema-valid adapter RECEIPT denominator。不要新造另一套 seal 命名族。

## C7 — Authorization schema symmetric hardening

在 `schemas/auto-review-authorization.schema.json`：

- `approval_evidence_path` 必须非空、安全 repo-relative，拒绝 absolute、`..`、
  CR/LF/control characters；
- 非 null `supersedes` 使用同一安全 repo-relative 约束；
- `scope.task_ids` 加 `minItems: 1` 与 `uniqueItems: true`；
- `stage_branch` 必须非空且拒绝 CR/LF/control characters，runner 仍做 exact
  status/branch match。

不要加 `^stage/` pattern：AGENTS 允许 intake 记录 explicit user-approved branch
exception；schema 不得使该高权威例外失效。

除上述加固外，不得改 authorization 字段集、3/≤2/2 冻结数字、required+nullable
`expires_at`、`authorized_by: human` 或 high-end false。

## C8 — Evidence append, errata, and minor dispositions

不得改写/删除原 `20-implementation.md`。在末尾追加
`T1 Merged Correction Round 1 v2`，包含：

- B1–B5、A2/A3/A4/A6 的逐项 disposition；
- A1 deferred 原因；
- 所有本轮修改的既有句子逐字 before/after；
- 原报告勘误：实际 13 paths = 11 delivery + 2 shared evidence；原 status snapshot
  漏了 report 自身；原 receipt-required-fields 声明在修复前不准确；
- A5 记录：当前四处 fingerprint 公式文本逐字一致；不改公式、不新增 protocol，
  T2 仍须以 shared canonical function 作为唯一 executable implementation；
- A7 记录：registry 历史 machine key `embedded_pre_review` 仅兼容保留，不是允许
  新散文继续使用旧术语的先例；不得改该 key；
- final changed paths、风险与 `git status --short`。

## Required Checks And Raw Evidence

把每条命令、**完整原始 stdout/stderr** 与 exit status append 到
`60-test-output.txt`，不得重写已有 evidence：

```text
python3 -m json.tool schemas/auto-review-authorization.schema.json
python3 -m json.tool schemas/runner-receipt.schema.json
python3 -m json.tool reports/agent-runs/_template/status.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches / exit 1
```

运行并记录 receipt 正/负例：positive valid；缺五 required keys invalid；expanded/
secret-like ref invalid；adapter/ref mismatch invalid；同-prefix yolo/availability ref
invalid；`next_transition=bookkeeper_decision` invalid。

运行并记录 authorization 正/负例：positive valid；absolute/traversal/newline
`approval_evidence_path` invalid；unsafe non-null `supersedes` invalid；empty/duplicate
`task_ids` invalid；control-character branch invalid。另加一个 safe、non-`stage/`
branch 正例，证明 schema 保留 user-approved exception、runner 再做 exact match。

这些例子必须用 `jsonschema.Draft202012Validator` 对实际 schema 执行；每个 invalid
case 至少产生一个 validation error。不得只检查 JSON parse。

再运行并记录：

```bash
ruby -e 'require "yaml"; YAML.load_file("workflows/templates/stage-delivery.yaml"); YAML.load_file("agents/registry.yaml"); puts "YAML PARSE PASSED"'
```

使用 Ruby YAML + JSON 或等价只读脚本断言：

- workflow `allowed_next_transitions` 集合等于 receipt schema
  `next_transition.enum` 去除 null 后的集合；
- 集合不含 `bookkeeper_decision`；
- docs 与 README 都出现精确 `runner-<seq>-seal.receipt.json`；
- disabled representation 三字段与 runner-state enum 不包含 disabled。

`git diff --check <T1-base>..<T1-head>` 仍由 bookkeeper 在 delivery commit 后运行；
你不得 commit 生成 head。

## Non-Regression Guard

不得破坏已通过面：default-off templates、authorization frozen numbers 与 nullable
expiry、Pilot Evaluation Contract、post-cross-check blocking rerun、seen-diff bind、
review-2/merge human gates、manual mode、fingerprint formula、product isolation。

## Stop And Return

任何修正需要越过 writable set、改 frozen design、增加 fingerprint、改变
Authority Order、硬编码 `^stage/`、改 review-2/merge gate、启用本 stage auto
mode、调用 live model/network，立即停止并 append blocker。

完成后停止并返回 bookkeeper。不得 dispatch Kimi。结尾使用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 重新检查 merged T1 correction、独立复跑 frozen/counterexample checks；通过后才可 seal 并准备 Kimi review-1
```
