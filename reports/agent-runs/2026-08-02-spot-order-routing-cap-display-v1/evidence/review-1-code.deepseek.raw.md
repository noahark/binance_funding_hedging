# review-1-code — DeepSeek 原始回执

由 Human 于 2026-08-03 交回 Bookkeeper；原文保留如下。

```text
[TASK_RESULT v2]
任务 ID: review-1-code
执行结果: completed（完成）
结果摘要: HIGH_RISK review-1（DeepSeek，只读）完成。固定区间 1a55781..0ef8053（后端 04ab07b + 前端 0ef8053）六项重点中五项通过：路由方向、普通现货闭环与 endpoint 权威、allowlist 与缓存隔离、SnapshotService 组合根与四态展示、v0.9 契约/schema/前端均核验无误。491 个任务卡测试与 frontend self-check 全绿。但发现 1 项 in-range 缺陷：生产接口签名变更未同步两个既有测试文件的桩（均不在任务卡清单），独立运行 77 个测试失败。评审结论 REWORK。
产物: [none（只读评审未写文件）]
检查结果:
1. [pass] 基线命令：git rev-parse 两 SHA 均解析正确；git diff --check 1a55781..0ef8053 通过（exit=0）。
2. [pass] 路由方向：decide_spot_route 纯函数正确（reverse→papi_margin 不读名单；forward 命中名单→regular_spot/collateral_cap_precheck、TRADIFI→tradifi_regular_spot、否则 papi_margin）；provider 仅 forward 新读名单，负费率测试证明无 restricted_asset 调用；openLongRestrictedAsset 不读不存。
3. [pass] 执行与审计：regular_spot POST/GET 走 /api/v3/order（api.binance.com）、build_regular_spot_order_params 无 sideEffectType；PRODUCT_SPOT 独立（SPOT_BUSINESS_CODES 空，不继承 51169）；leg.endpoint 唯一权威；PAPI UM 合约腿未变；历史缺字段回退 papi_margin。
4. [pass] allowlist 与隔离：五条 exact (method,path) 全部硬绑定 api.binance.com；_require_whitelisted 在签名/发送前拒绝未登记路径；restricted-asset 经 _get_apikey_only 只带 X-MBX-APIKEY、无 timestamp/recvWindow/signature；预检每次新读、provider 不持有展示缓存、预检结果不回填。
5. [pass] 展示侧：组合根 _build_restricted_asset_client 独立于 APP_HEDGE_EXECUTOR 与 private channel、构造不发请求、不改 Start gate；collateral_cap_for_row 四态无第五组合；失败即未知（last-good 不投影）；方向不过滤；不进 negative_funding_status；checked_at 全表同值。
6. [pass] 契约/schema/前端：v0.9 amendment 含三条闸门、字段定义、真值表、硬规则，margin_public.source 原因已更正；schema collateral_cap optional additive、历史样本仍过；前端 OPTIONAL_ROW_FIELDS/有序判定/fail-closed 未知/标的列高亮/不驱动排序过滤按钮/零外域零新定时器。
7. [fail] 测试接口未同步（in-range）：本区间将 PreflightProvider.get_snapshot 扩为 (coin, direction)、LiveHedgeExecutor.query_leg 扩为 (leg, symbol, cid, endpoint)，但 backend/tests/test_hedge_task_local.py（:95/:1544 get_snapshot、:118/:238/:1412 query_leg）与 backend/tests/test_hedge_review2_regressions.py（:116 get_snapshot、:147 query_leg）的桩仍是旧签名；两文件均不在任务卡 12 文件清单内，独立运行 test_hedge_task_local.py 52 failed、test_hedge_review2_regressions.py 25 failed（TypeError: get_snapshot() takes 2 positional arguments but 3 were given；可复现命令：PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py -q → 77 failed）。base（1a55781）上两接口签名与桩匹配，破裂由本区间引入。修复：同步两文件桩签名为接受 direction/endpoint（或 *a/**k 转发），并将两文件加回回归范围重跑至全绿。
8. [pass] 安全与范围：全部测试 fake transport（491 passed 于 34.1s + self-check 全绿），无真实 Binance 调用/凭证；无 config.py/fixtures 改动；store.py 仅参数化无 DDL/迁移；server.py 组合根未触碰 Start gate；HEAD 仍为 0ef8053，工作区无本评审写入。
阻塞项: [none（返工项见检查结果 7）]
评审结论: REWORK（返工）
问题记录: backend/tests/test_hedge_task_local.py, backend/tests/test_hedge_review2_regressions.py（破裂源：backend/hedge_open_tasks/service.py 与 backend/services/live_hedge_executor.py 的接口签名变更）
修复要求: 由后端作者（claude_glm）按检查项 7 同步两个测试文件的 get_snapshot/query_leg 桩签名并将两文件加入回归范围重跑至全绿；修复后重跑 review-1（按 §8 递增 rework_count 至 1）。修复轮不改变已核验的生产逻辑，仅补测试面。
本地北京时间: 2026-08-03 08:14:32 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本原始回执交回 Bookkeeper（codex）；Bookkeeper 核验后将 REWORK 转后端作者修复（最小测试桩同步 + 回归），修复与新提交后由 Human 启动 review-1 重跑；review-1 ACCEPT 前不得启动 review-2。
[/TASK_RESULT]
```
