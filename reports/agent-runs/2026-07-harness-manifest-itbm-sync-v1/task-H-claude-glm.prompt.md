<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/task-H-claude-glm.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/20-implementation.md; reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/60-test-output.txt; reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/record-checkpoint-single-owner.raw-output.txt; reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/61-validate-pre-review.txt; reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/30-review-1.md
next_dispatch: review-1-kimi.prompt.md executor:self
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
You are Claude-GLM implementing Harness stage
`2026-07-harness-manifest-itbm-sync-v1`.

Read first:

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `agents/registry.yaml`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/status.json`

Hard boundaries:

- Delivery edit allowed: `harness-manifest.yaml`
- Evidence edit allowed:
  `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/**`
- Do not edit `AGENTS.md`, `workflows/**`, `scripts/**`, `schemas/**`,
  `agents/**`, `docs/model-adapters.md`, or product files.
- Do not merge to `main`.
- Do not rebase.

Implementation task:

Update `harness-manifest.yaml` so `harness_owned` explicitly includes:

- `docs/independent-task-branch-mode.md`
- `scripts/_itbm.py`
- `scripts/record-checkpoint`
- `scripts/prepare-review-2`
- `scripts/tests/itbm_dry_run.py`

Do not add broad `scripts/` ownership.

Required tests:

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
```

Write the raw command output to:

```text
reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/60-test-output.txt
```

Update:

- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/70-handoff.md`

Single-owner checkpoint sequence:

1. Confirm current branch is
   `stage/2026-07-harness-manifest-itbm-sync-v1`.
2. Confirm changed files are only `harness-manifest.yaml` and this stage's
   evidence files.
3. Run:

```bash
checkpoint_output="$(python3 scripts/record-checkpoint 2026-07-harness-manifest-itbm-sync-v1 \
  --branch stage/2026-07-harness-manifest-itbm-sync-v1 \
  --task-worktree "/Users/ark/Desktop/ai code/funding_hedging" \
  --base-sha 0a2abb8e5e68973325a6a6cacca5c66a7e896b98 \
  --single-owner 2>&1)"
checkpoint_rc=$?
printf '%s\n' "$checkpoint_output"
printf '%s\n' "$checkpoint_output" > reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/record-checkpoint-single-owner.raw-output.txt
test "$checkpoint_rc" -eq 0
```

4. Preserve recorder output in git. Because the current single-owner recorder
   does not update top-level `status.json`, perform the following follow-up:
   update `70-handoff.md` with the checkpoint result and commit the recorder
   raw output/handoff evidence. Then compute the review fingerprint for that
   evidence commit using the same canonical helper:

```bash
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
from _itbm import canonical_fingerprint, rev_parse
stage = "2026-07-harness-manifest-itbm-sync-v1"
base = "0a2abb8e5e68973325a6a6cacca5c66a7e896b98"
repo = Path(".").resolve()
head = rev_parse("HEAD", cwd=repo)
print(head)
print(canonical_fingerprint(repo, base, head, stage))
PY
```

5. Update only `status.json` with:
   - `status`: `review_1`
   - `base_sha`: `0a2abb8e5e68973325a6a6cacca5c66a7e896b98`
   - `head_sha`: the HEAD from the helper output
   - `diff_fingerprint`: the helper fingerprint
   - `changed_files`: include `harness-manifest.yaml` and stage evidence files
   - `tests.status`: `pass`
   - `review_1` pending fields still null
   - task `H` base/head/fingerprint matching top-level values
   Commit this status-only update.

6. Run and preserve:

```bash
python3 scripts/validate-stage.py 2026-07-harness-manifest-itbm-sync-v1 --phase pre-review \
  | tee reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/61-validate-pre-review.txt
```

Commit `61-validate-pre-review.txt`.

Review-1 self-dispatch:

Run Kimi in a fresh session using the prewritten dispatch:

```bash
kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/review-1-kimi.prompt.md)" \
  | tee reports/agent-runs/2026-07-harness-manifest-itbm-sync-v1/30-review-1.md
```

After Kimi returns:

- If the final JSON verdict is `ACCEPT`, update `status.json`:
  - `status`: `review_2`
  - `review_1.verdict`: `ACCEPT`
  - `review_1.json_schema_valid`: `true`
  - `review_1.diff_fingerprint`: the status-recorded fingerprint
  - task `H.review_1` matching the same verdict/fingerprint
  - `next_action`: `review-2 final reviewer selection after user returns`
  Commit `30-review-1.md`, `status.json`, and handoff updates.
- If verdict is `REWORK` or `BLOCKED`, do not proceed to review-2. Record the
  verdict, set the status to `fixing` or `human_escalation_required` according
  to the verdict, and stop.
- If Kimi output lacks strict valid JSON, retry once with the same prompt. If
  still invalid, record `invalid_json_attempts=2` and stop for human
  escalation.

Final response requirements:

- Report current branch, HEAD, git status, reviewed `base_sha..head_sha`, and
  `diff_fingerprint`.
- Report test commands and review-1 verdict.
- End with:

```text
本地北京时间: <from local date command>
下一步模型: human
下一步任务: select review-2 reviewer for 2026-07-harness-manifest-itbm-sync-v1 per AGENTS.md
```
