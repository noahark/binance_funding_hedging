# 平滑开单 V1：设计上下文、决策记录与交付边界

状态：**平滑开单代码已完成上一轮 F1 修复并通过 Review-1，Human 页面验收发现三项需在 Review-2 前更正的实际问题：新建 smooth 卡自动执行、未启动卡误展示空盘口、放行到两腿提交之间没有可解释延迟的持久化证据。本次只新增 D17–D19，须经一次跨 provider 窄范围计划复核后，才可由原 Implementer 返修。当前页面验收服务仍在运行旧交付；本计划不授权改源码、重启、创建任务、下单、push、merge、部署或实盘。**
日期：2026-08-12（2026-08-13 增量修订：D15–D19 + §6.5/§6.6 + §16/§17）
适用范围：现有对冲开仓任务的 `mode=smooth`。立即开单和平仓任务不是本轮改造对象。

## 1. 为什么要做

当前开仓任务已经具备经过实盘验证的主链：逐轮预检、持久化保留 attempt、现货与合约两腿并发提交、查询各自订单至终态、结算当前 pair 后再进入下一轮。市场页也已有正向/反向开单率，但它来自约 60 秒刷新的 REST 快照，只用于展示，不能作为逐轮成交门槛。

Human 要恢复旧 JS 中“每轮在固定时间内等更好盘口”的产品体验，但不沿用旧实现的 REST `getDepth` 轮询：

1. 用 WebSocket 最优买卖价和一档数量，在每一轮发单前实时计算本方向开单率；
2. 行情好时提前成交，最多等 5 分钟；等不到就按现有立即开单成交，不让任务无限等待；
3. 允许 Human 在任务卡上强制放行**当前正在校验的一轮**，但绝不能因此多发一轮；
4. 下单、查单、单腿结果和任务收尾全部沿用立即开单，不建立第二套资金路径。

产品目标不是“保证没有滑点”，而是用最优一档做一个低维护、低延迟的机会过滤器。Market 单实际成交仍可能受一档之后的深度和发送期间行情变化影响。

## 2. 现有事实与接入缝

### 2.1 旧 JS 只提供产品框架，不提供可复用 WebSocket

旧文件 `币安套费率策略，逐仓杠杆.js` 中，平滑开单按钮生成 `openPositions:<symbol>:<direction>:smoothOpen`。`checkCMD` 分派到 `smoothOpenOrderFirstMethod`，再到 `checkSmoothOpenOrClose` / `positiveOpenCheck`，最终调用 `getDepth`。`getDepth` 通过 FMZ `exchange.Go("GetDepth")` 并发发起现货/合约深度请求；这是异步 REST，不是本仓库可复用的 WebSocket 订阅。

因此沿用的是“逐轮等待→校验→放行→复用立即成交”的状态框架，不照搬旧行情获取实现。

### 2.2 当前 Python 下单链已经是目标资金路径

- `backend/hedge_open_tasks/service.py::_worker_round` 保证同一任务上一 pair 处理完成后才进入下一 pair；
- `HedgeOpenStore.prepare_attempt` 原子检查 `running`、`scheduled_attempt_count < target_n` 和无未决 pair，并在发单前持久化 attempt；
- `backend/hedge_open_tasks/service.py::_dispatch_live` 调用现有 executor；executor 并发提交现货与合约两腿，worker 随后同步推进两腿查询、结算和暂停逻辑；
- 当前任务 worker 由 `_workers_lock` 保证每个 task 最多一个进程内 owner，store 再提供持久化在途 pair 硬门。

平滑门必须插在“无在途 pair、目标次数未到”与 `_dispatch_one_for_task` 之间。门通过后只调用原有 `_dispatch_one_for_task`，不得复制 preflight、reserve、executor、query 或 settlement。

### 2.3 当前 `成交1次` 不能直接复用后端语义

`post_fill_once` 在 live-capable 模式下只是把任务置为 running 并启动 worker；worker 可以继续跑完所有剩余轮次。它不是“只放行当前平滑校验轮”。

因此 UI 文案可以沿用，平滑任务的后端动作必须改为“给当前 gate 发一次性放行信号”，而不是调用一次下单器或再启动一个调度循环。

另外，当前 `create_task` 明确拒绝 `mode != immediate`，市场页平滑按钮仍为 disabled；任务卡一旦出现 smooth task，`showFillAll = task.mode === 'smooth'` 又会显示“立即成交所有”。P2 必须在同一交付中解除前两处冻结、按新语义分流 fill-once，并移除 smooth 的 fill-all 展示/调用，不能只打开前端按钮。

### 2.4 当前开单率是可复用口径

`backend/domain/snapshot.py::compute_opening_spread_pct` 已用 Decimal 计算并四舍五入到百分比小数点后两位：

- 正向：`(合约买一 - 现货卖一) / 现货卖一 × 100%`；
- 反向：`(现货买一 - 合约卖一) / 合约卖一 × 100%`。

`frontend/index.html::renderOpeningQuotesCell` 已按“参与计算的两腿价格 + 带符号百分比 + 正负颜色”展示。平滑成交判断和任务卡展示都复用这个口径，不能再定义第二种分母、精度或颜色规则。

### 2.5 当前任务卡已有唯一的 2 秒刷新时钟

前端 `EXECUTION_POLL_MS = 2000`；展开日志时立即加载该任务日志，运行中的已展开任务随后每 2 秒重取。平滑盘口展示搭载这条已有读链，不增加新的前端 timer。

## 3. 已定决策及前后因果

下表区分 Human 明确决定与为落实该决定不可缺少的最小实现约束。评审不应把已经拍板的取舍重新当作待定需求；若发现它与代码事实或资金安全矛盾，应给出证据和实际影响。

| 编号 | 最终决定 | 之前考虑/现状 | 选择原因与实际后果 | 来源 |
|---|---|---|---|---|
| D1 | 公共盘口统一层采用 CCXT Pro；V1 只负责公共市场数据；候选版本锁为 `ccxt==4.5.64` | 曾讨论把 CCXT Pro 当全部交易所统一层 | CCXT Pro 可统一 WebSocket 订阅和返回字段，但不能抽象本项目的组合保证金、借币、划转、两腿语义和本地恢复契约；这些继续使用现有 Binance 专用链。P0 已在隔离环境实测该版本，正式依赖清单仍须单独交付和评审 | Human 目标 + 当前代码事实 + P0 实测 |
| D2 | 每个现货/合约腿使用 `bookTicker` 语义；CCXT Pro 首选 `watchBidsAsks([symbol])` | 最初考虑两个 `watchOrderBook` | 本轮只需要买一/卖一价格和数量。完整订单簿需要快照、增量序列、重建与一致性维护，成本更高；一档机会过滤不需要它 | Human 明确决定 |
| D3 | 现货和合约由两个独立 async 消费任务维护 | REST `getDepth` 可并发返回，但不是持续订阅；单一串行循环会让一侧异常阻塞另一侧 | 两侧独立等待、更新、异常和重连；gate 读取两侧最新有效快照。独立是故障隔离，不代表每个业务任务新建两条物理连接 | Human 明确决定 |
| D4 | 当前方向开单率必须**严格大于**任务阈值 | 可选 `>=`，但 Human 原话是“大于” | `0.05%` 本身不通过，`0.06%` 才通过；负阈值仍保持同一数学比较 | Human 明确决定 |
| D5 | 平滑按钮后放一个小输入框和 `%`；默认 `0.05`；允许 `0` 和负数 | 只支持正阈值会错过高资金费足以回收一次差价损耗的场景 | 阈值是百分数值而非 ratio；不设置人为最小值或最大值。负值不是错误，也不是自动改成零 | Human 明确决定 |
| D6 | 阈值与开单率都按现有两位百分比 Decimal 口径比较 | 若用未舍入值比较、任务卡仍显示两位，会出现页面 `+0.05%` 却通过 `0.05%` 门槛 | 判断值等于展示值，避免操作员无法从页面解释成交。输入最多两位小数，非法/空值不建任务 | Human 要求同格式 + 现有权威推导 |
| D7 | 正常提前成交同时要求“本方向开单率通过”和“两腿各自买一/卖一档覆盖任务固化的本轮 `q_common` 至少 80%” | 只看价会在一档极薄时把机会判断为可成交；完整深度又超出 V1 | 80% 只过滤机会，不把实际订单缩成 80%。当前可达普通 USDⓈ-M symbol 的两腿共用基础币 `q_common`；P0 必须证明 BookTicker 数量同量纲并断言 `contractSize == 1`，否则该侧 invalid。1000x 乘数币继续由现有建卡门封禁，本轮不顺手做换算 | Human 明确决定 + 当前可达路径的单位安全约束 |
| D8 | 每轮独立等待最多 5 分钟；自然通过即成交；超时则绕过平滑行情条件，走立即开单 | 无限等待会让计划次数无法落地；把断流永久当机会不好也会卡死 | 5 分钟内“没有机会”包括盘口持续不达标或某一订阅一直无有效快照。超时仅绕过开单率/80%/WS 有效性，不绕过 Start gate、任务状态与 `prepare_attempt` 的原子复核。**2026-08-13 更正**：D15 之后，smooth 的三种放行原因（含 timeout）都不再执行每轮联网 fresh preflight，因此本行原先“不绕过 preflight、路由、余额、限流”的表述对 smooth 已不成立，仅对 immediate 继续成立 | Human 明确决定 |
| D9 | `成交1次` 只强制当前活动 gate，绝不创建新 attempt | 若按钮直接调用 executor，恰逢第 10 轮自然通过可能出现第 11 单 | 自然通过、5 分钟超时、Human 点击是同一 gate 的三个放行原因；只有 worker owner 能消费一次并进入原 dispatch。无活动 gate、已达 `target_n`、暂停/结束时拒绝 | Human 明确决定 + 资金安全约束 |
| D10 | 两腿继续并发提交，worker 同步等待并处理结果 | 为平滑功能另写串行下单会改变单腿风险与现有审计语义 | 平滑只决定“何时调用”，不改变“如何调用、如何查单和结算”；单腿场景原样复用立即开单逻辑 | Human 明确决定 |
| D11 | 任务卡显示动态正向/反向盘口，格式与费率行情页一致 | 市场页 REST 约 60 秒缓存不能代表 gate 当前值 | 任务卡展示来自平滑 WS cache；复用现有百分比 formatter/颜色规则并扩展新盘口块，正向显示合约买一/现货卖一，反向显示现货买一/合约卖一，同时显示两侧数量和覆盖率；不是直接复用只支持价格的旧 cell | Human 明确决定 |
| D12 | 任务卡同源读请求复用共享 2 秒 tick；**最新任务快照中所有 `status === 'running'` 的任务均刷新 task-id 日志，不区分 `mode`、`task_type`、方向或日志展开状态**；非 running 任务仅在仍存在且日志已展开时继续刷新 attempt/腿日志，收起或任务不存在时停止。动态盘口块是否渲染另由 D18 决定，只限 `running`（2026-08-13 页面验收后再次更正：running 刷新不再以“日志已展开”为前提，避免刷新后空 `hedgeLogExpanded` 导致 running 卡长期误报“数据不完整”） | 另开 timer 会重复请求且把“UI 刷新率”误当“成交校验率”；只刷新 `running` 且仅当展开时，会让浏览器刷新/切页后丢失展开状态，从而 running 卡长期拿不到真实盘口；而刷新非 running 展开日志可让暂停/删除后仍在 drain/settle 的在途订单在页面上可见 | 前端只每 2 秒看一次；后端仍在每次 WebSocket 更新时重新评估 gate。两者时钟完全分离 | Human 明确决定 + 2026-08-13 页面验收再次更正 |
| D13 | V1 平滑任务只保留 `成交1次`，不展示 `立即成交所有` | 现 UI 为 smooth 预留了 `立即成交所有`，但 Human 本轮只定义逐轮 5 分钟和“成交1次” | 一次放行有清晰 gate 身份；“所有”会引入永久绕过或批量新 attempt 的第二语义，且与逐轮校验目标冲突 | 本轮最小范围结论 |
| D14 | 多个任务订阅同一交易所同一 symbol 时，共享一个 watcher 的 latest snapshot | 若每个 task 各开两条逻辑订阅，任务数会线性放大订阅和重连工作 | 以 `(exchange_id, market_type, unified_symbol)` 为 key 引用计数；task 只订阅/释放，不拥有 socket。现货与合约仍是两个独立 key 和两个 async loop | D3 的最小可维护实现 |
| D15 | **smooth 的每轮联网 fresh preflight 取消**：gate 以 market/manual/timeout 任一原因通过后，直接复用建卡固化的 `q_common`、`position_side_mode`、`preflight_snapshot`/route 构造请求，原子 reserve 后进入既有两腿异步提交 | 首轮实现里 gate 通过后仍走 `_resolve_fresh_preflight`，一次联网读取插在“判定成交”和“真正发单”之间 | 让「WS 判定通过」到「两腿提交」之间不再有任何联网读取、交易所设置、sleep 或其他阻塞调用，否则一档价差过滤的时效性被自己抵消。**代价（Human 明确接受，不得包装成 fail-closed）**：等待期间余额/保证金、交易规则、position mode、下单限频、现货路由等事实若发生变化，不再有每轮预检拦截，可能出现两腿都被拒或单腿成交；单腿仍由现有任务卡告警、任务暂停与 Human 人工核对收口。建卡时的首次完整 preflight、固化数据、regular-spot 预划转、缺腿/乘数合约拒绝全部保留；immediate 每轮 fresh preflight 逐字不变 | Human 2026-08-13 决定 |
| D16 | **smooth 首轮杠杆前移**：live smooth 任务在 `scheduled_attempt_count == 0` 时，必须先完成该任务唯一一次合约杠杆设置，成功后才允许订阅 WebSocket、建立或恢复 gate、执行第一次滑点计算 | 首轮实现把杠杆设置放在 gate 通过后的 `_dispatch_one_for_task` 内（`service.py:3177`），那是 D15 要求清空的那段窗口 | 杠杆是每任务一次的交易所设置，必须发生在“开始盯盘”之前而不是“决定成交”之后。设置失败沿用现有 `leverage_set_failed` 暂停与中文原因，并且此时零 gate、零订阅、零 attempt、零订单。后续轮次不重复设置；首轮尚未产生 attempt 就因失败或进程重启而重新进入执行入口时可幂等重试，但仍必须在任何订阅/gate 之前。**不得**把杠杆提前到建卡时（建卡不代表会执行）；不新增持久化列或新状态机 | Human 2026-08-13 决定 |
| D17 | **smooth 新建后固定为 `paused`，必须由 Human 在任务卡点击“启动”才进入执行**；创建响应不得启动 worker、订阅盘口或建立 gate | 当前 `create_task` 把 smooth 直接建成 `running`，且全局 Start gate 开启时立即 `ensure_worker`，所以新卡的启动按钮置灰并可能马上真实成交 | 把“创建计划”和“开始盯盘/下单”拆开，复用现有任务卡 `post_start`、按钮状态与 worker 启动路径；点击启动后的顺序仍是 D16 杠杆 → 订阅 → gate。**边界**：建卡时既有首次完整 preflight、固化 `q_common`/route 与 regular-spot 预划转保持不变，因此创建卡片仍可能发生既有预划转，长时间暂停也会使固化事实更旧；这是 D15 已接受的取舍，不把 preflight/划转迁到 Start。本项只改 smooth，当前代码中 immediate 新建仍是 `running`，不得借“流程一致”顺手改变 immediate | Human 页面验收 2026-08-13 |
| D18 | **未执行的 smooth 卡只显示固化滑点阈值，不显示盘口连接、正反向开单率、价格、数量、覆盖率、gate 轮次或倒计时；仅 `status=running` 显示动态盘口块** | 动态盘口只在 worker 订阅后有意义；当前前端对所有 smooth 卡无条件渲染，未拉取日志时就把空缓存解释成“现货/合约 数据不完整” | 消除“卡刚创建就像订阅坏了”的误导。Human 点击启动成功后，前端沿用现有自动展开日志与同源 GET，动态块随 running 卡出现；任务后续 paused/done/stopped/deleted 时隐藏盘口块，但已展开的 attempt/腿日志仍按 D12 继续刷新，不新增 timer | Human 页面验收 2026-08-13 |
| D19 | **持久化每一轮 smooth 放行快照与“放行→两腿各自开始调用订单客户端”的分段耗时**；只做观测，不成为准入条件 | 首笔实盘只留下 `smooth_pass_reason=market`，没有放行瞬间 bookTicker，也没有区分本地组参、SQLite reserve、executor/线程启动与订单客户端调用的耗时，无法解释成交价偏离阈值发生在哪一段 | 同一次 gate 评估必须携带其实际操作数和结果，禁止为了审计再读一次盘口。用 monotonic 微秒记录相对耗时，用 wall clock 记录放行时刻；两腿返回后才通过既有日志表追加 `smooth_dispatch_audit`，故放行到 POST 前不新增 SQL/网络/sleep/print。审计写失败不得改变订单结果。仍不恢复任何 fresh preflight 或二次滑点复核，也不改变两腿并发、单腿处置和成交次数 | Human 页面验收 2026-08-13 |

## 4. CCXT Pro 的职责边界

### 4.1 V1 使用范围

建立一个只读 `BestBidAskProvider` 边界，V1 的 Binance 实现由 CCXT Pro 提供：

- spot client：现货统一 symbol 的 `watchBidsAsks`；
- USDⓈ-M client：合约统一 symbol 的 `watchBidsAsks`；
- 从每项 `info` 只读取原始字符串 `b/B/a/A`，分别作为 bid price/qty、ask price/qty；禁止让 CCXT normalized float 进入 gate 或展示；
- spot 记录 `exchange_ts = null`，perp 有 raw `E` 时记录该值；两侧都记录本地接收时间；
- watcher 注册、共享、释放、断开后失效、首次新消息后恢复有效；
- 进程关闭时关闭 CCXT Pro clients。

P0 已在仓库外隔离 venv 实测 `ccxt==4.5.64`：`binance` 和 `binanceusdm` 的 `watchBidsAsks` 可用；现货 key 为 `BTC/USDT`，合约返回 unified key `BTC/USDT:USDT`；双独立 watcher 取消其一不影响另一侧继续更新；普通 BTC U 本位永续 `contractSize=1.0`。同时证实 normalized 价量为 float、spot 无 `E/T`、1000PEPE 的 `contractSize` 也为 `1.0`，故 raw string、spot 本地接收时间和现有 1000x 封禁均是硬约束。原始证据见 `docs/planning/ccxt-bookticker-recon-2026-08-13.md`。

P0 没有 executable 证明自动断线重连、重连 generation、引用归零、close 后零 CCXT 内部 task 或多 symbol 共享。这些不是可忽略观察，必须由 P1 的 fake source/lifecycle 测试证明；证明失败则按既定边界切 Binance 原生 public bookTicker fallback。

本仓当前不仅没有 CCXT，也没有任何运行时依赖清单。P0 不得直接污染正在跑真钱服务所用的 `.venv`：先在隔离临时虚拟环境完成 proof；通过后才由单独授权的交付新建仓库唯一的运行时依赖清单并固定精确版本，随后才允许安装到生产运行环境。清单的维护者是后端运行环境，读者是安装/升级脚本；现有文件无法承载这一独立职责，故允许新增。

### 4.2 同步服务与 asyncio 的桥

当前 HTTP 服务和任务 worker 都是线程模型，仓库没有现成 asyncio runtime。CCXT Pro provider 使用一个进程级专用 event-loop 线程：

- 该线程独占 CCXT Pro clients 和 async watcher tasks；
- 现货、合约是独立 coroutine；同一 market key 只存在一个 watcher；
- provider 用锁保护不可变 latest snapshot 和订阅引用计数；同步 worker 只读副本；
- 注册/释放通过线程安全提交到 event loop；不得从 worker 直接 `await`；
- provider 更新、异常或重连时通知正在等待相关 symbol 的同步 gate；
- service close 先取消 watcher/关闭 clients，再停止并 join event-loop 线程；测试必须证明无悬挂 task。

### 4.3 明确不接管

CCXT Pro 本轮不用于：

- 私有订单 WebSocket、订单状态最终确认；
- create/cancel/query order；
- 组合保证金、逐仓/全仓、position side、reduce-only；
- 借币、还款、资产划转；
- 现货路由、预检、数量网格、client order id；
- 两腿并发、UNKNOWN 恢复、限流和单腿敞口处理。

这些仍以当前 `hedge_open_tasks`、preflight provider 和 live executor 为唯一权威。后期接其他交易所时，只能先替换 `BestBidAskProvider`；不能据此宣称资金执行已经跨交易所统一。

## 5. 盘口快照与有效性

### 5.1 快照字段

每个 market key 只保存最后一条不可变快照：

- `exchange_id`、`market_type`、`symbol`；
- `bid_price`、`bid_qty`、`ask_price`、`ask_qty`（原始十进制字符串）；
- `exchange_ts`（交易所/CCXT 有则记录，没有则为 null）；
- `received_at_us`；
- `generation`（每次订阅建立或重连递增）；
- `status = connecting | live | disconnected`；
- 最后一次错误的安全中文摘要（不得含凭证或完整请求）。

价格与数量必须为可解析且大于零的 Decimal，否则该侧快照对 gate 无效。不得用 `float`，不得用市场页 60 秒 REST cache 回填执行 gate。

### 5.2 无人为 stale 秒数

`bookTicker` 在最优价或最优量变化时推送；静止盘口不必为了“时间老”而虚构失效。V1 不另造 1 秒/5 秒 stale TTL：

- 当前连接 generation 收到首条合法消息后为有效；
- watcher 抛错、断开或进入重连时，该侧立即 invalid；
- 重连后的旧 generation 不可复用，必须等新 generation 首条合法消息；
- 每次任一侧更新，都用“该侧新值 + 另一侧当前 generation 的 latest”评估一次；两交易所消息没有原子同时刻，V1 接受 latest/latest 近似，不增加人为时间窗。

5 分钟到期或 `成交1次` 可绕过这组行情有效性要求，随后仍经过现有立即开单安全门。

## 6. 每轮 gate 的精确语义

### 6.1 轮次身份和生命周期

gate 身份为 `(task_id, next_attempt_seq)`，其中 `next_attempt_seq = scheduled_attempt_count + 1`。只有满足以下条件时 worker 才能建立 gate：

- task 是 `open + smooth + running`；
- Start gate 开启；
- 没有本任务未终态 legs；
- `scheduled_attempt_count < target_n`。

建立 gate 时持久化其 seq、开始时间和 force flag；这样服务进程重启后继续同一轮的剩余 5 分钟，不把固定等待重新计满，也不会丢掉已经由接口接受的人工放行。停机时间计入这 5 分钟，因此恢复时 deadline 已过可立即形成 `timeout` 候选；这是“固定墙钟窗口、不因维护静默延长”的明确结果。**2026-08-13 更正（D15/D16）**：恢复后的实际发单路径是——若 `scheduled_attempt_count == 0`（首轮尚未调度），先按 D16 在订阅与 gate 恢复之前完成该任务唯一一次杠杆设置；随后仍须经过任务状态、Start gate 与 `prepare_attempt` 的原子复核才可能发单。smooth 已不再有每轮 fresh preflight 可拦（原文此处的“现有 preflight”对 smooth 不再成立，对 immediate 不变）。attempt prepare 前任何 `running → 非 running`（Human pause、系统因 preflight/限流等暂停、delete、终态）以及 Start gate 关闭都清掉活动 gate；再次 Start 为仍未调度的 seq 建一个新的完整 5 分钟 gate。仅进程停止/崩溃而 task 仍是 running 时续原 gate。

三个事件竞争同一 gate：

1. 当前方向 `spread_pass && spot_coverage_pass && perp_coverage_pass`；
2. `now >= gate_started_at + 5min`；
3. `force_requested == true`。

worker 根据快照、deadline 和 force flag 得出候选 `pass_reason = market | timeout | manual`，再把 `expected_gate_seq + pass_reason` 传给现有 reserve/prepare 路径。store 必须在创建 attempt、写入 pass_reason、递增 `scheduled_attempt_count`、清空当前 gate 的**同一个事务**内重查：gate seq 仍活动、task running、次数未满、无在途 pair；任一不满足则不生成 attempt、不联系 executor。这样不存在“gate 已 consumed、attempt 尚未 prepare”的持久化中间态：事务前崩溃，gate 仍在；事务后崩溃，沿用现有 PREPARED client-id 查询恢复且绝不重发。

### 6.2 等待与唤醒

平滑 gate 不允许让 `_worker_round` 在无在途 legs 时空转：

- 每个活动 gate 有一个进程内 `threading.Condition` 和递增 `wake_version`，只负责唤醒，不作为持久化事实；
- worker 在 condition 锁内记住 `wake_version`，锁外重读 task/gate/Start gate 和两侧 immutable snapshot；未通过时用 `wait_for(version 已变化, timeout=deadline 剩余秒数)` 等待“WS 更新、人工 force、task pause/delete、Start gate 变化、service stop 或 deadline”中任一个，避免 clear/set 的丢唤醒竞态；
- `post_fill_once` 先持久化 force，再幂等调用 `ensure_worker` 并通知 event；worker 已存在时不会产生第二 owner，worker 丢失时不会出现“接口 200 但无人消费”；
- pause/delete/Start gate 变化要通知这一独立 gate event，使 worker 立即重读状态退出；不复用当前只服务停止/在途查询的 `_stop_events`，也不改变在途 pair 必须 drain 的既有语义；
- timeout 使用持久化 wall-clock deadline；测试注入 fake clock，不真实 sleep 5 分钟。

### 6.3 开单率

实现必须直接调用现有 `compute_opening_spread_pct(perp_bid, spot_ask)` 和 `compute_opening_spread_pct(spot_bid, perp_ask)`，不得复制公式。返回值已经是 `_OPENING_SPREAD_QUANT = Decimal("0.01")`、`ROUND_HALF_UP` 后的百分数；将其解析回 Decimal，与同为两位小数的 `threshold_pct` 做严格 `>`。

例：阈值 `-0.10`，当前 `-0.05`，通过；当前 `-0.20`，不通过。

严格比较舍入后两位值意味着真实未舍入值至少要进入下一显示档才会通过。例如阈值 `0.05` 时，任务卡仍显示 `+0.05%` 的任何值都不会成交；这是有意的显示/判断一致性，不是精度缺陷。

### 6.4 80% 一档覆盖

覆盖比较针对**本轮将要发送的完整腿量**，不是任务总剩余量：

```text
spot_coverage = executable_spot_l1_base_qty / task.q_common
perp_coverage = executable_perp_l1_base_qty / task.q_common
coverage_pass = spot_coverage >= 0.80 && perp_coverage >= 0.80
```

- forward：现货用 askQty，合约用 bidQty；
- reverse：现货用 bidQty，合约用 askQty；
- 分母只取建卡时已经固化并展示的 `task.q_common`，不得误用 USDT 金额或在每个 WS tick 重跑 private preflight；当前可达普通 symbol 的现有两腿发送同一基础币量；
- P0 必须证明 CCXT/Binance 返回数量与基础币 `q_common` 同量纲，并对当前可达 symbol 断言 `contractSize == 1`；不满足或无法证明时 snapshot invalid，5 分钟内不得按市场条件放行；1000x symbol 继续由现有 `multiplier_contract_unsupported` 拒绝，本轮禁止用通用 contractSize 乘法暗中恢复；
- 价格和数量都来自形成该方向开单率的同一 latest snapshot；
- `>= 80%` 通过，79.99% 不通过；
- 实际发送仍是原完整两腿数量，不因 coverage 修改数量。

**2026-08-13 更正（D15 之后）**：dispatch 对 smooth 不再重新读取 preflight/filter，因此判定分母与实际发送量恒为同一个建卡固化 `q_common`，原先“fresh 数量可能与建卡不同”的小概率差异对 smooth 不再存在。随之消失的是每轮以交易所最新过滤器复核数量的能力——这已计入 D15 的接受代价。immediate 保持原状：仍每轮 fresh preflight，仍以交易所过滤器正确性为先。

## 6.5 首轮杠杆前置与放行后的零联网路径（D15/D16）

一个 smooth 任务从“开始执行”到“发出订单”，顺序被固定为：

```text
（建卡时，不变）create_task 首次完整 preflight → 固化 q_common / position_side_mode /
                preflight_snapshot(route) → regular_spot forward 预划转 → 缺腿/乘数合约拒绝
        ↓
（执行入口，D16 新增）live && smooth && scheduled_attempt_count == 0
        → 该任务唯一一次合约杠杆设置
        → 失败：leverage_set_failed 暂停 + 中文原因；此时零订阅、零 gate、零 attempt、零订单
        ↓
        订阅现货/合约两个 watcher → 建立或恢复 gate → 第一次滑点计算
        ↓
        每轮：WS 更新时评估「当前方向开单率严格 > threshold」且「两腿一档各 >= 80% q_common」
        ↓
（D15）market / manual / timeout 任一放行
        → 不调用 HedgePreflightProvider.get_snapshot
        → 直接用固化的 q_common / position_side_mode / preflight_snapshot(route) 构造既有请求
        → prepare_attempt 原子复核（task 状态、target、无在途 pair、gate seq、pass reason）
        → 既有 _dispatch_live 两腿异步提交 → 同步等返回 → 查单 → 结算
```

硬约束：

- 从任一次 gate 判定通过到 `prepare_attempt` / `_dispatch_live` 之间，**不得再发生任何联网读取、交易所设置、sleep 或其他阻塞调用**。这条是 D15 的目的本身，不是附带优化。
- `_dispatch_one_for_task` 对 smooth 不得再设置杠杆；immediate 仍在自己的首个 attempt 前按现状设置。
- `prepare_attempt` 的原子复核、两腿并发提交、查单、结算、单腿暂停链一律不变；不复制 executor，不新建 smooth 专用下单实现。
- 后续轮次不重复设置杠杆；首轮尚未产生 attempt 就因失败或进程重启重新进入执行入口时，可在任何订阅/gate 之前幂等重试。

## 6.6 Human 启动与放行延迟审计（D17–D19）

smooth 创建仍完成既有首次 preflight、身份/数量固化与必要的 regular-spot 预划转，但 INSERT 必须直接写成 `paused + awaiting_manual_start`，并且创建请求不得调用 `ensure_worker`。Human 在任务卡点击“启动”后只复用现有 `post_start`：先把任务改为 `running`，再由同一 task worker 执行 D16 杠杆、订阅、gate 与后续轮次。未点击启动前必须是零订阅、零 gate、零 attempt、零订单；`成交1次` 不能绕过首次启动。

每次 `market` / `manual` / `timeout` 放行形成一份只读审计对象，至少包含：gate seq、放行原因、方向、阈值、实际参与判定的 spot/perp 一档原始 Decimal 字符串与接收时间、当次 spread/两腿 coverage/pass 结果、放行 wall-clock 时刻。该快照必须来自**产生放行结论的同一次读取**，不得放行后再调用 `latest()` 拼一份看似对应的盘口。

同一审计对象以放行 monotonic 时刻为零点，记录以下相对微秒：进入 `_dispatch_one_for_task`、请求参数组装完成、`prepare_attempt` 开始/提交完成、进入 live executor、现货/合约线程各自启动、两腿各自开始调用订单客户端、两腿订单客户端返回、两腿线程完成、executor 返回。持久化时同时给出相邻阶段耗时和 `gate→spot order client` / `gate→perp order client` 总耗时，字段名称须明确“订单客户端调用开始”而不是宣称网络包已离开机器。

审计不得反过来制造延迟：放行到两腿订单客户端调用之前，不新增日志 SQL、网络请求、sleep、同步输出或锁；`prepare_attempt` 的 durable-before-send 原子写仍是资金安全硬门，必须保留并单独计时。两腿 executor 返回后，以现有 `hedge_open_log` 追加 `kind=smooth_dispatch_audit`；失败只丢审计、不得回滚或改写已经发生的订单。任务专属日志 GET 以新增的 `smooth_dispatch_audits` 字段返回这些记录，前端本轮不新增延迟面板。

## 7. `成交1次` 的并发契约

平滑任务的动作可继续使用现有 `/fill-once` 路由和按钮，但 service 按 mode 分流：

- immediate/现有其他模式保持当前行为，不在本轮改写；
- smooth 只执行原子 `force_current_gate(task_id, gate_seq)`，成功后幂等 `ensure_worker` 并唤醒 gate event；它仍然不直接调用 dispatch；
- 请求不携带或携带已过期 gate seq 时，后端以当前 task 文档返回冲突，不猜测下一轮；前端点击时提交卡片上最近读取到的 gate seq；
- 接口只有在 gate 仍活动、任务 running、未达目标、无在途 pair 时接受；否则 409 且不改变 task；
- 重复相同请求幂等地保持该 gate 的 force flag，不会累积“次数”；
- Human 点击、WS 更新、timeout 同时发生时，只有 worker 能把该 gate 与 attempt 在一次 prepare 事务中绑定；按钮线程绝不直接 dispatch；
- gate 被成功 prepare 后，卡片立刻不再提供活动 seq；即使旧按钮请求晚到，也只能 409，不能作用于下一轮。

为避免收起日志后卡片缓存的是旧 seq，点击 `成交1次` 时前端必须先走现有日志 GET 立即刷新一次，取得当前 `smooth_gate_seq` 后再 POST；GET 与 POST 之间若 gate 已推进，409 是正确的安全结果。smooth + 非 running 或读不到活动 seq 时按钮禁用；这与 immediate 任务当前 fill-once 行为有意不同。

这个 seq 绑定是对“10/10 自然通过同时点击”场景的直接防护：第 10 gate 只被消费一次；随后 store 的 `scheduled_attempt_count >= target_n` 使任何第 11 gate 都无法建立。

## 8. API、持久化与 UI 契约

### 8.1 创建任务

创建 body 增加：

```text
slippage_threshold_pct: decimal string
```

- `mode=smooth` 必填，前端默认提供 `"0.05"`；服务端仍必须独立校验；
- 规范化允许 `-12`、`0`、`0.05`、`.05`（归一为 `0.05`），最多两位小数；拒绝空、NaN、Infinity、科学记数和 `%` 字符；
- `mode=immediate` 不使用该字段，前端不发送；
- 任务创建后把规范值固化到 task，页面输入变化不追改旧任务。
- smooth 创建成功后状态固定为 `paused`，暂停原因使用既有 `awaiting_manual_start`（中文改为任务通用措辞）；创建响应不启动 worker。首次 preflight、固化数据及 regular-spot 预划转仍发生在建卡阶段，immediate 创建语义不变。

任务确认弹框和任务卡都显示“滑点阈值：`x.xx%`”，并说明实际比较的是“当前方向开单率”。

### 8.2 任务读模型

平滑 task 文档至少增加：

- `slippage_threshold_pct`；
- `smooth_gate_seq`、`smooth_gate_started_at`、`smooth_gate_deadline_at`；
- `smooth_gate_force_requested`；
- `smooth_gate_state` 的展示派生值。

任务级持久化只承担跨重启和按钮绑定所需事实，不把每个 WebSocket tick 写入 SQLite。

最小 schema 形态：task 增 `slippage_threshold_pct TEXT`、`smooth_gate_seq INTEGER NULL`、`smooth_gate_started_at_us INTEGER NULL`、`smooth_gate_force_requested INTEGER NOT NULL DEFAULT 0`；deadline 由固定 5 分钟和 started_at 派生，不重复落列。attempt 增 `smooth_pass_reason TEXT NULL`，与 attempt prepare 同事务写入。不存在单独的 `consumed` 状态或任务级“最近 pass”重复字段。

### 8.3 动态盘口读模型

沿用 `GET /api/hedge-open-logs?task_id=...` 这条已存在的展开日志读请求，在返回中增加当前 task 的 `smooth_market`，前端一次请求同时更新日志表和盘口块，不新增端点和 timer。字段包含：

- spot/perp 连接状态与最后接收时间；
- 四个一档价格和数量；
- `forward_spread_pct`、`reverse_spread_pct`；
- 两腿 coverage 百分比及 pass；
- spread pass、整体 gate pass、当前等待原因。

同一路由在 task_id 模式下再增加 additive `smooth_dispatch_audits` 数组，元素是 `kind=smooth_dispatch_audit` 的结构化日志；只记录公共盘口、阶段名、相对耗时、task/attempt/gate 身份，不记录凭证、签名、完整 URL 或私有账户响应。现有 `logs=[]`、`attempts`、`smooth_market` 字段语义不改，前端可忽略该新增字段。

执行判断以 backend cache 为唯一权威；前端只展示，不自行重算 gate。

### 8.4 页面位置与刷新

每个正向/反向操作单元：

```text
[平滑开单] [ 0.05 ] %    [立即开单]
```

任务卡盘口块按市场页格式展示：

```text
正向开单率
合约买一 <price>  数量 <qty>
现货卖一 <price>  数量 <qty>
+0.05%

反向开单率
现货买一 <price>  数量 <qty>
合约卖一 <price>  数量 <qty>
-0.03%
```

任务卡始终显示固化 threshold；只有 `status=running` 才渲染由日志 GET 填充的 gate/倒计时、连接、正反向盘口和覆盖率块。非 running 卡隐藏整个动态块，不能渲染“数据不完整”的占位。**共享 2 秒 tick 在任务标签页内先刷新任务列表，再为“所有 running 任务”与“仍存在且日志已展开的非 running 任务”的去重并集请求 task-id 日志；running 任务日志收起只隐藏日志表，不停止动态数据请求。** 页面首次加载、浏览器刷新、进入开单任务页或 Start 成功后的第一次 `loadHedgeTasks()` 走同一路径，running smooth 即使 `hedgeLogExpanded` 为空也能立即显示真实盘口。非 running 任务收起或任务不存在时停止自动刷新并保留最后值。启动成功沿用现有自动展开与立即 GET。收起态点击 `成交1次` 会额外执行一次同源 GET 只为取得当前 gate seq。`connecting/disconnected/incomplete` 只可能出现在 running 动态块中，且必须显示 `—`，不得把旧值涂成 fresh。

## 9. 超时、暂停、故障与收尾

- WS 一侧失败：只使该侧 invalid，另一侧 watcher 继续；库按自身机制重连，不自造第二重固定退避。**2026-08-13 补充**：本条“不自造退避”指不叠加第二套指数退避/重试状态机，**不等于允许零等待重试**——watcher 在异常分支与“立即返回无效快照”分支重试前必须有一个简单固定最小等待，否则库同步抛错时该循环会自旋（见 §16 的必修项 4）；
- 5 分钟内 WS 恢复：收到新 generation 首条有效消息后继续正常判断；
- 5 分钟到期仍无双侧有效数据：以 `timeout` 通过当前平滑 gate，再走立即开单；
- Human 点击 `成交1次`：以 `manual` 通过当前 gate，再走立即开单；
- task pause/delete、Start gate 关闭：不得因已有 timeout/force 在后台继续开新 pair；恢复后按 §6.1 建新 gate；
- dispatch 前 preflight incomplete、路由变化、限流、余额不足等：**对 immediate 完全沿用立即链的暂停/退出规则不变**。**2026-08-13 更正（D15）**：smooth 放行后不再执行每轮 fresh preflight，因此这些事实不再在发单前被拦截；它们改为以交易所拒单的形式出现，由既有的单腿告警、`insufficient_*` / `rate_limited` 等原因暂停和 Human 人工核对收口。平滑 gate 仍不把这些失败改写成行情失败；
- task pause/delete 之后仍在 drain/settle 在途订单时：任务卡日志与 attempt/腿状态必须继续可见（见 §16 必修项 5），不能因为任务已非 `running` 就停止刷新；
- 两腿有一个 UNKNOWN 或已受理：沿用保存的 client order id 查询，绝不因平滑 retry 重发；
- pair 结算后若还有计划轮次，才建立下一 gate；没有两轮并行等待。

## 10. V1 非目标

- 不订阅或维护完整 order book；
- 不用盘口深度估算整笔 VWAP，也不改 Market 为限价单；
- 不动态调整下单数量，不拆分单个 pair；
- 不把资金费率加入 gate 公式；负阈值已允许 Human 自己表达“愿意接受差价折损”；
- 不提供阈值动态编辑、每轮不同阈值、不同等待时长或不同 coverage；
- 不实现 `立即成交所有`；
- 不接私有订单 WebSocket；
- 不改变立即开单、平仓、借币、还款、划转和其他交易所的资金执行；
- 不承诺仅靠 CCXT Pro 就完成其他交易所接入。

## 11. 已完成的只读 proof

结论：**已完成并由 Bookkeeper 核验，结果为 `continue-with-ccxt`（条件性）。**

执行边界：仓库外隔离 venv、`ccxt==4.5.64`、无凭证公共行情；未接任务 worker/executor，未修改依赖清单或生产环境。报告、脚本和原始输出分别为 `docs/planning/ccxt-bookticker-recon-2026-08-13.md`、`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py` 和 `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt`。

已证明：

1. 同一普通 symbol 同时收到 spot/perp `watchBidsAsks`；raw `info` 含所需字段，normalized 价量为 float，adapter 必须保留 raw `b/B/a/A` 字符串；
2. 普通 BTC U 本位永续 `contractSize == 1`，与当前 `q_common` 同量纲；1000PEPE 同样报告 `1.0`，不能用于解除现有 1000x 封禁；
3. spot 缺 `E/T` 且 CCXT `timestamp=None`，perp 有 `E/T`；spot 必须使用本地 `received_at_us`；
4. 两个独立 client/task 并发工作，取消 spot watcher 后 perp 仍持续更新；
5. `close()` 正常返回；公共样本无凭证、无私有流、无订单/账户/资产调用。

尚待 P1 证明：断线/异常后的 generation 失效与恢复、延迟消费者隔离、引用归零、最后订阅释放、close 后零 CCXT 内部 task、多 symbol 共享。P1 未通过时停止资金链集成并切原生 fallback。

proof 失败时停止，不接资金 worker；改用 Binance 原生 public bookTicker adapter 作为备选，不改变本设计的 `BestBidAskProvider`、gate 和 UI 契约。

## 12. 交付拆分与评审拓扑

本功能涉及订单触发时机、任务次数硬上限和实盘资金路径，整体为 **HIGH_RISK**。实现开始前需要一次跨 provider 的独立只读计划评审；交付后必须 Review-1 + Review-2。任何 ACCEPT 都不授权启动服务或实盘下单。

### Human 2026-08-13：两项非资金前置（已完成）

在正式集成和正式计划评审之前，先完成两项互不依赖的前置产物：

1. **Kimi 前端 fake 样式**：只改前端，展示平滑按钮后的 `0.05 %` 输入框，并在任务页“执行中”区域加入一张明确标注“样式预览、不执行”的 fake 平滑任务卡。所有 fake 动作禁用，不发送 smooth 创建、fill-once 或任何真实请求；现有立即开单行为不变。它只用于 Human 看布局、文案和信息密度。
2. **Claude-GLM CCXT 公共行情摸排**：只研究/验证后续会用到的 `watchBidsAsks`、spot/USDⓈ-M client、symbol、bid/ask volume 单位、contractSize、双独立 watcher、重连、取消和 close。允许访问公开文档/源码和在隔离临时环境连接公共行情；禁止读取凭证、连接私有流、安装进生产 `.venv`、启动本服务或调用订单/资产接口。

两项均已完成；P0 证据已回填本设计。fake UI 不冻结最终 API 字段；CCXT 摸排不授权把依赖接入生产。下一步由 Opus 5 根据 `docs/planning/smooth-open-orders-v1-development-checklist.md` 细拆独立 worktree、文件所有权、依赖次序与验收命令，之后再进入正式跨 provider 计划评审。

### P0：公共 WebSocket proof（只读、独立）

- **完成**：候选版本 `ccxt==4.5.64`；结论 `continue-with-ccxt`（条件性）；未修改 worker/executor、依赖清单或生产环境。
- P1 必须关闭 §11 的未证事项；失败则切 Binance 原生备选。

### P1：后端市场数据 provider 与确定性假源

- 实现共享 watcher lifecycle、generation invalidation、Decimal snapshot；
- 用 fake async sources 测两侧独立更新/失败/恢复/释放；
- 尚不接订单 worker。

### P2：持久化 gate、任务 API 与 worker 接入

- 固化 threshold、gate seq/start/force；
- 解除 create_task 的 immediate-only 和前端 `smooth_next_round`/disabled 冻结；smooth fill-all 明确拒绝/不展示；
- 实现 5 分钟、80%、严格 `>`、manual/timeout/market 三种候选原因；pass_reason 与 attempt prepare 同事务；
- 用独立 gate event/condition 阻塞等待，由 WS、force、暂停/删除、Start gate、service stop 和 deadline 唤醒，禁止 busy loop；
- gate 通过只调用现有 `_dispatch_one_for_task`；
- 全部使用 fake clock、fake market provider、record executor 验证，不发真实订单。

### P3：前端

- 启用平滑按钮，增加带 `%` 的 signed threshold 输入和确认回显；
- 任务卡添加动态盘口块；复用开单率 formatter 和展开日志 2 秒读链；
- smooth 的 `成交1次` 提交当前 gate seq；隐藏 `立即成交所有`。

### P4：契约、回归和两轮独立评审

- 同步 API schema、产品/架构/开发文档；
- 跑后端、前端 self-check 及下列验收矩阵；
- Bookkeeper 固定 `base_sha..delivery_sha` 后进行 Review-1；ACCEPT 后由不同 provider Review-2；
- Human 最终决定是否合并、部署；首次公共 WS 连通和任何实盘验证均需再次明确授权。

后端 provider、持久化 gate 和 worker 接入高度耦合于同一服务生命周期，P1/P2 可分提交但不可由两个 implementer 同时修改 `service.py`。前端可在 P2 的冻结 API 契约后独立实施。

## 13. 验收矩阵

1. **阈值输入**：默认 `0.05`；正、零、负合法；超过两位小数、科学记数、`%`、空值被前后端拒绝；任务保存十进制字符串。
2. **严格比较和同屏一致**：阈值 `0.05` 时显示 `+0.05%` 不成交、`+0.06%` 成交；负阈值例符合 §6.3；前端不二次乘 100。
3. **方向价格**：forward 只用 perp bid + spot ask；reverse 只用 spot bid + perp ask；任一操作数非法只使对应方向 unavailable。
4. **80%**：分母是 `task.q_common`；两腿均为 80% 时通过；任一腿 79.99% 不通过；P0 证明普通合约 BookTicker qty 同量纲且 `contractSize == 1`，非 1/不明则 invalid；1000x 仍无法建卡；实际下单量仍为 100%。
5. **独立订阅**：一侧延迟、异常、重连不阻塞另一侧的更新计数；断侧在新 generation 首条合法值前不可参与 market pass。
6. **latest/latest**：任一侧更新触发评估；没有人为同刻要求或 stale 秒数；市场页 REST 数据绝不进入 gate。
7. **5 分钟**：fake clock 在 4:59 不超时、5:00 超时；断流也在 5:00 进入既有下单链。**2026-08-13 更正（D15）**：此处仍能拒绝实际 dispatch 的是 Start gate、任务状态与 `prepare_attempt` 的原子复核；smooth 不再有每轮 fresh preflight 可拒。
8. **人工/自然竞态**：同一 gate 同时 market pass + manual 只 prepare 一个 attempt、只调用 executor 一次；同 gate 重复点击不累计；force 后 worker 丢失会由幂等 ensure_worker 恢复消费者。
9. **10/10 竞态**：第 10 gate 自然通过同时点击，最终只有 10 个 attempts、无第 11 次 executor 调用；无活动 gate 的 fill-once 返回 409。
10. **重启/崩溃缝**：事务前崩溃保留同一 gate，事务后崩溃只恢复 PREPARED attempt；不存在 consumed-without-attempt；同一 seq、原 deadline 和 force 均恢复，停机超过 5 分钟可形成 timeout 候选但仍过现有门；已有非终态 legs 只 query 不 resend。
11. **暂停/删除/Start gate**：等待中停止后不会因旧 timer/force dispatch；Human pause 后再 Start 会为仍未调度的同一 next seq 新建完整 5 分钟等待；进程恢复则续原 deadline；终态不保留活动 gate。
12. **原链复用**：两腿仍并发提交；单腿受理、UNKNOWN、429、余额不足、结算与 task 状态和 immediate 基线一致。**2026-08-13 更正（D15）**：“路由变化”对 smooth 不再在发单前拦截（frozen route 即为所用 route），改由交易所拒单与既有单腿处置收口；immediate 的路由变化拦截不变。
13. **任务卡**：正反向价格/开单率格式和市场页一致；threshold、coverage、连接状态可见；展开立即刷新；无额外 interval。**2026-08-13 更正**：只要任务仍存在且日志已展开，非 `running`（paused/deleted/done/stopped）在 drain/settle 期间也必须继续刷新，见 §16 必修项 5。
14. **订阅共享与释放**：两个同 symbol 任务只各占用一个 spot/perp watcher；最后引用释放才取消；专用 event-loop 线程 close/join 后无悬挂 async task。
15. **模式隔离**：immediate 创建、现有 fill-once、close 任务和 market REST opening quote 行为无回归；immediate 的每轮 fresh preflight 与杠杆设置时机逐字不变。
16. **首轮杠杆前置（D16）**：live smooth 且 `scheduled_attempt_count == 0` 时，杠杆设置发生在任何订阅、gate 建立/恢复与第一次滑点计算之前；失败时零订阅、零 gate、零 attempt、零订单并按 `leverage_set_failed` 暂停；后续轮次不重复设置。
17. **放行后零联网（D15）**：顺序型回归用 spy 断言调用顺序为 `set_leverage → subscribe/open gate → market evaluation → prepare_attempt → dispatch`；market pass 之后 `set_leverage` 与 `HedgePreflightProvider.get_snapshot` 的调用计数均不再增加；三种 pass reason 均适用。
18. **固化数据复用（D15）**：smooth 发出的两腿请求数量、position side 与 route 完全来自建卡固化值；`prepare_attempt` 的原子复核（状态、target、无在途 pair、gate seq、pass reason）与 immediate 一致。
19. **人工启动（D17）**：smooth 创建响应为 paused，零 worker/订阅/gate/attempt/订单；原始 Start 按钮可点击且 `post_start` 后才出现一次 worker。未经 Start 的 fill-once 返回 409，进程恢复也不领取这张 paused 卡。immediate 创建行为零 diff。
20. **任务卡可见性（D18）**：paused smooth 卡保留 threshold 和立即任务卡全部基础信息，但 DOM 中没有连接/正反向盘口/覆盖率块；Start 成功后的 running 卡用原展开日志链显示该块；再次 paused/done/stopped/deleted 时隐藏动态块，展开的 attempt 日志仍继续刷新。
21. **延迟审计（D19）**：fake monotonic clock 精确验证同一次 gate 快照、全部阶段顺序和分段耗时；错误实现若二次读盘口、在订单客户端调用前写审计日志、执行 fresh preflight/sleep，或漏记任一腿订单客户端调用边界，测试必须变红。审计写入发生在两腿 executor 返回后，写入失败不影响订单处置；immediate 不生成该审计。

## 14. 评审请求

请评审者重点回答：

1. `watchBidsAsks`→Binance bookTicker、spot/USDⓈ-M client 和 volume/contractSize 判断是否有遗漏的当前事实；
2. 持久化 gate seq + 单 worker + `prepare_attempt` 硬门，能否确实封住自然/人工/timeout 三方竞态和 10/10 多单；
3. 5 分钟断流后仍回退立即开单，是否被文档一致表达为 Human 的产品取舍，而不是误当 WS 安全门；
4. 复用当前开单率两位精度是否会产生判断/展示不一致；
5. 80% 覆盖的单位换算是否足以形成可执行契约；
6. 是否存在当前代码证据支持的资金安全缺口、不可测试点或不必要复杂度。

评审若提出新假设场景，应给出当前代码路径、官方契约或具体并发/单位证据，以及它对本交付的实际影响。只对偏好不同、已明确接受的市场风险或未来扩展不应判为阻塞。

## 15. 参考

- CCXT Pro manual：<https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual>
- CCXT Pro Binance source：<https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/binance.py>
- Binance Spot bookTicker：<https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#individual-symbol-book-ticker-streams>
- 当前开单率：`backend/domain/snapshot.py::compute_opening_spread_pct` / `build_opening_quotes`
- 当前任务 worker：`backend/hedge_open_tasks/service.py::_worker_round`
- 当前 attempt 硬门：`backend/hedge_open_tasks/store.py::prepare_attempt`
- 当前任务卡/盘口格式/2 秒刷新：`frontend/index.html`

## 16. 首轮交付后的已知限制与必修项（2026-08-13）

来源：固定交付 `e955bdd..24074b1` 的 Bookkeeper 核验 `verified-source-but-nonaccepting`（证据见 `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md` 的 `rejection_basis` 与 `reproducible_evidence`）。

### 16.1 Human 明确接受、本轮不修的三项具名限制

这三项是本次交付的已知限制，不是待办缺陷，也不再作为验收失败项。返修实现**不得**顺手修它们（那会扩大受审范围）。

| # | 事实 | 实际影响 | 临时操作方式 | 重开条件 |
|---|---|---|---|---|
| L1 | Start 总开关关闭或 `service.stop()` 可能恰好落在「行情放行」与「reserve/dispatch」之间 | 关闸后仍可能真实发出这一轮；或在错误时机转为模拟路径并消耗一次计划次数；快速 OFF→ON 可能复用旧 gate | 关闸后不要立即认定“已停止”，到任务卡与交易所确认这一轮的实际结果；需要确定停住时先暂停任务再关闸 | Human 实际遇到关闸后仍成交并造成困扰，或未来要求关闸具备强准入语义 |
| L2 | 新 gate 可能使用上一轮结算前捕获的旧 `now_us`，等待窗口因此短于完整 5 分钟 | 该轮实际等待时间被上一轮查单/结算耗时抵扣，可能提前进入 timeout | 把 5 分钟理解为上限而非精确值；对时间敏感时以任务卡显示的剩余时间为准 | Human 实际观察到明显缩短，或产品要求每轮严格满 5 分钟 |
| L3 | 60 秒整表刷新或单行重绘会把尚未提交的 threshold 输入恢复为 `0.05` | 输入到一半被重置，若未察觉就点按钮会用 `0.05` 建任务 | 点「平滑开单」前重新确认输入框里的数值 | Human 实际因此建错任务，或要求输入值在刷新间持久保留 |

**不得**为 L1 增加新的准入锁、`stopping` 中间状态或 store 侧 gate 复核；**不得**为 L2 改动时钟获取点；**不得**为 L3 扩大前端 capture selector。

### 16.2 本轮必修的五项根因

每项都有固定交付上的可复现证据；修复要求与验收命令写在 `docs/planning/smooth-open-orders-v1-development-checklist.md` §12。

1. **provider 并发冷启动僵尸订阅**：`start()` 对已 alive 但 loop 尚未 ready 的线程直接 return，且 `_ensure_smooth_subscriptions` 先登记 task_id 再逐个 subscribe 并吞掉异常——并发首次订阅可留下“已登记但没有 watcher”的僵尸态。
2. **`APP_OFFLINE=true` 仍构造真实公共 WebSocket provider**：组合根只看 `default_source_available()`，未判 `config.offline`；离线模式本应零构造、零线程、零订阅。
3. **超长 signed 整数 threshold 逃逸为服务异常**：合法字符（无科学记数、无 `%`、整数）但位数超出 Decimal 默认 context，`quantize` 抛 `InvalidOperation`，接口返回 500，而不是正常规范化并由创建接口接受（`201`）。这类输入是合法值，不应改判为 `400`；只有格式非法输入才返回 `400`。
4. **provider 持续异常/无效快照零等待热循环**：`_watch` 的异常分支与“立即返回无效快照”分支在重试前没有任何等待；零网络 always-fail 假源实测 0.1 秒约 15 万次回调，会同时空转 provider 线程并风暴式唤醒等待中的 worker。
5. **暂停/删除后仍在 drain/settle 时前端停止刷新展开日志**：`post_pause`/`post_delete` 明确不打断 worker（在途订单继续 drain/settle），而前端原只刷新 `status === 'running'` 且日志已展开的卡，导致这段时间新增的 attempt/腿状态在页面上不可见。修复后统一规则：所有 `status === 'running'` 的任务均刷新 task-id 日志（不再要求日志展开），非 running 任务仅在仍存在且日志已展开时继续刷新；收起或任务不存在时停止。

## 17. Human 页面验收后的窄修订（2026-08-13）

已观察任务 `36951966-6942-43e3-833c-99606ca3fae5` 在创建后自动 running 并以 `market` 放行。任务卡最初显示两侧“数据不完整”，展开日志后才显示 provider 实为 live；成交均价折算的 forward spread 约 `-0.465%`，但现有持久化只证明放行原因为 `market`，不能还原放行盘口或定位本地延迟。由此触发 D17–D19。

本轮不以成交均价倒推 gate 一定算错，也不恢复被 D15 删除的下单前二次行情校验。Market 单在放行后仍可能因行情变化和深度产生偏离；本次交付的目标是把 Human 启动边界改对、消除未启动卡的误导展示，并让下一笔的放行快照与本地分段耗时可审计。
