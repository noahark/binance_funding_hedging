# Task Handoff: P11-repaid-interest-price-review-2-kimi

## Source Report (author-only; immutable after task end)
- task_id: P11-repaid-interest-price-review-2-kimi
- role: Reviewer / Review-2（现实性复评）
- target model: kimi（provider moonshot）
- stage_id: 2026-08-28-repaid-interest-price-v1
- created_at: 2026-08-29 00:02:07 CST
- base_sha: f4f6c6f60113b15a6b7b84abf1c665d67eb00449
- delivery_sha: d315fbd9e5ac93461ecdbd8a4edd1890e35f7f4e（与 status.json revision 17 同值）

### 评审范围与方法

只读评审固定区间 `git diff f4f6c6f..d315fbd`：恰 9 文件（8 实现文件 + 实现者
handoff），区间内仅一个提交 `d315fbd`，无 stage 控制提交混入；HEAD `3c4541f`
为控制提交、范围外。需求权威 `repaid-interest-price.plan.md` 经
`git diff e37d45a..HEAD -- <plan>` 验证与固定版逐字节一致。工作树干净。

**隔离声明**：知悉 Bookkeeper 已临时移交 opus5/claude 且其为计划作者。本评审
未采信 handoff 的 Bookkeeper Verification 段任何结论——所有 M1-M8 判断均由
本评审直接从固定 diff、交付版源码（`git show d315fbd:...`）与自跑命令独立
得出。与并行 Review-1（grok）互不知悉。

### M1 资金缝隙（pass）

交付版 `server.py:1031-1052` 源码核验：`_dispatch_margin_repay` 返回后、
`store.resolve` 之前**只有一个**动作——`parsed["amount"] == "0" and
resolution.get("status") == STATUS_SUCCEEDED` 时调用一次
`_capture_repay_spot_bid`（`:1110-1131`）。该函数整体包在单个
`try/except Exception` 内，只做 `self.service.get_snapshot()` 进程内纯读
（与既有白名单校验、PnL 取价同一快照读法），**无网络、无重试、无 sleep、
无跨库读、无第二次观测**；任何异常返回 None。「绝不抛出」契约成立。
`resolve` 在条件分支**之外**无条件恰好执行一次；`_dispatch_margin_repay`
自身捕获一切异常并恒返回 dict（`:1150-1185`），故 `resolve` 不可被跳过。
缝隙动作数 0 → 1，与计划 §4.2 穷举一致。`resolution` 的键
（status/repaid_amount/update_time/error_code/error_message）与两个新
kwargs 不相交，无 `**resolution` 撞键。

### M2 终态谓词（pass）

唯一谓词两处语义同一：domain `is_terminal_repay`（字符串精确 `== "0"` 且
`== "succeeded"`，不做数值归一）与 server 缝隙闸门（`== "0"` 且
`== STATUS_SUCCEEDED`，已核 `STATUS_SUCCEEDED = "succeeded"`，
`margin_repay/store.py:30`）。正常 API 入口 `_parse_margin_repay_request`
（`server.py:224-280`）确实拒绝 `"0.0"`/`"0.00"`/`"00"`（精确 `"0"` 或
`Decimal > 0` 二选一，其余 400），计划的两层事实表述与代码一致。
re-borrow 重新开放由匹配规则自然成立（`match_interest_repay` 只取
`settlement_ms >= accrued_at_ms` 的第一条，终态后新行落入开放桶）。
计划 §1.3/§3.1、domain 模块注释、`docs/api/public-market-contract.md`
v0.23 三处均如实写「Human 产品约定，NOT proof of exchange debt zero」。

### M3 单一折算权威（pass）

两消费者共用 domain 五函数：`build_pnl_series` 利息分支与
`LedgerFlowService.sum_interest_usdt_by_asset` 都逐行走
`match_interest_repay` + `interest_usdt_value`。price_map 同源：曲线
（`server.py:702-710`）与持仓视图（`:1611-1615`）都从快照
`opening_quotes.status=="fresh"` 且 `spot_bid_price` 非空构建，逐字同规则。
排序键 `(settlement_ms, client_request_id)` 升序确定；`settlement_ms` 回退
`updated_at_us // 1000` 正确（`update_time` 不可解析时穿透到回退，均缺 →
None 不进索引）。开放行用当前价、匹配行只用存储价、互不顶替。

### M4 fail-closed（pass）

终态行 `repay_price_usdt` 为 NULL/不可解析时，`interest_usdt_value` 只读
`matched["repay_price_usdt"]`，**无任何回退到当前价/计提价/零值的路径**。
曲线侧：缺适用价格（金额可解析、非 USDT、非真零）→ `unpriced.add(asset)`，
与开放行缺当前价同一出口，前端经既有 `unpriced_assets` 遮蔽净收益（「成本
不全」）， wire 零改动。持仓侧：`sum_interest_usdt_by_asset` 任一行 None →
整体 None（绝不部分相加）→ `borrow_interest_usdt=None` → `net_pnl=None`
（「暂无」）。与 base 版对比：`to_usdt` 旧缺价登记语义在新利息分支被逐一
复刻（None 前置条件不登记、USDT/真零不登记），开放桶行为零变化。

### M5 schema 与迁移（pass）

`_SCHEMA` 恰增 `repay_price_usdt` / `repay_price_source` 两个裸 TEXT nullable
列，**无 CHECK、无封闭枚举**；`__init__` 按 `PRAGMA table_info` 逐列幂等
`ALTER ADD`。`resolve()` 两参数可选、缺省 NULL，旧调用形状不破坏。
`list_records()` 返回 `_row_to_doc` 全键 + `updated_at_us`（int），SQL
`ORDER BY updated_at_us, client_request_id` 确定。`manual_correction` 写入
路径未被堵死（有测试实证可写可读）。

### M6 零回归（pass）

diff 内无 `close_log` / `_finalize_close_task` 改动；`net_pnl` 公式逐字未变
（仅 `interest_usdt` 来源换成统一权威）；币本位 `sum_interest_by_asset` 未
动；前端 `frontend/` 零文件入 diff；`build_pnl_series` 缺省
`repay_records=None` 时行为等同 base（有 T-兼容性用例固定）。POST/GET 响应
仅 additive 扩两键。

### M7 被删设计未复活（pass）

对 diff 全文关键词扫描（debt/kline/backfill/assume/coverage/fetch_unified/
repay_after/debt_cleared/infer/推定/回补）：命中项全部是否定义表述（文档与
注释中的「不做/非证明」），无一实现性复活。`service.py` 的
`coverage_for_window` 是 base 前既有的账本覆盖度包装（diff 中为未改动的
上下文行），非 P4 F6 那个回补闸门。无新脚本、无新依赖（requirements.txt 未
动）、无新抽象层（五函数即计划 §3.3 原文签名）、无 `--assume-debt-zero`。

### M8 测试真实性（pass）— 按本仓库两起假绿前科的形状逐一排查

- **stub 只替换 I/O 边界**：`_StubRepayClient`（币安网络）与
  `_StubSnapshotService`（快照服务）；被测逻辑走真实 HTTP 服务器
  （`build_server` + 真端口 `_post`）、真实 SQLite `MarginRepayStore`、
  真实 domain 函数。`_series` 仅是对真 `build_pnl_series` 的薄封装。
- **oracle 均锚定**：T2 手算 `-2.5` 且当前价 2→9 结果不变（匹配失效则
  `-1.0`/`-4.5`，必红）；T7 手算 `"1.75"` 外加两消费者逐位等；T4/T10 用
  `snap.calls == 2 / == 1` 精确计数——已核 `_margin_repay_borrowed_assets`
  每请求恰读快照一次，故非终态 `calls==1` 真证明取价未发生；T6 同毫秒
  `aaa`/`bbb` 不同价格使 tie-break 方向可区分；T9 七个边界值带正例对照。
- **无恒真断言/空集满足**：`index == {}` 有 T6 非空索引对照；`unpriced_assets
  == ["WLD"]` 是精确列表等值；`_RESULT_KEYS` 用于 `set(doc) ==` 精确集合
  断言（test_margin_repay.py:186、:687）；parametrize 循环均为具体用例。
- **T8 迁移**用真实旧 schema 建库、两次 `__init__`、PRAGMA 计数断言，旧行
  NULL 与旧读路径均实测。
- 既有断言无一被削弱（三测试文件 diff 只增不改语义；stub 默认值保持原行为）。

### 命令与结果（本评审自跑，非采信转述）

1. `pytest backend/tests/test_ledger_flow_domain.py test_ledger_flow_service.py
   test_margin_repay.py -q` → **177 passed**（32.51s）。
2. `pytest backend/tests -q` → **2062 passed, 1 failed**（166.83s）；唯一失败
   `test_urlopen_only_in_designated_http_clients` 为 dispatch 具名的 2026-08-23
   既有基线项（`public_ip_service.py` 白名单漏登记，本阶段零触碰），不重复报告。
3. `node frontend/self-check.js` → 全部自检通过。
4. `git diff --check f4f6c6f..d315fbd` → clean。

### 范围外观察（不阻塞，仅留痕）

- `_handle_pnl_series` 调 `query_interest_rows(start_ms, end_ms)` 不传 limit，
  已核 base 版 `store.py:443-450`：`limit=None` 即全量，非缺陷，且该调用形态
  base 前既存、本交付未改。
- 现实性提示（计划 §7 预期行为，非缺陷）：本交付不改变任何**存量**显示——
  STORJ 历史终态行迁移后价格仍为 NULL，上线后继续 fail-closed 遮蔽，直至
  Human 单独授权的人工修正。机制只对交付后的新终态还款生效。

### 结论

**评审结论：ACCEPT。** M1-M8 逐条通过，无 in-range 发现，无
pre-existing-release-critical 发现。本 verdict 不授权合并、部署、实盘或
§7 的 STORJ 人工数据库修正。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-2-kimi.handoff.md`；
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`；
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-1-grok.handoff.md`（并行 Review-1 的确定性路径，可能尚未生成）
- 执行：Bookkeeper 按 Task Handoff Evidence Contract 同文件核验本评审（源
  SHA-256、task_id/role/stage_id/base_sha 对账），收齐并行 Review-1 结论后
  按 AGENTS.md §8/§9 推进 stage 状态。
- 关卡：双评审结论齐备后由 Human 决定是否合并/部署；STORJ 人工数据库修正须
  Human 另行单独授权。
- 不能假设的事实：① 本 ACCEPT 不授权合并/部署/实盘；② 全量套件的那一红是
  2026-08-23 既有基线，不得记到本交付头上；③ 本评审不知悉 Review-1（grok）
  结论，双票须独立核对；④ 存量 STORJ 遮蔽是计划 §7 的预期行为，不是回归。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P11-repaid-interest-price-review-2-kimi
执行结果: completed（完成）
结果摘要: Review-2 现实性复评固定区间 f4f6c6f..d315fbd（恰 9 文件），独立于 Bookkeeper 核验。M1-M8 逐项过：缝隙内唯一异常隔离内存取价、resolve 恰一次；谓词精确 "0"+succeeded 且三处如实写 Human 约定；两消费者同一 domain 权威、price_map 同源；终态缺价整体遮蔽、无任何顶替路径；schema 恰两列自由 TEXT、迁移幂等；零回归；被删设计零复活；T1-T10 oracle 均锚定、无假绿形态。四条复现命令全部自跑通过。
产物: [reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-2-kimi.handoff.md]
检查结果: [目标三文件 177 passed（pass，自跑）; 全量 2062 passed + 1 既有基线失败（pass，2026-08-23 白名单既有项）; self-check 全过 + diff --check clean（pass）; M1 缝隙唯一动作 + resolve 恰一次（pass，源码核验）; M2/M5 谓词与 schema 契约（pass）; M3/M4 单一权威与 fail-closed 无顶替（pass）; M6/M7 零回归、被删设计零复活（pass，关键词扫描）; M8 T1-T10 无恒真断言/空集满足/mock 被测逻辑（pass）]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-29 00:02:07 CST
下一步模型: opus5（claude 窗口，当前 status.json.bookkeeper；codex 额度耗尽临时移交）
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-2-kimi.handoff.md、reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json、reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P11-repaid-interest-price-review-1-grok.handoff.md；执行：Bookkeeper 同文件核验本评审并收齐并行 Review-1（grok）结论后推进 stage；关卡：双评审齐备后 Human 决定合并/部署，STORJ 人工修正须另行单独授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
