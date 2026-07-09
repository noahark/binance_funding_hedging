# Agent Run Blackboard

Each workflow stage gets one directory:

```text
reports/agent-runs/<stage-id>/
  00-intake.md
  00-task.md
  10-design.md
  11-adr.md
  12-development-breakdown.md   (MEDIUM/HIGH/MILESTONE stages)
  20-implementation.md
  embedded-review-<task-id>-round<N>.diff.patch      (parallel-mode checkpoint)
  embedded-review-<task-id>-round<N>.prompt-for-<reviewer>.md
  embedded-review-<task-id>-round<N>.raw-output.md
  embedded-review-<task-id>-round<N>.fix-note.md     (when fixed)
  pre-review-task-<task-id>-by-<reviewer>.prompt.md
  30-review-1.md
  30-review-1-<task-id>.md   (optional for multi-task stages)
  40-fix-report.md
  50-review-2.md
  60-test-output.txt
  70-handoff.md
  status.json
```

Use `_template/` when creating a new stage.

Direction files are required only for milestone or user-requested direction
freeze rounds. Each registered panel member for the round writes one draft:

```text
direction-drafts/<model-id>.md
direction-drafts/<model-id>.unavailable.md   (when a member is unavailable)
06-direction-synthesis.md
```

The panel roster is declared in `agents/registry.yaml` under
`direction_panels.<stage_key>` (stage-id with `-` replaced by `_`), falling
back to `direction_panels.default`. Record the panel key used in
`status.json`.

Drafts and intermediate outputs must remain in the stage directory. Approved
project documents are promoted into fixed paths under `docs/`:

```text
docs/product/PRD.md
docs/architecture/ARCHITECTURE.md
docs/architecture/ADR/
docs/development/DEVELOPMENT_GUIDE.md
docs/planning/ROADMAP.md
docs/planning/DECISIONS.md
```

## Ownership

| File | Owner | Purpose |
|---|---|---|
| `00-intake.md` | Bookkeeper / stage operator | User discussion summary, complexity classification, routing decision |
| `00-task.md` | Designer | Scope, non-goals, acceptance criteria, file boundaries |
| `direction-drafts/<model-id>.md` | Registered panel member | Independent direction and requirement draft, or `.unavailable.md` note |
| `06-direction-synthesis.md` | GPT/Codex | Conditional final synthesized direction for user review |
| `10-design.md` | Designer | Architecture, task split, risks, test strategy |
| `11-adr.md` | Designer | Stage decision context, alternatives, tradeoffs, reviewer notes |
| `12-development-breakdown.md` | Breakdown author | Implementation boundaries, contracts, tests, owner split, review focus |
| `20-implementation.md` | Implementer | Changed files, decisions, tests, remaining work |
| `embedded-review-<task-id>-round<N>.*` | Implementer-dispatched fresh reviewer | Pre-commit embedded cross-review checkpoint; not formal review-1 |
| `pre-review-task-<task-id>-by-<reviewer>.prompt.md` | Designer / bookkeeper | Prewritten prompt used by the implementation terminal's R10 dispatch tail |
| `30-review-1.md` | Reviewer | First review findings and strict JSON verdict |
| `30-review-1-<task-id>.md` | Reviewer | Task-specific cross-review verdict for multi-task stages |
| `40-fix-report.md` | Implementer | Fix mapping and retest evidence |
| `50-review-2.md` | Final reviewer | Final raw-artifact review and strict JSON verdict |
| `60-test-output.txt` | Bookkeeper / stage operator | Raw or scrubbed command output |
| `70-handoff.md` | Bookkeeper / stage operator | Current facts, artifact index, next action |
| `status.json` | Bookkeeper / stage operator | Machine-readable stage status |

Reviewers must not edit implementation reports. Implementers must not edit
formal review files. Only the bookkeeper updates `status.json`, git commits,
and committed review fingerprints.

## Status Values

Allowed values:

```text
planned
designing
implementing
testing
review_1
fixing
review_2
accepted
paused
decision_models_exhausted
development_models_exhausted
stage_accepted_waiting_user
human_escalation_required
blocked
abandoned
```

Terminal stop reasons are limited to:

- `decision_models_exhausted`
- `development_models_exhausted`
- `stage_accepted_waiting_user`
- `human_escalation_required`

`blocked` and `abandoned` are retained-branch bookkeeping states. They must map
to one of the terminal stop reasons above in `terminal_reason` or
`human_escalation.reason`.

## Evidence Rules

- Store enough output to reproduce the conclusion.
- Scrub credentials and tokens before committing reports.
- Mark stale or skipped tests explicitly.
- Contract amendments that change previously frozen API/data contracts must
  include raw public samples under `reports/api-samples/<stage>/`. Synthetic
  fixtures can cover edge cases but cannot replace fact evidence.
- New delivery stages should record a `stage_branch` object in `status.json`.
  When `stage_branch.name` is non-empty, all stage evidence commits before user
  acceptance stay on that branch, normally named `stage/<stage-id>`.
- `review-2 ACCEPT` enters `stage_accepted_waiting_user`; it does not merge the
  stage branch to `main`. Merge or fast-forward to `main` happens only after
  explicit user acceptance.
- Harness/template sync commits land on `main` and must not be mixed into an
  active stage branch unless the stage explicitly needs the new Harness
  behavior. If `main` is merged into a stage branch by exception, record the
  reason, rerun tests and validator, recompute fingerprints, and re-enter or
  mechanically rebind review gates as required. Rebase is forbidden.
- Failed or abandoned stage branches are retained as evidence and are not
  merged to `main`.
- Before review, commit the stage artifacts locally. Local review commits are
  Harness evidence; they do not imply push, merge, deploy, or final acceptance.
- Record `base_sha`, `head_sha`, and `diff_fingerprint` before review.
- `diff_fingerprint` is the single committed-state scheme:
  `head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")`.
  `status.json` is excluded because it stores the fingerprint. Do not use
  worktree fingerprints or alternate fingerprint fields.
- `head_sha` is delivery-anchored: it points at the delivery commit review
  inspects. Later auxiliary commits (status-only metadata, handoff updates,
  validator evidence re-anchor) do not move `head_sha` unless the stage
  explicitly re-anchors and re-runs `validate-stage.py --phase pre-review`. See
  the "Evidence Conventions" section of `docs/independent-task-branch-mode.md`.
- A committed validator log obeys the fixed-point property: it cannot contain
  the fingerprint of the commit that contains itself. A committed
  `61-validate-pre-review.txt` records a pre-inclusion snapshot; the
  authoritative final fingerprint is always `status.json.diff_fingerprint`.
- Capture validator evidence with `validate-stage.py --phase pre-review
  --evidence-out <path>` instead of `... | tee <path>`. `--evidence-out` checks
  a clean worktree first and writes the evidence file only after every check
  passes, so evidence capture no longer dirties the worktree before the
  clean-worktree check.
- For single-owner stages, validator evidence must be inside or reconciled with
  the reviewed range. Commit the evidence before anchoring `head_sha`, or
  recompute `head_sha` / `diff_fingerprint` after the evidence commit
  (re-running `record-checkpoint --single-owner` re-anchors to the current tip).
  `record-checkpoint --single-owner` now writes top-level `status.json` review
  metadata (`base_sha`, `head_sha`, `diff_fingerprint`, `changed_files`);
  `--dry-run` prints those fields with no repository mutation (no `git add`,
  no `git commit`, no `status.json` write, `HEAD` and index unchanged).
- Review prompts and reviewer commands must use the recorded
  `<base_sha>..<head_sha>` range, not a moving `HEAD`, because unrelated Harness
  commits may be added after a stage is frozen.
- Model dispatch must follow `docs/model-adapters.md`. A bookkeeper or
  implementation session that lacks a built-in tool for a model must not skip
  the runner-level CLI adapter check.
- For stages using `docs/parallel-development-mode.md`, every implementation
  task prompt must include the R10 dispatch tail: exact self-test commands,
  exact diff command, exact prewritten cross-review adapter command, artifact
  paths, PASS/BLOCKER handling, and receipt block.
- A `next_dispatch` marked `executor: self` is executable work, not a note. The
  implementation terminal must execute it or write an escalation reason before
  reporting completion.
- Embedded cross-review checkpoints happen before committed review gates. They
  may catch and fix local issues, but they do not replace formal review-1 after
  the bookkeeper creates committed H_A/H_B evidence.
- Before committing task evidence in a parallel-mode stage, the bookkeeper must
  regenerate the task diff and reconcile it with the implementer-produced
  `embedded-review-*.diff.patch`. Differences require a fix note or escalation.
- Run `scripts/validate-stage.py <stage-id> --phase pre-review` before
  dispatching `review-1` or `review-2`.
- Run `scripts/validate-stage.py <stage-id> --phase pre-accept` before writing
  `accepted` or `stage_accepted_waiting_user`.
- `review_1` and `review_2` verdicts are tracked separately.
- Multi-task stages should record each implementation task in
  `status.json.tasks` with owner, reviewer, base_sha, head_sha,
  diff_fingerprint, review verdict, and test evidence path. Task-specific
  cross-review files should use `30-review-1-<task-id>.md`.
- Parallel-mode embedded checkpoint history belongs in the top-level
  `status.json.embedded_reviews` object, using the rich structure defined in
  `docs/parallel-development-mode.md` section 5. Do not duplicate a second
  embedded review schema under `tasks[]`.
- A `REWORK` verdict must include `fix_start_prompt`, a ready-to-send prompt
  for the fix implementer that preserves raw artifact paths, findings, required
  fixes, file boundaries, and verification commands.
- All review verdict JSON objects must include `reviewer_prior_involvement`.
- A final reviewer may overlap with the designer, direction synthesizer, or
  development breakdown author only through the strong-reviewer disclosure
  override: the status must record prior involvement, fallback reason, and an
  existing evidence file proving the unrelated decision model was unavailable.
- A final reviewer must never share provider identity with any implementation
  or fix author for the reviewed code.
- The same model may emit invalid verdict JSON at most twice for a gate; after
  two invalid attempts, route that model as unavailable for the gate.
- A stage is not accepted until `status.json`, `70-handoff.md`, test output, and
  schema-valid review verdicts agree.

## 报告语言偏好 (Reporting Language Preference)

`status.json` may carry a top-level `reporting_preferences` object that stages
and dispatch packets can read to set the report language:

```json
"reporting_preferences": {
  "primary_language": "zh-CN",
  "explain_english_terms": true,
  "preserve_exact_strings": [
    "commands", "file_paths", "json_keys", "schema_fields",
    "code_identifiers", "model_names", "provider_identifiers"
  ]
}
```

When `primary_language` is set (for example `zh-CN`), model-facing reports,
handoffs, review narratives, and significant bookkeeper responses default to
that language's prose. `explain_english_terms=true` asks the author to add a
short Chinese explanation for necessary English technical terms on first use.

`preserve_exact_strings` lists the string classes that must stay in their exact
English form and are never translated. This preference affects narrative prose
and dispatch prompt text only; it must never alter strict JSON verdict keys,
schema fields, commands, file paths, code identifiers, model names, or provider
identifiers.

中英混排示例（correct mixed-language usage）:

- `fingerprint`（指纹，用于绑定被审 diff 的哈希）
- `delivery-anchored head_sha`（交付锚定的 `head_sha`，即 `head_sha` 锚定在代码
  交付提交而非后续辅助提交）
- `provider identity`（提供方身份，例如 `claude_glm` 的提供方身份是
  `zhipu_glm`，不是 `anthropic`）
- `fix_start_prompt`（返工修复启动提示，REWORK 判决中给修复实现者的可发送提示）

The dispatch templates in `workflows/templates/stage-delivery.yaml` may inject
this preference into prompt headers so future reports default to the requested
language without corrupting exact machine strings.

## Report Footer

Model-facing reports and handoffs should end with:

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

The timestamp must be copied from a local `date` command. Do not guess it from
model memory. For strict JSON verdict files, place the footer before the final
JSON block or in schema-approved fields so the verdict remains parseable.
