# Dispatch Packet — review-2 round 5（final gate）（executor: human operator → Codex）

用户指示：round-4 Codex 仍 REWORK(F9-F12)，fix 已改派 **Fable5** 直接完成(commit
`e214d6f`)，现让 **Codex** 再跑一轮 review。`codex exec`（read-only）；输出落到
`50-review-2.md`（覆盖；round 1/2/3/4 原文存于 51-/52-/53-/50-→本轮覆盖前 bookkeeper
会先把 round-4 归档为 54-）。前置：status=review_2、工作树干净。

## 路由合规（已核）
- review_2 = Codex（openai）。fix authors = claude_glm（zhipu_glm）、**Fable5（anthropic）**。
  `validate-stage.py:717-718` 硬规则 review_2 厂商 ≠ 所有 fix author 厂商：openai ≠
  zhipu_glm、openai ≠ anthropic ✓ **通过**。用户选 Codex 绕过了 anthropic 身份约束。
- Codex 非 fix author；与设计/breakdown 作者（opus4.8/anthropic）跨厂商；
  `reviewer_prior_involvement=direction_synthesis`（四模型审计，已披露）。

`codex exec "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/59-dispatch-review-2-codex-round5.md)"`

---

## PROMPT BODY

你是 review-2 最终门（round 5，read-only）。stage `2026-07-docs-truth-sync-v1`：你在
round-4 判 REWORK（F9/F10 P1 + F11/F12 P2）。用户第二次授权超 rework 上限，fix author
改派 **Fable5（anthropic/claude-fable-5）**，已修 F9/F10（契约）并以代理 bookkeeper 处理
F11/F12。现在终审修复后范围。以 PRD/schema/server/前端为最高权威，独立复验；不得改文件。

### 受审范围（锚定 committed 指纹，勿用移动 HEAD）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..e214d6f819d76daa3b85865c1021b5aa2497ee95`
- diff_fingerprint（bookkeeper pre-review 已 PASS；verdict 中原样回填）：
  `e214d6f819d76daa3b85865c1021b5aa2497ee95:d93ff6d4be65eda9882a6145e69a8dfcb346b854af38f40da79ff49f5cdf965e`
- 注：`e214d6f` 之后另有 bookkeeper 证据提交（handoff/review 落盘/test-output），不改
  交付文件；终审锚定 `e214d6f` 的指纹（validator 已确认可复现）。

### 必须确认你 round-4 的 F9/F10 是否已解决
- **F9（P1）** `docs/api/public-market-contract.md`：offline 场景 `published_version: 0`
  是否已改为 mode-dependent 表述——live=真实内部 `PublishedState` 修订号 / offline=`0`
  sentinel（offline 不创建 PublishedState）；row-from-same-PublishedState 事实是否限定为
  live。对照 `backend/services/snapshot_service.py`（offline 路径 373-393；live
  237-257/351-359）。
- **F10（P1）** contract wire-visible warnings 清单是否补齐——round-4 reviewer 指出漏
  `refresh_command_expired:<symbol>`；fix 另独立补了 `base_raw_unavailable:<symbol>`
  （`snapshot_service.py:1400-1404` 同序列化路径）。确认清单与代码实际序列化的一致。
- **F11/F12（P2, bookkeeper-owned）** 已由 Fable5 代理处理：handoff 全文同步、status.json
  补 fix authors R3/R4 + 全员 session receipts + round-4 账目、新指纹、路由约束。

### 其余（回归）
F1–F8 保持已解决；无新引入过度承诺/回归；文件边界 0 越界（Forbidden 集：backend//
frontend//schemas//scripts/、Stage-B/Harness-track、bookticker living-docs、active
status/handoff/60-test/ACTIVE）；范围收敛正确。

### 流程注记（不影响判断）
本轮为用户第二次 rework 上限豁免（rework 5）+ round-4/5 review-1 豁免；fix author 改派
Fable5——均为已记录的 user authorization（`status.user_authorizations`），非隐藏偏离。
`40-fix-report.md` Round-4 段含超范围披露：`snapshot_service.py:320-322` docstring 仍写
same-version，但 backend 属 Forbidden，建议并入 deferred contract-amendment，不在本轮修。

### 必读
`40-fix-report.md`（Round-4/F9-F10 段）、`54-review-2-round4.md`（你 round-4 原文，
bookkeeper 归档）、`60-test-output.txt`、实际 diff、真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`final_reviewer`，
`reviewer_prior_involvement`=`direction_synthesis`，`diff_fingerprint` 用上面给定值，
`verdict`∈{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`stage_accepted_waiting_user`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
