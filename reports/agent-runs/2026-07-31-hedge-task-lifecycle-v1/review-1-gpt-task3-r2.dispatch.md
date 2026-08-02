# review-1-gpt-task3-r2.dispatch

```text
Identity:
  task_id:         review-1-gpt-task3-r2
  target_role:     Reviewer (review-1, 第 2 轮 / REWORK 后复审)
  target_model:    gpt
  provider:        openai
  status_revision: 31
  required_skill:  agents/skills/code-reviewer.md
```

## 读取位置（先确认）

本仓库有 **4 个 worktree**。受审内容只在**主工作区**
`/Users/ark/Desktop/ai code/funding_hedging` 的
**`stage/2026-07-31-hedge-task-lifecycle-v1`** 分支。`main` 上该 stage 目录停在 `49-`。

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
pwd && git branch --show-current
```

## Goal

对修复交付 `f70e6ca` 执行 **review-1 复审**（§8：`REWORK` 修复后返回 review-1）。

**评审区间（固定，不得移动 `HEAD`）**：

```text
base_sha     9faa716396cbbe67ebeec272ad6b3dd443bba583
delivery_sha f70e6ca20ac2… （以 status.json 为准）
```

区间内的 `9568cc2` / `c875425` / `48257df` / `10b4c2e` / `0aac185` / `1c19ef7` /
`5bb495a` 为本阶段**控制提交**（packet、`status.json`、Bookkeeper 记录），按
`AGENTS.md` §8「评审范围口径」属**上下文而非受审交付**。

风险等级 `HIGH_RISK`。

## 你在上一轮的角色（同 provider 延续）

上一轮 review-1 由 `codex`（同为 `openai`）执行，报告 `28-review-1-codex-task3.md`，
结论 `REWORK`，五条 `in-range` 发现 F1-F5。**本轮首要任务是判断这五条是否真正修复。**

Bookkeeper 已对五条逐条独立复验并确认全部成立（`27-` §6.3），修复后又逐条复验（`30-`）。
**但不要以 Bookkeeper 的核验代替你自己的判断。**

## 本轮交付内容

### F1 的修法被 Human 改变（重点复核）

上一轮的容忍机制是**「距下单时间 5 秒」的时间窗口**（锚点 `dispatched_at_us`）。
Human 于 2026-08-02 决定**整体换成内存重试计数器**，理由：

- Human 原本要求的就是原 JS 的 `getSpotOrderInfo(id, 10)` 重试计数，Bookkeeper 在前一份
  packet 中**擅自替换为时间窗口**，理由（需新增 DB 字段）不成立——计数器无需持久化；
- 两者不等价：请求超时 `DEFAULT_TIMEOUT_SECONDS = 10` 秒 **> 窗口 5 秒**，一次超时即
  吃光整个预算而实际只查了 1 次；
- 时间窗口需要锚点，**锚点缺失正是 F1 的根因**；换成计数器后 F1 从根上消失。

现行实现：`D.LEG_QUERY_MAX_RETRIES = 10`，每腿计数存于 service 实例的
`_leg_query_retries` dict（**纯内存，不落库**），未达上限时 404/-2013 与 inconclusive
一律保持非终态继续查；达上限时按最后一次结果分流（404 → `absent` 终态；仍 inconclusive
→ `SIGNAL_ORDER_STATE_UNKNOWN` → 人工暂停，腿非终态、永不重发）。

**请判断**：该机制替换本身是否正确？内存计数在并发多任务、worker 重入、恢复重启下是否
有 Bookkeeper 未发现的问题？计数清理（`service.py:1166`、`:1406`）是否覆盖所有退出路径，
会不会泄漏或提前清零？

### F2-F5 的修复

- **F2**：非运行态（`deleted`/`done`/`stopped`）只记录事件、不改状态；running/paused 仍
  走人工暂停语义。
- **F3**：复用既有 `task_paused` kind 进 entries，并**补全了 `task_paused` 的
  `_event_to_entry` 映射**。
- **F4**：两个 signal 产生点各有独立测试。
- **F5**：新增迁移回归测试。

### 已授权的越界改动

`test_hedge_review2_regressions.py::test_5b` 被修改。**Human 已确认批准**（Bookkeeper
初次核验时无此记录，事后确认属实，见 `30-` §7）。原因是本轮删除了 `test_5b` 引用的
`ABSENT_TOLERANCE_WINDOW_US` 常量——**这是 Bookkeeper packet 的自相矛盾**（要求删常量却
把引用它的文件列入禁改）。改动仅调整驱动方式，核心断言 `fail_count == 1` 逐字未改。

## 请重点判断的四项

1. **F1-F5 是否真正修复**，而非表面通过。建议自行破坏验证（Bookkeeper 的破坏输出见
   `30-` §2，请独立复现或另设破坏点）。
2. **范围外的顺带修复如何定性**：F3 补全 `task_paused` 映射时，纠正了一个既有缺陷——该
   kind 此前落入 wait 分支得到 `overall_result=None`，即既有的 `insufficient_*` /
   `collateral_cap_full` 事件在 entries 时间线上**一直投影错误**。该缺陷为 `pre-existing`，
   但其修复是 F3 接线的必然结果、无法分离。请按 §8 范围三分类给出定性，并判断这次顺带
   修复**是否改变了既有 entries 消费者的行为**（前端、日志、其它读取方）。
3. **同族扫描清单**（`29-` §8，15 项）是否真的穷尽？有没有它列为「不适用」而实际适用的
   契约？这是本轮防止「新路径未与既有契约接线」这一根因复发的主要手段。
4. **BK-T3-002 发布门**：你在上一轮认定实盘库写入构成独立发布门。本轮实现者**未再触碰
   `data/`**（Bookkeeper 三重确认：mtime 未变、值未变、留痕清单一致）。请确认该发布门
   状态是否有变化，或维持原判。

## Allowed Files

**只读。不得修改仓库中任何文件**（含 `status.json`、evidence、代码、测试）。
**不得执行任何会写入 `data/` 下数据库的操作**——那是活的实盘库，需要真实数据请先复制到
临时目录。不得启动或停止任何服务进程。

可自由读取仓库全部内容并运行只读命令与测试。

## Inputs

| 材料 | 路径 |
|---|---|
| 本轮 packet | `fix-review1-retry-counter-v1.dispatch.md` |
| 本轮实现报告（含同族扫描清单 §8、留痕 §11） | `29-fix-retry-counter-implementation.md` |
| 本轮测试输出 | `64-fix-retry-counter-test-output.txt` |
| **Bookkeeper 本轮核验** | `30-bookkeeper-verification-retry-counter.md` |
| 上一轮你的评审报告 | `28-review-1-codex-task3.md` |
| 上一轮 Bookkeeper 核验（含 §6 自认的两处错误） | `27-bookkeeper-verification-task3-500ms.md` |
| 上一轮被 REWORK 的交付 | `d8522df` |

## Acceptance Checks（你的评审须覆盖）

1. 按固定 `base_sha..delivery_sha` 读取，未移动 `HEAD`；
2. F1-F5 逐条给出「已修复 / 未修复 / 部分修复」的明确结论，附独立证据；
3. 上述四项重点均给出明确结论，不以 Bookkeeper 核验代替独立判断；
4. 每条 `REWORK` 发现按 §8 标注范围三分类，`pre-existing-*` 须附早于 `base_sha` 的引入
   提交引用；
5. 检查新增测试是否为真断言（可自行破坏验证）；
6. 检查边界：`live_hedge_executor.py`、`frontend/`、429 站点、51169 文案区未改动；
   `test_hedge_review2_regressions.py` 仅 `test_5b` 的已授权改动。

## Stop

只读评审 → 写评审记录到
`reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/31-review-1-gpt-task3-r2.md`
→ 按 `AGENTS.md` §7 返回 `[TASK_RESULT v2]`，含：

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

**停在这里。** 不得修改代码或 `status.json`、不得启动其他模型、不得合并。原始结果由
Human 转交 Bookkeeper（`opus5`）同步。

无明确且格式良好的 `ACCEPT` 即为非接受（`AGENTS.md` §3 #7）。

**你 `ACCEPT` 之后仍不放行**：本交付随后须经 review-2（`Fable5`，Human 已显式启用其独立
付费额度），且 BK-T3-002 发布门须 Human 单独裁定。
