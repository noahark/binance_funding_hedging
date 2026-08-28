# Task Handoff: P11-repaid-interest-price-review-1-grok

## Source Report (author-only; immutable after task end)
- task_id: P11-repaid-interest-price-review-1-grok
- role: Reviewer / Review-1
- target model: grok（provider xai）
- stage_id: 2026-08-28-repaid-interest-price-v1
- created_at: 2026-08-29 00:02:56 CST
- base_sha: f4f6c6f60113b15a6b7b84abf1c665d67eb00449
- delivery_sha: d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e

### 只读评审范围与隔离

固定 `git diff f4f6c6f60113b15a6b7b84abf1c665d67eb00449..d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e`：恰 9 文件（8 实现 + P10 实现者 handoff），该区间不含 stage 控制提交。`HEAD` `3c4541f` 为封存/派单控制提交，按 §8 范围外。工作区实现文件与 `d315fbd` 一致。

需求权威：`repaid-interest-price.plan.md` 固定于 `e37d45a`。对计划口径本身无异议上交。

隔离：本会话只读新鲜评审；实现作者 `claude_glm` / zhipu_glm，本 Reviewer `grok` / xai，跨 provider 成立。未读取并行 Review-2（kimi）任何产物。未因 Bookkeeper（opus5，同时是计划作者）核验结论降低标准：M1–M8 均对照 `d315fbd` 源码、测试原文与独立复现命令复核。

未启停服务、未下单、未写库、未使用凭据。唯一写入即本文件。

### M1 资金缝隙 — pass

`_handle_margin_repay_post`（`server.py` 于 delivery）在 `_dispatch_margin_repay` 返回后、`store.resolve` 之前：

1. 仅当 `parsed["amount"] == "0"` 且 `resolution.get("status") == STATUS_SUCCEEDED`（`"succeeded"`）调用一次 `_capture_repay_spot_bid`。
2. `_capture_repay_spot_bid` 整段 `try/except Exception: return None`。体内只有 `self.service.get_snapshot()`、遍历 `rows`、读取 `opening_quotes.spot_bid_price`。无 `sleep`/`retry`/`urlopen`/`urllib.request`/跨库 SQL/第二次业务观测。
3. 生产还款客户端在 `config.offline` 时为 `None`（POST 503、走不到缝隙）。live `SnapshotService.get_snapshot` 是 `_published_state` 引用纯读，无锁等待、无上游 I/O；未就绪抛 `SnapshotNotReady`，被捕获函数吃掉并返回 `None`。
4. `resolve(...)` 在该 `try` 之外，成功/失败/非终态路径都执行恰好一次。幂等回放（`is_new=False`）在派发前返回，不在缝隙内。
5. `_dispatch_margin_repay` 返回键仅为 `status` / `repaid_amount` / `update_time` / `error_code` / `error_message`，与显式传入的 `repay_price_*` 无关键字碰撞，不会因 `TypeError` 跳过 `resolve`。

缝隙内动作数 0→1，符合计划 §3.2 / §4.2 B3、B8。

### M2 终态谓词 — pass

`is_terminal_repay`：精确 `record.get("amount") == "0" and record.get("status") == "succeeded"`，无数值归一。捕获侧同一谓词（请求意图 + 本次 resolution）。非零部分还款与 `pending`/`unknown`/`failed` 不进索引、不取价。domain 注释、store 注释、server 注释、`docs/api/public-market-contract.md` v0.23 均写明 **Human 产品约定、非交易所债务归零证明**。终态后 re-borrow：`accrued_at_ms` 晚于上一终态则落入开放桶（T3）。

### M3 单一折算权威 — pass

五个纯函数仅在 `ledger_flow/domain.py`，零 I/O。曲线 `build_pnl_series(..., repay_records=)` 与持仓 `sum_interest_usdt_by_asset` 都走 `interest_usdt_value` / `match_interest_repay`。组内排序 `(settlement_ms, str(client_request_id or ""))`；`update_time` 可解析用它，否则 `updated_at_us // 1000`，均缺不进索引。开放行用 `price_map[f"{asset}USDT"]`，匹配行只用 `matched["repay_price_usdt"]`。T7：同一输入下 service `"1.75"` 与曲线利息 `-1.75` 逐位相反相等。

### M4 fail-closed — pass

`interest_usdt_value`：匹配非空时**不**回退 `price_map`；存储价 NULL/不可解析 → `None`。USDT/真零沿用既有 `to_usdt` 规则。曲线把可解析、非 USDT、非真零却折不出的资产写入 `unpriced_assets`（前端既有 `pnlCostsIncomplete` 把净收益画成「暂无」）；持仓任一行 `None` → 该资产 `borrow_interest_usdt`/`net_pnl` 为 `None`。无当前价/计提价/零值顶替终态价的路径。T5 domain：`price_map` 含 WLD=2 仍 `unpriced_assets==["WLD"]` 且利息合计 0；T5 service：存储价 NULL 时即使当前价=3 仍整体 `None`。

### M5 schema 与迁移 — pass

仅 `repay_price_usdt` / `repay_price_source` 两个裸 `TEXT` 可空列；`_SCHEMA` 与 `ALTER ADD` 均无 `CHECK`/封闭枚举。`__init__` 按 `PRAGMA table_info` 幂等补列。`resolve` 两参数可选，缺省 NULL。`list_records()` 返回 `_row_to_doc` 全键 + `int(updated_at_us)`，`ORDER BY updated_at_us, client_request_id`。T8 旧库两次 `__init__` 列各一份、旧行 NULL；自由 TEXT 可写 `manual_correction` 并读回。

### M6 零回归 — pass

区间无 `frontend/`、`requirements.txt`、新脚本。`close_log` / `_finalize_close_task` 未改。`sum_interest_by_asset` 函数体未改。`net_pnl` 仍为 `funding − interest_usdt − fee_usdt`，缺任一仍 `None`。还款 JSON additive 两键（计划 §3.4 允许）；PnL/持仓 wire 形状未改（缺价仍走 `unpriced_assets` / 行级 `null`）。

### M7 被删设计未复活 — pass

交付 8 个实现文件中无 `debt_cleared`、`repay_after_*`、`--assume-debt-zero`、K 线回补脚本、历史推断、签名余额 GET。`coverage_for_window` 仅保留为**既有**账本窗口完整门（持仓统计 / PnL coverage），未用作还款终态或回补闸门。无新依赖、无新抽象层（五个函数即计划 §3.3 签名）。

### M8 测试真实性 — pass

按仓库假绿前科（恒真非空、空集真空）逐条审视：

| 用例 | 为何不是假绿 |
|---|---|
| T1 | 部分还款 `amount="12.5"` 不进索引；若索引恒空，T2（0.5×存储价 5 = −2.5，改当前价 2→9 不变）会失败 |
| T2 | 算术钉死 −2.5；误用当前价则 −1.0 / −4.5 |
| T3 | 0.5×2 + 0.5×7 + 0.5×3 = 6.0，三档价格缺一即不等 |
| T4 | `fail_after=1`：白名单第 1 次成功、取价第 2 次抛；`status==200/succeeded`、两列 NULL、`resolve_calls==1`。成功路径 sibling 钉 `snap.calls==2` |
| T5 | `price_map` 有当前价仍 unpriced；误用当前价则利息 −1.0 且 unpriced 空 |
| T6 | 同毫秒插入序 bbb 先于 aaa，断言匹配 aaa（crid 升序）；仅 `updated_at_us` 可匹配；不可解析且无回退不进索引 |
| T7 | 终态+开放混合 1.75，全当前价会是 2.25、全存储价会是 1.5 |
| T8 | 旧 schema INSERT 后两次迁移；`PRAGMA` 列计数；旧行 NULL |
| T9 | `"0.0"`/`"0.00"`/`"00"`/`""`/`None`/`0`/`"1"` 均 False；缺 status False；精确 `"0"+succeeded` True |
| T10 | 三参数化路径 `snap.calls==1`（白名单一次）；若误取价则为 2。成功路径对照为 2 |

未发现恒真断言或空集真空。测试调用的是真实 `_capture_repay_spot_bid` / 真实 store / 真实 domain 函数，桩只替换快照与还款 HTTP。

### 独立复现（不采信 Bookkeeper / 实现者自述）

```text
.venv/bin/python -m pytest backend/tests/test_ledger_flow_domain.py \
  backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q
→ 177 passed in 32.45s

.venv/bin/python -m pytest backend/tests -q --tb=line
→ 1 failed, 2062 passed in 162.59s
  唯一失败：test_urlopen_only_in_designated_http_clients
  （public_ip_service.py 未登记白名单，PROJECT_STATE [OPEN][2026-08-23] 既有项，本区间未触碰）

node frontend/self-check.js → 全部自检通过
git diff --check f4f6c6f..d315fbd → clean
```

### 非阻塞观察（不进入 Human 摘要、不构成 REWORK）

1. T4 未再断言 `snap.calls==2`；异常路径是否被走到依赖「白名单必读一次 + fail_after=1」与成功路径 sibling。当前代码下成立。
2. 曲线在 `unpriced_assets` 非空时 API `totals.net` 仍为数字（既有 `test_pnl_series_unpriced_asset_is_skipped_not_zeroed` 同构）；遮蔽由前端 `pnlCostsIncomplete` 完成，符合 M6 零改前端。
3. 同资产「终态行缺价 + 后续开放行有当前价」时，曲线利息分量可能仍计入开放行，持仓侧整段 `None`；净收益仍因 `unpriced_assets` 遮蔽。这不是用当前价顶替终态价。

### 结论

`ACCEPT`。无 in-range `REWORK` 发现。本 verdict 不授权合并、部署、实盘或计划 §7 STORJ 人工数据库修正。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-1-grok.handoff.md`；`reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`
- 执行：Bookkeeper 按 Task Handoff Evidence Contract 同文件核验（`BOOKKEEPER_APPEND_ONLY` 标记前字节 SHA-256、评审闭包 `ACCEPT`、`base_sha`/`delivery_sha` 与 `git rev-parse` 一致、独立复现命令）
- 关卡：与并行 Review-2（kimi）均核验后按 HIGH_RISK 双评审路由推进；合并/部署/STORJ 人工修正仍须 Human 另行授权
- 不能假设的事实：① 本文件是 Review-1 的唯一正式产物，控制台回执不得替代它；② `3c4541f` 及之后的控制提交不在受审交付内；③ 全量套件那一个失败是 2026-08-23 既有基线，不是本交付回归

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P11-repaid-interest-price-review-1-grok
执行结果: completed（完成）
结果摘要: Review-1 ACCEPT。固定区间 f4f6c6f..d315fbd 恰 9 文件。M1–M8 均通过：缝隙内仅一次内存取价且 resolve 恰一次；终态谓词精确 0+succeeded；单一折算权威；缺价 fail-closed 不顶替；两列无 CHECK；零回归；被删设计未复活；T1-T10 真实。177 passed，全量 2062+1 基线。不授权合并/部署/STORJ 修正。
产物: [reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-1-grok.handoff.md]
检查结果: [M1 缝隙内仅一次 get_snapshot 内存读、捕获 except Exception 不抛、无网络/重试/sleep/跨库、resolve 异常边界外恰一次且 **resolution 无键碰撞（pass）; M2 终态谓词精确 amount=="0" AND status=="succeeded"，非终态不锁价，注释/v0.23 写明 Human 约定非交易所证明（pass）; M3 五纯函数唯一权威，(settlement_ms, client_request_id) 排序，update_time 回退 updated_at_us//1000，T7 逐位相等（pass）; M4 匹配行只用存储价、缺价 fail-closed，无当前价/计提价/零值顶替（pass）; M5 两 nullable TEXT 无 CHECK/枚举，迁移幂等，list_records 含 updated_at_us（pass）; M6 close_log / 币本位合计 / net_pnl 公式 / 前端文件零改动（pass）; M7 债务归零查询/K线/--assume-debt-zero/回补闸门/新脚本未复活（pass）; M8 T1-T10 非恒真/非空集真空；独立 177 passed；全量 2062 passed + 1 既有基线；self-check 全过；diff --check clean（pass）]
阻塞项: [none]
本地北京时间: 2026-08-29 00:02:56 CST
下一步模型: opus5（claude 窗口，当前 status.json.bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-1-grok.handoff.md、reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json；执行：Bookkeeper 同文件核验本 Review-1（源 SHA-256、ACCEPT 闭包、base_sha..delivery_sha）；关卡：与并行 Review-2（kimi）均核验后按双评审路由推进，合并/部署/STORJ 人工修正须 Human 另行授权
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
