<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的后端返工实现者。禁止调用、启动或转派任何其他模型/adapter。
只可在本任务范围内写代码；绝不读取凭据、绝不连接 Binance、绝不发真实 POST，
绝不 commit、绝不改 status.json、70-handoff.md、PRD、设计/ADR 或前端。

这是终审 REWORK（需要返工）的后端子任务。完整、未改写的 reviewer fix_start_prompt
和全部 findings 都在 `reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`
最后 JSON 中：先逐字阅读它，再阅读
`{04-user-execution-policy.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md}`。
本 dispatch 只做文件边界拆分，不改变 reviewer 的要求、测试或验收口径。
固定被审指纹是：
`01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`。

你的必须修复范围是 reviewer 必须项 1—6：
1. `target_n` 是“计划尝试组数”硬上限，统一使用原子
   `scheduled_attempt_count < target_n`；scheduler、fill-once、任何并发都不能
   建立或 POST 第 N+1 条 attempt。成功/失败/单腿只记录结果，不能触发补发。
2. 每组必须完整新鲜预检后，才用本次精确 q_common、仓位模式、过滤器、账户、余额、
   价格和限频快照持久化 attempt/wire shape，之后才 POST。预检失败：零 attempt、
   零 POST、零模拟、零失败计数。
3. 预检必须 fail-closed（事实不完整即拒绝）：账户/交易对状态、`dualSidePosition`
   字面 false、价格/余额、NOTIONAL 或 MIN_NOTIONAL、MARKET_LOT_SIZE 逐项回退
   LOT_SIZE、当前订单限频事实和批准的安全响应头。
4. 本地记录元数据与交易所 wire 参数分离；两腿签名正文不含 `endpoint` 或其他内部字段。
5. client-ID 对账独立于新开单和 Start，不阻断每秒 dispatch；仅明确 absent 业务证据
   才确认未受理。鉴权/签名/时间戳/权限/5xx/timeout 保持未知；正确终结
   CANCELED/EXPIRED/REJECTED/FILLED 并保留部分成交。
6. 端到端保存实际累计 base/quote、均价、可得手续费、部分成交与 residual；持仓聚合
   纳入任何实际成交量。

允许修改：
- `backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}`
- `backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`
- `backend/app/server.py`（仅独立恢复职责需要的最小接线）
- 直接相关 `backend/tests/test_hedge_*.py`、`backend/tests/test_live_hedge_executor.py`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md`

禁止修改：`frontend/**`、`backend/services/binance_signing.py`、`backend/borrow_tasks/**`、
`docs/**`、`reports/api-samples/**`、`status.json`、`70-handoff.md`、`50-review-2.md`、
环境/凭据文件和任何真实网络配置。

必须新增 reviewer 指定的确定性离线回归，先证明旧缺陷能复现、修复后通过：
- target_n=1 的 success/confirmed_failed/single_leg 及 fill-once+scheduler 并发都至多一条 attempt；
- 新过滤器改变共同网格时，持久化和实际 wire 都使用新 q；任一预检事实缺失零 attempt/POST/失败计数；
- executor→client 两腿签名字段精确且没有 endpoint；Start off/无 eligible/done 仍可对账但不挡 dispatch；
- 400 鉴权错误保持未知、明确 absent 才拒绝、CANCELED 部分成交正确终结；
- quote/partial/fee/residual 进入投影与聚合。网络只能注入 fake。

实际执行并如实记录：
`.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py -q`
`.venv/bin/python -m pytest backend/tests -q`
`node frontend/self-check.js`
`.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`
`git diff --check`

把完整原始实现说明、实际命令输出摘要、findings→fix 映射、已知剩余风险和 changed files
写到 `40-fix-review-2-backend.md` 并停止。为避免并行写同一审计文件，不要修改
`60-test-output.txt`；bookkeeper 会原样汇总你的测试输出。不要 commit、不要评审、不要派发。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect the bounded backend fix, reconcile its diff, and run integration evidence
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/52-review-2-rework-backend.dispatch.md
本地北京时间: 2026-07-24 13:49:15 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session
