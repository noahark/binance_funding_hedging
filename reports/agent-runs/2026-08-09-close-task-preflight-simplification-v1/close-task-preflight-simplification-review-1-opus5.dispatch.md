# 平仓两段式交付 Review-1 dispatch — Opus 5 / Anthropic

## Identity

- task_id: `close-task-preflight-simplification-review-1-opus5`
- target_role: `Reviewer / Review-1`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `1`（本 stage `status.json` revision，对应 `current_task` 指向本 dispatch）
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对固定交付范围做 `HIGH_RISK` 独立只读代码评审，判断 Codex/OpenAI 的「平仓两段式建卡 +
启动后预检瘦身」实现是否以最小、安全、可恢复的方式落实 v2 计划与强制约束 C1—C3，并同步活文档。
固定范围、固定 SHA，评审移动中的 `HEAD` 或未提交工作树一律非接受。

完整评审目标、必查调用链与逐项验收见 companion：
`docs/planning/close-task-preflight-simplification-2026-08-09.review-1-code-opus5.md`（本 dispatch
引用其逐项检查，但不替代其内容）。本 dispatch 自身负责确定 SHA、status revision、唯一
create-only handoff 路径与 stop 条件。

## 固定范围与 SHA（formal review diff）

- base_sha：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`
- delivery_sha：`e5f83f1c7f53bba4593a51f843fd1f45f52814bd`
- 固定 diff：`git diff dc356cd7f6acdc8502cd6caa44a48f6e3c760cac..e5f83f1c7f53bba4593a51f843fd1f45f52814bd`（恰好 20 文件：实现/测试/活文档/四份计划证据）
- 该范围不含本 stage 的控制/ledger 提交（dispatch、status.json、intake、B 证据、ACTIVE.json、
  两份控制文稿）；针对控制提交的发现按 §8 评审范围口径记为范围外。

## 隔离披露

- 实现作者：Codex / OpenAI（provider `openai`）。
- 本 Reviewer：Opus 5 / Anthropic（provider `anthropic`）。Review-1 与实现作者跨 provider，隔离成立。
- **披露**：Opus 5 曾完成本需求 v1/v2 的独立只读**计划复评**（v2 结论 `ACCEPT`），但**未编写本次实现**。
  计划评审参与不替代本次代码 verdict；本轮必须从固定 diff 与源码调用链重新验证。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-1-opus5.handoff.md`
- Bookkeeper 预检（2026-08-09 16:46 CST）：`test ! -e <上述路径>` → **ABSENT**，create-only 权威成立。
  该路径在开始前不存在；若开始时已存在即任务失败。Reviewer 不得修改本文、交付代码、测试、既有文档、
  `status.json`、`PROJECT_STATE.md`、`ACTIVE.json`，不得 commit/merge/push/部署/重启/控制服务/读凭据/访问 live DB/发起交易所请求。

handoff 须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract：引用固定 base/delivery SHA、
原始命令结果、逐项结论、问题路径、修复要求；带 `BOOKKEEPER_APPEND_ONLY` 标记以划定 source 边界。

## Inputs

按下列顺序读取（路径优先级高于 companion 中的默认顺序）：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/close-task-preflight-simplification-review-1-opus5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 小节
7. `agents/skills/code-reviewer.md`（required_skill）
8. stage intake evidence：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/stage-intake.md`
   与 Bookkeeper 原始测试输出：`evidence/backend-pytest.txt`、`evidence/frontend-self-check.txt`、`evidence/git-diff-check.txt`、`evidence/bookkeeper-B-retest-summary.md`
9. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`（v2 计划）
10. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`（v2 计划复评 ACCEPT，含 C1—C3 + 活文档）
11. Review-1 companion：`docs/planning/close-task-preflight-simplification-2026-08-09.review-1-code-opus5.md`
12. `docs/planning/DECISIONS.md`、`docs/product/PRD.md`、`docs/architecture/ARCHITECTURE.md` 与相关历史计划更新
13. 固定 `base_sha..delivery_sha` 的完整 diff、调用方、消费者与测试

## Acceptance Checks

逐项检查清单见 companion 的「必查调用链与验收」（轻量建卡与原子状态、Start 与绕过防护、
dispatch 固定顺序与 fail-closed、C1 UM position 新鲜度/方向/数量、C2/F2 每轮 base 门、
保留与删除的读取、C3 dry-run/最终核实/既有执行语义、前端与文档）。本 dispatch 强制的硬性先验：

1. **SHA 一致**：`git rev-parse` 与 `status.json` 的 base/delivery 完全一致；`git diff --name-status
   dc356cd..e5f83f1` 是固定已提交范围（不随后续 ledger 提交移动）。
2. **隔离**：实现作者为 OpenAI、Reviewer 为 Anthropic；披露 Opus 5 计划复评参与。
3. **handoff create-only**：开始前 `test ! -e` 通过的确定性 handoff 为唯一写入；既有路径失败。
4. **必跑检查**（只读环境引用原始结果）：
   ```
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider backend/tests
   node frontend/self-check.js
   git diff --check dc356cd7f6acdc8502cd6caa44a48f6e3c760cac e5f83f1c7f53bba4593a51f843fd1f45f52814bd
   ```
   Bookkeeper 已得 `1610 passed` / 前端全通过 / `git diff --check` 干净；Reviewer 须自行复核，
   并按固定 diff 定向检查两段式 create/start、1000x 历史 NULL、UM 正反号/无行/超龄/实时失败、
   3 次 forward remaining、第二笔失败零 attempt/POST、dry-run 零 POST、open cache miss 回归、
   startup recovery、fill API 绕过。不用毫秒阈值；用 fake client 调用次数证明 create/Start 同步外部调用为 0。
5. **verdict 规则**：一次给全反馈；存在一个有证据的 `in-range` 阻塞项即 `REWORK（返工）`；实现/测试/
   契约全通过则 `ACCEPT（接受）`。每条 `REWORK` 发现按 §8 标 `in-range`/`pre-existing-independent`/
   `pre-existing-release-critical` 并附源码/测试/提交证据；新假设场景须满足 Scenario Admission。
   计划评审 `ACCEPT` 不替代代码 verdict；后端全绿不替代资金路径的静态量纲/顺序/fail-closed 检查。

## Stop

完成后停止，由 Claude-GLM Bookkeeper 核验；不得自行启动修复或 Review-2，不得 commit/merge/push/
部署/重启/控制服务/读凭据/访问 live DB/发起交易所请求。Reviewer 除上述确定性 handoff 外零写入。

控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`（含 `评审结论: ACCEPT（接受）` 或
`REWORK（返工）`、`问题记录`、`修复要求`）；只有格式完整且 verdict 明确才算通过。`下一步模型` 为
本 stage Bookkeeper `claude_glm`，`下一步任务` 用 `读取／执行／关卡` 形式指向确定性 handoff 与
Bookkeeper 核验关卡。闭合标记 `[/TASK_RESULT]` 后不得再输出任何文字。
