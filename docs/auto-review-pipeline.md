# Auto Review Pipeline v1

Status: **NORMATIVE CONTRACT — default-off, opt-in per stage**
Source of authority: `AGENTS.md` > `workflows/templates/stage-delivery.yaml` >
`docs/parallel-development-mode.md` > `schemas/*.schema.json` >
`agents/registry.yaml`. The frozen design baseline is
`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
and stage design `10-design.md` / `11-adr.md`.

This document is the normative human-readable contract for the
`auto_review_pipeline/v1` mode. It is additive: nothing here changes the manual
human-dispatch workflow, the committed-range `diff_fingerprint` formula,
provider/session isolation, raw-evidence discipline, or strict verdict
validation. Where this document is silent, the manual rules in `AGENTS.md` and
`stage-delivery.yaml` apply unchanged.

## Vocabulary (locked)

- `runner`: deterministic, non-LLM local orchestrator; the **only** automated
  dispatcher and mechanical writer (adapter invoke, blocking check, seal,
  evidence commit, mechanical status, fixed transition).
- `embedded cross-check`: advisory cheap-model cross-read (e.g. GLM↔Kimi).
  **Not** formal review-1. **Not** validator `--phase pre-review`.
- `review-1`: formal first gate. Under auto mode the primary is Grok
  (`grok-4.5`, plan mode).
- `review-2`: final human-started high-end gate. Unchanged by this mode.
- `seal`: clean snapshot commit of the review snapshot plus the existing
  `diff_fingerprint` fields.
- `seen-diff bind`: patch byte-equality gate (capture at cross-check, assert at
  seal). It is **not** a fingerprint and is not recorded as a hash.
- `code-scope`: diff pathspec excluding `reports/agent-runs/<stage-id>/`
  evidence paths, used for the bind check.
- `review unit`: one formal review-1 subject: a task range with an explicit
  author-provider set. v1 is serial and `task`-only; `tip`/`integration` units
  are deferred to a future version.

Use `review-1`, `review-2`, and `embedded cross-check` only. Historical
synonyms for review-1 and bare `pre-review` (for model activity) are forbidden
as contract terms.

## 1. Principles

1. **One authority per concern:** workflow files define transitions; registry
   defines adapters; runner executes deterministic transitions; models provide
   bounded implementation/review content; humans retain product and final gates.
2. **Default-off compatibility:** missing or disabled auto configuration is
   manual mode, not malformed auto mode.
3. **Committed truth:** formal review binds only committed ranges using the
   existing fingerprint.
4. **No model-driven control flow:** model content is data, never a command or
   transition source unless a schema-valid verdict maps to a fixed transition.
5. **Fail closed with evidence:** every automatic stop produces a durable
   reason, receipt references, and the next permitted human action.
6. **No silent identity broadening:** reviewer eligibility is calculated from
   every author provider in the exact review unit.

## 2. Opt-In and Authorization

Auto mode is enabled per stage only by a committed, schema-valid, human-approved
authorization artifact validated by
`schemas/auto-review-authorization.schema.json`. Normative path:

```text
reports/agent-runs/<stage-id>/auto-run-authorization-v<N>.json
```

Required authorization semantics:

- `authorized_by` must be human; `approval_evidence_path` must point to the
  committed operator approval receipt; `approval_recorded_by` must identify the
  non-implementer bookkeeper that recorded it. Model claims are invalid.
- Adapter authority is fixed by the committed workflow/registry: the auto loop
  is Grok-primary with eligible serial Kimi/GLM fallback, and high-end
  (GPT/Claude) dispatch is absent. No per-authorization `allowed_adapters`,
  `review_1_provider`, or `auto_high_end_dispatch_allowed` field is carried.
- Authorization carries two configurable caps: `max_model_calls` and
  `max_auto_code_changes` (at most 2). `max_stage_rework` (3) and
  `invalid_json_max_attempts_per_model` (2) are global workflow/runtime
  invariants, not per-authorization fields; the top-level `rework_count` ledger
  is bounded by the stage-rework invariant of 3.
- `expires_at` is required and nullable. `null` means there is no independent
  authorization-expiry timestamp — it is **not** unlimited authorization; the
  run remains bound by call-count budgets, the rework
  ledger, operator stop, and stage gates. A non-null ISO8601 value must be
  later than the current time before every model invocation and git commit. A
  missing `expires_at` field is invalid.
- Any change to scope, budgets, or expiry requires a new versioned artifact
  whose `supersedes` points to the prior one.
- The runner refuses an expired artifact or a stage/branch mismatch before any
  model invocation or commit.
- The authorization artifact is never generated or edited by an implementer.

Missing, disabled, expired, wrong-stage, wrong-branch, or incomplete
authorization fails before any model invocation or commit.

## 3. Runner Authority

The runner (`scripts/auto-review-runner.py`) is the sole automatic dispatcher
and mechanical writer. It is deterministic and non-LLM. It may invoke registry
adapters, run blocking checks, seal, update mechanical status fields, commit
evidence, and apply fixed transitions.

It must not synthesize narrative requirements, select new files, broaden paths,
select unregistered models, create shell commands from model output, invoke
high-end (GPT/Claude) models in the automatic loop, or declare final
acceptance. Model-produced commands and next-hop instructions are never
executed. Narrative handoff is generated from deterministic templates.

## 4. Status Shape and Transition Matrix

`auto_review_pipeline` is a nested status contract. It does not add top-level
Harness statuses. Shape (status records usage only; the two configurable caps
live in the authorization artifact):

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
      "model_calls_used": 0,
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

`dispatch_mode` has only two values: `human_dispatch` (default) and `auto_review`
(authorized). Lifecycle values belong only to `runner_state`.

Allowed `runner_state` values: `authorized`, `running`, `awaiting_human`,
`stopped`, `completed_review_1`. Unknown values fail closed. These are auto
substates, not top-level Harness statuses.

The transition matrix below labels the pre-authorization state `disabled`, but
`disabled` is a conceptual state only. Its machine representation is exactly
`enabled: false` + `dispatch_mode: human_dispatch` + `runner_state: null`; it is
not a sixth `runner_state` value.

### Transition matrix

| Dispatch mode | Runner state from→to | Trigger | Top-level status/effect |
|---|---|---|---|
| human_dispatch→auto_review | disabled→authorized | new human authorization | runner may start |
| auto_review | authorized→running | successful full preflight | automatic loop starts |
| auto_review | running→awaiting_human | recoverable worktree/runner/adapter fallback condition | set `mode_flip_pending=human_dispatch`, top-level `paused`, write evidence, stop |
| auto_review→human_dispatch | awaiting_human→disabled | explicit human mode-flip decision | human may use current DRAFT-2 path |
| auto_review | awaiting_human→authorized | new/superseding human authorization | clear pending flip and rerun full preflight |
| auto_review | running→stopped | operator stop | no further calls |
| auto_review | running→completed_review_1 | all required units ACCEPT | stop before review-2 |
| auto_review | running→awaiting_human | cap, timeout, budget, unroutable fix, or Grok serial-fallback exhaustion | top-level `human_escalation_required`, write `80-*.md`, stop |

No automatic transition from a failed auto path directly into model dispatch in
human mode is allowed. The runner records the pending mode flip or terminal
escalation and stops; human action is required to resume.

`mode_history` is a continuous ledger: every row's `from` state must equal the
prior row's `to` state, and the final `to` state must equal the current
`dispatch_mode`/`runner_state`. When a human supplies a superseding artifact,
the bookkeeper commits the artifact and updates `authorization_path` while
leaving `runner_state=awaiting_human`; the runner alone records
`superseding_human_authorization` and moves to `authorized`. The bookkeeper must
not pre-write that mechanical transition.

### Call accounting

- A model call is charged immediately before starting a registry adapter
  process.
- Success, timeout, provider failure, invalid JSON, and empty output all
  consume one call.
- Pure local availability probes and git/test commands do not consume
  model-call budget but do produce evidence when used for routing.
- Invalid JSON retry consumes calls but not rework.
- Per-call subprocess timeout comes from the committed registry
  (`adapters.<id>.timeout_seconds`, or a command-specific override); there is no
  total runner-session deadline.
- Resume after `awaiting_human` requires new authorization; historical usage
  remains recorded.

### Rework accounting

One top-level `rework_count` remains authoritative.

- Initial implementation does not charge rework.
- A blocking-test automatic fix charges 1.
- Each review-1 REWORK that enters code-changing fix charges 1.
- Review-2 REWORK charges 1 under the existing human path.
- Automatic charges stop at 2 even if the total stage cap 3 is not yet reached.
- Invalid JSON, provider retry without code change, and cross-check unavailability
  do not charge rework, but do charge call budget when an adapter was started.

## 5. Budgets

Each stage authorization freezes its own positive `max_model_calls` and
`max_auto_code_changes` — the only two per-authorization caps. The remaining
limits are global workflow/runtime invariants, not per-authorization fields:

```text
MAX_STAGE_REWORK = 3                         # top-level rework_count ledger, shared with review-2
max_auto_code_changes <= 2                   # per-authorization; all automatic code-changing retries combined
INVALID_JSON_MAX_ATTEMPTS = 2                # consumes calls, not rework
```

Status records usage only (`model_calls_used`, `auto_code_changes_used`); caps
are not mirrored in status.

Cap, timeout, budget exhaustion, unroutable fix, or Grok serial-fallback exhaustion route
to `human_escalation_required` plus an `80-*.md` escalation artifact.

## 6. Worktree and Task Topology

### Exclusive runner worktree

The runner owns one exclusive worktree attached to the stage branch. Auto
preflight verifies:

- exact branch match;
- the worktree is registered and not used by another active runner lock;
- no unrelated dirty/untracked path;
- every dirty path is inside the active task's authorization allowlist;
- stage status and authorization reference agree.

The lock is runtime-only under git metadata and is never committed. Auto mode
refuses a shared, wrong-branch, or dirty worktree outside the explicitly
allowed phase.

### Serial topology (v1)

v1 is serial-only. Each task runs to review-1 ACCEPT before the next task
begins. For task `T`:

1. runner freezes `T.base_sha` at current HEAD;
2. blocking checks run;
3. optional/required embedded cross-check runs;
4. the same frozen blocking command set reruns after cross-check evidence lands;
5. seal produces `T.head_sha` and fingerprint;
6. Grok reviews unit `T`;
7. verdict-record commit lands outcome;
8. REWORK loops only within `T`; ACCEPT unlocks the next task.

Automatic parallel task worktrees, parallel-tip routing, and integration review
units are deferred to a future version after real serial pilots.

## 7. Blocking Checks and Embedded Cross-Check

### Required-attempt rule

The stage design/authorization records `required_attempt` explicitly. The
runner does not infer "high contract risk" from prose.

- explicitly high-contract-risk: required attempt;
- other single-owner: optional.

An unavailable required cross-check is fail-open for review-1 but must produce
an unavailable artifact and set bind to `N/A`.

### Post-cross-check blocking rerun (frozen)

Whether the cross-check runs, skips, or records unavailability, the runner
executes the same frozen blocking command set immediately afterwards and before
seal. Blocking command input pathspecs exclude the current stage evidence
directory. Test/log output may be written there, but no blocking result may
depend on prompt, raw-output, seen-patch, receipt, or unavailable artifacts.
Cross-check prompt/raw-output/seen-patch writes therefore cannot make the
second pass semantically different from the first. A missing or failed second
pass blocks seal.

### P7: one automatic blocking-fix, then escalation

An initial blocking-test failure permits at most one automatic fix, which
charges the shared rework ledger. After that single fix the runner reruns the
identical frozen blocking command set; if it still fails, the runner writes an
escalation artifact and stops at `human_escalation_required`. A second automatic
blocking fix is not permitted. The aggregate auto-change cap
(`max_auto_code_changes <= 2`) is a combined budget shared with review-1 REWORK
fixes; it is not a license to attempt two blocking fixes. This P7 rule is the
normative counterpart of
`workflows/templates/stage-delivery.yaml:auto_review_pipeline.executable_contract.p7_one_blocking_fix_then_escalate`.

### Artifact paths

```text
embedded-cross-check-<unit>-round<N>.prompt.md
embedded-cross-check-<unit>-round<N>.seen.diff.patch
embedded-cross-check-<unit>-round<N>.raw-output.md
embedded-cross-check-<unit>-round<N>.unavailable.md        (when not run)
runner-<seq>-embedded-cross-check.receipt.json
```

### Seen-diff bind algorithm

1. Freeze `base_sha` and the exact ordered pathspec list.
2. Capture raw bytes from `git diff --binary <base_sha> -- <pathspecs>` before
   cross-check and store them as the seen patch.
3. Seal the review snapshot.
4. Regenerate raw bytes from
   `git diff --binary <base_sha>..<snapshot_head> -- <same-pathspecs>`.
5. Compare byte-for-byte.
6. Mismatch escalates; no hash/status fingerprint is written.

Evidence paths under the current stage directory are excluded from code-scope.
The pathspec list itself is recorded in status/receipt so the comparison cannot
be silently narrowed.

## 8. Seal and Commit Protocol

The fingerprint is unchanged:

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
2. Compute the fingerprint using the canonical shared function.
3. Atomically update status review-unit/base/head/fingerprint fields and write
   the seal receipt.
4. **H_bind:** commit only status, deterministic handoff fields, and the seal
   receipt. Do not change code-scope.
5. Require a clean tree and run the validator against the recorded snapshot.

The formal reviewer receives the recorded snapshot range, not moving HEAD.
H_bind is evidence after `head_sha`, which existing rules permit.

The deterministic seal receipt is written as:

```text
runner-<seq>-seal.receipt.json
```

It is deterministic seal evidence whose shape is defined by the T2 seal
contract (`scripts/stage-seal.py` and the shared Harness library). It is not a
model-adapter invocation receipt: it does not validate against
`schemas/runner-receipt.schema.json`, records no adapter id or registry command
reference, and is excluded from the P11 expected adapter-call count and the
schema-valid adapter RECEIPT denominator. No other seal receipt naming family
is defined.

Crash recovery is fail-closed:

- crash before H_snapshot: no sealed unit; rerun preflight;
- crash after H_snapshot before H_bind: the runner detects an unbound snapshot,
  writes escalation, and requires deterministic bind recovery using the exact
  commit — never a second code commit;
- crash after H_bind: validator/receipt determine whether review may begin.

## 9. Review Unit Model

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

`kind` is `task` in v1. Review-1 eligibility is evaluated
against the full `author_provider_identities` set, including every fix author
who changed the current snapshot.

Review-1 completeness predicate:

```text
all(unit.required implies
    unit.review_1.verdict == ACCEPT and
    unit.review_1.json_schema_valid == true and
    unit.review_1.diff_fingerprint == unit.diff_fingerprint)
```

Only then may the runner stop at `completed_review_1` for human review-2.

## 10. Review-1 Routing and Verdict Boundary

### Primary and fallback

- Auto primary: `grok` / `grok-4.5` plan mode, via the existing
  `adapters.grok.optional_review_command`.
- Serial fallback: an eligible Kimi/GLM cross-pool candidate is used only if its
  normalized provider identity is absent from that unit's author set.
- When no eligible serial candidate remains, Grok failure or repeated invalid
  verdict escalates via `review_1_fallback_exhausted`.
- GPT/Claude are never automatically substituted.

### Output parsing

Raw stdout is always saved first. The runner enumerates complete top-level JSON
object candidates in the output and accepts only when:

1. exactly one candidate validates against `review-verdict.schema.json`;
2. that candidate is the final non-whitespace structured block;
3. its stage id, role, and fingerprint match the active review unit;
4. no second schema-valid verdict exists in the stream.

The accepted bytes are saved unaltered as
`review-1-<unit>-round<N>.verdict.json`. Prose/footer stays only in
`review-1-<unit>-round<N>.raw-output.md`. No regex-mined or bookkeeper-rewritten
JSON may pass.

### Verdict-record commit

After validation, the runner writes status and commits: raw output, the exact
verdict JSON, the receipt, and deterministic handoff/status updates. This commit
never changes the review unit's base/head/fingerprint. A REWORK transition
increments the ledger only when code-changing fix dispatch begins.

## 11. Multi-Owner Fix Routing

The full reviewer `fix_start_prompt` is preserved for every assigned owner. A
runner-generated immutable header adds: the active unit/fingerprint; owner
provider/domain; the exact finding indexes and file paths assigned;
allowed/forbidden paths; frozen test commands; and a "fix only your assigned
findings" instruction.

Routing uses `findings[].file` plus frozen task ownership. Missing/ambiguous
paths, shared-contract changes, or cross-boundary requirements are unroutable
and escalate. The runner never guesses from natural-language title text.

In v1, owners modify the exclusive worktree serially. Each owner receives a
fresh bounded session and produces a separate fix report/receipt. Unified tests
and reseal occur only after every assigned owner finishes.

## 12. Security and Trust Boundary

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

## 13. Escalation Contract

Normative path:

```text
reports/agent-runs/<stage-id>/80-escalation-<reason>-<UTC timestamp>.md
```

Required content:

- stage/mode/runner version;
- current status and review unit;
- snapshot fingerprint when one exists;
- rework and budget usage;
- raw output/verdict/receipt/test paths;
- sanitized failure class;
- allowed next actions (`human_dispatch`, new authorization, task/design
  amendment, or terminal human escalation).

Status records `last_escalation_path` and changes the runner substate to
`awaiting_human`. Cap, timeout, budget, unroutable fix, and Grok
serial-fallback exhaustion always set top-level `human_escalation_required`.
Recoverable preflight/mode-fallback conditions use existing top-level `paused`
until the human chooses a mode.

## 14. Pilot Evaluation Contract

Each pilot stage must land:

```text
reports/agent-runs/<pilot-stage-id>/auto-review-pilot-metrics.json
```

Minimum fields:

- pilot kind (`docs_only` or `small_real`), stage id, terminal status, and
  authorization path;
- total Grok verdict attempts, schema-valid attempts, invalid attempts, and the
  computed schema-valid rate;
- the final schema-valid Grok verdict path and fingerprint;
- escalation paths, the shape-validation result for each, and whether a
  controlled escalation drill was exercised;
- expected runner calls/RECEIPTs, schema-valid RECEIPTs, missing RECEIPTs, and
  the completeness rate;
- model calls, automatic code-change charges, and the final
  stage outcome.

Pilot/default-flip rules:

1. Pilot 1 is docs-only; pilot 2 is a small real stage.
2. Both must reach `stage_accepted_waiting_user` under the accepted auto mode.
3. Both must contain at least one final schema-valid Grok verdict.
4. RECEIPT completeness must be 100% in both.
5. Every produced escalation must match the frozen `80-*.md`/status shape.
6. At least one pilot must exercise a safe controlled escalation and subsequent
   human-authorized disposition.
7. The Grok schema-valid rate includes invalid retries and is recorded exactly,
   but v1 does **not** invent a global promotion threshold; a later operator
   decision evaluates both rates before any default flip.

Missing metrics, missing raw attempt evidence, or failed shape/completeness
checks make a pilot ineligible as default-flip evidence even when its delivery
diff otherwise passes review.

## 15. Bootstrap Stage Constraint

This contract's own delivery stage (`2026-07-auto-review-pipeline-v1`) does not
self-host auto mode. It records
`auto_review_pipeline.enabled_for_this_stage=false` and runs entirely under the
current DRAFT-2 human-dispatch workflow. Default flip is a separate, later,
operator decision that requires the two pilot artifacts above.

## Frozen Decision Traceability

| Frozen item | Realization in this contract |
|---|---|
| D1 | Embedded cross-check before H_snapshot plus byte-equality bind (§7, §8) |
| D2 | Serial task-only units; tip / integration units deferred past v1 (§6, §9) |
| D3 | Explicit `required_attempt`; unavailable/skip evidence and bind N/A (§7) |
| D4 | One rework ledger; aggregate auto code-change budget ≤2 (§4, §5) |
| D5 | Exclusive runner worktree and evidence-backed human mode flip (§6, §4) |
| D6 | Runner is sole automatic adapter invoker (§3) |
| D7 | Grok auto primary; eligible serial fallback; fallback-exhaustion escalation (§10) |
| D8 | Default-off versioned opt-in plus later two-pilot gate (§2, §14) |
| D9 | HIGH stage under frozen task/design/ADR and required breakdown |
| D10 | Implementers never commit or write authoritative status in auto mode (§3) |
| D11 | No review-1 ACK; authorization/review-2/merge remain human gates (§10, §4) |
| D12 | Locked review-1/review-2/embedded cross-check vocabulary (Vocabulary) |
| P1 | Shared canonical fingerprint implementation; no new protocol (§8) |
| P2 | Mechanical runner; deterministic narrative templates (§3) |
| P3 | Final-and-only schema-valid verdict boundary (§10) |
| P4 | Auto mode and historical parallel checkpoint mode are mutually exclusive (§4) |
| P5 | Verdict-record commit after frozen snapshot (§10) |
| P6 | Path/owner routing and serialized v1 multi-owner fixes (§11) |
| P7 | One blocking retry, charged to the shared ledger (§4, §5) |
| P8 | Required per-stage call authorization budgets (§2, §5) |
| P9 | No automatic GPT/Claude invocation (§3, §10) |
| P10 | Harness-only file boundary and product-path negative check |
| P11 | Two pilot metrics artifacts: Grok validity rate, escalation shape, RECEIPT completeness (§14) |
| P12 | Required `80-escalation-*` evidence contract (§13) |
| P13 | Untrusted-artifact and secret-safe receipt boundary (§12) |

```text
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: <model-or-human>
下一步任务: <specific next task>
```

The timestamp above is a template placeholder for the normative document; stage
reports and handoffs fill it from a local `date` command.
