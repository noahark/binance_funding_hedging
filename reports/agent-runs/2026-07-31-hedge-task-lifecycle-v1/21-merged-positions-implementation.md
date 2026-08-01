# 21-merged-positions-implementation —— Task 1（①）实现报告

- task_id: `hedge-merged-positions-v1`
- target_model: `claude_glm`（zhipu_glm）
- base_sha: `c1cc10e8fb491f83fe4c09f565b34e06c2de0a50`
- 实现：2026-07-31（CST）
- 状态：`dispatched` → `reported`（未合并、未推送；本 dispatch 未授予提交职责）

权威规格：`12-development-breakdown.md` 的 `## Task 1`，决策依据 `10-design.md` P1 / N1-N5、`11-adr.md` ADR-001。计划评审 `deepseek` 已 `ACCEPT`，无 `in-range` 发现（`40-plan-review-deepseek-v2.md`）。

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
