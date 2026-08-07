# F4 修复计划：「交易所无仓」在未经检查时被声称

- 日期：2026-08-07
- 作者：Opus 5
- 状态：**待评审**（未动代码）
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
- 覆盖 `unified` / `spot` / `um_positions` / `pm_account` 四个可选源，一次把口径统一。
- `verified=false` 时该字段仍照常填（此时通常是全部）。

**为何不用 `source_checked_at` 推断**：它记的是「最后一次成功的时间」。本次失败但
曾经成功过的源，时间戳仍是旧值——要判定「本次是否失败」就得引入新鲜度阈值，那是**推断**
而非事实，且阈值必然与各源的刷新节奏耦合（Group A/B 节奏不同）。入参 `None` 是无歧义的。

**为何不用「数组为空」**：`[]` 恰恰是「确实没有任何 UM 持仓」这个重要真值的表示。
拿它当失败信号，会在真正空仓时误报「未知」——把一个假声明换成另一个假声明。

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

**路径 1/2 一并收编**：`verified=false` 时 `um_readable` 也是 `false`，于是那两条路径
的行内文案同样从「交易所无仓」变成「未知」——**三条路径在同一处收口**，不是打三个补丁。

### 4.3 展示层

`frontend/index.html:5804` 附近：

| `match_status` | 标记 | 悬浮提示 |
|---|---|---|
| `no_um`（不变） | 交易所无仓 | 本地有任务记录，但交易所无对应持仓（可能已强平或手工平仓） |
| `um_unknown`（新） | **交易所仓位未知** | 本次未读到交易所持仓数据，**无法判断该仓位是否还在**；请到币安核实。本地任务记账仍展示在本行 |

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
6. `um_positions=None` → `unavailable_sources` 含 `"um_positions"`，且 `verified` 仍为 `true`
7. `um_positions=[]` → `unavailable_sources` **不含** 它（空数组是合法答案）

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

- 后端 3 处（snapshot 组装、merge 判定、参数透传），前端 2 处（行内标记、横幅）
- 新增测试 ~9 条，回归复核 5 条
- 无迁移、无 DB 变更、无资金路径改动
