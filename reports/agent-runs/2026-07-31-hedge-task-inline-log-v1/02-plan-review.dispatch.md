# 02-plan-review：2026-07-31-hedge-task-inline-log-v1（计划评审 dispatch packet）

> AGENTS §8「计划评审」：HIGH_RISK 任务在实现开始前须经一次独立的、跨 provider 的
> 只读计划评审。verdict 回 Bookkeeper，不触碰 `rework_count`。本终端**只读**。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-plan-review
- target_role: Reviewer（计划评审，只读）
- target_model: `grok`（Human 2026-07-31 决定：kimi 额度不可用，改派 grok）
- provider: `xai`
- status_revision: 3
- required_skill: `agents/skills/software-architect.md`

## Goal

对实现 packet `00-task.md` 做一次只读计划评审，判断它在实现开始前是否成立。重点：

1. **F10 方向 B 是否正确**：packet 否决了方向 A（把调度上限改成 `accepted >= target_n`），
   理由是那会突破用户设定的「计划 N 组」资金上限、且 A-1 上限在预留事务中原子生效。
   这个判断是否成立？方向 B 能否真正消除「重启不生效」的死锁？
2. **根因家族清单是否完整**：packet 列出 `scheduled >= target_n` 的四处站点
   （`service.py:1116`、`store.py:686`、`:736`、`:971`）。是否有遗漏站点，或有站点
   不属于该家族？
3. **验收标准是否可执行**：8 条 Acceptance Checks 是否每条都有明确的通过/不通过判据，
   有没有「靠人工观察」或口径含糊的条目。
4. **文件边界是否够用且不过宽**：Allowed Files 是否足以完成 Goal，是否包含了不必要的
   文件（尤其 `server.py` 的可选参数是否必要，能否只靠前端过滤而不改后端契约）。
5. **Stop 条款是否覆盖真实风险**：资金语义、暂停阈值、轮询、scope 蔓延。
6. **未识别的风险**：packet 没写但实现时一定会撞上的问题。

## Allowed Files

只读。不修改任何文件。评审结论以 `[TASK_RESULT v2]` 文本返回给 Human，由 Human 转交
Bookkeeper 落盘；本终端不写 `status.json`、不写 evidence 文件。

## Inputs

- 本 stage：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`（受审对象）、
  `status.json`、`01-intake-to-opus5.md`（交接背景）。
- 授权文件：`AGENTS.md`（尤其 §3 安全内核、§8 评审规则）、`agents/roles.md` Reviewer 段。
- F10 诊断：`reports/agent-runs/2026-07-hedge-fast-fix-v1/findings.md`（F10 行）。
- 代码（只读）：`backend/hedge_open_tasks/service.py`、`store.py`、`domain.py`、
  `backend/app/server.py`、`frontend/index.html`（fake 原型在 `:4229` 起）。
- 基线：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`。
- provider 隔离：implementer = `claude_glm`（zhipu_glm），review-1 = `grok`（xai），
  review-2 = `codex`（openai），本 packet 定稿者 = `opus5`（anthropic）。
  - **本终端的隔离状态（须在结论中原样披露）**：你（grok / xai）同时是本 stage 的
    review-1。跨 provider 要求满足（xai ≠ zhipu_glm，你不是实现作者，`AGENTS.md` §8
    与 `agents/roles.md` Reviewer 的 review-1 隔离成立），终审 review-2（codex / openai）
    完全独立、未参与任何设计。但你在 review-1 阶段将评审一份**你自己批准过计划**的
    实现，`agents/roles.md` 要求披露这一设计参与事实。请在 `[TASK_RESULT v2]` 中写明
    一行：「计划评审与 review-1 同为 grok/xai，本轮已参与计划批准」。
  - 由此带来的评审要求：**若你认为 packet 的某个方向可疑，此刻就要说**。计划评审
    ACCEPT 之后，你在 review-1 阶段再推翻自己批准的方向，代价是一整轮返工。

## Acceptance Checks

- 逐条回答上述 Goal 6 项，每项给出明确判断与依据（引用文件:行号）。
- 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察），阻塞项须给出可执行的修改要求。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`
  （按 AGENTS §7）。计划评审的 REWORK 表示 packet 需修订后才可实现，不计入
  `rework_count`。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交。
- 不做实现、不写修复代码、不启动其他终端。
- 不替 Human 做合并、部署、实盘决策。
