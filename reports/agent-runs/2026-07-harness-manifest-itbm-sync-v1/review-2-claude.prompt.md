<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude / claude-fable-5
adapter_cmd:   claude --model claude-fable-5 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/review-2-claude.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/50-review-2.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
You are the final review-2 reviewer for Harness stage
`2026-07-harness-manifest-itbm-sync-v1`.

Reviewer identity:

- You are Claude/Fable5 (`anthropic` provider identity).
- You did not implement or fix this stage.
- You did not design, synthesize direction, or author breakdown for this stage.
- `reviewer_prior_involvement` must be `"none"` unless you discover contrary
  evidence in the raw artifacts.

Read-only requirement:

- Do not modify files.
- Do not run write commands.
- Inspect raw artifacts and relevant source files directly.
- End with one strict JSON object matching `schemas/review-verdict.schema.json`.

Authoritative review range:

- `base_sha`: `0a2abb8e5e68973325a6a6cacca5c66a7e896b98`
- `head_sha`: `d613dea403dcb82d2006484ced237ac4da528d31`
- `diff_fingerprint`:
  `d613dea403dcb82d2006484ced237ac4da528d31:423b1154fc1615928112cb1d4376b51da68857c049d09ca978b072674bd6e20b`
- Review the delivery diff using exactly:

```bash
git diff --binary 0a2abb8e5e68973325a6a6cacca5c66a7e896b98..d613dea403dcb82d2006484ced237ac4da528d31 -- . ":(exclude)reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json"
```

Do not substitute moving `HEAD` for the gate diff.

Required raw artifacts:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `agents/registry.yaml`
- `schemas/review-verdict.schema.json`
- `harness-manifest.yaml`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/00-intake.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/30-review-1.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/61-validate-pre-review.txt`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/62-validate-pre-review-review2.txt` when present
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/70-handoff.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/record-checkpoint-single-owner.raw-output.txt`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/task-H-claude-glm.prompt.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/review-1-kimi.prompt.md`

Final review focus:

1. Confirm `harness-manifest.yaml` adds exactly the required independent
   task-branch mode assets:
   - `docs/independent-task-branch-mode.md`
   - `scripts/_itbm.py`
   - `scripts/record-checkpoint`
   - `scripts/prepare-review-2`
   - `scripts/tests/itbm_dry_run.py`
2. Confirm no broad `scripts/` ownership was added.
3. Confirm protected Harness behavior files were not modified by the delivery
   range, other than the intended manifest metadata.
4. Confirm tests and validator evidence are sufficient for a manifest-only
   Harness stage.
5. Evaluate the single-owner recorder trial evidence and Kimi review-1 history.
6. Explicitly assess Kimi's residual findings:
   - P2: `status.json.head_sha` stays anchored at the delivery/review range
     `d613dea` while later branch-tip commits (`aec14af`, `a9463e9`, and
     review-2 dispatch/preflight commits) are auxiliary review evidence outside
     the gate diff.
   - P3: `61-validate-pre-review.txt` records a pre-inclusion validator
     fingerprint because a validator log cannot include the exact fingerprint
     of the commit that contains itself; the authoritative gate fingerprint is
     in `status.json` and was revalidated by `validate-stage`.
7. Confirm review-1 was performed by Kimi, provider identity differs from the
   GLM implementer/fix author, and verdict is schema-valid `ACCEPT`.
8. Identify any P0/P1 blocker or missing evidence that should prevent
   `stage_accepted_waiting_user`.

Verdict rules:

- Use `ACCEPT` only if no P0/P1 findings remain and evidence is sufficient.
- Use `REWORK` if a bounded fix is required; include `fix_start_prompt`.
- Use `BLOCKED` only for a human decision or missing evidence that cannot be
  repaired inside the current stage.
- `diff_fingerprint` in the final JSON must equal:
  `d613dea403dcb82d2006484ced237ac4da528d31:423b1154fc1615928112cb1d4376b51da68857c049d09ca978b072674bd6e20b`
- `reviewer_prior_involvement` must be `"none"` unless raw evidence proves
  otherwise.
- For `ACCEPT`, set `"next_action": "stage_accepted_waiting_user"`.

Place any footer before the final JSON block so the final JSON remains
parseable.
