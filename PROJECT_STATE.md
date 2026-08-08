# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-08-08)

- **No active stage.** `ACTIVE.json` 为 `null`。服务以 Human 手动前台进程运行
  （2026-08-08 00:13 重启，已载入全部改动；launchd 损坏不修，见 Live Risks）。
  测试基线 **1601 passed + self-check EXIT=0**。实盘库数据自 2026-08-06 清理后
  从新起点累积（备份 `data/*.sqlite3.bak-clean-20260806-120813`）。

- **[2026-08-07 已收口] 展示层诚实性整族修复**（Human 直接驱动，无 stage；交付
  `d7057e3`/`dd0b3e3`/`184d76e`/`44ab175` 等，细节见 git 历史）：
  单腿敞口判定（补裸空 + 部分失衡，差额 >1% 容差）、drift 账户口径（两账户求和）、
  终态任务结算文案（`order_state_unknown_final`）、F4 交易所无仓假声明
  （`private_account.unavailable_sources` 契约 + 标题红字）。
  **可复用判断**：修「假声明」要区分「不知道」与「知道没有」，缺省一侧永远倒向
  「已知」（本轮三次踩到同一形状）。
  **F4 验证口径（勿误读）**：正常侧（读得到时红字不出现）已经 2026-08-08 实盘
  验证；「读不到时红字出现」一侧未经实盘触发（需真实 UM 单源故障），目前仅由
  self-check 的 5 项断言覆盖。

- **[2026-08-07 已收口] 现货腿身份统一 + SPOT_SYMBOL_MAP 纯表**（Human 直接驱动，
  无 stage；交付 `ee35b5e..be3f583` + `8ee6d3c`，细节见 git 历史）：
  现货腿身份是任务第一等属性——建任务时由静态表（71 条 = 65 bStock + 6 乘数）
  解析一次并固化，下单/平单/展示三环只读不算；全部字符串猜测规则已删除
  （fail-closed：未收录即无现货腿）。实盘闭环：SNXXUSDT 开平仓身份继承无误。
  维护：`scripts/check-spot-symbol-map.py --verify/--emit`。

- **[2026-08-07 已收口] Q4 统一账户可转出额**：最终形态 = 前端零请求沿用快照
  （DEC-2026-08-07-004）——USDT 用 `total_available_balance_usdt` 标签「可转」，
  其余币用 `cross_margin_free` 标签「可用」，措辞跟数据来源走；**严禁把 USDT 的
  算法推广到其他币**（抵押品折算率约束，self-check 有断言守）。
  `GET /api/private-account/max-withdraw` 端点留在后端但无前端消费者，已移出前端
  同源白名单；要精确的 per-asset 可转出额时它是唯一数据源。

- **[领域事实][Human 2026-08-07]** **bStock 类币没有借币市场，故不存在负费率开单。**
  负费率开单（reverse）= 借币卖现货 + 开多合约，借不到就做不了这条策略。
  **推论**：一切「reverse + bStock」的代码路径都不可达，那里的 fail-closed 不是
  缺陷而是正确行为；`decide_spot_route` 对 reverse 固定走 `papi_margin` 也因此
  自洽。判断影响面前先套这条（曾有模型缺了它误报 Live Risk）。

- **[2026-08-08] 文档追平 + Harness 两条规则**（Human 直接驱动）：docs/ 活文档
  一次性追平到 2026-08-08；AGENTS.md 新增「任何交付收口必须同步 docs 活文档」；
  Update Rule 新增「完结留痕在 git 不进本文」。见 DEC-2026-08-08-001 与 git 历史。

- **[2026-08-08 已收口] regular_spot 开仓自动划转 USDT + dispatch 路由核验**（Human
  直接驱动，无 stage；交付 `fb59c38..c837722`，细节见 git 历史 +
  `docs/planning/open-spot-usdt-transfer-2026-08-08.review-request.md`）：
  所有 USDT 默认放统一账户当保证金；`open+forward+regular_spot` 建仓时 `create_task`
  内一次性划转 `truncate(q×N×price×1.03)` USDT 到现货，失败不建卡 + 前端弹窗
  （`open_spot_transfer_failed`）；preflight 对 regular_spot forward 余额门放行
  （不校验、不缓冲）。**dispatch 下单前核验**：`fresh=regular_spot` 时建卡固化的
  `frozen route` 必须也是 `regular_spot`（即已备款），否则暂停不发单防裸空——覆盖
  路由变化（建卡 PAPI→下单 regular_spot）与 snapshot None 建卡后恢复 regular_spot 两
  场景；`frozen=regular_spot` 即"已划转备款"的间接证据，故无需持久化 tranId。开完不
  自动回流，残余 USDT 人工收尾。实盘验证 TSTUSDT 两腿成交（划转 15.77→现货买 1000 +
  合约空 1000→done，残余 ~0.81 人工收尾）。
  **Human 决断（勿议）**：不查统一账户余额（前端/人工已校验）、不做幂等/tranId/恢复
  链、不自动回流、本轮不做前端防重——均人工收尾。
  **review**：codex 预提交 review1 `ACCEPT` + Human 特批本次归档。
  **活文档**：review-request 已入库 docs/planning；PRD/架构/API 公共契约未改（划转为
  create_task 内部行为，不涉公共市场契约）。

- 挂账 follow-up：本地数量口径（X/Y/Z 方案待定）、close_log 利息 ≈U（价格源注入
  service 层）。

## Live Risks

- `[RESOLVED-BY-BLOCKING][2026-08-07]` **1000x 乘数合约两腿数量口径错配（资金安全）**。
  执行链两腿发同一个 `q_common`，但 1 张 1000x 合约 = 1000 个现货币：现货买 N 个、
  合约空 N 张 → 净裸空 999N。实盘库从未开过此类仓位，无实际损失。
  **止血（已实施）**：`create_task` 对 `symbol_match_type == multiplier_strip_alias`
  的 **open** 任务 fail-closed（`multiplier_contract_unsupported`）。
  **⚠️ close 放行 ≠ close 安全**：close 走同一个 `compute_preflight`、同样两腿一个
  `q_common`，自动平仓腿量同样错 1000 倍；放行只是不再添堵，真要处置这种仓位须
  人工去交易所平。
  **换算改造（资金路径）见 Open Follow-ups 的「1000x 腿量换算」条，须 Human 授权。**
  另注意：持仓表 `single_leg_exposure` 对乘数币因量纲不同会误报，换算落地时跟着改。

- `[OPEN][ACCEPTED][2026-08-07]` **划转端点默认即可真实动钱，不受 `APP_HEDGE_EXECUTOR`
  控制（review-1 R1，Human 决定接受现状，DEC-2026-08-07-001）**。事实：
  `POST /api/asset-transfer`（`server.py` `_build_asset_transfer_client`）启用条件
  仅为 `config.offline=False` + `binance_hedge_api_key` 非空；无独立开关；对照
  hedge 链路 `hedge_executor` 默认 `disabled` 为系统默认安全态且有启动警示（B-4
  事故教训）。启动有提示（启用/未启用两分支打印，纯可见性，非闸门）。可能影响：
  进程以 disabled/离线启动（降级/测试）时，该端点是当时唯一会真实划转的通路；
  `confirm: true` 是唯一门槛，任何能触达 `127.0.0.1:8787` 的本地进程可发起真实
  资金转移。接受理由：Human 2026-08-07 决定接受现状（生产实际以 live 运行、
  start_gate 常开为既定前提）。临时限制/观察方式：任何非离线启动均假定划转端点
  可用；实盘试划转须 Human 在场小额执行；全量划转落 `data/asset-transfer.sqlite3`
  审计表可事后核查。后续复看条件：服务以 disabled/离线模式启动前须先处置本
  暴露面；或 Human 决定加开关/警示。
  **仅验证 `unified→spot` 成功路径**；`spot→unified`/`failed`/`unknown` 三路径
  仅离线证据。

- `[BY-DESIGN]` **Standing operating premise: the Start gate is kept ON and the
  system runs live.** Human decided 2026-08-03 to leave it open permanently, so
  this is the intended steady state, not an open risk — do not file it as one
  again. Verified at the 2026-08-03 restart:
  `hedge_open_execution_mode mode=live start_gate=true` and
  `borrow_execution_mode mode=live execution_owner=true`, unchanged across
  restarts. **What follows from it, and still holds:** a task moved to `running`
  can send real orders immediately; close is delivered and `close_gate` defaults
  on (SNXXUSDT 全平 2026-08-07). No agent may create orders,
  touch credentials, control the service, or write the live task DB; an
  authorized read-only check must precede any live action.

- `[OPEN][OPERATIONS][2026-08-03]` **The launchd service is broken and has been
  failing in a tight loop** (unrepaired by Human decision 2026-08-03).
  `com.aoke.funding-hedging.server` reports `last exit code = 126`; root cause
  (2026-08-07): launchd-spawned bash cannot get TCC permission for `~/Desktop`
  (`scripts/run-server.sh: Operation not permitted` + `getcwd` failure).
  The service on `127.0.0.1:8787` is a manually started foreground process in
  the operator's terminal, so killing it does NOT hand over to launchd — the
  restart must be manual (`scripts/run-server.sh`, required because
  `backend/config.py` never parses `.env` itself). Diagnose with
  `scripts/service-control.py doctor` (read-only); every repair subcommand needs
  `--confirm`.
  **⚠️ `service-control.py status` 具有误导性**：它报的 `health 200` 来自手动
  进程、`commit` 字段读的是当前 git HEAD 而非运行中进程加载的代码版本——据此
  判断「服务已是最新代码」会出错，须以进程启动时间对比提交时间为准。

- `[NOTE][2026-08-03]` The "no agent may control the service" rule was waived
  once, explicitly and narrowly: Human directly ordered a restart (read-only
  smoke only, no order/borrow/transfer/credential/gate change). The waiver was
  for that one restart and does not generalize.

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
  `docs/api/public-market-contract.md`; full evidence:
  `archive/2026-08-02-spot-order-routing-cap-display-v1`.
  **Display-side operating premise:** the snapshot service uses the same hedge
  API key to read the platform collateral-cap list on its existing refresh
  cadence. A missing, revoked, or IP-rejected key makes the page show
  「抵押额度未知」; its cache never feeds the order preflight.

- `[NOTE][2026-08-07]` **drift 是弱告警，不是对账**：统一账户侧取
  `totalWalletBalance`，含 UM/CM 合约子钱包（同资产被当作合约保证金占用的部分
  也计入「持有」）。所以「有报警必真少」成立，「无报警即相符」**不成立**——
  别拿它当对账工具。

- `[RESOLVED][OPERATIONS][2026-08-05]` Live DB schema 曾由服务重启自动迁移
  （幂等 additive DDL，无数据变化；教训：迁移前应先备份）。全过程与证据：
  `archive/2026-08-hedge-position-cycle-v1` 相关 handoff（见 git 历史）。

## Operating Limits (Task 3, merged 2026-08-02)

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

## Open Follow-ups

- `[OPEN][NEEDS-HUMAN-AUTHORIZATION][2026-08-07]` **1000x 腿量换算——未做的资金路径**。
  P0 止血只是把 6 个乘数币（BONK/FLOKI/LUNC/PEPE/SHIB/XEC）挡在门外（见 Live Risks
  同日条目），**换算本身一行未写**。恢复这 6 个币的对冲能力必须改下单数量这条真金
  白银的路径，故须 Human 明确授权后单开一轮，不得顺手夹带。
  **必须一次改齐的八处**（改一半比不改更危险——半套换算会造出一个「看起来对、
  实际错」的敞口，而现在至少是显式拒绝）：
  1. `backend/services/live_hedge_executor.py:873` `send_qty = ctx.q_common` ——
     两腿共用一个数量。现货腿需 ×1000（或合约腿 ÷1000），方向别搞反：合约 1 张 =
     1000 个现货币，故**现货腿的量 = 合约张数 × 1000**。
  2. `backend/services/hedge_preflight_provider.py:832`
     `est_price = self._read_est_price(spot_symbol)` —— 取的是**现货**价。合约腿的
     minNotional 校验与 UM 保证金估算需要合约价（= 现货价 × 1000），两腿不能共用一个价。
  3. `backend/hedge_open_tasks/domain.py:1183` `q_common = floor_to_grid(single_amount, grid)`
     —— `grid = lcm(spot_step, perp_step)` 把两腿的 stepSize 当同一量纲取最小公倍数，
     换算后这个 lcm 不再成立，两腿的取整格必须各算各的。
  4. `backend/hedge_open_tasks/domain.py:1267/1273` `required` 的两个方向分支 ——
     forward 是 `q_common * target_n * est_price`（USDT），reverse 是
     `q_common * target_n`（**币的数量**）。reverse 分支尤其危险：若 `q_common` 是
     合约张数，required 会少算 1000 倍，余额检查通过但实际卖出需要 1000 倍的币。
  5. `backend/hedge_open_tasks/domain.py:1952` 持仓表 `single_leg_exposure` 的
     `abs(spot_qty - perp_qty)` —— 两腿记账量纲不同（个 vs 张），换算前它对乘数币
     必然误报，换算后要按同一量纲比。代码注释已留指针。
  6. **`backend/hedge_open_tasks/domain.py:1001-1027` `_check_common_quantity`**
     （review-1 kimi 2026-08-07 指出，此前清单遗漏）——它是 `compute_preflight`
     中间调用的**独立 helper**，极易被「preflight 一起改了」带过。两处都错：
     (a) `for filters in (spot_filters, perp_filters)` 拿**同一个** `q_common` 去比
     两腿各自的 min/max qty；(b) `notional = q_common * est_price` 用**同一个**数量
     和**现货**价算出一个 notional，再拿它比两腿各自的 minNotional。
     修法：每腿的数量边界和 minNotional 各按各的量纲与价格查。
  7. `backend/hedge_open_tasks/domain.py:1191-1202` `snapshot_record` 的审计指纹
     （`spot_min_qty`/`perp_min_qty`/`grid`/`est_price`）——**不影响计算正确性**，
     但这份不可变记录当前隐含「两腿同量纲」，换算后不更新会让事后审计读错。
  8. `backend/hedge_open_tasks/domain.py:1265` `base = base_asset(coin)` ——
     只剥 USDT 后缀得 `1000BONK`，而 `snapshot.balances` 的键是币安返回的真实资产名
     `BONK`，`balances.get(base, 0)` 查不到即 `available=0` → 恒判余额不足。
     走到这一行的是 `open + reverse`（负费率开仓，借币卖现货，papi_margin）。
     修法：改用 `resolve_spot_identity(coin)[1]`（纯查表零 IO，与建任务时固化身份同源）。
     **当前被 P0 拦截掩盖**：乘数币开不了 open，所以这一行现在走不到；移除 P0 拦截的
     同一轮必须连它一起修，否则换算做对了、余额检查仍恒拒。
     （bStock 也命中这一行，但**无借币市场故不存在负费率开单**，对它而言 fail-closed
     恰是正确行为——见 Current Status 的领域事实条目。）

  **行号校验（2026-08-07 核对，全部命中）**：这份清单的价值全在行号准确。改动
  `domain.py` 后行号会漂——下轮动手前先跑一遍校验，别照着漂移的行号改：
  ```
  python3 - <<'EOF'
  for path, line, needle in [
      ("backend/services/live_hedge_executor.py", 873, "send_qty = ctx.q_common"),
      ("backend/services/hedge_preflight_provider.py", 832, "est_price = self._read_est_price"),
      ("backend/hedge_open_tasks/domain.py", 1183, "q_common = floor_to_grid"),
      ("backend/hedge_open_tasks/domain.py", 1267, "required = q_common * target_n * snapshot.est_price"),
      ("backend/hedge_open_tasks/domain.py", 1273, "required = q_common * target_n"),
      ("backend/hedge_open_tasks/domain.py", 1952, "abs(spot_qty - perp_qty)"),
      ("backend/hedge_open_tasks/domain.py", 1001, "def _check_common_quantity"),
      ("backend/hedge_open_tasks/domain.py", 1195, '"spot_min_qty"'),
      ("backend/hedge_open_tasks/domain.py", 1265, "base = base_asset(coin)"),
  ]:
      lines = open(path, encoding="utf-8").read().split("\n")
      hit = needle in (lines[line-1] if line <= len(lines) else "")
      print(("OK  " if hit else "DRIFT ") + f"{path}:{line}",
            "" if hit else [i+1 for i,l in enumerate(lines) if needle in l])
  EOF
  ```
  **改完要一并移除**：`service.py:807` 的 `multiplier_contract_unsupported` 拦截
  + `test_hedge_service.py` 的两条拦截测试 + `test_hedge_cycle_close.py` 的
  `_allow_multiplier_open` monkeypatch（三处调用）。
  **验收不能只靠单测**：这是量纲错误，单测很容易两边用同一个错误假设而全绿。
  建议先用最小额度实盘开一笔再立刻平掉，核对交易所两腿的**实际持仓数量**是否对平
  （而非只看系统自己的记账）。
  **乘数来源**：币安不在 exchangeInfo 里给显式 multiplier 字段，倍率隐含在 symbol
  前缀里，只能由 `SPOT_SYMBOL_MAP` 显式携带（当前表只存 symbol 映射，不存倍率，
  需要扩表）。当前 6 条恰好全是 1000 倍，但**别把倍率写死成常量**：币安存在过
  `1000000` 前缀（`1000000MOG`——d717595 的 `base[4:]` 正是在它上面剥成 `000MOG` 的），
  倍率应随表逐条声明，新增条目时由 `scripts/check-spot-symbol-map.py` 一起校验。

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
- `[RESOLVED][OPERATIONS][2026-08-05]` **COOKIEUSDT 平仓单腿事故**（已修复并实盘
  验证）：forward close 现货 SELL 被路由误导到普通现货账户而币在统一账户 → 单腿
  遗留。修复链含 close 固定账户路由 + 万向划转补足 + close 完成判定重构。
  **持仓表口径决策（Human 2026-08）仍生效**：只显示「未平仓周期」。全过程：
  `archive/2026-08-hedge-position-cycle-v1` 相关证据（见 git 历史）。
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
  because the closure data was explicit and unambiguous in the same file, and the
  Review-2 dispatch now demands the three explicit lines. Decide whether the
  reviewer dispatch template should state them literally so the omission cannot
  recur. Not a merge blocker.

## Next Priority

- **No active stage.** Current priorities (detail in the sections above):
  1. 1000x 腿量换算 —— 唯一涉及资金路径的待办，须 Human 授权后单开一轮；
  2. launchd 损坏 —— Human 自 2026-08-03 决定不修（机器重启服务不会自动起来）；
  3. 本地数量口径 X/Y/Z 方案 —— 待 Human 定。
- Nothing open authorizes deployment, Start-gate changes, credentials, or live
  operation. Live actions follow the Live Risks gates above.

## Last Completed

- stage: `2026-08-06-asset-transfer-live-v1`
- archive_ref: `archive/2026-08-06-asset-transfer-live-v1`
  (delivery range `bb47d02..bbe81b0` + 各轮封存；T1/T2 `rework_count` 各 1；
  review-1 deepseek 兼任、无 review-2，均 Human 越门)
- recorded_completed_at: `2026-08-07`
- outcome: 资产互转真实划转前后端打通，实盘首批三笔真实划转 `succeeded`
  （1+50+50 USDT 带交易所流水号）；Human 实盘验收通过并授权合并推送。
- follow-ups: 见 Live Risks R1 条与 Open Follow-ups（R3 `pending` 卡死不修、
  仅 `unified→spot` 成功路径有实盘证据）。
- previous stage: `2026-08-06-hedge-order-close-validation` —— 下单/平仓链路实盘验收
  通过，合并 main（`f153cdc..64f0051`）。归档 `archive/2026-08-06-hedge-order-close-validation`。
- previous stage: `2026-08-04-dual-ledger-flow-log-v1` —— 双栏流水日志。归档
  `archive/2026-08-04-dual-ledger-flow-log-v1`。
- previous stage: `2026-08-03-hedge-status-account-refresh-v1` —— 账户刷新周期 +
  `source_checked_at` + 持仓双账户显示。归档
  `archive/2026-08-03-hedge-status-account-refresh-v1`。
- previous stage: `2026-08-03-harness-task-handoff-evidence-v1`
  (`archive/2026-08-03-harness-task-handoff-evidence-v1`, `0a0b952`)
- 更早的完结记录见 git 历史与 `git branch -a | grep archive/`（共 8 分支 + 9 tag）。

## Update Rule

Record live incidents at once; remove resolved items. Completed work leaves its
trace in git history and archive references, not in narratives here — commit
messages must state the one-line outcome so history stays traceable, and this
file records only live risks, open follow-ups, and pointers. Over budget: evict
resolved first, then oldest, keeping a git reference.
