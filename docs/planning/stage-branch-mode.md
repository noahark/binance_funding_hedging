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
3. **合回 main 的唯一时点 = 用户验收后**，由 bookkeeper 执行：
   - 优先 fast-forward（保 sha 不变 → 无需指纹 rebind）；
   - main 已被推进（如 Harness sync）时：merge main 进 stage 分支解决后
     再合回，**禁止 rebase**（rebase 重写 sha 会强制全量 rebind）；
   - 若确需 rebind，按 bstock-alias-v1 evidence-backfill 的 rebind
     先例执行（diff 哈希逐位一致才允许）。
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
- `reports/agent-runs/_template/status.json`：增 `stage_branch` 字段
  （名称 + merged_back sha）。
- `scripts/validate-stage.py`：checkpoint/pre-review 校验当前分支 =
  `stage/<stage-id>`（终态后允许 main）。

---

本地北京时间: 2026-07-05 00:45 CST
记录: Fable5（用户批准落档，待当前 GLM 开发轮完成后执行）
