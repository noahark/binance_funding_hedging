<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-serial-v1-slimming-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
task:          T4 serial-only auto-review v1 slimming — parallel removal + auth shrink + P8 removal + registry timeout alignment + startup/history policy
skill:         senior_developer + minimal_change_engineer
authority:     16-serial-v1-slimming-design.md; 12-serial-v1-slimming-development-breakdown-codex.md; 54-p8-wall-clock-withdrawal-operator-decision.md
rework_charge: 0 — separately human-authorized contract amendment; historical ledger stays 3/3
outputs:       append 20-implementation.md + 60-test-output.txt; code/docs/tests within exact writable set
next_dispatch: none（bookkeeper verifies, commits, then prepares Kimi review-1）
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T4 Implementation — Serial-Only Auto Review v1 Slimming

你是 Claude-GLM / GLM-5.2 implementer（provider identity `zhipu_glm`）。
这是操作者在 escalation 后明确授权的合同精简，不是 rework 4。你不得
dispatch 任何模型、不得 commit、不得 push、不得联网、不得修改
status/handoff/history/review/verdict/packet。实现必须 stdlib-only。

## Read First

1. `AGENTS.md`
2. `16-serial-v1-slimming-design.md`
3. `12-serial-v1-slimming-development-breakdown-codex.md`
4. `54-p8-wall-clock-withdrawal-operator-decision.md`
5. 当前生产文件与对应 tests

不要递归读取 `history/`。只有本 packet 明确引用某个旧 finding 时才读取
单个历史文件；本任务所需的当前要求已全部冻结在上述三份 active 文档中。

## Exact Writable Set

仅允许修改 breakdown §Exact Writable Set 中列出的 17 个 contract/runtime/
test 文件，并 append 两个 evidence 文件。`scripts/stage-seal.py` 与其测试
只读；产品路径全部禁止。若实现证明需要额外文件，停止、append blocker，
不得 fix-forward。

## Required Behavior

### A. Serial-only v1

- 删除 auto authorization/runtime/docs/workflow 中的 parallel topology、
  parallel tip、integration unit 和自动 worktree integration 承诺。
- auto review unit 仅 `kind=task`。
- 保留旧 manual `parallel_mode`；auto enabled 时仍与之互斥。
- Grok primary + eligible serial Kimi/GLM fallback 固定在 workflow/registry。

### B. Slim authorization

严格按 design 的 keep/remove 字段表修改 JSON schema、手写 validator、
runner preflight、fixtures、templates、docs。`additionalProperties:false`；
每个 removed field 都要有独立 negative test。

### C. Remove total wall clock

- 删除 `wall_clock_seconds`、`run_started_at`、`run_deadline_at`、
  `_check_wall_clock`、`_init_wall_clock` 及所有调用。
- 删除 `timedelta` 等仅为总时钟存在的 import。
- fake clock 前进数小时本身不得停止健康 run。
- `expires_at` 的 call/commit guard 保持原样。

### D. Registry-driven per-call timeout

- restricted registry loader 同时读取 `timeout_seconds` 与
  `optional_review_timeout_seconds`。
- invocation 按 adapter + command 解析 timeout；command-specific override
  优先，adapter default 其次；缺失/非法必须 preflight fail closed，不能静默
  用统一 1800 覆盖生产配置。
- invoker 测试注入仍可观测收到的 timeout。
- GLM=3000、Grok optional review=900、其他按真实 registry。
- timeout 继续计 call、写 receipt、按现有路线停止。

### E. Startup/history policy

- AGENTS 顶部附近加入 Startup Read Budget：新终端只读 AGENTS、active
  workflow、active status/handoff、`status.current_inputs`；非必要不读
  `history/` 或递归扫描 `reports/agent-runs/`。
- review/audit/finding 明确引用时必须能读取 history raw；不得以瘦身隐藏证据。
- README/templates 对齐 cold-history + active-context 约定。

### F. Adjacent P3

- 修正 duplicate-shadowed FX6 test method；两个方向使用唯一测试名并均执行。
- 修正 runner-lock docstring，使其与 lock loser `lock_busy` 零写行为一致。

## Anti-Drift

- 不改 fingerprint、seen-diff、seal transaction、receipt byte fidelity、
  provider isolation、review-2/merge gates。
- 不删或放松 FX1–FX7 防护。
- 不用修改测试期望掩盖实现缺口；旧行为删除时必须用新合同测试替代。
- 不新增 v2/compatibility/optional parallel/second timeout protocol。
- 不改历史证据和 symlink。

## Evidence And Completion

在 `20-implementation.md` append `T4 Serial-Only v1 Slimming`，逐文件列出
变更、removed/kept contract、测试映射、风险和 git status。在
`60-test-output.txt` append breakdown 的全部 required commands 原始输出。
完成时工作树只允许 exact writable set + 两个 append evidence 文件。

页脚：

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: Codex bookkeeper
下一步任务: 边界/残留/测试复验，创建 evidence commit，准备 Kimi review-1
```
