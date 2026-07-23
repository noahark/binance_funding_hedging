# Backend R4 Fix Dispatch — Hedge Open Real API v1

Human operator: run the prompt body in the original Claude-GLM implementation
session if it remains usable, or a fresh write-capable Claude-GLM fix session.
Do not ask Kimi to change frontend code: its extractor already accepts the
additive `attempts` array required below. Preserve the complete unedited output
as `40-fix-backend-r4.md`.

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须
   对应你本会话内真实发生的动作。
3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

你是本 stage 的 Task A 后端原实现者，执行 bookkeeper 的 R4 范围内修复；不要改前端、
docs、status.json、70-handoff.md 或任何非后端文件，不要 git commit。当前工作树包含你
自己的未提交 Task A 改动和已完成 Task B 前端改动；保留两者，禁止回滚或覆盖前端。

必须先阅读：
- AGENTS.md；
- docs/product/PRD.md §6、§9.2；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,05-cadence-resolution.md,10-design.md,11-adr.md,12-development-breakdown.md,13-r4-diff-reconciliation.md,20-implementation-backend.md}；
- 现有 backend/hedge_open_tasks/{service.py,store.py,domain.py,executor.py} 和 hedge tests；
- frontend/index.html 仅用于确认它已读取 additive `attempts`，不可修改。

修复 R4-1（API/UI attempt 投影）：
- 保留 `/api/hedge-open-logs` 路由、既有 `logs` 项、cursor 行为和旧 payload 语义。
- 在同一响应上**增量**加入 first-class `attempts` 数组。该数组直接投影 durable
  `hedge_open_attempt` + 两条 `hedge_open_leg`，不能仅把 legacy record payload 伪装成
  attempt。它必须覆盖 PREPARED/UNKNOWN_QUERYING/ACCEPTED_OR_QUERYING 以及 resolved
  attempts，让 UI 在查询中也能显示。
- 每项严格至少含：`attempt_id`、`attempt_seq`、`direction`、`q_common`、
  `pair_outcome`、`spot`、`perp`、`residual`、`ts`；legs 含 `client_order_id`、
  `order_id`、`status`、`cumulative_base_qty`、`cumulative_quote_amt`、`avg_price`，
  spot 可含 fee 字段。所有 Decimal 仍为字符串。可添加 `task_id` 以便 UI 关联，但不可
  删除或改名冻结字段。
- 增加 service/API 测试，证明 record attempt 与 querying attempt 的 attempts 投影，
  legacy logs/cursor 不退化，且 residual/Decimal 不走 float。

修复 R4-2（每卡独立异步节拍）：
- `tick()` 必须使每个 eligible running task 的 `_dispatch_one_for_task()` 独立运行，
  不可让慢的 live preflight/POST/查询阻塞另一张卡本 tick 的提交。两腿依然在一对内并发；
  多个任务可同一秒进入自己的 pair 提交。
- 共享 Start、executor mode 和 exchange rate-limit cooldown 仍是 safety gate；不能引入
  全局产品一对一秒锁、不能漏掉 durable-before-send、不能改变 timeout→client-ID 查询、
  不能增加 auto-repair/close/borrow/repay/transfer。
- 用可控 blocking fake executor 写确定性测试：两个 eligible tasks 都已进入 dispatch，
  再释放任意一个；测试不访问网络、不依赖 sleep race。

不要修复或改变：
- disabled/record 默认语义：本 stage 的批准 PRD/10-design 明确它们零**真实 POST**，
  record/dry-run 是现有安全默认；此次不要重构这一点。
- `recvWindow` 的数值也不是本 R4 修复项。
- quoteOrderQty 禁止、fixed q_common 并发、failure threshold、live fill-all 禁止同步 POST、
  filter/Decimal/no-resend 仍必须保持。

允许改动仅限 Task A 原边界中的 backend/hedge_open_tasks/{service.py,store.py,domain.py,
executor.py,scheduler.py}、backend/tests/test_hedge_*.py、backend/tests/test_live_hedge_executor.py、
backend/tests/test_hedge_open_live_client.py，以及
`reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md`。不需要改
backend/services 除非为上述两项提供必要的极小修复；若要超出此范围则 ESCALATED。

必须实际执行并记录：
`.venv/bin/python -m pytest backend/tests -q`
`node frontend/self-check.js`

将原始修复报告写入
`reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md`，说明逐项修复、
实际命令结果、API 形状、并发测试方式、改动文件和遗留问题，并以 footer 结束。完成后停止，
不 commit、不改 status.json、不派发评审。

当前 Session ID: report provider-native ID, or unavailable with reason
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: reconcile R4 fixes, rerun integration evidence, and create H_A/H_B commits
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/backend-r4-fix.prompt.md
本地北京时间: 2026-07-23 22:32:36 CST
下一步模型: human operator
下一步任务: execute this bounded R4 fix packet with Claude-GLM
