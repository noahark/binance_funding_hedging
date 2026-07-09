# Review: kimi-for-coding (DRAFT-2)

## Verdict

REWORK

## Summary

DRAFT-2 rev b 成功吸收了 round-1/round-2 的核心阻塞项：D1 的 task-local snapshot 消解了元数据交集问题；§13 明确了 review-1 产物留在 task worktree、由 `prepare-review-2` 在集成分支统一提交；§11 把 `invalid_json_attempts` 落到 `evidence/<task-id>/review-1.attempts.json`；§17 区分了 enablement stage 与 product trial stage 的 `allow_harness_change`。方向与主要不变量已经成立。剩余问题集中在**执行契约的精确性**：`allowed_scope` 与 evidence 目录的边界、`prepare-review-2` 如何跨 worktree 读取未提交 review-1 产物、canonical fingerprint 与 rebind hash 的 `--no-renames` 分歧、以及 merge/integration fingerprint 的稳定性。这些问题会让 §17 的 dry-run fixture 在实现阶段卡住或给出虚假通过。

## Findings

### P1 — `allowed_scope` 是否包含 `evidence/<task-id>/` 仍不明确（§3, §6, §9）

- §3 说 `allowed_scope` 冻结为 `backend/**` vs `frontend/**`。
- §9.3 说 record-checkpoint 校验 changed files 全部落在冻结 `allowed_scope` 内，越界 BLOCKED。
- §9.5 说 record-checkpoint 提交 `evidence/<task-id>/`。
- §6 明确 `evidence/<task-id>/` **不计入** product rebind hash，但没说它是否被允许改动、是否属于 `allowed_scope`。

如果 `allowed_scope` 严格只是 `backend/**`，record-checkpoint 无法提交 evidence 目录；如果 `allowed_scope` 被扩展为 `backend/**` + `evidence/backend/`，则 §3 的描述不准确。DRAFT-2 需要显式定义 `allowed_scope` 的两种成分：**product_scope**（用于 rebind 与不相交校验）和 **evidence_scope**（用于 commit 范围校验），或者把 `evidence/<task-id>/` 作为每个 task 自动附加的提交范围，不计入 `allowed_scope` 字面。

### P1 — `prepare-review-2` 读取其他 worktree 未提交 review-1 产物的机制未定义（§10, §13）

§13 明确 review-1 产物（`30-review-1.md`、`review-1.raw-output.md`、`review-1.attempts.json`）不提交回 task branch，以未提交文件留在各自 worktree 的 `evidence/<task-id>/` 中，由 `prepare-review-2` 在**集成分支**统一提交。

但 `prepare-review-2` 运行在集成分支的 worktree。git worktree 之间的工作树文件默认不可见（每个 worktree 有独立的 checkout 目录）。DRAFT-2 没有说明：

- `prepare-review-2` 如何通过 `git worktree list --porcelain` 定位 backend/frontend worktree 的根目录；
- 未提交文件是否通过 `git worktree` 路径直接读取，还是由 human_stage_operator 在运行 `prepare-review-2` 前手动复制到集成分支；
- 如果 human 负责复制，是否必须有 receipt/记录以保证证据链完整。

这是一个会立刻阻塞脚本实现的缺口。建议：在 §10 增加一步，`prepare-review-2` 通过 `--backend-worktree`/`--frontend-worktree` 参数或从分支名解析 worktree 路径，直接读取未提交的 review-1 artifacts，并校验它们存在于对应 worktree 中。

### P2 — canonical fingerprint 与 rebind hash 的 `--no-renames` 分歧在 product rename 下有歧义（§6）

§6 明确：
- canonical `task_diff_fingerprint` **不加** `--no-renames`（沿用 `compute_diff_fingerprint()`）；
- product rebind hash **加** `--no-renames`。

在 product 文件发生 rename/move 时：
- canonical fingerprint 会把同一内容识别为 rename，diff 体积小而 hash 反映 rename 语义；
- rebind hash 会把 rename 识别为 delete + add，diff 大但逐位可复现。

这会导致两个合法结果：rebind hash 在 rename 场景下**仍然相等**（因为两边用同样的 `--no-renames` 过滤），但 rebind hash 的值与 canonical fingerprint 的 hash 部分**语义不同**。这不是错误，但 §6 的开放问题已经意识到这一点。更关键的是：如果未来有人试图用 rebind hash 替代或校验 canonical fingerprint，口径差异会被误用。建议在 §14 schema 中把两个 hash 的字段名和注释区分开，并在 dry-run fixture 中增加一个 product rename 场景，证明 rebind 断言在 rename 下仍通过且 canonical fingerprint 也能独立重算。

### P2 — merge strategy 未指定，影响 integration fingerprint 稳定性（§10.5）

§10.5 说 "依次 merge 两 task branch"，但没有指定：
- 是否使用 `--no-ff`（强制产生 merge commit）；
- 是否允许 fast-forward；
- merge order（backend 先还是 frontend 先，或任意但需记录）；
- 如何处理 merge commit message。

如果 task branch 的 head 直接就是 base 的后代（例如只一次 checkpoint commit），`git merge` 默认会 fast-forward，导致 integration branch 的 `head_sha` 等于第二个被 merge 的 task branch 的 `head_sha`，而不是一个独立的 merge commit。这本身不影响 rebind 断言，但会影响 `integration_diff_fingerprint` 的语义：它是两个 task diff 的并集，但没有一个明确的 integration merge commit 作为锚点。建议强制 `--no-ff`，使 `merge_head_sha` 始终是一个新的 merge commit，便于 review-2 独立重算 integration diff。

### P2 — `review-1.attempts.json` schema 未给出（§11）

§11 只给出文件路径 `evidence/<task-id>/review-1.attempts.json`，没有 schema。建议明确：

```json
{
  "invalid_json_attempts": {
    "kimi": 1,
    "claude_glm": 0
  },
  "recorded_by": "human_stage_operator",
  "updated_at": "2026-07-08T19:50:22+08:00"
}
```

并说明 `prepare-review-2` 读取该文件，对每个 review-1 涉及的模型校验 `attempts ≤ 2`，超限 BLOCKED。

### P2 — stale-tip 风险在 review-1 后仍然存在（§9, §10）

§9 校验 `base_sha` 是 `HEAD` 祖先，§10 校验 merge-base 一致，§13 明确 review-1 产物不提交回 task branch。这些措施使 task branch tip 在正常情况下不会移动。但 DRAFT-2 没有显式禁止 human_stage_operator 或实现者在 review-1 ACCEPT 之后、prepare-review-2 之前对 task branch 追加 commit 或 amend。如果发生，prepare-review-2 会基于新的 tip 做 rebind，而 review-1 审的是旧 tip。

建议 §10 增加 anti-stale-tip 校验：`prepare-review-2` 计算当前 task tip 的 `task_diff_fingerprint`，并与 review-1 verdict 中记录的 `diff_fingerprint` 逐位比较，不等则 BLOCKED。

### P2 — `human_decision` 非 proceed 分支的落档格式未明确（§12）

§12 说 `assign_fix`/`escalate` 时 `prepare-review-2` 不运行，决策块由人写入受影响 track 的 evidence 或临时 stage 决策文件。但没有说明：
- 临时文件的命名（例如 `evidence/<task-id>/human-decision.json` 或 `reports/agent-runs/<stage>/human-decision.json`）；
- 内容 schema（与 proceed 分支的 `human_decision` 块是否一致）；
- validator 如何在后续阶段校验这些文件。

建议统一落档路径为 `evidence/<task-id>/human-decision.json`（task 级决策）或 `reports/agent-runs/<stage>/human-decision.json`（stage 级决策），并在 §14 schema 更新中增加 `human_decision` 的 required fields。

### P2 — 单 owner 路径的 `record-checkpoint` 行为未细化（§7, §9）

§7 允许单 owner 阶段直接在 `stage/<id>` 上运行 `record-checkpoint` 并写顶层 `status.json`，§9 的契约是按 task branch 写的（`--branch <task-branch>`、不写顶层 status.json）。DRAFT-2 没有说明单 owner 时：
- `record-checkpoint` 是否仍带 `--branch stage/<id>`；
- 是否跳过 `prepare-review-2`；
- 顶层 `status.json` 由 record-checkpoint 直接写还是由人写；
- validator `--phase pre-review` 在单 owner 下如何接受 task-local 证据路径。

建议 §7 增加单 owner 的 `record-checkpoint` 调用示例和状态机转换说明。

### P3 — §14 "允许 stage_branch.name 为 task branch 形态" 的改动量被高估（§14）

`scripts/validate-stage.py:validate_stage_branch()` 只比较 `current_branch == status.json.stage_branch.name`，不校验模板格式。因此 task branch 名称（如 `stage/<id>/backend-glm`）作为 `stage_branch.name` 在当前 validator 下已经可以通过。§14 第一项说需要"允许 stage_branch.name 为 task branch 形态"，容易让人误以为需要改 validator。实际风险在于：当 validator 在**集成分支**跑 `--phase pre-review` 时，`stage_branch.name` 应指向集成分支 `stage/<id>`，而不是 task branch。建议 §14 更正措辞，强调 validator 需要识别"当前分支是集成分支，但 status.json.tasks[].branch 指向 task branch"的上下文，而不是简单地"允许 task branch 形态"。

## Required Changes

Before landing §14 framework changes / running the §17 enablement stage:

1. **Clarify `allowed_scope` vs evidence scope.** Either split `allowed_scope` into `product_scope` + `evidence_scope`, or state that `evidence/<task-id>/` is automatically allowed for commits but excluded from product rebind and intersection checks. Update §3, §6, §9 consistently.
2. **Define cross-worktree artifact reading in `prepare-review-2`.** Add explicit parameters or discovery logic for locating backend/frontend worktrees, and require `prepare-review-2` to read uncommitted review-1 artifacts directly from those worktrees before committing them on the integration branch.
3. **Specify merge strategy.** Force `--no-ff` for both task merges so `merge_head_sha` is always a dedicated integration merge commit.
4. **Add `review-1.attempts.json` schema** to §11 or §14, and have `prepare-review-2` enforce `invalid_json_attempts ≤ 2` per model.
5. **Add anti-stale-tip check** to `prepare-review-2`: current task tip fingerprint must equal the fingerprint recorded in the review-1 ACCEPT verdict.
6. **Define `human_decision` artifact path and schema** for `assign_fix`/`escalate` branches.
7. **Add single-owner `record-checkpoint` example** to §7, including how it writes the top-level `status.json` and how validator accepts task-local evidence paths.
8. **Add a product rename fixture** to §17 dry-run assertions to validate that canonical fingerprint recomputes and rebind assertion holds under rename/move/delete edges.

## Open Questions

1. Should `allowed_scope` be a single field that implicitly includes `evidence/<task-id>/`, or should it be split into product and evidence scopes?
2. Should `prepare-review-2` discover worktree paths automatically via `git worktree list`, or should the human operator pass them explicitly?
3. For the `--no-renames` divergence, does the project want to eventually align canonical fingerprint with rebind hash, or keep them intentionally divergent with documented semantics?
4. Who is responsible for recording `review-1.attempts.json` when the human dispatcher runs review-1 manually: the human, or should the review-1 prompt instruct the reviewer to append to it?

## Footer

本地北京时间: 2026-07-08 19:50:22 CST
下一步模型: human stage operator / dispatch author
下一步任务: Revise DRAFT-2 rev b to close the allowed_scope/evidence boundary, cross-worktree artifact reading, and merge-strategy gaps, then re-dispatch for final review or proceed to §17 enablement stage.
