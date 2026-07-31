# 10：Bookkeeper 核验记录（opus5，2026-07-31）

对 `claude_glm` 的实现交付（`09-delivery.md`）做独立核验。结论：**通过，予以封存**，
`current_task.state` 由 `reported` 推进为 `verified`。

## 独立复跑的证据（不是转述交付回执）

| 检查 | 命令 | Bookkeeper 实测结果 |
|---|---|---|
| 后端回归 | `python3 -m pytest backend/tests -q` | `1104 passed in 57.84s` —— 与交付一致 |
| 前端自检 | `node frontend/self-check.js` | `全部自检通过`（含「零新任务定时器」断言） |
| fake 残留 | `grep -rn "renderHedgeTaskCardFake\|HEDGE_FAKE_TASK_ID\|showFakePreview" frontend/` | `0` 处 |
| `store.py` 未改 | `git diff --name-only \| grep store.py` | 无输出 —— 确认未触碰 |
| 改动范围 | `git diff --stat` | 仅 5 个 Allowed Files（+ 记账文件），全部在边界内 |

## 验收逐条核验（11 项，全部 pass）

| # | 项 | 核验方式与结论 |
|---|---|---|
| 1 | 四状态冻结映射 | 读 `hedgeAttemptStatusCell`（`index.html:4253`）：`null` 走**显式分支**（符合 O-2），其余查表；self-check 断言「不得出现失效的 `warning` class 或 fake 的『已成交』文案」。pass |
| 2 | 钱原样透传 | 读 `hedgeLogLegCell`（`:4266`）：仅 `hedgeText`，未用 `formatHedgeDecimal`/`hedgeNum`。self-check 用带尾零夹具断言逐字透传。pass（描述歧义见下 O-A） |
| 3 | 未受理腿门控 | 读 `:4268` 按 `order_id` 判空；self-check 断言单腿行 perp 三格 muted 数**恰为 3**，断言范围限定在该行（未做过宽的「整页无 0」）。pass |
| 4 | 错误回退链 | 读 `hedgeLogErrorCell`（`:4287`）：`error_reason_zh` → `error_category`/`error_code` 原样 → 失败/单腿行「原因未记录」→ 其余 `—`。未编造中文业务句。pass |
| 5 | `task_id` 全量取数 | 读新增 `test_get_logs_task_id_returns_all_attempts_unpaged`：真构造 **51** 个 attempt，断言全部返回、序号 `1..51`、`entries == []`、两个游标均 `None`，并对比全局模式只返回 50。pass |
| 6 | 进展 = `attempt_seq/target_n` | 读 `hedgeTaskLogRowsHtml`（`:4322`）用 `a.attempt_seq`；未出现 `scheduled_attempt_count`。pass |
| 7 | 展开保持 + 零定时器 | `state.hedgeLogExpanded` 沿用既有 `Set`；self-check「零新任务定时器」断言通过；toggle 已绑真卡（fake 分支已删）。pass |
| 8 | `#task-id` | 回归项，`index.html:4216` 既有实现仍在。pass |
| 9 | fake 清干净 | grep 三个符号均 0 处。pass |
| 10 | 后端只动读路径 | 逐行读 `server.py`/`service.py` 的 diff：`server.py` 仅多解析一个 query 参数并透传；`service.py` 仅加 3 个既有列的投影 + `task_id` 早返回分支（只调 `list_attempts_for_task` / `list_legs_for_attempt` / `attempt_to_doc` 三个既有只读方法）。**未触碰**状态机、调度、结算、计数器、暂停/删除、worker。pass |
| 11 | 回归零转红 | 见上表，1104 passed 独立复现，无既有用例转红。pass |

排序另核：`hedgeTaskLogRowsHtml`（`:4316-4320`）用 `slice().sort((a,b) => sb - sa)` 降序，
不改原数组，`attempt_seq` 为 `null` 时以 `-Infinity` 排末尾。倒序要求满足。

## Bookkeeper 观察项（不阻塞封存，移交评审）

- **O-A 交付描述歧义（钱的展示）**：`09-delivery.md` 的 AC2 写「均价原样透传含尾零
  （`120.70000000` / `120.70300000`）」。该测试本身**有效且正确**——它证明前端不做二次
  加工（若用 `formatHedgeDecimal` 会变成 `120.7`）。但那两个值是 self-check 夹具的手写
  默认值；**真实数据不可能带尾零**，因为后端 `fmt_decimal`（`domain.py:1250-1252`）在上线
  前已 `rstrip("0")`。照字面读会以为界面上能看到 `120.70000000`，实际只会看到 `120.7`。
  属措辞不精确，非功能缺陷。已向 Human 说明。
- **O-B N+1 查询**：`get_logs` 的 `task_id` 分支对每个 attempt 各发一次
  `list_legs_for_attempt`，即 1 + N 次查询。`target_n` 只校验 `>= 1`、**无上限**，
  故极端任务会放大。本地 SQLite 影响有限，未构成阻塞；若日后 attempt 数量级上升，
  应改为一次 join。
- **O-C `task_id` 模式下 `logs` / `entries` 为空**：交付已在「可推翻项」中声明。当前
  只有内嵌表使用该参数，其它调用不带 `task_id`、契约不变，故无实际影响。
- **O-D `target_n` 取不到时的进展列**：`targetN` 取自 `findHedgeTask(taskId)`，任务不在
  当前列表时回退空串，进展列会显示 `4/`。展开日志的前提是卡片可见，实际难触发。
- **O-E 均价列 `—` 的三种来源无法区分**：「该腿未受理」「受理了但成交额未知」「无数据」
  在均价列都渲染为 `—`。两者对资金判断含义不同（前者钱没动，后者钱动了但价格未知），
  好在**数量列可区分**（前者 `—`，后者有值）。是否改为更明确的提示由 Human 定。
  已记为 review-2 的关注点。

## 已记入跨 stage follow-up（Human 2026-07-31 决定）

**均价不应本地计算。** 交易所订单信息里有权威 `avgPrice`，`live_hedge_executor.py:116`
已经解析，但 `hedge_open_leg` 表没有 `avg_price` 列（`store.py:85-99`），该值被丢弃，
展示时改用 `cumulative_quote_amt / cumulative_base_qty` 本地现算（`service.py:224`）。

Human 判断：应改用交易所返回值，更精确。该改动需要加表列 + 动写路径，**超出本 stage
「只动读路径」的边界**，故记为 follow-up 而非本轮修复。已写入 `PROJECT_STATE.md`
（`[OPEN][MONEY-ACCURACY]`）。

当前的实际后果：**合约均价经常为空**——币安 2026-07-14 从 UM 下单返回里移除了
quote/avgPrice，成交额靠事后 GET 补，补不到就是 `NULL`，均价随之为 `—`（数量仍有值）。

## SHA 封存

- `base_sha`：`42de1aff364e7c979d2fbb5dc56f1dec65287cc7`（未变）
- `delivery_sha`：见 `status.json`，指向仅含实现交付的提交（本记账文件与
  `PROJECT_STATE.md` 更新在其后的记账提交里，按 `AGENTS.md` §8「评审范围口径」属评审者
  的上下文而非受审交付）。
- 评审区间：`base_sha..delivery_sha`。

## 下一步

按 §8 HIGH_RISK 路由：review-1（`grok` / xai，`code-reviewer` 技能）→ review-2
（`codex` / openai，`reality-checker` 技能）。`rework_count` 仍为 **0**。
