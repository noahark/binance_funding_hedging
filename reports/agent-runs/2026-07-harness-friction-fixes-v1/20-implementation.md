# Implementation Report — 2026-07-harness-friction-fixes-v1

- 实现者 (Implementer): Claude-GLM (`glm-5.2`), provider identity `zhipu_glm`
- 任务边界: 按 `12-development-breakdown.md` 实现 F1-F9（单原子任务，
  Harness 脚本/模板/文档修改，无产品代码改动）
- 测试证据: `reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt`

本报告按 `status.json.reporting_preferences`（reporting language preference，
报告语言偏好）以中文为主撰写；命令、路径、JSON key、schema field、代码标识、
model name、provider identity 保留英文原文，必要英文术语首次出现附中文释义。

## 修改文件列表 (Modified files)

| 文件 | 摩擦点 | 说明 |
|---|---|---|
| `scripts/validate-stage.py` | F1, F4 | 新增 `review_selected_identity()`；`validate_review_identity()` 改用它做 isolation 检查；新增 `--evidence-out` |
| `scripts/record-checkpoint` | F3 | `run_single_owner()` 写 top-level `status.json` review 元数据 + status-only commit；新增 `--dry-run` |
| `scripts/tests/test_validate_stage.py` | F1, F4 | 新建：F1 三个 isolation 用例 + F4 两个 evidence-out 用例（共 9 断言） |
| `scripts/tests/itbm_dry_run.py` | F3 | 扩展 `test_single_owner` 验证 status 字段；新增 `test_single_owner_dry_run` 并在 REWORK 中加强为 3 条断言（13 → 15 → 17） |
| `reports/agent-runs/_template/status.json` | F6, F9 | `review_2` 新增 `actual_model`；顶层新增 `reporting_preferences` |
| `workflows/templates/stage-delivery.yaml` | F2, F5, F6, F7, F8, F9 | review-1/review-2 preflight 增证据捕获与卫生说明；两处 `fix_start_prompt` 增 `next_action`；policy 增 F8 规则；末尾新增 `single_owner_mode` 与 `reporting` 块 |
| `docs/independent-task-branch-mode.md` | F2, F5 | 新增 "Single-owner recorder"（含 evidence-before-anchor 排序）与 "Evidence Conventions" 段；断言计数 13 → 15 → 17 |
| `docs/model-adapters.md` | F6, F7 | Claude 段增 `actual_model` 记录约定；Kimi 段增 "Review output hygiene"（stderr 分离） |
| `reports/agent-runs/README.md` | F2, F5, F9 | Evidence Rules 增 delivery-anchored `head_sha` / fixed-point / `--evidence-out` / single-owner 排序条目；新增 "报告语言偏好" 段 |

所有改动均在 `00-task.md` / `12-development-breakdown.md` 的 allowed files 内，
未触碰 `backend/**`、`frontend/**`、`docs/product/**`、`docs/architecture/**`、
`reports/api-samples/**`、`AGENTS.md`、`agents/registry.yaml`、`schemas/**`、
`prototypes/**`、`.env*`。`agents/skills/stage_operator.md` 不存在，按任务要求
（"仅当已存在时修改；不要新建"）未创建。

## F1-F9 完成状态

### F1 — Unselected review-2 preferred provider 不触发 designer-overlap ✅
- 新增 `review_selected_identity(review)`：只探测 `reviewer / provider /
  selected_provider`，**不**探测 `primary_provider`（primary_provider 只是未选定
  的偏好/preference，不是已选定的审阅者 identity）。
- `validate_review_identity()` 的 review-1 implementer-overlap、review-2
  implementer-overlap（hard ban，无 override）、review-2 designer-overlap（需
  disclosure override）全部改用 `review_selected_identity()`。
- `review_provider_identity()` 原签名保留，仍被 `validate_tasks()` 用于 task 级
  review identity 探测（非死代码）。
- 覆盖测试（`test_validate_stage.py`）：
  - 未选定 `primary_provider="codex"` + `designer=codex` → 不报 designer-overlap；
  - 已选定 `reviewer="codex"` + `designer=codex` → 报 designer-overlap disclosure；
  - 已选定 `reviewer="kimi"` + implementer=kimi → 报 hard ban（no override）；
  - 已选定 `reviewer="kimi"`（与 designer/implementer 均无关）→ 干净通过。

### F2 — Single-owner validator evidence 必须在 reviewed range 内 ✅（文档+脚本）
- 根因分析：上一 stage 的 review-1 P2/P3 findings 显示，validator evidence
  （`61-validate-pre-review.txt`）与后续 handoff commit 落在锚定的 `head_sha`
  之后，且 validator 日志记录的是 pre-inclusion（纳入前）fingerprint。
- `stage-delivery.yaml` 新增 `single_owner_mode.evidence_ordering`，给出两条等价
  路径：**evidence-before-anchor**（提交证据后再锚定 `head_sha`，借助 F4 的
  `--evidence-out`）或 **reconcile-after**（先锚定、提交证据后重算
  `head_sha`/`diff_fingerprint`，重跑 `record-checkpoint --single-owner` 即重新锚定）。
- `docs/independent-task-branch-mode.md` 新增 "Single-owner recorder" 段含可执行
  命令序列；`reports/agent-runs/README.md` 增操作条目。
- 验收：dispatch 模板步骤顺序已确保 `61-validate-pre-review.txt` 在
  `base_sha..head_sha` 范围内或被安全 reconcile。

### F3 — `record-checkpoint --single-owner` 写 status.json review 元数据 ✅
- `run_single_owner()` 在 commit 后写入 top-level `status.json` 的 `base_sha`、
  `head_sha`、`diff_fingerprint`、`changed_files`，再做一次 status-only commit。
- `status.json` 在 canonical fingerprint 的 `:(exclude)` pathspec 中
  （`_itbm.py` `canonical_fingerprint`），故 status-only commit **不**改变
  `diff_fingerprint`，不引入自指 fingerprint（self-referential fingerprint）。
- 新增 `--dry-run`：**零仓库修改（no repository mutation）**——不执行 `git add`、
  不执行 `git commit`、不写 `status.json`、不改变 `HEAD`/index/worktree。它读取当前
  branch tip 并打印基于已提交状态计算的 status 字段，作为无副作用的预览（因此不反映
  未提交的 pending 改动；非 dry-run 路径会先提交 pending）。详见下方 "REWORK 修复
  （F3 dry-run 语义）"。
- `_has_staged_changes()` 让重新锚定（worktree 已干净时）不会因空 content commit
  失败，从而支持 F2 的 reconcile-after 路径。
- 测试：`itbm_dry_run.py` 的 `test_single_owner` 验证 status 字段写入，
  `test_single_owner_dry_run` 断言 HEAD、`git status --short`、`status.json` metadata
  三者在 dry-run 后均不变（17/17 通过）。

### F4 — Validator evidence capture 不污染 worktree ✅
- `validate-stage.py` 新增 `--evidence-out <path>`：先执行全部验证（含
  clean-worktree check），**全部 PASS 后**才把与 stdout 相同的输出写入指定路径；
  FAIL 时不创建文件（避免掩盖真正的 dirty-worktree 失败）。
- 时序：clean-worktree check → 全部验证 → 若 PASS → 写 evidence file → exit 0。
- 这让操作者可用 `validate-stage.py --phase pre-review --evidence-out <path>`
  取代 `... | tee <path>`，避免 `tee` 在 clean-worktree check 之前/之后弄脏工作树。
- 测试：`test_validate_stage.py` 的 `test_evidence_out_on_pass` /
  `test_evidence_out_on_fail`（9/9 通过）。

### F5 — Delivery-anchored `head_sha` 与 validator fixed-point 文档 ✅
- `docs/independent-task-branch-mode.md` 新增 "Evidence Conventions" 段：
  - delivery-anchored `head_sha`：`head_sha` 锚定交付提交，后续辅助提交（status
    metadata、handoff、evidence re-anchor）不移动 `head_sha`，除非显式重新锚定
    并重跑 validator；
  - validator fixed-point property（验证器日志自指不动点性质）：提交进仓库的日志
    不可能包含包含它自身的 commit 的 fingerprint，故日志记录 pre-inclusion 快照，
    `status.json.diff_fingerprint` 为权威值。
- `reports/agent-runs/README.md` 增交叉引用条目；`stage-delivery.yaml` review-1/
  review-2 preflight 引用该约定。未引入新 fingerprint protocol 或状态值。

### F6 — 记录实际 Claude fallback model ✅
- `_template/status.json` 的 `review_2` 新增 `"actual_model": null`，记录实际执行
  的模型（例如 dispatch 预期 `claude-fable-5`，实际跑 `claude-opus-4-8`）。
- `docs/model-adapters.md` Claude 段明确：Fable5 不可用时回退 `claude-opus-4-8`，
  并要求把实际模型记入 `status.json.review_2.actual_model`。
- `stage-delivery.yaml` review-2 preflight 增 `actual_model` 记录要求。
- 不改变 provider identity 规则（`claude-fable-5` 与 `claude-opus-4-8` 同为
  `anthropic`），anti-self-review isolation 不变。

### F7 — Review output hygiene（审阅输出卫生）✅（文档）
- `docs/model-adapters.md` Kimi 段新增 "Review output hygiene"：Kimi 一次性 prompt
  模式会把适配器噪声输出到 stderr，建议捕获 review 输出时分离 stderr（如
  `2>...stderr.log | tee 30-review-1.md`），stderr 留作调试但不混入 strict JSON
  verdict 区。
- `stage-delivery.yaml` review-1 preflight 引用该卫生约定。
- 未新建适配器脚本（符合 non-goal）。

### F8 — `fix_start_prompt.next_action` 指向真正的下一步 ✅
- `stage-delivery.yaml` review-1 与 review-2 的 `fix_start_prompt.must_include` 各
  新增 `next_action`：review-1 REWORK → fix → retest → **redispatch review-1**
  （不直接跳 review-2）；review-2 REWORK → fix → retest → redispatch review-2。
- `policy` 段新增 `review_1_rework_redispatches_review_1_not_review_2: true` 与
  `fix_start_prompt_next_action_matches_originating_review: true`。

### F9 — Reporting language preference（报告语言偏好）✅
- `_template/status.json` 顶层新增 `reporting_preferences`（`primary_language`、
  `explain_english_terms`、`preserve_exact_strings`）；本 stage 的 `status.json`
  已由 bookkeeper 设置该偏好，模板现已同步。
- `stage-delivery.yaml` 新增 `reporting` 块：dispatch prompt 读取
  `status.json.reporting_preferences` 注入语言指令；仅影响 narrative prompt，
  不进入 verdict schema / JSON key / 命令 / 路径 / 代码标识。
- `reports/agent-runs/README.md` 新增 "报告语言偏好" 段含中英混排示例
  （`fingerprint`、`delivery-anchored head_sha`、`provider identity`、
  `fix_start_prompt`）。

## 测试命令与结果

原始输出见 `60-test-output.txt`。

```bash
python3 scripts/tests/itbm_dry_run.py                              # 17/17 PASSED
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py   # exit 0
python3 scripts/tests/test_validate_stage.py                       # 9/9 PASSED
python3 scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase checkpoint  # STAGE VALIDATION PASSED
```

- `itbm_dry_run.py`：13 → 15 → 17 断言。新增 single-owner status 写入用例；REWORK
  后把 `test_single_owner_dry_run` 加强为 3 条断言——dry-run 后 `HEAD` 不变、
  `git status --short` 不变、`status.json` 的 `base_sha`/`head_sha` 不被写入，
  直接锁定 P1 修复的零仓库修改语义。全部既有 fail-closed gate 仍通过。
- `test_validate_stage.py`（新建）：F1 三个 isolation 用例 + F4 两个 evidence-out
  用例（含一个 "选定无关 reviewer 干净通过" 的正向用例），9/9 通过。
- `validate-stage.py --phase checkpoint` 本阶段通过（status=`implementing`，
  stage_branch 校验通过）。

## 关键设计决策与取舍

1. **F2 的 fixed-point 现实**：提交进仓库的 validator 日志不可能包含包含它自身的
   commit 的 fingerprint（自指不可能）。因此 "日志 fingerprint == 最终 head 的
   fingerprint" 在数学上不可达。采取的方案是：用 F4 的 `--evidence-out` 干净捕获
   证据，并要求 `61-validate-pre-review.txt` 落入 reviewed range（evidence-before-anchor
   或 reconcile-after），同时用 F5 把 "日志为 pre-inclusion 快照、status.json 为权威"
   明确文档化——这正是上一 stage Kimi review-1 的 P3 finding 所需的澄清。
2. **F1 保留 `review_provider_identity()`**：仅在 isolation/overlap 检查改用
   `review_selected_identity()`（排除 `primary_provider`）；`review_provider_identity()`
   原签名保留并仍用于 `validate_tasks()` 的 task 级 review identity，避免删除造成
   更大改动（surgical changes）。
3. **F3 `--dry-run` 语义（REWORK 修正后）**：dry-run 为真正的只读预览——不执行
   `git add`、不执行 `git commit`、不写 `status.json`、不改变 `HEAD`/index/worktree
   （详见下方 "REWORK 修复（F3 dry-run 语义）"）。初版错误地在 `args.dry_run` 检查
   之前调用了 `git add -A` 与可能的 content commit，使 dry-run 虽不写 `status.json`
   却仍移动了 `HEAD` 与 index；记账员的检视（`21-bookkeeper-inspection.md`）将其
   标为 P1 并发起 REWORK。修正方案是把 dry-run 分支提前到 `run_single_owner()` 的
   任何变更操作之前，并把受保护路径检查提取为只读的 `_guard_protected_pending()`
   守卫（只读 `git status`，对 dry-run 路径安全）。
4. **本 stage 自身不使用 single-owner recorder**：本 stage 修改 `scripts/`、
   `workflows/`、`docs/model-adapters.md` 等 protected Harness path，而
   `record-checkpoint --single-owner` 对 protected path 硬禁止（适用于产品任务）。
   因此本 stage 的 checkpoint/commit 由 bookkeeper 按常规方式完成，F3 的能力通过
   `itbm_dry_run.py`（产品路径 fixture）验证。这是预期行为，非缺陷。

## REWORK 修复（F3 dry-run 语义）

记账员在 review-1 前的检视（`21-bookkeeper-inspection.md`）发现 P1：F3 初版的
`record-checkpoint --single-owner --dry-run` 虽然跳过了写 `status.json`，但仍会
修改存储库——`run_single_owner()` 在检查 `args.dry_run` 之前就调用了
`git add -A` 并可能在 `_has_staged_changes` 为真时做 content commit，导致 dry-run
仍移动 `HEAD` 与 index。这违反 F3 验收标准 "`--dry-run` 模式仅打印，不修改文件"。

- **根因**：dry-run 分支位于变更操作之后，先 mutate、再 short-circuit，mutate 已发生。
- **修正**（`scripts/record-checkpoint` `run_single_owner()`）：
  1. 任何变更操作之前先解析 `base`，再调用只读守卫 `_guard_protected_pending()`
     （仅读 `git status`，对 dry-run 安全，受保护路径命中即 raise）；
  2. 紧接着处理 `args.dry_run`：读取当前 branch tip，打印将写入的 `base_sha` /
     `head_sha` / `diff_fingerprint` / `changed_files`，然后 `return 0`——
     全程不执行 `git add` / `git commit`、不写 `status.json`、不动 `HEAD`/index/worktree；
  3. 非变更路径（提交 pending → 锚定 `head_sha` → 写 top-level `status.json` →
     status-only commit）逻辑保持不变，置于 dry-run 分支之后。
- **测试加强**（`scripts/tests/itbm_dry_run.py` `test_single_owner_dry_run`）：
  原 1 条断言（returncode==0）加强为 3 条——dry-run 前后 `HEAD` 不变、
  `git status --short` 不变、`status.json` 的 `base_sha`/`head_sha` 不被写入。
  断言计数 13 → 15 → 17。
- **文档同步**：`docs/independent-task-branch-mode.md`、`reports/agent-runs/README.md`、
  `workflows/templates/stage-delivery.yaml` 的 dry-run 描述统一改为 "no repository
  mutation / 无仓库修改"（删除旧的 "提交 pending + 打印 fingerprint" 兼容表述）。
- **影响面**：仅 `scripts/record-checkpoint` 与其 dry-run 文档表述；非 dry-run 路径
  行为不变；不触碰产品代码、不新增 fingerprint protocol、不改 provider identity 规则。

## 未解决风险 / 后续建议

1. **F8 `next_action` 为契约文档，尚无机器校验**：`validate-stage.py` 当前不校验
   review verdict 中 `fix_start_prompt.next_action` 的内容是否与来源 review 阶段一致。
   可作为后续 gate（读取 `30-review-1.md` / `50-review-2.md` 的 verdict JSON 校验
   next_action 文本），但本阶段未新增 schema，遵循 non-goal。
2. **`single_owner_mode` / `reporting` 为 YAML 意图层**：未新增 status 值或 fingerprint
   protocol（遵循 non-goal）；其字段不被 `validate-stage.py` 解析，属 intent/routing。
3. **`--evidence-out` 路径父目录**：实现中 `mkdir(parents=True, exist_ok=True)` 以容忍
   操作者指定新文件名；仅在 PASS 时写入。
4. **dispatch receipt**：`implementation-claude-glm.prompt.md` 顶部的 DISPATCH RECEIPT
   （`started_at`/`completed_at`/`session_id`）按 "bookkeeper 稍后补证据" 约定留给
   bookkeeper 填写；PROMPT BODY 未改动。
5. **reporting_preferences 的强制力**：当前仅靠 prompt/文档约定生效；若需更强保证，
   后续可在 dispatch 模板生成器中机械注入（本阶段不新增适配器基础设施）。

## 当前 git status --short

实现者交付（implementer deliverables）：

```text
 M docs/independent-task-branch-mode.md
 M docs/model-adapters.md
 M reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md
 M reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
 M reports/agent-runs/README.md
 M reports/agent-runs/_template/status.json
 M scripts/record-checkpoint
 M scripts/tests/itbm_dry_run.py
 M scripts/validate-stage.py
 M workflows/templates/stage-delivery.yaml
?? scripts/tests/test_validate_stage.py
```

记账员自有文件（bookkeeper-owned，本实现者未改动，列出仅供对照真实工作树）：

```text
 M reports/agent-runs/2026-07-harness-friction-fixes-v1/70-handoff.md
 M reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json
?? reports/agent-runs/2026-07-harness-friction-fixes-v1/21-bookkeeper-inspection.md
?? reports/agent-runs/2026-07-harness-friction-fixes-v1/implementation-fix-claude-glm.prompt.md
```

实现者交付物未 commit（按任务要求 "不要 commit"），等待 bookkeeper 重新检视后做
delivery commit。`status.json` 与 `70-handoff.md` 由 bookkeeper 维护，不在本实现者
交付范围内。

本地北京时间: 2026-07-09 18:04:29 CST
下一步模型: codex_gpt5
下一步任务: bookkeeper re-inspect implementation and prepare delivery commit if clean
