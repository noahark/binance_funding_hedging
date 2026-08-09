# 对冲开单持仓周期（position cycle）设计草案 v1

状态：**草案，未评审，不授权实现、不授权迁移、不授权任何实盘操作。**
性质：为「平仓再开仓成本基隔离」与「起始持仓时间」提供数据模型与归属规则的设计讨论稿。
基线：以当前工作树为准（未固定 `base_sha`；正式评审前需补记）。

---

## 1. 目标与边界

### 1.1 目标

1. 让持仓行均价/数量表达「当前这一仓」的成本基，平仓再开仓后不与历史混算。
2. 给定持仓，能确定可靠的时间起点（起始持仓时间），用于按窗口查询本地流水（资金费/借币利息）。
3. 区分三类情形：同币种多段持仓（开→全平→再开）、同任务加仓、多任务叠仓同一仓。

### 1.2 语义口径（Human 已确认的方向，见讨论）

| 场景 | 周期判定 | 起始持仓时间 |
|---|---|---|
| A：开仓 → 部分平仓 → 继续加仓 | 同一周期延续（仓位从未完全归零） | 该周期第一次开仓的派发时间 |
| B：开仓 → 完全平仓 → 再开仓 | 新周期（仓位归零过） | 再开仓的派发时间 |

时间精度：**派发时间（`dispatched_at_us`）即可**，粗颗粒，用于费率/利息的粗算窗口，不必精确到成交时刻。

**周期收益口径（Human 已拍板）**：只计算「资金费 + 借币利息」窗口合计；**不含**未实现盈亏、**不含**平仓盈亏（平仓盈亏留到平仓事件接入后，通过周期结算日志补充）。

### 1.3 不在本轮

- 不做平仓功能本身；平仓仍由交易所手工完成（或功能三开发后由系统平仓任务完成）。**本阶段不做自动归零观察、不做平仓关闭的触发逻辑**——只实现 `close_cycle` 方法本身，触发留给功能三（人工核实关闭作为可选纠偏）。
- 不做平仓成交明细记账（平仓成交均价/数量拿不到）；周期结算日志的 `close_avg_price` 字段预留、留空，等平仓事件接入后填充。
- 不改现货「周期」语义：现货无交易所持仓概念，现货腿跟随同 attempt 的合约周期，不单独定义归零。
- 不改变 Start gate、订单、查单、借币、划转、风险限制、凭证路径。
- 不在本轮改聚合口径之外引入新的资金字段含义（`accrued_funding`/`borrow_interest`/`net_pnl` 仍为占位或按 §7 逐步接入）。

---

## 2. 现状与设计约束（代码事实）

1. 聚合唯一揉合点：`HedgeOpenStore.aggregate_positions()`（`backend/hedge_open_tasks/store.py:2022-2185`），桶键 `(coin, direction)`（`store.py:2051`），双源全历史加权（`hedge_open_fill` 空壳 + `hedge_open_leg` 现行源），已删任务成交仍计入（D15）。
2. 持仓骨架在快照侧：`private_account.um_positions` 带 `entry_price`/`position_amt`（`backend/domain/snapshot.py:1312-1327`）；合并层 `merge_positions`（`backend/hedge_open_tasks/domain.py:1729`）以 UM 真实仓位为骨架。
3. 派发时间：`hedge_open_leg.dispatched_at_us` 首次派发时写入（`store.py:1185/1251`，`COALESCE`），与 `hedge_open_attempt.created_at_us`（发单前事务写入，`store.py:791-807`）微秒级接近。**全库无交易所 `transactTime`**。
4. 发单时拿不到「交易所当前有无仓位」：`PreflightSnapshot`（`domain.py:819-857`）只有余额/过滤器/position_mode，无 `um_positions`；快照与 HedgeOpen 服务刻意解耦（`server.py:738` 注释）。→ 周期边界不能靠「发单瞬间查仓」判断；周期关闭由功能三平仓任务触发（§4.2）。
5. 迁移机制已存在：`_migrate` 用 `PRAGMA table_info` 探测 + `ALTER TABLE ADD COLUMN`（`store.py:390-410`），幂等；leg 表历史上做过一次表重建（`cumulative_quote_amt` 改可空），有先例。
6. 流水账本查询能力满足需求：`query_interest_rows(start_ms, end_ms)` / `query_income_rows(start_ms, end_ms)`（`backend/ledger_flow/store.py:324-359`）按时间窗只读；资金费 `um_income_rows` 有 `symbol`+`time_ms`，利息 `interest_rows` 只有资产维度（`asset`+`accrued_at_ms`）。
7. 老策略参照物 `币安套费率策略，逐仓杠杆.js`：`BINANCE_OPEN_ORDER_INFO`（每 symbol 一条当前持仓记录，加仓合并、全平后 `unshift` 到 `_HISTORY` 并 `delete`）证明「周期」产品模型可行；但存在记账数量只增不减、无开仓时间戳、归档即失联、平仓后迟到费率挂不上、`_G` 持久化脆弱五个问题——本设计逐条规避（详见 §4 取舍）。

---

## 3. 数据模型

### 3.1 新增表 `hedge_open_cycle`

```sql
CREATE TABLE IF NOT EXISTS hedge_open_cycle (
    id            TEXT PRIMARY KEY,      -- 周期 UUID（稳定关联键，不删除）
    symbol        TEXT NOT NULL,         -- 币种（带 USDT 后缀，与任务 coin 一致）
    direction     TEXT NOT NULL,         -- forward / reverse
    opened_at_us  INTEGER NOT NULL,      -- 周期起点 = 首次开仓派发时间（us）
    closed_at_us  INTEGER,               -- NULL=活跃中；全平观察后补写
    close_reason  TEXT,                  -- auto_close（功能三）/ manual_verify（人工纠偏）
    first_task_id TEXT,                  -- 起始任务 id（追溯）
    last_task_id  TEXT                   -- 最后贡献成功腿的任务 id（追溯）
);
CREATE INDEX IF NOT EXISTS idx_cycle_active
    ON hedge_open_cycle (symbol, direction, closed_at_us);
```

### 3.2 新增表 `hedge_open_cycle_close_log`（周期结算日志）

类老策略 `BINANCE_OPEN_ORDER_INFO_HISTORY`，但 SQLite 持久化、以 `cycle_id` 关联未来数据。**周期关闭时写入**，不可变快照；供历史查阅与后续平仓盈亏补充。

```sql
CREATE TABLE IF NOT EXISTS hedge_open_cycle_close_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        TEXT NOT NULL,      -- 关联 hedge_open_cycle.id
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,
    opened_at_us    INTEGER NOT NULL,   -- 周期起点（首次开仓派发时间）
    closed_at_us    INTEGER NOT NULL,   -- 平仓观察时间（近似）
    close_reason    TEXT,               -- auto_close / manual_verify（结算日志写入时记录）
    open_avg_price  TEXT,               -- 开单均价快照（周期成本基，关闭时现算写入）
    open_qty        TEXT,               -- 开单累计数量快照
    close_avg_price TEXT,               -- 平单均价：本轮无来源，留空；平仓事件接入后 UPDATE
    funding_fee     TEXT,               -- 周期内资金费合计（关闭时窗口现算）
    borrow_interest TEXT,               -- 周期内利息合计（资产维度近似）
    settled_at_us   INTEGER NOT NULL    -- 结算写入时间
);
CREATE INDEX IF NOT EXISTS idx_close_log_cycle ON hedge_open_cycle_close_log (cycle_id);
```

### 3.3 现有表加列

```sql
ALTER TABLE hedge_open_attempt ADD COLUMN cycle_id TEXT;
CREATE INDEX IF NOT EXISTS idx_attempt_cycle ON hedge_open_attempt (cycle_id);
```

- **`hedge_open_attempt` 挂 `cycle_id`**：一次发单整体属于一个周期（语义层；现货腿天然跟合约腿同周期）。
- **`hedge_open_leg` 不加列**：聚合 SQL-B 已 `JOIN hedge_open_attempt`，`SELECT` 加 `a.cycle_id` 即可，避免两处冗余写的一致性风险。
- **`hedge_open_task` 不加列**：任务与周期是 N:1（一个任务可跨周期），任务卡要显示周期信息时 JOIN 即可。

### 3.4 迁移方式（吸取 BK-T3-002 教训）

1. 备份 `data/hedge-open-tasks.sqlite3`（复制文件 + 校验大小）；
2. 只 `ALTER TABLE ADD COLUMN`（轻量、不重写表；禁止动 `cumulative_quote_amt` 这类已定契约的列）+ 新表 `CREATE TABLE IF NOT EXISTS`（幂等，与现有 `_SCHEMA` 一致）；
3. 回填 SQL 落盘审计文件（§6），前后行数/数值核对；
4. 全程不触碰 `ledger-flow.sqlite3`。

---

## 4. 周期生命周期逻辑

### 4.1 分配（发单时，`prepare_attempt` 事务内）

```
发单时（prepare_attempt）：
  查询 hedge_open_cycle
    WHERE symbol = ? AND direction = ? AND closed_at_us IS NULL
    ORDER BY opened_at_us DESC LIMIT 1
    ├─ 有活跃周期 → 复用其 id，写入 attempt.cycle_id
    │              （场景 A：部分平仓后加仓 → 延续，起始时间不变 ✓；
    │                删任务重建但仓位没平 → 复用，同一仓合并 ✓）
    └─ 无活跃周期 → 新建：
        id = uuid4()
        opened_at_us = 本次派发时间（≈ attempt.created_at_us / leg.dispatched_at_us）
        first_task_id = last_task_id = 当前 task_id
        写入 attempt.cycle_id
        （场景 B：全平后再开 → 新周期、新起始时间 ✓）
```

- 幂等：`prepare_attempt` 已有事务与重试语义；cycle 插入与 attempt 插入同事务，失败回滚。
- `cycle_id` 对旧数据为 NULL（回填见 §6）。

### 4.2 关闭（预留接口，功能三触发；人工核实为纠偏）

关闭周期的触发源**不是自动观察**，而是明确的两个来源。本阶段（功能一）只实现 `close_cycle` 方法本身，不实现触发逻辑（Human 2026-08 决定）：

```
来源一（主路径，功能三开发后）：系统平仓任务完成
  功能三平仓任务卡完成全部平仓后，调用本阶段预留的关闭接口：
    close_cycle(cycle_id, closed_at_us, close_reason='auto_close')
  调用前核实交易所该币种合约已无持仓（功能三的实现责任；接口本身只做单向写入）

来源二（纠偏，可选）：人工核实
  你在交易所手工平仓后，页面「核实平仓」按钮触发：
    实时查交易所该币种合约持仓（不读缓存快照）
    ├─ 无持仓 → close_cycle(cycle_id, now, 'manual_verify')，标记「已完全平仓」
    ├─ 仍有持仓 → 拒绝关闭，提示「未平干净」
    └─ 查询失败 → 拒绝关闭，提示「核实失败」（fail-closed，宁可不动）
```

**明确否决项（Human 2026-08）**：
- **不做自动归零观察**：快照刷新失败/网络异常可能把「读取失败」误报为「无仓」（F4 家族缺陷，`PROJECT_STATE.md` 有同类记录），自动关闭会把显示错误升级为**不可逆的数据错误**（周期被关、成本基被归档）；
- **无宽限期需求**：180s 宽限期只为防自动盯梢误判新仓，自动盯梢废弃后一并取消；
- **忘记核实 / 平仓未完成** → 周期保持「持仓中」（fail-closed，宁可延续，不误判）。

**close 接口契约**（本阶段实现方法）：
- 幂等：重复关闭不覆盖已有 `closed_at_us`；
- 单向：`closed_at_us` 只允许 NULL→值 写入；
- 事务：功能三关闭时与结算日志写入同事务；
- 展示状态：`cycle_closed_at` NULL → 「持仓中」；非 NULL → 「已完全平仓」（展示层派生，不新增字段）。

### 4.3 部分平仓语义

周期不因部分平仓改变：成本基不变、起始时间不变。已平仓段已实现盈亏的会计归属（平仓冲销）不在本轮。

---

## 5. 聚合与展示变化

### 5.1 聚合键

`store.py:2051` 桶键 `(coin, direction)` → `(coin, direction, cycle_id)`：

- 同 cycle 的腿 → 同一行（场景 A 正确：加仓并入，加权均价）；
- 不同 cycle 的腿 → 独立行（场景 B 正确：新行只含本周期腿，旧周期不污染新仓成本基）；
- 已删任务成交仍计入其所属 cycle 行（D15 精神保留，只是粒度从「币种」细化为「周期」）。

### 5.2 输出行新增字段

```
cycle_id         TEXT    -- 周期 UUID
cycle_opened_at  TEXT    -- ISO（从 cycle.opened_at_us 转换）
cycle_closed_at  TEXT    -- ISO 或 null（活跃）
```

### 5.3 展示策略（Human 已拍板周期语义，展示细节阶段 2 细化）

- 已平仓周期行：独立成行，标「已平仓」+ 平仓时间；默认折叠或隐藏，提供开关（阶段 2 细化）。
- 活跃周期行：正常展示，起始持仓时间直接显示。

### 5.4 与 merge 层的关系（P0-1 返工：merge 层必须改）

`merge_positions`（`domain.py:1729`）**必须改动**，不能维持「不改」的断言。现状缺陷：`bucket_by_key` 用 `(coin, direction)` 二元组 `setdefault`（`domain.py:1783-1785`），同一键只保留第一个桶；`matched_buckets` 也按二元组记账（`:1812-1814`）。一旦同一 `(coin, direction)` 存在多个周期桶（场景 B），UM 骨架会匹配到**最早的已平仓周期桶**（排序靠前），真正活跃周期的正确数据被整批跳过——旧成本基顶着真实仓位显示，当前仓完全消失，直接违反目标 1。

返工后的匹配规则：

```
1. 桶键与匹配都以周期为粒度：bucket_by_key 用 (coin, direction, cycle_id)
   （或桶身份）；matched 集合记录「已被 UM 骨架消费的周期桶」，不用二元组。
2. UM 骨架匹配：对每个 (symbol, position_side)，只匹配「活跃周期」（cycle_closed_at
   IS NULL / cycle_closed_at 为 null）的桶；同键下多个活跃周期（异常）取最近 opened 者，
   其余按未匹配处理。
3. step 2 未匹配输出：同 (coin, direction) 下未被消费的其它周期桶（含已平仓周期、
   无对应交易所仓位的活跃周期）各自作为独立 no_um 行输出——已平仓周期行带
   cycle_closed_at，标「已平仓」，不合并、不丢弃。
4. match_status 语义不变：normal（UM + 活跃周期桶）/ no_task / no_um。
```

验收（§8 用例 2 补强）：同一 `(coin, direction)` 同时存在一个已平仓周期和一个活跃周期时，输出**两行**：UM 骨架行挂活跃周期的均价/起始时间，已平仓周期独立成行（`no_um` + 已平仓标记）。

---

## 6. 历史回填（旧数据无 cycle_id）

现状数据：29 个任务、102 条 leg（92 条有成交）、1 个已删任务；8 个 `(coin, direction)` 组合，其中 RSRUSDT reverse 有 13 个任务（集中于 2026-07-30 16:16～18:12 两小时内）、COOKIEUSDT forward 5 个（含 1 已删）、KORUUSDT forward 4 个、RSRUSDT forward 3 个。

**回填策略（Human 已拍板）：按币种全归一个周期**，每个 `(coin, direction)` 一个周期：
- `opened_at_us` = 该币种最早成功腿的 `dispatched_at_us`（无则最早 `attempt.created_at_us`）；
- `closed_at_us` = NULL（活跃；历史数据无平仓事件，保持「持仓中」，由功能三平仓完成/人工核实时关闭）
- `first_task_id` / `last_task_id` = 最早 / 最晚任务 id。

两种方式的取舍（记录备查）：
- **按币种全归**：符合「只要没全部平仓都算第一次开单到现在」的语义；RSRUSDT reverse 的 13 个两小时内密集任务归 1 段，避免假分裂。风险：历史中若真全平过再开，会被混成一段（起始时间偏早、成本基混算）。
- **按任务分组**（不采用）：13 个任务 → 13 段假分裂，且同币种多任务加仓场景下起始时间失真。

**修正能力**：回填脚本支持人工指定分段点（某币种若记得全平过再开，可显式切分为多周期）；默认全归一段。回填 SQL 必须落盘为审计文件，执行前后行数核对并记录。

---

## 7. 费率 / 利息窗口归属

周期窗口 = `[opened_at_us, closed_at_us 或 now]`。

| 项目 | 数据源 | 归属规则 |
|---|---|---|
| 资金费 | `um_income_rows`（`symbol` + `time_ms` + `income_type`） | 按 `symbol` + 窗口聚合，**可靠对齐** |
| 借币利息 | `interest_rows`（资产维度；**实盘 `isolated_symbol` 全空**，`type=PERIODIC`） | 按 `asset` + 窗口聚合：周期没全平，窗口内该资产的利息都算进这个周期。单仓准确；多仓并存时同一资产利息近似归属当前活跃周期（Human 已拍板：只要没全部平仓都算在本次周期内） |

**周期收益（Human 已拍板，2026-08-08 更正）**：`funding_fee − borrow_interest` 窗口合计（`interest_rows.interest` 为币安记的正数成本，原文误作相加）；不含未实现盈亏、不含平仓盈亏。展示层 `net_pnl`/`accrued_funding`/`borrow_interest` 由此填充，未实现盈亏仍独立展示（现有 `unrealized_profit` 字段）。

**迟到费率（Human 已拍板）**：不特殊处理极端迟到。窗口用闭区间 `[opened_at, closed_at]`；费率到账晚于窗口但在 ledger 约 1 小时自动刷新窗口内的，自然进入后续展示；超出窗口的极端情况接受近似，不追溯。

**覆盖率判定（P1-2 返工：复用 gap-aware 判定，不新造端点比较）**：
- 复用 `LedgerFlowService._build_coverage`（`backend/ledger_flow/service.py:373`，已有 gap-aware 完整性判定：`complete = cov_start is not None and window_start >= cov_start and len(gaps) == 0`）或为其做按窗口调用的公开包装；`get_coverage()`（`backend/ledger_flow/store.py:383`）返回真实字段名 `interest_start_ms`/`interest_end_ms`/`income_start_ms`/`income_end_ms` + `gaps` 列表（`{"source","start_ms","end_ms"}`）。
- 判定规则：窗口整体落在覆盖率内 **且** 窗口内无已记录缺口（`gaps` 与窗口相交数为 0）→ 完整；否则该行统计标 `stats_incomplete`（前端显示「统计区间不全」）。
- 硬约束不变：**绝不把覆盖率不足的窗口当成真值**——端点覆盖但中间有洞的窗口同样算不完整。

**单位注意**：`um_income_rows.time_ms` / `interest_rows.accrued_at_ms` 是**毫秒**，本地周期时间为**微秒**（us），换算统一在查询层处理。

---

## 8. 验收用例

| # | 场景 | 输入 | 期望输出 |
|---|---|---|---|
| 1 | 场景 A：部分平仓 + 加仓 | 同 symbol+direction：开仓 t1 → 交易所手工平一半 → 再开仓 t2 | 同一行，起始时间 = t1 派发时间，均价 = t1+t2 加权，数量与交易所当前仓一致 |
| 2 | 场景 B：全平再开 | 开仓 t1 → 功能三平仓完成调用 close_cycle → 再开 t2 | 两个独立 cycle：新行起始时间 = t2，旧周期行标「已完全平仓」 |
| 2b | 场景 B merge 匹配（P0-1） | 同一 `(coin, direction)` 同时存在一个已平仓周期和一个活跃周期，快照确认新仓 | 输出**两行**：UM 骨架行挂活跃周期均价/起始时间（match_status=normal），已平仓周期独立成行（no_um + 已平仓标记） |
| 3 | 删任务重建（仓未平） | 删旧任务 → 新建任务同币种同方向 | 复用活跃 cycle，同一行，无混算 |
| 4 | 删任务重建（仓已平） | 删旧任务 + 平仓完成（close_cycle 已调）→ 新建任务 | 新 cycle，新起始时间，旧周期成本不进新行 |
| 5 | 同任务加仓 | 同一 task 多次成功 attempt | 同 cycle 同行，加权均价 |
| 5b | close 接口契约（功能一验收） | 重复调用 close_cycle / 传已关闭的 cycle | 幂等：closed_at_us 不覆盖；单向：NULL→值 后不再变 |
| 6 | 迟到费率归属 | 平仓后费率到账，时间 ≤ closed_at_us | 计入该周期资金费 |
| 7 | 冷启动（快照未验证） | GET positions 且 snapshot 不可用 | 周期行照常显示，不误关活跃周期（本阶段无自动关闭，天然满足） |
| 8 | 迁移幂等 | 重复运行迁移 | 无重复列、无重复回填、行数核对一致 |
| 7 | 冷启动（快照未验证） | GET positions 且 snapshot 不可用 | 周期行照常显示，不误关活跃周期 |
| 8 | 迁移幂等 | 重复运行迁移 | 无重复列、无重复回填、行数核对一致 |

验收口径变化属于资金/PnL 含义：全部用例需在测试库上以「修改前后数值 diff」形式呈现，人工核验。

---

## 9. 拍板记录与残余开放问题

### 9.1 已拍板（Human 2026-08 讨论）

1. **历史回填：按币种全归一个周期**（每个 `(coin, direction)` 一个周期，起始时间 = 最早开仓派发时间；支持人工分段点修正）。
2. **新增周期结算日志表** `hedge_open_cycle_close_log`：记录已平仓周期的开单均价/数量快照、资金费、利息、平仓时间；`close_avg_price` 预留留空（平仓事件接入后填充）。
3. **周期边界语义**：只要没全部平仓，都算从第一次开单到现在的同一个周期。
4. **周期收益口径**：只计算费率 + 利息窗口合计，不含未实现盈亏与平仓盈亏。
5. **迟到费率**：不特殊处理极端迟到；窗口闭区间，迟到的在 ledger 约 1 小时自动刷新后自然展示。

### 9.2 残余开放问题

- 无阻塞项；展示层文案（「已平仓」行、起始持仓时间列、结算日志入口）在阶段 2 实施时细化。

---

## 10. 风险与评审

- 改聚合口径 = 资金/PnL 含义变化 → **HIGH_RISK**：实现前需独立计划评审，实现后 review-1 + review-2，评审锚定 `base_sha..delivery_sha`。
- 迁移安全：实盘库存在 BK-T3-002 迁移静默重写生产库前科（`PROJECT_STATE.md`）；本设计强制「备份 → 仅 ADD COLUMN → 回填落盘审计 → 前后核对」。
- 关闭动作完全受控（无自动观察）：快照读取失败不再可能误关周期；剩余风险是「平仓后忘记核实 → 周期显示持仓中」（fail-closed，宁可延续，不误判），发布说明明示。
- 已删任务成交计入（D15）在新模型下的语义：从「币种行」细化为「周期行」，不丢失成本基可见性，但展示层文案需同步更新（「含已删除任务」标记仍按行保留）。

---

## 11. 实施切分建议（供排期，非本轮承诺）

- **阶段 0**：本草案评审 + 设计定稿（§9 拍板项已确认）。
- **阶段 1**：schema 迁移 + 回填 + `aggregate_positions` 桶键改 `(coin, direction, cycle_id)` + 输出 `cycle_id`/`cycle_opened_at`；后端 + 测试库验收用例 1/2/5/8。
- **阶段 2**：`close_cycle` 接线（功能三平仓完成触发 / 人工核实纠偏）+ 展示层（已平仓行、起始持仓时间列、「持仓中/已完全平仓」状态）；用例 3/4/6/7。
- **阶段 3**（可选，依赖平仓功能或流水接入）：费率/利息窗口接入 `accrued_funding`/`borrow_interest`。

---

## 12. 平仓现货卖出路由重设计（2026-08-05 append-only，Human 已拍板）

> **2026-08-09 supersession pointer:** 本节保留为历史设计记录；其中 §12.2
> “首个 attempt 前一次性余额检查”已被两段式 close 方案取代。当前合同见
> `docs/product/PRD.md` §6.3 与 `DEC-2026-08-09-001`：建卡只落 paused，启动后
> 每个 attempt 按 fresh `q_common × remaining_attempts` 执行 UM/forward-base 门。
> 划转端点、方向、审计与 USDT 回流语义未被改写。

触发事实：COOKIEUSDT 平仓实测——开仓现货买在统一账户（`/papi/v1/margin/order`），平仓现货 SELL
被 `decide_spot_route` 的 collateral-cap 预检误导到普通现货账户（`/api/v3/order`）→ `-2010
insufficient_funds`（普通账户无货），合约腿已平、现货单腿 paused（Human 手工处理现货）。

### 12.1 路由规则（decide_spot_route 加 task_type 参数，默认 'open' 行为不变）

| task_type | direction | 现货腿路由 | 原因 |
|---|---|---|---|
| close | forward（卖现货） | **固定 `regular_spot`**（`/api/v3/order`） | 卖出在普通账户是唯一出口；**不再走 collateral-cap 预检**（cap 只对买入有意义） |
| close | reverse（买现货） | **固定 `papi_margin`**（`/papi/v1/margin/order`） | 统一杠杆账户（与开仓 reverse 一致，借币语义；还币后续任务） |
| open | 任意 | 现有逻辑逐字不变 | — |

close 任务的 preflight direction 是反转后的余额检查方向（forward close 卖现货需现货余额）；
provider 内把 route 决策方向反转回持仓方向后调用 `decide_spot_route`。close 不依赖 collateral-cap
列表读取（open+forward 才读；读失败 fail-closed 只影响 open 路径）。

### 12.2 划转时序（close 任务首个 attempt 发单前，一次性 + fail-closed）

仅 forward close（现货 SELL 走普通账户）：

```
1. 实时查普通现货账户该币 free 余额（GET /api/v3/account，不用缓存快照）
2. 余额 ≥ 计划卖量 → 直接返回（无需划转）
3. 余额 < 计划卖量 →
   a. universal_transfer('PORTFOLIO_MARGIN_MAIN', base, 差额)   ← 一次性，仅此处一次
   b. 复检普通账户余额（防「响应丢失但划转成功」误判）
   c. 复检仍不足 → 任务 paused（fail-closed），中文错误写任务卡日志，不重试、不发单
4. 任一步失败/异常 → 任务 paused + 日志，不重试
reverse close（现货 BUY）：跳过划转，维持现状（统一账户）
```

幂等保证：划转只在 close 任务首个 attempt 发单前调用一次（`scheduled_attempt_count == 0`）；
任务 paused/stopped 后 worker 由既有拦截挡住，不进入该路径；无重试循环。

### 12.3 USDT 回流（forward close 平仓完成后）

```
1. 统计本轮 close 任务全部现货腿成交额（cumulative_quote_amt 合计，USDT）
2. universal_transfer('MAIN_PORTFOLIO_MARGIN', 'USDT', 合计)    ← 划回统一账户
3. 失败 → 不阻塞（平仓已完成是主事实），错误写任务卡日志（中文），任务状态不变（done）
金额 0/空 → 跳过；reverse close 无回流（买入花钱）
```

### 12.4 万向划转端点（受控扩展）

- 白名单新增 `POST /sapi/v1/asset/transfer`（用户万向划转，权重 TRADE；API key 万向划转权限
  Human 2026-08-05 已确认开启，沿用开单 api key）；
- 参数冻结：`type` 仅 `PORTFOLIO_MARGIN_MAIN`（统一→现货）/ `MAIN_PORTFOLIO_MARGIN`（现货→统一）；
  `asset`/`amount` 由内部计算传入，拒绝外部注入；
- 写语义与订单一致：超时/5xx 不重试，返回 tranId 或抛错，调用方 fail-closed。

### 12.5 安全要点（评审重点）

- 划转端点白名单受控扩展（第 4 个 POST 写端点，参数冻结）；
- 时序：发单前一次性、失败即停（不重试、不发单）；
- 复检防误判（划转响应丢失 ≠ 未划转）；
- 回流不阻塞主流程（平仓已完成是主事实，失败仅任务卡日志提示人工）。
