# T1 Implementation Report — `contract-and-schemas`

Stage: `2026-07-auto-review-pipeline-v1` · Task: T1 · Mode: manual DRAFT-2
human dispatch (auto mode stays disabled for this bootstrap stage).

## 0. Metadata

- Branch (read at start, never switched): `stage/2026-07-auto-review-pipeline-v1`
- T1 `base_sha` (read from `status.json tasks[id=T1].base_sha`): `a385c7ad77da1611c6e952b2219aee56b49f442f`
- Implementer: `claude_glm` (provider identity `zhipu_glm`) / `glm-5.2[1m]`
- Pre-conditions verified before writing: branch matches;
  `tasks[id=T1].status == ready_for_human_dispatch`;
  `auto_review_pipeline.enabled_for_this_stage == false`;
  `parallel_mode.enabled == false`.
- T1 `head_sha` / `diff_fingerprint`: NOT set by the implementer. The bookkeeper
  creates the T1 delivery commit and records these; the implementer must not
  commit.

## 1. Changed Files And Allowlist Confirmation

All twelve delivery files touched by T1 are inside the §3 writable allowlist.
No forbidden path was touched.

| File | Status | In §3 allowlist |
|---|---|---|
| `schemas/auto-review-authorization.schema.json` | new | yes |
| `schemas/runner-receipt.schema.json` | new | yes |
| `reports/agent-runs/_template/status.json` | modified | yes |
| `reports/agent-runs/_template/70-handoff.md` | modified | yes |
| `AGENTS.md` | modified | yes |
| `workflows/templates/stage-delivery.yaml` | modified | yes |
| `agents/registry.yaml` | modified | yes |
| `docs/auto-review-pipeline.md` | new | yes |
| `docs/model-adapters.md` | modified | yes |
| `docs/parallel-development-mode.md` | modified | yes |
| `reports/agent-runs/README.md` | modified | yes |
| `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt` | append (shared evidence) | yes (shared) |

`agents/developer-discipline.md` is in the T1 writable list but was **not**
modified: the frozen T1 contract (§5 items 1–9, breakdown §3) places no
additive requirement on it. It is generic developer execution discipline;
auto-review is a control-plane concern that does not change developer coding
discipline. Per the surgical-changes rule, no request → no edit. Flagged here
for reviewer awareness.

Shared evidence: this `20-implementation.md` is create-if-absent (T1 first
section). `60-test-output.txt` was appended only; pre-existing content was not
rewritten.

Forbidden paths verified untouched: `scripts/**`, `harness-manifest.yaml`,
`schemas/review-verdict.schema.json`, `agents/skills/**`, `backend/**`,
`frontend/**`, `schemas/api/**`, `docs/product/**`, the live stage
`status.json` / `70-handoff.md` / `30-review-1-*` / `task-*.prompt.md`, and all
`2026-07-funding-*` paths.

## 2. §5 Frozen T1 Contract — Item Status (1–9)

1. **`schemas/auto-review-authorization.schema.json`** — DONE. JSON Schema draft
   2020-12, `additionalProperties:false`. Fields match 10-design §Authorization
   Artifact one-for-one. `expires_at` is required and nullable
   (`["string","null"]`). Includes `supersedes` (`["string","null"]`) and
   `scope.{task_ids,allowed_pathspecs,forbidden_pathspecs,topology}`. All five
   budget keys present with `max_stage_rework` const 3, `max_auto_code_changes`
   maximum 2, `invalid_json_max_attempts_per_model` const 2.
   `auto_high_end_dispatch_allowed` is const false.
2. **`schemas/runner-receipt.schema.json`** — DONE. JSON Schema draft 2020-12,
   `additionalProperties:false`. Required fields match 10-design §Runner Receipt
   (schema_version/stage_id/sequence/node/attempt; adapter id + registry command
   ref; prompt/raw_output/verdict paths; started/completed/exit_status/timeout;
   call_budget before/after; failure_class; next_transition). The description
   states the forbidden-content rule; `adapter` stores only id + registry ref
   (never expanded command); `next_transition` and `failure_class` are
   enum-constrained so no model-selected next action or arbitrary string can
   be stored.
3. **`_template/status.json`** — DONE. Added the nested `auto_review_pipeline`
   block from 10-design §Status Shape with `enabled:false` default and
   `dispatch_mode:"human_dispatch"`. Both review blocks changed from prefilled
   `reviewer_prior_involvement:"none"` to `null` plus
   `reviewer_prior_involvement_pending:true` (the E1 shape this stage already
   applied to its own status).
4. **`_template/70-handoff.md`** — DONE. Added matching handoff fields
   (Auto-review pipeline / Dispatch mode / Runner state in Current State;
   Auto-run authorization / Runner receipts / Embedded cross-check set /
   Escalation artifacts / Pilot metrics in Artifact Index).
5. **AGENTS / workflow / registry / docs additive amendment** — DONE. Manual
   mode original meaning preserved everywhere (see §3.1: zero manual sentences
   reworded). The auto exception is explicitly predicated on a schema-valid,
   human-approved, committed per-stage authorization artifact; the runner is the
   sole automatic dispatcher; review-2 and merge remain human gates; manual/auto
   mode mutex is stated in AGENTS, workflow, registry, and the parallel-mode
   doc.
6. **Registry auto invocation policy** — DONE. The `auto_review_pipeline` block
   references the existing `adapters.grok.optional_review_command`
   (`grok-build`, plan mode) and the existing `invocation_owner:runner`. No new
   command was invented.
7. **`docs/auto-review-pipeline.md`** — DONE (normative). Contains: transition
   matrix; budgets; review-unit and seal summaries; post-cross-check blocking
   rerun; escalation contract; threat boundary; and the full Pilot Evaluation
   Contract (`auto-review-pilot-metrics.json` minimum fields, P11 metrics, 100%
   RECEIPT completeness, escalation drill, and rule 7 explicitly does not invent
   a promotion threshold).
8. **`docs/parallel-development-mode.md`** — DONE as minimal diff. One additive
   bullet states the mode mutex and migration wording. No document
   restructuring; historical "预审" wording in untouched bullets was left as-is
   per the rewrite-on-touch rule.
9. **`reports/agent-runs/README.md`** — DONE. Appended the new evidence names to
   the existing naming list (authorization, receipts, embedded-cross-check set,
   `80-escalation-*`, pilot metrics).

## 3. Additive-Change Audit

### 3.1 Pre-existing sentences modified (before/after, by file)

Only `reports/agent-runs/_template/status.json` has modified pre-existing
lines — the E1 `reviewer_prior_involvement` change in both review blocks. Every
other delivery file is pure additive insertion or a brand-new file; no other
pre-existing sentence was reworded.

**`reports/agent-runs/_template/status.json` — `review_1` block:**

before:
```json
    "reviewer_prior_involvement": "none",
```
after:
```json
    "reviewer_prior_involvement": null,
    "reviewer_prior_involvement_pending": true,
```

**`reports/agent-runs/_template/status.json` — `review_2` block:**

before:
```json
    "reviewer_prior_involvement": "none",
```
after:
```json
    "reviewer_prior_involvement": null,
    "reviewer_prior_involvement_pending": true,
```

(The two `before` lines are identical strings in different blocks; the
`review_1` line is followed by `fix_start_prompt_present`, the `review_2` line
by `reviewer_prior_involvement_notes`. The change is the frozen E1 pattern;
`"none"` is exactly the latent-bypass this stage removes.)

### 3.2 Additive insertions (by file)

- **`schemas/auto-review-authorization.schema.json`** — new file. Full
  authorization schema; no insertion anchor (entire file is additive).
- **`schemas/runner-receipt.schema.json`** — new file. Full receipt schema.
- **`reports/agent-runs/_template/status.json`** — one insertion: the
  `auto_review_pipeline` object is placed between the `parallel_mode` object and
  the `embedded_reviews` field. (Plus the two E1 line changes in §3.1.)
- **`reports/agent-runs/_template/70-handoff.md`** — two insertions: three
  lines after `- Parallel mode:` in Current State; five lines after
  `- Embedded review checkpoints:` in Artifact Index.
- **`AGENTS.md`** — one insertion: a new top-level section
  `## Auto Review Pipeline (Opt-In, Default-Off)` placed between the end of
  `## Hard Gates` (the `Harness/template sync lands on main only …` bullet) and
  `## Standard Stage Delivery`. No existing bullet or sentence was altered.
- **`workflows/templates/stage-delivery.yaml`** — two insertions: (a) auto
  guard keys added inside `guards:` immediately after
  `require_r4_diff_reconciliation_before_parallel_task_commits` and before
  `max_rework_per_stage`; (b) a new top-level `auto_review_pipeline:` mapping
  placed between the `guards:` block and the `artifacts:` block.
- **`agents/registry.yaml`** — one insertion: a new top-level
  `auto_review_pipeline:` mapping placed between the end of `model_policies`
  (after `terminal_stop_reasons`) and `failure_classes`.
- **`docs/auto-review-pipeline.md`** — new file. Normative contract.
- **`docs/model-adapters.md`** — one insertion: a new `## Auto Review Pipeline`
  section appended after the final paragraph of `## Dispatch Failure Semantics`
  (the `failure_classes.embedded_checkpoint` sentence). No prior section changed.
- **`docs/parallel-development-mode.md`** — one insertion: a single bullet
  appended to `## 6 与现行 workflow 的关系` (after the
  `reviewer_prior_involvement` disclosure bullet), stating mode mutex and
  migration. No other bullet reworded.
- **`reports/agent-runs/README.md`** — one insertion: new evidence filenames
  appended to the existing stage-directory naming list (after `status.json`,
  before the closing fence).

### 3.3 Audit summary

- Pre-existing sentences reworded: 2 (both the E1 `reviewer_prior_involvement`
  line in `_template/status.json`, listed verbatim above).
- All other changes are additive insertions or new files.
- No manual-mode rule was weakened, broadened, or silently reworded.

## 4. Required Checks — Raw Results And Exit Status

All commands are recorded in
`60-test-output.txt` (T1 section, 2026-07-11 13:32:15 CST). Summary:

| Command | Result | Exit |
|---|---|---|
| `python3 -m json.tool schemas/auto-review-authorization.schema.json` | PASS | 0 |
| `python3 -m json.tool schemas/runner-receipt.schema.json` | PASS | 0 |
| `python3 -m json.tool reports/agent-runs/_template/status.json` | PASS | 0 |
| `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint` | PASS (`STAGE VALIDATION PASSED`, status=designing) | 0 |
| `git diff --check` (worktree-equivalent) | PASS (no whitespace errors) | 0 |
| `grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template` | PASS (no matches) | 1 |

The committed-range `git diff --check <T1-base>..<T1-head>` is bookkeeper-run
after the T1 delivery commit; the implementer did not commit. The worktree
`git diff --check` is the implementer-side equivalent and is clean.

The `grep` negative scan initially matched a vocabulary line in the new
`docs/auto-review-pipeline.md` that named the forbidden literal term inside a
"do not use" sentence. The line was rephrased to avoid the literal term
without changing vocabulary policy, and the frozen command was rerun unchanged;
it now returns no matches (exit 1). The command was not rewritten to mask the
exit status.

## 5. `git status --short` (at report time)

```text
 M AGENTS.md
 M agents/registry.yaml
 M docs/model-adapters.md
 M docs/parallel-development-mode.md
 M reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
 M reports/agent-runs/README.md
 M reports/agent-runs/_template/70-handoff.md
 M reports/agent-runs/_template/status.json
 M workflows/templates/stage-delivery.yaml
?? docs/auto-review-pipeline.md
?? schemas/auto-review-authorization.schema.json
?? schemas/runner-receipt.schema.json
```

All twelve paths are inside the §3 allowlist. No commit was created.

## 6. §6 Audit Questions — Explicit Answers

- **Manual rule original meaning preserved?** Yes. No manual-mode sentence in
  AGENTS.md, the workflow, the registry, model-adapters, the parallel-mode doc,
  or README was reworded. The only pre-existing lines changed are the two E1
  `reviewer_prior_involvement` placeholders in the template status, which is a
  frozen T1 requirement, not a manual-rule weakening. Auto exceptions are
  isolated in new sections/blocks and explicitly name the authorization
  artifact.
- **Default-off consistent across template/workflow/registry/docs?** Yes.
  Template `auto_review_pipeline.enabled:false`; workflow
  `auto_review_pipeline_default_enabled:false` and `default_enabled:false`;
  registry `default_enabled:false`; AGENTS and docs state default-off; this
  stage keeps `auto_review_pipeline.enabled_for_this_stage:false`.
- **Pilot Evaluation Contract complete?** Yes.
  `docs/auto-review-pipeline.md` §14 includes the
  `auto-review-pilot-metrics.json` minimum fields, P11 metrics (Grok
  schema-valid rate, escalation-shape validation, RECEIPT completeness), the
  100% RECEIPT completeness rule, the controlled escalation drill, and rule 7
  explicitly states v1 invents no global promotion threshold.
- **Nullable `expires_at` semantics?** `expires_at` is required (in the schema
  `required` array) and nullable (`["string","null"]`). Missing field → invalid.
  `null` → no independent authorization-expiry timestamp, not unlimited; still
  bound by call/wall-clock/rework budgets, operator stop, and stage gates.
  Non-null ISO8601 → enforced before every model call and commit. Stated in the
  schema description, AGENTS auto section, and `docs/auto-review-pipeline.md` §2.
- **Any forbidden path touched?** No (expected). Verified by `git status` and
  the forbidden-path scan in `60-test-output.txt`.

## 7. Blockers, Risks, Review-1 Focus

- **Blockers:** none. All §5 items landed; all §7 checks pass; no stop-condition
  in §8 was triggered.
- **Unresolved risks:**
  - Contract-text drift remains the highest review-2 exposure. The mitigation
    is this verbatim before/after + additive-insertion audit (§3) and the
    frozen-command evidence (§4).
  - `agents/developer-discipline.md` was intentionally not edited; if review-1
    finds an auto-mode developer-discipline rule is required, that is a design
    amendment, not a T1 fix-forward.
  - The template `auto_review_pipeline` block uses runtime-null fields
  (`authorization_path`, `runner_state`, `budgets`, etc.) for the default-off
  state; positive values are filled only when a real authorization lands. This
  matches 10-design "default-off compatibility" but review-1 should confirm the
  validator treats `enabled:false` as "skip auto checks" (T2 owns the validator
  implementation).
- **Suggested review-1 (Kimi) focus, beyond the frozen breakdown list:**
  1. Field-level match of both schemas vs 10-design shapes — especially
     `expires_at` required+nullable and the three frozen budget numbers
     (`max_stage_rework` const 3, `max_auto_code_changes` ≤ 2,
     `invalid_json_max_attempts_per_model` const 2), and
     `auto_high_end_dispatch_allowed` const false.
  2. Zero weakening of any manual rule — audit every line in the T1 diff against
     §3.1/§3.2; confirm only the two E1 lines changed and all else is additive.
  3. `docs/auto-review-pipeline.md` completeness vs 10-design, especially the
     Pilot Evaluation Contract and the post-cross-check blocking rerun rule.
  4. Receipt schema really forbids expanded command / env / secret /
     model-selected next action (enum-constrained `next_transition` and
     `failure_class`; `adapter` stores reference only).
  5. Registry auto policy references the existing `adapters.grok.optional_review_command`
     and `invocation_owner:runner`, inventing no new command.

## 8. What The Implementer Did NOT Do

- Did not commit, push, merge, rebase, create a branch, or modify git history.
- Did not write `status.json`, `70-handoff.md`, `30-review-1-*`, or any review
  file for the live stage.
- Did not set T1 `head_sha` / `diff_fingerprint` (bookkeeper-owned).
- Did not dispatch any model, run any live model/network/auto-review runner, or
  record any credential/token/cookie/expanded alias.
- Did not touch `scripts/**`, `harness-manifest.yaml`,
  `schemas/review-verdict.schema.json`, `agents/skills/**`, product/runtime
  paths, or any other task's files.

Next step is the bookkeeper: verify boundaries, run independent commands,
create the committed T1 range, compute the standard fingerprint, run the
validator gate, and prepare the human Kimi review-1 packet. The Kimi review-1
gate must not be skipped.

```text
本地北京时间: 2026-07-11 13:36:27 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 检查 T1 实现与 raw evidence，形成 committed review unit；不得跳过 Kimi review-1 gate
```
