# 04：计划评审 round 1 verdict + 需求变更（2026-07-31）

## grok 计划评审 round 1：REWORK（正文未转交，未封存）

Human 转交的 `[TASK_RESULT v2]` 原文摘要如下（回执块由 Human 粘贴，本文件不改写其措辞）：

- `评审结论: REWORK`
- `问题记录: none（只读未落盘；完整发现见本输出正文）`
- `修复要求: none（只读未落盘；packet 修订清单见正文「packet 修订要求」）`
- `结果摘要`：方向 B 正确、A 否决成立；scheduled 四站完整但 `store.py:971` 已是半成品 B。
  AC1 与 R2-F1 现状矛盾，残留死锁在「paused + 配额用尽后 `post_start` 静默再武装」。
- `检查结果`：Goal1 方向 B pass；Goal2 家族清单 pass-with-971 注记；**Goal3-AC1 fail 阻塞**；
  Goal3-AC2/5-8 pass；Goal3-AC3/4 建议改；Goal4 边界 pass；**Goal6 残留死锁与诊断过时 fail**。
- 披露：计划评审与 review-1 同为 grok / xai，本轮已参与计划批准（按 packet 要求已披露）。

### Bookkeeper 核验：**正文已补齐，已封存**

回执首次转交时 `问题记录` / `修复要求` 均为 `none`、正文缺失，Bookkeeper 拒绝据此推进并
向 Human 索要正文。Human 已于同一轮补交 grok 终端全文（发现表 + 「packet 修订要求」
五条清单），本 verdict 据此封存。原始正文由 Human 粘贴转交，未经编辑。

grok 提供的、已核验为**事实性**的关键判断（均带代码/测试引用，Bookkeeper 已复核路径存在）：

1. **`store.py:971` 的 R2-F1 收口是有效的，不是半成品。** `test_hedge_store.py:174-192`
   （`test_apply_single_leg_drains_planned_to_done`）已锁定「计划 1、连败 1 < 阈值 3 →
   结算后为 `done`」。→ **推翻了 packet 原 AC1 的前提**：不存在「971 为何没生效」的谜团。
2. **F10 findings 中 COOKIEUSDT「卡在 running」的叙述与该测试冲突，判定为诊断过时。**
   处置：不追溯该历史实例（追溯需读实盘 DB，属 Human 授权的只读检查，本 stage 不做），
   把验收对象换成下面的真实残留路径。
3. **真实残留死锁路径**：`paused` 优先于配额收口（`store.py:967-982` 的 R2-F1 要求
   `new_status == running`，而暂停先落）→ `post_start`（`service.py:582-596`）对非
   `deleted`/`done` 一律 `set_task_status(RUNNING)` + `ensure_worker`，**不检查配额** →
   worker 立刻 `WORKER_EXIT_TARGET_REACHED` 退出 → 任务留在 `running` 无进展。
   复现条件：`target_n == failure_pause_threshold`。
4. **再武装入口不止一个**：`fill-once` / `fill-all` 在 live 下同样 `set RUNNING +
   ensure_worker`（`service.py:622-645`），与 `post_start` 同族。
5. **`done` 幂等 200 无中文说明**（`service.py:587-588`），前端 `showHedgeTaskActionError`
   只在 `!ok` 时提示（`index.html:4318`）→ 用户体感「重启没反应」。
6. **家族清单外、不得并入的三处**（不同谓词）：`domain.py:1087`（`accepted_count >=
   target_n`，成功完成口径）、`service.py:653`（dry-run `fill_all` 用 `success_count`）、
   `store.py:806-807`（只是计数器 +1，不是判据）。
7. **`skip_counters` 限频结算不走 R2-F1**（`store.py:899-916`）→ 配额已耗仍可能非终态。
8. **`done` 语义歧义**：`done` 表示「计划组用尽/不再调度」而非「全部成功」，前端文案须
   区分，否则业务误读。
9. 边界与 Stop 主线无需推翻；`server.py` 的可选 `task_id` 过滤**有必要**（禁止只滤当前
   全局页）；`store.list_attempts_for_task`（`store.py:1403`）已存在可复用。

不计入 `rework_count`：计划评审 verdict 按 `AGENTS.md` §8 不触碰该计数器。

不计入 `rework_count`：计划评审 verdict 按 `AGENTS.md` §8 不触碰该计数器。

## Human 需求变更（2026-07-31，两问两答）

Human 在收到 round 1 结论的同一时刻提出产品决策变更，**取代**原 Goal 3 的方向 B 表述：

> 「失败三次任务卡直接改成删除状态，暂停只用做人工手动暂停，这样就不存在重启导致任务
> 卡住不动的情况。」

Bookkeeper 摆出的两点事实与 Human 的决定：

1. **该变更不覆盖 F10 的实例**。COOKIEUSDT 是「计划 1 / 已调度 1 / 已受理 0 / 连续失败 1」，
   阈值 3，从未进入暂停，卡在 `running`。真正的病根是「计划次数用尽但未达成、任务无归宿」，
   必须单独收口。→ 两条都写进 Goal 3。
2. **现有 `paused` 有六个来源**，只有一个是「连续提交失败」，其余五个（429 限流、余额不足、
   保证金不足、可用数量不足、抵押额度打满）是补一下就能继续的外部临时状况。Bookkeeper
   建议只改第一条。**Human 明确选择：六种全部改成自动删除。** 该建议已提出并被 Human
   重申的决定覆盖，按 Human 决定执行。
3. **重试路径**：Human 选择手动重建（删掉就是删掉，想重试自己新建一张卡）。本 stage
   不做「复制参数新建」按钮，不扩 scope。

### Bookkeeper 主动上报的资金风险（已写入 packet 硬约束）

`单腿成交（single_leg_exposure）` 目前计入失败刹车（R2-F1 / user authorization 28 §2.1）。
六种全改自动删除后，**一个留有未平单腿敞口的任务可能被自动删除**——敞口仍在账户里，
承载它的任务卡却从默认列表消失。packet 已加死条款：自动删除不得让未平敞口从界面消失，
敞口告警与持仓视图必须仍可见。此项属 `AGENTS.md` §8 的资金语义，交计划评审 round 2 重点核。

### 计数与流程后果

- 需求变更属 Human requirement refinement，按 `AGENTS.md` §8 **不计入** `rework_count`
  （仍为 0）。
- packet 的 Goal 3 需重写，`00-task.md` 升 `status_revision: 4`。
- HIGH_RISK 的计划评审须对**修订后**的 packet 重跑一轮（round 2），仍由 grok 执行。
