# 02-scope-decisions —— Human 对本 stage 的范围与路由决策

- stage: `2026-07-31-hedge-task-lifecycle-v1`
- 记录人：opus5（本 stage bookkeeper），2026-07-31
- 依据：Human 在 intake 会话中对 `01-intake-brief.md` 四个决策点的答复，及随后追加的两轮修订
- 本文件是 dispatch 的上游依据；与 `01-intake-brief.md` 冲突时以本文件为准（brief 写于决策之前）

## 1. 已定决策

| # | 决策点 | Human 的选择 |
|---|---|---|
| D1 | 四项待办的排期 | **四项一轮全做**（在 ① 由小修变为重做后再次确认，见 §3） |
| D2 | `done` 的语义歧义（「次数用尽」vs「全部成功」） | **暂不处理**，保持现状，本轮不碰 |
| D3 | 模型分配 | **轮换，review-1 仍用 grok**：计划评审换 `deepseek`；实现 `claude_glm`；review-1 `grok`（Kimi 额度不可用，Human 批准的备选）；review-2 `codex` |
| D4 | 动状态机前先做只读真机验证 | **跳过**，直接进方案评审 |
| D5 | ① 的做法（Human 主动提出的修订） | **改为以 UM 真实持仓为基准**，匹配现货/杠杆账户余额与任务卡成交记录；参照 `币安套费率策略，逐仓杠杆.js` 的展示思路 |
| D6 | 持仓展示怎么组织 | **合并成一张表**，以真实合约持仓为骨架，现有「UM 持仓」表并入 |
| D7 | 真实持仓与任务记录对不上时 | **都显示，标清楚**；不自动执行任何动作，只展示 |
| D8 | 是否先做 fake UI | **做**，范围 = ①合并持仓表 + ②卡片展示；**可切多种场景**，不是静态一屏 |

## 2. D5 的来源与已核实事实

Human 参照 `币安套费率策略，逐仓杠杆.js`（仓库根目录，3447 行，2023 年的 FMZ 策略脚本）。该脚本的展示结构：

| 脚本中的表 | 数据来源 | 函数 |
|---|---|---|
| 合约持仓 | 交易所真实持仓 `GetPosition` | `showBinanceTable` / `getBinanceContractHoldTableInfo`（:1767/:1778） |
| 杠杆持仓 | 逐仓杠杆账户真实资产 | `showMarginAccount` / `getBinanceMarginAccountTableInfo`（:3120/:3133） |
| 开单信息 | 本地开单记录 | `showHoldPositionsInfo` / `getHoldPositionsTableInfo`（:2999/:3019） |

核心思路：**前两张表以交易所为权威，本地记录只用于补充成本/价差/费率/利息**；并用真实数据互相核对（`checkSpotAndFutureHold`，:2043 —— 合约有仓但逐仓借币与利息均为 0 则判定被强平）。

本项目现状（已逐处核实）：

- **真实合约持仓已在系统内**：`private_client.fetch_um_positions()` 取 `GET /papi/v1/um/positionRisk`，经 `snapshot.assemble_private_account`（`snapshot.py:1152-1168`）产出 `private_account.um_positions[]`，字段 `symbol` / `position_side` / `notional_usdt` / `position_amt` / `entry_price` / `mark_price` / `unrealized_profit` / `liquidation_price`。前端已渲染（`index.html:2729-2764`），但**未展示 `liquidation_price`**。
- **真实现货/杠杆资产已在系统内**：`balances_unified[]`（含每资产 `cross_margin_borrowed` 全仓借款）与 `balances_spot[]`，同一个 `private_account` 块。
- **本地记账表独立存在**：`GET /api/hedge-open-positions` → `store.aggregate_positions()`（`store.py:1934+`），前端 `renderHedgePositionsSection`（`index.html:4407-4470`）。
- **三份数据前端已同时在手**（`state.snapshot.private_account` 与 `state.hedgePositions`），合并**不需要新增任何交易所请求**，不增加限频权重。

### 2.1 本项目与该脚本的结构性差异（不可照抄的部分）

脚本用**逐仓杠杆**（每币一个独立子账户），本项目用**统一账户全仓**（PM），因此：

| 脚本字段 | 本项目 |
|---|---|
| 每币清算价 | 合约腿有（`liquidation_price`，现未展示）；现货/杠杆腿**没有**，全仓只有账户级风险率（`pm_account.uniMMR`） |
| 每币借入/利息 | 借入有（`cross_margin_borrowed`，按资产）；利息目前按资产查历史接口，**未实时挂在行上** |
| 逐仓账户价值 / 逐仓未实现盈亏 | **无对应概念** |

Bookkeeper 立场（供方案评审裁定）：能拿到的照做，拿不到的不编造，不用账户级数值冒充每币数值。

### 2.2 现有持仓表的四列是写死的占位零

`store.aggregate_positions` 返回的 `price_pnl` / `accrued_funding` / `borrow_interest` / `net_pnl` 均为字面量 `"0"`（`store.py:2050-2053`），`service.get_positions`（`service.py:924-925`）不做加工，前端逐字渲染为 `0.00`。`open_basis_rate` 同为 `"0"`，但前端改用两条腿均价现算（`index.html:4448` 注释已说明）。

影响：接入真实持仓后，未实现盈亏可由 `um_positions[].unrealized_profit` 提供真值；资金费与借币利息仍无数据源，本轮不接。fake UI 必须把「真值 / 暂无数据源 / 后续接入」三种情况分开呈现，不得沿用占位零。

关联 `PROJECT_STATE.md` 的 `[OPEN][RESIDUAL]` money-zero tripwire（DEC-2026-07-30-001）。

### 2.3 符号匹配风险

`hedge_open_task.coin` 存的是完整 USDT 本位符号（如 `BTCUSDT`，`domain.py:785`/`:1104` 校验），与 `um_positions[].symbol` 多数情况可直接对齐。但 **1000x 倍率前缀**的六个合约（BONK/FLOKI/LUNC/PEPE/SHIB/XEC）UM 符号为 `1000PEPEUSDT` 而现货为 `PEPEUSDT`，属已记录的 follow-up（`normalize.py` 未做前缀剥离），当前这六个币无法建对冲任务，但**可能以手工仓形式出现在真实 UM 持仓里**。fake UI 需覆盖该场景（作为「无任务记录」行）。

## 3. D1 的两次确认

Human 首次选择「四项一轮全做」时，① 的认知是「改一个 `WHERE` 条件」。D5 提出后 ① 升级为「持仓表换数据源重做」，Bookkeeper 就前提变化重新征询排期，Human **再次选择四项一轮全做**。按 `AGENTS.md` §10，此为已定决策，不再劝阻。

已向 Human 明示的风险，留档不粉饰：两块高风险改动（持仓表换源 + 任务状态机）共用同一交付范围的三次返工额度。

## 4. 由 D1 与 D8 推出的执行顺序

fake UI 不新开 stage（`PROJECT_STATE.md` 已记 ~39 个完成 stage 目录积压，vs §9.5），作为本 stage 内的**第一个独立交付物**：

1. `fake-ui-positions-and-cards-v1` —— 纯前端假数据原型，`LOW_RISK` 单评审（理由见该 dispatch）
2. Human 看过并给出展示形状的反馈
3. Planner 出四项的完整实现方案（fake UI 的验收结果是其输入之一）
4. 跨 provider 只读计划评审（`deepseek`，§8 HIGH_RISK 要求）
5. 真实实现（`claude_glm`）→ review-1（`grok`）→ review-2（`codex`）

`rework_count` 按 `AGENTS.md` §8 绑定交付物：fake UI 与真实实现是两个交付物，各自计数，fake UI 的返工不消耗真实实现的额度。

## 5. 前一 stage 带来的、对本 stage 直接适用的两条教训

1. **不要只读代码字面就下结论，要验证外部真实行为。** 上一 stage 因此耗掉一次返工额度。本次尤其适用：fake 的假数据必须照真实字段的取值形状造（`liquidation_price` 无值时币安返回字符串 `"0"` 而非空；数量是带多位小数的字符串；合约均价因币安 2026-07-14 移除 POST 返回字段而可能确实拿不到），不得编造「好看的数字」。
2. **fake → 真实接线存在已发生过的漂移成本。** `hedge-open-live-v1` round-1 抓修 3 次跨 seam 漂移（R4-001/F-001/F-007）。降低办法即上一条：假数据字段名与形状与真实契约一致。
