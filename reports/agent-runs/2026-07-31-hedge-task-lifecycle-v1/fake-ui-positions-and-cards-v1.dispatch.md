# Dispatch —— fake-ui-positions-and-cards-v1

> **勘误 2026-07-31（bookkeeper opus5，作者本人就地更正）**：下方 §Inputs 数据形状 A 原将
> `position_side` 写为小写 `"long" | "short"`，与真实契约不符 —— `snapshot.py:893-895`
> 的 `_infer_position_side` 返回**大写** `"LONG"` / `"SHORT"`，零仓为 `null`，
> 前端 `index.html:2198-2204` 的 `directionForPosition` 亦按大写比对。已改为大写。
> 由实现者在交付回执中作为 packet 勘误报出，属 packet 缺陷而非交付缺陷，按 `AGENTS.md` §7
> 采信更正，**不递增 `rework_count`**。本次更正不改变交付效果：实现者已按真实契约（大写）
> 造数据，验收检查通过状态与结论均不变。

```text
Identity:
  task_id:         fake-ui-positions-and-cards-v1
  target_role:     Implementer
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 2
  required_skill:  agents/skills/senior-developer.md
```

## Goal

在 `frontend/index.html` 里新增一个**纯前端、假数据、可切场景**的预览区块，让 Human 在真实实现开工前先看清两样东西的展示形状：

1. **合并后的持仓表** —— 以交易所真实合约持仓为骨架，一行一个合约标的，横向拼上对应的现货/杠杆账户资产与任务卡成交记录；
2. **新规则下的任务卡** —— 六种非人工暂停原因改为自动删除之后，卡片长什么样。

这是**设计探针**，不是功能交付。**不碰后端，不接真实数据，不改任何现有真实渲染路径。** 目的只有一个：Human 看过之后能说「就这么画」或「这里不对」，从而让随后的 HIGH_RISK 真实实现少一轮返工。

范围依据见同目录 `02-scope-decisions.md`（D5/D6/D7/D8）。该文件与本 dispatch 冲突时以本 dispatch 为准。

### 为什么是 LOW_RISK 单评审（`AGENTS.md` §8 要求记录理由）

本任务不触及订单、仓位、借贷、还款、划转、资金/盈亏口径、账务、实盘闸门、风控限额、凭证、控制契约，也不改 Harness 安全或工作流契约：

- 不改任何后端文件，不新增/修改任何 API 端点，不发起任何网络请求（假数据是脚本内常量）；
- 不改动 `renderHedgePositionsSection` 与 `renderHedgeTaskCard` 这两个真实渲染函数（评审可按逐字未变核验）；
- 预览区块默认关闭，且带显著「假数据」标识，不可能被误读为真实账户数据；
- 验收标准明确可执行（下方 Acceptance Checks 逐条可复核 + `node frontend/self-check.js`）。

因此按 §8 走 `LOW_RISK`：一次独立最终评审即可，不需要计划评审与双评审。随后的真实实现仍是 `HIGH_RISK`，走完整路线。

## Allowed Files

可修改：

- `frontend/index.html` —— 唯一的产品代码改动位置
- `frontend/self-check.js` —— **仅限**两种情况：(a) 为预览开关追加断言；(b) 修复因新增 DOM 导致的既有断言失配。**不得放宽、跳过或删除任何既有断言**；任何改动须在实现报告中逐条说明原因

新建：

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/20-fake-ui-implementation.md` —— 实现报告
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/60-fake-ui-test-output.txt` —— `node frontend/self-check.js` 的**原始**输出（不得改写为叙述性总结）

其他任何文件都在边界外。后端目录 `backend/` 全部禁止改动。边界不足即为阻塞项，报告并停止，不得自行扩大。

## Inputs

### 必读（按锚点定位读取，勿整文件读）

| 文件 | 字节数 | 读什么 |
|---|---|---|
| 本 dispatch | 12317 | 全部 |
| `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/02-scope-decisions.md` | 7647 | 全部（§2 是字段事实的权威来源） |
| `AGENTS.md` | 16587 | §3 §4 §7 §8 |
| `agents/roles.md` | 12183 | 仅 Shared Rules + Implementer 段 |
| `agents/developer-discipline.md` | 3662 | 全部 |
| `agents/skills/senior-developer.md` | 11243 | 全部 |
| `frontend/index.html` | 239559 | **仅下列锚点**，禁止整文件读 |

`frontend/index.html` 锚点：

| 行 | 内容 |
|---|---|
| 2729-2764 | 个人账户面板的「UM 持仓」表渲染（真实合约持仓的现有展示） |
| 3551 | `HEDGE_TASK_STATUS_LABELS` 状态中文标签 |
| 3572 | `HEDGE_PAUSE_REASON_LABELS` 暂停原因中文标签 |
| 3750-3760 | 持仓表数据加载（`GET /api/hedge-open-positions`） |
| 4169-4235 | `renderHedgeTaskCard` 任务卡渲染（**不得修改**） |
| 4407-4470 | `renderHedgePositionsSection` 现有持仓表渲染（**不得修改**） |
| 813 起 | 既有 fake 预览的 CSS 先例（`F10-fake 预览`），可参照其标注风格 |

参考先例（可选读，帮助对齐本仓 fake 原型的既有做法）：`git show 5871791 -- frontend/index.html`，上一次任务卡 fake 原型的完整做法。

### 数据形状（必须照此造假数据，不得编造「好看的数字」）

真实契约字段名与取值形状如下。假数据的**字段名、类型、小数位风格必须与之一致**，这是为了避免上一轮 `hedge-open-live-v1` 发生过的 fake→真实接线漂移（3 次抓修）。

**A. 真实合约持仓** —— `state.snapshot.private_account.um_positions[]`

```text
symbol             字符串，如 "BTCUSDT"；1000x 倍率币为 "1000PEPEUSDT"
position_side      "LONG" | "SHORT" | null（大写；由 position_amt 符号推出，为零时 null）
notional_usdt      字符串
position_amt       字符串，带符号，空头为负，如 "-0.153"
entry_price        字符串
mark_price         字符串
unrealized_profit  字符串，可正可负
liquidation_price  字符串；无值时币安返回 "0" 而非空，必须如实体现
```

**B. 统一账户资产** —— `state.snapshot.private_account.balances_unified[]`

```text
asset                   字符串，如 "BTC"
total_balance           字符串
cross_margin_borrowed   字符串 | null（全仓借款额；null 表示无该字段）
value_usdt              字符串 | null
```

**C. 现货账户资产** —— `state.snapshot.private_account.balances_spot[]`

```text
asset    字符串
free     字符串
locked   字符串
value_usdt  字符串 | null
```

**D. 任务卡本地记账** —— `GET /api/hedge-open-positions` → `positions[]`

```text
coin                        完整符号，如 "BTCUSDT"
direction                   "forward"（现货买入+合约做空） | "reverse"（现货卖出+合约做多）
position_qty                字符串，带符号
spot_avg / perp_avg         字符串
spot_avg_price_incomplete   布尔（true = 该均价是在部分名义额上算的，当前前端未展示）
perp_avg_price_incomplete   布尔（同上）
open_basis_rate             后端占位 "0"，前端改用两条腿均价现算
price_pnl                   后端占位 "0"，从未计算过
accrued_funding             后端占位 "0"，从未计算过
borrow_interest             后端占位 "0"，从未计算过
net_pnl                     后端占位 "0"，从未计算过
```

**关于占位零（重要）**：D 的最后四项在后端是字面量 `"0"`（`store.py:2050-2053`），不是真实数值。合并表**不得**继续把它们画成 `0.00`。三类必须在视觉上可区分：

- **真值**：合约腿未实现盈亏可由 A 的 `unrealized_profit` 提供 —— 画成真数字；
- **暂无数据源**：累计资金费、借币利息本轮不接 —— 画成明确的「暂无」而不是 0；
- **拿不到**：合约均价可能确实缺失（币安 2026-07-14 移除了 UM 下单返回里的 quote/avgPrice）—— 画成破折号或等价的「未知」标记。

### 本项目与参考脚本的结构差异（不可照抄）

Human 参照的 `币安套费率策略，逐仓杠杆.js` 用的是**逐仓杠杆**（每币一个独立子账户）；本项目是**统一账户全仓**。因此：每币清算价只有合约腿有（A 的 `liquidation_price`，现有 UM 持仓表未展示，本次预览应展示）；现货/杠杆腿**没有**每币清算价，全仓只有账户级风险率；「逐仓账户价值」无对应概念。**不得用账户级数值冒充每币数值，不得为对齐脚本而虚构列。**

## Acceptance Checks

每项在 `[TASK_RESULT v2]` 的 `检查结果` 里按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`。

1. **预览入口可达且不污染生产界面**：对冲开单视图内存在一个默认关闭、带显著「假数据 · 预览」标识的区块；关闭状态下页面与改动前一致。实现报告写明 Human 打开它的确切点击路径。
2. **两个真实渲染函数逐字未变**：`renderHedgePositionsSection` 与 `renderHedgeTaskCard` 的函数体与 base 版本完全一致（预览用新增的独立函数渲染）。报告附 `git diff` 中这两个函数未出现的证明。
3. **零网络请求**：预览区块的任何交互都不发起 `fetch`/`XMLHttpRequest`；假数据是脚本内常量。
4. **合并持仓表以真实合约持仓为骨架**：一行一个合约标的；同一行内可读到该标的的真实持仓事实（方向/数量/开仓价/标记价/强平价/未实现盈亏）、对应的现货与杠杆账户资产（含全仓借款额）、以及任务卡记录（两条腿均价、价差率）。含总计行。
5. **六个场景可切换**，每个都能在预览里选到并看清：
   - (a) 正常对冲仓：真实持仓、账户资产、任务记录三者对得上；
   - (b) **真实有仓但无任务记录**：标注为无任务记录（手工单或卡已被删），成本类列留空而非填零；其中**至少一行用 1000x 倍率符号**（如 `1000PEPEUSDT`），因为这六个币当前建不了对冲任务却可能以手工仓存在；
   - (c) **有任务记录但交易所无仓**：单独区分展示，标注为交易所无持仓（可能已被强平或手工平掉）；
   - (d) **单腿敞口**：现货腿已成交、合约腿没有对应持仓 —— 这是本系统最危险的状态，必须一眼可辨；
   - (e) **数据拿不到**：合约均价缺失、`liquidation_price` 为 `"0"`、`cross_margin_borrowed` 为 `null` 同时出现的一行；
   - (f) **完全空仓**。
6. **占位零与真值可区分**：按上文「关于占位零」的三分类实现，报告说明每一列归入哪一类。
7. **任务卡预览覆盖新规则**：六种非人工暂停原因（`consecutive_submission_failure` / `rate_limited` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full`）改为自动删除后的卡片样子；人工暂停仍显示为「暂停」，两者可区分。另含一张「完成」卡的展示变体（在现有已调度/已受理计数基础上，让「计划 N 次 / 实际成功 M 次」一眼可读）—— **纯展示试画，不新增任何状态值，不改后端语义**（Human 已决定 `done` 语义本轮不处理，此项仅供其看过后决定要不要）。
8. **51169 文案逐字冻结**：`collateral_cap_full` 的中文原因必须与 `backend/hedge_open_tasks/domain.py:1315-1324` 的 `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE` **逐字一致**（`{asset}` 占位符填入即可）。该文案是 ADR-T3 契约，注释明写 `must NOT be reworded`。**严禁**替换为「保证金不足」话术 —— 平台级抵押上限是全平台共享、追加资金无效，「保证金不足」正是它要否认的假事实。若因自动删除需要补充说明，**只允许在其后追加**。
9. **前端自检通过**：`node frontend/self-check.js` 全绿，原始输出存入 `60-fake-ui-test-output.txt`。若改动了 `self-check.js`，逐条说明改了什么、为什么，并证明没有放宽既有断言。
10. **实现报告完整**：`20-fake-ui-implementation.md` 含 —— 打开预览的点击路径、六个场景各自的触发方式、每一列的数据来源归属（真实持仓 / 账户资产 / 任务记录 / 暂无数据源）、与参考脚本刻意不同之处及原因、以及你认为真实接线时最可能出问题的地方。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，把 `current_task.state` 从 `dispatched` 改为 `reported`，然后**停止**。
- 不得改动 `status.json` 的其他任何字段，不得设置 `next`，不得自行判定验收。
- 不得合并、不得推送、不得改动后端、不得接触凭证或实盘路径。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 若发现本 dispatch 的边界不足以完成目标，或发现假数据形状与真实契约存在本文件未记录的冲突：**停止并报告**，不要自行扩大范围或猜测。
- 若阅读量将显著超出上述锚点范围，按 `agents/developer-discipline.md` §5 停止并报告，不要靠整文件读硬撑 —— 本仓已因上下文耗尽后的压缩发生过跨接缝漂移。
