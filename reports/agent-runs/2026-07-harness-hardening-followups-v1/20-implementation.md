# Implementation

本阶段（stage）`2026-07-harness-hardening-followups-v1` 将
`2026-07-harness-friction-fixes-v1` review-2 留下的 5 项 P2 hardening（加固）
finding（发现项）转为小而可测的 Harness 修复。实现者（implementer）为
`claude_glm`（`zhipu_glm` provider identity）。

## 修改文件列表（Changed Files）

全部落在 `00-task.md` 的 allowed files（允许文件）范围内，无 forbidden path
（禁止路径）被触碰：

```text
scripts/validate-stage.py
scripts/record-checkpoint
scripts/tests/itbm_dry_run.py
scripts/tests/test_validate_stage.py
reports/agent-runs/_template/status.json
workflows/templates/stage-delivery.yaml
reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md
```

未修改 `status.json`、`70-handoff.md`（由 bookkeeper 维护）；未触碰产品代码、
`AGENTS.md`、`agents/registry.yaml`、`schemas/**`、
`reports/agent-runs/2026-07-harness-friction-fixes-v1/**`。

## 5 项 Acceptance Criteria（验收标准）完成状态

### AC1 — `--evidence-out` 写入失败捕获 `OSError`（已完成）

`scripts/validate-stage.py` 的 `compute_diff_fingerprint` 同函数文件内，`main()`
里的 evidence（证据）写入路径原先直接调用 `evidence_path.parent.mkdir(...)` 与
`evidence_path.write_text(output)`。现将其包裹在 `try/except OSError` 中：失败时
向 stderr（标准错误流）打印一行受控 Harness 错误，包含目标路径与系统错误，并以
非零退出码返回，**不暴露 Python traceback（回溯）**。

```text
EVIDENCE WRITE FAILED: could not write <path>: <OSError>
```

注意：该错误在 validation（校验）已通过并打印 `STAGE VALIDATION PASSED` 之后
发生，因此刻意使用独立于 `STAGE VALIDATION FAILED` 的措辞，避免误导调用脚本。

### AC2 — `--dry-run` 缺少 `--single-owner` 时失败（已完成）

`scripts/record-checkpoint` 的 `main()` 在进入 `try` 后、任何分支逻辑之前加入
early guard（前置守卫）：当 `args.dry_run and not args.single_owner` 时抛出
`ItbmError`。该守卫在 double-owner（双所有者）路径的任何 `git` mutation（仓库
变更）之前触发，经由既有 `except ItbmError` 处理输出 `RECORD-CHECKPOINT BLOCKED`
与清晰原因，并以退出码 1 返回。这样用户不会误把 double-owner 写路径当成预览。

### AC3 — `compute_diff_fingerprint` 显式固定 `diff.renames=true`（已完成）

`scripts/validate-stage.py` 的 `compute_diff_fingerprint` 现在显式加上
`-c diff.renames=true`，与 `scripts/_itbm.py` 的 `canonical_fingerprint`
byte-identical（逐字节一致）。因 `diff.renames=true` 本就是 git 默认值，固定它
不会改变任何已记录的 diff_fingerprint（差异指纹），但消除了对用户级或仓库级
`.gitconfig` 的依赖。

### AC4 — 模板支持 `review_1.actual_model`（已完成）

`reports/agent-runs/_template/status.json` 在顶层 `review_1` 块与 `tasks[].review_1`
（任务级）块均新增 `"actual_model": null`，对齐 `review_2.actual_model` 的字段
形态，便于记录 review-1（第一轮审查）的实际执行模型（如 adapter alias（适配器
别名）解析或模型替换）。

同时，`workflows/templates/stage-delivery.yaml` 的 `review-1` preflight（前置
检查）新增一条与 `review-2` 对称的指引：当派发的 review-1 模型与预期不符时，记入
`status.json.review_1.actual_model`，provider identity（提供方身份）不变。这样
该字段成为 workflow（工作流）一等支持、可被记录与审查。

### AC5 — workflow 编码 fix（修复）回归原始 review gate（审查门禁）（已完成）

`workflows/templates/stage-delivery.yaml` 的 `fix` stage（阶段）新增机器可读的
`return_gate` 块：

```yaml
return_gate:
  rule: "a fix must not skip the originating review gate"
  after_fix_from_review_1: review-1
  after_fix_from_review_2: review-2
```

含义：review-1 的 REWORK（返工）→ fix → retest（复测）→ 回到 review-1
redispatch（重新派发）；review-2 的 REWORK → fix → retest → 回到 review-2。
fix 不得跳过其起源 review gate。该规则此前仅以 `policy` 块（F8）叙述表达，现在
以显式 transition（转换）字段编码，便于未来 validator（校验器）或 dispatch
（派发）逻辑机械读取。未删除既有 F8 policy，仅作可机械路由的补充。

## 测试命令与结果

完整原始输出见 `60-test-output.txt`。最低命令集与结果：

```text
[1] python3 scripts/tests/itbm_dry_run.py            -> 19/19 assertions passed, exit 0
[2] python3 -m py_compile scripts/validate-stage.py
        scripts/_itbm.py scripts/record-checkpoint    -> py_compile OK, exit 0
[3] python3 scripts/tests/test_validate_stage.py      -> 19/19 assertions passed, exit 0
[4] python3 scripts/validate-stage.py
        2026-07-harness-hardening-followups-v1
        --phase checkpoint                            -> STAGE VALIDATION PASSED, exit 0
[5] git diff --check                                  -> exit 0（无空白错误）
```

新增/扩展的测试（均通过）：

- **AC2 行为测试**（`scripts/tests/itbm_dry_run.py`，新增 `test_dry_run_requires_single_owner`）：
  以 `--dry-run` 且不带 `--single-owner` 调用 `record-checkpoint`，断言返回
  `RECORD-CHECKPOINT BLOCKED`、消息含 `single-owner`，且 HEAD 与
  `git status --short` 均未变（拒绝时不产生任何 mutation）。
- **AC1 行为测试**（`scripts/tests/test_validate_stage.py`，新增
  `test_evidence_out_write_failure_clean_error`）：令 evidence 路径的父级为普通文件
  触发 `OSError`，断言退出码非零、消息含 evidence 与目标路径、且不含
  `Traceback`。该模拟确定且跨平台（不依赖 chmod/root）。
- **AC3 行为测试**（新增 `test_fingerprint_pins_renames_true`）：构造一个真实
  rename（重命名）的 base..head 区间并设置仓库级 `diff.renames=false`，断言
  `validate-stage.compute_diff_fingerprint` 与 `_itbm.canonical_fingerprint` 在
  该 hostile config（敌对配置）下仍逐字节相等；并以一次 `--no-renames` 风格重算
  断言 rename 策略确实改变 diff（保证测试有意义）。
- **AC4 静态断言**（新增 `test_template_review_1_actual_model`）：加载
  `_template/status.json`，断言顶层与任务级 `review_1` 块均含 `actual_model`。
- **AC5 静态断言**（新增 `test_workflow_fix_return_gate`）：读取
  `stage-delivery.yaml`，断言 `after_fix_from_review_1: review-1` 与
  `after_fix_from_review_2: review-2` 存在。

回归说明：原 F1/F4 测试与 `itbm_dry_run.py` 全部既有断言均保持通过
（itbm 由 17→19，validate 由 9→19，无既有用例被改动语义）。

## 未解决风险与后续建议

- **AC5 仅为文档/约束级编码，非运行时强制**：`return_gate` 是机器可读的 YAML
  字段，但 `validate-stage.py` 尚未读取它做硬校验。这与 design D5「machine-readable
  enough for future validators or dispatch logic」一致，属有意的最小实现；若未来
  需要 fail-closed（失败即关闭）级别的强制，可作为下一个 Harness stage 在
  `validate-stage.py` 增加对 `return_gate` 的校验。本阶段不新增 fingerprint
  protocol（指纹协议），也不扩大 scope（范围）。
- **AC4 未在 `_template` 之外的既有 stage status.json 回填**：仅修改模板。各 stage
  的实际 `status.json` 由各自 bookkeeper 维护，不在本阶段 allowed/职责范围内。
- **AC1/AC2 错误路径用例已覆盖**；未模拟极少数并发文件系统故障（如磁盘满），其
  行为由同一 `except OSError` 分支统一覆盖，错误信息会如实包含系统错误文本。

## 当前 `git status --short`

```text
 M reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md
 M reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
 M reports/agent-runs/_template/status.json
 M scripts/record-checkpoint
 M scripts/tests/itbm_dry_run.py
 M scripts/tests/test_validate_stage.py
 M scripts/validate-stage.py
 M workflows/templates/stage-delivery.yaml
```

当前分支：`stage/2026-07-harness-hardening-followups-v1`。所有改动均未 commit
（本阶段禁止 commit/push/merge/rebase），等待 bookkeeper 检视、提交与预审。

本地北京时间: 2026-07-09 21:28:33 CST
下一步模型: codex_gpt5
下一步任务: bookkeeper inspect implementation, commit delivery, run pre-review validation, and prepare Kimi review-1
