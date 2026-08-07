# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check.

## Current Status (2026-08-07)

- **[2026-08-07 晚 已收口]「展示层诚实性」整族修复（Human 直接驱动，无 stage）**。
  贯穿本轮的一条线：**界面在声称它其实不知道的事**。四项全部收口 —— 单腿敞口判定
  （漏报裸空 + 部分失衡）、drift 账户口径（对多数币恒假阴性）、终态任务结算文案
  （对已删任务说「已暂停、请恢复」）、F4 交易所无仓假声明（三条路径 + `no_um` 措辞）。
  同族的展示口径修正还有：划转「可用/可转」措辞按数据来源分开、任务卡暂停原因直读
  后端中文、持仓表显示现货腿 symbol。
  **一条可复用的判断**：修「假声明」时最容易犯的错，是**把一个假声明换成另一个**。
  三次踩到同一形状——`[]`（真空仓）当失败信号会在真空仓时误报；`unavailable_sources`
  缺失当故障会让每个旧调用方平白报警；用可用额冒充可转出额显示。共同解法是
  **区分「不知道」与「知道没有」，且缺省一侧永远倒向「已知」**。
  **过程中另有两项非展示交付**：1000x 乘数币 fail-closed 拦截（资金安全，见 Live
  Risks）、前后端字段名绑定检查（E4，沉默型故障的护栏）。
  **测试基线 1601 passed + self-check EXIT=0**；本轮新增 ~30 条断言，其中多条
  **注入回退验证过会红**（字段改名、条件移除），不是写完就算。

- **[2026-08-07 已收口] symbol-identity-unification（现货腿身份统一；Human 直接驱动，无 stage）**：
  方案 `docs/planning/symbol-identity-unification-2026-08-07.opus5.md`（r2）+ 三轮 DeepSeek
  评审全部 ACCEPT。**现货腿身份自此是任务的第一等属性**：建任务时由静态表解析一次并
  固化到 `hedge_open_task.spot_symbol / spot_base_asset / symbol_match_type`，下单/平单/
  展示三环只读不算，取值统一走 `spot_symbol_of(task)` / `spot_base_of(task)`（接口守卫：
  只接受 task 字典，传裸字符串 TypeError）。
  交付：`ee35b5e`(①固化+回填) `8d23063`+`7d2a104`(②消费点+删 spot_order_symbol+必填)
  `90edf0a`(③展示环) `5105e4a`(④⑤收尾+close 继承) `be3f583`(-2015 文案)。1571 passed。
  **三条可复用的设计判断**：
  1. **身份 ≠ 存在性**——身份来自静态表（稳定、可固化），存在性必须实时探测（会变：
     `KORUUSDT` 曾无现货腿，币安后来上线 `KORUBUSDT`）。二者混同会让「无腿」退化成
     「查表查不到」，而表外绝大多数恰是同名有腿的普通币。据此撤销了方案原定的 D1
     「创建时拒绝」——该拒绝早已由 `check_symbol_legs` 完整覆盖（实测 BUSDT/1000000MOG
     均被 missing_leg 拦下）。
  2. **固化优于实时**——对冲是跨时间的持仓，平仓必须用开仓时的身份；映射表若在持仓
     期间变更，重新解析会让两条腿对不上。close 经 `cycle.first_task_id` 继承开仓身份
     （零迁移）；表变动由 D3 `identity_drift`（只报不拦、每任务去重）+ 桶内
     `identity_conflict` 审计 + `--verify` 的 STALE 三处告警，绝不静默切换。
  3. **静默默认值是类型混淆的温床**——`AttemptContext.spot_symbol` 一度给了默认 None +
     回退 coin，评审要求改必填后**立即暴露 7 处漏传构造**（26 用例失败）。合约名/现货名/
     资产名都是裸字符串，传错不报错只算错值。
  **实盘闭环（17:00–17:40，SNXXUSDT 真实成交）**：开仓 `feeaf73f` 2/2——现货腿实发
  **SNXXBUSDT**、合约腿 SNXXUSDT，均 FILLED；持仓面板 `spot_balance=3` 与实际余额一致
  （Q1 症状消除，此前恒 null，连带 `drift` 是假阴性）；平仓 `ac93dcab`+`a745c7d0` 身份
  **继承开仓任务**、现货 SELL 正确路由 `/api/v3/order`（SNXXB 在普通现货账户——正是
  COOKIE 单腿事故的判定点，本次无误）；全平后周期 `8bc56030` auto_close、USDT 划回。
  全程无 `identity_drift` / `identity_conflict`。
  **插曲教训**：一次平仓因出口 IP 变更被币安 401 `-2015` 拒（两腿均未发出、无裸腿）。
  系统把 auth 类判为 `UNKNOWN_QUERYING` 而非 REJECTED 是**有意的保守设计**（auth/签名/
  时间戳存在歧义 → 只按 clientOrderId 重查、绝不重发），行为正确不改；错的是文案让人
  去找一张从未存在的单。已改为点名 IP 白名单 + 「订单未发出」。
  **本线遗留三项（1/2 已于 2026-08-07 晚清理，见 `<PENDING>`）**：
  1. `[RESOLVED][2026-08-07]` ~~**`issue-triage-2026-08-07.opus5.md` 仍带已更正的错误**
     （第 173/192/371 行）：称 bStock 失配导致 `single_leg_exposure` 失效、裸空不报警。
     实为**只有 `drift` 受影响**——`single_leg_exposure` 只读任务记账的 `spot_qty`/
     `perp_qty`，不读 `real_spot`，一直正常。更正已写在
     `unified-symbol-resolver-2026-08-07.review-opus5.md` §二，但**原文档未同步**，
     单独阅读会被误导；该文档给 Q1 排的优先级理由也有一半不成立。~~ 已订正五处
     （摘要表状态、结论标题、影响第 2 条 + 订正块、验收建议、优先级理由），并在文档
     顶部加了状态头。
  2. `[RESOLVED][2026-08-07]` ~~**前端持仓表尚未显示现货腿 symbol**~~ 已交付：币种列下
     加「现货腿 SNXXBUSDT」子行，仅当与合约名不同才显示（同名不加噪音、`no_task` 行
     无固化身份则不显示）。
  3. `[OPEN]` **launchd 托管仍未修**——见 Live Risks 同名条目（2026-08-03 记录，
     2026-08-07 补根因 TCC）。Human 尚未决定是否处置。
- **[2026-08-07] 现货符号解析改显式映射表 + P1/P2 死区修复已提交（`8ee6d3c`）**：
  d717595 的字符串猜测规则被纯表取代（`SPOT_SYMBOL_MAP` 71 条 = 65 bStock + 6 乘数，
  最新 exchangeInfo 实测生成）：d717595 放开 B 后缀 TRADIFI gate 的**全部影响面仅 1 条且是
  错的**（合约 BUSDT/base=B 会误配到 BounceBit 的 BBUSDT，两个独立币种，误配贯穿预检/开单/
  展示/平单——真实裸敞口风险）；`base[4:]` 对 `1000000MOG` 剥成 `000MOG` 同样被纯表消除。
  同一提交含 P1/P2 修复（collateral-cap 开单死区：缓存超龄实时重读 + 手动刷新覆盖
  restricted_asset）。**服务已于 2026-08-07 12:39 由 Human 重启并实测两项修复生效**：
  手动「更新缓存」使 cap 的 `checked_at` 由 `04:42:45Z` 推进到 `04:44:28Z`（旧代码此处
  纹丝不动）；注入超龄 10h 且谎称 THE 已打满的缓存后，实时重读得 `False`——既证明
  死区消除，也证明陈旧清单未被采用。服务其后于 **16:59:28 再次重启**，已载入身份统一
  全部提交（`be3f583` 之前），并据此完成了 SNXXUSDT 开平仓实盘闭环。
  issue-triage（`docs/planning/issue-triage-2026-08-07.opus5.md`）**Q1 已随本线解决并
  实盘验证**；**Q4 已于 2026-08-07 晚交付**；**Q2/Q3 仍未处理**：
  - `[OPEN]` Q3 多任务卡回显：错误提示只写 DOM 未入 state，任何重渲染（他卡操作 /
    60s 自动刷新）即抹除；按钮无 pending 态；每次 mutate 触发 3 个 GET + 2 次全量
    DOM 重建。
  - `[RESOLVED][2026-08-07]` Q4 统一账户可转出额：~~划转界面用 `cross_margin_free`
    当可用（393.22），而 PM `total_available_balance_usdt` 是 192.51、币安界面
    「最多可转出」是 222.xx，三个数互不相等。~~ 已接入
    `GET /papi/v1/margin/maxWithdraw`（白名单 15→16，`fetch_max_withdraw`，
    模式照搬同族 `maxBorrowable`）+ 新端点
    `GET /api/private-account/max-withdraw?assets=X,Y,...`（批量）+ **划转下拉里
    「可用」整列改为「可转」**（Human 2026-08-07 晚要求：去掉单独一行提示，真实可转
    直接进下拉标签）。
    **最终形态（Human 2026-08-07 晚定稿）：前端零请求，全部沿用后端 account 缓存快照。**
    - **USDT** 用账户级 `total_available_balance_usdt`，标签说「**可转**」。
      **实测同时刻对照**：该字段 209.18 vs `maxWithdraw(USDT)` 209.28（差 0.05%，
      快照 60s 缓存的时间差），是同一个数；而 `cross_margin_free` 是 413.93，差一倍。
      Human 已在币安界面独立核实 208 即真实可转出额。
      成立仅因 **USDT 是计价单位**——「账户还能动 209 USDT 的价值」对 USDT 而言就是
      「能转 209 个 USDT」。**严禁推广到其他币**：转走 BNB 时它作为抵押品的贡献一并
      消失，而抵押品按**折算率**而非市值计入保证金，「总额 ÷ 币价」必然偏大，
      偏大意味着以为能转、实际被交易所拒。self-check 有断言守这条。
    - **其余币**用 `cross_margin_free`，标签说「**可用**」。它**不等于**可转出额
      （转出还要过统一账户抵押约束）——所以**措辞跟着数据来源走**（`row.kind`），
      两个词对应两个不同的事实。把可用额标成「可转」正是本项最初要修的毛病；
      账户级字段缺失时 USDT 也退回可用额并**同步改口**为「可用」。
    - **为什么放弃实时接口**：币安 `maxWithdraw` 无批量版，一资产一次签名请求。
      **实测**单次往返 0.35~0.90s，18 个资产串行 **9.68 秒**——点开下拉干等 10 秒
      不可接受。瓶颈是延迟不是权重（18 次 ≈ 90，占 PAPI IP 池约 1.5%）。
    - **端点 `GET /api/private-account/max-withdraw` 仍在后端**（批量形状 + 逐资产
      失败隔离 + 去重 + 30 个上限，8 条 wire 测试），**但当前无前端消费者**。
      要精确的 per-asset 可转出额时它是唯一数据源。**已从前端同源白名单移除**：
      若哪天前端又发起该请求，self-check 守卫会立刻抓到——那必须是显式决定，
      不能悄悄回潮。
    - **教训（曾踩）**：拉取触发点一度放在 `renderAssetTransfer` 里，被 self-check 的
      「隐私切换不得 fetch」守卫抓住——面板 60s 自动重渲染、隐私开关等纯本地操作都会
      走渲染函数。**渲染函数不得有副作用。**
    - 未做：`/papi/v1/balance` 的 13 个字段（实测样本）确认**无** per-asset 可转出额；
      账户级只有一个 USDT 计价标量，答不了「BNB 能转几个」。
  - `[OPEN]` Q2 流水勾选「划转」不回显：数据在（2 条 TRANSFER），是显示上限 20 条 +
    全局时间序把它挤到第 33 位；只勾划转能看到、默认基础上加勾看不到。

- **stage `2026-08-06-asset-transfer-live-v1` 已收尾归档（2026-08-07）**：Human 实盘验收通过并
  授权合并推送（`bb47d02..b98ad4f` + 记录提交 `4d0fd44` 均已推送 origin）；证据归档
  `archive/2026-08-06-asset-transfer-live-v1`（archive 分支已推送 origin，含全部
  dispatch/handoff/evidence/status.json）；`ACTIVE.json` 已置 `null`；阶段目录已从工作树移除。
  本阶段交付：资产互转真实划转前后端打通——`POST /api/asset-transfer`（复用
  `universal_transfer`、`client_request_id` 唯一索引幂等、超时/5xx 记 `unknown` 不重试、
  O-1/O-2 无闸门无上限）、前端接线（只认 `body.status`、`unknown` 锁定+「我已核对」解锁、
  成功后刷快照缓存、空态文案改写）、UUID 生成器修复（实盘 `crypto.randomUUID()` 故障→
  随机字节+格式自拼）。全量 1518 passed + self-check 全绿 + 实盘首批三笔真实划转
  `succeeded`。**后续项（开放缺口）**：R1 划转端点不受 `APP_HEDGE_EXECUTOR` 控制
  （接受现状，见 Live Risks）、R3 `pending` 卡死（不修，人工查库处置）、仅验证
  `unified→spot` 成功路径（`spot→unified`/`failed`/`unknown` 三路径仅离线证据）。
- **stage `2026-08-06-hedge-order-close-validation` 已归档（2026-08-06 合并 main + 手动重启）**：
  下单与平仓链路经 Human **实盘显示验收通过**；Human 授权合并 main（`f153cdc..64f0051`
  fast-forward）并手动重启服务（healthz ok，新代码已生效）。修复链
  `ee7ec4f..83c0b8a`：task 05 preflight 本地缓存+平仓简化+预检失败可见暂停（e4d5464）、
  task 06 close+forward 余额读普通现货账户（5388938，THE 600 不再误报可用 0）、
  task 07 视图滚动定位（3006db3）、HTML 多余 `</section>` 删除（10f1f01，f153cdc 残留致
  history-view 被浏览器移出 main——历史仓位表单落页面底部的真正根因）、F-1 徽标 class 互斥
  + 措辞 dry-run→已禁用（83c0b8a）。review-1（opus5）对四个交付 REWORK 仅 F-1 一条
  （dry-run 徽标警示色被 muted 覆盖），修复方案即 opus5 所提方案 a；**Human 决定修复后
  不回审、不安排 review-2，以显示验收为准**；`rework_count` 2。
  不阻塞后续项：N-2（`_close_transfer_done` 只写不清）、N-3（settings 重复渲染）、
  N-4（monotonic 跨进程演进风险）；第三态「live 但凭证为空」（`live_hedge_executor.py:743`
  腿状态未知但徽标显示 live）为独立待决项；`executor_mode_snapshot` 死字段
  （停 2026-07-27）未清理；周期表 `096232b7` first/last_task_id 指向已删任务。
  证据归档：`archive/2026-08-06-hedge-order-close-validation`。
- **持仓周期三功能 + 平仓执行：全部开发完成，Human 验收通过，sonnet5 综合评审 ACCEPT**
  （review-1+review-2 合一；首轮 REWORK 1 处真实 P0 → 修复 + live 回归测试 → 复评 ACCEPT）。
  提交：`97ecb7f`（工作树后续改动见 git status）。
- **数据已清理（从头测试起点，Human 2026-08-06 授权）**：三个库数据记录清空
  （hedge-open-tasks 447 行 / borrow-tasks 1299 行 / ledger-flow 2285 行），保留表结构与
  settings（start_gate/close_gate 配置）；备份 `data/*.sqlite3.bak-clean-20260806-120813`。
  交易所仓位 Human 已全部手工平仓。（服务此后已恢复运行；当前由 Human 手动前台启动，
  见 Live Risks 的 launchd 条目。）
- **前端「假数据 · 预览」设计探针已删除**（真实功能已上线，探针无意义；frontend/index.html
  + self-check.js，2026-08-06）。
- **[领域事实][Human 2026-08-07]** **bStock 类币没有借币市场，故不存在负费率开单。**
  负费率开单（reverse）= **借币卖现货** + 开多合约（卖存货是清仓不是对冲），借不到
  就做不了这条策略。**推论**：一切「reverse + bStock」的代码路径都不可达，那里的
  fail-closed 不是缺陷而是正确行为；`decide_spot_route` 对 reverse 固定走
  `papi_margin` 也因此自洽——借来的币本就在统一账户。
  **纠错留痕**：opus5 曾把 `domain.py:1265` 的资产名错误报为「影响 65 个 bStock 的
  Live Risk」，正是缺了这条领域事实；经 Human 指出后已撤下该条，改并入 1000x 换算
  清单第 8 处（真正受影响的只有 6 个乘数币，且当前被 P0 拦截掩盖）。
- 挂账 follow-up：本地数量口径（X/Y/Z 方案待定）、close_log 利息 ≈U（价格源注入 service
  层）。（「MUUUSDT 现货别名配对」已随 `SPOT_SYMBOL_MAP` 解决：MUUSDT→MUBUSDT 与
  MUUUSDT→MUUBUSDT 是两个并存的真实合约，均已收录；此前「MUUUSDT 系笔误」的判断有误。）

## Live Risks

- `[RESOLVED-BY-BLOCKING][2026-08-07]` **1000x 乘数合约两腿数量口径错配（资金安全）**。
  执行链两腿发的是**同一个** `q_common`（实盘执行器 `dispatch` 里 `send_qty` 两腿共用），
  但 1 张 `1000BONKUSDT` = 1000 个 BONK：现货买 N 个、合约空 N 张 → **净裸空 999N**。
  全链路搜不到任何乘数换算；`est_price` 取的是**现货** symbol 的价格，故 `required`
  与合约腿 minNotional 校验同样错 1000 倍，口径全面错乱。
  **发现路径**：做 B3（两腿差额判定）时需要确认腿量口径，顺藤查出来的。
  **是本轮上游改动打开的口子**：2026-08-07 早些时候加的 `SPOT_SYMBOL_MAP` 让这 6 个币
  （BONK/FLOKI/LUNC/PEPE/SHIB/XEC）第一次通过 `check_symbol_legs` 的现货腿存在性探测，
  在此之前它们建不了任务。
  **无实际损失**：实盘库 `hedge_open_task` 历史币种仅 SNXX/THE/XLM/XVG/WLD，**从未开过**。
  **止血（已实施）**：`create_task` 对 `symbol_match_type == multiplier_strip_alias`
  的 **open** 任务 fail-closed（`multiplier_contract_unsupported`，中文 detail 点明
  「1 张 = 1000 个 X」与「999 倍裸空」）。**只拦 open，close 放行**（三个乘数币的身份
  固化/平仓划转测试用 monkeypatch 关掉建单拦截后继续守护那条路径）。
  **⚠️ 放行 close 不等于 close 安全**（2026-08-07 复核订正）：close 走**同一个**
  `compute_preflight`、同样两腿发一个 `q_common`，自动平仓的腿量同样错 1000 倍。
  放行只是不再额外添堵（历史库并无此类仓位），**真要处置这种仓位得人工去交易所平**。
  最初写的「平仓逃生口必须活着」措辞不准，已订正。
  **未做的资金路径改造见 Open Follow-ups 的「1000x 腿量换算」条**（须 Human 授权）。
- `[RESOLVED][2026-08-07]` **资产互转端点已上线且前后端打通，并经 Human 实盘验收**。
  交付 `036fcd1`（T2 前端）+ `bbe81b0`（UUID 修复轮）后，`POST /api/asset-transfer`
  已完成**首次真实调用验证**：Human 实盘小额试划转成功（`data/asset-transfer.sqlite3`
  只读核实三笔均 `succeeded` 且带交易所流水号——1 USDT tran_id 398029611774、
  50 USDT tran_id 398029775970、另 50 USDT tran_id 398031449101）。实盘首笔曾被后端
  400 拦下（浏览器 `crypto.randomUUID()` 返回非标准值），修复为格式自拼后通过。
  **仍开放**：仅验证 `unified → spot` 成功路径；`spot → unified`、`failed`、`unknown`
  三路径未经真实验证（仅离线断言）。服务重启后启动日志应出现
  `!!! [ASSET-TRANSFER] 划转端点已启用`（表示该口子真的能动钱）。
- `[OPEN][ACCEPTED][2026-08-07]` **划转端点默认即可真实动钱，不受 `APP_HEDGE_EXECUTOR`
  控制（review-1 R1，Human 决定接受现状）**。事实：`POST /api/asset-transfer`（T1
  `1f91241`，`server.py:1244` `_build_asset_transfer_client`）启用条件仅为
  `config.offline=False` + `binance_hedge_api_key` 非空；无独立开关；对照
  hedge 链路 `hedge_executor` 默认 `disabled` 为系统默认安全态且有启动警示（B-4 事故教训）。
  **T1 修复轮 `ce2569e` 已补启动提示**（启用/未启用两分支打印，纯可见性，非闸门——
  未引入任何开关或运行时分支）。可能影响：进程以 disabled/离线启动（降级/测试）时，
  该端点是当时唯一会真实划转的通路；`confirm: true` 是唯一门槛，任何能触达
  `127.0.0.1:8787` 的本地进程可发起真实资金转移。接受理由：Human 2026-08-07 决定
  接受现状（未选独立开关/跟随 executor；生产实际以 live 运行、start_gate 常开为既定
  前提，端点可用与现状一致）。临时限制/观察方式：任何非离线启动均假定划转端点可用；
  实盘试划转须 Human 在场小额执行；全量划转落 `data/asset-transfer.sqlite3` 审计表可
  事后核查。后续复看条件：服务以 disabled/离线模式启动前须先处置本暴露面；或 Human
  与 opus5 讨论后决定加开关/警示。
- `[BY-DESIGN]` **Standing operating premise: the Start gate is kept ON and the
  system runs live.** Human decided 2026-08-03 to leave it open permanently, so
  this is the intended steady state, not an open risk — do not file it as one
  again. Verified at the 2026-08-03 restart:
  `hedge_open_execution_mode mode=live start_gate=true` and
  `borrow_execution_mode mode=live execution_owner=true`, unchanged across
  restarts. **What follows from it, and still holds:** a task moved to `running`
  can send real orders immediately. （**订正 2026-08-07**：原文「no close function
  exists」已过时——平仓功能早已交付，`close_gate` 默认开，2026-08-07 实盘用 close
  任务完成过 SNXXUSDT 全平。仍然成立的是：任务一旦 `running` 就会真实下单。） No agent may create orders,
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
  **2026-08-07 补充线索**：stderr 日志显示失败原因是
  `/bin/bash: scripts/run-server.sh: Operation not permitted` + `getcwd: cannot
  access parent directories` —— launchd 拉起的 bash 拿不到 `~/Desktop` 的 TCC 授权
  （与 `env-zellij-tcc-desktop-block` 同源），故 exit 126。**另注意 `service-control.py
  status` 具有误导性**：它报的 `health 200` 来自手动进程、`commit` 字段读的是当前
  git HEAD 而非运行中进程加载的代码版本——据此判断「服务已是最新代码」会出错，
  须以进程启动时间对比提交时间为准。
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
- `[RESOLVED][OPERATIONS][2026-08-05]` **Live DB schema was auto-migrated by an
  operator service restart (Human-confirmed), ahead of the planned explicit
  migration.** New code (hedge-open position-cycle v1, stage
  `2026-08-hedge-position-cycle-v1`) adds `hedge_open_cycle` (empty table) and
  `hedge_open_attempt.cycle_id` (column + index) to `_SCHEMA`/`_migrate`, which
  `HedgeOpenStore.__init__` executes idempotently on every open. Human restarted
  the 8787 service at ~2026-08-05 14:54 while the implemented code was already
  in the worktree; the restart therefore migrated the live DB: `hedge_open_cycle`
  empty (0 rows), `attempt.cycle_id` column present, 0 rows affected, no data
  change, no backfill data written. Impact: none (idempotent additive DDL; the
  current `prepare_attempt` does not yet write `cycle_id`, behavior unchanged).
  Process deviation vs design v1 §3.4: migration ran WITHOUT a prior live-DB
  backup (`bak-cycle-test-*` is a test copy taken after migration, not a pre-migration
  backup). Remaining gates: live backfill still requires Human authorization and
  must first back up the live DB, then dry-run → `--apply` → row-count verify.
  Evidence: `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/
  hedge-position-cycle-v1-cycle-table-backfill.handoff.md`; audit
  `data/hedge-open-tasks.sqlite3.bak-cycle-test-20260805-145452.audit.json`.
## Merged Position Table — Accepted Limitations (Task 1, merged 2026-08-01)

All three are the same class: **the display asserting something it does not
know.** None costs money directly; each can mislead an operating decision.
**A / B / F4 已于 2026-08-07 全部修复——本段三项至此清零。**
展示层诚实性这一族（单腿敞口、drift、终态文案、交易所无仓）本轮收口完毕。

- `[RESOLVED][2026-08-07]` **A** — ~~the single-leg marker only fires when the perp
  leg is entirely absent, so a partial imbalance (spot 2.0 / perp 1.0) reads as
  "no exposure".~~ 判定改为**两腿差额 > 较大腿的 1%**（`_EXPOSURE_IMBALANCE_TOLERANCE`）。
  一并补上了此前**完全没报**的另一半：旧式子写死 `spot>0 且 perp==0`，只看裸多，
  **裸空（合约腿在、现货腿没有）从来不亮**——那是风险上不封顶的一侧。1% 只吸收
  精度/舍入（两腿发同一个 `q_common`，本应逐位相等），不是「允许 1% 敞口」。
  仍不是权威裁决：per-attempt 内联日志才是。
  **已知边界**：1000x 乘数币两腿单位不同（张 vs 个）会在此误报；开单侧已 fail-closed
  （见 Live Risks 同日 P0 条），腿量换算落地时这里要跟着换算。
- `[RESOLVED][2026-08-07]` **B** — ~~spot balance and drift read the classic spot
  account while the hedge buys into the unified account, so the **drift flag is
  permanently inert**.~~ `drift` 改为**两账户余额求和**后再与任务记账比较。
  根因比原记录更准确：现货腿落哪个账户是 `decide_spot_route` 动态决定的
  （bStock / cap 打满 → 普通现货，其余 → 统一杠杆），所以旧判定对**大多数**币恒为
  假阴性，而非全部。求和是保守方向——同资产的无关持仓可能掩盖真实减少（假阴性），
  但绝不凭空造出持仓，故**一旦报警就说明账户确实少于记账**。
  **它是弱告警，不是对账**（review 2026-08-07 指出的具体假阴性来源）：统一账户侧取的是
  `totalWalletBalance`，**含 UM/CM 合约子钱包**，同资产被当作合约保证金占用的部分也计入
  「持有」。所以「有报警必真少」成立，「无报警即相符」**不成立**——别拿它当对账工具。
  `verified=false` 时不求和、直接 False：两张余额表在那种状态下都是空的，照常求和
  会把「读不到」算成 0 给每一行印假告警——正是 F4 那类错误。
  **2026-08-03 (v4.1) 的旧注记仍成立且仍需警惕**：持仓表加了「杠杆」行让统一账户
  余额可见（合并日实测 `COOKIEUSDT` 统一账户 `2997.0`、普通现货侧 `null`），但那次
  **没有**改 `drift` 本身。展示变丰富 ≠ 一致性检查修好了——这次才是。
- `[RESOLVED][2026-08-07]` ~~**F4 — "exchange has no position" is claimed without
  checking.** 账户读不到时每行仍报 `no_um` 并印「交易所无仓」+ 爆仓暗示——已验证
  账户块里明明含有该持仓时也照印。~~ **已收口**（`184d76e` + `44ab175`）。
  **根因**：`fetch_um_positions` 用 `[]` 表示「读到了，确实空仓」、`None` 表示
  「没读到」，而 `assemble_private_account` 的 `or []` 降级把这个区别抹平了。降级
  本身是对的（UM 挂了不该让余额一起消失），错在丢掉了降级这个事实。
  （原记录说根因在 `snapshot.py:1098/1120` —— 那两个行号已漂且指向无关代码，
  实际在 `assemble_private_account` 的入参降级处。）
  **修法**（Human 定稿的简化方案，比原计划的行级状态更直观）：
  契约层新增 `private_account.unavailable_sources`（判据是**入参 `is None`**，
  不是数组为空——`[]` 恰是「确实空仓」的真值表示，拿它当失败信号会在真正空仓时
  误报，等于把一个假声明换成另一个）；组装根透传进 `account_meta`；持仓表**保留
  表格**、只在标题后加一行红字「未获取到交易所持仓数据，仅展示本地缓存记录」。
  表格保留是关键——本地记账在故障时刻恰恰最有用，它告诉你该去核对哪几个币。
  **三条路径全部收口**：快照未就绪 / `verified=false` / UM 单源失败（第三条此前
  完全无提示）。前端判据含 `verified === false`，因为 merge 在该状态下会**主动
  忽略** UM 数据，哪怕那一路其实读到了。
  **连带修正 `no_um` 自身**（`44ab175`）：已平仓周期行本来就该没有交易所仓位，
  此前它会与「已完全平仓」标记并排印出红色「交易所无仓（可能已强平）」——对正常
  平完的周期是纯误导。现在只对**活跃周期**警示；文案降调为「可能已强平、手工平仓，
  或本地记账与交易所不同步——请到币安核实」，不把推测说成结论。
  **双评审**：kimi ACCEPT；DeepSeek REWORK（三条修复要求已全部收编）。两位**独立
  抓到同一个缺口**（`account_meta` 未桥接），确认那是原计划的硬伤。DeepSeek 另
  独立确认：无第四条路径、两个判据否决站得住、`no_task` 推理成立，并逐条核对 5 处
  `no_um` 回归断言全属真空仓场景（故**原样未动**）。
  计划与评审留档：`docs/planning/f4-exchange-no-position-claim-2026-08-07.opus5.md`
  （含 r3 简化方案与一处立场变更的记录）。
  **操作规矩可以放松但建议保留**：「『交易所无仓』永远不足以证明仓位没了」技术上
  不再必要，但**陈旧数据是未覆盖的独立维度**（10 分钟前的快照 vs 5 分钟前被强平），
  `source_checked_at` 只把时间摆出来供判断。
- `[VOID][2026-08-07]` ~~The read-only smoke run was never executed. Checklist:
  archive `49-`; it is a **hard prerequisite** for the next live activation.~~
  **该门禁经 Human 决定正式作废——实盘启用不再需要任何前置检查。**
  作废理由（不是"暂缓"，是撤销）：它自登记起一次未跑，而这期间实盘开单/平仓/划转
  已发生多次，事实上早被绕过。**一条被反复绕过的「必须」比没有门禁更糟**——它让
  文档里其他真的「必须」一起贬值，后来者无从判断哪条当真。
  与之绑定的「B-6 未覆盖 F4 第三条路径，用前需补」一并作废（F4 本身仍 OPEN，
  见 Merged Position Table 段，但不再有任何门禁挂在它上面）。
  清单原件留在 archive `49-` 作历史，**不再具备效力**；任何人不得再据此声称
  「实盘前必须先跑 smoke」。

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
- `[RESOLVED][2026-08-07]` ~~Task-card pause reasons render **1 of 7** in Chinese —
  the frontend never reads the `pause_reason_zh` the backend already returns.~~
  已交付（`dd0b3e3`）：前端直读 `task.pause_reason_zh`（后端实为 **11 种**
  `PAUSE_REASON_*`，非当初记的 7 种），孤儿表 `HEDGE_PAUSE_REASON_LABELS` 已删，
  后端未给中文时回退英文枚举。连带激活了同日新写的 `-2015` 文案（点名请求 IP +
  「订单未发出」），此前它写在后端却永远显示不出来。
- `[RESOLVED][2026-08-07]` ~~`exposure_alert` is a **dead status** — nothing writes
  it, so the frontend badge can never appear.~~ 整个状态已删除（后端常量 +
  `ALL_STATUSES` + `?status=` 过滤器合法值 + 前端 label/badge/两处判定）。
  它在 breakdown §4.5 把单腿敞口降级为 advisory 后就没有写入方了，删除而非补写入
  是遵循那个决策。实盘库中 0 行该状态，删除零迁移风险。敞口信号 = 持仓表
  `single_leg_exposure`（本轮刚修好，见上文 A）+ per-attempt 内联日志。
- `[RESOLVED][2026-08-07]` ~~A deleted task's `order_state_unknown` settlement
  records `kind=task_paused` with text saying "task paused… resume manually" — it
  was neither paused nor is it resumable.~~ 终态任务（deleted/done/stopped）改记
  `kind=order_state_unknown_final`，时间线投影为
  `overall_result=manual_verification` / `next_action=verify_manually`（前端
  「待人工核实」/「去交易所核实」），文案改为点明「本任务已删除/已完成/已终止，
  状态不再改写、也无法恢复；请到交易所核实这笔订单——系统不会重发下单，也不会
  自动补平」。**只改措辞与词汇**：sticky 状态、腿保持非终态、永不重发三条行为一行未动。
  静态与并发两条路径的测试都已切到新 kind（否则修复只在慢路径成立）。

- `[CLOSED][2026-08-04]` **双栏流水日志 stage 交付完成，Human 决策：直接合并推送**。review-1（REWORK→修复→复审 ACCEPT）+ review-2（ACCEPT）全过，`rework_count` 1/3；Human 授权合并推送（未做前后端联调，推迟至后续 stage）。遗留后续项见下。
- `[RESOLVED][2026-08-07]` ~~**前后端联调未做**。真实 `POST /api/private-ledger/refresh` 连币安拉取从未执行过。~~ **已在跑，实测证据（只读查 `data/ledger-flow.sqlite3` 的 `flow_refresh_runs`，2026-08-07 22:0x）**：`manual` 3 次（最后 17:46:11，interest/income 全 ok——即流水页「刷新」按钮打的那条真实路径）、`scheduled` 38 次（最后 22:01:20，32 次双 ok）、`startup_catchup` 3 次；落库 `interest_rows` 91 行 + `um_income_rows` 94 行。该条自 2026-08-04 起即过时，2026-08-07 核实后关闭。
- `[NOTE][2026-08-04]` **Human 已重启后端服务加载新代码（合并后部署）**。Human 计划在 2026-08-05 00:01（每小时整点后 1 分钟的定时刷新首触发点）观察流水日志页面数据是否自动拉取——这是 fetcher→落库端到端路径（review-2 F-R2-2）的首次活体验证。观察要点：页面「流水日志」看板数据是否出现、状态条「上次刷新」时间是否推进、两栏是否有 error 短码、`coverage` 是否正常（重点 `truncated`/`gaps`/`unparsed_row_count`）。观察结果若有异常，按 Human 决定开后续修复 stage。

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

- `[CLOSED][2026-08-04]` **fake 原型阶段闭环，Human 目视验收通过**。v2 独立流水页（侧栏切换 + 每栏默认最新 20 条 + FAKE 护栏）已提交 `d46523d`。后端任务 A 已恢复路由（glm，从 dispatch 重做）；设计定稿 v1.3（§13.7 独立页布局 + 默认 20 条 + 修订记录）由 Planner 在 C 路由前落定；A → B → C 串行，每份交付后走 review-1 + review-2。
- `[CLOSED][2026-08-04]` **前端布局定稿（Human 验收通过）**。tab-layout v2（panel-actions 双按钮、侧栏三项、market-view 内第二看板）+ 元数据卡片左右排微调（微调由 Human 直接安排 grok 完成，未走标准路由，Bookkeeper 已核验 self-check 全绿），前端最终交付提交 `5613c4e`。下一步：设计 v1.4（Planner）→ 前后端联调（真实 `POST /refresh` 须 Human 授权）→ 统一 review-1 + review-2（A+B+C，provider 隔离：review-1 避 `zhipu_glm`+`xai`，review-2 避两实现作者）。**review-2 模型决定（Human 2026-08-04）**：由默认 Opus 5 改为 **`sonnet5`（anthropic）**，理由为 Claude 额度考量；review-1 仍为 kimi（moonshot）。**kimi 额度（Human 2026-08-04 告知）**：`moonshot` 额度 **2026-08-07 之后可用**；在此之前 review-1 若需路由，改用 `deepseek`（`deepseek`）或 `codex`（`openai`），8 月 7 日后可切回 kimi。
- `[RESOLVED][2026-08-07]` **借币利息流水已实现并在跑**（`ledger-flow.sqlite3`
  `interest_rows` 91 行）。此前记录的「未实现」已过时。API 侦察结论仍有效：源 =
  `GET /papi/v1/margin/marginInterestHistory` ≡ `sapi/v1/margin/interestHistory`
  （同 `txId`/`interest`/`total`），1h 计息（`PERIODIC`+`ON_BORROW`），累计 =
  `Σ rows.interest` 按 `txId` 幂等；`balance.crossMarginInterest` 只是未付欠息、
  非历史累计。证据 `reports/api-samples/2026-08-borrow-interest-history-recon-v1/`。
- `[RESOLVED][2026-08-07]` **UM 资金费/手续费流水已实现并在跑**（`um_income_rows`
  94 行，实测含 FUNDING_FEE/COMMISSION/REALIZED_PNL/TRANSFER）。此前「未实现」已过时。
  API 侦察结论仍有效：PM 路径是 `GET /papi/v1/um/income`（本 key 打 fapi 得 `-2015`），
  按 `(incomeType, tranId)` 幂等、升序、limit≤1000、权重 ~30。证据
  `reports/api-samples/2026-08-um-income-funding-recon-v1/`。
- `[RESOLVED][2026-08-07]` ~~**No automated check binds the frontend field names to
  the backend ones.**~~ 已交付 `backend/tests/test_frontend_field_binding.py`（4 用例）。
  **锚定链**：`test_hedge_api::test_positions_shape_after_fill` 用**真实 HTTP 响应**钉住
  `_POSITION_KEYS == GET /api/hedge-open-positions 的字段集` → 新测试钉住
  `前端引用 ⊆ _POSITION_KEYS` → 合起来即「前端读的每个字段后端都真的发」。
  另一条方向相反的用例钉 `merge 层产出 ⊆ _POSITION_KEYS`，防「后端加了字段但契约常量
  没跟上」——merge 是纯函数最易被单独改，而 API 那条要跑完整 HTTP 链路才覆盖得到。
  **实现踩到的坑**：权威源最初取 `merge_positions` 的产出，结果误报两个**正常工作**的
  字段——`stats_incomplete` / `borrow_interest_usdt` 是 handler 在 merged rows 之上追加的
  （`server.py:1125/1171`，周期费率利息现算），故 merge 层产出是 wire 契约的**真子集**。
  **失效防护**：检查靠正则从 `index.html` 抓 `p.xxx` / `posRow.xxx`，一旦函数改名或结构
  变动抓空，主断言会**因集合为空而通过**——所以每个消费点钉了引用数下限
  （`_POSITION_CONSUMERS`），抓空即红。**新增消费变量必须加进那张表**，否则不被覆盖。
  **已验证会红**（不是写完就算）：注入前端改名 `p.um_mark_price`→`p.um_markprice` 主断言红；
  注入后端改名 `row["um_mark_price"]`→`row["um_markprice"]` 反向断言红；两次均已还原。
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
- `[RESOLVED][2026-08-07]` **现货/合约 symbol 别名已统一（纯表方案：SPOT_SYMBOL_MAP）。**
  原「MUUUSDT 案例」（2026-08-05）已由 opus5 纯表方案解决并推广：`normalize.py`
  `SPOT_SYMBOL_MAP` 71 条（65 bStock + 6 乘数，2026-08-07 最新 exchangeInfo 实测生成），
  `resolve_spot_leg` 改为 `exact → 查表 → (None,None)`（删除全部字符串猜测，fail-closed：
  未收录即无现货腿，宁无腿不错腿）；预检 filters/探测、快照 spot.base_asset、展示
  asset_map、平单环消费同源真值。**勘误**：MUUSDT 与 MUUUSDT 是两个**都真实存在**的合约
  （→ MUBUSDT / → MUUBUSDT，verify 证实并存），此前「MUUUSDT 为笔误」判断有误；
  旧规则两个真实缺陷已被纯表取代（`BUSDT` 合约 base=B 会被 B 后缀猜测误配到
  BBUSDT/BounceBit；`base[4:]` 对 `1000000MOGUSDT` 剥成 `000MOG`）。维护：
  `scripts/check-spot-symbol-map.py --verify/--emit`（STALE/MISSING/SUSPECT 三类，
  SUSPECT 绝不自动收录）。测试：后端 1533 passed + self-check EXIT=0 + verify 退出码 0。
- `[RESOLVED][OPERATIONS][2026-08-05]` **COOKIEUSDT 平仓单腿事故（已修复并实盘验证）。**
  事件：首次实盘平仓时，forward close 现货 SELL 被 `decide_spot_route` 的
  collateral-cap 预检误导到**普通现货账户**（`/api/v3/order`），而现货实际在**统一账户**
  （开仓走 `/papi/v1/margin/order`）→ `-2010 insufficient_funds`；合约腿已平（reduceOnly
  FILLED）、现货单腿（1000 COOKIE 留在统一账户），任务 paused（Human 确认保持暂停）。
  根因：平仓任务复用开仓路由规则，close 未区分账户 + create/fresh preflight 路由漂移。
  修复链（全部完成并实盘验证，Human 2026-08-05 验收通过）：① `close-spot-sell-redesign`
  （forward close 固定普通现货账户 + 发单前一次性万向划转补足 + 复检 + fail-closed + USDT
  回流；reverse 维持统一账户；`POST /sapi/v1/asset/transfer` 白名单 type 冻结；API key 划转
  权限已确认）；② 划转前统一账户余额检查 + 失败日志带交易所详情（`query_unified_free` 修复
  `/papi/v1/balance` 顶层数组解析）；③ **close 完成判定重构**（Human 拍板：close 任务从
  running 变其他状态必须先走合约无仓核实——`_worker_round` 核实优先 + resolve suppress_done
  + 部分平 done 语义）；④ 前端提前量检测（总量=单次×次数 vs 统一账户+合约持仓，强制拦截零请求）。
  数据修正：COOKIE 周期已手动补关（`closed_at_us` + close_reason=manual_verify）+ close_log
  补记（合约/现货开平均价、成交量、资金费、滑点 %）。**持仓表口径决策（Human 2026-08）**：
  只显示「未平仓周期」——`aggregate_positions` 加 `(cycle_id IS NULL OR closed_at_us IS NULL)`
  过滤，已平仓标的从根源排除（只在历史仓位页 close_log 呈现）。**本地数量口径保持现状**
  （累计开仓，close 腿扣减方案 B 已回退——Human 决定暂不改）。挂账 follow-up：本地数量与
  交易所脱节（手工/强平不可记账）的整改方案待 Human 定（X 交易所权威 / Y 手工录入 / Z 现状）。
  证据：`reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/`（close/redesign handoff +
  本条目时间线）。
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

- stage: `2026-08-06-asset-transfer-live-v1`
- archive_ref: `archive/2026-08-06-asset-transfer-live-v1`
  (delivery range `bb47d02..bbe81b0` + 各轮封存；基线 `8e17027` + T1 `1f91241` + 修复轮 `ce2569e` +
  T2 `036fcd1` + UUID 修复轮 `bbe81b0`；review-1 deepseek 兼任（Human 越门）R1-R5 → R1 接受现状、
  R2 转 T2、R3 不修、R4/R5 修复；无 review-2（Human 越门）；T1 `rework_count` 1、T2 `rework_count` 1)
- recorded_completed_at: `2026-08-07`
- scope delivered: 资产互转真实划转前后端打通——`POST /api/asset-transfer`（复用
  `universal_transfer` 本体零改动、`client_request_id` 唯一索引幂等（币安该端点无幂等键，重放零外发）、
  超时/5xx 记 `unknown` 不重试、O-1/O-2 无闸门无上限、R5 状态码人话映射 418/429→`unknown`）；
  前端接线（UUID 幂等键前端生成、只认 `body.status`、`unknown` 锁定表单+「我已核对」人工解锁、
  `failed` 不锁定、成功后刷快照缓存、空态文案改写）；UUID 生成器修复（实盘 `crypto.randomUUID()`
  返回非标准值→随机字节+版本/variant 位与格式自拼，self-check 注入坏实现回归）；全量
  1518 passed + self-check 全绿 + 实盘首批三笔真实划转 `succeeded`（1+50+50 USDT 带交易所流水号）。
- closing note: Human 2026-08-07 实盘验收通过并授权合并推送（`bb47d02..b98ad4f` + 记录提交
  `4d0fd44` 推送 origin）；三笔交付均无 dispatch（Human 直接指示，越门如实记录）；bookkeeper 兼
  review-1、无 review-2（Human 越门，配额耗尽原因）。后续项：R1 划转端点不受 `APP_HEDGE_EXECUTOR`
  控制（接受现状，启动有提示）、R3 `pending` 卡死（不修，人工查 `data/asset-transfer.sqlite3` 处置）、
  仅验证 `unified→spot` 成功路径（`spot→unified`/`failed`/`unknown` 三路径仅离线证据）。
- previous stage: `2026-08-06-hedge-order-close-validation`
- archive_ref: `archive/2026-08-06-hedge-order-close-validation`
  (delivery range `ee7ec4f..83c0b8a` 修复链 + 收尾；01/02/03 + 05 + 06 + 07 + HTML 标签修复 + F-1 徽标修复；
  review-1 opus5 对四交付 REWORK 仅 F-1 一条 → 修复后 Human 决定不回审、不安排 review-2，以显示验收为准；`rework_count` 2)
- recorded_completed_at: `2026-08-06`
- scope delivered: 验证下单/平仓核心链路 + 修复小 bug 全链——01 SPOT_ONLY 路由修复、02 开单前自动设杠杆、03 传输层异常证据保全 + 移除 dry-run 假成交模式（RecordTransportExecutor 移出生产）、05 preflight 改读本地缓存（2h/5min/10min 陈旧上限，restricted_asset 唯一 fail-closed）+ 平仓校验简化（平完判定收敛 + 划转去复检）+ 预检失败可见暂停（含失败读名）、06 close+forward 平仓余额读普通现货账户（THE 600 误拦修复）、07 视图切换滚动定位、HTML 多余 `</section>` 删除（history-view 落底根因）、F-1 徽标 class 互斥 + 措辞 dry-run→已禁用；全量回归 1467 passed + self-check 全绿。
- closing note: Human 2026-08-06 实盘显示验收通过（下单与平仓），授权合并 main（`f153cdc..64f0051` fast-forward 推送）并手动重启服务（healthz ok）；Human 决定修复链只做一轮 review-1（F-1 修复后不回审），不安排 review-2。后续项：N-2/N-3/N-4、第三态「live 凭证为空」（`live_hedge_executor.py:743`）、`executor_mode_snapshot` 死字段、周期表 `096232b7` first/last_task_id 指向已删任务。
- previous stage: `2026-08-04-dual-ledger-flow-log-v1`
- archive_ref: `archive/2026-08-04-dual-ledger-flow-log-v1`
  (delivery range `dc4cc6d..0c9c4de` + 收尾提交；A/B/C+前端最终+修复；deepseek review-1 REWORK→修复→复审 ACCEPT、sonnet5 review-2 ACCEPT；`rework_count` 1)
- recorded_completed_at: `2026-08-04`
- scope delivered: 双栏流水日志——私有账户 panel-actions 双看板按钮（费率行情|流水日志）、侧栏三项、流水为费率行情页内第二看板（每栏默认最新 20 条、元数据卡片左右排）；后端取数（白名单 13→15 + 两单页 fetcher）+ 本地 SQLite 幂等账本 + 拉取编排/整点调度 + `GET flow-log`/`POST refresh` 路由 + 增量统计与 coverage 诚实性护栏；全量回归 1351 passed、self-check 全绿。
- closing note: Human 2026-08-04 授权直接合并推送（未做前后端联调，推迟至后续 stage 一并修复）；联调/端到端验证、微信通知、开单任务联动列为后续项。**（2026-08-07 更新：联调已自然完成——`flow_refresh_runs` 实测 manual 3 次 + scheduled 38 次全在跑；微信通知与开单任务联动经 Human 决定**取消**，不再作为后续项。此行保留为当时的归档事实。）**
- previous stage: `2026-08-03-hedge-status-account-refresh-v1`
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
