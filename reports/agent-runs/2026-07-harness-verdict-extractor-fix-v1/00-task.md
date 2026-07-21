# Task H — Select The Final Top-Level Review Verdict Object

## Objective

Repair the gate-critical verdict extractor so a findings-bearing review
artifact yields its complete final top-level verdict object, never its last
nested finding. Preserve tolerant prose/fence/footer handling and fail-closed
schema validation.

## Required behavior

1. `extract_last_json_object(text)` returns the final top-level JSON object.
   A parseable object whose decoded span is strictly contained inside another
   decoded JSON container — dictionary or array — is nested and cannot win.
   In particular, `[valid_verdict]` must fail closed rather than promote its
   contained dictionary.
2. For a verdict with zero, one, or multiple `findings`, the complete verdict
   object is returned.
3. Prose, Markdown JSON fences, navigation footers, trailing whitespace,
   braces inside strings, escaped quotes, and an unparseable trailing brace
   remain supported.
4. If the final top-level object is schema-invalid, the validator reports that
   object's schema errors. It must not silently fall back to an earlier valid
   object.
5. A later standalone parseable top-level object remains authoritative and may
   fail schema validation. This preserves fail-closed ordering.
6. Session-ID footer consistency receives regression coverage for unavailable
   explanations introduced by an ASCII space and by full-width punctuation,
   or the implementation records and enforces a stricter compatible grammar.
7. The R12 prose is updated from “last nested parseable object wins” semantics
   to final top-level-object semantics.
8. Human-only dispatch, receipt validation, review schema, identity isolation,
   fingerprinting, clean-worktree gates, and historical-stage behavior are not
   weakened.

## Allowed files

```text
scripts/validate-stage.py
scripts/tests/test_validate_stage_dispatch_protocol.py
docs/parallel-development-mode.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-claude-glm.dispatch.md
```

## Forbidden files and actions

- All `backend/**`, `frontend/**`, schemas, product/design docs, canonical
  product docs, credentials, `.env*`, unrelated stages, and Boundary C files.
- `AGENTS.md`, `agents/registry.yaml`, workflow YAML, `ACTIVE.json`, this task,
  `10-design.md`, `11-adr.md`, `status.json`, and `70-handoff.md`.
- Commit, push, merge, rebase, checkout/switch to `main`, model dispatch,
  network calls, credential reads, or acceptance claims.

## Acceptance evidence

```text
python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
python3 -m pytest scripts/tests -q
python3 -m py_compile scripts/validate-stage.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase checkpoint
git diff --check
```

The implementation report must map each requirement to changed files and
tests, include actual command outputs, disclose any residual risk, end with the
required six-line runtime footer, and stop for bookkeeper intake.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/00-task.md
本地北京时间: 2026-07-21 15:59:10 CST
下一步模型: human operator → original Claude-GLM / glm-5.2[1m]
下一步任务: execute the bounded BK-H-001 array-container micro-fix, rerun the exact Harness checks, fill the receipt, and stop for bookkeeper
