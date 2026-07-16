# Dispatch Packet — review-2（final gate）（executor: human operator → Codex）

操作者：在 Codex 终端用 **`codex exec`（read-only）** 执行下面 PROMPT BODY（schema-bound
verdict 用 `codex exec`，不用 `codex review`）。Codex 是本 stage 的 review-2 最终门。
read-only，不得改文件。执行后把原始输出落到
`reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`。

Bookkeeper 不执行本 dispatch，不代 Codex 生成 verdict。

## 身份与隔离（如实披露）
- 实现者：`claude_glm`（zhipu_glm）。review-1：Kimi（Moonshot，ACCEPT，schema-valid）。
- review-2：Codex（openai）。**硬禁令满足**：非实现者/修复者。**优先隔离满足**：与设计者+
  breakdown 作者（Anthropic Opus，即 bookkeeper）跨 provider。
- **需你（Codex）在 verdict 中如实披露的先前涉入**：你参与过产出本 backlog 的只读四模型
  审计（direction 级）。因此 `reviewer_prior_involvement` 填 `direction_synthesis`。
  这不构成对设计者 provider 的重叠，无需 override 机制；但要求你**独立复验，不得复读
  自己的审计结论**——以 PRD/schema/server/前端真值为最高权威。

---

## PROMPT BODY

你是 review-2 最终门（read-only）。对 stage `2026-07-docs-truth-sync-v1` 的内容回填做
终审。这是纯文档 stage：判据 = 文档所述是否等于已存在的 schema/代码/前端真值。**不得
改任何文件。以 PRD/产品文档/schema/server/前端为最高权威，独立复验，不要复用你之前
四模型审计的结论作为证据。**

### 受审范围
- `git diff 127a600281d60b7332be8aeb9552740a5e8c3254..c72987dc5cfe288e8df887cd14a965a48e93e3f3`
- diff_fingerprint（bookkeeper pre-review 已校验 PASS；你在 verdict 中原样回填，勿重算）：
  `c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`
- 当前 HEAD 在 `c72987d` 之后有 bookkeeper chore 提交（status.json/handoff/评审派工/
  验证日志），不改 8 个交付文件；终审锚定 `c72987d` 的指纹。

### 交付文件（终审重点，8）
`docs/api/public-market-contract.md`、`docs/product/PRD.md`、
`docs/development/DEVELOPMENT_GUIDE.md`、`docs/planning/DECISIONS.md`、
`reports/follow-ups/README.md`、`docs/architecture/ARCHITECTURE.md`、
`reports/agent-runs/2026-07-bookticker-open-columns-v1/{70-handoff.md,20-implementation.md}`。
range 内其余为 bookkeeper 脚手架/证据（`00/10/11/12/15/35/55/80/81/60/62-*`、
`30-review-1.md`、`ACTIVE.json`），作背景，勿据其判越界。

### 必读工件
`00-task.md`、`10-design.md`（Acceptance Criteria + File Boundaries）、`11-adr.md`、
`12-development-breakdown.md`、`20-implementation.md`、`60-test-output.txt`、
`62-validate-pre-review.txt`、`30-review-1.md`（Kimi ACCEPT）。
真值对照物：`schemas/api/public-market/{snapshot,funding-history,symbol-snapshot}.schema.json`、
`backend/app/server.py`、`backend/config.py`、`backend/tests/test_funding_history*.py`、
`scripts/service-control.py`、`frontend/index.html`。实际 diff。

### 必查项
1. 契约新增 `annualized_*` 字段与 funding-history/symbol-snapshot 端点小节，是否与
   对应 schema **逐字对应、无凭空字段/端点/参数**（过度承诺）。
2. PRD 是否还把 simulation-only manual open 当现存 UI；as-built 新增
   （opening_quotes/年化/后台刷新/launchd）与 contract/ARCHITECTURE/config/前端一致；
   技术栈 as-built vs future 分层正确。
3. follow-ups/DECISIONS 的 retired/历史注释是否准确、无死链、未改事实。
4. 文件边界：diff 是否触碰任一 Forbidden（`STAGE_INDEX.md`、`ROADMAP.md`、
   `harness-manifest.yaml`、`harness-design.md`、`AGENTS.md`、`stage-branch-mode.md`、
   `docs/README`、`docs/architecture/ADR/`、任何代码/schema）。应为 0。
5. P1-9 归一是否完整且未篡改事实；认同/异议 review-1 对 bookticker status.json
   保持不动的裁决（review_1_open_observations）。
6. 范围收敛是否正确：STAGE_INDEX/ROADMAP/manifest 延后 Stage B、harness-design/AGENTS
   延后 Harness 轨——确认本 stage 未越界做这些。

### 输出要求
- 结尾必须是严格 JSON verdict，匹配 `schemas/review-verdict.schema.json`，必填：
  `schema_version, stage_id, role, model, verdict, diff_fingerprint,
  reviewer_prior_involvement, reviewed_artifacts, findings, required_fixes, next_action`。
- `role` = `final_reviewer`；`reviewer_prior_involvement` = `direction_synthesis`
  （如实披露四模型审计参与）；`diff_fingerprint` 用上面给定值；`verdict` ∈
  {ACCEPT, REWORK, BLOCKED}；ACCEPT 时 `next_action` = `stage_accepted_waiting_user`。
- REWORK 必须给 `fix_start_prompt`（可直接发 fix 实现者，含原始工件路径、findings、
  必修项、文件边界、验收断言）。
- 统一 footer + provider-native Session ID（或 unavailable+原因）。read-only，不 commit。

## END PROMPT BODY
