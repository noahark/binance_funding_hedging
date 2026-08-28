# 已还款利息按还款时价格折算 — 最小开发方案（P1 产物）

- stage: `2026-08-28-repaid-interest-price-v1`
- author: Planner `claude_glm`（zhipu_glm）
- created: 2026-08-28 17:15 CST
- base_sha: `4e6f4909dd17eb43c08f0f393258793df24a6ec7`
- 状态: 计划待评审（P2，`opus5`/anthropic，只读）；本文档不授权任何实现、写库或部署。

## 1. 产品口径（Human 已固定，不可改写）

1. **未匹配成功还款的利息 = 开放暂估**：按公开行情快照**当前**现货买一价
   （`opening_quotes.spot_bid_price`，`status="fresh"`）动态折 USDT，随价变动。
2. **匹配到成功还款的利息 = 终态固定成本**：按该还款**发生时刻**的价格折 USDT，
   折算后不再随当前价变动。还款时历史曲线重算一次（该资产历史点全部用新口径
   重新现算）是**预期结算动作**，不是需要消除的不稳定。
3. **禁止**把「利息发生（计提）时冻价」当默认或回退（Human 2026-08-28 17:06 CST
   否决）。
4. **fail-closed 保留**：无可靠适用价格（开放行缺当前价、或已还款行缺还款价）→
   该资产利息不计入、登记缺价、净收益「暂无」。绝不按 0、绝不残缺相加、绝不用
   另一口径的价格顶替。

## 2. 缺陷现状（已核验证据）

- 生产 `interest_rows` 仅一条 STORJ `ON_BORROW`：本金 `200`、利息 `0.0130242`、
  `accrued_at_ms` 对应 `2026-08-20 14:00:00 CST`。
- 生产 `margin_repay` 有一条 STORJ `amount="0"`（=全部还款）、`status=succeeded`、
  `update_time` 对应 `2026-08-20 14:31:03.837 CST` 的记录。
- STORJ 无对冲任务、周期或平仓订单——任何依赖 close order 的设计解决不了本缺陷。
- 现状代码（`server.py` `_handle_pnl_series` 与 `_hedge_open_positions`、
  `domain.py` `build_pnl_series.to_usdt`）把**所有**币本位利息一律按当前快照价
  折算；STORJ 合约 `SETTLING` 后被快照排除 → 缺价 → 曲线与持仓统计「暂无/成本不全」。
- `margin_repay` 表无还款时价格列、无对 `interest_rows` 的外键。

## 3. 设计

### 3.1 匹配规则（确定性，按资产、时间 FIFO）

对每条 `interest_rows` 行 `(asset, accrued_at_ms)`：

> 匹配对象 = 同 `asset` 的 `margin_repay` 记录中，**结算时刻 ≥ `accrued_at_ms` 的
> 第一条 `status='succeeded'` 记录**；不存在则落入**开放桶**。

- **结算时刻**（单一权威定义）：`update_time`（币安回传毫秒字符串）可解析时用它；
  否则回退 `updated_at_us // 1000`（本地落终态时刻，与真实还款相差一次 HTTP 往返，
  列 `NOT NULL` 恒有值）。分组内排序键 `(结算时刻 ms, client_request_id)`，保证
  同毫秒多条时结果确定。
- **只认 `succeeded`**。`failed` 不匹配（明确没还）。`pending` 不匹配（未发出）。
  `unknown` 不匹配：它是「可能已还」的显式态而非成功事实；把 unknown 当已还会给
  实际未还的利息错误冻价，当未还则维持开放暂估（与现状一致、不制造假终态），
  fail-closed 取后者。人工在币安核实后以新的成功还款记录自然收口。
- **字段语义不臆造**（P1 验收红线）：`amount="0"` 是「全部还款」的既有语义，
  不是缺失；`repaid_amount IS NULL` 是「币安未回传精确数量」（INJ 实测形态），
  不否定成功。匹配判定只消费 `status` + `asset` + 结算时刻，不消费金额。
- **领域依据**（PROJECT_STATE 2026-08-16 已实测两条证据）：任何一次成功还款
  （含部分还款）都会结清该资产当时**已计提**的全部利息——SNX 借 100 还 50 后
  `borrowed − 本金` 与还款前累计息 8 位全等；INJ 还款瞬间 `borrowed` 吸收当时
  `crossMarginInterest`。因此「计提后第一次成功还款即该利息行的终态事件」与
  交易所行为一致，部分还款、反复借贷（息1→还1→息2→还2）都被同一规则覆盖，
  无需数量配对，也就无需新增外键或数量账本。

### 3.2 还款时价格（单一权威定义与两个来源）

> **还款时价格 = 该还款结算时刻的 `{asset}USDT` 现货买一价**，落库于
> `margin_repay.repay_price_usdt`（TEXT，Decimal 字符串），来源标记
> `margin_repay.repay_price_source`。

- **未来还款（事件时捕获）**：`_handle_margin_repay_post` 在严格成功分支
  `_dispatch_margin_repay` 返回后、`store.resolve` 前，从公开行情快照
  （`service.get_snapshot()`，纯读、零上游请求）取 `symbol = f"{asset}USDT"` 的
  `opening_quotes.spot_bid_price`（仅 `status="fresh"` 且非空）。取到 →
  `repay_price_source="snapshot_spot_bid"`；取不到 → 两列写 NULL，**不改变还款
  终态**（还款成功是主事实，价格缺失只让匹配利息保持 fail-closed）。价格查找键
  规则与现有两处现价查找逐字相同（`price_map[symbol]` ← `spot_bid_price`），
  bStock 等解析不齐的资产维持现状 fail-closed，不在本阶段扩围。
- **存量 succeeded 行（含 STORJ，历史回补）**：一次性只读脚本
  `scripts/backfill-repay-prices.py` 查币安**公共**现货 K 线
  （`GET /api/v3/klines`，无签名、只读），确定性规则：
  1. 取**包含结算时刻的那根 1m K 线的 `close`**（`source="kline_1m_close"`）；
  2. 该分钟无成交 → 取**不早于结算时刻的第一根存在的 1m K 线的 `open`**
     （`source="kline_1m_open_fallback"`）；
  3. 仍取不到（交易对彻底无历史数据）→ 保持 NULL，该利息行维持 fail-closed
     「暂无」，绝不以当前价或计提价顶替。
  脚本只处理 `status='succeeded' AND repay_price_usdt IS NULL` 的行（幂等，可重复
  运行），支持 `--dry-run`。**运行写生产库，须 Human 单独授权**；交付只含脚本与
  测试。STORJ 合约 `SETTLING` 不影响现货历史 K 线；实现阶段先以一次只读
  `curl` 验证 `STORJUSDT` 在 `2026-08-20 14:31 CST` 附近有 K 线数据，把输出存入
  阶段 evidence。
- **回补与捕获的取舍**：捕获走快照（与现价同体系、零请求、含买一价精度），
  回补走 K 线（历史时点唯一可审计来源）；两者都落在同一列、同一折算语义，
  来源列使任何一行价格可追溯到其证据。

### 3.3 统一折算权威（两消费者同一算法）

新增 `backend/ledger_flow/domain.py` 纯函数（零 I/O，供两处共用，是本方案唯一的
匹配+折算实现）：

```python
def build_repay_match_index(repay_records) -> dict
    # succeeded 记录按 asset 分组，组内按 (结算时刻 ms, client_request_id) 升序。

def match_interest_repay(asset, accrued_at_ms, index) -> Optional[dict]
    # 返回匹配的 succeeded 还款记录；None = 开放桶。

def interest_usdt_value(interest_amount, asset, matched, price_map) -> Optional[Decimal]
    # matched 为 None → price_map[f"{asset}USDT"] 当前价（缺 → None）；
    # matched 非 None → Decimal(matched["repay_price_usdt"])（NULL/不可解析 → None）；
    # USDT 本位与真零沿用现有 to_usdt 规则。
```

- **PnL 曲线**：`build_pnl_series` 新增可选参数 `repay_records=None`（缺省空 =
  现行为，向后兼容）；利息分支从 `to_usdt` 改为逐行
  `interest_usdt_value`。已匹配但缺还款价 → 该资产进 `unpriced_assets`
  （与开放行缺当前价同一出口、前端零改动），利息不计入、净收益遮蔽。
- **持仓视图**：`LedgerFlowService` 新增
  `sum_interest_usdt_by_asset(asset, start_ms, end_ms, price_map, repay_records)`
  ——窗口内逐行匹配折算、Decimal 求和，任一行 None → 整体 None；真零返回
  `"0"`（0 × 任何价 = 0，无需价格）。「借币利息」币本位列继续用现有
  `sum_interest_by_asset` 不变。
- **`_hedge_open_positions`**：`borrow_interest_usdt` 改调上述新方法（替换现有
  行内乘法块）；`net_pnl` 公式、遮蔽条件不变。
- **close_log（`_finalize_close_task`）不触碰**：它固化的是币本位利息合计
  （`borrow_interest`，历史仓位页直接显示币本位原值，不折 U），不随价格重画，
  与本缺陷无关。`sum_interest_by_asset` 因此保留。
- **`margin_repay_store` 未配置**（仅测试/未配置环境）→ 曲线与持仓传空
  `repay_records`，行为等同「无还款记录」（现状）。生产恒配置该 store。

### 3.4 Schema 变更、迁移与回滚

- `margin_repay` 新增两列（仅此一处 schema 变更；`interest_rows` 不动）：

  ```sql
  ALTER TABLE margin_repay ADD COLUMN repay_price_usdt TEXT;
  ALTER TABLE margin_repay ADD COLUMN repay_price_source TEXT;
  ```

- 迁移幂等：`MarginRepayStore.__init__` 在 `CREATE TABLE IF NOT EXISTS` 后按
  `PRAGMA table_info(margin_repay)` 逐列检查、缺则 `ALTER ADD`（新库直接建全列）。
  与既有库兼容：旧行新列为 NULL，旧代码按名取列不受多列影响。
- 回滚：`git revert` 交付 commit 即回代码；残留两列对旧代码无害，无需 DROP。
- 回补脚本重复运行只补 NULL 行，天然幂等。
- `resolve()` 增可选参数 `repay_price_usdt` / `repay_price_source`；
  `_row_to_doc` 增两键（POST/GET 响应 additive 扩列，四态展示与前端
  `body.status` 信任链不变）。新增 `list_records()` 供读路径取全量记录。

## 4. 改动文件清单（bounded）

| 文件 | 改动 |
|---|---|
| `backend/margin_repay/store.py` | 两列迁移、`resolve` 参数、`_row_to_doc`、`list_records()` |
| `backend/app/server.py` | 还款成功时捕获价格；`_hedge_open_positions` 换 `sum_interest_usdt_by_asset`；`_handle_pnl_series` 传 `repay_records` |
| `backend/ledger_flow/domain.py` | §3.3 三个纯函数；`build_pnl_series` 利息分支改造 |
| `backend/ledger_flow/service.py` | `sum_interest_usdt_by_asset` |
| `backend/tests/test_ledger_flow_domain.py` | §5 匹配/折算/曲线用例 |
| `backend/tests/test_ledger_flow_service.py` | 新 service 方法用例 |
| `backend/tests/test_margin_repay.py` | 价格捕获/NULL/迁移幂等/响应键 |
| `scripts/backfill-repay-prices.py` | 新建：一次性回补脚本（含 `--dry-run`） |
| `docs/api/public-market-contract.md` | 新增 additive amendment：双口径折算、匹配规则、新列、fail-closed 语义 |

前端 `frontend/index.html` / `frontend/self-check.js` **预期零改动**：wire 形状
不变（缺价仍走 `unpriced_assets` → 「成本不全」遮蔽 + 点名），已还款行 merely
从「缺价遮蔽」变为「有价计入」。仅当评审要求脚注文案区分两种缺价来源时才允许
最小文案调整，届时同步 self-check 断言。

## 5. 测试计划（全部离线、可执行）

`python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q`
（实现任务另跑全量后端套件与前端 self-check，排除既有白名单误报。）

domain（`test_ledger_flow_domain.py`）：

1. `accrued` 早于 succeeded 结算时刻 → 匹配；succeeded 早于 `accrued` → 开放。
2. `amount="0"`（全部）与 `repaid_amount=None` 的 succeeded 均匹配（字段语义）。
3. 部分还款（`amount="5"`）同样匹配并结清此前计提利息。
4. 反复借贷：息1→还1→息2→还2，各自匹配到正确一条；多笔 succeeded 夹一条利息
   时取 `accrued` 之后第一条。
5. `failed` / `unknown` / `pending` 均不匹配。
6. `update_time` 缺失/不可解析 → 回退 `updated_at_us//1000`。
7. **核心时序断言**（验收 6）：开放行在 `price_map` 改变时值随之改变 → 引入匹配
   还款后值切换为还款价（恰一次）→ 此后继续改变 `price_map` 值不再变化。
8. 已匹配行 `repay_price_usdt` NULL → `interest_usdt_value` 返回 None（不暂估、
   不按 0、不用计提时价）。
9. `build_pnl_series`：已还款行用还款价入利息线；缺还款价资产进
   `unpriced_assets` 且不计入；不传 `repay_records` 时输出与现行为逐位一致
   （回归锁定）。
10. STORJ 场景复刻：一条 STORJ 利息 + `amount="0"` succeeded + 回补价 → 曲线
    利息线计入 `0.0130242 × 回补价`、`unpriced_assets` 为空；去掉回补价 → 遮蔽。

service（`test_ledger_flow_service.py`）：

11. 周期窗口内已还款 + 开放混合 → 各按各自价格折算求和；任一 None → 整体 None。
12. 真零利息（`"0"`）返回 `"0"`，无需任何价格。

margin_repay（`test_margin_repay.py`）：

13. `_RESULT_KEYS` 增两键；严格成功 + 桩快照有价 → `repay_price_usdt`/
    `repay_price_source` 落库并出现在响应。
14. 严格成功 + 快照无该 symbol → 两列 NULL，`status` 仍 `succeeded`（价格缺失
    不改变还款终态）。
15. 旧 schema 库（无新列）打开后自动补列；重复打开幂等；旧行两列为 NULL。

回补脚本：`--dry-run` 只打印计划写入；kline 规则两分支与「无数据保持 NULL」
按桩 HTTP 响应断言（脚本测试随脚本文件落位，允许最小 `test_backfill_repay_prices.py`
或并入现有脚本测试形态）。

## 6. 生产验证（实现交付并部署后，均须 Human 授权；本计划不授权）

1. 部署前：`curl` 只读验证 `STORJUSDT` 公共 1m K 线覆盖 `2026-08-20 14:31 CST`，
   输出存阶段 evidence。
2. 部署后只读检查：曲线 `unpriced_assets` 不再含 STORJ、净收益恢复数值；利息线
   该桶值 = `0.0130242 × 回补价`。
3. 回补脚本运行（写生产库）→ 复核 `margin_repay` STORJ 行两列非空且
   `source` 符合规则。
4. 下一笔真实还款发生后：复核新行 `repay_price_usdt` 已事件时捕获，且该资产
   历史利息点仅重算一次后稳定。

## 7. 非目标（不做）

- 不为 close-log/历史仓位页引入 U 折算（其币本位展示是既有决定）。
- 不修 bStock / 1000x 利息资产与快照价格键不齐的问题（维持现状 fail-closed）。
- 不给 `margin_repay` ↔ `interest_rows` 建外键或数量配对账本（匹配按时间 FIFO
  足以确定，见 §3.1）。
- 不引入还款价格的快照存储表、不缓存历史 K 线。
- 不改前端展示结构；不改 `unknown` 还款的人工核对流程。

## 8. 风险与评审焦点（供 P2）

1. **匹配规则的时间 FIFO 是本方案最大的口径决定**：它依赖「一次成功还款结清
   当时已计提利息」的币安行为（两条实测证据），若评审掌握相反证据（例如存在
   只还本金不结息的还款形态），规则需改为数量配对——那是数量级更大的方案。
2. **还款时价格的两源体系**（快照买一 / K 线 close）在「同一结算时刻」语义上是
   两种近似；已用来源列显式区分，评审可裁定是否需要统一为单一来源。
3. **`unknown` 还款不匹配**会让「实际已还但本地 unknown」的利息停留在开放暂估
   （成本随价浮动）；这是 fail-closed 取舍，评审可裁定是否需在 UI 提示。
4. **缺还款价遮蔽净收益**：比现状更严的遮蔽只发生在「已匹配但价格不可得」的
   新情形，且仅当回补也失败；STORJ 是唯一已知存量案例。
5. 迁移为纯 additive 两列，无数据搬移；评审关注点应在匹配确定性与测试充分性。
