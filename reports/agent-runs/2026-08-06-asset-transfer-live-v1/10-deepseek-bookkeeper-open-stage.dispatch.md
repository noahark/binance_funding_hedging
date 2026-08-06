Identity: task_id: asset-transfer-live-open-stage; target_role: Bookkeeper; target_model: deepseek; provider: deepseek; status_revision: none（本任务负责创建 revision 1）; required_skill: none

Goal

开设阶段 `2026-08-06-asset-transfer-live-v1`（资产互转接入真实划转，`HIGH_RISK`），
建立权威阶段状态，并对 Planner 的开发文稿执行一次跨 provider 的只读**计划评审**
（`AGENTS.md` §8 对 HIGH_RISK 的实现前要求；该评审的 verdict 返回 Planner，
不触碰 `rework_count`，也不是 Human 所说的那一轮实现后 review-1）。

本阶段的评审拓扑存在两处 Human 越门决定，你必须在阶段状态里如实记录，不得
粉饰、不得替 Human 改写为合规写法：

1. 你（Bookkeeper）兼任 review-1，违反 `agents/roles.md` Bookkeeper Purpose
   中 "without becoming an implementer, reviewer, or autonomous dispatcher"；
2. 本阶段无 review-2，违反 `AGENTS.md` §8 对 HIGH_RISK 的 review-1 + review-2
   要求。

越门原因为其余模型配额耗尽，可用模型仅剩 opus5 与 deepseek，由 Human 于
2026-08-06 决定。详见开发文稿 §3。

Allowed Files

- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/status.json`（创建）
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/11-deepseek-plan-review.md`（创建，计划评审记录）
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/20-opus5-t1-backend.dispatch.md`（仅当 Human 已在本终端给出 O-1 与 O-2 决定时创建）

Inputs

- `AGENTS.md`
- `agents/roles.md`（Bookkeeper 节 + Reviewer 节的 Provider Identity 与 Isolation）
- `reports/agent-runs/ACTIVE.json`（当前为 `{"active": null}`）
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-06-asset-transfer-live-v1/00-intake.md`（Planner 开发文稿，计划评审对象）
- Human 在本终端给出的开放项决定：O-1（授权形态）、O-2（单笔上限取值）、
  O-3（是否执行本次计划评审）、O-4（基线提交方式）
- Git 证据：`git rev-parse HEAD`、`git status --porcelain`、`git log --oneline -5`

Acceptance Checks

1. 用 `git rev-parse HEAD` 的实际输出确定 `base_sha`，并用 `git status --porcelain`
   核验工作区是否已按开发文稿 §6 完成基线提交。若仍存在未提交改动，**不要自行提交**，
   在 `blockers` 记录并把下一步交回 Human。
2. 创建本阶段 `status.json`，恰好包含 `agents/roles.md` Bookkeeper 节规定的
   全部顶层字段：`schema_version`="2"、`revision`=1、
   `stage_id`="2026-08-06-asset-transfer-live-v1"、`bookkeeper`="deepseek"、
   `phase`、`checkpoint`、`base_sha`、`delivery_sha`=null、`ledger_sha`、
   `current_task`、`next`、`rework_count`=0、`blockers`。
   每个 SHA 必须直接来自 `git rev-parse` 输出，写入前对照 Git 验证。
3. 在 `blockers` 中写入两条具名条目，逐条记录 Goal 所述的两处越门：条目须含
   规则出处、越门内容、Human 决定日期与原因。这两条是记录而非阻塞，不得因其
   拒绝开阶段。
4. 将 `reports/agent-runs/ACTIVE.json` 指向本阶段。
5. 若 Human 批准 O-3：以只读方式评审 `00-intake.md`，产出
   `11-deepseek-plan-review.md`，至少覆盖——设计是否满足 Human 点名的任务 2 与
   任务 3；幂等设计（`client_request_id` 唯一索引 + one-shot 不重试 + 「结果未知」
   显式状态）是否足以防止重复划转真金白银；单笔上限与 `confirm` 门是否构成足够的
   动钱约束；错误回显三分类是否会诱导用户重试一笔可能已成功的划转；任务拆分与
   验收标准是否可执行。结论用 `ACCEPT` 或 `REWORK`，`REWORK` 须给可执行的修改
   要求。**该 verdict 返回 Planner（opus5），不触碰 `rework_count`。**
   若 Human 未批准 O-3，跳过本项并在 `status.json` 记录跳过事实与 Human 决定。
6. 仅当 Human 已给出 O-1 与 O-2 的决定时，才创建 T1 后端实现 dispatch
   （`20-opus5-t1-backend.dispatch.md`），其形状严格为 `agents/roles.md` 规定的
   `Identity / Goal / Allowed Files / Inputs / Acceptance Checks / Stop` 六段，
   `target_model`=opus5、`provider`=anthropic、`required_skill`=
   `agents/skills/senior-developer.md`（实现任务恰好一个技能）。准备好 dispatch
   之后，再让最后一次 `status.json` 修订指向它。
   **O-1 或 O-2 缺任一项，不得创建该 dispatch**，把 `next.actor` 设为
   `human_operator` 并说明缺哪一项决定。
7. 不修改 `AGENTS.md`、`agents/roles.md`、`PROJECT_STATE.md`、任何产品代码、
   任何前后端测试。不合并、不 rebase、不 push、不部署、不接触凭证、不启动或
   转交另一个模型会话。不得代 Human 做产品决策或宣布评审接受。

Stop

返回 `AGENTS.md` §7 规定的中文 `[TASK_RESULT v2]` 后停止，并包含三行中文交接
标签（`本地北京时间`、`下一步模型`、`下一步任务`）。若执行了计划评审，同时返回
`评审结论` / `问题记录` / `修复要求` 三行。

下一个动作者是 Human：由 Human 决定尚未回答的开放项、授权基线提交，并在
dispatch 就绪后亲自启动 opus5 实现终端。你不得启动它。
