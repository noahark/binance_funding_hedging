# 15-fix：2026-07-31-hedge-task-inline-log-v1（修复 dispatch packet，rework 1）

> 两件事一起做：修 review-2 的阻塞发现 R2-F1，**并**按 Human 2026-07-31 决定把交易所
> 返回的权威均价落库并优先展示。后者**扩出了本 stage 原有的「只动读路径」边界**——
> 见下「范围扩大与流程后果」。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-fix-1
- target_role: Implementer（bounded finding repair）
- target_model: `claude_glm`（原实现者；§3 #6「原实现者以最小改动修复明确发现」）
- provider: `zhipu_glm`
- status_revision: 13
- required_skill: `agents/skills/minimal-change-engineer.md`
  （**不要**加载 `senior-developer.md`——本轮是定界修复）
- rework_count: **1**（本轮递增；范围扩大不额外递增，仍是同一交付物的第一次修复轮）

### 范围扩大与流程后果（Human 已授权）

原 packet 的边界是「后端只动读路径」。Part B 要加表列并写入,**碰 schema 与写路径**。
Human 2026-07-31 明确决定两件事一起做,该授权覆盖 `AGENTS.md` §3 #1 对数据写入的要求。

流程后果（Bookkeeper 已告知 Human 并被接受）：本轮修复完成后**必须重跑 review-1**
（§8：review-2 阶段的修复若扩文件、改契约或增风险,须重过 review-1）,然后才回 review-2。
不再适用「窄发现直接回 review-2」的快路径。

## Part A —— 修 R2-F1：「成交时间」列在说谎（review-2 阻塞项）

### 已核实的根因（不要重新调查）

- 该列取 `attempt.ts` = `D.us_to_iso(attempt.get("created_at_us"))`（`service.py:270`）。
- `created_at_us` 在 `prepare_attempt` 的**预发送事务**里写入,早于两条腿 POST。
- **系统里根本没有成交时间**：attempt 表只有 `created_at_us`（`store.py:79`）；leg 表只有
  `dispatched_at_us` 与 `last_query_at_us`（`store.py:97-98`）；交易所的 `transactTime` /
  `updateTime` 从未落库。本轮**不新增**成交时间戳（那是另一件事,不在本轮范围）。

### 钉死的修法

1. 列头「成交时间」→ **「尝试时间」**。全文不再出现「成交时间」字样。
2. **去掉该列的 `order_id` 门控**：`hedgeLogTimeCell`（`index.html:4276`）当前要求「至少一腿
   已受理」才显示。该门控是为「成交时间」这个语义设的；列头改名后顾虑消失,且每一行都
   真实存在一个尝试时间。改为：`attempt.ts` 有值就显示,无值才 `—`。
3. 同步更新 `index.html` 中描述该列的注释与 `self-check.js` 中受影响的断言。

## Part B —— 均价改用交易所返回值（Human 2026-07-31 决定）

### 现状（已核实,不要重新调查）

- 交易所返回的 `avgPrice` **执行器已经解析**：`_avg_price_decimal`
  （`live_hedge_executor.py:93-97`）,POST 与 GET 两条路径都取（`:116`、`:137`）。
- 它**已经传到写库那一层**：`live_hedge_executor.py:467`/`474` 的 `"avg_price": ...`。
- 但 **`hedge_open_leg` 表没有 `avg_price` 列**（`store.py:85-99`）,`_leg_final_fields`
  （`store.py:815`）不取它,于是被丢弃。
- 展示时只能用 `cumulative_quote_amt / cumulative_base_qty` 现算（`service.py:224`）,
  而合约腿的 quote 经常是 `NULL`（币安 2026-07-14 从 UM POST 移除 quote/avgPrice,
  靠事后 GET 补,补不到即 NULL）→ 均价显示 `—`。

### 钉死的修法（**九处**,全部为加性改动）

> **2026-07-31 增补（revision 13）**：实现者在首轮执行中停下回报,指出原清单有两处缺口
> ——漏了 reconcile 写入路径、且未裁定 review-1 r6 守卫与 entries 流。**两处经 Bookkeeper
> 核实全部属实**,清单由六处增补为九处,并追加 r6 守卫裁定（见下）。这是 packet 缺陷,
> 不是实现缺陷；实现者按 AC11/Stop 停下是正确行为,**不额外递增 `rework_count`**。

1. **migration**：`store.py:380` 一带的 `leg_additions` 元组加一行
   `("avg_price", "TEXT")`。沿用既有 per-column ALTER guard 模式,保持幂等。
2. **`_leg_final_fields`**（`store.py:815`）：返回值增加 `avg_price`,取自
   `leg_outcome.get("avg_price")`,**原样透传**。
3. **`resolve_attempt`**（`store.py:1104-1135` 一带）：解包新增值,`UPDATE hedge_open_leg`
   语句增加 `avg_price = ?`。
4. **【增补】`resolve_leg_from_query`**（`store.py:1561`）：签名增加 `avg_price` 关键字
   参数,`UPDATE hedge_open_leg` 语句增加 `avg_price = ?`。
   **这是最关键的一处**——它是事后 GET 补数据的路径,而**合约腿的均价正是靠它补回来的**
   （币安 2026-07-14 从 UM POST 移除了 quote/avgPrice）。漏掉它,Part B 对本次要解决的
   核心场景**完全不生效**。
5. **【增补】reconcile 调用点**（`service.py:1202`）：传 `avg_price=verdict.avg_price`。
   `verdict` 是 `LegDispatch`,已带该字段（`live_hedge_executor.py:265`）,加一行即可。
6. **`_row_to_leg`**（`store.py:258`）：增加 `"avg_price": row["avg_price"]`。
7. **`_leg_to_doc`**（`service.py:214`）：均价优先级改为
   **① 库里存的 `avg_price`（交易所权威值）→ ② 没有则退回既有的 `quote / base` 本地计算
   → ③ 都没有则 `None`**。
8. **【增补】`_entry_spot_leg` / `_entry_perp_leg`**（`service.py:288` / `:314`）：
   **必须与 #7 用完全相同的三级优先级**。这两个是 entries 流的腿投影,与 attempts 流是
   同一笔数据的两个出口——**两流不一致等于同一笔钱在界面两处显示不同的价格**,比单流
   错误更严重。不可只改一个。
9. 补测试：覆盖三级优先级（两流各一套）、migration 幂等、既有行不受损、r6 守卫拆分。

### 【裁定】review-1 r6 守卫的处置（Bookkeeper 2026-07-31）

实现者指出：改动 #7 会让 `test_null_notional_projects_null_on_attempts_and_entries`
（`test_hedge_service.py:474-493`）转红——该用例的夹具 `_NullQuoteExecutor` 带
`avg_price="50000"` 且 quote 为 NULL,现断言两流的 `avg_price is None`。

**裁定：拆分该守卫,不是删除它。** 依据：

- r6 守卫的意图写在 `_leg_to_doc` 的注释里——「an unknown notional is also an unknown
  average price, **so do not divide**」。它禁止的是**用未知的成交额去做除法**,防的是
  「凭空造出一个价格」。
- 交易所返回的 `avgPrice` **不是除出来的**,是交易所的原话。展示它不构成造假,恰恰相反
  ——丢掉它才是让用户看不到真实成本（本轮修复的起因）。
- 因此守卫的**反造假内核必须保住**,但它的边界要精确化。

**拆成两个用例,两流各测**：

- **保内核**：NULL quote + **无** `avg_price` → 两流的 `avg_price` 均为 `None`。
  （需要一个新夹具,或把 `_NullQuoteExecutor` 的 `avg_price` 改为 `None`。）
- **新语义**：NULL quote + **有交易所** `avg_price` → 两流均展示该值,**且值相同**。

原用例中 `cumulative_quote_amt is None` 的断言**一律保留不动**——quote 的 NULL 契约不变。

修改该守卫时须在测试注释中写明：本次变更由 Human 2026-07-31 决定（改用交易所返回的
权威均价）,并说明 r6 的反造假内核由拆分后的第一个用例继续守卫。

> **这是 `avg_price` 字段的资金语义契约变更**：从「由 quote/base 算出」变为「交易所值
> 优先,否则算,都没有则 null」。Bookkeeper 已就此向 Human 说明。

### Part B 的四条硬约束（违反即返工）

1. **只存交易所原话,不得推导。** 不得用 `filled_qty × avg_price` 反推 `cumulative_quote_amt`
   ——`store.py:815` 的 docstring 记载,**review-1 r4（2026-07-29）已明确移除该推导**,
   理由是「该列记录交易所说了什么,绝不替换成推导值」。本轮只是把 `avg_price` 这个交易所
   原话存下来,**不得动 `cumulative_quote_amt` 的 NULL 契约**。
2. **不得改 `_avg_price_decimal`。** 它已把 `"0"` / 缺失映射为 `None`
   （`live_hedge_executor.py:93-97`）——这正是本 stage「`0` 不是价格」硬约束要的行为。
   落库的是 `None` 而非 `"0"`,不要"修"它。
3. **既有数据不得倒退。** migration 后既有 leg 行的 `avg_price` 为 `NULL`,必须仍走
   ② 本地计算,**不能变成 `—`**。要有测试证明历史行的展示与修复前一致。
4. **不扩到别处。** 不碰状态机、调度、结算判定、计数器、暂停/删除、worker、
   `aggregate_positions`；不新增成交时间戳；不碰下单行为。本轮对写路径的改动**仅限**
   多记一列观测值。

## Allowed Files

- `frontend/index.html`（Part A：表头、`hedgeLogTimeCell`、注释）
- `frontend/self-check.js`（受影响的断言）
- `backend/hedge_open_tasks/store.py`（Part B：migration、`_leg_final_fields`、
  `resolve_attempt` 的 UPDATE、**`resolve_leg_from_query` 的签名与 UPDATE**、`_row_to_leg`）
- `backend/hedge_open_tasks/service.py`（Part B：`_leg_to_doc`、**`_entry_spot_leg` /
  `_entry_perp_leg` 的均价优先级**、**reconcile 调用点 `:1202` 传 `avg_price`**）
- `backend/tests/test_hedge_*.py`（新增/修改测试,含按裁定拆分 r6 守卫）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（修复报告）

超出边界即为 blocker,停下回报。

## Inputs

- review-2 verdict 与 Bookkeeper 核实：同目录 `14-review-2-verdict.md`（**必读**）。
- 原 packet 与钱的展示硬约束：同目录 `00-task.md`（`status_revision: 9`）。
- 原交付自述：同目录 `09-delivery.md`（其「成交时间门控」一节即 Part A 推翻的决策）。
- 修复基线：`delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`。

## Acceptance Checks

### Part A（**首轮已完成,自测通过,无需重做**）

1. ~~列头已改~~ —— 已完成：全量搜索「成交时间」= 0。
2. ~~所有行都显示时间~~ —— 已完成：四状态每行第 3 列均显示北京时间,self-check 新断言通过。

保留在工作树中,与 Part B 一并回报。

### Part B

3. **优先用交易所值**：构造一条 `avg_price` 已落库的腿,断言展示的是**库里的值**,
   且与本地 `quote / base` 的计算结果**不同**（用刻意不同的夹具,证明确实走了 ①）。
   **attempts 与 entries 两流各测一次,并断言两流的值相同。**
4. **退回本地计算**：构造 `avg_price` 为 `NULL` 但 quote/base 齐全的腿（模拟既有历史行）,
   断言展示的仍是本地计算结果,**与本次修复前完全一致**。两流各测。
5. **都没有则 `—`**：构造 `avg_price` 与 quote 均缺失的腿,断言展示 `—`,**不是 `0`**。
5b. **reconcile 路径生效**：构造「POST 未带均价、事后 GET 带回 `avgPrice`」的合约腿场景
   （即本轮要解决的核心场景）,断言经 `resolve_leg_from_query` 后该均价已落库并展示。
   **不测这条等于没验证 Part B 的主目的。**
5c. **r6 守卫已按裁定拆分**：两个用例（NULL quote + 无 avg → `None`；NULL quote + 有 avg
   → 展示该值）在两流上均通过,且原用例中 `cumulative_quote_amt is None` 的断言未被改动。
6. **migration 幂等且不损伤既有数据**：对一个已有 leg 数据的库连续跑两次迁移,断言不报错、
   列只加一次、既有行的 `cumulative_base_qty` / `cumulative_quote_amt` / `order_id`
   等字段值**逐字未变**。
7. **未推导、未动 quote 契约**：断言 `cumulative_quote_amt` 的 NULL 语义不变——给一条
   「有 `filled_qty` 和 `avg_price` 但 quote 缺失」的腿,断言 quote 仍为 `NULL`
   （不得被反推成数值）。
8. **`_avg_price_decimal` 未被修改**：`git diff` 证明 `live_hedge_executor.py` 未改动。

### 通用

9. **回归**：`node frontend/self-check.js` 全过；`python3 -m pytest backend/tests -q` 全过
   （贴原始输出）。
   - **唯一允许改动的既有用例是 `test_null_notional_projects_null_on_attempts_and_entries`**
     （按上面的裁定拆分）。这是本轮**预期内**的改动,不是"碰到了不该碰的地方",
     **不要为此停下**。
   - 除它以外的任何既有用例转红,都说明改超了范围——停下回报。
10. **改动量**：给出 `git diff --stat`。预期量级：前端十几行 + 后端二三十行 + 测试。
    若显著超出,停下回报——那说明理解偏了。

## Stop

- 不碰状态机、调度、结算判定、计数器、暂停/删除语义、worker 生命周期、
  `aggregate_positions`。
- 不改 `_avg_price_decimal`；不改 `cumulative_quote_amt` 的 NULL 契约；不做任何推导填充。
- 不新增成交时间戳、不新增 API 路由、不新增轮询定时器。
- 不碰下单行为、不碰凭据、不开 live 闸门、不做部署、不写 live task DB。
- 不扩 scope：不碰「任务卡卡住」全套、不碰持仓聚合。
- 不合并、不推送、不启动评审终端。自测完成后停下回报给 bookkeeper（opus5）。
