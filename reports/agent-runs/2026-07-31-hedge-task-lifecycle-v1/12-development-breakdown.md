# 12-development-breakdown —— 可交付任务拆分与验收标准

- task_id: `plan-hedge-task-lifecycle-v1`
- 关联：`10-design.md`（裁定）、`11-adr.md`（ADR-001/002/003）。
- 四项 → **三个交付任务**，序 ①→②→③，④ 搭车于 ②。每个任务给：范围、文件边界、验收标准、风险标注与理由、依赖。

总顺序硬约束（dispatch P8）：**① 在 ② 前**（资金可见性先于会隐藏任务的自动删除）；**③ 在 ② 后**（`rate_limited` 语义须先在 ② 落定）。①② 文件独立（前端 vs 后端），可并行**开发**，但 ② 不得先于 ① **合并**。③ 须基于 ② 的 `delivery_sha` rebase（都改 `service.py` worker 区）。

---

## Task 1 —— `hedge-merged-positions-v1`（① 前端合并持仓表）

### 范围
以真实 UM 持仓为骨架，在 `index.html` 把 `state.snapshot.private_account` 与 `state.hedgePositions` 合并成一张表，取代既有「UM 持仓」面板与 `renderHedgePositionsSection`（D6）。

要点：
- 骨架 `um_positions[]`，一行一合约标的；任务记录中无对应持仓的标的追加成行（fake 场景 c `no_um`）。
- 每行横拼三源：真实合约持仓（A）/ 账户资产（B 现货余额、C 全仓借款）/ 任务记录成本（D 两腿均价、价差率）。
- **符号/base-asset 三方归一**：`um_positions[].symbol` ↔ 任务 `coin` ↔ 现货 `asset`，统一用一个 base-asset 归一函数（三处共用）；1000x 六币**不剥离前缀**，照实落入「无任务记录」行（fake 场景 b）。
- `position_side` 按真实契约**大写** `LONG`/`SHORT`（复用 `directionForPosition`，`index.html:2106`）。
- **占位零三分类**（P7）：未实现盈亏取 `um_positions[].unrealized_profit` 真值（红绿）；累计资金费/借币利息/净盈亏画「暂无」（灰斜体），**不画 0.00**；拿不到画 `—`/`null`/强平价 sentinel `0`（带 title）。
- **P2 偏离软标记**：真实现货余额 < 记录累加值时，复用 single_leg 红行视觉 + 标记「本地记录与实际不一致」，不告警/不动作。
- 单腿敞口判定**只读后端** `pair_outcome`/`leg_exposure`，前端不重推（避免双源漂移）。
- 账户级 `uniMMR` 放表外摘要，**不**冒充为某币列（红线 #4）。
- 与 fake `63f5007` 形状一致；差异仅 §5 列出的四点（数据源真值化、`rate_limited` 卡文案、P2 标记、净盈亏「暂无」）。

### 文件边界（Allowed Files）
- `frontend/index.html`（新增真实合并渲染函数，取代既有 UM 面板 + `renderHedgePositionsSection`）
- `frontend/self-check.js`（新增断言；仅 a 新增断言 / b 修复因新 DOM 致既有断言失配两类，**不放宽既有断言**，对齐 fake-ui §8 纪律）

**不得改动**：`backend/` 任何文件、`status.json`、其它。

### 验收标准
1. 合并表默认渲染真实数据（`state.snapshot.private_account` + `state.hedgePositions`）；六场景口径（normal/no_task/no_um/single_leg/missing/empty）可达并正确。
2. 占位零三分类视觉可区分：真值/暂无/拿不到；**无任何 `0.00` 占位**出现在资金费/借币利息/净盈亏列。
3. 1000x 六币（如 `1000PEPEUSDT` um ↔ `PEPE` 现货）被诚实处理（匹配或落入「无任务记录」行），不假对齐。
4. P2 偏离：真实现货 < 记录时出现软标记；真实 > 记录不标记。
5. 51169 文案逐字渲染（`COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`，`domain.py:1315-1324`），未换「保证金不足」话术。
6. `node frontend/self-check.js` → `EXIT=0`，既有断言全绿、未放宽。
7. 两个被取代的旧渲染入口不再产出（或被合并表包裹），无重复表。
8. 不引入对 `backend/` 的改动（`git diff --name-only | grep backend` 无输出）。

### 风险标注
**HIGH_RISK**。理由（§8）：渲染资金/PnL = money-meaning；错误符号、虚构值、假对齐会误导操作者对敞口的判断（操作性风险）。虽只读、无下单路径，仍属资金显示正确性。fake UI 之 LOW_RISK 仅因其是「常量设计探针、无真实接线」；真实接线不同。

### 依赖
无。是 Task 2 的前置（须先于 ② 合并）。

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
Task 1（① 须先合并，保证删卡后敞口仍可见）。

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
Task 1 (① 前端合并, HIGH_RISK) ──┐
                                 ├─→ Task 2 (②+④ 后端状态机, HIGH_RISK) ──→ Task 3 (③ 节奏, HIGH_RISK)
                  ① 须先于 ② 合并                                        ③ 在 ② 后, rebase ②
```

- 三个交付物各自计 `rework_count`（§8 绑定交付物）。
- HIGH_RISK 任务实现前须经一次跨 provider 只读计划评审（`deepseek`，§8）。
- 实现 `claude_glm` → review-1 `grok` → review-2 `codex`（D3 + D12 路由）。
