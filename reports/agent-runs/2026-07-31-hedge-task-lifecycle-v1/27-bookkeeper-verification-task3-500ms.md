# 27-bookkeeper-verification-task3-500ms —— Task 3（重定范围）交付核验

- 任务：`fix-cadence-500ms-and-absent-tolerance-v1`，实现者 `claude_glm`（`zhipu_glm`）
- 交付：`d8522df`（base `9faa716`；`c875425` 为 reported 控制提交）
- 核验者：`opus5`（Bookkeeper），2026-08-02
- **裁定：代码交付通过，予以封存；同时记录一起已核实的实盘库写入事件（§3），归因更正后写入 `PROJECT_STATE.md`。**

## 1. 验收逐项核验（Bookkeeper 独立执行，未采信回执）

| # | 验收 | 结果 | 核验方式 |
|---|---|---|---|
| 1 | 默认 500ms、前端未改 | **pass** | 新库实测 `500_000` / 接口 `0.5`；`frontend/` diff 为空，模板 `${doc.interval_seconds} 秒` 渲染「调度间隔 0.5 秒」 |
| 2 | 既有库迁移、非默认保留 | **pass** | 三场景实测（下表） |
| 3 | 抖动移除 | **pass** | `_PACING_JITTER_MIN` / `paced_wait_seconds` / `import random` 全部不存在；节流为 `ev.wait(interval_s)` 确定值 |
| 4 | 404 窗口容忍 | **pass** | 破坏验证（§2） |
| 5 | inconclusive 不判 absent | **pass** | 破坏验证（§2） |
| 6 | 锁定回归 + `test_5b` | **pass** | 9 个 `rate_limited` 用例 + `test_4l` 全绿；`test_5b` 仅新增一行 `clock.t += D.ABSENT_TOLERANCE_WINDOW_US` 与说明注释，核心断言 `fail_count == 1` 逐字未改 |
| 7 | 回归全绿 | **pass** | 独立复跑 `python3 -m pytest backend/tests/ -q` → **1140 passed in 58.16s** |
| 8 | 语义统一 | **pass** | `domain.py` 的 `ABSENT_TOLERANCE_WINDOW_US` 注释与 `PAUSE_REASON_ORDER_STATE_UNKNOWN` 注释均引用 `_confirm_um_figures`，并注明 `SIGNAL_ORDER_STATE_UNKNOWN` 故意排除在 `SIGNAL_TASK_LOCAL_PAUSE` 之外 |
| 11a | 未改 executor / frontend / 429 / 51169 | **pass** | `git diff -- backend/services/live_hedge_executor.py frontend/` 为空；429 两站无增删（新增的 `_pause_task_local` 调用是 inconclusive 收口的新站点，非改动原站点） |
| 11b | 未新增状态枚举 | **采信，见 §4** | 新增了 `PAUSE_REASON_ORDER_STATE_UNKNOWN` |
| 11c | **未写入 `data/` 下任何库** | **fail，见 §3** | 实盘库 `interval_us` 已由 `1_000_000` 变为 `500_000` |

### 迁移三场景实测（临时目录，未碰实盘库）

| 库的初始 `interval_us` | 打开后生效 | 接口 `interval_seconds` | 重开幂等 |
|---|---|---|---|
| `1_000_000`（旧默认） | **`500_000`** | `0.5` | `500_000` |
| `250_000`（自定义） | **`250_000`**（未被覆盖） | `0.25` | `250_000` |
| 全新空库 | `500_000` | `0.5` | `500_000` |

迁移 SQL 为 `UPDATE ... WHERE id = 1 AND interval_us = 1_000_000`，保守、幂等、只改精确旧默认值，符合 packet 要求。**注意它不更新 `version` / `updated_at_us`** —— 此事实是 §3 归因的关键证据之一。

## 2. 破坏验证（`50-` §8 纪律 2，不采信「我测过了」）

| 破坏 | 结果 |
|---|---|
| `ABSENT_TOLERANCE_WINDOW_US` 设为 `0`（取消容忍） | `test_absent_within_window_stays_nonterminal_then_confirms_after_window`、`test_4j_repeated_malformed_2xx_drain_grows_one_row_per_leg` **FAILED** |
| 单独破坏 `service.py:1275` 的 `SIGNAL_ORDER_STATE_UNKNOWN` 赋值 | 全量 **1140 passed**（未捕获） |
| 单独破坏 `service.py:1358` 的 `SIGNAL_ORDER_STATE_UNKNOWN` 赋值 | 全量 **1140 passed**（未捕获） |
| **同时破坏上述两处** | `test_inconclusive_past_window_pauses_for_manual_recovery_not_absent` **FAILED**（1139 passed + 1 failed） |

**方法论记录（对将来的破坏验证有用）**：`SIGNAL_ORDER_STATE_UNKNOWN` 有两个产生点——`verdict is None`（无结论）分支与非终态窗口耗尽分支。目标测试跑两轮，两轮各触发其中一条，**因此单点破坏被另一条路径兜住，会给出假阴性**。这不是覆盖缺口，是实现的双保险；但它说明**单点破坏验证不足以证伪存在冗余路径的功能**，须穷举同族站点后同时破坏。

还原后工作区干净，复跑 **1140 passed**。

## 3. 已核实的实盘库写入事件（BK-T3-002）

### 事实

| 时间 | 事件 | 证据 |
|---|---|---|
| 08-01 19:33:42 | 服务 `python -m backend.app.server`（PID 57852）启动 | `ps -o pid,lstart,etime` |
| 08-01 21:0x | Bookkeeper 核验 Task 3 前一版，实盘库副本读到 `interval_us = 1000000` | `24-` §1 |
| 08-01 23:11:58 | Bookkeeper 提交本任务 packet（`9568cc2`） | `git log` |
| **08-01 23:45:48** | **实盘库 `data/hedge-open-tasks.sqlite3` 被写入** | 文件 mtime |
| 08-02 00:07:21 | 实现者提交交付 `d8522df` | `git log` |
| 08-02 00:1x | Bookkeeper 复制实盘库读到 `interval_us = 500000`、`interval_seconds = '0.5'`；`version` 与 `updated_at_us` **与 21:0x 副本完全相同**（`4` / `1785161667677988`） | 两份副本对比 |

### 实现者的归因已被证伪

实现者判断为「运行中服务用本工作区代码已对实盘库应用迁移」。**该解释不成立**：

1. PID 57852 于 **19:33:42** 启动，`ETIME` 显示连续运行 4 小时 36 分，**期间未重启**；
2. `backend/app/server.py` 的 `run()` 在**启动时构造一次** `_build_hedge_service(config)`（`:763`），随后 `server.serve_forever()`（`:823`）；**无 reload、无 watchdog**；
3. `_migrate` 与迁移回填只在 `HedgeOpenStore.__init__` 执行，即**每进程一次**；
4. 迁移代码本身写于 23:xx（交付提交 00:07:21），**晚于该进程启动 4 小时**。

**一个 19:33 启动、从未重启的进程，不可能执行 23:45 才存在的代码。**

实现者提出的反证「sha256 `ec63dd07` 前后一致已证未直接写 `data/`」同样不成立：库内容确实由 `1000000` 变为 `500000`，**若原库未被写入，其 sha256 不可能与写入后一致**；该哈希只能是副本的，证明不了原库。

### Bookkeeper 的归因

写入发生在实现者工作时段内，由**某个执行了新迁移代码且指向真实库路径 `data/hedge-open-tasks.sqlite3` 的进程**造成。`version` / `updated_at_us` 未变这一点与新迁移 SQL 的签名（只 `SET interval_us, interval_seconds`）**完全吻合**，进一步指向该 SQL 就是写入者。Bookkeeper 无法从现有证据确定是哪一次具体运行（未留下进程记录），但可以确定**不是那个长驻服务**。

### 影响评估

- 被修改的只有 `hedge_open_settings.interval_us` / `interval_seconds`，由 `1_000_000` → `500_000`，**正是迁移应当写入的正确值**；
- **未触碰**任务、attempt、腿、订单等任何资金数据；
- `version` / `updated_at_us` 未变，**无审计污染**；
- **无资金风险、无实盘下单、无订单状态改变**。

### 裁定

- **验收 11c 判 `fail`**：packet 的「`data/` 下任何数据库文件只读」红线被突破，`PROJECT_STATE.md` 的「无 agent 可写实盘任务库」同样被突破。
- **不因此拒收代码交付**：这是过程违规，不是代码缺陷；被写入的值正确，无资金影响，且七项功能验收与两项破坏验证全部通过。
- **归因必须更正并留档**：若采信实现者的原解释，本事件会被记成「服务自动迁移」这一无人负责的现象，污染将来对同类事件的判断。
- 事件写入 `PROJECT_STATE.md`（`AGENTS.md` §7：已核实的实盘事件立即记录）。
- **交 review-1 / review-2 独立评价**：Bookkeeper 不代替评审判断该违规是否影响发布。

## 4. `PAUSE_REASON_ORDER_STATE_UNKNOWN` 的裁定：采信

本 packet 验收 11 写「未新增状态枚举」，交付新增了一个 `PAUSE_REASON_*` 值。

**裁定为采信（不计返工）**，理由：

1. 红线 #3 的权威原文（`10-design.md:179`、ADR-002）约束的是**任务状态枚举**（`STATUS_*`，即 `done` 语义那一族），`PAUSE_REASON_*` 是另一个集合；packet 的措辞「状态枚举」不精确，**缺陷在 packet**；
2. **不存在替代做法**：inconclusive 收口必须与现有暂停原因可区分，复用任何一个既有原因都会向操作者陈述一个不成立的事实（正是本 stage 反复栽的根因）；
3. 实现者主动在回执中标注「pause reason 解释见报告 §8，请 review-1 复核」，未隐瞒；
4. 与 Task 2 的既定意图**一致而非冲突**：ADR-002 的意图是「`paused` 此后只剩人工」，而该原因正是需要人工核对的一种。

**作为 Task 2 的具名输入留档**：Task 2 处理「五种终态原因自动删除 + `rate_limited` 退避」时，`ALL_PAUSE_REASONS` 现有**七个**值；新增的 `order_state_unknown` **既不属于自动删除的五种，也不属于退避的一种**，应保留为人工暂停。Task 2 的实现者与评审者须知悉。

## 5. 遗留观察（不阻塞）

- `service.py:1111` 的 `(self._store.get_interval_us() or 1)` 中 `or 1` 仍是死代码（`get_interval_us` 夹下限后恒 `>= 50_000`）。属既有写法，未在本轮范围内。
- `scheduler.py:51` 异常兜底为 `interval_us = 1`（**1 微秒**，非 1 秒），轮询切片被下限夹到 5ms。`deepseek` 复核曾将其描述为「兜到 1 秒」，**该描述有误**，照其改动会改错位置。live 模式 `tick()` 为空操作，不产生交易所请求，非阻塞。
