# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-08-21)

- **[2026-08-21 Human 直接驱动，无 stage] 资金费率收益曲线 + 流水日志升为侧栏一级视图：**
  新增 `GET /api/private-ledger/pnl-series` 与纯函数 `ledger_flow.build_pnl_series`，前端手搓
  SVG 绘制五条线（资金费收益 / 手续费 / 利息 / 滑点 / 净收益），左图右表并排、双滑块选区、
  贴线悬停、1D/3D/7D/全部本地切片零请求、隐私脱敏。口径：**净收益 = 资金费 − 手续费 − 利息
  − 滑点**，成本在序列中存负值直接相加，与持仓级 `net_pnl`（`4d52c39`）一致；出点节拍为「有
  资金费结算的小时」（350 → 91 点）；`REALIZED_PNL` 不进净收益（对冲下被现货腿抵消，单列供
  对账，当前 `-23.54 U`）。同时将流水日志从费率行情页内双看板移到侧栏一级视图，`state.marketBoard`
  退役；私有账户面板拆为 `#private-overview-panel`（八张统计卡）与 `#private-panel`
  （余额/互转/持仓）。提交区间 `b0bffaf..f3fe3ba`，经 codex + grok 四轮双评审。
  已知失真与接受理由见 Live Risks「收益曲线的滑点已统一到 close-log 口径」。

- **[2026-08-20 Human 直接驱动，无 stage] 持仓与历史表价差/滑点折算 USDT 实际盈亏第二行：**
  持仓表「开单价差率」列与历史表「总计开单滑点 %」「总计平单滑点 %」列同步增加第二行折算 USDT 实际盈亏金额。正收益绿（+X.XX U）、负成本红（-X.XX U）、零值与亚分位（<0.005 U 取整 0.00 U）灰（muted）、隐私模式脱敏（****）。四组合买卖腿识别与后端完全对齐。纯前端改动，经 Claude 独立 Fast Review ACCEPT 并由 Human 授权推送至 main 分支（提交区间 `4e9295f..1115fce`）。

- **[STAGE COMPLETED 2026-08-20] 成交手续费冻价成本 V1 (`2026-08-19-hedge-order-fee-cost-v1`)：**
  表结构四列手续费扩展落库、历史数据回补 268 腿成功落库（待补 269 腿中，132/133 条 UM 路由腿成功回补；仅 1 条约 9.6 天前的历史老单因超出币安合约 7 天查询窗口返回空列表，系统按 D10/D11 宁缺毋滥原则整行安全显示 `—`）、读链路真实折 U 聚合（quote/base 严格均价、不全 None/None/True 安全契约）、平仓结算 `close_log` 全腿现算冻结、实时下单 commit-first 钩子自动拉取写入（D4 实时现价冻结）。
  双评审闭环（Kimi ACCEPT + Opus 5 ACCEPT）。已合并 main 并重新部署。


- **[2026-08-18 Human 直接驱动，无 stage] 非正常借币中标红：**
  不是「live + 已启动、且没有拦住原因」时，借币页顶上执行状态改红色；
  这时若还有借币中任务，侧栏「借币任务」后的数字一并标红。覆盖停止、
  缺凭证、418 速率受限、加载失败等。纯前端，刷页面即可。
  验证：`node frontend/self-check.js`。未授权提交、部署或实盘操作。

- **[LIVE][2026-08-18 11:18:43 CST] 借币 IP 418：** COTI 一次借币 POST 收到
  HTTP 418（`rate_limited_418_ban`）。本机最低冷却到 **11:23:43 CST**（已过）。
  `requires_rearm=1` 仍在，借币不会自动再发。币安回包里的「banned until」
  没有落库、服务日志也没有，**交易所真正解封时间未知**。未授权对币安探测，
  也未点启动。开单任务侧今天没有 418 记录。

- **[2026-08-18 Human 直接驱动，无 stage] 开单任务卡编号点击复制：**
  卡头 `#id` 可点，写入剪贴板的是裸任务编号（不含 `#`），约 1 秒后文案回到 `#id`。
  纯前端，刷页面即可。验证：`node frontend/self-check.js`。未授权提交、部署或实盘操作。

- **[2026-08-18 Human 直接驱动，无 stage] 开单任务两秒刷新只留给执行中的卡：**
  停在「已暂停 / 已删除 / 已完成」，或「全部」里当前没有执行中任务时，两秒轮询
  不再重拉任务列表、也不再重画这些终态卡。执行中页整表仍每两秒更新（页上本来
  都是 running）。「全部」里还有执行中任务时，两秒只替换 running 卡（刚离开
  执行中的那张补一刀改徽标），旁边的暂停/完成卡不动。点暂停/启动/删除、刚进
  开单任务页、以及 60 秒市场快照仍整表拉一次。纯前端，刷页面即可。
  验证：`node frontend/self-check.js`。未授权提交、部署、重启或实盘操作。

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

- `[RESOLVED-BY-DELIVERY][2026-08-21]` **借币「崩溃孤儿永久卡死任务」已从根上取消（`DEC-2026-08-21-001`）。**
  原风险：`COTI`/`HOME`/`PROM` 三卡因 `crash_orphan_responseless` 被 ADR-006 fail-closed 永久
  阻塞调度，页面却仍显示上一次的 `known_rejection:51061`「可贷资产不足，请稍后再试」，看起来像在
  正常重试；`HOME` 静默停摆 5 天。
  处置不是补徽标，而是按 Human 裁定改口径：**只有 POST 返回可用 `tranId` 才算借成，其余一律当
  「没借成」、任务继续跑**。据此删除了整套借币记录对账子系统（`_reconcile_pass`、
  `advance_reconciliation`、`attribution_is_unique`、`LiveBorrowExecutor.reconcile`、
  `fetch_loan_records` 与 `GET /papi/v1/margin/marginLoan` 白名单项——借币客户端现在只剩下单
  POST 一个签名端点）与前端「待对账·暂停调度」徽标，净减约 1400 行。
  `unresolved_attempt_id` 降级为纯进程内在途锁：每次结算清、开机也清。
  ⚠️ **开机恢复已改为 owner-gated**（先抢 sidecar 锁再开库）：codex Review-1 发现非 owner 进程
  启动会清掉在跑进程的在途标记，随后一次「清空日志」即可删掉它正要结算的那行，**丢掉一笔真实
  `tranId` 成功**。已修 + 并发回归测试（变异验证改坏即红）。
  **接受的代价**：每个孤儿最多多借一笔，Human 从币安控制台核对余额收口；「每卡只准释放一次」
  的闸门经评估后由 Human 否决为过度设计。**不查实际借到的本金**（POST 只回 `tranId`），
  Human 原话「出了问题再增加查询实际借到的资金量」。
  三张旧卡**下次重启自愈**（开机清掉残留标记），无需删卡重建、无需数据库手术。
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
