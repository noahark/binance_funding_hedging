# ADR — Harness Verdict Extraction Repair

## ADR-HVX-001 — Repair on the existing Harness reform branch

Status: accepted by user for preparation.

Use `harness/dispatch-review-reform-v1`, whose head already contains the v0.5
validator. Do not mix the implementation into Boundary C. After independent
review, the user decides whether the corrected Harness commits land on `main`.

## ADR-HVX-002 — Extract by JSON nesting, not verdict-schema matching

Status: accepted.

The extractor selects the final non-nested decoded dictionary. It does not
search backwards for the first object that happens to satisfy the verdict
schema, because that could hide a final malformed or schema-invalid verdict by
falling back to stale earlier JSON.

## ADR-HVX-003 — Preserve fail-closed downstream validation

Status: accepted.

`_parse_review_artifact` remains responsible for schema validation. Receipt,
Session-ID, identity, fingerprint, and clean-worktree checks retain their
current authority and behavior.

## ADR-HVX-004 — Lightweight route, full deterministic evidence

Status: accepted.

Skip the direction panel and development breakdown. Require targeted tests,
the complete Harness suite, `py_compile`, the historical compare sentinel,
checkpoint validation, diff checking, an independent Kimi review, and explicit
user authorization before any `main` merge.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/11-adr.md
本地北京时间: 2026-07-21 14:36:22 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute the bounded implementation and return raw evidence to the bookkeeper
