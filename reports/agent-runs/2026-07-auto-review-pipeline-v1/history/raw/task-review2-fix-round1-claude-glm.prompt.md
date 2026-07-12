<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-fix-round1-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
task:          stage-level review-2 fix round 1 (gpt-5.6-sol BLOCKED: findings F2–F7, all spot-confirmed)
findings_source: reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-gpt-5.6-sol.md (§Findings verbatim authority)
rework_charge: 2 of 3 (second formal charge this stage)
note:          F1 (override evidence form) is a bookkeeper-line item, resolved separately via evidence file v2 (operator declined third-model enablement); P2 (status stale fields) already self-fixed by bookkeeper. This packet covers the six substantive code findings F2–F7.
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Review-2 Fix Round 1 — runner/seal 控制面修复（六项 P1，全部经复现坐实）

你是本 stage 的 fix implementer（Claude-GLM，fresh bounded session）。
review-2 终审（gpt-5.6-sol，BLOCKED）以 temp-repo 反例坐实了六项代码级
P1；bookkeeper 抽验 3/3 成立。findings 原文是修复的**权威依据**：
`50-review-2-gpt-5.6-sol.md` §Findings（逐条行号）与 §Required
disposition。本 packet 只加机械路由，不改写 findings。

不得 dispatch 任何模型；不得 commit。

## Read First

- `reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-gpt-5.6-sol.md`（§Findings/§Required disposition——权威）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/51-review-2-panel-disposition.md`（复现记录）
- `docs/auto-review-pipeline.md`（normative 契约）与
  `workflows/templates/stage-delivery.yaml` `executable_contract`
- `agents/registry.yaml`（**真实命令模板形状**：`<prompt-file>`/`<repo>`）
- `schemas/review-verdict.schema.json`（F5 的对照基准）
- `scripts/auto-review-runner.py` / `scripts/stage-seal.py` 现状
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md` 验收
  3/13/16/17/19/28

前置核对：branch `stage/2026-07-auto-review-pipeline-v1`；status 顶层
`fixing`；`review_2.panel.substantive_findings_confirmed=true`。不符即
append blocker 停止。

## Writable Set（完整清单）

```text
scripts/auto-review-runner.py
scripts/stage-seal.py
scripts/tests/test_auto_review_runner.py
scripts/tests/test_stage_seal.py
```

仅 append：`20-implementation.md`、`60-test-output.txt`。
其余全部只读——特别是 `harness_stage_lib.py`、`validate-stage.py`、全部
T1 契约文件、manifest、status/handoff/review/packet。若修复确需触碰
只读文件，停止并 append blocker（说明路径与原因），不得 fix-forward。

## 修复项（编号对应 sol §Findings 顺序，F1/P2 不在本 packet）

### F2 — authorization 实绑定（sol P1 #2）

runner preflight 必须：①要求 authorization artifact 与 approval receipt
均已 **committed**（git 可达，非仅存在于工作树）；②将授权的
`scope.task_ids`、`topology`、`allowed_pathspecs`、`forbidden_pathspecs`
与 live status 的 tasks/review_units **逐项精确比对**，超出授权集合的
任何单元/路径 → fail-closed；③运行时 call/wall-clock 上限以
**authorization 数值**为准，status 内计数字段仅作累计，不得作为上限来源；
④uncommitted 修改过的 authorization（工作树 dirty 覆盖 committed 版本）
必须拒绝。负测试：sol 反例场景（T1-only 1-call 授权 vs status 含 T2 与
99 calls；dirty forbidden path；uncommitted authorization 修改）逐一
fail-closed。

### F3 — 生产 registry 命令兼容（sol P1 #3）

命令模板替换必须支持真实 registry 形状：`<prompt-file>`、`<repo>`
（保留 `@PROMPT@`/`@REPO@` 向后兼容可以，但真实形状必须工作）；受限
YAML loader 必须正确反转义带引号命令字符串（`\"` 等）。**测试必须直接
加载真实 `agents/registry.yaml`** 断言 claude_glm/kimi/grok 的实际命令
模板经替换后不含任何字面占位符且引号结构正确——不得再用合成
`@PROMPT@` 模板替代生产形状。

### F4 — verdict 校验对齐 schema + 字节保真（sol P1 #4）

runner 内 review-verdict 手写校验（:125-178 区域）必须：拒绝未知顶层
字段（additionalProperties:false 语义）、校验 `required_fixes` 等数组
项类型，与 `schemas/review-verdict.schema.json` 全约束面对齐。
`_store_verdict` 必须保存**被接受的原始字节 span**（从 raw stdout 中
定位的那段字节原样写入），不得 `json.dumps` 重序列化；同步修正其
docstring/注释。负测试：未知字段 verdict 拒收；存盘字节与源 span
逐字节相等（含非常规空白/键序的 fixture）。

### F5 — 单账本联动 + expires_at 每步检查（sol P1 #5）

`_charge_auto_change` 在增 `auto_code_changes_used` 的同时必须递增
顶层 `rework_count`（单账本权威），且断言 `rework_count` ≤ `max_rework`
否则 escalation。`expires_at` 非 null 时必须在**每次 model call 前与
每次 git commit 前**重新检查（验收 28），不只 preflight。负测试：auto
fix 后顶层 rework_count 同步 +1；过期时刻落在 run 中途时下一次
call/commit fail-closed。

### F6 — exclusive lock + H_snapshot 崩溃窗（sol P1 #6）

①实现 runner lock（git 元数据目录下 runtime-only 文件，含
pid/stage/时间戳；已存在活动 lock → preflight fail-closed；退出清理）；
②seal 的 H_snapshot 崩溃窗：commit snapshot **之前**先落
pending-snapshot marker（含 task/base/预期路径集），H_bind 完成后清除;
恢复路径依据 marker 检测真实崩溃点。**崩溃测试必须在真实执行流中注入
崩溃**（monkeypatch 使 commit 后、status 写前抛异常），不得手工预放
marker 模拟。

### F7 — restart 幂等 + adapter 错误停机（sol P1 #7）

runner 启动时按 runner_state/单元状态恢复：`running` 重启不得重派已
ACCEPT 单元；`completed_review_1` 重启为 no-op（或仅校验）；
implementation/fix adapter 非零退出或超时 → 记 receipt 后**停止该单元
流转**（按 workflow 映射进入 fix 或 escalation），绝不带着失败结果
继续 blocking/seal。负测试：从 running/completed_review_1 重启的
幂等性；adapter 非零退出后 blocking/seal 未被执行。

## Required Checks（append 完整原始输出到 60-test-output.txt）

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" scripts harness-manifest.yaml   # expect exit 1
```

每个 F2–F7 的新负测试单独可跑（报告列出 finding→测试函数映射）。
全量套件必须全绿；无网络、无 live model、stdlib-only 不变。

## Non-Regression

不得破坏：110 个既有测试、TransitionTruthSourceTests、三对 review-1
路由、post-cross-check blocking rerun、seen-diff bind、fingerprint 单一
实现（lib 不可改）、显式路径 git add、receipt 卫生、pilot 谓词。

## Completion Report

`20-implementation.md` 末尾 append `Review-2 Fix Round 1`：F2–F7 逐项
disposition + finding→测试映射 + 修改文件确认在 writable set + 全部
命令原始结果 + `git status --short` + 风险。页脚用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 F2–F7 → re-seal（新指纹）→ Kimi re-review-1（fix 单元）→ 重回 review-2
```
