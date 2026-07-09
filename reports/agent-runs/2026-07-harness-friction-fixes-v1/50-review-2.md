# Review-2: `2026-07-harness-friction-fixes-v1`

审阅者（reviewer）：Claude/Anthropic（`anthropic` provider identity）
实际执行模型（actual model）：`claude-opus-4-6`（用户选定）
角色（role）：`final_reviewer`
先前参与度披露（prior involvement）：`breakdown`（Anthropic/Claude 编写了 `12-development-breakdown.md`（开发拆解文档），但未参与本阶段实现或修复；参见 strong-reviewer disclosure override（强审阅者披露覆盖）说明）

---

## 一、指纹与范围核验

| 检查项 | 结果 |
|--------|------|
| `base_sha` | `4b98bf3d09f3aacee7e6ffdb9a2353e246af7e41` ✅ |
| `head_sha` | `b051e7c7c93b28ff40b3d94e46413ea9742834a7` ✅ |
| `diff_fingerprint` | `b051e7c7c93b28ff40b3d94e46413ea9742834a7:b1c997df18aecab355525ed9f891477810a04bf2aad46138e868a6a4376a057e` ✅ |
| 指纹独立计算验证 | `git diff --binary <base>..<head> -- . ':(exclude)status.json' \| shasum -a 256` = `b1c997df...` ✅ 匹配 |
| 禁止文件扫描 | `backend/`, `frontend/`, `docs/product/`, `docs/architecture/`, `reports/api-samples/`, `.env` 均未出现在 diff 中 ✅ |
| Stage branch | `stage/2026-07-harness-friction-fixes-v1` ✅ |
| 变更统计 | 23 files, +2166 / -18 lines（以新增 Harness 脚本、文档、模板和阶段证据为主）|

---

## 二、各摩擦点（Friction Point）核查

### F1: 未选定 `review_2.primary_provider` 不触发 designer-overlap（设计者重叠）

**结论：✅ 正确实现**

- `validate-stage.py` 新增函数 `review_selected_identity()`（行 333–349），仅探测 `reviewer`/`provider`/`selected_provider` 三个已确认字段，**刻意排除** `primary_provider`（未选定偏好）。
- `validate_review_identity()`（行 781–817）在 review-1 和 review-2 的隔离检查中均使用 `review_selected_identity()`，不使用旧函数 `review_provider_identity()`。
- 旧函数 `review_provider_identity()`（行 352–360）保留但仅在 `validate_tasks` 中用于已完成审阅的身份校验。
- **模板** `_template/status.json` 中 `review_2.reviewer/provider/model` 均为 `null`，`primary_provider` 和 `fallback_provider` 是路由偏好，不是身份字段。
- 已选定审阅者仍正确执行 implementer hard ban（实现者硬禁止，行 797–798）和 designer-overlap disclosure override（设计者重叠披露覆盖，行 800–817）。
- **测试覆盖**：4 个专用测试用例（`test_unselected_primary_provider_no_designer_overlap`、`test_selected_reviewer_enforces_overlap`、`test_selected_reviewer_implementer_ban`、`test_selected_reviewer_unrelated_is_clean`）全部通过。

### F2/F5: single-owner validator evidence ordering, delivery-anchored `head_sha`, validator fixed-point semantics

**结论：✅ 正确文档化与实现**

- `docs/independent-task-branch-mode.md` 行 87–105 新增两节：
  - **Delivery-anchored `head_sha`**（交付锚定的 `head_sha`）：`head_sha` 指向审阅检视的交付提交（delivery commit），后续辅助提交（如 status.json metadata commit、handoff 更新）不移动 `head_sha`，除非阶段显式 re-anchor（重锚定）并重新验证。
  - **Validator fixed-point property**（验证器不动点性质）：已提交的 validator 日志不可能包含包含自身的提交指纹（自指不可能），因此日志记录的是 pre-inclusion snapshot（包含前快照）。权威最终指纹始终在 `status.json.diff_fingerprint` 中。
- `reports/agent-runs/README.md` 行 142–155 有一致的重复文档。
- 未引入新的 fingerprint protocol（指纹协议）。行 113–116 明确保留单一 canonical diff fingerprint。
- 实际阶段证据链完整：`61-validate-pre-review.txt`（pre-reconcile anchor）→ `62-validate-pre-review-final.txt`（final anchor 匹配 status.json）→ `63-validate-pre-review-review2.txt`（review-2 phase 通过），三者关系在 `70-handoff.md` 中有明确说明。

### F3: `record-checkpoint --single-owner` 写入 top-level `status.json` metadata

**结论：✅ 正确实现**

- `run_single_owner()`（行 108–144）：先 `git add -A` + 条件 `git commit`，然后计算 `head_sha` / `diff_fingerprint` / `changed_files`，写入 `status.json` 的 `base_sha`/`head_sha`/`diff_fingerprint`/`changed_files` 四个字段，最后 `git add -A` + `git commit` metadata commit。
- `status.json` 被 canonical fingerprint 排除（`_itbm.py` `canonical_fingerprint` 使用 `:(exclude)status_rel(stage_id)`），因此 metadata commit 不改变指纹。
- **`--dry-run` 无 mutation（无变更）验证**：行 113–121 仅调用 `rev_parse`/`canonical_fingerprint`/`changed_files`（全部是只读 git 操作），不执行 `git add`/`git commit`/文件写入。
- `_guard_protected_pending` 在 `--dry-run` 前运行（行 111）但仅执行 `git status --porcelain`（只读），安全。
- **测试覆盖**：`itbm_dry_run.py` 的 `test_single_owner` 和 `test_single_owner_dry_run` 分别验证正常写入和 dry-run 无变更（检查 HEAD 不变、`git status --short` 不变、`status.json` metadata 未写入）。

### F4: `validate-stage.py --evidence-out <path>` 仅在 PASS 后写入

**结论：✅ 正确实现**

- 行 933–936：任何 error 存在时立即 `return 1`，不到达 evidence-out 代码。
- 行 959–964：仅在所有检查通过后才写入 evidence 文件。
- `ValidationError` 异常（行 966–969）也返回 1，不写入。
- 注释（行 953–958）清晰解释了设计意图：避免 `tee` 仓库文件导致 clean-worktree 检查自冲突。
- **测试覆盖**：`test_evidence_out_on_pass` 和 `test_evidence_out_on_fail` 两个专用测试。

### F6/F7: `actual_model`、review output hygiene

**结论：✅ 正确文档化**

- `_template/status.json` 行 113 新增 `"actual_model": null`（在 `review_2` 块中）。
- `docs/model-adapters.md` 行 102–108 文档化了 actual model 回退记录规则。
- `docs/model-adapters.md` 行 305–321 文档化了 Kimi review output hygiene（审阅输出卫生），含 stderr 分离的 bash 示例。
- `stage-delivery.yaml` review-1 preflight（行 554）引用了 output hygiene 文档。

### F8: `fix_start_prompt.next_action` 指向正确的 review gate

**结论：✅ 正确实现**

- `stage-delivery.yaml` 行 159–163 新增政策声明：
  - `review_1_rework_redispatches_review_1_not_review_2: true`
  - `fix_start_prompt_next_action_matches_originating_review: true`
- review-1 `output_contract`（行 598）和 review-2 `output_contract`（行 728）分别要求 `next_action` 命名正确的 review gate（review-1 REWORK → fix → retest → redispatch review-1；review-2 REWORK → fix → retest → redispatch review-2）。

### F9: `reporting_preferences`（报告语言偏好）

**结论：✅ 正确实现**

- `_template/status.json` 行 38–50 新增 `reporting_preferences` 对象（`primary_language`/`explain_english_terms`/`preserve_exact_strings`）。
- `reports/agent-runs/README.md` 行 211–249 完整文档化了语义、用法和混合语言示例。
- `stage-delivery.yaml` 声明了 `reporting_preferences` 支持。
- 当前阶段 `status.json` 行 83–97 已激活 `reporting_preferences`，实际 dispatch prompt 均采用中文为主。

---

## 三、Review-1 证据核查

| 检查项 | 结果 |
|--------|------|
| Review-1 审阅者 | Kimi（`moonshot_kimi` provider identity），符合 cross-review pool 要求 ✅ |
| Schema-valid ACCEPT | `30-review-1.md` 行 86–127 含 JSON verdict，`verdict=ACCEPT`，`schema_version=1`，`findings=[]`，`required_fixes=[]`，`next_action=continue` ✅ |
| Schema 验证 | `60-test-output.txt` 行 116–125 记录了对 `review-verdict.schema.json` 的独立验证，`schema_valid=true` ✅ |
| Raw 输出保留 | `30-review-1.raw-output.md`（151 行）完整保留 Kimi 原始输出 ✅ |
| Cleaned vs Raw | `30-review-1.md`（128 行）仅移除了前 17 行 adapter header noise（CLI metadata/progress/诊断），审阅叙述和 JSON verdict 逐字节一致 ✅ |
| 指纹一致性 | Review-1 verdict 中 `diff_fingerprint` 与 `status.json` 顶层、task 级别、`review_1` 级别、`62-validate-pre-review-final.txt` 全部一致 ✅ |

---

## 四、Strong-reviewer override（强审阅者覆盖）披露核查

| 检查项 | 结果 |
|--------|------|
| 覆盖原因 | 无决策模型 provider 与本阶段设计集完全无关：OpenAI 有 design/bookkeeper 参与，Anthropic 有 breakdown 参与 ✅ |
| 证据文件 | `review-2-strong-reviewer-override-evidence.md` 存在，含完整 provider 表格和理由 ✅ |
| `status.json` 字段 | `review_2.reviewer_prior_involvement=breakdown`、`design_conflict_override.used=true`、`unrelated_reviewer_unavailable_evidence` 指向证据文件 ✅ |
| 实现/修复作者禁令 | Claude/Anthropic 不是实现者（`zhipu_glm`）也不是修复者（`fix_authors=[]`），禁令不适用 ✅ |

---

## 五、发现与建议

### P2 发现（可改进但不阻塞验收）

| # | 标题 | 文件 | 证据 | 影响 | 建议 |
|---|------|------|------|------|------|
| 1 | `--evidence-out` 写入未包裹异常处理 | `validate-stage.py` L959–964 | `evidence_path.write_text(output)` 无 try/except | 权限错误时用户看到 Python traceback 而非清晰错误 | 用 `try/except OSError` 包裹并打印友好消息 |
| 2 | `--dry-run` 未守护 `--single-owner` 缺失 | `record-checkpoint` L155–173 | `--dry-run` 无 `--single-owner` 时被静默忽略 | 用户可能误以为 dry-run 生效但实际执行了写操作 | 在 `main()` 中加入 `if args.dry_run and not args.single_owner: raise ItbmError(...)` |
| 3 | `diff.renames=true` 未在 `validate-stage.py` 指纹计算中显式固定 | `validate-stage.py` L160–176 vs `_itbm.py` L51–65 | `_itbm.py` 用 `-c diff.renames=true`，`validate-stage.py` 依赖 git 默认值 | 若用户 `.gitconfig` 设置 `diff.renames=false` 则两处产生不同指纹 | 在 `validate-stage.py` 的 `compute_diff_fingerprint` 中也加 `-c diff.renames=true` |
| 4 | `review_1` 无 `actual_model` 字段 | `_template/status.json` L96–108 | `review_1` 块无 `actual_model` 而 `review_2` 有 | review-1 模型替换时无法记录实际模型 | 建议为 `review_1` 也加 `actual_model` 或记录 intentional asymmetry 原因 |
| 5 | `test` 阶段转换未编码 review gate 来源 | `stage-delivery.yaml` L639–642 | `fix → test` 是同一转换，不区分 review-1/review-2 REWORK 来源 | 依赖 bookkeeper 逻辑而非机械路由 | 考虑加 `after_fix_from_review_1/2` 显式转换 |

### P3 发现（信息性）

| # | 标题 | 文件 | 说明 |
|---|------|------|------|
| 1 | `70-handoff.md` artifact index 显示"pending"但实际已完成 | `70-handoff.md` L24–26 | 叙述体和 `status.json` 正确，仅索引过期 |
| 2 | `61-validate-pre-review.txt` 指纹不同于最终锚定 | `61` vs `62` | 预期行为，`62` 替代 `61`，已在 handoff 中说明 |
| 3 | `pre-accept` 阶段 `validate_tasks` 可能重复调用 | `validate-stage.py` L925–931 | 非功能性冗余，不影响正确性 |

---

## 六、综合评估

| 维度 | 状态 |
|------|------|
| F1: 未选定 preference 不触发隔离检查 | ✅ |
| F2/F5: 交付锚定 `head_sha` + 不动点文档 | ✅ |
| F3: single-owner checkpoint 写 status metadata | ✅ |
| F4: `--evidence-out` 仅在 PASS 后写入 | ✅ |
| F6: `actual_model` 支持 | ✅ |
| F7: review output hygiene 文档 | ✅ |
| F8: REWORK redispatch 路由正确 | ✅ |
| F9: `reporting_preferences` 支持 | ✅ |
| 范围边界 | ✅ 无禁止文件修改 |
| 产品运行时 | ✅ 未触碰 |
| Review-1 证据 | ✅ Schema-valid ACCEPT |
| 指纹一致性 | ✅ 所有引用一致 |
| Strong-reviewer override 披露 | ✅ 充分记录 |
| 测试通过 | ✅ 26/26 tests + 3 validator passes |
| P0/P1 blocker | 无 |

所有 9 个摩擦点修复均已正确实现或文档化。5 项 P2 建议为 hardening（加固）改进，均非正确性错误，不阻塞验收。可作为后续 follow-up 处理。

---

本地北京时间: 2026-07-09 20:52:24 CST
下一步模型: human
下一步任务: 确认 review-2 ACCEPT 后将阶段状态更新为 `stage_accepted_waiting_user`，然后由用户决定是否合并 stage branch 至 `main`

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-friction-fixes-v1",
  "role": "final_reviewer",
  "model": "claude-opus-4-6",
  "verdict": "ACCEPT",
  "diff_fingerprint": "b051e7c7c93b28ff40b3d94e46413ea9742834a7:b1c997df18aecab355525ed9f891477810a04bf2aad46138e868a6a4376a057e",
  "reviewer_prior_involvement": "breakdown",
  "reviewer_prior_involvement_notes": "Anthropic/Claude authored 12-development-breakdown.md but did not implement or fix this stage. The implementer is zhipu_glm (Claude-GLM); the fix_authors list is empty; review-1 is moonshot_kimi; the designer and bookkeeper are openai (Codex/GPT-5). No decision-model provider is unrelated to the stage design set: OpenAI has design/bookkeeper involvement and Anthropic has breakdown involvement. This review uses the documented strong-reviewer disclosure override. The user-approved stage task, AGENTS.md, workflow YAML, and schemas were treated as authoritative over the breakdown notes.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "docs/independent-task-branch-mode.md",
    "docs/model-adapters.md",
    "reports/agent-runs/README.md",
    "reports/agent-runs/_template/status.json",
    "schemas/review-verdict.schema.json",
    "scripts/validate-stage.py",
    "scripts/record-checkpoint",
    "scripts/tests/itbm_dry_run.py",
    "scripts/tests/test_validate_stage.py",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/00-task.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/10-design.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/11-adr.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/21-bookkeeper-inspection.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/22-bookkeeper-reinspection.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/30-review-1.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/30-review-1.raw-output.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/61-validate-pre-review.txt",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/62-validate-pre-review-final.txt",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/63-validate-pre-review-review2.txt",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/70-handoff.md",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json",
    "reports/agent-runs/2026-07-harness-friction-fixes-v1/review-2-strong-reviewer-override-evidence.md"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "--evidence-out write lacks OSError handling",
      "file": "scripts/validate-stage.py",
      "line": 959,
      "evidence": "evidence_path.write_text(output) at line 964 has no try/except; permission or I/O errors produce a Python traceback instead of a clean Harness-style error.",
      "impact": "Users on read-only filesystems or with path issues see confusing tracebacks. The return code is still 1 (crash), but UX is degraded.",
      "recommendation": "Wrap the evidence write in try/except OSError and print a clear warning to stderr."
    },
    {
      "severity": "P2",
      "title": "--dry-run silently ignored without --single-owner",
      "file": "scripts/record-checkpoint",
      "line": 155,
      "evidence": "--dry-run help text says 'single-owner only' but no runtime guard exists. If passed without --single-owner, the double-owner path proceeds with real git mutations.",
      "impact": "A user who mistakenly passes --dry-run without --single-owner would see real commits, not a preview.",
      "recommendation": "Add an early guard: if args.dry_run and not args.single_owner: raise ItbmError('--dry-run is only supported with --single-owner')."
    },
    {
      "severity": "P2",
      "title": "diff.renames=true not pinned in validate-stage.py fingerprint computation",
      "file": "scripts/validate-stage.py",
      "line": 160,
      "evidence": "_itbm.py canonical_fingerprint uses '-c diff.renames=true' but validate-stage.py compute_diff_fingerprint relies on git defaults. A user with diff.renames=false in .gitconfig would get mismatched fingerprints.",
      "impact": "Low probability but potential false fingerprint mismatch in non-default git configurations.",
      "recommendation": "Add '-c diff.renames=true' to the git diff invocation in compute_diff_fingerprint for consistency."
    },
    {
      "severity": "P2",
      "title": "review_1 block lacks actual_model field (asymmetry with review_2)",
      "file": "reports/agent-runs/_template/status.json",
      "line": 96,
      "evidence": "review_2 has actual_model: null but review_1 does not. If review-1 ever has a model substitution, there is no field to record it.",
      "impact": "Low — review-1 uses direct model selection, not a fallback chain. But the asymmetry is undocumented.",
      "recommendation": "Add actual_model to review_1 or document the intentional omission."
    },
    {
      "severity": "P2",
      "title": "fix stage test transition does not encode originating review gate",
      "file": "workflows/templates/stage-delivery.yaml",
      "line": 639,
      "evidence": "fix → test is the same transition regardless of review-1 or review-2 REWORK origin. Routing back to the correct gate relies on bookkeeper logic + fix_start_prompt, not mechanical YAML transitions.",
      "impact": "Low — the system works correctly via policy + prompt contract, but a bookkeeper bug could route to the wrong gate.",
      "recommendation": "Consider adding explicit transition guidance (after_fix_from_review_1 / after_fix_from_review_2) for mechanical routing."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "P2 findings above are hardening improvements, not correctness bugs. They should be tracked as follow-up work.",
    "The 70-handoff.md artifact index shows stale 'pending' statuses for completed artifacts (cosmetic, no functional impact)."
  ],
  "next_action": "stage_accepted_waiting_user"
}
```
