# 平仓两段式交付 Review-2 dispatch — Sonnet 5 / Anthropic

## Identity

- task_id: `close-task-preflight-simplification-review-2-sonnet5`
- target_role: `Reviewer / Review-2`
- target_model: `sonnet5`
- provider: `anthropic`
- status_revision: `2`（本 stage `status.json` revision，对应 `current_task` 指向本 dispatch）
- required_skill: `agents/skills/reality-checker.md`

## Goal

对固定交付范围做 `HIGH_RISK` 独立只读 **Review-2（现实核验）**：判断 Codex/OpenAI 的「平仓
两段式建卡 + 启动后预检瘦身」交付**对 Human 已批准的需求、真实交付效果、证据、运营风险与发布
就绪度**是否成立（`AGENTS.md` §8：Review-2 检查需求、实际效果、证据、运营风险与发布就绪）。
固定范围、固定 SHA；评审移动中的 `HEAD` 或未提交工作树一律非接受。

Review-1（Opus 5 / Anthropic）已对代码/契约/测试/seam 给出 `ACCEPT`（handoff 见 Inputs）。
Review-2 不重复 Review-1 的逐行代码 verdict，而是从需求与真实世界效果角度独立判断；如发现
新的 `in-range` 阻塞须按 §8 标注并附证据。

## 固定范围与 SHA（formal review diff）

- base_sha：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`
- delivery_sha：`e5f83f1c7f53bba4593a51f843fd1f45f52814bd`
- 固定 diff：`git diff dc356cd7f6acdc8502cd6caa44a48f6e3c760cac..e5f83f1c7f53bba4593a51f843fd1f45f52814bd`（恰好 20 文件：实现/测试/活文档/四份计划证据）
- 该范围不含本 stage 的控制/ledger 提交（dispatch、status.json、intake、B 证据、ACTIVE.json、
  Review-1 handoff、两份控制文稿、本 dispatch）；针对控制提交的发现按 §8 评审范围口径记为范围外。

## 隔离披露

- 实现作者：Codex / OpenAI（provider `openai`）；交付范围内无其它实现/修复作者。
- 本 Reviewer：Sonnet 5 / Anthropic（provider `anthropic`）。Review-2 须与交付范围内**全部**
  实现/修复作者跨 provider：`anthropic` ≠ `openai`，隔离成立（`AGENTS.md` §3.5、
  `agents/roles.md` Reviewer/Isolation）。
- **披露 1**：Review-1 由 Opus 5（同为 `anthropic`）完成。§8 只要求 Review-2 与实现/修复作者
  跨 provider，不要求 Review-2 与 Review-1 跨 provider，故 anthropic 同时承担两轮不违反隔离；
  本 Reviewer 为独立只读新会话，未参与计划/设计/实现/Review-1。
- **披露 2**：Opus 5 曾完成本需求 v1/v2 计划复评；本 Reviewer 未参与任何计划或设计。
- 默认路由：Review-2 默认模型 `sonnet5`（Human 决定 DEC-2026-08-04-001，由 Opus 5 改为
  Sonnet 5 以节省 Claude 配额）。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-2-sonnet5.handoff.md`
- Bookkeeper 预检（2026-08-09 17:08 CST）：`test ! -e <上述路径>` → **ABSENT**，create-only 权威成立。
  该路径在开始前不存在；若开始时已存在即任务失败。Reviewer 不得修改本 dispatch、交付代码、测试、
  既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`、Review-1 handoff，不得
  commit/merge/push/部署/重启/控制服务/读凭据/访问 live DB/发起交易所请求。

handoff 须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract：引用固定 base/delivery SHA、
原始命令结果、逐项结论、问题路径、修复要求；带 `BOOKKEEPER_APPEND_ONLY` 标记以划定 source 边界。

## Inputs

按下列顺序读取（路径优先级最高）：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/close-task-preflight-simplification-review-2-sonnet5.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 小节
7. `agents/skills/reality-checker.md`（required_skill）
8. Review-1 handoff（Bookkeeper 已核验）：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-1-opus5.handoff.md`
9. stage intake evidence：`reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/stage-intake.md` 与 Bookkeeper 原始测试输出：`evidence/backend-pytest.txt`、`evidence/frontend-self-check.txt`、`evidence/git-diff-check.txt`、`evidence/bookkeeper-B-retest-summary.md`
10. v2 计划：`docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`；v2 计划复评（ACCEPT，含 C1—C3 + 活文档）：`docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`
11. Review-1 代码评审 companion（上下文，非本轮重点）：`docs/planning/close-task-preflight-simplification-2026-08-09.review-1-code-opus5.md`
12. `docs/product/PRD.md`、`docs/planning/DECISIONS.md`（DEC-2026-08-09-001）、`docs/architecture/ARCHITECTURE.md` 与 `docs/planning/hedge-open-position-cycle-v1.md` §12 supersession 指针
13. 固定 `base_sha..delivery_sha` 的完整 diff、调用方、消费者与测试

## Acceptance Checks

Review-2 聚焦需求/真实效果/证据/运营风险/发布就绪（详见 `agents/skills/reality-checker.md`）。
本 dispatch 强制的硬性先验与重点：

1. **SHA 一致**：`git rev-parse` 与 `status.json` 的 base/delivery 完全一致；`git diff --name-status
   dc356cd..e5f83f1` 是固定已提交范围（不随后续 ledger 提交移动）。
2. **隔离**：实现作者为 OpenAI、本 Reviewer 为 Anthropic；披露 Review-1 与计划复评均由 anthropic 完成。
3. **handoff create-only**：开始前 `test ! -e` 通过的确定性 handoff 为唯一写入；既有路径失败。
4. **必跑检查**（只读环境引用原始结果，并与 Bookkeeper/Review-1 比对）：
   ```
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider backend/tests
   node frontend/self-check.js
   git diff --check dc356cd7f6acdc8502cd6caa44a48f6e3c760cac e5f83f1c7f53bba4593a51f843fd1f45f52814bd
   ```
   预期 `1610 passed` / 前端全通过 / `git diff --check` 干净（Bookkeeper B 节与 Review-1 均已得此结果）。
5. **现实核验重点**（按 reality-checker skill，不限于）：
   - 需求对齐：v2 计划目标（卡片立即出现、Start 不阻塞、启动后才校验/发单）是否被交付真实满足；
     C1—C3 强制约束是否在真实运行语义下成立（非仅测试绿）。
   - 真实效果与运营风险：未部署事实是否诚实标注；两腿并发非原子、多 close 卡竞争、cache miss 实时
     等待、position-mode/env-key 前提变更等剩余风险是否已在 `PROJECT_STATE.md`/计划 §9 披露且未在本
     交付被悄悄恶化；1000x 仅人工平仓的限制是否保持。
   - 证据充分性：是否有离线测试之外可支撑资金路径安全声明的证据缺口；`_verify_close_flat` 等不可逆
     结算事实是否仍走实时查询。
   - 发布就绪：在「两轮 ACCEPT + Human 最终决定」前，本交付是否仍只是本地待评审、不得部署；有无遗漏
     的活文档失真或契约回归。
6. **verdict 规则**：一次给全反馈；存在一个有证据的 `in-range` 阻塞项即 `REWORK（返工）`；否则
   `ACCEPT（接受）`。每条 `REWORK` 发现按 §8 标 `in-range`/`pre-existing-independent`/
   `pre-existing-release-critical` 并附源码/测试/提交证据；新假设场景须满足 Scenario Admission。
   Review-1 `ACCEPT` 不替代本轮；后端全绿不替代需求/运营/发布判断。

## Stop

完成后停止，由 Claude-GLM Bookkeeper 核验；不得自行启动修复或合并/部署，不得 commit/merge/push/
部署/重启/控制服务/读凭据/访问 live DB/发起交易所请求。Reviewer 除上述确定性 handoff 外零写入。

控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`（含 `评审结论: ACCEPT（接受）` 或
`REWORK（返工）`、`问题记录`、`修复要求`）；只有格式完整且 verdict 明确才算通过。`下一步模型` 为
本 stage Bookkeeper `claude_glm`，`下一步任务` 用 `读取／执行／关卡` 形式指向确定性 handoff 与
Bookkeeper 核验关卡（Review-2 ACCEPT 后由 Human 做最终业务验收与合并/部署授权决定）。闭合标记
`[/TASK_RESULT]` 后不得再输出任何文字。
