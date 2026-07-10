# Stage Implementation Index

This index does not replace or summarize the raw implementer reports. Formal
reviewers must read both reports and the committed diff.

## Task A: Backend Contract And Settled History

- Owner: Claude-GLM (`glm-5.2`, provider identity `zhipu_glm`)
- Raw report:
  `20-implementation-backend.md`
- Bounded delivery commit: `2e27efc`
- Scope: Decimal annualization, bounded/cached public history retrieval,
  optional additive schema fields with current-service output guarantee, raw
  sample evidence, and backend tests.

## Task B: Frontend Table And Drawer

- Owner: Kimi (`kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`)
- Raw report:
  `20-implementation-frontend.md`
- Scope: annualized table columns, selectable rows, right-side settled-history
  drawer, fixture/self-check updates, and the DOM-order startup fix.

## Shared Verification

See `60-test-output.txt` for exact command evidence. The stage remains in
implementation until the bookkeeper freezes Task B, anchors the combined diff,
and satisfies the formal pre-review gate.

```text
本地北京时间: 2026-07-10 19:38:24 CST
下一步模型: bookkeeper
下一步任务: 提交 Task B，记录 combined stage fingerprint，并在工作区清理后运行 formal pre-review。
```
