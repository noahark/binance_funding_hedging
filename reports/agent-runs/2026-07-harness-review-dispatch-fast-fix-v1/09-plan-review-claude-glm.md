# Independent Plan Review (2nd) — `2026-07-harness-review-dispatch-fast-fix-v1`

Reviewer: `claude_glm` (model `glm-5.2[1m]`, provider `zhipu_glm`, via Claude Code).
Mode: read-only plan review. No Harness source file was modified; only this
artifact was written, at the operator's instruction, alongside the first
independent review.

## Relationship To The First Review

`09-plan-review.md` is the first independent plan review (reviewer: Grok Build,
verdict **ACCEPT**, findings F-1…F-8). This file is a **second independent
review** by a different provider. It was produced without adopting Grok's
findings as premises; convergence is therefore corroboration, not inheritance.

**Both reviews independently reach ACCEPT.** Findings overlap on the load-bearing
points and complement each other on the rest. A cross-reference table appears at
the end. Where Grok names a finding I agree with, I say so explicitly rather than
re-derive it.

This is a plan review, not formal code Review-1.

## Recommendation: **ACCEPT** (with required pre-implementation clarifications)

The root-cause attribution is correct (six incidents → three system causes),
the three Decisions are mutually consistent and sit correctly under the
`AGENTS.md` authority order (`AGENTS.md` wins over parallel-mode and workflow
YAML), and the proposed file scope is the smallest change that dissolves the
contradiction without weakening a committed-state gate. Nothing below overturns
a Decision. The findings are implementation-shape clarifications to freeze in
the implementation task's design before coding, plus one tightening (F1) that
protects the repair's intent against a weak default.

## Source-Evidence Verification

Each source claim in `05-root-cause-and-fix-plan.md#evidence-in-current-harness`
was re-checked against the current tree. All accurate:

- `AGENTS.md:137-142` — human operator executes implementation / embedded-review /
  Review-1 / Review-2 / fix dispatches. Verified.
- `docs/parallel-development-mode.md:104-110` — Phase 2 requires the implementer
  terminal to execute the embedded adapter command (R10) and start a fresh
  opposite-model read-only session. Verified.
- `docs/parallel-development-mode.md:211-238` — R9 makes `next_dispatch` an
  execution constraint with `executor: self`; R10 hardens the implementer
  dispatch tail with the opposite-model adapter command. Verified.
- `workflows/templates/stage-delivery.yaml:477-510` — line 477 attributes
  implementation dispatch execution to the human operator, while lines 485-510
  define `embedded-cross-review-checkpoint` with `actor: implementing_terminal`.
  The contradiction is real and localized as claimed.
- `scripts/validate-stage.py:665-668` — dispatch-ready rejects anything but
  `next_dispatch_executor == "self"` and requires
  `manual_user_handoff_allowed is False`. Verified.

Corroborating fact for "evidence capture is advisory": the current validator
never parses review *file* content. `validate_required_files`
(`scripts/validate-stage.py:743-752`) checks only that `30-review-1.md` /
`50-review-2.md` exist; `validate_acceptance`
(`scripts/validate-stage.py:1271-1314`) reads `verdict` / `json_schema_valid` /
`diff_fingerprint` from `status.json`, never from the reviewer's output file.
The strict-verdict contract is thus enforced today only by a bookkeeper-filled
boolean — exactly the gap Decision 3 targets. (Converges with Grov F-1.)

## Answers To The Five Reviewer Questions

1. **Does removing mandatory embedded review preserve the strongest useful
   gate?** Yes. The only review bound to a committed, recomputable fingerprint is
   formal task Review-1 (and stage Review-2). Embedded review reviews an
   uncommitted worktree; `docs/parallel-development-mode.md` R5 explicitly
   classifies it as a checkpoint, not a gate. Retaining it as opt-in with a
   recorded reason removes a duplicate *uncommitted* round while leaving the
   committed-state gate intact. Reduced early feedback is a real tradeoff,
   already recorded in `11-adr.md`.
2. **Is the capture-only helper narrow enough to avoid an autonomous runner?**
   Yes. It reads stdout, persists exact bytes, parses one JSON object, validates
   schema, writes the canonical verdict, and prints a receipt. It does not
   select or invoke a model, commit, edit status, or advance state; it parses
   but does not act on verdict content, so it is not a decision node. Narrowness
   holds subject to F5 (I/O shape) and to Grok's F-2 hard-ban-list point, which I
   endorse.
3. **Is raw + strict-verdict separation auditable and backward compatible?**
   Yes, subject to F1 and F3. Raw bytes are immutable; the verdict is
   schema-valid JSON; the receipt carries SHA-256 and byte counts, so the
   raw→verdict transform is auditable as "transport whitespace only." Backward
   compatibility holds via `review_artifact_protocol`, *provided* F1 makes new
   stages default-on rather than opt-in.
4. **Are there validator bypasses or status-transition gaps?** One latent bypass
   (F1): an opt-in field lets a new stage omit it and inherit the lenient legacy
   path, re-exposing failures #4/#5/#6. No status-transition gap: the plan adds
   or removes no `ALLOWED_STATUSES` value and changes no state-machine edge; it
   only reverses two dispatch-ready assertions and adds file-content checks
   gated on the protocol field.
5. **Can the file scope be reduced without reintroducing contradictory rules?**
   Not meaningfully. `AGENTS.md`, `docs/parallel-development-mode.md`,
   `workflows/templates/stage-delivery.yaml`, and `scripts/validate-stage.py`
   are the four surfaces where the contradiction lives and must move together.
   The capture helper, fixtures, and template protocol field are genuinely new.
   `schemas/review-verdict.schema.json` can stay unchanged (the verdict reuses
   the existing schema; the protocol field belongs in `status.json`), matching
   `00-task.md`'s "only if clarification is necessary." `docs/model-adapters.md`
   likely needs only a wording check (it already prohibits Codex/Claude sessions
   from invoking other model terminals, lines 19-22).

## Ordered Findings

> Numbering F1…F8 is local to this file and independent of Grok's F-1…F-8.

### F1 — P1 — Protocol field must default ON for new stages, not stay opt-in
- **Claim:** `05-root-cause-and-fix-plan.md` "Versioning And Historical
  Compatibility" frames the field as opt-in ("New stages using the field must
  satisfy the new rules").
- **Why it matters:** If opt-in, a new stage can omit `review_artifact_protocol`
  and pass through the current lenient validation (file-exists + bookkeeper
  booleans), re-opening failures #4, #5, #6 on any stage that does not
  volunteer the field. That defeats the repair for the common case.
- **Required change:** Default-on for stages created after this change. Set
  `"review_artifact_protocol": "raw-plus-strict-json/v1"` in
  `reports/agent-runs/_template/status.json` (currently absent — verified). The
  validator applies strict rules when the field is present (new stages inherit
  it) and legacy rules when it is absent (the 36 historical stages, none of
  which carry it — verified by grep). State this explicitly in the plan's
  Versioning section. (Converges with Grok F-4; I raise severity to P1.)
- **Evidence:** `reports/agent-runs/_template/status.json` (no such field);
  `scripts/validate-all-stages.py:69-74` iterates 36 historical stages;
  `review_artifact_protocol` appears nowhere in `reports/agent-runs/` except
  `05-...md`.

### F2 — P2 — Validator is dependency-free; schema-validation strategy is undecided
- **Claim:** "Validator Changes → Review-1 / Review-2" requires parsing the whole
  verdict file and validating it against `schemas/review-verdict.schema.json`.
- **Why it matters:** `scripts/validate-stage.py:4-6` declares the script
  "intentionally dependency-free," and `scripts/validate-all-stages.py:31-37`
  imports it by file path with no third-party dependency. JSON-Schema validation
  either needs a hand-rolled minimal validator (keeps the property; non-trivial)
  or the `jsonschema` package (breaks the property). The plan does not choose.
- **Required change:** Commit to one path in the implementation design —
  preferably a small hand-rolled validator covering only the constructs this
  schema uses (`required`, `enum`, `const`, `if/then`, `minLength`, `minItems`,
  `additionalProperties: false`, nested `$ref`) — with negative fixtures on its
  edges. Keep `validate-stage.py` importable with zero third-party imports.
- **Evidence:** `scripts/validate-stage.py:4-6`; `schemas/review-verdict.schema.json`.
  (Not surfaced by Grok.)

### F3 — P2 — Verdict-file ↔ status.json cross-consistency is unspecified
- **Claim:** The plan says validate "schema, fingerprint, role, model, and
  reviewer-provider isolation" but does not require the verdict *file's* fields
  to agree with `status.json`.
- **Why it matters:** Without a cross-check, a bookkeeper could record
  `status.review_1 = {provider: kimi, verdict: ACCEPT, diff_fingerprint: X}`
  while the captured `*.verdict.json` says `model: claude_glm` /
  `diff_fingerprint: Y`; each check passes independently, recreating an advisory
  gap in a new place. This is the file-content side of Grok's F-1: Grok asks the
  validator to re-derive authority from files; I additionally require that the
  derived file fields and the status fields agree.
- **Required change:** For protocol-v1 stages, assert that
  `verdict.json.{stage_id, role, model, verdict, diff_fingerprint}` agree with
  the corresponding `status.review_1` / `review_2` record (provider identity via
  the existing `provider_identity()` helper), and that `diff_fingerprint` equals
  the recomputed committed fingerprint. Mismatch = fail-closed, non-advancing.
- **Evidence:** `scripts/validate-stage.py:1290-1314` reads only status fields;
  `:743-752` checks only file existence.

### F4 — P2 — `30-review-1.md` / `50-review-2.md` vs new raw+verdict names
- **Claim:** The plan introduces `*.raw-output.md` and `*.verdict.json` but does
  not state the fate of the bare `30-review-1.md` / `50-review-2.md` names.
- **Why it matters:** `scripts/validate-stage.py:750` requires those bare names
  at pre-accept, and `workflows/templates/stage-delivery.yaml:69,72` lists them
  as required artifacts. Without a rule, old and new names fork.
- **Required change:** State the rule explicitly. Recommended (and compatible
  with Grok F-5's multi-task form): under protocol v1 use
  `30-review-1-<task-id>.raw-output.md` + `30-review-1-<task-id>.verdict.json`
  per task, and `50-review-2.raw-output.md` + `50-review-2.verdict.json` at stage
  level; retire the bare `30-review-1.md` / `50-review-2.md` for v1 stages;
  update `validate_required_files` and the template's `required_files`. Under
  legacy (no field) the bare names remain.
- **Evidence:** `scripts/validate-stage.py:749-752`;
  `workflows/templates/stage-delivery.yaml:69,72`; intake failure #4 names
  `30-review-1-{backend,frontend}.md`. (Overlaps Grok F-5; I add the
  template/validator required-files update.)

### F5 — P2 — Capture-helper I/O shape is ambiguous
- **Claim:** Conceptual use shows `--raw <raw-output-path>` (reads like input)
  while required-behavior step 2 says the helper "atomically persist[s] exact
  bytes to `*.raw-output.md`" (writes the raw). Unclear whether the helper reads
  stdout and writes both files, or reads an already-captured raw file and emits
  only the verdict.
- **Why it matters:** Atomicity and "do not replace a prior verdict on failure"
  depend on which file the helper owns; the test-matrix case ("capture
  interrupted before atomic rename; earlier canonical verdict untouched") needs
  a defined write order. Complements Grok F-2 (which sets the non-dispatch
  ban-list) and Grok F-8 (interactive-vs-one-shot capture).
- **Required change:** Pin one shape in the implementation design. Either is
  acceptable; recommend: helper reads review stdout from a path (or stdin),
  writes `*.raw-output.md` and `*.verdict.json` to temp paths in the same
  directory, then `os.replace` each atomically; on any parse/schema/write error
  it exits non-zero without touching any existing canonical file. State whether
  raw is persisted when any stdout bytes were read but parsing failed (prefer:
  yes — raw is evidence, verdict is the gate).

### F6 — P2 — R10 / dispatch-ready field semantics must be rewritten for human dispatch
- **Claim:** The plan reverses `next_dispatch_executor` from mandatory `"self"`
  to mandatory `human_operator` and makes embedded review opt-in.
- **Why it matters:** The current dispatch-ready check
  (`scripts/validate-stage.py:617-686`) requires, per parallel task, a full
  `r10_checklist` whose semantics assume the implementer terminal launches the
  opposite model (`cross_review_adapter`, `cross_review_command_ref`,
  `cross_review_raw_output_path`, `cross_review_dispatch_path`,
  `next_dispatch_executor: self`, `manual_user_handoff_allowed: false`,
  `unavailable_branch`). Under human-dispatch + opt-in embedded review, several
  of these change meaning or become conditional.
- **Required change:** Specify in the implementation design (a) that the default
  (no embedded review) dispatch-ready path no longer demands the embedded-review
  fields, and (b) for opt-in embedded review, which fields remain, what
  `next_dispatch_executor` must equal (`human_operator`), and how
  `unavailable_branch` is recorded when a human — not a terminal — is the actor.
  Mirror the change in `docs/parallel-development-mode.md` R9/R10 and
  `workflows/templates/stage-delivery.yaml` `task-breakdown` acceptance
  (lines 435-436). (Overlaps Grok F-6.)
- **Evidence:** `scripts/validate-stage.py:617-686`, especially `:665-668`.

### F7 — P3 — `docs/parallel-development-mode.md` rewrite is larger than implied
- **Claim:** The plan lists parallel-mode flow update as one step.
- **Why it matters:** That document's R9/R10/Phase 2/§5 naming and the
  `embedded_reviews` status block are built on "implementing terminal
  mechanically triggers the opposite-model pre-review." Decisions 1+2 remove
  that mechanism, so the document needs a semantic rewrite, not a few-line trim;
  otherwise `12-development-breakdown.md` Review-Focus #1 ("authority order is
  consistent") fails — the validator would say `human_operator` while
  parallel-mode still describes `executor: self`.
- **Required change:** Budget an explicit, non-trivial edit (status header
  ADOPTED-TRIAL → note the default change; R9/R10/Phase 2 rewritten around human
  dispatch; embedded review marked opt-in with a recorded reason; `embedded_reviews`
  status block semantics updated), preserving the document's revision-header
  convention.
- **Evidence:** `docs/parallel-development-mode.md:104-110, 211-238, 281-325`.
  (Not surfaced by Grok.)

### F8 — P3 — This introducing stage should itself run under protocol v1
- **Claim:** The plan does not say whether this stage's own Review-1/Review-2
  use the new protocol.
- **Why it matters:** Opting this stage in is the first end-to-end exercise of
  raw+verdict capture and gives Review-2 real evidence to inspect; skipping it
  leaves the protocol untested outside fixtures until the next stage.
- **Required change:** Set `"review_artifact_protocol": "raw-plus-strict-json/v1"`
  in this stage's `status.json` once the field is supported, so the repair stage
  is itself bound by the new rules.
  (Not surfaced by Grok.)

## Agreement With Grok `09-plan-review.md` (Cross-Corroboration)

I explicitly endorse the following Grok findings (independent derivation reached
the same conclusion):

- **Grok F-1** (re-derive verdict authority from files) — see my F3.
- **Grok F-2** (capture helper must be explicitly non-dispatching) — complements
  my F5; I agree the non-goal list belongs in the helper's acceptance criteria,
  not only prose.
- **Grok F-3** (keep bookkeeper R4 reconciliation after removing default
  embedded review) — **I did not list this separately and I agree it is
  required.** R4 (`docs/parallel-development-mode.md:151-156`) and the workflow
  rule "bookkeeper must re-generate and reconcile each task diff before
  committing" (`workflows/templates/stage-delivery.yaml:510`) are independent of
  the embedded-review default and must remain mandatory; the plan's Decision 2
  mentions "bookkeeper scope reconciliation and committed H_A/H_B ranges" but
  should state R4 retention explicitly.
- **Grok F-4** (protocol bootstrap for new stages) — see my F1 (raised to P1).
- **Grok F-5** (freeze multi-task artifact naming) — see my F4.
- **Grok F-6** (replace `next_dispatch_executor == "self"`) — see my F6.
- **Grok F-7** (JSON-only review prompts vs AGENTS.md footer) — agreed; the
  AGENTS.md protocol-v1 section must state that strict review-gate responses are
  one JSON object only and that navigation metadata for those gates lives in
  `reviewer_prior_involvement_notes` and/or `status.json.session_receipts`, not
  in trailing Markdown. `schemas/review-verdict.schema.json` already has
  `reviewer_prior_involvement_notes`, so no schema change is needed.
- **Grok F-8** (interactive terminal capture is harder than one-shot CLI) —
  agreed as a residual risk; recommend documenting one-shot stdout capture as
  the preferred v1 path and file-mode capture as the interactive fallback,
  without expanding the helper into a TTY multiplexer.

Points I add beyond Grok: **F2** (dependency-free schema strategy), **F7**
(parallel-mode doc rewrite size), **F8** (this stage opts into v1), and the
file↔status cross-consistency half of **F3**.

## Six-Failure Coverage (Plan + Findings)

| # | Decision coverage | Residual if findings ignored |
| --- | --- | --- |
| 1 Unverifiable self-launch | Decision 1 | Low (validator rejects `self`) |
| 2 Nested same-provider launch | Decision 1 + prompt bans | Medium without prompt/validator text |
| 3 Duplicate review round | Decision 2 | Low |
| 4 Missing Review-1 files | Decision 3 | **High** without F1/F3/F4 |
| 5 Missing Review-2 files | Decision 3 | **High** without F1/F3/F4 |
| 6 Fenced / trailing-byte JSON | Decision 3 | **High** without F2/F3/F5 |

## Residual Risks

- **R1 — Legacy misclassification.** If the protocol branch is imprecise, strict
  file-content checks could fire on the 36 historical stages (whose
  `30-review-1.md` / `50-review-2.md` legitimately carry narrative + footer
  around the JSON) and flip them red. Mitigant: run
  `scripts/validate-all-stages.py --baseline-out` before and `--compare` after,
  plus the legacy positive fixture; any FLIP/ERRDRIFT blocks the stage.
- **R2 — Hand-rolled schema-validator drift (F2).** A minimal validator may
  diverge from `jsonschema` on edge constructs. Mitigant: negative fixtures per
  schema construct, including the REWORK→`fix_start_prompt` `if/then`.
- **R3 — Atomic-rename portability (F5).** `os.replace` atomicity holds for
  same-filesystem POSIX renames, not universally across network filesystems.
  Mitigant: write temp and target in the same directory (same filesystem).
- **R4 — Reviewer-narrative loss perception.** Forcing findings into JSON may
  reduce prose quality. Mitigant: `findings[].evidence/impact/recommendation`
  and `residual_risks` are free text inside JSON; raw `*.raw-output.md` preserves
  any prose (`11-adr.md` Tradeoffs already notes this).

## Required Changes (Consolidated, Pre-Implementation)

1. (F1, P1) Make `review_artifact_protocol` default-on via `_template/status.json`;
   document default-on-for-new / legacy-for-old in the plan's Versioning section.
2. (F2, P2) Choose and document the dependency-free schema-validation strategy.
3. (F3, P2) Add verdict-file ↔ `status.json` cross-checks for v1 stages; treat
   `status.json.json_schema_valid` as derived, never sole authority (with Grok F-1).
4. (F4, P2) Freeze the `30-review-1-<task-id>` / `50-review-2` raw+verdict naming;
   retire bare names under v1; update `validate_required_files` + template (with
   Grok F-5).
5. (F5, P2) Pin the capture-helper I/O shape and atomic write order; add the
   non-dispatch ban-list to acceptance criteria (with Grok F-2).
6. (F6, P2) Rewrite R10/dispatch-ready field semantics for human dispatch +
   opt-in embedded review; mirror in parallel-mode doc and workflow YAML (with
   Grok F-6).
7. (Grok F-3) Explicitly retain bookkeeper R4 reconciliation in the default flow.
8. (Grok F-7) AGENTS.md protocol-v1 section: strict review-gate response is one
   JSON object; footer metadata lives in schema fields / `session_receipts`.
9. (F7, P3) Budget the `docs/parallel-development-mode.md` semantic rewrite.
10. (F8, P3) Opt this stage into protocol v1.

None of the above contradicts the three Decisions; all fit the single bounded
Harness task proposed in `12-development-breakdown.md`.

## Recommendation Summary

```text
PLAN_REVIEW_VERDICT: ACCEPT
BLOCKING_PRE_IMPL_CLARIFICATIONS: F1, F2, F3
SHOULD_FIX_BEFORE_CODE: F4, F5, F6, Grok-F3, Grok-F7
NICE_TO_DOCUMENT: F7, F8, Grok-F8
IMPLEMENTATION_OWNER: user-selected model != both plan reviewers; Codex excluded
PRODUCT_SCOPE: none
CROSS_REVIEW_AGREEMENT: converges with 09-plan-review.md (Grok) on ACCEPT
```

---

当前 Session ID: unavailable (current runtime does not expose a provider-native session ID in this session)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/09-plan-review-claude-glm.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: Codex bookkeeper（折叠两份审查的 findings）→ 用户指定的不同实现模型
下一步任务: 将 F1–F8 + Grok F-1…F-8 冻入任务验收口径后，派发单任务 Harness 实现；本审查不写代码
