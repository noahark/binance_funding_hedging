# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-08-12)

- **Active stage: `2026-08-12-herdr-approved-handoff-v1`。** 本阶段只规划 Harness 的 Human 批准 Herdr 信息交接；尚未改动 Harness、启动 Herdr 会话、发送模型消息、部署或重启服务。当前等待 Human 启动已准备的 Planner packet：`reports/agent-runs/2026-08-12-herdr-approved-handoff-v1/herdr-approved-handoff-plan.dispatch.md`。该变更属于 HIGH_RISK Harness workflow contract，实施前必须完成独立跨 provider 的计划评审。

- 最近完成的历史仓位滑点口径修复已归档；本次未部署或重启服务。

- 上一 stage `2026-08-11-reverse-position-drift-v1` 已获 Human 最终验收并
  push 到 `origin/main`，完整阶段证据归档在
  `archive/2026-08-11-reverse-position-drift-v1`。JSTUSDT 型 reverse 持仓不再因现货
  free 为零长期误报；当前手动前台进程在交付提交后启动，已加载本修复，本次归档未重启
  服务。交付只改展示校验，不改变下单、借还、划转或闸门；`drift=false` 仍不是对账证明。

- 前一 stage `2026-08-10-cross-margin-flow-log-v1` 已归档；全仓杠杆流水使用本地缓存。

- 当前服务仍以 Human 手动前台进程运行；统一账户手动还款已最终验收，
  `APP_MARGIN_REPAY_ENABLED` 按 Human 决定保持开启。XLM 指定 5 与 INJ 全部还款各一笔成功；
  日常操作只用一个标签页，全额还款以刷新后负债为准。归档与操作限制见 Last Completed / Live
  Risks。实盘库数据自 2026-08-06 清理后从新起点累积（备份
  `data/*.sqlite3.bak-clean-20260806-120813`）。

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

- 挂账 follow-up：close_log 利息 ≈U（价格源注入 service 层）。
  （本地数量口径 X/Y/Z 已由 Human 2026-08-08 关闭：持仓表数量列以交易所实际持仓
  为主，读不到时红字提示 + drift 标记已兜底，维持现状不再整改。）

## Live Risks

- `[RESOLVED][LIVE-INCIDENT][2026-08-10]` **XLMUSDT reverse 平仓单腿成交，现货负债腿已由
  Human 人工收口。**
  任务 `840a11a5-b47e-4406-858f-4947934901bf` 于 10:30:54 CST 并发提交两腿：
  PAPI UM `reduceOnly SELL 100` 已 `FILLED`（order `22675869218`，均价 `0.16230`），
  PAPI Margin `BUY 100` 被币安明确拒绝 `-2019 Margin is insufficient`。10:35 CST
  只读快照确认 UM 已无
  XLMUSDT 仓位，而 XLM `cross_margin_free=95`、`cross_margin_borrowed=195.10900819`
  （约净空 `100.10900819 XLM`）；组合保证金 `total_available_balance_usdt=0`，虽
  USDT `cross_margin_free=229.09557812`。Human 11:00:10 CST 通过 XLM 资产卡提交 `amount=0`
  全额还款，11:01 快照确认 XLM 余额/可用/借款全为 `0`；按 Human 提供的现货
  `BUY 100 @ 0.1632` 补录 `hedge_open_cycle_close_log.id=5`，周期以 `manual_verify`
  于 11:00:11 CST 关闭，任务置 `done`。原始 attempt `60` / raw `169..171` 保持不变；
  补录前备份为 `data/hedge-open-tasks.sqlite3.bak-manual-xlm-close-20260810-110010`。

- `[OPEN][LIVE-RISK][2026-08-10]` **reverse 自动平仓仍可能因组合保证金口径再次单腿。**
  两腿非原子并发，合约腿不等待现货腿；close+reverse 预检仅以最长 5 分钟缓存可命中的
  逐资产 `crossMarginFree >= q×估价` 放行，未校验组合保证金 `totalAvailableBalance`，
  也未验证任一腿先成交后的中间态，故本地门通过不代表币安组合风控会接受现货买回。
  临时边界：修复前不要使用 reverse 自动平仓；如需处置，Human 在币安逐腿核对并人工
  收口。重开修复至少要使用能覆盖组合风控与单腿中间态的真实验收口径，不能继续把
  `crossMarginFree` 当成成交保证；任何代码修复仍需另行明确授权。

- `[OPEN][LIVE-OBSERVATION][2026-08-10]` **还款功能在双评审完成前已由 Human 开闸并做
  真实还款。** 本地审计确认 XLM 请求 5、实际 5、`succeeded`；INJ 请求 `0`（外发省略
  `amount`）、`succeeded`，且 00:40:19 本地已发布账户快照的
  `cross_margin_borrowed="0.0"`，仅一笔 INJ 请求、无错误。实际差异：INJ 的币安成功
  响应未提供官方响应模型列出的 `amount`，故 `repaid_amount=null`；这不影响本次全部
  还款成立，但本地审计不能证明实际偿还数量。临时口径：全额还款记录若
  `repaid_amount` 为空，只能结合币安账户/刷新后负债归零确认，不得从本地记录宣称精确
  数量。若以后出现 `success: true` 但完整刷新后负债仍非零，须重开并把“全部已偿还”文案
  改为以刷新结果为准。双评审已接受当前口径；Human 2026-08-10 最终决定闸门保持开启。

- `[OPEN][OBSERVATION][2026-08-10]` **还款未决锁不跨浏览器标签页共享。** 每个标签页只在
  启动时读取一次 localStorage 到内存；两个已打开的同源标签页可各生成新 UUID，对同一借款
  资产分别二次确认并提交。它不是系统自动重发，每笔仍须 Human 主动输入并确认，因此
  review-2 不阻塞交付。临时操作边界：还款时只保留一个页面，不在多标签页/多窗口并行操作。
  重开条件：出现自动化/定时提交路径，或 Human 实际需要多标签页/多设备并行还款。

- `[RESOLVED-BY-BLOCKING][2026-08-07]` **1000x 乘数合约两腿数量口径错配（资金安全）**。
  执行链两腿发同一个 `q_common`，但 1 张 1000x 合约 = 1000 个现货币：现货买 N 个、
  合约空 N 张 → 净裸空 999N。实盘库从未开过此类仓位，无实际损失。
  **止血（已实施）**：`create_task` 对 `symbol_match_type == multiplier_strip_alias`
  的 **open** 任务 fail-closed（`multiplier_contract_unsupported`）。
  **⚠️ 当前运行中服务的 close 放行 ≠ close 安全**：它仍会给两腿同一个
  `q_common`，自动平仓腿量同样错 1000 倍；真要处置这种仓位须人工去交易所平。
  2026-08-09 交付已通过双评审、合并 main、部署生效并经 TSTUSDT 实盘平仓验证（见 Last
  Completed）；close 侧建卡/dispatch 双判拦截已在运行中服务生效，但仅有离线 + 一笔实盘证据。
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

- `[OPEN][OPERATIONS][2026-08-03, updated 2026-08-09]` **launchd 无法托管，已 disable，
  改用手动前台模式。** 根因是 macOS TCC：launchd 启动的进程拿不到 `~/Desktop` 访问权限。
  2026-08-09 Human 给 `/bin/bash` 加了「完全磁盘访问」后 bash 能进 Desktop（退出码 126→1），
  但 `run-server.sh` 调的 python（`.venv/bin/python` → `/opt/homebrew/opt/python@3.11/bin/python3.11`）
  仍未授权，读 `.venv/pyvenv.cfg` 时 `Operation not permitted` → launchd 仍起不来。Human 决定
  **不逐个授权可执行文件**（homebrew python 一升级路径就变、TCC 失效，太脆弱），由 Bookkeeper
  执行 `launchctl disable + bootout gui/501/com.aoke.funding-hedging.server` 停掉 fail loop
  并防止 `RunAtLoad` 下次开机复发。**当前服务 = 手动前台进程**（如 PID 54099，2026-08-09 19:11
  启动，跑最新 main 代码），在 `127.0.0.1:8787`；重启必须手动 `scripts/run-server.sh`
  （`backend/config.py` 不自行解析 `.env`）。根治（想要重启自动起）：把项目移出 `~/Desktop`
  到非 TCC 保护目录；给 python 也授权不可取（脆弱）。诊断用 `scripts/service-control.py doctor`
  （只读），修复子命令需 `--confirm`。要恢复 launchd：`launchctl enable + bootstrap gui/501` 该 plist。
  **⚠️ `service-control.py status` 具有误导性**：`health 200` 来自手动进程、`commit` 字段读当前
  git HEAD 而非运行进程加载的代码版本——判断「服务最新」须以进程启动时间对比提交时间为准。

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

- `[OPEN][PRE-EXISTING][2026-08-11]` **小额统一账户资产卡可能连同还款回显一起被过滤。**
  `frontend/index.html` 先按「持有价值与净价值均低于 10 USDT」过滤整张资产卡，之后才
  生成还款成功、失败、未决或未知回显；因此借款已读为 0 且资产价值较小时，未决锁仍在
  浏览器状态中，但「查询结果 / 我已核对 / 再次刷新」等回显和操作入口可能随卡片消失。
  该顺序早于 2026-08-11 的资产卡/持仓表展示调整，**不是本次改动引入的回归**。
  临时边界：若还款后资产卡消失，不要换请求号重试，先到币安核对实际负债；仍按现有
  单标签页操作限制执行。重开条件：实际出现未决还款资产卡消失，或产品要求任何还款
  回显都不受小额卡片过滤影响。最小修复方向是让存在还款 pending/result 的资产绕过
  整卡过滤；证据锚点：`frontend/index.html` 的统一账户 `.filter(...)` 早于
  `renderRepayStatus(asset)`。

- `[OPEN][DOCUMENTATION][2026-08-11]` **reverse drift 的账户级归因边界（review-2 O-2）。**
  当前 `A=max(B-F-L,0)` 使用统一账户内该资产的整体验证值，不按策略周期分配负债、
  可用量或锁定量；同币 forward 与 reverse 同时活跃时可能保守误报，存在无关借款时
  也可能掩盖短缺。它只影响弱告警展示，不触发资金动作，本轮批准范围明确不做周期归因。
  后续在 `docs/api/public-market-contract.md` 补充该边界；若 Human 遇到 reverse 红字但
  币安核对一致，或需要同币双向并存运行，则重开评估。证据见本阶段 review-2 handoff O-2。

- `[OPEN][DOCUMENTATION][PRE-EXISTING][2026-08-11]` **forward drift 的既有假阳性契约缺口
  （review-2 O-4）。** `docs/api/public-market-contract.md` 尚未说明同资产借币负债净减
  `total_balance` 可造成 forward 假阳性；原始评审记录由提交 `bbeb130` 引入，早于本阶段
  base `7194876`，因此不阻塞本轮交付。后续与 O-2 一并补齐文档，不改变当前弱告警口径。

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
- `[OPEN][RESIDUAL]` **UM drain 可在 `cumulative_quote` 未知时把 FILLED 腿判为终态。**
  该路径会保留 `avg_price` 但缺 quote，导致该周期的合约均价与开/平滑点显示 `—`；这是
  fail-closed，不影响订单或持仓且不臆造数值。重开条件：出现真实历史周期命中该形态，或 Human
  决定统一 drain/inline 终态规则；届时应同批评估 quote 缺失时用 `avg_price × qty` 加权的口径。
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
  1. 1000x 腿量换算 —— 恢复乘数币能力仍须 Human 授权后单开一轮；
  2. launchd 已 disable、改手动前台模式（TCC 部分修复但 python 未授权；根治须移项目出 ~/Desktop）。
- Nothing open authorizes deployment, Start-gate changes, credentials, or live
  operation. Live actions follow the Live Risks gates above.

## Last Completed

- stage: `2026-08-12-hedge-slippage-spread-v1`
- archive_ref: `archive/2026-08-12-hedge-slippage-spread-v1`（tip
  `ad774315eb56e933ab14615c7a92e0b697f4e5e9`，完整 dispatch/handoff/status 与 Human Fast
  最终验收记录）
- delivery: `05d2ac9..f99795c`；`rework_count` 0；核心计算经跨 provider 计划评审、review-1、
  Sonnet 5 review-2 ACCEPT；O-2 文字与 JSTUSDT 单行补录由 Human 确认显示正常并以 Fast Direct
  免除新增双评审，批准提交/合并/推送。
- recorded_completed_at: `2026-08-12`
- outcome: 历史仓位开/平滑点按两腿真实成交数量加权均价的卖减买价差计算，卖价高于买价为正，
  四位百分比且不读 `est_price`；O-2 界面说明已同步；本地 JSTUSDT close-log id=6 在备份后更正为
  `0.2316/-0.2192`。前端自检与定向后端 131 项通过，数据库及备份完整性通过。
- follow-ups: UM drain 缺 quote 的 O-1/O-4 保留在 Open Follow-ups；该形态 fail-closed 显示
  `—`，不臆造数值。未部署、未重启服务。
- previous stage: `2026-08-11-reverse-position-drift-v1` —— 统一账户 reverse 持仓弱告警修复；
  归档 `archive/2026-08-11-reverse-position-drift-v1`（tip `66135ce8e6529f8f2e13fd57cdaf7f7053a1b81c`）。
- previous stage: `2026-08-10-cross-margin-flow-log-v1` —— 全仓杠杆流水本地缓存；归档
  `archive/2026-08-10-cross-margin-flow-log-v1`。
- previous stage: `2026-08-10-local-net-position-v1` —— 本地净持仓 open−close；归档
  `archive/2026-08-10-local-net-position-v1`。
- previous stage: `2026-08-09-pm-margin-repay-v1` —— 统一账户借款资产卡手动还款，XLM 5 与
  INJ 全部还款实盘成功；归档 `archive/2026-08-09-pm-margin-repay-v1`
  （`ee0d532..5a81bdc`，archive commit `ee927a1`）。
- previous stage: `2026-08-09-close-task-preflight-simplification-v1` —— 平仓两段式与派发前
  安全门，TSTUSDT 实盘闭环；归档
  `archive/2026-08-09-close-task-preflight-simplification-v1`（`dc356cd..e5f83f1`）。
- previous stage: `2026-08-06-asset-transfer-live-v1` —— 资产互转真实划转打通，实盘三笔
  `succeeded`，合并 main（`bb47d02..bbe81b0`）。归档 `archive/2026-08-06-asset-transfer-live-v1`。
- previous stage: `2026-08-06-hedge-order-close-validation` —— 下单/平仓链路实盘验收
  通过，合并 main（`f153cdc..64f0051`）。归档 `archive/2026-08-06-hedge-order-close-validation`。
- previous stage: `2026-08-04-dual-ledger-flow-log-v1` —— 双栏流水日志。归档
  `archive/2026-08-04-dual-ledger-flow-log-v1`。
- previous stage: `2026-08-03-hedge-status-account-refresh-v1` —— 账户刷新周期 +
  `source_checked_at` + 持仓双账户显示。归档
  `archive/2026-08-03-hedge-status-account-refresh-v1`。
- previous stage: `2026-08-03-harness-task-handoff-evidence-v1`
  (`archive/2026-08-03-harness-task-handoff-evidence-v1`, `0a0b952`)
- 更早的完结记录见 git 历史与 archive branches/tags。

## Update Rule

Record live incidents at once; remove resolved items. Completed work leaves its
trace in git history and archive references, not in narratives here — commit
messages must state the one-line outcome so history stays traceable, and this
file records only live risks, open follow-ups, and pointers. Over budget: evict
resolved first, then oldest, keeping a git reference.
