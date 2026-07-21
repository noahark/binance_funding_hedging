# Harness Follow-Up — Findings-Bearing Verdict Extraction

Status: `OPEN_MAIN_ONLY`

The v0.5 `extract_last_json_object` implementation in
`scripts/validate-stage.py` returns the last nested object when a final verdict
contains non-empty `findings`. The Boundary C Kimi artifact is schema-valid
when the top-level object ending at EOF is selected, but the validator selects
the final finding and rejects it.

Required dedicated Harness change:

1. Select the final top-level JSON object, not a nested object. Preserve support
   for prose, Markdown fences and the navigation footer before the verdict.
2. Add regression tests for zero, one and multiple findings; nested objects;
   braces/escaped quotes inside strings; trailing whitespace/fence handling;
   and schema-invalid final objects.
3. Add a session-footer token test covering explanatory text introduced by an
   ASCII space and by full-width punctuation, or freeze a stricter footer
   grammar that the prompt/receipt templates enforce.
4. Ensure review dispatch templates contain the machine-readable
   `DISPATCH RECEIPT` block before human execution.
5. Run `python3 -m pytest scripts/tests -q`, the historical validator compare
   sentinel, and `git diff --check`.

This repair must land through the dedicated Harness path on `main`. It is
forbidden from the Boundary C product correction packet. If Boundary C needs
the repaired behavior before its next review gate, any main-to-stage sync must
record the exception, rerun tests/validator, recompute the product fingerprint
and re-enter review as required by AGENTS.md.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/harness-review-verdict-extractor.follow-up.md
本地北京时间: 2026-07-21 12:02:59 CST
下一步模型: human operator / dedicated Harness implementer
下一步任务: schedule a main-only Harness fix for findings-bearing verdict extraction; do not mix it into the Boundary C product correction
