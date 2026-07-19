# Bookkeeper Reconciliation — Implementation Round 1

## Disposition

**FIX REQUIRED before the evidence commit and formal Review-1.** This is a
bookkeeper scope/contract reconciliation, not a formal code-review verdict and
does not increment `rework_count`.

The implementation is Harness-only and its focused suite reports 39/39 PASS,
but the current worktree does not yet satisfy the frozen task/amendment.

## Blocking Findings

### R1 — Protocol omission remains a live-stage bypass

- Frozen contract: `00-task.md` criterion 8 and amendment §3 require the exact
  protocol on active/new stages at dispatch-ready, pre-review, and pre-accept;
  missing must fail closed, while cold historical stages remain legacy.
- Actual: `review_artifacts.resolve_protocol({})` returns legacy and the focused
  test explicitly expects `missing protocol -> legacy`. The validator does not
  distinguish the active stage from cold history.
- Required: dispatch-ready always rejects missing protocol; pre-review and
  pre-accept reject it for the stage named by `ACTIVE.json`; cold historical
  all-stage validation retains legacy behavior. Add direct fixtures.

### R2 — Pre-review timing deadlocks Review-1 dispatch

- Frozen contract: amendment §8 requires Review-1 artifacts at pre-review only
  when status is `review_2`; status `review_1` is the preflight before the
  Review-1 model runs.
- Actual: `validate_review_artifact_protocol()` sets `require_review1` true for
  every pre-review invocation, including `status == review_1`.
- Impact: the formal Review-1 preflight requires output that cannot exist until
  after the review is dispatched.
- Required: `pre-review/review_1` validates protocol/routing but not result
  pairs; `pre-review/review_2` requires Review-1 pairs; pre-accept requires both
  Review-1 and Review-2. Add missing-pair tests for all three cases.

### R3 — Workflow nodes still prescribe legacy output and an invalid footer

- Frozen contract: protocol-v1 Review-1/2 writes raw + strict verdict pairs and
  emits exactly one JSON object without Markdown footer.
- Actual: `stage-delivery.yaml` Review-1 still writes `30-review-1.md` and
  requires `navigation_footer.position: before_final_json_object`; Review-2
  repeats the same conflict with `50-review-2.md`.
- Required: make node writes/output contract protocol-aware and use the frozen
  task/serial/Review-2 pair names. Protocol v1 footer is operator receipt/status
  metadata only; retain old behavior solely in an explicit legacy branch.

### R4 — Strict canonical verdict is calculated but deliberately not enforced

- Frozen contract: verdict is deterministic canonical JSON with no surrounding
  bytes or terminal newline.
- Actual: `load_and_parse_pair()` computes the canonical bytes, then executes
  `pass` when file bytes differ.
- Required: fail on any byte difference. Test noncanonical whitespace/key order,
  leading whitespace, and trailing whitespace/newline. Raw may contain only JSON
  grammar transport whitespace; verdict may contain none.

### R5 — Artifact path and identity checks are bypassable

- Status-selected raw/verdict paths are joined without enforcing a stage-local
  basename or the exact frozen name/retry pattern. Absolute and `..` paths can
  escape the stage evidence directory.
- Task provider isolation prefers the free-form verdict `model` string over the
  normalized status reviewer provider, so an alias such as a provider-specific
  model name can evade same-provider comparison.
- Verdict `stage_id` is not compared with `status.stage_id`.
- Required: require stage-local protocol filenames (including positive retry
  numbers), reject absolute/traversal paths, cross-check `stage_id`, require and
  use normalized status reviewer provider for isolation, and cross-check model.
  Add negative fixtures for each bypass.

### R6 — Embedded opt-in and schema fixture contracts are incomplete

- Amendment criterion 10 requires each enabled embedded round to record a
  verdict/result in addition to dispatch, patch, raw, round, and reason. Current
  validator does not require a round verdict. Require a frozen scalar result
  such as `PASS|BLOCKER` (do not mislabel it formal Review-1 or broaden the
  formal verdict schema).
- Amendment criterion 11 requires fixtures for every schema-v1 constraint.
  Current parity coverage checks only representative cases. Expand the corpus
  across all required keys, types, enums, array/item constraints, finding
  fields, line minimum/null, additional properties, and conditional fix prompt.

### R7 — Atomic no-overwrite has a race

`write_bytes_atomic()` checks existence and then uses `os.replace()`, which can
overwrite a destination created between those operations. Use an atomic
no-clobber publication primitive in the same directory and test the collision
path; preserve temp cleanup and fsync behavior.

## Scope Finding Requiring User Authorization

`scripts/validate-all-stages.py` has a necessary five-line integration change,
but it is not listed in `00-task.md#Allowed Files`. The change ensures the
aggregate validator actually calls the new protocol gate. Recommended action:
the user explicitly adds this one file to Task H1 scope; otherwise Grok must
revert it and the aggregate validation goal must be narrowed.

## User Disposition

At 2026-07-19 23:32:37 CST the user authorized a full rollback of Grok's
uncommitted Harness source changes, reassigned implementation to Fable5, and
accepted the recommended scope sequence including
`scripts/validate-all-stages.py`. The seven findings remain required negative
cases for the clean reimplementation; they are not a request to patch Grok's
discarded source.

## Process Note

The implementer edited `status.json`, `70-handoff.md`, and `ACTIVE.json`, despite
the single-writer bookkeeper rule. The changes are recoverable and have been
re-derived here; this is not code authorship, but the fix round must leave those
three files to the bookkeeper. The verified operator-supplied Grok Session ID is
`019f7ae4-25a4-7ee1-81bd-29f4b3172f1d`.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/21-bookkeeper-reconciliation.md
本地北京时间: 2026-07-19 23:32:37 CST
下一步模型: Fable5 / Anthropic
下一步任务: 以本报告作为负向用例清单，从 committed baseline 清洁重做
