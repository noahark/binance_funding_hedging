# Review 请求：展示层诚实性四项修复 + 1000x 乘数币 fail-closed

- 日期：2026-08-07
- 提交：`d7057e3`（实现）、`cae52a1`（文档补充 + 一处措辞订正）
- 基线：`dd0b3e3`
- 实现者：Opus 5
- 测试：后端 **1587 passed**（新增 15 条）、前端 self-check **EXIT=0**（新增 1 组断言）

---

## 0. 请先看这一条：本轮最重要的发现不在原定范围内

Human 点的是四项展示层缺陷（B2/B3/B4/Q4）。做 B3 时为确认两腿数量口径，顺藤查出一个
**资金安全级别的缺陷**，它比原定四项都严重，且**是当日早些时候我自己的改动打开的口子**。

### 缺陷

执行链两腿发的是**同一个** `q_common`：

```python
# backend/services/live_hedge_executor.py:873
send_qty = ctx.q_common if ctx.q_common is not None else ctx.single_amount
# 现货腿 quantity=send_qty，合约腿 quantity=send_qty
```

但 1 张 `1000BONKUSDT` = 1000 个 BONK。于是：

```
输入 N  →  现货买 N 个 BONK
        →  合约空 N 张 = N×1000 个 BONK
        →  净裸空 999N
```

全链路 grep 不到任何乘数换算。连带 `est_price = self._read_est_price(spot_symbol)`
（`hedge_preflight_provider.py:832`）取的是**现货**价，所以 `required` 与合约腿的
minNotional 校验也一起错 1000 倍——口径是全面错乱，不是单点。

### 归因（不粉饰）

2026-08-07 早些时候我加的 `SPOT_SYMBOL_MAP` 让这 6 个币（BONK/FLOKI/LUNC/PEPE/SHIB/XEC）
第一次通过 `check_symbol_legs` 的现货腿存在性探测。**在此之前它们建不了任务**。
换句话说：映射表补上了「叫什么」，但「一张等于多少个」从来没人补，而前者一通过，
后者的缺失就变成了可执行的风险路径。

### 实际影响：零

实盘库 `hedge_open_task` 历史币种只有 SNXX/THE/XLM/XVG/WLD，这 6 个**从未开过**。

```
$ sqlite3 -readonly data/hedge-open-tasks.sqlite3 \
    "SELECT coin, COUNT(*) FROM hedge_open_task WHERE coin LIKE '1000%' GROUP BY coin;"
（空）
```

### 止血（已实施）

`service.py:807`，建 open 任务时 fail-closed：

```python
if task_type == D.TASK_TYPE_OPEN:
    mult_spot_symbol, _, mult_match = resolve_spot_identity(coin)
    if mult_match == SPOT_MATCH_MULTIPLIER:
        raise D.HedgeError(400, "multiplier_contract_unsupported", ...)
```

拦在 `check_symbol_legs` 之后、`compute_preflight` 之前——纯查表零 IO，preflight 的
实盘读取都省了。

### 请重点审这两点

**(a) 拦截位置与范围是否正确。** 我只拦 `open`，放行 `close`。

并且我要主动交代一处**自我订正**：最初写注释时我说「平仓逃生口必须活着」，暗示
close 是安全的。复核后发现**这个说法是错的**——`close` 走同一个 `compute_preflight`
（`service.py:814-820`），同样两腿发一个 `q_common`，自动平仓的腿量同样错 1000 倍。
放行只是不再额外添堵，真要处置这种仓位得人工去交易所平。注释与 PROJECT_STATE 都已订正。

**那么问题是：既然 close 也不安全，还应不应该放行它？** 我的判断是应该，理由是
拦住 close 会把仓位彻底困在系统里（连记账都动不了），而放行至少保留了任务侧的可操作性，
且历史库中并无此类仓位、风险是纯理论的。但这是个可以有不同意见的判断，请给结论。

**(b) 换算本身没做，是否接受。** 它要动下单数量这条资金路径，我判断需要 Human 明确授权
后单开一轮，不该在展示层修复这一轮里顺手夹带。已在 PROJECT_STATE 的 Open Follow-ups
列出必须一次改齐的五处（下单量 / est_price 量纲 / grid 的 lcm 不再成立 / required /
持仓表敞口比较）、改完要移除的三处脚手架，以及验收要求（**单测容易两边用同一个错误
假设而全绿，需最小额度实盘开平后核对交易所实际持仓**）。

---

## 1. B3 — 单腿敞口判定

### 原缺陷

```python
row["single_leg_exposure"] = bucket is not None and spot_qty > 0 and perp_qty == 0
```

Human 报的是「部分失衡读作无敞口」。修的时候发现还漏了更严重的一半：这个式子写死
`spot>0 且 perp==0`，**只看裸多，裸空（合约腿在、现货腿没有）从来没报过**——而那是
风险上不封顶的一侧。

### 修法

```python
larger = max(spot_qty, perp_qty)
row["single_leg_exposure"] = (
    bucket is not None
    and larger > 0
    and abs(spot_qty - perp_qty) > larger * _EXPOSURE_IMBALANCE_TOLERANCE  # 1%
)
```

### 阈值的理由

两腿发同一个 `q_common`，本应逐位相等。1% **只吸收精度/舍入**，不是「允许 1% 敞口」——
真实单腿至少是一整组 `q_common` 的量级，比它高几个数量级。

### 请审

- 1% 是否合适？我考虑过绝对量阈值但否决了（币种量级从 BTC 0.001 到 SHIB 1000000 跨 9 个
  数量级，绝对阈值不可行）。
- 字段名 `single_leg_exposure` 现在语义是「两腿不平衡」，我**没有改名**（会波及前端、
  测试、API 契约），只在注释里说明。前端标签仍是「单腿敞口」。这个取舍是否接受？
- 新增测试 5 条：裸空、部分失衡、1% 内容差、`no_task` 行不报、原有裸多形态保持。

---

## 2. B2 — drift 账户口径

### 原记录的说法需要订正

PROJECT_STATE 原文写「drift 读普通现货账户而对冲买入统一账户，故**永久**失效」。
核实后**这个说法不完全准确**：现货腿落哪个账户是 `decide_spot_route` **动态**决定的——

| 场景 | 路由 |
|---|---|
| open + forward，cap 打满 | `regular_spot` |
| open + forward，bStock | `regular_spot` |
| open + forward，其余 | `papi_margin` |
| open + reverse | `papi_margin` |
| close + forward | `regular_spot`（固定） |
| close + reverse | `papi_margin` |

所以旧判定对**大多数**币失效，而非全部——对 bStock 和 cap 打满的币，它比的账户恰好是对的。

### 修法

两账户余额求和后再与任务记账比较：

```python
if not account_readable or recorded_spot is None or recorded_spot <= 0:
    row["drift"] = False
else:
    held = real_spot if real_spot is not None else Decimal(0)
    unified_amt = _merge_num(row.get("unified_balance"))
    if unified_amt is not None:
        held += unified_amt
    row["drift"] = held < recorded_spot
```

### 两个设计取舍，请审

**(a) 求和 vs 按路由选账户。** 我选求和。按路由选更精确，但路由是 per-task 的动态决策，
merge 层拿到的是聚合桶（可能跨多个任务/周期），要正确对齐得把路由也带进桶——改动面
大得多。求和是**保守方向**：同资产的无关持仓可能掩盖真实减少（假阴性），但**绝不凭空
造出持仓**，所以**一旦报警就说明账户确实少于记账**。这个取舍是否接受？

**(b) `verified=false` 必须直接 False。** 两张余额表在那种状态下都是空的，照常求和会把
「读不到」算成 0，给每一行印假告警——正是 F4「未经检查就声称」那类错误。我给
`_merge_build_row` 加了 `account_readable` 参数（来自 `merge_positions` 的 `verified`）。
新增参数是否比其他方案（如用 `None` 哨兵区分空字典与不可读）更好？

新增测试 3 条：统一账户不足报警、两账户求和达标不报、账户不可读不报。

---

## 3. B4 — 两个死词汇

### (a) `exposure_alert` 整个删除

确认无写入方：`grep -rn "STATUS_EXPOSURE_ALERT"` 只有常量定义、`ALL_STATUSES` 成员、
`?status=` 过滤器的错误消息、前端 label/badge/两处判定——**没有任何 `set_task_status`
写它**。`service.py` 的注释写明它在 breakdown §4.5 把单腿敞口降级为 advisory 后就退役了。

所以我选择**删除概念而非补写入方**——补写入等于推翻 §4.5 的决策。

实盘库该状态 0 行：

```
$ sqlite3 -readonly data/hedge-open-tasks.sqlite3 \
    "SELECT status, COUNT(*) FROM hedge_open_task GROUP BY status;"
deleted|9   done|12   stopped|1
```

零迁移风险。删除后 `?status=exposure_alert` 返回 400，这是正确的（该状态不存在）。

**请审**：删除 vs 保留占位，是否同意删除？

### (b) 终态任务的结算文案

原行为：deleted/done/stopped 任务的 `order_state_unknown` 结算记 `kind=task_paused`，
时间线渲染成 `overall_result=任务暂停` / `next_action=已暂停`，中文说「任务已暂停，
请…手动恢复」——**三个假声明**（没暂停、不可恢复、还指示去做一个不存在的操作）。

修法：新 kind `order_state_unknown_final` → `overall_result=manual_verification` /
`next_action=verify_manually`（前端「待人工核实」/「去交易所核实」），文案改为：

> 订单状态经 10 次重试查询仍不明，无法确认是否已被交易所接受。本任务已删除，状态不再
> 改写、也无法恢复；请到交易所核实这笔订单的实际下场——系统不会重发下单，也不会自动补平

**行为一行未改**：sticky 状态、腿保持非终态、永不重发三条都原样。

**请审一处细节**：我把静态 sticky 测试**和**并发删除测试都切到了新 kind。理由是如果
只改慢路径，「已删任务不自称暂停」这条修复在并发窗口里就不成立。这个判断是否正确？

---

## 4. Q4 — 统一账户「最多可转出」

### 原缺陷

前端拿 `cross_margin_free` 当可转出额，**代码注释里已经承认它不准**（`snapshot.py:1290`
「it is NOT a max-transferable quote」），但一直没接正确数据源。三个数互不相等：
`cross_margin_free` 393.22 / PM `total_available_balance_usdt` 192.51 / 币安界面 222.xx。

### 修法

三层：

1. `private_client.fetch_max_withdraw(asset, force=False)` — 照搬同族 `fetch_max_borrowable`
   的模式，白名单 15→16
2. `GET /api/private-account/max-withdraw?asset=X` — 只读端点
3. 前端「最多可转出」行，选中资产时按需拉取

### 三个设计决定，请审

**(a) 按需实时读，不进快照。** 理由：per-asset 一次请求（进快照要为每个资产各调一次，
统一账户 20 个资产就是 20 次），且该值随价格波动——缓存住就会在按「划转」那一刻给出
过期的数。所以走 `force=True` 绕开 client 缓存。

**(b) 读不到时显示「—（读取失败：…）」，绝不回退 `cross_margin_free` 顶替。**
那正是本项要修的毛病，回退等于把老 bug 换个位置留着。self-check 有一条断言专门守这个：
失败文案中**不得出现任何数字**（`if (/\d+\.\d+/.test(text)) throw`）。

**(c) 端点读不到时返回 200 + `max_withdraw: null`，不返回错误码。** 调用方要能区分
「读不到」和「是 0」——0 是一个合法且重要的答案（账户满仓抵押时确实一分钱转不出）。

### 未做（请确认是否接受）

- `cross_margin_free` 仍是「可用」列的口径。它本身没错，错的是拿它冒充可转出额。
- 前端超额校验仍按可用额拦。真正的拦截以服务端/交易所为准。

新增测试：client 层 2 条、端点 wire 5 条（含大小写归一、缺参 400 且不打交易所、
503 分支）、self-check 1 组 4 项。

---

## 5. 两处 deny-by-default 白名单挡住了我（设计意图生效）

- 后端私有端点白名单：`test_whitelist_accepts_exactly_fifteen_get_endpoints` 红了，
  必须显式改成 16 并在 papi 路径集合里加一行。
- 前端同源白名单：`fetch URL 不在同源白名单` 红了，必须显式加正则。

两处我都改了测试并在注释里写明为什么。**请确认这不是在「绕过守卫」而是守卫的正常用法**。

另有一处：`test_hedge_domain_package_does_not_import_live_adapter` 抓到我在注释里写了
live 模块名（那个守卫连注释都查）。我改了措辞而非放宽守卫。

---

## 6. 测试脚手架的一处妥协，请重点审

P0 拦截让三个既有测试无法构造场景（它们用 1000BONKUSDT 建 open 任务来验证身份固化
和平仓划转）。我的处理：

```python
def _allow_multiplier_open(monkeypatch):
    """1000x 开单已被 P0 fail-closed。身份固化与平仓路径对乘数币的正确性仍然要守——
    那是「拦截生效前的历史仓位」必须能平掉的逃生口。这里只关掉建单拦截，被测逻辑
    本身一行未改。"""
    monkeypatch.setattr(service_mod, "SPOT_MATCH_MULTIPLIER", "__off_for_test__")
```

**担心的是**：这等于在测试里关掉一道资金安全闸门。我认为可接受，因为被测的是身份解析
与划转资产名（与腿量无关）、且注释写明了意图。但这是个可以有不同意见的地方——
如果你认为应该改成直接构造 DB 行而非关闸门，请说。

（注意：上面 docstring 里「逃生口」的措辞沿用了我最初的错误理解，实际 close 也不安全——
见 §0。这处 docstring 措辞我保留待你意见，因为改它要连带解释一整段。）

---

## 7. 完整改动清单

| 文件 | 改动 |
|---|---|
| `backend/hedge_open_tasks/service.py` | P0 拦截；两处 exposure_alert 注释；终态结算新 kind + 映射 |
| `backend/hedge_open_tasks/domain.py` | 删 `STATUS_EXPOSURE_ALERT`；新 `order_state_unknown_final_reason_zh`；B3 判定 + 常量；B2 判定 + `account_readable` 参数 |
| `backend/services/private_client.py` | 白名单 +1；`fetch_max_withdraw` |
| `backend/app/server.py` | `GET /api/private-account/max-withdraw` |
| `frontend/index.html` | 删 exposure_alert 三处；`loadMaxWithdraw`/`maxWithdrawText`/`renderMaxWithdrawLine`；「最多可转出」行；提示措辞 |
| `frontend/self-check.js` | mock 元素 +1；fetch mock +1；同源白名单 +1；Q4 断言组 |
| 测试 | 见各节 |
| `PROJECT_STATE.md` | A/B/exposure_alert/终态文案/Q4 标 RESOLVED；P0 入 Live Risks；1000x 换算入 Open Follow-ups |

---

## 8. 我希望你重点看的（按重要性）

1. **§0 (a)** — 拦 open 放行 close 的判断，在「close 同样不安全」这个事实下是否仍成立
2. **§0 (b)** — 换算未做、列为待授权 follow-up，五处清单是否有遗漏
3. **§2 (a)** — drift 求和 vs 按路由选账户
4. **§6** — 测试里关掉资金安全闸门的妥协
5. **§1** — 1% 阈值与不改字段名的取舍
6. 有没有我**自己没意识到的**、被这轮改动打开的新口子——上一次就是这么栽的
