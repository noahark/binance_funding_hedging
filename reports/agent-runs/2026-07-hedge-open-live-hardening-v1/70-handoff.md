# Handoff — Hedge Open Live Hardening v1

## Recovery Header

- Active phase: `DESIGN DISPATCH PREPARED — the S3 decision is closed; 10-design-and-breakdown.dispatch.md awaits human execution. No implementation dispatched.`
- Stage branch: `stage/2026-07-hedge-open-live-hardening-v1`, created from `main` at `4ce968623ff6cf1b574539437871064ca69b9f2d`.
- Bookkeeper: Claude Opus 5, independent session, writes no delivery code.
- Complexity: `MEDIUM`, direction panel skipped with user approval (2026-07-27); inherits `2026-07-hedge-open-real-api-v1/06-direction-synthesis.md`.
- Reviewer pool restored on 2026-07-27: `codex`, `claude_glm`, `kimi`, `claude`.
- Live surface is CLOSED: service PID 15780 stopped at 17:32, `start_gate = 0` (version 3), backup taken before the write.

## Why This Stage Exists

`2026-07-hedge-open-real-api-v1` was accepted and merged, then its first real
order was **sent and rejected** by Binance on 2026-07-27. Everything that only a
real send can prove — credentials, signing, six read-only preflight endpoints,
symbol filters, `q_common` derivation, concurrent two-leg submit, rejection
handling, reconciliation, settlement — behaved correctly. The chain fails at the
last inch: `clientOrderId` is 38 chars against a 36-char cap.

That stage's `70-handoff.md` §First live run and
`status.json.live_first_run_findings` hold the full evidence, including the
live DB task id and error codes. Read those before touching S1.

## Scope

Five items, all recorded in `00-intake.md` with anchors, and in `00-task.md`
with acceptance criteria:

- **S1 (P0)** `clientOrderId` ≤ 36 — nothing can trade until this lands.
- **S2 (P1)** a new card is `running` but Start is disabled and live `tick()` is
  a no-op → deadlock; today's workaround is Pause→Start.
- **S3 (P2)** the Start gate has no operator entry point; it was opened by
  direct SQL.
- **S4** show `worker_active` / `last_worker_exit_reason`; refuse card creation
  when a symbol lacks the spot or the perp leg (`KORUUSDT` is the case).
- **S5** the offline transport must enforce Binance's parameter constraints —
  its absence is why S1 survived nine review rounds.

## Closed Decision — S3 Write Surface (2026-07-27)

The user chose the **symmetric confirmation dialog**: the backend gains a write
path for the durable Start gate, and the frontend drives both directions from
one control, each requiring exactly one confirmation dialog. No typed
confirmation word, no asymmetry between on and off. The design must still
specify concurrency safety via the settings row's existing `version` column and
keep the gate closed by default on a fresh install.

Recorded in `00-intake.md` §User Decision and `status.json.scope.S3.user_decision`.

## Next Action

1. **Human operator** runs
   `10-design-and-breakdown.dispatch.md` in a fresh Claude Fable 5 session
   (backup: Opus 4.8 — record which one ran) and saves its three file blocks as
   `10-design.md`, `11-adr.md`, `12-development-breakdown.md`.
2. Bookkeeper archives the raw output, records the session receipt, and
   commits.
3. The breakdown decides whether backend (S1/S3/S5) and frontend (S2/S4) run in
   parallel. If parallel, flip `parallel_mode` plus its R10/R4 flags and run
   `scripts/validate-stage.py <stage-id> --phase dispatch-ready` before
   dispatch.
4. Routing: design/breakdown → `claude`; backend → `claude_glm`; frontend →
   `kimi`; Review-1 crosses them (backend reviewed by Kimi, frontend by
   Claude-GLM); Review-2 → `codex`. Claude provider deliberately does not write
   delivery code here, and Codex deliberately has no design involvement, so
   Review-2 needs no strong-reviewer disclosure override.
   All dispatch is prepared as packets and executed by the human operator.

## Safety Standing Order

No implementer or reviewer opens a live gate, places an order, or touches
credentials. `APP_HEDGE_EXECUTOR=live`, the durable Start gate, and the first
real task remain three separate human authorizations. Re-opening the gate after
this stage is a user action, not a stage deliverable.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/70-handoff.md
本地北京时间: 2026-07-27 17:33:33 CST
下一步模型: human
下一步任务: 决定 S3 的 Start 闸门写入接口形态与确认语义，然后进入 10-design.md
