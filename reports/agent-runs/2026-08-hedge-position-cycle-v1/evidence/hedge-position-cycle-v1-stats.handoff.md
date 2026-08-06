# Task Handoff: hedge-position-cycle-v1-stats

## Source Report (author-only; immutable after task end)

- task_id: `hedge-position-cycle-v1-stats`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-05 15:40 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，与任务一/二同基线；未移动 HEAD）
- delivery_sha: `pending`（未提交任何 commit，交付为工作树改动）

### 任务背景

功能二：持仓行三列 `accrued_funding` / `borrow_interest` / `net_pnl` 从占位 `"0"` 变为周期窗口真值
（`net_pnl = 资金费 + 利息`；纯读、现算、不写库）。依据：dispatch
`reports/agent-runs/_proposals/2026-08-hedge-position-cycle-v1-stats.dispatch.md`、stage3 文稿
`docs/planning/hedge-open-cycle-stage3-stats-dev.md`、设计 v1 §7。前置依赖（功能一剩余块 cycle-core）
已在本工作树完成（未提交），positions 输出已含 `cycle_id`/`cycle_opened_at`/`cycle_closed_at`——本任务读取其输出。

### 前置依赖成立证据

实盘服务（重启后新代码在跑）：`curl http://127.0.0.1:8787/api/hedge-open-positions` 输出 merged rows 含
`cycle_id: null, cycle_opened_at: null, cycle_closed_at: null`（旧代码无此三键）；单元/接线测试断言
`cycle_id is not None`（fill-all 后自动分配）。前置成立，未 blocked。

### 实际修改范围

1. `backend/ledger_flow/service.py`（只读路径，新增 3 方法）：
   - `sum_funding_by_symbol(symbol, start_ms, end_ms) -> str | None`：`um_income_rows` 中
     `income_type='FUNDING_FEE' AND symbol=? AND time_ms ∈ [start, end]` 的 `income` Decimal 合计；
     复用 `query_income_rows(limit=None)` + `domain._sum_amounts`（任一不可解析 → None，绝不部分相加）；
     无行 → `"0"`（真零）。
   - `sum_interest_by_asset(asset, start_ms, end_ms) -> str | None`：`interest_rows` 同规则。
   - `coverage_for_window(start_ms, end_ms)`：`_build_coverage` 的公开包装（gap-aware 判定权威不复制）。
   - 不新增 SQL、不动 store 写路径、不触碰 scheduler。
2. `backend/app/server.py`：
   - `import Decimal`；新增 `_now_us()` / `_iso_to_us()`（`us_to_iso` 反向解析）。
   - `_hedge_open_positions`：`merge_positions` 之后、`_send_hedge_open` 之前，对每个 merged row 现算三列：
     - 无 `cycle_id` / ledger 未注入 / `cycle_opened_at` 不可解析 → 三列 `None`（前端「暂无」），
       `stats_incomplete=False`；
     - 窗口 = `[cycle_opened_at, cycle_closed_at 或 now]`（us→ms 换算在查询层 `//1000`）；
     - `coverage_for_window(...).complete == False`（含窗口内 gaps）→ 三列 `None` + `stats_incomplete=True`，
       绝不把覆盖率不足窗口当真值；
     - 完整 → `accrued_funding`/`borrow_interest` = 真值；`net_pnl` = 两者 Decimal 之和；任一 None → `net_pnl=None`；
     - base_asset 组合根本地推导（`hedge_open_domain._merge_base_asset`，1000x 不自动对齐），不改 domain.py；
     - 保持纯读：不触发 ledger 刷新、不写 ledger、不发网络请求。
3. `frontend/index.html`（仅 renderHedgePositionsSection 相关）：
   - 新增 `statsCell`：`null/''` → 「暂无」；字符串（含 `"0"`）→ 数值（真零可见，P7 规则）；
   - 三列 `pendingCell` → `statsCell`；`net_pnl` 列按值正负着色（`classForSignedNumber`）；
   - markers 追加：`stats_incomplete` → 「统计区间不全」（title 说明非真值）；`cycle_closed_at` 非空 → 「已完全平仓」。
4. `frontend/self-check.js`：追加第 83 段断言（三列真值渲染、net_pnl 正值 positive 着色、「统计区间不全」+「已完全平仓」标记、三列 null → 暂无）。
5. 测试：
   - `backend/tests/test_ledger_flow_service.py` +5：funding 窗口/类型/symbol 过滤、不可解析→None、interest 窗口/资产过滤、不可解析→None、`coverage_for_window` gap-aware 包装（窗口起点早于 coverage → complete=False）；
   - `backend/tests/test_hedge_api.py` +4：真值（活跃窗口 0.1+0.3 / 利息 0.2 / net_pnl 0.6）、ledger 未注入 → 三列 None、coverage 缺失（interest 源失败）→ `stats_incomplete`、已平仓窗口 [opened, closed] 排除 closed 后到账；`_POSITION_KEYS` 追加 `stats_incomplete`；
   - `backend/tests/test_account_cache_refresh_v1.py`：`_CapHandler` 测试桩补 `ledger_flow_service = None` 类属性（与 `_Handler` 一致；`_RunStubService` 补 `private_client` 同款桩补齐）。

### wire 语义决策（重要，评审关注）

三列 wire 语义统一为：**`null` = 无统计（前端「暂无」），字符串（含 `"0"`）= 真值（真零可见）**。
原 aggregate 输出三列恒 `"0"` 占位（store 层禁止改动），server 接线把无统计行（无周期 / ledger 未注入 /
coverage 不足 / 窗口起点不可解析）三列统一改写为 `None`——避免前端无法区分「占位 0」与「真零 0」；
符合 stage3 §3.1「None → 暂无、真零 → "0"」与 P7「绝不把未知渲染成 0」。

### 测试结果

- 全量：`timeout 400 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1385 passed**（89s，无回归）。
- 前端：`node frontend/self-check.js` → **137 PASS，0 FAIL**（含新 83 段）。
- 指定单测文件：test_ledger_flow_service.py 25 passed（+5）、test_hedge_api.py 39 passed（+4）。

### 验收逐项

1. **前置依赖成立**：实盘 positions 响应含周期三字段（null 值，因实盘周期数据为 0）+ 测试断言非 None——pass。
2. **汇总方法**：窗口过滤 / income_type 过滤 / symbol·asset 过滤 / 不可解析→None / 无行→"0"——单测全过；
   ms/us 换算在 server 层（`_iso_to_us` + `//1000`），接线测试覆盖。
3. **三列真值**：活跃周期窗口求和（0.4/0.2/0.6）pass；已平仓窗口 [opened, closed] 排除 closed 后到账（0.1 计、0.5 排除）pass。
4. **诚实降级**：ledger 未注入 → 三列 None pass；coverage 缺失 → `stats_incomplete=True` + 三列 None pass；
   任一不可解析 → sum 返回 None → `net_pnl=None`（service 单测 + server 逻辑）pass。
5. **前端**：self-check 137 PASS（三列真值、正负着色、「统计区间不全」标记）pass。
6. **回归**：pytest 1385 + self-check 137 全绿。
7. **范围核对**：`git status --short` 本任务改动仅 `backend/ledger_flow/service.py`、`backend/app/server.py`、
   `frontend/index.html`、`frontend/self-check.js`、`backend/tests/test_hedge_api.py`、
   `backend/tests/test_ledger_flow_service.py`、`backend/tests/test_account_cache_refresh_v1.py`；
   `backend/hedge_open_tasks/store.py`/`domain.py` 的 M 为**功能一 cycle-core 未提交改动**（本任务未触碰，
   只读）；无 `backend/hedge_open_tasks/service.py`、`backend/ledger_flow/store.py`、`backend/ledger_flow/domain.py`、
   `data/*.sqlite3` 改动；未提交 git、未移动 HEAD、未对实盘库/交易所做任何写操作（实盘 `cycle_rows=0`）。

### 行为变化说明（对实盘/后续影响）

- 前端三列渲染升级：无周期数据行（实盘当前全部行，三列 null）仍显示「暂无」，与现状一致；有周期 + 真值后
  显示数值与正负着色——**要看到真值，仍依赖实盘周期数据**（回填 + 新发单分配）。
- 实盘 ledger-flow.sqlite3 的 coverage 由 hourly scheduler 维护；周期窗口统计首次点亮前建议人工核对
  coverage 是否覆盖 [最早周期 opened, now]（实盘回填后）。
- 功能三（结算日志/平仓执行）将复用同一汇总方法。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-stats.handoff.md`（本交接件）
  2. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-core.handoff.md`（功能一剩余块）
  3. `backend/ledger_flow/service.py`（sum_* / coverage_for_window）
  4. `backend/app/server.py`（_hedge_open_positions 接线）
  5. `frontend/index.html`（renderHedgePositionsSection：statsCell / markers）
  6. `docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能二依据；功能三需另开 dispatch）
- 执行：Bookkeeper 核验本交接件与测试/范围
- 关卡：核验通过后 Human 决定下一步（实盘回填授权 / 功能三 dispatch / 统一 review-1+review-2）
- 不能假设的事实：任务一/二/三均未提交（工作树改动，delivery_sha 均 pending）；实盘库周期数据为 0
  （positions 周期字段 null）；三列 wire 语义 null=暂无/字符串=真值；`prepare_attempt` 已自动分配 cycle
  （新发单产生周期数据）；`close_cycle` 未接线；实盘回填未做、需 Human 单独授权并先备份。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hedge-position-cycle-v1-stats
执行结果: completed（完成）
结果摘要: 功能二完成：ledger 三个只读汇总方法（funding/interest 窗口求和 + coverage 包装）、server 组合根接线三列真值（窗口=周期起止或 now，net_pnl=两者之和，任一不可解析→暂无）、诚实降级（无周期/无 ledger/coverage 不足→None+统计区间不全）、前端三列真值渲染+正负着色+已平仓标记；全量 1385 passed、self-check 137 PASS；未提交、未写实盘。
产物: [backend/ledger_flow/service.py, backend/app/server.py, frontend/index.html, frontend/self-check.js, backend/tests/test_ledger_flow_service.py, backend/tests/test_hedge_api.py, backend/tests/test_account_cache_refresh_v1.py, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-stats.handoff.md]
检查结果: [前置依赖（positions 含周期字段）pass；汇总方法（窗口/类型/不可解析→None）pass；三列真值（活跃窗口求和 + 已平仓窗口排除 closed 后）pass；诚实降级（无 ledger/coverage 不足/部分相加禁止）pass；前端（self-check 137 含新断言）pass；回归 1385+137 全绿 pass；范围外零改动 pass]
阻塞项: [none]
本地北京时间: 2026-08-05 15:40:00 CST
下一步模型: Bookkeeper（核验交付与范围）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-stats.handoff.md（含引用文件）；执行：Bookkeeper 核验三列 wire 语义与测试/范围；关卡：核验通过后由 Human 决定下一步（实盘回填授权 / 功能三 dispatch / 统一 review-1+review-2）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
