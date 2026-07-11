<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round2-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      a385c7ad77da1611c6e952b2219aee56b49f442f
prior_correction: task-T1-correction-round1-v2-claude-glm.prompt.md (executed; reinspection found T1-R2-1/R2-2)
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T1 Correction Round 2 — Review-1 Fallback And Executable Transitions

你是 T1 的 fresh bounded Claude-GLM correction session。Round1-v2 已执行并保留；
bookkeeper reinspection 又发现 T1-R2-1/R2-2。只执行本 packet，不得 dispatch
任何模型。

## Read First

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/11-adr.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/24-bookkeeper-reinspection-T1.md`
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

开始前确认：branch 为 `stage/2026-07-auto-review-pipeline-v1`；T1 base 为
`a385c7ad77da1611c6e952b2219aee56b49f442f`；task status 为
`correction_round2_packet_ready_for_human_dispatch`；auto/parallel mode 均 false。
任一不符即 append blocker 并停止，不得改 status。

## Writable Set

仅允许修改：

```text
schemas/runner-receipt.schema.json
workflows/templates/stage-delivery.yaml
docs/auto-review-pipeline.md
```

仅允许 append：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

其他全部只读。禁止 status/handoff/inspection/packet/review files、registry、其他
T1 文件、`scripts/**`、manifest、产品/runtime、funding stages。不得 commit、
push、merge、rebase、切换 branch。

## R2-C1 — Make serial review-1 fallback receipts schema-valid

对 `node=review_1`，只允许三个精确 pair：

```text
grok        + agents/registry.yaml#adapters.grok.optional_review_command
kimi        + agents/registry.yaml#adapters.kimi.embedded_read_only_review_command
claude_glm  + agents/registry.yaml#adapters.claude_glm.embedded_read_only_review_command
```

用 `oneOf` 或等价 draft-2020-12 约束。不要允许 noninteractive/write/yolo/
availability refs 作为 review-1。

Schema 只表达可表示 route；runner/validator 仍检查：仅 serial unit 可 fallback、
candidate provider 不在 unit 全部 author/fix provider 集合、parallel tip 无 Kimi/
GLM fallback、Grok tip failure/repeated invalid verdict → human escalation。

正例：Grok primary、Kimi serial fallback、GLM serial fallback 全 valid。负例：
Kimi noninteractive review-1、Grok development review-1、adapter/ref mismatch 全
invalid。

## R2-C2 — Align embedded cross-check prose

`docs/auto-review-pipeline.md` 当前
`embedded cross-check ... (e.g. GLM↔Kimi or Grok)` 的 `or Grok` 没有冻结出处，
且 schema 的 embedded cross-check node 只允许 GLM/Kimi read-only refs。最小修改
为冻结示例 `e.g. GLM↔Kimi`；不要扩大 Grok cross-check route。在 report 记录该句
逐字 before/after。

## R2-C3 — Add executable state/node maps

在 `stage-delivery.yaml:auto_review_pipeline.executable_contract` 保留已通过的
guards/order/P7/disabled/allowed target set，但新增或重构为 runner 可直接读取的
structured mappings。Human-readable `note` 可保留；transition choice 不得只存在于
自然语言字符串。

1. **Structured activation requirements**：明确 status field/value、authorization
   schema ref、committed/human/not-expired、exact stage/branch/scope/budget match、
   parallel mutex、failure effect=no adapter call/manual rules unchanged。
2. **Eight state transitions**：增加 `state_transitions` list；每项有稳定 `id`、
   structured `from`、`event`、structured `to`、top-level effect/stop behavior，
   逐行对应 10-design Transition Model 八行。概念 disabled 用既有 null 表示。
3. **Structured node transitions**：增加 `node_transitions` mapping，event key →
   exact target，覆盖 implementation、initial blocking、one fix、cross-check run/
   skip/unavailable、post-cross-check blocking、seal/bind、review-1 ACCEPT/REWORK/
   invalid retry/fallback、fix loop、completion、budget/unroutable escalation。条件
   分支使用 object/list，不写“X or Y”让 runner 猜。
4. **Structured review-1 routes**：Grok primary exact ref；Kimi/GLM serial
   fallback exact refs；`serial_only:true`；provider-not-in-author-set；parallel-tip
   cross-pool disabled；high-end substitution false；attempt limit 2。
5. **Structured pilot predicate**：至少精确落：

```text
required_pilot_kinds = [docs_only, small_real]
required_terminal_status = stage_accepted_waiting_user
min_final_schema_valid_grok_verdicts = 1
required_adapter_receipt_completeness_rate = 1.0
require_escalation_shape_validation = true
require_controlled_escalation_drill_in_at_least_one_pilot = true
grok_rate_promotion_threshold = null
automatic_default_flip_allowed = false
```

保持 `allowed_next_transitions` 与 receipt enum 集合相等，不改 fingerprint、top-level
status、review-2/merge gates 或 auto default。

## R2-C4 — Evidence And Tests

在 `20-implementation.md` 末尾 append `T1 Correction Round 2`：R2-1/R2-2、
R2-C1–C3 disposition、所有既有句子 before/after、最终路径、风险、git status。
不要改写 prior reports。

把命令、完整 stdout/stderr、exit status append 到 `60-test-output.txt`：

```text
python3 -m json.tool schemas/runner-receipt.schema.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches / exit 1
ruby -e 'require "yaml"; YAML.load_file("workflows/templates/stage-delivery.yaml"); YAML.load_file("agents/registry.yaml"); puts "YAML PARSE PASSED"'
```

用 `jsonschema.Draft202012Validator` 运行上述三条 review-1 正例和三条负例。
另用 Ruby/Python 只读断言：

- `state_transitions` 恰有 8 个稳定 id，from/event/to 均是 structured fields；
- `node_transitions` 覆盖 implementation、initial blocking、embedded cross-check、
  post-cross-check blocking、seal、review-1、fix；
- review-1 fallback refs 与 receipt schema 三个 pair 一致；
- pilot exact values 全部存在；
- transition choice leaf 不以含 `or`/`then` 的自然语言字符串代替 mapping；
- receipt next-transition enum 仍等于 workflow allowed target set。

## Non-Regression / Stop

不得破坏 round1-v2 已通过的 receipt required/safe paths、authorization schema、
P7、disabled、seal path、Pilot docs、post-cross-check rerun、seen-diff bind、manual
mode、fingerprint、Authority Order、review-2/merge gates。不得启用本 stage auto
mode或调用 live model/network。

完成后停止并返回 bookkeeper；不得 dispatch Kimi。页脚使用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 独立复验 T1 round2 fallback/schema/transition maps；通过后才可 seal 并准备人工 Kimi review-1
```
