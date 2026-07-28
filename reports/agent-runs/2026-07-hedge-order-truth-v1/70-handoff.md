# Handoff — Hedge Order Truth And Error Fidelity v1

## Recovery Header

```text
stage_id:        2026-07-hedge-order-truth-v1
status:          designing
stage_branch:    stage/2026-07-hedge-order-truth-v1
branch_base:     ecc38418f52b525eb61bf1c72b9b2b41c26130ef (local main)
current_branch:  stage/2026-07-hedge-order-truth-v1
head:            see git; intake commit only
worktree:        clean at intake
rework_count:    0 / 3
next_action:     human operator runs 10-design-and-breakdown.dispatch.md in a
                 fresh Claude Fable 5 session
next_model:      claude (Fable 5, backup Opus 4.8)
blockers:        none
```

⚠️ **Live surface is OPEN this stage.** Service PID 96409 running in live mode,
durable Start gate `start_gate=1` (version 4), 3 paused cards in the database,
and a real naked SHORT 10000 NOMUSDT (orderId 888412130) outstanding with no
close function. The user was offered closing the gate and stopping the service
and chose to leave both. **No agent may create a card, press Start, place an
order, touch credentials, start/stop the service, or write to
`data/hedge-open-tasks.sqlite3`.** Read-only queries for evidence are fine.

## What this stage is

The previous stage made a real order succeed. This one makes the *record* of it
true. Four defects, three from the standing proposal and one found at intake,
all the same shape: a plausible value substituted for information the system
had or could have fetched.

| Id | Sev | What is wrong today |
| --- | --- | --- |
| T1 | P0 | A leg that filled 10000 NOMUSDT recorded a notional of `0` — Binance removed `cumQuote`/`avgPrice` from UM/CM responses on 2026-07-14 and `_decimal_str(None)` returns `"0"` |
| T2 | P1 | `51169` recorded `error_category = NULL` — the code tables hold only negative literals, so no margin-endpoint code can match |
| T3 | P1 | Binance's own words are discarded; there is no column for them and no raw payload is stored anywhere |
| T5 | P1 | The live exposure record is timestamped `1970-01-01` — `service.py:1688` hardcodes `0`; the dry-run path passes a real timestamp, which is why offline tests miss it |
| T4 | P2 | `51169`'s root cause is undetermined; gated on a user-authorized discriminator order before any preflight change |

Primary evidence is `01-live-record-evidence.md` — raw rows read from the
production database at intake. It outranks every narrative in this stage,
including this file.

## Routing, and the one thing to know about it

| Role | Provider | Model |
| --- | --- | --- |
| Designer + breakdown | `claude` | Fable 5 (Opus 4.8 on quota exhaustion) |
| Implementer | `claude_glm` | `glm-5.2[1m]` |
| Review-1 | `codex` | GPT-5 Codex |
| Review-2 | `codex` | GPT-5 Codex |
| Bookkeeper | `claude` | Opus 5 (no delivery code) |

**Review-1 and Review-2 are the same model this stage.** The user chose Codex
for Review-1; AGENTS.md then allowed only Codex-again or Claude at the final
gate, and Claude was needed for design. Every hard gate holds — both reviewers
are provider-isolated from the implementer and Review-2 has no design
involvement, so no waiver or disclosure override is claimed. What is lost is
independence: the final gate largely re-confirms its own earlier reading.

Full reasoning and the binding mitigations: `15-user-authorized-codex-review-1.md`.
The mitigations are not optional — whoever prepares the review packets must
apply them:

1. Two distinct fresh read-only sessions, no shared transcript.
2. Review-2's packet points at `00-task.md` as top authority, not `10-design.md`.
3. Review-2's packet discloses that Review-1 was the same provider and tells the
   reviewer to treat its own prior verdict as unproven.
4. Review-1's verdict is committed before Review-2 is dispatched.

## Settled decisions — do not re-litigate

- **`single_leg_exposure` stays ADVISORY** (user, 2026-07-28). A single-leg
  outcome does not pause the task, even though a real naked position resulted.
  T2 must not change this.
- **The live surface stays open** (user, 2026-07-28). Not a defect; not this
  stage's to close.
- **T4 does not touch the preflight** until its discriminator has run. Fixing it
  against an unproven cause is how the current gate was written.

## Open items the design must resolve

- T1: authoritative source for UM/CM fill figures, and **when** the read happens
  (today a leg is never queried after dispatch).
- T1(e) + T5(d): what to do about the historical rows already holding `0` and
  `1970`. Must be a tested one-off migration in code if anything — no manual SQL.
- T2: the structural rule for positive codes, and keeping unrecognised codes
  distinguishable from recognised ones.
- T3: storage shape, retention, redaction.
- Whether `p3-preflight-snapshot-key-contract-untested` (carried from the
  previous stage) is cheap enough to fold in.

## Sequence from here

1. ▶ Human operator runs `10-design-and-breakdown.dispatch.md` → `10-design.md`,
   `11-adr.md`, `12-development-breakdown.md`.
2. Bookkeeper archives them, sets file boundaries in `status.json`, prepares the
   implementation packet.
3. Human operator runs the implementation packet in Claude-GLM.
4. Bookkeeper verifies boundaries, commits evidence, computes the fingerprint,
   runs `scripts/validate-stage.py 2026-07-hedge-order-truth-v1 --phase pre-review`.
5. Review-1 (Codex, fresh read-only session) → Review-2 (Codex, second fresh
   session) → `stage_accepted_waiting_user`.
6. T4's discriminator is a separate user authorization and can be requested at
   any point after the design exists; if declined, T4 defers as a follow-up.

Merge to `main` only after explicit user acceptance. Note `main` itself is not
pushed — the previous two stages are merged locally only.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/70-handoff.md
本地北京时间: 2026-07-28 07:26:35 CST
下一步模型: human operator
下一步任务: 在全新的 Claude Fable 5 终端执行 10-design-and-breakdown.dispatch.md
