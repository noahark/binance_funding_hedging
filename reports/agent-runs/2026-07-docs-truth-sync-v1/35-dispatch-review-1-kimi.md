# Dispatch Packet — review-1（executor: human operator → Kimi）

操作者：在 Kimi 终端执行下面 PROMPT BODY。Kimi 是本 stage 的 review-1（cross-review，
与实现者 `claude_glm` 跨提供商隔离）。read-only，不得改任何文件。执行后把原始输出落到
`reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md`。

Bookkeeper 不执行本 dispatch，不代 Kimi 生成 verdict。

Kimi one-shot：
`kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/35-dispatch-review-1-kimi.md)"`

---

## PROMPT BODY

你是 review-1（`code_reviewer` skill，只读）。评审 stage `2026-07-docs-truth-sync-v1`
的内容回填交付。**这是纯文档 stage，判据 = 文档所述是否等于已存在的 schema/代码/
前端真值；不得改任何文件。**

### 受审范围与指纹
- 提交范围：`git diff 127a600281d60b7332be8aeb9552740a5e8c3254..c72987dc5cfe288e8df887cd14a965a48e93e3f3`
- diff_fingerprint（已由 bookkeeper pre-review 校验 PASS，勿重算）：
  `c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`

### 交付文件（评审重点，8 个）
`docs/api/public-market-contract.md`、`docs/product/PRD.md`、
`docs/development/DEVELOPMENT_GUIDE.md`、`docs/planning/DECISIONS.md`、
`reports/follow-ups/README.md`、`docs/architecture/ARCHITECTURE.md`、
`reports/agent-runs/2026-07-bookticker-open-columns-v1/{70-handoff.md,20-implementation.md}`。
range 内其余文件（`00/10/11/12/15/80/81/60/62-*`、`ACTIVE.json`）是 bookkeeper
脚手架/证据，作背景读，不是实现者交付代码，勿据其判定越界。

### 必读原始工件
- `00-task.md`、`10-design.md`（含 Acceptance Criteria 与 File Boundaries）、
  `12-development-breakdown.md`、`20-implementation.md`、`60-test-output.txt`、
  `62-validate-pre-review.txt`。
- 真值对照物：`schemas/api/public-market/{snapshot,funding-history,symbol-snapshot}.schema.json`、
  `backend/app/server.py`、`backend/config.py`、`backend/tests/test_funding_history*.py`、
  `scripts/service-control.py`、`frontend/index.html`。
- 实际 diff。

### 必查项
1. **契约 vs schema 一致**：`public-market-contract.md` 新增的 `annualized_*` 字段名与
   funding-history/symbol-snapshot 端点小节，是否与对应 schema 逐字对应；**有无引入
   schema 里不存在的字段/端点/参数**（过度承诺）。
2. **PRD as-built 真实性**：是否还把「simulation-only manual open」当现存 UI；新增的
   opening_quotes/年化/后台刷新/launchd 描述是否与 contract/ARCHITECTURE/config/前端
   真值一致；技术栈 as-built vs future 分层是否正确。
3. **死链/退役措辞**：follow-ups/README 是否已无「current normative」死链、retired 表述
   是否准确；DECISIONS 历史注释是否只加注不改事实。
4. **文件边界**：diff 是否触碰任一 Forbidden 路径（`STAGE_INDEX.md`、`ROADMAP.md`、
   `harness-manifest.yaml`、`harness-design.md`、`AGENTS.md`、`stage-branch-mode.md`、
   `docs/README`、`docs/architecture/ADR/`、任何 `backend/`/`frontend/`/`schemas/`/
   `scripts/` 代码与 schema）。应为 0。
5. **P1-9 归一**：bookticker `70-handoff.md`/`20-implementation.md` 是否已无与 accepted
   冲突的 pending/not-started token，且**未篡改** SHA/Session ID/指纹等事实。
6. **需你裁决的边界分歧（见 status.json.review_1_open_observations）**：设计 P1-9 点名了
   bookticker `status.json`，但实现者未改它，理由是其第 518 行是 accepted 记录内的
   历史 note、改动 status.json note 可能构成篡改证据。请判定：该残留「remain」措辞
   是需要归一，还是合法历史。给出明确结论。

### 输出要求
- 结尾必须是一段严格 JSON verdict，匹配 `schemas/review-verdict.schema.json`，必填：
  `schema_version, stage_id, role, model, verdict, diff_fingerprint,
  reviewer_prior_involvement, reviewed_artifacts, findings, required_fixes,
  next_action`。
- `diff_fingerprint` 用上面给定值；`reviewer_prior_involvement` = `none`（Kimi 未涉入
  本 stage 设计/实现）；`role` = `review-1`。
- verdict ∈ {ACCEPT, REWORK, BLOCKED}。若 REWORK，必须给 `fix_start_prompt`
  （可直接发给 fix 实现者，含原始工件路径、findings、必修项、文件边界、验收断言）。
- 统一 footer + provider-native Session ID（或 unavailable+原因）。
- 只读：不 commit、不改文件。

## END PROMPT BODY
