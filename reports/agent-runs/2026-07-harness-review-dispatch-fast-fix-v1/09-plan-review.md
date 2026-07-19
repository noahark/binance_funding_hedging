# Independent Plan Review — 2026-07-harness-review-dispatch-fast-fix-v1

- Reviewer: Kimi (`moonshot_kimi` / `kimi-code/kimi-for-coding`), fresh read-only
  session, no prior involvement in this stage's direction, design, or breakdown.
- Review type: independent plan review per `08-plan-review.prompt.md`. This is
  not formal code Review-1; no files were modified.
- Recommendation: **REWORK** — bounded plan revision. All three core decisions
  (single human dispatch authority, one default committed-state cross-review,
  capture-only helper + raw/verdict split) are correct and stand unchanged. The
  required changes are plan/task text amendments and enumerated edit points, not
  architectural changes: one P1, three P2, four P3 findings.

## Inputs Reviewed

- Stage files: `00-intake.md`, `00-task.md`, `05-root-cause-and-fix-plan.md`,
  `08-plan-review.prompt.md`, `10-design.md`, `11-adr.md`,
  `12-development-breakdown.md`, `status.json`, `70-handoff.md`
- Cited sources: `AGENTS.md`, `docs/parallel-development-mode.md`,
  `workflows/templates/stage-delivery.yaml`, `docs/model-adapters.md`,
  `scripts/validate-stage.py`, plus `scripts/validate-all-stages.py`,
  `schemas/review-verdict.schema.json`, `harness-manifest.yaml`,
  `reports/agent-runs/_template/`

## Verification Of The Plan's Evidence Base

All five citations in `05 §Evidence In Current Harness` check out verbatim:

- `AGENTS.md:137-142` — confirmed: human operator executes implementation,
  embedded pre-review, review-1, review-2, and fix dispatches.
- `docs/parallel-development-mode.md:104-110` — confirmed: Phase 2 requires the
  implementer terminal to launch the opposite review model itself (R10).
- `docs/parallel-development-mode.md:211-238` — confirmed: `executor:self` is an
  execution constraint; R10 embeds the exact opposite-model adapter command in
  the implementation prompt tail.
- `workflows/templates/stage-delivery.yaml:477-510` — confirmed: line 477 human
  executes packets; line 478 implementer must execute `executor:self`;
  `embedded-cross-review-checkpoint` node has `actor: implementing_terminal`.
- `scripts/validate-stage.py:665-668` — confirmed: dispatch-ready rejects
  anything except `next_dispatch_executor == "self"` and requires
  `manual_user_handoff_allowed == false`.

One imprecision worth fixing during the rewrite (feeds finding F5): the plan
says "`AGENTS.md` says the human operator executes every model dispatch."
`AGENTS.md:137-142` and the Hard Gates both enumerate only **Codex/GPT and
Claude provider sessions**; `claude_glm` is explicitly `zhipu_glm`, not
Anthropic, and Kimi is not named. `docs/parallel-development-mode.md:274-279`
exploits exactly this gap ("Dispatch execution is human-operated for Codex/GPT
and Claude provider sessions"), implying GLM/Kimi implementer terminals may
self-dispatch. So the defect is a contradiction **plus an actor-scope
ambiguity**; Decision 1's replacement rule must be actor-neutral ("no model
session launches another model; the human operator launches every external
dispatch"), not another enumerated-session list.

## Incident → Decision Coverage

The six intake incidents map cleanly onto the three system causes:

- Incidents 1–2 (unverifiable model-side launch claim; GLM review terminal
  launching another GLM) → Decision 1. Resolved structurally: with no
  model-side dispatch there is nothing to claim, and the human dispatch
  boundary is the only path.
- Incident 3 (embedded + formal duplicate pairing) → Decision 2. Resolved:
  one committed-state Review-1 is the single default round.
- Incidents 4–6 (missing `30-review-1-*`/`50-review-2` files; fenced/dirty
  verdict JSON) → Decision 3. Resolved, and the plan's diagnosis is confirmed
  by an additional fact the plan should cite: today the acceptance gate reads
  `review_*.verdict` and `review_*.json_schema_valid` **from `status.json`**
  (`scripts/validate-stage.py:1290-1311`) while the review files themselves
  are only checked for existence (`scripts/validate-stage.py:743-752`). The
  verdict is currently a bookkeeper-attested claim, not a parsed artifact —
  exactly why incidents 4–6 were possible.

Coverage is complete; no incident is left unaddressed.

## Findings (ordered by severity)

### F1 (P1) — Protocol opt-in field creates a silent bypass of the entire fix

- Evidence: `05-root-cause-and-fix-plan.md` §"Versioning And Historical
  Compatibility" (lines 108-119): "New stages using the field must satisfy the
  new raw + verdict rules." `00-task.md` acceptance #7: "New protocol
  enforcement is opt-in/versioned for new stages." Nothing in the plan makes
  `review_artifact_protocol` mandatory at any gate.
- Impact: any future stage whose `status.json` omits one line silently falls
  back to legacy advisory validation — the exact failure mode (incidents 4–6)
  this stage exists to eliminate. `00-task.md`'s own goal ("guarantee that
  review evidence and strict verdict JSON are captured mechanically before a
  stage can advance") is unconditional; "opt-in" and "guarantee" currently
  contradict each other.
- Recommendation: the plan must name the enforcement points. Workable rule:
  require `review_artifact_protocol == "raw-plus-strict-json/v1"` at the live
  progression gates (`--phase dispatch-ready` and `--phase pre-review`) for
  stages that run them after this change; keep pre-accept record-level legacy
  behavior when the field is absent so historical stages stay green under
  `scripts/validate-all-stages.py` (which only exercises record-level
  pre-accept — `validate-all-stages.py:40-66`). Ship the field in
  `reports/agent-runs/_template/status.json` (already an allowed path). State
  explicitly whether **this** stage adopts v1 for its own reviews
  (recommended: yes — it is the natural dogfood of the capture helper before
  acceptance).

### F2 (P2) — Verdict authority: parsed file vs. `status.json` claims is undefined

- Evidence: `scripts/validate-stage.py:1296-1299` gates on
  `status.review_*.verdict == "ACCEPT"` and `json_schema_valid == true`;
  `05` §"Validator Changes / Review-1 / Review-2" says "Parse the entire
  verdict file, validate schema, fingerprint, role, model, and
  reviewer-provider isolation" but never says how the parsed file relates to
  the existing `status.json` review blocks.
- Impact: after the change there would be two sources of verdict truth — a
  machine-parsed `*.verdict.json` and bookkeeper-written status fields. If the
  validator does not mechanically cross-check them, the "model claims are not
  evidence" gap survives in a new form (a stale or mistaken status entry could
  contradict the file undetected).
- Recommendation: plan must state: the parsed `*.verdict.json` is
  authoritative; for v1 stages the validator cross-checks
  `status.review_*.verdict`, `json_schema_valid`, `diff_fingerprint`,
  `role`/`model` against the parsed object and fails on mismatch (or derives
  the status fields from the file). Same for task-level `tasks[].review_1`.

### F3 (P2) — `harness-manifest.yaml` missing from Allowed Files; new helper would not sync

- Evidence: `harness-manifest.yaml:9-27` lists harness-owned files
  individually (`scripts/install-harness.sh`, `scripts/update-project-harness.sh`,
  `scripts/validate-stage.py`) — not `scripts/**`. `00-task.md` Allowed Files
  (lines 20-32) does not include `harness-manifest.yaml`.
- Impact: the new capture helper script would not be harness-owned and would
  not propagate to target projects on harness sync; synced installs would get
  a validator requiring raw+verdict artifacts but no mechanical producer —
  reintroducing manual capture, the precise thing being fixed. Acceptance
  criterion #9 (one consistent flow across docs/validator/helper/tests) would
  fail downstream.
- Recommendation: add `harness-manifest.yaml` to Allowed Files and add the
  helper's exact path to `harness_owned`. (Pre-existing, out of scope but
  worth a follow-up note: `scripts/validate-all-stages.py` is also absent from
  `harness_owned`.)

### F4 (P2) — Output Footer rule conflicts with the strict parser; `reviewer_prior_involvement_notes` overload

- Evidence: `AGENTS.md` Output Footer section allows "place the footer before
  the final JSON block" for strict JSON verdicts. `05` requires "narrative
  outside the object is invalid." `_template/30-review-1.md:58` currently
  embeds the Session-ID footer directly before the verdict JSON — every
  verdict produced under that template would be **rejected** by the new
  capture contract. Separately, `05` (line 106) routes footer/navigation data
  into `reviewer_prior_involvement_notes`, whose schema semantics are
  prior-involvement disclosure (`schemas/review-verdict.schema.json:67-70`).
- Impact: surviving footer text contradicts the new parser (systematic invalid
  outputs at first use), and overloading a disclosure field with navigation
  metadata dilutes its audit meaning.
- Recommendation: amend the `AGENTS.md` Output Footer section for
  protocol-v1 verdicts (footer stays out of verdict-producing stdout; it lives
  in the raw output, the capture receipt — which already carries an optional
  operator-provided Session-ID source — and `status.json.session_receipts`);
  update `_template/30-review-1.md` / `50-review-2.md` accordingly; do not
  overload `reviewer_prior_involvement_notes`. If footer-in-verdict is truly
  wanted, add a dedicated optional field via the allowed "schema clarification"
  path instead.

### F5 (P3) — Authority rewrite must enumerate every surviving self-dispatch edit point

- Evidence: beyond the cited lines, self-execution/embedded-default language
  lives at `docs/parallel-development-mode.md:274-279` (the Codex/GPT/Claude
  carve-out), `workflows/templates/stage-delivery.yaml:435, 467, 478, 482,
  485-527` (the whole `embedded-cross-review-checkpoint` node incl.
  `actor: implementing_terminal`), `:550`; validator coupling at
  `scripts/validate-stage.py:436-446` (`parallel_mode.enabled` currently
  **requires** `r10_dispatch_tail_required=true` and non-empty
  `embedded_reviews` at pre-review/pre-accept — a v1 parallel stage with
  opt-in embedded review would fail these legacy checks) and `:585-687`
  (dispatch-ready R10 checklist shape, incl. 665-668).
- Impact: if any one of these survives unedited, the contradiction
  reappears; if `validate_parallel_mode` is not gated on the protocol field,
  either new parallel stages fail legacy requirements or historical parallel
  stages fail new ones.
- Recommendation: the plan's implementation step 1–2 should carry an explicit
  edit-point list (the files/lines above), state that the new rule text is
  actor-neutral, bump `docs/parallel-development-mode.md` with a revision
  record entry (its 修订记录 convention), and gate the
  `r10_dispatch_tail_required`/`embedded_reviews`-required checks on the
  protocol field.

### F6 (P3) — Capture helper: failure/overwrite and operational semantics under-specified

- Evidence: `05` lines 90-106. Open points: (a) requirement 7 protects only
  the canonical **verdict** on failure; a failed later attempt would still
  atomically replace the **raw** file (requirement 2), breaking provenance
  pairing with an earlier valid verdict. (b) No guidance on the left side of
  the pipe (adapter exit status is invisible to the helper without
  `set -o pipefail`/explicit operator check). (c) The split of
  responsibilities (helper = transport + schema; validator =
  fingerprint/role/model/isolation) is implicit.
- Impact: small, but provenance mismatch and operator misuse would surface
  exactly at review gates.
- Recommendation: specify — failed attempts preserve raw as attempt evidence
  without clobbering a canonical raw+verdict pair (suffix or refuse without an
  explicit flag); verdict written via tmp+rename only after full validation;
  runbook note on `pipefail`/adapter exit codes; semantic checks stay in
  `validate-stage.py` (which already has `compute_diff_fingerprint`), keeping
  the helper capture-only.

### F7 (P3) — Pre-accept wording omits top-level review_1 for serial stages

- Evidence: `05` §"Validator Changes / Pre-accept" requires "all task
  Review-1 strict verdicts and the Review-2 strict verdict." Serial stages
  (including this one) have a top-level `review_1`, not task reviews;
  `validate-stage.py:750` requires `30-review-1.md` at pre-accept.
- Recommendation: reword to "every recorded review (top-level review_1,
  task-level review_1 entries when present, and review_2) requires raw +
  strict verdict."

### F8 (P3) — Embedded-review opt-in signal and artifact set undefined

- Evidence: `05` line 130-131 references `embedded_review.enabled == true`,
  but no such field exists today (`status.json` has top-level
  `embedded_reviews` + `parallel_mode`; validator at
  `scripts/validate-stage.py:427-431` requires `embedded_reviews` empty unless
  parallel mode is enabled).
- Recommendation: name the exact opt-in signal field, and state that opt-in
  embedded checkpoints remain human-dispatched, keep the existing four-piece
  artifact set (`.dispatch.md` / `.diff.patch` / `.raw-output.md` /
  `.fix-note.md`), produce PASS/BLOCKER — not strict verdict JSON — and never
  count as the formal Review-1.

## Answers To The Five Reviewer Questions (05 §Reviewer Questions)

1. **Does removing mandatory embedded review preserve the strongest useful
   gate?** Yes. The retained gate — cross-provider Review-1 over an immutable
   committed fingerprint — is strictly stronger evidence than an uncommitted
   worktree checkpoint, which the Hard Gates already classify as in-progress
   and which R5 already barred from substituting for formal Review-1. The real
   cost is later feedback (defects surface as formal REWORK consuming
   `rework_count` instead of local rounds); the ADR records this tradeoff
   honestly. Acceptable.
2. **Is a capture-only helper sufficiently narrow?** Yes, as specified: stdin
   → files, schema validation, mechanical receipt; no model selection, no
   dispatch, no git, no status mutation, fail-closed. It does not recreate the
   retired autonomous pipeline — provided semantic checks stay in
   `validate-stage.py` (F6).
3. **Is raw + strict verdict separation auditable and backward compatible?**
   Auditable: yes — exact raw bytes plus SHA-256 receipt, deterministic
   derivation, ADR correctly rejects in-place stripping. Backward compatible:
   only with the F1 enforcement-point fix; as written the opt-in field is a
   bypass, and `validate_parallel_mode`'s legacy requirements need
   protocol-gating (F5).
4. **Validator bypasses or status-transition gaps?** Three found: F1
   (protocol-field omission), F2 (status-attested verdict fields not
   cross-checked against the parsed file), F5 (`validate_parallel_mode`
   legacy checks would break v1 parallel stages or vice versa). No other
   bypass found; the existing authorized-exception negative list
   (`validate-stage.py:1271-1314`) is untouched by the plan, which is correct.
5. **Can file scope be reduced?** No material fat. Every allowed file is
   load-bearing for eliminating the contradiction; the scope is actually
   missing one file (`harness-manifest.yaml`, F3) rather than carrying
   excess.

## Answers To The Six Special-Attention Points (08 prompt)

1. Human-only dispatch vs `executor:self`: real contradiction plus actor-scope
   ambiguity (see Evidence Base section); Decision 1 resolves it if written
   actor-neutrally (F5).
2. Removing mandatory embedded review: preserves the strongest gate; see
   question 1 above.
3. Capture-only helper: does not recreate an autonomous runner; see question 2.
4. Raw vs. strict-verdict provenance/atomicity: sound design; overwrite and
   failure semantics need the F6 clarifications.
5. Legacy completed-stage compatibility: viable via the protocol field, but
   only with F1's enforcement points and F5's `validate_parallel_mode` gating;
   `validate-all-stages.py` record-level scope confirmed compatible with this
   approach.
6. Validator bypasses / missing tests / reducible scope: F1/F2/F5; the test
   matrix covers the six incidents well — add one fixture for "status.json
   review block contradicts parsed verdict file" (F2) and one for "new stage
   without the protocol field fails the live gate" (F1). Scope cannot be
   materially reduced; it is missing one file (F3).

## Consolidated Required Changes (for the plan revision)

1. (F1) Define protocol-field enforcement points (dispatch-ready + pre-review
   require v1 for new stages; pre-accept record-level legacy when absent);
   ship field in `_template/status.json`; state this stage's own protocol
   adoption.
2. (F2) Declare `*.verdict.json` authoritative; validator cross-checks
   status.json review blocks against it.
3. (F3) Add `harness-manifest.yaml` to Allowed Files; register the helper in
   `harness_owned`.
4. (F4) Amend Output Footer rule for strict-JSON verdicts; fix
   `_template/30-review-1.md` / `50-review-2.md`; drop the
   `reviewer_prior_involvement_notes` overload (dedicated optional field or
   footer-out-of-verdict).
5. (F5) Add the explicit surviving-language edit-point list to the plan;
   actor-neutral rule text; parallel-mode revision record; protocol-gate
   `validate_parallel_mode` checks.
6. (F6) Specify helper failure/overwrite/pipe semantics; semantic checks stay
   in the validator.
7. (F7) Fix pre-accept wording to include top-level review_1.
8. (F8) Name the embedded opt-in signal field and its artifact set.

## Residual Risks (if all required changes are absorbed)

- Human-operator throughput: every dispatch is human-executed, adding manual
  steps per stage. This is the pre-existing AGENTS.md rule, not a new cost;
  the capture helper removes its most error-prone part.
- Opt-in embedded review may drift into disuse; when enabled it must still
  satisfy its artifact discipline.
- Protocol-gated validator branches add complexity; the
  `validate-all-stages.py --compare` sweep is the regression net and must be
  run as the plan's test strategy requires.
- Kimi one-shot review has no CLI read-only flag (per `docs/model-adapters.md`);
  read-only behavior remains prompt-enforced. Unchanged by this plan.

当前 Session ID: session_e7dd8ea6-f702-40b3-b7f1-ecb406f9ed2c
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/09-plan-review.md
本地北京时间: 2026-07-19 22:39:28 CST
下一步模型: Codex（bookkeeper / plan author）
下一步任务: 按 Consolidated Required Changes 1–8 修订 05-root-cause-and-fix-plan.md 与 00-task.md；修订后由用户决定是否复核并指定不同的实现模型
