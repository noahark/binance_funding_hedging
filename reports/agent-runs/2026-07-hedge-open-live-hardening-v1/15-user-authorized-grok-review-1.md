# User Authorization — Grok As The Review-1 Gate (Both Tasks)

## Why this record exists

`AGENTS.md` Hard Gates: *"Review-1 uses the configured cross-review pool. Grok is
not a default review gate and must not be substituted into review-1 unless the
user explicitly enables it for the stage."*
`agents/registry.yaml` repeats it under `adapters.grok.notes`: *"Do not silently
substitute Grok Build for cross-review review-1."*

This file is that explicit stage-level enablement. Without it the routing below
would fail closed.

## The decision

- **Authorizer**: user
- **At**: 2026-07-27, during the implementation phase of this stage
- **Decision**: both Review-1 gates — backend and frontend — are routed to
  **Grok**, in two separate fresh read-only sessions.
- **Supersedes**: the Claude Opus 4.8 Review-1 routing recorded earlier the same
  day, which itself replaced the original GLM↔Kimi cross pool after Kimi's quota
  failed to recover.

## How it got here

1. Intake routing: backend → `claude_glm`, frontend → `kimi`; Review-1 crossed
   between them; Review-2 → `codex`.
2. Kimi quota did not recover. Both implementation tasks moved to `claude_glm`,
   which made the GLM↔Kimi cross pool unusable.
3. First replacement: both Review-1 gates → Claude Opus 4.8 (Anthropic wrote no
   delivery code this stage, so isolation from the implementer held), with the
   designer-overlap disclosed.
4. The user reported Grok quota is available and chose to route **both** Review-1
   gates to Grok instead.

## The tradeoff, as presented to the user before the choice

Recorded verbatim in substance, so a later reviewer can see the decision was
informed rather than accidental:

- **Against**: Grok has never run a review gate in this repository, so its
  ability to emit a verdict conforming to `schemas/review-verdict.schema.json`
  is unverified. Invalid verdict JSON is non-accepting evidence and forces a
  retry, and this is the round that fixes a P0 blocking all real trading.
  Putting both gates on one unverified channel concentrates that risk.
- **For**: it removes the concentration of the Anthropic provider acting as both
  designer/breakdown author and both Review-1 reviewers, and gives the stage a
  genuinely independent third provider identity.

The user chose to route both gates to Grok. That is their call to make and this
stage proceeds on it.

## Identity check

- Implementers: `claude_glm` (`zhipu_glm` identity), both tasks.
- Review-1: `grok` (`xai_grok` identity) — different provider identity from the
  implementer, so provider-level cross-review isolation holds for both tasks.
- Review-1 reviewers have no design involvement in this stage (design, ADR and
  breakdown were authored by Claude Fable 5), so the earlier designer-overlap
  disclosure no longer applies to Review-1.
- Review-2: `codex` — unchanged, still zero prior involvement, still no
  strong-reviewer disclosure override needed.

## Operating conditions attached to this authorization

1. **Two separate sessions.** One Grok session must not review both tasks. Each
   reviews only its own task's diff range.
2. **Read-only.** The review command must be the adapter's read-only form
   (`--permission-mode plan`, per `agents/registry.yaml`
   `adapters.grok.optional_review_command`). A reviewer that writes files
   invalidates its own review.
3. **Exact model must be recorded.** `agents/registry.yaml` lists only
   `grok-build` and `grok-composer-2.5-fast` as observed models; the user
   referred to "Grok 4.5". Before dispatch the human operator runs
   `grok models` and the bookkeeper records the exact model id actually used in
   `status.json.review_1_dispatch_plan` and the session receipt. No guessed
   model id enters the record.
4. **Strict verdict JSON.** The dispatch prompt must carry the anti-relay
   preamble and demand a verdict conforming to
   `schemas/review-verdict.schema.json`. If a verdict is missing or invalid,
   that attempt is non-accepting: retry once, and if it fails again, fall back
   to Claude Opus 4.8 for that gate and record the fallback reason and evidence
   path. This fallback is pre-authorized by this record so the stage does not
   stall.
5. **No live authority.** Reviewers touch no credentials, place no orders, start
   no service, and do not alter the Start gate. The live surface stays closed
   (service stopped, `start_gate=0`).

## Status

Not yet dispatched. Both implementation tasks are still running; Review-1
packets are prepared only after the implementers stop and the bookkeeper
completes R4 reconciliation, the merged-state test rerun, the evidence commit
and the fingerprint.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/15-user-authorized-grok-review-1.md
本地北京时间: 2026-07-27 18:55:00 CST
下一步模型: human operator
下一步任务: 等两个实现会话停手；出 review-1 packet 前先跑 `grok models` 确认确切模型 id
