# 平滑平仓 V1：设计上下文、决策记录与交付边界

状态：**设计 r3（第二次计划评审后的返工稿），等待第三次跨 provider 只读计划评审。未授权改源码、重启服务、创建任务、下单、push、merge 或部署。**
日期：2026-08-14（r1 → r2 → r3 同日修订，修订依据见 §11、§12）
适用范围：现有对冲**平仓**任务（`task_type=close`）的 `mode=smooth`。立即平仓、立即开单、平滑开单均不是本轮改造对象，行为必须零回归。

## 1. 为什么要做

平滑开单 V1 已合并 `main`（产品 delivery `ad8c631`）：每一轮在发单前用 WebSocket 一档盘口等一个更好的开单率，最多等 5 分钟，等不到就按立即开单成交。Human 要求平仓具备镜像能力——功能和特点镜像平滑开单，并与立即平仓的流程保持一致。

产品目标与开单一致：不是"保证没有滑点"，而是用最优一档做一个低维护、低延迟的机会过滤器。Market 单实际成交仍可能受一档之后的深度和发送期间行情变化影响。

## 2. 现有事实与接入缝

### 2.1 平仓率不需要新公式，方向翻转即可复用

`backend/domain/snapshot.py::compute_opening_spread_pct`（`snapshot.py:613`，签名为 `(bid, ask)`，**没有 direction 形参**）已是唯一权威（Decimal、四舍五入到百分比两位）：

- 开单 forward = `compute(perp.bid, spot.ask)`
- 开单 reverse = `compute(spot.bid, perp.ask)`

平仓两腿方向与开仓相反（`domain.py::direction_to_leg_actions` 在 `task_type=close` 时交换两腿 side）：

- 平仓 forward（现货 SELL 吃 spot 买一 + 合约 BUY 吃 perp 卖一）= `(spot.bid − perp.ask)/perp.ask` = **开单 reverse 公式**
- 平仓 reverse（现货 BUY 吃 spot 卖一 + 合约 SELL 吃 perp 买一）= `(perp.bid − spot.ask)/spot.ask` = **开单 forward 公式**

而 `domain.py::evaluate_smooth_gate`（`domain.py:1552`）的 reverse 分支取的正是 `spot.bid_qty` / `perp.ask_qty`，恰好是 forward 平仓两条腿实际吃的档位。**因此 `evaluate_smooth_gate` 一行不改**，只要传入翻转后的方向。

**r2 更正**：r1 曾称"方向翻转在本仓已有两处先例"。实测只有 `_resolve_fresh_preflight`（`service.py:3033`）一处真正在用；`create_task` 里的 `preflight_direction` 三元表达式在 `service.py:941`，而 close 的轻量建卡分支在 `service.py:901` 已经 return，**该分支对 close 是不可达代码**，不构成先例。翻转必须由本轮显式覆盖 §4.2 列出的全部调用点。

### 2.2 平仓的发单前工作全部集中在 `_dispatch_one_for_task`

`service.py:3239` 的 `if live and task.get("mode") != D.MODE_SMOOTH:` 分支里，平仓比开单多做三件事（下称"备料"）：

| 门 | 位置 | 作用 | 网络/耗时 |
|---|---|---|---|
| fresh preflight | `service.py:3240` | filters / 价格 / position mode / 路由，**算出 q_common** | 联网读 |
| `_close_um_position_error` | `service.py:3268` / 定义 `2321` | 合约可平量 ≥ `q_common × 剩余轮次` | 缓存优先，缺则实时查 |
| `_ensure_close_spot_balance` | `service.py:3282` / 定义 `2247` | 仅 forward：普通现货账户余额不足则**真划转** + `time.sleep(0.1)` | 联网写 + 100ms |

平滑开单的 D15 硬约束是"放行到两腿提交之间不得有任何联网读取、交易所设置、sleep 或阻塞调用"。这三件事若留在原位，平滑平仓等于把 D15 作废；若照抄平滑开单直接跳过，forward 平仓的币根本没划到普通现货账户，现货腿必挂，稳定留裸多。**因此只能整体前移**（见 §4）。

`q_common = floor_to_grid(single_amount, lcm(spot_step, perp_step))`（`domain.py:1231`）——它不是用户输入值本身，而是输入币量向两腿共同网格向下取整的结果，立即平仓现在发出的就是这个值。平滑门的覆盖率分母必须用它，才能保证判定分母与实际发送量是同一个数。

**发送量回退是硬风险**：`service.py:3349` 为 `send_qty = q_common if q_common is not None else Decimal(task["single_amount"])`。若在 `q_common` 尚未写入时就建立 gate，`timeout` / `manual` 放行**仍会走下单链**（`evaluate_smooth_gate` 在数量无效时只是不按行情放行），两腿就会用未过共同网格的原始输入量发单。这与平滑开单已具名接受的 F-A 同形，本设计用 C15 在平仓侧封死。

### 2.3 平仓已是两阶段建卡，天然满足"人工启动"

`create_task` 的 close 分支（`service.py:880`–`901`）只做本地校验（活跃周期、身份继承、1000x 拦截），直接落 `paused + awaiting_manual_start`，不读 filters/余额/持仓、不划转、不建 attempt、不启 worker。这正是平滑开单页面验收后才补上的 D17 行为，平仓无需再改。

### 2.4 暂停原因已经是现成的失败展示通道

三种备料失败在立即平仓里早已有对应的暂停原因与中文文案（`domain.py:1858`–`1863`），由 `_pause_task_local` 写入，任务卡的"暂停原因"行直接渲染：

- `preflight_incomplete`：预检数据不完整，任务已暂停（fail-closed，未发单）；请检查网络后手动恢复
- `close_um_position`：合约持仓方向或可平数量不足，任务已暂停（fail-closed，未发单）
- `close_spot_balance`：平仓现货余额检查/划转失败，任务已暂停（fail-closed，未发单）

**r2 决定（C6）因此不再需要任何新的失败展示机制**：备料失败落 `paused` + 上述既有原因即可，与立即平仓完全一致。

### 2.5 建卡阶段同步做交易所动作并弹中文原因已有先例

`create_task` 在 open + forward + `regular_spot` 时，会在 HTTP 请求内同步执行 `universal_transfer` 预划转，失败即 400 + 中文原因，前端弹窗（`service.py` 建卡分支）。**C13 的同步备料沿用这一既有交互模式**，不是新范式，也不改 worker 模型。

### 2.6 平仓闸门目前不参与平滑 gate，且发单侧完全不检查

- `_wait_for_smooth_gate` 的等待循环只检查 Start gate（`service.py:1859`），不检查平仓闸门；
- `put_close_gate`（`service.py:1540`）没有 `_notify_all_smooth()`，而 `set_start_gate` / `put_start_gate` 有（`service.py:1491` / `1533`）；
- `_dispatch_one_for_task` 的 `live` 判据是 `self._live_dispatch_capable() and self.is_start_gate_on()`（`service.py:3214`），**完全不含平仓闸门**。

后果：关闭平仓闸门时，正在 5 分钟等待中的平滑平仓 gate 既不会被唤醒，超时放行后也不会在发单侧被拦——存在一个**长达 5 分钟**的"关闸后仍发出一笔"的窗口。这与平滑开单 §16 的 L1（微秒级竞态）不是一个量级，属本轮必修（C12）。

### 2.7 前端平滑开关是 mode-based，但展示文案写死为开单

`index.html` 的动态盘口块（`6093`）、`成交1次` 的 gate_seq 绑定（`6008`）、隐藏"立即成交所有"（`6145`）都按 `task.mode === 'smooth'` 判定，平仓卡自动继承。但展示层写死了开单语义：

- 盘口块两列标题写死 `正向开单率` / `反向开单率`（`index.html:6098` / `6104`）；
- 等待原因来自 `evaluate_smooth_gate` 的 `wait_reason`，其文案写死 `"等待当前方向开单率严格大于阈值"`（`domain.py:1591`），前端原样渲染（`index.html:6111`）。

正向平仓真正参与判定的是"反向开单率"那一组价格。**只把块标题改成"平仓率"会让操作员去看错误的一列**，且等待原因仍会说"开单率"。这是展示层不诚实，必须一并修（C16）。

## 3. 已定决策及前后因果

下表区分 Human 明确决定与为落实该决定不可缺少的最小实现约束。评审不应把已拍板的取舍重新当作待定需求；若发现它与代码事实或资金安全矛盾，应给出证据和实际影响。带「r2 修订」的行是第一次计划评审后按 Human 决定改写的。

| 编号 | 最终决定 | 之前考虑/现状 | 选择原因与实际后果 | 来源 |
|---|---|---|---|---|
| C1 | 平仓率 = 把任务方向翻转后调用现有 `compute_opening_spread_pct`；`evaluate_smooth_gate` 不改 | 可另写一套平仓价差公式 | §2.1 已证明两者数学上是同一族，翻转后连覆盖率取的档位都正确。第二套公式会产生第二个分母/精度/颜色口径 | 当前代码事实 |
| C2 | 滑点阈值默认 `0.05`，允许 0 和负数，最多两位小数，与开单率同精度**严格大于**比较 | 曾考虑按平仓常态给负默认值 | 输入框规则与平滑开单逐字一致。**已知后果**：正费率币常态是合约价高于现货，正向平仓率通常为负，阈值 `0.05` 意味着多数轮次等满 5 分钟后按 timeout 放行；需要提前成交时由 Human 逐任务填负值 | Human 2026-08-14 决定 |
| C3 | 不实现老 JS 的 `当前平仓率 + 开单率 > 0` 浮动门槛 | 旧 `positiveCloseCheck` 用开仓两腿成交均价算出开单率，与当前平仓率相加判往返不亏 | 阈值只按建卡时输入的百分比比较，与开仓成交价无关。省掉从活跃周期倒算开单均价的一整块 | Human 2026-08-14 决定 |
| C4 **（r2 修订）** | **备料成功后不再重做**：判据为 `q_common` 已写入。人工暂停后再启动**跳过**备料；备料失败或中途崩溃则 `q_common` 仍为空，下次启动重做一遍 | r1 写的是"每任务只做一次"，未定义失败与崩溃后的语义 | 让"已备料"成为一个可判定、可自愈的事实而不是一次性动作。重做是安全的：划转前先查余额，币已到账则不会二次划转。**代价（Human 明确接受）**：备料成功后冻结的事实随时间变旧，暂停期间交易所侧变化不再被发单前拦截 | Human 2026-08-14 决定 |
| C5 **（r2 修订，r3 补闸门）** | 备料时机：**在 `post_start` 接口内同步执行**，全部成功后才把任务置为 `running` 并启动 worker、订阅盘口、建立 gate。**备料之前先校验 Start gate 与平仓闸门，任一关闭即拒绝：返回中文原因、任务保持 `paused`、零资金动作** | r1 把备料放在 worker 启动后（异步）；r2 把备料移入 `post_start` 后，两道闸门都不再管它 | 卡片在备料期间原地停留在"已暂停"，成功才转"执行中"。失败由 HTTP 响应直接带回中文原因。**闸门校验是恢复 r2 之前就存在的保护**：划转原本发生在 worker 的 dispatch 路径内，受 `is_start_gate_on()` 与 `_worker_round` 的平仓闸门检查双重约束；不校验会出现"关着平仓闸门点启动 → 币照划 → 任务起来一轮即退"的真实资金移动 | Human 2026-08-14 决定 |
| C6 **（r2 反转）** | 备料失败 → 任务**回退 `paused`** + §2.4 的既有中文暂停原因；不再落 `deleted` | r1 曾定为落 `deleted`（页面"已删除"分类）；第一次计划评审（codex）以"deleted 无原因持久化通道、且与人工软删除同形"判 REWORK | 复用立即平仓已在跑的暂停路径：**零新字段、零新文案、零新机制**，且与"和立即平仓流程一致"的原始要求吻合。卡片留在原处，Human 补币或处理完仓位后直接点启动继续，不必重新开卡。**第一次评审的阻塞发现 R1 因该机制不再存在而整体作废，不是被绕过** | Human 2026-08-14 决定 |
| C7 | 放行到两腿提交之间**不得有任何联网读取、交易所设置、sleep 或阻塞调用**（平滑开单 D15 同款） | — | 一档价差过滤的时效性是本功能的目的本身。备料前移正是为此 | Human 2026-08-14 决定（效率优先） |
| C8 **（r2 收窄）** | **仅 `mode=smooth` 的平仓任务** `failure_pause_threshold = 1`：出现第一次单腿成交或提交失败即暂停。**立即平仓保持默认 3，行为零回归** | r1 写的是"平仓任务 = 1"，涵盖了立即平仓，与文首及 §7 的"立即平仓零回归"自相矛盾 | 立即平仓每轮都重跑三道门，其单腿成因与平滑（冻结事实过期）不同；把一个长期实盘运行的行为顺手改掉属扩范围。要改应单独提一轮并单独验收。零新代码：建卡时对 smooth close 传 1 | Human 2026-08-14 决定 |
| C9 | 单腿的动作仍是**暂停**，不是终止 | 可改为 stopped | 暂停保留周期不关，人工处理完敞口点恢复即可接着平剩余次数。且平仓有"合约无仓核实"收尾判定，暂停不会误触发 | 本轮最小范围结论 |
| C10 **（r3 补解禁）** | 5 分钟固定窗口、`market / manual / timeout` 三种放行原因、gate 身份 `(task_id, next_attempt_seq)`、`成交1次` 携带 gate_seq、不提供「立即成交所有」——全部逐字沿用平滑开单。**但必须显式解禁 store 侧的 open-only 硬条件**：`store.open_smooth_gate`（`store.py:890`）与 `store.force_smooth_gate`（`store.py:928`）当前都写死 `task_type != TASK_TYPE_OPEN → return None`，同时为两者加上「`q_common` 有效」谓词（C15） | r2 只写"逐字沿用"，未提这两处 | 不解禁则平滑平仓**永远建不了 gate**：任务能启动、能订阅，但每轮建门失败、零成交，而验收里"零 attempt / 零 executor"的断言**全部会通过**——测试全绿、功能全废。这是设计措辞直接导致的实现陷阱 | 评审 grok 指出，Human 2026-08-14 采纳 |
| C11 | 80% 一档覆盖率的分母 = 备料冻结的 `q_common` | 曾考虑直接用输入的 `single_amount` | §2.2：`q_common` 是取整后的实际发送量，步长粗的币两者可差一整格 | 当前代码事实 |
| C12 **（r3 补两处）** | 平仓闸门接入平滑链，共五处：① `put_close_gate` 唤醒等待中的 gate；② gate 等待循环检查 `is_close_gate_on()` 并在关闸时 `clear_smooth_gate`；③ `_dispatch_one_for_task` 的发单准入同时要求平仓闸门开启；④ **`put_close_gate` 开闸后像 `put_start_gate` 那样为 running 的 smooth 任务 `ensure_worker`**；⑤ **`_worker_round` 因平仓闸门关闭退出时同样 `clear_smooth_gate`**（现状只有 Start gate 分支会清） | r2 只写了 ①②③；④⑤ 是 r3 补的 | 缺 ④ → 关闸再开闸后任务躺死不动，Human 以为系统坏了；缺 ⑤ → 关闸退出后 gate 残留，再开闸可能复用旧窗口。三处主路径 + 两处补漏合起来才让"关闸=真停住、开闸=真恢复"成立。残余的微秒级竞态与开单 L1 同构，按已接受处理 | 落实 C10 的最小实现约束（r2 补发单侧，r3 补开闸/清门，评审 grok 指出） |
| C13 **（r2 新增，r3 补置灰）** | 启动交互：点击启动 → 卡片**原地停留在"已暂停"**、按钮显示"备料中…" → 备料成功才转"执行中" → 备料失败当场弹出中文原因且卡片状态不变。**备料请求进行中，前端置灰该任务卡的全部操作按钮（含暂停、删除、成交1次），不只是启动按钮** | r1 的异步备料会让卡片先跳"执行中"再消失回"已删除" | 与 §2.5 的建卡同步划转交互一致。置灰全部按钮是为了压缩"人工操作与备料收尾竞争"的窗口（C14 的条件写是服务端的第二道）。**已知边界**：置灰只作用于当前页面，另开标签页或刷新后按钮仍可点，故服务端条件写不可省。**代价（Human 明确接受）**：启动请求会真实等待数秒，交易所慢时可能十几秒 | Human 2026-08-14 决定 |
| C14 **（r2 新增，r3 改条件写）** | `q_common` 只在**三步全部成功之后**写入；该写入与置 `running` 是**同一次条件写**，语义等价于 `WHERE id=? AND status='paused' AND q_common IS NULL`。未命中时不写、不置 running，重读任务并按当前权威状态返回：已删除/已完成 → 冲突错误且**绝不复活**；仍 paused 且已有 `q_common` → 只置 running（同样带 paused 谓词）；已 running → 幂等返回 | r1 是"预检出数量即冻结"；r2 改为末步写入但未规定谓词，`post_start` 现状是无条件 `set_task_status(RUNNING)` | 末步写入解决"已写数量未划转"的崩溃缺口。**加谓词解决的是另一件事**：C13 把"检查过未删除"到"写成 running"之间拉长到数秒，期间人工删除会被无条件覆盖，**已删除任务复活为 running 并继续发单**。谓词本身零成本——该写入在 store 里没有现成方法、本来就要新写这条 SQL，`WHERE` 多两个条件不是新增机制。`store.pause_task` 已有的 conditional 写正是同一模式（F2-P1） | Human 2026-08-14 决定（评审 glm A2 + grok 指出） |
| C15 **（r2 新增，r3 定处置）** | **没有有效 `q_common` 不得建立 gate、不得订阅、不得放行**（含 timeout 与 manual）。**拦截后的处置必须明确为 fail-closed：任务落 `paused` + 既有 `preflight_incomplete` 中文原因，worker 退出——不得只是"不建门然后返回"** | 现状：数量无效只让行情不通过，timeout/manual 仍会走下单链，且 `send_qty` 回退成未取整的 `single_amount`（§2.2）。r2 只写了不变量，没写拦下来之后干什么 | 封死平滑开单 F-A 在平仓侧的同形路径。**只写不变量不够**：`_wait_for_smooth_gate` 返回 None 且任务仍 running、Start gate 开时，`_worker_round` 会 `return False` 立刻进入下一轮，而无在途腿时该循环**不做节流**——形成无 sleep 的紧密循环，空转 CPU 并风暴式唤醒。更糟的是 r2 的验收只数"零 attempt / 零 executor"，**忙循环的错误实现照样全绿** | Human 2026-08-14 决定（评审 glm + grok 同点指出） |
| C16 **（r2 新增）** | 方向翻转必须覆盖**全部**判定与展示调用点（清单见 §4.2），并修正两处写死的开单文案：盘口块两列标题、`wait_reason` | r1 只写了"抽一个纯翻转函数供三处共用"，未列调用点；两处文案写死（§2.7） | 只翻预检不翻门 → 任务按开单率等待；只翻门不翻展示 → 后台对而卡片显示反方向，操作员照卡片判断即错。属"代码没错但呈现含义是错"的既有失败族 | Human 2026-08-14 决定（评审 grok + glm 指出） |
| C17 **（r3 新增）** | 任务卡显示**备料状态**：smooth close 显示"已备料 / 未备料"，由 `q_common` 是否有值**派生**，不新增数据库列、不新增状态机；immediate close 显示"每轮实时校验"，其行为不变 | r2 只把 `q_common` 当内部判据，卡片上看不出来 | Human 要在卡片上直接看到这张卡还需不需要备料，以解释"暂停后再启动为什么不重新备料"。派生显示零存储成本，且避免出现与 `q_common` 可能不一致的第二处真相。**明确不做**：不把 immediate close 也改成"启动时备一次料"——那会拿掉它每轮重查合约可平量的保护，与 §7 的立即平仓零回归冲突，属独立范围 | Human 2026-08-14 决定 |

## 4. 执行时序与调用点

### 4.1 时序（硬约束）

```text
（建卡，不变）close 轻量建卡：活跃周期校验 → 身份继承 → 1000x 拒绝
              → paused + awaiting_manual_start，零联网、零 worker
        ↓
（Human 点「启动」）POST /start —— C5/C13：备料在本请求内同步执行，前端置灰该卡全部按钮
        ├─ 【C5】Start gate 或平仓闸门任一关闭 → 拒绝：中文原因 + 保持 paused + 零资金动作
        ├─ 已有有效 q_common？→ 是：跳过备料（人工暂停后恢复的路径，C4）→ 置 running
        └─ 否：fresh preflight → 合约可平量门 → forward 现货余额检查/划转/sleep(100ms)
                ├─ 任一失败 → 任务保持/回退 paused + §2.4 既有中文原因
                │             HTTP 返回该原因；零订阅、零 gate、零 attempt、零订单
                └─ 全部成功 → 【C14】一次条件写：仅当仍 paused 且 q_common IS NULL 时
                              写入 q_common / position_side_mode / preflight_snapshot(route)
                              并置 running → 启动 worker
                              未命中 → 不写、不复活，按当前权威状态返回（已删除即冲突）
        ↓
        worker：订阅现货/合约两个 watcher → 建立或恢复 gate
                （【C10】store 侧 gate 已对 close 解禁；【C15】无有效 q_common 不得建立，
                  且拦截即 fail-closed 落 paused 并退出，不得空转）
        ↓
（每一轮，第 1…N 轮完全相同）
        WS 更新时评估「本任务平仓率严格 > threshold」且「两腿一档各 >= 80% q_common」
        → market / manual / timeout 任一放行
        → 【C7】零联网，直接用冻结参数组装请求
        → prepare_attempt 原子复核（任务状态、target、无在途 pair、gate seq、pass reason）
        → 既有 _dispatch_live 两腿并发提交 → 查单 → 结算
        → 单腿或提交失败一次（C8）→ 暂停（C9）
        ↓
（次数用完，不变）_verify_close_flat 实时查合约持仓 → flat 关周期 + 结算日志 /
                open 部分平完成 / failed fail-closed 暂停；forward 另做 USDT 回流
```

补充硬约束：

- 备料到置 `running` 之间、gate 放行到 `prepare_attempt`/`_dispatch_live` 之间，均不得新增联网、sleep 或阻塞调用（前者本身就是联网段，指的是不得在其后追加）；
- `prepare_attempt` 的 durable-before-send 原子写、两腿并发、查单、结算、单腿处置链一律不变；不复制 executor，不新建平仓专用下单实现；
- 立即平仓（`mode=immediate`）**仍在原调用点、每一轮**执行这三道门。抽出备料函数时最容易犯的回归就是把立即平仓也改成"启动时做一次"——那是行为变更，不是本轮特性。

### 4.2 方向翻转必须覆盖的调用点（C16）

平仓传入的方向 = 任务方向取反。以下每一处都必须使用翻转后的方向，缺一处即为缺陷：

1. gate 等待循环的评估（`service.py::_wait_for_smooth_gate` → `_eval_smooth_from_sides`）；
2. 任务卡盘口读模型（`service.py::_smooth_market_doc`，含正/反两向的计算与"当前方向"的选取）；
3. 两腿一档覆盖率（同一次评估的产物，随 1、2 自动一致，但测试须单独锁住）；
4. 放行审计快照（`_build_smooth_pass_audit` 使用的那次评估结果）；
5. 发单前预检方向（`_resolve_fresh_preflight` 已有，行为不变）；
6. 前端盘口块两列标题与"当前方向"的对应关系（`index.html:6098` / `6104`）；
7. 等待原因文案（`domain.py:1591` 的 `wait_reason`）。

其中 6、7 是展示层：平仓卡不得出现"开单率"字样，且必须让操作员一眼看出哪一列是本任务实际参与判定的那一组价格与数量。实现方式（service 层改写字符串或 domain 层参数化）不限定，但不得为此改变 `evaluate_smooth_gate` 的判定逻辑。

## 5. 接受的代价与新增风险（Human 已知）

1. **冻结事实的陈旧**（C4/C5/C7 的合并结果）：备料成功到实际发单之间，短则秒级，长则跨越多次暂停恢复。期间余额/保证金、交易规则、position mode、下单限频、现货路由、合约可平量若发生变化，不再有发单前拦截，改为以交易所拒单形式出现。反向平仓的组合保证金弱检查同样继承并略加重。
2. **单腿的两个触发源**：
   - 暂停期间 Human 在交易所手工平仓 → 恢复后合约腿 `reduceOnly` 被拒（安全）、现货腿照卖 → 单腿；
   - **部分成交积累**：两腿单轮成交量本就可以不一致，若剩余可平量已小于下一笔 `q_common`，立即平仓每轮重比会暂停不发单，而平滑只在备料时比过一次，会照发 → 同样形成单腿。
   两者形状相同，均由 C8 的阈值 1 停在第一次。**它不撤销已经发生的那一次单腿**；且 Human 未核对敞口就再次点启动时，仍可能再产生一次。**操作要求：恢复前先到交易所核对两腿。**
3. **划转后暂停/删除，币留在普通现货账户**：备料会把币从统一账户划到普通现货账户；任务此后被暂停或删除时不会自动划回，需人工处理或由下次平仓使用。USDT 回流仍只在平仓完成时发生。备料内部的顺序是"划转在末步"，因此**备料失败本身不会留下已划转的币**（划转失败除外）。
4. **默认阈值 0.05% 下多数轮次走 timeout**（C2 已说明），任务卡会大量出现 `timeout` 放行原因，这是预期结果而非故障。
5. **启动请求会真实等待数秒**（C13），交易所慢时可能更久。

6. **并发双启动可能各划一次币（Human 具名接受，不加互斥）**：`post_start` 没有同任务互斥，服务是 `ThreadingHTTPServer`（`server.py:1515`）。两个同任务的启动请求可以各自读到同一笔现货缺口、各自调用一次 `universal_transfer`，把同一差额划两遍。
   - **不修的依据（Human 2026-08-14 判定）**：本系统只有一个操作者，"数秒内点两次启动"不会发生；C13 的前端置灰进一步压缩窗口。
   - **已被 C14 覆盖的部分**：条件写保证两个请求**最多一个**能写入 `q_common` 并置 running，因此不会出现状态覆盖、已删除任务复活或双 worker。
   - **残余后果的边界**：多划的币只是从统一账户转到普通现货账户（自有账户之间），不产生错单、不产生裸敞口、不影响发单数量（发单量由 `q_common` 决定）；下次备料查到余额已足即不再划。代价是那部分币暂时不再计入统一账户保证金，需人工划回。
   - 第二次正式计划评审（R2）将此列为阻塞项；**Human 已按上述理由具名接受，第三次评审不应据此再次阻塞**，除非能给出"单一操作者前提不成立"或"后果超出上述边界"的当前证据。
7. 平滑开单 V1 已具名接受、平仓侧同样继承的三项限制：L1（Start gate 关闸与放行之间的微秒竞态）、L2（新 gate 可能使用上一轮结算前的 `now_us` 导致窗口略短）、L3（前端整表刷新会重置未提交的阈值输入——持仓表加阈值输入后同样作用于平仓列）。本轮**不修**，不得顺手扩大受审范围。**注意平仓闸门不在此列**：§2.6 的窗口长达 5 分钟，由 C12 必修。

## 6. 契约

### 6.1 创建任务

- `mode=smooth` 解除 open-only 限制（`service.py:801`），close 分支同样要求公共盘口 provider 可用，否则 400 `smooth_market_unavailable`；
- `slippage_threshold_pct` 校验复用 `D.validate_slippage_threshold_pct`，默认前端提供 `"0.05"`，服务端独立校验；close 轻量建卡分支必须把规范值落库（当前该分支未传此字段）；
- **仅 smooth close** 建卡时把 `failure_pause_threshold` 落 1（C8）；immediate close 保持默认 3；
- 创建后状态仍为 `paused + awaiting_manual_start`，零联网、零 worker（§2.3，不变）。

### 6.2 启动接口

- `post_start` 对 `smooth + close` 且 `q_common` 为空的任务，顺序为：**闸门校验 → 同步备料 → 一次条件写**；
- **闸门校验（C5）**：Start gate 或平仓闸门任一关闭 → 返回中文原因（沿用既有错误响应形状），任务保持 `paused`，**不做任何预检、查仓或划转**；
- 备料任一步失败：任务保持 `paused` 并写入 §2.4 的对应中文原因，HTTP 返回该原因，**不置 running、不启动 worker**；
- **成功收尾（C14）**：一次条件写，语义等价 `WHERE id=? AND status='paused' AND q_common IS NULL`，命中才写入 `q_common` / `position_side_mode` / `preflight_snapshot` 并置 `running`，随后 `ensure_worker`；未命中则重读任务按当前权威状态返回，已删除/已完成一律冲突错误且不复活；
- `q_common` 非空时跳过备料，仅做置 `running`（同样带 `paused` 谓词），行为与今天的 `post_start` 一致（C4）；
- 其他任务类型（immediate close、open 的两种模式）的 `post_start` 行为零 diff。

### 6.3 任务读模型与持久化

- 复用平滑开单已有字段：`slippage_threshold_pct`、`smooth_gate_seq`、`smooth_gate_started_at_us`、`smooth_gate_force_requested`、attempt 的 `smooth_pass_reason`、日志 `kind=smooth_dispatch_audit`；
- 备料结果写入 task 行**现有**的 `q_common` 与 `preflight_snapshot` 两列（平仓卡当前为 NULL / `available:false`）；**不新增列、不新增状态**；
- 任务文档增加一个**派生**字段表达备料状态（C17），取值由 `q_common` 是否有值决定，不落库；
- `GET /api/hedge-open-logs?task_id=...` 的 `smooth_market` 与 `smooth_dispatch_audits` 字段语义不变。

### 6.4 UI

- 私有持仓面板平仓列镜像市场页开单列：`[平滑平仓] [ 0.05 ] % [立即平仓]`；确认弹框回显阈值并说明比较的是"当前方向平仓率"；
- 启动按钮在请求进行中显示"备料中…"，且**该卡的全部操作按钮（暂停、删除、成交1次）一并置灰**直至请求返回；失败时原地展示后端返回的中文原因（C13）；
- 任务卡显示备料状态（C17）：smooth close 为"已备料 / 未备料"，immediate close 为"每轮实时校验"；
- 任务卡动态盘口块对 close 卡按 §4.2 第 6、7 项改为平仓语义，两列与"当前方向"的对应必须明确；仅 `status=running` 渲染；
- 前端不自行重算 gate，执行判断以 backend 为唯一权威。

## 7. 非目标

- 不订阅或维护完整 order book，不做 VWAP 估算，不改 Market 为限价单；
- 不动态调整平仓数量、不拆分单个 pair；
- 不实现平仓的「立即成交所有」；
- **不改变立即平仓、立即开单、平滑开单、借币、还款、划转的任何行为**（含立即平仓的每轮三道门与默认阈值 3）；
- 不实现老 JS 的开单率补偿门槛（C3）；
- 不解除 1000x 乘数合约的平仓封禁；
- 不新增任务状态、不新增数据库列、不新增第二套下单或备料路径；
- 不改动 §5 第 6 条列出的 L1–L3。

## 8. 验收矩阵

1. **方向翻转（判定侧）**：forward close 只用 `spot.bid` + `perp.ask` 与 `spot.bid_qty` / `perp.ask_qty`；reverse close 只用 `perp.bid` + `spot.ask` 与 `perp.bid_qty` / `spot.ask_qty`；任一操作数非法则该任务盘口 unavailable，不得按市场条件放行。
2. **方向翻转（覆盖面）**：§4.2 的 1–5 项各有独立断言；任意一处漏翻必须让测试变红（含"只翻预检不翻 gate"与"只翻 gate 不翻读模型"两种错误实现）。
3. **展示诚实**：平仓卡的两列标题与等待原因中**不出现"开单率"字样**；当前方向对应的列与后端判定所用的那一组价格/数量一致；开单卡的文案零 diff。
4. **阈值**：默认 `0.05`；正/零/负合法；超两位小数、科学记数、`%`、空值前后端均拒绝；超长合法整数正常规范化并建卡成功（不得 500）；建卡后固化。
5. **严格比较与同屏一致**：阈值 `0.05` 时任务卡显示 `+0.05%` 不成交、`+0.06%` 成交；前端不二次乘 100。
6. **80% 覆盖**：分母是备料写入的 `q_common`（非 `single_amount`）；两腿均 80% 通过、任一腿 79.99% 不通过；实际发送量仍为 100%。
7. **同步备料与状态翻转（C5/C13/C14）**：`post_start` 返回前完成三道门；成功时 `q_common` 与 `running` 在同一流程结尾写入，且 `q_common` 的写入发生在划转成功之后；任一步失败时任务仍为 `paused`、带对应中文原因、HTTP 携带该原因，且 `ensure_worker` 调用计数为 0、订阅数为 0、attempt 数为 0。
7a. **闸门前置（C5）**：Start gate 或平仓闸门任一关闭时点击启动 → 返回中文原因、任务仍 `paused`，且 `get_snapshot` / 持仓查询 / `universal_transfer` 调用计数**全为 0**（关闸不得发生任何资金动作）。
7b. **条件写不复活（C14）**：在"备料已完成、条件写尚未执行"处注入一次 `post_delete`（或 `post_pause`），随后执行条件写 → 任务终态仍为 `deleted`（或 `paused`），`q_common` 与 `running` 均未被写入，`ensure_worker` 调用计数为 0。已删除任务任何情况下不得回到 `running`。
8. **崩溃自愈（C14）**：在"划转已发出、`q_common` 尚未写入"处注入中断，重启后任务不是 running、`q_common` 仍为空；再次启动会重跑备料，且余额已足时**不发生第二次划转**。
9. **跳过备料（C4）**：`q_common` 非空的任务点击启动时，预检 / 持仓查询 / 划转的调用计数均为 0，任务直接进入 running。
10. **无数量不放行（C15）**：构造 `q_common` 为空且 status 为 running 的任务，gate 不得建立；即使注入 timeout 到期或 `成交1次`，`prepare_attempt` 与 executor 的调用计数仍为 0，绝不出现以 `single_amount` 发送的两腿请求。**且必须同时断言处置正确**：任务落 `paused` + `preflight_incomplete` 中文原因、worker 退出；在固定时间窗内 `_worker_round` 的进入次数有上限（不得忙循环）——只数"零 attempt / 零 executor"的实现若在空转，本项必须变红。
10a. **gate 对 close 解禁（C10）**：`open_smooth_gate` / `force_smooth_gate` 对 `task_type=close` 且 `mode=smooth` 的 running 任务能成功建立/强制 gate；对 `q_common` 为空的任务仍拒绝。**一个"能启动、能订阅、但每轮建门失败、零成交"的实现必须让本项变红**（这是 r2 措辞会诱发的实现陷阱）。
11. **单腿刹车（C8）**：smooth close 建卡后 `failure_pause_threshold == 1`，一次单腿成交或一次确认提交失败即暂停并记录敞口；**immediate close 与 open 任务的阈值仍为 3（零回归）**。
12. **5 分钟**：fake clock 在 4:59 不超时、5:00 超时；断流也在 5:00 走既有下单链；仍受任务状态、Start gate、平仓闸门与 `prepare_attempt` 原子复核约束。
13. **平仓闸门（C12，五项）**：① 等待中关闭平仓闸门 → gate 被立即唤醒、worker 退出；② **退出时 gate 被清空**（不残留旧窗口）；③ 关闸后触发 timeout 放行时 `_dispatch_one_for_task` 不得发单；④ **重新开闸后 running 的 smooth 任务 worker 被重新拉起**（对齐 `put_start_gate`），不需要人工再点一次启动；⑤ 重新开闸后为仍未调度的同一 seq 建新的完整 5 分钟窗口。
14. **放行后零联网（C7）**：三种 pass reason 下，放行之后 `get_snapshot`、持仓查询、`universal_transfer`、`set_leverage`、`sleep` 的调用计数均不再增加。
15. **持仓查询计数（分段）**：**备料段**的合约可平量查询最多一次；次数用完后的 `_verify_close_flat` 是**独立的一次实时查询，必须保留**——该断言以调用点区分而非全生命周期总数，错误实现若为绿测删掉收尾核实，测试必须变红。
16. **人工/自然竞态与 N/N 竞态**：同 gate 同时 market pass + manual 只 prepare 一个 attempt、只调 executor 一次；最后一轮自然通过同时点击不产生第 N+1 单；无活动 gate 的 fill-once 返回 409。
17. **重启/崩溃缝**：事务前崩溃保留同一 gate，事务后崩溃只恢复 PREPARED attempt；已有非终态腿只 query 不 resend。
18. **收尾不变**：次数用完仍走 `_verify_close_flat` 三分支（flat 关周期 + 结算日志 / open 部分平完成 / failed fail-closed 暂停）；forward 的 USDT 回流不变。
19. **模式隔离（零回归）**：立即平仓的三道门仍在 `_dispatch_one_for_task` 原调用点、每轮执行；立即开单、平滑开单、市场页 REST 开单率、其他任务的 `post_start` 均无 diff。
20. **订阅共享与释放**：同 symbol 的平仓与开单任务共用一个 spot/perp watcher；最后引用释放才取消；无悬挂 async task。
21. **延迟审计**：平仓放行同样产出 `smooth_dispatch_audit`，快照来自产生放行结论的同一次读取；写入发生在两腿 executor 返回后，失败不改变订单处置。审计中记录的方向必须是**实际参与评估的方向**（翻转后），或显式注明翻转规则，不得只记任务方向让读者自行换算。
22. **备料状态展示（C17）**：smooth close 卡在备料前显示"未备料"、成功后显示"已备料"，取值与 `q_common` 是否有值一致；immediate close 卡显示"每轮实时校验"且其调度行为零 diff。前端不得因该字段产生第二处真相（不落库、不缓存跨刷新）。

## 9. 交付拆分与评审拓扑

本功能涉及订单触发时机、平仓资金准备与实盘资金路径，整体为 **HIGH_RISK**（`AGENTS.md` §8）。r2 须再经一次跨 provider 独立只读计划评审；交付后必须 Review-1 + Review-2。任何 `ACCEPT` 都不授权启动服务或实盘下单。

- **P1 后端**：备料抽函数 + `post_start` 同步执行 + 立即平仓原调用点不动；方向翻转覆盖 §4.2；gate 与平仓闸门三处接线；建卡放行 smooth close、阈值 1、threshold 落库。全部用 fake clock / fake market provider / record executor 验证，不发真实订单。
- **P2 前端**：持仓面板平仓列的平滑按钮与阈值输入、启动按钮"备料中…"与失败原因展示、任务卡平仓语义文案与列对应。
- **P3 契约与回归**：同步 API schema 与产品/架构/开发文档，跑后端与前端 self-check 及 §8 验收矩阵。

P1 与 P2 可分派不同 implementer，但 P2 必须在 P1 冻结 API 契约之后开始；两者不得同时修改同一文件。

## 10. 参考

- 平滑开单 V1 设计与已接受限制：`docs/planning/smooth-open-orders-v1.md`（D1–D19、§16 L1–L3、F-A）
- 开单率唯一权威：`backend/domain/snapshot.py::compute_opening_spread_pct`
- 平滑门：`backend/hedge_open_tasks/domain.py::evaluate_smooth_gate`、`service.py::_wait_for_smooth_gate`
- 平仓三道门：`service.py::_resolve_fresh_preflight` / `_close_um_position_error` / `_ensure_close_spot_balance`
- 平仓收尾：`service.py::_verify_close_flat` / `_finalize_close_task` / `_transfer_back_usdt`
- attempt 硬门：`backend/hedge_open_tasks/store.py::prepare_attempt`
- 连续失败刹车：`domain.py::resolve_status_after_attempt`、`store.py` 的 `failure_pause_threshold`

## 11. r1 → r2 修订记录

**评审输入**

- 正式跨 provider 计划评审（`gpt-5.6-sol` / openai，handoff 见本 stage `evidence/01-plan-review.handoff.md`）：结论 **REWORK**，唯一阻塞发现 R1 = "C6 的 deleted 原因无持久化来源、且与人工软删除同形"。
- 非正式初评三份（`grok` / xai、`claude_glm` / zhipu_glm、`gemini-3.1-pro` / google），均不构成接受性结论。

**逐条处置**

| 来源 | 发现 | 处置 |
|---|---|---|
| codex（正式，阻塞） | deleted 原因无持久化通道，且与人工软删除同形 | **C6 反转为 paused**：该机制不再存在，R1 随之作废（不是绕过） |
| grok | `q_common` 先落库后划转 → 崩溃恢复跳过划转 | 新增 **C14**：末步写入 + 幂等重做；验收 8 |
| grok | 无有效 `q_common` 时 timeout/manual 仍会以 `single_amount` 发单 | 新增 **C15**；验收 10 |
| grok | 方向翻转调用点不全；`create_task` 的翻转对 close 是死代码 | 新增 **C16** + §4.2 清单；§2.1 更正；验收 2 |
| grok | C8 覆盖立即平仓，与"零回归"自相矛盾 | **C8 收窄**到仅 smooth close；验收 11 |
| grok | 验收"持仓查询最多一次"会逼实现删掉收尾核实 | 验收 15 改为按调用点分段 |
| grok | 单腿触发源不止人工平仓（部分成交后剩余不足） | §5.2 补写 |
| grok | 启动是异步的，失败后卡片先跳"执行中"再消失 | 由 **C5 + C13** 的同步备料整体解决 |
| glm | `wait_reason` 写死"开单率"，平仓卡会照抄 | 并入 **C16** / §4.2 第 7 项；验收 3 |
| glm | 发单侧不检查平仓闸门 | **C12 补齐**发单准入；验收 13 |
| agy | deleted 卡缺原因行 | 与 C6 反转同区域；其建议的 `pause_reason` 直读补丁会把人工删除标成系统删除，未采纳 |

**Human 在本轮做出的产品决定**：C4（备料成功才算备好、失败与崩溃重做）、C5/C13（启动接口内同步备料，卡片原地显示"备料中…"）、C6（失败落暂停而非删除）、C8（阈值 1 仅给平滑平仓）。

## 12. r2 → r3 修订记录

**评审输入**

- 第二次跨 provider 正式计划评审（`gpt-5.6-sol` / openai，handoff 见 `evidence/02-plan-review-2.handoff.md`）：结论 **REWORK**，阻塞发现 R2 = 并发 `post_start` 可重复划转。同时确认 R1 已实质消解、C15/C16/陈旧风险/阈值 1 全部通过。
- 非正式初评三份（`grok` / xai、`claude_glm` / zhipu_glm、`gemini-3.1-pro` / google）。

**逐条处置**

| 来源 | 发现 | 处置 |
|---|---|---|
| codex（正式，阻塞 R2） | 并发 `post_start` 重复划转 | **Human 具名接受，不加互斥**，理由与后果边界写入 §5.6；其中"状态覆盖 / 复活 / 双 worker"部分由 C14 的条件写封住 |
| glm（A2） | 备料期间人工 pause/delete 被无条件置 running 覆盖，**已删除任务复活并继续发单** | **C14 改为条件写**（`WHERE ... status='paused' AND q_common IS NULL`）；验收 7b |
| grok（同族第三条） | `q_common` 写入若无谓词会打在已删除行上 | **Human 判定不成立**：已删除任务不可再启动（`post_start` 首先拒绝 deleted），该行数据不会被任何路径读取；grok 的论据是"未来若有恢复路径漏检 deleted"，属无当前证据的假设场景，按 `AGENTS.md` §1 不予采纳。条件写本身仍会顺带覆盖此情形 |
| grok（独有，功能阻断） | `open_smooth_gate` / `force_smooth_gate` 写死 `task_type == open`，平滑平仓永远建不了 gate，且验收全绿 | **C10 补解禁 + 数量谓词**；验收 10a 专门要求"能启动但零成交"的实现变红 |
| glm + grok（同点） | C15 只写不变量、未定处置 → worker 忙循环，且验收放行该错误实现 | **C15 补 fail-closed 落 paused + 退出**；验收 10 补"不得忙循环" |
| grok | `put_close_gate` 开闸不拉 worker；`_worker_round` 因关闸退出不清 gate；备料不再受两道闸门约束 | **C5 补闸门前置校验**（验收 7a）、**C12 补 ④⑤**（验收 13） |
| glm + grok（观测） | 审计记任务方向而非评估方向；前端 `forward/reverse_spread_pct` 字段名对 close 有误导 | 验收 21 补审计方向要求；字段名不改（§6.3 语义不变），由验收 2/3 保证接线正确 |
| Human 新要求 | 卡片要能看出是否需要备料 | **C17 新增**：派生显示，不新增列；immediate close 显式标注"每轮实时校验"且行为不变 |

**Human 在本轮做出的产品决定**：接受 R2 残余风险（§5.6）、否决 grok 的同族第三条、C5 的闸门前置、C13 的全按钮置灰、C17 的备料状态展示、以及"不把 immediate close 改成备料一次"。

**Human 记录在案的偏好（不改变本轮范围）**：Human 不偏好现有闸门机制，实际运行中默认两道闸门全开。因此 §5.6 与闸门相关的路径在日常操作中命中率低；这不构成删除闸门的授权，闸门精简若要做属独立范围。
