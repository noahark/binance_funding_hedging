# review-1-gpt-task3-r3.dispatch

```text
Identity:
  task_id:         review-1-gpt-task3-r3
  target_role:     Reviewer (review-1, 第 3 轮 / 穷举扫描后复审)
  target_model:    gpt
  provider:        openai
  status_revision: 34
  required_skill:  agents/skills/code-reviewer.md
```

## 读取位置

主工作区 `/Users/ark/Desktop/ai code/funding_hedging`，分支
`stage/2026-07-31-hedge-task-lifecycle-v1`（本仓库有 4 个 worktree）。
先执行 `pwd && git branch --show-current`。

## Goal

对 `d2ac353` 执行 review-1 第 3 轮复审。**评审区间（固定）**：

```text
base_sha     9faa716396cbbe67ebeec272ad6b3dd443bba583
delivery_sha d2ac353…（以 status.json 为准）
```

区间内的 Bookkeeper 提交（`9568cc2` `c875425` `48257df` `10b4c2e` `0aac185` `1c19ef7`
`5bb495a` `165598e` `1f9c6a9` `0917ade`）为控制提交，按 §8 属**上下文而非受审交付**。

风险 `HIGH_RISK`。**`rework_count` 已达 `2/3`，仅剩 1 次**——若本轮 `REWORK`，须由 Human
在「缩小范围 / 重新设计 / 接受限制 / 停止」中选择，Bookkeeper 不得自行再派修复。

## 你上两轮的发现与本轮处置

你在 `31-` 提出 F1-P1（worker 交接竞态）与 F2-P1（旧快照写状态）。本轮处置**不对称**：

### F2-P1 —— 修了，而且修的是比你所述更大的家族

Human 指出原设计是「暂停/删除在当前查询之后执行」。核实成立：`post_delete` 注释原文为
「do NOT interrupt the worker … **then exits on the status check**」，**而实现从未遵守**。

Bookkeeper 派工前扫描发现：drain 阶段有**三个**站点用旧快照写状态，其中**两个早于
`base_sha`**（429、`insufficient_*`），探针三条全部稳定复现「查询中删除任务 → 复活为
`paused`」。故 F2-P1 是**既有缺陷家族**的新成员，非本次引入。

修法为**根修**：`store.pause_task`（全项目单一调用者）加 `WHERE status IN
(running, paused)` 条件写，一处覆盖三条路径；packet 明禁在三个调用点各加守卫。

### F1-P1 —— **未修，Human 决定接受为已知限制**

五要素记录见 `32-` §7.3。要点：三个触发入口（`post_start` / `post_fill_once` /
`post_fill_all`）**全为人工点击**，第四个（`_recover_workers`）只在服务启动时运行、
彼时旧进程已终止；窗口为 `_clear_task_leg_retries` 遍历 attempts/legs 的毫秒级耗时；
后果仅为该腿重获预算、收口推迟约 5 秒，**不涉资金错误、不误判订单、不重发**。
复看条件：**若将来引入任何非人工触发 `ensure_worker` 的路径，须重新评估。**

**请独立判断该接受是否成立**（见下方重点 3）。这是 Human 的风险决定，你的意见供其复核，
但不得据此单独返工——若你认为接受不成立，请在报告中说明理由并标注为需 Human 重新裁定。

## 本轮交付的实际内容

实现者的扫描在 packet 点名的三条路径与一条待确认线索之外，**自行确认并修复了两个站点**：

| # | 站点 | 性质 |
|---|---|---|
| 1e | `_stop_task_fatal_preflight` | packet 的待确认线索，判定**属同族**（preflight 无锁网络读期间 `post_delete` → 旧快照写 `stopped`）。已加 `stop_task_fatal` 条件写 + 并发回归 |
| 1f | pause 类结算的 `done` 推进 | **条件写自身引入的新问题**：两腿终态且带 pause 类事实时 `resolve_attempt` 先推进 `done`，而 `done` 不在条件写允许集内 → 随后的 pause 必然未命中 → 「余额不足则暂停」契约悄悄降级为 `done`。修法 `suppress_done=True` |

`1c`（`order_state_unknown`）另加了 service 层守卫（每轮重读权威状态），为双层保护。

## Bookkeeper 已完成的核验（不得据此代替你的判断）

- **同一探针改前全红、改后全绿**（三条路径，见 `34-` §1）；
- 破坏 `pause_task` 条件 → 3 红；**破坏 `suppress_done` → 4 条既有测试红**；
- 独立复跑 **1158 passed**；
- `data/` `frontend/` `backend/services/` diff 均空；实盘库未动；
- F1-P1 相关代码确认未被触碰。

## 请重点判断的四项

1. **条件写是否真的覆盖全族**：`WHERE status IN (running, paused)` 是否存在被绕过的路径？
   `pause_task` 返回值由 `dict|None` 改为 `(dict|None, bool)` 元组，**所有调用方与测试
   是否都正确处理了新形状**？未命中时「只记事件、不改状态」在每条路径上是否都成立？
2. **`suppress_done`（1f）是否正确且充分**：它豁免了一次 `done` 推进——**会不会让某些本
   应收口为 `done` 的场景不再收口**？与 A-1 计划上限家族、`scheduled_attempt_count >=
   target_n` 的既有收口逻辑有无冲突？
3. **F1-P1 的接受是否成立**：请独立核查「三个触发入口全为人工点击」这一事实基础——是否
   存在 Bookkeeper 与 Human 都未发现的非人工触发路径（定时器、恢复流程、API 组合调用、
   前端自动重试等）？若存在，该接受的前提即不成立。
4. **穷举清单是否真的穷尽**：`33-` §一的五族是否有遗漏族？特别是——**本轮修复本身是否
   又引入了新的运行时接缝**（1f 正是上一次修复引入的，请检查这次会不会重演）。

## Allowed Files

**只读。不得修改仓库任何文件。** 不得执行写入 `data/` 下数据库的操作（活的实盘库，
需真实数据先复制到临时目录）。不得启停任何服务进程。可自由读取与运行只读命令、测试。

## Inputs

| 材料 | 路径 |
|---|---|
| 本轮 packet | `fix-runtime-seam-scan-v1.dispatch.md` |
| 实现报告（穷举清单在 §一） | `33-runtime-seam-scan-implementation.md` |
| 测试输出 | `65-runtime-seam-scan-test-output.txt` |
| **Bookkeeper 本轮核验** | `34-bookkeeper-verification-runtime-seam-scan.md` |
| 同根因刹车判定 + 先导扫描 + F1-P1 五要素 | `32-bookkeeper-sync-review1-r2-rework.md` |
| 你上一轮的报告 | `31-review-1-gpt-task3-r2.md` |

## Acceptance Checks

1. 按固定区间读取，未移动 `HEAD`；
2. 上述四项重点均给出明确结论，不以 Bookkeeper 核验代替独立判断；
3. F2-P1 家族（1a/1b/1c/1e/1f）逐站点给出「已修复 / 未修复」结论；
4. 每条 `REWORK` 发现按 §8 标注范围三分类，`pre-existing-*` 附早于 `base_sha` 的引入
   提交引用；
5. 检查新增测试是否为真断言（可自行破坏验证）；
6. 边界：`live_hedge_executor.py`、`frontend/`、429 触发语义、51169 文案区未改动。

## Stop

只读评审 → 报告写到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/35-review-1-gpt-task3-r3.md`
→ 返回 `[TASK_RESULT v2]`，含：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

**停在这里。** 不改代码或 `status.json`、不启动其他模型、不合并。原始结果由 Human 转交
Bookkeeper（`opus5`）。

无明确且格式良好的 `ACCEPT` 即为非接受（§3 #7）。**你 `ACCEPT` 后仍不放行**：还须经
review-2（`Fable5`），且 BK-T3-002 发布门须 Human 单独裁定。
