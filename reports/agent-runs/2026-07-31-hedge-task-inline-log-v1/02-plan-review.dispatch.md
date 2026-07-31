# 02-plan-review：2026-07-31-hedge-task-inline-log-v1（计划评审 dispatch packet）

> AGENTS §8「计划评审」：HIGH_RISK 任务在实现开始前须经一次独立的、跨 provider 的
> 只读计划评审。verdict 回 Bookkeeper，不触碰 `rework_count`。本终端**只读**。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-plan-review-r3
- target_role: Reviewer（计划评审 **round 3，窄范围复评**，只读）
- target_model: `grok`（Human 2026-07-31 决定：kimi 额度不可用，改派 grok）
- provider: `xai`
- status_revision: 5
- required_skill: `agents/skills/software-architect.md`

## Round 3 背景（必读）

你在 round 2 返回 `REWORK`，携带完整正文、发现清单 R2-F1..F5 与五条修订要求，已封存于
`05-plan-review-r2-verdict.md`。Bookkeeper 复核了你引用的 `store.py:1934-1951`（持仓
聚合排除 `deleted`）与 `domain.py:1315-1324`（51169 冻结模板），**两条阻塞均属实**，
并已按你的修订要求 1-4 全部改完，第 5 条「不改」的内容原样保持。

`00-task.md` 现为 `status_revision: 5`。本轮是**窄范围复评**：只判断两条阻塞是否已闭合，
不重评已通过的部分。

### 修订要点（供你核对）

1. **R2-F1**：AC5 由「敞口告警 / 持仓视图 / 已删除筛选**至少其一**」改为硬性要求——
   自动删除后该任务的已成交腿**仍须计入** `GET /api/hedge-open-positions`，即修改
   `aggregate_positions` 不再因 `deleted` 丢弃已成交 fill/leg（或等价且默认可见的方案）；
   「已删除筛选可见」降为附加验收，不能单独满足。`aggregate_positions` 修复已写入
   Goal 3 与 Allowed Files 的 `store.py` 说明。回报须写明用户在默认视图哪里看到这笔钱。
2. **R2-F2**：Goal 3 增加例外条款——51169 的 `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`
   正文逐字冻结，只允许追加固定删除后缀，严禁换成「保证金不足」话术；其余五条可改为
   删除语义。Stop 增加同款禁令。AC3 增加「冻结正文逐字未变」的断言要求。
3. **R2-F3**：Goal 1 的进度口径交叉引用由 Goal 3 改指 Goal 4；Goal 4 的 COOKIEUSDT
   「卡在 running」动机句降级为历史注记。
4. **R2-F4**：AC4 点名搜索符号（`pause_task` / `_pause_task_local` / `_pause_from_signal` /
   `STATUS_PAUSED` 赋值点 / `resolve_status_after_attempt` 返回值）；Stop 补持仓不丢腿与
   51169 冻结两条；Goal 3 增加事件 kind payload / `reason_zh` 与 `_entry_next_action`
   （`service.py:366-367`）的时间线语义对齐要求。
5. **R2-F5（观察）**：429 连环删卡的运维后果已写入 Goal 3（明确不加防抖）；AC12 说明
   既有 `STATUS_PAUSED` 断言转红属预期，须逐个改为 `deleted` 期望并说明，禁止为让测试
   变绿而弱化 Goal 3 语义。

## Goal

**窄范围复评，只回答四个问题**：

1. **R2-F1 是否闭合**：修订后的 Goal 3 资金硬约束 + AC5，是否足以保证「自动删除后
   账户里的敞口在默认视图仍看得见」？判据是否还有可被绕过的空隙？
2. **R2-F2 是否闭合**：51169 的「正文冻结 + 只追加后缀」写法，是否既满足删除语义又
   不破坏 ADR-T3 冻结契约？AC3 的断言要求够不够。
3. **改动有没有引入新问题**：`aggregate_positions` 不再排除 `deleted` 是一处契约变更
   （`GET /api/hedge-open-positions` 的输出会变），是否会影响其它已冻结的资金投影、
   前端展示或既有测试？有没有更小的改法？
4. **是否可以开工**：若两条阻塞已闭合且无新问题，返回 `ACCEPT`；否则给出仍未闭合的
   具体判据与最小修订。

不要重评已通过的部分（Goal 3/4 正交、家族清单、文件边界、drain 约束、r1 五条），除非
本轮修订破坏了它们。

## Allowed Files

只读。不修改任何文件。评审结论以 `[TASK_RESULT v2]` 文本返回给 Human，由 Human 转交
Bookkeeper 落盘；本终端不写 `status.json`、不写 evidence 文件。

## Inputs

- 本 stage：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`（受审对象，
  `status_revision: 5`）、`status.json`、`04-plan-review-r1-verdict.md`、
  `05-plan-review-r2-verdict.md`（你前两轮的结论与 Bookkeeper 处置）。
- 授权文件：`AGENTS.md`（尤其 §3 安全内核、§8 评审规则）、`agents/roles.md` Reviewer 段。
- 本轮重点代码（只读）：`backend/hedge_open_tasks/store.py:1934-1951`
  （`aggregate_positions` 排除 `deleted`）、`backend/hedge_open_tasks/domain.py:1315-1324`
  （51169 冻结模板）、`backend/app/server.py` 的 `_hedge_open_positions`、
  `frontend/index.html` 的持仓与任务筛选展示。
- 其余代码（按需只读）：`service.py`、`domain.py`、`frontend/index.html`。
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

- 逐条回答上述 Goal 四项，每项给出明确判断与依据（引用文件:行号）。
- 对每条问题标注严重度（阻塞实现 / 建议修改 / 观察），阻塞项须给出可执行的修改要求。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`
  （按 AGENTS §7）。计划评审的 REWORK 表示 packet 需修订后才可实现，不计入
  `rework_count`。
- `问题记录` / `修复要求` 沿用 round 2 的做法（`inline-full-text` + 正文清单），
  不要写 `none`。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交。
- 不做实现、不写修复代码、不启动其他终端。
- 不替 Human 做合并、部署、实盘决策。
