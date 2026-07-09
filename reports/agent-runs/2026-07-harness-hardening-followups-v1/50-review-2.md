# Review-2 (Final Reality-Check): Harness Hardening Follow-ups

## Reviewer Identity & Disclosure（审阅者身份与披露）

- Implementer（实现者）: `claude_glm` / `glm-5.2`, provider identity `zhipu_glm`。
- Reviewer-1（首审）: `kimi` / `kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`，verdict `ACCEPT`。
- Designer + Bookkeeper（设计者兼记账）: `codex_gpt5`, provider identity `openai`。
- Reviewer-2（final, 本次）: `claude`, provider identity `anthropic`。
  - Anticipated model: `claude-fable-5`；**actual executed model: `claude-opus-4-8`**（记入 `status.json.review_2.actual_model`；provider identity 仍为 `anthropic`，不变）。
- Fallback 背景: anticipated primary review-2 model `codex`/`GPT` 因 `quota_exhausted`（限额）不可用，fallback 到 `claude`（见 `review-2-fallback-evidence.md`）。符合 `stage-delivery.yaml` review-2 `fallback_only_on: quota_exhausted`。

### Provider isolation（提供方隔离）

- `anthropic` ≠ `zhipu_glm`（实现者）✓
- `anthropic` ≠ `moonshot_kimi`（review-1）✓
- `anthropic` ≠ `openai`（designer/bookkeeper）✓
- Claude/`anthropic` 对本 stage 无 design / breakdown / direction-synthesis / implementation / fix 参与。本 stage 亦无 breakdown、无 synthesis、无 fix author。
- 结论: `reviewer_prior_involvement = "none"`；无需 design-conflict / strong-reviewer disclosure override。

### Dual-hat disclosure（双重身份披露）

- **重要披露**: 本次 review-2 由与 bookkeeper 相同的 Claude 会话执行（user 明确授权“直接在本会话内跑”）。即本会话同时承担 bookkeeper（记账）与 review-2 reviewer（审阅）两个角色。
- 这与常规「Claude session 仅准备 dispatch packet、由人工在目标终端执行」的流程不同，属 user-authorized 例外。
- 该 dual-hat 不构成 `reviewer_prior_involvement`：bookkeeper 仅做编排/记账，未撰写 reviewed range 内的任何 design/implementation/fix 代码。bookkeeper 的全部提交均在 `head_sha` 之后、且不在 reviewed diff range 内。
- 记入 `status.json.bookkeeper.dual_hat_disclosure` 供审计。

## Reviewed Range（审阅范围）

- `base_sha`: `ddcf0e11a2ece33bdb9863512504fcc404867e4f`
- `head_sha`: `6eb87a0fdb8ee550115013a1faccd678ed51282d`
- `diff_fingerprint`: `6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638`
- 本地按 `git -c diff.renames=true diff --binary base..head -- . :(exclude)<stage>/status.json` recompute，与 `status.json.diff_fingerprint` **byte-for-byte 一致**。
- `30-review-1.md`、`63-validate-pre-review-review-2.txt`、`review-2-fallback-evidence.md`、`review-2-claude.prompt.md`，以及 `head_sha` 之后的 status/handoff commit，均为 auxiliary evidence，不在授权 reviewed range 内。

## Verdict

`ACCEPT`。5 项 acceptance criteria（AC1–AC5）全部真实实现，且各有有效测试覆盖；provider isolation 满足；scope 无越界；无 P0/P1/P2 finding。我同意 review-1（Kimi）的 ACCEPT 结论。

## AC-by-AC Findings（逐条核对，均无缺陷）

### AC1 (D1) — `--evidence-out` 写入失败的受控错误处理

- `scripts/validate-stage.py` `main()` 中，`evidence_path.parent.mkdir(...)` 与 `evidence_path.write_text(output)` 被 `try/except OSError` 包裹；失败时向 `stderr` 打印 `EVIDENCE WRITE FAILED: could not write <path>: <OSError>` 并 `return 1`，无 Python traceback（回溯）。
- 行为正确性核对: validation 本身已 PASS 并向 stdout 打印；仅 evidence 落盘失败时返回非零——这是正确的，因为请求了 `--evidence-out` 却未能捕获证据即视为操作失败。
- 测试 `test_evidence_out_write_failure_clean_error` 真实有效: 通过把 evidence 父路径设为普通文件触发 `OSError`；`run_validator` 使用 `stderr=subprocess.STDOUT`，故对 stderr 消息的断言（含路径、`return code == 1`、无 `Traceback`）成立。复跑通过。

### AC2 (D2) — `record-checkpoint --dry-run` 需 `--single-owner`

- `scripts/record-checkpoint` 在 `try` 块内、`if args.single_owner: return run_single_owner(...)` **之前**加入守卫: `if args.dry_run and not args.single_owner: raise ItbmError(...)`，在任何 double-owner mutation（双所有者写入变更）之前失败。错误信息清晰可操作（提示加 `--single-owner` 预览或去掉 `--dry-run`）。
- `--dry-run --single-owner` 组合仍可正常预览（守卫先于 single-owner 分支放行），既有 `test_single_owner_dry_run` 仍通过。
- 测试 `test_dry_run_requires_single_owner` 断言 `returncode == 1`、`RECORD-CHECKPOINT BLOCKED`、且 `HEAD` 与 `git status` **零变更**。复跑通过。

### AC3 (D3) — `compute_diff_fingerprint` 固定 `diff.renames=true`

- `scripts/validate-stage.py::compute_diff_fingerprint` 显式加入 `-c diff.renames=true`，与 `scripts/_itbm.py::canonical_fingerprint`（同为 `-c diff.renames=true`）源码级一致。
- 正确性: `diff.renames=true` 是 git 默认值，pinning 不改变任何既有记录的 fingerprint（注释与 `_itbm` 说明一致）；作用是使多个 recompute site 在敌意本地/仓库 `.gitconfig` 下仍 byte-identical。
- 测试 `test_fingerprint_pins_renames_true` 强度高: 构造真实 rename、设置敌意 `diff.renames=false`，验证 `validate-stage` 与 `_itbm` 结果相等、且 `renames=true` 与 `renames=false` recompute 不相等（证明测试非空测）。复跑通过。

### AC4 (D4) — status.json 模板支持 `review_1.actual_model`

- `reports/agent-runs/_template/status.json` 在顶层 `review_1` 与 task 级 `review_1` 均加入 `"actual_model": null`，与既有 `review_2.actual_model` 对称，未破坏既有结构。
- `workflows/templates/stage-delivery.yaml` review-1 preflight 新增指引: 当实际执行模型与 anticipated 不同才记录到 `status.json.review_1.actual_model`（provider identity 不变），与 review-2 既有对应指引一致。
- 测试 `test_template_review_1_actual_model` 断言顶层与 task 级 `review_1` 均含 `actual_model`。复跑通过。

### AC5 (D5) — workflow 编码 fix return gate

- `workflows/templates/stage-delivery.yaml` `fix` stage 新增 machine-readable `return_gate`: `rule` + `after_fix_from_review_1: review-1` + `after_fix_from_review_2: review-2`，作为既有 F8/policy 文字的机器可读补充（非替代）。
- 测试 `test_workflow_fix_return_gate` 断言两条 `after_fix_from_*` 键均存在。复跑通过。

## Scope Check（范围检查）

授权 diff range 内改动仅落在: `scripts/validate-stage.py`、`scripts/record-checkpoint`、`scripts/tests/itbm_dry_run.py`、`scripts/tests/test_validate_stage.py`、`reports/agent-runs/_template/status.json`、`workflows/templates/stage-delivery.yaml`，以及本 stage evidence 目录。未触碰 forbidden paths: `backend/**`、`frontend/**`、`docs/product/**`、`docs/architecture/**`、`reports/api-samples/**`、`AGENTS.md`、`agents/registry.yaml`、`schemas/**`、`reports/agent-runs/2026-07-harness-friction-fixes-v1/**`。

## Review-1 Cross-check（交叉复核）

复核 Kimi review-1 的 ACCEPT: 其对 AC1–AC5 的定位（文件/行/测试）与我的独立核对一致，未发现其遗漏的 P0/P1/P2。同意其结论。

## Tests Re-run by Reviewer（复跑证据）

```bash
python3 scripts/tests/itbm_dry_run.py                 # 19/19 assertions passed
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py scripts/record-checkpoint  # OK
python3 scripts/tests/test_validate_stage.py          # 19/19 assertions passed
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint   # PASSED
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase pre-review   # PASSED
git diff --check                                       # clean
```

全部成功退出。

## Residual Risks（残余风险，均可接受、符合设计意图）

- AC5 `return_gate` 为 machine-readable workflow 指引，`validate-stage.py` 尚未 runtime-enforce；符合 stage design intent（“machine-readable enough for future validators or dispatch logic”），不回归既有行为。
- AC4 仅更新 template，未回填既有 stage `status.json`；符合设计意图（既有 stage 由各自 bookkeeper 维护）。
- Dual-hat（bookkeeper 兼 reviewer）为 user-authorized 例外，已完整披露；未影响 reviewed range 的独立性（bookkeeper 提交均在 range 之外）。

本地北京时间: 2026-07-09 22:11:13 CST
下一步模型: 无（等待 user 决定是否 merge 到 main）
下一步任务: bookkeeper 记录 verdict，进入 `stage_accepted_waiting_user`

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-hardening-followups-v1",
  "role": "final_reviewer",
  "model": "claude-opus-4-8",
  "verdict": "ACCEPT",
  "diff_fingerprint": "6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Reviewer provider anthropic has no design/breakdown/synthesis/implementation/fix involvement in this stage. Disclosure: this review-2 ran in the same Claude session that acts as bookkeeper (user-authorized dual-hat). Bookkeeping is orchestration/record-keeping only and authored no code inside the reviewed base..head range; all bookkeeper commits are after head_sha and outside the reviewed diff. Anticipated model was claude-fable-5; actual executed model is claude-opus-4-8, provider identity unchanged (anthropic).",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "docs/product/PRD.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/model-adapters.md",
    "reports/agent-runs/README.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/21-bookkeeper-inspection.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/30-review-1.md",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/63-validate-pre-review-review-2.txt",
    "reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json",
    "reports/agent-runs/_template/status.json",
    "schemas/review-verdict.schema.json",
    "git diff --binary ddcf0e11a2ece33bdb9863512504fcc404867e4f..6eb87a0fdb8ee550115013a1faccd678ed51282d -- . :(exclude)reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "AC5 return_gate is machine-readable workflow guidance, not yet runtime-enforced by validate-stage.py; matches stage design intent.",
    "AC4 updates only the status.json template; legacy stage status.json files are not backfilled.",
    "Review-2 executed under user-authorized bookkeeper/reviewer dual-hat; fully disclosed, and reviewed range independence is preserved (bookkeeper commits are outside base..head)."
  ],
  "next_action": "stage_accepted_waiting_user"
}
```
