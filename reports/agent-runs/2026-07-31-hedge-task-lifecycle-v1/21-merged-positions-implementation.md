# 21-merged-positions-implementation —— Task 1（①）实现报告

- task_id: `hedge-merged-positions-v1`
- target_model: `claude_glm`（zhipu_glm）
- base_sha: `c1cc10e8fb491f83fe4c09f565b34e06c2de0a50`
- 实现：2026-07-31（CST）
- 状态：`dispatched` → `reported`（未合并、未推送；本 dispatch 未授予提交职责）

权威规格：`12-development-breakdown.md` 的 `## Task 1`，决策依据 `10-design.md` P1 / N1-N5、`11-adr.md` ADR-001。计划评审 `deepseek` 已 `ACCEPT`，无 `in-range` 发现（`40-plan-review-deepseek-v2.md`）。

> **修订说明（2026-08-01，`fix-merged-positions-n2-ui-v1`，修复轮 1/3）**：review-1（`grok`，`41-review-1-grok-task1.md`）对本交付（`969c455`）判 `REWORK`，两条 `in-range` 发现 F1（阻塞）/F2 + Bookkeeper 追加的测试完整性项。按 `minimal-change-engineer.md` 就地更正本报告并附本轮修复记录（§10）。`rework_count` 由 `0` → `1`。本轮只做 R1-R4；评审其余建议（混合桶均价单测、HTTP 级 N2 断言、强平价 title、注释更正）已由 Human 推后、未纳入；已接受限制 A/B 未触碰。

## 0. 边界与改动范围

仅改动 dispatch 允许的文件；`scheduler.py`、`private_client.py`、`hedge_preflight_provider.py` 白名单、`domain.py` 的暂停原因集与 51169 文案区（`:1315-1324`）、`status.json`（`current_task.state` 以外）**一律未触**。

```text
 backend/app/server.py                    # handler 接两服务 + 降级装配
 backend/hedge_open_tasks/domain.py       # 新增纯函数 merge_positions（仅追加，文件末尾）
 backend/hedge_open_tasks/store.py        # aggregate_positions: D15 去两条 WHERE + 标记
 backend/tests/test_hedge_store.py        # N-1：D15 反转断言
 backend/tests/test_hedge_api.py          # _POSITION_KEYS 扩为合并行形状
 backend/tests/test_positions_merge.py    # 新增：merge_positions 数据驱动测试（14 用例）
 frontend/index.html                      # 合并表渲染器 + 取代 UM 子表 + account meta
 frontend/self-check.js                   # N-4：mock 同步新形状
```

`service.py` 在 Allowed Files 内但**无需改动**：`get_positions` 仍返回 `aggregate_positions` 桶，合并发生在 handler 层（见 §2）。`test_hedge_review2_regressions.py`（N-3 授权）经核验**无需改动**（见 §3.N-3）。

后端 `git diff c1cc10e -- backend/` 仅落在上列文件；`scheduler.py` / `private_client.py` / `hedge_preflight_provider.py` 零差异。

## 1. 实现要点（对应 N1-N5）

- **后端合并（D14）**：`_hedge_open_positions`（`server.py:607`）现调 `self.service.get_snapshot()`（`try/except SnapshotNotReady`）取 `private_account`，调 `hedge_open_service.get_positions()` 取记账桶，经纯函数 `hedge_open_domain.merge_positions(positions, private_account)` 合并后返回 `{"positions": merged, "account": account_meta}`。两服务**保持解耦**——`SnapshotService` 不注入 `HedgeOpenTaskService`，handler 是装配点。
- **N1（接口）**：就地改 `GET /api/hedge-open-positions`。唯一真实消费者是前端（`index.html:loadHedgePositions`），本任务同步重写渲染器；既有字段名（`coin`/`direction`/`position_qty`/`spot_avg`/`perp_avg`/…）保留，追加合并层字段。无既有消费者受冲击（消费者清单与评审 R3 一致：前端 / self-check mock / test_hedge_api / test_hedge_review2_regressions）。
- **N2（降级）**：账户未就绪或不可用时**不整体 503**。`SnapshotNotReady` 或 `private_account` 缺失/`verified=false` 时，仍返回本地记账行（含 D15 已删任务），账户派生列（UM/现货/借款/未实现盈亏）置空，响应带 `account:{verified:false,error,checked_at}`，HTTP 200。
- **N3（D15 契约）**：`aggregate_positions` 两条查询（`store.py` fill_rows / leg_rows）去掉 `WHERE t.status != deleted`，SELECT 带 `t.status`，桶级 `includes_deleted_task` 标记。已删任务已成交腿计入。
- **N4（前端）**：前端缩为「渲染后端合并结果 + 展示策略」。`renderHedgeMergedPositions`（取代 `renderHedgePositionsSection` + 私有面板 UM 子表）一张表展示 UM 骨架 + 任务成本 + 现货/借款 + 标记。
- **N5（测试）**：合并逻辑在 Python，主战场移到 `backend/tests/test_positions_merge.py`（六场景/1000x/D15/降级/漂移，14 用例确定性单测）；`self-check.js` 只验渲染。

## 2. `merge_positions` 是纯函数（acceptance #13）

- 定义于 `backend/hedge_open_tasks/domain.py`（文件末尾追加，未触碰既有暂停/文案区）。
- 签名 `merge_positions(positions, private_account) -> (merged_rows, account_meta)`：**不持有服务引用、不发起 I/O、不读 SQLite**；入参出参均为纯 dict。
- handler（`server.py`）是唯一装配点：取两服务产物喂入纯函数。`HedgeOpenTaskService` 未被注入 `SnapshotService`。
- 已被 `test_positions_merge.py` 直接数据驱动调用（不经过 HTTP/服务）验证。

## 3. 计划评审具名项 N-1 ~ N-4（acceptance #11）

- **N-1（既有测试断言了 D15 要反转的行为）**：`test_hedge_store.py` 原 `test_aggregate_positions_excludes_deleted_tasks` 断言删卡后 `aggregate_positions() == []`。**已更新**（非删除）为 `test_aggregate_positions_includes_deleted_tasks_d15`：同一 fixture（BTCUSDT forward，fill 0.5@50000），只改任务状态为 deleted，断言「行仍在 + `includes_deleted_task is True` + position_qty=`-0.5` + spot_avg/perp_avg=`50000`」。新旧差异：旧行为=排除（空），新行为=D15 计入并标记。原回归意图（锁死「删除任务与聚合的关系」）保留，方向反转。
- **N-2（行文案写明均价含义）**：合并表对含已删任务的行标记文案为「**含已删除任务记录，均价为混合值**」（采纳评审建议，不止「含已删除任务记录」），提醒用户该行均价混合了活任务与已删任务的腿。
- **N-3（间接消费者）**：`test_hedge_review2_regressions.py:477` 经 `svc.get_positions()` 消费。**经核验无需改动**：合并发生在 HTTP handler 层，`get_positions()` 仍返回 `aggregate_positions` 桶（仅 +`includes_deleted_task`/`spot_qty`/`perp_qty` 等加性字段）；该测试只读 `p["coin"]`，不受影响，全绿。授权文件保留备查，未放宽或删除其任何回归意图。
- **N-4（前端 mock 同步）**：`self-check.js` 三处 mock 同步为新形状 `{positions, account}`：默认 mock（:420）、用例 82 的覆写（:4001）与空态重置（:4051），均带 `account:{verified,error,checked_at}`。

## 4. 因契约变更而修改的测试（acceptance #12，逐条说明）

| 文件 | 改动 | 原回归意图 | 是否保留 |
|---|---|---|---|
| `test_hedge_store.py` | N-1：`excludes_deleted_tasks` → `includes_deleted_tasks_d15`（断言反转） | 锁死「删除任务与聚合关系」 | 保留（方向按 D15 反转） |
| `test_hedge_api.py` | `_POSITION_KEYS` 由 12 键扩为 26 键（桶 15 + 合并层 11） | 锁死 `/api/hedge-open-positions` 行形状 | 保留（形状随 N1 扩展，是收紧非放宽） |
| `test_hedge_review2_regressions.py` | 无改动（核验后不需要） | 间接消费 get_positions | 原样保留 |
| `test_positions_merge.py`（新） | 新增 14 用例：六场景/1000x 诚实不对齐/D15/降级 None/降级 verified=false/漂移/无漂移/JSON 可序列化/无重复行 | 覆盖合并契约 | 新增 |

未删除或放宽任何既有断言；`self-check.js` 128 项全绿、EXIT=0（空态文案与原一致，未改断言）。

## 5. 零新增交易所请求（acceptance #14）

实现路径未引入任何上游读取：`self.service.get_snapshot()` 在 live 是「zero-upstream pure read of the published state」（`snapshot_service.py:237-257`，事实 F-B，经评审独立复核）。handler 仅读已发布状态 + 本地 SQLite 记账桶，二者皆非新增币安请求。`merge_positions` 为纯函数（无 I/O）。

## 6. 占位零三分类（P7）

合并表逐列口径（前端渲染政策，后端占位零 `"0"` 不改）：
- **真值**：未实现盈亏（取 `um_positions[].unrealized_profit`，合并时挂到 `price_pnl`，仅当存在真实 UM 持仓才显示，否则「暂无」）。
- **暂无**：累计资金费 / 借币利息 / 净盈亏 —— 后端恒 `"0"` 占位（本轮无数据源）渲染「暂无」；仅当出现真实非零值（未来接入）才显示数字（故 self-check 用例 82 的 mock `accrued_funding:0.0614` 仍如实显示 `0.0614`，二者一致）。
- **拿不到（—）**：UM 持仓/现货余额/借款在账户未就绪或无 UM 时显示 `—`；强平价忠实显示币安 sentinel `"0"`（带语义，不当价格参与计算）。

## 7. 测试结果

- 后端 `pytest backend/tests/`：**1126 passed**（含新增 `test_positions_merge.py` 14 用例、N-1 反转用例）。
- 前端 `node frontend/self-check.js`：**128 PASS / 0 FAIL，EXIT=0**。
- 原始输出（未改写为叙述）存于 `61-merged-positions-test-output.txt`。

## 8. 与 fake `63f5007` 的形状对齐

合并表形状（UM 骨架 + 任务成本 + 现货/借款 + 标记 + 占位零三分类）对齐 fake 预览。差异已在 `10-design.md` §5 列出（数据源改后端真实合并、`rate_limited` 卡文案属 Task 2、P2/净盈亏口径）。本任务未触碰 fake 预览代码（`index.html` 假数据区块逐字未动，self-check 假数据块仍 PASS）。

## 9. 未越界声明

- 未触碰 Task 2 / Task 3 范围：暂停/删除逻辑、worker 退避、重查间隔（`interval_us`、`scheduler.py`、worker 429 站点）一律未改。
- `rate_limited` 剥离属 Task 2/3，本任务未动。
- 未合并、未推送、未接触凭证或实盘路径。
- 一处透明性说明：dispatch Identity 写 `status_revision: 8`，而 `status.json` 当前 `revision: 9`——差异源自 Bookkeeper 在签发本 Task 1 dispatch 后又落了 D16（rate_limited 裁定，与本任务无关）一记控制提交；`status.json.current_task` 仍精确指向本 dispatch、`state=dispatched`，backend 代码 base_sha..HEAD 无差异，故锚点成立、按本 dispatch 执行。

## 10. 修复轮 1/3（fix-merged-positions-n2-ui-v1）—— R1-R4

修复 review-1（grok，`41-review-1-grok-task1.md`）F1/F2 + Bookkeeper 测试完整性项，按 `minimal-change-engineer.md` 只改必需之处。

### R1｜F1（阻塞）：账户未就绪时合并表仍须可见
- **根因**：`renderPrivatePanel` 在 `pa` 缺失（`display:none;return`）或 `pa.verified!==true`（整页替换为「私有账户未读取」后 `return`）两条路径下都不调用 `renderHedgeMergedPositions`；`loadHedgePositions` 又仅在 `verified===true` 时重绘。后端 N2 数据进了 state，真实降级窗口用户看不见。
- **改法**（`frontend/index.html`）：
  - `renderPrivatePanel`：`!pa` → `!pa && !hasPositions` 才隐藏（无账户且无本地持仓才无可展示）；其余显示面板。`!pa || pa.verified!==true` 分支在「私有账户未读取」占位后**追加 `renderHedgeMergedPositions()`**。
  - `loadHedgePositions`：重绘去掉 `verified===true` 门闩，改为「面板当前可见 或 本地持仓非空」即重绘。
- **兼容性**：test 29（优雅降级，`!pa` 且无持仓）仍隐藏面板；test 26/27（verified=false）占位文案逐字保留、合并表追加其后，断言用 `includes` 不受影响。

### R2｜F2：有 UM 但 unrealized_profit 缺失时不得画 0
- **根因**：`_merge_build_row` 在 upnl 不可解析时保留桶占位 `price_pnl="0"`；前端 `hasUm` 只看 `um_position_amt`，为真即画占位，冒充真值。
- **改法**：
  - 后端（`domain._merge_build_row`）：`price_pnl = upnl if _merge_num(upnl) is not None else None`——可解析（含真值 `"0"`）才写真值，否则 `None`。真值 0 与缺失可区分。
  - 前端（`renderHedgeMergedPositions`）：PnL 仅在 `hasUm && unrealized_profit 可解析` 时画数字，否则「暂无」。
  - 测试（`test_merge_missing_sentinel_values`）：不再锁「缺失→`price_pnl=="0"`」；改为缺失→`None`，并补真值 `"0"` 保留用例。

### R3｜被掏空的断言（Bookkeeper §1.1 / 评审 O4）
- `self-check.js` 原 `includes('UM 持仓')` 验证的是已删除的独立 UM 子表；删除后改由合并表承载，副标题「（UM 持仓为骨架）」恰好命中子串而仍绿——断言空转。
- **改法**：改为验证合并表 section 标题 `includes('对冲开单持仓')`（新结构下有意义的对象），未删除。

### R4｜补渲染断言并验证可失败
- 新增 self-check 块 82b：
  - R1 证据：`verified=false` + 本地 BTCUSDT 行 → 面板不隐藏、`账户数据未就绪` 横幅出现、`对冲开单持仓` section 与 `BTCUSDT` 行可见。
  - R2 证据：有 UM（`um_position_amt`）但 `unrealized_profit=null` → PnL 单元格（合并表第 8 列）含「暂无」、不含 `0.00`。
- **可失败性已实测**：临时回退 R2（`pnlReal=hasUm`）→ R2 断言红（单元格渲染 `—` 而非「暂无」，`EXIT=1`）；临时移除 `!verified` 分支的合并表 → R1 断言红（横幅缺席，`EXIT=1`）。两探测均已还原，全绿。

### 本轮改动文件
`backend/hedge_open_tasks/domain.py`（R2，仅 upnl/price_pnl 一处）、`frontend/index.html`（R1+R2 渲染）、`backend/tests/test_positions_merge.py`（R2 测试）、`frontend/self-check.js`（R3+R4）。`store.py`/`server.py`/`service.py` 本轮未改。

### 测试结果（本轮）
后端 `1126 passed`；前端 `129 PASS / 0 FAIL，EXIT=0`。原始输出覆盖于 `61-merged-positions-test-output.txt`。

### 未触碰
禁改区（`scheduler.py`/`private_client.py`/`hedge_preflight_provider.py` 白名单、51169 文案区 `domain.py:1315-1324`、暂停原因集）、已接受限制 A/B（`single_leg_exposure` 判据、`spot_balance`/`drift` 资金池来源）、Task 2/3 范围、被 Human 推后的评审建议（混合桶均价单测、HTTP 级 N2 断言、强平价 title、注释更正）——均未改。

## 11. 修复轮 2/3（fix-merged-positions-mismatch-labels-v1）—— F3 + G1-G7 + 同根因穷举

修复 review-2（codex，`43-review-2-codex-task1.md`）`in-range` 阻塞 **F3** + Human 真机追加的 **G5/G6/G7**（`44-runtime-observation-task1.md`），按 `minimal-change-engineer.md` 只改必需之处。`rework_count` 由 `1` 递增为 **`2`**（上限 3，仅剩 1 次）。review-2 发布就绪结论：当前不可合并。

### 11.0 两个设计决策（在回执中声明，影响评审路由）

1. **G1 用新增显式字段 `match_status`（Option B），不是前端靠全零反推（Option A）。** 后端 `_merge_build_row` 是唯一同时知道「UM 侧是否存在」与「任务侧是否存在」的位置；显式字段（`normal`/`no_task`/`no_um`）比前端从「全零」反推稳妥——靠全零反推正是本 stage 反复出问题的那类歧义，也是 Bookkeeper 倾向。**代价**：新增一个接口键属契约扩展，按 `AGENTS.md` §8 **须先回 review-1（grok），再回 review-2（codex）**（评审轮次不消耗 `rework_count`，只消耗时间）。
2. **G5 把「字面 `0` 名义额 + 真实成交量」与 `NULL` 名义额同等对待（Policy Y）。** 即：未知名义额既不计入均价的分子（名义额）也**不计入分母**（成交量），并置 incomplete 标记；用独立的 `*_qty_priced` 累加器，使展示用的 `position_qty`/`spot_qty`/`perp_qty` 保持真实值不变。这样 RSRUSDT 合约均价 = `12.46/10000 = 0.001246`（真值），而非 `(0+12.46)/20000 = 0.000623`（被腰斩）。dispatch G5 要求 1「不计入名义额」+ 要求 3「均价不被拉低」只有在此读法下同时成立。

### 11.1 G1-G7 改动逐条（finding→fix 映射）

| 项 | 改动 | 位置 |
|---|---|---|
| **G1** 错配两类有真实文案 | 后端合并层新增 `match_status`；前端在「标记」列渲染简短标签「无任务记录」/「交易所无仓」，推测原因放 `title` 悬停 | `domain.py:_merge_build_row`、`index.html:renderHedgeMergedPositions` markers |
| **G2** no_task 不得显示假 0 成本 | `_merge_empty_bucket_row` 的成本字段（`position_qty`/`spot_qty`/`perp_qty`/`spot_avg`/`perp_avg`）由 `"0"` 改 `None`；前端 `formatHedgeDecimal(None)`→`—`、价差率 `computeHedgeOpenBasisRate(null,…)`→`—` | `domain.py:_merge_empty_bucket_row`（前端无需改，null 已走 —） |
| **G3** 两类错配 + G5 不完整标记的渲染断言 | 新增 self-check 块 82c：no_task 成本列=`—`且不含`0`、标记含「无任务记录」；no_um 标记含「交易所无仓」；incomplete 标记含「均价不完整」+均价单元格带 `title` | `self-check.js` 82c |
| **G4** 不回退 | 后端 `1127 passed`、前端 `130 PASS/0 FAIL`；D15/N2/精确键集/`merge_positions` 纯度/禁改区/F1F2 全保持 | 见 §11.4 |
| **G5** 字面 `0` 名义额按未知 | `aggregate_positions` 新增 `spot_qty_priced`/`perp_qty_priced` 分母；leg_rows 把 `quote is None or 0` 当未知（排除分子分母+置标记）；均价=`notional/priced_qty`；前端显示 incomplete 标记+均价 `title` | `store.py:aggregate_positions`、`index.html` markers+avg title |
| **G6** 全仓借款同币多行不重复 | 前端按 base 资产去重：同币首行显示真值（带 `title`「账户级·按资产·勿竖向相加」），其余行显示「同↑」 | `index.html:renderHedgeMergedPositions` borrowCell |
| **G7** 均价小数位收敛 | 新增 `formatHedgeAvgPrice`（8 位有效数字），用于「现货均价」「合约均价」两列；缺失仍 `—`、真实 0 仍 `0`，**极小真值永不因收敛抹成 0** | `index.html:formatHedgeAvgPrice` |

### 11.2 同根因穷举（§8 同根因刹车）—— 合并表「每列 × 六场景」显示口径

本交付两轮 REWORK 同根因：**展示层没有如实告知用户**（降级整表不显示 → 缺失盈亏画 0 → 错配行不标注且假成本显示 0）。下表把合并表每一列在六个场景下显示什么逐格写明（真值 / 「暂无」/ `—` / 标记文案），标出**本轮改动**的格子，并覆盖「金额为字面 0」情形。目的是一次扫完，不再出现第三类「看起来像真数字的假数字」。

源类：**真值**=有真实数据源的数字；**暂无**=本轮无数据源（资金费/借币利息/净盈亏）画「暂无」；**—**=拿不到/缺失/无记录；**[标记]**=标记列徽标。

| 列 | normal | no_task | no_um | single_leg | missing | empty |
|---|---|---|---|---|---|---|
| 币种 | 真值 | 真值 | 真值 | 真值 | 真值 | 空态 |
| 方向 | 真值 | 真值 | 真值 | 真值 | 真值 | 空态 |
| 仓位价值 | 真值 | 真值 | **—** | 真值/— | **—** | 空态 |
| 持仓数量 | 真值(UM) | 真值(UM) | 真值(本地) | 真值 | 真值(本地) | 空态 |
| 合约开仓价 | 真值 | 真值 | **—** | 真值/— | **—** | 空态 |
| 标记价 | 真值 | 真值 | **—** | 真值/— | **—** | 空态 |
| 强平价 | 真值(sentinel 0 照显) | 真值 | **—** | 真值/— | **—** | 空态 |
| 价格未实现盈亏 | 真值/暂无 | 真值/暂无 | **暂无** | 真值/暂无 | **暂无** | 空态 |
| 现货余额 | 真值/— | 真值/— | 真值/— | 真值/— | **—** | 空态 |
| 全仓借款 | 真值/— | 真值/— | 真值/— | 真值/— | **—** | 空态 |
| 现货均价 | 真值 | **—**【G2】 | 真值 | 真值/— | 真值/— | 空态 |
| 合约均价 | 真值 | **—**【G2】 | 真值 | —/真值 | 真值/— | 空态 |
| 开单价差率 | 真值 | **—**【G2】 | 真值 | 真值/— | 真值/— | 空态 |
| 累计资金费 | 暂无 | 暂无 | 暂无 | 暂无 | 暂无 | 空态 |
| 借币利息 | 暂无 | 暂无 | 暂无 | 暂无 | 暂无 | 空态 |
| 净盈亏 | 暂无 | 暂无 | 暂无 | 暂无 | 暂无 | 空态 |
| 标记 | — 或徽标 | **「无任务记录」**【G1】 | **「交易所无仓」**【G1】 | 「单腿敞口」(既有) | 「交易所无仓」+横幅 | 空态 |

派生展示（清单外）：
- **全仓借款去重**【G6】：同币多行时，首行显示真值（带 `title`「账户级·按资产·同币多行勿竖向相加」），其余行显示「同↑」——`normal`/`no_task`/`no_um`/`single_leg`/`missing` 五场景统一适用。
- **均价小数位**【G7】：`现货均价`/`合约均价` 两列在所有有真值的格子统一收敛到 8 位有效数字（消除除法超长尾数），缺失仍 `—`。
- **「账户数据未就绪」横幅**：仅 `missing`（`account.verified=false`）场景在表头上方出现。
- **`title` 悬停**：均价单元格在 incomplete 时带说明（G5）；全仓借款单元格带账户级说明（G6）；错配标记带推测原因（G1）。

**额外覆盖——「金额为字面 0」情形（G5，归入 normal/no_um 的子情形）**：一条腿 `cumulative_quote_amt` 为字面 `"0"`（币安 2026-07-14 移除 UM 下单返回的成交金额，实盘写路径把未知存成 `"0"`）且 `cumulative_base_qty > 0` 时：
- `合约均价`/`现货均价`：显示**仅在已知金额成交上算的真实均价**（如 RSRUSDT `0.001246`，不被 0 拉低成 `0.000623`）；
- `持仓数量`：仍显示真实成交量（如 `-20000`，未知金额腿的数量照常计入展示）；
- `标记`：追加「**均价不完整**」【G5】；该均价单元格带 `title`「部分成交金额未知，均价为不完整口径」；
- 后端 `perp_avg_price_incomplete`/`spot_avg_price_incomplete` 置真。
- **写入端把未知存成 `"0"` 属 pre-existing（早于 base_sha 的实盘写路径），本轮不改写入端**；只改读取/展示侧不得把它当真值（dispatch G5 范围说明）。

清单外站点的**不适用理由**：
- `fill_rows` 循环（`hedge_open_fill.avg_price`）有**刻意不同**的策略（r5：真实 `"0"` avg_price 是真零、不置 incomplete，`test_hedge_store.py:717` 锁定）。它与 leg_rows 的 `cumulative_quote_amt` 是不同列、不同策略，**不是同一缺陷站点**；本轮不动（动了会反转 r5 既定决策、超出 G5 范围）。`fill_rows` 已同步喂 `*_qty_priced` 分母，保持均价口径一致。
- `single_leg_exposure` 判据、`spot_balance`/`drift` 资金池来源 = 已接受限制 A/B（`22-` §5），Human 已决定本轮不修，不纳入。
- 强平价 title、HTTP 级 N2 断言、混合桶均价单测 = Human 推后项（`42-` §2），不纳入。

### 11.3 G3 断言可失败性（已实测）

- 临时把 `index.html` 的 no_task 标记分支改为 `if (false && …)` → self-check 82c 报 `[FAIL] G1: no_task 行应标记「无任务记录」`（`EXIT=1`），还原后绿。
- 临时把 incomplete 标记分支改为 `if (false && …)` → 82c 报 `[FAIL] G5: 不完整均价应显示「均价不完整」标记`（`EXIT=1`），还原后绿。
- 后端 G5 测试 `test_aggregate_positions_literal_zero_quote_treated_as_unknown_g5` 同时断言 `perp_avg == 0.001246` 与 `!= 0.000623`（回归守卫：若 leg_rows 仍把 `"0"` 当真值，均价会变 `0.000623`，断言红）。

### 11.4 测试结果（本轮）

- 后端 `python3 -m pytest backend/tests -q`：**1127 passed**（+1：G5 锁定用例；`_POSITION_KEYS` 扩为 27 键含 `match_status`；`test_positions_merge` 加 match_status/no_task-None 断言）。
- 前端 `node frontend/self-check.js`：**130 PASS / 0 FAIL，EXIT=0**（+1：82c 块）。
- 原始输出覆盖于 `61-merged-positions-test-output.txt`。

### 11.5 本轮改动文件

`backend/hedge_open_tasks/domain.py`（G1 match_status + G2 no_task None）、`backend/hedge_open_tasks/store.py`（G5 priced-qty + 字面0按未知）、`backend/tests/{test_hedge_api.py, test_hedge_store.py, test_positions_merge.py}`、`frontend/index.html`（G1/G2/G5/G6/G7 渲染）、`frontend/self-check.js`（G3 82c）。`server.py`/`service.py` 本轮未改（match_status 由 `merge_positions` 在 domain 层产出，handler 无需动）。

### 11.6 评审路由声明 + §5 差异同步

- **路由**：本轮**新增接口键 `match_status`** → 契约扩展 → 按本 dispatch「评审路由」段，**先回 review-1（grok），再回 review-2（codex）**。
- **`10-design.md` §5 已同步**：补登「状态标识列（match_status：正常/无任务记录/交易所无仓）」与「均价不完整标记（G5）」「全仓借款去重（G6）」「均价 8 位有效数字收敛（G7）」四项，使「未列即一致」重新成立（见 `10-design.md` §5 末新增条目）。

### 11.7 未触碰（重申）

禁改区（`scheduler.py`/`private_client.py`/`hedge_preflight_provider.py` 白名单、`domain.py:1315-1324` 51169 文案区、暂停原因集）零差异；已接受限制 A/B、Task 2/3 范围、推后项（强平价 title、HTTP N2 断言、混合桶均价单测、注释更正）均未触碰。未合并、未推送、未接触凭证或实盘路径。
