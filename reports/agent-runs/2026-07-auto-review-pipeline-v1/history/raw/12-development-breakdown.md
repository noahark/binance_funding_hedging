# Development Breakdown: 2026-07-auto-review-pipeline-v1

Status: **FROZEN FOR DISPATCH PREPARATION — no implementation or model dispatch authorized by this document**
Date: 2026-07-11
Author: Claude Fable 5 (`anthropic/claude-fable-5`), skill `task_planner`, per
registry `rotation_defaults.development_breakdown`.
Author prior involvement disclosure: direction-level patches merged into the
frozen decision table (F1–F3) and stage-design review
`13-stage-design-review-fable5.md`. Under `AGENTS.md`, authoring this breakdown
is additional design involvement for review-2 disclosure purposes; status.json
review-2 routing remains a pending human gate.

Frozen inputs (this document refines, never reopens):

- `00-task.md`, `10-design.md`, `11-adr.md` as fixed by design commit
  `c38c5a8` plus review-fix commit `db8d58c` (disposition record
  `14-stage-design-review-fix.md`), checkpointed at `8eca2e9`.
- `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
  (FROZEN — POST DUAL REVIEW).

## 1. Delivery Topology (frozen)

- Three tasks, strictly serial: `T1 → T2 → T3`. A task may start only after the
  previous task's review-1 unit is ACCEPT.
- Single implementation owner for all tasks: **Claude-GLM**
  (`claude_glm`, provider identity `zhipu_glm`), per 10-design bootstrap
  topology. No frontend surface exists in this stage.
- Review-1 for every task: **fresh read-only Kimi session**
  (`kimi`, provider identity `moonshot_kimi`), cross-pool rule for a
  `claude_glm` implementer. Review-1 must receive raw artifact paths and the
  exact `base..head` range recorded by the bookkeeper.
- Fix author on REWORK: `claude_glm` (same owner), dispatched via the
  reviewer's `fix_start_prompt`. Each code-changing fix round charges the
  single stage ledger (`max_rework = 3`, shared across all three tasks).
- Bookkeeper: current Codex/GPT session. Sole writer for `status.json`,
  `70-handoff.md`, evidence commits, and fingerprints. Implementer sessions
  never write those files.
- Dispatch execution: **human operator only** (current DRAFT-2 rules). Codex
  and Claude sessions prepare packets; they do not execute them.
- `parallel_mode.enabled` stays `false`. The auto pipeline being built stays
  **disabled** for this stage (`auto_review_pipeline.enabled_for_this_stage:
  false`); every gate below runs under the existing manual workflow.
- Review-2: unresolved human routing gate (see `status.json.model_routing`).
  Nothing in this breakdown selects it.

## 2. Allowlist Disposition

`00-task.md` permits the breakdown to remove optional files. Removed from the
stage allowlist (rationale, per file):

- `agents/skills/code-reviewer.md` — the P3 "final and only schema-valid JSON
  block" rule is runner parsing behavior; the skill's existing local override
  ("Response must end with schema-valid JSON verdict") already covers reviewer
  guidance. No verdict-boundary change requires editing this file.
- `agents/skills/minimal-change-engineer.md` — the multi-owner fix header is a
  runner-generated artifact (10-design), not a skill-text concern.

If implementation later shows either file must change, stop and record a design
amendment before dispatch; do not edit them under this breakdown.

Every other file named below is the **complete** writable set for its task.
Anything not listed for the active task is forbidden for that task, including
files owned by another task. `schemas/review-verdict.schema.json` is read-only
for all tasks. Product paths (`backend/**`, `frontend/**`, `schemas/api/**`,
product docs) are forbidden for all tasks; touching one is an immediate
escalation, not a fix-forward.

Shared writable-by-role exceptions for all tasks (append-only, evidence):

- `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
  (implementer, one appended section per task/fix round)
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`
  (implementer appends raw command output; bookkeeper appends gate runs)

`status.json`, `70-handoff.md`, review files (`30-review-1-*.md`), and all
commits remain bookkeeper-only.

## 3. Task T1 — `contract-and-schemas`

**Goal:** land the complete written auto-mode contract: policy, workflow,
registry, docs, templates, and the two new JSON Schemas. No executable code.

**Depends on:** nothing (first task). **Base:** integration branch HEAD at
dispatch (bookkeeper records `base_sha`).

### Writable files

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `agents/registry.yaml`
- `agents/developer-discipline.md`
- `docs/auto-review-pipeline.md` (new)
- `docs/model-adapters.md`
- `docs/parallel-development-mode.md`
- `reports/agent-runs/README.md`
- `reports/agent-runs/_template/status.json`
- `reports/agent-runs/_template/70-handoff.md`
- `schemas/auto-review-authorization.schema.json` (new)
- `schemas/runner-receipt.schema.json` (new)

Explicitly not writable in T1: `scripts/**`, `harness-manifest.yaml` (T3 owns
the manifest sync).

### Contracts produced (frozen for T2/T3)

1. **Authorization schema** — exactly the 10-design "Authorization Artifact"
   field set, including required-but-nullable `expires_at`, `supersedes`,
   `scope.{task_ids,allowed_pathspecs,forbidden_pathspecs,topology}`, the five
   budget keys with frozen values (`max_stage_rework` const 3,
   `max_auto_code_changes` ≤ 2, `invalid_json_max_attempts_per_model` const 2),
   and `auto_high_end_dispatch_allowed: false`.
2. **Receipt schema** — the 10-design "Runner Receipt" required fields; the
   forbidden-content rule (no expanded command, environment, token, cookie,
   secret, model-selected next action) stated in the schema description and
   enforced by pattern/absence constraints where machine-checkable.
3. Both schemas: JSON Schema **draft 2020-12** with
   `additionalProperties: false`, matching the style of
   `schemas/review-verdict.schema.json`.
4. **Status/template shape** — `_template/status.json` gains the nested
   `auto_review_pipeline` block from 10-design "Status Shape" with
   `enabled: false` default; `_template/70-handoff.md` gains the matching
   handoff fields. Additionally, replace the template's prefilled
   `reviewer_prior_involvement: "none"` (both review blocks) with `null` plus
   `reviewer_prior_involvement_pending: true` — the same accepted E1 pattern
   this stage already applied to its own status file; prefilled `"none"` is the
   exact latent-bypass this stage exists to remove.
5. **Policy text** — AGENTS.md auto-mode section (default-off, human
   authorization artifact, runner as sole automatic dispatcher, review-2/merge
   human gates unchanged, mode mutex), workflow optional nodes/transitions,
   registry auto invocation policy referencing the existing
   `adapters.grok.optional_review_command` (grok-build plan mode) and existing
   `invocation_owner: runner` fields. `docs/auto-review-pipeline.md` is the
   normative contract and must contain the transition matrix, budgets,
   review-unit and seal protocol summaries, escalation contract, threat
   boundary, and the full **Pilot Evaluation Contract** (metrics artifact
   `auto-review-pilot-metrics.json`, P11 metrics, 100% RECEIPT completeness,
   escalation drill, no invented promotion threshold).

### Implementation constraints

- **Additive amendments only.** Existing manual-mode sentences keep their
  meaning; where a current rule gains an auto-mode exception (e.g. the AGENTS
  Grok review-1 hard gate, the human-executes-dispatch rule), the manual rule
  text stays intact and the exception explicitly names the auto authorization
  artifact as the user's per-stage enablement. Every touched pre-existing
  sentence must be listed verbatim (before/after) in the T1 section of
  `20-implementation.md`.
- `docs/parallel-development-mode.md`: minimal diff — add the mutual-exclusion
  /migration wording; update historical "embedded pre-review" phrasing to
  "embedded cross-check" only inside touched sections (frozen "rewrite on
  touch" rule); do not restructure the document.
- `reports/agent-runs/README.md`: append the new evidence filenames
  (authorization, receipts, seen-patch/cross-check set, `80-escalation-*`,
  pilot metrics) to the existing naming list.
- Locked vocabulary everywhere: `review-1` / `review-2` /
  `embedded cross-check`; never `formal-1`, never bare "pre-review" for model
  activity.

### Required tests (record verbatim in 60-test-output.txt)

```text
python3 -m json.tool schemas/auto-review-authorization.schema.json
python3 -m json.tool schemas/runner-receipt.schema.json
python3 -m json.tool reports/agent-runs/_template/status.json
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check <T1-base>..<T1-head>
grep -rn "formal-1" AGENTS.md workflows agents docs schemas reports/agent-runs/_template   # expect no matches
```

### Review-1 unit and focus (Kimi)

Unit: `T1 base..head` diff plus `20-implementation.md` T1 section and raw test
output. Focus, in order:

1. Field-level match of both schemas against 10-design shapes (including
   `expires_at` required+nullable and the three frozen budget numbers).
2. Zero weakening of any existing manual rule — audit every touched sentence
   against the implementer's before/after list; reject silent rewording.
3. Default-off everywhere (templates, workflow, registry, docs).
4. `docs/auto-review-pipeline.md` completeness against 10-design, especially
   the Pilot Evaluation Contract and post-cross-check blocking rule.
5. Locked vocabulary and template E1-pattern change.

### Risks

- Contract-text drift is this stage's highest review-2 exposure; T1 REWORK
  spends the shared ledger, so the packet must point the implementer at exact
  10-design sections rather than paraphrases.
- AGENTS.md edits can silently break unrelated stages — hence the verbatim
  touched-sentence list and the checkpoint validator run on this live stage.

## 4. Task T2 — `seal-and-validator`

**Goal:** the deterministic mechanics: shared library, seal tool, validator
auto support, and their tests. No runner.

**Depends on:** T1 ACCEPT (consumes committed schemas/status shape read-only).

### Writable files

- `scripts/harness_stage_lib.py` (new)
- `scripts/stage-seal.py` (new)
- `scripts/validate-stage.py` (amend)
- `scripts/tests/test_harness_stage_lib.py` (new)
- `scripts/tests/test_stage_seal.py` (new)
- `scripts/tests/test_validate_stage_auto_review.py` (new)

No other new files — no `conftest.py`, no `__init__.py`, no fixtures module.
Shared test helpers (temp git repo builder with isolated env) are defined in
`test_harness_stage_lib.py` and imported by the sibling test modules; runtime
helpers belong in `harness_stage_lib.py`.

### Contracts produced (frozen for T3)

1. `harness_stage_lib.py` public API (stdlib-only):
   - `compute_diff_fingerprint(root, stage_dir, base_sha, head_sha) -> str` —
     byte-identical to the current `validate-stage.py` implementation;
   - byte-preserving git diff capture for a frozen base + ordered pathspecs;
   - patch byte-equality compare;
   - atomic JSON write (temp file + replace);
   - provider-identity normalization (superset of the validator's current
     mapping table);
   - stage/worktree-safe path resolution rejecting traversal and symlink
     escape;
   - hand-written structural validators for the authorization and receipt
     documents (see constraint 2).
2. **Dependency rule:** `validate-stage.py` is intentionally dependency-free
   and stays that way; so do the new scripts. No `jsonschema`, no `yaml`
   import. The T1 schema files are the authoritative written contract; runtime
   checking is hand-written in `harness_stage_lib.py`, and tests must feed the
   same positive/negative fixtures through the hand-written checks so the two
   cannot drift silently.
3. `validate-stage.py` refactor: fingerprint computation delegates to the
   library (single canonical path); auto additions per 10-design (config
   version, substates/transition history, budgets/one-ledger invariants,
   review units, receipt/escalation existence, mode mutex, pilot constraint);
   statuses without `auto_review_pipeline` keep byte-for-byte current behavior.
4. `stage-seal.py` implements the nine-step protocol from the fixed 10-design,
   including step 3 (verify the frozen blocking command set was rerun after
   cross-check evidence landed, with evidence-independent inputs), two-commit
   H_snapshot/H_bind, and fail-closed crash detection (unbound snapshot →
   escalation artifact, deterministic bind recovery, never a second code
   commit).

### Implementation constraints

- Tests build throwaway git repositories under `tempfile` directories with
  isolated identity (`GIT_CONFIG_NOSYSTEM=1`, `HOME` redirected, explicit
  `-c user.name/user.email`); no network, no live models, no product fixtures.
- Fingerprint regression is mandatory in `test_harness_stage_lib.py`:
  recompute a recorded `diff_fingerprint` from at least one historical
  accepted stage's `status.json` in this repository (read-only regression
  input per 00-task) and assert exact equality, plus an in-repo equivalence
  check that the amended validator and the library agree on this stage's
  branch commits.
- `test_validate_stage_auto_review.py` must include the manual-mode regression
  matrix: representative status fixtures without auto fields pass
  `checkpoint`, `dispatch-ready`, `pre-review`, `pre-accept` exactly as today,
  and unknown `runner_state`/transition values fail closed.
- Seal tests must cover the post-cross-check blocking verification (evidence
  writes between the two passes must not change outcomes; a missing or failed
  second pass blocks seal) and bind mismatch fail-closed with no hash written
  to status.

### Required tests (record verbatim)

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check <T2-base>..<T2-head>
```

(The frozen four-command suite from 00-task runs in full in T3, when
`auto-review-runner.py` exists for `py_compile`.)

### Review-1 unit and focus (Kimi)

Unit: `T2 base..head` plus T2 report/test sections. Focus:

1. Fingerprint: single implementation path; regression evidence present and
   exact; no second fingerprint/hash anywhere (bind is byte compare only).
2. Manual-mode regression: current validator behavior provably unchanged for
   auto-less stages; this live stage still passes checkpoint.
3. Seal protocol order, step-3 blocking verification, crash branches, atomic
   status writes, clean-tree gates.
4. Hand-written validators against T1 schema fixtures (both directions:
   valid fixtures pass, each missing/violated field fails).
5. stdlib-only imports; no allowlist-external files created.

### Risks

- `validate-stage.py` is the live gate for every Harness stage; a regression
  here breaks the whole delivery system → the manual-mode matrix is the
  non-negotiable heart of this task.
- Temp-repo tests that accidentally read developer-global git config produce
  flaky results → enforced env isolation.

## 5. Task T3 — `runner-and-integration`

**Goal:** the deterministic runner, its integration tests, and final manifest
sync. Completes the frozen command suite.

**Depends on:** T2 ACCEPT (consumes library/seal/validator read-only).

### Writable files

- `scripts/auto-review-runner.py` (new)
- `scripts/tests/test_auto_review_runner.py` (new)
- `harness-manifest.yaml`

### Contracts produced

1. Runner implements the 10-design state machine exactly: preflight
   (authorization validity/expiry incl. null semantics, exclusive worktree,
   branch, lock), transition matrix and `mode_history`, budgets (a model call
   is charged when adapter execution begins; wall-clock from
   `authorized→running`; restart does not reset the deadline), review units
   with full author-provider sets, blocking → cross-check → identical blocking
   rerun → seal delegation, verdict parsing (final-and-only schema-valid
   block, stage/role/fingerprint match), verdict-record commits, serialized
   multi-owner fix routing with unroutable → escalation, `80-escalation-*`
   artifacts, and stop at `completed_review_1`.
2. Adapter/workflow/registry data reaches the runner through an injectable
   load path so tests substitute fake adapter definitions and fake executables;
   the runner never constructs shell from model output and never uses
   `git add -A` (stages the frozen allowlist only, fails on extra changes).
3. `harness-manifest.yaml` `harness_owned` gains exactly:
   `scripts/harness_stage_lib.py`, `scripts/stage-seal.py`,
   `scripts/auto-review-runner.py`, `scripts/tests/`,
   `docs/auto-review-pipeline.md`. (`schemas/` and `workflows/` directory
   entries already cover the new schema/workflow content.)

### Implementation constraints

- Integration tests cover every 10-design scenario list item, including:
  default-off manual status accepted; preflight rejections before any adapter
  invocation; fake implementation → blocking → cross-check → blocking rerun →
  two-commit seal; post-cross-check blocking with evidence-directory
  mutations; bind mismatch fail-closed; fake Grok ACCEPT to
  `completed_review_1`; invalid JSON retried exactly once per model then
  routed; aggregate auto code-change budget stops at 2; parallel author set
  rejects Kimi/GLM fallback and escalates tip failure; serialized multi-owner
  fixes; crash/resume at each seal/verdict boundary; verdict-record commit
  leaves the reviewed fingerprint unchanged; receipts contain command
  references only (negative test asserts absence of expanded command/env/
  secret-like content).
- No live model, no network, no credential/environment capture in receipts or
  fixtures.

### Required tests (frozen 00-task suite, in full, record verbatim)

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check <T3-base>..<T3-head>
```

### Review-1 unit and focus (Kimi)

Unit: `T3 base..head` plus T3 report/test sections. Focus:

1. No model text ever selects a command, path, transition, or adapter (P2/P13
   audit of every subprocess call site).
2. Budget accounting timing and the shared rework ledger invariant (auto ≤ 2
   within stage cap 3).
3. Provider-isolation including fix authors; parallel-tip empty fallback set →
   human escalation, never GPT/Claude substitution.
4. Receipt negative tests and escalation artifact shape.
5. Manifest completeness against the actual delivered file set.

### Risks

- The runner is the privileged component; any test shortcut that invokes a
  real CLI violates P13/no-network and must be treated as a review-1 P1
  finding.
- Manifest omissions silently break downstream harness sync (template-repo
  carve-out discipline).

## 6. Cross-Task File Ownership Matrix (mutual exclusivity)

| Path | T1 | T2 | T3 |
|---|---|---|---|
| `AGENTS.md`, `stage-delivery.yaml`, `agents/registry.yaml`, `agents/developer-discipline.md` | write | — | — |
| `docs/auto-review-pipeline.md`, `docs/model-adapters.md`, `docs/parallel-development-mode.md`, `reports/agent-runs/README.md` | write | — | — |
| `_template/status.json`, `_template/70-handoff.md` | write | — | — |
| `schemas/auto-review-authorization.schema.json`, `schemas/runner-receipt.schema.json` | write | read | read |
| `scripts/harness_stage_lib.py`, `scripts/stage-seal.py`, `scripts/validate-stage.py` | — | write | read |
| `scripts/tests/test_harness_stage_lib.py`, `test_stage_seal.py`, `test_validate_stage_auto_review.py` | — | write | read |
| `scripts/auto-review-runner.py`, `scripts/tests/test_auto_review_runner.py` | — | — | write |
| `harness-manifest.yaml` | — | — | write |
| `schemas/review-verdict.schema.json` | read | read | read |
| Stage evidence dir (report/test-output appends per §2) | shared | shared | shared |

No path has two writers. A task needing a change in another task's file stops
and escalates to the bookkeeper for either re-sequencing or a recorded design
amendment; it does not edit across the boundary, and REWORK fixes stay inside
the unit under review.

## 7. Per-Task Delivery Loop (manual DRAFT-2, applies to each of T1/T2/T3)

1. Bookkeeper freezes `base_sha`, prepares the dispatch packet (below), human
   operator dispatches Claude-GLM.
2. Implementer writes only its §3–§5 file set, appends its
   `20-implementation.md` section (including the touched-sentence list for T1)
   and raw test output.
3. Bookkeeper verifies boundaries (`git status` against the ownership matrix),
   runs the task's required commands, commits the task delivery, records
   `base_sha`/`head_sha`/`diff_fingerprint` in `status.json.tasks[]`, runs
   `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase
   pre-review` on the clean tree before review dispatch.
4. Human operator dispatches fresh read-only Kimi review-1 with the recorded
   range and raw paths; verdict lands as `30-review-1-<task-id>.md` plus the
   unaltered JSON verdict; invalid JSON follows the existing
   retry-once-then-escalate contract.
5. REWORK → human operator dispatches the reviewer's `fix_start_prompt` to
   Claude-GLM; bookkeeper increments the shared `rework_count`; loop within
   this task only. ACCEPT → next task.
6. After T3 ACCEPT: review-2 remains blocked until the operator resolves the
   independent-reviewer route (Gemini enablement vs disclosure override);
   this breakdown adds Anthropic breakdown authorship to that disclosure.

Dispatch packet minimum contents (bookkeeper prepares; human executes):
task id and goal; the task's writable/forbidden lists verbatim; the frozen
contract references (exact 10-design/00-task section names); required test
commands verbatim; report/evidence paths; locked-vocabulary reminder; the
instruction that implementer sessions never commit, never write status/handoff,
and stop-and-escalate on any boundary conflict.

Recommended (non-blocking): bookkeeper runs
`scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase
dispatch-ready` once before the T1 dispatch and archives the output in
`60-test-output.txt`.

## 8. Out Of Scope / Not Authorized Here

- No implementation, no code, no schema content beyond what T1–T3 define.
- No model dispatch of any kind (preparation only, human executes).
- No review-2 routing selection; no auto-mode enablement for this stage; no
  default flip; no pilot execution.
- No edits to `agents/skills/*` (removed from allowlist, §2), no new files
  outside the §6 matrix, no product/runtime paths.

本地北京时间: 2026-07-11 12:43:02 CST
下一步模型: Codex/GPT（bookkeeper）
下一步任务: 落盘本 breakdown（status.json 填 breakdown_author/tasks[] 三条目并 checkpoint），随后准备 T1 dispatch packet 交人工执行；实现仍未授权，须待 packet 与操作者确认
