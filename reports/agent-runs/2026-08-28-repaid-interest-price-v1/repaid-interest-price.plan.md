# 已还款利息按还款时价格折算 — 最小开发方案（P5 定档版）

- stage: `2026-08-28-repaid-interest-price-v1`
- author: Planner `opus5`（anthropic）；P1/P3 作者 `claude_glm`（zhipu_glm）
- created: 2026-08-28 17:15 CST（P1）→ 18:17 CST（P3）→ **P5 定档 2026-08-28**
- base_sha: `4e6f4909dd17eb43c08f0f393258793df24a6ec7`
- 状态: 定档稿待 P6 只读计划复评（`gpt-5.6-sol`/OpenAI）；**本文档不授权任何实现、写库或部署**。

## 0. P5 修订记录：从「证明归零」退到「Human 约定终态」

P4 复评 `REWORK`（`evidence/P4-repaid-interest-price-plan-rereview.handoff.md`）命名两个
**连续两轮**出现的根因家族，并禁止再对单点打补丁。Human 随后固定了产品口径，
本次据此**删除整条「证明债务归零」的设计线**，而不是修补它。

**删除清单（全部移出产品实现范围）**：

| 被删对象 | 出处 | 删除依据 |
|---|---|---|
| `repay_after_borrowed` / `repay_after_interest` / `repay_after_source` 三列 | P3 §3.4 | 归零证据不再是终态依据 |
| 还款后签名余额 GET（`fetch_unified_balances(force=True)`） | P3 §3.2.1 观测 2 | P4 F5：把 15 秒超时的网络调用插进资金缝隙 |
| 「列表无该 asset 行 → 记 `"0"`」缺席语义 | P3 §3.2.1 | 根因 A：缺席当证明 |
| `debt_cleared()` 判定函数 | P3 §3.3 | 终态谓词改为存储意图，无需该函数 |
| 回补推定条件 a / b / c | P3 §3.2.2 | 根因 A；P4 F6/F7 |
| `coverage_for_window` 回补闸门 | P4 F6 要求新增 | 连同被闸门保护的推断一并删除，不再需要 |
| 跨库历史推断（利息库 × 还款库联合推定） | P3 §3.2.2 | 根因 A |
| `--assume-debt-zero` 人工模式 | P3 §3.2.2-c | 根因 A：人工断言当观测 |
| 通用历史/未来 K 线回补脚本 `scripts/backfill-repay-prices.py` | P3 §3.2.2 | 仅为存量异常而生；异常改走人工修正 |

**P2/P4 认可并保留的骨架**：单一折算权威（§3.3）、两消费者收口、additive 幂等迁移、
异常隔离的内存取价、fail-closed 缺价语义、测试编排。

## 1. 产品口径（Human 已固定，不可改写）

1. **未出现本地终态事件前 = 开放暂估**：该资产全部历史利息行按公开行情快照**当前**
   现货买一价（`opening_quotes.spot_bid_price`，`status="fresh"`）动态折 USDT，随价变动。
2. **唯一终态事件**：一次**本地资产卡还款**，其**存储意图** `amount == "0"`（还全部）
   **且**终态 `status == "succeeded"`。该事件发生时，该资产在此结算时刻**之前**计提的
   利息行一次性切换为按该次还款捕获的存储价格折算，此后不再随当前价变动。
3. **`0 + succeeded` 是 Human 明定的产品约定，不是「交易所债务已归零」的证明。**
   存储响应不含剩余负债字段（`hedge_open_live_client.py:538` 只中继
   `success/asset/amount/updateTime`），本方案**不主张**它证明了任何交易所侧事实，
   也**不得**为加强它而增加任何实时余额查询或债务推断。
4. **非零部分还款绝不锁价**；`pending` / `unknown` / `failed` 一律不锁价。
5. 终态之后再次借款（re-borrow）开启新的开放区间：新计提的利息行回到当前价暂估，
   直到下一次 `0 + succeeded`。
6. **禁止**把「利息计提时冻价」当默认或回退（Human 2026-08-28 否决）。
7. **fail-closed**：无可靠适用价格（开放行缺当前价、或终态行缺存储还款价）→ 该资产
   利息不计入、登记缺价、净收益「暂无」。绝不按 0、绝不残缺相加、绝不用另一口径的
   价格顶替。
8. **存量异常（STORJ 等）不由正常程序处理**，见 §7。

## 2. 缺陷现状（已核验证据，P5 复核保留）

- 生产 `interest_rows` 仅一条 STORJ `ON_BORROW`：本金 `200`、利息 `0.0130242`、
  `accrued_at_ms` 对应 `2026-08-20 14:00:00 CST`。
- 生产 `margin_repay` 有一条 STORJ `amount="0"`、`status=succeeded`、`update_time`
  对应 `2026-08-20 14:31:03.837 CST` 的记录。
- 现状代码（`server.py` `_handle_pnl_series` / `_hedge_open_positions`、
  `ledger_flow/domain.py:571` `to_usdt`）把**所有**币本位利息一律按当前快照价折算；
  STORJ 合约 `SETTLING` 后被快照排除 → 缺价 → 曲线与持仓统计「暂无/成本不全」。
- `margin_repay` 现有列（`store.py:35-47`）无任何价格列：
  `client_request_id / asset / amount / repay_asset / status / repaid_amount /
  update_time / error_code / error_message / created_at_us / updated_at_us`。
  `amount` 为 `TEXT NOT NULL`，存的是**请求意图**——这正是 §1.2 终态谓词的依据。
- **还款写路径现状缝隙宽度为零**（`server.py:1028-1029`）：
  ```python
  resolution = self._dispatch_margin_repay(...)      # 1028 钱在此出去
  record = self.margin_repay_store.resolve(...)      # 1029 终态在此落库
  ```
  两行之间**当前没有任何动作**（`_now_us()` 在 `resolve` 参数内求值）。任何新增都是
  从零开始加——这是 §4 根因 B 扫描的基线事实。

## 3. 设计

### 3.1 终态谓词与匹配规则

**终态谓词（唯一，确定性，零推断）**：

```
is_terminal(record) := record["amount"] == "0" AND record["status"] == "succeeded"
```

- 两个输入都是**本地已存储的确定值**：`amount` 是建单时写入的请求意图，
  `status` 是既有严格终态。**不读响应体推断、不查余额、不看利息行有无。**
- 字符串精确比较 `== "0"`，不做数值归一（`"0.0"` / `"0.00"` 不是 repay-all 意图，
  它们是数量为零的异常输入，按非零部分还款处理即不锁价）。由测试固定该边界。
- **本谓词是 Human 产品约定**。计划、代码注释、文档三处均须如实表述为
  「Human 约定的终态」，**不得**写成「债务已归零」「已结清」或任何交易所侧事实主张。

**匹配规则**：对每条 `interest_rows` 行 `(asset, accrued_at_ms)`：

> 匹配对象 = 同 `asset` 的 `margin_repay` 记录中，**结算时刻 ≥ `accrued_at_ms` 的
> 第一条 `is_terminal` 记录**；不存在则落入**开放桶**（当前价暂估）。

- **结算时刻**（单一权威定义）：`update_time`（币安回传毫秒字符串）可解析时用它；
  否则回退 `updated_at_us // 1000`（本地落终态时刻，列 `NOT NULL` 恒有值）。
  **这不是推断**：两者都是已存储的本地事实，回退只是字段可用性选择，不对交易所侧
  状态做任何主张。
- 分组内排序键 `(结算时刻 ms, client_request_id)`，同毫秒多条时结果确定。
- **覆盖形态**：非零部分还款 → 不锁；部分还款 + 后续 `0+succeeded` → 息行匹配后者；
  反复借/全额还/再借 → 每轮利息行匹配各自轮次内第一条终态（re-borrow 后新行
  `accrued` 晚于上一终态时刻，自然落入下一轮）；终态行取价失败（NULL）→ 见 §1.7
  fail-closed。无需数量配对、无需外键。

### 3.2 还款时取价（缝隙内唯一动作）

`_handle_margin_repay_post` 在 `_dispatch_margin_repay` 返回后、`store.resolve` 调用前，
执行**唯一一个** best-effort 动作：

**内存快照取价**（零上游 I/O、零网络、零重试、零 sleep）：读 `service.get_snapshot()`
（进程内已发布状态的纯读），取 `symbol = f"{asset}USDT"` 的
`opening_quotes.spot_bid_price`（仅 `status == "fresh"` 且非空）。

**硬约束**：

1. 整个读取与解析包在**一个** `try/except Exception` 内；`SnapshotNotReady` 或任何
   异常 → `repay_price_usdt = NULL`，`repay_price_source = NULL`。
2. 捕获函数以「绝不抛出」为契约。
3. `store.resolve(...)` 的调用位置与参数**不受取价结果影响**，且在异常边界**之外**
   恰好执行一次——还款终态落库无条件、无延迟。
4. **仅当** `is_terminal` 成立（`amount=="0"` 且 `status=="succeeded"`）才取价并写列；
   非零部分还款与非 succeeded 终态一律不取价、两列保持 NULL。这使缝隙内动作的触发
   面进一步收窄。
5. **如实命名**：`repay_price_source = "snapshot_spot_bid_at_capture"`——捕获时刻内存
   快照里的现货买一价，可能滞后于真实还款时刻（`fresh` 仅表示四价齐全，
   `backend/domain/snapshot.py:806-812`，无时效含义）。它**不是**币安还款成交汇率。

**NULL 的处置**：终态行价格为 NULL → 该资产利息按 §1.7 fail-closed 遮蔽。
**不设自动回补**：无 K 线脚本、无重试、无二次观测。存量异常走 §7 人工路径。

### 3.3 统一折算权威（两消费者同一算法）

`backend/ledger_flow/domain.py` 纯函数（零 I/O，本方案唯一的匹配+折算实现）：

```python
def settlement_ms(record) -> Optional[int]
    # update_time 可解析 -> int；否则 updated_at_us // 1000；均缺 -> None（不进索引）。

def is_terminal_repay(record) -> bool
    # record["amount"] == "0" and record["status"] == "succeeded"（字符串精确比较）。

def build_repay_match_index(repay_records) -> dict
    # 仅收 is_terminal_repay 的记录，按 asset 分组，组内按 (settlement_ms, client_request_id) 升序。

def match_interest_repay(asset, accrued_at_ms, index) -> Optional[dict]
    # 组内第一条 settlement_ms >= accrued_at_ms 的记录；None = 开放桶。

def interest_usdt_value(interest_amount, asset, matched, price_map) -> Optional[Decimal]
    # matched 为 None -> price_map[f"{asset}USDT"] 当前价（缺 -> None）；
    # matched 非 None -> Decimal(matched["repay_price_usdt"])（NULL/不可解析 -> None）；
    # USDT 本位与真零沿用现有 to_usdt 规则。
```

- **PnL 曲线**：`build_pnl_series` 新增可选参数 `repay_records=None`（缺省空 = 现行为，
  向后兼容）；利息分支（`domain.py:571`）逐行改用 `interest_usdt_value`。终态行缺还款价
  → 该资产进 `unpriced_assets`（与开放行缺当前价同一出口、前端零改动）。
- **持仓视图**：`LedgerFlowService` 新增
  `sum_interest_usdt_by_asset(asset, start_ms, end_ms, price_map, repay_records)`
  ——窗口内逐行匹配折算、Decimal 求和，任一行 None → 整体 None；真零返回 `"0"`。
  币本位列继续用现有 `sum_interest_by_asset` 不变。
- **`_hedge_open_positions`**：`borrow_interest_usdt` 改调上述新方法；`net_pnl` 公式与
  遮蔽条件不变。
- **`close_log`（`_finalize_close_task`）不触碰**（P2 已核实）：落库 `borrow_interest`
  为币本位合计，历史仓位页显示币本位原值，不折 U、不随价重画。
- **`margin_repay_store` 未配置**（仅测试/未配置环境）→ 两消费者传空 `repay_records`，
  行为等同「无还款记录」（现状）。

### 3.4 Schema 变更、读形状、迁移与回滚

`margin_repay` 新增 **2 个 NULL-able TEXT 列**（仅此一处 schema 变更；`interest_rows` 不动）：

```sql
ALTER TABLE margin_repay ADD COLUMN repay_price_usdt   TEXT;  -- 捕获的折算价
ALTER TABLE margin_repay ADD COLUMN repay_price_source TEXT;  -- 恒为 snapshot_spot_bid_at_capture 或 NULL
```

- 迁移幂等：`MarginRepayStore.__init__` 建表后按 `PRAGMA table_info(margin_repay)` 逐列
  检查、缺则 `ALTER ADD`（新库直接建全列），与 `backend/hedge_open_tasks/store.py:498`
  模式一致。旧行新列为 NULL（开放桶语义），旧代码按名取列不受影响。
- `resolve()` 增 2 个可选关键字参数；`_row_to_doc` 增这 2 键（POST/GET 响应 additive
  扩列；`_RESULT_KEYS` 测试同步）。
- **`list_records()`（新方法，承接 P2 F3）返回形状**：`_row_to_doc(row)` 的全部键
  **外加** `updated_at_us`（int）、`repay_price_usdt`、`repay_price_source`。按
  `updated_at_us` 升序返回全量。（P4 已核实 `store.py:51-63` 的 `_row_to_doc` 现无
  `updated_at_us`，故该补充必要且充分。）
- 回滚：`git revert` 交付 commit 即回代码；残留两列对旧代码无害，无需 DROP。

## 4. 同根因穷举扫描（P4 §四 要求，本节为定档核心）

按 AGENTS.md §8 同根因刹车：以下对两个根因家族各做一次**穷举**枚举，含已修复与已删除
站点；清单外的已审站点给出不适用理由。

### 4.1 根因 A：把「没有观测到」或「可以推断」当作「已被证明」

**判据**：任何以「缺席」「未出现」「可推定」「应该是」为依据、却输出一个被下游当作
事实消费的判定点。

| # | 判定点 | 出处 | P5 处置 | 依据 |
|---|---|---|---|---|
| A1 | 「任一成功还款结清已计提利息」 | P1 §1 | **已删除**（P3 修） | P2 F1：所引证据证明的是资本化 |
| A2 | `debt_cleared()`：`repay_after_*` 双零 → 归零事实 | P3 §3.1/§3.3 | **本次删除** | 该观测本身被 F5 删除，判定点随之消失 |
| A3 | 缺席语义：余额列表无该 asset 行 → 记 `"0"` | P3 §3.2.1 | **本次删除** | 典型缺席当证明 |
| A4 | 回补条件 a：「同资产最后一条 succeeded」 | P3 §3.2.2 | **本次删除** | 「后面没有了」是缺席 |
| A5 | 回补条件 b：「其后无新利息行 → 未继续计息」 | P3 §3.2.2 | **本次删除** | P4 F6：账本断档会造假终态；连同其 `coverage_for_window` 闸门一并删除 |
| A6 | 回补条件 c：「当前余额为零 → 当时已归零」 | P3 §3.2.2 | **本次删除** | 当前态推过去态 |
| A7 | `--assume-debt-zero` 人工断言 | P3 §3.2.2 | **本次删除** | 人工断言被写成观测来源 |
| A8 | K 线 fallback：「该分钟无成交 → 用下一根 open」 | P3 §3.2.2-1 | **本次删除**（随脚本） | 用邻近值顶替未观测值 |
| A9 | **`0 + succeeded` = 终态** | 本版 §3.1 | **保留，重新表述** | **这是家族内唯一保留项**：它不主张任何未观测事实，而是 Human 明定的**产品约定**。§1.3 / §3.1 / 代码注释 / API 文档四处均须写明「Human 约定，非交易所证明」。禁止后续为「加强」它而添加余额查询或推断（见 §8 非目标） |
| A10 | `unknown` 不匹配 | P3 §3.1 → 本版 §1.4 | **保留** | 家族的**正确形态**：不把「可能已还」当已还 |
| A11 | `pending` / `failed` 不匹配 | 同上 | **保留** | 同 A10 |
| A12 | `settlement_ms` 回退 `updated_at_us` | P3 §3.1 → 本版 §3.1 | **保留，补说明** | **不属于本家族**：两个候选都是已存储的本地事实，回退是字段可用性选择，不对交易所侧状态作主张。§3.1 已明文 |
| A13 | 缺价 → fail-closed 遮蔽 | 本版 §1.7 | **保留** | 家族的正确形态：不知道就说不知道 |

**清单外已审站点的不适用理由**：`build_repay_match_index` / `match_interest_repay` /
`interest_usdt_value`（§3.3）均为纯查表与算术，无任何基于缺席的判定；additive 迁移与
`list_records()` 只搬运已存储值；`close_log` 不触碰。

### 4.2 根因 B：在「钱已出去、终态未落库」这条缝隙上追加观测动作

**缝隙定义**：`server.py:1028` `_dispatch_margin_repay` 返回 → `:1029`
`margin_repay_store.resolve` 返回之间。**基线事实：现状该缝隙内动作数为 0。**

| # | 动作 | 出处 | P5 处置 | 依据 |
|---|---|---|---|---|
| B1 | 无异常隔离的内存取价（可跳过 `resolve`） | P1 §3.2 | **已删除**（P3 修） | P2 F2 |
| B2 | 签名网络 GET `fetch_unified_balances(force=True)` | P3 §3.2.1 观测 2 | **本次删除** | P4 F5：最长 15 秒超时插进资金缝隙 |
| B3 | **异常隔离的内存快照取价** | P3 §3.2.1 观测 1 → 本版 §3.2 | **保留，为缝隙内唯一动作** | 纯进程内读；`try/except Exception` 全包；且仅在 `is_terminal` 时触发 |
| B4 | 取价失败后的重试 / sleep / 退避 | — | **明令不做** | 任何等待都是延迟资金终态落库 |
| B5 | 缝隙内第二次业务观测（任何形式） | — | **明令不做** | B2 的一般化禁令 |
| B6 | 缝隙内跨库读（利息库 / 对冲库） | P3 §3.2.2 的跨库推断若前移 | **明令不做** | 同 B5 |
| B7 | 缝隙内写第二张表 / 发指标 / 落日志文件 | — | **明令不做** | 任何 I/O 都可能抛异常或阻塞 |
| B8 | `resolve` 调用次数与位置 | 本版 §3.2 硬约束 3 | **锁定**：异常边界之外恰好一次 | 防「取价失败 → 跳过/延迟 resolve」 |

**穷举完整性声明**：本节枚举了 P1/P3 计划曾在该缝隙内提出的**全部** 2 个动作（B1、B2）
与本版保留的 1 个（B3），并对 5 类可能的后续追加（B4-B8）预先设禁。缝隙内动作数：
现状 0 → 本版 **1**（纯内存读，条件触发）。

**清单外不适用理由**：`begin()`（`:1017`）在派发**之前**，幂等回放分支（`:1025`）在派发
之前直接返回，二者不在缝隙内；`_send_borrow`（`:1032`）在 `resolve` **之后**，其失败
不影响已落库终态。

## 5. 改动文件清单（bounded）

| 文件 | 改动 |
|---|---|
| `backend/margin_repay/store.py` | 2 列幂等迁移、`resolve` 增 2 参数、`_row_to_doc` 增 2 键、新增 `list_records()` |
| `backend/app/server.py` | 还款成功且 `amount=="0"` 时的单次异常隔离内存取价；`_hedge_open_positions` 换 `sum_interest_usdt_by_asset`；`_handle_pnl_series` 传 `repay_records` |
| `backend/ledger_flow/domain.py` | §3.3 五个纯函数；`build_pnl_series` 利息分支改造 |
| `backend/ledger_flow/service.py` | `sum_interest_usdt_by_asset` |
| `backend/tests/test_ledger_flow_domain.py` | §6 匹配/折算/曲线用例 |
| `backend/tests/test_ledger_flow_service.py` | 新 service 方法用例 |
| `backend/tests/test_margin_repay.py` | 取价捕获/异常隔离/条件触发/迁移幂等/响应键 |
| `docs/api/public-market-contract.md` | additive amendment：双口径折算、终态约定（含「非交易所证明」的明确表述）、2 新列、来源语义、fail-closed |

**不新建任何脚本文件。** 前端 `frontend/index.html` / `frontend/self-check.js`
**预期零改动**：wire 形状不变（缺价仍走 `unpriced_assets` → 「成本不全」遮蔽 + 点名）。

## 6. 测试计划（最小充分的资金/PnL 守卫，全部离线）

`python -m pytest backend/tests/test_ledger_flow_domain.py backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q`
（实现任务另跑全量后端套件与前端 self-check，排除既有 `public_ip_service.py` 白名单误报。）

| # | 用例 | 断言 |
|---|---|---|
| T1 | 非零部分还款（`amount="12.5"`, succeeded） | 利息保持**动态**：改 `price_map` 结果随之变 |
| T2 | `0 + succeeded` | 该终态**之前**的利息行切换为存储价，改 `price_map` 结果**不变** |
| T3 | 终态后 re-borrow 新利息行 | 回到动态；下一个 `0+succeeded` 再次锁定 |
| T4 | 取价时快照抛异常 | 记录仍 `succeeded`、`repay_price_usdt IS NULL`、`resolve` 恰调用一次 |
| T5 | 终态行价格 NULL | 该资产进 `unpriced_assets`，利息不计入、净收益遮蔽（fail-closed） |
| T6 | 终态排序与同毫秒 tie-break | 同 `settlement_ms` 多条按 `client_request_id` 确定；`update_time` 缺失时回退 `updated_at_us//1000` |
| T7 | 两消费者一致 | 同一 `(interest_rows, repay_records, price_map)` 下曲线与持仓的利息折算值逐位相等 |
| T8 | additive 迁移幂等 | 旧库 `__init__` 两次 → 列各一份、旧行新列 NULL、旧读路径不受影响 |
| T9 | 终态谓词边界 | `"0.0"` / `"0.00"` / `""` / `None` 均**不**构成终态；仅精确 `"0"` 且 succeeded 构成 |
| T10 | 非终态不取价 | 非零部分还款与 `failed`/`unknown` 记录：两列恒 NULL，取价函数**未被调用** |

**不存在**任何仅为已删除推断机制服务的测试脚手架（P3 测试 8/16 中依赖
`repay_after_*` 与回补推定的部分一并不写）。

## 7. 存量异常（STORJ 等）— 正常程序之外的人工路径

**正常程序不含**针对存量异常的任何通用推定、K 线回补、跨库覆盖启发或兜底引擎。
STORJ 那条历史利息行在本方案下的正常表现是：其后的 `0 + succeeded` 记录**没有**
`repay_price_usdt`（该列在还款发生时尚不存在）→ 终态行缺价 → 按 §1.7 fail-closed 遮蔽。

存量异常改由**单独授权、备份、可审计的人工数据库修正**归档。以下仅为**后续**操作
清单，**本计划与后续的部署/评审均不授权该写入**：

1. Human 单独授权（与实现交付、部署授权分开）。
2. 写前备份目标数据库，记录备份路径与 `PRAGMA quick_check` 结果。
3. 独立选定历史价格（人工在交易所或行情源查证），记录来源与取值时刻。
4. 直接 `UPDATE` 该行的 `repay_price_usdt`，并写入**区别于正常来源**的
   `repay_price_source`（例如 `manual_correction`），使其在数据上永远可与
   `snapshot_spot_bid_at_capture` 区分。
5. 回读校验：重新查询该行确认写入值，并确认曲线/持仓两处折算结果符合预期。
6. 审计留证：操作时间、执行人、SQL 原文、前后值、备份路径一并归档。

## 8. 非目标与具名限制

- **不做**任何实时余额查询、债务归零推断、a/b/c 推定、`--assume-debt-zero`。
- **不做**通用历史或未来 K 线回补脚本、跨库历史推断、`coverage_for_window` 闸门。
- **不做**「利息计提时冻价」作为默认或回退（Human 已否决）。
- **不做**缝隙内的重试、sleep、第二次观测、跨库读、附加写（§4.2 B4-B8）。
- **不覆盖**交易所侧手动/自动还款（本地无记录 → 无终态事件 → 利息保持开放暂估）。
  这是已知口径边界，不是缺陷。
- **不触碰** `close_log` 币本位落库、`sum_interest_by_asset`、前端 wire 形状。
- 缺价遮蔽是**全局**的（该资产整体不计入），非逐行部分计入。

## 9. P2 / P4 发现解决对照（供 P6 索引）

| 发现 | P5 处置 |
|---|---|
| P2 F1 结清表述与证据相反 | 整条「证明归零」设计线删除；终态改为 Human 约定并四处如实表述（§1.3/§3.1/A9） |
| P2 F2 捕获插在写路径无异常保护 | §3.2 硬约束 1-3；缝隙内动作降至 1 个（§4.2 B3） |
| P2 F3 回退结算时刻字段不可达 | §3.4 `list_records()` 外加 `updated_at_us` |
| P2 F4 价格定义强于代码可证语义 | §3.2-5 `snapshot_spot_bid_at_capture`，明示 `fresh` 无时效含义 |
| P4 F5 签名 GET 插进资金缝隙 | **删除该观测**（§0、§4.2 B2），非缩短超时 |
| P4 F6 账本无行当无计息、缺覆盖闸门 | **删除整个回补推定**（§0、§4.1 A5），闸门随之无需存在 |
| P4 F7 推定被表述为可确认、判定点不分推定与观测 | **删除 `debt_cleared()`**（§4.1 A2）；新谓词仅读本地存储意图，无推定成分 |
| P4 §四 同根因刹车 | §4 两个家族各一次穷举扫描，含已删站点与清单外不适用理由 |
