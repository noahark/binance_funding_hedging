# Handoff: Public Market Implementation V1

## Checkpoint: Review-1 COMPLETE — Task A→Kimi ACCEPT, Task B→fresh Claude-GLM ACCEPT; stage review-2 next

Task-level review-1 is complete and both verdicts are ACCEPT, schema-valid,
with fingerprints independently recomputed and matching `status.json`, and
zero findings / zero rework:

- Task A (backend, implementer `claude_glm`) → reviewer Kimi (`kimi-2.7`):
  `30-review-1-backend.md`. Recomputed `5148a473…1e93` == recorded. 21-file
  boundary clean. 10/10 behavior-rule checkpoints pass. Independent rerun:
  39 pytest passed + SMOKE OK. `float()` audit clean.
- Task B (frontend, implementer `kimi`) → reviewer fresh read-only
  Claude-GLM (`glm-5.2[1m]`, `--no-session-persistence`, not the controller
  transcript): `30-review-1-frontend.md`. Recomputed `4bebeb52…6bde` ==
  recorded. 4-file boundary clean. 8/8 checkpoints pass. Independent rerun:
  `node frontend/self-check.js` 10/10 PASS. Fresh session confirmed (no
  "Restored session" in raw-output).

Both verdict JSON objects validate against `schemas/review-verdict.schema.json`.
Next: commit review-1 evidence, then stage-level review-2 (Codex/GPT), then
`pre-accept`. The controller does not declare final acceptance.

The original Tasks-A+B+C-implemented checkpoint (now superseded) follows for
historical navigation.

Status: `implementing`. `H_intake` (`32f6f0f`), `H_A` backend (`a40b204`), and
`H_B` frontend (`c1e33b6`) are committed with task-level fingerprints recorded
in `status.json.tasks.{A,B}`. Task C integration verification passed
(`60-test-output.txt` Section 4, INTEGRATION OK); the stage-level summary
(`20-implementation.md`) and integration sample are staged for `H_C`. Next:
commit `H_C`, fill the stage-level top-level fingerprint, and dispatch
task-level review-1 (A→Kimi, B→fresh read-only Claude-GLM). The controller
does not declare final acceptance (`can_accept_final: false`); only
schema-valid task-level review-1, stage-level review-2, and `pre-accept`
advance the stage.

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
   **DONE: `32f6f0f`.**
2. `H_A` — Task A: `backend/**` + `20-implementation-backend.md` +
   `60-test-output.txt` (Task A pytest + smoke). Task A `base_sha=H_intake`,
   `head_sha=H_A`. **DONE: `a40b204`; fingerprint
   `a40b204…d72:5148a473…1e93`; tests pass (39 pytest + float audit + smoke).**
3. `H_B` — Task B: `frontend/**` + `20-implementation-frontend.md`. Task B
   `base_sha=fc018ea` (Task-A checkpoint), `head_sha=H_B`. **DONE: `c1e33b6`;
   fingerprint `c1e33b6…414:4bebeb52…6bde`; Node self-check 10 PASS.**
4. `H_C` — Task C: `20-implementation.md` (stage summary) +
   `60-test-output.txt` Section 4 + `integration-snapshot-*.json` + final
   `status.json`/handoff. Stage-level top-level `base_sha=H_intake`,
   `head_sha=H_C`. NEXT.

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

本地北京时间: 2026-07-03 22:03 CST
下一步模型: Codex/GPT (review-2)
下一步任务: Commit review-1 证据（30-review-1-{backend,frontend}.md + 两个 raw-output + status + handoff）→ 派发阶段级 review-2（Codex/GPT，无关决策审查者；设计者 Fable5 已披露；两个实现者 claude_glm/kimi 均禁止 review-2）→ pre-accept（validate-stage.py）。Controller 不声明最终验收。
