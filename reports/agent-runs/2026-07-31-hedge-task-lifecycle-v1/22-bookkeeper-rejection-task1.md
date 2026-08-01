# 22-bookkeeper-rejection-task1 —— Task 1 核验拒收记录

- task_id: `hedge-merged-positions-v1`
- 核验人：opus5（bookkeeper），2026-08-01
- 结论：**核验未通过**。`current_task.state` 保持 `reported`，**不写 `verified`**（`agents/roles.md` 拒收落盘）
- 两条 in-range 缺陷，均涉及资金可见性，均未在 `21-merged-positions-implementation.md` 中披露
- 后续修复任务按 `AGENTS.md` §8 递增 `rework_count`（0 → 1）

## 0. 通过的部分（不返工，修复时不得回退）

| 项 | 复验方式 | 结果 |
|---|---|---|
| 后端测试 | 自行运行 `python3 -m pytest backend/tests -q` | `1126 passed`，与回执一致 |
| 前端自检 | 自行运行 `node frontend/self-check.js` | `EXIT=0`，128 PASS，未放宽断言 |
| 文件边界 | `git status --short` | 仅授权文件；`service.py` 未动 |
| 禁改区 | `git diff HEAD --stat -- private_client.py hedge_preflight_provider.py scheduler.py service.py` | 空 |
| 51169 与暂停原因集 | `git diff HEAD -- domain.py \| grep COLLATERAL_CAP\|PAUSE_REASON` | 无匹配，未动 |
| D15 两条查询 | `git diff HEAD -- store.py` | 两处 `WHERE t.status != ?` 均已去除，两处 `includes_deleted` 置位 |
| N-1 | `git diff HEAD -- test_hedge_store.py` | 测试改写而非删除，注释说明新旧断言差异 |
| N2 不 503 | `server.py` handler | `try/except SnapshotNotReady` 后恒 `200` |
| `merge_positions` 纯度 | 函数体内无 import / I/O / 服务引用 | 成立 |
| `_POSITION_KEYS` 精确集断言 | `test_hedge_api.py:618` `assert set(...) == _POSITION_KEYS` | 契约收紧，成立 |

## 1. 缺陷 B-1：`single_leg_exposure` 未消费后端裁定，改用更弱的自造谓词

### 规格要求（原文）

`12-development-breakdown.md` Task 1「范围」：

> 单腿敞口**只读后端** `pair_outcome`/`leg_exposure`，前端不重推。

`10-design.md` §6 证据表同列：「合并表消费后端 `pair_outcome`/`leg_exposure` | 避免双源口径漂移 | fake-ui §9 #6」。

### 实际实现

`backend/hedge_open_tasks/domain.py:1463-1467`：

```python
spot_qty = _merge_num(row.get("spot_qty")) or Decimal(0)
perp_qty = _merge_num(row.get("perp_qty")) or Decimal(0)
row["single_leg_exposure"] = bucket is not None and spot_qty > 0 and perp_qty == 0
```

即以**聚合后成交数量**自造判据，未消费后端既有的 `pair_outcome` / `leg_exposure` 裁定。代码注释写「not re-derived on the frontend」—— 这回答的是「在哪层算」，而规格要求的是「以谁为准」。

### 两者不等价，且新判据更弱

后端裁定按**受理**（`orderId` 是否返回）逐 attempt 记录（`domain.py:998-1012` `classify_attempt`，注释明写 fill 只是观测、不参与判定）；新判据按**成交量**、且是 `(coin, direction)` **聚合后**的总量。

**具体失败场景**（可复现）：同一 `BTCUSDT` forward 任务

| | 现货腿 | 合约腿 | 后端裁定 |
|---|---|---|---|
| attempt 1 | 成交 1.0 | 未受理 | `single_leg_exposure`，记 `leg_exposure` |
| attempt 2 | 成交 1.0 | 成交 1.0 | `success` |

桶聚合后 `spot_qty = 2.0`、`perp_qty = 1.0` → 新判据 `2.0 > 0 and 1.0 == 0` = **False**。

**实际有 1.0 BTC 现货未被对冲，合并表不打任何单腿标记。** 该判据只能识别「合约腿完全为零」，识别不了任何部分失衡 —— 而部分失衡恰恰是多次开单场景下的常态。

### 为什么不能算「实现细节自由」

`aggregate_positions` 的两条查询确实未 `SELECT` `pair_outcome` / `leg_exposure`（可验证：该函数体内两者出现次数均为 0），所以后端裁定当前够不到。但：

1. `store.py` **在本任务的授权文件内**，把裁定带进桶是合规改动；
2. 本 dispatch 的 Stop 段明确写着：「若发现方案与实际代码矛盾、或某条验收标准无法在不越界的前提下满足：**停止并报告**，不要自行取舍」；
3. 实现报告全文搜索 `single_leg` / `exposure` / `敞口` / `pair_outcome` / `leg_exposure` **零命中**，即该替换未被披露。

## 2. 缺陷 B-2：`spot_balance` 与 `drift` 取错账户，P2 的偏离检测结构性失效

### 实际实现

`domain.py:1516-1521` 从 `private_account.balances_spot` 建 `spot_by_asset`；`:1457` 与 `:1472-1478` 据此产出 `spot_balance` 列与 `drift` 标记。

### 事实：对冲的现货腿不在那个账户里

| # | 事实 | 证据 |
|---|---|---|
| 1 | 现货腿是 **margin 单**，写入统一账户 | `hedge_open_live_client.py:9` `POST /papi/v1/margin/order` — margin leg write |
| 2 | 冻结文案自述现货腿买入的是保证金账户 | `domain.py:1322`「现货腿当前无法买入保证金账户」 |
| 3 | `balances_spot` 来自经典现货账户 | `private_client.py` E6 `GET /api/v3/account` |
| 4 | 两个资金池**互斥** | `snapshot.py:1200` `total = spot_value + unified_net`（相加即不重叠，否则双计） |

结论：对冲买入的币落在 `balances_unified`（`/papi/v1/balance` 的 `totalWalletBalance`，其 docstring 明写已含 crossMargin 子账户），**不在** `balances_spot`。

### 后果

- **`spot_balance` 列取错资金池**：显示的是经典现货钱包余额，而非对冲实际持有的保证金账户余额。该列是资金列。
- **`drift` 结构性失效**：`real_spot = spot_by_asset.get(base_asset)`，币不在现货钱包时返回 `None`，`drift` 恒为 `False`（`:1474` 有 `real_spot is not None` 守卫）。而 P2 的**全部目的**就是发现「手工减仓导致真实持有 < 本地记录」。该标记因此在它本该保护的账户形态下**永不触发**，是一个静默失效的安全信号 —— 比报错更危险，因为界面看起来一切正常。

（注：`cross_margin_borrowed` 取自 `balances_unified`，来源正确，不在本缺陷内。）

## 3. 修复要求

修复任务须同时满足：

1. **B-1**：`single_leg_exposure` 改为消费后端既有裁定（`pair_outcome` / `leg_exposure`）。若需让 `aggregate_positions` 带出该裁定，`store.py` 在授权范围内。修复后须覆盖上表的「部分失衡」场景测试。
2. **B-2**：`spot_balance` 与 `drift` 改用正确资金池。若判定需要同时呈现两个账户，须显式说明各自含义，不得把一个当另一个。修复后须有测试锁定「对冲买入的币出现在统一账户时被正确匹配」。
3. **同族穷举**（`AGENTS.md` §8 同根因刹车的预防性应用）：`_merge_build_row` 内**每一个派生字段**逐个列出其数据来源，并说明该来源为何正确。清单须覆盖 `um_*` 全部、`unrealized_profit`、`price_pnl` 覆盖、`spot_balance`、`cross_margin_borrowed`、`single_leg_exposure`、`drift`、`includes_deleted_task`。**目的是一次扫完，避免第三轮再冒出同类来源错误。**
4. §0 表中已通过的项**不得回退**：后端 1126 与前端 128 仍须全绿，禁改区仍不得触碰，`_POSITION_KEYS` 精确集断言须同步更新且保持精确集形式。
5. 修复须在实现报告中**逐条披露**做法与取舍；若再遇规格与代码矛盾，按 dispatch Stop 段停止并报告，不得自行替换定义。

## 4. 计数

~~`rework_count` 由 `0` 递增为 `1`~~ —— **见 §5：拒收已由 Human 撤销，修复轮未发生，`rework_count` 回落为 `0`。**

---

## 5. Human 裁定（2026-08-01）：两条均不修，转为已接受的已知限制

Bookkeeper 两次说明 B-1 与 B-2 的影响后，Human 明确决定：**两条本轮都不修**，待后续结合真实使用场景另行设计。按 `AGENTS.md` §10，这是已定决策，不再劝阻。

`fix-merged-positions-sources-v1.dispatch.md` **作废**（从未交付）。`current_task.state` 由 `reported` 推进为 `verified`，`rework_count` 回落为 `0`（未发生任何修复轮 —— §8 计数绑定实际发生的再交付，而非被撤销的拒收）。

### 5.1 已接受风险记录（`AGENTS.md` §8 要求的五要素）

#### 限制 A —— 单腿敞口标记会漏报部分失衡

- **问题事实**：`domain.py` 的 `single_leg_exposure` 判据为「现货成交量 > 0 且合约成交量 == 0」，只能识别合约腿完全缺失；聚合后的部分失衡（如现货 2.0 / 合约 1.0）判为 `False`。规格原文要求消费后端 `pair_outcome` / `leg_exposure` 裁定，未执行。
- **可能影响**：合并持仓表在**确实存在裸露敞口时显示「无敞口」**。属"错误的安心"而非报错。多次开单场景下部分失衡是常态，故触发概率不低。**不造成资金损失，但会延迟发现已发生的敞口。**
- **接受理由**：Human 判断敞口的展示形态需先观察真实使用场景再设计，此刻定死判据可能定错；且该缺陷不影响下单、不影响账务数字本身，只影响一个提示标记。
- **临时限制 / 观察方式**：**不得把该标记当作敞口的权威判断**。当前可用的替代观察点（Bookkeeper 已核实）——(1) 任务卡上的单腿提示行（`task.leg_exposure`，仅保留最近一次）；(2) 展开任务卡内嵌日志，逐组看 `pair_outcome`，标黄「单腿成交」的即是，**这是唯一完整的历史**；(3) 合并表上现货余额与合约持仓的差额可人工比对。另注：状态枚举中的 `exposure_alert`（敞口告警）**无任何写入者，是死代码**，筛选它恒为空。
- **后续复看条件**：Human 结合真实场景给出敞口展示设计时；或 Task 2 的自动删除上线后（届时任务卡进入「已删除」筛选，上述 (1)(2) 两个观察点从默认视图消失，合并表成为唯一入口，该限制的权重显著上升）——**以先到者为准**。

#### 限制 B —— 现货余额列与偏离标记取自错误资金池

- **问题事实**：`spot_balance` 与 `drift` 读 `private_account.balances_spot`（经典现货账户 `GET /api/v3/account`），而对冲现货腿是 margin 单、买入统一账户（`hedge_open_live_client.py:9`；冻结文案 `domain.py:1322` 自述；`snapshot.py:1200` 的相加口径证明两池互斥）。
- **可能影响**：(1) `spot_balance` 列显示的是经典现货钱包余额，**与该对冲实际持有无关**；(2) `drift` 因 `real_spot is not None` 守卫而恒为 `False` —— P2 的「手工减仓致真实 < 记录」检测**静默失效**，装上但永不触发。同样属"错误的安心"。**不造成资金损失。**
- **接受理由**：Human 判断该展示同样需结合真实场景设计，与限制 A 一并延后。
- **临时限制 / 观察方式**：**不得把 `spot_balance` 列读作「本对冲的现货持有量」**，也**不得把 `drift` 无标记读作「记录与实际一致」**。真实持有须看个人账户面板的统一账户余额；手工减仓与否目前只能人工核对。
- **后续复看条件**：同限制 A；另在任何依赖 `drift` 做判断的新功能提出时必须先修。

### 5.2 授权边界

按 `AGENTS.md` §8：该接受**仅针对本次交付与后续合并**。部署、实盘操作与风险参数调整仍须单独授权；若这两条限制在实盘中造成可验证的资金后果，须按 §7 立即写入 `PROJECT_STATE.md`。

**合并到 `main` 时，本节两条限制须提升为 `PROJECT_STATE.md` 的 `[OPEN]` 条目**（Bookkeeper 待办，避免随 stage 目录归档而丢失）。

### 5.3 给后续评审者的说明

review-1（`grok`）与 review-2（`codex`）若独立发现上述两条，**属已知且已被 Human 明确接受的限制，不构成 `REWORK`**。请在结论中记为观察并注明本节路径，不要据此返工 —— 返工额度须留给本次交付中尚未被发现的问题。若发现的是**本节之外**的缺陷，照常按 §8 处置。
