# 12-development-breakdown —— 可交付任务拆分与验收标准

- task_id: `plan-hedge-task-lifecycle-v1`
- 关联：`10-design.md`（裁定）、`11-adr.md`（ADR-001/002/003）。
- 四项 → **三个交付任务**，序 ①→②→③，④ 搭车于 ②。每个任务给：范围、文件边界、验收标准、风险标注与理由、依赖。

> **修订说明（2026-07-31，`plan-revision-backend-merge-v1`）**：按 Human D14/D15 重写 **Task 1**——由「纯前端合并」改为「后端合并 + 前端渲染」（文件边界扩到 `backend/`，含 `aggregate_positions` D15、纯合并函数、handler 接两服务、降级契约、N1-N5）。**Task 2、Task 3 不受 D14/D15 影响，原样保留**。顺带更正：①② 因都改后端（`store.py`/`service.py` 重叠）**不再文件独立**，改为严格串行。本次修订不计 `rework_count`（仍 0）。

总顺序硬约束（dispatch P8）：**① 在 ② 前**（资金可见性先于会隐藏任务的自动删除）；**③ 在 ② 后**（`rate_limited` 语义须先在 ② 落定）。**修订后 ①② 不再文件独立**：① 改 `store.aggregate_positions`/`service`/`server`，② 改 `store`/`service`/`domain`，重叠于 `store.py`/`service.py` → **不可并行**，② 须基于 ① 的 `delivery_sha` rebase。③ 与 ② 都改 `service.py` worker 区，③ 须基于 ② rebase。即三者**严格串行 ①→②→③**。

---

## Task 1 —— `hedge-merged-positions-v1`（① 后端合并 + 前端渲染）

### 范围
在**后端服务器层**合并持仓，前端只渲染。要点（N1-N5 详见 `10-design.md` P1·附）：

- **后端合并**：`_hedge_open_positions`（`server.py:607`）handler 调 `self.service.get_snapshot()`（`try/except SnapshotNotReady`）取 `private_account`，调 `hedge_open_service` 取 `aggregate_positions`，经**纯函数** `merge_positions(positions_rows, private_account)` 合并后返回。
- **D15**：`aggregate_positions`（`store.py:1937-2057`）两条查询（`:1950`/`:1960`）去 `WHERE != DELETED`，SELECT 带 `t.status`，分桶时置桶级 `includes_deleted_task` 标记。
- **N1**：就地改 `GET /api/hedge-open-positions` 形状（保留既有字段名 `coin`/`direction`/`position_qty`/`spot_avg`/`perp_avg` + 追加合并字段）。
- **N2**：降级契约——账户未就绪（`SnapshotNotReady`）/不可用（`verified:false`）时，**仍返回本地记账行** + `account:{verified:false,error}`，HTTP 200，不整体 503。
- **符号/base-asset 三方归一在后端 `merge_positions` 内**（`um_positions[].symbol` ↔ `coin` ↔ 现货 `asset`；1000x 六币**不剥离前缀**，诚实落入「无任务记录」行）；`directionForPosition`（`index.html:2198`）前端复用。
- **前端**：一张合并表取代既有「UM 持仓」面板（`index.html:2913` 区）与 `renderHedgePositionsSection`（`:4500`）；占位零三分类（P7）；P2 偏离软标记 + N3 已删任务标记 + N2 账户未就绪标记；保持 `63f5007` 展示形状。
- 单腿敞口**只读后端** `pair_outcome`/`leg_exposure`，前端不重推。
- 账户级 `uniMMR` 放表外摘要，**不**冒充为某币列（红线 #4）。
- `merge_positions` 为纯函数（可单测）；handler 仅装配，**不**把 `SnapshotService` 注入 `HedgeOpenTaskService`（保持两服务解耦）。

### 文件边界（Allowed Files）
- `backend/app/server.py`（`_hedge_open_positions` 接两服务 + `SnapshotNotReady` 捕获）
- `backend/hedge_open_tasks/service.py`（`get_positions` 改 / 合并装配；或 `merge_positions` 纯函数置此）
- `backend/hedge_open_tasks/store.py`（`aggregate_positions` 去两条 `WHERE` + `includes_deleted_task`）
- `backend/hedge_open_tasks/domain.py`（若 `merge_positions`/base-asset 归一函数置此）
- `backend/tests/test_hedge_store.py`（`aggregate_positions` D15 回归）、`test_hedge_service.py`（`get_positions`/合并）、`test_hedge_api.py`（端点 + 降级）或新增 `test_positions_merge.py`
- `frontend/index.html`（合并表渲染器取代 UM 面板 + `renderHedgePositionsSection`）
- `frontend/self-check.js`（渲染断言；仅 a 新增 / b 修复 DOM 失配，不放宽既有断言）

**不得改动**：`private_client.py`、`hedge_preflight_provider.py` 白名单、`backend/hedge_open_tasks/scheduler.py`、`domain.py` 暂停原因集与 51169 文案区（`:1315-1324`）、`status.json`、其它。

### 验收标准
1. **后端合并**：`GET /api/hedge-open-positions` 返回合并行（UM 骨架 + 现货/借款 + 任务成本），六场景（normal/no_task/no_um/single_leg/missing/empty）口径正确（`backend/tests/` 数据驱动覆盖）。
2. **D15**：已删任务的已成交腿计入 `aggregate_positions`，带 `includes_deleted_task` 标记；**两条查询都改**。
3. **N2 降级**：`SnapshotNotReady` 与 `verified:false` 时接口 HTTP 200、返回本地记账行 + `account.verified=false`，**不整体 503**。
4. **N1 形状**：既有字段名保留，前端渲染器同步重写；无既有消费者受冲击（唯一消费者是前端）。
5. **符号对齐**：1000x 六币（`1000PEPEUSDT` ↔ `PEPE`）诚实处理（映射或落入「无任务记录」），不假对齐（`backend/tests/` 覆盖）。
6. **占位零三分类**：资金费/借币利息/净盈亏画「暂无」，无 `0.00`；未实现盈亏取 `unrealized_profit` 真值。
7. **标记齐全**：P2 偏离（真实<记录）软标记、N3 已删任务行标记、N2 账户未就绪列标记。
8. **51169 文案逐字渲染**（`domain.py:1315-1324`），未换「保证金不足」话术。
9. `node frontend/self-check.js` → `EXIT=0`，既有断言全绿、未放宽；前端只验渲染（数据正确性由 backend 测）。
10. UM 面板 + `renderHedgePositionsSection` 被单一合并表取代，无重复表。

### 风险标注
**HIGH_RISK**。理由（§8）：资金显示（money-meaning）+ **后端 money-read 契约变更**（`aggregate_positions` D15，触及 `[OPEN][MONEY-VISIBILITY]` 资金可见性契约）+ **接口契约变更**（§3.4 Position JSON 形状）+ **snapshot 耦合**。虽无下单路径，但改的是资金/账务含义的读路径与对外接口形状。比原前端方案风险面更宽（多了后端契约 + 耦合，见 `10-design.md` §7.1）。

### 测试策略（N5）
合并逻辑主战场移到 `backend/tests/`（确定性）：六场景 / 符号对齐（1000x 六币）/ D15（已删任务 + 标记）/ N2 降级（两路径）/ `aggregate_positions` WHERE 回归——均数据驱动。`frontend/self-check.js` 只验**渲染**（占位零三分类视觉、`account.verified=false` 列、已删任务标记、与 `63f5007` 结构一致）；六场景**数据正确性**不再在 DOM 测。

### 依赖
无。是 Task 2 的前置（须先于 ② 合并；且② rebase 于①）。

---

## Task 2 —— `hedge-task-lifecycle-v1`（② + ④ + P3 `rate_limited` 剥离）

### 范围
任务状态机修复 + 六种非人工暂停改自动删除（`rate_limited` 除外）+ ④ 搭车。

要点：
- **死锁修法（P4）**：在 `post_start`/`post_fill_once`/`post_fill_all` 汇到的共享再武装路径加配额守门——`scheduled_attempt_count >= target_n` 时收口到 `DONE`（复用 `post_start` 既有 `DONE` 幂等路径），不置 `running`+`ensure_worker`；`post_start` 对 `stopped` 不再武装。谓词与 A-1 家族同（`scheduled_attempt_count`），收紧非放宽。
- **五种终态原因自动删除**：`consecutive_submission_failure`（改 `resolve_status_after_attempt` 阈值分支返回 `DELETED` 而非 `PAUSED`，`_apply_task_counters` 在 `new_status==DELETED` 时仍写 `pause_reason`）、`insufficient_balance`/`insufficient_margin`/`insufficient_available_qty`/`collateral_cap_full`（worker `_pause_from_signal` 改走删除转移）。删除复用 `post_delete` 不打断 drain 语义，保留 `pause_reason`+`pause_reason_zh`（51169 文案留显）。
- **`rate_limited` 剥离（P3 / ADR-002）**：worker 两处 429 站点（`service.py:1152-1160`、`:1176-1180`）不再 `_pause_task_local`/`pause_task`，改为指数退避 + 抖动重试（用既有 `stop_event.wait`，不新增字段/枚举）。`skip_counters` 结算不变。
- **A-1 守门补齐**：见 `10-design.md` §2 逐站评估。
- **`skip_counters` 非终态收口**：评估并补一处「限频结算后配额已耗仍非终态」的收口（若 `scheduled >= target_n` 且无更高优先态 → `DONE`），与 R2-F1 同向。
- **④ 搭车**：`resolve_leg_from_query`（`store.py:1596-1619`）的 `cumulative_quote_amt = ?`、`avg_price = ?` 改为 `COALESCE(?, cumulative_quote_amt)` / `COALESCE(?, avg_price)`，与既有 `order_id` 保护同款。
- 不新增状态枚举（红线 #3）；不放宽 A-1（红线 #2）；51169 文案逐字不动（红线 #1）。

### 文件边界（Allowed Files）
- `backend/hedge_open_tasks/service.py`（再武装守门、worker 429 退避、删除转移路径）
- `backend/hedge_open_tasks/store.py`（`resolve_leg_from_query` COALESCE、`pause_task`→删除转移或新辅助、`skip_counters` 收口）
- `backend/hedge_open_tasks/domain.py`（`resolve_status_after_attempt` 阈值分支 → `DELETED`；不动 51169 文案区 `:1315-1324`）
- `backend/tests/test_hedge_service.py`、`test_hedge_store.py`、`test_hedge_task_local.py`、`test_hedge_domain.py`（回归 + 新断言）

**不得改动**：`frontend/`、`private_client.py`、`hedge_preflight_provider.py` 白名单、51169 文案、`status.json`、其它。

### 验收标准
1. **死锁**：复现条件 `target_n == failure_pause_threshold` 下，`post_start` 再武装 → 任务到 `done`，不卡 `running`；三入口均覆盖。
2. **自动删除**：五种终态原因触发 → `status=deleted` + `pause_reason` 留存 + 51169 文案逐字；drain 安全（在途腿达终态后才退出）。
3. **`rate_limited` 退避**：注入 `SIGNAL_RATE_LIMITED` → 不写 `paused`/`deleted`、发生退避等待、最终干净重试或退出；`skip_counters` 结算不受影响。
4. **A-1 穷举**：四站同谓词断言；新增守门用 `scheduled_attempt_count`，未切 `accepted` 口径。
5. **④**：后查返回 `None` 不覆盖已知 `avg_price`/`quote_amt`（`test_resolve_leg_from_query_persists_avg_price` 扩展覆盖 `None` 不覆盖）。
6. 既有回归全绿（`test_hedge_store.py:174-192` 的 R2-F1 锁定用例等不被破坏）。
7. 不新增状态枚举值；51169 文案区 `domain.py:1315-1324` 逐字未改。
8. 不触碰 `frontend/`、白名单、`status.json`。

### 风险标注
**HIGH_RISK**。理由（§8）：任务状态机 + 资金可见性 + 实盘写路径（worker 派发/对账/限频）。本 stage 最大一块。④ 虽本身 LOW（残 risk、当前不可达），但搭车于 HIGH_RISK 任务，随其走 review-1+review-2， scrutiny 更高，无害。

### 依赖
Task 1（① 须先合并，保证删卡后敞口与成本基仍可见；且② rebase 于①共享的 `store.py`/`service.py`）。

---

## Task 3 —— `hedge-leg-requery-cadence-v1`（③ 重查间隔 1s → 100ms）

### 范围
把腿重查节奏从 1s 降到 100ms，修显示，加护栏。`rate_limited` 退避节流参数在此调优（机制已在 Task 2 落定）。

要点：
- **前置显示修复**：`service.py:178` 整除 → 亚秒渲染（ms 或小数秒）。
- **下调默认**：`interval_us` 种子默认 `1_000_000` → `100_000`（100ms）。
- **下限**：`get_interval_us` 读取处夹下限（建议 50ms）。
- **抖动**：worker 节流 `service.py:1079` `ev.wait(interval_s)` 加随机抖动。
- **退避节流参数调优**：与 Task 2 的退避协同，定退避上限/上限重试次数（防忙轮询/死循环）。
- 不新增运行时配置入口（红线 #6）；不拆分双间隔（ADR-003）。

### 文件边界（Allowed Files）
- `backend/hedge_open_tasks/service.py`（显示修复 + worker 抖动 + 退避参数）
- `backend/hedge_open_tasks/store.py`（`interval_us` 默认值 + `get_interval_us` 下限）
- `backend/hedge_open_tasks/scheduler.py`（若 poll slice 需随亚秒调整；`scheduler.py:56` 已自适应，预计无改或微调）
- `backend/tests/test_hedge_service.py`、`test_hedge_task_local.py`

**不得改动**：`frontend/`、51169 文案、`status.json`、`private_client.py`、`domain.py` 暂停原因集。

### 验收标准
1. **显示**：`interval_us=100_000` 时设置接口返回亚秒值（非 `0`）。
2. **节奏**：在途腿重查间隔 ≈100ms（用 `_pump_worker`/可控时钟断言）；下单频率不变（A-9：一对腿终态才进下一对）。
3. **下限**：误配极小值（如 1ms）被夹到下限，不忙轮询。
4. **抖动**：多 worker 节流起始被错峰（断言抖动存在）。
5. **退避**：429 退避有上限、不死循环（与 Task 2 验收 3 协同）。
6. 既有回归全绿；不新增配置入口、不拆分间隔字段。

### 风险标注
**HIGH_RISK**。理由（§8）：改查询节奏 = 限频/操作性风险；触 worker 实盘路径；验收 oracle 非显然（「100ms 是否安全」须靠退避+抖动论证，非简单断言）。下单频率虽不变（A-9），但聚合请求权重上升，429 概率上升——靠 ADR-002 退避兜底。

### 依赖
Task 2（`rate_limited` 语义与 worker 退避机制须先在 ② 落定；③ 只调节奏与参数）。须基于 Task 2 的 `delivery_sha` rebase（共享 `service.py` worker 区）。

---

## 交付顺序总图

```
Task 1 (① 后端合并+前端渲染, HIGH_RISK) ──→ Task 2 (②+④ 后端状态机, HIGH_RISK) ──→ Task 3 (③ 节奏, HIGH_RISK)
        ① 须先于 ② 合并；二者改 store.py/service.py 重叠 → ② rebase 于 ①              ③ 在 ② 后, rebase ②
```

- 三个交付物各自计 `rework_count`（§8 绑定交付物）。
- HIGH_RISK 任务实现前须经一次跨 provider 只读计划评审（`deepseek`，§8）。
- 实现 `claude_glm` → review-1 `grok` → review-2 `codex`（D3 + D12 路由）。
