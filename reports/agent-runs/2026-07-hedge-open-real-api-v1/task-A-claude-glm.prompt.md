# Task A Dispatch — Backend Hedge Open Real API v1

Human operator: run the prompt body below in a fresh write-capable Claude-GLM
(`glm-5.2[1m]`) implementation session. This packet is immutable task evidence.
The human, not this bookkeeper or the implementation session, owns cross-model
dispatch. Preserve the model's complete unedited response in the implementation
report path named below.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须
   对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

你是 Task A 的唯一后端实现者。实现本阶段已批准的 Hedge Open Real API v1 后端，不做
其他模型派发、不要改 status.json、70-handoff.md、任何 canonical docs 或前端，也不要
自行 git commit。当前分支为 `stage/2026-07-hedge-open-real-api-v1`。

先阅读：
- AGENTS.md；
- docs/product/PRD.md（特别是 §6 与 §9）；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,05-cadence-resolution.md,10-design.md,11-adr.md,06-direction-synthesis.md,12-development-breakdown.md}；
- reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md；
- 相关现有 `backend/hedge_open_tasks/**`、`backend/services/**`、`backend/app/server.py`、
  `backend/config.py` 和 hedge tests。

冻结合同（不得重新设计）：
- 正向 = PAPI margin MARKET BUY + UM MARKET SELL；反向 = PAPI margin MARKET SELL +
  UM MARKET BUY；两腿均以同一 Decimal `q_common`、`quantity` 并发发送。
- margin 使用 `sideEffectType=NO_SIDE_EFFECT`，UM 使用 `positionSide=BOTH`，开仓不
  带 reduceOnly；本阶段任何路径都不用 quoteOrderQty。
- 每张运行任务卡片都是独立异步 worker：每张卡各自每秒一组；多张卡可同一秒各发一组。
  任何任务的旧成交、partial、residual、pending 查询不得阻塞该任务下一组。
- POST 前在同一 durable transaction 落 attempt 和两个 deterministic client order ID。
  orderId 仅代表已受理；查询到终态。timeout/ambiguous 5xx 先按 origClientOrderId 查询，
  永不盲目重发 write POST。
- 两腿都返回 orderId 才是 accepted pair 并清零失败连续计数；仅在查询确认未受理的 pair
  才增加 task-snapshotted `failure_pause_threshold`（默认 3）；达到阈值暂停。成交差异只记录，
  禁止自动补单、取消、平仓、借还币、转账或数量/金额风险上限。
- live 仅能在 `APP_HEDGE_EXECUTOR=live` + durable Start + fresh preflight 时通过窄
  adapter 发送；默认 disabled。任何 live fill-all 不得同步循环 POST。
- 测试和本次实现中禁止真实 Binance POST、私有请求、真实凭据访问或启用 Start/live。
  live client 必须可注入 fake transport；复用唯一 signer，`hedge_open_tasks/**` 不得引入
  签名/网络原语。
- smooth/WebSocket 是后续阶段，不实现。

允许改动：
- backend/hedge_open_tasks/{domain.py,store.py,service.py,executor.py,scheduler.py}
- 新建 backend/services/{hedge_open_live_client.py,live_hedge_executor.py,hedge_preflight_provider.py}
- backend/config.py、backend/app/server.py
- backend/tests/test_hedge_*.py、backend/tests/test_hedge_open_live_client.py、
  backend/tests/test_live_hedge_executor.py
- reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md

禁止改动：frontend/**；backend/services/binance_signing.py；private_client.py 的 allowlist
（只能读式复用）；backend/borrow_tasks/**；public snapshot route/schema；docs/**；
reports/api-samples/**；status.json；70-handoff.md；以及任何凭据或环境文件。

实现要求：
1. 依 `12-development-breakdown.md` §3.3/§3.4 做 additive forward SQLite migration、
   durable attempt/leg、累计成交/均价/残差的展示数据；不删除旧数据或旧 route。
2. 做接受态而非成交态的失败计数与 client-ID query/restart recovery；未知状态持续查询，
   不是失败也不是重发。
3. scheduler 必须在每个 eligible running task 各自 dispatch，不可只取 eligible[0]；
   exchange rate-limit cooldown 仍可作为 shared safety gate。
4. 真实 adapter 的 endpoint/参数/query 行为必须受 `order-model-and-live-seams-recon.md`
   的事实约束；Decimal 固定小数串与各腿 filter 独立处理。
5. 保持 disabled/record 为零网络写入；live fill-all 禁止同步 POST。
6. 后端与前端共用 JSON 字段严格使用 breakdown §3.4，不得改字段名或删除旧字段。

必须实际执行并如实记录：
`.venv/bin/python -m pytest backend/tests -q`

将完整实现报告写到
`reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md`，至少包含：
实际改动的文件、schema/migration 选择、已执行命令和原样结果摘要、未解决问题、与冻结合同
的映射、git diff 概要。报告末尾必须带下面 footer（时间用本机 date 得到）。

完成后停止，等待 bookkeeper；不要 commit、不要改 status.json、不要派发/评审其他模型。

当前 Session ID: report provider-native ID, or unavailable with reason
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-backend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect Task A report, reconcile the backend diff, and run integration evidence
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/task-A-claude-glm.prompt.md
本地北京时间: 2026-07-23 20:13:12 CST
下一步模型: human operator
下一步任务: execute this packet in a fresh Claude-GLM write-capable terminal
