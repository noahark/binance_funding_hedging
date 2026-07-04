# Handoff: Public Market Implementation V1

## Post-Review New Finding: bStocks B-Suffix Alias Blocks Final User Acceptance

After review-2 accepted this stage against the frozen contract, a live Binance
check confirmed a new bStocks case not covered by `public-market-contract-v2`.
Futures TRADIFI symbols use the non-`B` equity symbol (`TSLAUSDT`, `MSTRUSDT`,
`NVDAUSDT`), while the newly supported bStocks spot/margin assets use a `B`
suffix (`TSLABUSDT`, `MSTRBUSDT`, `NVDABUSDT`). The current backend joins spot
by exact symbol, so the 15 announced bStocks still classify as
`PERP_ONLY_EXCLUDED` with `spot.symbol=null`.

Evidence and required amendment are recorded in
`post-review-bstocks-alias-finding.md`. The `review-2` verdict remains valid for
the frozen reviewed contract, but user final acceptance should wait until a
follow-up contract amendment and implementation repair add the bStock
`baseAsset + "B" + quoteAsset` spot-leg alias rule, dynamic collateral fields,
and frontend display of futures symbol vs actual bStock spot symbol.

## Checkpoint: Review-2 COMPLETE (Codex ACCEPT, final gate) — all gates passed; pre-accept next

Stage-level review-2 (final gate) is complete: Codex/GPT (gpt-5.5, xhigh,
provider proxy2233, read-only sandbox) returned **ACCEPT**, schema-valid, with
the stage `diff_fingerprint` `7fdbbf17…ce0e` independently recomputed and
matching, all three task fingerprints matching, task boundaries clean, and
every backend/frontend/integration checkpoint passing — zero findings, zero
rework. `reviewer_prior_involvement = direction_synthesis` (Codex was the prior
direction synthesizer for the covering contract-v2; strong-reviewer disclosure
override invoked; implementer/fix-author hard ban satisfied). Independent test
rerun by Codex: `node frontend/self-check.js` PASS;
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest backend/tests -q` 39/39.

Schema-bound `--output-schema` was unavailable (review-verdict.schema.json's
optional fields are incompatible with OpenAI strict response_format), so per
AGENTS.md Codex ran free-form and the controller jsonschema-validated the
emitted verdict (PASS). Details: `50-review-2.md` + `review-2-codex.raw-output.txt`.

All Harness gates now pass (`validate-stage.py --phase pre-review` PASSED).
Next: `validate-stage.py --phase pre-accept`. The controller holds the stage at
`stage_accepted_waiting_user` and does **NOT** declare final acceptance
(`can_accept_final: false`) — awaiting user final acceptance.

The review-1 checkpoint (already complete) follows for historical navigation.

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

本地北京时间: 2026-07-03 22:28 CST
下一步模型: 用户 (final acceptance)
下一步任务: validate-stage.py --phase pre-accept（已提交 review-2 证据，status.json/70-handoff.md 待最终 commit）→ 阶段停在 stage_accepted_waiting_user，等待用户最终接受（controller 不声明 accepted，can_accept_final=false）。所有 gate 已通过：review-1（Task A→Kimi ACCEPT + Task B→fresh Claude-GLM ACCEPT）+ review-2（Codex/GPT gpt5.5 xhigh ACCEPT，final_reviewer，direction_synthesis 披露 override）。review-2 evidence commit: c9f8788。

---

## User final acceptance (2026-07-04)

用户于 2026-07-04 11:47 CST 对 impl-v1（head `ce00489`）与
`2026-07-public-market-bstock-alias-v1`（最终 head `548ae0d`，含 evidence
backfill 与 rework round 1）一并给出最终验收。`status=accepted`。
P1 finding `bstocks_b_suffix_spot_margin_alias` 的 `resolved_by_stage` 引用按
verbatim 保留纪律停在关闭时点 head `0842820`；alias 闭环已在 548ae0d 由该阶段
rework review-2 + live-raw 重放再次确认。pre-accept 校验输出留档于
`pre-accept-validation-final.txt`。本阶段终结；下一轮多模型方向盘启动新阶段。
