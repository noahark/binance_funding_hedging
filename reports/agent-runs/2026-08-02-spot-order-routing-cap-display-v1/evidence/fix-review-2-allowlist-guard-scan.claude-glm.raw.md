# fix-review-2-allowlist-guard-scan — Claude-GLM 原始回执

由 Human 于 2026-08-03 交回 Bookkeeper；以下为原始回执全文。

```text
提交仅含 2 个 Allowed Files（90 增/23 删）。穷举扫描已完成（无范围外需修站点）。任务完成，输出回执。

[TASK_RESULT v2]
任务 ID: fix-review-2-allowlist-guard-scan
执行结果: completed（完成）
结果摘要: 修 review-2 两处 in-range：purity 守卫更新为冻结 12 条 endpoint（7 PAPI papi.binance.com + 5 spot api.binance.com，保留精确相等+长度 12+按组分 host，未知路径仍 fail-closed）；client 模块 docstring 补 5 条端点并如实陈述展示路径独立注入（无可执行行改动）。穷举扫描 6 项共享项：除该守卫外均无需修。1215 passed + self-check 全绿，提交 e99974a。
产物: [backend/tests/test_hedge_purity.py, backend/services/hedge_open_live_client.py]
检查结果:
1. [pass] 守卫修复：_FROZEN_ALLOWLIST 锁 12 条；test_allowlist_is_exactly_the_frozen_twelve_endpoints 精确相等 + len==12 + PAPI/spot 键集不相交；test_allowlist_hosts_hardcoded_per_group 按 7/5 分组验 host 且 set(values)=={papi,api}；未知路径参数化 5 条均不在 12 条内、仍 PermissionError；test_gate_fires_before_signing 不变。
2. [pass] docstring 更正：hedge_open_live_client.py 端点清单补 5 条；ADR-4 段改为「下单执行路径仍 default-off（仅 live 注入 executor）；展示路径由组合根独立注入、与 APP_HEDGE_EXECUTOR 无关、只可调名单 GET」。AST 顶层结构（imports+9 Assign+AnnAssign+2 ClassDef+1 FunctionDef）未变；git diff 两 hunk 均在 docstring 区（行 14–20、32–46），无可执行行改动。
3. [pass] 穷举扫描（backend/tests/** × {ALLOWLIST, get_snapshot, query_leg, prepare_attempt, _persist_leg_raw, build_rows}），逐项结论：
   - ALLOWLIST：test_hedge_purity（冻结守卫）→已修；test_hedge_open_live_client:208–226（5-aware 正向断言）→无需修；test_service_health:489–490（5-aware）→无需修；test_portfolio_margin_borrow_client（另一 borrow-client 审计面）→无需修。
   - get_snapshot：preflight fake（test_hedge_preflight_provider、test_hedge_service:51/184、test_hedge_task_local:95/1544、test_hedge_review2_regressions:116）均已同步为 (coin, direction)；其余命中为 SnapshotService.get_snapshot()（无参、不同方法）→无需修。
   - query_leg：test_live_hedge_executor:519–532、test_hedge_review2_regressions:147、test_hedge_task_local:118/238/305/1412/1419 均已同步 endpoint（含 super() 转发）→无需修；test_hedge_purity:86 是静态正则禁令→无需修。
   - prepare_attempt：test_hedge_store（13 站）、test_hedge_service:478、test_hedge_review2_regressions:821 均已补 spot_endpoint；其他命中仅注释/docstring→无需修。
   - _persist_leg_raw：test_hedge_task_local:973 仅 docstring 提及→无需修。
   - build_rows：test_snapshot/test_phase2_borrow_sort/test_funding_history 不传 collateral_cap_state（新可选 kwarg，默认 None，additive）→无需修。
4. [pass] 全量验收命令原始尾行：pytest backend/tests -q → 1215 passed in 70.95s；node frontend/self-check.js → 全部自检通过。
5. [pass] git diff --check clean；交付改动仅 2 个 Allowed Files（90 增/23 删）；未触生产逻辑/契约语义/schema/前端/config/fixtures/阶段记录/PROJECT_STATE.md；无新增兼容层/环境变量/测试跳过。
阻塞项: [none]
本地北京时间: 2026-08-03 09:53:38 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本回执交回 Bookkeeper（codex）；Bookkeeper 核验 1215 passed + self-check 全绿 + 仅 2 个 Allowed Files 后，以修复提交 SHA e99974ad934af5117b0c2385e5545f9861812d5d 替换 delivery_sha；随后必须由 DeepSeek 在新 SHA 上重跑 review-1（rework_count=2，根因「改共享常量/签名后 dispatch 清单外既有守卫测试失效」已穷举修复），通过后再回 Opus5 重跑 review-2；未经 review-2 明确 ACCEPT 不授权合并/部署/实盘，本任务不开闸、不调币安、不启动服务。
[/TASK_RESULT]
```
