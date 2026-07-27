<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at: unavailable:no start timestamp was recorded by the operator or the report
completed_at: unavailable:the produced report's footer records no clock time and no operator timestamp exists
completed_at_source: 40-fix-review-2-backend.md (no clock time in footer)
session_id: unavailable:the produced report's footer records that the runtime did not expose a provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md
next_dispatch: none
supersedes: 52-review-2-rework-backend.dispatch.md (never executed; do not run it)
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27, closing the 74-review-2-r2.md P1 backlog. Evidence is taken ONLY from the produced report's own footer; every field without a recorded source is marked unavailable with its reason. No command, timestamp or Session ID was invented.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的后端返工实现者。禁止调用、启动或转派任何其他模型/adapter。
只可在本任务范围内写代码；绝不读取凭据、绝不连接 Binance、绝不发真实 POST，
绝不 commit、绝不改 status.json、70-handoff.md、PRD、设计/ADR 或前端。

这是终审 REWORK（需要返工）的后端子任务，且执行合同已被用户批准的修正案替换。
按顺序逐字阅读：
1. `reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md`
   —— 用户批准的修正案，节奏/错误矩阵/开单日志的最高权威；
2. `reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md`
   —— 本轮替换拆分（binding interpretations I-1..I-7、需求 A-1..A-9、冻结 entries 契约 §5）；
3. `reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`
   —— 原始终审 findings 与必须修复项（最后 JSON 是原始 verdict）；
4. `{04-user-execution-policy.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md}`。
冲突时以 15 号修正案为准：**每任务一个顺序执行的活动组**替换旧的每秒一组节奏；
旧包 52 已作废，不得按它执行。被审历史指纹（仅审计锚点）：
`01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`。

你的必须修复范围 = 16 号拆分 A-1..A-9：
1. `target_n` 是"计划尝试组数"硬上限；选择与发送前事务统一原子检查
   `scheduled_attempt_count < target_n`；scheduler、fill-once、任何并发共用同一
   每任务串行入口（I-1），失败/单腿绝不补发第 N+1 组。
2. 每组先完整新鲜预检，再在一个事务里用本次精确 q_common、仓位模式、过滤器/
   账户/余额/价格/限频快照 + 两腿 client ID + wire shape 持久化 attempt，之后才
   并发 POST 两腿。预检失败按 I-7：零 attempt、零 POST、零模拟、零失败计数；
   致命预检事实（余额不足/交易对不可用/仓位模式无效/过滤器违规）→ 任务
   `stopped` + `stop_reason` + 日志条目。
3. 预检 fail-closed：账户/交易对状态、`dualSidePosition` 字面 false、价格/余额、
   NOTIONAL 或 MIN_NOTIONAL、MARKET_LOT_SIZE 逐约束回退 LOT_SIZE、当前订单限频
   事实，缺一即拒；只留脱敏限频响应头。
4. 记录元数据与交易所 wire 参数分离；两腿签名正文不含 `endpoint` 或其他内部字段，
   executor→client 全链路逐字段断言。
5. 顺序组循环 + 独立对账（I-6）：本任务未终态组只挡本任务下一组，绝不挡其他任务；
   Start 关/任务 done/无 eligible 时仍继续轮询既有未终态腿。仅明确 absent 业务码
   确认未受理；鉴权/签名/时间戳/权限/5xx/timeout 保持未知并按 client ID 查询、
   绝不重发；CANCELED/EXPIRED/REJECTED/FILLED 均正确终结并保留部分成交。
6. 端到端保存实际累计 base/quote、均价、可得手续费、部分成交与 residual；
   持仓聚合纳入任何实际成交量（不看字面 FILLED）。
7. 实现修正案错误矩阵（含 I-4 新增 additive 任务态 `stopped`、I-5 全进程 429
   写延迟不改任何任务业务态、I-2 计数语义：双腿受理清零、已知非致命失败计数、
   致命立停）。所有错误记录含机器可读 category/code + 安全中文原因；绝不记录
   密钥/签名/含密头。
8. 按 16 号拆分 §5 冻结契约，additive 扩展 GET /api/hedge-open-logs 的 `entries`
   投影（同路由、同 cursor/limit/next_cursor；logs/attempts 原样保留）；entries
   含各状态 attempt 及任务事件（致命停止/阈值暂停/无 orderId 错误/429 延迟），
   newest-first。字段名不得偏离 §5；有疑问升级 bookkeeper，不得自行改名。

允许修改：
- `backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}`
- `backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`
- `backend/app/server.py`（仅最小接线）
- 直接相关 `backend/tests/test_hedge_*.py`、`backend/tests/test_live_hedge_executor.py`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md`

禁止修改：`frontend/**`、`backend/services/binance_signing.py`、`backend/borrow_tasks/**`、
`docs/**`、`reports/api-samples/**`、`status.json`、`70-handoff.md`、`50-review-2.md`、
`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`、
环境/凭据文件和任何真实网络配置。禁止新增 WebSocket/smooth、自动补单/取消/平仓/
借还币/转账、风险上限或任何真实网络测试。

必须新增 16 号拆分 §3.3 全部 9 条确定性离线回归（先证明旧缺陷可复现、修复后通过），
特别是第 9 条：两个任务 worker 独立推进，且各自 pair 2 绝不早于自己 pair 1 终态。
网络只能注入 fake。

实际执行并如实记录：
`.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py -q`
`.venv/bin/python -m pytest backend/tests -q`
`node frontend/self-check.js`
`.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`
`git diff --check`

把完整原始实现说明、实际命令输出摘要、finding→fix 映射（含修正案条目映射）、
已知剩余风险和 changed files 写到 `40-fix-review-2-backend.md` 并停止。为避免并行
写同一审计文件，不要修改 `60-test-output.txt`；bookkeeper 会原样汇总你的测试输出。
不要 commit、不要评审、不要派发。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-backend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect the bounded backend fix, reconcile its diff, and run integration evidence
```

当前 Session ID: 94305f00-bde4-4d80-a69e-091eddffcbe7
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/54-review-2-rework-backend.dispatch.md
本地北京时间: 2026-07-24 14:55:04 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session (after bookkeeper records this packet)
