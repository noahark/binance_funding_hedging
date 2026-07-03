# Stage Intake: 2026-07-public-market-bstock-alias-v1

- Stage ID: `2026-07-public-market-bstock-alias-v1`
- Stage type: contract amendment + implementation repair. Promotes the
  post-review bStock B-suffix spot/margin alias finding (P1) from a descriptive
  note into a frozen contract amendment, a backend classification repair, a
  frontend display update, and tests.
- Controller: Claude-GLM (`glm-5.2[1m]`, provider `claude_glm`), via the local
  `claude-glm` adapter. The controller is also the Task A (contract + backend)
  implementer and the Task C integration verifier, so this stage keeps the
  `controller_and_backend_implementer_same_model` evidence policy from prior
  stages.
- Prerequisite stage: `2026-07-public-market-impl-v1` — dual-reviewed ACCEPT and
  `stage_accepted_waiting_user` (head `b8048f9`), but with an OPEN post-review
  P1 finding `bstocks_b_suffix_spot_margin_alias` (evidence commit `35e032a`,
  `reports/agent-runs/2026-07-public-market-impl-v1/post-review-bstocks-alias-finding.md`).
  This stage closes that finding.

## Why a new stage (not a hotfix on impl-v1)

impl-v1 reviewed and accepted against the FROZEN `public-market-contract-v2`.
The bStock alias case was discovered AFTER review-2, so it is a contract
amendment, not a rework of the frozen contract. impl-v1's review-2 verdict
stands for the contract it reviewed and is NOT altered. This stage formally
amends the contract (`snapshot.schema.json` + `public-market-contract.md`),
repairs the backend spot-leg join, updates the frontend, and re-runs
independent review-1/review-2 before asking the user for final acceptance.

## Complexity classification

- Classification: **MEDIUM**.
- Direction panel required: **false**. The user-approved direction synthesis
  (`2026_07_initial_direction`) covers Phase 1 public market discovery, and the
  user explicitly specified the 6 amendment points.
- `existing_synthesis_covers_task`: true.
- `user_approved_lightweight_route`: true (the user started this stage with a
  precise 6-point amendment spec; Fable5 breakdown unavailable → controller-
  direct design, see below).
- Rationale:
  - No new product direction; the amendment is a localized rule addition
    (bStock B-suffix alias + `spot.match_type`).
  - Multi-task (contract+backend / frontend / integration), so design is
    recorded before coding.
  - No new human gate: public data only, `127.0.0.1` binding, no keys, no
    order/borrow/repay/transfer paths.

## Direction panel

- Panel key: not run this stage. The active milestone direction
  (`2026_07_initial_direction`) was approved in prior stages and covers Phase 1.
- Synthesis: `approved_prior_stage` (Codex/GPT synthesis already user-approved).

## Development breakdown (design involvement)

- Intended breakdown author: Claude/Fable5 (`claude-fable-5`, provider
  `anthropic`) — **NOT reachable this session**. Runner-level check failed (see
  `fable5-detail-breakdown.unavailable.md`): the local `claude` CLI auth routes
  to `zhipu_glm`, so `--model claude-fable-5` returns error 1211 "模型不存在";
  the claude.ai login is overridden by the configured auth source.
- Fallback (approved plan `[可调整]`): **controller-direct design**. The
  controller authors `00-task.md` + `10-design.md` + `11-adr.md` as the design
  record. `complexity.user_approved_lightweight_route = true`. Fable5 is
  re-runnable if an Anthropic-authed environment is provided.
- Design-involvement consequence: this stage's designer/breakdown author is the
  controller (`claude_glm`), also the Task A implementer (review-2 hard-banned).
  Fable5 has no involvement. Review-2's only prior involvement is Codex
  (`direction_synthesis`).
- Task split: Task A (contract amendment + backend, Claude-GLM), Task B
  (frontend, Kimi), Task C (integration verification, controller, no product
  code).

## Human gates

- None beyond standing Harness gates. Public REST data only; `127.0.0.1`
  binding; no credentials, no signed endpoints, no account endpoints, no
  execution paths.

## Model routing summary (full record in status.json)

- Contract + backend owner: Claude-GLM (`claude_glm`) — Task A.
- Frontend owner: Kimi (`moonshot_kimi`) — Task B.
- Review-1 (task-level, cross-review): Task A → Kimi; Task B → a fresh
  read-only Claude-GLM session (not the controller/implementer transcript).
- Review-2 (stage-level, final gate): prefer Codex/GPT (`codex`). Codex is the
  prior direction synthesizer (covers this stage); Fable5 is unavailable;
  both implementers hard-banned from review-2.
- Grok excluded from implementation and review.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller)
下一步任务: Freeze `00-task.md` boundaries + `10-design.md` / `11-adr.md`, then build `status.json` task records and commit `H_intake`.
