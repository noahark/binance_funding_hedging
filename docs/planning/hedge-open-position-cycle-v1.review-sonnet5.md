# 计划评审 — 持仓周期三功能（v1 设计 + 功能①②开发文稿 + ROADMAP 排期）

被审对象：
- `docs/planning/hedge-open-position-cycle-v1.md`（设计权威）
- `docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（功能①：周期表）
- `docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能②：费率/利息统计）
- `docs/planning/ROADMAP.md`「Planned: 持仓周期三功能」节

评审角色：独立计划评审（`AGENTS.md` §8「计划评审」），只读；本次由 sonnet5 本人执行（此前误将本轮评审对象转述为「待 sonnet5 核对」，实际本会话即 sonnet5，评审直接在本会话完成，不再转手）。
评审基线：`main @ 08127aa`（三份文稿为工作树内未跟踪新增文件 / `ROADMAP.md` 为未暂存修改）。
本评审未使用任何凭证、未发任何单、未改动 Start gate，只读了源码与 `data/hedge-open-tasks.sqlite3` 的行计数。

**评审结论：REWORK（返工）**

本轮不授权实现。verdict 返回 Planner，不触碰 `rework_count`（§8 计划评审豁免）。

---

## 0. 先说计划做对的部分（这些不必重做）

1. **全部代码行引用经逐条核实成立**（`prepare_attempt:734`、`aggregate_positions:2022`、`_migrate:370`、`_hedge_open_positions:737`、`query_income_rows:344`、`query_interest_rows:324`、`_sum_amounts:269`、`coverage_exists:347`、`merge_positions:1729`、`_merge_base_asset:1559/1676`、`PreflightSnapshot:819`、`self._lock = threading.RLock():343`、`D15` 标记 `store.py:2175`）。文档基线扎实，没有臆造引用。
2. **stage2 §3.3/§3.4 的锁语义已修正到位。** `self._lock` 确系可重入 `RLock`，同线程重入不会死锁；真实风险是 sqlite3 `Connection.__exit__` 在内层 `with self._conn:` 退出时提前 commit，破坏「cycle 插入与 attempt 插入同一事务」的原子性。文稿现已改为双版本方法（`_get_active_cycle_locked`/`_create_cycle_locked` 内部无锁版 + 对外加锁版），并与代码内既有先例 `_apply_task_counters`（`store.py:906`，docstring 明确「MUST run inside the caller's transaction」）对齐，命名一致、无遗留错误引用。
3. **迁移方式经核实安全。** `_migrate`（`:370`）本身不持有 `with self._conn:`，由 `__init__`（`:351`）的外层事务托管，`attempt_additions`/`leg_additions` 的 `PRAGMA table_info` 探测 + `ALTER TABLE ADD COLUMN` 模式与 stage2 §3.2 的追加写法完全兼容；`hedge_open_cycle` 建表放进 `_SCHEMA`（随 `executescript` 每次 `__init__` 自动幂等建表）与 `attempt.cycle_id` 走 `_migrate` 追加列，两条路径不冲突、不双写。
4. **`hedge_open_fill`「空壳」的现状判断属实**：`insert_fill()`（`store.py:1682`）在生产分发路径（`service.py`/`server.py`/`live_hedge_executor.py`）零调用点，`data/hedge-open-tasks.sqlite3` 实测 `hedge_open_fill` 行数为 0（见 §3 P2-1，这是「现状为真」但「非结构性保证」的区别，不影响本轮结论）。
5. **`query_income_rows`/`query_interest_rows`（`ledger_flow/store.py:324/344`）确实支持 `[start_ms, end_ms]` + `limit=None` 全量返回**，与 stage3 §3.1 的复用计划一致；`_merge_base_asset`（`domain.py:1559`）「1000x 资产不自动对齐」的行为描述与代码注释逐字一致，stage3 §3.2 引用它做 base_asset 推导是安全的。
6. **`prepare_attempt` 的 cycle 分配插入点选得对**：eligibility 提前返回（task 状态、`scheduled_attempt_count`、in-flight pair）全部发生在 `:790` 之前；cycle 分配到 attempt INSERT 之间没有其他 early-return 分支，配合单一 `with self._lock, self._conn:` 事务，「失败回滚不留孤儿 cycle」这条要求在当前插入点下是可达成的。
7. **排期问题（③a 是否应提前到②之前）判断正确**：`hedge_open_cycle_close_log.funding_fee`/`borrow_interest` 按设计 v1 §3.2/§4.2 要求「关闭时现算写入」，这一写入行为本身依赖②built 的窗口求和能力，表结构无依赖但写入行为有依赖；维持 ①→②→③a→③b 顺序是唯一不产生重复实现或语义妥协的排法，ROADMAP 现状不需要调整。

---

## 1. P0 — 阻塞项

### P0-1 `merge_positions` 未改动这件事本身就是缺陷：一旦同一 `(coin, direction)` 出现多个周期桶，正确的周期会被静默吞掉，而不是设计 v1 §5.4/§8 用例 2 承诺的「新行显示当前仓、旧行标已平仓」

设计 v1 §5.4 与 stage2 §3.5 核对点都断言「`merge_positions` 不改——周期拆分发生在桶层，merge 按 `(symbol, position_side)` 匹配一个活跃周期桶，历史周期桶以 `no_um` 附加行出现」。我通读了 `merge_positions` 全文（`domain.py:1729-1823`），这个断言不成立：

```python
# domain.py:1780-1782
bucket_by_key = {}
for p in positions or []:
    bucket_by_key.setdefault((p.get("coin"), p.get("direction")), p)
```

`bucket_by_key` 的键仍是旧的 `(coin, direction)` 二元组，且用 `setdefault`——**同一 `(coin, direction)` 只会保留 `positions` 列表里第一个出现的桶**，其余全部被丢弃，且这一步发生在 UM 骨架匹配（step 1）之前。`positions` 来自 `aggregate_positions` 的输出，其排序（`store.py:2184`，stage2 计划追加 `cycle_opened_at_us` 作为同键 tiebreaker）会把同一 `(coin, direction)` 下**最早的周期排在前面**——`Python sort` 是稳定排序，即使不追加 tiebreaker，`buckets.items()` 的插入序本就是按 `leg_rows`（`ORDER BY a.created_at_us ASC`）时间序推进的，同一键下第一个建桶的必然是时间最早的周期。

于是场景 B（设计 v1 §8 用例 2，全平再开）的实际运行结果是：

1. `bucket_by_key[(coin, direction)]` 拿到的是**最早（已平仓）的周期桶**，不是当前活跃周期；
2. step 1 遍历 UM 骨架时，交易所真实持仓（属于新周期）会匹配到这个**错误的旧桶**，于是展示行会挂着**旧周期的成本基/起始时间**，却顶着一个当前真实存在的 UM 仓位——这正是整套设计要防止的「过去仓位与当前仓位混算」，而且是最隐蔽的一种：数字看起来合理，只是错的；
3. step 2（`domain.py:1811-1820`）用 `key = (coin, direction)` 二元组判断「是否已被匹配」并 `continue` 跳过——**同一 `(coin, direction)` 下的所有其他周期桶（包括真正当前活跃、成本基正确的那个）都会被这一行连带跳过**，不会作为 `no_um` 附加行出现，直接从输出里消失。

净结果：全平再开后，前端看到的是**一行**，挂着已平仓周期的均价和起始时间，而真正当前仓位的正确数据完全不可见——不是「合并展示」的降级，是数据丢失加错误归因同时发生。这与设计 v1 §1.1 目标 1「平仓再开仓后不与历史混算」直接矛盾，也不满足 §8 用例 2 的验收断言。

这个 bug 在**改动前完全不可观测**，因为今天 `(coin, direction)` 本就是唯一桶键，`positions` 列表里从不会有重复键——它是①上线后才会被激活的潜伏缺陷，且恰好命中①存在的核心场景（开→平→再开），不是边缘情况。

**要求：** `merge_positions` 必须改，不能维持「不改」的断言。具体到实现，需要：
- UM 骨架匹配时，对每个 `(symbol, direction)`，只应该匹配**活跃周期**（`cycle_closed_at is None`）的桶，而不是「列表里第一个」；
- `matched_buckets`（或等价的已消费标记）需要按**周期粒度**（如 `cycle_id` 或桶身份）记账，而不是 `(coin, direction)` 二元组，这样 step 2 才能把同键下未被匹配的**其它**周期桶正确地当作独立 `no_um` 行输出，而不是整批跳过。
- 补一条验收用例：同一 `(coin, direction)` 同时存在一个已平仓周期和一个活跃周期（即设计 v1 §8 用例 2 的「快照已确认新仓」这一时刻）时，输出必须是两行，UM 骨架行挂**活跃周期**的均价/起始时间，已平仓周期独立成行。

---

## 2. P1 — 需在返工版本中解决

### P1-1 归零观察没有「新建周期宽限期」，快照滞后会把刚创建、仓位还没走完全流程的周期误判成「已平仓」，把同任务的加仓拆成多个周期

设计 v1 §4.2 与 stage2 §3.6 的归零观察逻辑：本地活跃周期若在最新私有账户快照的 `um_positions` 里找不到对应 `(symbol, direction)`，立即 `close_cycle`。

问题在时序：`prepare_attempt`（`store.py:734`）创建 cycle 的时刻，是**发单前**（executor 在 `prepare_attempt` 返回之后才真正把订单发给交易所——见其 docstring「The executor is invoked AFTER this returns」）。而私有账户快照按设计文档自述是约 60s 轮询一次的缓存发布物（§4.2「快照轮询粒度（约 60s）」）。这意味着：一个周期从创建到它对应的仓位真正出现在交易所快照里，天然存在一段延迟窗口（发单延迟 + 成交延迟 + 最多约 60s 快照刷新延迟）。如果这段窗口内前端轮询触发了一次 `GET /api/hedge-open-positions`，而当时的快照仍是「还没看到新仓位」的旧快照，归零观察会把这个**刚刚创建、仓位正在路上**的周期直接判定为「已平仓」（`um_flat`）。

这不是设计文档已承认的「平仓后立即再开」延迟风险（那是对**真实平仓事件**的检测滞后，代价是费率窗口多算几分钟）；这是一个**从未平仓过的、正在被创建的周期被误判为平仓**，方向完全不同，后果也不同：

- 违反设计 v1 §1.1 目标 3 与 §8 用例 5（「同任务加仓 → 同 cycle 同行，加权均价」）——因为 `prepare_attempt` 的 in-flight 保证只序列化同一任务内部相邻两次 attempt 的**下单**节奏（§4.5/`store.py:759` 附近的 in_flight 检查），并不保证私有账户快照的刷新节奏能跟上；同一任务连续两次 attempt 之间，若第一次的仓位还没被快照看见，第二次 `prepare_attempt` 会因为「无活跃周期」而新建一个 cycle，人为把本该合并的一次加仓拆成两个周期；
- 污染 `opened_at_us`（目标 2「可靠起始时间」）——真正的首次开仓时间被浪费在一个秒级就被关闭的幽灵周期上，展示给用户的起始时间是**较晚**的那个;
- 一旦③a 落地，每次误判都会连带写一条 `hedge_open_cycle_close_log`（§4.2「关闭时同步写入结算日志」），产生垃圾结算记录。
- 该风险与并发任务数无关但因并发任务而必然触发：只要账户里**任何其它币种**已有持仓，`um_positions` 非空这一前置条件（stage2 §3.6 步骤 1）就会满足，触发对新建周期的逐条核对——不需要账户从零开始才会命中。

**要求：** 归零观察需要一个「新建宽限期」保护，例如：只有当所用快照的 `checked_at`（`merge_positions` 已在读，`domain.py` 的 `account_meta["checked_at"]`）晚于该周期的 `opened_at_us` 一定余量（例如快照刷新周期的 2～3 倍，覆盖发单+成交+快照刷新的链路延迟）时，才允许对该周期执行归零关闭；余量内一律「宁可延续，不误拆」。这与设计 v1 §4.2 已经承认的「宁可延续，不误拆」原则同向，只是把它同样应用到「新建」而不仅是「快照不可用」这一种情形。

### P1-2 stats_incomplete 覆盖率检查引用的字段名不存在，且提议的「只比较窗口端点」比代码里已有的 gap-aware 判定更粗糙，可能把真正不完整的窗口显示成完整

stage3 §3.3 写「查询前检查 ledger 覆盖率（`ledger_flow_meta` 的 `interest_coverage_start/end`、`income_coverage_start/end`）」。我核实了 `ledger_flow/store.py` 的 `get_coverage()`（`:361` 附近）与 `service.py` 的 `_build_coverage`（`:373`）：

- 实际字段名是 `interest_start_ms`/`interest_end_ms`/`income_start_ms`/`income_end_ms`（`get_coverage()` 返回），不存在 `interest_coverage_start/end` 这个命名——纯粹的引用错误，实现者对着这个名字去找字段会直接扑空。
- 更重要的是，`_build_coverage`（`service.py:373-395`）已经实现了比「起止时间戳」更精确的完整性判定：它会取 `store_cov["gaps"]` 中与查询窗口相交的已知缺口列表，`complete = cov_start is not None and window_start >= cov_start and len(gaps) == 0`——也就是说，即使窗口整体落在 `[cov_start, cov_end]` 之内，只要窗口中间存在一段已记录的缺口（例如 scheduler 曾经中断过一段时间），`complete` 仍然是 `False`。stage3 §3.3 提议的「窗口起点早于 coverage_start 或终点晚于 coverage_end → stats_incomplete」只比较端点，**不检查窗口内部的 gaps**，会把「端点覆盖但中间有洞」的窗口误判为完整，恰好违反了这份文档自己在同一节强调的硬约束——「绝不把覆盖率不足的窗口当成真值」。

**要求：** §3.3 改为复用（或对 `_build_coverage` 做一个按窗口调用的公开包装）已有的 gap-aware 完整性判定，而不是重新发明一个只看端点的更粗糙版本；同时把字段名引用改成真实存在的 `interest_start_ms`/`interest_end_ms`/`income_start_ms`/`income_end_ms`（经 `get_coverage()`）或 `_build_coverage` 返回结构里的对应字段。

---

## 3. P2 — 应处理，不单独阻塞

- **P2-1** `hedge_open_fill`「空壳，0 行，不参与周期拆分」目前为真（实测 0 行，`insert_fill()` 在生产路径零调用），但这是**当前数据事实**而不是代码强制的不变量——`insert_fill()` 仍是一个可调用的活方法。若未来任何代码路径重新调用它（哪怕是测试脚手架误用），SQL-A 会开始产出无 `cycle_id` 的行，落入 stage2 §3.5「桶键含 None，仍能聚合（防御性，不报错）」的兜底分支，但那些行永远不会被归入任何周期、也不会被 P0-1 修好后的 merge 逻辑正确处理（无 cycle_id 的桶算不算「活跃」是未定义的）。建议在 §3.5 补一句：SQL-A 分支若观察到非零行数，应视为异常并记录告警，而不是静默吃掉。不阻塞本轮实现，留作实现时的一条防御性断言即可。
- **P2-2** stage2 §3.2 核对点仍写着「`hedge_open_cycle` 表创建也在此（或 `_SCHEMA` 的 `CREATE TABLE IF NOT EXISTS` 在 `__init__` 时自动执行，二者取一，不双写）」——这句话读起来像一个待决问题，但文档自己在 §3.1 已经把建表放进了 `_SCHEMA`，答案已经定了。建议把这句改成陈述句（「建表已放在 §3.1 的 `_SCHEMA`，`_migrate` 只追加 `ALTER TABLE`，不重复建表」），避免实现者读到「二者取一」误以为还需要自己选一次。纯措辞问题，不影响正确性。

---

## 4. 返工要求（可执行）

1. 重写 `merge_positions` 的桶匹配逻辑：UM 骨架匹配只认活跃周期桶，已匹配标记按周期粒度记账，未匹配的非活跃周期桶作为独立 `no_um` 行输出；stage2 §3.5 与设计 v1 §5.4 的「merge 层不改」表述一并删除。补一条验收用例覆盖「同 `(coin, direction)` 同时存在一个已平仓周期和一个活跃周期」。—— P0-1
2. 归零观察加一个基于快照 `checked_at` 相对周期 `opened_at_us` 的宽限期判定，宽限期内一律不关闭；设计 v1 §4.2 与 stage2 §3.6 同步更新这条边界条件。—— P1-1
3. stage3 §3.3 改用已有的 gap-aware 覆盖率判定（`_build_coverage`/`get_coverage()` 的真实字段名与 gaps 列表），删除不存在的 `interest_coverage_start/end` 字段引用。—— P1-2
4. 处理 P2-1（SQL-A 非零行的防御性告警）、P2-2（措辞去歧义），不改变设计主线。

修订后重新提交一次独立计划评审。任何评审都不授权实盘开闸或使用真实凭证。
