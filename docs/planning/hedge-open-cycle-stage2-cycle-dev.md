# 功能 2 开发文稿：持仓周期表（hedge-open position cycle）

状态：**开发文稿，供独立核对；不授权实现、迁移或任何实盘操作。**
设计权威：`docs/planning/hedge-open-position-cycle-v1.md`（下称「设计 v1」；§9 五项口径已由 Human 拍板）。
本文稿把设计 v1 §3–§6 细化到文件/函数级实现点与验收断言，供 sonnet5 独立核对（核对点用「🔍」标注）。

---

## 1. 目标与边界

### 1.1 目标

1. 引入「持仓周期」实体：同一币种+方向，仓位从未完全归零 → 同一周期；归零后再开 → 新周期。
2. 聚合键 `(coin, direction)` → `(coin, direction, cycle_id)`：平仓再开仓后新仓成本基不与历史混算。
3. 每个周期有可靠起始时间（`opened_at_us` = 首次开仓派发时间），供后续费率/利息窗口统计。
4. 历史数据回填：按 `(coin, direction)` 全归一个周期（Human 已拍板）。

### 1.2 不在本轮

- 不做周期结算日志表 `hedge_open_cycle_close_log`（功能 ③a）、不做费率/利息统计（功能 ②）、不做平仓执行（功能 ③b）。
- 不改现货「周期」语义（现货腿跟随同 attempt 的合约周期）。
- 不改变 Start gate、订单、查单、借币、划转、凭证路径。
- 聚合口径变化属于资金/PnL 含义：只改后端聚合与输出字段，**不改前端真实渲染路径**（前端仅消费新增字段，本轮允许 `cycle_id`/`cycle_opened_at` 为空时不展示）。

---

## 2. 数据模型（设计 v1 §3 精确复制）

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

```sql
ALTER TABLE hedge_open_attempt ADD COLUMN cycle_id TEXT;
CREATE INDEX IF NOT EXISTS idx_attempt_cycle ON hedge_open_attempt (cycle_id);
```

约束（设计 v1 §3.4，吸取 BK-T3-002 教训）：迁移只 `ADD COLUMN` + 新表 `CREATE TABLE IF NOT EXISTS`，**禁止重建表、禁止动 `cumulative_quote_amt` 等已定契约列**；全程不触碰 `ledger-flow.sqlite3`。

---

## 3. 实现点（文件:行级）

### 3.1 建表：`backend/hedge_open_tasks/store.py` `_SCHEMA`（37-165）

在 `_SCHEMA` 末尾（`hedge_open_raw_response` 建表与索引之后，`:164` 附近）追加 `hedge_open_cycle` 建表 + `idx_cycle_active` 索引。🔍 核对点：DDL 与 §2 逐字一致；幂等（`IF NOT EXISTS`）。

### 3.2 迁移：`store.py` `_migrate`（370-410）

仿照现有 `attempt_additions`/`leg_additions` 模式（`:388-410`，`PRAGMA table_info` 探测 + `ALTER TABLE ADD COLUMN`）：
在 attempt 迁移段追加：

```python
attempt_cycle = {r["name"] for r in self._conn.execute("PRAGMA table_info(hedge_open_attempt)")}
if "cycle_id" not in attempt_cycle:
    self._conn.execute("ALTER TABLE hedge_open_attempt ADD COLUMN cycle_id TEXT")
self._conn.execute("CREATE INDEX IF NOT EXISTS idx_attempt_cycle ON hedge_open_attempt (cycle_id)")
```

🔍 核对点：与既有迁移同一事务、幂等（重复运行不报错、不重复加列）。**建表已定在 §3.1 的 `_SCHEMA`**（`CREATE TABLE IF NOT EXISTS` 随 `executescript` 每次 `__init__` 自动幂等执行）；`_migrate` 只追加 `ALTER TABLE` + 索引，**不重复建表**。

### 3.3 新 store 方法（`store.py`，`aggregate_positions` 之前插入）

每对方法做**双版本**（沿用 `_apply_task_counters` 先例，见 §3.4 核对点）：

```python
# 内部无锁版：MUST run inside the caller's with self._lock, self._conn: transaction
def _get_active_cycle_locked(self, symbol, direction) -> dict | None:
    """活跃周期 = closed_at_us IS NULL 的最新一条。"""

def _create_cycle_locked(self, symbol, direction, opened_at_us, task_id) -> dict:
    """新建周期：id=uuid4(); first_task_id=last_task_id=task_id。"""

# 对外加锁版：供功能三平仓任务 / 人工纠偏等非事务调用方使用
def get_active_cycle(self, symbol, direction) -> dict | None: ...   # with self._lock, self._conn: 包 _get_active_cycle_locked
def create_cycle(self, symbol, direction, opened_at_us, task_id) -> dict: ...  # 同上

def get_cycle_by_id(self, cycle_id) -> dict | None:
    """周期行映射（含 opened_at_us/closed_at_us）。"""

def close_cycle(self, cycle_id, closed_at_us, close_reason) -> None:
    """关闭周期：closed_at_us 只允许 NULL→值 的单向写入；幂等（重复调用不覆盖）。
    供功能三平仓任务（close_reason='auto_close'）与人工纠偏（'manual_verify'）调用；
    本阶段只实现方法本身，不接线任何触发逻辑。"""
```

🔍 核对点：
- `_create_cycle_locked`（事务内路径）与 attempt 写入**同一事务**，见 §3.4；
- `close_cycle` 幂等（重复关闭不覆盖已有 closed_at_us）；`close_cycle` 是独立写操作，自带 `with self._lock, self._conn:`；
- `close_cycle` **本阶段不接线触发逻辑**（无自动盯梢、无核实端点），只定义方法 + 单测，调用方是功能三（见 §3.6）。

### 3.4 分配：`store.py` `prepare_attempt`（735-851）

在 `:790`（seq 计算后）与 attempt INSERT（`:792-807`）之间插入：

```
1. cycle = _get_active_cycle_locked(task.coin, task.direction)   -- 内部无锁版，见下方核对点
2. cycle_id = cycle["id"] if cycle else _create_cycle_locked(...)["id"]
   -- opened_at_us = now_us（本次派发时间；与 attempt.created_at_us 同事务写入，微秒级一致）
3. attempt INSERT 列清单追加 cycle_id
```

🔍 核对点：
- 分配发生在**同一事务**（`with self._lock, self._conn:` 内），失败回滚不留孤儿 cycle；
- `self._lock` 是重入 `RLock`（`:343`），同线程再套 `with self._lock` **不会死锁**——真正风险在 sqlite3 `Connection.__exit__`：内层 `with self._conn:` 退出时会对已执行语句**提前 commit**，破坏「cycle 插入与 attempt 插入同一事务、失败整体回滚」的原子性。因此分配方法**不得自带 `with self._conn:`**，须做成内部无锁版本（§3.3 的 `_get_active_cycle_locked`/`_create_cycle_locked`），在 `prepare_attempt` 的既有事务内直接调用；
- 代码内先例：`_apply_task_counters`（`:906`）docstring 明确「MUST run inside the caller's with self._lock, self._conn: transaction」，由 `resolve_attempt`/`finalize_attempt` 内部直接调用、自己不加锁——新方法沿用同一模式，**不引入新模式**；
- `task.coin`/`task.direction` 需从 `:760` 的 task SELECT 补两列。

### 3.5 聚合拆分：`store.py` `aggregate_positions`（2022-2185）

- SQL-B（`:2042-2049`）：`SELECT` 追加 `a.cycle_id, c.opened_at_us AS cycle_opened_at_us, c.closed_at_us AS cycle_closed_at_us`；追加 `LEFT JOIN hedge_open_cycle c ON c.id = a.cycle_id`。
- SQL-A（`:2035-2041`，`hedge_open_fill` 空壳）：无 cycle_id，保持现状（0 行，不参与周期拆分）。**防御性断言（P2-1）**：SQL-A 若观察到非零行数，应视为异常并记录告警，而不是静默并入聚合——`insert_fill()`（`:1682`）仍是可调用的活方法，任何未来路径重新调用都会产出无 `cycle_id` 的行，落入桶键含 None 的兜底分支但永远无法归入周期，merge 也无法正确处理（无 cycle_id 的桶是否「活跃」未定义）。
- 桶键（`:2051` 及 `_bucket` 调用点 `:2079`/`:2112`）：`(coin, direction)` → `(coin, direction, cycle_id)`；`_bucket` 签名与 `setdefault` 同步改。
- 输出行（`:2162-2182`）追加：
  - `cycle_id`：桶键第三元（NULL → 保持现有 `None`/省略，前端不渲染）
  - `cycle_opened_at`：`D.us_to_iso(cycle_opened_at_us)` 或 null
  - `cycle_closed_at`：同规则（活跃周期 = null）
- 排序键（`:2184`）追加 cycle_opened_at_us（同一 coin+direction 多周期按时间序）。

🔍 核对点：
- 同一 cycle 内加权逻辑（G5 分母规则、`includes_deleted_task` 标记）**逐字不变**，只改桶键与输出字段；
- 旧数据（cycle_id NULL）行为：回填后无 NULL；回填前 bucket key 含 None，仍能聚合（防御性，不报错）；
- **`merge_positions`（`backend/hedge_open_tasks/domain.py:1729`）必须改（P0-1）**：现状 `bucket_by_key` 用 `(coin, direction)` 二元组 `setdefault`（`:1783-1785`），同一键只保留第一个桶（排序靠前 = 最早周期），`matched_buckets` 也按二元组记账（`:1812-1814`）。多周期场景下 UM 骨架会匹配到已平仓旧桶、活跃周期数据被整批跳过——必须改为按周期粒度匹配（UM 骨架只匹配活跃周期桶，matched 按周期记账，未匹配的其它周期桶各自独立 no_um 输出）。匹配规则权威在设计 v1 §5.4，实现时照此。

### 3.6 关闭接口预留（Human 2026-08 决定：不做自动归零观察）

本阶段**只实现 `close_cycle` 方法本身，不实现任何触发逻辑**。`server.py` 无改动（原「归零观察关闭」逻辑**废弃**，不留代码）。

```
close_cycle(cycle_id, closed_at_us, close_reason) -> None   -- store 方法（§3.3）
  契约：幂等（closed_at_us 已非 NULL 不覆盖）；单向（仅 NULL→值）；自带事务

将来调用方（功能三开发后接线）：
  主路径：平仓任务卡完成全部平仓 → close_reason='auto_close'（调用前核实交易所无持仓）
  纠偏  ：人工核实（页面按钮 → 实时查交易所合约无持仓）→ close_reason='manual_verify'
  查询失败 / 仍有持仓 → 拒绝关闭（fail-closed，宁可不动）
```

🔍 核对点：
- **明确否决自动归零观察 + 180s 宽限期**（Human 2026-08）：快照刷新失败/网络异常可能把「读取失败」误报为「无仓」（F4 家族缺陷），自动关闭会把显示错误升级为不可逆的数据错误；宽限期只为防自动盯梢误判新仓，随盯梢一并取消；
- **忘记核实 / 平仓未完成** → 周期保持「持仓中」（fail-closed，宁可延续，不误判）；
- 展示状态由 `cycle_closed_at` 派生：NULL=「持仓中」，非 NULL=「已完全平仓」（不新增字段）；
- `close_reason` 枚举：`auto_close`（功能三）/ `manual_verify`（人工纠偏）；**`um_flat` 废弃**；
- 本阶段验收：`close_cycle` 存在且契约正确（幂等/单向/事务）——方法级单测，不要求任何触发路径。

### 3.7 历史回填（轻量表内部数据初始化，数据源 = 开单任务卡）

**数据来源（Human 2026-08 确认）**：轻量表建好后，内部数据直接从**开单任务卡**初始化——因为当前系统没有任何平仓事件，每条周期记录的开启时间就是「该币种最早的开仓时间」，`closed_at_us` 全部为 NULL（都是「持仓中」）。

**数据源映射（任务卡 → 周期行）**：

```
输入查询（回填脚本）：
  hedge_open_task t                          -- 任务卡（定位该币种有哪些任务）
    JOIN hedge_open_attempt a ON a.task_id = t.id   -- 发单时间
    JOIN hedge_open_leg l ON l.attempt_id = a.id    -- 派发时间 / 成交
  按 (t.coin, t.direction) 分组

周期行生成（每个 (coin, direction) 一条，9 组合实测）：
  id            = uuid4()
  symbol        = t.coin
  direction     = t.direction
  opened_at_us  = 组内最早【成功腿】的 l.dispatched_at_us
                  （无成功腿 → 最早 a.created_at_us；仍无 → 不建周期行，因无仓位）
  closed_at_us  = NULL（当前无平仓事件，全部「持仓中」；由功能三/人工核实时关闭）
  close_reason  = NULL
  first_task_id = 组内最早任务 id（按 t.created_at_us）
  last_task_id  = 组内最晚任务 id

attempt.cycle_id 回填：按 attempt 所属 task 的 (coin, direction) → 组 cycle_id
```

**时间取值注意（KORUUSDT 实测案例）**：任务卡 `created_at_us`（07-27）与最早发单时间（08-03）可能相差很远——任务早建但迟迟未成功发单。因此 `opened_at_us` **不用任务卡创建时间**，而用最早成功腿的 `dispatched_at_us`（仓位真正开启时刻）；任务卡仅用于定位「该币种有哪些任务」。实盘 9 组合中 8 个三者时间差在数秒～数分钟，仅 KORUUSDT 差异显著。

```
执行步骤：
1. 备份 data/hedge-open-tasks.sqlite3（复制 + 大小校验）
2. 按上表生成周期行（dry-run 输出计划）
3. 每条 attempt 回填 cycle_id（按 task → 组的映射）
4. 人工分段点支持：--split "SYMBOL,DIRECTION,ISO时间" 可指定某币种分段
5. 落盘审计 SQL + 前后行数/数值核对（cycle 数、attempt 覆盖数、无 NULL cycle_id）
```

🔍 核对点：
- 回填是**一次性写库操作**，按仓库规则属需 Human 显式授权的写操作；脚本默认 dry-run 输出计划，`--apply` 才写库；审计文件路径由执行时指定；
- **无成功腿的组合不建周期行**（没有仓位就没有周期）——回填后周期数 ≤ 有成交的组合数；
- 回填后 `closed_at_us` 全 NULL（当前无平仓事件，与「持仓中」展示一致）。

### 3.8 测试

- `backend/tests/test_hedge_store.py`：新方法单测（get/create/close/list_active_cycles）、`prepare_attempt` 分配（有活跃 cycle 复用 / 无则新建）、`aggregate_positions` 按周期拆桶（场景 A/B）。
- `backend/tests/test_hedge_api.py`：`GET /api/hedge-open-positions` 输出含 `cycle_id`/`cycle_opened_at`；**merge 多周期匹配（P0-1）**：同 `(coin, direction)` 一已平仓周期 + 一活跃周期，输出两行，UM 骨架行挂活跃周期数据。
- `close_cycle` 契约单测（本阶段验收）：幂等（重复关闭不覆盖）、单向（NULL→值 后不变）、事务（自带 `with self._lock, self._conn:`）。
- 迁移幂等测试：重复构造 store 不重复加列、回填后无 NULL cycle_id。
- 前端 `frontend/self-check.js`：无需改（新增字段后端透传，前端本轮不渲染）。

---

## 4. 迁移与回填步骤（执行顺序，全部需 Human 授权）

1. 备份：`cp data/hedge-open-tasks.sqlite3 data/hedge-open-tasks.sqlite3.bak-cycle-<ts>` + 校验大小；
2. 部署新代码（含 `_migrate` 自动 ADD COLUMN + 建表）——**先测试库，后实盘**；
3. 测试库跑回填脚本（dry-run → apply）→ 核对审计；
4. 实盘跑回填（Human 授权）→ 前后行数核对；
5. 验证 `GET /api/hedge-open-positions` 输出。

---

## 5. 验收用例（设计 v1 §8，测试库执行）

| # | 场景 | 期望 |
|---|---|---|
| 1 | 部分平仓 + 加仓（同 cycle） | 同一行，起始时间 = 首次派发时间，均价 = 加权 |
| 2 | 全平再开（close_cycle 已调） | 两个独立 cycle：新行起始时间 = 再开时间，旧周期行标「已完全平仓」 |
| 3 | 删任务重建（仓未平） | 复用活跃 cycle，同一行 |
| 4 | 删任务重建（仓已平） | 新 cycle，新起始时间，旧成本不进新行 |
| 5 | 同任务加仓 | 同 cycle 同行，加权均价 |
| 5b | close 接口契约 | 重复 close 不覆盖；NULL→值 单向；自带事务 |
| 8 | 迁移幂等 | 重复运行无重复列/回填，行数核对一致 |

额外：修改前后数值 diff 呈现（改口径属资金/PnL 含义，Human 需人工核验 diff）。

---

## 6. 风险与评审

- HIGH_RISK（改聚合口径 = 资金/PnL 含义）：实现前需独立计划评审（跨 provider 只读）；实现后 review-1 + review-2，锚定 `base_sha..delivery_sha`。
- 实盘库迁移前科 BK-T3-002（`PROJECT_STATE.md`）：迁移只 ADD COLUMN + 幂等建表；回填 dry-run 先行。
- 关闭动作完全受控（无自动观察）：快照读取失败不再可能误关周期；剩余风险是「平仓后忘记核实 → 周期显示持仓中」（fail-closed），发布说明明示。
- 前端本轮不渲染新字段：避免 fake→真实接线漂移（历史仓位页 fake 在功能 ③a 接真数据，与功能 2 解耦）。
