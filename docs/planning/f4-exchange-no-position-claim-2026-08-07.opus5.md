# F4 修复计划：「交易所无仓」在未经检查时被声称

- 日期：2026-08-07
- 作者：Opus 5
- 状态：**已交付（r3 简化方案）**。Human 2026-08-07 定稿改用更简的做法，双评审对 r2 的判据/路径/回归结论仍全部适用，见 §11。
- 对应 PROJECT_STATE：Merged Position Table 段 `[OPEN][ACCEPTED]` **F4**
- 基线提交：`3b7a6d2`

---

## 1. 问题

持仓表在**读不到交易所数据时**，对每一行都印出「交易所无仓」，并在悬浮提示里补一句
「可能已强平或手工平仓」（`frontend/index.html:5804`）。

已验证：账户块里**明明含有那个持仓**时，它照样这么印。

危险在于时机耦合：一次交易所故障会同时触发 `order_state_unknown`（任务暂停、要你去
核对）**和**这句假声明。**表最不可信的时刻，正是你最需要它的时刻。**

现行操作规矩（PROJECT_STATE 已载明）：「交易所无仓」本身永远不足以证明仓位没了，
去币安核实。本计划的目标是让这条规矩不再必要。

## 2. 三条路径与现状

`no_um` 由 `merge_positions` 判定（`domain.py:1993-2001`）：`um is None and bucket is
not None`。而 `um is None` 有两种截然不同的成因，代码不区分：

| # | 触发 | `verified` | UM 数据 | 现状横幅 | 现状行内 |
|---|---|---|---|---|---|
| 1 | `private_account is None`（快照未就绪） | `false` | 无 | ✅ 显示 | ❌ 印「交易所无仓」 |
| 2 | 凭证失效 / 两个余额源都失败 | `false` | 无 | ✅ 显示 | ❌ 印「交易所无仓」 |
| 3 | **`um_positions` 单源 fetch 失败** | **`true`** | **降级为 `[]`** | **❌ 不显示** | ❌ 印「交易所无仓」 |

路径 3 是最隐蔽的，因为它**没有任何外部提示**。

### 2.1 路径 3 的根因（有意的降级，但事实丢了）

`fetch_um_positions` 的契约（`private_client.py:604-607`）：

> Returns the raw list (**empty when flat**) or **`None`** (disabled/failed).

即 `[]` 与 `None` 是**两个不同的答案**——「确实没有仓位」vs「没读到」。

但 `assemble_private_account` 的降级规则（`snapshot.py:1213-1215` docstring）：

> Otherwise `verified=true` with available arrays
> (**a failed single source degrades to an empty array**, not a block-level failure)

单源失败不拖垮整个块——**这个降级本身是对的**（余额还能看，不该因为 UM 挂了就整块不可用）。
错的是降级时把「这是降级」这个事实丢了：下游只看到 `[]`，无法与「真的空仓」区分。

### 2.2 现有的可用信号

`private_account.source_checked_at` 已按源记录成功时间（实测本机）：

```json
{"price_map": "...", "unified_balances": "...", "um_positions": "2026-08-07T15:13:49Z",
 "spot_balances": "...", "pm_account": "..."}
```

**但本计划不采用它做判据**，理由见 §4.1。

## 3. 设计原则

1. **区分「不知道」与「知道没有」，在数据结构上分开，不靠下游推断。**
   这与本轮已交付的 drift 修复同源：`_merge_build_row` 的 `account_readable` 参数就是
   「账户读不到时不报 drift」，而不是让 drift 逻辑去猜。
2. **记录事实，不做事后推断。** 失败发生在 `assemble_private_account` 的入参处
   （`um_positions is None`），那里知道得最准；越往下游越只能靠时间/空值猜。
3. **不改降级策略。** 单源失败仍然只降级该源，不升级为块级失败——那会让余额、
   现货、PM 摘要一起消失，是更差的产品行为。
4. **fail-loud 而非 fail-closed。** 这是展示层，不是资金闸门。正确的行为是**说不知道**，
   而不是拒绝渲染。

## 4. 方案

### 4.1 契约层：把「哪些源没读到」写进 `private_account`

`backend/domain/snapshot.py::assemble_private_account`

新增块级字段（additive）：

```python
"unavailable_sources": ["um_positions"]   # 本次组装时为 None 的源，稳定排序
```

- 判据是**入参是否为 `None`**，不是数组是否为空——`[]` 是合法答案（真的空仓/空钱包）。
- **键名必须复用 `_SOURCE_CHECKED_AT_KEYS` 的正式名**（`snapshot.py:80-86`）：
  `unified_balances` / `spot_balances` / `um_positions` / `pm_account`。
  原计划写的「unified / spot」是口语化简称——同一个块里出现两套命名会让消费方
  分不清该按哪套匹配（review-2 DeepSeek 指出）。`price_map` 不属于账户源，不收录。
- `verified=false` 时该字段仍照常填（此时通常是全部四个）。

**为何不用 `source_checked_at` 推断**：它记的是「最后一次成功的时间」。本次失败但
曾经成功过的源，时间戳仍是旧值——要判定「本次是否失败」就得引入新鲜度阈值，那是**推断**
而非事实，且阈值必然与各源的刷新节奏耦合（Group A/B 节奏不同）。入参 `None` 是无歧义的。

**为何不用「数组为空」**：`[]` 恰恰是「确实没有任何 UM 持仓」这个重要真值的表示。
拿它当失败信号，会在真正空仓时误报「未知」——把一个假声明换成另一个假声明。

### 4.1.1 默认值语义：字段缺失 = 源可用（review-1 kimi 复核后钉死）

`unavailable_sources` 缺失或为空时，**必须视为「该源可用」**，不得反过来 fail-loud。

这不是图省事，是回归复核推出来的硬约束：五处既有 `no_um` 断言中，
`test_hedge_cycle_core.py:259/289/306` 用的是 `um_positions: [_um()]`——**UM 列表有内容**，
只是那些行没匹配上（已平仓周期 / 同键多周期只消费最近的）。这是最纯粹的 `no_um`。
若默认按「不可用」处理，这五处会集体变成 `um_unknown`——**把一个假声明换成另一个**。

**风险与缓解**：默认可用意味着任何忘记填该字段的组装路径会静默退回旧的假声明行为。
故 `assemble_private_account` 必须**无条件**输出该字段（成功时为空列表，而非省略），
并由测试钉死「该键恒存在」。这样「缺失」只可能出现在测试自造的 mock 里，不会出现在
生产链路上。

### 4.1.2 `account_meta` 透传（review-1 kimi 指出的缺口）

前端横幅读的是 `state.hedgeAccountMeta`（`index.html:5728`），其来源是
`merge_positions` 返回的 `account_meta`，当前只有 `verified` / `error` / `checked_at`
（`domain.py:2042-2046`）。计划原文说横幅要读 `unavailable_sources` 却没交代它怎么
进入前端视野——**这是原计划的缺口，kimi 复核时抓到。**

已有先例可循：`server.py:1094` 在 merge 返回后于组装根追加 `source_checked_at`。
但本字段**不照搬那个模式**，改为在 `merge_positions` 内部写进 `account_meta`：

- `source_checked_at` 是**纯展示**数据，merge 层不消费，放组装根合理；
- `unavailable_sources` 是 §4.2 的**判定依据**，merge 层必须读它。让判定与展示共用
  同一次读取，避免两处各读一次而漂移（本轮 drift 修复踩过的正是「同一事实两处各判一次」）。

**与 review-2 的分歧（保留记录，Human 可推翻）**：DeepSeek 建议照搬 `source_checked_at`
的组装根模式，在 `server.py:1093` 附近附加。两方案产出的 wire 形状**完全相同**，当下
无优劣；分歧只在抗未来漂移：若某天 merge 的判定加了额外条件（例如「源虽可用但过旧
也算不可用」），组装根那份展示值不会跟着变，横幅与行内标记就会各说各话。**我选择
merge 内部写入以消除这个可能**。若评审坚持一致性优先，改回组装根只是搬一行，不影响
本计划其余部分。

**`private_account is None` / `verified=false` 时的取值**：`account_meta.unavailable_sources`
填**全部四个源**（诚实——此时确实一个都没读到），而不是空列表。空列表在 §4.1.1 的
语义下等同「全部可用」，在这里会是又一次假声明。

### 4.2 判定层：`match_status` 新增 `um_unknown`

`backend/hedge_open_tasks/domain.py::merge_positions` / `_merge_build_row`

```
um_unknown : 有任务记录，但 UM 侧数据本次未读到 —— 无法判断交易所是否还有仓
no_um      : 有任务记录，且 UM 侧确实读到了、其中没有这个仓位
```

判定顺序（`um is None and bucket is not None` 分支内）：

```python
if not um_readable:      # 来自 unavailable_sources / verified
    row["match_status"] = "um_unknown"
else:
    row["match_status"] = "no_um"
```

`um_readable` 沿用 §4.1 的事实，经 `merge_positions` 参数传入 `_merge_build_row`
（与既有 `account_readable` 同一模式，不新增全局状态）。

**读取必须对字段缺失容错**（review-2 DeepSeek 指出，§4.1.1 的语义在此落地）：
写成 `pa.get("unavailable_sources") or []`，缺失/`None` 一律当空列表处理。旧缓存块与
测试自造块都不带这个字段，直接下标或假定非空会让 `test_positions_merge.py:120/129`
直接 `TypeError` —— 那不是「测试需要更新」，是实现没兜住向后兼容。

**路径 1/2 一并收编**：`verified=false` 时 `um_readable` 也是 `false`，于是那两条路径
的行内文案同样从「交易所无仓」变成「未知」——**三条路径在同一处收口**，不是打三个补丁。

### 4.3 展示层

`frontend/index.html:5804` 附近：

| `match_status` | 标记 | 悬浮提示 |
|---|---|---|
| `no_um`（文案降调） | 交易所无仓 | 本地有任务记录，但**交易所当前无对应持仓（可能已强平、手工平仓或周期已结束）** |
| `um_unknown`（新） | **交易所仓位未知** | 本次未读到交易所持仓数据，**无法判断该仓位是否还在**；请到币安核实。本地任务记账仍展示在本行 |

`no_um` 文案降调（§8-3）**纳入本轮**：两位评审都建议做，DeepSeek 给了措辞。理由是
即便 UM 确实读到了、确实没这个仓位，「可能已强平」也只是三种成因之一（还有手工平仓、
周期已结束、本地记账过期）。修完假声明却留半句推测，等于活儿只干一半。改动是一行文案。

配色：`no_um` 现为 `risk-warn`；`um_unknown` 用中性/`muted` 色——它不是风险结论，是
**没有结论**，不该和真实告警抢注意力。

横幅（`index.html:5730`）：现在只在 `account.verified === false` 时出现。改为
`verified === false` **或** `unavailable_sources` 非空时出现，文案带上具体源名。
这样路径 3 第一次有了外部提示。

### 4.4 契约常量

`_POSITION_KEYS` **不变**（`match_status` 已在其中，只是取值域扩了一个）。
`private_account` 的 `unavailable_sources` 是新字段，需同步该块的形状测试。

## 5. 测试计划

新增（`test_positions_merge.py`）：

1. UM 源不可用 + 有任务记录 → `um_unknown`，且**不是** `no_um`
2. UM 源可用且返回 `[]`（真空仓）+ 有任务记录 → 仍是 `no_um`（**不得**被误判为未知）
3. `verified=false` → `um_unknown`（路径 1/2 收编验证）
4. UM 源不可用时，`no_task` 行不会凭空产生（它们本就来自 UM 列表）
5. `um_unknown` 行的其余字段（任务记账、成本基）照常呈现——不因未知而清空

`test_private_account_v1.py`：
5b. `unavailable_sources` 键**恒存在**（成功路径为空列表，不得省略）——§4.1.1 的
    默认值语义靠它兜底。
6. `um_positions=None` → `unavailable_sources` 含 `"um_positions"`，且 `verified` 仍为 `true`
7. `um_positions=[]` → `unavailable_sources` **不含** 它（空数组是合法答案）

`test_positions_merge.py`（向后兼容，review-2 DeepSeek 建议）：
7b. `private_account` **不带** `unavailable_sources` 字段（旧块/测试构造块）→
    merge 不抛异常，按「无源不可用」处理，行仍判 `no_um`。
    这条钉住的正是 §4.1.1 的隐含语义——目前没有任何测试守它。

self-check：
8. `um_unknown` 渲染为「交易所仓位未知」且**不含**「无仓」二字
9. `unavailable_sources` 非空时横幅出现并点名源

回归：现有 5 处断言 `"no_um"` 的测试需逐条确认其场景属于「真空仓」还是「读不到」，
**分类错的要改，不是改断言让它变绿**。

## 6. 明确不做

- **不改单源降级策略**（§3.3）。
- **不为陈旧数据报未知**：缓存命中但已陈旧 ≠ 不知道。数据年龄由既有
  `source_checked_at` 暴露，是独立维度。本计划只解决「有 / 没有读到」。
- **不动 `no_task` 判定**：UM 不可用时压根不会产生 no_task 行。
- **不做主动重试**：展示层不该为了一个标记去打交易所。

## 7. 已知边界

1. **陈旧但成功的数据仍可能是错的**（10 分钟前的 UM 快照，仓位 5 分钟前被强平）。
   本计划不覆盖，`source_checked_at` 已提供判断依据。
2. **部分成功不存在**：`fetch_um_positions` 是整体成功或整体失败，无「读到一半」。
3. `um_unknown` 是**展示状态**，不驱动任何闸门或自动动作。
4. **非 list 返回未处理**（review-2 DeepSeek 提出，同意不处理）：若
   `fetch_um_positions` 返回非 list（如 dict），`um_positions or []` 会把它当真值、
   迭代出键字符串并被逐个滤掉，表现为「真空仓」。币安 `positionRisk` 恒返回 list，
   风险极低；记录在案，本计划不加防御——为一个从未观测过的形状加分支，不值。

## 8. 想请评审判断的开放问题

1. **字段形状**：`unavailable_sources: list[str]` vs 每源一个布尔
   （`um_positions_available: bool`）。前者可扩展、一次覆盖四源；后者更直白但会长出四个字段。
2. **路径 1/2 是否该与路径 3 用同一状态**。我倾向同一个（成因不同但**对操作者的含义
   相同**：这一行的交易所侧无法判断）。反方意见：`verified=false` 已有横幅，行内再变可能冗余。
3. **`no_um` 的爆仓暗示要不要一并降调**。即便 UM 读到了、确实没这个仓位，「可能已强平」
   仍是一种推测——真实成因也可能是手工平仓、周期已结束、或本地记账过期。
4. **是否值得让 `um_unknown` 抑制同行的 `single_leg_exposure` 标记**。该标记只读任务
   记账（不读交易所），所以技术上仍有效；但在「交易所侧未知」的行上并排显示一个敞口
   结论，是否会误导。我倾向**不抑制**（它有独立的、明确的语义），但请判断。
5. **回归的 5 处 `no_um` 断言**里，若发现某处原本就属于「读不到」却被写成 `no_um`，
   那是本缺陷在测试中的固化——请确认这类应当改断言而非保留。

## 9. 预估

- 后端 **4 处**：snapshot 组装（新字段）、merge 判定（`um_unknown`）、
  `_merge_build_row` 参数透传、`account_meta` 写入（原计划漏列，两位评审均指出）
- 前端 2 处（行内标记、横幅）+ `no_um` 文案降调 1 处
- 新增测试 **~11 条**（含向后兼容 1 条、字段恒存在 1 条），回归复核 5 条——
  经两位评审逐条核对，**5 处全部属真空仓场景，应原样保留**
- 无迁移、无 DB 变更、无资金路径改动

---

## 10. 评审结论

### review-1 — kimi（2026-08-07 23:22 CST）：**ACCEPT**，零阻塞

六条事实核查全部 pass（含逐条行号复验）。对 §8 五个开放问题的结论：

| # | 开放问题 | kimi 结论 |
|---|---|---|
| 1 | 字段形状 `list[str]` vs 四布尔 | ACCEPT 列表形状——更简洁、可扩展、四源口径统一 |
| 2 | 路径 1/2 与 3 共用 `um_unknown` | ACCEPT 共用——成因不同但对操作者含义一致，应同处收口 |
| 3 | `no_um` 爆仓暗示降调 | **建议做，但不阻塞本计划**；可改中性的「无对应持仓」 |
| 4 | 抑制 `single_leg_exposure` | **不抑制**——二者语义独立（任务记账 vs 交易所可读性） |
| 5 | 回归断言处置原则 | ACCEPT——5 处大多属真空仓场景；若有本属「读不到」的应改断言而非为绿而改 |

**contested 项（已在本次修订收编）**：`account_meta` 未交代如何透传
`unavailable_sources` → 见新增 §4.1.2；连带补出 §4.1.1 的默认值语义硬约束。

### review-2 — DeepSeek：待回


### review-2 — DeepSeek（2026-08-07）：**REWORK**（细节调整，方向与判据无需重写）

七条事实核查全部 pass。**独立确认了三项我最担心的判断**：

- **无第四条路径**：前端「交易所无仓」唯一输出在 `index.html:5804`，后端 `no_um` 唯一
  判定在 `domain.py:1999`，三条路径全部收口于 `um is None and bucket is not None`。
- **判据否决站得住**：「时间戳推断」（旧值 + 阈值耦合刷新节奏）与「数组为空」
  （`[]` 是真空仓真值）两个否决理由均充分，`入参 is None` 是组装时刻的事实。
- **`no_task` 推理成立**：`no_task` 只产生于 UM 骨架循环，UM 不可用时该循环为空。

另外**逐条核对了全部 5 处回归断言**，结论比原计划的假设更强：
`test_hedge_cycle_core.py:259/289/306` 的 `pa` 都带真实 `um_positions`，
`test_positions_merge.py:120/129` 的 `_pa()` 构造 `um_positions=[]` 表达真空仓——
**没有一处是「读不到」被固化，5 处全部应原样保留**。§8-5 那条担心没有发生。

**阻塞项（横幅数据流断裂）**：与 review-1 的 contested 指向同一处缺口——
**两位独立评审都抓到了同一个洞，说明那确实是原计划的硬伤**，不是过度谨慎。
已在 §4.1.2 收编（含与 DeepSeek 建议方案的分歧记录）。

**三条修复要求的收编位置**：

| 修复要求 | 收编于 |
|---|---|
| `account_meta` 桥接 | §4.1.2（选 merge 内部写入，分歧与理由并存）+ §9 预估补第 4 处 |
| 键名对齐 `_SOURCE_CHECKED_AT_KEYS` | §4.1（口语化的「unified / spot」改正式键名） |
| 缺失字段兼容语义 + 对应测试 | §4.2（`pa.get(...) or []`）+ §5 新增 7b |

**额外发现一并收编**：非 list 返回的边界记入 §7-4（同意不处理）；
`no_um` 文案降调采纳其措辞并纳入本轮（§4.3）。

### 双评审汇总

| 开放问题 | kimi | DeepSeek | 采纳 |
|---|---|---|---|
| 1 字段形状 | list ✓ | list ✓ **+ 键名须对齐** | list + 正式键名 |
| 2 路径 1/2 共用 | 共用 ✓ | 共用 ✓ | 共用 |
| 3 爆仓暗示降调 | 建议做，不阻塞 | 建议做，给了措辞 | **纳入本轮** |
| 4 抑制 single_leg | 不抑制 ✓ | 不抑制 ✓（并指出 drift 已有 `account_readable` 保护，两者层次不同） | 不抑制 |
| 5 回归断言 | 原则 ✓ | **逐条核对：5 处全属真空仓，应保留** | 原样保留 |

两位在五个开放问题上**结论一致**，唯一分歧是 `account_meta` 的写入位置（§4.1.2 已记录）。

---

## 11. r3：Human 定稿的简化方案（已交付）

Human 看过视觉预览后定稿：**保留表格，只在标题后加一行红字**，不做行级状态。

```
对冲开单持仓 （UM 持仓为骨架） 未获取到交易所持仓数据，仅展示本地缓存记录
```

### 为什么它比 r2 更好

r2 要给每一行判 `um_unknown`，读者得逐行扫描才知道出事了；r3 把结论提到标题上，
**一眼看到，且不可能误读**。更关键的是：**表格保留**，本地记账仍然可见——那在故障
时刻恰恰最有用，它告诉你该去交易所核对哪几个币。

### 相对 r2 砍掉的部分

| r2 计划 | r3 实际 |
|---|---|
| `match_status` 新增 `um_unknown` | **不做**——没有行级状态 |
| `_merge_build_row` 参数透传 `um_readable` | **不做** |
| 行内标记 + 新配色 | **不做**——复用既有 `.negative`（红 + 粗） |
| `no_um` 文案降调（§8-3） | **未做**，独立小项留待 Human 决定 |
| §8-4「是否抑制 single_leg_exposure」 | **作废**——没有 `um_unknown` 状态了 |

### 一处立场变更（诚实记录）

§4.1.2 我曾坚持 `unavailable_sources` 由 `merge_positions` 内部写入，理由是「判定与
展示同源、抗未来漂移」。**r3 下这个理由不成立了**——没有行级判定，该字段退化为纯展示
数据，与 `source_checked_at` 完全同类。故改回 **review-2(DeepSeek) 建议的组装根附加**
（`server.py`），与既有模式一致。他的方案在新前提下才是对的。

### 判据与两位评审确认过的结论：全部沿用

- 判据仍是**入参 `is None`**（否决时间戳推断与数组为空，理由见 §4.1）
- 键名对齐 `_SOURCE_CHECKED_AT_KEYS`（DeepSeek 要求）
- 缺失字段按「全部可用」处理（§4.1.1 硬约束）
- 快照整个不在时列全四源，不填空列表
- 5 处 `no_um` 回归断言**原样未动**（两位逐条核对过：全属真空仓场景）

### 前端判据（两种情况都算「表格没在用 UM 数据」）

1. `unavailable_sources` 含 `um_positions` —— 该源本次读取失败/禁用
2. `verified === false` —— `merge_positions` 在此状态下**主动忽略** UM 数据
   （`domain.py`: `um_positions = pa.get(...) if verified else None`），
   哪怕 UM 那一路其实读到了，表格也没在用它

### 实际改动

| 层 | 位置 |
|---|---|
| 契约 | `snapshot.py::assemble_private_account` 两个返回分支各加 `unavailable_sources` |
| 契约 | `schemas/api/public-market/snapshot.schema.json`（`additionalProperties:false` 守卫拦下了，必须显式声明——正是它该做的） |
| 桥接 | `server.py` 组装根附加到 `account_meta`（两个分支） |
| 展示 | `index.html` 标题后条件红字（复用 `.negative`） |
| fixture | 两个 fixture 同步新字段 |

**测试**：后端新增 7 条（4 条契约 + 3 条桥接），self-check 新增 1 组 5 项。
**1601 passed + self-check EXIT=0**。
