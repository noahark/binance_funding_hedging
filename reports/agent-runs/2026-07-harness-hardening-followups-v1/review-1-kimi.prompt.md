<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  kimi / kimi-code/kimi-for-coding
adapter_cmd:   kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-harness-hardening-followups-v1/review-1-kimi.prompt.md)" 2>reports/agent-runs/2026-07-harness-hardening-followups-v1/review-1-kimi.stderr.log | tee reports/agent-runs/2026-07-harness-hardening-followups-v1/30-review-1.md
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-hardening-followups-v1/30-review-1.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，派发后不得修改） ===== -->
你是 Harness stage `2026-07-harness-hardening-followups-v1` 的 review-1 审阅者。

请以中文为主撰写审阅说明。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。最终输出必须以一个严格 JSON object 结尾，并匹配 `schemas/review-verdict.schema.json`。

Read-only requirement（只读要求）：

- 不要修改文件。
- 不要运行破坏性命令。
- 只审阅原始 artifact（工件）和 `status.json` 记录的 committed diff range（已提交差异范围）。

Reviewer identity（审阅者身份）：

- Implementer（实现者）: Claude-GLM `glm-5.2`, provider identity `zhipu_glm`。
- Reviewer（审阅者）: Kimi `kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`。
- Provider isolation（提供方隔离）满足：review-1 不与实现者共享 provider identity。
- `reviewer_prior_involvement` 必须为 `"none"`。

Required context（必须阅读）：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/21-bookkeeper-inspection.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/61-validate-pre-review.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/62-validate-pre-review-final.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`
- `schemas/review-verdict.schema.json`

Diff instructions（差异审阅指令）：

1. Read `base_sha`, `head_sha`, and `diff_fingerprint` from:
   `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`
2. The current recorded values are:
   - `base_sha`: `ddcf0e11a2ece33bdb9863512504fcc404867e4f`
   - `head_sha`: `6eb87a0fdb8ee550115013a1faccd678ed51282d`
   - `diff_fingerprint`: `6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638`
3. Inspect exactly:

```bash
git diff --binary ddcf0e11a2ece33bdb9863512504fcc404867e4f..6eb87a0fdb8ee550115013a1faccd678ed51282d -- . ":(exclude)reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json"
```

4. Do not review a moving `HEAD` diff as the gate diff.
5. `62-validate-pre-review-final.txt`, this prompt, and later status/handoff commits may be auxiliary evidence after the recorded `head_sha`. Treat `status.json.base_sha..status.json.head_sha` as the authoritative reviewed range.

Review focus（审阅重点）：

- AC1: `validate-stage.py --evidence-out` 写入失败是否捕获 `OSError`，并返回清晰 Harness 错误而非 Python traceback（回溯）。
- AC2: `record-checkpoint --dry-run` 缺少 `--single-owner` 时是否在任何 double-owner mutation（双所有者写入变更）前失败，错误是否清晰。
- AC3: `validate-stage.py compute_diff_fingerprint` 是否显式使用 `-c diff.renames=true`，并与 `scripts/_itbm.py canonical_fingerprint` 一致。
- AC4: `reports/agent-runs/_template/status.json` 是否支持顶层和任务级 `review_1.actual_model`，且不破坏既有 review-2 actual model 记录。
- AC5: `workflows/templates/stage-delivery.yaml` 是否编码 fix return gate（修复返回审查门禁）：review-1 REWORK 后回 review-1，review-2 REWORK 后回 review-2。
- Tests（测试）：新增/修改测试是否覆盖 AC1-AC5，且既有 Harness regression（回归）仍通过。
- Scope（范围）：不应触碰 `backend/**`、`frontend/**`、`docs/product/**`、`docs/architecture/**`、`reports/api-samples/**`、`AGENTS.md`、`agents/registry.yaml`、`schemas/**`、`reports/agent-runs/2026-07-harness-friction-fixes-v1/**`。

Expected tests（期望测试证据）：

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py scripts/record-checkpoint
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase pre-review
git diff --check
```

Return format（返回格式）：

- 先给 findings（发现的问题），按严重度排序。
- 最后输出一个严格 JSON object，必须匹配 `schemas/review-verdict.schema.json`。
- `ACCEPT` 时使用 `"next_action": "continue"`。
- `REWORK` 时必须包含 `fix_start_prompt`，且 `next_action` 使用 `"fix"`。
- `BLOCKED` 时使用 `"next_action": "human_gate"` 或 schema 允许的更准确值。

最终 JSON 必须包含：

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-hardening-followups-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "continue | fix | human_gate"
}
```
