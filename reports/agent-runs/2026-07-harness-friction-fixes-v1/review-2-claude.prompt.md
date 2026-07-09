<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude / claude-fable-5 (fallback: claude-opus-4-8 or actual user-selected Claude model)
adapter_cmd:   claude --model claude-fable-5 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-harness-friction-fixes-v1/review-2-claude.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-friction-fixes-v1/50-review-2.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，派发后不得修改） ===== -->
You are the final review-2 reviewer for Harness stage
`2026-07-harness-friction-fixes-v1`.

请以中文为主撰写审阅说明。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。最终输出必须以一个严格 JSON object 结尾，并匹配 `schemas/review-verdict.schema.json`。

Reviewer identity and disclosure:

- You are Claude/Anthropic (`anthropic` provider identity).
- Planned model is `claude-fable-5`; if another Claude model actually runs, report the actual model in the final JSON `model` field.
- You did not implement or fix this stage.
- Anthropic/Claude authored `12-development-breakdown.md`, so this final review uses the documented strong-reviewer disclosure override.
- `reviewer_prior_involvement` in the final JSON must be `"breakdown"`.
- Include `reviewer_prior_involvement_notes` explaining that Anthropic/Claude authored the breakdown but did not implement/fix the stage, and that OpenAI/Codex has design/bookkeeper involvement, so no decision-model provider is unrelated to the stage design set.
- Treat raw artifacts, `AGENTS.md`, workflow YAML, schemas, and the user-approved stage task as authority over the breakdown notes.

Read-only requirement:

- Do not modify files.
- Do not run write commands.
- Inspect raw artifacts and relevant source files directly.
- End with one strict JSON object matching `schemas/review-verdict.schema.json`.

Authoritative review range:

- `base_sha`: `4b98bf3d09f3aacee7e6ffdb9a2353e246af7e41`
- `head_sha`: `b051e7c7c93b28ff40b3d94e46413ea9742834a7`
- `diff_fingerprint`:
  `b051e7c7c93b28ff40b3d94e46413ea9742834a7:b1c997df18aecab355525ed9f891477810a04bf2aad46138e868a6a4376a057e`

Review the delivery diff using exactly:

```bash
git diff --binary 4b98bf3d09f3aacee7e6ffdb9a2353e246af7e41..b051e7c7c93b28ff40b3d94e46413ea9742834a7 -- . ":(exclude)reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json"
```

Do not substitute moving `HEAD` for the gate diff.

Required raw artifacts:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/_template/status.json`
- `schemas/review-verdict.schema.json`
- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/tests/itbm_dry_run.py`
- `scripts/tests/test_validate_stage.py`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/21-bookkeeper-inspection.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/22-bookkeeper-reinspection.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/30-review-1.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/30-review-1.raw-output.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/61-validate-pre-review.txt`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/62-validate-pre-review-final.txt`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/63-validate-pre-review-review2.txt`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/70-handoff.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/review-2-strong-reviewer-override-evidence.md`

Final review focus:

1. Confirm F1: unselected `review_2.primary_provider` no longer triggers designer-overlap, while selected reviewer/provider identities still enforce implementer hard bans and designer-overlap disclosure.
2. Confirm F3: `record-checkpoint --single-owner` writes top-level `status.json` metadata safely, and `--dry-run` performs no repository mutation. Tests must cover unchanged `HEAD`, unchanged `git status --short`, and unwritten `status.json` metadata.
3. Confirm F4: `validate-stage.py --evidence-out <path>` writes evidence only after a full PASS and does not create the file on failure.
4. Confirm F2/F5: single-owner validator evidence ordering, delivery-anchored `head_sha`, and validator fixed-point semantics are documented without introducing another fingerprint protocol.
5. Confirm F6/F7/F8/F9: `actual_model`, review output hygiene, `fix_start_prompt.next_action`, and `reporting_preferences` are implemented/documented within scope.
6. Confirm scope: no product runtime files or forbidden files were modified.
7. Confirm review-1 evidence: Kimi returned schema-valid `ACCEPT`; `30-review-1.raw-output.md` preserves raw stdout and `30-review-1.md` only removes adapter header noise.
8. Confirm the strong-reviewer disclosure override is adequately recorded for Claude/Anthropic breakdown involvement.
9. Identify any P0/P1 blocker or missing evidence that should prevent `stage_accepted_waiting_user`.

Verdict rules:

- Use `ACCEPT` only if no P0/P1 findings remain and evidence is sufficient.
- Use `REWORK` if a bounded fix is required; include `fix_start_prompt`.
- Use `BLOCKED` only for a human decision or missing evidence that cannot be repaired inside the current stage.
- `diff_fingerprint` in the final JSON must equal:
  `b051e7c7c93b28ff40b3d94e46413ea9742834a7:b1c997df18aecab355525ed9f891477810a04bf2aad46138e868a6a4376a057e`
- For `ACCEPT`, set `"next_action": "stage_accepted_waiting_user"`.

Place any footer before the final JSON block so the final JSON remains parseable.
