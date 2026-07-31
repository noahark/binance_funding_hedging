# 06：范围收窄 —— 「任务卡卡住」移出本 stage（Human 决定，2026-07-31）

Human 决定：本 stage 回到**开单任务日志**这一个核心功能，「任务卡卡住」相关的全部工作
移出，另立 stage。`00-task.md` 已重写为 revision 6。

## 移出本 stage 的内容（原 Goal 3 / Goal 4 全部）

1. **F10：任务卡「重启不生效」**。
2. **六种自动暂停改为自动删除**（Human 2026-07-31 需求，尚未实现）。
3. **配额用尽任务的收口**与三个再武装入口的配额检查。
4. **持仓聚合排除 `deleted` 的资金可见性缺口**（见下，**已升级为独立 follow-up**）。

## 收窄的收益

- 本 stage 从「前端 + 调度语义 + 状态机 + 资金投影」缩回「前端 + 一个只读过滤参数」。
- 后端只动读路径，不碰任何状态机——既有测试不应有任何一条转红，这本身成了验收判据。
- 两轮计划评审耗掉的时间没有白费：grok 的发现全部留档，下个 stage 直接可用。

## ⚠️ 不随范围收窄一起丢弃的事项

### A. 持仓聚合排除 `deleted` —— 当前就存在的资金可见性缺口

`store.aggregate_positions`（`store.py:1934-1951`）的两条查询都带 `WHERE t.status != ?`
（`STATUS_DELETED`）。**任务一旦被删（今天靠手动删就能触发），它已经成交的腿就从
`GET /api/hedge-open-positions` 消失，而账户上的敞口仍然存在。**

- 这个缺口**先于本 stage 存在**，不是本 stage 引入的，也不会因范围收窄而消失。
- 原本它只是「偶发手动」；一旦将来实现「六种自动暂停→自动删除」，它会变成**常态自动**
  ——尤其单腿敞口本身就计入失败刹车，等于攒够单腿敞口就自动把敞口藏起来。
- 因此：**它既是当前的 follow-up，也是下个 stage 的前置条件**。已写入 `PROJECT_STATE.md`。
- 发现者：计划评审 round 2（grok / xai），Bookkeeper 已逐行复核属实。

### B. 51169 文案冻结契约

`COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`（`domain.py:1315-1324`）是 10-design §2(d) /
ADR-T3 的逐字冻结契约，注释明写 `must NOT be reworded`，严禁被换成「保证金不足」话术。
下个 stage 若改暂停文案，只允许追加后缀，正文一字不改。

### C. grok 两轮计划评审的事实判断（下个 stage 直接可用，不必重挖）

1. `store.py:971` 的 R2-F1 收口**有效**，`test_hedge_store.py:174-192` 已锁定；F10
   findings 中 COOKIEUSDT「卡在 running」的叙述**判定为过时诊断**。
2. **真实残留死锁路径**：`paused` 优先于配额收口（`store.py:967-982` 要求
   `new_status == running`）→ `post_start`（`service.py:582-596`）不检查配额就
   `set_task_status(RUNNING)` + `ensure_worker` → worker 立刻 `WORKER_EXIT_TARGET_REACHED`
   退出 → 任务留在 `running` 无进展。复现条件：`target_n == failure_pause_threshold`。
3. **再武装入口有三个**：`post_start`（`service.py:582`）、`post_fill_once`（`:622`）、
   `post_fill_all`（`:636`）；另 `post_start` 不挡 `stopped`。
4. `scheduled >= target_n` 家族四站：`service.py:1116`、`store.py:686`、`:736`、`:971`。
   **清单外不得并入的三处**（谓词不同）：`domain.py:1087`（`accepted_count`）、
   `service.py:653`（dry-run `success_count`）、`store.py:806-807`（只是计数器 +1）。
5. 非人工写入 `paused` 的路径：`domain.resolve_status_after_attempt`（`domain.py:1089-1093`）、
   `store._apply_task_counters`（`:942-960`）、`service._pause_task_local` /
   `_pause_from_signal` → `store.pause_task`（`store.py:1742-1745`）、worker
   （`service.py:1097+`、`1121+`）。人工：`post_pause`（`service.py:608`）。
6. `skip_counters` 限频结算（`store.py:899-916`）不走 R2-F1 收口，配额已耗仍可能非终态。
7. `done` 语义歧义：表示「计划组用尽/不再调度」而非「全部成功」，前端文案需区分。
8. 对已 `done` 的任务点启动是幂等 200 且无中文说明（`service.py:587-588`），前端
   `showHedgeTaskActionError` 只在 `!ok` 时提示（`index.html:4318`）→ 用户体感「点了没反应」。

完整原始记录：`04-plan-review-r1-verdict.md`、`05-plan-review-r2-verdict.md`。

## Stage 收尾待办：`agents/roles.md` 补 DeepSeek 的 provider identity

Human 2026-07-31 把计划评审 round 4 改派给 **DeepSeek Pro**。`agents/roles.md` 的
provider identity 表（`claude_glm→zhipu_glm` / `kimi→moonshot` / `codex→openai` /
`Claude→anthropic` / `Grok→xai`）**没有 DeepSeek 一行**。

- 本 stage 内按 `deepseek` 为独立厂商记录，隔离据此判定。
- **不在评审中途改 `roles.md`**：provider 映射是 Harness 路由契约，其唯一权威在
  `roles.md`（`AGENTS.md` §2），中途修改属 Harness 变更，应走自己的评审。
- 因此列为 **stage 收尾待办**（`AGENTS.md` §9 第 1 条：把持久决策提升到权威文档）。

顺带的好消息：改派后四方 provider 完全不重叠（计划评审 deepseek / 实现 zhipu_glm /
review-1 xai / review-2 openai），前三轮「计划评审与 review-1 同为 grok/xai」的设计参与
污染随之消失，review-1 不再需要披露。

## 计数与流程

- `rework_count` 保持 **0**：范围收窄属 Human requirement refinement，按 `AGENTS.md` §8
  与计划评审 verdict 一样不触碰该计数器。
- 本 stage 风险分级**保持 HIGH_RISK**（review-1 + review-2）。理由见 `00-task.md`
  Identity：展示成交价格/数量/订单号即展示账务信息，且 §8 的 `LOW_RISK` 只覆盖「文档或
  机械性改动」，本 stage 是新功能 + 读接口参数变更，不符合。
- 范围整体变更，计划评审需对新 packet 重新评一轮（不是 round 3 的窄范围复评）。
