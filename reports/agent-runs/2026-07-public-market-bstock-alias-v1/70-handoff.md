# Handoff: Public Market bStock Alias Amendment V1

## Stage start: contract amendment + backend/frontend repair of the bStock B-suffix alias

Stage `2026-07-public-market-bstock-alias-v1` closes the impl-v1 post-review P1
finding `bstocks_b_suffix_spot_margin_alias`. impl-v1 accepted against the
FROZEN `public-market-contract-v2`; the bStock alias case was found AFTER
review-2, so this is a **contract amendment** (not a rework of the frozen
contract). impl-v1's review-2 verdict is NOT altered.

The amendment promotes the alias rule into:
- `schemas/api/public-market/snapshot.schema.json` — new `spot.match_type` field.
- `docs/api/public-market-contract.md` — descriptive note → frozen amendment rule.
- `backend/domain/normalize.py` — `resolve_spot_leg` pure function (exact →
  bStock B-suffix alias → none).
- `backend/domain/snapshot.py` — `build_rows` uses `resolve_spot_leg`, fills
  `match_type`, updates `CONTRACT_WARNINGS[2]`.
- `frontend/**` — futures symbol vs actual spot symbol + match source.
- `backend/tests/**` + synthetic `bstock-alias-raw/` fixture.

**Semantic core**: `classify.py` is NOT changed. The existing
`negative_funding_status` priority (PERP_ONLY → BSTOCK → SPOT_ONLY →
PRIVATE_BORROW) already yields `MARGIN_SPOT_CANDIDATE` + `DISABLED_BSTOCK` for
a bStock with a margin-allowed spot leg, once the correct spot symbol reaches
`classify_route`. The real fix is the spot-leg join.

## Fable5 breakdown UNAVAILABLE → controller-direct design

The plan called for Fable5 (`claude-fable-5`, anthropic) to author
`fable5-detail-breakdown.md`. Runner-level probe failed: the local `claude` CLI
auth routes to `zhipu_glm`, so `--model claude-fable-5` returns error 1211
(模型不存在); the claude.ai login is overridden. Evidence:
`fable5-detail-breakdown.unavailable.md`. Per the approved plan's `[可调整]`
clause, the controller authors the design record directly (`00-task.md`,
`10-design.md`, `11-adr.md`); `user_approved_lightweight_route=true`. Fable5 is
re-runnable if an Anthropic-authed environment is provided. Review-1 and
review-2 still run as independent gates. This SIMPLIFIES review-2 disclosure:
Fable5 has no involvement, so the only prior involvement is Codex
(`direction_synthesis`).

## Task boundaries (from 00-task.md)

- Task A — contract amendment + backend repair. Owner Claude-GLM. Writes
  `schemas/api/public-market/snapshot.schema.json`,
  `docs/api/public-market-contract.md`, `backend/domain/{normalize,snapshot}.py`,
  `backend/tests/**`, `backend/tests/fixtures/bstock-alias-raw/**`,
  `20-implementation-backend.md`. (`classify.py` forbidden.)
- Task B — frontend display. Owner Kimi. Writes `frontend/**` +
  `20-implementation-frontend.md`. Depends on Task A freezing `match_type`.
- Task C — integration verification. Owner controller. No product code.

A boundary crossing is REWORK regardless of code quality.

## Commit-order strategy (keeps task fingerprints clean)

Same as impl-v1. Serial commits so each task's `base..head` diff is
owner-scoped:

1. `H_intake` — stage evidence (intake, task, design, ADR, status, handoff,
   Fable5 unavailable record). This is the task base. **THIS COMMIT.**
2. `H_A` — Task A: amendable contract schema/doc + `backend/**` + tests +
   `20-implementation-backend.md` + `60-test-output.txt` (Task A). Task A
   `base_sha=H_intake`, `head_sha=H_A`. NEXT.
3. `H_B` — Task B: `frontend/**` + `20-implementation-frontend.md`. Task B
   `base_sha=H_A checkpoint`, `head_sha=H_B`.
4. `H_C` — Task C: `20-implementation.md` + `60-test-output.txt` Section 4 +
   integration sample + final `status.json`/handoff. Stage-level top-level
   `base_sha=H_intake`, `head_sha=H_C`.

Same fingerprint formula at both scopes; no second protocol.

## Evidence policy (controller == contract+backend implementer)

Controller and Task A implementer share provider (`claude_glm`). Mitigations
(recorded in `status.json.evidence_policy`): reviewers recompute
`diff_fingerprint` from raw `base..head`; test output is replayable raw
command output; review prompts pass raw artifact and raw diff paths, not
controller summaries; Task B review-1 uses a fresh read-only Claude-GLM session
(not the controller/Task A transcript).

## Review routing (planned)

- Task A review-1: Kimi (`code_reviewer`, read-only) → `30-review-1-backend.md`.
- Task B review-1: fresh read-only Claude-GLM → `30-review-1-frontend.md`.
- Stage review-2: Codex/GPT (`codex`, gpt5.5 xhigh). Codex is the prior
  direction_synthesizer (covers this stage); Fable5 unavailable; both
  implementers (`zhipu_glm`, `kimi`) barred from review-2. Codex reviews via
  the `direction_synthesis` strong-reviewer override.
- Grok excluded from implementation and review.

## Branch / state

- Branch: `main` (local only, ahead of origin). Current HEAD `35e032a`
  (impl-v1 bStock finding record); `H_intake` commits on top.
- `status.json` is the authoritative machine state; this handoff is a human
  navigation aid.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller / Task A implementer)
下一步任务: Commit `H_intake` (stage evidence), then implement Task A (contract amendment + `resolve_spot_leg` + `build_rows` + synthetic fixture + tests) → `H_A`.
