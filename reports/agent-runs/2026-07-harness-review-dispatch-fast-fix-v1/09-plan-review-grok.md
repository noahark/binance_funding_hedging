# Independent Plan Review — 2026-07-harness-review-dispatch-fast-fix-v1

**Reviewer model:** Grok 4.5 (xAI / Grok Build CLI)  
**Artifact:** `09-plan-review-grok.md`  
**Note:** This is a re-land of the Grok plan review after the shared
`09-plan-review.md` path was overwritten by another model. Do not treat other
`09-plan-review*.md` files as this reviewer's output.

## Verdict

**ACCEPT** (with mandatory pre-implementation clarifications)

The root-cause grouping is correct, the three decisions are the right minimal
repair set, and the plan addresses all six observed failures without product
scope creep. Implementation may proceed after the findings below are frozen into
`00-task.md` / `05-root-cause-and-fix-plan.md` (or an explicit amendment note
committed with the stage evidence). These findings do **not** reverse Decisions
1–3; they prevent a weak implementation from recreating failures 4–6.

This is a plan review, not formal code Review-1. No code was changed.

## Scope Reviewed

Stage artifacts:

- `00-intake.md`
- `00-task.md`
- `05-root-cause-and-fix-plan.md`
- `10-design.md`
- `11-adr.md`
- `12-development-breakdown.md`
- `08-plan-review.prompt.md`
- `status.json`, `70-handoff.md`

Cited live sources:

- `AGENTS.md` (authority order; human dispatch; parallel R10 `executor:self`)
- `docs/parallel-development-mode.md` Phase 2/4 and R10
- `workflows/templates/stage-delivery.yaml` embedded-cross-review-checkpoint
- `scripts/validate-stage.py` dispatch-ready / pre-accept gates
- `docs/model-adapters.md` human-execution rule
- `schemas/review-verdict.schema.json` (footer field availability)

## Root-Cause Correctness

| Failure (from intake) | Plan cause mapping | Assessment |
| --- | --- | --- |
| 1. Unverifiable implementer claim of launching opposite model | Cause 1: dispatch authority contradiction | Correct. `AGENTS.md:137-142` makes the human the only external dispatcher; parallel-mode Phase 2 and validator force model-side `self` launch. |
| 2. Review terminal nested another same-provider process | Cause 1 + missing hard stop in prompts | Correct. Nested launch is a predictable outcome of `executor:self` plus incomplete stop rules. |
| 3. Embedded + formal Review-1 duplicate pairing | Cause 2: duplicate review architecture | Correct. Parallel-mode Phase 2 then Phase 4 intentionally repeats the same cross-provider pairing. |
| 4. Review-1 finished without `30-review-1-*.md` on disk | Cause 3: advisory evidence capture | Correct and understated: current pre-accept trusts status fields more than file content (see F-1). |
| 5. Review-2 finished without `50-review-2.md` | Cause 3 | Correct, same mechanism. |
| 6. Fenced / trailing narrative around verdict JSON | Cause 3 + soft JSON contract | Correct. Capture + whole-file strict parse is the right fix. |

**System causes are three, not six.** That compression is accurate and useful.

Authority-order reading is also correct: under `AGENTS.md` Authority Order item 1,
human dispatch wins over parallel-mode and workflow YAML. Therefore model-side
launch claims were never sufficient dispatch evidence, even if a subprocess
sometimes ran.

## Answers To The Five Reviewer Questions

### 1. Does removing mandatory embedded review preserve the strongest useful gate?

**Yes.** The strongest useful gate is independent review of **immutable committed
bytes with a recomputable fingerprint**. That is formal task Review-1 (and stage
Review-2), not the uncommitted worktree embedded pass.

Embedded review can still be valuable as early feedback, but it is weaker:

- no committed fingerprint;
- same implementer terminal often initiates it;
- formal Review-1 must re-run anyway on committed ranges.

Retaining embedded review as **opt-in with recorded reason**, never as a
substitute for formal Review-1, is the right default change.

**Residual risk:** less early defect filtering before H_A/H_B commits. Acceptable
for a fast Harness fix if bookkeeper R4 scope reconciliation remains mandatory
(see F-3).

### 2. Is a capture-only helper sufficiently narrow to avoid recreating an autonomous runner?

**Yes, if and only if the helper is stdin/process-capture only** and never:

- selects an adapter/model;
- shells out to `codex` / `claude` / `claude-glm` / `kimi` / `grok`;
- edits `status.json`, commits, or advances phase;
- retries / chains a second model after parse failure.

The conceptual pipe in the plan is the right shape:

```text
<human-launched registered adapter> | capture-review-output --raw ... --verdict ...
```

**Required hardening (F-2):** the plan text should state these non-goals as hard
acceptance criteria for the helper CLI, not only prose intent. Otherwise an
implementer may “helpfully” wrap adapter invocation and recreate a mini-runner.

### 3. Is raw + strict verdict separation auditable and backward compatible?

**Yes, directionally.**

- Raw exact bytes → audit / dispute / repro.
- Derived strict `*.verdict.json` → gate input.
- Atomic write + no replace on failure → protects prior good verdicts.
- `review_artifact_protocol: raw-plus-strict-json/v1` opt-in → historical stages
  remain green without mutation.

Footer guidance using schema-approved
`reviewer_prior_involvement_notes` is compatible with
`schemas/review-verdict.schema.json` (field already exists). Full
AGENTS.md footer still needs a protocol-v1 exception path so models are not
told both “JSON-only” and “append Markdown footer after JSON”.

### 4. Are there any validator bypasses or status transition gaps?

**Yes — two material ones, fixable inside this stage without changing Decisions.**

See F-1 and F-4. Summarized:

- Today `validate-stage.py` pre-accept checks `review_*.verdict == ACCEPT` and
  `json_schema_valid == true` as **status.json claims**, and only requires
  filename presence for `30-review-1.md` / `50-review-2.md`. It does **not**
  re-parse file bytes against the schema. That is exactly how failures 4–6 can
  pass bookkeeping narrative while disk evidence is missing or soft.
- Protocol opt-in is good for history, but if a **new** stage omits the field it
  silently stays on the weak path. Template/default bootstrap is required.

No new terminal status values are invented; good. Keep existing
`stage_accepted_waiting_user` / human merge gate.

### 5. Can the file scope be reduced without reintroducing contradictory rules?

**No meaningful reduction.** The allowed set in `00-task.md` is already tight:

- Authority text must move together: `AGENTS.md`,
  `docs/parallel-development-mode.md`, `workflows/templates/stage-delivery.yaml`,
  `docs/model-adapters.md`.
- Behavior must move with text: `scripts/validate-stage.py` + new capture helper
  + focused fixtures.
- Template under `reports/agent-runs/_template/**` is needed so new stages start
  on protocol v1 rather than legacy soft mode.
- Product trees correctly remain forbidden.
- Avoid schema meaning changes; only touch
  `schemas/review-verdict.schema.json` if a navigation field is truly missing
  (it is not, for footer notes).

Do **not** drop parallel-mode docs or workflow YAML to “save scope”; that would
leave the original contradiction live.

## Ordered Findings

### F-1 — HIGH — Validator must re-derive verdict authority from files

**Evidence:** `scripts/validate-stage.py` `validate_acceptance()` requires
`review_1`/`review_2` objects with `verdict == ACCEPT` and truthy
`json_schema_valid`, plus `validate_required_files()` existence checks for
`30-review-1.md` / `50-review-2.md`. There is no whole-file JSON parse of a
canonical verdict artifact.

**Why it matters:** Failures 4–6 are status/metadata trust failures. If
implementation only renames docs and still trusts `json_schema_valid: true`
written by a bookkeeper narrative, the mechanical gate is not fixed.

**Required change before/during implementation:**

For protocol `raw-plus-strict-json/v1`:

1. Require non-empty `*.raw-output.md` and `*.verdict.json` paths recorded in
   status (stage and/or task).
2. Parse the entire verdict file as one JSON object (only terminal transport
   whitespace allowed around it — plan’s stricter “no surrounding prose”
   preferred).
3. Validate against `schemas/review-verdict.schema.json`.
4. Compare role/model/fingerprint fields to status and recomputed fingerprints.
5. Treat status `json_schema_valid` as derived/redundant, never as sole authority.
6. Fail closed if raw is missing/empty even when verdict JSON exists (provenance).

### F-2 — HIGH — Capture helper must be explicitly non-dispatching

**Evidence:** Plan Decision 3 lists required behaviors but does not put a hard
ban list into acceptance criteria or CLI contract.

**Required change:**

- Helper inputs: stdout stream (stdin or explicit file), output paths, schema
  path, optional operator Session ID metadata.
- Helper must not accept a model name, adapter command, or registry lookup for
  execution.
- Documented operator sequence remains two steps: (1) human launches adapter,
  (2) human runs capture on that process output / saved transcript bytes.
- On failure: non-zero exit; do not create/replace canonical verdict; raw may be
  written if bytes were received (plan should pick one: always persist raw on
  any received stdout, or only on successful capture — prefer **always persist
  raw when any stdout bytes were read**, never replace prior good verdict).

### F-3 — MEDIUM — Keep bookkeeper R4 reconciliation after removing default embedded review

**Evidence:** Parallel-mode R4 and workflow rule “bookkeeper must re-generate and
reconcile each task diff before committing” are independent of embedded review
value. Plan Decision 2 mentions “bookkeeper scope reconciliation and committed
H_A/H_B ranges” but does not explicitly retain R4 as mandatory.

**Required change:** Default flow without embedded review must still require:

1. implementer stops after report + self-tests (no model child dispatch);
2. bookkeeper reconciles task diffs / scopes;
3. committed H_A/H_B ranges + task fingerprints;
4. one formal cross-provider Review-1 per committed task fingerprint.

Do not silently delete R4 when deleting mandatory embedded review.

### F-4 — MEDIUM — Protocol bootstrap for new stages must not be forgettable

**Evidence:** Plan relies on optional field absence = legacy. That protects
history, but a new stage that omits the field gets the weak gate by accident.

**Required change:**

- `_template` / new-stage intake defaults set
  `review_artifact_protocol: raw-plus-strict-json/v1`.
- Validator behavior:
  - missing field → legacy rules (historical green);
  - field present → strict raw+verdict rules;
  - optional stronger rule for this stage only: once the helper lands on main,
    document that new delivery stages **should** set the field (template
    default). Avoid date-based magic in v1 if it risks historical breakage.

### F-5 — MEDIUM — Freeze the multi-task artifact naming contract

**Evidence:** Intake failure #4 names `30-review-1-{backend,frontend}.md`.
Current pre-accept hardcodes stage-level `30-review-1.md` / `50-review-2.md`.
Historical stages already mix `raw_output`, `raw_output_path`, `verdict_path`,
and `review_record` keys.

**Required change:** Specify one naming scheme for protocol v1, for example:

```text
# task formal Review-1
30-review-1-<task-id>.raw-output.md
30-review-1-<task-id>.verdict.json

# stage Review-2
50-review-2.raw-output.md
50-review-2.verdict.json
```

Status fields must point at these paths. Validator reads paths from status, not
only conventional filenames. Do not leave parallel task stages half-covered.

### F-6 — MEDIUM — Replace `next_dispatch_executor == "self"` and clarify handoff flags

**Evidence:** `validate-stage.py:665-668` requires
`next_dispatch_executor == "self"` and `manual_user_handoff_allowed is not False`
(i.e. must be false). Plan correctly rejects external `executor:self` and
requires `human_operator`, but does not specify the replacement checklist shape
for dispatch-ready when embedded review is off.

**Required change:**

- Default parallel dispatch-ready checklist drops embedded prompt/self-exec
  fields.
- External model dispatches use `executor: human_operator`.
- `manual_user_handoff_allowed` either becomes obsolete or is redefined so it
  cannot reintroduce “model executes next model”. Prefer: remove the false
  requirement that forbids human handoff of external dispatches; human handoff
  **is** the authorized path.
- Opt-in embedded review, if enabled, still cannot use model-side external
  launch under AGENTS authority; its “self” only means “same terminal continues
  local work”, not “spawn opposite provider”. If that distinction is too subtle,
  ban `executor:self` entirely and always use human_operator for any other-model
  launch (recommended).

### F-7 — LOW — JSON-only review prompts vs AGENTS.md output footer

**Evidence:** AGENTS.md requires a Markdown navigation footer on model-facing
reports; plan says Review prompts default to JSON-only with footer data inside
schema fields.

**Required change:** In AGENTS.md protocol-v1 section, explicitly say strict
review gate responses are **one JSON object only**, and navigation metadata for
those gates lives in `reviewer_prior_involvement_notes` and/or
`status.json.session_receipts` written by the operator/bookkeeper from the
capture receipt — not trailing Markdown after the JSON.

### F-8 — LOW — Interactive terminal capture is operationally harder than one-shot CLI

**Evidence:** model-adapters document both one-shot `-p` forms and interactive
terminals. Pipe capture fits one-shot well; interactive sessions often cannot
be cleanly piped.

**Residual risk, not a blocker:** Document that protocol v1 preferred path is
one-shot adapter command with stdout capture. Interactive sessions require the
operator to save exact transcript bytes to the raw path then run capture in
file mode. Do not expand helper into a TTY multiplexer.

## Six-Failure Coverage After Plan + Findings

| # | Covered by Decisions 1–3? | Residual if findings ignored |
| --- | --- | --- |
| 1 Unverifiable self-launch | Decision 1 | Low if validator rejects `self` |
| 2 Nested same-provider launch | Decision 1 + prompt bans | Medium without prompt/validator text |
| 3 Duplicate review cost | Decision 2 | Low |
| 4 Missing Review-1 files | Decision 3 | **High** without F-1/F-5 |
| 5 Missing Review-2 files | Decision 3 | **High** without F-1/F-5 |
| 6 Soft/fenced JSON | Decision 3 | **High** without F-1/F-2 |

## Scope And Minimality

The plan is the smallest high-quality change set that removes the contradiction
rather than documenting around it:

1. One dispatch authority.
2. One default committed cross-review round.
3. Mechanical raw + strict verdict capture.

Rejected alternatives in `11-adr.md` are correctly rejected:

- Keep both review rounds → keeps cost and disputed launch path.
- Promote embedded PASS to formal Review-1 → uncommitted target.
- Let reviewers write workspace files → remote/read-only terminals cannot.
- Strip fences in place → destroys provenance.
- Full autonomous pipeline → larger than the six failures and fights human gate.

Codex exclusion from implementation authorship is consistent with Harness rules
and this stage’s routing.

## Residual Risks (Acceptable)

1. Fewer early pre-commit review cycles → mitigate with R4 + strong formal Review-1.
2. Operator friction from explicit human launch + capture → still cheaper than
   false automation claims.
3. Two files per review → small storage / path bookkeeping cost.
4. Protocol branch complexity in validator → required for history safety.
5. Opt-in embedded review may rot → acceptable; formal gate remains mandatory.

## Disposition For Next Stage Actions

1. **Bookkeeper (Codex):** fold F-1…F-7 into `00-task.md` acceptance criteria
   and/or a short plan amendment note; update `status.plan_review` to record this
   ACCEPT and reviewer identity; keep implementation owner **different** from
   this plan reviewer.
2. **User:** assign implementation model (not Codex; not this plan reviewer if
   two-model separation is desired).
3. **Implementer:** single bounded Harness task in suggested order from the plan;
   treat F-1 and F-2 as acceptance blockers, not polish.
4. **Do not implement yet under the unamended soft reading of Decision 3** where
   status flags alone could still pass pre-accept.

## Recommendation Summary

```text
PLAN_REVIEW_VERDICT: ACCEPT
REVIEWER_MODEL: grok-4.5 (xAI)
ARTIFACT: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/09-plan-review-grok.md
BLOCKING_AMENDMENTS: F-1, F-2
SHOULD_FIX_BEFORE_CODE: F-3, F-4, F-5, F-6
NICE_TO_DOCUMENT: F-7, F-8
IMPLEMENTATION_OWNER: user-selected model ≠ plan reviewer; Codex excluded
PRODUCT_SCOPE: none
```

当前 Session ID: unavailable (Grok Build/CLI runtime does not expose a provider-native session ID in this session)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/09-plan-review-grok.md
本地北京时间: 2026-07-19 22:46:25 CST
下一步模型: Codex bookkeeper（折叠 findings）→ 用户指定的不同实现模型
下一步任务: 将 F-1…F-7 冻入任务验收口径后，再派发单任务 Harness 实现；本审查不写代码
