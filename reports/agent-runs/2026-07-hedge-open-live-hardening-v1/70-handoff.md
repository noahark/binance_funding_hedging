# Handoff — Hedge Open Live Hardening v1

## Recovery Header

- Active phase: `IMPLEMENTING — packet 13 (backend) is running; packet 14 (frontend) reassigned to a second Claude-GLM terminal and awaiting execution.`
- Owner change 2026-07-27 18:40: Kimi quota did not recover, so **both** tasks are owned by `claude_glm`. Review-1 therefore moves to **Claude Opus 4.8 for both tasks** (two separate fresh read-only sessions); Review-2 stays with `codex`, still zero prior involvement.
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

## Design Phase — Done (2026-07-27, Claude Fable 5)

`10-design.md`, `11-adr.md`, `12-development-breakdown.md` are archived; session
receipt recorded. The five decisions, in one line each:

- **S1** → `hg{attempt_id}s|p`, fixed 35 chars (ADR-H1). One derivation point,
  shared by record and live. Historical 38-char rows are all terminal and are
  not migrated, because reconciliation reads the persisted leg row and never
  re-derives.
- **S2** → **frontend button-condition defect**, called cleanly (ADR-H3).
  `running` is the frozen "armed" persistent semantic; what was missing is the
  runtime fact, which the backend already exposes as `worker_active`. Backend
  changes nothing.
- **S3** → `POST /api/hedge-open-settings/start-gate` with
  `{enabled, confirm: true, version}`: literal `confirm` as the server-side
  confirmation, `version` as a CAS (409 `version_conflict` returns the current
  doc), and an audit row written in the same transaction as the gate flip.
  Deliberately kept out of the frozen entries vocabulary, so no contract
  revision (ADR-H2).
- **S4** → (a) pure frontend display of two existing fields with a Chinese exit
  reason map; (b) a tri-state existence probe that may only refuse creation when
  the read **succeeded** — a read failure stays permissive (ADR-H5).
- **S5** → standalone pure validator `wire_constraints.py` consumed by the
  record transport and the strict test fake; the live send path deliberately
  does not mount it, to avoid a second parameter authority on the real-money
  path (ADR-H4).

## Bookkeeper Verification Of The Design's Factual Claims

Spot-checked against the code, all confirmed: reconciliation reads
`leg["client_order_id"]` (`service.py:1055`); `worker_active` is a real
tri-state that is `None` in dry-run (`service.py:508-516`); the settings row
already has `version` and `start_gate NOT NULL DEFAULT 0` (`store.py:127-136`);
`_is_hedge_open_path` matches `/api/hedge-open-settings` exactly and does need
the new sub-path (`server.py:98-105`); `hedge_open_log` has no foreign key, so
the `task_id="start-gate"` sentinel is admissible (`store.py:119-125`); the
eight worker exit reasons match the Chinese map (`domain.py:193-200`); the
`hgo-` literals are exactly 18 in `backend/tests`, 1 in `executor.py`, 2 as
thread names in `live_hedge_executor.py`, and 14 in `frontend/self-check.js`.

Two implicit dependencies the design left unstated are now pinned in both
packets as **M-1** and **M-2** (recorded in
`status.json.bookkeeper_added_checkpoints`):

- **M-1**: the start-gate audit row travels to the frontend in the legacy
  `logs` array, which `extractHedgeAttempts` scans. Verified that the designed
  payload carries none of the four attempt-shape keys, so it is correctly
  ignored — but that is load-bearing and unasserted. Backend asserts the payload
  key set; frontend asserts `extractHedgeAttempts` returns empty for such a row.
- **M-2**: the 14 `hgo-` fixtures in `frontend/self-check.js` were unassigned by
  the design. They are arbitrary arguments, so changing them is optional — but
  if changed, all 14 must change together. The backend is told not to touch
  them; the frontend must state its choice.

## Owner Reassignment — 2026-07-27 18:40

Kimi quota did not recover. The user reassigned Task B to `claude_glm`; Task A
was already running when the change was made. Recorded in
`status.json.model_routing.frontend_owner_reassignment`.

- **Parallelism is still valid.** Parallel mode requires disjoint allowed-file
  sets, not distinct owner providers. Backend touches `backend/**` plus the
  api-samples page; frontend touches `frontend/index.html` and
  `frontend/self-check.js`. Nothing overlaps.
- **Review-1 had to move.** With both implementers on `zhipu_glm`, the
  GLM↔Kimi cross pool is unusable. Both Review-1 gates go to **Claude Opus 4.8**
  in two separate fresh read-only sessions — Anthropic wrote no delivery code
  this stage, so provider-level isolation from the implementer holds. Disclosed:
  the reviewers share provider identity with the designer (Claude Fable 5);
  AGENTS.md constrains designer overlap only for Review-2, so this is admissible
  for Review-1, and a different model plus a fresh session keeps it separated
  from the design session.
- **Review-2 is unaffected**: still `codex`, still zero prior involvement, still
  no strong-reviewer disclosure override needed.
- **New parallel hazard**: both sessions write the same working tree at the same
  time, and each packet's self-tests include the other side's suite. Packet 14
  now tells the frontend session how to handle a transient backend failure
  (record it, never fix across the boundary). Packet 13 was already dispatched
  and carries no such note, so if its report shows `node frontend/self-check.js`
  failing, the bookkeeper must treat that as possibly transient and judge it by
  the merged-state rerun, not by the implementer's observation.

## Next Action

1. **Human operator** runs `14-implementation-frontend.dispatch.md` in a
   **second, separate** write-capable Claude-GLM terminal. Packet 13 is already
   running in the first one. Each implementer runs its self-tests, writes its
   `20-implementation-*.md` report and **stops without committing**.
2. Bookkeeper: R4 diff reconciliation against the allowed-file lists, then
   **rerun the full suites on the merged state** — that rerun, not either
   implementer's observation, is the authoritative test verdict this round.
   Then evidence commit, fingerprint, `validate-stage.py --phase pre-review`.
3. Review-1 packets, executable in parallel but in **two separate sessions**:
   backend → **Claude Opus 4.8**, frontend → **Claude Opus 4.8**. One session
   must not review both tasks.
4. Review-2 → **codex**.

Integration check to prioritise (direct lesson from last round's three
cross-seam drifts): the three contract faces the frontend consumes —
`settings.version`, the start-gate POST shape, and `missing_leg` — must match
the backend's actual wire shape field for field.

## Gate Record

`scripts/validate-stage.py 2026-07-hedge-open-live-hardening-v1 --phase
dispatch-ready` → PASSED. Output preserved at
`12-dispatch-ready-validation.txt`.

## Safety Standing Order

No implementer or reviewer opens a live gate, places an order, or touches
credentials. `APP_HEDGE_EXECUTOR=live`, the durable Start gate, and the first
real task remain three separate human authorizations. Re-opening the gate after
this stage is a user action, not a stage deliverable.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/70-handoff.md
本地北京时间: 2026-07-27 18:42:00 CST
下一步模型: human operator
下一步任务: packet 13（Claude-GLM 后端）已在执行；在第二个独立的 Claude-GLM 终端执行 packet 14（前端），两份 20-implementation-*.md 出齐后交回 bookkeeper
