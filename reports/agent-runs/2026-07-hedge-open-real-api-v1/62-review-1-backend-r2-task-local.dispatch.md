<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md
next_dispatch: none
supersedes: 61-review-1-backend-r2-rework.dispatch.md (unexecuted; runtime/error-policy clauses superseded by user amendment 21)
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 2026-07-hedge-open-real-api-v1 的唯一后端返工实现者。禁止调用、启动或转派任何其他模型/adapter。禁止读取凭据、连接 Binance、发送真实 POST、启用 live/Start、commit，或修改 status.json、70-handoff.md、frontend/**、docs/**、PRD、设计/ADR、环境/凭据文件。

这是第三次也是最后一次允许的有界返工。先逐字读取：
1. `reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md` —— 本包最高业务权威；
2. `58-review-1-backend-r2.md`（含末尾 JSON verdict）—— 原始 P1 证据；
3. `61-review-1-backend-r2-rework.dispatch.md` —— 完整保留的审查者 fix_start_prompt。它未执行；除被 21 明确替换的“全局 tick 对账/全局 429 冷却/余额不足 stopped”运行时条款外，其余要求仍有效；
4. `15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`（尤其 I-7、A-3、A-5）和当前相关源码/测试。

固定旧审查指纹 `8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320` 仅是被审基线；在其之上修改，bookkeeper 会在完成后重算新指纹。

必须完成：

1. **双方向价格完整性（保留 Review-1 P1）**
   `compute_preflight` 对 `est_price` 缺失、零或负值的 fail-closed 要求必须与方向无关。反向任务也必须返回 `REJECT_PREFLIGHT_INCOMPLETE`，且零 attempt、零 POST、零失败计数。增加确定性单测：`DIR_REVERSE + est_price=None` 得到该 rejection。

2. **取消全局守护/全局查询循环；改为任务本地、有界生命周期 worker**
   不得新增或保留一个长期循环扫描所有任务并在主/调度线程里逐腿查询的 immediate-open 守护路径。正常 immediate 任务由人工 Start/recover 触发后，为该 `task_id` 创建（或原子认领）一个本地 worker；该 worker 只拥有自己的一个活跃 pair，执行 `fresh preflight -> durable reserve -> 并发两腿 submit -> 只查询本任务两腿到终态 -> 单次 settle -> 必要时下一组`。任务 done/paused/stopped 时 worker 退出。

   `HedgeOpenScheduler` / `tick()` 不得再作为 immediate 任务的全局“先查全部 pending legs、再发所有任务新单”的运行通道；不得让一个任务的 `query_leg` 卡住另一个任务的 reserve/submit。允许一次性的启动/人工恢复发现，但它只为发现到的具体 task 启动本地恢复 worker 后返回，不得成为常驻扫描器。

   通过 store 的原子任务/attempt claim、已有 active-pair guard 和 durable clientOrderId 保障：重复 Start/recover、并发请求或重启恢复不能为同一 task/pair 创建第二个 worker 或第二次 POST。重启恢复只能按保存的 clientOrderId 查询，绝不重发 write。

3. **任务本地暂停，人工恢复；无本地跨任务联动**
   - 确认的 429/Retry-After：持久化当前任务 `paused`、中文原因和审计日志；当前 worker 退出；不自动 sleep/retry，不增加连续失败次数，不设置/读取全局 rate-limit cooldown，不改变其他任务状态或调度。
   - 确认的余额不足、保证金不足或可用数量不足：持久化当前任务 `paused`、精确安全原因和审计日志；当前 worker 退出；不等待三次阈值，不改变其他任务。
   - 其它既有 fatal 配置事实（symbol、position mode、filter/min-notional）仍是当前任务 `stopped`，除非 21 明确列为暂停。
   - 其它已知非致命失败仍只在 pair 两腿均为终态后，对当前任务结算一次连续失败计数；不允许按单腿分别计数。single_leg、timeout/5xx/unknown 的 client-ID 查询、绝不盲重发规则不变。
   - Binance 外部账户/IP 限频无法保证其他请求被交易所接受；但本应用不得因 A 的 429 而主动暂停、停止、计数或延迟 B/C。

4. **确定性离线回归**
   至少新增并通过下列测试，不能使用 sleep race 或真实网络：
   - 任务 A 的 `query_leg` 被显式 gate 阻塞时，任务 B 仍能及时 reserve/submit 自己的一组；
   - 同一任务的并发 Start/recover 只能得到一个 worker/一个 attempt reservation；
   - A 确认 429 后为 `paused`、A worker 退出、A failure count 不变，B 仍可 dispatch；
   - A 确认余额/保证金/可用数量不足后为 `paused`，B 仍可 dispatch；
   - pending pair 的恢复只 query 保存的 clientOrderId、没有第二次 write；
   - 反向缺失价格预检拒绝。

允许修改：
- `backend/hedge_open_tasks/{domain.py,executor.py,scheduler.py,service.py,store.py}`
- `backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`
- `backend/app/server.py`（仅 Start/recover 到任务本地 worker 的最小接线）
- 直接相关 `backend/tests/test_hedge_*.py` 与 `backend/tests/test_live_hedge_executor.py`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt`（只追加真实命令输出）

禁止修改：`frontend/**`、`docs/**`、PRD、设计/ADR、`status.json`、`70-handoff.md`、`50-review-2.md`、`58-review-1-backend-r2.md`、`61-review-1-backend-r2-rework.dispatch.md`、`21-task-local-runtime-and-manual-pause-amendment.md`、环境/凭据文件或真实网络配置。不要顺便加入 WebSocket、平滑开仓、自动恢复、自动补单、自动平仓、转账、借币或还币。

精确自测（全部通过并把原始输出追加到 `60-test-output.txt`）：
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_review2_regressions.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

将实施说明写入 `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md`（新文件，不覆盖既有 40/41 报告），逐项写明：changed files、旧缺口如何确定性复现、每个任务本地暂停原因、worker 退出/恢复行为、跨任务隔离证据、剩余风险（包括交易所外部 IP/account 429 仍可能拒绝其它请求）。报告末尾写标准 Session footer，然后停止等待 bookkeeper。不得提交、不得派发评审、不得自行判定验收。
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/62-review-1-backend-r2-task-local.dispatch.md
本地北京时间: 2026-07-24 23:15:34 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude-GLM session
