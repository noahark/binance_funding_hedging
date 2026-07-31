# 02-plan-review：2026-07-31-hedge-task-inline-log-v1（计划评审 dispatch packet）

> AGENTS §8「计划评审」：HIGH_RISK 任务在实现开始前须经一次独立的、跨 provider 的
> 只读计划评审。verdict 回 Bookkeeper，不触碰 `rework_count`。本终端**只读**。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-plan-review-r2
- target_role: Reviewer（计划评审 **round 2**，只读）
- target_model: `grok`（Human 2026-07-31 决定：kimi 额度不可用，改派 grok）
- provider: `xai`
- status_revision: 4
- required_skill: `agents/skills/software-architect.md`

## Round 2 背景（必读）

你在 round 1 返回了 `REWORK`。两件事随后发生：

1. **你 round 1 的全部发现已被采纳并落盘**（`04-plan-review-r1-verdict.md`），
   `00-task.md` 已按你的「packet 修订要求」五条逐条修订。Bookkeeper 已复核你引用的
   `test_hedge_store.py:174-192`、`store.py:899-916`、`service.py:622-650` 三处，属实。
   已写进 packet 的：971 收口有效不得重写、COOKIEUSDT 判定为过时诊断、真实残留路径
   （paused 优先 + post_start 不检查配额）、三个再武装入口、终态沿用 `done`、`done` 的
   两种含义要在前端区分、`skip_counters` 路径要扫、清单外三处不得并入。
   - 一个流程提醒：你的 `问题记录` / `修复要求` 写了 `none`，正文是 Human 追加转交的。
     **本轮请把发现清单与修订要求的路径或全文随回执一起交出**，否则 Bookkeeper 无法封存。
2. **Human 变更了需求**，`00-task.md` 的 Goal 3 已被整体重写、原 Goal 3 的配额收口部分
   下移为 Goal 4（packet 现为 `status_revision: 4`）：所有**非人工**原因导致的 `paused`
   一律改为直接进入 `deleted` 终态，`paused` 此后只剩人工手动暂停。这是新增的一大块，
   你 round 1 没有评过，请重点评。

## Goal

对修订后的实现 packet `00-task.md` 做一次只读计划评审，判断它在实现开始前是否成立。重点：

1. **「六种自动暂停全改删除」是否会造成新的资金或运维风险**。Bookkeeper 曾建议只改
   `consecutive_submission_failure` 一种（其余五种是限流/余额/保证金/数量/抵押额度打满，
   都是补一下就能继续的外部临时状况），**Human 明确选择六种全改**。这是已定的产品决策，
   不要求你推翻它；请评估它的**实现风险**并指出 packet 是否已把风险约束住：
   - 单腿敞口达阈值 → 自动删除，敞口是否会从界面消失（packet AC5 的硬约束是否足够）；
   - 429 限流 → 自动删除，是否会在一次限频窗口内批量删掉多张卡；
   - 自动删除与 worker drain 在途腿的时序（packet AC6）。
2. **`paused` 只剩人工来源这一不变量是否可验证**：AC4 要求用全量搜索证明，这个判据够不够。
3. **Goal 3 与 Goal 4 是否正交**：你在 round 1 指出的真实残留路径是「`paused` 优先于
   配额收口 → `post_start` 不检查配额 → 静默再武装」。Goal 3 把六种自动暂停改成
   `deleted` 之后，该路径的触发者只剩**人工暂停**（`deleted` 的 `post_start` 已抛 409）。
   请评：① packet 的 AC2 用人工暂停构造红测是否仍能复现这条路径；② 两条 Goal 会不会
   互相掩盖，导致某个死锁面在测试里看不见了却仍然存在。
4. **根因家族清单是否完整**：`scheduled >= target_n` 的四处站点（`service.py:1116`、
   `store.py:686`、`:736`、`:971`）加上 `stopped` 的 `post_start` 入口，是否有遗漏。
   自动暂停站点清单（Inputs 里列的 `PAUSE_REASON_*` / `_pause_from_signal` 等）是否有遗漏。
5. **验收标准是否可执行**：12 条 Acceptance Checks 是否每条都有明确的通过/不通过判据，
   有没有「靠人工观察」或口径含糊的条目。
6. **文件边界是否够用且不过宽**：Allowed Files 是否足以完成已扩大的 Goal（六种暂停改
   删除会触碰更多 `service.py` / `domain.py` 路径），是否包含不必要的文件（尤其
   `server.py` 的可选参数是否必要，能否只靠前端过滤而不改后端契约）。
7. **Stop 条款是否覆盖真实风险**：资金语义、阈值触发条件、在途单、轮询、scope 蔓延。
8. **未识别的风险**：packet 没写但实现时一定会撞上的问题。

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
