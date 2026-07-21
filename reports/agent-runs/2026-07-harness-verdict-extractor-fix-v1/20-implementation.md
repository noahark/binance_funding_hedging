# Implementation — Pending Human-Executed Claude-GLM Dispatch

Status: `pending`.

The bookkeeper prepared the immutable implementation prompt and dispatch
receipt. No implementation claim exists yet. The target runtime must append
its real changed-file list, requirement-to-test mapping, raw command results,
residual risks, and its own verified six-line footer, then stop for bookkeeper.

---

## Task H implementation evidence (appended by Claude-GLM / glm-5.2[1m])

Status: `done` (self-tests green; stopped for bookkeeper intake; no review or
acceptance claimed).

### Root cause

`extract_last_json_object` scanned `{` candidates from the END of the text
backwards and returned the first suffix that `json.JSONDecoder.raw_decode()`
accepted as a `dict`. When a verdict carried a non-empty `findings` array, the
last `{` in the file was the opening brace of the final finding object, and
that finding is itself a perfectly parseable `dict`. The reverse scan therefore
returned the nested finding and discarded the enclosing verdict. The Boundary C
Kimi review-1 artifact (schema-valid at the true top level) was rejected
because the validator schema-checked the finding instead.

### Algorithm and tradeoffs

Span-aware top-level selection (matches the authoritative semantic in
`10-design.md` §"Required semantic model"):

1. Scan every `{` left to right. At each position attempt
   `decoder.raw_decode(text[brace:])`. Record each candidate that decodes to a
   `dict` together with its decoded source span `[start, end)` (start = the
   `{` offset; end = `brace + consumed`). `raw_decode` is string-aware, so
   braces and escaped quotes inside JSON strings do not start candidates, and
   arrays / scalars are never candidates. A final unparseable trailing brace
   yields no candidate.
2. A candidate is *nested* when another decoded dict's span strictly contains
   its whole span (`s2 <= start and end <= e2` for a distinct candidate).
   Because `raw_decode` is deterministic and each `{` is scanned once, distinct
   candidates never share a span, so the non-strict `<=`/`<=` test against a
   different candidate is strict containment.
3. Keep the non-nested candidates and return the last one in document order.

Tradeoffs:

- Chosen the explicit span-collection + containment filter rather than a
  forward "skip-past-consumed-object" scan. Both yield the same final winner,
  but the explicit form maps 1:1 to the design's containment semantic, which is
  easier for an independent reviewer (Kimi review-1) to verify against the
  spec. The cost is O(C²) over the candidate set C; for review artifacts C is
  tiny (verdict + each finding), so this is negligible and no premature
  optimization was added.
- The extractor stays schema-independent (it never references
  `review-verdict.schema.json`). Schema validation remains solely in
  `_parse_review_artifact`, so a final schema-invalid top-level object still
  fails closed instead of falling back to an earlier object — verified by
  `test_final_schema_invalid_does_not_fall_back_to_earlier_valid`.
- Public name and return type unchanged; zero third-party dependencies; only
  `json` (already imported) is used.

### Requirement → test mapping

Task prompt "测试必须包含" 1–8 ↔ `scripts/tests/test_validate_stage_dispatch_protocol.py`:

| # | Requirement | Test |
|---|---|---|
| 1 | zero / one / multiple findings | `test_zero_findings`, `test_one_finding_returns_verdict`, `test_multiple_findings_return_verdict_not_last_finding` |
| 2 | finding 内嵌 metadata object | `test_nested_metadata_object_in_finding` (uses a non-schema `metadata` key to also prove extractor schema-independence) |
| 3 | braces 与 escaped quotes 位于字符串中 | `test_braces_and_escaped_quotes_inside_strings` |
| 4 | prose + fence + footer + trailing whitespace / malformed brace | `test_prose_fence_footer_trailing_whitespace_and_malformed_brace` |
| 5 | 较早独立 JSON object + final verdict | `test_earlier_standalone_object_then_final_verdict` |
| 6 | 较早 schema-valid verdict + final schema-invalid top-level object, 证明不 fallback | `test_final_schema_invalid_does_not_fall_back_to_earlier_valid` |
| 7 | `_parse_review_artifact` 对 findings-bearing REWORK 的集成通过 | `test_parse_review_artifact_accepts_findings_bearing_rework` |
| 8 | Session ID unavailable 由 ASCII 空格与全角标点引入的一致性回归 | `TestSessionFooterUnavailableConsistency.test_unavailable_reason_after_ascii_space_is_consistent`, `..._full_width_punctuation_is_consistent` |

The pre-existing `TestTolerantExtraction` regression (footer braces, prose-only,
REWORK `fix_start_prompt`) continues to pass unchanged.

### Changed files

```text
scripts/validate-stage.py                                          (extract_last_json_object rewritten)
scripts/tests/test_validate_stage_dispatch_protocol.py             (+2 test classes, 11 tests)
docs/parallel-development-mode.md                                  (R12 semantic note, 1 spot)
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt  (appended only)
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md (this append)
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-claude-glm.dispatch.md (receipt + footer)
```

All within the Task H file boundary. No `backend/**`, `frontend/**`, schemas,
`AGENTS.md`, `registry.yaml`, workflow YAML, `ACTIVE.json`, sibling stage
files, Boundary C files, or credentials touched.

### Real command results

Captured verbatim and appended to `60-test-output.txt` (run at
2026-07-21 15:43:14 CST on `harness/dispatch-review-reform-v1`):

```text
$ python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
49 passed in 0.75s                                              exit=0

$ python3 -m pytest scripts/tests -q
125 passed in 1.91s                                             exit=0

$ python3 -m py_compile scripts/validate-stage.py               exit=0

$ python3 scripts/test-validate-all-stages-compare.py --repo-root .
SENTINEL SUMMARY: 11/11 passed — compare gate catches all three drift categories   exit=0

$ python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase checkpoint
STAGE VALIDATION PASSED
stage=reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1
phase=checkpoint
status=implementing                                             exit=0

$ git diff --check                                              exit=0
$ git status --short                                            exit=0
```

### Residual risk

- The containment model assumes well-formed JSON object balancing for the
  winning candidate. A deliberately malformed artifact where the outer `{`
  fails to decode but an inner `{` decodes to a dict will return that inner
  dict; this matches the design's "final non-nested decoded dict" semantic and
  still fails closed downstream when the returned object is schema-invalid. No
  change to fail-closed behavior.
- The Session-ID footer regex (`当前 Session ID[:：]\s*(\S+)`) still captures
  only the first whitespace-delimited token; an unavailable reason that begins
  with non-`unavailable`/`n/a` text would not be classed unavailable. This is
  pre-existing behavior; the new tests pin the two documented introduction
  styles (ASCII space, full-width punctuation) as the supported regression
  surface rather than widening the grammar.
- No production, schema, identity, fingerprint, receipt, or clean-worktree gate
  was weakened. Historical-stage behavior is preserved (verified by the
  11/11 compare sentinel and the full 125-test suite).

### git status --short

```text
 M docs/parallel-development-mode.md
 M scripts/tests/test_validate_stage_dispatch_protocol.py
 M scripts/validate-stage.py
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-claude-glm.dispatch.md
```

当前 Session ID: 37d9d7c4-c33f-4012-bcbf-16e6e6d3b461 (Claude Code runtime session id; Zhipu/GLM provider-native id not exposed by this runtime)
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
本地北京时间: 2026-07-21 15:47:23 CST
下一步模型: bookkeeper
下一步任务: independently audit Task H, rerun Harness tests, create committed evidence and prepare fresh Kimi review-1 only if all gates close

---

## BK-H-001 micro-fix evidence (appended by Claude-GLM / glm-5.2[1m])

Same author, pre-review bookkeeper-intake fix. Formal `rework_count` stays `0`
(formal review-1 has not started). No review or acceptance claimed.

### Finding BK-H-001

Bookkeeper intake (`20-implementation.bookkeeper-audit.md`) found a fail-open
boundary: when the final JSON value is a top-level array wrapping a valid
verdict (`[valid_verdict]` or `[[valid_verdict]]`), the extractor promoted the
inner verdict dict, and `_parse_review_artifact` returned `ACCEPT` with zero
errors — a gate-critical false acceptance.

### Root cause

Containment compared each dict candidate's span only against other decoded
**dict** spans. The outer decoded array was never recorded, so the inner
verdict dict had no containing span and looked non-nested. `10-design.md`
already states arrays are not verdict objects, so this was an extractor gap,
not a contract change.

### Fix

`scripts/validate-stage.py` `extract_last_json_object` now scans both `{` and
`[`. Each successfully decoded value is recorded:

- a decoded **dict** is a verdict candidate *and* a container span;
- a decoded **list** is a container span only (never returned).

A dict candidate is nested when any *other* decoded dict-or-list container
span strictly contains its whole span. A candidate's own span is the only equal
span (raw_decode is deterministic, each structural char scanned once), so
equality identifies self and is excluded. For `[verdict]` / `[[verdict]]` the
verdict is strictly inside the array span(s), so nothing is non-nested, the
extractor returns `None`, and `_parse_review_artifact` fails closed with "no
parseable JSON verdict object". Lists are never returned; no schema matching
or fallback was added.

Docstring and inline comment updated to say "decoded dict or list container
span". The extractor remains schema-independent and dependency-free; the public
name and return type are unchanged.

### Requirement → test mapping

`scripts/tests/test_validate_stage_dispatch_protocol.py`
(`TestFinalTopLevelVerdictExtraction`), prompt "新增至少以下 regression":

| # | Requirement | Test |
|---|---|---|
| 1 | `[valid_verdict]` → extractor returns None, parse gate fail closed | `test_top_level_array_wrapping_verdict_fails_closed` |
| 2 | `[[valid_verdict]]` → fail closed | `test_nested_top_level_arrays_wrapping_verdict_fails_closed` |
| 3 | normal top-level verdict + non-empty findings still returns full verdict | `test_multiple_findings_return_verdict_not_last_finding` (existing, still green) |
| 4 | footer harmless bracket text keeps the prior valid verdict | `test_footer_harmless_bracket_text_keeps_valid_verdict` |
| 5 | `test_final_schema_invalid_does_not_fall_back_to_earlier_valid` keeps passing | (existing, still green) |

### Changed files (this micro-fix)

```text
scripts/validate-stage.py                                          (extract_last_json_object: list containers)
scripts/tests/test_validate_stage_dispatch_protocol.py             (+3 BK-H-001 tests)
docs/parallel-development-mode.md                                  (R12: "dict or list container span")
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md  (this append)
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt    (appended only)
reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-bookkeeper-fix-1.dispatch.md (receipt + footer)
```

All within the fix-1 file boundary. No `ACTIVE.json`, task/design/ADR,
`status.json`, `70-handoff.md`, bookkeeper audit, workflow/schema/registry,
product code, Boundary C, or credentials touched.

### Real command results

Captured verbatim and appended to `60-test-output.txt` (block
"## Task H — BK-H-001 micro-fix verification", run at 2026-07-21 16:25:36 CST):

```text
$ python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
52 passed in 0.87s                                              exit=0
$ python3 -m pytest scripts/tests -q
128 passed in 1.99s                                             exit=0
$ python3 -m py_compile scripts/validate-stage.py               exit=0
$ python3 scripts/test-validate-all-stages-compare.py --repo-root .
SENTINEL SUMMARY: 11/11 passed                                  exit=0
$ python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase checkpoint
STAGE VALIDATION PASSED  status=fixing                          exit=0
$ git diff --check                                              exit=0
$ git status --short                                            exit=0
```

### Residual risk

- A top-level JSON value that is a single scalar or a malformed object still
  yields no dict candidate and fails closed, unchanged.
- Harmless bracket text in footer prose (e.g. `[note]`) does not decode as a
  list, so it cannot nest a preceding verdict; a valid array that appears in
  the footer is positioned after the verdict and cannot contain it either.
  Pinned by `test_footer_harmless_bracket_text_keeps_valid_verdict`.
- No protocol widening: lists are containers for nesting only and are never
  returned; schema/receipt/identity/fingerprint/clean-worktree gates and
  historical-stage behavior are unchanged (11/11 sentinel, 128-test suite).

### git status --short (this fix's in-boundary files)

```text
 M docs/parallel-development-mode.md
 M scripts/tests/test_validate_stage_dispatch_protocol.py
 M scripts/validate-stage.py
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/60-test-output.txt
 M reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/task-H-bookkeeper-fix-1.dispatch.md
```

当前 Session ID: 37d9d7c4-c33f-4012-bcbf-16e6e6d3b461 (Claude Code runtime session id, continued from Task H; Zhipu/GLM provider-native id not exposed by this runtime)
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/20-implementation.md
本地北京时间: 2026-07-21 16:26:55 CST
下一步模型: bookkeeper
下一步任务: independently verify BK-H-001 closure, commit evidence, and prepare fresh Kimi review-1 only if all gates close
