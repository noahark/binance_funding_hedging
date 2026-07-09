<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude / claude-fable-5 (fallback opus4.8 on Fable5 quota exhaustion)
adapter_cmd:   claude --model claude-fable-5 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-harness-hardening-followups-v1/review-2-claude.prompt.md)" 2>reports/agent-runs/2026-07-harness-hardening-followups-v1/review-2-claude.stderr.log | tee reports/agent-runs/2026-07-harness-hardening-followups-v1/50-review-2.md
fallback_cmd:  claude --model opus4.8 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-harness-hardening-followups-v1/review-2-claude.prompt.md)" 2>reports/agent-runs/2026-07-harness-hardening-followups-v1/review-2-claude.stderr.log | tee reports/agent-runs/2026-07-harness-hardening-followups-v1/50-review-2.md
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-hardening-followups-v1/50-review-2.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，派发后不得修改） ===== -->
你是 Harness stage `2026-07-harness-hardening-followups-v1` 的 review-2（final reviewer）审阅者，执行 reality-checker（现实核对）职责。

请以中文为主撰写审阅说明。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。最终输出必须以一个严格 JSON object 结尾，并匹配 `schemas/review-verdict.schema.json`。

Read-only requirement（只读要求）：

- 不要修改文件。
- 不要运行破坏性命令。
- 只审阅原始 artifact（工件）和 `status.json` 记录的 committed diff range（已提交差异范围）。

Reviewer identity（审阅者身份）与 isolation（隔离）：

- Implementer（实现者）: Claude-GLM `glm-5.2`, provider identity `zhipu_glm`。
- Reviewer-1（首审）: Kimi `kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`，verdict `ACCEPT`。
- Designer + Bookkeeper（设计者兼记账）: `codex_gpt5`, provider identity `openai`。
- Reviewer-2（本次，final）: Claude `claude-fable-5`（若 Fable5 限额则 `opus4.8`）, provider identity `anthropic`。
- Provider isolation 满足：`anthropic` ≠ `zhipu_glm`（实现者）、≠ `moonshot_kimi`（review-1）、≠ `openai`（designer）。
- 本 stage 无 direction synthesis、无 development breakdown、无 fix author。
- Claude/`anthropic` 对本 stage **无** design / breakdown / synthesis / implementation / fix 参与，因此 `reviewer_prior_involvement` 必须为 `"none"`。**不需要** design-conflict / strong-reviewer disclosure override。
- Fallback 背景：anticipated primary review-2 model 是 `codex`/`GPT`，因 `quota_exhausted`（限额）fallback 到 `claude`（见 `review-2-fallback-evidence.md`）。

Required context（必须阅读）：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/product/PRD.md`（product 权威文档，优先级高于 stage 内 00-task/10-design/11-adr）
- `docs/architecture/ARCHITECTURE.md`（architecture 权威文档）
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/21-bookkeeper-inspection.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/30-review-1.md`（review-1 原始输出与 verdict）
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/61-validate-pre-review.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/62-validate-pre-review-final.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/63-validate-pre-review-review-2.txt`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/review-2-fallback-evidence.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`
- `schemas/review-verdict.schema.json`

Diff instructions（差异审阅指令）：

1. 从 `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json` 读取 `base_sha`、`head_sha`、`diff_fingerprint`。
2. 当前记录值为：
   - `base_sha`: `ddcf0e11a2ece33bdb9863512504fcc404867e4f`
   - `head_sha`: `6eb87a0fdb8ee550115013a1faccd678ed51282d`
   - `diff_fingerprint`: `6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638`
3. 精确审阅：

```bash
git diff --binary ddcf0e11a2ece33bdb9863512504fcc404867e4f..6eb87a0fdb8ee550115013a1faccd678ed51282d -- . ":(exclude)reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json"
```

4. 不要把 moving `HEAD` diff 当作 gate diff。
5. `30-review-1.md`、`63-validate-pre-review-review-2.txt`、`review-2-fallback-evidence.md`、本 prompt，以及记录 `head_sha` 之后的 status/handoff commit，都是 recorded `head_sha` 之后的 auxiliary evidence（辅助证据）。授权 reviewed range 为 `status.json.base_sha..status.json.head_sha`。
6. 请本地核对 `diff_fingerprint` 与 status.json 记录是否 byte-for-byte 一致（这是 head-anchored delivery fingerprint）。

Review focus（审阅重点，final reality-check）：

- AC1: `validate-stage.py --evidence-out` 写入失败是否捕获 `OSError`，返回清晰 Harness 错误而非 Python traceback（回溯），并返回非零。
- AC2: `record-checkpoint --dry-run` 缺少 `--single-owner` 时是否在任何 double-owner mutation（双所有者写入变更）前失败，错误信息是否清晰、可操作。
- AC3: `validate-stage.py compute_diff_fingerprint` 是否显式使用 `-c diff.renames=true`，并与 `scripts/_itbm.py canonical_fingerprint` 一致（防止 rename 处理不一致导致 fingerprint 漂移）。
- AC4: `reports/agent-runs/_template/status.json` 是否同时支持 top-level 与 task-level `review_1.actual_model`，且不破坏既有 `review_2.actual_model` 记录；workflow 是否给出「actual_model 与 anticipated 不同才记录」的指引。
- AC5: `workflows/templates/stage-delivery.yaml` 是否编码 fix `return_gate`（修复返回审查门禁）：review-1 REWORK 后回 review-1，review-2 REWORK 后回 review-2；并与既有 F8 policy text 一致（machine-readable 补充，不替代）。
- Tests（测试）：新增/修改测试是否真实覆盖 AC1-AC5，且既有 Harness regression（回归）仍通过；测试断言是否有效（非空测/伪断言）。
- Review-1 交叉核对：复核 review-1（Kimi）ACCEPT 结论是否成立，或有遗漏的 P0/P1/P2。
- Scope（范围）：不应触碰 `backend/**`、`frontend/**`、`docs/product/**`、`docs/architecture/**`、`reports/api-samples/**`、`AGENTS.md`、`agents/registry.yaml`、`schemas/**`、`reports/agent-runs/2026-07-harness-friction-fixes-v1/**`。
- Residual risk 核对：AC5 为 machine-readable workflow 指引，`validate-stage.py` 尚未 runtime-enforce `return_gate`；AC4 仅更新 template，未回填既有 stage status.json。确认这些是否符合 stage design intent、是否构成需要 REWORK 的缺陷。

Expected tests（期望测试证据，可自行只读复跑）：

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py scripts/record-checkpoint
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase pre-review
git diff --check
```

Return format（返回格式）：

- 先给 findings（发现的问题），按严重度排序；无问题时明确说明。
- 最后输出一个严格 JSON object，必须匹配 `schemas/review-verdict.schema.json`。
- `role` 必须为 `"final_reviewer"`（schema enum；review-2 final reviewer）。
- `ACCEPT` 时使用 `"next_action": "stage_accepted_waiting_user"`。
- `REWORK` 时必须包含 `fix_start_prompt`，且 `next_action` 使用 `"fix"`；`fix_start_prompt` 内必须注明 review-2 REWORK 修复后 redispatch 回 review-2（不得跳过）。
- `BLOCKED` 时使用 `"next_action": "human_escalation_required"` 或 schema 允许的更准确值。
- `reviewer_prior_involvement` 必须为 `"none"`。

最终 JSON 必须包含：

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-harness-hardening-followups-v1",
  "role": "final_reviewer",
  "model": "claude-fable-5",
  "verdict": "ACCEPT | REWORK | BLOCKED",
  "diff_fingerprint": "6eb87a0fdb8ee550115013a1faccd678ed51282d:3ce700761aad68d0084a22ff742edf1ee0e2194716625bfa563a8927eb821638",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [],
  "next_action": "stage_accepted_waiting_user | fix | human_escalation_required"
}
```

注意：若实际执行模型为 `opus4.8`（Fable5 限额 fallback），请在叙述中说明，并由 bookkeeper 记录到 `status.json.review_2.actual_model`（provider identity 仍为 `anthropic`，不变）。
