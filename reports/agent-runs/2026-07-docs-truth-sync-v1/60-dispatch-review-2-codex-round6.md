# Dispatch Packet — review-2 round 6（final gate）（executor: human operator → Codex）

Fable5 已完成 round-6 语义收敛 fix（F13/F14，commit `d59f823`），opus4.8 已对账。现派
**Codex** 终审。`codex exec`（read-only）；输出落到 `50-review-2.md`（覆盖；round 1-5 原文
存于 51-/52-/53-/54-/50-review-2-round5.md）。前置：status=review_2、工作树干净。

## 路由合规
review_2=Codex(openai)，与全部 fix author（claude_glm=zhipu_glm、fable5=anthropic）跨
厂商 → `validate-stage.py:717-718` 通过。Codex 非 fix author；与设计/breakdown 作者
（opus4.8/anthropic）跨厂商；`reviewer_prior_involvement=direction_synthesis`（已披露）。

`codex exec "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/60-dispatch-review-2-codex-round6.md)"`

---

## PROMPT BODY

你是 review-2 最终门（round 6，read-only）。stage `2026-07-docs-truth-sync-v1`：你在
round-5 判 REWORK（F13/F14 P1 + F15 P2）。用户选了**语义收敛**路线并第三次授权超限，
Fable5 已重写 symbol-snapshot 失败矩阵 prose，bookkeeper 已修 F15。现在终审修复后范围。
以 PRD/schema/server/前端为最高权威，独立复验；不得改文件。

### 受审范围（锚定 committed 指纹）
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..d59f8234c4134e26843abeca6019b3e13a4062bd`
- diff_fingerprint（bookkeeper pre-review 已 PASS；verdict 中原样回填）：
  `d59f8234c4134e26843abeca6019b3e13a4062bd:361be6984dcc210dd77b952054b844a9ef865c8324394b1a83b69dbf0f35ea84`

### 必须确认 F13/F14 是否已解决（收敛策略）
- **F13**：symbol-snapshot 的 row-source 是否已是**唯一权威的 mode-dependent 定义**
  （live=latest PublishedState；offline=同步构建/缓存 snapshot，无 PublishedState），
  refresh_status 总注与 row 字段是否**引用该定义而非各自复述**；无条件"row always from
  published state"句是否全清。对照 `snapshot_service.py`（offline 373-393；live 237-257）。
- **F14**：`base_raw_unavailable` 是否已从公开契约**完全删除**（应 0 命中）；是否已明确
  写"首次 publication 前端点返回 503 `snapshot_not_ready`，本端点无 200 冷启动响应"。
  对照 `snapshot_service.py:333-335`（503）、`:998`（_base_raw 在 publish 前设置、无
  重置路径）、`:1395-1402`（该分支仅单元测试直调可达）。
- **收敛质量**：timeout 是否只保守说"本请求无新 publication，live row 用 last-good"、
  明写有意不枚举成因；warnings 是否为开放式非穷尽（客户端不得假设完整/不得对未记载值
  分支，refresh_status 权威）；保留的 token（如 refresh_command_expired）是否仅作
  non-normative example 且实际可达。
- **注意授权约束**：本轮**有意不**把 vocabulary 权威指向 `symbol-snapshot.schema.json`
  （它无 token 枚举、5/39 行 prose 已陈旧，指它会造新过度承诺）——这是用户授权的设计
  选择，非缺陷。

### 其余（回归）
F1–F12 保持已解决；无新引入过度承诺/回归；文件边界 0 越界；范围收敛正确（STAGE_INDEX/
ROADMAP/manifest 延后 Stage B、harness-design/AGENTS 延后 Harness 轨）。
（`snapshot_service.py:320-322` docstring same-version 属已披露 deferred，不在本 stage 修。）

### 流程注记
本轮 rework 6（三次用户超限授权）+ review-1 维持豁免 + fix author=Fable5（anthropic），
均记于 `status.user_authorizations`，非隐藏偏离。

### 必读
`40-fix-report.md`（Round-5 段）、`50-review-2-round5.md`（你 round-5 原文）、
`60-test-output.txt`、实际 diff、真值对照物。

### 输出
结尾严格 JSON verdict（`schemas/review-verdict.schema.json`）：`role`=`final_reviewer`，
`reviewer_prior_involvement`=`direction_synthesis`，`diff_fingerprint` 用上面给定值，
`verdict`∈{ACCEPT,REWORK,BLOCKED}，ACCEPT 时 `next_action`=`stage_accepted_waiting_user`。
统一 footer + Session ID（或 unavailable）。只读，不 commit。

## END PROMPT BODY
