# Handoff — 2026-07-phase2-borrow-sort-v1

## 当前状态

- `status`：`review_2`（review-1 **COMPLETE**，待 review-2 final gate）
- 提交链：H_A `d8a1164` → H_B `cc25148`（round-1 fingerprint head）→ H_bind
  `59e0eab` → … → round-1 evidence `bd0159a` → **H_A2 `2a793a9`（E1 fix，
  review-1 round-2 / review-2 fingerprint head）** → round-2 prep `deded6f`
  →（用户）治理 `2dc1aee`（stage-branch-mode DEC，非本 stage）
- `diff_fingerprint`：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
  （base = H_intake `4d47ad2`；reviewer/bookkeeper 三方重算一致 MATCH；fingerprint
  head = H_A2 产品代码完成点，其后的 evidence/治理 commit 不进入指纹）
- 测试：pytest **96 passed**（round-1 95 + E1 新测试 1，reviewer round-2 自跑复核）；
  node self-check 20 PASS（reviewer round-2 自跑复核）
- `rework_count`：1（round-1 A=REWORK E1，已 fix 且 round-2 复审通过）

## review-1 结论（COMPLETE）

- **Task A（backend）**：
  - round-1 ← fresh Kimi `session_bfdbafa6`：**REWORK**，P1 = live fundingInfo 失败不
    降级（违反 design §2 E1）。verdict `30-review-1-backend.md`。
  - **fix H_A2 `2a793a9`**：`_fetch_live` fundingInfo try/except 降级 + 空 dict +
    warning；`assemble_snapshot` 加 `extra_warnings`（additive，schema 开放 array
    未改）；`snapshot_service` 透传；新测试 `test_live_fundinginfo_failure_degrades_to_8h_with_warning`。
  - round-2 ← fresh Kimi `session_bc79ad49`（≠ round-1）：**ACCEPT**。指纹三方 MATCH
    （reviewer 重算 = bookkeeper 重算 = status.json）；reviewer **独立重跑** 96+20
    通过；fix 仅触 4 文件，零回归。verdict `30-review-1-round2-backend.md`。
- **Task B（frontend）** ← fresh Claude-GLM：round-1 **ACCEPT**，2x P3 非阻塞
  （self-check 回归网收窄 F1 + role 模板 bug F2）。backend-only fix 不影响 frontend，
  **B 无需 round-2**。verdict `30-review-1-frontend.md`。
- 两 reviewer **独立**确认：模板 `role=second_reviewer` 不在 schema 枚举（模板 bug），
  均采合规 `first_reviewer`。

## 下一步（review-2，final gate）

- **reviewer**：Codex gpt5.5，**用户交**，只读（`codex exec -s read-only`）。
- `reviewer_prior_involvement`：`direction_synthesis`（status.json 已披露；review-2
  prompt 明示， reviewer 自行判断是否构成偏见）。
- dispatch：`review-2-task-c-by-codex.prompt.md`（base=`4d47ad2`, head=`2a793a9`）。
- review-2 ACCEPT → `stage_accepted_waiting_user`（运行 `validate-stage pre-accept`，
  预期 `can_accept_final=false`，报告交用户）。
- review-2 REWORK → fixing（rework_count=2）。

## 工作树 / 门禁现状

- review-1 round-2 已落档（`30-review-1-round2-backend.md` + raw output）；status.json
  已更新至 review_2。
- **worktree-clean 结构性阻塞**（已批准根治，下 stage 生效）：night-collection 流程
  + 并行治理 commit（用户 `2dc1aee`）持续产出 untracked/modified，反复触发
  validator 的全库 `git status --porcelain` 门禁。用户已批准 **DEC-2026-07-05-001
  stage-branch mode**（`stage/<stage-id>` 分支，review diff 天然不含 main 无关变更），
  **执行时点 = 本 stage 用户验收后**。本 stage 仍在 main，night-collection untracked
  由 bookkeeper 代 commit 独立（用户授权）解除门禁。
- review-2 reviewer 用 committed fingerprint（base..2a793a9），不受 worktree untracked 影响。

## 待 review/用户决策

- **ADR-5**：bounded portfolio 选样策略（live `portfolio_filled=0`，§3.4 结果非 bug；
  是否调整策略留 design 决策）。
- **模式文档修复**：模板 T1/T2 `role=second_reviewer` → `first_reviewer`/`final_reviewer`
  （两 reviewer 独立标记的 harness bug）。

---

本地北京时间: 2026-07-05 00:17 CST
作者: bookkeeper (claude_glm)
