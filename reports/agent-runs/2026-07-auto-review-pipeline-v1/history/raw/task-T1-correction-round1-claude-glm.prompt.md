<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T1-correction-round1-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      a385c7ad77da1611c6e952b2219aee56b49f442f
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T1 Correction Round 1 — `contract-and-schemas`

你是原 T1 Claude-GLM implementer 的 fresh bounded correction session。只修
bookkeeper inspection 中的 T1-B1–T1-B5。当前仍是人工 DRAFT-2 流程；不得
dispatch 任何模型。

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
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

开始前必须确认：branch 为
`stage/2026-07-auto-review-pipeline-v1`，T1 base 仍是
`a385c7ad77da1611c6e952b2219aee56b49f442f`，task status 为
`correction_packet_ready_for_human_dispatch`，auto/parallel mode 均为 false。
任一不符即停止并在 report 追加 blocker，不得自行改 status。

## Correction Writable Set

仅允许修改以下 delivery 文件：

```text
schemas/runner-receipt.schema.json
workflows/templates/stage-delivery.yaml
docs/auto-review-pipeline.md
AGENTS.md
docs/parallel-development-mode.md
```

仅允许 append 以下 evidence：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

其他全部只读。特别禁止 `status.json`、`70-handoff.md`、inspection/packet、
review files、`scripts/**`、manifest、registry、其他 T1 文件、T2/T3 文件、产品
与 funding-stage 路径。不得 commit、push、merge、rebase 或切换 branch。

## Required Corrections

### C1 — Receipt required/null-able evidence keys

在 `schemas/runner-receipt.schema.json` 顶层 `required` 增加：

```text
review_unit_id
task_id
prompt_path
raw_output_path
verdict_path
```

这些 key 必须始终存在；不适用时值为 JSON `null`。非 null 字符串必须
`minLength: 1`，证据路径必须是安全的 repo-relative path：拒绝 absolute path、
`..` traversal 与 newline。

### C2 — Registry reference enforcement

`adapter.registry_command_ref` 必须用 anchored pattern 限定为
`agents/registry.yaml#adapters.<id>.<command-key>`，不得接受 expanded command、
shell 片段、空白/newline 或 secret-like arbitrary value。再用 `if/then`、
`oneOf` 或等价 draft-2020-12 约束保证 adapter id 与 reference prefix 配对：

- `claude_glm` → `agents/registry.yaml#adapters.claude_glm.*`
- `kimi` → `agents/registry.yaml#adapters.kimi.*`
- `grok` → `agents/registry.yaml#adapters.grok.*`

不要把 expanded command 或新命令复制进 schema。现有 registry command refs 是
唯一来源。

### C3 — Executable workflow auto contract

保持原 manual guards/text 原义不变，在现有
`stage-delivery.yaml:auto_review_pipeline` 内做 additive machine-readable 补充：

1. activation predicate：仅 `enabled=true`、committed schema-valid
   human authorization、stage/branch/scope/budget match、parallel mutex 通过时，
   才启用 auto exception；否则 manual human dispatch/bookkeeper rules 不变。
2. authorized exception：runner 是 sole automatic dispatcher 与 sole mechanical
   writer；implementer/fix/reviewer model 永不 commit、永不写 authoritative
   status/handoff；review-2/merge 不变。
3. frozen nodes/order：preflight → implementation → initial blocking check →
   embedded cross-check（run/skip/unavailable）→ identical post-cross-check
   blocking rerun → seal → review-1；所有 next hop 来自 workflow mapping。
4. P7：initial blocking failure 只允许一次 automatic implementer fix，charge
   shared ledger；相同 blocking set 复测仍失败即 `human_escalation_required` +
   `80-*.md`，不得第二次 blocking fix。
5. review-1 fixed transitions：schema-valid ACCEPT、REWORK fix、invalid JSON
   retry/fallback、unavailable/tip-once escalation；不得由 model text 选路径。
6. completion predicate：所有 required units 均 schema-valid ACCEPT，且 verdict
   fingerprint 等于 unit fingerprint，才进入 `completed_review_1`。
7. pilot/default-flip predicate：两 pilot 类型、均到
   `stage_accepted_waiting_user`、最终 Grok schema-valid verdict、100% RECEIPT、
   escalation shape/drill；不新增 Grok-rate threshold，不自动 flip default。

YAML key/shape 应简洁、确定，供 T2 validator 与 T3 runner 直接读取，不要只复制
散文，也不要增加新 top-level Harness status。

### C4 — Normative P7 prose

在 `docs/auto-review-pipeline.md` 的 blocking/rework 操作正文明确：一次 initial
blocking failure 可派发一次 automatic fix 并 charge ledger；重跑相同 blocking set
仍失败，必须写 escalation 并停止。aggregate auto change cap≤2 不等于允许两次
blocking fix。同步引用 workflow mapping。

### C5 — Rewrite-on-touch vocabulary and evidence errata

只做不改变语义的锁词替换，并在 report 逐句记录 before/after：

- `AGENTS.md` 当前第 37、115、286、423 行附近的 advisory-pass 历史名称 →
  `embedded cross-check`；保留 validator `--phase pre-review` 的机械名称。
- `docs/parallel-development-mode.md` 已触及的 §6 内两处历史“预审”表述（当前
  第 329、336 行附近）→ `embedded cross-check`；不批量改其他未触及 section。

不要改写原始 `20-implementation.md` 内容。在文件末尾追加
`T1 Correction Round 1`，包含：

- T1-B1–B5/C1–C5 逐项 disposition；
- 所有本轮修改的既有句子逐字 before/after；
- 原报告勘误：实际 13 paths = 11 delivery + 2 shared evidence；原 status snapshot
  漏了 report 自身；原 receipt-required-fields 声明在修复前不准确；
- 最终 changed-file list、风险与 `git status --short`。

## Required Checks And Raw Evidence

把每条命令、**完整原始 stdout/stderr** 与 exit status 追加到
`60-test-output.txt`；不得重写已有 evidence：

```text
python3 -m json.tool schemas/auto-review-authorization.schema.json
python3 -m json.tool schemas/runner-receipt.schema.json
python3 -m json.tool reports/agent-runs/_template/status.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches / exit 1
```

再运行并记录以下 counterexample check；三个 invalid cases 必须各产生至少一个
schema validation error：

```bash
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("schemas/runner-receipt.schema.json").read_text())
Draft202012Validator.check_schema(schema)
base = {
    "schema_version": 1,
    "stage_id": "stage-example",
    "sequence": 1,
    "node": "review_1",
    "attempt": 1,
    "review_unit_id": "T1",
    "task_id": "T1",
    "adapter": {
        "id": "grok",
        "registry_command_ref": "agents/registry.yaml#adapters.grok.optional_review_command"
    },
    "prompt_path": "reports/agent-runs/stage-example/review.prompt.md",
    "raw_output_path": "reports/agent-runs/stage-example/review.raw-output.md",
    "verdict_path": "reports/agent-runs/stage-example/review.verdict.json",
    "started_at": "2026-07-11T00:00:00Z",
    "completed_at": "2026-07-11T00:00:01Z",
    "exit_status": 0,
    "timeout": False,
    "call_budget": {"before": 2, "after": 1},
    "failure_class": None,
    "next_transition": "completed_review_1"
}
v = Draft202012Validator(schema)
assert not list(v.iter_errors(base)), "positive receipt must validate"

missing = dict(base)
for key in ("review_unit_id", "task_id", "prompt_path", "raw_output_path", "verdict_path"):
    missing.pop(key)
assert list(v.iter_errors(missing)), "missing five required keys must fail"

expanded = dict(base)
expanded["adapter"] = {"id": "grok", "registry_command_ref": "grok --token SECRET"}
assert list(v.iter_errors(expanded)), "expanded command/secret-like ref must fail"

mismatch = dict(base)
mismatch["adapter"] = {
    "id": "grok",
    "registry_command_ref": "agents/registry.yaml#adapters.claude_glm.noninteractive_command"
}
assert list(v.iter_errors(mismatch)), "adapter/ref mismatch must fail"
print("RECEIPT SCHEMA POSITIVE/NEGATIVE CHECKS PASSED")
PY
```

再运行 YAML parse：

```bash
ruby -e 'require "yaml"; YAML.load_file("workflows/templates/stage-delivery.yaml"); YAML.load_file("agents/registry.yaml"); puts "YAML PARSE PASSED"'
```

`git diff --check <T1-base>..<T1-head>` 仍由 bookkeeper 在 delivery commit 后运行；
你不得 commit 来生成 head。

## Stop And Return

任何修复需要越过本 packet writable set、修改 frozen design、增加 fingerprint、
改 review-2/merge gate、启用本 stage auto mode，或调用 live model/network，立即
停止并追加 blocker。

完成后停止并返回 bookkeeper。不得 dispatch Kimi。结尾使用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 重新检查 T1 correction、独立复跑 frozen/counterexample checks；通过后才可 seal 并准备 Kimi review-1
```
