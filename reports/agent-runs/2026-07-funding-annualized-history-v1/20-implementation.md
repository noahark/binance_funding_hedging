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

## Task C: Selected-Symbol History Endpoint (Planned)

- Owner: Claude-GLM (`glm-5.2`, provider identity `zhipu_glm`)
- Dispatch artifact: `task-history-endpoint-claude-glm.prompt.md`
- Planned raw report: `20-implementation-backend-history-fix.md`
- Scope: same-origin public endpoint, selected-symbol cache reuse, explicit
  empty versus unavailable semantics, response schema, and backend tests.

## Task D: Drawer History And Table Refinement (Planned)

- Owner: Kimi (`kimi-code/kimi-for-coding`, provider identity `moonshot_kimi`)
- Dispatch artifact: `task-drawer-history-refinement-kimi.prompt.md`
- Planned raw report: `20-implementation-frontend-history-fix.md`
- Scope: on-demand endpoint consumption, retry/error states, removal of the
  default route-class column, and wider non-wrapping Drawer cards.

## Shared Verification

See `60-test-output.txt` for exact command evidence. The stage remains in
implementation until the bookkeeper freezes Task B, anchors the combined diff,
and satisfies the formal pre-review gate.

```text
本地北京时间: 2026-07-10 19:38:24 CST
下一步模型: bookkeeper
下一步任务: 提交 Task B，记录 combined stage fingerprint，并在工作区清理后运行 formal pre-review。
```
