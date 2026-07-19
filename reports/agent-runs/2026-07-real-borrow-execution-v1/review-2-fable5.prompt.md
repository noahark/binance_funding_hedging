<!-- RECEIPT — bookkeeper fills this metadata after the human operator executes the packet.
status: done
target_model: claude / claude-fable-5 (fresh plan/read-only session)
adapter_cmd: claude --model claude-fable-5 --permission-mode plan --json-schema "$(cat schemas/review-verdict.schema.json)" -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/review-2-fable5.prompt.md)"
started_at: unavailable (not captured by operator)
completed_at: 2026-07-19T21:09:04+08:00
session_id: f64e6dea-a2bf-49a9-b3e1-9a3631384b8d
session_id_source: operator (verified provider-native Session ID)
output: reports/agent-runs/2026-07-real-borrow-execution-v1/50-review-2.md
next_dispatch: ACCEPT → stage_accepted_waiting_user; REWORK → bounded domain-owner fix
-->

--- PROMPT BODY (immutable from this line) ---

You are a fresh, plan/read-only Anthropic Fable5 final reviewer (`reviewer_2`)
for stage `2026-07-real-borrow-execution-v1`. You must not reuse an
implementation, embedded-review, Review-1, or bookkeeper session. Do not edit
files, change the worktree, commit, start a server, make network requests,
access credentials, or invoke Binance.

## Mandatory independence disclosure

You did not implement or fix delivery code. You did author this stage's
development breakdown (`12-development-breakdown.md`). The user selected this
configured fallback after Codex/GPT's stage-design conflict; this is a
strong-reviewer disclosure, not an independent-design claim. Read
`66-review-2-strong-reviewer-override.md`.

Treat the user-approved direction synthesis, `docs/product/PRD.md`, and
`docs/architecture/ARCHITECTURE.md` as higher authority than your own earlier
breakdown. Your verdict must disclose `reviewer_prior_involvement: "breakdown"`.

## Fixed review target

- Do not use moving `HEAD`.
- base_sha: `5b2b3232673fa7ee193efdcc6f80c4df82aa0fa9`
- head_sha: `4bab47d250b739539c0c2f09786baa75bba25d6d`
- expected fingerprint:
  `4bab47d250b739539c0c2f09786baa75bba25d6d:54e166f1c4c4a6378f987c6a7c4cde60fa390599888129924c68d8be33fa6f08`

Independently run:

```sh
git diff --binary 5b2b3232673fa7ee193efdcc6f80c4df82aa0fa9..4bab47d250b739539c0c2f09786baa75bba25d6d -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-execution-v1/status.json' | shasum -a 256
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
git diff --check
```

If the recomputed hash differs, return `BLOCKED`.

## Mandatory raw evidence

Read the following, the actual fixed diff, relevant current source, and frozen
borrow-task schemas. Do not rely only on summaries:

- `AGENTS.md`, `workflows/templates/stage-delivery.yaml` Review-2 node,
  `schemas/review-verdict.schema.json`, `docs/product/PRD.md`, and
  `docs/architecture/ARCHITECTURE.md`;
- `06-direction-synthesis.md`, `00-task.md`, `10-design.md`, `11-adr.md`,
  `12-development-breakdown.md`, `13-user-decisions-and-contract-amendment.md`;
- `20-implementation.md`, both task implementation reports, `60-test-output.txt`,
  `61-r4-diff-reconciliation.txt`, `62-pre-review-validation.txt`, and
  `63-review-2-preflight-validation.txt`;
- both raw formal Review-1 results: `30-review-1-backend.md` and
  `30-review-1-frontend.md`, plus `30-review-1.md`;
- `66-review-2-strong-reviewer-override.md`, `status.json`,
  `backend/borrow_tasks/**`, `backend/app/server.py`, `backend/config.py`,
  `schemas/api/borrow-tasks/**`, `frontend/index.html`, and
  `frontend/self-check.js`.

## Final acceptance focus

Decide whether the entire A+B delivery safely implements a durable local
borrow-task system while deliberately making **zero** Binance write/auth-read/
signing/credential/live-executor operations. Verify backend/frontend contract
alignment, creation-immediately-borrowing behavior, disabled executor ledger
truthfulness, decimal/microsecond discipline, transactional/restart safety,
unknown-outcome blocking, global decimal cadence, lifecycle/version/error
semantics, newest-first opaque-cursor logs, same-origin UI authority, no client
scheduler or fake success, test evidence, and preservation of existing
read-only snapshot/private behavior. Reassess the P3 observations from Review-1
and confirm they remain non-blocking under the approved product sources.

## Output contract

The adapter enforces `schemas/review-verdict.schema.json`, so return **only one
schema-valid JSON object**: no narrative outside it and no Markdown fence. The
object must be the final content, with no character after its closing `}`.

Use the allowed `reviewer_prior_involvement_notes` string for both the required
breakdown-involvement disclosure and the navigation footer, with these literal
labels and real values separated by newlines:

Current Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/50-review-2.md
本地北京时间: <obtain with local date command>
下一步模型: <model-or-human>
下一步任务: <specific next task>

Put substantive review reasoning in `findings`, `required_fixes`, and
`residual_risks`. The final JSON must include `schema_version: 1`, the exact
stage_id, `role: "final_reviewer"`, `model: "claude-fable-5"`, the exact
fingerprint, `reviewer_prior_involvement: "breakdown"`, reviewed_artifacts,
findings, required_fixes, and next_action. If verdict is `REWORK`, include a
ready-to-send `fix_start_prompt` that preserves every raw evidence path, each
finding, domain file boundaries, forbidden side effects, exact test commands,
and acceptance criteria. Do not use a prior Review-1 ACCEPT as a substitute for
this review.
