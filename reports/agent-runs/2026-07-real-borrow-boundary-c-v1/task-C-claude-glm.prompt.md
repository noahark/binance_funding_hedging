[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。

# Task C — Boundary C Live Borrow Implementation

## Role And Outcome

你是本阶段唯一实现者：`claude_glm` / provider identity `zhipu_glm` /
`glm-5.2[1m]`，role `senior_developer`。这是单一串行、backend-dominant 的
混合任务；frontend 只是轻量集成。Codex 不是实现者，Kimi 是后续 fresh
review-1 reviewer。

实现已经冻结的 Boundary C：在默认 disabled、显式 live process mode、durable
global Start、dedicated credentials、单 DB execution owner 等全部 gate 允许时，
把现有 durable borrow-task executor seam 接到精确 allowlist 的 Binance
Portfolio Margin borrow POST；unknown 结果必须 durable blocked 并通过有界 loan
history reconciliation 证明 success，绝不自动重发 POST。

## 必读 Authority

按下列顺序读取并执行；不得只依赖本 prompt 的摘要：

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 `implementation` 节
3. `agents/developer-discipline.md`
4. `agents/skills/senior-developer.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
9. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`
10. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md`
11. 上述 evidence capture 内四份 `raw/*.md`
12. 实际涉及的现有源码与测试；修改前先读，不得按猜测重建。

如以上 authority 真正冲突，写 `ESCALATED`、列出精确文件/段落并停止。不得自行
改需求、降低 fail-closed 语义或向其他模型询问。

## Hard Safety Boundary

- **禁止任何真实、认证或可到达 Binance production host 的请求。** 所有 transport
  测试使用 fake/recording transport 和 dummy credentials；不得读取 `.env`、key
  file、cookie、credential store 或 expanded alias environment。
- 不实现 repay、transfer、sell、order、hedge、close 或 general-purpose signed
  client。
- 不增加 app-level USDT cap、asset allowlist、principal accounting、
  `maxBorrowable` preflight、draft/arm lifecycle、concurrent POST worker 或 browser
  scheduler。
- 不修改 Harness/workflow/validator、unrelated stage、history 或
  `reports/agent-runs/_proposals/**`。
- 不修改 `status.json`、`70-handoff.md`、task/design/ADR/breakdown、canonical
  `docs/**`；不 commit、push、merge、dispatch review 或声明 acceptance。
- 工作树已有 stage evidence 和 `_proposals` 属于用户/其他会话；只触碰本任务允许
  文件，不清理、不覆盖、不顺手重构。

## Allowed Files

- `backend/services/binance_signing.py`（new）
- `backend/services/portfolio_margin_borrow_client.py`（new）
- `backend/services/live_borrow_executor.py`（new）
- `backend/services/private_client.py`（signer refactor only; remains exact-path
  GET-only）
- `backend/borrow_tasks/**`（must remain network/signing-free）
- `backend/app/server.py`, `backend/config.py`
- `schemas/api/borrow-tasks/**`
- `frontend/index.html`, `frontend/self-check.js`
- `.env.example`, `scripts/run-server.sh`
- `backend/tests/test_borrow_*.py`, `backend/tests/test_private_client.py`,
  `backend/tests/test_binance_signing.py`,
  `backend/tests/test_portfolio_margin_borrow_client.py`,
  `backend/tests/test_live_borrow_executor.py`, `backend/tests/test_config.py`
- `backend/tests/test_service_health.py`, `backend/tests/conftest.py`,
  `scripts/tests/test_service_control.py` only when server wiring or credential
  redaction requires them
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
- append-only implementation evidence in
  `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`

Anything else is forbidden unless you stop with `ESCALATED` first.

## Frozen Contracts And Invariants

### Live modules and signing

- Exactly one HMAC/signing primitive in `backend/services/binance_signing.py`.
- Exact transport in `portfolio_margin_borrow_client.py`; exact typed executor in
  `live_borrow_executor.py`; both under `backend/services/` and injected through
  `BorrowTaskService(executor=...)`. `backend/borrow_tasks/**` must not import
  network/signing/live-service modules.
- Borrow client allowlists only:
  `POST https://papi.binance.com/papi/v1/marginLoan` and
  `GET https://papi.binance.com/papi/v1/margin/marginLoan`.
- POST uses the archived `application/x-www-form-urlencoded` body. One
  serializer produces the exact bytes/string consumed by signing and sending.
  No internal POST retry. Dedicated module timeout constant = 10 seconds,
  test-overridable, not env-configurable and not the snapshot timeout.
- Credentials are only `BINANCE_BORROW_API_KEY` and
  `BINANCE_BORROW_API_SECRET`; never log/expose them.

### Configuration, ownership and control API

- `APP_BORROW_EXECUTOR=disabled|live`, default disabled. Unknown value hard-fails
  at config load. Live with missing credentials keeps snapshot/UI available but
  returns `borrow_credentials_missing` and generates zero signed borrow traffic.
- One execution owner per SQLite DB via non-blocking
  `fcntl.flock(LOCK_EX | LOCK_NB)` on `<borrow_db_path>.lock`, acquired before
  any scheduler thread and held for process lifetime. Non-owner serves read/task
  mutation APIs, starts no scheduler, never dispatches, reports
  `not_execution_owner`.
- Exact routes:
  `GET /api/borrow-execution/status`,
  `POST /api/borrow-execution/start`,
  `POST /api/borrow-execution/stop`.
  Start/Stop have no body, are idempotent, return 200 with the status document.
- Implement `schemas/api/borrow-tasks/execution-status.schema.json` exactly as
  frozen in §3.3 of the canonical breakdown; reject extra properties.
  `execution_enabled` defaults false on fresh/migrated DBs. Cooldown is exposed
  but excluded from `can_execute`.

### Durable correctness

- One pre-network transaction rechecks owner, `borrowing`, `live_authorized=1`,
  global Start, no cooldown, no unresolved attempt, and count below target;
  atomically inserts pending, advances cursor, and sets
  `unresolved_attempt_id`. Failed predicate = zero row and zero POST. No DB
  transaction is held during I/O.
- `PRAGMA user_version` migration is idempotent. Add
  `live_authorized INTEGER NOT NULL DEFAULT 0`; pause legacy borrowing tasks once.
  New tasks are authorized by Confirm; migrated tasks only by later explicit
  Start. Ordinary restart preserves post-C state and blocks/reconciles orphans.
- Eligibility includes
  `status='borrowing' AND unresolved_attempt_id IS NULL AND live_authorized=1
  AND success_count < success_target`; Start at target returns `completed`.
- At most one POST in flight. Never replay/catch up missed ticks. Verified floor
  = 2 seconds, default = 5 seconds.

### Classification and reconciliation

- Success only for valid positive arbitrary-precision-normalized `tranId`.
- `known_rejection` exactly `-51006/-51014/-51061`; every other 4xx unknown,
  except `-1003` is rate-limited under HTTP 400 body or HTTP 429.
- 429/418 are global rate limits. Invalid/missing `Retry-After` = 60s; valid
  seconds clamp `[60,300]`. 418 = 300s minimum cooldown plus manual global
  re-arm; never auto-resume.
- Timeout, connection loss, malformed/empty 2xx, 5xx, and executor exceptions are
  unknown. Unknown never sends another POST.
- Reconcile at `+5/+15/+60/+300/+900s`, then visible terminal
  `reconciliation_exhausted`, still blocked. Operator Stop blocks only new POST;
  rate cooldown blocks every signed borrow-client call including GET.
- A unique `CONFIRMED` record proves success: known id uses `txId == tranId`;
  response-less unknown requires exact asset and Decimal principal in a bounded
  dispatch-anchored window. Zero/multiple/cross-task ambiguity remains blocked.
  Persist matched id and `reason="reconciled_unique_txid_match"`. No force-clear
  or retry-anyway HTTP surface.
- Apply the complete resolve matrix in breakdown §5.4. Real success always
  increments; deleted stays deleted; paused/borrowing complete at target;
  completed stays completed. Contain failures at `_dispatch_one` and
  `BorrowScheduler._loop`.

### Frontend and five guards

- Minimal badge, Start/Stop, cooldown/blocked/reconciliation display, pre-create
  amount×count/interval confirmation, and one 2s display poll. Browser never
  signs, schedules or contacts Binance.
- Narrow exactly five guards with dual assertions: single HMAC exit, urlopen
  confinement, unchanged borrow-package AST purity, self-check timer whitelist,
  and self-check POST-method whitelist. No wildcard/prefix/directory exemption.

## Required Tests

Implement every scenario in canonical breakdown §9, including at minimum:
two-owner/no-scheduler; each atomic-gate abort with zero row/POST;
success-after-delete; paused-at-target completion; Start-at-target; no catch-up;
one POST for every 429/418/timeout/reset/5xx/malformed case; dual-layer exception
containment; idempotent raw-SQL pre-C migration fixture; reconciliation
unique/zero/multiple/cross-task/exhausted; exact Decimal match; large `tranId`;
both credential names redacted; both frontend self-check guards; exact
host/path/method/body and gate-before-signing tests.

Run these exact completion commands, and keep their real output:

```text
python3 -m pytest \
  backend/tests/test_borrow_domain.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_executor.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_private_client.py \
  backend/tests/test_binance_signing.py \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py \
  backend/tests/test_config.py -q
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

If a command fails, fix within scope and rerun it. If failure requires a contract
change, forbidden file, live request or outside authority, record exact failure
and stop `ESCALATED`; do not conceal it.

## Closing Duty — Then Stop

1. Append the exact commands, exit/result summaries, relevant failure output and
   local `date` timestamp to
   `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`;
   preserve all existing checkpoint history.
2. Write
   `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
   listing actual changed files, implementation decisions, tests/results,
   remaining findings, `git status`, branch and HEAD. End with the six-line
   `AGENTS.md` footer; Session ID must come from runtime evidence or be explicitly
   unavailable, and Beijing time must come from a local `date` command.
3. Do **not** create a diff patch (parallel/embedded review is disabled), commit,
   change `status.json`/handoff, or dispatch Kimi/review. Stop for the bookkeeper.
4. Final reply reports only outcome, artifact paths, tests and blockers. Never
   claim review or acceptance.

当前 Session ID: unavailable (current bookkeeper runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-claude-glm.prompt.md
本地北京时间: 2026-07-21 07:19:53 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute Task C implementation, run fake-only tests, write 20-implementation.md and append 60-test-output.txt, then stop for bookkeeper
