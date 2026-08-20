# Task Handoff: 31-phase1-backend-stub-glm

## Source Report (author-only; immutable after task end)

- task_id: `31-phase1-backend-stub-glm`
- role: `Implementer`
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-19-hedge-order-fee-cost-v1`
- created_at: 2026-08-20 10:43 CST
- base_sha: `aa2b9cf6a005728b1d00dec22a48f78c96d7cae4`（`git rev-parse HEAD`）
- delivery_sha: pending（dispatch 禁止本任务 commit；交付提交由后续流程落盘后由 Bookkeeper 解析）

### 任务背景

阶段一后端加列与占位（10-design r4 §3 D1/D11、§5.1、§5.2）：在
`backend/hedge_open_tasks/store.py` 完成 `hedge_open_leg` 4 列与
`hedge_open_cycle_close_log` 3 列的加列迁移与映射，`aggregate_positions`
返回 3 个冻结键的占位值，`insert_close_log` 写入新列（未传入默认不全），
并同步 `_POSITION_KEYS` 与 `_MONEY_NAMES`。本任务只建列、映射与占位，
不做真实费用聚合（T2 后半）、不做回补（T3）、不做实时写入（T5）、不做前端（T1/T4）。

### 实际修改范围（全部在 dispatch Allowed Files 内）

1. `backend/hedge_open_tasks/store.py`
   - `_SCHEMA`：`hedge_open_leg` 建表加 `fee_bnb_qty` / `fee_bnb_price` /
     `fee_other_qty` / `fee_other_asset`（均 TEXT）；`hedge_open_cycle_close_log`
     建表加 `trading_fee_usdt` TEXT、`fee_bnb_qty` TEXT、
     `trading_fee_incomplete INTEGER NOT NULL DEFAULT 1`（D11：旧行默认不全，禁止 DEFAULT 0）。
   - `_migrate`：同列进 `leg_additions` 与 close_log 加列循环，沿用仓内
     `PRAGMA table_info` 集合 + `if col not in cols: ALTER TABLE … ADD COLUMN`
     既有幂等守卫模式。
   - `_row_to_leg`：映射 4 个新列（`row["fee_bnb_qty"]` 等，读出即线上腿 dict 键）。
   - `insert_close_log`：INSERT 列表与参数扩 3 列；未传入时
     `trading_fee_usdt=None`、`fee_bnb_qty=None`、`trading_fee_incomplete=1`
     （「还没算」≠ 0，D10/D11）。
   - `aggregate_positions`：每个 position dict 增加占位三键
     `"trading_fee_usdt": None, "fee_bnb_qty": None, "trading_fee_incomplete": True`，
     经 `merge_positions`（`dict(bucket)` 原样保留）与 `server.py` handler
     透传到 `/api/hedge-open-positions` wire 契约。
   - dispatch 提及的 `_row_to_close_log` 在 store.py 中不存在：`list_close_logs`
     为 `SELECT *` + `dict(row)`，列名即线上键名（10-design §2.3 已载明），
     新列自动出现在 `GET /api/hedge-open-close-logs`，未新造映射函数。
2. `backend/tests/test_hedge_api.py`：`_POSITION_KEYS` 增 3 键。
3. `backend/tests/test_hedge_purity.py`：`_MONEY_NAMES` 增
   `fee_bnb_price` / `fee_bnb_qty` / `fee_other_qty` / `trading_fee_usdt`。
4. `backend/tests/test_hedge_store.py`（dispatch 条件允许项，已动用）：新增 3 条测试
   - `test_fee_columns_added_and_idempotent`：DROP COLUMN 模拟旧库 → 重开补列
     （走真实 ALTER 路径）→ 再开幂等；断言 `trading_fee_incomplete` PRAGMA
     `(notnull=1, default='1')`。
   - `test_row_to_leg_maps_fee_columns`：UPDATE 四列后经 `list_legs_for_attempt`
     （`_row_to_leg`）读回原值。
   - `test_insert_close_log_fee_defaults_and_round_trip`：未传入默认
     `1/NULL/NULL`；传入 `0/"1.23"/"0.5"` 原样落库。

### 命令与结果

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_hedge_api.py
  backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_store.py
  backend/tests/test_hedge_purity.py -q`
  → **1 failed, 146 passed**。唯一失败为基线既有（见下）。
- 佐证消费方无破坏：`pytest backend/tests/test_hedge_cycle_close.py
  backend/tests/test_hedge_cycle_core.py -q` → 89 passed；
  `pytest backend/tests/test_positions_merge.py
  backend/tests/test_account_cache_refresh_v1.py -q` → 120 passed。
- 基线失败复证：`git stash` 后在干净 HEAD `aa2b9cf` 上
  `pytest backend/tests/test_frontend_field_binding.py -q` →
  **1 failed, 13 passed**（同一用例、同一锚点错误），`git stash pop` 恢复。

### 既有基线失败（范围外，须 Bookkeeper 裁定）

`test_frontend_field_binding.py::test_expanded_log_poll_includes_all_running_tasks_and_retains_non_running_expanded`
在 base_sha `aa2b9cf` 即失败：测试 `text.index("async function loadHedgeTasks()")`
（test_frontend_field_binding.py:266）锚点写死无参签名，而
`frontend/index.html:5607` 实际为 `async function loadHedgeTasks(opts) {`。
`frontend/index.html` 与 `backend/tests/test_frontend_field_binding.py` 均不在本任务
Allowed Files（后者仅列为只读 Inputs），故未修。该失败使 dispatch 验收检查 4 的
字面「全绿」不成立，已在回执 `检查结果` 标 `contested` 并附本证据；该锚点问题
同样会影响 T1 前端任务的验收基线，派发前宜先处置。

### 不能假设的事实 / 交接边界

- wire 上的三个持仓新键**只保证出现在有任务记录的行**（bucket 行）；
  `domain._merge_empty_bucket_row` 构造的 no_task 行（UM 有仓、无本地任务）不含
  这 3 键——`backend/hedge_open_tasks/domain.py` 不在本任务 Allowed Files。前端
  必须把「键缺失」当「不全/—」处理；若要全行键集一致，归 T2 后半/T4。
- `GET /api/hedge-open-close-logs` 的旧行与既有 settle 调用方
  （`service.py` `_settle_cycle…` 不传新键）新写入的行均为
  `trading_fee_usdt=NULL, fee_bnb_qty=NULL, trading_fee_incomplete=1`——
  这是诚实默认，不是缺陷；回补后也不改写旧 close_log 行（10-design §5.2/§6）。
- `_MONEY_ZERO_SCOPE` 仍只有 `hedge_open_tasks` 与 `live_hedge_executor`；
  T3 建 `scripts/backfill-leg-fees.py` 时必须把脚本路径加进扫描范围
  （10-design §4.2），本任务未动。
- `hedge_open_leg` 的 T1 旧库重建分支（cumulative_quote_amt NOT NULL 探针触发的
  `hedge_open_leg__new` 重建）不带新 4 列，与既有 `avg_price` 列同暴露面；该分支
  仅对 2026-07-28 前的 legacy 库可达，生产库早已迁移，实际不可触发，未改。

### 未完成事项（按设计属后续任务，非本任务遗漏）

- T2 后半：`aggregate_positions` / `insert_close_log` 的真实折 U 聚合（只汇总
  open 腿；不全时 `trading_fee_usdt` 与 `fee_bnb_qty` 一并 NULL）。
- T3：`scripts/backfill-leg-fees.py` 回补（Human 另授权才打 live 库）。
- T5：两写入站点（`resolve_attempt` / `resolve_leg_from_query` 终态 commit 后）
  各至多 1 次成交明细 GET 与 `update_leg_fees`。
- T1/T4：前端展示与解除 fake。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md`
  2. `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
- 执行：Bookkeeper 核验阶段一后端加列与占位交付（复跑上方 pytest 命令与
  PRAGMA 断言），裁定 `contested` 项（基线锚点漂移的处置归属），随后派发阶段一
  前端展示任务（32-phase1-frontend-ui-kimi）。
- 关卡：Human 启动 kimi 窗口执行前端展示任务。
- 不能假设的事实：前端展示任务的验收基线里 `test_frontend_field_binding.py`
  有一条 base 即红的锚点失败（见上），须先裁定；持仓三新键的占位值为
  `None/None/True`，前端不得把 null 渲染成 0。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 31-phase1-backend-stub-glm
执行结果: completed（完成）
结果摘要: store.py 完成 hedge_open_leg 4 列与 close_log 3 列（trading_fee_incomplete NOT NULL DEFAULT 1）幂等加列迁移，_row_to_leg 映射、insert_close_log 默认写不全（1/NULL/NULL）、aggregate_positions 冻结 3 键占位（None/None/True）；_POSITION_KEYS 与 _MONEY_NAMES 同步，新增 3 条 store 测试。指定四文件 146 passed，唯一失败为 base 即存在的 index.html 锚点漂移（stash 干净 HEAD 复证），判 contested。
产物: [backend/hedge_open_tasks/store.py, backend/tests/test_hedge_api.py, backend/tests/test_hedge_purity.py, backend/tests/test_hedge_store.py, reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md]
检查结果: [加列迁移幂等（DROP 模拟旧库补列+再开跳过+DEFAULT 1 断言）pass；_row_to_leg 映射与 insert_close_log 默认/回写（新增 2 测试）pass；aggregate_positions 占位 3 键且 _POSITION_KEYS 与 wire 全等 pass；_MONEY_NAMES 增 4 字段且 money-zero 全绿 pass；指定四测试文件 146 passed，周期/合并消费方 209 passed 佐证 pass；dispatch 验收检查 4「全绿」contested——唯一失败 test_frontend_field_binding.py::test_expanded_log_poll_includes_all_running_tasks_and_retains_non_running_expanded 在 base_sha aa2b9cf 即失败（git stash 干净 HEAD 复跑同败 1 failed/13 passed；frontend/index.html:5607 实为 loadHedgeTasks(opts) 而测试锚点写死 loadHedgeTasks()，两文件均不在本任务 Allowed Files），详见 handoff「既有基线失败」节；交接件 create-only（预检 ABSENT 复核成立）pass]
阻塞项: [none]
本地北京时间: 2026-08-20 10:43:00 CST
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md；执行：核验阶段一后端加列与占位交付并裁定 contested 基线锚点失败，派发阶段一前端展示任务（32-phase1-frontend-ui-kimi）；关卡：Human 启动 kimi 窗口执行前端展示
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- Bookkeeper: `gemini-3.7-flash`（provider `google`，窗口 `agy`）
- 核验时间（本地北京时间）：2026-08-20 10:45:00 CST
- 核对的 status revision：`10`（`phase=implementation`、`current_task.state=dispatched`）
- source_sha256（`BOOKKEEPER_APPEND_ONLY` 标记前字节，UTF-8）：`6947ce22b25ec87e4314d8b7f18a469928557e8974391c2a54509a20d4ebe5bc`
- 源边界复核：源区块收口于 Human Brief 闭合代码块（`...[/TASK_RESULT]\n\n`），标记独占一行。
- 核验结论：**通过核验，采信交付与 contested 裁定**。
  1. **修改范围合规**：修改文件严格受限于 dispatch 声明的 `store.py`、`test_hedge_api.py`、`test_hedge_purity.py`、`test_hedge_store.py`；
  2. **create-only 成立**：本交接件在预检时为 ABSENT，本次任务新建；
  3. **加列与占位有效**：
     - `hedge_open_leg` 增加 4 列与 `close_log` 增加 3 列（`trading_fee_incomplete DEFAULT 1`）幂等迁移通过，新增 3 条 store 测试全部 pass；
     - `aggregate_positions` 返回占位三键（`None/None/True`），`_POSITION_KEYS` 集合与线上 wire 完全一致；
     - `_MONEY_NAMES` 新增 4 个字段，money-zero 扫描测试通过；
  4. **contested 项裁定（采信）**：
     - 被质疑项：验收检查 4「测试全绿」；
     - 事实核实：经 `git log -L` 复核，`test_frontend_field_binding.py:266` 锚点 `loadHedgeTasks()` 与 `index.html:5607` 的 `loadHedgeTasks(opts)` 漂移早于 `base_sha aa2b9cf`（在 `dfd38a6` 引入），属于 `pre-existing-independent` 既有历史缺陷，且两文件均不在本任务 Allowed Files；
     - 裁定结论：**采信 contested 质疑，不计入返工，`rework_count` 保持为 0**。建议在后续阶段（如 T1/T4）顺带修正该单测锚点。
- 可复现命令（核验脚本）：
  `python3 -c "import hashlib;raw=open('reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/31-phase1-backend-stub-glm.handoff.md','rb').read();m=b'<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->';print(hashlib.sha256(raw.split(m)[0]).hexdigest())"`
- 后续状态：提交本交付 commit，更新 `status.json` 至 `revision=11`，派发阶段一前端展示任务 `32-phase1-frontend-ui-kimi`。

## Errata (append-only)

（暂无。）

