# ADR — Human Dispatch, Single Committed Review, Split Verdict Evidence

## Context

The previous stage demonstrated that mandatory model-side embedded dispatch,
duplicate cross-review, advisory output paths, and Markdown-plus-JSON output are
not reliable together.

## Decision

1. Human operator is the only external model-dispatch actor.
2. Default parallel delivery performs one cross-provider Review-1 after task
   commits; embedded review is opt-in.
3. Review stdout and strict verdict JSON are separate artifacts produced by a
   deterministic capture-only helper.
4. New behavior is versioned and does not reinterpret historical stages.

## Alternatives Rejected

- Keep embedded + formal review mandatory: preserves duplicated cost and the
  disputed model-side launch path.
- Treat embedded PASS as formal Review-1: review target is uncommitted and has
  no committed fingerprint.
- Let reviewers write files directly: read-only reviewers and remote terminals
  cannot guarantee workspace writes.
- Silently strip fences/newlines in place: destroys raw evidence provenance.
- Restore a fully autonomous review pipeline: broader than the six failures and
  contrary to the human-dispatch gate.

## Tradeoffs

- One fewer default review round reduces early feedback, but the retained round
  reviews immutable committed bytes.
- Two evidence files per review add small storage overhead but make raw/canonical
  provenance explicit.
- Protocol versioning adds validator branches but avoids breaking history.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/11-adr.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: user-selected independent plan reviewer
下一步任务: 判断 ADR 是否完整解决六项故障且没有削弱门禁
