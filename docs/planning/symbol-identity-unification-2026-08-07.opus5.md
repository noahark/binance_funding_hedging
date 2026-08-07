# 开发方案：现货腿身份统一（下单 / 平单 / 展示三环同源）

- 日期：2026-08-07
- 执笔：**claude-opus-5**（Claude Opus 5）
- 版本：**r2**（响应 DeepSeek 评审修订；r1 的 D1 已撤销，见 §4）
- 前置：`unified-symbol-resolver-2026-08-07.review-opus5.md`（显式映射表已落地，1533 passed）
- 触发：Human ——「匹配 symbol 这一步应该放到最前面做，如果 symbol 拿错了后面的匹配也都失真了」

## r2 修订摘要（对评审的响应）

| 评审项 | 处置 | 说明 |
|---|---|---|
| **P1** 纯查表判定不了「无现货腿」 | **采纳，且结论更强：D1 整个撤销** | 实证表明拒绝职责**已由现有 `check_symbol_legs` 完整覆盖**，identity 不该也不需要回答存在性。评审给的 a/b 两解法均不采用——正确解法是「不做」 |
| **P1补** 漏了 `tests/fakes.py:155` | 采纳 | 已补入清理清单（§3④） |
| **P2** `spot_base_asset` 来源与冗余性 | 采纳 | §3① 写明来源与取舍 |
| **P3** 旧载体处置未明确 | 采纳 | §3② 明确停写 + 删函数 |
| **P4** 展示环数据载体未写 | 采纳 | §3③ 写明 `aggregate_positions` 的 join |
| **D2** close 身份来源 | **采纳关切，用更轻的方案** | 不给 cycle 加列——`hedge_open_cycle` 已有 `first_task_id`，close 经它继承 open 的身份列，零迁移且严格配对 |
| **D3** 身份不可变告警 | 采纳，默认做 | |
| 小点 测试 10 落接口层 | 采纳 | |

---

## 1. 问题

映射表解决了「规则算错」，但没解决「**谁在什么时候算、算完存哪**」。现货腿身份目前不是任务的属性，而是 **live preflight 的副产品**。

### 1.1 实测证据

库里同一个币的两个任务，解析出两个结果：

```
7f1836fe  SNXXUSDT  preflight={"available":false}  → spot_order_symbol = SNXXUSDT   ★错★
89f80678  SNXXUSDT  preflight 完整                  → spot_order_symbol = SNXXBUSDT  OK
```

`preflight_snapshot.spot_symbol` 只在 live 预检成功时写入（`domain.py:1151`，且仅当 `!= coin`）。没有它，`spot_order_symbol()` 回退到合约 symbol —— 对 bStock / 1000x 必错。上面那条恰好是 `deleted` 状态，没造成损失，但机制缺陷是真实的。

### 1.2 三环现状

| 环节 | 身份来源 | 时机 | 缺陷 |
|---|---|---|---|
| 下单 | `preflight_snapshot.spot_symbol` | 发单前 | 无 live preflight 即回退合约 symbol |
| 平单 | 同上（读开单落库值） | 平单时 | 继承开单的错，且开单没解析时无从补救 |
| 展示 | **当前快照** `asset_map` | 每次渲染 | 与记账不同源；快照未就绪回退 `_merge_base_asset` |

三条路虽都指向同一张表，但**时机与载体不同，仍是三份真相**。

### 1.3 真正难防的风险：类型混淆（非二次转换）

先澄清一个已验证的**非问题**：转换是幂等的。转换后的名字再解析，第一步 exact 命中自己，不会二次转换（新旧规则皆然）：

```
SNXX -> SNXXBUSDT (表命中) --再喂--> SNXXBUSDT (exact_symbol)
B    -> None      (表外)   --再喂--> None
```

真正的风险是**把一类名字喂给期望另一类的函数**。`_merge_base_asset` 只剥 USDT、不做转换：

```
_merge_base_asset("SNXXUSDT")  → "SNXX"    ← 合约名进 → 错的资产名（账户里没这个资产）
_merge_base_asset("SNXXBUSDT") → "SNXXB"   ← 现货名进 → 正确
```

函数没错，错在调用方喂了合约名——**这正是持仓面板读不到 bStock 现货余额的本质**。合约名 / 现货名 / 资产名三者都是裸字符串，传错不报错，只静默算出错答案。

---

## 2. 设计原则

1. **身份在任务创建时确定一次，固化为任务的第一等属性**，此后只读不算
2. **固化优于实时**：对冲是跨时间的持仓，平仓必须用开仓时的身份
3. **单一取值入口**：所有取现货 symbol / 资产名的地方走同一函数
4. **身份与存在性严格分离**（r2 强化，见 §2.2）

### 2.1 为什么固化而非实时

开仓与平仓之间交易所可能改名或下架。若平仓时重新解析并静默切换，两条腿就对不上——比报错危险。交易所真变了 ⇒ `--verify` 报 `STALE` ⇒ **人工介入**，不走自动切换。

### 2.2 身份 ≠ 存在性（r2 核心修正）

r1 让 `resolve_spot_identity` 同时回答「叫什么」和「有没有」，评审 P1 指出后者纯查表做不到——**正确**：表外绝大多数是同名 exact（`BTCUSDT` 有腿），真正无腿的是另一批，二者靠查表无法区分。

但正确的解法不是给 identity 加数据源，而是**它本就不该回答存在性**：

| 关注点 | 由谁负责 | 数据源 | 稳定性 |
|---|---|---|---|
| **身份**：这个合约对应哪个现货 symbol | `SPOT_SYMBOL_MAP` 查表 | 静态表 | 稳定，可固化 |
| **存在性**：该现货此刻能否下单 | 现有 `check_symbol_legs`（S4b/ADR-H5） | 实时 exchangeInfo | **会变，必须实时** |

`KORUUSDT` 是活证据：`service.py:774` 的注释还把它举例为「无现货腿」，但币安后来上线了 `KORUBUSDT`，探测现已放行。**存在性固化不得**。

### 2.3 实证：拒绝职责已被现有机制完整覆盖

用最新 exchangeInfo 跑现有 `check_symbol_legs`：

```
BUSDT            {'spot': False, 'perp': True}  -> ★建任务被拒: missing_leg ['spot']★
1000000MOGUSDT   {'spot': False, 'perp': True}  -> ★建任务被拒: missing_leg ['spot']★
SNXXUSDT         {'spot': True,  'perp': True}  -> 放行
1000BONKUSDT     {'spot': True,  'perp': True}  -> 放行
BTCUSDT          {'spot': True,  'perp': True}  -> 放行
KORUUSDT         {'spot': True,  'perp': True}  -> 放行（现已有现货腿）
```

无现货腿的合约**在 live 模式下早已被拒**。r1 的 D1 在 live 下是纯冗余，在 dry-run 下与既有「dry-run create 不变」的设计冲突。

⇒ **D1 撤销**。连带消除评审担心的两个副作用：1533 个测试的破坏面、以及前端列表的可见行为变化——**都不会发生**。

---

## 3. 改造步骤

### ① 任务表新增身份列 + 创建时固化 + 存量回填

**新增列**（`store.py:_migrate` 的 `additions`，additive-forward + ALTER 守卫，沿用既有模式）：

| 列 | 类型 | 含义 |
|---|---|---|
| `spot_symbol` | `TEXT` | 现货腿交易对，如 `SNXXBUSDT`；普通币等于 `coin` |
| `spot_base_asset` | `TEXT` | 现货资产名，如 `SNXXB` |
| `symbol_match_type` | `TEXT` | `exact_symbol` / `bstock_b_suffix_alias` / `multiplier_strip_alias` |

放列而非塞进 `preflight_snapshot` JSON：后者语义是「发单前的行情快照」，身份不属于它。

**新增纯函数**（`normalize.py`）：

```python
def resolve_spot_identity(contract_symbol: str) -> tuple[str, str, str]:
    """合约 symbol -> (spot_symbol, spot_base_asset, match_type)。纯查表零 IO。

    永不返回 None —— 只回答「身份」，不回答「存在性」（后者是 check_symbol_legs
    的职责，见方案 §2.2）。表内取映射值；表外即同名，返回 (coin, base, exact)。
    """
```

**P2 响应 —— `spot_base_asset` 的来源与冗余性**：由 `spot_symbol` 剥 `QUOTE_ASSET` 得到（`D.base_asset("SNXXBUSDT") == "SNXXB"`，纯字符串截断，安全）。它**是可推导的冗余列**，仍单独存储的取舍：

- 收益：余额/利息/划转三处高频读取免去每次剥取；SQL 侧可直接按资产名聚合
- 代价：与 `spot_symbol` 存在一致性义务
- 护栏：写入只经 `resolve_spot_identity` 一个出口；测试断言 `spot_base_asset == base_asset(spot_symbol)` 恒成立

**创建时固化**（`service.py:create_task`，在现有 `check_symbol_legs` 探测**之后**，不改探测逻辑）：

```python
spot_symbol, spot_base, match_type = D.resolve_spot_identity(coin)
```

三个值随 `create_task` 落库。**不新增拒绝分支**（D1 已撤销）。

**回填脚本** `scripts/backfill-spot-identity.py`：对存量任务按 `coin` 查表写三列。幂等，可重复执行；执行前按 `data/*.bak-*` 惯例备份。

### ② 五个消费点切到任务列（P3：旧载体明确处置）

`spot_order_symbol(coin, preflight_snapshot)` → **删除**，代之以 `spot_symbol_of(task)`。

| 位置 | 现状 | 改为 |
|---|---|---|
| `service.py:67` | `spot_order_symbol(coin, preflight_snapshot)` | `spot_symbol_of(task)` |
| `service.py:2547` | 同上 | 同上 |
| `live_hedge_executor.py:875` | `spot_order_symbol(ctx.coin, ctx.preflight_snapshot)` | 从 ctx 读任务列 |
| `service.py:1639`（平单划转） | `spot_order_symbol` + 手工剥 USDT | `spot_base_of(task)` |
| `service.py:1742`（平单利息） | 同上 | `spot_base_of(task)` |
| **`tests/fakes.py:155`** | `D.spot_order_symbol(ctx.coin, ctx.preflight_snapshot)` | 随 ctx 改造同步（**评审补漏**） |

**旧载体处置（P3）**：

- `preflight_snapshot.spot_symbol`：**停写**（`domain.py:1151` 整段删除，连带去掉「仅当 `!= coin` 才落库」的优化）。**读取侧不保留兼容**——存量行由回填脚本补齐任务列，回填后该字段无人读取；保留读取路径等同保留第二份真相，与本方案核心论据冲突
- `spot_order_symbol`：**删除函数**，非 deprecated。全仓仅 6 处调用，一次改净

### ③ 展示环：`asset_map` 降级为 `no_task` 行专用（P4：载体明确）

**数据载体**：`HedgeOpenStore.aggregate_positions` 的 SQL 增选三列，bucket 字典随之带出 `spot_symbol` / `spot_base_asset`。`merge_positions` 从 bucket 读，**签名不再新增参数**（`asset_map` 保留现有签名位置，仅服务 `no_task` 行）。

base 解析优先级：

```
bucket.spot_base_asset      有任务记录 → 权威，不随快照变
  ↓ 无任务记录（no_task 行：手工下单 / 卡已删）
asset_map（当前快照解析，尽力而为）
  ↓ 快照未就绪
_merge_base_asset(coin)（现状回退）
```

`no_task` 行没有任务列可读，必须保留 `asset_map` 这条路。有任务记录的行则彻底不依赖快照就绪——顺带消除评审早前提出的「冷启动 drift 闪烁」。

`server.py:1097` 的周期统计 base 同样改为优先 bucket 列。

### ④ 收敛取值入口

新增两个函数作为**唯一**入口：

```python
def spot_symbol_of(task) -> str        # 现货交易对：下单 / 查单 / 划转
def spot_base_of(task) -> str | None   # 现货资产名：余额 / 利息 / 借币记账
```

**接口层守卫（评审小点）**：两函数只接受 task 字典，传入裸字符串直接 `TypeError`。任务列是固化值，运行时不存在「传入合约名」的场景——守卫落在接口形状上，而非运行时值检查。

待清理的散落调用（含评审补漏）：

| 位置 | 现状 |
|---|---|
| `service.py:1643` | `D._merge_base_asset(task["coin"]) or task["coin"].replace("USDT","")` |
| `service.py:1746` | `D._merge_base_asset(task["coin"])` |
| `server.py:1097` | `asset_map.get(coin) or _merge_base_asset(coin)` |
| `domain.py:1776` | `(asset_map or {}).get(coin) or _merge_base_asset(coin)` |
| **`tests/fakes.py:155`** | `D.spot_order_symbol(...)` |

`_merge_base_asset` 保留但降级为私有实现细节，仅供 `spot_base_of` 与 `no_task` 回退路径内部使用。

**命名约定**（新增代码遵守，存量不强制重命名）：`contract_symbol` / `spot_symbol` / `spot_base`，不再用裸 `symbol`。

### ⑤ D2：close 任务经 cycle 继承 open 的身份

评审指出 r1 的「close 重新查表」与 §2.1「固化优于实时」自相矛盾，**接受**。但不采用「给 cycle 加列」——`hedge_open_cycle` **已有 `first_task_id`**，无需迁移：

```python
# close 创建时（service.py:760 已取到 active_cycle）
origin = self._store.get_task(active_cycle["first_task_id"])
spot_symbol, spot_base, match_type = identity_of(origin)   # 严格继承开仓身份
# origin 缺失/未回填 → 回退 resolve_spot_identity(coin) + 记 warning
```

这样开平仓严格同腿，且零存储变更。领域上也更正确：对冲的载体是周期，close 是周期的一部分而非独立事件。

### ⑥ D3：身份一致性告警（默认做）

发单前比对任务列 `spot_symbol` 与当前 `resolve_spot_identity(coin)`：不一致则记 warning + 中文事件（**不阻断**）。低成本，能在表更新影响存量任务时及早暴露，并兜住 ⑤ 中 `origin` 缺失的回退路径。

---

## 4. r1 的 D1 已撤销

r1 曾提议「创建时解析失败 → 拒绝建任务」。§2.3 实证表明该拒绝**已由现有 `check_symbol_legs` 完整覆盖**，D1 在 live 下冗余、在 dry-run 下与既有设计冲突。撤销后：

- 不改 `create_task` 的拒绝逻辑，**零行为变化**
- 评审担心的「1533 测试破坏面」与「前端列表可见变化」均不会发生
- 无现货腿合约仍被拒（由探测负责），错误码仍是既有的 `missing_leg`

---

## 5. 测试计划（先红后绿）

| # | 用例 | 断言 |
|---|---|---|
| 1 | dry-run 创建 bStock 任务 | 三列正确落库（复现 `7f1836fe`：改前 `SNXXUSDT`，改后 `SNXXBUSDT`） |
| 2 | **回归锚点**：live 下创建 `BUSDT` 任务 | 仍 400 `missing_leg`（现有行为，非新增；防未来改动破坏 §2.3 的覆盖） |
| 3 | 平单划转资产名 | bStock `SNXXB`、1000x `BONK` |
| 4 | 平单利息资产名 | 同上 |
| 5 | 展示：有任务记录的行 | 不传 `asset_map` 也取到正确 base（不依赖快照） |
| 6 | 展示：`no_task` 行 | 仍走 `asset_map` |
| 7 | 展示：无任务 + 无 `asset_map` | 回退旧规则，不崩 |
| 8 | 回填脚本 | 存量任务三列正确；幂等（重跑结果不变） |
| 9 | `spot_symbol_of` 旧行兼容 | 列为 `NULL` 时回退 `resolve_spot_identity` |
| 10 | **接口层守卫** | `spot_base_of("SNXXUSDT")` 抛 `TypeError`，不静默返回错值 |
| 11 | **冗余列一致性** | 全表 `spot_base_asset == base_asset(spot_symbol)` |
| 12 | **D2 继承** | close 任务身份 == 其 cycle 的 open 任务身份（含 origin 缺失时的回退） |
| 13 | **D3 告警** | 任务列与当前查表不一致时记 warning 且**不阻断**发单 |

回归基线：后端 **1533 passed** + `self-check EXIT=0` + `check-spot-symbol-map.py --verify` 退出码 0。

---

## 6. 风险与取舍

| 风险 | 缓解 |
|---|---|
| 回填脚本改动生产库 | 先备份（`data/*.bak-*` 惯例）；脚本幂等 |
| 冗余列 `spot_base_asset` 一致性漂移 | 单一写入出口 + 测试 11 |
| 表更新后存量任务身份陈旧 | D3 告警（⑥）+ `--verify` 的 `STALE` |
| 改动横跨 store/domain/service/executor/server/tests | 五步独立提交，每步单独可测可回滚 |
| 删除 `spot_order_symbol` 破坏未知调用方 | 全仓已确认 6 处（含 `fakes.py`）。Python 无编译期，兜底是全量测试：残留调用在 import / 调用时抛 `AttributeError`，属显式失败而非静默错值。删除前以 `grep -rn "spot_order_symbol" backend/` 复核调用面 |

**不做**（记录在案）：

- 乘数数量换算（`1000BONK` 合约 1 张 = 现货 1000 个）。当前 drift/single_leg 比较「任务记录的现货买入量 vs 现货余额」，同域无需换算
- 存量变量批量重命名（只约束新增代码）
- 保留 `preflight_snapshot.spot_symbol` 的读取兼容（见 §3② P3 处置理由）

---

## 7. 交付顺序

```
① 加列 + resolve_spot_identity + 创建时固化 + 回填脚本      → 测试 1/8/9/11
② 六个消费点切换 + 删 spot_order_symbol + 停写旧字段        → 测试 2/3/4
③ aggregate_positions 带出三列 + 展示环 asset_map 降级       → 测试 5/6/7
④ 收敛入口 + 接口层守卫 + 清理散落调用                       → 测试 10
⑤ close 经 cycle 继承 + D3 一致性告警                        → 测试 12/13 + 全量回归
```

每步独立提交，全量测试绿后再进下一步。
