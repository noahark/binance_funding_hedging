# Dispatch Packet — review-2 round 3（final gate）（executor: human operator → Codex）

**仅在 round-3 review-1 (Kimi) ACCEPT 且已由 bookkeeper 提交、status=review_2、工作树
干净后执行**（round-2 时 Codex 曾正确地因前置未满足而拒跑）。`codex exec`（read-only）；
输出落到 `50-review-2.md`（覆盖，round 1/2 已归档）。

⚠️ **rework 账本 2/3**：本轮 Codex 若再 REWORK，将触发 `human_escalation_required`
（终态，交用户）。请只在真有 P0/P1 缺陷时 REWORK；P2/P3 可作为 findings 记录但不必
阻断（用你的判断）。

`codex exec "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/57-dispatch-review-2-codex-round3.md)"`

---

## PROMPT BODY

你是 review-2 最终门（round 3，read-only）。stage `2026-07-docs-truth-sync-v1`：你在
round-1 判 REWORK（F1/F2/F3，已修）、round-2 判 REWORK（F4/F5/F6，已修）。现在在修复后
范围终审。以 PRD/schema/server/前端为最高权威，独立复验；不得改文件。

### 受审范围（新）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..568fd4160b67d3b73303134d6f078a6a59bb93d9`
- diff_fingerprint（bookkeeper pre-review 已 PASS；verdict 中原样回填）：
  `568fd4160b67d3b73303134d6f078a6a59bb93d9:ec91074df380632652180548168583da1756669a9e63d0077f73041621fc1ffe`

### 必须确认你 round-2 的 F4/F5 是否已解决
- **F4** contract symbol-snapshot：区分 live-worker/no-worker/offline；投影行来自最新
  已发布状态、不必然本次请求新建 publication；warnings 限 wire-visible（cmd.error 不
  暴露、timeout 可无原因）；披露 symbol-snapshot.schema.json:5 + :39。对照
  `snapshot_service.py:331-359,373-393,1499/1516/1532/1537`、`test_symbol_snapshot_endpoint.py`。
- **F5** bookticker `70-handoff.md`：human_visual_acceptance vs user_acceptance 已分开，
  事实不变。
- **F6**（bookkeeper-owned）已处理：active status.json changed_files 含 bookticker
  status.json、ACTIVE.json phase 已更新、60-test-output 已注明 diff-check 范围。

### 其余
无新引入的过度承诺/回归；文件边界 0 越界；范围收敛正确（STAGE_INDEX/ROADMAP/manifest
延后 Stage B、harness-design/AGENTS 延后 Harness 轨）。F1/F2/F3 保持已解决。

### 必读
`40-fix-report.md`（含 round-2 段）、`50-review-2.md`（你 round-2 原文）、`30-review-1.md`
（round-3 Kimi）、`60-test-output.txt`、实际 diff、真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`final_reviewer`，
`reviewer_prior_involvement`=`direction_synthesis`，`diff_fingerprint` 用上面新值，
`verdict`∈{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`stage_accepted_waiting_user`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
