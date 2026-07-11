# Stage Design: Auto Review Pipeline v1

## Summary

Implement an additive, default-off Harness execution mode around a deterministic
local runner. The runner owns automatic control-plane actions, while existing
model sessions remain bounded workers that receive immutable prompt bodies and
return untrusted output.

The design preserves the current human workflow as the compatibility path and
does not change top-level stage statuses or the committed-range fingerprint
formula. Auto mode adds a versioned substate, human authorization, budgets,
review units, receipts, and explicit evidence commits.

This stage itself is a bootstrap delivery and continues to use current DRAFT-2
human dispatch. Nothing in this design authorizes implementation.

## Design Principles

1. **One authority per concern:** workflow files define transitions; registry
   defines adapters; runner executes deterministic transitions; models provide
   bounded implementation/review content; humans retain product/final gates.
2. **Default-off compatibility:** missing auto fields are interpreted as manual
   mode, not malformed auto mode.
3. **Committed truth:** formal review binds only committed ranges using the
   existing fingerprint.
4. **No model-driven control flow:** model content is data, never a command or
   transition source unless a schema-valid verdict maps to a fixed transition.
5. **Fail closed with evidence:** every automatic stop produces a durable
   reason, receipt references, and next permitted human action.
6. **No silent identity broadening:** reviewer eligibility is calculated from
   every author provider in the exact review unit.

## Assumptions

- Git and a stage branch already exist.
- Auto mode runs in a dedicated stage integration worktree.
- Adapter availability and command templates remain defined in
  `agents/registry.yaml` / `docs/model-adapters.md`.
- The current verdict schema remains sufficient for v1; multi-owner routing is
  runner metadata, not a schema amendment.
- Python standard library plus git commands are sufficient; Harness runtime
  scripts remain dependency-free.
- Human approval can be represented as a committed schema-valid artifact plus
  status reference; the runner does not infer approval from chat text.

## Component Architecture

### `scripts/harness_stage_lib.py`

A small shared module for pure, reusable Harness mechanics:

- canonical `compute_diff_fingerprint` implementation used by validator and
  seal;
- git command wrapper with byte-preserving diff output;
- stage path resolution and safe relative-path checks;
- provider-identity normalization shared by runner/validator;
- JSON load/write helpers that use atomic temporary-file replacement;
- patch byte comparison helpers.

This module must not contain workflow judgment or model routing policy.

### `scripts/stage-seal.py`

The sole automatic seal primitive. It:

1. verifies authorization, branch, worktree, status, allowed paths, and the
   expected runner lock;
2. verifies blocking checks and required embedded cross-check evidence;
3. compares the captured and regenerated code-scope patches byte-for-byte;
4. creates the review snapshot commit;
5. computes the existing fingerprint from the selected base to snapshot head;
6. writes mechanical status fields and seal receipt;
7. creates a binding/evidence commit after the snapshot;
8. runs `validate-stage.py --phase pre-review` on a clean tree.

It does not invoke models and does not decide whether a finding is acceptable.

### `scripts/auto-review-runner.py`

The deterministic state-machine executor. It:

- loads workflow, registry, status, authorization, and task/review-unit data;
- owns automatic adapter invocation and per-call receipt creation;
- enforces budgets, transition matrix, provider isolation, and path scopes;
- invokes blocking checks from frozen task metadata;
- invokes embedded cross-check/review-1/fix workers through registry command
  references;
- validates verdict output before applying a fixed transition;
- delegates seal mechanics to `stage-seal.py`;
- writes deterministic handoff/escalation templates;
- stops before review-2.

It must not synthesize narrative requirements, select new files, create shell
commands from model output, or invoke GPT/Claude automatically.

### `scripts/validate-stage.py`

Remains the executable gate. Auto additions validate:

- configuration/version and authorization reference;
- allowed auto substates and transition history;
- budget accounting and one-ledger invariants;
- review-unit shape, author providers, fingerprints, verdict completeness;
- receipt/verdict/escalation artifact existence;
- manual/auto mode mutual exclusion;
- pilot/default-flip constraints.

Legacy status files without `auto_review_pipeline` retain current behavior.

### Schemas

- `schemas/auto-review-authorization.schema.json` validates human authority and
  fixed budgets/scope.
- `schemas/runner-receipt.schema.json` validates invocation provenance without
  storing expanded commands or secrets.
- `schemas/review-verdict.schema.json` is read-only in v1.

### Contract Documents

- `AGENTS.md`: hard permission boundary and human gates.
- `stage-delivery.yaml`: optional nodes/transitions and acceptance predicates.
- `agents/registry.yaml`: runner-owned auto invocation policy and Grok review
  adapter reference.
- `docs/auto-review-pipeline.md`: normative human-readable auto contract.
- `docs/parallel-development-mode.md`: mutual exclusion/migration wording and
  terminology update to embedded cross-check.
- templates: versioned status and handoff fields, default disabled.

## Machine-Readable Configuration

### Status Shape

The following is the normative v1 shape. It is nested under status and does not
add top-level workflow statuses.

```json
{
  "auto_review_pipeline": {
    "schema_version": 1,
    "enabled": true,
    "dispatch_mode": "auto_review",
    "mode_flip_pending": null,
    "authorization_path": "reports/agent-runs/<stage>/auto-run-authorization-v1.json",
    "runner_state": "authorized",
    "runner_version": "auto-review-pipeline/v1",
    "exclusive_worktree": {
      "path": "<absolute-or-runner-resolved-path>",
      "stage_branch": "stage/<stage-id>",
      "verified": true
    },
    "budgets": {
      "max_model_calls": 12,
      "model_calls_used": 0,
      "wall_clock_seconds": 3600,
      "run_started_at": null,
      "run_deadline_at": null,
      "max_stage_rework": 3,
      "max_auto_code_changes": 2,
      "auto_code_changes_used": 0
    },
    "mode_history": [],
    "review_units": [],
    "embedded_cross_checks": [],
    "last_receipt_path": null,
    "last_escalation_path": null
  }
}
```

The numbers above illustrate shape only. Each stage authorization freezes its
own positive `max_model_calls` and `wall_clock_seconds`; v1 has no global numeric
defaults beyond the frozen rework values.

Allowed `runner_state` values:

- `authorized`
- `running`
- `awaiting_human`
- `stopped`
- `completed_review_1`

Unknown values fail closed. These are auto substates, not top-level Harness
statuses.

Legacy `parallel_mode.enabled=true` and `auto_review_pipeline.enabled=true` are
mutually exclusive. Auto mode may still authorize `scope.topology=parallel`,
but it uses the new runner/task-worktree/cross-check contract rather than
inheriting the historical R1–R10 embedded checkpoint semantics.

### Authorization Artifact

Normative path:

`reports/agent-runs/<stage-id>/auto-run-authorization-v<N>.json`

Required fields:

```json
{
  "schema_version": 1,
  "stage_id": "<stage-id>",
  "stage_branch": "stage/<stage-id>",
  "contract_version": "auto-review-pipeline/v1",
  "authorized": true,
  "authorized_by": "human",
  "approval_evidence_path": "reports/agent-runs/<stage>/auto-run-authorization-v1.approval.md",
  "approval_recorded_by": "bookkeeper",
  "authorized_at": "<ISO8601>",
  "expires_at": null,
  "scope": {
    "task_ids": ["<task-id>"],
    "allowed_pathspecs": ["<path>"],
    "forbidden_pathspecs": ["<path>"],
    "topology": "serial"
  },
  "allowed_adapters": ["claude_glm", "kimi", "grok"],
  "review_1_provider": "grok",
  "budgets": {
    "max_model_calls": 12,
    "wall_clock_seconds": 3600,
    "max_stage_rework": 3,
    "max_auto_code_changes": 2,
    "invalid_json_max_attempts_per_model": 2
  },
  "auto_high_end_dispatch_allowed": false,
  "supersedes": null
}
```

Rules:

- `authorized_by` must be human; `approval_evidence_path` must point to the
  committed operator approval receipt and `approval_recorded_by` must identify
  the non-implementer bookkeeper that recorded it. Model claims are invalid.
- `max_stage_rework` must equal 3, `max_auto_code_changes` must be at most 2,
  and invalid JSON attempts must equal current contract value 2.
- Scope/adapter/budget changes require a new versioned authorization artifact
  whose `supersedes` points to the prior artifact.
- Runner refuses an expired artifact or mismatch with current stage/branch.
- The authorization artifact is never generated or edited by an implementer.

### Runner Receipt

Normative flat path:

`reports/agent-runs/<stage-id>/runner-<seq>-<node>.receipt.json`

Required fields include:

- schema version, stage id, sequence, node, attempt, review unit/task id;
- adapter id and registry command reference;
- prompt path, raw output path, verdict path when applicable;
- started/completed timestamps, exit status, timeout flag;
- call-budget before/after values;
- sanitized failure class and next fixed transition.

Forbidden fields include expanded command, environment, token, cookie, secret,
or arbitrary model-selected next action.

## Transition Model

### Dispatch Mode And Runner State

`dispatch_mode` has only two values: `human_dispatch` (default) and
`auto_review` (authorized). Lifecycle values belong only to `runner_state`.

Allowed transitions:

| Dispatch mode | Runner state from→to | Trigger | Top-level status/effect |
|---|---|---|---|
| human_dispatch→auto_review | disabled→authorized | new human authorization | runner may start |
| auto_review | authorized→running | successful full preflight | automatic loop starts |
| auto_review | running→awaiting_human | recoverable worktree/runner/adapter fallback condition | set `mode_flip_pending=human_dispatch`, top-level `paused`, write evidence, stop |
| auto_review→human_dispatch | awaiting_human→disabled | explicit human mode-flip decision | human may use current DRAFT-2 path |
| auto_review | awaiting_human→authorized | new/superseding human authorization | clear pending flip and rerun full preflight |
| auto_review | running→stopped | operator stop | no further calls |
| auto_review | running→completed_review_1 | all required units ACCEPT | stop before review-2 |
| auto_review | running→awaiting_human | cap, timeout, budget, unroutable fix, or tip-once Grok failure | top-level `human_escalation_required`, write `80-*.md`, stop |

No automatic transition from a failed auto path directly into model dispatch in
human mode is allowed. The runner records the pending mode flip or terminal
escalation and stops; human action is required to resume.

### Call And Wall-Clock Accounting

- A model call is charged immediately before starting a registry adapter process.
- Success, timeout, provider failure, invalid JSON, and empty output all consume
  one call.
- Pure local availability probes and git/test commands do not consume model-call
  budget but do produce evidence when used for routing.
- Invalid JSON retry consumes calls but not rework.
- Wall-clock starts when runner changes `authorized` to `running` and includes
  all automatic work until stop/completion.
- A process restart does not reset the deadline.
- Resume after `awaiting_human` requires new authorization and a newly frozen
  budget; historical usage remains recorded.

### Rework Accounting

One top-level `rework_count` remains authoritative.

- Initial implementation does not charge rework.
- P7 blocking-test automatic fix charges 1.
- Each review-1 REWORK that enters code-changing fix charges 1.
- Review-2 REWORK charges 1 under the existing human path.
- Automatic charges stop at 2 even if total stage cap 3 is not yet reached.
- Invalid JSON, provider retry without code change, and cross-check unavailable
  do not charge rework, but do charge call budget when an adapter was started.

## Worktree And Task Topology

### Exclusive Integration Worktree

The runner owns one integration worktree attached to the stage branch. Auto
preflight verifies:

- exact branch match;
- worktree is registered and not used by another active runner lock;
- no unrelated dirty/untracked path;
- every dirty path is inside the active task's authorization allowlist;
- stage status and authorization reference agree.

The lock is runtime-only under git metadata and is never committed.

### Serial Topology

Each task runs to review-1 ACCEPT before the next task begins.

For task `T`:

1. runner freezes `T.base_sha` at current integration HEAD;
2. implementer writes allowed paths;
3. blocking checks run;
4. optional/required embedded cross-check runs;
5. seal produces `T.head_sha` and fingerprint;
6. Grok reviews unit `T`;
7. verdict-record commit lands outcome;
8. REWORK loops only within `T`; ACCEPT unlocks next task.

After the last task, the runner computes a code-scope diff from the last task
head to candidate final code head. Evidence/status-only changes do not create an
integration unit. A non-empty code-scope diff creates one required integration
unit.

### Parallel Topology

Initial implementation uses isolated task worktrees/branches from a common
base. Models never commit. The runner:

1. checks each task boundary and blocking evidence;
2. creates runner-owned task commits;
3. applies task commits without committing, in frozen task-id order, to the
   exclusive integration worktree;
4. rejects conflicts or out-of-bound integration as escalation;
5. performs required per-task embedded cross-checks and binds each task's
   code-scope/pathspec against the integrated uncommitted tip;
6. runs unified blocking checks;
7. seals one integrated tip review unit;
8. sends that unit once to Grok review-1.

For v1, a tip REWORK that spans owners is fixed serially in the integration
worktree, one frozen domain assignment at a time. Parallel multi-owner fix
writes are deferred. After all owners finish, the runner reruns unified checks,
cross-check/bind, and seal.

## Embedded Cross-Check And Seen-Diff Bind

### Required Attempt Rule

The stage design/authorization records `required_attempt` explicitly. Runner
does not infer “high contract risk” from prose.

- parallel/two-owner: required attempt;
- explicitly high-contract-risk: required attempt;
- other serial/single-owner: optional.

Unavailable required cross-check is fail-open for review-1 but must produce an
unavailable artifact and set bind to `N/A`.

### Artifact Paths

- `embedded-cross-check-<unit>-round<N>.prompt.md`
- `embedded-cross-check-<unit>-round<N>.seen.diff.patch`
- `embedded-cross-check-<unit>-round<N>.raw-output.md`
- `embedded-cross-check-<unit>-round<N>.unavailable.md` when not run
- `runner-<seq>-embedded-cross-check.receipt.json`

### Bind Algorithm

1. Freeze `base_sha` and exact ordered pathspec list.
2. Capture raw bytes from `git diff --binary <base_sha> -- <pathspecs>` before
   cross-check and store them as the seen patch.
3. Seal the review snapshot.
4. Regenerate raw bytes from
   `git diff --binary <base_sha>..<snapshot_head> -- <same-pathspecs>`.
5. Compare byte-for-byte.
6. Mismatch escalates; no hash/status fingerprint is written.

Evidence paths under the current stage directory are excluded from code-scope.
The pathspec list itself is recorded in status/receipt so comparison cannot be
silently narrowed.

## Seal And Commit Protocol

The fingerprint remains:

```text
head_sha + ":" + sha256(
  git diff --binary <base_sha>..<head_sha> -- .
  ":(exclude)reports/agent-runs/<stage-id>/status.json"
)
```

Seal is a two-commit mechanical transaction because `head_sha` is not known
until after the snapshot commit:

1. **H_snapshot:** commit allowed implementation, tests, reports, blocking
   evidence, and embedded cross-check artifacts. Status may be unchanged.
2. Compute fingerprint using canonical shared function.
3. Atomically update status review-unit/base/head/fingerprint fields and write
   the seal receipt.
4. **H_bind:** commit only status, deterministic handoff fields, and seal
   receipt. Do not change code-scope.
5. Require clean tree and run validator against the recorded snapshot.

The formal reviewer receives the recorded snapshot range, not moving HEAD.
H_bind is evidence after `head_sha`, which existing rules permit.

Crash recovery is fail-closed:

- crash before H_snapshot: no sealed unit; rerun preflight;
- crash after H_snapshot before H_bind: runner detects an unbound snapshot,
  writes escalation, and requires deterministic bind recovery using the exact
  commit—never a second code commit;
- crash after H_bind: validator/receipt determine whether review may begin.

## Review Unit Model

Each status review unit contains:

```json
{
  "id": "task-a",
  "kind": "task",
  "required": true,
  "task_ids": ["task-a"],
  "base_sha": null,
  "head_sha": null,
  "diff_fingerprint": null,
  "code_pathspecs": ["scripts/**"],
  "author_provider_identities": ["zhipu_glm"],
  "embedded_cross_check": {
    "required_attempt": false,
    "status": "pending",
    "seen_patch_path": null,
    "bind_status": "pending"
  },
  "review_1": {
    "provider": null,
    "verdict": null,
    "json_schema_valid": false,
    "verdict_path": null
  }
}
```

`kind` is `task`, `tip`, or `integration`. Review-1 eligibility is evaluated
against the full `author_provider_identities` set, including every fix author
who changed the current snapshot.

Review-1 completeness predicate:

```text
all(unit.required implies
    unit.review_1.verdict == ACCEPT and
    unit.review_1.json_schema_valid == true and
    unit.review_1.diff_fingerprint == unit.diff_fingerprint)
```

Only then may runner stop at `completed_review_1` for human review-2.

## Review-1 Routing And Verdict Boundary

### Primary And Fallback

- Auto primary: `grok` / `grok-build` plan mode.
- Serial task fallback: existing cross-pool candidate only if its normalized
  provider identity is absent from that unit's author set.
- Parallel tip: Kimi/GLM cross-pool is ineligible when both authored code;
  Grok failure or repeated invalid verdict escalates.
- GPT/Claude are never automatically substituted.

### Output Parsing

Raw stdout is always saved first. The runner enumerates complete top-level JSON
object candidates in the output and accepts only when:

1. exactly one candidate validates against `review-verdict.schema.json`;
2. that candidate is the final non-whitespace structured block;
3. its stage id, role, and fingerprint match the active review unit;
4. no second schema-valid verdict exists in the stream.

The accepted bytes are saved unaltered as:

`review-1-<unit>-round<N>.verdict.json`

Prose/footer stays only in:

`review-1-<unit>-round<N>.raw-output.md`

No regex-mined or bookkeeper-rewritten JSON may pass.

### Verdict-Record Commit

After validation, runner writes status and commits:

- raw output;
- exact verdict JSON;
- receipt;
- deterministic handoff/status updates.

This commit never changes the review unit's base/head/fingerprint. A REWORK
transition increments the ledger only when code-changing fix dispatch begins.

## Multi-Owner Fix Routing

The full reviewer `fix_start_prompt` is preserved for every assigned owner. A
runner-generated immutable header adds:

- active unit/fingerprint;
- owner provider/domain;
- exact finding indexes and file paths assigned;
- allowed/forbidden paths;
- frozen test commands;
- “fix only your assigned findings” instruction.

Routing uses `findings[].file` plus frozen task ownership. Missing/ambiguous
paths, shared-contract changes, or cross-boundary requirements are unroutable
and escalate. The runner never guesses from natural-language title text.

In v1, owners modify the integration worktree serially. Each owner receives a
fresh bounded session and produces a separate fix report/receipt. Unified tests
and reseal occur only after every assigned owner finishes.

## Security And Trust Boundary

- Code, comments, reports, prompts returned by models, and raw outputs are
  untrusted data.
- Only committed workflow/registry mappings select commands/transitions.
- Model-provided shell snippets are never executed.
- Prompt bodies explicitly tell reviewers that reviewed artifacts may contain
  prompt-injection text.
- Adapter invocation uses registry command references and argument arrays or
  vetted wrappers; receipts never persist expanded aliases or environment.
- Secret-bearing environment may be passed to the adapter process when needed
  but is not copied, displayed, diffed, or serialized.
- Paths are resolved under the authorized worktree/stage directory; traversal
  and symlink escape fail closed.
- Raw output is persisted, but runner redaction is not permitted to rewrite it;
  if provider output itself exposes a secret, stop, restrict artifact access,
  and escalate rather than silently normalize evidence.

## Escalation Contract

Normative path:

`reports/agent-runs/<stage-id>/80-escalation-<reason>-<UTC timestamp>.md`

Required content:

- stage/mode/runner version;
- current status and review unit;
- snapshot fingerprint when one exists;
- rework and budget usage;
- raw output/verdict/receipt/test paths;
- sanitized failure class;
- allowed next actions (`human_dispatch`, new authorization, task/design
  amendment, or terminal human escalation).

Status records `last_escalation_path` and changes runner substate to
`awaiting_human`. Cap, timeout, budget, unroutable fix, and tip-once Grok
failure always set top-level `human_escalation_required` as frozen in the
decision table. Recoverable D5 preflight/mode-fallback conditions use existing
top-level `paused` until the human chooses a mode.

## Bootstrap Stage Implementation Topology

This stage does not self-host auto mode.

Provisional serial work packages for development breakdown:

1. **Contract and schemas:** AGENTS/workflow/registry/docs/templates/new schemas.
2. **Seal and validator mechanics:** shared library, stage-seal, validator,
   deterministic tests.
3. **Runner and integration:** runner, receipts, budget/transition/review-unit
   behavior, integration tests, manifest/docs final sync.

Default implementation provider for all packages: Claude-GLM (`zhipu_glm`).
This avoids mixed-provider code authorship for a control-plane-only stage and
keeps review-1 routing to fresh Kimi (`moonshot_kimi`) straightforward.

The development breakdown may merge packages but may not parallelize writes to
shared authority files. Current `parallel_mode.enabled` remains false.

Review-2 remains a human routing gate. OpenAI/Codex and Anthropic/Claude both
participated in the frozen design chain. Before review-2, operator must either:

1. explicitly enable an eligible independent decision reviewer such as the
   registry's future Gemini candidate; or
2. use a permitted strong-reviewer disclosure override with truthful prior
   involvement and required runner-level eligibility/unavailability evidence.

No current reviewer is prefilled as `none`.

## Test Strategy

### Unit Tests

- authorization schema and semantic cross-field checks;
- transition matrix and mode history;
- call/wall-clock/rework accounting;
- provider normalization and review-unit eligibility;
- final JSON block parser;
- path allowlist/traversal checks;
- patch byte equality and fingerprint compatibility;
- receipt/escalation artifact validation.

### Integration Tests In Temporary Git Repositories

- default-off manual status remains accepted;
- valid auto authorization reaches runner preflight;
- dirty/wrong/shared worktree fails before adapter invocation;
- fake adapter implementation → blocking → cross-check → two-commit seal;
- bind mismatch fails closed;
- Grok fake ACCEPT reaches completed_review_1;
- invalid JSON retries exactly once then routes correctly;
- blocking fix plus review REWORK consumes aggregate auto budget;
- serial unit completeness and integration-unit detection;
- parallel author set rejects Kimi/GLM fallback;
- multi-domain fix writes are serialized;
- crashes at each seal/verdict boundary resume or escalate deterministically;
- verdict record does not alter reviewed fingerprint.

### Regression Tests

- current manual stages without auto fields;
- existing `dispatch-ready`, `checkpoint`, `pre-review`, `pre-accept` fixtures;
- existing provider-isolation and strong-reviewer override cases;
- exact fingerprint values before/after shared-library extraction.

### Prohibited Test Behavior

- no live model invocation;
- no network;
- no real user credentials/environment capture;
- no product fixture or product-stage mutation.

## Frozen Decision Traceability

| Frozen item | Design realization |
|---|---|
| D1 | Embedded cross-check before H_snapshot plus byte-equality bind |
| D2 | Serial task units; parallel tip unit; code-only integration-unit detection |
| D3 | Explicit `required_attempt`; unavailable/skip evidence and bind N/A |
| D4 | One rework ledger; aggregate auto code-change budget ≤2 |
| D5 | Exclusive integration worktree and evidence-backed human mode flip |
| D6 | Runner is sole automatic adapter invoker |
| D7 | Grok auto primary; unit-aware serial fallback; tip escalation |
| D8 | Default-off versioned opt-in plus later two-pilot gate |
| D9 | HIGH stage under frozen task/design/ADR and required breakdown |
| D10 | Implementers never commit or write authoritative status in auto mode |
| D11 | No review-1 ACK; authorization/review-2/merge remain human gates |
| D12 | Locked review-1/review-2/embedded cross-check vocabulary |
| P1 | Shared canonical fingerprint implementation; no new protocol |
| P2 | Mechanical runner; deterministic narrative templates |
| P3 | Final-and-only schema-valid verdict boundary |
| P4 | Auto mode and historical parallel checkpoint mode are mutually exclusive |
| P5 | Verdict-record commit after frozen snapshot |
| P6 | Path/owner routing and serialized v1 multi-owner fixes |
| P7 | One blocking retry, charged to shared ledger |
| P8 | Required per-stage call and wall-clock authorization budgets |
| P9 | No automatic GPT/Claude invocation |
| P10 | Harness-only file boundary and product-path negative check |
| P11 | Pilot readiness only; no default flip in this stage |
| P12 | Required `80-escalation-*` evidence contract |
| P13 | Untrusted-artifact and secret-safe receipt boundary |

## Raw Artifact Requirements For Review

- `00-intake.md` and both intake reviews
- frozen `40-operator-decision-table.md`
- `00-task.md`
- `10-design.md`
- `11-adr.md`
- `12-development-breakdown.md`
- exact committed diff/fingerprint
- implementation/fix reports and runner test output
- relevant Harness source files
- review-unit, receipt, verdict, and escalation fixtures

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Runner becomes over-privileged | deterministic allowlists, authorization, registry refs, receipts, tests |
| Second fingerprint protocol appears | byte patch compare only; no hash/status field |
| Status self-reference/circular commit | H_snapshot then status-only H_bind |
| Grok output is unstable | raw capture, strict final schema-valid JSON, bounded retry |
| Cross-pool fallback self-reviews tip | full review-unit author set; tip escalation |
| Test retry silently exceeds ledger | one shared counter and validator invariant |
| Two fixers race in one worktree | v1 serial multi-owner fix writes |
| Auto failure silently becomes human dispatch | awaiting-human state + evidence + explicit resume |
| Prompt injection changes control flow | immutable prompts; model artifacts treated as data |
| Manual mode regresses | absent-field compatibility and regression fixtures |
| Bootstrap stage self-hosts unreviewed code | auto mode explicitly disabled for this stage |

本地北京时间: 2026-07-11 11:54:00 CST
下一步模型: Claude Fable 5（development breakdown author）
下一步任务: 按本设计冻结 owner split、allowed/forbidden files、task dependencies、exact tests 与 review focus；不得开始实现。
