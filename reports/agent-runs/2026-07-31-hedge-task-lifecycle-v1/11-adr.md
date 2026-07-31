# 11-adr —— 架构决策记录

- task_id: `plan-hedge-task-lifecycle-v1`
- 关联：`10-design.md`。本文件为其中需要立 ADR 的决策点补 Context / Decision / Consequences。
- 模板来源：`agents/skills/software-architect.md` 的 ADR 模板。

> **修订说明（2026-07-31，`plan-revision-backend-merge-v1`）**：按 Human D14 重写 **ADR-001**——其前一版本判定「后端合并被事实堵死（须扩白名单/新增读路径 = 新增限频权重）」，该前提被 Bookkeeper 核查推翻（`build_server` 同时注入两服务、`get_snapshot()` live 零上游纯读，见 `04-backend-merge-decision.md` F-A/F-B 与 `10-design.md` §0 事实 17-20）。Context 如实记录此事（不粉饰、不改写历史），Decision 改为后端合并，Consequences 重估；顺带更正前一版的 `index.html:2106` 错误引用（`directionForPosition` 实际在 `:2198`）。**ADR-002、ADR-003 不受 D14/D15 影响，原样保留。** 本次修订不计 `rework_count`（仍 0）。

---

## ADR-001: 持仓合并在后端做（backend merge，按 D14）

### Status
Proposed（取代前一版「前端 join」裁定）

### Context

① 要一张合并持仓表：以交易所真实 UM 持仓为骨架，匹配置现货/杠杆账户资产与任务卡成交记录（`02-scope-decisions.md` D5/D6）。问题是在哪一层做这次合并。

**前一版的判断与它被推翻的过程（如实记录）**：前一版 ADR-001 判定「后端合并被事实堵死」——理由是 hedge 服务够不到 `private_account`，而 `private_client.py` 白名单冻结不可扩，故后端合并须扩白名单或新增读路径 = **新增限频权重**；据此选了前端 join。

**该前提的前半句成立、结论不成立**，由 Bookkeeper 在 `04-backend-merge-decision.md` 核查并经作者复核（`10-design.md` §0 事实 17-20）：

- **F-A**（`server.py:632-642` `build_server`）：`_Handler.service = service`（`SnapshotService`，产出 `private_account`）与 `_Handler.hedge_open_service = hedge_open_service` 注入**同一个 `_Handler` 类**；处理 `/api/hedge-open-positions` 的 `_hedge_open_positions`（`server.py:607-608`）**两服务皆在手**。
- **F-B**（`snapshot_service.py:237-257` `get_snapshot()`）：docstring 原文 `live: zero-upstream pure read of the published state`；live 分支 `state = self._published_state; return state.snapshot`——读的是后台已发布状态，**零新增交易所请求、零新增限频权重**。
- **F-C**：首次发布前 live 读抛 `SnapshotNotReady`（server 映射 503）；offline 是同步构建 + 60s 缓存。
- **F-D**（`snapshot.py:1097-1116`）：`private_account` 不可用时的降级形状已定义（`verified: false`、三数组空、金额 `null`、`error` 带原因）。

即：**后端合并可在服务器层完成，不扩任何白名单，也不产生任何新的交易所请求**。前一版所述代价不存在。

Human 据此于 `04-backend-merge-decision.md` 作 **D14（合并改为后端做）** 与 **D15（保留被删任务成本基——改 `aggregate_positions` 两条 `WHERE`）**。本 ADR 按已定决策设计后端做法，**不重新比较前后端优劣**（红线 #7）。

### Decision

在**后端服务器层做合并**：

- `_hedge_open_positions`（`server.py:607`）handler 内调 `self.service.get_snapshot()` 取 `private_account`，调 `hedge_open_service` 取 `aggregate_positions`，经一个**纯合并函数** `merge_positions(positions_rows, private_account)` 合并后返回。
- **就地改 `GET /api/hedge-open-positions`**（N1）：唯一消费者是前端、本任务同步重写渲染器；不新开端点、不留兼容层（红线 #6）。
- **降级契约**（N2）：`SnapshotNotReady` / `verified:false` 时持仓接口**不整体失败**，仍返回本地记账行 + `account:{verified:false,error}`，HTTP 200。
- **D15**（N3）：`aggregate_positions` 两条查询（`store.py:1950`/`:1960`）去 `WHERE != DELETED`，已删任务已成交腿计入，带 `includes_deleted_task` 标记。
- 合并函数为纯函数（可测，N5）；handler 仅装配，不注入 `SnapshotService` 到 `HedgeOpenTaskService`（保持两服务解耦）。

### Consequences

**变容易**：
- 合并逻辑在 Python（**可测**，六场景/符号对齐/降级/D15 均可确定性单测，N5），胜过 JS 侧「比 SQL 难测」。
- 口径唯一：接口与界面同一份合并数字，消除前端 join 的双源漂移。
- D15 正面回应 `PROJECT_STATE.md` 被标「Blocks that change」的 `[OPEN][MONEY-VISIBILITY]`：被删任务成本基不再消失。
- 零新增交易所请求/限频权重（F-B）。
- 可逆性高：回退 handler 即恢复旧 `get_positions`。

**变难**（前一版「放弃的难测」变为下列新代价）：
- 须处理账户未就绪/不可用的降级（N2）：错误处理会让持仓接口误 503 或混入脏数据。
- 改既有接口契约（N1）：§3.4 Position JSON 形状变更（虽唯一消费者同步改）。
- 与 `SnapshotService` 发布时序耦合：持仓接口现依赖已发布状态，后台滞后则带陈旧账户数据（靠 `checked_at`/`verified` 暴露）。
- `aggregate_positions` 语义变化（D15/N3）：已删任务腿开始计入，需 `includes_deleted_task` 标记防误读。
- 合并函数虽纯，但后端多一处装配逻辑与两源读点不一致的固有问题（见 `10-design.md` §7.1）。

> 前一版引用更正：`directionForPosition` 实际在 `index.html:2198`（非旧写的 `:2106`）。

---

## ADR-002: `rate_limited` 移出「自动删除集」，改为调度层退避；另五种终态暂停原因改自动删除

### Status
Proposed（**本方案唯一触碰 Human 已述决策之处，须计划评审与 Human 裁定**）

### Context

Human 已定「六种非人工暂停全改自动删除」（dispatch ② / intake）。但 `rate_limited`（429，`domain.py:134`）恰是六种之一，且 ③ 又把腿重查量放大 10 倍（10 任务 × 10 次/秒 = 100 次/秒）。若字面执行「六种全删」+ ③：一次 429 即删卡，批量删卡成常态，毁掉已部分成交任务的资金可见性（① 的全部意义）——把一个**瞬态背压信号**误判为**终态失败**。

两处写 `rate_limited → paused` 的 worker 站点：`service.py:1152-1160`（query 期 429）、`service.py:1176-1180`（dispatch 期 429）。`rate_limited` 对经 `skip_counters` 结算（`store.py:907`），本就不进 R2-F1 收口。

「六种全改」的**深层意图**是「非人工暂停不得变成需手动恢复的僵尸态；`paused` 此后只剩人工」。

### Decision

- **五种终态原因**（`consecutive_submission_failure` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full`）→ 自动写 `DELETED`（复用既有终态，红线 #3），保留 `pause_reason`+`pause_reason_zh`（51169 冻结文案逐字留显，红线 #1），复用 `post_delete` 不打断 drain 语义（`service.py:645`）。
- **`rate_limited` 移出删除/暂停集**：两处 worker 429 站点不再调 `_pause_task_local`/`pause_task`，改为**指数退避 + 抖动重试**（用既有 `stop_event.wait`，不新增字段/枚举）。不写 `paused`、不写 `deleted`。
- **不做**投机性全局 token-bucket 限流器（红线 #6）；429 退避即全局背压阀门；仅当实测仍频发才作后续项。

### Consequences

**变容易**：
- `paused` 真正只剩人工（红线/意图达成）；非人工原因不再留僵尸态。
- ③ 可安全做：429 不再删卡，限频解除后自恢复，资金可见性不毁。
- 退避用既有机制（`stop_event.wait`），不增状态机复杂度。

**变难 / 放弃**：
- 字面「六种」清单的整齐性——细化为「五种删 + 一种退避」。这是与**字面**偏离、与**意图**对齐的选择。
- worker 多了退避路径，须防忙轮询/死循环（用 §7 验证 2 兜）。
- **回退方案**：若 Human 坚持字面「六种全删」，则**不做 ③**（保留 1s），因 ③ + 字面六删会让批量删卡常态化。

**为何不与「六种全改」冲突**：`rate_limited` 与其余五种本质不同——五种是**不重新参参即无法成功**的终态失败（删之合理），`rate_limited` 是**瞬态**背压（退避即解，删之毁资金可见性）。故把 `rate_limited` 的「改」理解为「不再作为任务级失败暂停，升格为调度层退避」，比「删」更彻底地达成意图。

---

## ADR-003: 重查间隔不拆分，全局下调到 100ms；先修整除显示；加下限 + 抖动

### Status
Proposed（偏离 `PROJECT_STATE.md` follow-up「拆分两间隔」的旧建议，以新证据为据）

### Context

③ 要把订单重查间隔从 1s 降到 ~100ms，让成交数据更早落袋。`PROJECT_STATE.md` follow-up 建议「拆分 dispatch 间隔与 re-query 间隔、加下限、修整除显示、考虑 429 退避」。

新证据（`10-design.md` 事实 8）：**LIVE 模式 `tick()` 是安全空操作**（`service.py:1500-1517`，注释明写 "A periodic tick must NEVER scan all tasks"）。故 `interval_us` 在 live **只**节流 worker 的腿重查（`service.py:1079`），**不**驱动下单节奏；worker 仅在有在途腿时节流，一对腿终态即进下一对（A-9）。→ 下调 `interval_us` **只**缩短腿重查延迟，**不**抬高下单频率。

「下单调度间隔」在 live 无对应物（`tick()` 空操作）；拆分只对 DRY-RUN 节奏（`tick():1519`）有意义，而 DRY-RUN 是 record-only、不下单，其 10x 加速无害。故拆分解决的并非真实问题（红线 #6 / 架构师第 1 条）。

整除显示 bug（`service.py:178` `int(interval_us) // 1_000_000`）会让亚秒值显示成 `0`，须先修。

### Decision

1. **前置**：修 `service.py:178` 整除为亚秒渲染（ms 或小数秒）。
2. **不拆分**：把唯一共享 `interval_us` 默认值 1s（`1_000_000`）下调到 100ms（`100_000`），不新增「下单调度间隔」字段。
3. **加下限**：读取处（`get_interval_us`）夹下限（建议 50ms），防误配忙轮询。
4. **加抖动**：worker 节流（`service.py:1079`）`ev.wait` 加随机抖动，避免 10 worker 对齐成脉冲。
5. 不新增运行时配置入口（改的是种子默认值 + 读处下限；configurability 非需求，红线 #6）。

### Consequences

**变容易**：
- 改动面小：一个默认值 + 一个显示修复 + 一个下限 + 一处抖动。
- 下单频率不受影响（A-9 已保证），验收 oracle 清晰（重查延迟下降、下单次数不变）。
- 退避（ADR-002）与此天然协同：100ms 重查 + 429 退避 = 快速落袋且不删卡。

**变难 / 放弃**：
- DRY-RUN `tick()` 跑快 10 倍（无害，record-only）。
- 偏离 `PROJECT_STATE.md`「拆分」旧建议——以事实 8 为据主动推翻，须在评审中说明。
- 10 任务并发在途腿时聚合查询仍可达 ~100 req/s（币安请求权重限约 1200/min ≈ 20/s）——靠抖动 + 退避自调；若实测不足，全局限流器为证据触发的后续项（非目标 §3 #7）。
