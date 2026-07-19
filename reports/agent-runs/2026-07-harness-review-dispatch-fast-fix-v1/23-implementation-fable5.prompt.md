<!-- ===== DISPATCH RECEIPT =====
status: pending
target_model: claude-fable-5 / anthropic
executor: human_operator
adapter_cmd: claude --model claude-fable-5 --permission-mode acceptEdits -p "$(cat reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/23-implementation-fable5.prompt.md)"
started_at:
completed_at:
session_id:
session_id_source:
outputs: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/20-implementation-fable5.md, reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/60-test-output.txt
next_dispatch: stop for Codex bookkeeper reconciliation; do not invoke a reviewer
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY (immutable after dispatch) ===== -->

You are the clean-room implementation author for Harness Task H1. The human
operator selected Fable5 after fully rolling back a failed Grok source attempt.
Do not recover, reuse, or patch Grok's discarded source. Implement from the
current committed Harness baseline and the frozen requirements.

Read completely before editing:

1. `AGENTS.md` and the implementation/review portions of
   `workflows/templates/stage-delivery.yaml`;
2. `agents/developer-discipline.md` and
   `agents/skills/minimal-change-engineer.md`;
3. stage `00-task.md`, `05-root-cause-and-fix-plan.md`,
   `12-development-breakdown.md`, and the normative
   `13-plan-review-synthesis-and-amendment.md`;
4. `21-bookkeeper-reconciliation.md` as a mandatory negative-test checklist;
5. the existing Harness sources named in Allowed Files.

Role and hard boundaries:

- You are implementation author only. Do not invoke another model or adapter.
- Do not commit or push.
- Do not edit `status.json`, `70-handoff.md`, or
  `reports/agent-runs/ACTIVE.json`; the Codex bookkeeper is their single writer.
- Do not edit product/backend/frontend/API/sample/completed-stage files.
- `scripts/validate-all-stages.py` is explicitly authorized by the user for the
  necessary protocol integration.
- Write only the authorized Harness source/template files, focused tests, your
  `20-implementation-fable5.md`, and append fresh evidence to
  `60-test-output.txt`.

Implement the smallest coherent solution that satisfies every acceptance
criterion. In particular, prove rather than assume:

1. All external dispatch is `human_operator`; no model-side child dispatch
   survives in AGENTS, workflow, parallel-mode, adapter guidance, templates, or
   validator.
2. Embedded review is default-off and conditional; bookkeeper R4 reconciliation
   and one committed formal task Review-1 remain mandatory.
3. Protocol v1 is default-on and mandatory for active/new stages at
   dispatch-ready, pre-review, and pre-accept, while cold historical stages with
   no field remain legacy-compatible. Use explicit active-stage evidence, not a
   date heuristic.
4. Phase timing has no deadlock: `pre-review + review_1` does not require a
   result; `pre-review + review_2` requires Review-1; pre-accept requires both.
5. Raw and verdict decode to the same object. Verdict bytes must be exact
   deterministic canonical JSON with no surrounding bytes or final newline.
6. Selected paths stay inside the stage directory and match exactly the frozen
   serial/task/Review-2 name or a positive `-retry-N` variant.
7. Verdict `stage_id`, role, model, fingerprint, and provider identity are
   cross-checked against authoritative stage/task status. Provider aliases must
   not allow self-review.
8. Enabled embedded rounds require dispatch, patch, raw output, round, reason,
   and a non-formal `PASS|BLOCKER` result; do not conflate this with formal
   Review-1 verdict schema.
9. Capture helper is standard-library-only, accepts an already captured raw
   file, checks producer exit status and canonical schema-v1 semantics, never
   dispatches or mutates stage state, and publishes verdict atomically without
   a no-clobber race.
10. Workflow Review-1/2 nodes use protocol-v1 raw+verdict pairs and JSON-only
    stdout; Markdown footer behavior exists only in an explicit legacy branch.
11. The stdlib validator and optional `jsonschema` oracle have a fixture corpus
    covering every schema-v1 constraint, plus all negative cases in
    `21-bookkeeper-reconciliation.md`.
12. Harness manifest distributes every new/changed Harness helper and focused
    test needed by downstream projects.

Before reporting completion, run at minimum:

```text
python3 scripts/tests/test_review_artifacts.py
python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py scripts/validate-all-stages.py
python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1 --phase checkpoint
python3 scripts/validate-all-stages.py --repo-root .
python3 scripts/test-validate-all-stages-compare.py --help
git diff --check
```

Also run focused fixtures proving the three phase-timing cases, live-missing vs
cold-legacy protocol behavior, canonical-byte rejection, path containment/name
validation, stage/provider identity binding, conditional embedded result, and
atomic collision safety. Record exact commands/output and a requirement-to-code
mapping. If a frozen requirement is ambiguous or incompatible with the baseline,
stop with BLOCKER instead of silently weakening it.

When done, report PASS/BLOCKER and stop for the Codex bookkeeper. Do not launch
formal Review-1.
