# Handoff: Public Market Implementation V1

## Checkpoint: stage started, building evidence + dispatching tasks

Status: `implementing`. Stage evidence is being committed as the task base
(`H_intake`); Task B (frontend) is dispatched to Kimi; Task A (backend) is
implemented by Claude-GLM (the controller). The controller does not declare
final acceptance (`can_accept_final: false`); only schema-valid task-level
review-1, stage-level review-2, and `pre-accept` advance the stage.

Prerequisite stage `2026-07-public-market-contract-v2` is ACCEPT and frozen
(head `a25e431`, `diff_fingerprint` `53484d21…`). The frozen contract doc, the
JSON schema, the frozen raw samples, and the frozen normalized sample are
read-only inputs to this stage.

Implementers: Claude-GLM (`claude_glm`, Task A backend) and Kimi
(`moonshot_kimi`, Task B frontend). Breakdown author / stage designer of record:
Claude/Fable5 (`anthropic`, `fable5-detail-breakdown.md`) — design involvement
for review-2 disclosure.

## Task boundaries (from 00-task.md / fable5-detail-breakdown.md)

- Task A — backend snapshot service. Owner Claude-GLM. Writes `backend/**` and
  `20-implementation-backend.md`. Serves `GET /api/public-market/snapshot`
  (schema-validated, 503 on invalid) and statically hosts `frontend/` at `/` on
  `127.0.0.1`.
- Task B — frontend market table. Owner Kimi. Writes `frontend/**` and
  `20-implementation-frontend.md`. Consumes only the same-origin snapshot
  endpoint + a byte-copy fixture.
- Task C — integration verification. Owner controller. No product code. Curls
  the endpoint, validates against the schema, loads the page; output in
  `60-test-output.txt`.

A boundary crossing is REWORK regardless of code quality.

## Commit-order strategy (keeps task fingerprints clean)

Implementers may work in parallel, but commits are serialized by the controller.
The frozen fingerprint formula is fixed (whole-tree diff except `status.json`),
so a clean per-task diff requires that each task's `base..head` not contain the
other task's files. The controller achieves this by committing in order:

1. `H_intake` — stage evidence (intake, task, design, ADR, status, handoff,
   Task B dispatch prompt, the Fable5 breakdown). This is the task base.
2. `H_A` — Task A: `backend/**` + `20-implementation-backend.md` +
   `60-test-output.txt` (Task A pytest). Task A `base_sha=H_intake`,
   `head_sha=H_A`.
3. `H_B` — Task B: `frontend/**` + `20-implementation-frontend.md`. Task B
   `base_sha=H_A`, `head_sha=H_B`. **Kimi writes frontend into the worktree and
   does NOT `git commit`; the controller commits Task B** so the order holds.
4. `H_C` — Task C: integration evidence + final `status.json`/handoff update.
   Stage-level top-level `base_sha=H_intake`, `head_sha=H_C`.

Same fingerprint formula at both scopes; no second protocol
(see `11-adr.md` ADR-6).

## Evidence policy (controller == backend implementer)

Controller and Task A implementer share provider (`claude_glm`). Mitigations,
recorded in `status.json.evidence_policy`: reviewers recompute `diff_fingerprint`
from raw `base..head`; test output is replayable raw command output; review
prompts pass raw artifact and raw diff paths, not controller summaries; Task B
review-1 uses a fresh read-only Claude-GLM session (not the controller/Task A
transcript).

## Review routing (planned)

- Task A review-1: Kimi (`code_reviewer`, read-only) → `30-review-1-backend.md`.
- Task B review-1: fresh read-only Claude-GLM → `30-review-1-frontend.md`.
- Stage review-2: Codex/GPT (`codex`). Codex has no design involvement this
  stage (the designer is Fable5), so it is the unrelated decision reviewer; no
  disclosure override needed unless Codex is unavailable. Both implementers
  (`zhipu_glm`, `kimi`) are barred from review-2.
- Grok excluded from implementation and review.

## Branch / state

- Branch: `main` (local only, ahead of origin). Working tree carries this
  stage's evidence (untracked until `H_intake`).
- `status.json` is the authoritative machine state; this handoff is a human
  navigation aid.

本地北京时间: 2026-07-03 20:36:32 CST
下一步模型: Claude-GLM (controller)
下一步任务: Commit stage evidence (H_intake, the task base), dispatch Task B to Kimi, then implement Task A backend.
