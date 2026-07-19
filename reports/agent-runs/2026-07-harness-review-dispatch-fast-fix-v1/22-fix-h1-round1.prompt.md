<!-- ===== DISPATCH RECEIPT =====
status: superseded_not_executed
target_model: grok-4.5 / xai_grok
executor: human_operator
adapter_cmd: operator resumes Session ID 019f7ae4-25a4-7ee1-81bd-29f4b3172f1d
started_at:
completed_at:
session_id: 019f7ae4-25a4-7ee1-81bd-29f4b3172f1d
session_id_source: operator
outputs: 20-implementation-fix-round1.md, 60-test-output.txt
next_dispatch: superseded by 23-implementation-fable5.prompt.md
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY (immutable after dispatch) ===== -->

SUPERSEDED: the user chose full source rollback and clean Fable5
reimplementation. Do not execute this packet.

Resume Task H1 as its original Grok implementer. This is a scope-contained
implementation correction before any evidence commit or formal Review-1. Do not
invoke another model, commit, or edit `status.json`, `70-handoff.md`, or
`reports/agent-runs/ACTIVE.json`.

Read and implement every finding in:

- `reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/21-bookkeeper-reconciliation.md`
- frozen authority:
  `00-task.md` and `13-plan-review-synthesis-and-amendment.md`

Required outcomes:

1. Active/new missing protocol fails at dispatch-ready, pre-review, and
   pre-accept; cold historical stages without the field remain legacy.
2. `pre-review` with `status=review_1` does not require Review-1 output;
   `status=review_2` requires Review-1; pre-accept requires both review levels.
3. Workflow Review-1/2 nodes use raw+strict-verdict artifacts and JSON-only
   protocol-v1 output, with an explicit legacy branch only.
4. Validator rejects noncanonical verdict bytes, stage-external or invalidly
   named artifact paths, wrong stage ID, model/status mismatch, and
   same-provider aliases.
5. Enabled embedded rounds require a non-formal `PASS|BLOCKER` result field.
6. Schema fixture/parity corpus covers every schema-v1 constraint.
7. Atomic verdict publication is both no-clobber and crash-safe.
8. If and only if the user explicitly approves the scope amendment,
   `scripts/validate-all-stages.py` may retain its five-line protocol integration;
   otherwise restore that file to the stage baseline.

Allowed source paths remain those in `00-task.md`, subject only to the operator's
explicit decision on `scripts/validate-all-stages.py`. Update
`20-implementation-fix-round1.md` and append fresh command output to
`60-test-output.txt`. Do not modify product code or completed stage evidence.

Run at minimum:

```text
python3 scripts/tests/test_review_artifacts.py
python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py scripts/validate-all-stages.py
python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1 --phase checkpoint
python3 scripts/validate-all-stages.py --repo-root .
git diff --check
```

Report the exact test count, historical comparison result, changed files, and a
finding-to-fix mapping. Then stop for the Codex bookkeeper. Do not launch formal
Review-1 yourself.
