# 01-intake-brief —— 给接手本 stage 的 opus5（bookkeeper）

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- 写于 2026-07-31 19:58 CST，作者：上一窗口的 opus5（前一 stage 的 bookkeeper）
- **你读不到上一个对话窗口，本文件是自包含的交接。** 需要原始证据时，看归档标签
  `archive/2026-07-31-hedge-task-inline-log-v1`（25 份文件，`git show` / `git ls-tree` 可取）。

## 你要做什么

Human 决定把上一 stage 移出的**四项**待办放进**同一个 stage** 处理。
**具体方案 Human 会再跟模型商议**——本文件给的是**已核实的事实**与**待决策清单**，
不是定死的方案。不要照抄成 packet 就派，先跟 Human 过一遍。

- `base_sha` = `8392fa98427059fbb7fd8eb8c631c1f5e28b6f52`（上一 stage 收尾提交，已推 main）
- 风险分级：**HIGH_RISK**（改任务状态机 + 资金可见性 + 实盘写路径）
- 上一 stage 的 `rework_count` 是 2/3；**新交付范围重置为 0**（§8）

## 四项待办与依赖关系

### ① 持仓聚合丢腿（资金可见性，**是 ② 的前置条件**）

`store.aggregate_positions`（`store.py:1934-1951`）两条查询都带 `WHERE t.status != deleted`。
**任务一被删，它已经成交的腿就从 `GET /api/hedge-open-positions` 消失，而账户上的敞口
仍然存在。**

- **今天手动删卡就会触发**，不是理论问题。
- 若先做 ②（自动删除）而不修它，会变成「攒够单腿敞口 → 自动删卡 → 敞口从界面消失」。
- 发现者：上一 stage 计划评审 r2（grok），Bookkeeper 逐行复核属实。

### ② 任务卡卡住 + 六种自动暂停改为自动删除（最大一块）

**Human 已定的产品决策**（2026-07-31）：把所有**非人工**原因导致的 `paused` 改为直接进
`deleted` 终态，`paused` 此后只剩人工手动暂停；删掉的卡不可恢复，重试靠手动重建
（**不做**「按原参数复制新建」按钮）。Bookkeeper 曾建议只改「连续失败」一种，
**Human 明确选择六种全改**——这是已定决策，不要再劝。

**两轮计划评审已挖清的事实（直接引用，不要重挖）**：

1. **`store.py:971` 的 R2-F1 收口是有效的**，`test_hedge_store.py:174-192` 已锁定
   「计划 1、连败 1 < 阈值 3 → 结算后 `done`」。F10 findings 里 COOKIEUSDT「卡在
   running」的叙述**已判定为过时诊断**，不要拿它当验收对象。
2. **真实残留死锁路径**：`paused` 优先于配额收口（`store.py:967-982` 要求
   `new_status == running`，而暂停先落）→ `post_start`（`service.py:582-596`）
   **不检查配额**就 `set_task_status(RUNNING)` + `ensure_worker` → worker 立刻
   `WORKER_EXIT_TARGET_REACHED` 退出 → 任务留在 `running` 无进展。
   复现条件：`target_n == failure_pause_threshold`。
3. **再武装入口有三个**：`post_start`（`service.py:582`）、`post_fill_once`（`:622`）、
   `post_fill_all`（`:636`）；另 `post_start` 不挡 `stopped`。
4. **`scheduled >= target_n` 家族四站**：`service.py:1116`、`store.py:686`、`:736`、`:971`。
   **清单外不得并入的三处**（谓词不同）：`domain.py:1087`（`accepted_count`）、
   `service.py:653`（dry-run `success_count`）、`store.py:806-807`（只是计数器 +1）。
5. **非人工写入 `paused` 的路径**：`domain.resolve_status_after_attempt`
   （`domain.py:1089-1093`）、`store._apply_task_counters`（`:942-960`）、
   `service._pause_task_local` / `_pause_from_signal` → `store.pause_task`
   （`store.py:1742-1745`）、worker（`service.py:1097+`、`1121+`）。
   人工：`post_pause`（`service.py:608`）。
6. `skip_counters` 限频结算（`store.py:899-916`）**不走** R2-F1 收口，配额已耗仍可能非终态。
7. `done` 语义歧义：表示「计划组用尽/不再调度」而非「全部成功」，前端文案需区分。
8. 对已 `done` 的任务点启动是幂等 200 且**无中文说明**（`service.py:587-588`），
   前端 `showHedgeTaskActionError` 只在 `!ok` 时提示（`index.html:4318`）→ 用户体感
   「点了没反应」。

**必须守住的红线**：

- **51169 文案逐字冻结**：`COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`
  （`domain.py:1315-1324`）是 ADR-T3 契约，注释明写 `must NOT be reworded`，
  **严禁换成「保证金不足」话术**（平台级抵押上限是全平台共享、追加资金无效，
  「保证金不足」是它要否认的假事实）。只允许**追加**删除后缀。
- **自动删除不得终止正在 drain 在途腿的 worker**（`post_delete` 现有行为是不打断，
  继续 drain 到终态再退出，见 `service.py:609-619`）。
- 不得放宽 A-1 计划上限（`scheduled_attempt_count` = 用户设定的下单次数硬上限）；
  **不得**把它改成 `accepted` 口径——那会让失败无限重发、突破用户设定的资金上限。

### ③ 重查间隔 1 秒 → 100ms（Human 提出）

- 目前**写死 1 秒、没有设置入口**（`store.py:19`、`scheduler.py:5` 注释均为 "fixed 1s"）。
- `service.py:178` 用 `// 1_000_000` 整除 → **亚秒值会显示成 `0`**，改之前要先修展示。
- **实盘模式下它不影响下单频率**：下一组要等两条腿都终态（A-9 每任务串行），间隔只用于
  「还有非终态腿时等多久再查」。
- **风险**：查询权重按任务数放大（10 个任务 × 10 次/秒 = 100 次/秒），而 **429 当前会
  暂停任务**。
- 建议：拆分「下单调度间隔」与「订单重查间隔」（现在共用一个值，语义不同）、加下限、
  考虑 429 退避而非暂停。

### ④ O1 覆盖保护（最小，可搭车）

`resolve_leg_from_query` 写 `avg_price` / `quote_amt` **无 `COALESCE`**，后一次查询返回
`None` 会覆盖已知值。**当前不可达**（币安订单详情 GET 同时返回两者），是上游变化时的
保险。上一 stage review-2 裁定不阻塞合并。改法：`COALESCE(?, avg_price)` 或等价的
「不用未知覆盖已知」。

## 待 Human 决策（开工前问清）

1. **四项的先后与拆分**：①必须在②之前（前置条件）。③④相对独立，是否并行？
2. **`done` 的终态叫什么**：上一 stage 计划评审建议「沿用现有 `done`，不新造状态枚举」，
   但②之后语义会更混（「计划用尽未达成」vs「全部成功」）。是否需要区分？
3. **model 分配**：上一 stage 中 `grok`（xai）担任了 4 轮计划评审 + 3 轮 review-1，
   视角已相当固定；`deepseek` 只做过一轮计划评审、表现干净且是全新视角；
   `codex`（openai）做 review-2 抓到了两轮 in-range 缺陷，是本 stage 唯一发现真问题的
   评审位。实现者一直是 `claude_glm`（zhipu_glm）。是否轮换？
4. **是否先做运行时验证**：上一 stage 的日志功能**已合并但从未在真实服务上跑过**
   （review-2 明确声明）。②要改的正是任务状态机——在动状态机之前先确认现有功能可用，
   可能更稳。这需要 Human 授权的只读检查（`PROJECT_STATE.md` 的 live-risk 条款）。

## 上一 stage 值得带走的两条教训

1. **不要只读代码字面就下结论，要验证外部真实行为。** 上一 stage 的 bookkeeper（我）
   两次栽在这里：看到判零条件写着 `(None, "", "0", 0)` 就断定完备，没验证币安实际返回
   `"0.00000"`；还把「不许改这个函数」写成 packet 禁令，主动堵死了实现者发现它的路。
   该缺陷最终由 review-2 抓到，耗掉一次返工额度。
2. **评审结论的正文经常不随回执转交。** 上一 stage 七轮评审中**四轮**如此（两轮索要后
   补齐，两轮因是 `ACCEPT` 未阻断）。在 dispatch 的 Acceptance Checks 里写死
   「`问题记录`/`修复要求` 写 `inline-full-text` 并把清单放在**同一次输出的正文里**」
   仍不足以杜绝——提醒 Human 转交时带上正文。

## 你的下一步

1. 按 `AGENTS.md` §4 读：`AGENTS.md` → `reports/agent-runs/ACTIVE.json` →
   `PROJECT_STATE.md` → 本 stage `status.json` → 本文件 → `agents/roles.md` Bookkeeper 段。
2. **先跟 Human 过一遍上面四个决策点**，再动手写 packet。
3. HIGH_RISK 须在实现前做一次独立的跨 provider 计划评审（§8）。
4. 准备 dispatch 后再改 `status.json` 的最后一版指向它；**不要自己启动任何终端**（§3 #2）。
