# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-08-27)

- **[SECURITY][2026-08-27] 云端访问边界：一个进程只加载一份 `.env` 和一组页面登录凭证。**
  `APP_UI_USERNAME` + `APP_UI_PASSWORD` 使用标准库 HTTP Basic 保护静态页面和全部业务 API；
  `/healthz`、`/readyz` 仅供云平台探活，保持无认证。非回环监听缺任一凭证即拒绝启动；公网部署
  必须由反向代理终止 HTTPS，二级域名、证书、限频和进程/数据目录隔离均由部署层承担。应用不提供
  用户库、注册、找回密码、角色或同进程账号切换。

- **[DEPLOYMENT][2026-08-27] AWS 日本节点 `18.182.23.47` 已部署提交 `3487820`。**
  Amazon Linux 2 宿主通过 Docker/systemd 运行 Python 3.11 镜像；服务 `active` + `enabled`，
  `/healthz`、`/readyz` 均为 200。部署身份固定为 `env_aoke`：root:root `0600` 配置位于
  `/etc/funding-hedging/env_aoke`，独立数据位于 `/var/lib/funding-hedging/env_aoke/data`；后续每台
  机器仍只运行一个具名配置。2026-08-27 已在本地停服后迁移完整 `.env` 和 `data/`，5 个主库
  `quick_check=ok`，10 个关键表行数逐项一致，云端私有账户读取 `verified=true`。借币、开/平仓执行器
  和还款仍强制关闭；资产划转凭据已存在，因此 localhost 上的确认式划转接口具备实盘能力。
  `aoke.kengbi.pro` 的 Caddy/Let's Encrypt 配置和证书保留，但因当前 UI 密码强度不足，公网代理已
  停止并取消开机启动；更换强密码并取得 Human 明确授权前不得恢复。8787 始终只绑定
  `127.0.0.1`。临时部署包和临时凭据副本已从本机及服务器 `/tmp` 清除。

- **本机服务已于 2026-08-27 停止**，`127.0.0.1:8787` 无监听；后续运行、开发和验证转到
  AWS `env_aoke` 实例。本地 `.env` 保留作 Human 授权的源配置，权限已收紧为 `0600`；不得再次
  启动本机实例与云端实例同时拥有执行权。

- **实盘库数据自 `2026-08-06` 清理后从新起点累积**，备份
  `data/*.sqlite3.bak-clean-20260806-120813`。做任何跨期统计前先套这条。

- **[领域事实][Human 2026-08-07]** **bStock 类币没有借币市场，故不存在负费率开单。**
  负费率开单（reverse）= 借币卖现货 + 开多合约，借不到就做不了这条策略。
  **推论**：一切「reverse + bStock」的代码路径都不可达，那里的 fail-closed 不是
  缺陷而是正确行为；`decide_spot_route` 对 reverse 固定走 `papi_margin` 也因此
  自洽。判断影响面前先套这条（曾有模型缺了它误报 Live Risk）。

- **已按 Update Rule 驱逐 `2026-08-07`..`2026-08-21` 的 15 条交付叙事**（完成工作的痕迹留在
  git 与 commit message，这里只放活风险、未决项和指针）。完整原文
  `git show 046fff5:PROJECT_STATE.md`。**驱逐时提取出的仍然生效的约束保留在下方 Evicted 段。**

## Live Risks

- `[OPEN][ACCEPTED][2026-08-21]` **收益曲线的滑点已统一到 close-log 口径，代价是成本在时间轴上
  前移，最长实测 8 天。**
  背景：在持仓周期原按 `attempt` 逐笔配对、已平仓周期走 `close-log` 周期汇总，两套粒度导致
  周期一平仓、同一段历史就在曲线上重排（TSTUSDT `08-11` 五笔开仓塌缩到周期起点）。`f3fe3ba`
  统一到 close-log 口径：均价走 `cycle_leg_basis` 同一算法，数量也照抄其取法（open 取合约腿、
  close 取现货腿），新函数 `store.list_open_cycle_slippage_basis`。
  实测依据：10 个已平仓周期中，新算法与 `close_log` 现有口径 **9 个精确相等（差 0.0000）**，
  唯一不等的 `XLMUSDT` 是 close-log 侧脏数据（见下条）；12 个在持仓周期中 **10 个金额分文不变**，
  变化只在两个敞口币（`INJ -0.0530`、`TST +1.6736`）。腿的筛选条件同步照抄
  `cumulative_base_qty > 0`，不再按 `terminal` 过滤，顺带修掉正在部分成交的腿被漏计。
  **已知失真（Human `2026-08-21` 明示接受，不修）：**
  ① **成本前移**：整周期一个数挂在周期开仓时刻。TSTUSDT 14 笔跨 `08-11..08-19`（8 天）全挂
  `08-11`，XVGUSDT 12 笔跨 7 天全挂 `08-06`。**末值/总额恒准，中间任一时点的曲线值偏高**；
  持仓越久、加仓越多越严重。
  ② **部分平仓时点位后移**：在持仓周期的 close 段挂「该周期最后一笔平仓腿」时刻，每新平一次
  就整体后移。已平仓周期锚 `closed_at_us`，实测两者差 0.5–1.4 秒（桶 1 小时，不跨桶），
  唯 `XLMUSDT` 差 1757 秒且跨整点。
  ③ **两腿量不等段计入但失真**：加权均价推出的价差不对应单次真实成交，仍按 close-log 口径
  计入（不计入就与历史仓位页分家），新增 `slippage_unbalanced_count` 计数 + 前端脚注明示。
  close-log 只固化开仓两腿量，其平仓腿失衡无从判断、不计数。
  ④ **早于现货流水入库起点的点净收益偏高**：现货手续费与滑点那时尚未入库。实测
  `spot_flow_start_ms = 08-09 20:51`，受影响 **22/92 点**（曲线左侧 24%），前端 `partial=1` 标记。
  ⑤ **曲线不存快照、每次全量现算**：数据源一变（补录、脏数据修复、手续费回补）历史即重画。
  `2026-08-21` 人工补录 TST 500 后，`08-11` 那一刻凭空多出 `+0.93` 即为实例。
  影响：仅展示层，不影响下单与资金安全。`slippage_incomplete_count`（当前 4 笔，即今早四个
  半平仓币的 close 段）与 `slippage_unbalanced_count`（当前 2 段）均只驱动脚注、**不遮蔽净收益**；
  遮蔽只发生在数据源读失败或缺行情价时。
  改进方案已评估但 Human 决定暂不做，见 Open Follow-ups「按任务卡分组」。
  重开条件：出现单张任务卡成交跨度显著变长（当前 55 张卡全部 ≤1 小时），或曲线失真造成实际误判。

- `[OPEN][MONEY][MANUAL][2026-08-21 12:00 CST]` **TSTUSDT 开仓敞口由 Human 手动补仓 + 人工补录
  账本收口——这是一次绕过系统下单链的生产数据写入，必须留痕可追。**
  事实：TST 原为现货 `7000` / 合约 `-6500`，裸多 `500`（≈7.51 U）。Human 于币安手动做空 500，
  订单 `1974358402`，成交 `500 @ 0.015060`、成交额 `7.53 USDT`、手续费 `0.003765 USDT`，
  `12:00:54 CST`。成交明细经 `GET /papi/v1/um/userTrades` 只读核对，非系统下单。
  账本补录：新建**独立任务卡** `3199dff1`（不挂现有自动卡，避免那张卡的 attempt 数与实际执行
  不符）+ attempt `149`（`pair_outcome=single_leg`，如实反映单腿）+ 一条 perp 腿
  （`terminal=1`、`exchange_status=FILLED`、四列手续费直接填入，故回补引擎与结算流程都不会再
  触碰它）。`hedge_open_log` 写入 `kind=manual_backfill` 留痕（含订单号、成交明细、授权人、
  备份路径）。备份：`scratchpad/hedge-open-tasks.BACKUP-20260821-120337.sqlite3`。
  验证：持仓表 `7000 / -7000`、`single_leg_exposure=false`；合约均价 `0.017900` 与币安自报
  `um_entry_price=0.0179003` **独立吻合（差 ≈0.0024 U）**；曲线滑点 `+1.6208 → +0.2672`、
  净收益 `+3.5597 → +2.2634`、失衡段 `3 → 2`。数据库不在版本控制内，无代码变更，无需重启。
  **残留问题**：补录的合约腿单独成卡、卡内无现货腿，而对应的现货 500 在另一张已删除卡
  `be355ffd`（attempt 142，合约腿 `REJECTED -2019`）内——**按周期汇总能配上，若将来改按任务卡
  分组则配不上、会算不出**（实测差 `0.32`）。改按卡分组前须先把这条腿改挂到 `be355ffd`。
  重开条件：TST 平仓收口，或补录数据被发现与币安实际不符。

- `[OPEN][DATA-LOSS][2026-08-21]` **合约成交手续费一旦漏写且超过 7 天即永久缺失，该币手续费栏
  终身显示 `—`。**
  事实：币安 `GET /papi/v1/um/userTrades` 无 `orderId` 参数、只能按时间窗查，且**跨度硬上限
  7 天**（`fee_fetcher.um_window_clamped_7d`）。TSTUSDT 14 条开仓合约腿中有 **1 条**缺手续费：
  订单 `1950618349`，`500` 个、`11.555 U`、`2026-08-11 01:13:51 CST`，距今 10 天，已不可回补。
  手续费成本按 fail-closed 口径聚合（任一腿未知 → 整体 `trading_fee_incomplete=true`、
  `trading_fee_usdt=null`），故 TST 整张卡的手续费栏显示 `—` 而非一个少算的数——**这是正确
  行为，不是缺陷**。其余 13 条合约腿与全部 14 条现货腿手续费均在库。
  影响：仅持仓表手续费列；曲线的手续费线走币安账单流水（`um_income_rows` /
  `margin_capital_flow_rows`），不受此影响。正常下单路径手续费是终态实时写入的，只有漏写才
  依赖回补。
  唯一出路：从币安账单人工查得该单手续费后按 `manual_backfill` 方式补填。
  重开条件：补填完成，或再次出现新的超窗缺口。

- `[OPEN][LIVE][MONEY][2026-08-21 09:35 CST]` **四个反向持仓平仓任务因统一账户真实可用余额不足形成单腿敞口。**
  `INJ/WLD/JST/SNX` 四个 `close + reverse + smooth` 任务（attempt `145..148`）均在第一轮
  同时提交两腿后出现：现货 `BUY /papi/v1/margin/order` 被币安 `-2019 Margin is
  insufficient` 拒绝，合约 `SELL /papi/v1/um/order`（`reduceOnly=true`）分别成交
  `2 INJ / 20 WLD / 100 JST / 50 SNX`；任务均以 `insufficient_margin` 暂停、worker 已退出，
  但现货负债未买回，现有反向对冲量因此分别少了上述数量。`09:44 CST` 只读快照仍显示四项
  `single_leg_exposure=true`：INJ 借款本金 `8.00109129` 对 UM 多仓 `4`，WLD `60` 对 `40`，
  JST `200` 对 `100`，SNX `50.10709571` 对 `0`（另有各币未还利息）。
  根因有三层：① 前端 `requestHedgeCloseConfirm` 的余额提前拦截只在 `direction=forward`
  分支执行，反向平仓没有按预计买入额检查统一账户 USDT；② 后端反向平仓预检虽然存在，
  `HedgePreflightProvider._read_balances` / `compute_preflight` 却用 USDT
  `crossMarginFree`，没有用 PM 账户级 `totalAvailableBalance`。事后同一缓存快照为
  `crossMarginFree=117.29255906 U`、`totalAvailableBalance=4.47625223 U`，前者会误放行，
  后者才反映账户可用于新交易的余额；③ smooth close 只在 `09:30` Start 时同步备料并冻结
  `q_common/preflight_snapshot`，随后等待完整 5 分钟，四笔均在 `09:35` 以 `reason=timeout`
  放行，真实 POST 前不再刷新余额。四任务并发还要求余额门按计划总额/在途预留处理，不能仅
  逐任务读取同一旧余额后各自放行。
  **临时限制：不要直接重启这四张卡**；恢复会继续提交剩余计划次数，并不能补齐已经失败的
  现货腿。先由 Human 在币安核对并决定如何补齐现货负债/合约对冲，再处理任务状态。修复需同时
  覆盖前端提示、后端 fail-closed 实时门及并发余额预留/串行化；属资金与订单路径，须走
  HIGH_RISK 计划评审、实现、Review-1、Review-2。重开条件：上述敞口人工收口、修复上线并经
  实盘前只读验收，或任一余额/仓位继续变化。
  **Fast 修复已上线（2026-08-21 11:46 CST）：** 分支
  `fast/reverse-close-total-available-balance` 已补前端计划总额提示，并在后端每次真实
  reverse-close `prepare_attempt` 前读取 5 分钟内的 PM `totalAvailableBalance`；不足、缺失、
  超龄或非法均暂停且零 attempt/零 POST。双审核均 `ACCEPT` 后根据 Claude-GLM 的观察
  继续移除了旧反向平仓逐币种 `crossMarginFree` 误拦：所有 close 的 domain 预检只校验交易过滤器，
  forward 余额由现有普通现货 base 门负责，reverse 余额只由发单前的 PM 账户级门负责。
  前端全量 self-check 通过；后端相关 138 项通过，完整套件排除既有 HTTP 白名单误报后
  `2053 passed, 1 deselected`，并新增旧门误拦、PM 快照缺失/超龄/缺字段/非法值与价格缺失的
  回归检查。`42629cc` + `2d339b6` 已合并 `main` 并推送，服务已于 `11:46 CST` 重启，该门现已生效。
  **但只防新发、不补存量**：上述四笔单腿敞口不会自愈，四张卡仍 `paused`（`连续失败 1 / 阈值 1`），
  重启只会继续提交剩余计划次数、补不齐已失败的现货腿。
  `2026-08-21 12:10 CST` 只读复核净敞口：`INJ` 欠 8 对合约多 4（裸 4，≈19.08 U）、
  `JST` 欠 200 对 100（裸 100，≈10.71 U）、`SNX` 欠 50 对 0（**完全裸露**，≈10.82 U）、
  `WLD` 欠 60 对 40（裸 20，≈7.50 U），四者合计约 `48.11 U` 无对冲。
  **残余风险：** Fast 范围未增加跨任务余额预留；极近同时到达的多个任务仍可能各自读取同一份
  可用余额后分别放行（本次四笔正是挤在 40 秒内：`09:35:08/19/33/47`），故本条保持 OPEN，
  需后续正式 HIGH_RISK 修复或实盘限制。

- `[OPEN][OPERATING][2026-08-22]` **每次重启服务都可能留下一笔「发了但没收到回音」的借币，
  重启后要去币安核该币余额。** `DEC-2026-08-21-001` 起，只有 POST 返回可用 `tranId` 才算借成，
  其余（崩溃孤儿 / 畸形 2xx / 5xx / 传输失败）一律当没借成、任务继续跑；借币记录对账子系统已整个
  删除（`09a4084`，`main`）。代价是**每个孤儿最多多借一笔**，Human 从币安控制台核对余额收口
  （闸门与「查实际本金」均经评估后由 Human 否决）。
  实测频率：POST 均耗时 411ms / 派发间隔 1.5s → 每次重启约 27% 命中；`2026-08-21 20:01` 那次重启
  当场撞到一笔 `HOME 1000`，Human 核对后确认**未借成**，代价为 0。
  判定口径：启动日志 `borrow_execution_mode` 的 `recovered_orphan_blocker_count` 即本次重启留下的
  未确认笔数（字段名是历史遗留，不代表有任务被阻塞）；明细查
  `SELECT asset, requested_amount FROM borrow_attempt WHERE reason='crash_orphan_responseless';`。
  遗留物理列 `reconcile_next_at_us` / `reconcile_step` / `reconcile_exhausted` 仍在旧库中，
  已从 `_SCHEMA` / `_migrate` / 行映射移除，读取不受影响；`DROP COLUMN` 属数据库手术，未做。

- `[OPEN][ACCEPTED][REVIEW-2][2026-08-13]` **建卡预检从未成功的 live 平滑任务仍可能按默认值发单（F-A）。**
  事实：缓存未命中/超龄且实时补读失败时，smooth 仍会 `201 paused` 建卡，固化
  `q_common=NULL`、`preflight_snapshot.available=false`；Human Start 后，timeout 或「成交1次」可绕过
  「计划下单数量无效」等待结论，以原始 `single_amount`、默认 `papi_margin` 路由和默认 `BOTH`
  position 模式进入真实两腿链。回退零件早于 base（`d90f2f1`），D15 `dfd38a6` 首次使其在 smooth
  实盘写路径可达；immediate 每轮 fresh preflight 不受影响。Bookkeeper 已用临时 SQLite 和假执行器
  独立复现 `create=201 paused / q_common=None / timeout dispatch=1`。多数结果会被交易所过滤器拒绝；
  最坏是合约成交、现货因路由/备款不匹配被拒，留下单腿裸空。Human 认为须同时发生缓存失效和实时
  补读失败，概率低，决定本次合并接受、不再返修。临时限制：建卡后「公共网格量」为 `—` 就删除重建、
  不要启动；运行卡出现「计划下单数量无效」立即暂停，不等 timeout；不要为纯展示验收创建平滑任务。
  重开条件：实际出现「公共网格量为 `—`」的平滑卡、由此产生单腿敞口，或未来开放自动化/批量建卡。

- `[OPEN][ACCEPTED][LIVE-OBSERVATION][2026-08-13]` **平滑卡两位开单率在“等于阈值”时容易被误读为已通过。**
  Human 验收任务 `2fb9cfef-b9b1-46f4-bc6d-03c789fa7214`（SHELLUSDT、forward、threshold
  `0.05%`）于 `20:00:42 CST` 显示现货 ask `0.01970000`、合约 bid `0.0197100`、正向开单率
  `+0.05%`。原始计算约 `0.0507614%`，但冻结公共 formatter 先按 `ROUND_HALF_UP` 量化为
  `0.05%`，gate 再执行严格 `0.05 > 0.05`，所以 `spread_pass=false`、覆盖率通过但未放行；页面的
  wait reason 正确，却没有把“等于阈值仍未通过”单独醒目标记。`20:01:12 CST` 行情移动到 spot ask
  `0.01970000` / perp bid `0.0197300`，量化 spread `0.15%` 后以 `reason=market` 正常放行，两腿
  各成交 `500`；gate→现货/合约订单客户端调用分别约 `4.523ms` / `4.893ms`，证明本次不是下单前
  阻塞。实际影响仅是 Human 可能把等待误判成 worker 故障，资金判定仍按冻结严格 `>` 正确执行。
  临时口径：以卡片 wait reason 与后端 pass 状态为准，显示值与阈值相等不算通过。若 Human 要求
  消除歧义，最小 UI 修复是展示“当前 0.05% ≤ 阈值 0.05%，未通过”状态，不改 gate 或精度契约。
  Human 于 `2026-08-13 20:03 CST` 接受当前展示限制并决定继续最终评审；本次接受不改变严格 `>`
  或两位量化契约。重开条件：Human 实际因此误操作，或后续明确要求醒目的通过/未通过比较状态。

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

- `[DECIDED][OPERATIONS][2026-08-03, decided 2026-08-15]` **本地故意用手动前台模式；
  launchd 不再投入修复。** **当前服务 = 手动前台进程**，在 `127.0.0.1:8787`；重启必须手动
  跑 `scripts/run-server.sh`（`backend/config.py` 不自行解析 `.env`）。
  **决定（Human 2026-08-15）**：本地手动启动够用，不修 launchd。托管需求属于未来的服务器
  部署，那边是 systemd——plist 的 `RunAtLoad`/`KeepAlive`/`ThrottleInterval` 对应
  `WantedBy=`/`Restart=always`/`RestartSec=`，是重写不是移植；且服务器无 TCC，Desktop
  权限问题在那边不存在。`scripts/service-control.py` 的 launchd 子命令与 plist 渲染暂留
  不动，服务器部署时另开一轮写 systemd unit。
  **历史事实**：2026-08-09 的 launchd fail loop 根因是 macOS TCC——Human 给 `/bin/bash` 加
  「完全磁盘访问」后 bash 能进 Desktop（退出码 126→1），但 `run-server.sh` 调的 python
  （`.venv/bin/python` → homebrew `python@3.11`）未授权，读 `.venv/pyvenv.cfg` 报
  `Operation not permitted`。Human 决定不逐个授权可执行文件（homebrew python 一升级路径就变、
  TCC 失效，太脆弱），已 `launchctl disable + bootout gui/501/com.aoke.funding-hedging.server`。
  2026-08-15 `doctor` 只读复核：`loaded=false`、`launchctl print` rc `113`（domain 内无此
  service）、`server.stderr.log` 末次写入停在 2026-08-09 19:09——**权限修复从未经 launchd
  路径验证过**，既不能称已修好，也不能称仍坏。
  ⚠️ **TCC 不按父进程继承**：终端能进 Desktop 是终端 app 自身的授权由子进程继承；launchd
  拉起的进程按被执行二进制自身的授权判定。「手动能起」推不出「launchd 能起」。将来若真要恢复
  launchd（`launchctl enable + bootstrap gui/501` 该 plist），须重新实测这一点，不得引用手动
  启动的成功作为证据。
  **⚠️ `service-control.py status/doctor` 具有误导性**：`health 200` 来自手动进程、`commit` 字段读当前
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

- `[OPEN][2026-08-23]` **直连 HTTP 守卫白名单漏登记 `public_ip_service.py`，套件长期带一个红。**
  `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 失败：
  `backend/services/public_ip_service.py:47` 用 `urllib.request.urlopen` 但不在允许集内。
  **非本 stage 引入**——Bookkeeper 在基线 `dd12833` 独立复现同因。
  影响：守卫的意义是「没有产品模块能绕过指定客户端直连外部」，漏登记说明白名单与实际已脱节；
  且长期带红会让后来者误判「本来就红没事」。修法二选一：登记进允许集（若确认该直连合规），
  或把它改走既有客户端。`2026-08-23-hyperliquid-funding-compare-v1` 已正确登记
  `hyperliquid_public.py`，未顺手掩盖此项。

- `[OPEN][2026-08-23]` **HL 适配器未捕获 `UnicodeDecodeError`（Review-1 grok 非阻塞观察）。**
  `backend/adapters/hyperliquid_public.py` 捕获 `URLError/OSError/ValueError`，未含
  `UnicodeDecodeError`。非 UTF-8 的 HL `/info` 响应会让本轮 compose 被 worker 的 `except: pass`
  跳过，页面暂留上一份已发布快照。**不构成 success-only 缓存投影**——`hyperliquid_data_time`
  跟着一起旧，超 90 秒即标红，使用者看得见。无当前证据，故未在本 stage 修。
  **重开条件**：出现非 UTF-8 的 HL `/info` 响应。

- `[DEFERRED][2026-08-21]` **收益曲线滑点改按「任务卡」分组——已完整评估、数据支持，Human 决定
  暂不做，等实际遇到问题再说。**
  提议（Human）：滑点不按整轮持仓汇总、改按开单任务卡汇总。
  **实测支持**：① 全部 55 张任务卡的成交跨度 **47 张在 1 分钟内、8 张在 1 小时内、无一超过
  1 小时**（最长 `FFUSDT` smooth 平仓卡 50.2 分钟）——而曲线的桶就是 1 小时，**故按卡分组的时间
  精度已顶到图本身的分辨率上限，再细分到逐笔也画不出更多**。TST 那 8 天跨度不是「一张卡跑了
  8 天」，而是 Human 隔几天新建一张卡加仓（共 7 张）。② 换粒度不改金额：17 个币中 **14 个
  完全相同（0.0000）**，仅 3 个敞口币不等（`INJ +0.0563`、`THE +0.0433`、`TST -0.3200`），
  这是加权均价在两腿配平时与任意分组等价的数学性质。③ 算不出的组数：按周期 5、**按卡 6**、
  逐笔 10——**按卡比逐笔少丢一半**，同卡内其他成交能兜住被拒的单腿。④ 曲线点位 38 → 55。
  **改动规模**（估）：`store.list_open_cycle_slippage_basis` 改分组键 + 时间锚点改「该卡首笔
  成交时刻」+ 去掉 `closed_at_us IS NULL` 过滤，约 15 行实质改动；`domain` 中读 close-log 算
  滑点那 25 行**整段删除**；`server` 少拉一次 close-log 与一个状态标志；前端删 `close_logs_ok`
  一条提示；约 10 条用例调整。**净减代码。** 附带收益：时间锚点改为成交时刻后，上面 Live Risk
  的失真 ② 一并消失。
  **前置条件**：① 必须两边同时改（已平仓周期也按卡算），只改在持仓那半边会重新引入重排——实测
  TST 平仓那一刻会从 5 个点塌缩成 1 个、金额从 `+0.6100` 跳到 `+0.9300`；② 须先把手动补录的
  合约腿改挂到 `be355ffd`（见上条 Live Risk）；③ 曲线历史将完全依赖成交腿明细而非 close-log
  的 10 行汇总——**已确认当前无任何清理/归档/保留期机制，腿永久保留**，将来若新增数据清理功能，
  必须先知道收益曲线依赖它。
  **代价**：敞口币会与「历史仓位」页（close-log 周期级）对不上，三个币合计差 `0.22 U`；读取
  数据量增加（现 130 条在持仓腿 + 10 行 close-log → 全部 293 条腿，一年后约 7000 条腿）。
  重启触发条件：曲线时间失真造成实际误判，或单张任务卡成交跨度变长使前提失效。

- `[OPEN][2026-08-16]` **未还利息已进快照并落地展示（本轮已交付），遗留一处口径提醒。**
  `crossMarginInterest` 已进 `balances_unified`（`cross_margin_interest` +
  `cross_margin_interest_value_usdt`），统一账户卡展示实时未还利息、净价值扣息、
  小额过滤对「只剩欠息」的资产免过滤、`total_debt_usdt` 改为 Σ(本金+利息)。
  **口径事实（实盘两次验证，写进契约文档）**：`crossMarginBorrowed` 只吸收**历次还款
  那一刻**已计提的利息，此后新计提的挂在 `crossMarginInterest`，两者不重叠、相加恰好
  一次。证据一：SNX 借 100 还 50，还款前累计息 `0.10709571` 与 `borrowed(50.10709571)
  − 本金(50)` 8 位全等；证据二：2026-08-16 一笔 INJ 还款实时观测到 `borrowed` 从 `10.0`
  变为 `8.00109129`，多出的 `0.00109129` 正是还款前那一刻的 `crossMarginInterest`。
  ⚠️ **`total_debt_usdt` 语义已从「本金」变为「本金+未还利息」**——若与本轮之前的历史
  记录对账会有一个台阶（当时量级 0.06 USDT）。副标题已改为「本金 + 未还利息 折算合计」。
  **未做**：`docs/api/public-market-contract.md` 的 v0.x 修订号未递增（本轮按 additive
  amendment 追加章节处理）。
  **[grok Review-1 带出，判为 pre-existing 不阻塞，未修]** 概览「借币负债」与资产卡净值
  在**缺报价**时口径不一致：`total_debt_usdt` 走 `_usdt_value`（无价**按 0 计**+warning），
  行级 `*_value_usdt` 走 `_cross_margin_borrowed_value_usdt`（无价为 `null`）。评审实跑构造：
  某资产欠息 12.5 且价表无该 symbol → 卡片净值 `—`（诚实 fail-closed），概览负债把这笔当 0
  丢掉（偏小且不自知）。这是 `total_value_usdt`「缺价记 0」的既有规则，本轮未触碰。若要统一
  成 fail-closed 需单独决定——会影响 `total_value_usdt` 的既有行为。

- `[OPEN][SIMPLIFICATION][2026-08-15]` **正向平仓的前端余额预检可评估整个删除。**
  误拦已修（改为 `spot_balance + unified_balance` 两账户求和，`c04a006`，STOUSDT 实盘验证）。
  但 C13 落地后点「启动」会同步备料并当场回中文原因，这个基于 60 秒旧缓存的前端预检价值
  已大幅下降，可评估直接删除余额预检；**保留合约持仓预检**（口径简单且防超平）。

- `[OPEN][DEAD-CODE][2026-08-14]` **`hedge_open_fill` 表及其死代码待清理（须 Human 授权）。**
  round-1（dry-run record transport）遗留的「每对 attempt 一行、inline 两腿成交」表；real-API/live
  阶段已由 `hedge_open_attempt` + `hedge_open_leg` 两表取代（成交明细→leg、持仓源→leg），live 路径
  不再写它。**现状核验（2026-08-14，`data/hedge-open-tasks.sqlite3`）**：`hedge_open_fill` 行数 `0`
  （对照 attempt `99` / leg `198` / task `44`）；`insert_fill` / `list_fills_for_task` 生产代码零调用
  （仅 `backend/tests/test_hedge_store.py` 与 `test_hedge_cycle_core.py` 调用）；前端/API 无引用。
  `aggregate_positions` 仍 SELECT 该表（SQL-A），但 `for row in fill_rows` 因恒空从不执行，删之不改变
  任何聚合结果。**注**：P2-1 注释（`store.py:2602`）称非零行「告警而非并入」，实际代码是告警后仍并入
  `cycle_id=None` 桶——删时一并消除该注释/实现出入。
  **删除清单**：① `store.py:1952 insert_fill` + `2005 list_fills_for_task` + `265 _row_to_fill`；
  ② `aggregate_positions` 的 SQL-A 读取（`store.py:2579`）+ P2-1 告警块（`2602-2630`）+ fill_rows 循环
  （`2684` 起）；③ `_SCHEMA` 建表（`store.py:108`）+ 索引（`150-151`）；④ 上述 legacy 测试。
  **分两步（降低 schema 风险）**：先删方法 + fill 读取分支 + 测试、物理表暂留并跑全量测试；稳定后再
  对生产库 `DROP TABLE hedge_open_fill`。涉及生产库 schema 变更，须 Human 明确授权后单开一轮、不夹带；
  与 `docs/planning/dead-code-cleanup-2026-08-09.*` 的既有清理候选合并执行。

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

- `[OPEN][RESIDUAL]` **`close_log` 的利息仍是约数（≈U）**——精确化需要把价格源注入 service 层。
  挂账已久，未定优先级。

- `[OPEN][RESIDUAL]` **UM drain 可在 `cumulative_quote` 未知时把 FILLED 腿判为终态。**
  该路径会保留 `avg_price` 但缺 quote，导致该周期的合约均价与开/平滑点显示 `—`；这是
  fail-closed，不影响订单或持仓且不臆造数值。重开条件：出现真实历史周期命中该形态，或 Human
  决定统一 drain/inline 终态规则；届时应同批评估 quote 缺失时用 `avg_price × qty` 加权的口径。
- `[OPEN][RESIDUAL]` `_rate_limit_stamp_pending` is in-process: a restart mid-stamp
  costs one failure count (pauses one early, fail-closed). Fix = a new column.
- `[OPEN][RESIDUAL]` The money-zero tripwire is a speed bump, not a proof: five
  evasions + `fee_amount` outside the money names. DEC-2026-07-30-001.
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
## Next Priority

- **No active stage.** Current priorities (detail in the sections above):
  1. 服务器部署（systemd unit）—— 本地已决定不修 launchd，托管需求整体推到这一轮，须 Human 授权后单开。
  （1000x 腿量换算已于 2026-08-15 封存，不再是优先项——见 Open Follow-ups 的
  `[CLOSED-NOT-DOING]` 条目。）
- Nothing open authorizes deployment, Start-gate changes, credentials, or live
  operation. Live actions follow the Live Risks gates above.

## Last Completed
- stage: `2026-08-19-hedge-order-fee-cost-v1`
- archive_ref: `archive/2026-08-19-hedge-order-fee-cost-v1`（tip `08fce61`）
- delivery: `6ba28b0..45eb5ec`；`rework_count` 0。Phase 1/2/3 全部通过双评审（Kimi ACCEPT + Opus 5 ACCEPT）。Human 授权已合并 `main`（`merge: dd736b9`）并重新部署 8787 服务。
- recorded_completed_at: `2026-08-20`
- outcome: 成交手续费冻价成本 V1。完成 `hedge_open_leg` 四列手续费字段扩展与回补（268/269 腿成功入库）、`hedge_open_cycle_close_log` 三列历史关仓手续费字段现算聚合、持仓表 `aggregate_positions` 读链路真实折 U 聚合（quote/base 均价、宁缺毋滥 D10/D11 契约）、三处终态 commit-first 实时写入与 D4 现价冻结，实盘验证 `NOMUSDT` 自动落库记账。
- follow-ups: 币安 UM 合约历史成交受约 7 天接口限制，老单（如 TSTUSDT 9.6 天前合约腿）返回空列表按契约安全显示 `—`。
- stage: `2026-08-14-smooth-close-orders-v1`
- archive_ref: `archive/2026-08-14-smooth-close-orders-v1`（tip `f667e6ff8f5fb010d5116563b325bf4384c52caf`）
- delivery: `6f6c729..f95577f`；`rework_count` 1（P1修复一次）。Review-1 (gemini-3.1-pro) ACCEPT；Review-2 (opus5) ACCEPT。未授权 push/部署或合并。
- recorded_completed_at: `2026-08-14`
- outcome: 平滑平仓 V1。实现了以滑点阈值和计划次数自动拆分平仓，保持方向翻转诚实显示，并支持与现货、合约资产的实时盘口对照。
- follow-ups: 前端现货余额拦截误拦问题已记录，待后续修复。
- stage: `2026-08-12-smooth-open-orders-v1`
- archive_ref: `archive/2026-08-12-smooth-open-orders-v1`（tip
  `d404e204f124fc2f8b11a2634f4d54b1866d1bdc`，完整 planning、dispatch、handoff、status、Review-1/
  Review-2 与 Human 风险接受记录）
- delivery: `e955bdd..ad8c631`；`rework_count` 5。累计 Review-1 ACCEPT；最终 Review-2 技术结论
  REWORK，F-A 经 Bookkeeper 复现后由 Human 接受为本次合并已知风险且决定不修；Human 已授权本地
  `main` 合并，未授权 push/部署。
- recorded_completed_at: `2026-08-13`
- outcome: 平滑开单创建暂停、Human Start 后首轮杠杆前置、spot/perp 一档公共 WS gate、严格阈值与
  80% 覆盖、timeout/manual 当前轮放行、两腿并发、同次放行快照和分段延迟审计、running 卡统一 2 秒
  刷新均已交付并经页面/一笔真实订单链验证。
- follow-ups: F-A、L1/L2/L3 与两位等值展示限制继续按 Live Risks 的临时边界和重开条件管理；服务已停，
  下一次启动由 Human 本地执行。
- previous stage: `2026-08-12-local-ip-display-v1` —— 公网出口 IP 展示；归档
  `archive/2026-08-12-local-ip-display-v1`（tip `15eba3c92251dc5487e2c98f8fe8dbcec396887f`）。
- earlier previous stage: `2026-08-12-hedge-slippage-spread-v1` —— 历史仓位开/平滑点价差计算；归档 `archive/2026-08-12-hedge-slippage-spread-v1`（tip `ad774315eb56e933ab14615c7a92e0b697f4e5e9`）。
- earlier previous stage: `2026-08-11-reverse-position-drift-v1` —— 统一账户 reverse 持仓弱告警修复；
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

## Evicted (2026-08-22) — Current Status 交付叙事

按 Update Rule 驱逐了 `2026-08-07`..`2026-08-21` 的 15 条交付叙事（约 19 KB）。完整原文
`git show 046fff5:PROJECT_STATE.md`。**下列是从中提取的、仍然生效的约束**——它们不是历史，
只留 git 指针会让后来者误判：

- **修「假声明」的可复用判断**（2026-08-07 一轮里踩到三次同一形状）：要区分「不知道」与
  「知道没有」，**缺省一侧永远倒向「已知」**。读不到就说读不到，不要渲染成 0 或「没有」。
- **F4「交易所无仓」红字只验证过一半**：正常侧（读得到时不出现）已 2026-08-08 实盘验证；
  **「读不到时红字出现」一侧从未实盘触发**，仅由 self-check 5 项断言覆盖。
- **现货腿身份是任务第一等属性**：建任务时由静态表（71 条 = 65 bStock + 6 乘数）解析一次并
  固化，下单/平单/展示三环只读不算，字符串猜测规则已全删。**未收录即无现货腿（fail-closed）**。
  维护：`scripts/check-spot-symbol-map.py --verify/--emit`。
- **严禁把 USDT 的可转出额算法推广到其他币**（抵押品折算率约束，self-check 有断言守）。
  USDT 用 `total_available_balance_usdt` 标签「可转」，其余币用 `cross_margin_free` 标签
  「可用」，措辞跟数据来源走。`GET /api/private-account/max-withdraw` 无前端消费者、已移出
  前端同源白名单，但**要 per-asset 精确可转出额时它是唯一数据源**。
- **`regular_spot` 开仓的备款与防裸空**（DEC-2026-08-08）：`open+forward+regular_spot` 建卡时
  在 `create_task` 内一次性划转 `truncate(q×N×price×1.03)` USDT 到现货，失败不建卡。
  **dispatch 下单前核验**：`fresh=regular_spot` 时建卡固化的 frozen route 必须也是
  `regular_spot`（即已备款），否则暂停不发单——这是防裸空的闸门，别当冗余删掉。
  **开完不自动回流，残余 USDT 人工收尾。**
  **Human 决断（勿议）**：不查统一账户余额、不做幂等/tranId/恢复链、不自动回流、不做前端防重。
- **检索教训**：grep 找契约证据时**必须扫 `reports/api-samples/`**。只扫
  `backend/`/`docs/`/`schemas/` 会漏——2026-08-16 因此白推理数轮，那份 2026-08-04 的采样早已
  写明 `crossMarginInterest` 是「当前未还」而非「历史累计」。
- **`interest_rows` 表有 `principal` 字段**：币安在每笔计息记录里直接报了计息本金，不必用
  `borrowed` 与资金流水反推。实测该字段还反证了**小时计息不会自动资本化**。
- **平滑平仓 V1 的后端从未做过 Review-2**：后端 P1 区间 `7d3fe60..c4ae93a` 只有一次 Review-1
  （grok-4.6，REWORK/F1），且 F1 修复提交 `6f6c729` 未经独立评审。Human 合并时具名接受。
  以后动那段代码前先知道它的保证程度。
- ⚠️ **`2026-08-17` 有两处口径断裂，与那之前的历史记录对账会有台阶**：
  `total_value_usdt` `571.13 → 579.64`（+`8.51`）、`leverage_ratio` `3.07207789 → 2.98142928`
  （三张卡由 `accountEquity` 改取 `actualEquity`）。做跨期对账前先套这条。
- ⚠️ **一条既有 test-asserted 契约硬规则已被废**：`total_value_usdt = Σ(unified
  totalWalletBalance priced) + Σ(spot free+locked priced)`（anti-double-count 公式）
  **不再成立**——unified 侧改取净值，毛额不再进总额。毛额单独报在 `unified_wallet_value_usdt`
  上，原测试的本意（um/cm 不重复计入、`crossMarginFree`/负债不移动毛额）已移到该字段继续守。
  别按旧公式「修」代码。
- ⚠️ **测试分层边界（勿误读）**：`self-check` 的杠杆率断言守的只是「后端给 null 时卡面渲染成
  `—`」，其夹具写死 `leverage_ratio: null`——**后端若改回在缺源时算出 `1.0`，self-check 照样
  全绿**。守住那一侧的只有 pytest 的 `test_..._no_leverage_when_total_is_partial`。

- **`APP_MARGIN_REPAY_ENABLED` 按 Human 决定保持开启。**
- **持仓表数量列以交易所实际持仓为主，维持现状不再整改**（Human `2026-08-08` 关闭本地数量
  口径 X/Y/Z 的整改）：读不到时红字提示 + drift 标记已兜底。别当缺陷再去"修"。

## Evicted (2026-08-21)

按 Update Rule 驱逐了 8 条已结条目（`RESOLVED-BY-DELIVERY` / `RESOLVED-BY-BLOCKING` /
`CLOSED-SETTLED` / `CLOSED-NOT-DOING` ×2 / `SUPERSEDED-BY-ABOVE` / `RESOLVED` / `ACCEPTED`），
完整原文见 `git show 3c1834c:PROJECT_STATE.md`。**驱逐时从中提取出仍然生效的约束，保留在下方**
——它们不是历史，只留 git 指针会让后来者误判：

- **1000x fail-closed 拦截脚手架不得作为死代码清理。** `PAUSE_REASON_MULTIPLIER_CLOSE_UNSUPPORTED`
  常量/注册/文案与测试夹具 `_allow_multiplier_open` 全部保留。换算需求 Human `2026-08-15` 决定
  不做，该拦截已由「止血」转为**长期终态**。重启材料：
  `docs/planning/leg-unit-size-conversion-2026-08-15.CLOSED-lessons.md`、
  `docs/planning/HANDOFF-1000x-2026-08-15.md`（r5 清单已知不全，漏 residual 计算路径）。
- **持仓表只显示「未平仓周期」**（Human `2026-08` 决策，仍生效）：已平仓周期只在历史仓位页
  （close-log）呈现，避免全平标的回显。
- **`totalWalletBalance` 是部分钱包视图，不含 UM/CM 合约子钱包。** 做对账、算持仓成本、回答
  「统一账户里一共多少钱」都不能直接用它，必须另加合约钱包。当前前后端零消费者。
- **手动前台模式下日志不落固定文件**（已接受，不修）：从 operator 终端启动以便日志可回看；
  需留存自行重定向 `scripts/run-server.sh > 某文件 2>&1`。服务器部署由 systemd journal 接管后消解。

纯历史、无残留约束，仅存指针：1000x 腿量换算「必须一次改齐的八处」清单、1000x 乘数币适配封存
详情、首笔真实平滑任务验收缺口（已随交付修复）、COOKIEUSDT 平仓单腿事故修复链
（`archive/2026-08-hedge-position-cycle-v1`）。

## Update Rule

Record live incidents at once; remove resolved items. Completed work leaves its
trace in git history and archive references, not in narratives here — commit
messages must state the one-line outcome so history stays traceable, and this
file records only live risks, open follow-ups, and pointers. Over budget: evict
resolved first, then oldest, keeping a git reference.
