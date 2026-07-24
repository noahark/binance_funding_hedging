# Handoff — Hedge Open Real API v1

## Recovery Header

- Active phase: `fixing / task-local backend Review-1 repair is dispatch-ready`.
- Stage branch: `stage/2026-07-hedge-open-real-api-v1`, created from local main
  `28c550d87c1ca90983d5bde9c7102d42cffecd4e`; current HEAD is
  delivery evidence is `8af3f22d92354fdac61a6a057eb25760b924004b`; the latest
  bookkeeping commit before this checkpoint is `49740640a205abb4128fd53cec365536fc77b227`.
  Fresh task-level Review-1 has split: frontend ACCEPT at `59-review-1-frontend-r2.md`,
  backend REWORK at `58-review-1-backend-r2.md`. User amendment 21 supersedes
  unexecuted packet 61; the only active implementation packet is
  `62-review-1-backend-r2-task-local.dispatch.md`.
- Classification: `MILESTONE`; the mandatory direction panel is complete. The
  user approved a bounded design amendment at
  `15-immediate-loop-and-open-log-amendment.md`; Fable's replacement task
  breakdown is received at `16-replacement-development-breakdown.md`.
- Harness/main sync exception: user-selected Kimi K3 routing was committed on
  local main `5659f79` and merged into this stage as `53831d2`, because the
  pending mandatory panel must use K3. The Harness protocol suite passed
  52/52 and `validate-stage.py --phase checkpoint` passed after the merge.
- Read next: `status.json`, `21-task-local-runtime-and-manual-pause-amendment.md`,
  `58-review-1-backend-r2.md`, and `62-review-1-backend-r2-task-local.dispatch.md`.
- Carried evidence: previous round's
  `reports/agent-runs/2026-07-hedge-open-live-v1/{80-user-acceptance.md,design-inputs.md,10-design.md,11-adr.md}`.
- New raw API recon received:
  `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`.
  It validates PAPI margin quantity/quote capability, UM quantity-only,
  per-leg decimal/filter behavior, and no PAPI testnet. The user selects the
  fixed-quantity route, so quoteOrderQty is not used this stage.
- Safety: no credential access, Binance network call, real POST, push, global
  Start activation, or first live task is authorized. Do not enable
  `APP_HEDGE_EXECUTOR=live`, Start, or a first live task until packet 62 and
  renewed Review-1/Review-2 pass.
- Latest user policy: each task card is an independent asynchronous worker, but
  its count is sequential. It submits exactly one concurrent spot/perpetual
  pair, queries that pair to a final result, and only then may submit its next
  counted pair. Business errors stop only the affected task when classified as
  fatal; an opening-log page records all outcomes. See
  `15-immediate-loop-and-open-log-amendment.md`.

## User-Frozen Scope

- Include the real PAPI POST adapter; actual activation and first live task are
  still a separate human authorization after implementation/review.
- No product numeric risk caps and no numeric both-filled mismatch threshold;
  the operator controls amount, count, and margin allocation.
- An unresolved attempt blocks only its own task's next pair. `orderId` orders
  are queried to terminal state; ambiguous no-response cases are queried by
  client ID, never blindly resent. Three confirmed consecutive non-fatal
  failures pause by default, while a classified fatal error (such as insufficient
  balance) stops its own task immediately. No automatic repair or close occurs.
- Immediate only; smooth WebSocket mode is a separate next stage. Each future
  smooth task will independently monitor its price spread through WebSocket and
  trigger only on its own configured spread-rate condition.
- Working rule is concurrent fixed base `quantity=q_common` for every immediate
  hedge leg; `quoteOrderQty` is not used in this stage. Regular Portfolio Margin
  is the account assumption; PM-Pro is out of scope.
- Kimi direction routing is now `kimi_k3` / `kimi-k3`. The already stored
  `direction-drafts/kimi27.md` remains immutable under its historical filename;
  the human operator confirmed it was in fact executed by K3, so it is the
  valid K3 panel result and does not require rerun.

## Next Action

The final review at `50-review-2.md` remains schema-valid `REWORK`. Its P0
attempt-cap fix is still mandatory, but the user has replaced the timing model:
one task now owns one active pair at a time, while the two legs of that pair
remain concurrent. The same amendment adds a durable, paginated opening-log
page and task-local fatal-error stops. It does not authorize any real order.

`52-review-2-rework-backend.dispatch.md` and
`53-review-2-rework-frontend.dispatch.md` are preserved as immutable evidence
but are superseded before execution. Do not give either to a model.

Fable's replacement breakdown `16-replacement-development-breakdown.md` is
received with a verified Session ID recorded in `status.json`. It freezes the
new one-active-pair task contract, the task-local error matrix, and the
additive `entries` opening-log projection. `54-review-2-rework-backend.dispatch.md`
(Claude-GLM) and `55-review-2-rework-frontend.dispatch.md` (Claude Sonnet 5)
passed the parallel `dispatch-ready` gate and their raw implementation reports
are now received. The Sonnet frontend owner must later receive provider-isolated
GLM Review-1; do not reuse the historical Kimi ownership for this new code.

## Implementation intake and R4 status

- Task A / Claude-GLM and Task B / Kimi raw implementation reports are received
  at `20-implementation-backend.md` and `20-implementation-frontend.md`.
- The bounded backend fix is received in `40-fix-backend-r4.md`. R4-1 adds the
  durable additive `attempts` projection required by the frontend timeline;
  R4-2 starts one worker per eligible task so a slow card does not block a
  sibling card's same-tick submission.
- Bookkeeper reproduced `.venv/bin/python -m pytest backend/tests -q` with
  **862 passed in 43.58s**, `node frontend/self-check.js` with all checks
  passing, and `git diff --check` passing. See `14-r4-verification.md`.
- Backend Review-1 at `30-review-1-backend.md` is **ACCEPT**. Its P2 items are
  future hardening only: reduce `recvWindow` from 60 seconds toward 5 seconds,
  and cap per-tick pending-order reconciliation for a much larger task count.
  Neither changes the current business contract.
- Frontend Review-1 initially returned **REWORK** because `single_leg` and a
  null `pair_outcome` were not shown in plain Chinese and the self-check did not
  cover their real backend values. Sonnet 5 completed the bounded correction in
  `40-fix-frontend-r1.md`, committed as `820dd1e`; the new task fingerprint is
  `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`.
- The re-review in `45-review-1-frontend-rfix.md` is **ACCEPT**: `single_leg`
  now shows 「单腿成交」+ warning, `pair_outcome:null` shows 「查询中」+ info, and
  the self-check covers both states. This is a front-end wording/test repair
  only; it changes no trading, backend, API, credential, or risk rule.
- The raw backend review identifies itself as Opus 4.6. The user-reported
  Sonnet 5 session back-filled dispatch metadata and performed a limited
  spot-check; it did not author a separate review verdict.
- The human operator has now supplied the Task A Claude-GLM runner Session ID
  `694ea9e3-20e9-4f42-800e-940f9530a9bb` and Task B Kimi Session ID
  `session_135dcaae-ea96-456c-960e-00762ebc1fe8`; both are recorded in
  `status.json.session_receipts` with source `operator`.
- `20-implementation.md` is only an index required by the stage template. It
  points reviewers to the unedited Task A, Task B, and R4 raw reports and is
  not a substitute for those reports.

## Replacement rework intake and current R4 result

- Replacement backend report `40-fix-review-2-backend.md` and frontend report
  `40-fix-review-2-frontend.md` are received. The bookkeeper independently
  reproduced **880 backend tests**, the frontend self-check, the 55-test
  Harness protocol suite, and `git diff --check`, all passing. No credential,
  Binance, Start, or real-order action occurred.
- R4 found one P1 interface problem before any evidence commit: the new
  opening-log entries combine attempt records with task events but reuse a
  `next_cursor` belonging only to old logs. Clicking 「加载更多」 can repeat a
  task event. This affects audit display only, not order creation; it still
  must be repaired before review.
- `17-opening-log-pagination-compatibility.md` freezes the small additive
  correction: legacy `cursor` / `limit` / `next_cursor` stay unchanged; the
  opening-log page uses `entries_limit`, `entries_cursor`, and
  `entries_next_cursor`. Individual entry fields remain unchanged.
- `56-open-log-pagination-backend.dispatch.md` (Claude-GLM) and
  `57-open-log-pagination-frontend.dispatch.md` (Claude Sonnet 5) are the
  only current implementation packets. They may be human-run in fresh,
  separate write-capable sessions. They must not change trade behavior or
  activate anything live.

## Replacement R4 完成状态

- 56/57 的原始报告均已收到：`41-fix-open-log-pagination-backend.md` 与
  `41-fix-open-log-pagination-frontend.md`。日志分页已经从旧日志游标中分离：后端
  用稳定的三段排序游标；前端只使用 `entries_next_cursor`，不会回退到旧游标。
- Bookkeeper 完整复跑后端测试 **882 passed in 46.25s**；分页相关后端组合测试
  **63 passed in 13.59s**；前端自检和 55 项 Harness 协议测试均通过；`git diff
  --check` 通过。详情见 `19-replacement-r4-final-reconciliation.md`。
- 54-57 均已完成，R4 对账无待修问题。旧的 Review-1 与 Review-2 都只覆盖返工前
  指纹，不能直接放行这次代码；下一步是本地证据提交和新的 provider-isolated
  Review-1（不同供应商交叉复核）。
- 始终禁止实盘：不得启用 `APP_HEDGE_EXECUTOR=live`、Start 或首笔真实任务。

## 当前 Review-1 派发

证据提交为 `8af3f22`，固定审查指纹为
`8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320`。

- 后端交叉复核：`58-review-1-backend-r2.dispatch.md`，由 Claude Sonnet 5 只读审查
  Claude-GLM 后端；
- 前端交叉复核：`59-review-1-frontend-r2.dispatch.md`，由 Claude-GLM 只读审查
  Claude Sonnet 5 前端。

两者都必须由 human operator 在独立新会话执行；不允许任何审查者改动文件或代为启动模型。

`scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review`
已在 58/59 派发前的干净提交工作树通过。现在两份原始审查报告已经收到，不能再把
58/59 当作待派发任务。

补充审计：56 号包为 entries 不透明游标在 `backend/hedge_open_tasks/domain.py`
新增纯编解码函数，超出其最窄文件清单但不改变交易业务。偏差已记录在
`20-r4-scope-deviation-domain-cursor.md`，58 后端审查者必须结合实际 diff 核对。

## Review-1 结果与唯一下一步

- 前端 Review-1 为 **ACCEPT**。唯一 P3 是 `single_leg` 尝试时间线徽标使用了
  `warning`，样式表使用 `warn`，所以少了警示色；这不改变下单、状态、日志或风险规则，
  不在本次后端修复中顺带扩展。
- 后端 Review-1 为 **REWORK**，两个 P1 都是会影响真实开单的业务问题：反向任务拿不到
  价格时可能跳过最小下单金额校验；慢订单查询会把其它独立任务的新一组下单一起拖慢。
- `61-review-1-backend-r2-rework.dispatch.md` 保留为未执行的审查原文证据；用户批准的
  `21-task-local-runtime-and-manual-pause-amendment.md` 已用 `62` 替换其运行时方案：没有
  新的长期全局守护/全局查询循环，每张任务在自己的短生命周期 worker 内下单和查询。
- 确认 429 或余额/保证金/可用数量不足时，只把当前任务 durable `paused` 并退出 worker，
  等人工恢复；本应用不暂停、停止、计数或延迟其它任务。Binance 仍可能因外部 account/IP
  限频拒绝其它任务，不能保证交易所层面的独立接受。
- 这会使用 `rework_count=3 / max_rework=3` 的最后一次返工额度。P2 的实时限频用量响应头
  只作为后续风险记录，本轮不扩范围。
- 后端修复完成后，bookkeeper 必须核对实际 diff、复跑测试、提交证据并重新派发后端
  Review-1；前端源码未变，其 ACCEPT 证据保留。之后才可进入最终 Review-2。

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/70-handoff.md
本地北京时间: 2026-07-24 23:15:34 CST
下一步模型: human operator
下一步任务: run packet 62 in a fresh write-capable Claude-GLM session; do not activate live trading
