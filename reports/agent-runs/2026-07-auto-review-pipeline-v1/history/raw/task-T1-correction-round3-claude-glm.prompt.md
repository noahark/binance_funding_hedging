<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round3-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      a385c7ad77da1611c6e952b2219aee56b49f442f
prior_correction: round1-v2 and round2 executed; Fable5 reinspection (25-) found T1-R3-1/R3-2
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T1 Correction Round 3 — Node-Graph Closure（两处命名闭合，最小修正）

你是 T1 的 fresh bounded Claude-GLM correction session。Round1-v2 与 round2 已
执行并保留；Fable5 bookkeeper reinspection
（`25-second-reinspection-T1-fable5.md`）确认 R2-1/R2-2 主体关闭，仅剩两处
node-graph 闭合残留。只修 T1-R3-1/T1-R3-2，不得 dispatch 任何模型。

## Read First

- `reports/agent-runs/2026-07-auto-review-pipeline-v1/25-second-reinspection-T1-fable5.md`
- `workflows/templates/stage-delivery.yaml`（`auto_review_pipeline.executable_contract`）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`（§Transition Model）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

开始前确认：branch 为 `stage/2026-07-auto-review-pipeline-v1`；T1 base 为
`a385c7ad77da1611c6e952b2219aee56b49f442f`；task status 为
`correction_round3_packet_ready_for_human_dispatch`；auto/parallel mode 均
false。任一不符即 append blocker 并停止，不得改 status。

## Writable Set

仅允许修改：

```text
workflows/templates/stage-delivery.yaml
```

仅允许 append：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

其他全部只读。特别禁止：两个 schema、docs、AGENTS、registry、模板、
status/handoff/inspection/packet/review files、`scripts/**`、manifest、产品与
funding-stage 路径。不得 commit、push、merge、rebase、切换 branch。

## R3-C1 — 统一 post-cross-check blocking 节点名

`executable_contract.node_transitions` 中接收键 `post_cross_check_blocking`
改名为 `identical_post_cross_check_blocking_rerun`，与 `frozen_nodes_and_order`
及 `embedded_cross_check` 三个 event 的 target 完全一致。只改键名，不改其
`pass`/`fail` 分支值。

## R3-C2 — 定义 serial_unit_fallback 接收节点

`node_transitions.review_1.invalid_json.after_retry_limit` 的 target
`serial_unit_fallback` 当前无接收键。在 `node_transitions` 增加：

```yaml
serial_unit_fallback:
  eligible_candidate_found: "review_1"
  no_eligible_candidate: "human_escalation_required"
```

语义锚点：eligibility 规则不变，仍由 `review_1_routes.serial_fallback`
（serial_only、provider 不在 unit author/fix set）定义；本节点只表达路由
选择的两个确定性出口。同时删除 `review_1.serial_fallback_unavailable:
"human_escalation_required"` 这一行——其语义已被新节点的
`no_eligible_candidate` 分支完整覆盖，保留会造成同一转移两处定义。逐字
before/after 记入 report。

不得修改 `review_1_fixed_transitions` 与 `activation_predicate` 两个散文
块（结构化版本为权威，散文按 round2 "note 可保留"规则留存）；不得改
`state_transitions`、`allowed_next_transitions`、`review_1_routes`、
`pilot_predicate` 或任何 schema/docs。

## Required Checks And Raw Evidence

把每条命令、完整原始 stdout/stderr 与 exit status append 到
`60-test-output.txt`：

```text
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches / exit 1
ruby -e 'require "yaml"; YAML.load_file("workflows/templates/stage-delivery.yaml"); YAML.load_file("agents/registry.yaml"); puts "YAML PARSE PASSED"'
```

再运行并记录 node-graph 闭合断言（必须输出 `CLOSURE OK` 且 unresolved 为空）：

```bash
python3 - <<'PY'
import json, subprocess
y = subprocess.run(["ruby","-ryaml","-rjson","-e",
  'puts JSON.dump(YAML.load_file("workflows/templates/stage-delivery.yaml"))'],
  capture_output=True,text=True)
ec = json.loads(y.stdout)["auto_review_pipeline"]["executable_contract"]
nt = ec["node_transitions"]
node_keys=set(nt.keys()); terminals={"completed_review_1","human_escalation_required"}
def targets(x):
    if isinstance(x,str): yield x
    elif isinstance(x,dict):
        for v in x.values(): yield from targets(v)
unresolved=[(k,t) for k,spec in nt.items() for t in targets(spec)
            if t not in node_keys and t not in terminals]
assert ec["node_transitions"].get("identical_post_cross_check_blocking_rerun"), "R3-C1 key missing"
assert "serial_unit_fallback" in node_keys, "R3-C2 key missing"
assert len(ec["state_transitions"])==8, "state_transitions must stay 8"
print("unresolved:", unresolved)
assert not unresolved, "graph must close"
print("CLOSURE OK")
PY
```

在 `20-implementation.md` 末尾 append `T1 Correction Round 3`：R3-1/R3-2
disposition、逐字 before/after、最终 `git status --short`、风险。不得改写
先前报告。

## Non-Regression / Stop

不得破坏 round1-v2/round2 已通过面（receipt 18 required、三对 review-1
oneOf、authorization 安全路径、enum 相等、8 条 state_transitions、pilot
精确值、P7、disabled 表示、docs/README seal 收据命名）。任何修复需要越出
本 packet writable set 即停止并 append blocker。

完成后停止并返回 bookkeeper；不得 dispatch Kimi。页脚使用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 round3 闭合断言与冻结套件；通过后 seal T1 并准备人工 Kimi review-1 packet
```
