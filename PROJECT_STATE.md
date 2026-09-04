# Project State

Cross-stage state, read at startup. Keep under 64 KB. Git history is not a runtime
check. Completed work's trace is git history and archive references (see Update
Rule); this file records only live risks, open follow-ups, and pointers.

## Current Status (2026-09-03)

- **[DEPLOYMENT][2026-09-04 CST] 生产镜像升至 `funding-hedging:9889349`（aoke 主机
  `47.240.168.162`）。** 纯前端 Fast 修复：对冲开单持仓表点击资金费率格触发
  symbol-snapshot 刷新后，日净第二行不同步回显（合并只补丁市场表行与抽屉，持仓格
  要等下一轮私有面板轮询）。现按 `data-position-symbol` 做单元格级补丁，格内容渲染
  抽出 `positionFundingCellView` 与行渲染共用同一来源。零后端变更，
  `frontend/self-check.js` 全部通过（新增 82e 回归，含反向验证）。readyz 10 秒转 200，
  应用与 Caddy 反代均 active。

- **[DEPLOYMENT][2026-09-03 CST] 生产镜像升至 `funding-hedging:95530e9`（aoke 主机
  `47.240.168.162`）。** 纯前端 Fast 改动：对冲开单持仓表现货余额列在「借币利息」
  下方新增「借币日息: x.xxx%」行（沿用借币利息字体颜色；与统一账户资产卡「日利息」
  同源同档，账户档优先、VIP0 参考档标「参考」；账户级按资产去重，快照未覆盖不占行）。
  零后端变更，`frontend/self-check.js` 全部通过。readyz 10 秒转 200，应用与 Caddy 反代均 active。

- **[DEPLOYMENT][2026-09-03 CST] 生产镜像升至 `funding-hedging:a82dea9`（aoke 主机
  `47.240.168.162`）。** 纯前端 Fast 改动：资产卡「可开单」改「去开单」，配色换
  `.badge.success` 浅绿（与开单推荐按钮 `.btn.hedge-reco` 同色），并改为可点按钮——
  点击复用借币卡「行情 ↗」的 `viewBorrowAssetInMarket` 定位到对应市场行；无对应
  市场行时禁用。零后端变更，`frontend/self-check.js` 全部通过。readyz 11 秒转 200，
  应用与 Caddy 反代均 active。

- **[DEPLOYMENT][2026-09-03 CST] 生产镜像升至 `funding-hedging:5a858ec`（aoke 主机
  `47.240.168.162`）。** 纯前端 Fast 改动：统一账户余额资产卡在该资产有借币负债
  （`cross_margin_borrowed > 0`）且可用余额未用尽（`cross_margin_free > 0`）时，
  右上角显示「可开单」warn 徽标，提醒借来的币在空跑利息。零后端/零行为变更，
  `frontend/self-check.js` 全部通过。readyz 11 秒转 200，应用与 Caddy 反代均 active。

## Current Status (2026-09-02)

- **[DEPLOYMENT][2026-09-02 19:33 CST] 生产镜像升至 `funding-hedging:d907966`（aoke 主机 `47.240.168.162`）。**
  NILUSDT 死循环修复（commit `d907966`，claude-review 两轮复审）：① `_worker_round` 空
  `q_common` fail-closed 从 close-only 扩到全部 smooth 任务，门排在 SET_LEVERAGE 之前，
  恢复指引按类型分叉（open 删卡重下 / close 点击启动重新备料）；② `create_task` live
  模式预检快照读取失败（snapshot=None，即上述 429 场景）直接 400 `preflight_unavailable`
  拒绝建卡，dry-run 零变化。全量 2070 过（1 失败为既有无关项 urlopen 白名单）。readyz 9 秒
  转 200。**故障卡 `2620eb9d` 已由 Human 删除；上一条 OPEN 记录中「不要重启该开单卡」的
  临时限制就此解除**（借币 1 秒调度本身的 PAPI 权重问题仍在，见下条与 15:13 条目）。

- **[OPEN][LIVE][ORDERS][RATE-LIMIT][2026-09-02 14:57 CST] 借币 1 秒调度把同 IP 的
  PAPI 请求权重持续顶到 6000/分钟，开单任务 `2620eb9d-600c-4b9a-a066-df72e044bc01`
  设置 NILUSDT 杠杆时被 HTTP 429 拒绝，已 fail-closed 暂停且零 attempt、零两腿订单。**
  线上只读证据：`borrow_settings.interval_seconds=1`、执行开启、8 张 `borrowing` 卡持续轮转；
  借币唯一写端点 `/papi/v1/marginLoan` 每次权重 100，故单是该链即为
  `100 × 60 = 6000/分钟`。借币 attempt `918288` 于 `14:42:34 CST` 先收到
  `429/-1003` 并把本模块冷却到约 `14:43:34`；开单卡在 `14:42:49` 调
  `/papi/v1/um/leverage`，因开单链不共享借币冷却/额度状态而再次收到同一 IP 的
  6000/分钟错误。重复 `51061` 等已知拒绝按既有产品规则继续轮转，日志合并只隐藏重复行，
  不减少真实 POST。**临时限制：在 Human 明确决定停止借币或把调度间隔提高到留有 PAPI
  余量之前，不要重启该开单卡。** 另有独立展示缺陷：`_set_leverage_before_open` 对 executor
  异常再截断 200 字符，导致任务卡文案停在 `polling the AP`；executor 内层响应体已另有限长，
  后续最小修复应去掉这层重复截断并加完整 429 文案回归。修复涉及实盘借币节奏、跨模块额度
  协调和开单失败展示，按 HIGH_RISK 流程处理；未获授权前不改频率、闸门或线上状态。

- **[FAST DIRECT][CODE][2026-09-02 15:13 CST] Human 明确授权把借币新库默认调度间隔从
  1 秒改为 2 秒。** 默认种子现为 `2` / `2_000_000µs`，借币 domain/store/API 回归
  130 条通过，并新增“已有数据库不被新默认重种”的检查。该 Fast 交付不含部署或线上写入：
  生产 `env_aoke` 已有 SQLite 设置仍是 1 秒，上述限频临时限制继续生效，直至 Human 另行授权
  修改线上间隔或部署。

## Current Status (2026-08-30)

- **[DEPLOYMENT][2026-08-30 12:11 CST] 生产镜像升至 `funding-hedging:5cb6ae2`（aoke 主机 `47.240.168.162`）。**
  修复开单任务卡完成后展开日志停留在上一单的视图缓存缺陷（`loadHedgeTasks` 终态当轮拉取一次日志并随后恢复静默，自检通过）。
  readyz 11 秒转 200，systemd 双单元（funding-hedging + Caddy proxy）`active active`。

## Current Status (2026-08-29)

- **[DATA-CORRECTION][2026-08-29 00:31–01:25 CST] 12 条历史还款补录还款时价格，净收益曲线已恢复展示。**
  生产库 `/var/lib/funding-hedging/env_aoke/data/margin-repay.sqlite3`，Human 逐次授权执行。
  **备份**：`margin-repay.sqlite3.bak-storj-20260829-002721`（STORJ 单条前）与
  `margin-repay.sqlite3.bak-histprice-20260829-0040`（其余 11 条前，SQLite `.backup`），
  两份 `quick_check: ok`。**改动**：12 行，每条 `changes()=1`，均带 `repay_price_usdt IS NULL`
  幂等谓词（复跑实测影响 0 行）。**价格口径**：各自 `update_time` 所在那一分钟的币安公共
  1m K 线**收盘价**（`GET /api/v3/klines`，无签名只读）。**来源标记全部 `manual_correction`**，
  与自动路径的 `snapshot_spot_bid_at_capture` 永久可区分。
  **校验**：仍缺价终态还款 0 / 人工修正 12 / 自动捕获 0 / 总行 24 / `quick_check: ok`；
  线上容器内以空 `price_map` 实测 1638 条利息行中 1592 条已锁定且全部算得出，
  剩 46 条为未还清的开放行。Human 已在页面确认「成本不全」消失、净收益有数。

  | 资产 | 时刻(CST) | 价格 | | 资产 | 时刻(CST) | 价格 |
  |---|---|---|---|---|---|---|
  | INJ | 08-10 00:39 | 4.44200000 | | STORJ | 08-20 14:31 | 0.04090000 |
  | XLM | 08-10 11:00 | 0.16320000 | | SNX | 08-27 19:54 | 0.22600000 |
  | WLD | 08-10 13:50 | 0.33400000 | | WLD | 08-27 19:55 | 0.40130000 |
  | JST | 08-12 15:36 | 0.10224000 | | WLD | 08-27 22:00 | 0.40650000 |
  | MANA | 08-17 00:17 | 0.06400000 | | JST | 08-28 10:15 | 0.09785000 |
  | AVNT | 08-18 12:10 | 0.09160000 | | INJ | 08-28 11:22 | 5.33000000 |

- **[教训][2026-08-29] 新功能改变存量数据的解释方式时，上线前必须先数存量分布——本轮全流程漏掉了。**
  `2026-08-28-repaid-interest-price-v1` 上线后，净收益曲线对 7 个资产（INJ/XLM/WLD/JST/
  MANA/AVNT/SNX）显示「成本不全」，**且这是上线引入的回归**：上线前它们按当前价正常显示。
  根因是新逻辑「利息行匹配到 `0+succeeded` 即改用该记录的存储价」，而这 11 条历史还款
  发生在功能上线之前、当时根本没有价格列，存的是 NULL → fail-closed 遮蔽。
  **代码与计划都没错**——两轮代码评审审的是「实现是否忠实于计划」，忠实。
  **错在没有任何环节去数 `margin_repay` 里有多少条历史 `0+succeeded` 记录**：计划 §2 只统计了
  `interest_rows`（确实只有 STORJ 一条），就据此认为影响面是一条；而真正决定影响面的是
  *另一张表*的历史分布——11 条历史终态还款去匹配了 1636 条利息行。
  P5 定档、P7 修复、P6/P8 计划复评、P11 双代码评审、Bookkeeper 核验，六道关卡无一发问
  「上线后存量数据会变成什么样」。**可复用判断**：凡是新增「按某条历史记录的存储值改变
  既有数据解释」的功能，上线前必须查那张历史表的行数与取值分布，而不是只查被解释的那张表。

- **[DEPLOYMENT][2026-08-29 11:37–11:50 CST] 第二台生产机上线：profile `maizi_vip8`，
  `149.129.102.152` / `https://maizi.kengbi.pro`，镜像 `funding-hedging:3856137`（与 aoke 同版本）。**
  `readyz` 200，容器占 124MiB，5 个 SQLite 库已建于 `/var/lib/funding-hedging/env_maizi_vip8/data`
  并实测可写；docker / nginx / funding-hedging 三单元均 `enabled`（重启自恢复）。
  部署入口 `DEPLOY_HOST=funding-maizi scripts/deploy.sh`，已实测能解析该机当前 tag。
  **架构与 aoke 不同（判断影响面前先套这条）**：该机 `:443` 早被系统 nginx 占用（在服务
  `ops.kengbi.pro`），故 **HTTPS 走既有 nginx + certbot 反代到 `127.0.0.1:8787`，没有 Caddy**，
  证书 2026-11-27 到期、`certbot-renew.timer` 自动续期。systemd 单元名与镜像名两台相同，
  故 `deploy.sh` 只需 `DEPLOY_HOST` 切换，脚本一行未改。
  **该机不是专用机**：同机运行无关的实盘系统 `/opt/permanent_investment_strategy_binance/`
  （`grid-live`/`grid-fill-sync`/`shadow-dashboard`/`stage17-*`）与 FMZ `robot`。为此新增
  **2G swap 文件**（`/swapfile`，已写 `fstab`）——1.9GiB 无 swap 机器上做镜像构建，OOM 杀谁
  不由我们定，可能杀的是别人的移仓进程。该机禁止再装第二个 web server。
  新装 `docker-ce 26.1.3`（阿里云镜像源），常驻增约 51MiB。SSH 复用同一把专用部署密钥
  （别名 `funding-maizi`），`sshd_config` 一行未改，`PasswordAuthentication yes` 保留。
  **该实例已持有完整执行权**：`APP_BORROW_EXECUTOR=live` / `APP_HEDGE_EXECUTOR=live` /
  `APP_MARGIN_REPAY_ENABLED=true` / 私有通道开。**使用独立币安账户**，故不触犯本文
  「不得让两个实例同时拥有执行权」——该约束约束的是同一账户，不是同一镜像。

- **[教训][2026-08-29] 部署配置里 `APP_OFFLINE=true` 会让服务永远起不来，且日志不会直说原因。**
  首次启动 `maizi_vip8` 时 `readyz` 60 秒不转 200，唯一线索是启动行的 `offline=True`。
  离线模式改读 `reports/api-samples/.../raw` 的冻结样本，而**部署镜像只打包
  `backend`/`frontend`/`schemas`/`requirements.txt`，不含 `reports/`** → 快照永远建不起来。
  它还静默废掉所有写通道（`live` executor 与还款端点在离线下一律不生效）。
  改回 `false` 后 `readyz` 1 秒转 200。**可复用判断**：生产 env 里 `APP_OFFLINE` 只能是 `false`；
  见到 `not_ready` 先看启动行的 `offline=`，再查别的。

## Current Status (2026-08-28，以下为前日条目)

- **[OPEN][MONEY][PNL][2026-08-28 16:11 CST] 已还款利息仍按实时价折 U，STORJ 使净收益曲线
  fail-closed 显示「暂无 / 成本不全」。** 生产只读核验：账本有一条 STORJ `ON_BORROW`
  利息（本金 `200`、利息 `0.0130242 STORJ`、`2026-08-20 14:00 CST`），还款库有其后
  `amount=0` / `succeeded` 记录（`14:31:03.837 CST`），但对冲库无 STORJ 任务、周期或平仓
  订单。当前持仓统计与收益曲线都以公开行情快照的**当前**现货买一价折算币本位利息；合约进入
  `SETTLING` 后 STORJ 被当前可交易快照排除，故缺价并遮蔽全部净收益。实际订单与资金不受影响，
  但历史成本会随币价重画。Human 决定：已匹配成功还款的利息固定使用还款时价格，未匹配成功
  还款的利息才继续用当前价暂估；匹配、部分还款、价格证据和历史回补先走 HIGH_RISK 计划评审。
  Human 于 `2026-08-28 17:06 CST` 明确否决「利息发生时即冻价」：未结算借款必须随当前价格动态
  估值，成功还款才把相关利息按还款时价格切换为终态固定成本；还款发生时历史重算一次是预期的
  结算动作。Human 于 `2026-08-28 17:57 CST` 进一步明确终态判据：**任意一次部分还款不触发
  锁价**；只要该资产仍有借款持仓/未偿余额，相关历史利息的 USDT 成本全部继续按当前价动态计算，
  只有可确认借款完全归零时，才按该次完全还款时价格切换为终态固定成本。此前部分还款如何在
  交易所内部归集不作为终态证据。活动 stage：
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/`。Human 于 `2026-08-28 18:07 CST`
  选择还款时取价路径 A：成功还款返回后立即读取内存行情快照的现货买一价，接受顺时内微小价差；
  取价整体必须异常隔离，任何未就绪或其他异常只能留下缺价，**绝不能阻断还款成功终态落库**。
  该值的准确名称是「捕获时刻快照买一价」，不宣称为交易所真实还款成交汇率；缺价仍 fail-closed，
  不由正常程序猜价恢复。Human 于 `2026-08-28 21:01 CST` 最终收窄产品边界：正常程序的终态
  触发仅为「资产卡输入 `0`（全额还款意图）且严格返回 `succeeded`」；非零部分还款、`pending`、
  `unknown`、`failed` 均不锁价，相关累计利息继续按当前价动态折 U。`0 + succeeded` 是明确的
  **产品终态约定**，不再追加实时余额归零网络观测。STORJ 等存量非常规利息事件不建设通用推定、
  K 线回补或兜底引擎，后续以单独 Human 授权、写前备份和审计留痕的人工数据库修正归档。
  Human 于 `2026-08-28 21:10 CST` 调整本阶段分工：`opus5`/Anthropic 负责把开发方案定档并准备
  跨 provider 只读计划评审；`claude_glm`/Zhipu 只在定档计划通过后按派单实现，不承担方案定稿。
  Human 于 `2026-08-28 22:51 CST` 要求停止继续循环计划复评：由 Bookkeeper 直接把 P8 唯一
  遗留措辞改为「60 秒是代码默认、实际阈值按部署配置的 `2 × TTL` 计算」，并立即启动
  `claude_glm` 实现。该决定豁免剩余计划复评，不豁免实现后的 Review-1/Review-2，也不授权部署
  或 STORJ 人工数据库修正。

- **[DEPLOYMENT][2026-08-28 13:20 CST] 生产镜像已升到 `funding-hedging:5021c73`，部署通道固化为
  `scripts/deploy.sh`。** 线上 `47.240.168.162` / `https://aoke.kengbi.pro`，systemd 双单元
  （应用 + Caddy）均 `active`，readyz 7 秒转 200，切换期间无告警。
  **架构事实（判断影响面前先套这条）**：服务器上**没有 git 仓库**，应用跑在 Docker 里，
  systemd 单元 `ExecStart` 内联镜像 tag 且 **tag 即 commit sha**——单元文件本身就是版本记录。
  升级 = 重建镜像，**不是 `git pull`**。镜像只含 `backend/frontend/schemas/requirements.txt`，
  密钥经 `--env-file /etc/funding-hedging/env_aoke` 运行时挂载、不进镜像。
  部署脚本拒绝脏工作区、**拒绝未推送到 `origin/main` 的 commit**（线上版本必须可追溯），
  失败自动回滚到旧 tag。SSH 走专用无 passphrase 部署密钥 + `funding-prod` 别名；
  **sshd_config 一行未改，密码通道保留**（`PasswordAuthentication yes`），是密钥丢失时的恢复路径。
  用法见 `docs/development/DEVELOPMENT_GUIDE.md` §Remote deployment。

- **[SECURITY][2026-08-28 14:55 CST] 本机与云端一度同时持有执行权，已解除。** 为让 Human 查看
  新功能，`13:11:52` 启动了本机服务；本机 `.env` 与云端同为 `APP_HEDGE_EXECUTOR=live` /
  `APP_BORROW_EXECUTOR=live` / `APP_MARGIN_REPAY_ENABLED=true` / 私有通道开，且共用同一套币安
  密钥，违反本文「不得让两个实例同时拥有执行权」的既有约束，窗口约 1 小时 44 分钟。
  **实际未发生重复执行**：本机无 `running` 任务（16 deleted / 55 done / 1 paused / 1 stopped），
  `borrow-tasks.sqlite3` 与 `margin-repay.sqlite3` 本轮零写入，`hedge-open-tasks.sqlite3` 仅在启动
  瞬间写过一次（恢复链清点）。`14:55` 已 SIGTERM 停止本机进程，执行权仅剩云端一处。
  **教训**：本机 `.env` 是 live 配置，「只是本地看一眼页面」等于起第二个实盘执行者；查看 UI 应优先
  用云端 `https://aoke.kengbi.pro`，确需本机时先确认执行开关或改用只读配置。另启动时把
  `nohup` 输出丢进 `/dev/null` 使本轮日志不可查，只能靠数据库修改时间反推——不要这样启动。

- **[SECURITY][2026-08-27] 云端访问边界：一个进程只加载一份 `.env` 和一组页面登录凭证。**
  `APP_UI_USERNAME` + `APP_UI_PASSWORD` 使用标准库 HTTP Basic 保护静态页面和全部业务 API；
  `/healthz`、`/readyz` 仅供云平台探活，保持无认证。非回环监听缺任一凭证即拒绝启动；公网部署
  必须由反向代理终止 HTTPS，二级域名、证书、限频和进程/数据目录隔离均由部署层承担。应用不提供
  用户库、注册、找回密码、角色或同进程账号切换。

- **本机服务已于 2026-08-27 停止**，`127.0.0.1:8787` 无监听；`env_aoke` 已从停用的 AWS 实例
  迁到新主机，但当前仍等待上方 SHELLUSDT 恢复决策。本地 `.env` 保留作 Human 授权的源配置，
  权限已收紧为 `0600`；不得让本机、AWS 与新主机中的两个实例同时拥有执行权。

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

- **No active stage**（`ACTIVE.json` = null）。迁移与 SHELLUSDT 恢复已于 `2026-08-28 11:06` 执行完毕，
  该条已不再是优先项。当前待决：
  0. **`2026-08-28-repaid-interest-price-v1` 已完成并上线**（见 Last Completed）；其上线后
     的存量数据回归已修复，无遗留。
  1. **近 24h / 年化 7D 两列欠一次独立评审。** 该交付走 Fast Review 授权实现，但 Human
     `2026-08-28` 指示直接部署，**跳过了 Fast Review 要求的那一次非作者评审**。代码已过
     2039 项后端测试与全部前端自检并已上线，但无第二双眼睛看过固定 commit `5021c73`。
     补审随时可做；发现问题重新部署一次即可。
  2. 两条 `[OPEN][2026-08-23]` 后续项（直连守卫白名单漏登记、HL 适配器未捕获
     `UnicodeDecodeError`）见 Open Follow-ups，均非阻塞。
  3. **HL 别名表与乘数币映射仍未做**（设计 D3 非目标）：9 个命名不同的标的
     （GOLD/SILVER/PLATINUM/PALLADIUM/BRENTOIL/SP500/KR200/SMSN/SKHX）与 5 个乘数币
     （kPEPE/kSHIB/kBONK/kLUNC/kFLOKI）在 UI 上恒为 `—`。其中 `xyz:SKHX → SKHYNIX`
     已于 `2026-08-25` 用价格核实（1193.0 vs 1191.67，差 0.11%；`SKHY` 是另一标的，
     156.51 vs 156.67），要建表时可直接采用。
  4. 年化 30D 的 HL 侧仍为非目标：HL `fundingHistory` 单次上限 500 条（20.8 天）< 30 天，
     每标的须翻两页，历史请求量从每轮 20 增至 30。近 24h 与 7D 共用一次请求故已交付。
  （1000x 腿量换算已于 2026-08-15 封存，不再是优先项——见 Open Follow-ups 的
  `[CLOSED-NOT-DOING]` 条目。）
- 任何 Start-gate、凭据或实盘操作仍须遵循上方 Live Risks 闸门并取得 Human 明确授权。

## Last Completed
- stage: `2026-08-29-market-row-focus-style-v1`
- delivery: `2417b92..e449c9d`（实现），`rework_count` 0。
- recorded_completed_at: `2026-08-29`
- outcome: 行情行聚焦高亮样式优化：将动画拆分为 -bg/-left/-right 三组，内部 td 仅应用背景脉冲（无阴影/无 inset），
  左右竖条高亮仅应用于 td:first-child（inset 4px 0 0）与 td:last-child（inset -4px 0 0），彻底消除了内部各列的
  竖向绿线分割；reduced-motion 同步拆分。
- 评审: Kimi (`kimi`) 前端实现与自检（185 pass, 0 fail）；Grok (Review-1) 与 Claude-GLM (Review-2) 并行独立只读评审双 `ACCEPT`。
- 部署: Human 2026-08-29 授权部署并在线上 `https://aoke.kengbi.pro` 验收（镜像 `funding-hedging:ceff2b4`）。
- 流程偏差（据实记录）: 无。
- stage: `2026-08-29-borrow-card-market-nav-v1`
- delivery: `341aef6..1de9186`（实现），计划固定于 `cc87b1e`；`rework_count` 0。
- recorded_completed_at: `2026-08-29`
- outcome: 借币卡右上角增加「行情 ↗」反向定位按钮，严格 `base_asset` 解析与无匹配 disabled+title 降级；
  已可见时完整保留所有筛选与控件不重绘，被筛掉时放开 6 项条件（含 `showPerpOnly=true` 保底）并同步 DOM
  控件后单次重绘；切市场视图平滑滚动定位并伴随 1.5 秒聚焦高亮脉冲（支持 `prefers-reduced-motion` 静态反馈）；
  按钮事件完全隔离。
- 评审: Codex (`gpt-5.6-sol`) 方案设计；Claude (`opus5`) 设计前只读评审 `ACCEPT`；Kimi (`kimi`)
  前端实现与自检（184 pass, 0 fail）；Grok (Review-1) 与 Claude-GLM (Review-2) 并行独立只读评审双 `ACCEPT`。
- 部署: Human 2026-08-29 授权部署并在线上 `https://aoke.kengbi.pro` 实测验收（镜像 `funding-hedging:a4003e4`）。
- 流程偏差（据实记录）: 无。
- stage: `2026-08-29-market-borrow-view-button-v1`
- delivery: `7bb70a7..89ab96d`（实现），计划固定于 `eeea31b`；`rework_count` 0。
- recorded_completed_at: `2026-08-29`
- outcome: 市场表借币列增加「查看借币」跳转按钮，仅在对应资产存在 `borrowing` 或 `paused`
  借币任务时于「确认」按钮右侧展示（无任务/已完成/已删除隐藏）；1 对多按 `created_at` 降序、
  同值 `id` 降序确定目标；点击/键盘触发平滑跳转至借币任务视图对应卡片，自动切回任务页签、
  同步状态筛选（如 `paused` 任务自动切至 `paused` 筛选确保 DOM 渲染）、平滑居中滚动并带有
  约 1.5s 聚焦高亮脉冲（支持 `prefers-reduced-motion` 静态反馈）；事件完全隔离且表格重绘时
  输入框值完整保留。
- 评审: Codex (`gpt-5.6-sol`) 方案设计；Claude (`opus5`) 设计前只读评审 `ACCEPT`；Kimi (`kimi`)
  前端实现与自检（176 pass, 0 fail）；Grok (Review-1) 与 Claude-GLM (Review-2) 并行独立只读评审双 `ACCEPT`。
- 部署: Human 2026-08-29 授权部署并在线上 `https://aoke.kengbi.pro` 实测验收通过（镜像
  `funding-hedging:9c8842a`，readyz 10s 转 200）。
- 流程偏差（据实记录）: 无。
- follow-ups: 反向导航功能已于 `2026-08-29-borrow-card-market-nav-v1` 与 `2026-08-29-market-row-focus-style-v1` 完整交付闭环。
- stage: `2026-08-28-repaid-interest-price-v1`
- delivery: `f4f6c6f..d315fbd`（实现），计划固定于 `e37d45a`；`rework_count` 0。
- recorded_completed_at: `2026-08-29`
- outcome: 已还款利息按还款时价格折算。未出现本地终态事件前，币本位累计利息按当前缓存价
  动态折 U；唯一终态是**存储意图** `amount=="0"` 且严格 `status=="succeeded"`，届时此前利息行
  一次性切到捕获价并固定；非零部分还款与 `pending`/`unknown`/`failed` 不锁价；终态后
  re-borrow 重新开放。`margin_repay` 增 `repay_price_usdt`/`repay_price_source` 两个 nullable
  TEXT（**无 CHECK/枚举**，为人工 `manual_correction` 保留写入路径）。还款派发与 `store.resolve`
  之间只增一个 best-effort 内存取价（异常隔离、失败两列 NULL、`resolve` 在边界外恰一次）。
- 评审: 计划经 P6/P8 两轮独立跨 provider 复评（均 `REWORK` 后 `ACCEPT`）；Human 豁免剩余
  计划复评轮直接开发；实现经 Review-1(grok) 与 Review-2(kimi) 并行独立评审，双 `ACCEPT`。
  Human 2026-08-29 授权合并并部署（镜像 `funding-hedging:3856137`）。
- 流程偏差（据实记录）: ① 本 stage **全程直接在 `main` 提交、未建 stage 分支**，与
  `DEC-2026-07-05-001` 分支制不符；② Bookkeeper 于 revision 16 由 `gpt-5.6-sol`/codex
  临时移交 `opus5`/claude（codex 会话额度耗尽），而 opus5 同时是计划作者——该非常规状态
  已在两份评审派单中显式披露并要求 Reviewer 独立复核；③ P9 计划扫描任务未执行即作废
  （Human 明示跳过剩余计划复评）。
- follow-ups: 上线后暴露存量数据回归，12 条历史还款经 Human 逐次授权人工补录价格
  （见 Current Status 数据修正条与教训条）。**该缺陷由 Human 在页面上发现，不是任何评审发现的。**
- stage: `2026-08-23-hyperliquid-funding-compare-v1`
- archive_ref: `archive/2026-08-23-hyperliquid-funding-compare-v1`（tip `c7674ef`）
- delivery: `25cc8fe..6922bce`；`rework_count` 0（三轮设计评审的 REWORK 属实现前计划修订，按 §8 不计数）。
- recorded_completed_at: `2026-08-24`
- outcome: 费率行情表前四个费率列内每行增加 Hyperliquid 同口径第二行，市场表下方新增
  「HL 数据时间」并在不可用/陈旧时红色高亮。696 行中 244 行有 HL 对手（main 166 + xyz 78）。
  匹配为 exact + 类别校验（main 只配 `PERPETUAL`、xyz 只配 `TRADIFI_PERPETUAL`），
  `HL_SYMBOL_DENY` 显式拦 `xyz:BB`（黑莓 vs BounceBit）与 `xyz:QNT`。失败语义为 main+xyz
  原子组：任一 POST/shape/Decimal 失败即整源作废、全行 null、时间戳 null、不投影 last-good，
  币安四列照常且不阻断发布。
- 评审: 设计经 Codex 三轮独立跨 provider 评审（rev1 `REWORK` F1–F5、rev2 `REWORK` N1–N3、
  rev3 `ACCEPT`）；实现经 Review-1(grok) 与 Review-2(kimi) 并行独立评审，双 `ACCEPT`。
  Human `2026-08-24` 授权合并（`merge: f415848`）并推送。
- follow-ups: 上线后 Human 实盘发现小时费率固定 3 位小数吃掉有效数字（该列五个标的
  真实值分布 0.000625%~0.00125% 却全显示 `+0.001%`），已修（`merge: 13fa80c`，新增
  `formatFundingRateExact`）。**该缺陷绕过了全部五轮评审**——评审都在查失败语义、撞名、
  schema 兼容与假绿断言，无人核查「显示后还剩几位有效数字」；测试 fixture 用的人造整数值
  舍入后恰好不冲突，只有真实数据能暴露。回归断言已用 CRCL/INTC 真实值补上。
- 更早的已完成 stage 只留指针（完整记录见 git history 与各自 archive 分支）：
  `2026-08-19-hedge-order-fee-cost-v1`
  `2026-08-14-smooth-close-orders-v1`
  `2026-08-12-smooth-open-orders-v1`
  原文 `git show 4dcce9f:PROJECT_STATE.md`。

## Evicted (2026-08-28) — AWS→新主机迁移流水账

按 Update Rule 驱逐了 `2026-08-27`..`2026-08-28` 的 6 条迁移事件叙事（约 8.7 KB：新主机启动完成、
AWS 无响应事件、AWS 停止、迁移就绪/START BLOCKED、AWS 曾部署 `7a3bd41`、`[RESOLVED]` env-file
修复），以及 3 条较早的已完成 stage 记录。完整原文 `git show 4dcce9f:PROJECT_STATE.md`。
**下列是从中提取的、仍然生效的约束**——它们不是历史，只留 git 指针会让后来者误判：

- **内存仍无护栏**：AWS `t4g.micro` 只有 921 MiB、无 swap，应用 Python 以约 630 MiB 匿名内存两次
  被内核 OOM kill（`exit 137`），systemd 自动拉起，故障时 load 峰值 `9.43/29.81/20.09`，且表现为
  「TCP 能建连但应用层无响应」——排查时容易误判成网络问题。**新主机 1.8 GiB 同样无 swap、容器无
  memory limit**，应用 RSS 迁移后约 299 MiB 且会随运行增长。再次 OOM 的条件没有被消除，只是余量变大。

- **Docker `--env-file` 不做变量展开**：本地 `.env` 里 `BINANCE_BORROW_API_KEY=${BINANCE_API_KEY}`
  这类引用，经 `scripts/run-server.sh` 的 `source` 会正确展开，但 Docker 把带引号的 `${…}` **原文**
  当成环境值（20/23 字符）。后果是通用只读 Key 正常、专用写 Key 全废，而且**私有账户读取成功不能
  验证写通道**——这正是当时误判的地方。现行修法：应用以 `BINANCE_API_KEY/SECRET` 为默认凭据，
  专用 borrow/hedge 凭据保留为成对可选覆盖；云端 `env_aoke` 的四个未展开别名已删。配 env 必须逐个
  核对实际字符长度。

- **XVGUSDT 平滑平仓任务仍 `paused`，前端文案与机器原因不一致**：机器暂停原因是
  `consecutive_submission_failure`（连续提交失败 3），但 `pause_reason_zh` 仍是此前「订单状态不明」
  的旧说明，UI 可能持续显示旧文案。不改变终态或暂停行为。**不得由模型替 Human 恢复任务。**

- **部署前备份位置**：`/var/lib/funding-hedging/backups/deploy-7a3bd41-20260828T003319CST`
  （配置 + systemd unit + 数据库，`quick_check=ok`）。

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
