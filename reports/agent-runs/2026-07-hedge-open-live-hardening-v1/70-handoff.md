# Handoff — Hedge Open Live Hardening v1

## Recovery Header

- Active phase: `REVIEW-2 RETURNED REWORK — one verified P2 (S5 filter wiring). Fix packet 60-fix-review-2-s5.dispatch.md awaits a write-capable Claude-GLM session. rework_count 1/3.`
- ⚠️ A real naked SHORT 10000 NOMUSDT (orderId 888412130) is outstanding from that run and needs manual unwinding on Binance — the system has no close function.
- Pinned range: `base 6c5b170` → `head 319d831`; fingerprint `319d8317…:2a457c0f…` (full value in `status.json.diff_fingerprint`).
- Merged-state rerun (authoritative): backend **979 passed**, frontend **122 PASS**, protocol suite 72 passed, `git diff --check` clean. Evidence `60-test-output.txt`.
- Owner change 2026-07-27 18:40: Kimi quota did not recover, so **both** tasks are owned by `claude_glm`.
- Review-1 routing 2026-07-27 18:55: **Grok, both gates**, explicitly enabled by the user — see `15-user-authorized-grok-review-1.md`. Two separate fresh read-only sessions. Review-2 stays with `codex`, still zero prior involvement.
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
  GLM↔Kimi cross pool is unusable. It first went to Claude Opus 4.8, then — see
  the next section — to Grok.
- **Review-2 is unaffected**: still `codex`, still zero prior involvement, still
  no strong-reviewer disclosure override needed.
- **New parallel hazard**: both sessions write the same working tree at the same
  time, and each packet's self-tests include the other side's suite. Packet 14
  now tells the frontend session how to handle a transient backend failure
  (record it, never fix across the boundary). Packet 13 was already dispatched
  and carries no such note, so if its report shows `node frontend/self-check.js`
  failing, the bookkeeper must treat that as possibly transient and judge it by
  the merged-state rerun, not by the implementer's observation.

## Review-1 → Grok, User-Enabled 2026-07-27 18:55

`AGENTS.md` and `agents/registry.yaml` both forbid substituting Grok into
Review-1 without explicit stage-level user enablement. That enablement, the
tradeoff presented before the choice, and the operating conditions attached to
it are recorded in `15-user-authorized-grok-review-1.md`. Summary:

- **Both** Review-1 gates → Grok (`xai_grok`), two separate fresh **read-only**
  sessions (`--permission-mode plan`, per the registry's
  `optional_review_command`). One session must not review both tasks.
- Identity holds: `xai_grok` ≠ `zhipu_glm` (the implementer), and Grok has no
  design involvement, so the earlier designer-overlap disclosure no longer
  applies to Review-1.
- **Model resolved: `grok-4.5`.** `grok models` reports exactly one available
  model. Command to use, written out explicitly:
  `grok --cwd <repo> --model grok-4.5 --permission-mode plan --prompt-file <file>`.
- **Registry is stale, and this stage does not patch it.**
  `agents/registry.yaml` `adapters.grok` still pins `grok-build` /
  `grok-composer-2.5-fast` in all four command forms; neither model exists
  anymore. Harness edits belong on `main`, not in an active stage branch, and
  folding one in would widen this stage's diff and put a harness change in front
  of reviewers dispatched to review a hedge fix. Filed as
  `status.json.harness_followups[registry-grok-drift]`; the packets carry the
  real command instead. Unverified: whether `grok-4.5` still accepts
  `--effort high`, so the flag set stays minimal.
- **Pre-authorized fallback**: Grok has never run a review gate in this
  repository, so schema-conforming verdict output is unverified. If a verdict is
  missing or fails `schemas/review-verdict.schema.json`, that attempt is
  non-accepting — retry that gate once, then fall back to Claude Opus 4.8 for it
  and record the reason plus the invalid-output evidence path. This keeps the
  stage from stalling without anyone inventing a routing change mid-flight.

## Implementation — Delivered 2026-07-27

Both tasks came back and stopped without committing. Delivered:

- **A-1 (S1, P0)**: `hg{attempt_id}s|p`, 35 chars, single derivation point;
  `live_hedge_executor.py` untouched — it picks the change up by import.
- **A-2 (S5)**: `wire_constraints.py` validator, wired into the record transport
  and the strict test fake, with the pre-fix-derivation regression and the
  api-samples fact page.
- **A-3 (S3)**: `set_start_gate_cas` (CAS + same-transaction audit row),
  `put_start_gate`, the route, and `settings_to_doc` carrying `version`.
- **A-4 (S4b)**: tri-state `check_symbol_legs` probe with a status-surfacing
  reader that can tell `-1121` from a transport failure; `None` never blocks.
- **A-5**: the design's unverified `str(Decimal)` concern was **confirmed** —
  it can emit `1E-7` — so the params seam now uses `fmt_decimal`.
- **B-1/B-2/B-3/B-4/B-5**: strict `worker_active === false` button condition, the
  single symmetric gate control with one dialog per direction, the worker
  state/exit-reason line with the frozen Chinese map, `missing_leg` display
  pinned by self-check, and five new behavioural self-check sections.
- **M-1** pinned on both sides; **M-2** resolved as "leave all 14 fixtures
  alone", consistently.

## R4 Reconciliation — PASS

Full record: `16-r4-diff-reconciliation.md`. In short: every changed file is
inside its task's allowed list (backend 11 modified + 4 created, frontend 2
modified); every forbidden file has zero changes; no R3 escalation was raised or
needed; neither implementer committed or touched `status.json`/`70-handoff.md`.

The **cross-seam contract check** — the direct lesson from last stage's three
drifts — passed on all three faces: `settings.version` is emitted by
`settings_to_doc` and read by the frontend; the POST body `{enabled, confirm,
version}` matches `_START_GATE_BODY_KEYS` field for field; `missing_leg` reaches
the UI through the generic error channel with its Chinese detail intact.

Bookkeeper spot-checks against the code (not the reports) confirmed A-1's length
and single derivation point, A-3's literal-`True` confirm check and
bool-excluding version check, the CAS+audit single transaction, A-4's genuine
tri-state, M-1's assertions on both sides, and B-1's strict equality.

## Review-1 — Both Gates ACCEPT (grok-4.5, 2026-07-27)

The Grok channel worked: no schema retry was needed and the pre-authorized
Opus 4.8 fallback went unused.

| Gate | Verdict | Findings |
| --- | --- | --- |
| Backend (`30-review-1-backend.md`) | **ACCEPT** | 0 P0/P1/P2, 2 P3 |
| Frontend (`30-review-1-frontend.md`) | **ACCEPT** | 0 P0/P1/P2, 2 P3 |

Bookkeeper verification of both: JSON parses, validates against
`schemas/review-verdict.schema.json`, and carries a `diff_fingerprint`
**identical** to `status.diff_fingerprint` — so both reviewed the pinned range,
not a moving HEAD. Scope separation confirmed: the backend verdict's 27
`reviewed_artifacts` are all backend-scoped with zero frontend entries.

The backend gate's raw output was missing at the first archiving pass and the
operator supplied it afterwards. The pinned range never moved, so it reviews
exactly the code the frontend gate reviewed.

All four P3s were spot-checked against the code and are **factually correct**,
including the sharpest one: the api-samples facts page prose says the charset
includes a backslash, but `^[\.A-Z\:/a-z0-9_-]{1,36}$` has no backslash
literal — `\.` and `\:` are an escaped dot and colon.

None are repaired in this stage: any edit would move the diff and invalidate the
fingerprint both gates just reviewed. Filed as `status.json.stage_followups`,
and listed in the Review-2 packet for independent judgement.

## Next Action

1. **Human operator** runs `50-review-2.dispatch.md` in a fresh **read-only
   Codex** session (`codex exec --sandbox read-only`, not `codex review` —
   schema-bound nodes use `codex exec`). Output → `50-review-2.md`.
   Pinned to `6c5b170..319d831`.
2. Codex has **zero prior involvement**: design/ADR/breakdown → Claude Fable 5,
   both implementations → `claude_glm`, both Review-1 gates → `grok-4.5`. No
   strong-reviewer disclosure override is needed.
3. Bookkeeper archives the verdict. On ACCEPT the stage reaches
   `stage_accepted_waiting_user` — **merging to main and any live activation
   remain the user's decisions**, not the gate's.

## Open Items Carried Into Review (not blockers)

1. UM-side `newClientOrderId` charset regex is still not independently measured
   (the 36-char cap is); documented in the api-samples page.
2. The 409 dialog **title** was never frozen by the design — only its body text
   was. The frontend used a neutral structural title and flagged it.
3. Live `create_task` now issues two extra public unsigned GETs; dry-run is
   unaffected.
4. `set_start_gate_cas` has never run against the durable production DB, by
   design — implementers were barred from starting the service. Correctness
   rests on `tmp_path` tests until an operator exercises it.
5. ADR-H5's known tradeoff stands: a leg genuinely absent *while* the read also
   fails is not caught.

Integration check to prioritise (direct lesson from last round's three
cross-seam drifts): the three contract faces the frontend consumes —
`settings.version`, the start-gate POST shape, and `missing_leg` — must match
the backend's actual wire shape field for field.

## Live Acceptance Run — 2026-07-27 (during review_2)

The user restarted the service in live mode to accept the UI by hand, opened the
gate through the new S3 control, and ran a real NOMUSDT task. **No delivery code
was changed**, so the pinned range, the fingerprint and both Review-1 ACCEPTs
stand. Full evidence: `18-live-acceptance-findings.md`.

**It confirmed this stage's work in production**: the 35-char clientOrderId
passed Binance validation on both legs (S1's P0 is genuinely resolved — the perp
leg filled), the gate was opened through the new control rather than SQL
(version 3→4, S3's CAS behaved), and `settings.version` is present on the real
wire.

**It exposed four defects, none inside this stage's five items** — the user
decided they open a separate stage
(`_proposals/2026-07-27-hedge-order-truth-and-error-fidelity.md`):

- **F-1** Binance **removed** `cumBase`/`cumQuote`/`avgPrice` from
  `POST /papi/v1/um/order`, effective **2026-07-14** (official changelog,
  verified). `_decimal_str(None)` silently yields `"0"`, so every fill records a
  wrong amount and average price — and the position table's PnL derives from it.
  External contract drift; the recon that recorded those fields was true when
  captured and has since gone stale.
- **F-2** Binance uses **positive** codes on margin endpoints, **negative** on
  UM/CM. `domain.py`'s tables are all negative literals, so the **entire margin
  product line** is unmatched and falls through to the non-fatal counter. Not a
  missing entry for `51169` — a blind spot for a whole class.
- **F-3** `_business_msg()` extracts Binance's error text, but nothing persists
  it. Diagnosing the rejection required Binance support because our own records
  could not answer it.
- **F-4** `51169` root cause undetermined. Falsified: "NOM is not
  margin-tradable". Ruled out as a remedy: a PAPI test-order endpoint — it does
  not exist. Unproven: concurrency contention.

The run also left a real naked short. The task settled to `done` rather than
pausing, which is **correct per the frozen design** (`single_leg_exposure` is
advisory, `domain.py:96-99`) — whether that should remain the product behaviour
is an open user question recorded in the proposal.

The Review-2 packet discloses all of this and explicitly asks Codex to judge the
bookkeeper's scope determination independently.

## Review-2 — REWORK (GPT-5 Codex, 2026-07-27)

Schema-valid, fingerprint identical to status, zero prior involvement. One P2
finding, `next_action: fix`, with a complete `fix_start_prompt`.

**The finding, verified by the bookkeeper against the code rather than taken on
the reviewer's word:**

`RecordTransportExecutor.execute` calls `validate_order_params(spot_params)` and
`validate_order_params(perp_params)` (`executor.py:303-304`) passing **none** of
`step_size` / `min_qty` / `max_qty`, while `wire_constraints.py:101-119`
implements all three. A quantity violating the symbol's grid or bounds is
therefore still simulated as a successful fill offline. `00-task.md`'s S5
criterion requires *"quantity/price precision against the symbol filters already
loaded"* — the validator was built and then not wired in. **REWORK is correct.**

### A real Review-1 miss, recorded

The backend Review-1 (grok-4.5) **saw this exact fact** and filed it in
`residual_risks` instead of `findings`, reasoning it matched 10-design §2.5's
optional-grid wording. Review-2 measured against the **acceptance criteria**
instead — which is the authority order AGENTS.md mandates for the final gate
(approved requirements outrank design artifacts).

Recorded in `status.json.review_1_miss` as evidence for judging the
user-enabled Grok channel — not as grounds to discard it. Both Grok verdicts
were schema-valid, fingerprint-matched and on time; this was a severity and
authority-order judgement, not a failure to read the code.

## Next Action

1. **Human operator** runs `60-fix-review-2-s5.dispatch.md` in a fresh
   write-capable Claude-GLM session. Its PROMPT BODY is the final reviewer's own
   `fix_start_prompt`, **copied verbatim** — the bookkeeper added routing
   metadata and rewrote nothing.
2. The fix wires the loaded spot/perp MARKET quantity step/min/max into the
   record transport's two `validate_order_params` calls and adds an end-to-end
   regression (not just a direct validator unit test). **ADR-H4 stays frozen**:
   `wire_constraints` must not be mounted on the live send path.
3. The diff will move, so the current fingerprint dies with it. Then: bookkeeper
   R4 → merged-state rerun → evidence commit → **new** `base..head` and
   fingerprint → backend Review-1 on the new range (provider-isolated from
   `claude_glm`) → Review-2 again.
4. `rework_count` is **1 of 3**.

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
本地北京时间: 2026-07-27 21:00:00 CST
下一步模型: human operator
下一步任务: 在两个独立的只读 grok-4.5 会话分别执行 30-review-1-backend 与 30-review-1-frontend packet，范围钉死 6c5b170..319d831
