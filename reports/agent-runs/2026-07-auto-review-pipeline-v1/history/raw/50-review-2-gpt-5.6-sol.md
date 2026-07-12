# Stage Review-2（final_reviewer / parallel operator panel）— GPT-5.6 Sol

| Field | Value |
| --- | --- |
| Reviewer model | `gpt-5.6-sol` |
| Provider | OpenAI |
| Reasoning effort | `xhigh` |
| Role | `final_reviewer`（stage-level final gate；operator-invited parallel panel member） |
| Stage | `2026-07-auto-review-pipeline-v1` |
| Range | `a385c7ad77da1611c6e952b2219aee56b49f442f..4c668bb8748c09e7014eac2fbb7a34d3a7c247d5` |
| Stage fingerprint | `4c668bb8748c09e7014eac2fbb7a34d3a7c247d5:54186cecdb387a52a5d200acf3aa7fb1730f98256a3a53c040bd7bb01993f9e5` |
| Verdict | **BLOCKED** |
| Verdict JSON | `review-2-gpt-5.6-sol.verdict.json` |
| Prior involvement | `design` |

This is GPT-5.6 Sol's independent landing for the operator's parallel Review-2
panel. It does not advance `status.json`, accept the stage, or authorize merge.

## Disclosure

OpenAI previously authored the intake and stage-design artifacts and acted as
the earlier bookkeeper. `reviewer_prior_involvement` is therefore `design`.
The frozen operator decision table remains the requirements authority; the
OpenAI-authored design and breakdown artifacts were treated as reviewed
evidence rather than assumptions.

## Mechanical verification

- Stage fingerprint independently recomputed and matched the packet/status.
- T1, T2, and T3 fingerprints independently recomputed and matched.
- `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`: 110 tests OK.
- `python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py`: passed.
- `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase pre-review`: passed before the other parallel-review outputs appeared in the shared worktree.
- `git diff --check a385c7ad77da1611c6e952b2219aee56b49f442f..4c668bb8748c09e7014eac2fbb7a34d3a7c247d5`: passed.
- All four Review-1 verdict JSON artifacts validate against the frozen Draft
  2020-12 verdict schema.
- Delivery commits stayed inside the T1/T2/T3 file boundaries and introduced no
  product/runtime paths.
- T3's Review-1 REWORK → fix → reseal → round-2 ACCEPT chain and final stage
  `rework_count=1/3` are evidenced.

## Findings

### P1 — Strong-reviewer override evidence is not a runner-level failure record

`AGENTS.md:223-229` requires a failed runner-level availability check and its
evidence before a design-conflicted provider uses the override. The supplied
`review-2-unrelated-reviewer-unavailable-evidence.md:32-44` records an operator
statement that Gemini is frequently unreachable, but no concrete invocation,
timestamped exit status, raw output, or runner receipt. Under the packet's Stop
Conditions, this OpenAI review cannot issue an accepting gate.

### P1 — Authorization does not bind actual execution scope or budgets

`scripts/auto-review-runner.py:803-861` checks that scope and budget keys exist,
but does not require the authorization artifact or approval receipt to be
committed and does not compare authorized `task_ids`, topology, allowed and
forbidden pathspecs, or budgets with the live status/review units. Runtime call
limits come from mutable status fields.

A temporary-repository counterexample passed preflight with a human
authorization limited to T1 and one model call while status contained an extra
T2 and 99 calls; an uncommitted authorization modification and a dirty forbidden
path were also accepted. This violates
`workflows/templates/stage-delivery.yaml:113-115,175-180` and acceptance
criteria 3, 17, 19, and 28.

### P1 — Production registry commands are incompatible with runner substitution

`scripts/auto-review-runner.py:762-768` substitutes only `@PROMPT@` and
`@REPO@`, while `agents/registry.yaml:54,117-118,142-144` uses
`<prompt-file>` and `<repo>`. The restricted loader at
`scripts/auto-review-runner.py:374-410` also does not correctly unescape the
quoted YAML command strings. Tests replace the real registry with synthetic
`@PROMPT@` templates (`scripts/tests/test_auto_review_runner.py:265-274`), so
the production path is untested and the real adapters receive malformed or
literal placeholder arguments.

### P1 — Verdict validation is weaker than the frozen schema and rewrites bytes

The hand validator at `scripts/auto-review-runner.py:125-178` accepts unknown
top-level fields and invalid `required_fixes` item types rejected by
`schemas/review-verdict.schema.json:7,85-89,121-150`. The writer at
`scripts/auto-review-runner.py:1388-1395` reserializes the parsed object instead
of saving the accepted source span. This violates P3 and acceptance criterion
13's requirement to accept a schema-valid verdict and store it unaltered.

### P1 — Automatic repairs do not charge the authoritative stage ledger

`scripts/auto-review-runner.py:617-620` increments only nested
`auto_code_changes_used`; it never increments top-level `rework_count`, although
`docs/auto-review-pipeline.md:186-196` defines the latter as authoritative and
shared with Review-2 repair. The runner also checks `expires_at` only during
initial preflight (`auto-review-runner.py:821-828`) rather than before every
model call and commit as acceptance criterion 28 requires.

### P1 — Exclusive runner locking and the real H_snapshot crash window are open

`docs/auto-review-pipeline.md:215-228` requires a registered exclusive worktree
and an active-runner lock. Runner preflight implements only branch and dirty-path
checks. In the seal, H_snapshot is committed at `scripts/stage-seal.py:328-334`
before `snapshot_commit` is written to status at lines 341-387. A crash in that
window leaves no marker for the recovery path at lines 445-478. The existing
test manually adds the marker and therefore does not cover the actual crash
point.

### P1 — Restart and adapter-error paths can repeat or advance invalid work

`scripts/auto-review-runner.py:876-919` treats every state other than
`awaiting_human` as a new authorization and then runs implementation for every
unit (`998-1019`). A restart from `running` or `completed_review_1` can therefore
redispatch accepted work. Nonzero or timed-out implementation results are
recorded but do not stop the pipeline before blocking and seal
(`1032-1060`).

### P2 — Authoritative status retains obsolete blockers and routing

`status.json:56-73` still says T1 correction is ready and Review-1 is blocked;
`status.json:732-735` still lists closed T1-R2 blockers. These fields contradict
top-level `review_2` and all three task ACCEPT records. The validator does not
currently detect this inconsistency.

## Required disposition

1. Supply valid runner-level unrelated-reviewer failure evidence or bind the
   final gate to a genuinely unrelated eligible reviewer.
2. Repair authorization commit/exact-match enforcement, production adapter
   construction, verdict schema/byte preservation, the shared rework ledger,
   per-call/per-commit expiry, exclusive locking, crash recovery, restart
   idempotency, adapter-error routing, and status reconciliation.
3. Add deterministic negative tests for each reproduced counterexample.
4. Re-run the full suite, reseal affected units, recompute fingerprints, and
   re-enter Review-1 and Review-2 as required by the changed diff.

The recorded A1 Authority Order deferral, fail-closed approximate pathspec
matching, and stale registry model metadata may remain P3 follow-ups only after
the required fixes above are closed.

本地北京时间: 2026-07-11 21:20:04 CST
下一步模型: human → Claude-GLM
下一步任务: 先解决 Review-2 override 资格证据，再派发有边界的控制面修复并重走测试、seal 与 review gates
