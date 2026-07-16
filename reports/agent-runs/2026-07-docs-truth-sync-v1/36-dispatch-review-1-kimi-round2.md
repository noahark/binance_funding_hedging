# Dispatch Packet — review-1 round 2（executor: human operator → Kimi）

fix 改动了指纹，round-1 的 ACCEPT 已作废，需在**修复后范围**重跑 review-1。
在 Kimi 终端执行 PROMPT BODY；输出落到
`reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md`（覆盖 round-1，round-1
verdict 已归档于 `status.review_rounds[0]`）。read-only，不改文件。

`kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/36-dispatch-review-1-kimi-round2.md)"`

---

## PROMPT BODY

你是 review-1（round 2，`code_reviewer`，只读）。stage `2026-07-docs-truth-sync-v1`
经 review-2 REWORK 后已由 claude_glm 修复 F1/F2/F3，现在重审**修复后**范围。判据仍是
文档所述 == schema/代码/前端真值。不得改任何文件。

### 受审范围（新）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..a77a18aa069ecc236c8448b8bdced40ea53bdeb1`
- diff_fingerprint（bookkeeper pre-review 已 PASS，勿重算）：
  `a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9`

### 本轮修复重点（必须逐条复核修得对不对）
- **F1**：`docs/api/public-market-contract.md` funding-history 段是否已说明「纯
  PublishedState 投影、empty 不证明上游抓取成功」，与 `backend/services/snapshot_service.py`
  一致；是否如实披露 `funding-history.schema.json:34` 的较窄旧述为 deferred。
- **F2**：contract symbol-snapshot 的 `ok/partial/timeout` 是否已按代码实际覆盖
  （partial 含 premium/history/borrow warnings；timeout 含 deadline/worker_not_running/
  assemble_failed）；warnings 承载原因；披露 `symbol-snapshot.schema.json:39` deferred。
  对照 `snapshot_service.py`、`backend/tests/test_symbol_snapshot_endpoint.py`。
- **F3**：bookticker `70-handoff.md`/`20-implementation.md`/`status.json` 是否已把
  未来/待办措辞历史化，且 **SHA/指纹/Session ID/verdict/用户授权等事实零改动**
  （只改时态）。

### 其余交付面
其余 6 个交付文件（PRD/DECISIONS/follow-ups/ARCHITECTURE/DEV_GUIDE + bookticker）
在 round-1 已 ACCEPT，本轮确认 fix 未引入回归即可。文件边界仍禁 Forbidden 集
（STAGE_INDEX/ROADMAP/manifest/harness-design/AGENTS/stage-branch-mode/docs-README/
ADR、全部代码/schema）。

### 必读工件
`50-review-2.md`（Codex REWORK 原文）、`40-fix-report.md`（fix 映射）、`00-task.md`、
`10-design.md`、`60-test-output.txt`（含 round-2 验证）、实际 diff、上列真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`first_reviewer`，
`diff_fingerprint` 用上面新值，`reviewer_prior_involvement`=`none`，`verdict`∈
{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`continue`；REWORK 给 `fix_start_prompt`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
