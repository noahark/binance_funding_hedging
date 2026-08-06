# 功能 3 开发文稿：持仓周期费率/利息统计

状态：**开发文稿，供独立核对；不授权实现或任何实盘操作。**
设计权威：`docs/planning/hedge-open-position-cycle-v1.md` §7（下称「设计 v1」）。
前置：依赖功能 2（周期表）提供的 `cycle_id`/`opened_at_us`/`closed_at_us`。本文稿把设计 v1 §7 细化到文件/函数级，供 sonnet5 独立核对（核对点用「🔍」标注）。

---

## 1. 目标与边界

### 1.1 目标

1. 持仓行三列 `accrued_funding`（累计资金费）、`borrow_interest`（借币利息）、`net_pnl`（周期收益）从占位 `"0"` 变为**周期窗口真值**。
2. 统计口径（Human 已拍板）：`net_pnl = funding_fee + borrow_interest` 窗口合计；**不含**未实现盈亏、**不含**平仓盈亏。
3. 窗口 = `[cycle.opened_at, cycle.closed_at 或 now]`；迟到费率不特殊处理，ledger 约 1 小时自动刷新后自然可见。
4. 展示层（`frontend/index.html`）把「暂无」占位替换为真值；已平仓周期行显示窗口合计，活跃周期显示截至 now。

### 1.2 不在本轮

- 不做结算日志表（`hedge_open_cycle_close_log`，功能 ③a）、不做平仓执行（功能 ③b）。
- 不修改 ledger-flow 的拉取/刷新管线（scheduler 不动）；只新增只读查询。
- 不做利息多仓精确归属（数据现实：`interest_rows.isolated_symbol` 实盘全空，只能按资产维度近似）。
- 不改变 Start gate、订单、借币、划转、凭证路径。

---

## 2. 数据源与窗口规则（设计 v1 §7）

| 项目 | 表 | 对齐键 | 窗口 |
|---|---|---|---|
| 资金费 | `um_income_rows`（`income_type='FUNDING_FEE'`，`symbol`+`time_ms`） | symbol = cycle.symbol | `[opened_at, closed_at|now]`，可靠对齐 |
| 借币利息 | `interest_rows`（`asset`+`accrued_at_ms`） | asset = 周期的 base asset | 同窗口，单仓准确；多仓并存近似归属当前活跃周期 |

单位：ledger 为**毫秒**（ms），周期时间为**微秒**（us），查询层统一换算（`us / 1000`）。

费率到账晚于窗口：不追溯（Human 已拍板）；`closed_at` 之后到账且在下个窗口内的，归入下个周期（近似）。

---

## 3. 实现点（文件:行级）

### 3.1 ledger 汇总查询：`backend/ledger_flow/service.py` 新增方法

现有 `LedgerFlowService.get_flow_log(start_ms, end_ms)`（`:354`）返回明细块；`backend/ledger_flow/domain.py` 已有 `_sum_amounts`（`:269`，Decimal 求和、不可解析 → None 规则）。新增两个只读汇总方法：

```python
def sum_funding_by_symbol(self, symbol, start_ms, end_ms) -> str | None:
    """um_income_rows 中 income_type='FUNDING_FEE' AND symbol=? AND time_ms 在窗口内
    的 income Decimal 合计；任一行不可解析 → None（沿用 _sum_amounts 规则）。"""

def sum_interest_by_asset(self, asset, start_ms, end_ms) -> str | None:
    """interest_rows 中 asset=? AND accrued_at_ms 在窗口内的 interest 合计；规则同上。"""
```

实现复用 `LedgerStore.query_income_rows`/`query_interest_rows`（`backend/ledger_flow/store.py:344/324`，已支持 `[start_ms, end_ms]` 窗口 + `limit=None` 全量），在 service 层用 `domain._sum_amounts` 汇总。🔍 核对点：
- 只在已有明细查询上做 Decimal 求和，**不新增 SQL、不动 store 写路径、不触碰 scheduler**；
- `income_type` 过滤在 service 层做（`query_income_rows` 返回全类型，需排除 COMMISSION/REALIZED_PNL 等）；
- `None` 语义与占位 `"0"` 区分：`None` → 前端「暂无」，真零 → `"0"`（沿用 P7 规则，不可把未知渲染成 0）。

### 3.2 组合根接线：`backend/app/server.py` `_hedge_open_positions`（737-774）

`ledger_flow_service` 已在 `_Handler` 注入（`:124`，run() 注入）。仿照 `source_checked_at` 的 post-merge 附加模式（`:757-773`），在 `merge_positions` 之后、`_send_hedge_open` 之前：

```
1. 对每个 merged row：
   cycle_id 为空 → 保持占位（不查）
   window_us = [cycle_opened_at_us, cycle_closed_at_us 或 now_us]
   funding = ledger_flow_service.sum_funding_by_symbol(coin, window_us/1000)
   interest = ledger_flow_service.sum_interest_by_asset(base_asset, window_us/1000)
   row["accrued_funding"] = funding
   row["borrow_interest"] = interest
   row["net_pnl"] = (funding+interest) 若两者均可解析；任一 None → None（「暂无」，绝不部分相加）
2. ledger_flow_service 为 None（未注入）→ 三列保持占位
3. 单次请求 N 行 × 2 查询：行数少（实盘 9 行），SQLite 本地读可接受；行数多时按请求参数缓存（本轮不做，注明即可）
```

🔍 核对点：
- base_asset 推导复用 `merge_positions` 的 `_merge_base_asset` 规则（`domain.py:1676`，1000x 资产不自动对齐）——为免重复实现，可在 merge 层把 `base_asset` 附到行上（新增字段，前端不渲染）；
- 保持纯读：`_hedge_open_positions` 不触发 ledger 刷新、不写 ledger、不发网络请求；
- 迟到费率：窗口闭区间 `[opened, closed]`，查询天然只含窗口内行；超出窗口的迟到行不进入本周期（与 §2 规则一致）。

### 3.3 覆盖率检查与降级

- **复用现有 gap-aware 判定（P1-2 返工）**，不新造「只比端点」的粗糙版本：
  - 调用 `LedgerFlowService._build_coverage(window_start_ms, window_end_ms, store_cov)`（`backend/ledger_flow/service.py:373`，或为其做按窗口调用的公开包装）——它已实现 `complete = cov_start is not None and window_start >= cov_start and len(gaps) == 0`，**检查窗口内已记录缺口**；
  - 数据源字段名以 `get_coverage()`（`backend/ledger_flow/store.py:383`）返回为准：`interest_start_ms`/`interest_end_ms`/`income_start_ms`/`income_end_ms` + `gaps`（`{"source","start_ms","end_ms"}` 列表）。**不存在** `interest_coverage_start/end` 这类命名；
- 判定规则：`complete == True` → 统计为真值；`complete == False`（覆盖率未覆盖窗口端点、或窗口内存在缺口）→ 该行统计标 `stats_incomplete`（新字段，前端显示「统计区间不全」）；
- coverage 不存在（`coverage_exists()` 为 False，从未成功拉取）→ 三列保持「暂无」。
🔍 核对点：**绝不把覆盖率不足的窗口当成真值**——端点覆盖但中间有洞的窗口（scheduler 曾中断）同样算不完整；`_build_coverage` 是 service 层私有方法，实现时若直接调用需先确认其签名可用或补公开包装，不得复制其逻辑另造一份。

### 3.4 前端：`frontend/index.html`

- `renderHedgePositionsSection`（`:5235` 附近）三列的 `pendingCell(...)` 占位替换为真值渲染（`accrued_funding`/`borrow_interest` 用 `formatHedgeDecimal`，`net_pnl` 用 `formatHedgeSigned`，带正负着色）；
- `stats_incomplete` 时行尾标记追加「统计区间不全」；
- 已平仓周期行（`cycle_closed_at` 非空）增加「已平仓」标记与平仓时间（展示细节在功能 ③a 细化，本轮仅三列真值 + 标记位）。
🔍 核对点：与 fake 原型（`frontend/index.html` HISTORY_FAKE_ROWS）字段形状对齐，降低 ③a 接线漂移。

### 3.5 测试

- `backend/tests/test_ledger_flow_service.py`：`sum_funding_by_symbol`/`sum_interest_by_asset`（窗口过滤、income_type 过滤、不可解析→None、ms/us 换算）；
- `backend/tests/test_hedge_api.py`：mock ledger service 注入后三列真值；ledger 为 None → 占位；coverage 不足 → `stats_incomplete`；
- `frontend/self-check.js`：三列真值渲染、正负着色、「统计区间不全」标记。

---

## 4. 验收用例

| # | 场景 | 期望 |
|---|---|---|
| 1 | 活跃周期，窗口内有 3 笔 FUNDING_FEE | `accrued_funding` = 3 笔之和（Decimal 精度） |
| 2 | 已平仓周期 | 窗口 = [opened, closed]，不含 closed 之后到账的费率 |
| 3 | 利息单仓 | `borrow_interest` = 窗口内该资产利息之和 |
| 4 | 多仓并存同资产 | 近似归属当前活跃周期，行内/文档标注近似性 |
| 5 | ledger 未注入 / coverage 不存在 | 三列保持「暂无」，不渲染 0 |
| 6 | 窗口部分超出 coverage | `stats_incomplete` 标记，非真值 |
| 7 | 任意一行利息不可解析 | 该行 `net_pnl` = 「暂无」（绝不部分相加） |
| 8 | 迟到费率（closed 后到账） | 不进入本周期；ledger 刷新后在下个窗口自然可见 |

---

## 5. 风险

- 资金/PnL 展示含义变化 → HIGH_RISK：实现前独立计划评审，实现后 review-1 + review-2。
- 覆盖率不足静默显示偏小值的风险：§3.3 降级规则是硬约束，评审重点核查。
- 多仓利息近似：文档标注 + 展示层注明，不承诺精确归属。
- 依赖功能 2 的 `cycle_id`/`opened_at_us`/`closed_at_us` 输出：功能 2 未合入前本功能不可验收（排期顺序保证）。

---

## 6. 与排期的关系（ROADMAP「Planned」节）

- 功能 ② 排在功能 ①（周期表）之后：窗口数据依赖周期时间；
- 排在 ③a（平仓记录）之前：三列真值先点亮持仓页，历史仓位页在 ③a 复用同一汇总方法（不重复实现）。
