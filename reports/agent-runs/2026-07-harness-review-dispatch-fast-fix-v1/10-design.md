# Stage Design

## Summary

This is a Harness-only protocol repair. The detailed design is
`05-root-cause-and-fix-plan.md`. The intended end state has one human dispatch
authority, one default committed task Review-1 round, and two mechanically
linked review artifacts: immutable raw stdout plus strict verdict JSON.

## Assumptions

- Human dispatch remains a hard gate.
- A committed-state review is more valuable than an earlier uncommitted review
  when only one cross-review round is retained.
- Historical evidence cannot be rewritten.
- A capture helper may normalize transport whitespace only in the derived
  verdict while preserving exact raw bytes.

## Tasks

1. Independent plan review, selected and executed by the user.
2. Bounded Harness implementation by a different user-selected model.
3. Codex bookkeeper validation of diff, fixtures, backward compatibility, and
   stage gates.
4. User-authorized merge and push after validation.

## Test Strategy

- Focused positive/negative capture fixtures.
- Focused validator fixtures for dispatch actor, missing output, strict JSON,
  identity, fingerprint, and legacy protocol.
- `python3 -m py_compile` for changed Python files.
- `git diff --check`.
- Validate the new stage at relevant phases.
- Run `scripts/validate-all-stages.py` comparison to catch historical breakage.

## Risks

- Overbuilding a new automatic runner: prevented by making the helper
  capture-only and human-invoked.
- Breaking completed stages: prevented by explicit protocol opt-in.
- Losing reviewer narrative: structured findings/residual risks remain in JSON;
  raw stdout is preserved.
- Accidentally weakening review: committed task Review-1 and stage Review-2
  remain mandatory.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/10-design.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: user-selected independent plan reviewer
下一步任务: 审查设计，不修改 Harness 文件
