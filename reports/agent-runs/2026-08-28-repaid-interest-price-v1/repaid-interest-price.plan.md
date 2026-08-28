# 已还款利息按还款时价格折算 — 最小开发方案（P3 修订版）

- stage: `2026-08-28-repaid-interest-price-v1`
- author: Planner `claude_glm`（zhipu_glm）
- created: 2026-08-28 17:15 CST（P1）；**P3 修订 2026-08-28 18:17 CST**
- base_sha: `4e6f4909dd17eb43c08f0f393258793df24a6ec7`
- 状态: 修订稿待 P4 只读复评（`opus5`/anthropic）；本文档不授权任何实现、写库或部署。

### 修订记录（P3，2026-08-28 18:17 CST）

依据 P2 计划评审 `REWORK`（`evidence/P2-repaid-interest-price-plan-review.handoff.md`，
F1-F4 均为 in-range）与 Human 两项固定决定修订：

1. **F1 + Human 决定一（终态口径）**：删除「任一成功还款结清已计提利息」的错误领域
   依据（所引 PROJECT_STATE 371-380 证据证明的是**资本化**，不是结清）。新规则：
   **部分还款绝不锁价**；只要资产仍有借款持仓/未偿余额，全部相关历史利息继续按
   当前价动态折 U；只有**可确认借款完全归零**的还款才是终态事件，按该次完全还款
   的价格切换一次。资本化不是结清证据。
2. **F2 + Human 决定二（路径 A）**：保留还款成功后的内存快照取价，但整个取价/解析
   必须异常隔离；`SnapshotNotReady` 或任何异常只留下 NULL，**绝不能让
   `store.resolve` 的还款终态落库被跳过**。该价格如实称为**捕获时刻快照买一价**，
   不是真实还款成交汇率。
3. F3：`list_records()` 返回形状显式包含 `updated_at_us`，回退结算时刻可达。
4. F4：价格来源命名按语义区分（捕获时刻快照买一 vs 历史 1m K 线），定义强度不超过
   代码可证明的语义（`fresh` 仅表示四价齐全，无时效含义）。
5. O1-O3 具名（§7/§8）：本表不覆盖交易所侧手动/自动还款；生产回补含容器进入与
   写前备份；缺价遮蔽是全局的。

P2 认可并保留的骨架：单一折算权威（§3.3）、两消费者收口、additive 迁移、幂等
NULL-only 回补、测试编排。

## 1. 产品口径（Human 已固定，不可改写）

1. **未确认完全归零 = 开放暂估**：资产仍有借款持仓/未偿余额（或无法确认归零）时，
   该资产**全部**历史利息行按公开行情快照**当前**现货买一价
   （`opening_quotes.spot_bid_price`，`status="fresh"`）动态折 USDT，随价变动。
2. **可确认借款完全归零的还款 = 终态事件**：该资产在此还款结算时刻之前计提的
   利息行，切换为按该次还款的存储价格折算，此后不再随当前价变动。切换发生一次；
   还款时历史重算一次（该资产历史点按新口径全部重新现算）是预期结算动作。
3. **部分还款绝不锁价**；交易所把已计提利息并入 `crossMarginBorrowed` 的资本化
   行为**不是**结清证据（PROJECT_STATE 371-380 实测：SNX 借 100 还 50 后利息
   `0.10709571` 仍留在债务内继续生息；INJ 同形）。
4. 归零后再次借款（re-borrow）开启新的开放区间：新计提的利息行回到当前价暂估，
   直到下一次可确认归零的还款。
5. **禁止**把「利息计提时冻价」当默认或回退（Human 2026-08-28 否决）。
6. **fail-closed 保留**：无可靠适用价格（开放行缺当前价、或终态行缺还款价）→
   该资产利息不计入、登记缺价、净收益「暂无」。绝不按 0、绝不残缺相加、绝不用
   另一口径的价格顶替。归零证据不可得 → 该还款不构成终态事件，相关利息保持开放
   暂估（不是遮蔽，是口径内的正确状态）。

## 2. 缺陷现状（已核验证据）

- 生产 `interest_rows` 仅一条 STORJ `ON_BORROW`：本金 `200`、利息 `0.0130242`、
  `accrued_at_ms` 对应 `2026-08-20 14:00:00 CST`。
- 生产 `margin_repay` 有一条 STORJ `amount="0"`、`status=succeeded`、`update_time`
  对应 `2026-08-20 14:31:03.837 CST` 的记录；该还款后 8 天无新 STORJ 利息行，
  当前账户无 STORJ 借款——完全归零可由回补规则推定（§3.2 历史回补）。
- STORJ 无对冲任务、周期或平仓订单——任何依赖 close order 的设计解决不了本缺陷。
- 现状代码（`server.py` `_handle_pnl_series` / `_hedge_open_positions`、
  `domain.py` `build_pnl_series.to_usdt`）把**所有**币本位利息一律按当前快照价
  折算；STORJ 合约 `SETTLING` 后被快照排除 → 缺价 → 曲线与持仓统计「暂无/成本不全」。
- `margin_repay` 表无还款时价格列、无还款后负债证据列、无对 `interest_rows` 的外键。
- `repay_margin_debt` 响应（`hedge_open_live_client.py:538`）只中继
  `success/asset/amount/updateTime`，**不含剩余负债字段**——归零无法从还款响应本身
  证明；`amount=None` 的语义是「偿还资产足够时偿还全部」，`repaid_amount` 可为
  `NULL`，二者都不构成归零证明。

## 3. 设计

### 3.1 匹配规则（确定性：按资产、时间 FIFO、只认带归零证据的完全还款）

对每条 `interest_rows` 行 `(asset, accrued_at_ms)`：

> 匹配对象 = 同 `asset` 的 `margin_repay` 记录中，**结算时刻 ≥ `accrued_at_ms` 的
> 第一条「succeeded 且债务归零证据成立」的记录**；不存在则落入**开放桶**。

- **债务归零证据（单一权威判定）**：该还款行存储的 `repay_after_borrowed` 与
  `repay_after_interest` 均可解析为 Decimal 且 `== 0`。任一为 NULL、不可解析或
  非零 → 证据不成立 → 该还款不构成终态事件（含一切部分还款形态：其观测值必然
  非零或缺失）。**`status='succeeded'`、`amount="0"`、`repaid_amount` 缺失均不
  被等同为归零事实**——它们只说明「请求成功/请求全额/未回传数量」。
- **结算时刻**（单一权威定义）：`update_time`（币安回传毫秒字符串）可解析时用它；
  否则回退 `updated_at_us // 1000`（本地落终态时刻，与真实还款相差一次 HTTP 往返，
  列 `NOT NULL` 恒有值，经 §3.4 `list_records()` 导出、读取可达）。分组内排序键
  `(结算时刻 ms, client_request_id)`，同毫秒多条时结果确定。
- **只认 `succeeded`**。`failed` 不匹配（明确没还）；`pending` 不匹配（未发出）；
  `unknown` 不匹配（「可能已还」不是成功事实；当已还会给实际未还的利息制造假
  终态，维持开放暂估与现状一致，人工核实后由新的成功还款自然收口）。
- **领域事实如实陈述**（替代 P1 版被证伪的「结清」表述）：交易所行为是——还款
  时刻已计提利息被并入 `crossMarginBorrowed`（**资本化**），债务继续生息；只有
  债务整体归零（本金与未付利息均为 0）才意味着相关借款生命周期终结。因此终态
  锚定在「归零证据」而非「任一还款」，与 Human 口径 1/3/4 一致：部分还款后、
  归零前，全部历史利息（含被资本化的部分）继续按当前价动态折 U。
- **覆盖形态**：部分还款（无证据）→ 不锁；部分还款 + 后续归零还款 → 息行匹配
  **归零那次**（第一条带证据者），用归零那次的价格；反复借/全额还/再借 → 每轮
  利息行匹配各自轮次内第一条带证据的还款（re-borrow 后新行 `accrued` 晚于上一
  归零时刻，自然落到下一轮）；归零还款之后捕获失败（NULL 证据）→ 开放，恢复走
  §3.2 回补。无需数量配对、无需外键。

### 3.2 还款观测（价格 + 归零证据）与历史回补

#### 3.2.1 未来还款：成功响应后的两次独立异常隔离观测（Human 路径 A）

`_handle_margin_repay_post` 在 `_dispatch_margin_repay` 返回 `succeeded` 后、
`store.resolve` 调用前，执行**两个互相独立的 best-effort 观测**：

1. **价格观测**（零上游 I/O）：读内存快照 `service.get_snapshot()`，取
   `symbol = f"{asset}USDT"` 的 `opening_quotes.spot_bid_price`（仅 `status="fresh"`
   且非空）。整个读取与解析包在 `try/except Exception` 内：`SnapshotNotReady` 或
   任何异常 → `repay_price_usdt = NULL`。**如实命名**：该值是
   `repay_price_source = "snapshot_spot_bid_at_capture"`——捕获时刻内存快照里的
   现货买一价，可能滞后于真实还款时刻（滞后量由快照刷新节奏决定；`fresh` 仅表示
   四价齐全，`backend/domain/snapshot.py:806-808`，无时效含义）。它**不是**币安
   还款的真实成交汇率。
2. **归零证据观测**（一次只读 GET）：经快照服务持有的同一 `PrivateClient` 调
   `fetch_unified_balances(force=True)`（`GET /papi/v1/balance`，weight 20，`force`
   只驱逐该端点单一缓存键、触发一次新鲜签名 GET——既有机制）。从返回列表找
   `asset` 行：`crossMarginBorrowed` → `repay_after_borrowed`、`crossMarginInterest`
   → `repay_after_interest`（原样字符串）。**缺席语义**：列表非 `None` 但无该
   asset 行 → 两列记 `"0"`（该端点为全账户单响应、无分页；无余额且无负债的资产
   不构成债务——与 `_margin_repay_borrowed_assets` 白名单「列表内 `borrowed > 0`
   才算借款」是同一列表的互补读法，由测试固定）。返回 `None`（禁用/失败）或
   任何异常 → 两列 NULL，`repay_after_source = NULL`；成功记
   `"live_balance_after_repay"`。

**硬约束（F2）**：两个观测各自独立包裹异常，任一失败只置自己的列为 NULL，
互不影响；观测代码整体不抛出（捕获函数以「绝不抛」为契约）；
`margin_repay_store.resolve(...)` 的调用位置与参数不受任何观测结果影响——
**还款终态落库无条件执行**。不存在「取价失败 → 跳过/延迟 resolve → 记录永久
停在 pending」的路径。

**NULL 的恢复（不重发、不碰还款终态）**：价格或归零证据为 NULL 的 succeeded 行，
由 §3.2.2 幂等回补脚本按 NULL-only 谓词补齐（价格查历史 K 线；归零证据按回补
推定规则）。恢复过程绝不重发还款请求、绝不改写 `status`/`repaid_amount`/
`update_time`，只填 NULL 列。补齐前相关利息保持开放暂估或 fail-closed 遮蔽。

#### 3.2.2 历史回补（存量行，含 STORJ）：一次性只读脚本 `scripts/backfill-repay-prices.py`

幂等谓词：只处理 `status='succeeded'` 且目标列为 NULL 的行，支持 `--dry-run`。
两个职责：

1. **价格回补**：按结算时刻查币安**公共**现货 K 线（`GET /api/v3/klines`，无签名、
   只读）。确定性规则：包含结算时刻的 1m K 线 `close`（`kline_1m_close`）；该分钟
   无成交 → 不早于结算时刻的第一根存在 K 线的 `open`（`kline_1m_open_fallback`）；
   仍取不到 → 保持 NULL（fail-closed，绝不以当前价或计提价顶替）。
2. **归零证据回补**（推定规则，全部依据存储/只读证据，不臆造）：对证据为 NULL 的
   succeeded 行，同时满足以下三条才写 `repay_after_borrowed="0"` /
   `repay_after_interest="0"` / `repay_after_source="backfill_inferred"`：
   a. 它是同 `asset` **最后一条** succeeded 还款；
   b. 其结算时刻之后该资产**无新利息行**（若未归零，小时级计息必然继续出现——
      STORJ 还款后 8 天无一新行即为此证）；
   c. 脚本运行时 `fetch_unified_balances(force=True)`（或 `--assume-debt-zero`
      人工模式，供 Human 凭币安核对结果替代直连）确认该资产当前
      `crossMarginBorrowed` 与 `crossMarginInterest` 均为 0。
   任一条不满足（如多轮借还交错、当前仍有负债）→ 保持 NULL，相关利息保持开放。
   **不虚构平仓单关系**；STORJ（无对冲周期）恰好完整命中 a+b+c。

脚本网络访问优先复用既有公共客户端封装；HTTP 出口须符合直连守卫白名单
（`test_urlopen_only_in_designated_http_clients`——若 `scripts/` 在扫描范围外，
仍按指定客户端风格实现并在实现任务中确认）。**运行写生产库，须 Human 单独授权**。

### 3.3 统一折算权威（两消费者同一算法）

`backend/ledger_flow/domain.py` 纯函数（零 I/O，本方案唯一的匹配+折算实现）：

```python
def settlement_ms(record) -> Optional[int]
    # update_time 可解析 -> int；否则 updated_at_us // 1000；均缺 -> None（不进索引）。

def debt_cleared(record) -> bool
    # repay_after_borrowed 与 repay_after_interest 均可解析为 Decimal 且 == 0。

def build_repay_match_index(repay_records) -> dict
    # 仅收 status='succeeded' 且 debt_cleared 的记录，按 asset 分组，
    # 组内按 (settlement_ms, client_request_id) 升序。

def match_interest_repay(asset, accrued_at_ms, index) -> Optional[dict]
    # 组内第一条 settlement_ms >= accrued_at_ms 的记录；None = 开放桶。

def interest_usdt_value(interest_amount, asset, matched, price_map) -> Optional[Decimal]
    # matched 为 None -> price_map[f"{asset}USDT"] 当前价（缺 -> None）；
    # matched 非 None -> Decimal(matched["repay_price_usdt"])（NULL/不可解析 -> None）；
    # USDT 本位与真零沿用现有 to_usdt 规则。
```

- **PnL 曲线**：`build_pnl_series` 新增可选参数 `repay_records=None`（缺省空 =
  现行为，向后兼容）；利息分支逐行 `interest_usdt_value`。终态行缺还款价 → 该
  资产进 `unpriced_assets`（与开放行缺当前价同一出口、前端零改动），利息不计入、
  净收益遮蔽。
- **持仓视图**：`LedgerFlowService` 新增
  `sum_interest_usdt_by_asset(asset, start_ms, end_ms, price_map, repay_records)`
  ——窗口内逐行匹配折算、Decimal 求和，任一行 None → 整体 None；真零返回
  `"0"`。「借币利息」币本位列继续用现有 `sum_interest_by_asset` 不变。
- **`_hedge_open_positions`**：`borrow_interest_usdt` 改调上述新方法（替换现有
  行内乘法块）；`net_pnl` 公式、遮蔽条件不变。
- **close_log（`_finalize_close_task`）不触碰**（P2 已核实）：落库 `borrow_interest`
  为币本位合计，历史仓位页显示币本位原值，不折 U、不随价重画。`sum_interest_by_asset`
  因此保留。
- **`margin_repay_store` 未配置**（仅测试/未配置环境）→ 曲线与持仓传空
  `repay_records`，行为等同「无还款记录」（现状）。生产恒配置该 store。

### 3.4 Schema 变更、读形状、迁移与回滚

`margin_repay` 新增 **5 个 NULL-able TEXT 列**（仅此一处 schema 变更；
`interest_rows` 不动）：

```sql
ALTER TABLE margin_repay ADD COLUMN repay_price_usdt     TEXT;  -- 捕获/回补的折算价
ALTER TABLE margin_repay ADD COLUMN repay_price_source   TEXT;  -- snapshot_spot_bid_at_capture | kline_1m_close | kline_1m_open_fallback
ALTER TABLE margin_repay ADD COLUMN repay_after_borrowed TEXT;  -- 还款后 crossMarginBorrowed 原样字符串
ALTER TABLE margin_repay ADD COLUMN repay_after_interest TEXT;  -- 还款后 crossMarginInterest 原样字符串
ALTER TABLE margin_repay ADD COLUMN repay_after_source   TEXT;  -- live_balance_after_repay | backfill_inferred
```

- 迁移幂等：`MarginRepayStore.__init__` 在建表后按 `PRAGMA table_info(margin_repay)`
  逐列检查、缺则 `ALTER ADD`（新库直接建全列）；与既有
  `backend/hedge_open_tasks/store.py:498` 模式一致。旧行新列为 NULL（开放桶语义），
  旧代码按名取列不受多列影响。
- `resolve()` 增 5 个可选关键字参数；`_row_to_doc` 增价格两键（POST/GET 响应
  additive 扩列；`_RESULT_KEYS` 测试同步）。归零证据三列**不进** `_row_to_doc`——
  它们是内部匹配证据，不是还款结果契约。
- **`list_records()`（新方法，F3）返回形状**：`_row_to_doc(row)` 的全部键 **外加**
  `updated_at_us`（int）、`repay_price_usdt`、`repay_price_source`、
  `repay_after_borrowed`、`repay_after_interest`、`repay_after_source`——匹配索引
  所需的结算时刻回退字段与新证据列全部可达。按 `updated_at_us` 升序返回全量。
- 回滚：`git revert` 交付 commit 即回代码；残留列对旧代码无害，无需 DROP。
- 回补脚本只补 NULL 列，重复运行幂等。

## 4. 改动文件清单（bounded）

| 文件 | 改动 |
|---|---|
| `backend/margin_repay/store.py` | 5 列幂等迁移、`resolve` 参数、`_row_to_doc` 两键、`list_records()` |
| `backend/app/server.py` | 还款成功后两个独立异常隔离观测（价格 + 归零证据）；`_hedge_open_positions` 换 `sum_interest_usdt_by_asset`；`_handle_pnl_series` 传 `repay_records` |
| `backend/ledger_flow/domain.py` | §3.3 五个纯函数（`settlement_ms`/`debt_cleared`/索引/匹配/折算）；`build_pnl_series` 利息分支改造 |
| `backend/ledger_flow/service.py` | `sum_interest_usdt_by_asset` |
| `backend/tests/test_ledger_flow_domain.py` | §5 匹配/折算/曲线用例 |
| `backend/tests/test_ledger_flow_service.py` | 新 service 方法用例 |
| `backend/tests/test_margin_repay.py` | 双观测捕获/异常隔离/缺席语义/迁移幂等/响应键 |
| `scripts/backfill-repay-prices.py` | 新建：一次性回补脚本（价格 + 归零证据推定，`--dry-run`） |
| `docs/api/public-market-contract.md` | 新增 additive amendment：双口径折算、匹配规则、5 新列、两个来源语义、fail-closed |

前端 `frontend/index.html` / `frontend/self-check.js` **预期零改动**：wire 形状不变
（缺价仍走 `unpriced_assets` → 「成本不全」遮蔽 + 点名）。仅当复评要求脚注文案区分
缺价来源时才允许最小文案调整，届时同步 self-check 断言。

## 5. 测试计划（全部离线、可执行）

`python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q`
（实现任务另跑全量后端套件与前端 self-check，排除既有白名单误报。）

domain（`test_ledger_flow_domain.py`）：

1. 匹配基本形：`accrued` 早于带证据 succeeded 结算时刻 → 匹配；succeeded 早于
   `accrued` → 开放。
2. **部分还款不锁价**（F1/口径 3 核心断言）：`repay_after_borrowed` 非零（如
   `"50.10709571"`——SNX 资本化形态复刻）或 NULL 的 succeeded → 不匹配；该资产
   利息行值随 `price_map` 变动。
3. **全额归零切换恰一次**（验收核心时序）：开放行随当前价变动 → 引入带证据
   （`"0"`/`"0"`）的归零还款 → 值切换为该行存储价格（一次）→ 此后继续改变
   `price_map` 值不再变化。
4. **re-borrow 重新开放**：归零还款之后新计提的利息行（`accrued` 晚于归零时刻）
   → 开放、随当前价变动。
5. 部分还款 + 后续归零还款：利息行匹配**归零那次**、用其价格。
6. 反复借/全额还/再借多轮：各轮利息行各自匹配本轮归零还款。
7. `failed` / `unknown` / `pending` 不匹配；`amount="0"` 与 `repaid_amount=None`
   **本身不构成**匹配（无证据列时同不匹配——字段语义断言）。
8. `update_time` 缺失/不可解析 → 回退 `updated_at_us//1000`（经 `list_records()`
   形状传入的记录可携带该字段——F3 可达性）。
9. 同毫秒多条带证据还款：`(结算时刻, client_request_id)` 排序确定，取首条。
10. 归零还款 `repay_price_usdt` NULL → `interest_usdt_value` 返回 None（遮蔽，
    不暂估、不按 0、不用计提价）。
11. `build_pnl_series`：终态行用存储价入利息线；缺价资产进 `unpriced_assets` 且
    不计入；不传 `repay_records` 时输出与现行为逐位一致（回归锁定）。
12. STORJ 场景复刻：一条 STORJ 利息 + `amount="0"` succeeded + 回补
    （价格 + `backfill_inferred` 归零证据）→ 曲线利息线计入 `0.0130242 × 回补价`、
    `unpriced_assets` 为空；去掉回补价 → 遮蔽；去掉归零证据 → 回到当前价暂估。

service（`test_ledger_flow_service.py`）：

13. 周期窗口内终态 + 开放混合 → 各按各自价格折算求和；任一 None → 整体 None。
14. 真零利息（`"0"`）返回 `"0"`，无需任何价格。

margin_repay（`test_margin_repay.py`）：

15. `_RESULT_KEYS` 增价格两键；严格成功 + 桩快照有价 + 桩余额归零 → 5 列落库、
    价格两键出现在响应。
16. **异常隔离（F2 核心断言）**：桩快照 `get_snapshot` 抛 `SnapshotNotReady`（及
    另一用例抛任意 `RuntimeError`）、桩 `fetch_unified_balances` 抛异常/返回
    `None`——还款记录仍为 `succeeded`、对应观测列 NULL、`resolve` 恰好执行一次。
    两个观测独立失败互不传染（价格失败 + 余额成功 → 余额列仍落库，反之亦然）。
17. 缺席语义：余额列表非 `None` 但无该 asset → `repay_after_borrowed="0"`、
    `repay_after_interest="0"`、source=`live_balance_after_repay`。
18. `failed`/`unknown`/`pending` 分支不执行任何观测（零额外调用）。
19. 旧 schema 库（无新列）打开后自动补列；重复打开幂等；旧行新列 NULL。

回补脚本：`--dry-run` 只打印计划写入；kline 两分支与「无数据保持 NULL」；
归零推定 a/b/c 三条件各自不满足时保持 NULL（按桩 HTTP/余额响应断言）。

## 6. 生产验证（实现交付并部署后，均须 Human 授权；本计划不授权）

1. 部署前：`curl` 只读验证 `STORJUSDT` 公共 1m K 线覆盖 `2026-08-20 14:31 CST`，
   输出存阶段 evidence。
2. **进入方式（O2）**：服务器无 git 仓库、应用跑在 Docker（`PROJECT_STATE` 部署段）。
   回补执行 = `ssh funding-prod` → 定位数据卷中 `margin-repay.sqlite3` →
   **写前备份**（`sqlite3 <db> ".backup '<db>.bak-<timestamp>'"` 或文件级
   `cp`，备份路径留存于阶段 evidence）→ 脚本以 `docker cp` 进容器 +
   `docker exec ... python` 运行（镜像不含 `scripts/`；实现时若选择把 `scripts/`
   纳入镜像须另列改动）→ 先 `--dry-run` 核对再实跑。
3. 部署后只读检查：曲线 `unpriced_assets` 不再含 STORJ、净收益恢复数值；利息线
   该桶值 = `0.0130242 × 回补价`；`margin_repay` STORJ 行 5 列非空且
   `repay_after_source="backfill_inferred"`。
4. 下一笔真实还款发生后：复核新行价格两列与归零证据已捕获（或如实 NULL），
   部分还款不锁价、全额还款后该资产历史利息恰切换一次并稳定。

## 7. 非目标与具名限制（不做 / O1）

- **O1（数据源覆盖面）**：`margin_repay` 只记录经本应用 UI 发起的还款
  （`server.py` 唯一写路径）；在币安 App/网页手动还款或交易所自动还款不入表，
  其对应利息**永远**留在开放桶按当前价浮动——fail-closed 退化为现状行为，
  「已还款即固定」对这类还款不成立。交易所侧 `margin_capital_flow_rows` 含
  `REPAY` 流水，但该源单页无翻页、窗口 `[末-3h, now]`、历史深度有限，**本轮不
  改用**（P2 评估结论）；扩源须新证据另开任务。
- 不为 close-log/历史仓位页引入 U 折算（其币本位展示是既有决定）。
- 不修 bStock / 1000x 利息资产与快照价格键不齐的问题（维持现状 fail-closed）。
- 不给 `margin_repay` ↔ `interest_rows` 建外键或数量配对账本（终态锚定归零证据，
  无需数量配对）。
- 不引入还款价格/负债证据的快照存储表、不缓存历史 K 线。
- 不改前端展示结构；不为 `unknown` 还款增加 UI 提示（P2 §8.3 裁定：既有流程覆盖）。

## 8. 风险与评审焦点（供 P4）

1. **归零证据是单次观测**：捕获失败的归零还款不构成终态，恢复依赖脚本推定
   （§3.2.2 的 a/b/c）。推定规则对「还款后隔很久才补跑脚本」的情形依赖「无新
   息行」作归零侧证——若资产恰好在极低息率下长时间不计息（理论可能），推定
   仍可能把未归零误判为归零（假终态）。缓解：条件 c 的当前余额实时核验是硬门；
   残余窗口 = 「还款后负债清零前又恰好停息且当前读数归零」——实际语义上当前
   读数归零即当前无债务，假终态仅在「历史上从未归零、后来又归零」的交错时间线
   出现，此时用回补价终态化与 Human 口径偏差有限且可审计。P4 可裁定是否收紧。
2. **双价格源语义差异（F4 残留）**：捕获时刻快照买一（可能滞后）与历史 K 线
   close（结算分钟）两种近似落在同一列，由 `repay_price_source` 显式区分；价差
   量级相对利息金额可忽略。均为「结算时刻的可审计近似」，不是币安还款成交汇率。
3. **`fetch_unified_balances(force=True)` 的缺席语义**（§3.2.1-2）依赖「全账户
   单响应、无分页」的端点行为，由测试固定；若未来端点改分页，该语义须重审。
4. **缺价遮蔽是全局的（O3）**：`pnlCostsIncomplete()` 判 `unpriced_assets` 非空
   即整条净收益「暂无」——任何**一行**终态利息缺还款价、或任一开放资产缺当前价，
   都遮蔽全部净收益，不限于 STORJ。与 NULL 捕获失败合并评估：一次观测失败即
   触发全局遮蔽，直到回补完成。
5. 迁移为纯 additive 5 列，无数据搬移；评审关注点应在归零判定确定性与测试
   充分性。

## 9. P2 发现解决对照（供 P4 复评索引）

| P2 发现/观察 | 本版解决位置 |
|---|---|
| F1（结清表述与证据相反；无法区分全额/部分） | §1.3、§3.1（归零证据判定 + 资本化如实陈述）；测试 2/5/7 |
| F2（捕获插在写路径、无异常保护） | §3.2.1（双独立异常边界、resolve 无条件执行）；测试 16 |
| F3（回退字段读取不可达） | §3.4 `list_records()` 形状含 `updated_at_us`；测试 8 |
| F4（价格定义强于代码语义） | §3.2.1-1（捕获时刻快照买一 + 滞后来源 + 来源命名）；§8.2 |
| O1（交易所侧还款不入表） | §7 具名 |
| O2（回补可执行性） | §6.2（容器进入 + 写前备份 + dry-run 先行） |
| O3（遮蔽全局性） | §8.4 点明 |
