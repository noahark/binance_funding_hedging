# Dispatch Packet — review-1 round 3（executor: human operator → Kimi）

round-2 fix（F4/F5）改动了指纹，需在**新范围**重跑 review-1。Kimi 终端执行 PROMPT
BODY；输出落到 `30-review-1.md`（覆盖，round 1/2 已归档 `status.review_rounds`）。只读。

`kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/37-dispatch-review-1-kimi-round3.md)"`

---

## PROMPT BODY

你是 review-1（round 3，`code_reviewer`，只读）。stage `2026-07-docs-truth-sync-v1`
经 review-2 round-2 REWORK（F4/F5/F6）后已修复，现在重审**修复后**范围。判据：文档
所述 == schema/代码/前端真值。不得改任何文件。

### 受审范围（新）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..568fd4160b67d3b73303134d6f078a6a59bb93d9`
- diff_fingerprint（bookkeeper pre-review 已 PASS，勿重算）：
  `568fd4160b67d3b73303134d6f078a6a59bb93d9:ec91074df380632652180548168583da1756669a9e63d0077f73041621fc1ffe`

### 本轮 fix 重点（逐条复核修得对不对）
- **F4（P1）**：`docs/api/public-market-contract.md` symbol-snapshot 章节是否已区分
  live-worker / no-worker / offline 三路径；是否说明投影行来自最新已发布状态、**不必然**
  是本次请求新建的 publication；`warnings` 是否限定为 wire-visible（内部 `cmd.error`
  不上响应、timeout 可无具体原因）；是否披露 `symbol-snapshot.schema.json` **第 5 行和
  第 39 行**两处 prose drift。对照 `backend/services/snapshot_service.py`（offline
  331-332、no-worker last-good、351-359 只序列化 cmd.warnings）、
  `backend/tests/test_symbol_snapshot_endpoint.py`。
- **F5（P2）**：bookticker `70-handoff.md` 是否分开点名 `human_visual_acceptance.status
  =accepted` 与后续 `user_acceptance.status=accepted_merged_and_pushed`（两个门不合并），
  且事实不变。

### 其余
其余交付文件在前轮已 ACCEPT，确认 fix 无回归即可；F6 是 bookkeeper 账本修正
（ACTIVE.json/active status.json/60-test-output），非 fix-author 文档，作背景确认已处理。
文件边界仍禁 Forbidden 集。

### 必读
`50-review-2.md`（Codex round-2 REWORK 原文）、`40-fix-report.md`（含 round-2 段）、
`60-test-output.txt`、实际 diff、上列真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`first_reviewer`，
`diff_fingerprint` 用上面新值，`reviewer_prior_involvement`=`none`，`verdict`∈
{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`continue`；REWORK 给 `fix_start_prompt`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
