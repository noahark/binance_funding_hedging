# Task Handoff: P10-repaid-interest-price-implementation

## Source Report (author-only; immutable after task end)
- task_id: P10-repaid-interest-price-implementation
- role: Implementer（target_role）
- target model: claude_glm（provider zhipu_glm）
- stage_id: 2026-08-28-repaid-interest-price-v1
- created_at: 2026-08-28 23:36:42 CST
- base_sha: db680957151e17ad9703e1889bcf6571d4ecd812（与 status.json revision 16 一致）
- delivery_sha: pending（本 handoff 先于唯一交付提交创建；实现计划固定于
  e37d45a29017c739118018cab9f250e74a1155e5，控制提交 f4f6c6f 不在交付内）

### 任务背景与依据

按 dispatch 实现已定档计划
`reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
（固定 SHA `e37d45a`，Human 豁免剩余计划复评、授权开发）。产品口径：本地终态事件
（存储意图 `amount == "0"` 且严格 `status == "succeeded"`，Human 约定、非交易所
债务归零证明）之前，币本位累计利息按当前缓存现货买一价动态折 U；终态发生时，
该结算时刻之前的利息行一次性切到该次还款捕获的存储价并固定；终态后 re-borrow
的新行重新开放动态。非零部分还款与 `pending`/`unknown`/`failed` 一律不锁价。

### 实际修改范围（八个实现文件，均在 Allowed Files 内）

1. `backend/margin_repay/store.py` — `_SCHEMA` 增 `repay_price_usdt` /
   `repay_price_source` 两个 NULL TEXT 列（自由 TEXT、无 CHECK/封闭枚举）；
   `__init__` 按 `PRAGMA table_info` 逐列幂等 `ALTER ADD`（旧库补列、新库建全列）；
   `resolve()` 增 2 个可选关键字参数并写入两列（不传 = NULL，旧调用形状不破坏）；
   `_row_to_doc` 增 2 键（POST/GET 响应 additive 扩列）；新增 `list_records()`
   返回 `_row_to_doc` 全键 + `updated_at_us`（int），按 `(updated_at_us,
   client_request_id)` 升序（承接 P2 F3：结算时刻回退字段由此可达）。
2. `backend/ledger_flow/domain.py` — 新增五个纯函数（计划 §3.3，零 I/O，唯一
   匹配+折算权威）：`settlement_ms`（`update_time` 可解析用它，否则
   `updated_at_us // 1000`，均缺 → None 不进索引）、`is_terminal_repay`
   （精确 `"0"` 字符串 + `succeeded`，非数值归一）、`build_repay_match_index`
   （仅终态记录，按 asset 分组、组内 `(settlement_ms, client_request_id)` 升序）、
   `match_interest_repay`（组内第一条 `settlement_ms >= accrued_at_ms`，None =
   开放桶）、`interest_usdt_value`（开放桶当前价动态 / 终态桶存储价固定；USDT
   本位与真零沿用原 to_usdt 规则；缺适用价格 → None）。`build_pnl_series` 增
   可选参数 `repay_records=None`（缺省空 = 现行为向后兼容），利息分支逐行改走
   统一权威，缺适用价格（金额可解析、非 USDT、非真零）与开放行缺当前价同一出口
   进 `unpriced_assets`。
3. `backend/ledger_flow/service.py` — 新增 `sum_interest_usdt_by_asset(asset,
   start_ms, end_ms, price_map, repay_records=None)`：窗口内逐行匹配折算、
   `localcontext` prec=_SUM_PREC Decimal 求和；任一行 None → 整体 None（绝不
   部分相加）；无行 → `"0"`。币本位 `sum_interest_by_asset` 不变。
4. `backend/app/server.py` — 还款写路径（`server.py` 原 1028-1029 之间，现状
   零动作）：新增 `_capture_repay_spot_bid(asset)`，进程内已发布快照纯读
   `{asset}USDT` 的 `opening_quotes.spot_bid_price`（仅 `status=="fresh"` 且
   非空），整段 try/except Exception、契约绝不抛出，失败返回 None。仅当
   `amount == "0"` 且 resolution status 严格 `succeeded` 才调用（非终态零调用）；
   成功写 `repay_price_source="snapshot_spot_bid_at_capture"`。`store.resolve()`
   在异常边界之外无条件恰好执行一次（B8）。`_handle_pnl_series` 与
   `_hedge_open_positions` 均取 `margin_repay_store.list_records()` 传入
   （未配置/未装配 → 空表 = 全部动态暂估，现状）；`_hedge_open_positions` 的
   `borrow_interest_usdt` 改调 `sum_interest_usdt_by_asset`，`net_pnl` 公式、
   遮蔽条件、`close_log`、币本位列、前端 wire 形状均未触碰。
5. `backend/tests/test_margin_repay.py` — `_RESULT_KEYS` 同步 2 新键（计划 §3.4）；
   桩扩展（快照 rows 注入 / `fail_after` 定次抛异常 / 调用计数 / store 实例注入）；
   新用例：终态捕获成功、T4 取价异常仍 succeeded + 两列 NULL + resolve 恰一次、
   无 symbol/非 fresh 报价 → NULL、T10 非终态（非零 succeeded / 0+failed /
   0+unknown）不取价（快照读取停在白名单 1 次）、T8 旧库迁移幂等（两次 __init__
   列各一份、旧行 NULL、旧读不受影响）、新库自由 TEXT 且 `manual_correction`
   可写可读、`list_records` 形状与排序、`resolve` 两列持久化与缺省 NULL。
6. `backend/tests/test_ledger_flow_domain.py` — T1 部分还款保持动态；T2 终态切
   存储价且改当前价曲线不动；终态早于计息 → 开放桶；T3 re-borrow 重新开放 +
   下一终态再锁定；T5 终态行价格 NULL → `unpriced_assets` 且不计入；T6 同毫秒
   tie-break 按 `client_request_id`、`update_time` 缺失回退 `updated_at_us//1000`、
   结算早于计息不匹配、不可解析且无回退不进索引；T9 谓词边界（`"0.0"`/`"0.00"`/
   `"00"`/`""`/`None`/int 0 均非终态）；USDT/真零沿用；缺省 repay_records 现行为。
7. `backend/tests/test_ledger_flow_service.py` — T7 两消费者一致（同一
   (interest_rows, repay_records, price_map) 下 `sum_interest_usdt_by_asset` 与
   `build_pnl_series` 利息值逐位相等，含终态+开放混合）；T5 service 侧 fail-closed；
   空窗 `"0"` / USDT 本位免价 / 不可解析 None / 币本位合计不受影响。
8. `docs/api/public-market-contract.md` — 追加 v0.23 Repaid Interest Valuation
   Amendment：双口径（动态暂估/终态固定）与切换规则；终态约定明示「Human 产品
   约定、非交易所债务归零证明」；两新列与 `repay_price_source` 两个来源值
   （自动 `snapshot_spot_bid_at_capture` / 单独授权 `manual_correction`）及区别，
   自由 TEXT 无 CHECK、读取侧不做来源白名单；捕获边界（缝隙内唯一动作、
   异常隔离、resolve 恰一次）；`fresh` 参数化时效（缓存年龄 `< 2 ×
   cache_ttl_seconds` 且四价归一有效；代码默认 60 秒，仅部署未覆盖时默认阈值
   约 120 秒，未写成运行时保证）；fail-closed 与无自动回补。

### 计划硬边界核对（全部满足）

- 缝隙内动作数 0 → 1（纯内存读、条件触发、整段异常隔离、无网络/重试/sleep/
  跨库读/二次观测）；`resolve` 异常边界之外恰好一次。
- 未加回任何被删对象：无债务归零查询、无 K 线回补、无历史推断、无
  `--assume-debt-zero`、无 coverage 闸门、无新脚本、无前端改动、无新依赖、
  无新抽象层（五个纯函数即计划 §3.3 原文签名）。
- schema 仅两列、无 CHECK/枚举；文档未把默认 120 秒写成运行时保证。

### 命令与结果（dispatch 四条自测，2026-08-28 23:31-23:36 CST）

1. `python -m pytest backend/tests/test_ledger_flow_domain.py
   backend/tests/test_ledger_flow_service.py backend/tests/test_margin_repay.py -q`
   → **177 passed**。
2. `python -m pytest backend/tests -q` → **2062 passed, 1 failed**。唯一失败
   `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients`
   为既有基线失败（PROJECT_STATE Open Follow-ups `[OPEN][2026-08-23]`：
   `public_ip_service.py:47` urlopen 未登记白名单，Bookkeeper 已在基线 `dd12833`
   独立复现同因）。范围外证明：`git diff --name-only db68095 -- backend/services/
   public_ip_service.py backend/tests/test_private_client.py` 为空（本阶段零触碰），
   两文件最后改动提交为 `6922bce`（2026-08-23 stage），早于本阶段 base。失败断言
   原件：`AssertionError: urlopen found outside the designated HTTP clients:
   ['backend/services/public_ip_service.py']`。未修改任何无关文件。
3. `node frontend/self-check.js` → **全部自检通过**。
4. `git diff --check` → clean。

中途一次全量失败自纠：`_hedge_open_positions` 新增的 `margin_repay_store` 属性
读取使 `test_account_cache_refresh_v1.py` 的 duck-typed `_CapHandler`（不继承
`_Handler`）AttributeError（5 例）。该测试文件不在 Allowed Files，改生产代码为
`getattr(self, "margin_repay_store", None)`（未装配 = 未配置，语义等同 None），
全量恢复至仅剩上述既有基线失败。

### 未完成事项

无。存量异常（STORJ 等历史利息行）按计划 §7 留待单独 Human 授权的人工数据库
修正，本交付不含任何生产库写入；未 push/merge/部署/重启/触碰凭据。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json`；
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P10-repaid-interest-price-implementation.handoff.md`；
  `git show <delivery_sha> --stat`（Bookkeeper 解析实际交付 SHA 后填入）；
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- 执行：Bookkeeper 按 Task Handoff Evidence Contract 同文件核验（BOOKKEEPER_APPEND_ONLY
  标记前字节 SHA-256、`pending` delivery_sha 于交付提交后由 `git rev-parse` 解析并写
  status.json，不改写作者源区块），核验本任务 `reported` 转换，并准备 HIGH_RISK
  Review-1 派单（本任务属 money/PnL 口径变更，需 review-1 + review-2）。
- 关卡：Bookkeeper 封存 `base_sha..delivery_sha` 交付区间后，Review-1（跨 provider
  只读）→ Review-2；部署与 STORJ 人工数据库修正均须 Human 另行单独授权。
- 不能假设的事实：① `repay_price_usdt` 为 NULL 的终态行（含全部存量历史还款）在
  匹配到利息行时是 fail-closed 遮蔽而非按当前价折算——上线后 STORJ 会继续「暂无」，
  直到单独授权的人工修正写入；② 两新列在旧生产库上于服务重启（迁移随
  `__init__` 执行）前不存在；③ 全量套件的那一个失败是既有基线，不是本交付回归，
  不得顺手修改无关文件「修复」它。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P10-repaid-interest-price-implementation
执行结果: completed（完成）
结果摘要: 已按定档计划 e37d45a 实现还款时价格折算。margin_repay 增两自由 TEXT 列（幂等迁移）与 list_records；还款缝隙内唯一 best-effort 内存取价（仅 0+严格succeeded 触发、整段异常隔离、resolve 恰一次、失败两列 NULL）；ledger_flow 五纯函数统一折算权威，曲线与持仓两消费者同口径，缺价 fail-closed 遮蔽；测试覆盖 T1-T10；API 契约 v0.23 追加双口径、终态约定与两个来源值说明。前端零改动。
产物: [backend/margin_repay/store.py, backend/app/server.py, backend/ledger_flow/domain.py, backend/ledger_flow/service.py, backend/tests/test_ledger_flow_domain.py, backend/tests/test_ledger_flow_service.py, backend/tests/test_margin_repay.py, docs/api/public-market-contract.md, reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P10-repaid-interest-price-implementation.handoff.md]
检查结果: [目标三文件 177 passed（pass）; 全量 2062 passed + 1 既有基线失败 test_urlopen_only_in_designated_http_clients（pass，public_ip_service.py 白名单漏登记系 2026-08-23 既有项，git diff base 证明本阶段零触碰，原始断言输出已存 handoff）; node frontend/self-check.js 全部自检通过（pass）; git diff --check clean（pass）; 缝隙内动作 0→1 且无网络/重试/sleep/二次观测、resolve 异常边界外恰一次（pass，T4/T10 测试固定）; schema 仅两列无 CHECK/枚举、迁移幂等（pass，T8）; 文档含终态约定非交易所证明、两来源值、fresh 参数化时效（pass）]
阻塞项: [none]
本地北京时间: 2026-08-28 23:36:42 CST
下一步模型: opus5（claude 窗口，当前 status.json.bookkeeper；codex 额度耗尽临时移交）
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P10-repaid-interest-price-implementation.handoff.md、reports/agent-runs/2026-08-28-repaid-interest-price-v1/status.json；执行：Bookkeeper 同文件核验（源 SHA-256、git rev-parse 解析 pending delivery_sha 并写 status.json、确认本任务 reported 转换）后准备 HIGH_RISK Review-1 派单；关卡：Review-1（跨 provider 只读）→ Review-2，部署与 STORJ 人工修正须 Human 另行授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
