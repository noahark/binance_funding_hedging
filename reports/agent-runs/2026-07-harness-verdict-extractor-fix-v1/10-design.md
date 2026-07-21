# Design — Span-Aware Top-Level Verdict Selection

## Problem

The current extractor starts at the last `{` and returns the first suffix that
`json.JSONDecoder.raw_decode()` accepts as a dictionary. Because `raw_decode`
legitimately stops at the end of a nested finding object, a non-empty findings
array makes that nested object win over its enclosing verdict.

## Required semantic model

Treat each successfully decoded dictionary candidate as a source span
`[start, end)`. A candidate is nested when its complete span is strictly
contained by another successfully decoded dictionary span. Select the final
candidate among the non-nested spans.

This semantic requirement is authoritative; the implementer may choose the
smallest equivalent algorithm. The extractor must remain independent of the
review-verdict schema. Schema validation continues in `_parse_review_artifact`
after extraction, so a final schema-invalid object fails closed instead of
causing fallback to an earlier object.

## Compatibility boundaries

- Keep the public helper name and return type.
- Keep prose and Markdown-fence tolerance.
- Ignore braces inside JSON strings according to JSON decoder behavior.
- Preserve a final unparseable brace after a valid object.
- Do not accept arrays or scalars as verdict objects.
- Do not weaken dispatch receipt, Session-ID, reviewer identity, or fingerprint
  checks.
- Do not add dependencies.

## Test strategy

- Unit tests: zero/one/multiple findings and nested finding metadata.
- Lexical tests: literal braces, escaped quotes, Unicode, fences, footer text,
  whitespace, and malformed trailing brace.
- Ordering tests: earlier valid object followed by final valid object; earlier
  valid verdict followed by final schema-invalid object.
- Integration test: `_parse_review_artifact` accepts a schema-valid REWORK with
  findings and rejects a schema-invalid final top-level object.
- Footer tests: unavailable Session-ID explanation after ASCII space and after
  full-width punctuation.
- Full Harness suite and historical compare sentinel.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/10-design.md
本地北京时间: 2026-07-21 14:36:22 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: implement the smallest span-aware extractor and regression matrix without schema-coupled fallback
