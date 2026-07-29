# Fix Dispatch — Review-1 P1 (fallback order-detail GET not persisted)

Human operator: run in a **fresh, write-capable Claude-GLM session**
(`glm-5.2[1m]`) on branch `stage/2026-07-hedge-order-truth-v1`.

**Use a NEW session, not the one that implemented this stage.** That session
(`2b5e8d01`) was past 65% context before it started work; this fix is narrow and
does not need its history. AGENTS.md bans `reviewer == implementer`, not
`fixer == implementer`, so Claude-GLM remains the correct fix author.

`rework_count`: 1 / 3.

## Bookkeeper's mechanical corrections, disclosed not applied silently

AGENTS.md permits the bookkeeper to add routing metadata but forbids hiding or
rewriting reviewer evidence. The reviewer's `fix_start_prompt` is reproduced
**verbatim** in §Reviewer's fix_start_prompt below. Two mechanical corrections
are stated here instead of edited into it:

- **Interpreter**: the reviewer's prompt says `python3 -m pytest`. On this
  machine `python3` is the system **3.9.6**; the repository interpreter is
  `.venv/bin/python` (**3.11.15**). Use `.venv/bin/python`. Suite lists are
  unchanged. (Same correction as M-1 in the implementation packet — the reviewer
  copied the breakdown's wording, which carries the same slip.)
- **No commit**: the reviewer's prompt says to generate a diff patch and stop.
  Do not commit; the bookkeeper commits stage evidence. (Consistent with the
  reviewer's own "交给 bookkeeper".)

## Reading scope and budget

Applying the packet-scoping guidance that landed on `main` at `1bcc7c2`. Read
these ranges, not whole files. **Total ~10 KB / ~3k tokens.**

| Anchor | Why |
| --- | --- |
| `backend/services/live_hedge_executor.py:520-600` | `_send_one_leg`, including the fallback-query branch that drops the raw (the defect) and `_confirm_um_figures` right after it |
| `backend/services/live_hedge_executor.py:235-300` | the `LegDispatch` dataclass — where a new raw field would go |
| `backend/hedge_open_tasks/service.py:1130-1160` | the drain path, which **already does this correctly** with `source="order_query"` — follow this pattern |
| `backend/hedge_open_tasks/service.py:1575-1610` | `_dispatch_live`'s three `_persist_leg_raw` calls — where the fourth belongs |
| `backend/hedge_open_tasks/service.py:1682-1720` | `_persist_leg_raw` itself, including its control-flow isolation contract |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md` §T3 | the authoritative acceptance criterion |
| `reports/agent-runs/2026-07-hedge-order-truth-v1/30-review-1.md` | the verdict and the bookkeeper's confirmation |

Do not re-read whole files you have already inspected; return by line range. If
you materially exceed this budget, stop and report to the bookkeeper.

## What is actually wrong (bookkeeper's independent confirmation)

Verified against the code, not taken from the reviewer's word:

`live_hedge_executor.py:558-583` — when a POST returns `LEG_UNKNOWN_QUERYING`,
`_send_one_leg` immediately queries the order detail and classifies it. On a
conclusive result it returns a **new** `LegDispatch` that takes every business
field from `resolved.*` — but sets `raw_response=verdict.raw_response` (the
POST). **`resolved.raw_response`, the GET body that actually decided the leg's
fate, is discarded.**

`service.py:1585-1599` — `_dispatch_live` writes exactly three raw rows: spot
`order_post`, perp `order_post`, perp `order_confirm`. Nothing captures the
fallback GET.

**This is an internal inconsistency, and that is the important part.** The drain
path at `service.py:1147` already persists its query response with
`source="order_query"`, citing T3 §3 in its comment. The same class of evidence —
an order-detail GET that determines a leg's outcome — is persisted on one path
and dropped on another. **Follow the existing pattern; do not invent a second
one.**

Why it matters against `00-task.md` T3: the UNKNOWN-POST branch is exactly where
the exchange's own words matter most. The POST told us nothing conclusive, so the
GET is the only record of what happened. Losing it defeats T3 in its hardest
case.

## Reviewer's fix_start_prompt

Reproduced verbatim from the verdict JSON. Read the corrections above before
running the commands inside it.

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本次修复的唯一执行者。禁止调用、启动或转派任何其他模型会话或 adapter 命令。不得读取凭据、不得发 Binance 请求、不得创建任务卡/下单/写入 data/hedge-open-tasks.sqlite3，也不得启动或停止服务。

修复 stage 2026-07-hedge-order-truth-v1 的 review-1 P1 finding。权威验收标准：reports/agent-runs/2026-07-hedge-order-truth-v1/00-task.md（T3）。同时阅读原始证据：01-live-record-evidence.md、02-collateral-cap-finding.md、10-design.md、12-development-breakdown.md、19-r4-reconciliation.md、20-implementation.md、60-test-output.txt，以及固定评审区间 ecc38418f52b525eb61bf1c72b9b2b41c26130ef..5de9ef394b02df1036341cbac832cfc4f6c72ee3。

Finding：backend/services/live_hedge_executor.py:557-583 中，UNKNOWN POST 的即时 fallback GET 被 classify_query_response 解析后，返回的 LegDispatch 只保留原 POST 的 raw_response，丢弃 resolved.raw_response。backend/hedge_open_tasks/service.py:1585-1599 因而不会把该 GET 以 source=order_query 写入 raw 表。此路径不满足 T3"查询订单详情的全量信息落库"。

必须修复：
1. POST 原始响应和该即时 fallback GET 原始响应必须分别保留、分别落库；不得用 GET 覆盖 POST。
2. GET 的 raw 行必须使用 source=order_query，包含 response-only 的 body/http_status/code/msg/transport_error；不得持久化 request 参数、签名、API key 或凭据。
3. 覆盖至少一个服务级场景：POST UNKNOWN（例如 timeout/5xx）后即时 GET 返回确定结果；断言 raw 表同时有 POST 与 order_query 两条记录，并能检索 GET 的 body、code、msg。该修复不得改变订单判定、重发规则、限频规则或 raw 写失败时业务结果。
4. 不要修改锁定文件 backend/services/hedge_open_live_client.py、backend/hedge_open_tasks/wire_constraints.py、backend/services/binance_signing.py、backend/hedge_open_tasks/scheduler.py、schemas/**、docs/**、data/**、前端或其他非范围文件。

允许修改范围：backend/services/live_hedge_executor.py、backend/hedge_open_tasks/service.py、backend/hedge_open_tasks/store.py、backend/hedge_open_tasks/domain.py 及 backend/tests/test_hedge_domain.py、test_hedge_store.py、test_hedge_service.py、test_hedge_executor.py、test_hedge_task_local.py、test_hedge_api.py、test_live_hedge_executor.py。尽量采用最小范围改动。

必须执行：
python3 -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q
python3 -m pytest backend/tests -q

完成后更新本 stage 的实现报告和测试证据，生成所需 diff patch，然后停止，交给 bookkeeper。不要改 status.json 或 70-handoff.md。
```

## Commands to actually run (interpreter corrected)

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
.venv/bin/python -m pytest \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q 2>&1 \
  | tee -a reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

Baseline to beat: **1061 passed**. The new service-level test makes it 1062+.
`test_hedge_open_live_client.py` and `test_hedge_purity.py` are must-run and
must-not-modify.

## Closing

1. Run the tests, append to `60-test-output.txt`.
2. Append a section to
   `reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md`
   describing the fix: what changed, the new test, and confirmation that order
   verdicts, resend rules, rate-limit handling and raw-write-failure behaviour are
   all unchanged. Do not rewrite the existing report — append.
3. **Do not commit.** Stop for the bookkeeper.

## Safety (unchanged, live surface is open)

Service PID 96409 is running in live mode, the Start gate is `1`, and a real
naked SHORT 10000 NOMUSDT is outstanding. No order, no card, no Start, no
credentials, no service start/stop, no write to `data/hedge-open-tasks.sqlite3`.
Tests stay offline and deterministic.

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md（追加章节）
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 核验修复、重算指纹、重跑 pre-review，然后重派 review-1

---

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/31-fix-review-1.dispatch.md
本地北京时间: 2026-07-28 21:10 CST
下一步模型: human operator
下一步任务: 在全新可写 Claude-GLM 会话执行本 packet
