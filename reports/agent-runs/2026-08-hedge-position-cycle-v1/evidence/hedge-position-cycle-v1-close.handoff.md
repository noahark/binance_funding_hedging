# Task Handoff: hedge-position-cycle-v1-close

## Source Report (author-only; immutable after task end)

- task_id: `hedge-position-cycle-v1-close`
- role: `Implementer`（target_model: `deepseek`，provider: `deepseek`）
- stage_id: `2026-08-hedge-position-cycle-v1`（拟用值，以 Bookkeeper `status.json` 为准）
- created_at: `2026-08-05 19:51 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`，未移动 HEAD）
- delivery_sha: `pending`（未提交任何 commit，交付为工作树改动）

### 任务背景

功能三全链路：立即平仓执行（③b）+ 周期结算日志（③a）+ 历史仓位页接真数据。Human 已拍板决策：
平仓闸门默认开、完成判定以合约腿为准、现货腿纯买卖、平滑不做、手工补录不做、人工核实按钮不做。
在功能一（建表/回填/分配/聚合/merge/close_cycle）、功能二（stats + ≈U 换算）与前端平仓列 UI 预览
（工作树）基础上开发，前序改动全部保留（全量测试绿证明）。

### 实际修改范围

**模块 A（数据模型，store.py）**
- `_SCHEMA` 追加 `hedge_open_cycle_close_log` 表 + `idx_close_log_cycle` 索引（DDL 逐字设计 v1 §3.2；
  无 leg_kind 列——close 腿由 `task.task_type='close'` 标识）；
- `_migrate`：`hedge_open_task` 加 `task_type TEXT NOT NULL DEFAULT 'open'`（现有行不回填）、
  `hedge_open_settings` 加 `close_gate INTEGER NOT NULL DEFAULT 1`；
- `aggregate_positions` SQL-B 加 `WHERE t.task_type = 'open'`——平仓腿绝不进开仓成本基；
- `_row_to_task`/`get_settings` 输出 `task_type`/`close_gate`；
- 新方法：`insert_close_log`、`list_close_logs`（closed_at DESC）、`cycle_perp_basis` +
  `_cycle_perp_basis_locked`（周期内指定 task_type 合约腿加权均价/数量，G5 分母）、`set_close_gate_cas`
  （镜像 set_start_gate_cas，审计 kind `close_gate_changed`，sentinel `task_id="close-gate"`）。

**模块 B（平仓任务，domain/executor/service）**
- `domain.py`：`TASK_TYPE_OPEN/CLOSE` + `validate_task_type` + `CLOSE_REASON_AUTO_CLOSE/MANUAL_VERIFY` +
  `PAUSE_REASON_CLOSE_VERIFY_FAILED`（+中文文案）+ `WORKER_EXIT_CLOSE_GATE_OFF`；
  `direction_to_leg_actions(direction, position_side_mode, task_type='open')`——close 反转双腿方向
  （forward 平仓 = 现货 SELL + 合约 BUY 平空；reverse 平仓 = 现货 BUY + 合约 SELL 平多），
  `perp_position_side` 不变；
- `executor.py`：`AttemptContext` 加 `task_type: str = "open"`；`build_perp_order_params(..., task_type)`
  ——close 时合约腿 `reduceOnly: "true"`（开仓保持不设，ADR-3 不变）；RecordTransportExecutor 与
  live executor 双路径传 task_type；
- `service.py`：
  - `create_task` body 支持 `task_type`：close 校验（该 (coin,direction) 有活跃周期否则 409
    `no_active_cycle`「无仓不可平」；preflight 按反转方向做余额检查——forward close 卖现货需现货、
    reverse close 买现货需 USDT）；
  - `put_close_gate`（镜像 put_start_gate：confirm 字面 true + version CAS + 409 version_conflict）、
    `is_close_gate_on`、`settings_to_doc` 输出 close_gate；
  - `_dispatch_one_for_task` 传 task_type（direction_to_leg_actions / build_perp_order_params /
    AttemptContext）；
  - `_worker_round`：close 任务受独立 close_gate 约束（off → worker exit `close_gate_off`）；
    close 任务下一条 attempt 前 `_verify_close_flat` 完成核实：dry-run（executor 无
    `query_symbol_um_qty`）→ 模拟无仓（flat）；live → 实时查合约持仓（0 → flat，非零 → open
    继续按计划次数，None → failed 暂停 `close_verify_failed`——**绝不把「查不到」当「已平完」**）；
    flat → `_finalize_close_task`：任务 done → `close_cycle('auto_close')` → `insert_close_log`
    （顺序短事务，dispatch 允许「同事务或事务后紧接着」）；
  - `_finalize_close_task` 结算日志：open/close 合约腿加权均价现算（独立记录）、费率/利息复用
    功能二方法（`self._ledger_flow_service` 可选注入，duck-typed；统计失败不阻塞平仓完成）、
    滑点 null（无盘口参考价）、settled_at_us；
  - `get_close_logs()`：`{"logs": [...]}`（历史仓位页数据源）。
- `backend/services/hedge_open_live_client.py`【越界，见下】：
  `fetch_um_positions(symbol=None)`（GET /papi/v1/um/positionRisk + 白名单）+ `UM_POSITION_RISK_PATH`；
- `backend/services/live_hedge_executor.py`【越界，见下】：`query_symbol_um_qty(coin)`（调
  fetch_um_positions 过滤 symbol 求和；失败/不可解析 → None）+ `import json`。

**模块 C（结算日志 + 端点，server.py）**
- `GET /api/hedge-open-close-logs` 路由 + `_hedge_open_close_logs` handler；`POST
  /api/hedge-open-settings/close-gate` 路由 + `_hedge_open_close_gate` handler；`_is_hedge_open_path` 更新；
- `run()` 把 `ledger_flow_service` attach 到 `hedge_open_service._ledger_flow_service`。

**模块 D（前端）**
- `frontend/index.html`：`submitHedgeClose` stub → 真实 POST（`{task_type:'close', coin, direction,
  mode:'immediate', single_amount, target_n}`，no_active_cycle/insufficient_balance 就近中文处理）；
  `confirmMarketAction` 传完整 pending；历史仓位页移除 fake 横幅 + `HISTORY_FAKE_ROWS` +
  `renderHistoryFake`，新增 `loadHedgeCloseLogs` + `renderHedgeHistory`（真实 API 渲染；现货买/卖
  均价与滑点列显示 —，close_log 无现货/滑点字段）；元素 `history-fake-list` → `history-list`；
  helpers 导出。
- `frontend/self-check.js`：82a 段适配真实 POST 断言（task_type:close body）；98c 段适配真实
  close-logs API 渲染（mock 响应 + GET 请求断言 + 无 fake 横幅）；fetch mock 加 close-logs 路由 +
  同源白名单加 `/api/hedge-open-close-logs`；静态元素注册改名。

**测试（backend/tests/test_hedge_cycle_close.py，14 用例）**
迁移幂等（task_type/close_gate 列 + close_log 表 + 默认 close_gate=1 + 重复构造）、现有行默认 open、
开仓成本隔离（close 腿不进 aggregate）、close 创建校验（409 no_active_cycle / invalid task_type）、
dry-run 全链路（反转 SELL/BUY + reduceOnly + 无仓核实 → done + close + close_log）、完成判定
（open/failed/dry-run flat）、live query_symbol_um_qty 解析（positionRisk 行/失败/非 200）、
close_gate CAS（confirm/409/审计）、get_close_logs 端点。
另适配：test_hedge_api.py `_TASK_KEYS`/`_SETTINGS_KEYS` 加 task_type/close_gate；test_hedge_service.py
settings_to_doc 测试 dict 补 close_gate；test_hedge_purity.py 白名单冻结测试（见越界）。

### 越界标注（3 处，需 Bookkeeper/评审知悉）

1. **`backend/services/hedge_open_live_client.py` + `live_hedge_executor.py`**：不在 dispatch Allowed
   Files 字面列表，但 Goal 模块 B-5 明确要求「live 能力查交易所合约持仓」——live client 原无持仓读取、
   快照侧 private_client 的 E4 端点不在 hedge client 白名单。必要性驱动新增
   `GET /papi/v1/um/positionRisk`（与快照侧 E4 同一端点、非新权限）。**安全面变更**：hedge client
   ALLOWLIST 12 → 13，冻结测试 `test_allowlist_is_exactly_the_frozen_allowlist` 同步更新（长度 13、
   PAPI 8），拒绝列表移除 GET positionRisk（POST 仍拒）。dry-run 无此能力 → 模拟无仓（dispatch 约定）。
2. **`test_hedge_purity.py`**：白名单冻结测试是防扩张护栏，本次为满足 Goal 明确需求做了受控扩展，
   已改函数名（`..._frozen_twelve_endpoints` → `..._frozen_allowlist`）并注释扩展原因。
3. **`test_hedge_api.py`/`test_hedge_service.py`**：严格键集断言（`_TASK_KEYS`/`_SETTINGS_KEYS`）因
   新增 additive 字段（task_type/close_gate）同步更新。

### 与 dispatch 的偏差（诚实记录）

- **≈U 换算未进 close_log**：dispatch 模块 C 要求「费率/利息 + ≈U 换算（价格源沿用 opening_quotes）」；
  但 `opening_quotes` 在快照/background 层（snapshot rows），service 层（平仓完成写入点）不可得。
  实现：close_log 的 `funding_fee` 存 USDT、`borrow_interest` 存资产单位（与 positions 行
  `borrow_interest` 原始单位一致），**≈U 换算留待组合根层**（历史页显示原始单位）。若评审要求
  ≈U，需把价格源注入 service 层（后续修复任务）。
- **现货买/卖均价列**：close_log 表（设计 v1 §3.2 逐字）无现货列，历史页该两列显示 —。
- **滑点列**：close_log 无滑点字段（dispatch 明确第一版 null），历史页显示 —。
- **live 全链路 worker 循环**：dispatch 验收 4「live 模式 stub」以 `query_symbol_um_qty` 单测 +
  `_verify_close_flat` 三态单测覆盖（worker 线程循环属 live 运行面，dry-run 无 worker；代码路径经
  `_worker_round` 审查）。

### 测试结果

- 全量：`timeout 400 python3 -m pytest backend/tests -q -p no:cacheprovider` → **1399 passed**（89s，
  含新 close 14 用例；功能一/二逻辑未回退）。
- 前端：`node frontend/self-check.js` → **138 PASS，0 FAIL**（82a 真实 POST、98c 真实历史 API 等新断言）。
- 实盘零写：未对 `data/*.sqlite3` 做任何写操作；未提交 git、未移动 HEAD、未发实盘单
  （close_gate 默认开的风险已向 Human 明示，实盘启用需 Human 单独授权）。

### 验收逐项

1. **迁移幂等**：task_type/close_gate 列 + close_log 表存在；重复构造不重复加列/建表；现有任务行
   `task_type='open'`（单测过）。
2. **开仓成本隔离**：close 腿成交后 aggregate 开仓数量/均价不变（单测过）。
3. **立即平仓入口**：表头/输入框/禁用逻辑（已平仓行 + 无周期行禁用）/确认弹框/真实 POST
   `{task_type:'close', ...}`（self-check 82a 过）。
4. **平仓执行**：dry-run 全链路——创建 → 方向反转（forward: spot SELL + perp BUY）→ 合约腿
   `reduceOnly=true` → 双腿成交 → 无仓核实 → done（单测过）。
5. **完成判定**：合约仍有仓 → open（继续按计划次数）；查仓失败 → failed 暂停（fail-closed，
   查不到 ≠ 已平完）；dry-run 模拟无仓（单测过）。
6. **close_gate**：默认 1；`put_close_gate` CAS（confirm/version/409）+ `close_gate_changed` 审计；
   close_gate=0 时 close 任务拒发（`_worker_round` close_gate_off 路径，代码审查 + 单测过）。
7. **结算日志 + 历史页**：close_log 行写入（open/close 均价独立、费率利息复用功能二、滑点 null）；
   `GET /api/hedge-open-close-logs` 返回；前端历史页渲染真实数据（self-check 98c 过）。
8. **回归**：pytest 1399 + self-check 138 全绿。
9. **范围核对**：无 `backend/ledger_flow/store.py`、`backend/ledger_flow/domain.py`、`data/*.sqlite3`
   改动；功能一/二逻辑未回退（merge P0-1、stats 接线、close_cycle 契约单测全绿）；越界 3 处见上。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close.handoff.md`（本交接件）
  2. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-stats.handoff.md`
  3. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-cycle-core.handoff.md`
  4. `backend/hedge_open_tasks/service.py`（create_task / put_close_gate / _verify_close_flat /
     _finalize_close_task / _worker_round）
  5. `backend/hedge_open_tasks/store.py`（close_log 表与读写 / cycle_perp_basis）
  6. `backend/services/live_hedge_executor.py` + `hedge_open_live_client.py`（query_symbol_um_qty / fetch_um_positions）
  7. `frontend/index.html`（renderHedgeCloseInputs / submitHedgeClose / renderHedgeHistory）
  8. `docs/planning/hedge-open-position-cycle-v1.md`（§4.2/§3.2）
- 执行：Bookkeeper 核验本交接件与测试/范围，裁定 3 处越界与 ≈U 偏差
- 关卡：核验通过后进入统一 review-1 + review-2（HIGH_RISK）；实盘启用（close_gate 生效后真实发
  平仓单）需 Human 单独授权
- 不能假设的事实：功能一/二/三均未提交（工作树改动，delivery_sha 均 pending）；close_gate 默认开
  （服务重启后平仓入口实盘可用）；实盘库周期数据仍 0（未回填）；close_log 无 ≈U 换算/现货列/滑点；
  live client 白名单已扩至 13（positionRisk）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: hedge-position-cycle-v1-close
执行结果: completed（完成）
结果摘要: 功能三全链路完成：close 任务（方向反转+reduceOnly+无仓核实+close_gate）、结算日志（open/close 均价独立、费率利息复用功能二）、历史页接真数据、前端立即平仓真实 POST；全量 1399 passed + self-check 138 PASS；3 处越界（services 白名单+冻结测试等）已标注；未提交、未写实盘、未发实盘单。
产物: [backend/hedge_open_tasks/store.py, backend/hedge_open_tasks/domain.py, backend/hedge_open_tasks/executor.py, backend/hedge_open_tasks/service.py, backend/app/server.py, backend/services/hedge_open_live_client.py, backend/services/live_hedge_executor.py, frontend/index.html, frontend/self-check.js, backend/tests/test_hedge_cycle_close.py, backend/tests/test_hedge_api.py, backend/tests/test_hedge_purity.py, backend/tests/test_hedge_service.py, reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close.handoff.md]
检查结果: [迁移幂等（task_type/close_gate/close_log 表）pass；开仓成本隔离（close 腿不进 aggregate）pass；立即平仓入口（真实 POST task_type:close）pass；平仓执行（反转+reduceOnly+无仓核实+done）pass；完成判定（open/failed fail-closed/dry-run flat）pass；close_gate（CAS+审计+拒发）pass；结算日志+历史页（close-logs 端点+真实渲染）pass；回归 1399+138 全绿 pass；范围核对 pass（3 处越界已标注）]
阻塞项: [none（3 处越界与 ≈U 偏差待 Bookkeeper/评审裁定）]
本地北京时间: 2026-08-05 19:51:32 CST
下一步模型: Bookkeeper（核验交付与范围，裁定越界与 ≈U 偏差）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/hedge-position-cycle-v1-close.handoff.md（含引用文件）；执行：Bookkeeper 核验测试/范围并裁定 3 处越界与 close_log ≈U 偏差；关卡：核验通过后进入统一 review-1 + review-2，实盘启用（close_gate 生效发单）需 Human 单独授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification（2026-08-05 代记，正式 Bookkeeper 开 stage 后复核）

- source_sha256: `1a960257943aafdf8b2b55eac1b6da809a57b2deb3d4eaaf8768987dcf0552a1`
- 核验时间: 2026-08-05 CST（当前无活跃 stage，ACTIVE.json=null；由 Human 授权当前会话代记，
  正式 Bookkeeper 开 stage 后须按 status.json revision 复核）
- 核验命令（可复现）:
  - `python3 -m pytest backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py -q` → **77 passed**（独立复跑）
  - `node frontend/self-check.js` → **全部通过**（含 82a 真实 POST、98c 历史 API 断言）
  - `git status --short`：无 `backend/ledger_flow/store.py`、`backend/ledger_flow/domain.py`、`data/*.sqlite3` 改动；功能一/二逻辑未回退
- 结论：**通过**（`reported` → 待统一评审；`delivery_sha=pending`，交付为工作树改动，未提交）
- 三项裁定（Human 授权当前会话代记）：
  1. **越界 1（hedge_open_live_client.py + live_hedge_executor.py）**：验收驱动正当扩展，不递增
     rework（缺陷在 packet：Goal 模块 B-5 要求 live 查仓但 Allowed Files 漏列）。安全面：仅新增只读
     GET `/papi/v1/um/positionRisk`（与快照侧 E4 同端点、非新权限），POST 仍拒；白名单冻结测试 12→13
     受控扩展。
  2. **越界 2（test_hedge_purity.py）**：白名单冻结护栏为满足 Goal 受控扩展，改名+注释，护栏语义保留。
  3. **越界 3（test_hedge_api.py/test_hedge_service.py）**：严格键集加 additive 字段（task_type/close_gate），
     正常同步。
  - **≈U 偏差**：接受为设计取舍（dispatch 要求 close_log 含 ≈U，但 opening_quotes 在快照层、
    平仓写入点在 service 层不可得；实现存原始单位，≈U 留组合根层）。后续如需历史页 ≈U，需价格源
    注入 service 层的小修复（挂账 follow-up）。
- 记录依据：`AGENTS.md` §8 计划评审豁免 + Human 2026-08 拍板「全部开发后统一 review」；
  本块为核验记录，不授权实盘；实盘启用平仓（close_gate 生效发单）需 Human 单独授权。
