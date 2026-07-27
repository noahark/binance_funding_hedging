# User Acceptance — Hedge Open Live Hardening v1

- **Accepted by**: user
- **At**: 2026-07-28
- **Decision**: accept the stage and merge it to `main`.

## What is being accepted

The pinned range `6c5b17002cab189d752177b447ff576356998f58 ..
c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8`, fingerprint
`c91d2da5fe38c8b8ecf6bd3fb6c3ee9e0141a3c8:aad2351a429714f07e759304400087c2f0a5ccc33a0111b9532153bf86c50b23`.

Five items delivered:

- **S1 (P0)** clientOrderId → `hg{attempt_id}s|p`, fixed 35 chars. **Proven in
  production** during the 2026-07-27 acceptance run: both legs passed Binance's
  format validation and the perp leg filled. The `-4015` that blocked every
  order is gone.
- **S2 (P1)** a freshly created card can be started in live mode — called as a
  pure frontend button-condition defect; backend unchanged; dry-run behaviour
  byte-identical.
- **S3 (P2)** the Start gate has an operator entry point: symmetric confirmation
  dialog, `confirm` literal checked server-side, `version` CAS with a 409 path,
  and an audit row in the same transaction as the gate flip. **Proven in
  production**: the gate was opened through the control, not by SQL.
- **S4** worker state and exit reason displayed with the frozen Chinese map; a
  tri-state leg-existence probe refuses card creation only when the read
  genuinely succeeded.
- **S5** a standalone offline validator wired into the record transport and the
  strict test fake, now including the loaded symbol filters' step/min/max, with
  a regression proving the pre-fix S1 derivation fails offline.

Plus one confirmed side-finding: the design's "unverified" `str(Decimal)`
concern was **real** — it can emit `1E-7` — so the params seam now uses
`fmt_decimal`.

## Gate record

| Gate | Model | Verdict | Findings |
| --- | --- | --- | --- |
| Frontend Review-1 | grok-4.5 | ACCEPT | 0 P0/P1/P2, 2 P3 |
| Backend Review-1 (round 1) | grok-4.5 | ACCEPT | 0 P0/P1/P2, 2 P3 |
| Review-2 (round 1) | GPT-5 Codex | **REWORK** | 1 P2 |
| Backend Review-1 (round 2) | grok-4.5 | ACCEPT | 0 |
| Review-2 (round 2) | GPT-5 Codex | **ACCEPT** | 0 |

`rework_count` 1 of 3. `pre-accept` PASSED with **zero authorized exceptions
applied**.

Two things the user was shown before accepting, both recorded rather than
smoothed over:

1. **Routing deviation**: the round-2 backend Review-1 packet specified Claude
   Opus 4.8 and was executed on grok-4.5. The hard gate holds (`xai_grok` ≠ the
   implementer's `zhipu_glm`; grok review-1 is user-enabled), but it departed
   from the routing the user had chosen after grok's earlier severity miss.
   Mitigated by Codex, a third provider, independently reviewing the same range.
   Full record: `status.json.review_1_routing_deviation`.
2. **The class-1 frontend exception was never applied.** It was authorized, but
   the coverage-waypoint structure made it unnecessary — the frontend ACCEPT is
   honoured on its own merits. The record stays pinned and dormant.

## What acceptance does NOT grant

Merging to `main` is **not** live authorization. All three remain separate
human authorizations, none of them given here:

1. `APP_HEDGE_EXECUTOR=live`
2. the durable Start gate
3. the first real task

## Live state at acceptance — user-owned, not stage defects

- The **Start gate is OPEN** (`start_gate=1`), opened through the new S3 control
  during the 2026-07-27 acceptance run and deliberately left open at the user's
  instruction.
- A real **naked SHORT 10000 NOMUSDT** (orderId `888412130`) is outstanding and
  unhedged. The system has no close function — that is the third stage of the
  hedge programme and is not built. Unwinding is a manual action on Binance.

## Carried forward, not fixed here

Five P3 follow-ups in `status.json.stage_followups`. The sharpest: **no test
locks the key-name contract** between `compute_preflight` (which writes
`{leg}_min_qty` / `{leg}_max_qty`) and `_leg_qty_filters` (which reads them). A
future rename would leave the suite green while the filter checks silently stop
applying — the same silent-downgrade shape this stage kept running into.

Separately, the 2026-07-27 run surfaced four defects outside this stage's scope
(`18-live-acceptance-findings.md`), proposed as stage
`2026-07-hedge-order-truth-v1`
(`_proposals/2026-07-27-hedge-order-truth-and-error-fidelity.md`), including the
user's requirement to persist raw order-placement responses and full
order-detail reads.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/80-user-acceptance.md
本地北京时间: 2026-07-28 01:35:00 CST
下一步模型: bookkeeper
下一步任务: no-ff 合并到本地 main 并记录 merge sha
