# 02-plan-review：2026-07-31-hedge-task-inline-log-v1（计划评审 dispatch packet）

> AGENTS §8「计划评审」：HIGH_RISK 任务在实现开始前须经一次独立的、跨 provider 的
> 只读计划评审。verdict 回 Bookkeeper，不触碰 `rework_count`。本终端**只读**。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-plan-review-r3
- target_role: Reviewer（计划评审，只读）
- target_model: `grok`
- provider: `xai`
- status_revision: 6
- required_skill: `agents/skills/software-architect.md`

## 本轮背景（必读，范围已整体收窄）

你在 round 1 / round 2 各返回一次 `REWORK`，两轮发现全部被采纳并封存
（`04-plan-review-r1-verdict.md`、`05-plan-review-r2-verdict.md`）。你 round 2 挖出的
持仓资金洞（`aggregate_positions` 排除 `deleted`）与 51169 冻结文案冲突，Bookkeeper
逐行复核后确认**两条都属实**。

**随后 Human 决定收窄范围**：本 stage 回到「开单任务日志」这一个核心功能，
**「任务卡卡住」的全部工作移出**（F10、六种自动暂停→自动删除、配额收口、三个再武装
入口、持仓聚合修复），另立 stage。详见 `06-scope-reduction.md`。

因此本轮是**对一个新范围的首次计划评审**，不是 round 2 的复评：

- **不要再评**已移出的内容（Goal 3/4 的调度语义、暂停→删除、持仓聚合、51169 文案）。
  你对它们的判断已完整留档，下个 stage 会直接引用，不必重挖。
- 你 round 2 中仍然适用于本范围的结论已写进 packet：`server.py` 的可选 `task_id` 过滤
  **有必要**（只滤全局分页页面会漏该任务的历史尝试）、`store.list_attempts_for_task`
  （`store.py:1403`）已存在可复用。
- 本 stage 的后端边界被收到**只允许动读路径**，并把「既有测试不应有任何一条转红」
  写成了验收判据（AC11）。请重点评这个边界是否真的可执行。

`00-task.md` 现为 `status_revision: 6`。

## Goal

对收窄后的实现 packet `00-task.md` 做只读计划评审，判断它在实现开始前是否成立：

1. **收窄是否干净**：packet 里还有没有残留的旧范围引用、自相矛盾的条款，或依赖已移出
   工作才能成立的验收项。
2. **【钱】展示口径四条硬约束是否够**：数值原样透传、未受理腿显示 `—` 绝不显示 `0`、
   失败与单腿行必须有错误原因、单腿成交行视觉可辨。这四条能否防住「用户看着日志误判
   钱的去向」？有没有第五种误读方式没被堵住（例如进行中行的空值、部分成交、
   `cumQuote` 类字段缺失、精度/科学计数法、时区）？
3. **按任务过滤的设计**：新增可选 `task_id`（或等价）参数是否是最小且正确的做法？
   分页与既有 `cursor/limit`、`entries_cursor/entries_limit` 两套游标如何共存而不重蹈
   R4 缺陷（共享游标导致任务事件每页重现）？「覆盖该任务全部尝试」应该靠什么保证
   （一次性拉全 / 独立分页 / 上限）？
4. **「后端只动读路径」边界是否可执行**：AC10（`git diff --stat` + 说明）与 AC11
   （既有测试零转红）是否足以证明没碰状态机、调度、结算、计数器、暂停/删除语义、
   worker 生命周期？有没有既动读路径又必然碰到写路径的地方？
5. **验收标准是否可执行**：11 条 Acceptance Checks 是否每条都有明确的通过/不通过判据，
   有没有「靠人工观察」或口径含糊的条目。
6. **风险分级判断是否正确**：packet 保持 `HIGH_RISK`（理由：展示成交价格/数量/订单号
   即展示账务信息；§8 的 `LOW_RISK` 只覆盖「文档或机械性改动」，本 stage 是新功能 +
   读接口参数变更）。这个判断成立吗？
7. **文件边界是否够用且不过宽**。
8. **未识别的风险**：packet 没写但实现时一定会撞上的问题。

## Allowed Files

只读。不修改任何文件。评审结论以 `[TASK_RESULT v2]` 文本返回给 Human，由 Human 转交
Bookkeeper 落盘；本终端不写 `status.json`、不写 evidence 文件。

## Inputs

- 受审对象：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`
  （`status_revision: 6`）。
- 范围收窄说明与被移出项：同目录 `06-scope-reduction.md`。
- 你的前两轮结论（背景，不必重评）：同目录 `04-plan-review-r1-verdict.md`、
  `05-plan-review-r2-verdict.md`。
- 授权文件：`AGENTS.md`（尤其 §3 安全内核、§8 评审规则）、`agents/roles.md` Reviewer 段。
- 代码（只读）：`frontend/index.html`（fake 原型在 `:4229` 起）、`frontend/self-check.js`、
  `backend/app/server.py`（`_hedge_open_logs` 在 `:588`）、
  `backend/hedge_open_tasks/service.py`（`get_logs` 在 `:673`）、
  `backend/hedge_open_tasks/store.py`（`list_attempts_page`、`list_attempts_for_task`
  在 `:1403`）、`backend/hedge_open_tasks/domain.py`（attempt/leg 字段与投影）。
- 基线：`base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`。
- provider 隔离：implementer = `claude_glm`（zhipu_glm），review-1 = `grok`（xai），
  review-2 = `codex`（openai），本 packet 定稿者 = `opus5`（anthropic）。
  - **本终端的隔离状态（须在结论中原样披露）**：你（grok / xai）同时是本 stage 的
    review-1。跨 provider 要求满足（xai ≠ zhipu_glm，你不是实现作者），终审 review-2
    （codex / openai）完全独立、未参与任何设计。但你在 review-1 阶段将评审一份**你自己
    批准过计划**的实现，`agents/roles.md` 要求披露这一事实。请在 `[TASK_RESULT v2]` 中
    写明一行：「计划评审与 review-1 同为 grok/xai，本轮已参与计划批准」。
  - 由此带来的评审要求：**若你认为 packet 的某个方向可疑，此刻就要说**。计划评审
    ACCEPT 之后，你在 review-1 阶段再推翻自己批准的方向，代价是一整轮返工。

## Acceptance Checks

- 逐条回答上述 Goal 八项，每项给出明确判断与依据（引用文件:行号）。
- 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察），阻塞项须给出可执行的修改要求。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`
  （按 AGENTS §7）。计划评审的 REWORK 表示 packet 需修订后才可实现，不计入
  `rework_count`。
- `问题记录` / `修复要求` 沿用 round 2 的做法（`inline-full-text` + 正文清单），
  **不要写 `none`**——Bookkeeper 无法封存缺正文的 REWORK。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交。
- 不做实现、不写修复代码、不启动其他终端。
- 不重评已移出本 stage 的工作（见「本轮背景」）。
- 不替 Human 做合并、部署、实盘决策。
