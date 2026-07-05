# Handoff — 2026-07-phase2-borrow-sort-v1

## 当前状态

- `status`：**`stage_accepted_waiting_user`**（review-1 + review-2 全 PASSED，待用户验收）
- 提交链：H_A `d8a1164` → H_B `cc25148` → H_bind `59e0eab` → … → round-1 evidence
  `bd0159a` → **H_A2 `2a793a9`（E1 fix，最终 fingerprint head）** → round-2 prep
  `deded6f` →（用户）治理 `2dc1aee` → round-2 evidence `a91507f` → night-collection
  `1e7b3fc` →（待 commit）review-2 evidence
- `diff_fingerprint`：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
  （base = H_intake `4d47ad2`；**四方重算一致**：round-1 Kimi + round-2 Kimi +
  review-2 Codex + bookkeeper）
- 测试：pytest **96 passed**（review-2 Codex + review-1 round-2 Kimi 各自独立重跑
  确认）；node self-check 20 PASS
- `rework_count`：1（round-1 A=REWORK E1，已 fix 且 review-1 round-2 + review-2 复审通过）
- `can_accept_final`：`false`（最终验收是用户门）

## 评审门禁全通

- **review-1 round-1** ← fresh Kimi `bfdbafa6` + fresh Claude-GLM：
  - A=**REWORK**（P1 live fundingInfo 失败不降级，违反 design §2 E1）
  - B=**ACCEPT**（2× P3 非阻塞：self-check 回归网收窄 F1 + role 模板 bug F2）
- **E1 fix** H_A2 `2a793a9`：`_fetch_live` fundingInfo try/except 降级 + 空 dict +
  warning；`assemble_snapshot` 加 `extra_warnings`（additive，schema 开放 array 未改）；
  `snapshot_service` 透传；新测试。
- **review-1 round-2** ← fresh Kimi `bc79ad49`（≠ round-1）：A=**ACCEPT**
  （指纹三方 MATCH，独立重跑 96+20，零回归）。B round-1 ACCEPT（backend-only fix，
  无需 round-2）。
- **review-2（final gate）** ← fresh Codex gpt5.5 `019f2fae`（read-only）：
  **ACCEPT**。direction_synthesis 披露并接受。**实际执行** `git diff|shasum` 重算指纹
  MATCH + **实际重跑** pytest 96 passed（raw output 第 4656 行原始证据）。评审覆盖
  harness（AGENTS.md/stage-delivery.yaml/parallel-mode）+ 全产品代码 + schema/contract +
  discovery 证据链。verdict `30-review-2.md`。

## bookkeeper 独立核实

- 指纹四方一致（round-1/round-2/review-2/bookkeeper）。
- review-2 Codex 独立验证为**实际执行**（非声明）：指纹重算 shell（raw #779）+
  pytest 原始输出 `96 passed in 3.09s`（raw #4656）。
- 全部 verdict schema 合规（role 枚举内，无 second_reviewer 模板 bug 影响）。
- 耦合面三项（funding_interval_hours / daily_funding_rate / rows 排序）按 §1 实现，
  全程无自行变更。

## 下一步（用户验收门）

1. bookkeeper 运行 `validate-stage --phase pre-accept`（预期通过结构检查，
   `can_accept_final=false`——最终验收须用户拍板）。
2. **用户验收 ACCEPT** → stage DONE（合入主线 / 标记 delivered；可触发
   DEC-2026-07-05-001 stage-branch mode 执行，为下一 stage 建分支）。
3. 用户若要求调整 → 回到对应门（rework_count 上限 3，当前 1）。

## residual_risks / 待用户决策（review-2 提出，均非阻塞）

- **ADR-5**：bounded portfolio 选样策略（live `portfolio_account` 全 null 是 §3.4
  策略 + 市场现实，非实现 bug；是否调整策略留 design 决策）。
- **前端 self-check 覆盖**：切换设计期 fixture 后 BSTOCK/alias/PERP_ONLY 部分断言
  收窄（review-1 P3，后端 classify/normalize 测试兜底）。
- **模式文档修复**（harness 层）：模板 T1/T2 `role=second_reviewer` →
  `first_reviewer`/`final_reviewer`（两 reviewer 独立标记的模板 bug）。

## 工作树 / 门禁现状

- review-2 evidence（raw + last-message + 30-review-2.md）待 commit；status.json
  已更新至 stage_accepted_waiting_user。
- worktree-clean 结构性阻塞已由 DEC-2026-07-05-001 stage-branch mode 批准根治
  （执行时点 = 本 stage 验收后）；本 stage night-collection untracked 由 bookkeeper
  代 commit 独立解除（用户授权）。

---

本地北京时间: 2026-07-05 08:37 CST
作者: bookkeeper (claude_glm)
