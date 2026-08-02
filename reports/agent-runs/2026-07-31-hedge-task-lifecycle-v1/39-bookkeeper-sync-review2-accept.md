# 39-bookkeeper-sync-review2-accept —— review-2 ACCEPT 的同步、复验与 Bookkeeper 自我更正

- 评审：`review-2-fable5-task3`（`fable5`，`anthropic`），报告 `38-`，结论 **`ACCEPT`**
- 受审交付：`d2ac353`（固定区间 `9faa716..d2ac353`）
- Bookkeeper：`opus5`，2026-08-02
- **裁定：两道评审均 ACCEPT，交付技术收口。发布就绪 = 「合并前须补做」，见 §4。**

## 1. 复验：Fable5 的两处修正与一条加重事实，全部成立

### 1.1 请求速率口径 —— **Bookkeeper 算错了，须更正**

Bookkeeper 曾向 Human 陈述「500ms 下每任务约 2 次/秒，约 10 个任务打满币安 ~20 次/秒
的权重上限」。**该数字是单腿口径，错误。**

`_reconcile_own_legs` 的实现是 `for leg in legs: query_leg(...)` ——**每轮对该任务的
每一条非终态腿各查一次**。两腿在途时每轮 2 次请求：

| 口径 | 每任务请求速率 | 打满 ~20 次/秒所需任务数 |
|---|---|---|
| Bookkeeper 原述（单腿） | 2 次/秒 | ~10 个 |
| **实际（两腿在途）** | **4 次/秒** | **~5 个** |

**Human 的「控制开单标的数量」手柄据以校准的数字应为 5，不是 10。** 此更正直接影响
操作决策，已同步至 §4 的合并前清单。

### 1.2 BK-T3-002 的加重事实 —— 成立，两轮 review-1 与 Bookkeeper 均漏掉

Fable5 指出：base 版 worker **每一轮**都调用 `get_interval_us()`。核验
`git show 9faa716:backend/hedge_open_tasks/service.py`：

```python
while not self._worker_round(task_id):
    if self._store.list_non_terminal_legs_for_task(task_id):
        interval_s = (self._store.get_interval_us() or 1) / 1_000_000   # ← 循环体内，每轮重读
```

**该读取在 while 循环体内**，因此 2026-08-01 23:45:48 那次写入**不是「改了一份静止
数据」——它即时改变了正在运行的实盘服务的节奏配置**（下一轮 worker 起效；当时大概率
无 worker 在途，故为潜伏生效）。

**事件定性应加重为：未经授权改变了在运行实盘服务的行为。** 影响仍良性（值正确、只涉
重查间隔、未触碰任何资金数据），但比「写了一个文件」重一档。已同步 `PROJECT_STATE.md`。

### 1.3 「51169 文案从未显示过」—— **Bookkeeper 表述过重，须更正**

Bookkeeper 在 `36-` §2.4 与 review-2 packet 中称 51169 冻结文案「从未真正显示过」。
核验后端 `error_reason_zh`（`service.py:324` `:917`）与前端回退链
（`index.html:4326` `:4359` `:4362`：`error_reason_zh → error_code/error_category`）：

**该路径是通的。** 完整中文说明——含 `order_state_unknown` 的「查满 10 次仍不明…到
交易所核对…恢复后仅重查不重发」与 51169 冻结文案——**操作者在日志页可以看到**。

**正确表述**：从未在**任务卡**上显示过；**日志页路径自本轮 F3 修复起是通的**。
缺口是 1/7 的任务卡中文映射，不是全链路缺失。

### 1.4 scheduler 唤醒率 —— 经核实是虚惊

`PROJECT_STATE.md` 携带的「唤醒率五倍」担忧只适用于**已放弃的 100ms**：

```text
1 秒(旧)      切片 = 0.25s
500ms(本轮)   切片 = 0.25s   ← 与 1s 完全相同
100ms(已放弃)  切片 = 0.05s
```

`max(min(interval/1e6/2, 0.25), 0.005)` 的 `0.25` 封顶使 500ms 与 1s 同值，**无新增
后台负载**。该 follow-up 可关闭。

### 1.5 后续项的 blame 引用（§8 硬要求）

```text
d873699: ✓ 早于 base   2026-07-23  feat(hedge): render attempt timeline
d90f2f1: ✓ 早于 base   2026-07-23  feat(hedge): add gated real open backend
```

两条均经 `git merge-base --is-ancestor` 确认早于 `base_sha`，`pre-existing-independent`
标注成立。

## 2. 评审过程事件：工作区在评审进行中被切至 `main`

Fable5 报告 `§8` 记录：评审进行中（约 15:50:58）主工作区被会话外操作从 stage 分支切至
`main`，其一度 grep 到 `main` 的旧代码、险些误判「交付被回退」。

Bookkeeper 核验（2026-08-02 16:0x）：

- 发现时 `HEAD` 确在 `main`（`cc0cbee`）；
- **`stage` 分支 ref 完好**（`074dc21`），**交付对象 `d2ac353` 完好**；
- 工作区仅一个未跟踪文件（`38-` 报告本身），无未提交改动丢失；
- Bookkeeper 已将工作区切回 `stage/2026-07-31-hedge-task-lifecycle-v1`。

**评审结论不受影响**——Fable5 全程锚定固定区间的 git 对象，并使用 `git archive` 导出树
运行测试。但该风险真实：**飞行中切换评审环境可能让评审者的检查悄悄指向错误代码。**
本 stage 已因同类问题栽过一次（`deepseek` 曾报告文件不存在，实为不在同一 worktree）。

**建议**：模型终端运行期间不要切换主工作区分支；需要在 `main` 上操作时使用独立 worktree。

## 3. 两道评审的收口状态

| 评审 | 轮次 | 结论 |
|---|---|---|
| review-1 | r1 `codex` → r2 `gpt` → r3 `gpt` | `REWORK` → `REWORK` → **`ACCEPT`** |
| review-2 | `fable5` | **`ACCEPT`** |

`rework_count` 保持 **`2/3`**（ACCEPT 不递增）。**无 in-range 阻塞缺陷。**

## 4. 发布就绪：合并前须补做（Fable5 结论，Bookkeeper 采信）

**评审未因任何事项拒绝合并**，但合并前需 Human 完成三件事——两项裁定 + 一个动作：

1. **F4 重新裁定**（既定规则要求）。Fable5 的实质发现：`order_state_unknown` 与 F4
   **会被同一场交易所侧故障同时触发**——订单查询 inconclusive 导致暂停并要求「人工核对」，
   而账户读取失败同时让持仓表对每一行谎称「交易所无仓」。**最需要核对的时刻，恰是持仓表
   最不可信的时刻**；若操作者信了「无仓」，可能重建任务造成双重敞口。
2. **BK-T3-002 显式裁定**：接受并合并，但接受须显式，并附 ① 实盘库带时间戳快照 + 基线
   记录（mtime、`interval_us`、`version`）；② 流程规则「开发与验证运行一律在不含 `data/`
   的 worktree 或临时目录进行」；③ 把「归因止于某次指向真实路径的运行」显式记为已接受的
   调查终点。
3. **`49-` 升格**：由「被授权跳过的建议」升格为**下一次实盘启用前的硬前置**（不挡合并）。

## 5. 六条后续项（Bookkeeper 登记，非阻塞）

| # | 项 | 分类 | 引用 |
|---|---|---|---|
| 1 | 前端卡片读 `pause_reason_zh`（1/7 中文缺口） | `pre-existing-independent` | `d873699`，已核验 |
| 2 | `exposure_alert` 死枚举：删除或补写入路径 | `pre-existing-independent` | `d90f2f1`，已核验 |
| 3 | deleted/done/stopped 任务的 OSU 事件措辞失真 | in-range，非阻塞 | `38-` §6 |
| 4 | 操作守则两条：**同时在途任务 ≤ 5**（按 §1.1 更正后的数字）；banner 在屏不采信持仓表 | 运营 | `38-` §1 / §4 |
| 5 | `49-` 升格为实盘启用硬前置 | 运营 | `38-` §3 |
| 6 | F4 修复从暂缓的 Task 2 拆出单独排期 | 决策 | `38-` §4 |

第 3 条值得单独一提：它是本 stage 栽过四次的「界面断言它不知道 / 不成立的事」家族的
**轻症形态**——已删除任务的收口事件仍写「任务已暂停…请手动恢复」，而该任务既没暂停也
不可恢复。三方评审均已接受事件复用设计，故不阻塞。
