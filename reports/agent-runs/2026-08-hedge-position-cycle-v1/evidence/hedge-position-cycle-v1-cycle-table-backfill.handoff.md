# Task Handoff: hedge-position-cycle-v1-cycle-table-backfill

## Source Report (author-only; immutable after task end)

- task_id: `hedge-position-cycle-v1-cycle-table-backfill`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-05 14:56 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，任务开始前已提交基线）
- delivery_sha: `pending`（本任务未提交任何 commit、未移动 HEAD；交付为工作树改动）

### 任务背景

实现「持仓周期轻量表」第一块交付：建表 + 迁移 + 内部数据初始化（回填）+ 测试库回填验证与前后行数核对。依据：dispatch
`reports/agent-runs/_proposals/2026-08-hedge-position-cycle-v1-cycle-table-backfill.dispatch.md`、stage2 文稿
`docs/planning/hedge-open-cycle-stage2-cycle-dev.md` §3.1/§3.2/§3.7/§4、设计 v1 `docs/planning/hedge-open-position-cycle-v1.md` §3/§6。
不做 prepare_attempt 分配、aggregate 拆分、merge 匹配、close_cycle（后续任务，未实现）。

### 实际修改范围（3 个文件，均在 dispatch Allowed Files 内）

1. `backend/hedge_open_tasks/store.py`
   - `_SCHEMA` 末尾追加 `hedge_open_cycle` 建表（DDL 逐字照 stage2 §3.1，`IF NOT EXISTS` 幂等）+ `idx_cycle_active` 索引；
   - `_migrate` attempt 迁移段追加：`PRAGMA table_info` 探测 + `ALTER TABLE hedge_open_attempt ADD COLUMN cycle_id TEXT` +
     `CREATE INDEX IF NOT EXISTS idx_attempt_cycle`；**建表只在 `_SCHEMA`，`_migrate` 不重复建表**（stage2 §3.2 核对点）；
   - positions 段新增只读方法 `get_cycle_by_id(cycle_id)` / `list_cycles()`（最小集，未加任何写方法）。
2. `scripts/backfill-cycles.py`（新增）：数据源 = 开单任务卡（`hedge_open_task` + `hedge_open_attempt` + `hedge_open_leg`），
   每个 `(coin, direction)` 一条周期行；`opened_at_us` = 组内最早成功腿 `dispatched_at_us`（无成功腿取最早 attempt
   `created_at_us`；仍无则不建周期行）；`closed_at_us`/`close_reason` 全 NULL；`first_task_id`/`last_task_id` = 组内最早/最晚
   任务 id（按 `created_at_us`）；`attempt.cycle_id` 按 task 所属 `(coin, direction)` 回填。CLI：`--db <path>`（默认实盘库路径，
   仅 dry-run 只读）、`--split "SYMBOL,DIRECTION,ISO时间"`（人工分段点，可多次，按任务创建时间切两段）、**默认 dry-run 输出计划
   （SQLite `mode=ro` 只读打开，不写任何字节），`--apply` 才写库**（先构造 `HedgeOpenStore` 幂等迁移，再单事务插入+回填）、
   `--audit <path>`（与 `--apply` 同用，回填 SQL + 前后行数核对 JSON 审计落盘）。重复回填防护：目标库已有周期行或
   `attempt.cycle_id` 非空时拒绝（exit 2）。
3. `backend/tests/test_hedge_cycle_backfill.py`（新增 10 用例）：迁移幂等（建表字段/加列/双索引/重复构造）、只读方法、
   dry-run 字节级只读证明、apply 回填断言、无成功腿取 attempt created、无 attempt 组不建周期行、重复回填防护、`--split` 分段、
   `--audit` 审计、无周期 schema 时 dry-run 可用（模拟未迁移实盘副本）。

### 测试结果

- dispatch 指定命令：`python3 -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_backfill.py -q`
  → **57 passed**（既有 47 + 新增 10）。
- 全量回归：`timeout 300 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1361 passed**（92s，无回归）。

### 测试副本回填验证（命令与结果）

- 副本：`cp -p data/hedge-open-tasks.sqlite3 data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452`
  （`PRAGMA integrity_check` → `ok`；实盘库本体未写）。
- dry-run：`python3 scripts/backfill-cycles.py --db <副本>` → 周期行 **9**，每条 symbol/direction/opened_at/closed_at=NULL；
  `attempt.cycle_id 将回填：52 条`。
- apply：`python3 scripts/backfill-cycles.py --db <副本> --apply --audit <副本>.audit.json` →
  `回填完成：周期行 0 -> 9，attempt.cycle_id 0 -> 52（更新 52 条）`；rc=0。
- 审计落盘：`data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452.audit.json`
  （`before.cycle_rows=0` / `before.attempts_with_cycle_id=0`；`after.cycle_rows=9` / `after.attempts_with_cycle_id=52`；
  `diff: cycle_rows "0 -> 9"`、`attempts_with_cycle_id "0 -> 52"`、`attempts_updated 52`；SQL 61 行 = 9 INSERT + 52 UPDATE）。
- 回填后核对（只读查询）：
  - `hedge_open_cycle` 恰 9 行，`closed_at_us`/`close_reason` 全 NULL（`closed_not_null=0`）；
  - 成功腿（`CAST(cumulative_base_qty AS REAL) > 0`）所属 attempt 无 NULL cycle_id（`0`）；attempt 无 NULL cycle_id 残留（`0`）；
  - `opened_at_us` 与 stage2 §3.7 实测表秒级一致（UTC ISO）：
    NOMUSDT=2026-07-27T14:14:29、RSRUSDT fwd=2026-07-30T15:39:21、COOKIEUSDT=2026-07-30T16:00:06、
    RSRUSDT rev=2026-07-30T16:16:38、SNXXUSDT=2026-08-01T11:37:02、MUUUSDT=2026-08-02T09:35:56、
    KORUUSDT=2026-08-03T01:22:29、FFUSDT=2026-08-03T03:15:54、HFTUSDT=2026-08-05T02:47:41。
- 重复构造 store（副本上）：`HedgeOpenStore('<副本>')` 重建成功，`list_cycles()`=9，`get_cycle_by_id` 正常，不重复加列/建表。

### 范围核对

`git status --short` 新增改动仅：`M backend/hedge_open_tasks/store.py`、`?? backend/tests/test_hedge_cycle_backfill.py`、
`?? scripts/backfill-cycles.py`。其余已跟踪改动（`docs/planning/ROADMAP.md`、`frontend/index.html`、`frontend/self-check.js`、
`docs/planning/hedge-open-cycle-*`、`docs/planning/hedge-open-position-cycle-v1*`）均为本任务开始前已存在的规划期改动，本任务未触碰。
无 `backend/app/server.py`、`backend/hedge_open_tasks/domain.py`、`backend/hedge_open_tasks/service.py`、`frontend/**`（本任务）、
`data/ledger-flow.sqlite3` 改动；未提交 git、未移动 HEAD。

### 重要事实（需 Bookkeeper/Human 知悉）

1. **实盘库 schema 已被迁移（非本任务回填数据）**：2026-08-05 14:54 发现实盘库 `data/hedge-open-tasks.sqlite3` 已包含
   **空** `hedge_open_cycle` 表（0 行）+ `hedge_open_attempt.cycle_id` 列 + `idx_attempt_cycle` 索引；`attempts_with_cycle_id=0`、
   无任何回填数据。本任务所有命令均未以写模式打开实盘库（逐条核对：sqlite3 均 `-readonly` / `mode=ro` URI；pytest 全用
   `tmp_path`；冒烟用临时目录）。最可能原因：操作员用新代码重启了运行中的服务（`HedgeOpenStore` 构造自动幂等执行
   `_SCHEMA` + `_migrate`，服务启动即迁移实盘库——这正是设计预定的迁移时机，stage2 §4 步骤 2「先测试库，后实盘」中的实盘
   部署步）。影响：纯增量 DDL，0 数据行变化，行为无变化（新代码 prepare_attempt 尚不写 cycle_id，保持 NULL）；重复迁移幂等。
   此为范围偏差（任务约定「本次不写实盘库」），如实上报，由 Bookkeeper/操作员确认是否已发生服务重启。
2. 实盘回填（`--apply` 于实盘库）**未执行**，按设计需 Human 单独授权（本任务只跑了测试副本）。
3. 实盘库被运行中服务持续写入（14:54 大小/mtime 变化），属既定运行前提（PROJECT_STATE.md「Start gate 常开、系统实盘运行」），非本任务导致。

### 未完成事项 / 后续

- 全部在「不在本次范围」：`prepare_attempt` 周期分配（stage2 §3.4）、`aggregate_positions` 按周期拆桶（§3.5）、
  `merge_positions` 周期粒度匹配（P0-1，设计 v1 §5.4）、`close_cycle` 方法与接线（§3.3/§3.6）。实现前请读取 stage2 文稿相应章节。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-table-backfill.handoff.md`（本交接件）
  2. `backend/hedge_open_tasks/store.py`（`_SCHEMA` 末尾 cycle 建表、`_migrate` attempt 段、positions 段只读方法）
  3. `scripts/backfill-cycles.py`（回填逻辑与数据映射）
  4. `docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（§3.3–§3.6 为后续任务依据）
  5. `data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452`（已回填测试副本，只读参考）
  6. `data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452.audit.json`（回填审计）
- 执行：Bookkeeper 核验回填结果（对照本交接件命令与 diff）与范围核对，确认实盘 schema 迁移事实
- 关卡：核验通过后路由后续任务（prepare_attempt 分配 → aggregate 拆分 → merge 匹配 → close_cycle 预留）
- 不能假设的事实：实盘库 schema 已含 `hedge_open_cycle` 表与 `cycle_id` 列（0 数据行）；实盘回填未做、须 Human 单独授权；
  本任务未提交任何 commit（`delivery_sha` 为 pending）；`hedge_open_attempt` 无 NULL cycle_id 残留仅对已回填的测试副本成立。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hedge-position-cycle-v1-cycle-table-backfill
执行结果: completed（完成）
结果摘要: 建表+迁移+回填脚本+10 单测+测试副本验证全过：9 周期行 opened_at 与预期秒级一致、closed 全 NULL、52 attempt 全覆盖、审计 0→9/0→52；全量回归 1361 passed；实盘库未回填、未提交。发现实盘 schema 已被迁移（空表+cycle_id 列，0 数据），疑似操作员重启服务所致，已如实上报。
产物: [backend/hedge_open_tasks/store.py, scripts/backfill-cycles.py, backend/tests/test_hedge_cycle_backfill.py, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-table-backfill.handoff.md, data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452, data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452.audit.json]
检查结果: [建表/迁移幂等 pass；dry-run 计划 9 行 pass；apply 后 9 行且 closed 全 NULL pass；opened_at 与预期表秒级一致 pass；成功腿 attempt cycle_id 全覆盖无 NULL 残留 pass；前后行数核对 0→9/0→52 审计落盘 pass；指定测试 57 passed + 全量 1361 passed pass；范围外零改动 pass]
阻塞项: [none（一项待 Bookkeeper 核实：实盘库 schema 迁移事实与原因）]
本地北京时间: 2026-08-05 14:56:39 CST
下一步模型: Bookkeeper（核验回填结果与范围，确认实盘 schema 迁移事实）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-table-backfill.handoff.md（含其引用的测试副本与审计文件）；执行：Bookkeeper 核验回填结果与范围核对；关卡：核验通过后路由后续任务（prepare_attempt 分配 / aggregate_positions 拆分 / merge_positions 匹配）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
