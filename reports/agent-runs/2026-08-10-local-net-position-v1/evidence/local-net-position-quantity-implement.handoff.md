# Task Handoff: local-net-position-quantity-implement

## Source Report (author-only; immutable after task end)

- task_id: `local-net-position-quantity-implement`
- role: Implementer（中央净持仓聚合 + 测试 + API 语义文档 + 单一 delivery commit）
- target model: `claude_glm`（provider identity: `zhipu_glm`）
- stage_id: `2026-08-10-local-net-position-v1`
- created_at: 2026-08-10 12:50:31 CST
- base_sha: `53ed646f4b97d07ea478a834ed8eb6acb83bbedf`（= `git rev-parse 53ed646…`，与 status.json 固定值一致）
- delivery_sha: `pending`（本交接件先于包含它的唯一 delivery commit 创建；实际值由 Bookkeeper 在封存时从 `git rev-parse` 解析）
- required_skill: `agents/skills/senior-developer.md`

### 1. 任务背景与口径

执行 `03-implement.dispatch.md`（status_revision 3）。目标：用既有 `hedge_open_leg`
成交账本，按活跃周期逐腿输出本地剩余净持仓量，修复 XVG 部分平仓误报，并让 XLM 型单腿
平仓第一次能由本地账本触发既有失衡标记。口径权威：`00-change-plan.md` §3/§4/§5（含
§8 Planner 裁定：不增加「open 成交为 0 就隐藏桶」过滤；首轮计划评审 F-1 已降为非阻塞，
重开条件见 `plan-review-f1-counter-evidence.md` / `plan-review-f1-human-adjudication.md`）。

唯一数量语义：每条腿只按真实 `cumulative_base_qty > 0` 计量，open `+q`、close `-q`；
`spot_notional/perp_notional` 与 `spot_qty_priced/perp_qty_priced` 仍只由 open 腿贡献；
`spot_qty/perp_qty` 为本地账本剩余绝对量，`position_qty = direction_sign × perp_remaining`
（forward 负、reverse 正）；输出字段集合、`domain.py`、前端、下单/闸门/借还款/划转路径不变。

### 2. 实际修改范围（全部在 dispatch Allowed Files 内）

只改中央聚合 `aggregate_positions()`，不扩域、不新增字段、不做 schema migration：

- `backend/hedge_open_tasks/store.py`（`aggregate_positions`）
  - SQL-B：去掉 `WHERE t.task_type = ?` 及 `(D.TASK_TYPE_OPEN,)` 参数，改为同时读取 open 与
    close 腿并带出 `t.task_type`；已关闭周期过滤 `(a.cycle_id IS NULL OR c.closed_at_us IS NULL)`
    与排序、legacy `hedge_open_fill` 告警策略不变。
  - 聚合 loop：新增 `is_open = row["task_type"] == D.TASK_TYPE_OPEN` 与
    `leg_sign = Decimal(1) if is_open else Decimal(-1)`；`spot_qty/perp_qty += leg_sign * q`；
    notional/priced 分母仅当 `is_open` 时累加（close 腿即使有 quote 也不进开仓成本基，且不置
    `*_incomplete`）；`position_qty += direction_sign * leg_sign * q`。
  - docstring：更新 `position_qty`/`spot_qty`/`perp_qty` 为「剩余净量、非交易所对账」语义。
- `backend/tests/test_hedge_cycle_close.py`：将 `test_close_legs_excluded_from_open_cost_basis`
  （旧：断言 close 后 perp_qty 仍 0.5）重写为 `test_close_legs_reduce_local_net_qty_but_keep_open_cost_basis`
  ——双腿全平后剩余 0、`position_qty` 回 0，且 `spot_avg/perp_avg` 与 close 前逐字一致。
- `backend/tests/test_hedge_cycle_core.py`：最小扩展 `_create(task_type=…)`、`_apply(qty=…, outcome=…)`、
  `_outcome(spot_status/perp_status/spot_qty/perp_qty=…)`（默认值保持原行为，既有用例不受影响），
  新增净量覆盖块 8 例（验收 5/6/7 全覆盖，见 §4）。
- `docs/api/public-market-contract.md`：追加 v0.18「Local Net Position Quantity Amendment」，
  不新增字段、不改 shape，只重述 `spot_qty/perp_qty/position_qty` 为本地账本剩余量、非交易所对账，
  明确 `um_position_amt` 才是同次快照的交易所合约量，`single_leg_exposure=false` 与 `drift=false`
  都不得解读为两边一致。
- `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`：仅把 `current_task.state` 由
  `dispatched` 改为 `reported`（本任务结束动作；其余字段不动）。

未触碰：`backend/hedge_open_tasks/domain.py`、`service.py`、`frontend/`、任何 schema/migration、
闸门/订单/借还款/划转路径、`PROJECT_STATE.md`、凭证或 live DB。`test_hedge_store.py`、
`test_positions_merge.py`、`test_hedge_api.py` 经评估无需改动（merge 层为消费既有 bucket 的纯函数；
其既有用例已覆盖 single_leg_exposure 逻辑），保持原样并通过。

### 3. 未做的事 / 边界遵守

- 未增加「桶内只有 close 腿（open 累计成交为 0）就隐藏桶」的过滤（F-1 已降为非阻塞；静默隐藏会
  抹掉异常成交证据）。若该形状真出现，净量会按 open−close 自然得出（可能为负），保留可见。
- 未运行服务、未启动/重启、未读凭证、未访问 live DB、未 merge、未 push、未部署、未自评 ACCEPT、
  未创建 review dispatch、未联系 Reviewer。

### 4. 测试结果（验收 5/6/7 覆盖 + 验收 10 全量）

新增净量覆盖块（test_hedge_cycle_core.py）逐条映射验收检查：

| 用例 | 覆盖 | 关键断言 |
|---|---|---|
| `test_aggregate_local_net_qty_double_leg_partial_close` | 验收 5（XVG） | open 50000 + 两次双腿 close 各 10000 → 两腿 30000、forward `position_qty=-30000`、开仓均价不变 |
| `test_aggregate_local_net_qty_single_leg_close` | 验收 6（XLM） | reverse open 双腿 100，close 仅 perp 成交 100、spot 零成交 → 剩 spot 100/perp 0（不因 pair 失败忽略 perp） |
| `test_aggregate_local_net_qty_counts_non_filled_positive_fill` | 验收 7 | literal status=`PARTIALLY_FILLED` 但累计成交 0.3 > 0 仍按真实成交扣减 → 剩 0.7 |
| `test_aggregate_local_net_qty_zero_fill_close_changes_nothing` | 验收 7 | close 零成交腿（cumulative_base_qty=0）不改变剩余量 |
| `test_aggregate_local_net_qty_reverse_partial_close` | 验收 7（reverse） | reverse open 1、close 0.4 → 两腿 0.6、`position_qty=0.6`（正号） |
| `test_aggregate_local_net_qty_reopen_after_partial_close_same_cycle` | 验收 7 | 同周期 0.5−0.2+0.3=0.6，cycle_id 与起始时间不变 |
| `test_aggregate_local_net_qty_close_from_deleted_task_still_counted` | 验收 7 | 已删除 close 任务的真实成交仍扣减，`includes_deleted_task=True` |
| `test_aggregate_local_net_qty_hidden_after_cycle_closed` | 验收 7 | 含 open+close 腿的周期关闭后从持仓表根查询排除 |

验收 10 完整结果（5 个文件，未截断）：

```text
$ .venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py \
    backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py \
    backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py
============================= 224 passed in 25.01s =============================
```

（基线 216 passed；本次 +8 净量用例，全部通过。原始输出未单独存档——大体积原件只在此引用命令
与结果行，符合 Task Handoff Evidence Contract。）

验收 11：`git diff --check` 干净（无空白错误）；改动文件仅 `store.py`、
`test_hedge_cycle_close.py`、`test_hedge_cycle_core.py`、`docs/api/public-market-contract.md`
（+ 本次 status.json 状态位 + 本 handoff），无 schema migration、无 DB/data 变化、
无服务/闸门/订单/借还款/划转路径变化。

### 5. 可复现命令

```bash
git rev-parse 53ed646f4b97d07ea478a834ed8eb6acb83bbedf   # base_sha 校验
git diff --check
.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py \
  backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_store.py \
  backend/tests/test_positions_merge.py backend/tests/test_hedge_api.py
grep -rln "aggregate_positions" backend/tests/   # 仅这 5 个文件调用，无范围外连带
```

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md`
  2. `reports/agent-runs/2026-08-10-local-net-position-v1/03-implement.dispatch.md`
  3. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
  4. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
  5. `backend/hedge_open_tasks/store.py`（`aggregate_positions`）
  6. `docs/api/public-market-contract.md`（v0.18 段）
- 执行：Bookkeeper 先按本交接件核验（源区块 SHA-256、task_id/role/stage_id/base_sha 与 status
  一致、create-only 路径、TASK_RESULT v2 结构、验收 5/6/7/10/11 命令可复现），再解析 delivery
  commit 的真实 `git rev-parse` 值写入 `status.json.delivery_sha` 与同文件 Verification 块。
- 关卡：Bookkeeper 封存 `base_sha..delivery_sha` 后，由 Human 启动 Kimi review-1（独立只读会话，
  按 §8 受保护类走 review-1；本 stage 已获 review-2 豁免，review-1 ACCEPT 且 Bookkeeper 核验通过
  后 Human 已授权合并到 `main`，但部署/实盘仍须单独授权）。
- 不能假设的事实：
  - `delivery_sha` 仍为 `pending`，真实值待 Bookkeeper 在 delivery commit 后解析；本实现未自评 ACCEPT。
  - 净量为「open−close」按真实成交累计，未对「只有 close 腿的空桶」做隐藏；该形状无当前实例，
    若未来出现 close-only 真实成交应另开任务处置 stale close 派发，不在本任务预防性隐藏。
  - 224 passed 是本机 dry-run 只读测试结果，不含 live/DB 验证；本任务未运行服务、未触碰 live DB。
  - `um_position_amt`（交易所侧）与三个本地净量字段语义不同；`drift`/`single_leg_exposure` 均为弱告警，
    `false` 不等于对账一致（详见 v0.18 文档段）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: local-net-position-quantity-implement
执行结果: completed（完成）
结果摘要: 中央聚合改为同读 open/close 腿，open+q/close-q 得本地剩余净量；close 不进开仓成本基，字段集合/domain/前端/下单闸门不变。XVG 部分平仓误报修复、XLM 单腿平仓首次可被本地账本看见。5 个测试文件 224 passed（+8 净量用例），diff --check 干净。
产物: [reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md, backend/hedge_open_tasks/store.py, backend/tests/test_hedge_cycle_close.py, backend/tests/test_hedge_cycle_core.py, docs/api/public-market-contract.md]
检查结果: [
  1 SQL-B 同读 open/close 腿并带出 task_type，已关闭周期过滤与 legacy fill 告警不变：pass；
  2 每条腿按真实 cumulative_base_qty>0 计量，open+q/close−q：pass；
  3 notional/priced 分母仅由 open 腿贡献，close 不进 spot_avg/perp_avg：pass；
  4 输出字段集合不变，spot_qty/perp_qty 为剩余绝对量、position_qty 仍 forward 负 reverse 正，未改 domain/前端：pass；
  5 XVG 回归 open50000+两次close10000→两腿30000、position_qty=-30000、均价不变：pass；
  6 XLM 单腿 close（perp100成交/spot0）→剩spot100/perp0：pass；
  7 部分平仓/单腿/非FILLED正成交/零成交/reverse/同周期再加仓/已删除成交/周期关闭过滤全覆盖：pass；
  8 未新增「open成交0即隐藏桶」代码，F-1 不准入按降级裁定执行：pass；
  9 v0.18 文档段：本地净量非对账、um_position_amt 为交易所侧、两弱标记false≠一致：pass；
  10 5 文件 224 passed；git diff --check 干净，无 schema/DB/服务/闸门/订单/借还款/划转变化：pass
]
阻塞项: [none]
本地北京时间: 2026-08-10 12:50:31 CST
下一步模型: Codex（本 stage 的 Bookkeeper，负责状态核验与封存），由 Human 转交启动
下一步任务: 读取：reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-quantity-implement.handoff.md；reports/agent-runs/2026-08-10-local-net-position-v1/03-implement.dispatch.md；reports/agent-runs/2026-08-10-local-net-position-v1/status.json；执行：核验本交接件（源 SHA-256、base_sha 与 status/git rev-parse 一致、create-only 路径、TASK_RESULT v2、验收 5/6/7/10/11 可复现），解析 delivery commit 真实 SHA 写入 status.json.delivery_sha 与同文件 Verification 块；关卡：Bookkeeper 封存 base_sha..delivery_sha 后由 Human 启动 Kimi review-1
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
