# Stage 分支制（stage-branch mode）— 已批准，待执行

状态：**APPROVED-PENDING**（DEC-2026-07-05-001）。
执行时点：`2026-07-phase2-borrow-sort-v1` 完成（用户验收）之后、下一个
stage 的 H_intake 之前。执行路径：模板仓 `ai_project_harness` 先行修订
（GPT 复核），再 sync 回本项目——`AGENTS.md`/`stage-delivery.yaml` 属
harness_owned，禁止本地直接改。

## 动机（2026-07-04/05 试运行中的实际证据）

1. **工作树混污**：validator clean-worktree 门禁一次性拦下了 review-1
   修复中的 backend 文件、评审 raw output、`night-collection` 数据样本
   三个来源的变更；模型读 `git status`/`git diff` 时被无关变更干扰。
2. **提交流交错**：Harness sync 提交（92b949f…8132fb4）与业务 stage
   提交（ccb76ba 等）在 main 上交错；AGENTS.md「必须用 status.json 的
   base_sha..head_sha、禁止移动 HEAD」本质是在为此打补丁。
3. **回滚成本**：验收失败的 stage 在 main 上要 revert 提交串；分支上
   直接弃分支。

## 规则（模板修订时逐条落）

1. **建分支**：bookkeeper 在 H_intake 时创建 `stage/<stage-id>`，该
   stage 的全部提交（H_intake、H_A/H_B、review 落档、fix、终态记账）
   只落分支。单一写者纪律不变。
2. **指纹锚定分支**：base_sha/head_sha/diff_fingerprint 全部取分支上的
   提交；评审 diff = 分支上 base..head，天然不含 main 的无关变更。
3. **合回 main 的唯一时点 = 用户明确验收后**（v2，吸收 Codex 复核
   P1-1 与 P2-3），由 bookkeeper 执行：
   - `review-2 ACCEPT` 只能进入 `stage_accepted_waiting_user`，**不触发
     merge**；merge 动作只能由用户明确验收触发；
   - 默认路径：**stage 分支全程保持纯净**（不把 main merge 进分支）。
     验收后合回时，能 fast-forward 则 fast-forward（保 sha、免 rebind）；
     main 已被推进（如 Harness sync）则在 **main 侧**做 merge commit，
     冲突在 main 侧解决，分支历史不动；
   - 例外路径：stage 进行中确需 main 上的新 Harness 行为（如 validator
     修复）时，才允许 merge main 进 stage 分支，且必须记录理由，并且
     merge 后**重跑测试 + validator、重算指纹**；已出 verdict 仍绑定其
     记录的 sha（证据不变）——受审 diff 逐位不变时按 bstock-alias-v1
     rebind 先例机械重绑，有变化则重进对应评审门；
   - 任何情况下**禁止 rebase**（重写 sha 强制全量 rebind）。
4. **Harness/模板 sync 始终直接落 main**，与业务 stage 分支互不交错。
5. **验收失败/放弃的 stage**：分支保留为证据（不删除、不合并），在
   status.json 与 70-handoff.md 记录终态；main 零污染。
6. **并行模式关系**：本制度与 `docs/parallel-development-mode.md` 方案甲
   兼容（两实现终端共用 stage 分支的工作树，仍不 commit）；方案乙
   （每任务独立 worktree 分支）是其后续升级路径，此次不启用。

## 模板修订涉及面（预估）

- `AGENTS.md`：Hard Gates 增加 stage-branch 条目；「moving HEAD」条款
  改写为分支语境。
- `workflows/templates/stage-delivery.yaml`：guards 增
  `require_stage_branch`；H_intake/终态节点补建分支与合并动作。
- `reports/agent-runs/_template/status.json`：增 `stage_branch` 字段，
  取 Codex 复核 P2-4 的七字段形状：`name` / `created_from_main_sha` /
  `created_at` / `merged_back_to_main` / `merged_back_sha` /
  `merge_strategy` / `abandoned_reason`。
- `scripts/validate-stage.py`：分支 gate 仅当 status.json 存在非空
  `stage_branch.name` 时启用（历史 stage 无此字段完全不受影响）。
  按实际存在的三个 phase 区分（注意：validator 没有 "review-2" phase，
  review-2 派发前跑的就是 pre-review，不得发明新 phase）：
  - `checkpoint` / `pre-review` / `pre-accept`：当前分支必须 ==
    `stage_branch.name`；
  - status 为 accepted 且 `merged_back_to_main=true`：允许在 main 复验，
    并校验 `merged_back_sha` 在当前历史中可解析；
  - status 为 blocked/abandoned 终态：允许停在分支，不要求 main clean。

## Fable5 对 Codex 复核的裁定（2026-07-05 晚）

- **P1-1 采纳**：review-2 ACCEPT ≠ 用户验收，已写入规则 3（本轮 stage
  终态翻转的时序疑点是现实依据）。
- **P1-2 采纳 + 术语修正**：validator 只有 checkpoint/pre-review/
  pre-accept 三个 phase，"review-2" 不是 phase，不得发明新枚举值
  （fail-closed 原则）；分阶段规则已写入涉及面第 4 条。
- **P2-3 原则采纳、机制反转**：默认改为「分支保持纯净、分歧在验收后于
  main 侧 merge 解决」；「merge main 进分支」降级为例外路径（需记录
  理由），此时 Codex 要求的重跑测试/validator/指纹全部生效。原稿把它
  写成默认路径是 Fable5 的设计缺陷，已修订规则 3。
- **P2-4 全盘采纳**：七字段形状已写入涉及面第 3 条。

以下为 Codex 原文，逐字保留：

## Codex/GPT 复核意见（2026-07-05）

结论：方向成立，可以作为下一步 Harness 修订基线。它解决的是 Phase 2
试运行暴露出的主线混污问题：业务 stage、Harness sync、night-collection 同时
落 main，导致 clean-worktree 门禁频繁被无关文件打断。模板落地前建议补以下
四点。

1. **P1：`accepted` 之前不应合回 main。**
   第 3 条“合回 main 的唯一时点 = 用户验收后”是正确方向，但模板落地时要写
   清：`review-2 ACCEPT` 只能进入 `stage_accepted_waiting_user`，不能 merge；
   只有用户明确验收后，bookkeeper 才能执行 merge/fast-forward。否则模型可能
   把 review-2 通过误当最终用户验收。

2. **P1：`validate-stage.py` 的分支校验要区分 phase。**
   建议规则：
   - `checkpoint` / `pre-review` / `review-2` / `pre-accept`：必须在
     `stage/<stage-id>` 分支；
   - `accepted` 后：允许在 `main`，但必须记录
     `stage_branch.merged_back_sha`；
   - abandoned / blocked：允许分支保留，不要求 main clean。

3. **P2：main merge 回 stage 分支后，必须重跑 gate。**
   允许 main 被推进后先 merge main 进 stage 分支再合回，这个合理。但要补一条：
   merge main 进 stage 后必须重新跑测试、重算 fingerprint、重新进入 review gate。
   即使业务 diff 没变，Harness/schema/scripts 也可能改变了评审或验证语义。

4. **P2：`stage_branch` 字段需要更完整。**
   仅“名称 + merged_back sha”不够。建议最少记录：
   - `name`
   - `created_from_main_sha`
   - `created_at`
   - `merged_back_to_main`
   - `merged_back_sha`
   - `merge_strategy`
   - `abandoned_reason`

执行建议：仍然保持“模板仓 `ai_project_harness` 先行，GPT/Codex 或 Fable5
复核后再 sync 回本项目”。不要直接在本项目本地改 `AGENTS.md` /
`stage-delivery.yaml`，这些属于 `harness_owned`，下次 sync 会覆盖本地改动。

本地北京时间: 2026-07-05 17:26:56 CST
记录: Codex/GPT（独立复核）

---

本地北京时间: 2026-07-05 00:45 CST
记录: Fable5（用户批准落档，待当前 GLM 开发轮完成后执行）
