# 全仓杠杆流水本地缓存 + 三栏流水展示

状态：待独立计划评审；本文不授权实现、实盘操作、数据库迁移执行、服务重启或部署。

## 1. Human 已决定

- stage：`2026-08-10-cross-margin-flow-log-v1`。
- 目标：把 `GET /sapi/v1/margin/capital-flow`（不传 `symbol` = 全仓）增量缓存到本地，并在流水日志中于 **借币利息流水** 与 **合约资金流水** 之间增加 **全仓杠杆流水** 一栏。
- 数据源唯一主路径：`/sapi/v1/margin/capital-flow`（`api.binance.com`）。**不**使用已实测 404 的 `papi .../marginAccountFlow`。
- 缓存形态：与现有双账本一致——后端定时/启动/手动刷新拉币安 → 落 `data/ledger-flow.sqlite3`（或同库新表）→ 页面只读本地；前端 60s 轮询仍只读本地 API，不直打币安。
- 风险分级：`HIGH_RISK`（账务含义 / 资金流水展示）。实施前须独立跨 provider 只读计划评审；实现后 review-1 + review-2。
- 非目标：不改资产互转 POST 路径；不自动发起划转；不把互转硬塞进 `um/income`；本 stage 不做万向划转历史 `asset/transfer` 全量接入（可在文案/后续用 `tranId` 对账，非本 stage 必做）。

## 2. 已观察问题与证据

1. 资产互转（现货⇄统一）成功写入 `data/asset-transfer.sqlite3`，但合约资金流水（`um/income`）中看不到对应记录。
2. 实盘摸排（`reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`）：
   - `GET /papi/v1/margin/marginAccountFlow` → 全参数 **404**。
   - `GET /sapi/v1/margin/capital-flow` 不传 `symbol` → 全仓流水 **200**；`type=TRANSFER` 的 `tranId` 与本地互转一致；`amount` 正=入全仓、负=出全仓。
   - 今日 ±10 USDT 互转已在 capital-flow 中命中。
3. 现有流水日志两栏：利息 = `interestHistory` 本地表；合约 = `um_income` 本地表；调度约每小时增量。

## 3. 产品形态（MVP）

时间窗与刷新控件与现流水日志共用：

```text
借币利息流水 | 全仓杠杆流水 | 合约资金流水
interest     | capital-flow  | um/income
```

全仓栏默认筛选（前端）：

| 默认开 | 默认关（可勾选） |
|---|---|
| `TRANSFER` | 买卖拆行 `BUY_*` / `SELL_*` |
| `BORROW` / `REPAY` | 强平族 `*_LIQUIDATION`、`SMALL_CONVERT` 等 |
| （实现可选）`TRADING_COMMISSION` | 其余 |

转账展示文案（相对全仓钱包）：

- `amount > 0` → 入统一/全仓（常见现货→统一）
- `amount < 0` → 出统一/全仓（常见统一→现货）
- 不得把 capital-flow 的 `TRANSFER` 与 `um/income` 的 `TRANSFER` 混为同一筛选项而不标明数据源。

## 4. 技术边界（计划评审须核对）

### 4.1 必须做

1. `PrivateClient` 白名单增加 `GET /sapi/v1/margin/capital-flow`（deny-by-default）。
2. 单页 fetcher + service 增量窗口：文档单次 `start/end` ≤ **7 天**、历史约 90 天 → **按 ≤7 天切片**推进 coverage；权重约 **100 IP**，cadence 对齐现有小时调度（启动 catchup / scheduled / manual refresh 三源之一或扩展同一 run）。
3. 本地表（建议名 `margin_capital_flow_rows` 或等价）：至少 `id, tran_id, time_ms, asset, flow_type, amount, first_seen_*`；金额 **TEXT 原样**；幂等不得只用 `tranId`（同一 `tranId` 可多行不同 type）——以 **`id` 唯一** 或 `(id)` / 文档+实测可证明的复合键。
4. `GET flow-log` 响应扩展第三块（字段名由计划冻结，须 additive、旧前端可忽略未知键或同步改前端）。
5. 前端三栏布局 + 筛选 + 与现有隐私遮罩/时间格式一致；self-check 覆盖默认筛选与转账符号文案。
6. 测试：normalize/dedup/coverage 切片、fetcher mock、API 形状、前端 self-check；不接实盘写。

### 4.2 必须不变

1. 利息与 `um/income` 既有语义、表结构、幂等键与默认筛选（除非 additive 扩展响应）。
2. 资产互转 POST、`asset-transfer` 审计、确认弹窗与锁定逻辑。
3. 不引入 POST 到币安的新路径；capital-flow 仅 GET。
4. 不把 USDT 可转出额算法推广到其它币（既有 Q4 纪律无关本栏则不动）。

### 4.3 明确非目标

- `asset/transfer` 双 type 历史接入（可选 follow-up）。
- 逐仓 `symbol` 流水。
- 自动归集、自动还款、改 gate。
- 为展示去币安实时逐笔查询（禁止绕过本地库）。

## 5. 验收检查（计划须落到可执行断言）

1. 不传 `symbol` 的 capital-flow 行入库后，页面中栏可见；默认筛选下可见 `TRANSFER`/`BORROW`/`REPAY`。
2. 以已知互转 `tranId`（ recon 中的样本形状）在本地库与 UI 能对应；`+amount`/`-amount` 文案方向正确。
3. 同一 `tranId` 多 type 行（成交拆行）全部保留，互不覆盖。
4. 小时调度/手动刷新只增不改已存在 `id`；coverage 不越过失败窗。
5. 7 天切片：跨 >7 天的 catchup 不单次越界请求。
6. `um/income` 与利息栏回归：既有 self-check / backend 测试不破。
7. 前端三栏在流水看板时间窗切换下同源；隐私模式金额 `****`。

## 6. 建议实现落点（供计划收紧，非授权扩域）

- `backend/services/private_client.py` — whitelist + page fetch
- `backend/ledger_flow/{domain,store,service,scheduler}.py` — 第三源
- `backend/app/server.py` — flow-log 响应装配（若在此）
- `backend/tests/test_ledger_flow_*.py` 等
- `frontend/index.html` + `frontend/self-check.js`
- `docs/api/public-market-contract.md` — private-ledger 三栏 additive 说明

若计划评审认为必须改动边界外生产文件，应在 REWORK 中点名调用链，不得在实现时静默扩域。

## 7. 输入基线

- recon：`reports/api-samples/2026-08-margin-account-flow-recon-v1/20260810T062742Z/recon.md`
- 形状：`.../sanitized/endpoint-shape-for-design.json`
- 现网双账本设计：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（对照 cadence/coverage，不复制全文）
