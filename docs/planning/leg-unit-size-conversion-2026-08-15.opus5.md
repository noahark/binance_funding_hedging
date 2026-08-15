# 开发方案 r2：两腿数量换算（每腿乘数口径）

- 作者：Opus 5
- 日期：2026-08-15
- 状态：**设计稿 r2，未实现。r1 经 claude-glm 与 grok 双评审判 REWORK，本稿为返工版。**
- 目标读者：Human（不读代码）+ 评审模型
- 基线：`main` @ `f72a4d2`（行号已于该基线全量复核，32/32 命中）
- 前置：`docs/planning/symbol-identity-unification-2026-08-07.opus5.md`（现货腿身份统一，**已交付**）
- r1 评审：`*.review-claude-glm-result.md`、`*.review-grok-result.md`（同目录）

> **本文不含任何代码改动。**

## r2 变更摘要

| 项 | r1 | r2 |
|---|---|---|
| 核心口径 | 「标准量纲 + 唯一出口换算」 | **每条腿带 `(x, y)` 一对乘数，全路径统一施加**（Human 提出） |
| 换算点 | 声称「唯一出口」1 处 | **3 处装配点抽成一个共用函数**（r1 事实错误，grok F5） |
| 拒发时机 | 执行器末端 | **前移到建 attempt 之前**（grok F5） |
| 平仓路径 | 未覆盖 | 后端持仓门 + 前端预检 + 输入框（双方 F1/F2） |
| 平滑门 | 未覆盖 | 覆盖率 + 价差两处（双方） |
| 展示 | 未覆盖 | 市场表开单率 + 历史滑点（grok F4/F6、glm O2） |
| `est_price` 消费者 | 称「两个」 | **更正为三个**，新增第四条「不用改」（glm F4） |
| 护栏 | 一道，±5% | **两道**：建表前缀校验（第一道）+ 价格比值兜底（容差放宽） |
| 清单规模 | 7 处 | 约 15 项 |

---

## 0. 一句话结论

在已有的 `合约名 → 现货名` 对照表上**加一列倍数**；由它派生每条腿的一对乘数
（价格乘 `x`、数量乘 `y`），**在开仓、平仓、平滑、展示的每一条路径上统一施加**。
表外标的两个乘数都是 1，乘完恒等——**现有全部标的行为一行不变，且无需任何分支判断**。

---

## 1. 问题：一箱一千瓶

六个币（`BONK / FLOKI / LUNC / PEPE / SHIB / XEC`）的合约在币安叫 `1000BONKUSDT`
这种名字，**1 张合约 = 1000 个币**。系统给两条腿发的是同一个数量
（`live_hedge_executor.py:828`），现货买 N 个、合约空 N 张（= 1000N 个），**净裸空 999N**。

2026-08-07 的止血是把它们 fail-closed 挡住，换算一行没写。挡住是安全的，代价是
这六个币的对冲能力没有了。

### 1.1 没有先例可抄

原始 JS 策略（`币安套费率策略，逐仓杠杆.js:2842`）以
`if (BINANCE_MARGIN_SYMBOL[symbolInfo.symbol] == null) { continue; }`
把这些币静默跳过——它的币种池建自逐仓杠杆对列表（键为 `BONKUSDT`），拿合约名
`1000BONKUSDT` 查不到即跳过。**这些币从未进过它的视野。**

现系统会撞上此问题，恰因它比原始 JS 多做一步：建了显式映射表让 `1000BONKUSDT`
找到 `BONKUSDT` 这条现货腿。名字通了，量纲的坑才浮出来。

### 1.2 交易所元数据不足以识别（实测）

CCXT 对 `1000PEPE` 报 `contractSize == 1.0`，**与普通合约不可区分**
（`docs/planning/ccxt-bookticker-recon-2026-08-13.md:124`）；
`best_bid_ask_provider.py:319` 也只在 `size != 1` 时丢弃快照，**不做换算**，
即盘口数量按「张」原样透传。

→ **倍数只能由本地表显式携带，不可从交易所元数据推导。**

---

## 2. 设计

### 2.1 表加一列倍数（身份与固化机制已存在，直接复用）

`SPOT_SYMBOL_MAP`（`backend/domain/normalize.py:111`）由二元组扩为三元组，
第三位是**合约腿的倍数**；表外默认 1。`resolve_spot_identity`
（`normalize.py:188`）多返回一个倍数。

**symbol 映射与建任务固化本轮无需新建**——2026-08-07 身份统一已交付：表已含
bStock（`TSLAUSDT → TSLABUSDT`）与乘数币（`1000BONKUSDT → BONKUSDT`），且
`spot_symbol` / `spot_base_asset` / `symbol_match_type` 三列在建任务时固化、
平仓读开仓那份。**本轮只是让倍数搭同一班车。**

固化是硬要求：币安改过合约规格（`1000000MOG` 前缀真实存在过），不固化则
开仓用旧倍数、平仓用新倍数 → 直接错仓。

`scripts/check-spot-symbol-map.py` 的 `--emit` / `--verify` 一并覆盖倍数列（见 §5.1）。

### 2.2 每条腿带一对乘数，由同一个倍数派生

| 腿 | `x`（价格乘数） | `y`（数量乘数） |
|---|---|---|
| 现货腿 | `1` | `1` |
| 合约腿 | `1 ÷ 倍数` | `倍数` |

统一规则，**全系统只有这两行，没有任何 `if`**：

```
任一腿的价格 × 该腿 x  =  标准价（每个币多少 USDT）
任一腿的数量 × 该腿 y  =  标准量（多少个币）
```

**方向相反是本方案最易翻车处**：一箱装一千瓶 → **箱数少、箱价高** → 数量乘、价格除。
搞反不会报错，只会算出一个看似正常、实际错一百万倍的结果。

**`x` 与 `y` 必须由同一个倍数派生，不得各存一列。** 两列可互相矛盾且系统无法自检；
一个数派生两个则不可能不一致。

**跨腿角色中立**：该形状不假设「必有一腿是现货」。将来做合约对合约，A 腿 `(1,1)`、
B 腿 `(1/1000, 1000)` 即可，无需改公式。这是零成本的形状选择——本轮**不为多交易所
建任何机制**（§6）。

> r1 §3.1 曾称此形状与「表加一列倍率」是两种数据模型。**该表述错误已删除**：
> 按本方案的存法（表内只存合约腿倍数，现货腿隐含 1），二者就是同一件事，
> 差别仅在公式写法是否焊死「分母必为现货腿」。grok r1 评审指出，采纳。

### 2.3 全路径统一施加 —— r1 的根本错误

**r1 的核心错误是「唯一出口」这个心智模型。** 它假设数字只从一个口出去，因此
只需在末端换算一次。实际上合约侧的数字**从四条独立路径进来**：

```
交易所报的持仓（张）  ┐
合约盘口挂单量（张）  ├─→  这些都要 × y 变成「个」再参与计算
合约的步长/上下限（张）┘

合约的价格（每张）    ───→  要 × x 变成「每个」再参与计算
```

因此换算必须**在每个边界发生**，不是在末端发生一次。§3 按路径而非按文件组织，
正是为了让「哪条路进来的」一眼可数。

### 2.4 取整：既有机制，只改一个乘数（回答 Human 的复杂度提问）

**取整不是本方案新增的步骤，它已经在跑：**

- `domain.py:1245`：`grid = decimal_lcm(spot_step, perp_step)`
- `domain.py:1246`：`q_common = floor_to_grid(single_amount, grid)`
- `domain.py:837`：`floor_to_grid` 向下取整，已存在

**本方案对它的全部改动是一个乘数**：`decimal_lcm(spot_step, perp_step × 倍数)`。
倍数 = 1 时恒等，现有标的零影响。**增量复杂度 ≈ 一次乘法。**

**它不能交给 Human 主观过滤，理由是资金安全而非便利：**

1. 合约腿的量由 `个数 ÷ 倍数` 得出。若该结果不落在合约步长格子上，**交易所会拒绝
   合约腿**；而现货腿是并发提交的，大概率已成交 → **现货成交、合约被拒 → 单腿裸多**。
   这正是 §3.1 要 fail-closed 堵住的同一种事故。
2. Human 无法自行算出格子：它是 `最小公倍数(现货步长, 合约步长 × 倍数)`，两个步长
   都来自交易所实时下发的规则，页面上并不展示。
3. 取整只向下、不向上（`floor`），因此它**只会少下单，不会超下单**，方向本身是安全的。

**结论：保留取整，改一个乘数。** 这一步删掉会让系统更危险，不是更简单。

---

## 3. 改造清单（按路径组织）

> 行号为基线 `f72a4d2` 复核值，动手前重跑 §8.1。

### 3.1 结构先行：三处装配点抽成一个函数 + 拒发前移

**这一项必须最先做，§3.2–3.6 全部依赖它。**

现状：计算发单数量的地方有**三处**，各写各的，且都带同一条绕过取整的退路
（`q_common` 为空则回退用户原始输入）：

| # | 位置 | 作用 | r1 是否提及 |
|---|---|---|---|
| 1 | `service.py:3570` | 组装两腿 `request_shape` 写入审计记录，**发生在 `prepare_attempt`（`service.py:3614`）之前** | ✗ |
| 2 | `live_hedge_executor.py:828` | 真实 POST 的发单量 | ✓（r1 唯一提及处） |
| 3 | `backend/tests/fakes.py:152` | dry-run 假执行器，并用它跑合约过滤器 | ✗ |

三层后果：

- 只改 #2 → 库里的审计形状仍是「两腿同一个数」，事后审计读错；
- 拒发只加在 #2 → `prepare_attempt` 已落一行 attempt，事后再拒会留脏 attempt 并白耗一次尝试；
- #3 未改 → **假执行器与真执行器各持一份换算，两边同错则单测全绿**——正是
  `PROJECT_STATE` 反复警告的形状。

**改法：**

1. 抽一个纯函数 `split_legs(标准量, 合约腿倍数) -> (现货量, 合约张数)`，**三处共用**；
2. `q_common is None` 且倍数 ≠ 1 时**拒发**，落点在 `service.py:3570`、
   **`prepare_attempt` 之前**，不得回退到 `single_amount`；倍数 = 1 保持现有退路行为不变。

### 3.2 开仓路径

| 位置 | 现状 | 改法 | 乘数 |
|---|---|---|---|
| `domain.py:1245` | `grid = lcm(现货步长, 合约步长)` | 合约步长先 `× y` | `y` |
| `domain.py:1062`（循环体 `1075`） | 同一个 `q_common` 比两腿各自 min/max | 合约 min/max 先 `× y` | `y` |
| `domain.py:1342` | `base = base_asset(coin)` → `1000BONK`，账户键是 `BONK` → 余额恒 0 → **恒判不足** | 改用 `resolve_spot_identity(coin)` 的现货 base | 命名，非乘数 |
| `domain.py:1258` `snapshot_record` | 隐含「两腿同量纲」 | 加记倍数并注明「以下数量均为现货个数」 | 审计 |

`domain.py:1342` 走到的路径是 `open + reverse`（负费率开仓，借币卖现货），
**现被 P0 拦截掩盖**，拆拦截同轮必须连它一起修，否则换算做对了余额检查仍恒拒。
（bStock 亦命中此行，但其无借币市场、不存在负费率开单，fail-closed 对它是正确行为。）

### 3.3 平仓路径（r1 完全未覆盖）

| 位置 | 现状 | 改法 |
|---|---|---|
| `service.py:2442` → `2608` | `required_qty = q_common × 剩余次数`（**个**）拿去比 UM `positionAmt`（**张**）→ 乘数币恒判「合约可平数量不足」 | 比较前把可平张数 `× y` 换成个（或计划量 `÷ y` 换成张） |
| `frontend/index.html:5790-5796` | 网页预检同样拿 `总量`（个）比 `um_position_amt`（张） | 同上；页面在后端之前先拦，必须同批改 |

**后果是「开得进、出不来」**：仓能开、永远平不掉，本方案要恢复的能力在平仓侧被断路，
且 §8.3「开一笔立刻平掉」的验收会直接失败。方向是 fail-closed（不裸奔），但能力恢复不了。

关联核对：`_verify_close_flat`（`service.py:2393`，判定在 `2406`）用 `qty == 0` 判平，
**0 无量纲问题，不用改**——在此写明以免误伤。

> 注：glm r1 评审将此函数写作 `_is_close_flat`（`2403-2406`）。**该名称在仓库中不存在**，
> 真实名称与行号如上；其实质判断（`qty == 0` 无量纲问题）经复核成立，故采纳内容、更正引用。

### 3.4 平滑门（r1 完全未覆盖）

`evaluate_smooth_gate`（`domain.py` 起于 `1566`），open 与 close 的 smooth 模式共用：

| 位置 | 现状 | 改法 | 乘数 |
|---|---|---|---|
| `domain.py:1588` | `compute_opening_spread_pct(perp.bid, spot.ask)` = 每张价 vs 每个价 → 恒得 ≈ `+99900%` → `spread_pass` **恒真**，价差保护失效 | 合约价先 `× x` | `x` |
| `domain.py:1596` | `perp_coverage = perp_qty / q_common` = 张 ÷ 个 → **低估 1000 倍**，`SMOOTH_COVERAGE_MIN = 0.80`（`domain.py:96`）恒不过 | 合约盘口量先 `× y` | `y` |

净效果：`market_pass` 恒假 → 每笔等满窗口后按超时放行。**平滑模式的全部行情保护
对乘数币等于不存在，且每笔白等五分钟。**

### 3.5 展示路径（r1 完全未覆盖）

| 位置 | 现状 | 影响 |
|---|---|---|
| `snapshot.py:698` | 市场表行级开单率同样是每张价 vs 每个价 | 这六个币显示 ≈ `+99900%`，**Human 可能照假信号点「立即开单」**——拆拦截后即成真实误操作入口 |
| `store.py:2563` `cycle_slippage_pct` | 两腿成交均价直接相减 | 历史滑点同样 ≈ `+99900%`；**恰好在 §8.3 实盘验收时反着说** |

两处均 `× x` 对齐后再算。不造成错腿，但一处诱导误操作、一处干扰验收，**同批改**。

实测锚点（grok 于 2026-08-15 取公开价）：六币标记价 ÷ 现货价落在
`997.90`–`1000.22`，相对 1000 的偏离 ≤ `0.21%`。即 `+99900%` **全部**是量纲错误，
不含任何真实价差。

### 3.6 UI 单位与文案

| 位置 | 现状 | 改法 |
|---|---|---|
| `frontend/index.html:5671` | 标签「单次开单币量」不带单位，同行 symbol 列显示 `1000BONKUSDT` | 乘数币行标签写死「单次开单币量（个 BONK）」，并回显**取整后**的换算：「1,000,000 个 BONK = 1,000 张 1000BONKUSDT」 |
| `frontend/index.html:5719` | 「单次平仓币量」同构（与 5671 同段模板生成） | 同上，同批改，增量成本 ≈ 0 |
| `service.py:3097` | 抵押额度暂停文案用 `base_asset(task["coin"])` → 显示 `1000BONK` | 改用现货 base（随 `domain.py:1342` 顺带） |

⚠️ 前两项是**用户可见的资金安全项**：用户看 `1000BONKUSDT` 输 `1000`，可能意指
1000 个（本方案口径）或 1000 张（= 100 万个）。**不产生裸空**（两腿仍一致），
但产生**一千倍于本意的仓位**，系统无从判断用户本意。不得因「只是前端」延后。

回显必须展示**取整之后**的值：倍数 1000、格子 1000 个时，输 1500 实际下 1000
（丢弃 500），输 999 取整为 0 → 拒绝。

---

## 4. 不用改（四处，请评审重点核对）

> r1 列三处并称「`est_price` 只有两个消费者」。**该事实陈述有误**（glm F4）：
> `est_price` 的金额消费者是**三个**——`domain.py:1083`、`domain.py:1344`、
> **`service.py:998`**（开仓预划转，r1 通篇未提，而它正是评审问题清单点名的划转备料路径）。
> 结论未变，但「查全了」的核对基础不完整。r2 更正为三个消费者、四条「不用改」。

**共同论据——USDT 名义价值在换算下是不变量：**

```
现货腿 = 个数        × 现货价          = 个数 × 现货价
合约腿 = (个数÷倍数) × (现货价×倍数)   = 个数 × 现货价     ← 同一个数
```

| # | 位置 | 为何不用改 |
|---|---|---|
| 4.1 | `hedge_preflight_provider.py:862` `est_price` 取**现货**价 | 三个消费者都在算 USDT 或「个数 × 现货价」。合约价只在数量以「张」计价时才需要。**已核实：当前无任何单独用 `est_price` 估 UM 保证金的路径**（grok 指出 r0 旧清单该条可删） |
| 4.2 | `domain.py:1083` `notional = q_common × est_price` 比两腿各自下限 | 两腿名义价值本应相等（见上式），一个 USDT 数比两边下限正确。基差使「现货价 × 倍数 ≈ 标记价」仅为近似，但此处本就是 `est_price` **估算**，非本方案新引入 |
| 4.3 | `domain.py:1344` forward / `1352` reverse | forward = 买现货所需 USDT；reverse = 卖现货所需**个数**（对照的 `available` 同为个数）。**前提：§3.2 的 `domain.py:1342` 必须同批修**，二者不可拆开交付 |
| 4.4 | `service.py:998` 开仓预划转 `q_common × N × est_price × 1.03` | 个数 × 现货价 = 正确 USDT 需求，与 4.2 同构 |

**其余已逐条核对无误、不列入清单**（供评审复核）：
平仓现货备料 `_ensure_close_spot_balance`（`service.py:2490-2562`，个口径、base 用固化值）、
USDT 回流（`cumulative_quote`，USDT）、持仓 drift（现货记账个数 vs 账户个数，同量纲）、
`price_pnl`（来自交易所未实现盈亏，非本地两腿均价互减）。

**持仓聚合 `domain.py:2122`** `abs(spot_qty - perp_qty)`：`perp_qty` 确为张
（来自腿行成交），**需 `× y` 后再比**，已列入 §3.2 语义组（归属见 §9 清单）。

---

## 5. 两道护栏

倍数是**声明值**，写错一个零即十倍敞口，而系统无独立真值可对照。
`PROJECT_STATE` 点明：**这是量纲错误，单测很容易两边用同一个错误假设而全绿。**

### 5.1 第一道 —— 建表时校验「声明倍数 == 名字前缀」（新，零假阳性）

`scripts/check-spot-symbol-map.py:37` **已有** `MULTIPLIER_PREFIXES =
("1000000", "100000", "10000", "1000")` 并以之识别这六个币。
`--emit` / `--verify` 应**强制**：声明倍数 == 名字前缀整数；表外标的倍数必须为 1。

- 不需要行情、不受市场状态影响、**误判率为零**
- 发生在建表/校验期，**早于任何发单**
- 增量几行

**这是第一道闸。**

### 5.2 第二道 —— 发单前价格比值兜底（容差放宽）

```
实测倍数 ≈ 合约标记价 ÷ 现货价格
若偏离超过容差 → 拒绝发单（fail-closed，只会拒发，不会错发）
```

防的是 5.1 抓不到的情形：**币安改了产品规格但名字没改**。

**容差：建议倍数带 `[0.5×, 2×]`（等价 ±100%）。** 定值理由：

- 本护栏抓的是**数量级错误**（10 倍 / 1000 倍 / 1 倍）。`±5%` 与 `±30%` 与 `±100%`
  对该类错误**检出率完全相同**，差别仅在误拦率 → 无理由取紧。
- r1 评审在此分歧：grok 主张 `±5%`（今日实测偏离 ≤ `0.21%`）；claude-glm 主张 `±30%`
  （memecoin 剧烈行情下基差可超 5%，误拦导致告警疲劳、最终被关闭才是真风险）。
  **采纳 claude-glm 的方向并进一步放宽**：既然检出率不变，就该把误拦压到最低。
- 倍数 = 1 的普通币/bStock 同样适用（比值应 ≈ 1），是对现有路径的一道新体检。

---

## 6. 明确不做（范围边界）

| 不做 | 理由 |
|---|---|
| 抽象「交易所」接口 | 只有币安一个实现，单实现接口是纯负担 |
| 多计价资产 | `USDT` 硬编码于 `domain.py:675`、`normalize.py:93`，注释明写「全项目唯一计价资产」，今日无需求 |
| `spot_/perp_` 改名 `legA/legB` | 生产代码 1039 处、15 文件，今日零收益 |
| 跨交易所 / 合约对合约机制 | 见下 |
| 用户手填倍数的开单界面 | 填错一个零 = 十倍敞口且系统无法自察。倍数须**系统查出、用户确认**，不可反向 |

**跨交易所的真正难点不是倍数**：资金需链上提充（分钟级、有手续费与风控）；敞口窗口
从毫秒变分钟——现有设计（含 `PROJECT_STATE` 的 F-A 风险）全部建立在两腿并发毫秒级
之上，这是**换风险模型**而非加功能；两边费率/保证金/强平规则不同，对冲比例不再 1:1；
每接一家都是一整套新坑（币安一家已踩：margin 错误码为正而 UM 为负、PAPI 无 test 端点、
`cumQuote` 被移除、51169 为平台级抵押额度打满）。

**本方案对跨所的全部贡献仅是 §2.2 的形状选择，除此不做任何铺垫。**

---

## 7. 拆三道 fail-closed 拦截（最后一步）

换算落地并通过 §8 验收后，以下必须**同批**移除（留着这六个币仍打不开）：

| # | 位置 | 拦的是 |
|---|---|---|
| 1 | `service.py:872-881` | close 建卡：固化值 OR 当前映射双判 |
| 2 | `service.py:949-957` | open 建卡 |
| 3 | `service.py:3472-3490` | dispatch 再守一次历史 NULL 行 |

配套删除：`domain.py:183 / 216 / 1875` 的 `PAUSE_REASON_MULTIPLIER_CLOSE_UNSUPPORTED`
常量、注册与文案；`backend/tests/test_hedge_service.py:269 / 301` 两条拦截断言；
`backend/tests/test_hedge_cycle_close.py:1199` 的 `_allow_multiplier_open` 夹具与
`1213 / 1236 / 1267` 三处调用。

⚠️ **拆早了就是把 999 倍裸空放出来。**

---

## 8. 验收

### 8.1 动手前：行号校验

```bash
cd "$(git rev-parse --show-toplevel)" && python3 - <<'EOF'
checks = [
 ("backend/domain/normalize.py",111,"SPOT_SYMBOL_MAP = {"),
 ("backend/domain/normalize.py",188,"def resolve_spot_identity"),
 ("backend/hedge_open_tasks/domain.py",837,"def floor_to_grid"),
 ("backend/hedge_open_tasks/domain.py",1245,"grid = decimal_lcm"),
 ("backend/hedge_open_tasks/domain.py",1246,"q_common = floor_to_grid"),
 ("backend/hedge_open_tasks/domain.py",1062,"def _check_common_quantity"),
 ("backend/hedge_open_tasks/domain.py",1075,"for filters in (spot_filters, perp_filters)"),
 ("backend/hedge_open_tasks/domain.py",1083,"notional = q_common * est_price"),
 ("backend/hedge_open_tasks/domain.py",1258,'"spot_min_qty"'),
 ("backend/hedge_open_tasks/domain.py",1342,"base = base_asset(coin)"),
 ("backend/hedge_open_tasks/domain.py",1344,"required = q_common * target_n * snapshot.est_price"),
 ("backend/hedge_open_tasks/domain.py",1352,"required = q_common * target_n"),
 ("backend/hedge_open_tasks/domain.py",1588,"compute_opening_spread_pct(perp.bid, spot.ask)"),
 ("backend/hedge_open_tasks/domain.py",1596,"perp_coverage = perp_qty / q_common"),
 ("backend/hedge_open_tasks/domain.py",96,"SMOOTH_COVERAGE_MIN"),
 ("backend/hedge_open_tasks/domain.py",2122,"abs(spot_qty - perp_qty)"),
 ("backend/hedge_open_tasks/service.py",998,"snapshot.est_price"),
 ("backend/hedge_open_tasks/service.py",2442,"required_qty = fresh.q_common"),
 ("backend/hedge_open_tasks/service.py",2608,"if available < required_qty"),
 ("backend/hedge_open_tasks/service.py",3570,"send_qty = q_common if q_common is not None"),
 ("backend/hedge_open_tasks/service.py",3614,"prepare_attempt"),
 ("backend/hedge_open_tasks/service.py",3097,"collateral_cap_pause_reason_zh"),
 ("backend/services/live_hedge_executor.py",828,"send_qty = ctx.q_common"),
 ("backend/services/hedge_preflight_provider.py",862,"est_price = self._read_est_price"),
 ("backend/tests/fakes.py",152,"send_qty = ctx.q_common"),
 ("backend/domain/snapshot.py",698,"compute_opening_spread_pct(fut_bid, spot_ask)"),
 ("backend/hedge_open_tasks/store.py",2563,"def cycle_slippage_pct"),
 ("backend/services/best_bid_ask_provider.py",319,"size != 1"),
 ("scripts/check-spot-symbol-map.py",37,"MULTIPLIER_PREFIXES"),
 ("frontend/index.html",5671,"单次开单币量"),
 ("frontend/index.html",5719,"单次平仓币量"),
 ("frontend/index.html",5790,"um_position_amt"),
]
bad = 0
for path, line, needle in checks:
    lines = open(path, encoding="utf-8").read().split("\n")
    if needle not in (lines[line-1] if line <= len(lines) else ""):
        bad += 1
        print(f"DRIFT {path}:{line} -> {[i+1 for i,l in enumerate(lines) if needle in l][:4]}")
print(f"{len(checks)-bad}/{len(checks)} OK")
EOF
```

### 8.2 单元测试（先红后绿）

**反自证要求（两条硬约束，因本类错误极易两边同错而全绿）：**

- **A. 断言写在发给交易所的原始参数上**，不是换算后的内部值——例如断言
  `合约腿 order_params["quantity"] == "1000"` 这个即将出网的字符串。
- **B. 测试夹具不得共用同一个 1000。** 期望值由 `张 = 个数 ÷ 倍数` 独立算出；
  另设一条与倍数无关的不变量：`现货量 × 现货夹具价 ≈ 张数 × 合约夹具价`，
  且两个夹具价必须是不同的数（如 `0.00001` 与 `0.01`），不可都写 1。

用例：

1. 倍数 1000：现货腿 100 万个、合约腿 1000 张（**同一次调用产出两个不同数字**）
2. 倍数 1：两腿数字相同（回归——证明 bStock/普通币行为未变）
3. 取整：倍数 1000、输入 1500 → `q_common` 为 1000（非 1500、非 2000）；输入 999 → 0 且被拒
4. 上下限：合约「最少 1 张」时，个数少于 1000 应被拒
5. reverse 余额：`1000BONKUSDT` 应读到 `BONK` 的余额（§3.2 回归）
6. 持仓单腿告警：现货 100 万个 + 合约 1000 张 → 判**不是**单腿敞口
7. **平仓 UM 门**：可平 1000 张、计划 100 万个、剩余 1 次 → **必须放行**；可平 999 张 → 拒绝
8. **平滑覆盖率**：合约一档 800 张、计划 100 万个 → 覆盖率 80% 通过（非 0.08%）
9. **平滑价差 / 市场表开单率**：现货 `0.000012`、合约 `0.012` → 价差 ≈ 0（非 `+99900%`）
10. **三处装配点**：一次 dispatch 的 `request_shape` 中现货 quantity ≠ 合约 quantity（倍数 1000 时）
11. **拒发时机**：倍数 ≠ 1 且 `q_common is None` → **不得** `prepare_attempt`，不只是执行器内 return
12. **建表校验**：声明倍数 ≠ 名字前缀整数时 `--verify` 必须失败
13. 前端自检：开仓列与**平仓列**标签均含单位，回显为取整后的值；倍数 = 1 的行不变
14. **真实 exchangeInfo 金样**：用抓取的六币真实步长 / minQty / minNotional 做格子与上下限用例，不得只用编造的 `step=1`

### 8.3 ⚠️ 单测仍不足以验收

1. **§5.1 建表校验**——最早、零假阳性、不依赖行情
2. **§5.2 价格比值护栏**——外部真值，自动化即可证伪
3. **最小额度实盘**：开一笔立刻平掉，到**币安页面**核对两腿**实际持仓数量**是否对平
   （不看系统自己的记账——记账与计算共用同一套假设，自证无效）
4. **实盘核对自动化**（glm 建议，采纳）：成交后程序读两腿 order response 的
   `executedQty`，断言 `现货 executedQty ≈ 合约 executedQty × 倍数` 并写任务日志，
   把「肉眼看」变成可留档、可复核的机器断言

自动化只能证「代码与表一致」，证不了「表与币安今晚仍一致」。**实盘步骤不可省**，
须 Human 在场、单独授权。

---

## 9. 交付顺序

1. 表加倍数列 + `check-spot-symbol-map.py` 强制「倍数 == 前缀」（§5.1）
2. 任务表加倍数列 + 建任务时固化（旧行默认 1）
3. **§3.1 结构先行**：抽 `split_legs` 共用函数、拒发前移至 `prepare_attempt` 之前
4. §3.2–3.6 **一批改完，不拆分交付**
5. §5.2 价格比值护栏
6. §8.2 单测转绿（含 A/B 两条反自证约束）
7. **停 · Human 复核并授权实盘**
8. §8.3 最小额度实盘 + 自动化核对
9. §7 拆三道拦截，六币放出
10. 更新 `docs/api/public-market-contract.md` 量纲约定；`PROJECT_STATE` 收口

**§3.1 必须在 §3.2–3.6 之前**：后者全部依赖那个共用函数。
**第 4 步不接受分批**——半套换算会造出「看起来对、实际错」的敞口，比现在的显式拒绝更危险。

---

## 10. 对 r1 双评审的逐条应答

| r1 发现 | 提出方 | r2 处置 |
|---|---|---|
| close UM 持仓门 张比个 | 双方 | **采纳** → §3.3 |
| 前端平仓预检同病 | grok | **采纳** → §3.3 |
| 平仓输入框单位歧义 | 双方 | **采纳** → §3.6 |
| 平滑覆盖率 张÷个 | 双方 | **采纳** → §3.4 |
| 平滑价差 + 市场表开单率 | 双方 | **采纳** → §3.4 / §3.5 |
| `est_price` 三个消费者（r1 称两个） | glm | **采纳更正** → §4 前言 + §4.4 |
| 「唯一出口」不成立；三处装配点；拒发须前移 | **仅 grok** | **采纳** → §3.1（并删除 r1 全部「唯一出口」表述） |
| 历史滑点两腿均价直接减 | **仅 grok** | **采纳** → §3.5 |
| 抵押额度文案显示 `1000BONK` | glm | **采纳** → §3.6 |
| `_is_close_flat` 用 `qty == 0`，不用改 | glm | **采纳并写明**，防误伤 → §3.3 |
| 容差 ±5% / ±30% 分歧 | 分歧 | **采纳 claude-glm 方向并放宽至 `[0.5×,2×]`**；理由见 §5.2 |
| 建表脚本前缀校验应作第一道闸 | **仅 grok** | **采纳** → §5.1 |
| 「单位面值 vs 倍率是两种数据模型」表述夸大 | grok | **采纳，删除该表述** → §2.2 注 |
| 断言应写在交易所原始参数层 | glm | **采纳** → §8.2 约束 A |
| 测试夹具不得共用同一个 1000 | grok | **采纳** → §8.2 约束 B |
| 实盘核对自动化 | glm | **采纳** → §8.3 第 4 条 |
| 用真实 exchangeInfo 做金样 | grok | **采纳** → §8.2 用例 14 |
| 旧清单「UM 保证金估算需合约价」应删 | grok | **采纳**（已核实无该路径）→ §4.1 |
| §5 三条净减项成立 | 双方 | **维持**，并补第四条 §4.4 |
| §3.1 形状选择 | glm 维持 / grok 不反对 | **维持形状，删夸大表述** |

---

## 11. 给评审的问题

1. **§2.2 的 `(x, y)` 每腿乘数口径是否覆盖完全？** 特别是：是否存在既非「数量」
   也非「价格」、但同样受倍数影响的第三类量（例如名义价值、保证金、手续费口径）？
   §4 主张名义价值是不变量、无需第三类乘数——请独立验算。
2. **§3 是否仍有遗漏路径？** r1 漏了平仓、平滑、展示三条。请独立搜索是否还有第四类
   路径在消费两腿数量或价格（建议覆盖：借币链路、划转链路、任务卡日志、导出/报表）。
3. **§3.1 的 `split_legs` 落点是否正确？** 拒发放在 `service.py:3570`、
   `prepare_attempt`（`3614`）之前是否足够？三处共用是否还有第四处装配点？
4. **§2.4 的判断是否成立？** 本稿主张取整不可交给 Human 主观过滤，理由是合约腿
   不落格会被交易所拒而现货腿并发已成交 → 单腿。请核对该失败路径是否真实存在。
5. **§5.2 容差 `[0.5×, 2×]` 是否过宽？** 本稿论据是「对数量级错误检出率与紧容差
   相同，故应最小化误拦」。若认为存在紧容差才能抓到的真实错误类型，请举出。
6. **§8.2 的两条反自证约束是否足够？** 若仍存在「实现与断言共用同一错误假设」的
   残余路径，请指出。
