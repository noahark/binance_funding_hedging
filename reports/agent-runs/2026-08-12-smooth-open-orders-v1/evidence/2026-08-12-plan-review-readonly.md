# 平滑开单 V1 独立只读计划评议

- 评议模型：Kimi Code CLI
- 评议日期：2026-08-12
- 评议对象：`docs/planning/smooth-open-orders-v1.md`
- 性质：独立只读评议；非正式 Review-1/Review-2，非实现授权，未修改任何文件、status.json、服务、依赖或外部系统。

## 总体结论

**可进入正式计划评审，但必须先完成两项前置修订/验证：**

1. 在 `backend/hedge_open_tasks/store.py` 的 `hedge_open_task` schema 中补全平滑 gate 持久化字段；
2. 在 P0 CCXT Pro proof 中明确合约 `contractSize`/volume 单位证据，否则 80% 覆盖判断无法落地。

其余设计决策与当前代码事实（`service.py::_worker_round` 串行、`store.py::prepare_attempt` 硬门、`service.py::post_fill_once` live 行为、`domain/snapshot.py::compute_opening_spread_pct` 精度、`frontend/index.html` 2 秒轮询）基本自洽，未发现会颠覆方案的资金安全缺口。

## 按严重度列出的问题

### 高：schema 未预留 gate 持久化字段
- 证据：`backend/hedge_open_tasks/store.py:40-65` 的 `hedge_open_task` 表与 `_row_to_task`（`:212-253`）均没有 `slippage_threshold_pct`、`smooth_gate_seq`、`smooth_gate_started_at`、`smooth_gate_deadline_at`、`smooth_gate_force_requested`。
- 影响：设计 §6.1/§8.2 要求“服务重启后继续同一轮剩余 5 分钟、不丢掉已接受的人工放行”，若无持久化列，重启后 gate 状态会丢失，导致重复计时或丢 force 信号。

### 高：80% 覆盖的 `contractSize` 换算缺少权威来源
- 证据：设计 §6.3 要求“合约 `bidVolume/askVolume` 若以 contracts 表示，必须乘 `market.contractSize`”。但 `backend/hedge_open_tasks/domain.py:1145-1331` 的 `compute_preflight` 与 `snapshot_record` 中未持久化 `contractSize`；当前 `perp_filters` 只含 `step_size`、`min_qty`、`max_qty`、`min_notional`。
- 影响：gate 可能把张数直接当币量比较，导致 coverage 判断错误。该问题在 1000x 乘数币上已有资金风险先例，见 `PROJECT_STATE.md` Open Follow-ups。

### 中：gate 等待期间 worker 行为尚未精确化
- 证据：`backend/hedge_open_tasks/service.py:1592-1711` 的 `_worker_round` 在无在途 legs 后直接调用 `_dispatch_one_for_task`。设计 §6.1 要求 gate 阻塞“最多 5 分钟”，但文档未说明 worker 是 busy-wait 轮询、condition 唤醒，还是 pacing 等待。
- 影响：实现阶段若用忙等会浪费 rate-limit 预算并拉长 worker 生命周期；若用 event 唤醒则需与 `force_current_gate`、WebSocket update、timeout 三个信号正确集成，文档应给出推荐模式（建议 event + 5min deadline）。

### 中：`GET /api/hedge-open-logs?task_id=...` 返回契约未扩展
- 证据：`backend/hedge_open_tasks/service.py:1103-1128` 的 `get_logs` 在 `task_id` 模式下只返回 `attempts`，没有设计 §8.3 要求的 `smooth_market`（spot/perp 连接状态、四价四量、spread、coverage、pass 原因）。
- 影响：前端任务卡盘口块没有权威数据源，要么新增端点（与设计“不新增端点”冲突），要么必须扩展该返回。

### 中：`create_task` 当前拒绝 `mode=smooth`
- 证据：`backend/hedge_open_tasks/service.py:761-762` 明确 `if mode != MODE_IMMEDIATE: raise ...`。
- 影响：这是已知现状（设计 §2.3/§8.1 也提到），但实现 P2 时必须移除/分流，建议在计划中作为显式验收点。

### 低：CCXT Pro 依赖安装属 Human 授权范围
- 证据：设计 §4.1/§11 承认仓库无 CCXT 依赖；`AGENTS.md` §3.1 将“安装依赖”列为需 Human 授权的外部副作用。
- 影响：P0 proof 不是纯只读，会改动 `.venv` 或 `pyproject.toml`/lockfile，需在 dispatch 中明确授权。

## 已冻结 Human 决策（不重复质疑）

以下决策与代码事实不矛盾，仅作确认：

- **D4 严格大于**、**D5 允许 0/负数**：阈值是 Human 明确产品语义，实现按 Decimal 比较即可。
- **D7 80% 一档覆盖**：是合理的风控过滤器，不修改下单数量，不引入第二套资金路径。
- **D8 5 分钟超时回退立即开单**：文档已在 §5.2/§9 明确这是“产品取舍”而非 WS 安全门，表达一致。
- **D9 `成交1次` 只强制当前 gate**、**D13 不提供立即成交所有**：与当前 `prepare_attempt` 硬门和 `post_fill_once` 行为改造方向一致。
- **D14 共享 watcher**：任务数受 Operating Limits 约束（约 5 个并发 draining），共享 watcher 在可维护性上合理。

**需补充说明的潜在缺口**：D11/D12 要求任务卡盘口“跟随展开日志的 2 秒读链”，但当前 `EXECUTION_POLL_MS` 只驱动 `refreshExpandedRunningHedgeLogs`（`frontend/index.html:8081-8084`），该函数只拉 attempts。若扩展 `get_logs` 返回加入 `smooth_market`，则 D12 成立；否则需要新增数据路径。这不是 Human 决策矛盾，而是实现缺口。

## 可删除的不必要复杂度

1. **§2.1 对旧 JS 的冗长历史追溯**：可压缩为“旧实现用 REST getDepth，不提供可复用 WebSocket；本设计只沿用状态框架”。当前篇幅对评审价值有限。
2. **§8.3 中“当前 selected direction”的展示**：设计 D11 已要求正反向都展示，任务卡不需要再额外显示一个 selected direction 字段，可减少一个派生项。
3. **任务级 `smooth_pass_reason` 持久化**：§8.2 提出记录最近一次 `smooth_pass_reason`，但该值可通过 attempt 的 `pass_reason` 或日志反推，无需单独 task 字段，除非跨重启后任务卡要秒显最近原因。建议仅在 attempt 级记录。

## 最多 5 条具体修订建议

1. **补全持久化 schema**  
   在 `hedge_open_task` 新增 `slippage_threshold_pct TEXT`、`smooth_gate_seq INTEGER`、`smooth_gate_started_at_us INTEGER`、`smooth_gate_deadline_at_us INTEGER`、`smooth_gate_force_requested INTEGER DEFAULT 0`，并在 `_row_to_task` 中解析；`scheduled_attempt_count` 仍是 attempt 硬门，gate 字段不替代它。

2. **P0 proof 必须输出 contractSize/volume 单位证据**  
   对 Binance spot/USDⓈ-M `watchBidsAsks`，明确返回的 `bidVolume/askVolume` 是 contracts 还是 base coins；若是 contracts，给出获取 `contractSize` 的 CCXT Pro 字段或 exchangeInfo 路径。proof 失败时启用 Binance 原生 bookTicker adapter，不改变 gate/UI 契约。

3. **定义 gate 等待的 worker 集成模式**  
   在 `_worker_round` 无在途 legs 后、调用 `_dispatch_one_for_task` 前插入 `wait_for_gate(task, gate)`：优先使用 per-task threading.Event/Condition，由 WebSocket update、`force_current_gate`、timeout 三个来源唤醒，避免 busy-wait；5 分钟 deadline 用单调时钟计算。

4. **扩展 `GET /api/hedge-open-logs?task_id=...` 返回**  
   在 `get_logs` 的 task_id 分支返回中新增 `smooth_market` 对象，包含 spot/perp 连接状态与最后接收时间、四价四量、正反向 spread pct、当前 direction、两腿 coverage 及 pass 状态、整体 gate pass 与等待原因。前端据此渲染盘口块，不重算 gate。

5. **按 mode 分流 `post_fill_once` 并新增 threshold 校验**  
   - `backend/hedge_open_tasks/domain.py` 新增 `validate_slippage_threshold_pct`：允许 `-12`、`0`、`0.05`、`.05`，最多两位小数，拒绝 `%`/科学记数/空值/NaN/Infinite。  
   - `service.py::post_fill_once` 对 `mode=smooth` 调用 `force_current_gate(task_id, gate_seq)`（原子设置 force flag），不再直接 `ensure_worker`；`mode=immediate` 保持现有行为。
