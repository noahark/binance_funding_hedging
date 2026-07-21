[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task C — Bookkeeper Intake Fix 1

你是 Task C 原实现者：`claude_glm` / provider identity `zhipu_glm` /
`glm-5.2[1m]`。实现尚未 commit，也尚未进入 formal review-1。bookkeeper 对
实现 intake 做了静态审计并发现四项 scope-contained 缺口；本轮只修这些缺口，
不是重设计，也不是 reviewer verdict rework。

## 必读（按顺序）

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md`
9. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/query-margin-loan-record.md`
10. 当前 Task C source、tests 和 `60-test-output.txt`

## 必修项

### BK-C-001 — 按真实 `rows` envelope 解析并保持 pagination fail-closed

- `GET /papi/v1/margin/marginLoan` 的 200 contract 是
  `{"rows":[...],"total":N}`，不是 top-level list。
- 只从 contract-valid `rows` 读取记录。`rows` 类型错误、`total` 类型/取值
  错误、transport/HTTP/JSON 错误都必须 fail closed，不能证明 success。
- 若只读取了一页且 `total > len(rows)`，不能把当前页一个 match 当作全局唯一；
  要么真实遍历所需页面（仍限于 fake transport 测试），要么更小改动地保持
  blocked。禁止在证据不完整时宣称 unique。
- 所有 reconciliation fake response 改成官方 envelope；新增 malformed envelope、
  incomplete page/`total` 场景。

### BK-C-002 — 实现真正的 cross-task attribution gate

- 不能把 “record asset 与当前 task 不同” 当作 cross-task ambiguity。
- 在 resolve success 前查询 durable local ledger；candidate `txId` 已归属于其他
  attempt，或另一个 task 存在同 asset、exact Decimal amount、dispatch window
  重叠且尚不能排除归属的 attempt 时，当前 attempt 必须继续 blocked。
- 若需要扩展 network-free `ReconcileOutcome` 携带 candidate timestamp/selection
  metadata，可以在既有 `backend/borrow_tasks/**` 边界内做最小扩展；不得把网络/
  signing import 引入该包。
- response-less query 的 `endTime` 不得晚于本次 signed request timestamp；保持
  dispatch-anchored、最多 30 天、page size ≤100。
- 新增真正两任务测试：不同 task id、相同 asset/amount、重叠 dispatch window、
  官方 envelope 只有一个 CONFIRMED row，不能自动给任一待归属 attempt 计数。
  同时保留一个非歧义 positive case。

### BK-C-003 — 418 minimum cooldown + manual re-arm 不可绕过

- `Start` 不能清除任何尚未到期的 429/-1003/418 cooldown。
- 418 必须同时满足：本地至少 300s 已到期，且之后发生 manual global Start；
  仅时间到期不得 auto-resume，提前 Start 也不得预先消费 re-arm。
- reconciliation GET 收到 418 时必须把 manual-rearm 事实传到 durable store，不能
  退化成普通 cooldown。
- 新增/改正测试：early Start 仍 blocked；ordinary cooldown early Start 仍 blocked；
  418 到期但未 Start 仍 blocked；到期后 Start 才解除；reconciliation GET 418
  同样遵守。

### BK-C-004 — 补齐 sanitized startup lifecycle evidence

- live + missing/empty dedicated borrow key 或 secret 时，进程仍启动，但必须额外
  发出 distinct sanitized lifecycle event，至少包含冻结字段
  `borrow_executor=live` 与
  `borrow_execution_blocked=borrow_credentials_missing`。
- 启动 lifecycle 同时报告 live-authorized task count 与 recovered orphan-blocker
  count；只允许非敏感整数/enum/ownership facts。
- 在 `backend/tests/test_service_health.py` 的现有 `run`/lifecycle fake seam 覆盖：
  event 存在、字段正确、两个 marker credential values 均不出现在 stderr。

## Allowed Files

沿用原 Task C allowed files，且本轮只应触碰与四项 finding 直接相关者：

- `backend/services/portfolio_margin_borrow_client.py`
- `backend/services/live_borrow_executor.py`
- `backend/borrow_tasks/**`（仍必须 network/signing-free）
- `backend/app/server.py`
- `backend/tests/test_portfolio_margin_borrow_client.py`
- `backend/tests/test_live_borrow_executor.py`
- `backend/tests/test_borrow_store.py`
- `backend/tests/test_borrow_scheduler.py`
- `backend/tests/test_borrow_api.py`（仅确有必要）
- `backend/tests/test_service_health.py`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`（append only）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-1.dispatch.md`
  （只回填 Receipt）

禁止修改 `status.json`、`70-handoff.md`、`ACTIVE.json`、task/design/ADR/breakdown、
bookkeeper audit、canonical docs、Harness/workflow/validator、unrelated stage 与
`reports/agent-runs/_proposals/**`。不 commit/push/merge，不 dispatch reviewer。

## 安全约束

- 严禁真实、认证或 production-reachable Binance 请求；所有 transport exercise
  继续使用 injected fake/recording transport + dummy credentials。
- 不读取 `.env`、key file、cookie、credential store 或 expanded alias environment。
- 不增加 repay/transfer/sell/order/hedge/close，不增加 cap/allowlist/preflight/
  concurrent worker，不弱化 exact-path/HMAC/urlopen/import/UI guards。
- 任何不确定结果继续 fail closed；禁止新增 retry-anyway/force-clear/第二次 POST。

## 完成验证

先运行直接覆盖四项修复的最小测试，再完整重跑原五个 completion commands：

```text
python3 -m pytest \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_service_health.py -q
python3 -m pytest \
  backend/tests/test_binance_signing.py \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_config.py \
  backend/tests/test_private_client.py \
  backend/tests/test_private_account_v1.py \
  backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile \
  backend/services/binance_signing.py \
  backend/services/portfolio_margin_borrow_client.py \
  backend/services/live_borrow_executor.py \
  backend/services/private_client.py \
  backend/borrow_tasks/*.py \
  backend/app/server.py backend/config.py
git diff --check
```

把每条真实输出追加到 `60-test-output.txt`，不覆盖既有 checkpoint。更新
`20-implementation.md`，新增 `Bookkeeper intake fix 1` 小节，逐项映射
BK-C-001..004 → changed files → tests → result，并更正原报告中 top-level list、
cross-task、418 re-arm、lifecycle 的不实完成声明。回填 dispatch Receipt 和六行
页脚后停止，等待 bookkeeper re-audit；不得宣称 review 或 acceptance。

当前 Session ID: unavailable (prompt preparation session; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-1.prompt.md
本地北京时间: 2026-07-21 08:46:32 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute this fix packet, correct BK-C-001 through BK-C-004, rerun fake-only completion tests, update implementation evidence, and stop for bookkeeper
