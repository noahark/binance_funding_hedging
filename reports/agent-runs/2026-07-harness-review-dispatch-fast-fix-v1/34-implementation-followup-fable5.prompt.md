<!-- ===== DISPATCH RECEIPT =====
status: completed_with_quota_fallback
target_model: claude-fable-5 → opus4.8 / anthropic
executor: human_operator
adapter_cmd: claude --model claude-fable-5 --permission-mode acceptEdits -p "$(cat reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/34-implementation-followup-fable5.prompt.md)"
fallback_reason: claude-fable-5 quota exhausted after partial implementation; human operator continued the same bounded packet with opus4.8
fallback_adapter_cmd: unavailable (operator did not provide the exact command)
started_at: unavailable (operator did not provide exact start time)
completed_at: 2026-07-20T16:52:38+08:00
fable5_session_id: unavailable (quota-exhausted partial run; no verified provider-native ID supplied)
opus4.8_session_id: 8e7ef534-4310-4033-8bca-5f17b79ce77a
session_id_source: implementation report runtime_env plus human operator model identification
producer_exit_status: unavailable (operator reported PASS but did not provide a numeric exit status)
outputs: authorized Harness files, reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/20-implementation.md, reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/60-test-output.txt
next_dispatch: completed; returned to Codex bookkeeper reconciliation without invoking a reviewer
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY (immutable after dispatch) ===== -->

You are continuing your own Fable5 implementation of Harness Task H1 after the
user explicitly accepted five non-blocking Kimi findings into the same stage.
Implement those five items only. This is an implementation continuation, not a
formal review and not authority to merge.

Read completely before editing:

1. `AGENTS.md`, especially dispatch authority, implementer boundaries, Hard
   Gates, checkpoint requirements, and output footer;
2. the implementation/review portions of
   `workflows/templates/stage-delivery.yaml`;
3. `agents/developer-discipline.md` and
   `agents/skills/minimal-change-engineer.md`;
4. stage `00-task.md`, `13-plan-review-synthesis-and-amendment.md`,
   `20-implementation.md`, `21-bookkeeper-reconciliation.md`,
   `33-bookkeeper-current-progress.md`, and this prompt;
5. the current versions of `docs/harness-design.md`,
   `scripts/validate-stage.py`, and `scripts/tests/test_review_artifacts.py`.

Role and hard boundaries:

- You are the existing implementation author. Do not invoke another model or
  adapter. Stop and return to the Codex bookkeeper when implementation and
  self-tests finish.
- Do not commit, push, merge, or edit `status.json`, `70-handoff.md`, or
  `reports/agent-runs/ACTIVE.json`.
- Do not edit product/backend/frontend/API/sample/completed-stage files.
- The newly authorized source scope is `AGENTS.md`,
  `docs/harness-design.md`, `workflows/templates/stage-delivery.yaml`,
  `scripts/validate-stage.py`, `scripts/tests/test_review_artifacts.py`, your
  existing `20-implementation.md`, and appended test evidence in
  `60-test-output.txt`. Touch another file only if a deterministic test proves
  it is necessary, and stop with BLOCKER before broadening scope.
- Do not implement the three separately recorded residual design risks about
  provider alias coverage, cryptographic provenance, or mutable historical
  comparisons. They are not part of this bounded follow-up.

Required changes:

1. Rewrite the stale Parallel Development Mode passage in
   `docs/harness-design.md` so it cannot teach model-side dispatch. It must say
   embedded review is default-off, requires explicit stage opt-in with a
   non-empty reason, is executed only by the human operator, and never replaces
   committed formal Review-1. Remove the `executor: self` behavior and any
   instruction that an implementation terminal launches another model.
2. Audit every bare `30-review-1.md` and `50-review-2.md` reference in
   `workflows/templates/stage-delivery.yaml`. Mark bare files explicitly as
   legacy compatibility narratives/inputs, or make the reference conditional
   so protocol v1 clearly uses its `.raw-output.md` + `.verdict.json` pair.
   Preserve legacy behavior and existing validator expectations.
3. Tighten the AGENTS dispatch-ready hard gate so embedded prompt, escalation,
   and round checks are described as conditional on
   `parallel_mode.embedded_review.enabled == true`; keep R10, routing, and
   failure-path checks accurate for all parallel stages.
4. Correct your existing implementation report's self-reference from
   `20-implementation-fable5.md` to its actual canonical path
   `20-implementation.md`. Append a clearly dated follow-up section describing
   these five changes and fresh test evidence; do not erase the original
   result, authorship, or prior evidence.
5. Make `active_stage_id()` fail closed for structurally invalid but
   syntactically valid `ACTIVE.json`. A missing pointer file may still mean no
   active-stage evidence. A present pointer must have an object root and an
   `active` key whose value is either `null` or an object containing a
   non-empty string `stage_id`. Reject scalar/list roots; a missing `active`
   key; scalar/list `active`; and missing, non-string, or blank `stage_id`.
   Do not require unrelated optional metadata fields.
6. Add focused tests for every invalid shape above plus both valid forms
   (`active: null` and an object with a non-empty string `stage_id`). Verify the
   invalid shapes surface a validation error instead of silently choosing the
   legacy protocol path.

Before reporting PASS/BLOCKER, run and append exact commands and outputs to
`60-test-output.txt`:

```text
python3 scripts/tests/test_review_artifacts.py
python3 -m py_compile scripts/review_artifacts.py scripts/validate-stage.py scripts/validate-all-stages.py
python3 scripts/validate-stage.py 2026-07-harness-review-dispatch-fast-fix-v1 --phase checkpoint
python3 scripts/validate-all-stages.py --repo-root .
python3 scripts/test-validate-all-stages-compare.py --repo-root .
git diff --check
```

Also run focused text/YAML checks proving the stale self-dispatch language is
gone, all bare review filenames are visibly legacy-qualified, and the workflow
still parses. Record a concise requirement-to-code mapping and all changed
files in the appended follow-up section of `20-implementation.md`.

When done, report PASS/BLOCKER and stop for the Codex bookkeeper. Do not launch
Review-1, prepare a moving-HEAD review, or modify stage state.
