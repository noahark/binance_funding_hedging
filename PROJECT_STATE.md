# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-08-18)

- **[2026-08-18 Human 直接驱动，无 stage] 统一账户「已借未开单」资产卡提前一行：**
  已借本金 > 0、且当前没有对应开单（同快照 UM 仓量为 0、本地也没有未完全平仓周期）
  的资产卡单独放在统一账户余额第一行，名称后追加红字「未开单」。提醒：借了要么
  开单要么还掉，利息一直在计。UM 源没读到时不标（不把「没读到」说成「没开」）；
  只欠息、本金已还清的卡仍走正常行。纯前端，服务不用重启，刷新页面即可。
  验证：`node frontend/self-check.js` 全绿。当时实盘快照：SNX 已借 50.11 /
  AVNT 已借 100 无 UM 仓（应上第一行）；INJ 已借 8.00 且有 UM 仓（应留在正常行）。
  未授权提交、部署、重启或实盘操作。
  **同日续**：现货账户余额按同一两行格式，第一行固定 BNB → USDT（快照里有才展示，
  小额不过滤），第二行其他可见资产。快照没这两行时不编造 0 卡。
  **同日再续**：有已借本金的统一账户卡追加市场表同口径「日利息」；市场表原「日借币」
  子行同步改名。只欠息、本金已还的卡不展示该行。
  **同日再续**：上述有借币卡同时展示持仓表资金费率列的「实时」与「日净」（同源
  `last_funding_rate` / `net_daily_yield`，3 位小数；无日净则不占行）。

- **[2026-08-17 Human 直接驱动，无 stage] PM 权益字段口径修正 + 缺源「部分和标红」规则：**
  「总资产估值 / 统一账户净资产 / 杠杆率」三张卡由 `accountEquity`（按抵押率折算的风控
  口径）改取 `actualEquity`（与币安 App 同口径）。`accountEquity` 字段保留在快照里不删。
  **同轮按 Human 提出的规则统一缺源展示**：能算部分和的卡（总资产）缺源时展示已读到的
  部分并**标红点名缺了谁**，单值卡（统一账户净资产 / 杠杆率）缺则 `—`；现货卡改为按
  `unavailable_sources` 判缺（后端求和得 0 与「真的空仓」不可区分）。
  ⚠️ **两处口径断裂，与本轮之前的历史记录对账会有台阶**：`total_value_usdt`
  `571.13 → 579.64`（+`8.51`）、`leverage_ratio` `3.07207789 → 2.98142928`。
  契约已标注日期、方向与量级。
  ⚠️ **一条既有 test-asserted 契约硬规则被废**：`total_value_usdt = Σ(unified
  totalWalletBalance priced) + Σ(spot free+locked priced)`（anti-double-count 公式）
  不再成立——unified 侧改取净值，毛额不再进总额。毛额仍在 `unified_wallet_value_usdt`
  字段上单独报，原测试的本意（um/cm 不重复计入、`crossMarginFree`/负债不移动毛额）已
  移到该字段上继续守。
  **删掉了钱包毛额回退链**：此前统一账户读不到时总额退到毛额。**重启后实测揭穿了一个
  此前想当然的方向判断**——毛额 `100.68845086` 对净值 `191.41755452`，毛额只有净值的
  一半多，旧回退会把总资产**少报约 90 USDT**，在页面上读起来像凭空亏了一笔（此前文档
  一度写成「毛额含借币会报大」，方向是反的，已改）。两者是不同口径的量、差距既不小
  方向也不固定，互相顶替就是「假声明」（2026-08-07 修过三次的同一形状）。同轮删掉
  `_project_pm_account_summary` 内那段死的 leverage 计算（唯一调用方传 `total_value=None`，
  条件恒假，真正生效的是 assemble 里那处）。
  **评审**：实施前设计评审两家（`grok-4.6` / `claude-glm`，均 headless 只读）结论同为
  `ACCEPT-WITH-CHANGES`，其引用经本会话逐条复核（grok 有一处函数名指认偏差、一处
  百分比口径争议，均不影响结论）。两家在「缺失时要不要退回 `accountEquity`」上冲突，
  按 grok 判不退，Human 随后提出更彻底的部分和规则并据此实施。
  **这是设计评审，不是正式 Review-1/Review-2——两者本轮都未做。**
  材料：`docs/planning/pm-equity-field-fix-2026-08-17.review-request.md`。
  **改动三（交付后评审补入）：现货源缺失时不再给出杠杆率。** 此前那种情况下分子退化成
  净值本身、比值恒为 `1.00000000`——一个看着完整实则无信息的数字，还紧挨着一张已标红说
  「缺现货账户」的总资产卡。现在总额只要是部分和就不给比值（前端本就把 null 显示为 `—`，
  故只改后端一处）。该缺陷由 grok 评审发现并经本会话独立复现。
  验证：`test_private_account_v1.py` `113 passed`（含新增 4 条）；`node frontend/self-check.js`
  全绿。新增后端 4 条测试 + 前端 1 个测试块（4 个场景、14 个 throw 点），
  **9 次变异验证全部改坏即红**。
  ⚠️ **测试分层边界（勿误读）**：self-check 的杠杆率断言守的是「后端给 null 时卡面渲染成
  `—`」，其夹具写死 `leverage_ratio: null`——**后端若改回在缺源时算出 `1.0`，self-check
  照样全绿**。守住那一侧的只有 pytest 的 `test_..._no_leverage_when_total_is_partial`。
  **服务重启两次**：`36213` → `24679`（口径改动）→ **当前 `45346`**（`22:23:47` 启动，
  含杠杆率修复；`127.0.0.1:8787`，`readyz` 200，live + `start_gate=true`）。两次重启前
  均只读确认无 running 任务（40 done / 12 deleted / 1 stopped）、订单腿全
  `TERMINAL_RECORDED`。
  **实盘验证只覆盖「源齐全」一条路径**：`45346` 实测
  `spot 385.95344935 + actual 193.47983513 = total 579.43328448`、`leverage 2.99479935`，
  两家评审各自独立取数同构。**缺源行为无实盘证据，仅由单测覆盖。**
  ✅ **Human 已完成「面板 vs 币安 App」人工复对（2026-08-17）：与 App 大致一致，改动达成
  目标。** 残余细微差异归因于 **USDT/USD 计价波动**（App 侧按 USD 口径，本仓一律折 USDT），
  属预期噪声，不再追。这同时终结了 claude-glm 提的替代解释——曾担心 App 显示的是钱包毛额，
  而实测毛额 `100.68845086` 与 `actualEquity` 差近一倍，不可能混淆。
  ⚠️ 早先记录的 `total 579.45913371` 那组数出自 `24679`，即**修复前**的进程。
  **注**：`SIGINT` 杀不掉 nohup 脱离终端的服务进程，须用 `SIGTERM`；第二次重启 `readyz`
  从 503 到 200 等了约 75 秒（首次仅几秒），属正常初始化。
  **交付后代码评审两轮**（`grok-4.6` + `claude-glm`，均 headless 只读，四份结论全为
  `ACCEPT-WITH-CHANGES`，引用经本会话逐条复核属实）：
  round 1 — 两家共同指出两处文档失准（前端注释仍写「毛额会报大」、本条曾写「未重启」），
  grok 独有发现杠杆率缺陷（已修，见改动三）+ 三处过时注释（已同步）。
  round 2 — 两家共同指出**契约/schema 的 `leverage_ratio` 描述与实现打架**：原文写
  「两个操作数为正就相除」，而现货缺源时两者恰恰都为正、代码却故意不出比值；grok 的话是
  「以后若有人按契约『修』代码，会把 `1.00×` 请回来」。已改两处并加显式禁令。
  grok 另建议补一条「无关源丢失不该影响杠杆率」的回归测试（防止有人把 `unified_balances`
  写进完整性判据），已补并变异验证。
  材料 `docs/planning/pm-equity-field-fix-2026-08-17.review-packet.md`（第 6 节含两轮处置）。
  **仍未做正式 Review-1/Review-2**（本轮无 stage）。

- **[2026-08-16 Human 直接驱动，无 stage，Human 授权提交推送] 借币利息展示 + 未还利息进快照：**
  一轮连续的 UI/契约小改，全部直接在 `main` 工作区完成，未走 stage 流程（Human 逐项确认
  后授权推送）。交付内容见本条下方与 Open Follow-ups 前两条。
  **事后补做 Review-1（grok-4.6，headless 只读，区间 `75a2e0a..6d5b4fb`）：`ACCEPT`，无
  REWORK 发现**；两条 in-range 文档发现已修（`snapshot.schema.json` 的 `total_debt_usdt`
  描述、`_project_pm_account_summary` docstring 仍写「只加本金」）。其引用的每条事实经
  本会话逐条复核属实。**未做 Review-2**（按 §8 展示/账务口径属 HIGH_RISK，Human 知悉后
  决定暂不做）。
  ⚠️ **评审带出的两条检索教训（下次先查再推理）**：
  (1) `interest_rows` 表有 **`principal` 字段**——币安在每笔计息记录里直接报了计息本金，
  本会话此前全靠 `borrowed` 与资金流水反推。实值：SNX `2026-08-16 00:00` principal=100、
  `01:00` principal=50.10709571（还款后），且**还款前从未变成 100.107…**，反证「小时计息
  不会自动资本化」；XLM 有同形状的 `195.10900819`。这是比本会话原有证据更强的直接证据。
  (2) `reports/api-samples/2026-08-borrow-interest-history-recon-v1/`（2026-08-04）**早已
  写明** `crossMarginInterest` = "current outstanding unpaid interest (NOT historical
  cumulative)" 及「曾还息后与 Σ history 分叉」。本会话 grep 时只扫了 `backend/`/`docs/`/
  `schemas/`，漏了 `reports/api-samples/`，白推理数轮。
  验证：后端 `1893 passed`（`test_private_client.py::test_urlopen_only_in_designated_http_clients`
  为**本轮之前即已存在**的失败，`git stash` 验证过，与本轮无关）；`node frontend/self-check.js`
  全绿，新增断言均做过变异验证（改坏即红）。
  **服务由模型按 Human 明确授权重启过两次**（Human 出门期间授权「停旧服务起新服务」）：
  旧 PID 27940 → 32279 → **当前 36213**，`127.0.0.1:8787`，`readyz` 200，跑的是本轮后端代码。
  重启前只读确认过无 running 任务（37 done / 11 deleted / 1 paused / 1 stopped）、无在途下单。
  启动方式改为 `nohup bash scripts/run-server.sh` + `disown`（脱离终端，Human 关终端不受影响），
  日志在 `~/Library/Logs/funding-hedging/server.{stdout,stderr}.log`。**仍非 launchd 托管。**
  未授权部署、创建任务或实盘下单。
  ⚠️ 期间观察到一笔**非本会话发起**的 INJ 还款（`borrowed` 10.0 → 8.00109129），模型未碰任何
  下单/还款接口，来源未确认（Human 手机操作或自动任务），如非预期需查。

- **[2026-08-15 Human 授权合并并推送] 平滑平仓 V1 (P1+P2) 已合并 `main`：**
  以 `--ff-only` 合并 `stage/2026-08-14-smooth-close-orders-v1`，`main` 与 stage tip 同为
  `2cc6cde`；产品 delivery 为 `f95577f`（前端串联）与 `6f6c729`（后端 F1 修复）之上的
  `7d3fe60..f95577f` 区间。stage 分支与 `main` 均已推送 origin。
  **评审覆盖的真实情况（合并时具名接受）**：P2 前端串联区间 `6f6c729..f95577f` 有
  Review-1（gemini-3.1-pro）+ Review-2（opus5）双轮 ACCEPT；**后端 P1 区间
  `7d3fe60..c4ae93a` 只有一次 Review-1（grok-4.6，结论 REWORK/F1），F1 修复提交
  `6f6c729` 未经独立评审，后端从未做过 Review-2**。合并前补做过一次非正式初评
  （gemini 3.7 Flash，纯文本不落档，21 处锚点经 Opus 5 逐条复核属实，无新发现），
  但它是按清单核对而非开放式勘探。Human 知悉后决定合并。
  另注：P2 的 Review-1 由本 stage 的 Bookkeeper 会话自行执行并宣布 ACCEPT，与
  `agents/roles.md` 的「Bookkeeper 不得宣布评审接受」「评审须 fresh read-only session」
  不符；因该区间随后由 opus5 独立 Review-2 覆盖，未返工。
  合并时服务仍在运行（PID 38254，127.0.0.1:8787）；**新后端代码要下一次重启才会生效**。
  未授权部署、由模型启动/重启服务、创建任务或实盘下单。

- **[2026-08-13 Human 授权合并并停服] 平滑开单 V1 已合并本地 `main`，服务等待 Human 手动启动：**
  `smooth/v1-fullstack` 已以 `--ff-only` 合并，产品 delivery 为 `ad8c631`，完整阶段归档 tip 为
  `d404e20`。合并前只读确认开单 active=0、未结算 attempt=0、未终态订单腿=0、借币 active/
  unresolved=0；从 smooth worktree 运行的 PID `23396` 于 `2026-08-13 21:15 CST` 收到 `SIGINT`
  并走服务清理后退出，`127.0.0.1:8787` 已不再监听。主仓 `.venv` 已有 `ccxt==4.5.64`；下一次服务
  启动由 Human 在主仓本地执行。fresh Claude-GLM 累计 Review-1 为 ACCEPT；fresh Opus 5 最终
  Review-2 技术结论为 REWORK，唯一 finding F-A 已复现并由 Human 按下方具名风险接受、本轮不修。
  未授权 push、部署或由模型启动服务、创建任务、下单。

- **[2026-08-12 Human Fast Direct] 两次直接代码交付已推送：** `31d7ae6` 取消私有读取在 429/-1003 后的 0.5 秒立即重试；`0a0984c` 将空库首次利息/收入流水回补窗口改为 1 天。两项均已通过定向测试，接口/行为文档已同步；下一次从当前 main 启动时会一并加载。

- 当前服务已按 Human 要求停止、仍采用 Human 手动前台启动方式；统一账户手动还款已最终验收，
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

- `[RESOLVED-BY-DELIVERY][LIVE-OBSERVATION][2026-08-13]` **首笔真实平滑任务已成交；该次验收发现的任务卡刷新与放行审计缺口已修复。**
  Human 页面验收创建任务 `36951966-6942-43e3-833c-99606ca3fae5`
  （`1000CATUSDT`、forward、smooth、阈值 `+0.05%`、单次 `5000`、目标 `1`）。因全局
  Start gate 已开启，建卡后自动进入 `running` 并开启 gate，故“启动”按钮置灰是运行态按钮矩阵，
  不是启动失败；`2026-08-13 16:27:54 CST` 以 `smooth_pass_reason=market` 放行，现货 BUY
  `5000 @ 0.00172`、合约 SELL `5000 @ 0.0017120` 均 FILLED，任务 `done`。账户读模型随后
  显示现货 `+5000`、UM `-5000`、`single_leg_exposure=false`、`drift=false`；该 symbol 是
  exact `1000CAT` 资产，不是当前表内的 multiplier alias。
  **已证实的 UI 缺陷：**动态盘口块数据只由任务日志 GET 填充；新建 smooth 任务不会自动展开/
  拉取日志，因此卡片先显示“现货/合约 数据不完整”，即使后台 provider 已 live。手动展开日志后
  同源 GET 显示两侧 `live`，不是行情订阅故障。D17–D19 重启后，Human 于 `2026-08-13 18:50`
  启动 reverse smooth 任务 `b3ebc0fa-cc61-46f7-90da-85c1af29a596` 再次复现：启动当页可读，
  但浏览器刷新会清空仅存内存的 `hedgeLogExpanded`，运行卡仍渲染动态盘口块却不再请求
  `GET /api/hedge-open-logs?task_id=…`，因而永久误报两侧“数据不完整”；后端同一时刻两侧均为
  `live`。手动展开一次日志后卡片立即恢复真实价格，证明根因是前端刷新触发条件，不是 WebSocket。
  **审计观察：**最终成交均价折算 forward spread 约 `-0.465%`，与 `+0.05%` 阈值相反；当前
  attempt 只记录 `market`，不持久化放行瞬间两侧 bookTicker，故不能区分“放行后约 0.3–0.4 秒
  内行情跳动一档”与“放行快照本身异常”。D15 明确取消发单前联网复核，所以成交价偏离本身不证明
  gate 算错，但缺少放行快照使实盘不可审计。临时边界：UI 修正前不要把初始“数据不完整”解释成
  worker 未运行；也不要再创建平滑任务做纯展示验收——Start 开启时它会自动运行并可能真实成交。
  后续交付已把 smooth 新卡改为 `paused + awaiting_manual_start`、running 卡纳入统一 2 秒刷新，并持久化
  同次放行快照与 gate→两腿 client-call monotonic 分段；当前 PID `23396` 已加载这些修复。上文保留为
  历史触发证据，不再作为当前 UI/审计限制。

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

- `[RESOLVED-BY-BLOCKING][PERMANENT][2026-08-07 / 封存 2026-08-15]`
  **1000x 乘数合约两腿数量口径错配（资金安全）**。
  ⚠️ **2026-08-15 更新：换算需求已由 Human 决定不做，下述 fail-closed 拦截由「止血」
  转为「长期终态」。** 相关脚手架（`PAUSE_REASON_MULTIPLIER_CLOSE_UNSUPPORTED` 常量/
  注册/文案、测试夹具 `_allow_multiplier_open`）**全部保留，不得作为死代码清理**。
  重启说明见 `docs/planning/leg-unit-size-conversion-2026-08-15.CLOSED-lessons.md`。
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

- `[CLOSED-SETTLED][2026-08-17]` **`totalWalletBalance` 不含 UM/CM 合约子钱包——已定论，
  推翻契约的长期说法。** 不需要新接口，单份实盘快照反证即可：毛额 `100.82` − 负债
  `52.48` = `48.34`，而净值 `actualEquity` 是 `187.97`，**净值比它多 `139.63`**。
  权益不可能超过它据以计算的资产，所以毛额必然漏了这部分——即当时 9 个 UM 持仓占用的
  保证金与浮盈。逐行核对佐证：所有非零行都是明面持有的币（USDT/BNB/1000CAT/SNX/WLD/
  AVNT），没有一分合约保证金。
  **影响**：当前**无**——毛额自 2026-08-17 起不进任何总额，前后端零消费者。但它是一个
  **部分钱包视图**，不是「统一账户里的全部」：**做对账、算持仓成本、回答「里面一共多少钱」
  都不能直接用它**，必须另加合约钱包。这也量化了删除旧回退链的必要性——退到毛额会把总额
  少报三位数 USDT，页面上读起来像凭空亏了一笔。
  已同步 `docs/api/public-market-contract.md`、`backend/domain/snapshot.py` docstring、
  `test_private_account_v1.py` 注释。
  **未做**：字段本身零消费者且语义易误导，可考虑直接删除，但那属契约破坏（schema
  `required`）——归入既有的死代码清理轮（见 `hedge_open_fill` 条目），不单开。

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

- `[CLOSED-NOT-DOING][2026-08-15]` **1000x 乘数币适配：Human 决定不做，需求封存。**
  **活文档同步已完成**（`AGENTS.md` 收口义务）：`docs/product/PRD.md` §2.2 / §11.3、
  `docs/symbol-mismatch-analysis.md` 状态头、`docs/planning/duplicate-concept-
  consolidation-2026-08-15.opus5.md`（其「改动二并入乘数轮」的去向已作废，须单独立项）。
  `docs/api/public-market-contract.md` **无需改**——其 `multiplier_strip_alias` 相关
  描述是现行行为的事实陈述，未随本决定变化。
  **重启前必读 `docs/planning/leg-unit-size-conversion-2026-08-15.CLOSED-lessons.md`**
  （封存说明 + 五轮评审经验 + 已知漏项 + 重启顺序）。
  **代码零改动**，六个币仍被三道 fail-closed 挡着，**零风险敞口——这是终态，不是止血**。
  停的理由是投入产出比，不是设计不成立：五轮评审后三方中两家确认「设计本身逐点核对
  全部成立」，三个阻塞项全为清单完整性与文档自相矛盾。实测收益边际贡献 **1.72%**，
  其中 74% 集中于 `1000XEC` 单一标的，`1000SHIB` 在 500 个结算周期内从未达阈。
  ⛔ **`...opus5.md`（r5）与 `...column-inventory.md` 的清单已知不全**（至少漏 7 个展示格
  + `service.py:385`/`:1505` 的 `residual` 一个**计算路径**），**不要照其开工**。
  已交付并合并的两项纯技术债与本需求解耦、**不必回退**：发单数量三处装配点收敛为
  `domain.resolve_send_qty`（`3dc74f5`）、websocket 纯度扫描假阳性修复（`11be65f`）。
  测试基线 **1940 收集 / 1939 通过 / 1 已知失败**。

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

- `[CLOSED-NOT-DOING][2026-08-15]` **1000x 腿量换算——需求已封存，下文保留供重启参考**。
  Human 于 2026-08-15 决定不做；三道 fail-closed 拦截转为长期状态。
  **下文的「必须一次改齐的八处」已被五轮评审证明不全**（真实面为约 32 个展示格 +
  多个计算路径），**重启时勿照抄**，改读
  `docs/planning/leg-unit-size-conversion-2026-08-15.CLOSED-lessons.md` §6。
  以下原文保留仅供追溯：

- `[SUPERSEDED-BY-ABOVE][2026-08-07]` **1000x 腿量换算——未做的资金路径**。
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

- `[ACCEPTED][OPERATIONS][2026-08-03, decided 2026-08-15]` **手动前台模式下日志不落固定
  文件——已知代价，不修。** launchd 曾把 stdout/stderr 写到
  `~/Library/Logs/funding-hedging/`；改手动前台后日志只在启动它的那个终端里（2026-08-03 那次
  甚至落在临时的 Claude session scratchpad）。随「本地不修 launchd」的决定一并接受（见 Live
  Risks 同条）。**操作口径**：从 operator 终端启动以便日志留在可回看的窗口；需要留存就自己重定向
  （`scripts/run-server.sh > 某文件 2>&1`）。服务器部署由 systemd 的 journal 接管，届时自然消解。
- `[OPEN][RESIDUAL]` **UM drain 可在 `cumulative_quote` 未知时把 FILLED 腿判为终态。**
  该路径会保留 `avg_price` 但缺 quote，导致该周期的合约均价与开/平滑点显示 `—`；这是
  fail-closed，不影响订单或持仓且不臆造数值。重开条件：出现真实历史周期命中该形态，或 Human
  决定统一 drain/inline 终态规则；届时应同批评估 quote 缺失时用 `avg_price × qty` 加权的口径。
- `[OPEN][RESIDUAL]` `_rate_limit_stamp_pending` is in-process: a restart mid-stamp
  costs one failure count (pauses one early, fail-closed). Fix = a new column.
- `[OPEN][RESIDUAL]` The money-zero tripwire is a speed bump, not a proof: five
  evasions + `fee_amount` outside the money names. DEC-2026-07-30-001.
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
## Next Priority

- **No active stage.** Current priorities (detail in the sections above):
  1. 服务器部署（systemd unit）—— 本地已决定不修 launchd，托管需求整体推到这一轮，须 Human 授权后单开。
  （1000x 腿量换算已于 2026-08-15 封存，不再是优先项——见 Open Follow-ups 的
  `[CLOSED-NOT-DOING]` 条目。）
- Nothing open authorizes deployment, Start-gate changes, credentials, or live
  operation. Live actions follow the Live Risks gates above.

## Last Completed

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

## Update Rule

Record live incidents at once; remove resolved items. Completed work leaves its
trace in git history and archive references, not in narratives here — commit
messages must state the one-line outcome so history stays traceable, and this
file records only live risks, open follow-ups, and pointers. Over budget: evict
resolved first, then oldest, keeping a git reference.
