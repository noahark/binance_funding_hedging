# 全仓杠杆流水本地缓存 + 三栏流水展示

状态：计划已按 plan-review REWORK + Human 2026-08-10 决策改写；**授权进入实现派工**（Human 采纳「不必二次完整计划评审」的 Bookkeeper 建议：改写为净收缩，Bookkeeper 在实现 dispatch 内逐条核对冻结项）。本文**不**授权部署、服务重启、实盘写操作。

## 1. Human 已决定

- stage：`2026-08-10-cross-margin-flow-log-v1`。
- 目标：把 `GET /sapi/v1/margin/capital-flow`（不传 `symbol` = 全仓）增量缓存到本地，并在流水日志中于 **借币利息流水** 与 **合约资金流水** 之间展示 **全仓杠杆流水** 一栏。
- 数据源唯一主路径：`/sapi/v1/margin/capital-flow`（`api.binance.com`）。**不**使用已实测 404 的 `papi .../marginAccountFlow`。
- **历史深度（2026-08-10）**：**首次落档仅最近 1 天**（`now - 1d` … `now`）；之后按现有每小时节奏做增量，窗口为 `[capital_flow_coverage_end_ms - 3h, now]`。**不**回溯 30 天、**不**回溯 90 天。
- **不做分页（2026-08-10）**：前端默认展示约 20 条；不对往期完整性做分页级保证。
- **未提交前端（2026-08-10）**：第三栏假数据预览已单独提交为基线（`feat(ui): 流水日志三栏…`）；实现轮在该基线上换真数据，**沿用**既有 DOM id 与五桶筛选，接真数据时删除「预览」徽标与 `FLOW_LOG_CAPITAL_FAKE_ROWS`。
- 缓存形态：后端在现有小时调度/启动 catchup/手动刷新的**时机**顺带拉币安 → 落同库**新表** + `ledger_meta` 新 key → 页面只读本地；前端 60s 轮询仍只读本地 API。
- 风险分级：`HIGH_RISK`（账务含义 / 资金流水展示）。实现后 review-1 + review-2。
- 非目标：不改资产互转 POST；不自动划转；不把互转硬塞进 `um/income`；不接 `asset/transfer`；不做逐仓；**不做分页**。

## 2. 已观察问题与证据

1. 资产互转成功写入 `data/asset-transfer.sqlite3`，但 `um/income` 合约流水看不到对应记录。
2. 实盘摸排（`reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`）：
   - `GET /papi/v1/margin/marginAccountFlow` → **404**。
   - `GET /sapi/v1/margin/capital-flow` 不传 `symbol` → 全仓 **200**；`type=TRANSFER` 的 `tranId` 与本地互转一致；`amount` 正=入全仓、负=出全仓。
3. plan-review REWORK（handoff）：第三源若并入既有 coverage 聚合 / run 表会污染对冲净盈亏与 last_run；Human 决策后改为**完全独立状态**（见 §4）。

## 3. 产品形态（MVP）

时间窗与刷新控件与现流水日志共用：

```text
借币利息流水 | 全仓杠杆流水 | 合约资金流水
interest     | capital-flow  | um/income
```

前端基线已具备三栏 DOM；默认筛选（与基线五桶一致，删除「实现可选」措辞）：

| 默认开 | 默认关（可勾选） |
|---|---|
| `TRANSFER`（转账） | 买卖/手续费桶 `TRADE`（含 `BUY_*` / `SELL_*` / **`TRADING_COMMISSION`**） |
| `BORROW` / `REPAY` | 其他（强平族 `*_LIQUIDATION`、`SMALL_CONVERT` 等） |

转账展示文案（相对**全仓钱包**）：

- `amount > 0` → 入全仓（常见现货→统一）
- `amount < 0` → 出全仓（常见统一→现货）
- 不得与 `um/income` 的 `TRANSFER` 混筛选项而不标明数据源。

## 4. 技术边界（冻结）

### 4.1 必须做

1. `PrivateClient` 白名单增加 `GET /sapi/v1/margin/capital-flow`（deny-by-default）。
2. **拉取窗口（无切片、无 fromId 翻页）**  
   - 首次：`[now - 1d, now]`。  
   - 之后：`[capital_flow_coverage_end_ms - 3h, now]`（与既有利息/合约 3h 重叠缓冲同思想，但**只写 capital 自己的 meta**）。  
   - 单次**一页** `limit=1000`。  
   - 返回行数 **&lt; 1000** → 视为该窗口拉完。  
   - 返回**满 1000** → 标记该窗口「可能不全」（meta + 响应可观测字段），**不**猜测顺序、**不**续翻 `fromId`。  
   - 权重约 100 IP/次；搭在现有 `run_once` 时机执行即可。
3. **新表** `margin_capital_flow_rows`（`CREATE TABLE IF NOT EXISTS`，**零迁移**）  
   - 主键 **`id`**（币安流水 id）。  
   - 字段至少：`id, tran_id, time_ms, asset, flow_type, amount, first_seen_at_ms`。  
   - 金额 **TEXT 原样**。  
   - **不设** `first_seen_run_id`（不写 `flow_refresh_runs`）。  
   - 同一 `tran_id` 多 `flow_type` 行全部保留（不同 `id`）。
4. **状态只进 `ledger_meta` 新 key（零迁移）**，建议：  
   - `capital_flow_coverage_start_ms`  
   - `capital_flow_coverage_end_ms`  
   - `capital_flow_last_run`（JSON：完成时间、状态、错误短码、拉取行数、新增行数、可选 `possibly_incomplete`）  
5. **`GET flow-log` additive**  
   - 新增顶层块（冻结名：`capital_flow`）：含 rows / 可选 status 摘要；缺失时前端中栏**空态**（不是错误态）。  
   - 可选 `coverage.by_source.capital_flow` 仅作展示；**不参与** aggregate。  
   - **`schema_version` 保持 `private-ledger/v2` 不 bump**（`store` 常量、响应、`docs/api/public-market-contract.md` 三处同串）。
6. 前端：在基线三栏上接 `payload.capital_flow`；删除预览徽标与 `FLOW_LOG_CAPITAL_FAKE_ROWS`；隐私遮罩与既有一致；self-check 更新。
7. 测试：新表入库幂等、meta 推进、满 1000 标记、capital 失败不影响利息/合约 run、`coverage_for_window` 在 capital 从未成功时 complete 与接入前一致、前端缺块空态、回归既有 ledger/self-check。

### 4.2 必须不变 / 硬隔离（消解 P0-1、P0-2）

1. 利息与 `um/income` 既有语义、表结构、幂等键、默认筛选、`flow_refresh_runs` 列与行语义。  
2. **不写** `flow_refresh_runs`（不加列、不插 capital 行）。  
3. **不进** coverage 的 aggregate `start_ms` / `end_ms` / `complete` / `pending_tail_ms`。  
4. **不进** delta 基线、**不进** `_is_success_run`、**不进** `_format_last_run` 的默认「最近一条」。  
5. `coverage_for_window` 语义与消费方（对冲任务持仓周期资金费/利息/净盈亏，`server.py` 既有路径）**逐位不变**。  
6. capital 拉取用**独立 try/except**：失败只写 capital 的 meta，利息/合约 run 成功判定不受影响。  
7. 资产互转 POST、审计、确认弹窗与锁定逻辑不变；capital-flow **仅 GET**。

### 4.3 明确非目标

- `asset/transfer` 历史接入。  
- 逐仓 `symbol` 流水。  
- 自动归集 / 自动还款 / 改 gate。  
- 绕过本地库直打币安做展示。  
- **分页**（fromId 续翻、前端翻页控件、>1000 行完整回补）。  
- 30/90 天历史回补。  
- 修改 `schema_version` 或既有两源 coverage 聚合公式。

## 5. 验收检查（可执行）

1. 不传 `symbol` 的 capital-flow 行入库后，中栏默认筛选可见 `TRANSFER`/`BORROW`/`REPAY`。  
2. 已知互转 `tranId` 形状可与本地行对应；`+`/`-` 文案为入全仓/出全仓。  
3. 同一 `tran_id` 多 type 行全部保留，互不覆盖（`id` 主键）。  
4. 小时/手动刷新只插入未见过的 `id`；失败不推进 `capital_flow_coverage_end_ms`（或按实现冻结：仅成功窗口推进）。  
5. **单次请求窗口跨度 ≤ 1 天**；返回满 1000 行时 meta/响应标记「可能不全」。  
6. **`capital` 源从未成功或持续失败时，`coverage_for_window(既有窗口)` 的 `complete` 与接入前逐位相同**（防 P0-1）。  
7. 既有利息/`um_income` self-check 与 backend ledger 测试不破；缺 `capital_flow` 块时中栏空态。  
8. 三栏时间窗切换同源；隐私模式金额 `****`。  
9. `flow_refresh_runs` 行数/列集合在升级后与 capital 写入无关（无新 capital 列、无 capital kind 行污染 last_run）。

## 6. 建议实现落点

- `backend/services/private_client.py` — whitelist + 单页 fetch  
- `backend/ledger_flow/store.py` — 新表 + `ledger_meta` 新 key（**不**改 `flow_refresh_runs`）  
- `backend/ledger_flow/service.py` — run_once 内独立 try 拉取/入库/写 meta；flow-log 装配 `capital_flow`  
- `backend/ledger_flow/domain.py` — 如需 normalize 行形状  
- `backend/tests/test_ledger_flow_*.py` 等  
- `frontend/index.html` + `frontend/self-check.js` — 假数据换真数据  
- `docs/api/public-market-contract.md` — private-ledger additive 说明（v2 不 bump）

若必须改动上述边界外生产文件，停止并报告 blocker。

## 7. 输入基线

- recon：`reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`  
- 形状：`.../sanitized/endpoint-shape-for-design.json`  
- 双账本设计：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（对照 cadence；本源**不**并入其 coverage 聚合）  
- plan-review handoff：`evidence/cross-margin-flow-log-plan-review.handoff.md`  
- UI 基线提交：`a11a873`（三栏假数据预览）

## 8. 口径（P2-2）

capital-flow 站在**全仓钱包**记账。不经全仓的划转（例如 MAIN 与 UM/CM 直转等）**不会**出现在中栏。中栏**不是**「所有互转的全集」；与资产互转审计表可按 `tranId` 对账，但是产品上两套视角。

## 9. Bookkeeper 冻结项核对（实现 dispatch 前，2026-08-10）

| # | 改法来源 | 已落入正文 |
|---|---|---|
| 1 | §1 决策 1–3 + 首次 1 天 | 是 |
| 2 | §3 TRADING_COMMISSION∈TRADE 默认关 | 是 |
| 3 | §4.1.2 无切片、limit=1000、满页标记 | 是 |
| 4 | §4.1.3 新表零迁移、无 first_seen_run_id | 是 |
| 5 | §4.1.4/5 缺块空态、v2 不 bump | 是 |
| 6 | §4.2 不进 aggregate/run/delta/success/last_run | 是 |
| 7 | §4.3 不做分页 | 是 |
| 8 | §5.5 单次≤1 天 + 满 1000 标记 | 是 |
| 9 | §5 新增 coverage_for_window 不变断言 | 是 |
| 10 | §6 ledger_meta；§8 互转口径 | 是 |
