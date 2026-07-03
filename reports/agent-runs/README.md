# Agent Run Blackboard

Each workflow stage gets one directory:

```text
reports/agent-runs/<stage-id>/
  00-intake.md
  00-task.md
  10-design.md
  11-adr.md
  20-implementation.md
  30-review-1.md
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
| `00-intake.md` | Controller | User discussion summary, complexity classification, routing decision |
| `00-task.md` | Designer | Scope, non-goals, acceptance criteria, file boundaries |
| `direction-drafts/<model-id>.md` | Registered panel member | Independent direction and requirement draft, or `.unavailable.md` note |
| `06-direction-synthesis.md` | GPT/Codex | Conditional final synthesized direction for user review |
| `10-design.md` | Designer | Architecture, task split, risks, test strategy |
| `11-adr.md` | Designer | Stage decision context, alternatives, tradeoffs, reviewer notes |
| `20-implementation.md` | Implementer | Changed files, decisions, tests, remaining work |
| `30-review-1.md` | Reviewer | First review findings and strict JSON verdict |
| `40-fix-report.md` | Implementer | Fix mapping and retest evidence |
| `50-review-2.md` | Final reviewer | Final raw-artifact review and strict JSON verdict |
| `60-test-output.txt` | Controller | Raw or scrubbed command output |
| `70-handoff.md` | Controller | Current facts, artifact index, next action |
| `status.json` | Controller | Machine-readable stage status |

Reviewers must not edit implementation reports. Implementers must not edit
review files. Only the controller updates `status.json`.

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
```

Terminal stop reasons are limited to:

- `decision_models_exhausted`
- `development_models_exhausted`
- `stage_accepted_waiting_user`
- `human_escalation_required`

## Evidence Rules

- Store enough output to reproduce the conclusion.
- Scrub credentials and tokens before committing reports.
- Mark stale or skipped tests explicitly.
- Record `base_sha`, `head_sha`, and `diff_fingerprint` before review.
- `diff_fingerprint` is
  `head_sha + ":" + sha256(git diff --binary <base_sha>..HEAD)`.
- `review_1` and `review_2` verdicts are tracked separately.
- A `REWORK` verdict must include `fix_start_prompt`, a ready-to-send prompt
  for the fix implementer that preserves raw artifact paths, findings, required
  fixes, file boundaries, and verification commands.
- A stage is not accepted until `status.json`, `70-handoff.md`, test output, and
  schema-valid review verdicts agree.
