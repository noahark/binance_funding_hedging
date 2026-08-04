# Project State

Cross-stage state, read at startup. Keep under 32 KB. Git history is not a runtime
check.

## Live Risks

- `[BY-DESIGN]` **Standing operating premise: the Start gate is kept ON and the
  system runs live.** Human decided 2026-08-03 to leave it open permanently, so
  this is the intended steady state, not an open risk — do not file it as one
  again. Verified at the 2026-08-03 restart:
  `hedge_open_execution_mode mode=live start_gate=true` and
  `borrow_execution_mode mode=live execution_owner=true`, unchanged across
  restarts. **What follows from it, and still holds:** a task moved to `running`
  can send real orders immediately, and **no close function exists** — the system
  opens positions but cannot close them for you. No agent may create orders,
  touch credentials, control the service, or write the live task DB; an
  authorized read-only check must precede any live action.
- `[OPEN][OPERATIONS][2026-08-03]` **The launchd service is broken and has been
  failing in a tight loop.** `com.aoke.funding-hedging.server` reports
  `last exit code = 126` (not executable) with `runs = 78048` and
  `state = spawn scheduled`; it has never been the process serving traffic. The
  service on `127.0.0.1:8787` has been a manually started foreground process in
  the operator's terminal, so killing it does NOT hand over to launchd — the
  restart must be manual (`scripts/run-server.sh`, which is required because
  `backend/config.py` never parses `.env` itself). Diagnose with
  `scripts/service-control.py doctor` (read-only); every repair subcommand needs
  `--confirm`. Not yet fixed by decision (Human 2026-08-03).
- `[NOTE][2026-08-03]` The "no agent may control the service" rule above was
  waived once, explicitly and narrowly: Human directly ordered a restart
  (old PID `2494` → new PID `99045`, port `8787` unchanged, launched detached via
  `nohup scripts/run-server.sh`). Read-only smoke only — `/healthz` `200`,
  `/readyz` `200`, `private_account.verified=true`, 9 merged position rows; no
  order, borrow, transfer, credential, or gate change. The waiver was for that
  one restart and does not generalize.
- `[OPEN][ACCEPTED-CONFIGURATION-RISK]` Regular-spot routing intentionally does
  not perform a runtime API-key trading-permission check. Human states that the
  production API key, IP allowlist, and account permissions are fixed. If any
  of those configuration facts changes, a regular-spot leg can be rejected while
  its concurrently submitted PAPI UM leg has filled (unhedged exposure). This is
  an accepted design limitation only for the unchanged environment; re-review
  before rotating the key, changing IP allowlists/permissions, or enabling the
  regular-spot route. **Observation / temporary operating rule:** a broken
  premise presents as `/api/v3/order` `-2015` -> auth-class
  `LEG_UNKNOWN_QUERYING` -> the order query repeats the same `-2015` until its
  10-try budget ends -> task pauses as `order_state_unknown`, while the concurrent
  PAPI UM SELL may already be filled. The UI does not name this as a permission
  problem; when this pause appears, Human must verify the Binance order and UM
  position before any recovery. Durable behavior authority:
  `docs/api/public-market-contract.md` v0.9; full evidence:
  `archive/2026-08-02-spot-order-routing-cap-display-v1`.
  **Display-side operating premise:** the snapshot service uses the same hedge
  API key to read the platform collateral-cap list on its existing refresh
  cadence. A missing, revoked, or IP-rejected key makes the page show
  「抵押额度未知」; its cache never feeds the order preflight. This stage was
  formally reviewed, and Human separately confirmed the bStock order integration.
## Merged Position Table — Accepted Limitations (Task 1, merged 2026-08-01)

All three are the same class: **the display asserting something it does not
know.** None costs money directly; each can mislead an operating decision.

- `[OPEN][ACCEPTED]` **A** — the single-leg marker only fires when the perp leg is
  entirely absent, so a partial imbalance (spot 2.0 / perp 1.0) reads as "no
  exposure". Not the authoritative exposure verdict; the per-attempt inline log is.
- `[OPEN][ACCEPTED]` **B** — spot balance and drift read the classic spot account
  while the hedge buys into the unified account, so the **drift flag is
  permanently inert**. An absent drift marker does not mean "records agree".
  **Re-stated 2026-08-03 (v4.1 merged):** the positions table now shows the
  unified-account balance on its own 「杠杆」 line, so the account the hedge leg
  actually lands in is finally visible — real data on merge day: `COOKIEUSDT`
  held `2997.0` in the unified account with the classic spot side `null`, a
  holding the previous single 「现货余额」 column could not show at all. But
  `drift` itself was NOT changed: it still compares the task record against the
  classic spot balance (`backend/hedge_open_tasks/domain.py:1700-1709`), so it
  stays permanently inert. **The richer display must not be read as evidence
  that the consistency check was fixed.**
- `[OPEN][ACCEPTED]` **F4 — "exchange has no position" is claimed without
  checking.** Whenever the account cannot be read (`SnapshotNotReady`, or
  `verified: false` from an expired key / changed IP / Binance error), every row
  still reports `no_um` and prints 交易所无仓 with a liquidation hint — verified to
  do so even when the account block *does* contain that position.
  **Re-decided 2026-08-02**: Task 2 was to fix it, Task 2 is deferred, and F4
  **stays accepted**. An exchange outage can trigger both
  `order_state_unknown` (pause and verify) and this false claim, so the table is
  least trustworthy when it matters most. **Operator rule: 「交易所无仓」本身
  永远不足以证明仓位没了 —— 去币安核实。横幅只覆盖三条路径中的两条，
  它不出现，什么也证明不了。**
  Opus5 identified a third path: `verified=true` can hide
  a missing UM-side read. A task bucket plus no matching UM is `no_um` only
  after a successful UM-granular read; the reported root cause is
  `backend/domain/snapshot.py` near `:1098` and `:1120`. This remains deferred.
- `[OPEN][RELEASE-GATE]` The read-only smoke run was never executed. Checklist:
  archive `49-`; it is a hard prerequisite for the next
  live activation. Its B-6 covers private-channel-off, but not F4's third path;
  add that case before the gate is used.

## Task 3 — Cadence + Absent Tolerance (merged 2026-08-02)

Delivery `d2ac353`. Re-query cadence **1s -> 500ms** plus a **10-try per-leg
retry budget** before a `404`/`-2013` is believed. Both reviews ACCEPT after
three review-1 rounds; `rework_count` 2/3. Runtime evidence is **zero**.

- `[OPEN][OPERATING-LIMIT]` **Run at most ~5 tasks draining concurrently.** The
  worker queries *every* non-terminal leg each round, so two legs in flight is
  **4 req/s per task** against Binance's ~20/s weight budget. (An earlier
  Bookkeeper figure of "2/s, ~10 tasks" was a single-leg misreading.) Human's
  lever is symbol count; the durable fix is Task 2's `rate_limited` backoff.
  review-2 also advises a minimum-size first live order with the log page open.
- `[OPEN][ACCEPTED]` **F1-P1** — worker handoff can clear a re-entering worker's
  retry counters (leg regains its full budget, settlement ~5s late; no money
  error, no resend). Accepted because all three `ensure_worker` entries are manual
  clicks and the window is milliseconds. **Re-review the moment any non-manual
  path to `ensure_worker` appears.** Five elements: archive `32-` §7.3.
- `[OPEN][FOLLOW-UP]` Task-card pause reasons render **1 of 7** in Chinese — the
  frontend never reads the `pause_reason_zh` the backend already returns. The log
  timeline *is* wired (via `error_reason_zh`), so the frozen 51169 text and the
  new `order_state_unknown` guidance are reachable there, just not on the card.
  `pre-existing-independent` (`d873699`). Two-line frontend fix; should not wait
  for the deferred Task 2.
- `[OPEN][FOLLOW-UP]` `exposure_alert` is a **dead status** — nothing writes it,
  so the frontend badge can never appear. `pre-existing-independent` (`d90f2f1`).
- `[OPEN][FOLLOW-UP]` A deleted task's `order_state_unknown` settlement records
  `kind=task_paused` with text saying "task paused… resume manually" — it was
  neither paused nor is it resumable. Mild form of the family above.

## Open Follow-ups

- `[OPEN][DIRECTION-CHANGE][2026-08-04]` **Human 决定暂停后端任务 A，前端先行（fake 原型确认制）**。`backend-ledger-store-fetch-v1`（glm）启动后被 Human 叫停：白名单 + 两个单页 fetcher + 8 个测试的初步改动**未验证、未提交、未建 `ledger_flow/` 包**，已按纪律还原（恢复 A 时从 dispatch 重做，改动要点见 A packet 与设计 §13.6）。改由 `frontend-fake-flow-log-v1`（grok/xai）先行：需求 1 按钮真实调整 + 流水日志面板 fake 假数据原型（形状按设计 §13.2 冻结契约），Human 目视确认后再恢复 A → B → C 真实开发。fake 原型为 LOW_RISK（纯 UI 探针、假数据无资金语义）。后续项：glm 终端若仍在运行需手动停止（Bookkeeper 不控制其他终端）。
- `[CLOSED][2026-08-04]` **fake 原型阶段闭环，Human 目视验收通过**。v2 独立流水页（侧栏切换 + 每栏默认最新 20 条 + FAKE 护栏）已提交 `d46523d`。后端任务 A 已恢复路由（glm，从 dispatch 重做）；设计定稿 v1.3（§13.7 独立页布局 + 默认 20 条 + 修订记录）由 Planner 在 C 路由前落定；A → B → C 串行，每份交付后走 review-1 + review-2。
- `[CLOSED][2026-08-04]` **前端布局定稿（Human 验收通过）**。tab-layout v2（panel-actions 双按钮、侧栏三项、market-view 内第二看板）+ 元数据卡片左右排微调（微调由 Human 直接安排 grok 完成，未走标准路由，Bookkeeper 已核验 self-check 全绿），前端最终交付提交 `5613c4e`。下一步：设计 v1.4（Planner）→ 前后端联调（真实 `POST /refresh` 须 Human 授权）→ 统一 review-1 + review-2（A+B+C，provider 隔离：review-1 避 `zhipu_glm`+`xai`，review-2 避两实现作者）。
- `[OPEN][HUMAN-FEEDBACK][2026-08-04]` **流水日志改为费率行情页内双看板 tab（布局迭代，不触 rework_count）**。v1 实现（`frontend-flow-log-tab-layout-v1`）把「费率行情|流水日志」按钮误放 `.badge-row` 且未移除侧栏，Human 验收不合格，已回退至任务 C（f23368b）；根因是 packet 表述缺陷。按 Human 重述意图重新设计 v2（`frontend-flow-log-tab-layout-v2`，grok）：「费率行情」按钮放私有账户 `.panel-actions` 与 `#btn-flow-log` 紧邻、移除侧栏 `#nav-flow-log`、流水日志为 `#market-view` 内第二看板；功能硬规则零回退。确认后设计落 v1.4 → 前后端联调（真实 `POST /refresh` 须 Human 授权）→ 统一 review-1 + review-2（A+B+C）。
- `[OPEN][PROCESS-ADJUSTMENT][2026-08-04]` **Human 决定：先前后端联调通过，再统一评审（review-1 暂缓）**。现状：任务 A 已交付（后端底座，`backend/ledger_flow/` 有 domain/store；`server.py` 无任何 `private-ledger` 路由），任务 B（service+scheduler+两条路由）与任务 C（前端接真实数据）未做，前端页面仍为 fake 演示数据——**前后端未打通**。按 Human 指示：review-1（kimi）暂缓（packet 保留于 stage 目录），先路由 B（glm，status_revision=11）→ C（前端接真实数据，路由前须由 Planner 落设计 v1.3 并对齐 C packet）→ 前后端联调（离线部分免授权；`POST /refresh` 连币安拉真实数据前须 Human 单独授权）→ 联调通过后统一 review-1 + review-2（覆盖 A+B+C）。
- `[OPEN][FOLLOW-UP][2026-08-04]` **Borrow-interest cumulative accounting is still
  unimplemented; live API recon is done.** Signed GET recon on the private
  read-only key confirmed: ledger source =
  `GET /papi/v1/margin/marginInterestHistory` ≡
  `GET /sapi/v1/margin/interestHistory` (same `txId`/`interest`/`total`);
  charge cadence 1h (`PERIODIC` + `ON_BORROW`); cumulative =
  `Σ rows.interest` with `txId` idempotency; `balance.crossMarginInterest` is
  outstanding unpaid only (not historical sum); `portfolio/interest-history`
  empty while `negativeBalance=0`. Code still has E1/E1b whitelist-only (no
  fetcher) and no sapi interestHistory whitelist. Evidence:
  `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`.
  Not a live money risk; blocks a future interest-ledger feature until scoped.
- `[OPEN][FOLLOW-UP][2026-08-04]` **UM funding-fee / commission income ledger is
  still unimplemented; live API recon is done.** Prototype
  (`币安套费率策略，逐仓杠杆.js`) used `GET /fapi/v1/income`; PM path is
  `GET /papi/v1/um/income` (this key gets fapi `-2015`). Same row shape:
  `incomeType`/`income`/`asset`/`time`/`tranId`/`tradeId`. Live 30d mix:
  FUNDING_FEE + COMMISSION (BNB, feeBurn=true) + REALIZED_PNL + TRANSFER.
  Cumulative funding = `Σ income where incomeType=FUNDING_FEE`, idempotent on
  `(incomeType, tranId)`; sort ascending; limit≤1000; weight ~30. Also probed
  `um/commissionRate` and `um/feeBurn`. None are in `PrivateClient` whitelist.
  Evidence:
  `reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`.
  Not a live money risk; blocks a future funding-PnL feature until scoped.
- `[OPEN][IN-PROGRESS][2026-08-04]` **Dual-column flow-log stage
  `2026-08-04-dual-ledger-flow-log-v1` is open; design finalized v1.1, three
  implementation packets ready, plan review pending.** Human answered all
  §7 questions plus seven follow-ups (N1–N7): local SQLite dedup ledger,
  hourly HH:01 refresh, "since last refresh" increment with honest-coverage
  guardrails, contract `private-ledger/v2` (GET reads local DB only + POST
  refresh), three serial packets A→B→C (store-fetch / schedule-api / frontend).
  Plan review packet `plan-review-dual-ledger-flow-log-v1` (deepseek, read-only)
  is prepared but not started. Authority:
  `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` (§11–§18);
  packets under `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/`.
- `[OPEN][FOLLOW-UP][2026-08-04]` **WeChat notification for new funding-fee
  increments was explicitly deferred by Human** (not part of this stage); the
  hourly refresh + increment stats land on-page only. Revisit as a separate
  task if still wanted.
- `[OPEN][FOLLOW-UP][2026-08-04]` **Hedge-task status linkage with the flow log
  was explicitly deferred by Human** ("开单任务状态联动放到后面做"); not part of
  this stage.
- `[OPEN][FOLLOW-UP]` **One orphan borrow blocker recovered at the 2026-08-03
  restart** (`recovered_orphan_blocker_count=1` in the `borrow_execution_mode`
  startup line, alongside `live_authorized_task_count=26`). Never investigated;
  noted here so it is not lost now that the startup state itself is recorded as
  a by-design premise rather than a risk.
- `[OPEN][FOLLOW-UP]` **O-1 — per-asset balances repeat per row, with no
  anti-sum treatment.** The 「现货 / 杠杆」 lines are account-level per-asset
  figures rendered in a table keyed by (coin, direction), so a coin held both
  forward and reverse repeats the same amounts *and* the same USDT valuations on
  both rows; summing the column double-counts. The neighbouring 全仓借款 column
  already solves exactly this — repeats render `同↑` with the title
  「账户级（按资产）；同币多行请勿竖向相加」 (`frontend/index.html:4934-4945`,
  `ef53a02`), while the un-deduped `spot_balance` cell dates to `969c455`; both
  precede `base_sha`. v4.1 §9.2 specified the two lines without dedup, so the
  merged delivery is not a deviation — but it widened the gap from one amount to
  two amounts plus two USDT figures, and USDT reads as summable money. Fix =
  reuse the existing `同↑` treatment on the two balance lines (a two-line
  frontend change). Human accepted the risk at merge (2026-08-03) and deferred
  the fix. Detail: Review-2 handoff O-1.
- `[OPEN][FOLLOW-UP]` **O-3 — the `≈ … U` valuation's price age is invisible.**
  Those values are priced from `price_map`, but the 对冲开单持仓 section's source
  clock shows only the earliest of `um_positions` / `unified_balances` /
  `spot_balances` — v4 §5.3 deliberately keeps `price_map` off panel titles. So a
  valuation can rest on a quote older than the time displayed above it, with
  nothing on the page saying so. Pre-existing convention (the balance cards do
  the same) extended to a new place; not a false statement, just an unshown
  dimension.
- `[OPEN][FOLLOW-UP]` **O-6 — missing `free`/`locked` still paints a fake `0`.**
  `spot_by_asset` uses `free = _merge_num(...) or Decimal(0)`
  (`backend/hedge_open_tasks/domain.py:1768-1770`, introduced `969c455`, earlier
  than `base_sha` and untouched by this delivery), so a spot row carrying only
  `asset` renders 「现货: 0 ≈ — U」 — amount painted as a true zero while its
  valuation is unknown. This is the one hole in v4.1's 「缺失绝不画 0」 promise.
  Reaching it requires Binance to omit both fields on a balance row; never
  observed. Same family as the money-zero tripwire below.
- `[OPEN][FOLLOW-UP]` **No automated check binds the frontend field names to the
  backend ones.** The four v4.1 balance fields cross the seam by hand-typed name
  in three places (`domain.py` row keys, `test_hedge_api.py::_POSITION_KEYS`,
  `index.html` `p.xxx`); Review-2 verified all five keys character-by-character
  and the 2026-08-03 live smoke confirmed them end-to-end, but a future rename on
  either side would silently render `—` with every test still green.
- `[OPEN][FOLLOW-UP]` **Manual-restart logs land in a session scratchpad.** The
  2026-08-03 restart wrote stdout/stderr to a Claude session scratchpad path,
  which is temporary. Until the launchd service is repaired (see Live Risks),
  restart from an operator terminal so logs survive, or fix the LaunchAgent so
  they return to `~/Library/Logs/funding-hedging/`.
- `[OPEN][RESIDUAL]` `resolve_leg_from_query` writes `avg_price` / `quote_amt`
  without `COALESCE`, so a later `None` overwrites a known value. Unreachable
  today. Was to ride Task 2.
- `[OPEN][RESIDUAL]` Perp average price can read blank — upstream: Binance dropped
  quote/avgPrice from the UM POST result (2026-07-14), so figures only arrive via
  the order-detail GET. Renders as an em-dash, not a fabricated zero.
- `[OPEN][DEFERRED]` Three discarded-failure sites, by decision: `service.py:1141`,
  `:1632`, `live_hedge_executor.py:690-702`. Should these reach the `entries`
  timeline? Human decides. Audit: `archive/2026-07-unknown-not-zero-v1` file `71-`.
- `[OPEN][RESIDUAL]` `_rate_limit_stamp_pending` is in-process: a restart mid-stamp
  costs one failure count (pauses one early, fail-closed). Fix = a new column.
- `[OPEN][RESIDUAL]` The money-zero tripwire is a speed bump, not a proof: five
  evasions + `fee_amount` outside the money names. DEC-2026-07-30-001.
- `[OPEN][HARNESS]` ~41 completed stage dirs in `reports/agent-runs/`, vs §9.5.
  v2 findings: batch A merged; batch B + R3/R4 wait for a real problem, G1/G14
  OPEN by decision (Human 2026-07-31). Detail: archive `22-`.
- `[OPEN][HARNESS-FOLLOW-UP]` **O-A — handoff source SHA-256 boundary.** The
  accepted handoff contract needs one mechanical clarification: the source ends
  at the first line exactly equal to the complete `BOOKKEEPER_APPEND_ONLY`
  marker, and the source payload must not contain that exact marker line. Add a
  reference verification command in a separate Harness task; this does not
  invalidate archive `archive/2026-08-03-harness-task-handoff-evidence-v1`.
- `[OPEN][HARNESS-FOLLOW-UP]` **O-C — superseded unstarted dispatch.** Define a
  minimal record for a task packet that is prepared but never started and then
  replaced (for example, a provider quota change). The current Kimi-to-DeepSeek
  replacement is traceable and did not execute, so this is not a merge blocker.
- `[OPEN][HARNESS-FOLLOW-UP]` **O-D — review-closure field lines omitted.** The
  DeepSeek Review-1 receipt for `review-1-position-balance-display-v1-deepseek`
  carried its ACCEPT only as the Source Report conclusion and omitted the
  `评审结论:` / `问题记录:` / `修复要求:` field lines that `AGENTS.md` §7 requires
  inside the result block. Bookkeeper judged it a non-rejecting format deviation
  because the closure data was explicit and unambiguous in the same file, and
  the Review-2 dispatch now demands the three explicit lines. Decide whether the
  reviewer dispatch template should state them literally so the omission cannot
  recur. Not a merge blocker.

## Next Priority

- **No active stage.** `2026-08-03-hedge-status-account-refresh-v1` closed on
  2026-08-03 (see Last Completed). Its five deferred items are the O-1 / O-3 /
  O-6 / field-name-binding / restart-log entries in Open Follow-ups, plus the
  broken LaunchAgent in Live Risks; none blocks a new stage.
- F4 and the lifecycle Task 2 remain deliberately deferred; the Chinese task-card
  gap remains a separate low-scope follow-up.
- Nothing in the closed stage authorized deployment, Start-gate changes,
  credentials, or live operation, and none was performed. The one waived action
  was a Human-ordered service restart (see Live Risks `[NOTE][2026-08-03]`).

## Last Completed

- stage: `2026-08-03-hedge-status-account-refresh-v1`
- archive_ref: `archive/2026-08-03-hedge-status-account-refresh-v1`
  (delivery range `89103303..7f965f82`; v4.1 backend projection `65bdd81`
  (`claude_glm`) + frontend display `7f965f82` (Grok); DeepSeek Review-1 ACCEPT
  and Opus 5 Review-2 ACCEPT, both Bookkeeper-verified; `rework_count` 0)
- recorded_completed_at: `2026-08-03`
- scope delivered: one shared worker-only refresh cycle behind the ~60s tick, the
  manual 更新缓存 POST and the task-status hook; five per-source success clocks
  (`source_checked_at`); v4.1 display adjustments — the collateral-cap badge moved
  to the 借贷状态 / 资产 column, the positions 现货余额 column split into
  現货/杠杆 dual-account lines with their existing valuations, and the aggregate
  and PM clocks moved to their title positions.
- closing note: Human accepted after reading the Review-2 brief, authorized the
  merge, and deferred all seven Review-2 observations. The merge-day live smoke
  (restart + read-only GET) is recorded in the Review-2 handoff's verification
  block; it closed that review's named evidence gap by putting real account data
  through the four new fields for the first time.
- previous stage: `2026-08-03-harness-task-handoff-evidence-v1`
  (`archive/2026-08-03-harness-task-handoff-evidence-v1`, `0a0b952`)

## Update Rule

Record live incidents at once; remove resolved items. Over budget: evict resolved
first, then oldest, keeping a git reference.
