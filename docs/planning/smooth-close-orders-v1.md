# 平滑平仓 V1：设计上下文、决策记录与交付边界

状态：**设计草案，等待正式跨 provider 计划评审。未授权改源码、重启服务、创建任务、下单、push、merge 或部署。**
日期：2026-08-14
适用范围：现有对冲**平仓**任务（`task_type=close`）的 `mode=smooth`。立即平仓、立即开单、平滑开单均不是本轮改造对象，行为必须零回归。

## 1. 为什么要做

平滑开单 V1 已合并 `main`（产品 delivery `ad8c631`）：每一轮在发单前用 WebSocket 一档盘口等一个更好的开单率，最多等 5 分钟，等不到就按立即开单成交。Human 要求平仓具备镜像能力——功能和特点镜像平滑开单，并与立即平仓的流程保持一致。

产品目标与开单一致：不是"保证没有滑点"，而是用最优一档做一个低维护、低延迟的机会过滤器。Market 单实际成交仍可能受一档之后的深度和发送期间行情变化影响。

## 2. 现有事实与接入缝

### 2.1 平仓率不需要新公式，方向翻转即可复用

`backend/domain/snapshot.py::compute_opening_spread_pct` 已是唯一权威（Decimal、四舍五入到百分比两位）：

- 开单 forward = `compute(perp.bid, spot.ask)`
- 开单 reverse = `compute(spot.bid, perp.ask)`

平仓两腿方向与开仓相反（`domain.py:751`：`task_type='close'` 反转双腿方向）：

- 平仓 forward（现货 SELL 吃 spot 买一 + 合约 BUY 吃 perp 卖一）= `(spot.bid − perp.ask)/perp.ask` = **开单 reverse 公式**
- 平仓 reverse（现货 BUY 吃 spot 卖一 + 合约 SELL 吃 perp 买一）= `(perp.bid − spot.ask)/spot.ask` = **开单 forward 公式**

而 `domain.py::evaluate_smooth_gate`（`domain.py:1552`）在 reverse 分支取的正是 `spot.ask_qty→spot.bid_qty`、`perp.bid_qty→perp.ask_qty` 这一组，恰好是 forward 平仓两条腿实际吃的档位。**因此 `evaluate_smooth_gate` 一行不改**，只要传入翻转后的方向。

方向翻转在本仓已有两处先例：`service.py::_resolve_fresh_preflight`（`service.py:3033`）与 `create_task` 的 `preflight_direction`。本轮抽一个纯函数供三处共用，不新增第二套翻转规则。

### 2.2 平仓的发单前工作全部集中在 `_dispatch_one_for_task`

`service.py:3241` 的 `if live and task.get("mode") != D.MODE_SMOOTH:` 分支里，平仓比开单多做三件事：

| 门 | 位置 | 作用 | 网络/耗时 |
|---|---|---|---|
| fresh preflight | `service.py:3240` | filters / 价格 / position mode / 路由，**算出 q_common** | 联网读 |
| `_close_um_position_error` | `service.py:3268` / 定义 `2321` | 合约可平量 ≥ `q_common × 剩余轮次` | 缓存优先，缺则实时查 |
| `_ensure_close_spot_balance` | `service.py:3282` / 定义 `2247` | 仅 forward：普通现货账户余额不足则**真划转** + `time.sleep(0.1)` | 联网写 + 100ms |

平滑开单的 D15 硬约束是"放行到两腿提交之间不得有任何联网读取、交易所设置、sleep 或阻塞调用"。这三件事若留在原位，平滑平仓等于把 D15 作废；若照抄平滑开单直接跳过，forward 平仓的币根本没划到普通现货账户，现货腿必挂，稳定留裸多。**因此只能整体前移**（见 §4）。

`q_common = floor_to_grid(single_amount, lcm(spot_step, perp_step))`（`domain.py:1231`）——它不是用户输入值本身，而是输入币量向两腿共同网格向下取整的结果，立即平仓现在发出的就是这个值（`send_qty = q_common`）。平滑门的覆盖率分母必须用它，才能保证判定分母与实际发送量是同一个数。

### 2.3 平仓已是两阶段建卡，天然满足"人工启动"

`create_task` 的 close 分支（`service.py:880` 起）只做本地校验（活跃周期、身份继承、1000x 拦截），直接落 `paused + awaiting_manual_start`，不读 filters/余额/持仓、不划转、不建 attempt、不启 worker。这正是平滑开单页面验收后才补上的 D17 行为，平仓无需再改。

### 2.4 平仓闸门目前不参与平滑 gate 的唤醒

`_worker_round` 会在无在途腿时检查 `is_close_gate_on()`（`service.py:2100`），但：

- `_wait_for_smooth_gate` 的等待循环只检查 Start gate（`service.py:1858`），不检查平仓闸门；
- `put_close_gate`（`service.py:1538`）没有 `_notify_all_smooth()`，而 `put_start_gate`/`set_start_gate` 有。

结果是：关闭平仓闸门时，正在等待的平滑平仓 gate 不会被唤醒，最长要等到 5 分钟窗口自然到期。本轮必须补上。

### 2.5 连续失败刹车已经是 per-task 快照列

- 阈值列 `failure_pause_threshold`，建卡快照，默认 3（`domain.py:154`、`store.py:60`），已有窄 setter `store.set_failure_pause_threshold`；
- 计数器 `consecutive_submission_failures`：**提交失败**与**单腿成交**混算同一个计数器（`store.py:1244` / `1263`，R2-F1）；
- 成功一对归零（连续，不是累计）；达到阈值（`>=`）→ **暂停**，中文原因 `consecutive_submission_failure`；
- 例外不进计数器：交易所致命拒绝直接 `stopped`；429 单独 `rate_limited` 暂停。

`domain.py:152` 的注释明确预留了"may be 1 or 2"的用法，本轮平仓取 1 是使用既有能力，不是新机制。

### 2.6 前端平滑开关是 mode-based，不是 task_type-based

`index.html` 的动态盘口块（`6093`）、`成交1次` 的 gate_seq 绑定（`6008`）、隐藏"立即成交所有"（`6145`）都按 `task.mode === 'smooth'` 判定，平仓卡自动继承，只需改文案。

`deleted` 状态的卡片当前**没有**原因展示行：只有 stopped（`6134`）和 paused（`6164`）两种 note。C6 需要补一行。

## 3. 已定决策及前后因果

下表区分 Human 明确决定与为落实该决定不可缺少的最小实现约束。评审不应把已拍板的取舍重新当作待定需求；若发现它与代码事实或资金安全矛盾，应给出证据和实际影响。

| 编号 | 最终决定 | 之前考虑/现状 | 选择原因与实际后果 | 来源 |
|---|---|---|---|---|
| C1 | 平仓率 = 把任务方向翻转后调用现有 `compute_opening_spread_pct`；`evaluate_smooth_gate` 不改 | 可另写一套平仓价差公式 | §2.1 已证明两者数学上是同一族，翻转后连覆盖率取的档位都正确。第二套公式会产生第二个分母/精度/颜色口径 | 当前代码事实 |
| C2 | 滑点阈值默认 `0.05`，允许 0 和负数，最多两位小数，与开单率同精度**严格大于**比较 | 曾考虑按平仓常态给负默认值 | 输入框规则与平滑开单逐字一致，前后端各自独立校验。**已知后果**：正费率币常态是合约价高于现货，正向平仓率通常为负，阈值 `0.05` 意味着多数轮次等满 5 分钟后按 timeout 放行；需要提前成交时由 Human 逐任务填负值 | Human 2026-08-14 决定 |
| C3 | 不实现老 JS 的 `当前平仓率 + 开单率 > 0` 浮动门槛 | 旧 `positiveCloseCheck` 用开仓两腿成交均价算出开单率，与当前平仓率相加判往返不亏 | 阈值只按建卡时输入的百分比比较，与开仓成交价无关。省掉从活跃周期倒算开单均价的一整块（`open_slippage` 只在周期关闭时写，活跃期为 NULL，必须现算） | Human 2026-08-14 决定 |
| C4 | **备料只做一次**（每任务一次）：预检 + 合约可平量 + forward 现货余额/划转。暂停后恢复**跳过**备料直接继续 | 曾考虑每轮备料或每次 worker 启动备料 | 现货划转本就按"剩余轮次 × q_common"一次划足，重复做无意义；恢复不重做避免重复联网。**代价（Human 明确接受）**：冻结事实的陈旧期 = 建卡启动至今，暂停期间交易所侧变化（手工平仓、余额被他用）不再被发单前拦截 | Human 2026-08-14 决定 |
| C5 | 备料时机：点「启动」后、**订阅盘口与建立 gate 之前**；失败时零订阅、零 gate、零 attempt、零订单 | 平滑开单 D16 只前移杠杆设置 | 与 D16 同构：一次性交易所交互必须发生在"开始盯盘"之前而不是"决定成交"之后。备料是平仓版的 D16 | Human 2026-08-14 决定 |
| C6 | 备料失败 → 任务落 **`deleted`（页面「已删除」分类）** + 安全中文原因；Human 看原因后自行重新开卡 | 建议过用 `stopped`（已终止），因其卡片已有现成的中文原因渲染 | Human 选择软删除分类。**因此必须补**：`deleted` 卡片增加原因展示行（当前只有 stopped/paused 两种 note），否则中文原因不可见，该决定的目的落空 | Human 2026-08-14 决定 |
| C7 | 放行到两腿提交之间**不得有任何联网读取、交易所设置、sleep 或阻塞调用**（平滑开单 D15 同款） | — | 一档价差过滤的时效性是本功能的目的本身。备料前移正是为此 | Human 2026-08-14 决定（效率优先） |
| C8 | 平仓任务 `failure_pause_threshold = 1`：出现第一次**单腿成交或提交失败**即暂停 | 开单沿用默认 3 | 平仓的单腿会在"正在减风险"的时刻反而制造敞口（现货已卖、合约空单还在，或反之），继续平下一组会在敞口上叠加。零新代码：建卡时对 close 传 1 | Human 2026-08-14 决定 |
| C9 | 单腿的动作仍是**暂停**，不是终止 | 可改为 stopped | 暂停保留周期不关，人工处理完敞口点恢复即可接着平剩余次数；终止要重新开卡、重新备料、重新划转。且平仓有"合约无仓核实"收尾判定，暂停不会误触发 | 本轮最小范围结论 |
| C10 | 5 分钟固定窗口、`market / manual / timeout` 三种放行原因、gate 身份 `(task_id, next_attempt_seq)`、`成交1次` 携带 gate_seq、不提供「立即成交所有」——全部逐字沿用平滑开单 | — | 镜像要求。这些语义已由平滑开单 V1 的持久化 gate + `prepare_attempt` 原子复核封住三方竞态与超发，不重新设计 | Human 镜像要求 |
| C11 | 80% 一档覆盖率的分母 = 备料冻结的 `q_common` | 曾考虑直接用输入的 `single_amount` | §2.2：`q_common` 是输入向共同网格取整后的值，也是实际发送量。步长粗的币两者可差一整格，用输入值会让判定分母与发送量不一致 | 当前代码事实 |
| C12 | 平仓闸门接入平滑 gate：`put_close_gate` 唤醒等待中的 gate，gate 等待循环检查 `is_close_gate_on()` 并在关闸时 `clear_smooth_gate` | 现状只有 Start gate 有这条链（§2.4） | 否则关平仓闸门后 gate 最长空等 5 分钟才响应 | 落实 C10 的最小实现约束 |

## 4. 执行时序（硬约束）

```text
（建卡，不变）close 轻量建卡：活跃周期校验 → 身份继承 → 1000x 拒绝
              → paused + awaiting_manual_start，零联网、零 worker
        ↓
（Human 点「启动」→ worker 起来）
        ↓
（C5 备料，唯一的联网段，仅当尚未备料时执行一次）
        fresh preflight → 冻结 q_common / position_side_mode / preflight_snapshot(route)
        → 合约可平量门（q_common × 剩余轮次）
        → forward：现货余额检查 / 划转 / sleep(100ms)
        → 任一失败：任务落 deleted + 中文原因；零订阅、零 gate、零 attempt、零订单
        ↓
        订阅现货/合约两个 watcher → 建立或恢复 gate → 第一次滑点计算
        ↓
（每一轮，第 1…N 轮完全相同）
        WS 更新时评估「本任务平仓率严格 > threshold」且「两腿一档各 >= 80% q_common」
        → market / manual / timeout 任一放行
        → 【C7 零联网】直接用冻结参数组装请求
        → prepare_attempt 原子复核（任务状态、target、无在途 pair、gate seq、pass reason）
        → 既有 _dispatch_live 两腿并发提交 → 查单 → 结算
        → 单腿或提交失败一次（C8）→ 暂停（C9）
        ↓
（次数用完，不变）_verify_close_flat 实时查合约持仓 → flat 关周期 + 结算日志 /
                open 部分平完成 / failed fail-closed 暂停；forward 另做 USDT 回流
```

硬约束：

- 备料到 gate 之间、gate 放行到 `prepare_attempt`/`_dispatch_live` 之间，均不得新增联网、sleep 或阻塞调用；
- 暂停/恢复不重做备料（C4）；`q_common` 非空即视为已备料，不新增状态列；
- `prepare_attempt` 的 durable-before-send 原子写、两腿并发、查单、结算、单腿处置链一律不变，不复制 executor，不新建平仓专用下单实现；
- 立即平仓（`mode=immediate`）的调用顺序与位置逐字不变——备料代码被抽成独立函数后，立即平仓仍在原调用点调用它。

## 5. 接受的代价与新增风险（Human 已知）

1. **冻结事实的陈旧**（C4/C5/C7 的合并结果）：备料到实际发单之间，短则秒级，长则跨越多次暂停恢复。期间余额/保证金、交易规则、position mode、下单限频、现货路由、合约持仓若发生变化，不再有发单前拦截，改为以交易所拒单形式出现。
2. **手工平仓后恢复会撞单腿**：暂停期间 Human 在交易所手工平了仓，恢复后任务仍按原计划发单——合约腿 `reduceOnly` 会被交易所拒（这一层是安全的），但现货腿会照卖，结果是一次单腿。C8 的阈值 1 使其停在第一次，不会连着卖三次。
3. **划转后暂停/删除，币留在普通现货账户**：forward 平仓的备料会把币从统一账户划到普通现货账户；任务此后被暂停或删除时不会自动划回，需人工处理或由下次平仓使用。USDT 回流仍只在平仓完成（`_transfer_back_usdt`）时发生。
4. **默认阈值 0.05% 下多数轮次走 timeout**（C2 已说明），任务卡会大量出现 `timeout` 放行原因，这是预期结果而非故障。
5. 平滑开单 V1 已具名接受、本轮同样继承的三项限制（L1 关闸与放行的竞态窗口、L2 新 gate 可能使用上一轮结算前的 `now_us` 导致窗口略短、L3 前端整表刷新会重置未提交的阈值输入）在平仓侧同样存在，本轮**不修**，不得顺手扩大受审范围。

## 6. 契约

### 6.1 创建任务

- `mode=smooth` 解除 open-only 限制（`service.py:801`），close 分支同样要求公共盘口 provider 可用，否则 400 `smooth_market_unavailable`；
- `slippage_threshold_pct` 校验复用 `D.validate_slippage_threshold_pct`，默认前端提供 `"0.05"`，服务端独立校验；close 轻量建卡分支必须把规范值落库（当前该分支未传此字段）；
- close 建卡同时把 `failure_pause_threshold` 落 1（C8）；
- 创建后状态仍为 `paused + awaiting_manual_start`（§2.3，不变）。

### 6.2 任务读模型与持久化

- 复用平滑开单已有字段：`slippage_threshold_pct`、`smooth_gate_seq`、`smooth_gate_started_at_us`、`smooth_gate_force_requested`、attempt 的 `smooth_pass_reason`、日志 `kind=smooth_dispatch_audit`；
- 备料结果写入 task 行**现有**的 `q_common` 与 `preflight_snapshot` 两列（平仓卡当前为 NULL / `available:false`）；**不新增列、不新增状态**；
- `GET /api/hedge-open-logs?task_id=...` 的 `smooth_market` 与 `smooth_dispatch_audits` 字段语义不变。

### 6.3 UI

- 私有持仓面板平仓列镜像市场页开单列：`[平滑平仓] [ 0.05 ] % [立即平仓]`；确认弹框回显阈值并说明比较的是"当前方向平仓率"；
- 任务卡动态盘口块对 close 卡改标题为**平仓率**，展示参与判定的两腿价格与数量、覆盖率、gate 轮次与倒计时；仅 `status=running` 渲染；
- `deleted` 卡片新增中文原因展示行（C6）；
- 前端不自行重算 gate，执行判断以 backend 为唯一权威。

## 7. 非目标

- 不订阅或维护完整 order book，不做 VWAP 估算，不改 Market 为限价单；
- 不动态调整平仓数量、不拆分单个 pair；
- 不实现平仓的「立即成交所有」；
- 不改变立即平仓、立即开单、平滑开单、借币、还款、划转的任何行为；
- 不实现老 JS 的开单率补偿门槛（C3）；
- 不解除 1000x 乘数合约的平仓封禁；
- 不改动 §5 第 5 条列出的三项已具名接受的限制。

## 8. 验收矩阵

1. **方向翻转**：forward close 只用 `spot.bid` + `perp.ask` 与 `spot.bid_qty` / `perp.ask_qty`；reverse close 只用 `perp.bid` + `spot.ask` 与 `perp.bid_qty` / `spot.ask_qty`；任一操作数非法则该任务盘口 unavailable，不得按市场条件放行。
2. **阈值**：默认 `0.05`；正/零/负合法；超两位小数、科学记数、`%`、空值前后端均拒绝；超长合法整数正常规范化并建卡成功（不得 500）；建卡后固化，页面输入变化不追改旧任务。
3. **严格比较与同屏一致**：阈值 `0.05` 时任务卡显示 `+0.05%` 不成交、`+0.06%` 成交；负阈值同一数学比较；前端不二次乘 100。
4. **80% 覆盖**：分母是备料冻结的 `q_common`（非 `single_amount`）；两腿均 80% 通过、任一腿 79.99% 不通过；实际发送量仍为 100%。
5. **备料一次**：全任务生命周期内 `_resolve_fresh_preflight` / 持仓查询 / 划转各自最多发生一次；暂停→恢复→再暂停→再恢复后，调用计数不增加；用 spy 断言顺序为 `备料 → subscribe/open gate → 行情评估 → prepare_attempt → dispatch`。
6. **备料失败**：预检不完整、合约可平量不足、现货余额/划转失败三类各自使任务落 `deleted` 且带对应中文原因；此时零订阅、零 gate、零 attempt、零订单；前端 `deleted` 卡片可见该中文原因。
7. **放行后零联网**：三种 pass reason 下，放行之后 `get_snapshot`、持仓查询、`universal_transfer`、`set_leverage`、`sleep` 的调用计数均不再增加。
8. **单腿刹车**：close 任务建卡后 `failure_pause_threshold == 1`；一次单腿成交即暂停（`consecutive_submission_failure`），一次确认提交失败亦然；敞口仍被记录；开单任务的阈值仍为 3（零回归）。
9. **5 分钟**：fake clock 在 4:59 不超时、5:00 超时；断流也在 5:00 走既有下单链；仍受任务状态、Start gate、平仓闸门与 `prepare_attempt` 原子复核约束。
10. **平仓闸门**：等待中关闭平仓闸门 → gate 被立即唤醒、清空、worker 退出（不等满 5 分钟）；重新开闸后为仍未调度的同一 seq 建新的完整窗口。
11. **人工/自然竞态与 N/N 竞态**：同 gate 同时 market pass + manual 只 prepare 一个 attempt、只调 executor 一次；最后一轮自然通过同时点击不产生第 N+1 单；无活动 gate 的 fill-once 返回 409。
12. **重启/崩溃缝**：事务前崩溃保留同一 gate，事务后崩溃只恢复 PREPARED attempt；恢复不重做备料；已有非终态腿只 query 不 resend。
13. **收尾不变**：次数用完仍走 `_verify_close_flat` 三分支（flat 关周期 + 结算日志 / open 部分平完成 / failed fail-closed 暂停）；forward 的 USDT 回流不变。
14. **模式隔离（零回归）**：立即平仓的预检与三道门调用点、顺序与行为逐字不变；立即开单、平滑开单、市场页 REST 开单率无回归。
15. **订阅共享与释放**：同 symbol 的平仓与开单任务共用一个 spot/perp watcher；最后引用释放才取消；无悬挂 async task。
16. **延迟审计**：平仓放行同样产出 `smooth_dispatch_audit`，快照来自产生放行结论的同一次读取；审计写入发生在两腿 executor 返回后，写入失败不改变订单处置。

## 9. 交付拆分与评审拓扑

本功能涉及订单触发时机、平仓资金准备与实盘资金路径，整体为 **HIGH_RISK**（`AGENTS.md` §8）。实现开始前需要一次跨 provider 的独立只读计划评审；交付后必须 Review-1 + Review-2。任何 `ACCEPT` 都不授权启动服务或实盘下单。

- **P1 后端**：备料前移（抽函数 + 立即平仓原地调用 + 平滑平仓 gate 前调用）、方向翻转、gate 与平仓闸门接线、建卡放行 smooth close 与阈值 1；全部用 fake clock / fake market provider / record executor 验证，不发真实订单。
- **P2 前端**：持仓面板平仓列的平滑按钮与阈值输入、任务卡"平仓率"文案、`deleted` 卡片中文原因行。
- **P3 契约与回归**：同步 API schema 与产品/架构/开发文档，跑后端与前端 self-check 及本文件 §8 验收矩阵。

P1 与 P2 可分派不同 implementer，但 P2 必须在 P1 冻结 API 契约之后开始；两者不得同时修改同一文件。

## 10. 参考

- 平滑开单 V1 设计与已接受限制：`docs/planning/smooth-open-orders-v1.md`（D1–D19、§16 L1–L3）
- 开单率唯一权威：`backend/domain/snapshot.py::compute_opening_spread_pct`
- 平滑门：`backend/hedge_open_tasks/domain.py::evaluate_smooth_gate`、`service.py::_wait_for_smooth_gate`
- 平仓三道门：`service.py::_resolve_fresh_preflight` / `_close_um_position_error` / `_ensure_close_spot_balance`
- 平仓收尾：`service.py::_verify_close_flat` / `_finalize_close_task` / `_transfer_back_usdt`
- attempt 硬门：`backend/hedge_open_tasks/store.py::prepare_attempt`
- 连续失败刹车：`domain.py::resolve_status_after_attempt`、`store.py` 的 `failure_pause_threshold`
- 老 JS 产品框架（仅框架，不复用实现）：`币安套费率策略，逐仓杠杆.js::checkSmoothOpenOrClose` / `positiveCloseCheck`
