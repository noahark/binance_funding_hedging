# User Acceptance / Release Decision — Hedge Open Real API v1

## Decision

The user (repo owner) **accepts this stage** and **authorizes a no-fast-forward
merge to main, plus push**.

- User statement (2026-07-27): 「合并推送，我会起新的终端进行新开stage」.
- This follows the full review discipline — **NOT a waiver**:
  - Task-level Review-1 both **ACCEPT**: backend `73-review-1-backend-r6.md`
    (Claude Opus 5, r6 after six rounds), frontend `59-review-1-frontend-r2.md`
    (Claude-GLM).
  - **Review-2 final ACCEPT**: `75-review-2-r3.md` (Codex/GPT-5, the only
    provider free of delivery/fix authorship), zero P0/P1/P2, one P3, empty
    `required_fixes`, `next_action = stage_accepted_waiting_user`.
  - `scripts/validate-stage.py --phase pre-accept` → **PASS**, with **no
    `authorized_exception` needed**.

## Accepted content

| Item | Value |
| --- | --- |
| Stage branch | `stage/2026-07-hedge-open-real-api-v1` |
| Base SHA | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| Accepted head | `1c09db491e8f89426b811be990929148f01c1d3c` |
| `diff_fingerprint` | `1c09db491e8f89426b811be990929148f01c1d3c:a5b08463fb690d52687934ec6227783689e94aebc55a39ed51af461c941e7b78` |
| Backend task range | `28c550d..77c75bd` (its Review-1 range; r8 touched only `scripts/`) |
| Frontend task range | `28c550d..8af3f22` (`frontend/**` unchanged since) |

**Scope**: the real-API hedge-open round — live PAPI margin/UM order adapter
behind a deny-by-default seven-endpoint allowlist, read-only preflight, per-task
bounded workers (no global guardian), clientOrderId-only reconciliation that
never resends, task-local pause on 429 / insufficient funds, fatal stop, additive
`entries` timeline with independent pagination, positions panel.

**Tests at acceptance**: 918 backend, 72 Harness protocol, frontend self-check,
`git diff --check` clean.

## Review history (8 authorized code changes, 6 backend Review-1 rounds)

Every round was a user-authorized, bounded change with its own evidence file.
Defects genuinely caught and fixed along the way, in order:

1. Global guardian scanner → replaced by task-local bounded workers (H-1).
2. Sticky `pause_reason` disabling the consecutive-failure brake after a 429.
3. Manual pause/delete abandoning in-flight real orders.
4. Vacuous R3/R4 regressions that pinned nothing.
5. `STATUS_DONE` missing from restart recovery — a hedged pair rendering as a
   permanent naked short.
6. `single_leg` never accruing the failure brake.
7. Client-ID query calling a possibly-filled order absent, and discarding
   query-stage 429.
8. Crash seam leaving an attempt terminal-but-unsettled.
9. The finding-6 validator missing non-review dispatch receipts.

## Governance state carried forward (permanent)

- `rework_count` **8/8 exhausted**.
- The **reviewer pool for this stage is down to `codex` alone**: `anthropic` is
  barred twice (Claude Sonnet 5 wrote the frontend rework; Claude Opus 5 wrote
  the r8 validator fix), `zhipu_glm` is the backend author, `kimi`/`grok` have no
  quota. **Nobody can cross-check codex here.**
- The bookkeeper from 2026-07-25 (Claude Opus 5) is also the author of the r2–r6
  Review-1 rounds and of the r8 change. Disclosed in
  `27-user-authorized-r4-repair.md` §6, `29-user-special-approval-r8.md` and
  `status.json.bookkeeper.dual_hat_disclosure`. Review-2 was explicitly asked to
  scrutinise that dual hat and did.
- `29-user-special-approval-r8.md` records one change merged with **no model
  cross-review** at user instruction; `75-review-2-r3.md` later reviewed it as
  first-and-only reviewer.

## ⚠️ Accepted WITH a known live blocker

The first real order was attempted on 2026-07-27, **after** the final gate
passed. It was sent and rejected. Full detail in `70-handoff.md` §First live run
and `status.json.live_first_run_findings`:

- **P0** — `clientOrderId` is 38 chars (`executor.py:160`), Binance caps it at
  36 → every leg returns `-4015` → **no real order can currently succeed**.
- **P1** — a freshly created card cannot be started in live mode (the Start
  button is disabled for `running`, yet only `post_start` launches a worker
  there).
- **P2** — the global Start gate has no operator entry point at all.

These are **runtime/integration gaps that no offline review could reach**, not
regressions of reviewed behaviour, so they do not invalidate the ACCEPT. The
accepted code is correct against its frozen contracts; it is **not yet usable for
real trading**.

**No live gate is released by this acceptance.** `APP_HEDGE_EXECUTOR=live`, the
durable Start gate and the first real task remain three separate human
authorizations.

## Next

The user will open a new stage from a fresh terminal. Recommended scope:
the P0/P1/P2 above plus the standing follow-ups (frontend display of
`worker_active` / `last_worker_exit_reason`; validate spot+perp both exist at
card creation; make the offline fake transport enforce known Binance parameter
constraints so format-class defects fail offline). A new stage also **restores
the reviewer pool**.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/80-user-acceptance.md
本地北京时间: 2026-07-27 CST
下一步模型: none
下一步任务: merge to main and push; the user opens the next stage separately
