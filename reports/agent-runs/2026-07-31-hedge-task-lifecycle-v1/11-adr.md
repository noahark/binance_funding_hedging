# 11-adr —— 架构决策记录

- task_id: `plan-hedge-task-lifecycle-v1`
- 关联：`10-design.md`。本文件为其中需要立 ADR 的决策点补 Context / Decision / Consequences。
- 模板来源：`agents/skills/software-architect.md` 的 ADR 模板。

---

## ADR-001: 持仓合并在前端做（frontend join），不改后端、不扩白名单

### Status
Proposed

### Context

① 要一张合并持仓表：以交易所真实 UM 持仓为骨架，匹配置现货/杠杆账户资产与任务卡成交记录（`02-scope-decisions.md` D5/D6）。问题是在哪一层做这次合并。两个候选：

- **后端合并**：在 hedge 服务里把 `private_account` 的 um 余额与 `aggregate_positions` 合并后经 `GET /api/hedge-open-positions` 返回。
- **前端合并**：在 `index.html` 里把已在手的 `state.snapshot.private_account` 与 `state.hedgePositions` 两片 state join。

后端合并被事实堵死（`10-design.md` 事实 15）：

- hedge 服务够不到 `private_account`——`um_positions` / `balances_unified` / `balances_spot` 是经 `private_client.py` 的 snapshot 路径产出，而 `hedge_preflight_provider.py:14-19` 注释明写 "`private_client.py`'s frozen whitelist cannot be extended and lacks them"，白名单**冻结不可扩**。
- hedge 服务自己的 `HedgeOpenLiveClient` allowlist 只含三个 preflight 端点，**不含** snapshot 端点。给后端合并喂 `private_account`，要么扩冻结白名单（禁止），要么给 `HedgeOpenLiveClient` 新增 snapshot 端点 + 新读路径 = 新增限频权重（snapshot 路径已为「UM 持仓」面板抓过一次，再抓是重复抓取）。

而前端两源已在手（事实 16），合并是纯派生，**零新增交易所请求、零新增限频权重**。

更关键的是 ① 的本目的——**资金可见性**：`aggregate_positions` 两条查询都带 `WHERE t.status != deleted`（`store.py:1950`/`:1960`），任务一删其已成交腿就从该接口消失，而账户敞口仍在。② 落地后这会变成常态。前端合并以 `um_positions`（真实持仓，**独立于任务状态**）为骨架，于是「任务被删但敞口仍在」由构造解决——后端 `WHERE` 因此本轮不必改。

fake UI `63f5007` 已用前端 join 证伪了形状并经 Human 认可，是展示形状基准。

### Decision

在**前端 `index.html` 做合并**，消费 `state.snapshot.private_account` 与 `state.hedgePositions`。

- **不改**后端 `aggregate_positions`（其 `WHERE != DELETED` 保留，见 `10-design.md` 非目标 #7）。
- **不扩** `private_client.py` 白名单，**不给** `HedgeOpenLiveClient` 加 snapshot 端点。
- 合并表取代既有「UM 持仓」面板与 `renderHedgePositionsSection`（D6「合并成一张表，现有 UM 持仓表并入」）。
- 合并表消费后端同一份 `pair_outcome`/`leg_exposure` 判定，不自行重推单腿敞口（避免双源漂移，fake-ui §9 #6）。

### Consequences

**变容易**：
- 无后端 reach 问题、无白名单扩展、无新交易所请求/限频权重。
- 与经 Human 认可的 fake 形状一致（acceptance #8）。
- 资金可见性（删卡不丢敞口）由构造保证，不依赖后端改 `WHERE`。
- 可逆性高：纯前端渲染改动，回退即恢复两张旧表。

**变难**：
- 合并逻辑在 JS（比 SQL 难测）。缓解：`self-check.js` 断言 + 复用既有 `directionForPosition`（按大写 `LONG`/`SHORT` 判，`index.html:2106`）与统一的 base-asset 归一函数（三处共用）。
- 两张渲染器（合并表 + 任务卡）各自派生视图，口径漂移风险。缓解：单腿敞口等判定**只读后端 verdict**，前端不重推。
- 既有「UM 持仓」面板与 `renderHedgePositionsSection` 被取代（删除/替换）——属本任务范围内（D6），非副作用。

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
- 10 任务并发在途腿时聚合查询仍可达 ~100 req/s（币安请求权重限约 1200/min ≈ 20/s）——靠抖动 + 退避自调；若实测不足，全局限流器为证据触发的后续项（非目标 #8）。
