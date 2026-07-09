# Development Breakdown

## Owner Split（所有者分配）

| 角色 | 模型 | Provider Identity |
|------|------|-------------------|
| 实现者 (Implementer) | Claude-GLM (`glm-5.2`) | `zhipu_glm` |
| Review-1 审阅者 | Kimi (`kimi-2.7`) | `moonshot_kimi` |
| Review-2 终审 | Codex/GPT（首选），Claude（回退） | `openai` / `anthropic` |
| Bookkeeper（记账/调度） | Codex/GPT-5 | `openai` |
| Breakdown 作者 | Claude（本文档） | `anthropic` |

**任务划分决定**: 单任务交付（single atomic task）。全部 9 个摩擦点均为
Harness 脚本/模板/文档修改，无产品代码改动，工作量适中且高度内聚，拆分
子任务反而增加协调开销。Claude-GLM 为单一实现者。

## Allowed Files（允许修改的文件）

```text
scripts/validate-stage.py
scripts/record-checkpoint
scripts/_itbm.py
scripts/tests/itbm_dry_run.py
scripts/tests/test_validate_stage.py        # 新建
reports/agent-runs/_template/status.json
workflows/templates/stage-delivery.yaml
docs/independent-task-branch-mode.md
docs/model-adapters.md
reports/agent-runs/README.md
agents/skills/stage_operator.md             # 如已存在则修改报告语言段落
reports/agent-runs/2026-07-harness-friction-fixes-v1/**
```

## Forbidden Files（禁止修改的文件）

```text
backend/**
frontend/**
docs/product/**
docs/architecture/**
reports/api-samples/**
AGENTS.md                    # 除非必须修改 hard gate 或权限级规则
agents/registry.yaml         # 除非添加 reporting_preferences 路由键
schemas/**                   # 本阶段不新增 schema
prototypes/**
.env / .env.example
```

---

## 逐项实现要求

### F1: Unselected review-2 preferred provider 不触发 designer-overlap

**问题根因**: `validate-stage.py` 的 `review_provider_identity()` 函数（L333–338）
按 `reviewer → provider → selected_provider → primary_provider` 顺序探测
identity。模板 `_template/status.json` 的 `review_2.primary_provider` 默认值为
`"codex"`，而 `reviewer/provider/selected_provider` 均为 `null`。当 designer 也是
`codex`（如本阶段由 Codex 设计），验证器在 `pre-review` 阶段就会将未选定的偏好
误判为已选定的审阅者 identity，产生 false positive designer-overlap 错误。

**修复方案**:

1. 在 `review_provider_identity()` 中引入 **selected-vs-preferred 区分**：
   - 新增一个辅助函数 `review_selected_identity(review)` ，只探测
     `reviewer / provider / selected_provider`（即已确认选定的审阅者字段），
     不探测 `primary_provider`。
   - `validate_review_identity()` 在执行 designer-overlap 和 implementer-overlap
     检查时使用 `review_selected_identity()` 而非 `review_provider_identity()`。
   - 保留 `review_provider_identity()` 原函数签名不变，仅在
     pre-accept 阶段需要验证已完成 review 的全字段时使用。
2. 在模板 `_template/status.json` 中将 `review_2.primary_provider` 重命名或
   标注为 preference，不改默认值 `"codex"`，但确保验证器不再将其作为 identity
   来源用于 isolation 检查。

**验收条件**:
- `review_2.reviewer=null, provider=null, primary_provider="codex"` +
  `designer.provider="codex"` → 验证器 pre-review 不报 designer-overlap。
- `review_2.reviewer="codex"` (已选定) + `designer.provider="codex"` →
  验证器仍要求 `reviewer_prior_involvement` + `fallback_reason` + evidence file。

### F2: Single-owner validator evidence 必须在 reviewed range 内

**问题根因**: 上一阶段的 dispatch packet 在 step 4 锚定 fingerprint（anchor
`head_sha`），step 6 才运行 `validate-stage.py` 并提交证据到
`61-validate-pre-review.txt`。验证器证据落在 `head_sha` 之后，review-1 看不到它，
导致 Kimi REWORK。

**修复方案**:

1. 更新 `workflows/templates/stage-delivery.yaml` 的 single-owner dispatch
   步骤模板：validator evidence 必须在 fingerprint anchor 之前提交，或在 evidence
   提交后重新计算 `head_sha` / `diff_fingerprint`。
2. 在 `docs/independent-task-branch-mode.md` 中添加 **"evidence-before-anchor"
   规则**文档段落。
3. 在 `reports/agent-runs/README.md` 中补充操作说明。

**验收条件**:
- dispatch 模板步骤顺序确保 `61-validate-pre-review.txt` 在
  `base_sha..head_sha` 范围内。

### F3: `record-checkpoint --single-owner` 写入 status.json review 元数据

**问题根因**: 当前 `run_single_owner()` (L56–69) 仅执行
`git add -A` + `git commit` + 打印 fingerprint，不写 `status.json` 的
`base_sha`、`head_sha`、`diff_fingerprint`、`changed_files`。实际操作中 GLM
需要手动转录这些值。

**修复方案**:

1. `record-checkpoint --single-owner` 在 commit 后：
   - 读取 `status.json`。
   - 写入 `base_sha`、`head_sha`、`diff_fingerprint`、`changed_files`。
   - 再做一次 status-only commit（因为 `status.json` 被 fingerprint 排除，
     不影响 canonical fingerprint）。
2. 打印写入的字段供操作者确认。
3. 添加 `--dry-run` 标志：只打印不写入（保持当前行为作为兼容选项）。

**验收条件**:
- 运行 `record-checkpoint --single-owner` 后 `status.json` 包含正确的
  `base_sha`、`head_sha`、`diff_fingerprint`。
- `--dry-run` 模式只打印不修改文件。
- 不引入第二种 fingerprint protocol。

### F4: Validator evidence capture 不污染 worktree

**问题根因**: `validate-stage.py --phase pre-review` 需要 clean worktree，但
操作者通常用 `| tee reports/.../61-validate-pre-review.txt` 捕获输出，这会在
clean-worktree check 之前或之后弄脏工作树。

**修复方案**:

1. 为 `validate-stage.py` 添加 `--evidence-out <path>` 参数：
   - 先执行全部验证（包括 clean-worktree check）。
   - 全部通过后，将验证输出写入指定路径。
   - 失败时不写文件（避免掩盖真正的 dirty-worktree 错误）。
2. 验证运行顺序：先 check clean worktree → 运行所有验证 → 如果全部 PASS
   → 写 evidence file → 返回 exit 0。

**验收条件**:
- `--evidence-out` 写入的文件内容与 stdout 输出相同。
- dirty-worktree 失败时 `--evidence-out` 不创建文件。
- 不指定 `--evidence-out` 时行为不变。

### F5: Delivery-anchored `head_sha` 和 validator fixed-point 文档

**问题根因**: review-1 和 review-2 都对以下两个语义产生 P2/P3 findings：
- `head_sha` 锚定在交付提交（delivery commit），后续的 review 证据提交不修改
  `head_sha`。
- 验证器日志中记录的 fingerprint 是日志被提交之前的 HEAD，不是包含日志的
  提交的 fingerprint（fixed-point property，即自指不可能性）。

**修复方案**:

1. 在 `docs/independent-task-branch-mode.md` 中新增一个 section
   "Evidence Conventions（证据约定）"：
   - 明确 delivery-anchored `head_sha` 语义。
   - 明确 validator fixed-point property。
   - 说明 `status.json` 的 `diff_fingerprint` 是权威值，日志 fingerprint
     是 pre-inclusion 快照。
2. 在 `reports/agent-runs/README.md` 中添加简要交叉引用。
3. 在 `workflows/templates/stage-delivery.yaml` 的 review 步骤注释中添加引用。

**验收条件**:
- 文档存在且被 README 引用。
- 未引入新的 fingerprint protocol 或状态值。

### F6: Claude fallback model 记录

**问题根因**: dispatch 时指定 Fable5，但实际使用 Opus 4.8（因 Fable5 quota
耗尽）。`status.json` 和 handoff 中需要手动说明偏差。

**修复方案**:

1. 在 `_template/status.json` 的 `review_2` 部分新增字段
   `"actual_model": null`，用于记录实际执行的模型。
2. 在 `docs/model-adapters.md` 中明确记录：如果 Fable5 不可用，配置的回退
   模型是 `claude-opus-4-8`（已有内容需核实完整性）。
3. 在 `workflows/templates/stage-delivery.yaml` 的 review-2 节点增加
   `actual_model` 记录要求。

**验收条件**:
- `status.json` 模板和文档支持记录实际使用的模型。
- 不改变 provider identity 规则。

### F7: Review output hygiene（审阅输出卫生）

**问题根因**: Kimi review-1 输出包含适配器噪声（adapter stderr/metadata）。

**修复方案**:

1. 在 `docs/model-adapters.md` 中为 Kimi 记录推荐的输出清理方法（如
   stderr 重定向）。
2. 如果 `stage-delivery.yaml` 的 review 步骤有输出处理指引，补充 stderr
   分离建议。
3. 不在本阶段新建适配器基础设施。

**验收条件**:
- 文档化的清理方法存在。
- 未引入新的适配器脚本。

### F8: `fix_start_prompt.next_action` 指向真正的下一步

**问题根因**: REWORK 后生成的 `fix_start_prompt` 的 `next_action` 直接跳到
review-2，实际上应先重跑 review-1。

**修复方案**:

1. 在 `workflows/templates/stage-delivery.yaml` 的 review-1 REWORK 分支中，
   明确 `next_action` 模板为 `"redispatch review-1 after fix"`（而非跳到
   review-2）。
2. 在 fix dispatch 模板中要求 `fix_start_prompt.next_action` 与当前 review
   阶段匹配：review-1 REWORK → fix → review-1 redispatch；review-2
   REWORK → fix → review-2 redispatch。

**验收条件**:
- workflow YAML 和模板中 REWORK 分支的 `next_action` 与实际流程一致。

### F9: Reporting language preference（报告语言偏好）

**问题根因**: 用户请求 Harness 报告默认用中文，同时保留命令、路径、JSON key、
schema field、代码标识、model name、provider identity 的英文原文，必要英文术语
首次出现时附中文释义。

**修复方案**:

1. 在 `_template/status.json` 中新增 `reporting_preferences` 对象：
   ```json
   "reporting_preferences": {
     "primary_language": null,
     "explain_english_terms": false,
     "preserve_exact_strings": [
       "commands", "file_paths", "json_keys", "schema_fields",
       "code_identifiers", "model_names", "provider_identifiers"
     ]
   }
   ```
2. 在 `workflows/templates/stage-delivery.yaml` 的 dispatch 模板中增加
   reporting preference 段，dispatch prompt 可读取 `status.json` 的
   `reporting_preferences` 并在 prompt header 中注入语言指令。
3. 在 `docs/model-adapters.md` 或 `reports/agent-runs/README.md` 中
   新增 "报告语言" 段落，包含示例：
   - `fingerprint（指纹，用于绑定被审 diff 的哈希）`
   - `delivery-anchored head_sha（交付锚定的 head_sha，即 head_sha 锚定在
     代码交付提交而非后续辅助提交）`
4. 本阶段 `status.json` 已有 `reporting_preferences`（由 bookkeeper 添加），
   实现时需确保模板同步。

**验收条件**:
- 模板 `status.json` 包含 `reporting_preferences` 对象。
- 至少一处 dispatch 模板引用该偏好。
- 示例文档展示中英混排的正确用法。
- 不翻译 JSON key、命令、路径、代码标识。

---

## Test Plan（测试计划）

### 新增测试

| 测试文件 | 用例 | 验证目标 |
|----------|------|----------|
| `scripts/tests/test_validate_stage.py` | `test_unselected_primary_provider_no_designer_overlap` | F1: `review_2.primary_provider="codex"` + `reviewer=null` + `designer=codex` → 不报错 |
| 同上 | `test_selected_reviewer_enforces_overlap` | F1: `review_2.reviewer="codex"` + `designer=codex` → 报 designer-overlap |
| 同上 | `test_selected_reviewer_implementer_ban` | F1: `review_2.reviewer="kimi"` + implementer=kimi → 报 implementer-overlap（hard ban） |
| 同上 | `test_evidence_out_on_pass` | F4: `--evidence-out` 写入文件 |
| 同上 | `test_evidence_out_on_fail` | F4: 失败时不创建 evidence 文件 |
| `scripts/tests/itbm_dry_run.py` | 扩展 `test_single_owner` | F3: 运行后验证 `status.json` 包含 `base_sha`、`head_sha`、`diff_fingerprint` |

### 回归测试

```bash
# 现有测试必须通过
python3 scripts/tests/itbm_dry_run.py

# 语法检查
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py

# 新增验证器测试
python3 scripts/tests/test_validate_stage.py

# 本阶段 pre-review 验证
python3 scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase pre-review
```

### Test Evidence 路径

```text
reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
reports/agent-runs/2026-07-harness-friction-fixes-v1/61-validate-pre-review.txt
```

---

## Review Focus（审阅重点）

### Kimi Review-1

1. **F1 Identity 逻辑正确性**: `review_selected_identity()` vs
   `review_provider_identity()` 的调用边界是否准确——只有 pre-accept
   和已完成 review 的验证才使用全字段探测。
2. **F3 Status 写入安全**: `record-checkpoint --single-owner` 写 `status.json`
   后的 status-only commit 是否不影响 canonical fingerprint。
3. **F4 `--evidence-out` 时序**: evidence file 是否仅在全部验证通过后才写入。
4. **F9 Language 边界**: `reporting_preferences` 是否仅影响 prompt/dispatch
   文本，不影响 JSON verdict、schema key、命令。
5. **回归风险**: 现有 `itbm_dry_run.py` 13 assertions 是否全部通过；
   新测试是否覆盖 F1 的 positive 和 negative 路径。

### Review-2 Final（终审）

1. **Hard gate 完整性**: 修改 `validate-stage.py` identity 逻辑后，
   implementer-overlap hard ban 是否仍然无 override。
2. **Fingerprint protocol 不变性**: 未引入第二种 fingerprint protocol。
3. **模板 `status.json` 兼容性**: 新增字段（`actual_model`、
   `reporting_preferences`）是否与现有阶段的 `status.json` 兼容（旧阶段
   缺失字段时验证器不崩溃）。
4. **文档与代码一致性**: `docs/independent-task-branch-mode.md` 和
   `stage-delivery.yaml` 中的步骤顺序是否与脚本行为匹配。
5. **designer-overlap 检查**: review-2 本身如果有 designer-overlap
   （Codex 设计 + Codex 终审），是否正确要求 disclosure override。

---

## Non-Goals（非目标）

- 不修改产品运行时行为（`backend/**`、`frontend/**`）。
- 不替换整个 Harness 状态机。
- 不引入第二种 fingerprint protocol。
- 不更改 provider identity 规则（`claude_glm` 仍为 `zhipu_glm`）。
- 不翻译机器可读的 JSON key、命令、文件路径、代码标识。
- 不新建适配器脚本或新 schema 文件。
- 不修改 `AGENTS.md` 除非发现 hard gate 级别的规则冲突。

## Rollback / REWORK Triggers（回滚/返工触发条件）

1. `itbm_dry_run.py` 任一 assertion 失败。
2. `py_compile` 失败。
3. `validate-stage.py --phase pre-review` 本阶段未通过。
4. 新增测试中 F1 positive case（应通过但未通过）或 negative case（应失败但通过）
   结果不符。
5. 修改 `review_provider_identity()` 导致 pre-accept 阶段的已完成 review
   identity 检查缺失。
6. 修改 `record-checkpoint --single-owner` 引入自指 fingerprint
   （status.json 内容进入 fingerprint 计算）。

---

## Risk Points（风险点）

| 风险 | 缓解 |
|------|------|
| F1 修改过度放松导致自审 | 测试覆盖 positive + negative；review-1 重点检查 |
| F3 `status.json` 写入引入自指 fingerprint | `status.json` 在 fingerprint 排除列表中（`_itbm.py` `canonical_fingerprint` 的 `:(exclude)` pathspec） |
| F4 `--evidence-out` 掩盖 dirty-worktree | 仅 PASS 时写文件；FAIL 时不写 |
| F9 language preference 污染 JSON verdict | `reporting_preferences` 仅影响 narrative prompt，不进入 verdict schema |
| 模板新增字段导致旧阶段验证器崩溃 | 验证器使用 `.get()` 访问，缺失字段返回 `None`，不崩溃 |

---

## API/Data Contracts（接口/数据契约）

### `status.json` 新增字段

```json
{
  "review_2": {
    "actual_model": null
  },
  "reporting_preferences": {
    "primary_language": null,
    "explain_english_terms": false,
    "preserve_exact_strings": [
      "commands", "file_paths", "json_keys", "schema_fields",
      "code_identifiers", "model_names", "provider_identifiers"
    ]
  }
}
```

### `validate-stage.py` 新增参数

```text
--evidence-out <path>    # 全部 PASS 后写入验证输出到指定路径
```

### `record-checkpoint` 变更

```text
--single-owner           # 现在会写 status.json review 元数据
--single-owner --dry-run # 只打印不写入（兼容旧行为）
```

---

本地北京时间: 2026-07-09 14:50:57 CST
下一步模型: human
下一步任务: 审阅本 breakdown，然后 dispatch 实现任务给 Claude-GLM
