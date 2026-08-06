# Task Handoff: hedge-position-cycle-v1-cycle-core

## Source Report (author-only; immutable after task end)

- task_id: `hedge-position-cycle-v1-cycle-core`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-05 15:20 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，与任务一同基线；本任务未移动 HEAD）
- delivery_sha: `pending`（未提交任何 commit，交付为工作树改动）

### 任务背景

功能一剩余块：发单分配 + 聚合拆分 + merge 多周期匹配（P0-1）+ close 方法定义。依据：dispatch
`reports/agent-runs/_proposals/2026-08-hedge-position-cycle-v1-cycle-core.dispatch.md`、stage2 文稿
`docs/planning/hedge-open-cycle-stage2-cycle-dev.md` §3.3-§3.6、设计 v1 `docs/planning/hedge-open-position-cycle-v1.md`
§4.1/§5/§5.4。在任务一（建表+迁移+回填，工作树未提交）基础上开发，任务一改动全部保留。

### 实际修改范围

1. `backend/hedge_open_tasks/store.py`
   - `import uuid`；
   - 新增周期方法（positions 段，双版本模式沿用 `_apply_task_counters`:930 先例）：
     `_get_active_cycle_locked(symbol, direction)` / `_create_cycle_locked(symbol, direction, opened_at_us, task_id)`
     ——内部无锁版，MUST run inside caller's `with self._lock, self._conn:` 事务，**无嵌套 `with self._conn:`**；
     对外加锁版 `get_active_cycle` / `create_cycle`；`close_cycle(cycle_id, closed_at_us, close_reason)`——
     幂等（`WHERE closed_at_us IS NULL` 不覆盖）、单向（仅 NULL→值）、自带 `with self._lock, self._conn:`；
   - `prepare_attempt`：task SELECT 补 `coin, direction`；seq 计算后、attempt INSERT 前调用
     `_get_active_cycle_locked`（有活跃 `closed_at_us IS NULL` 复用其 id，无则 `_create_cycle_locked`
     `opened_at_us=now_us`、first/last=当前 task_id）；attempt INSERT 列清单追加 `cycle_id`——cycle 与
     attempt 同一事务写入，失败整体回滚；分配前的非法路径（task 非 RUNNING / 达 cap / in-flight）仍在
     cycle 创建之前 return，不留孤儿 cycle；
   - `aggregate_positions`：SQL-B（leg_rows）SELECT 追加 `a.cycle_id` + `c.opened_at_us`/`c.closed_at_us` +
     `LEFT JOIN hedge_open_cycle c ON c.id = a.cycle_id`；桶键 `(coin, direction)` → `(coin, direction, cycle_id)`
     （fill_rows 用 None 兜底）；输出行追加 `cycle_id` / `cycle_opened_at`（ISO）/ `cycle_closed_at`（ISO 或 null）；
     排序键追加 cycle_opened_at（ISO 字典序 = 时间序）；同 cycle 加权逻辑（G5 分母、includes_deleted_task）逐字不变；
     P2-1：SQL-A（hedge_open_fill）非零行时写 `hedge_open_log` 告警（kind=`aggregate_sql_a_nonzero`），不静默并入；
     `with self._lock:` 升级为 `with self._lock, self._conn:`（仅告警路径写入）。
2. `backend/hedge_open_tasks/domain.py`
   - `merge_positions` P0-1 重写：桶匹配按桶身份 `(coin, direction, cycle_id)` 记账，不再用
     `(coin, direction)` 二元组 setdefault（消除同键多周期静默丢弃）；UM 骨架只匹配活跃周期桶
     （`cycle_closed_at` 为 null），同键多个活跃周期（异常）取最近 opened 者，其余按未匹配处理；
     step 2 未被消费的周期桶各自独立 `no_um` 输出（已平仓周期带 `cycle_closed_at`，不合并不丢弃）；
     `match_status` 语义不变；排序加 cycle_opened_at 次级键；
   - `_merge_empty_bucket_row` 追加 `cycle_id`/`cycle_opened_at`/`cycle_closed_at` = None（no_task 行契约一致）；
     bucket 的周期字段经 `dict(bucket)` 透传。
3. `backend/tests/test_hedge_api.py`：`_POSITION_KEYS` 追加 `cycle_id`/`cycle_opened_at`/`cycle_closed_at`
   （该测试是 merged 输出严格键集断言，新字段为 additive，必须同步）。
4. `backend/tests/test_hedge_cycle_core.py`（新增 15 用例）：分配（新建/复用/失败无孤儿/close 后新 cycle/
   删任务重建复用）、聚合（周期字段 + 同 cycle 加权回归 + 多周期两行 + SQL-A 告警）、merge 2b（已平仓+活跃
   两行 / 无活跃时 no_task+no_um / 同键多活跃取最近）、close 契约（幂等/单向/unknown id noop）。
5. `backend/tests/test_hedge_cycle_backfill.py`：**越界适配（见下「需 Bookkeeper 裁定」）**。

### 需 Bookkeeper 裁定：test_hedge_cycle_backfill.py 的最小适配

任务一测试用 store 方法（`prepare_attempt`）构造数据；本任务引入发单分配后，任何 prepare 都会自动
建/复用 cycle，导致任务一回填测试的旧假设失效（populate 后 cycle 表非空 → 脚本 apply 的重复回填防护
拒绝执行，7 个用例失败）。该文件**不在本 dispatch Allowed Files 字面列表**，但验收 6 要求
`test_hedge_cycle_backfill.py` 全绿——两者冲突。处理：对该文件做最小适配（新增 `_strip_cycles` helper：
populate 后 `DELETE FROM hedge_open_cycle` + `UPDATE hedge_open_attempt SET cycle_id = NULL`，把自动分配
抹掉回到「无周期历史数据」场景），**测试断言本身不变**（回填 9 行/2 行、审计 diff 等全部原样）。请
Bookkeeper 判定该适配属验收驱动的正当范围扩展，或按勘误/修复规则另计。

### 测试结果

- dispatch 指定命令：`python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_cycle_backfill.py -q` → **214 passed**
  （另含新 `test_hedge_cycle_core.py` 15 用例同批全绿）。
- 全量回归：`timeout 400 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1376 passed**（87s，无回归）。

### 验收逐项

1. **分配**：新建（opened_at=now、first=last=task）/复用/失败回滚无孤儿/close 后新 cycle——单测全过
   （`test_assign_*`）；`_*_locked` 无嵌套 `with self._conn:`（代码核对）。
2. **聚合拆分**：输出含 `cycle_id`/`cycle_opened_at`/`cycle_closed_at`；同 cycle 加权回归断言
   （spot/perp avg=50000、qty 与旧口径一致）；SQL-A 非零行告警落库
   （`test_aggregate_sql_a_nonzero_writes_warning`）。
3. **merge 2b（P0-1）**：同 (coin, direction) 一已平仓 + 一活跃 → 两行，UM 骨架行挂活跃周期
   （normal + 活跃 avg/cycle），已平仓周期独立 no_um + cycle_closed_at（`test_merge_2b_*`）；无静默丢弃。
4. **场景用例**：A（同 cycle 加仓并入同行、起始时间=首次派发）、B/4（close 后重开两独立 cycle）、
   3（删任务重建仓未平复用 cycle）、5（同任务加仓同 cycle）——单测全过。
5. **close 契约**：幂等（重复不覆盖）、单向（NULL→值）、自带事务、unknown id noop——单测全过；
   grep 确认 `close_cycle` 调用点仅测试文件，**无任何生产触发接线**（无自动盯梢/核实端点）。
6. **回归**：指定 4 文件 214 passed；全量 1376 passed。
7. **范围核对**：`git status --short` 无 `frontend/**`、`backend/ledger_flow/**`、`backend/hedge_open_tasks/service.py`、
   `backend/app/server.py` 改动；`M frontend/index.html`/`frontend/self-check.js`/`docs/planning/ROADMAP.md` 为
   任务开始前已存在的规划期改动；任务一改动（`_SCHEMA` cycle 建表、`_migrate` cycle_id 加列、只读方法）保留未回退；
   未提交 git、未移动 HEAD、未对实盘库/交易所做任何写操作。

### 行为变化说明（对后续任务/实盘的影响）

- `prepare_attempt` 现在**自动分配 cycle**：任何新发单都会复用活跃周期或新建周期（写 `hedge_open_cycle` +
  `hedge_open_attempt.cycle_id`）。实盘服务若用新代码重启，发单即开始产生周期数据——这使实盘回填的
  「先建表后回填」时序更紧迫（回填防护会拒绝已含 cycle 数据的库；实盘库当前 0 周期行、52 attempt 无
  cycle_id，仍可回填）。
- `aggregate_positions` 输出新增 3 字段（additive）；`merge_positions` 匹配语义变化：同一 (coin, direction)
  多个周期桶时不再丢弃——这是 P0-1 修复，展示层（前端任务二）需按 cycle_closed_at 渲染「已平仓」。
- `close_cycle` 已定义但**未接线**；调用方是功能三（auto_close）/人工核实（manual_verify）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-core.handoff.md`（本交接件）
  2. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-table-backfill.handoff.md`（任务一）
  3. `backend/hedge_open_tasks/store.py`（周期方法 / prepare_attempt / aggregate_positions）
  4. `backend/hedge_open_tasks/domain.py`（merge_positions）
  5. `docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（§3.3-§3.6 已实现；功能二依据在 §3.7/§4 与 stage3 文稿）
  6. `docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能二统计，下一任务）
- 执行：Bookkeeper 核验本交接件与测试/范围，裁定 `test_hedge_cycle_backfill.py` 适配归属
- 关卡：核验通过后路由下一任务（功能二 stats 开发）
- 不能假设的事实：任务一与任务二均未提交（工作树改动，`delivery_sha` 均 pending）；`prepare_attempt` 已自动
  分配 cycle（新发单会产生周期数据）；`close_cycle` 未接线；前端未渲染周期字段；实盘库 schema 已迁移
  （0 周期行）但实盘回填未做、需 Human 单独授权并先备份。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hedge-position-cycle-v1-cycle-core
执行结果: completed（完成）
结果摘要: 功能一核心逻辑完成：发单分配（同事务、无孤儿）、聚合按周期拆桶+SQL-A 告警、merge P0-1 多周期匹配（已平仓+活跃两行）、close_cycle 契约（幂等单向自带事务、无触发接线）；新增 15 单测，指定 4 文件 214 passed，全量 1376 passed 无回归；未提交、未写实盘库。
产物: [backend/hedge_open_tasks/store.py, backend/hedge_open_tasks/domain.py, backend/tests/test_hedge_cycle_core.py, backend/tests/test_hedge_api.py, backend/tests/test_hedge_cycle_backfill.py, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-core.handoff.md]
检查结果: [分配（新建/复用/回滚无孤儿/close 后新 cycle）pass；聚合拆分（三周期字段+加权回归+SQL-A 告警）pass；merge 2b 两行输出（UM 挂活跃 normal、已平仓独立 no_um）pass；场景 A/B/3/4/5 pass；close 契约（幂等/单向/事务/无接线）pass；回归 214+1376 全绿 pass；范围外零改动 pass]
阻塞项: [none（一项待 Bookkeeper 裁定：test_hedge_cycle_backfill.py 因本任务行为变化做了最小适配，越出 Allowed Files 字面列表，断言未变）]
本地北京时间: 2026-08-05 15:20:12 CST
下一步模型: Bookkeeper（核验交付与范围，裁定回填测试适配归属）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-core.handoff.md（含本交接件引用文件）；执行：Bookkeeper 核验测试/范围并裁定 test_hedge_cycle_backfill.py 适配；关卡：核验通过后路由功能二 stats 开发
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
