# Handoff — 2026-07-phase2-borrow-sort-v1

## 当前状态：✅ STAGE ACCEPTED（DONE）

- `status`：**`accepted`**（用户验收 ACCEPT，2026-07-05 08:50 CST）
- `accepted_at`：`2026-07-05T00:50:00Z`；`accepted_by`：user
- `can_accept_final`：`true`（用户门已过）
- `rework_count`：1（round-1 A=REWORK E1，已 fix 且 review-1 round-2 + review-2 复审通过）
- `diff_fingerprint`（final）：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
  （四方重算一致：round-1 Kimi + round-2 Kimi + review-2 Codex + bookkeeper）
- 测试：pytest **96 passed**（review-2 Codex + review-1 round-2 Kimi 各自独立重跑确认）；
  node self-check 20 PASS

## 提交链（main，fingerprint head `2a793a9` 之后均不进指纹）

`2a793a9`(H_A2 E1 fix) → `deded6f`(round-2 prep) → `2dc1aee`(用户 stage-branch DEC)
→ `a91507f`(round-2 evidence) → `1e7b3fc`(night-collection 独立) → `e244f77`(review-2
evidence) → `98076bd`(pre-accept bridge) → **本 commit**(accept 收口)

## 门禁链（全 PASSED）

- **review-1 round-1** ← fresh Kimi `bfdbafa6` + fresh Claude-GLM：A=**REWORK**
  （P1 live fundingInfo 失败不降级）；B=**ACCEPT**（2× P3）。
- **E1 fix** H_A2 `2a793a9`：`_fetch_live` fundingInfo try/except 降级 + warning；
  `assemble_snapshot` `extra_warnings`（additive，schema 未改）；新测试。
- **review-1 round-2** ← fresh Kimi `bc79ad49`：A=**ACCEPT**（指纹三方 MATCH，独立重跑
  96+20，零回归）。B round-1 ACCEPT（无需 round-2）。
- **review-2（final）** ← fresh Codex gpt5.5 `019f2fae`（read-only，direction_synthesis
  披露并接受）：**ACCEPT**。**实际执行** `git diff|shasum` 重算指纹 MATCH + **实际重跑**
  pytest 96 passed（raw #4656 原始证据）。评审覆盖 harness+产品+证据。
- **validate-stage pre-accept**：**PASSED**。

## mode 首试摩擦 + bridge（已解决，记录交接）

1. **worktree-clean 多源污染**：night-collection 流程 + 用户并行治理 commit 反复触发
   validator 全库 clean 门禁。用户已批准 **DEC-2026-07-05-001 stage-branch mode** 根治
   ——**下一 stage 的 H_intake 起生效**：bookkeeper 建 `stage/<stage-id>` 分支，review
   diff 天然排除 main 无关变更。本 stage 由 bookkeeper「代 commit 独立」解除。
2. **validate-stage flat schema vs 并行 rounds**：validator 期望扁平
   `review_1/2.{verdict,json_schema_valid,diff_fingerprint}` + 文件 `30-review-1.md`/
   `50-review-2.md`，与 rounds 结构不匹配。bridge：**保留 rounds 细粒度** + 加扁平
   stage-level 字段 + 创建两份汇总文件（引用 task-level 详评）。validator 未改。

## residual_risks（交接后续，均非阻塞）

- **ADR-5**：bounded-portfolio 选样策略下 `portfolio_account` 当前市场全 null
  （§3.4 设计 + 市场现实，非实现缺陷）。留 design 决策。
- 前端 self-check 切换设计期 fixture 后 BSTOCK/alias/PERP_ONLY 断言收窄（review-1 P3）。
- harness 模板 T1/T2 `role=second_reviewer` 与 schema 枚举冲突（两 reviewer 独立标记，
   待 mode doc 修订）。

## 下一 stage

- **stage-branch mode 生效**（DEC-2026-07-05-001）：下一 stage H_intake 时 bookkeeper
  建 `stage/<stage-id>` 分支，本 stage 在 main 上的工作流摩擦（worktree 多源污染、
  commit 交错）从结构上消除。
- 本 stage 产物（backend private channel + borrow_validation + fundingInfo 排序 +
  前端列拆分/日费率可见）已交付 main。

---

本地北京时间: 2026-07-05 08:50 CST（user ACCEPT，stage DONE）
作者: bookkeeper (claude_glm)
