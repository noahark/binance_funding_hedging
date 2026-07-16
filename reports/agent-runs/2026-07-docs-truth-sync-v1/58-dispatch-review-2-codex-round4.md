# Dispatch Packet — review-2 round 4（final gate，user-authorized）（executor → Codex）

用户授权的最后一轮：F7 已由 claude_glm 修复，**用户豁免 round-4 review-1(Kimi)**，直接
Codex 终审。`codex exec`（read-only）；输出落到 `50-review-2.md`（覆盖，round 1/2/3 存于
51-/52- 及 review_rounds）。前置：status=review_2、工作树干净（bookkeeper 已提交）。

`codex exec "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/58-dispatch-review-2-codex-round4.md)"`

---

## PROMPT BODY

你是 review-2 最终门（round 4，read-only）。stage `2026-07-docs-truth-sync-v1`：你在
round-3 判 REWORK（F7 P1 + F8 P2）。用户授权了超 rework 上限的一次限定 fix，claude_glm
已修 F7，bookkeeper 已修 F8。现在终审修复后范围。以 PRD/schema/server/前端为最高权威，
独立复验；不得改文件。

### 受审范围（新）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..a4322847d831105d587a36f6f5d305586d10c264`
- diff_fingerprint（bookkeeper pre-review 已 PASS；verdict 中原样回填）：
  `a4322847d831105d587a36f6f5d305586d10c264:06ea8e1a2bf7e8ffdb4c9bb7df626e6d91b5d0cca7712f824b07874726a15604`

### 必须确认 F7/F8 是否已解决
- **F7** `docs/api/public-market-contract.md` symbol-snapshot：`published_version` 现是否
  定义为投影所用内部 `PublishedState` 修订号；是否明说 full snapshot v1 wire payload
  **无该字段**、无客户端可验证的跨请求同版本保证；是否保留 row 来自同一内部
  PublishedState.snapshot 的事实；drift 注记是否把 `symbol-snapshot.schema.json:5` 的
  same-version prose 列入 deferred。对照 `backend/services/snapshot_service.py:237-257`、
  `backend/app/server.py:58-88`、`schemas/api/public-market/snapshot.schema.json`
  （无 published_version）、`backend/tests/test_symbol_snapshot_endpoint.py:178-189`。
- **F8**（bookkeeper-owned）已处理：`60-test-output.txt` 有 c72987d..a77a18a 未限定
  exit-2 / 限定四文件 clean / 127a600..568fd41 clean 的可复现记录；handoff Current State
  已同步（不再 planned/intake）；ACTIVE.json 顶层 updated_at 已同步。

### 其余（回归）
F1–F6 保持已解决；无新引入过度承诺；文件边界 0 越界（Forbidden 集同前）；范围收敛正确
（STAGE_INDEX/ROADMAP/manifest 延后 Stage B、harness-design/AGENTS 延后 Harness 轨）。

### 流程注记（不影响你判断）
本轮为用户授权的 rework 上限豁免（rework 4，超 max 3）+ 豁免 round-4 review-1；这些是
已记录的 user authorization（`status.user_authorizations[0]`），非隐藏偏离。

### 必读
`40-fix-report.md`（含 round-3/F7 段）、`50-review-2.md`（你 round-3 原文）、
`60-test-output.txt`、实际 diff、真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`final_reviewer`，
`reviewer_prior_involvement`=`direction_synthesis`，`diff_fingerprint` 用上面新值，
`verdict`∈{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`stage_accepted_waiting_user`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
