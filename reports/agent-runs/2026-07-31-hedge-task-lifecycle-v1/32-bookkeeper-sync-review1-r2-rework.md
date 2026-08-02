# 32-bookkeeper-sync-review1-r2-rework —— review-1 复审 REWORK 的同步与同根因刹车判定

- 评审：`review-1-gpt-task3-r2`（`gpt`，`openai`），报告 `31-`，结论 **`REWORK`**
- 受审交付：`f70e6ca`（固定区间 `9faa716..f70e6ca`）
- Bookkeeper：`opus5`，2026-08-02
- **裁定：REWORK 采纳；`rework_count` 由 `1` 递增为 `2`（上限 3，剩 1 次）；**
  **`AGENTS.md` §8 的「同根因刹车」触发——下一轮不得再点补丁。**

## 1. 五条的现状

| 项 | 评审结论 | Bookkeeper 复验 |
|---|---|---|
| F1 | **部分修复** | 顺序路径确已修好（`30-` 已验：无锚点腿收口、计数不泄漏、重启归零）；**并发路径未闭合**，见 §2 |
| F2 | **部分修复** | 三种静态终态确已保持（`30-` 探针）；**并发路径未闭合**，见 §2 |
| F3 | **已修复** | 复用 `task_paused` 并补全 `_event_to_entry` 映射，含 API 层断言 |
| F4 | **已修复** | 两个 signal 产生点单点破坏各自转红（`30-` §2） |
| F5 | **已修复** | 删除迁移回填 SQL 转红 2 条（`30-` §2） |

## 2. 两条新发现的复验（Bookkeeper 独立执行）

### F1-P1 —— worker 交接与计数清理的竞态（代码顺序论证，成立）

`_run_task_worker` 的 `finally`：

```python
finally:
    with self._workers_lock:
        if self._workers.get(task_id) is threading.current_thread():
            self._workers.pop(task_id, None)      # ① 持锁：从 registry 摘除
    # ← 锁已释放，存在空窗
    self._clear_task_leg_retries(task_id)          # ② 不持锁：清理该 task 全部计数
```

**① 与 ② 不在同一个锁区间内。** `ensure_worker` 在 ① 之后即可看到 registry 无该 task
并启动新 worker；新 worker 写入 `_leg_query_retries`，随后旧 worker 的 ② 按 task 枚举
legs 并 `pop`，**把新 worker 刚写的计数清零**。

后果：该腿重新获得完整 10 次预算，收口被推迟；反复重入时预算上限实际失效。
生产入口 `post_start` / `post_fill_once` / `post_fill_all` / `_recover_workers` 均可在
空窗内触发 `ensure_worker`，**不是仅测试可达**。

评审另指出 `close()` 仅 `stop()` 后即关闭 store，worker 可能仍在 ② 中，异常被吞后计数
残留——同一清理覆盖问题的关闭路径表现。

### F2-P1 —— 收口使用查询前的旧快照（探针实证，成立）

`_worker_round` 在读取 `task` 快照之后、**无 store 锁**地调用 `_reconcile_own_legs`
（内含 executor 网络查询）；收口时 `_signal_order_state_unknown_recovery(task, ...)`
用的仍是**查询开始前**的快照，而 `store.pause_task` 的 `UPDATE` 无状态条件。

Bookkeeper 探针（在第 `2N-1` 次查询进行中把任务改为 `deleted`）：

```text
[并发] 第 19 次查询期间把任务改为 deleted
{"期望": "deleted", "实际": "paused", "pause_reason": "order_state_unknown", "terminal": [0, 0]}
=> F2-P1 成立：已删除任务被复活为 paused
```

**关键**：`post_delete` 的既有设计就是「不打断 worker、继续 drain」，因此该交错是
**设计允许的正常入口**，不是测试缝隙。上一轮的三态测试在 drain 前静态设置状态，
**结构上无法覆盖这个时间窗**。

## 3. 同根因刹车判定：**触发**

`AGENTS.md` §8：「连续两轮 `REWORK` 被归因于同一根因时，禁止第三次点补丁；下一个修复
任务必须是一次穷举根因扫描，枚举该缺陷家族在受审范围内的全部站点（含已修与未修），并
对清单外站点给出不适用理由，扫描本身仍算一轮。」

### 判定依据

| | 第一轮 REWORK（`28-`） | 第二轮 REWORK（`31-`） |
|---|---|---|
| F1 | 无 `dispatched_at_us` 锚点 → 无限重查 | worker 交接期计数被提前清零 |
| F2 | 状态粘性缺失 → 终态被复活 | 旧快照 → 终态仍被复活 |
| 性质 | 新路径未接**静态契约** | 新路径未接**运行时/并发契约** |

**同样的两个契约点（worker 生命周期、任务状态粘性），连续两轮出问题；同样的 F1、F2
两个编号；F2 甚至是同一个后果（终态被改成 `paused`），只是触发路径由静态变为并发。**

评审者在 `31-` §3 明确点破了这层联系（**根因命名，将在修复 dispatch 的 Goal 中原样
引用**）：

> `29-` §8 的 15 项清单覆盖了静态契约，并正确覆盖了 entries、状态、404、429、payload、
> 文案、API、恢复和 schema 边界。但它**不穷尽运行时接缝**：
> - 清单 #3 将 worker 生命周期标为已正确接线，却没有单列「registry 删除 → 计数清理 →
>   新 worker handoff」的并发契约，遗漏 F1-P1；
> - 清单 #2 将状态粘性标为已正确接线，却只验证已有状态快照，遗漏「查询期间状态变更后
>   仍使用旧快照」的契约，遗漏 F2-P1。

上一轮 Bookkeeper 命名的根因是「新增收口路径未与既有契约全面接线」，并已要求同族扫描；
实现者交了 15 项清单，**但该清单只扫了静态面**。第二轮暴露的是同一根因在运行时维度的
残留。

### 后果

1. **下一个修复任务必须是穷举根因扫描，不得是「修两个竞态」的点补丁**；
2. 扫描须枚举该缺陷家族在受审范围内的**全部站点，含已修与未修**，清单外站点给出不适用
   理由；
3. **扫描本身仍算一轮**：`rework_count` `1 → 2`；
4. 上限为 3，**此后仅剩 1 次**。若再出 `REWORK`，须由 Human 在「缩小范围 / 重新设计 /
   接受某项为限制 / 停止」四者中选择，Bookkeeper 不得自行再派修复。

## 4. F3 顺带修复的范围定性（评审者已给出，Bookkeeper 采信）

评审者用 `git blame` 定位到 `_event_to_entry` 缺失 `task_paused` 映射由 `8af3f22d`
引入，**早于 `base_sha` `9faa716`**，故标注为 **`pre-existing-release-critical`**：
它影响 `insufficient_*` / `collateral_cap_full` 这类资金/安全相关暂停事件在 entries
时间线上的结果语义。

评审者判定：不是本次引入，其修复是 F3 接线不可分离的必然结果，**不另立返工项**，
且当前交付已将其修好、不留发布风险。行为变化为「既有错误投影的纠正」，entries 字段
形状、排序、分页不变，原始 `logs` 与非 entries 读取方不受影响。

**Bookkeeper 采信该定性**（附有早于 `base_sha` 的引入提交引用，符合 §8 对
`pre-existing-*` 的证据要求）。

## 5. BK-T3-002 发布门：维持

评审者独立复核后维持原判：`data/hedge-open-tasks.sqlite3` 的 mtime 仍为
`2026-08-01 23:45:48`、`interval_us` 仍为 `500000`、`d8522df..f70e6ca` 无 `data/` 变化
——**本轮未新增写入，但不能抹除 2026-08-01 的历史事故**。

即使修复后两道评审通过，**合并、部署或实盘启用仍须 Human 单独裁定**。

## 6. 非阻塞观察

评审者在区间 `git diff --check` 中发现 `23-cadence-implementation.md:82` 有尾随空格，
属控制提交上下文而非受审交付，**未据此提出产品返工**。Bookkeeper 同意，不处理。
