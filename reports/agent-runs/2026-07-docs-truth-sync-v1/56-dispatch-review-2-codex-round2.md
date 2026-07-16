# Dispatch Packet — review-2 round 2（final gate）（executor: human operator → Codex）

**仅在 round-2 review-1 (Kimi) ACCEPT 后执行。** fix 改动了指纹，你 round-1 的 REWORK
针对旧范围；本轮在**修复后**范围终审你自己提的 F1/F2/F3 是否已解决。用 `codex exec`
（read-only）；输出落到 `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`
（覆盖 round-1，round-1 已归档于 `status.review_rounds[0]`）。

`codex exec "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/56-dispatch-review-2-codex-round2.md)"`

---

## PROMPT BODY

你是 review-2 最终门（round 2，read-only）。stage `2026-07-docs-truth-sync-v1`：你在
round-1 判 REWORK（F1/F2/F3），claude_glm 已修复。现在在修复后范围终审。以 PRD/schema/
server/前端为最高权威，独立复验；不得改文件。

### 受审范围（新）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..a77a18aa069ecc236c8448b8bdced40ea53bdeb1`
- diff_fingerprint（bookkeeper pre-review 已 PASS；verdict 中原样回填）：
  `a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9`

### 必须确认你的 F1/F2/F3 是否已解决
- **F1** funding-history：empty=纯投影、不证明上游成功；披露 funding-history.schema.json:34
  deferred。对照 `backend/services/snapshot_service.py:259-315`、
  `backend/tests/test_funding_history_endpoint.py`。
- **F2** symbol-snapshot ok/partial/timeout 是否覆盖代码实际（premium/history/borrow →
  partial；deadline/worker_not_running/assemble_failed → timeout）；warnings 承载原因；
  披露 symbol-snapshot.schema.json:39 deferred。对照 `snapshot_service.py:1420-1437,1527,
  347-359`、`test_symbol_snapshot_endpoint.py`。
- **F3** bookticker `status.json`/`70-handoff.md`/`20-implementation.md` 未来/待办措辞
  已历史化，且 SHA/指纹/Session ID/verdict/授权事实零改动。

### 其余
确认无新引入的过度承诺/回归；文件边界 0 越界（Forbidden 集同 round-1）；范围收敛正确
（STAGE_INDEX/ROADMAP/manifest 延后 Stage B、harness-design/AGENTS 延后 Harness 轨）。

### 必读
`40-fix-report.md`、`50-review-2.md`（你 round-1 原文）、`30-review-1.md`（round-2 Kimi
ACCEPT）、`60-test-output.txt`、实际 diff、真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`final_reviewer`，
`reviewer_prior_involvement`=`direction_synthesis`，`diff_fingerprint` 用上面新值，
`verdict`∈{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`stage_accepted_waiting_user`；
REWORK 给 `fix_start_prompt`。统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
