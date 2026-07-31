# 20-review-2（复审）：2026-07-31-hedge-task-inline-log-v1

> `AGENTS.md` §8：review-2 查**需求、实际效果、证据、运营风险、发布就绪**。
> 本终端**只读**，锚定固定区间，不移动 `HEAD`、不看工作树。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-review-2-rerun
- target_role: Reviewer（review-2 终审复审，只读）
- target_model: `codex`
- provider: `openai`
- status_revision: 15
- required_skill: `agents/skills/reality-checker.md`
- rework_count: 1（不因本次评审变化）

### 隔离状态

你（`codex` / openai）与实现作者 `claude_glm`（zhipu_glm）、review-1 及计划评审 r1-r3
`grok`（xai）、计划评审 r4 `deepseek`、bookkeeper `opus5`（anthropic）均不同 provider，
未参与任何设计或实现。无需披露。

## 你上一轮说了什么

你在首轮 review-2 判 `REWORK`，提了两件事：

1. **R2-F1（阻塞）**：日志表「成交时间」列展示的是尝试创建时间，异步成交时会误导用户
   判断资金何时成交。
2. **发布就绪 fail**：「现有功能能定位订单、数量和失败原因；但**合约均价缺失时仍无法
   完整判断成本**。该均价问题早于本交付存在，且会阻塞发布前的人类风险决定。」

**两件事都已处理，本轮请复审处理得对不对、够不够。**

## 这一轮做了什么

### Part A —— 回应你的 R2-F1

Bookkeeper 核实后确认成立，且发现根子更深：**系统里根本没有成交时间**——attempt 表只有
`created_at_us`，leg 表只有 `dispatched_at_us` / `last_query_at_us`，交易所的
`transactTime` 从未落库。列头是一个数据层面无法满足的断言。

修法：列头改为**「尝试时间」**，并去掉原本的 `order_id` 门控（该门控是为「成交时间」这个
语义设的；改名后每一行都真实存在一个尝试时间，包括失败行）。**未新增成交时间戳**——那
需要 schema + 写路径且属另一件事。

### Part B —— 回应你的「发布就绪 fail」

Human 2026-07-31 决定**把均价数据源问题并入本轮**（原计划另立 stage）。

- 币安返回的权威 `avgPrice` 执行器早已解析，但 `hedge_open_leg` 无该列，值到门口被丢弃。
- 本轮加了 `avg_price` 列，**两条写路径**都落库（结算路径 + reconcile 查询路径——后者
  是合约腿数据到达的唯一途径），展示时**优先用交易所值**，其次退回本地
  `quote / base` 计算，都没有才是 null。
- 三处腿投影（attempts 流与 entries 流）共用同一个 helper，**结构上保证两流不会显示
  不同的价格**。

## Goal

1. **你上一轮的两条是否真的闭合？**
   - R2-F1：列头改名 + 去门控，是否足以消除「误判资金何时成交」的风险？还是说
     用户仍会把「尝试时间」当成成交时间？有没有更该做的（例如列头加注解）？
   - 发布就绪：**合约均价现在真的能看到了吗？** 请判断实际效果——币安的 UM 下单响应
     不带均价，只能靠事后订单详情 GET 补；补到之前该列仍是破折号。这样够不够支撑
     「判断成本」这个目的？你上一轮的 fail 判断现在可以翻转吗？
2. **新引入的资金语义变更是否可接受**：`avg_price` 从「本地算出」变为「交易所值优先」。
   review-1（重跑）已判安全。请从**实际效果**角度判断：用户看到的价格会不会因此在
   某些场景下与他的实际成本对不上（例如手续费、部分成交、交易所口径差异）。
3. **历史数据的表现**：本次改动前写入的行该列为 NULL，会退回本地计算。请判断
   **同一张日志表里新旧行并存**（新行用交易所值、旧行用本地算值）会不会造成困惑或误读。
4. **运营风险**：schema 迁移对既有实盘库是否安全；写路径多记一列是否引入新的失败面。
5. **发布就绪**：这次交付能不能合并到 `main`？合并前 Human 必须知道什么。
6. **遗漏**：以独立视角看，还有什么会影响用户判断钱的去向。

### 需要你独立裁定的一条观察（review-1 重跑提出，Bookkeeper 已精确化）

**O1**：`resolve_leg_from_query` 写 `avg_price` / `quote_amt` 时**没有 `COALESCE`**，
后一次查询若带回 `None` 会覆盖先前已拿到的值。

- 触发需要「某次查询有均价但无成交额」，而当前币安**订单详情 GET 同时返回二者**
  （2026-07-14 移除的只是 UM 下单响应的字段），故**当前不可达**。
- review-1 定性为「非本轮引入」；Bookkeeper 精确化为「**本轮引入**（该列的写入是新加的）、
  沿用既有 `quote_amt` 的同一模式、当前不可达」。
- 若币安将来也从订单详情 GET 移除成交额，它即变为可达，届时应改为「不用未知覆盖已知」。

**请判断：这个残余风险是否需要在合并前处理，还是可以作为已知项记录后合并。**

## Allowed Files

只读。不修改任何文件、不提交、不建分支。结论以 `[TASK_RESULT v2]` 文本返回给 Human。

## Inputs

- **受审区间（唯一权威）**：
  `base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`
  `delivery_sha = d85a2d3c1953d635dee59c8a1ccfccdbc40ba73b`
  用 `git diff 42de1aff..d85a2d3c` 审查。**不要**看工作树、不要移动 `HEAD`。
  该区间含首轮交付与本轮修复的全部改动。
- 你上一轮的 verdict 与 Bookkeeper 核实：同目录 `14-review-2-verdict.md`（**必读**）。
- 修复 packet（含九处清单、r6 裁定、硬约束）：同目录 `15-fix.dispatch.md`（revision 13）。
- 实现者修复自述：同目录 `16-fix-result.md`。
- Bookkeeper 对修复的独立核验：同目录 `17-bookkeeper-verification-fix1.md`。
- review-1（重跑）的 `ACCEPT` 与两条观察：同目录 `19-review-1-rerun-verdict.md`。
- 原需求与钱的展示硬约束：同目录 `00-task.md`（`status_revision: 9`）。
- 首轮的核验与评审：同目录 `10-`、`12-`。
- 跨 stage 风险台账：`PROJECT_STATE.md`。
- 授权文件：`AGENTS.md`、`agents/roles.md` Reviewer 段、`agents/skills/reality-checker.md`。

### 已知且**不在**本次受审范围的事项

- **订单重查间隔 1 秒 → 100ms**：Human 2026-07-31 提出，已按其决定记为 follow-up
  （`PROJECT_STATE.md` 的 `[OPEN][DEFERRED]`，附已查明的事实与风险）。不在本轮。
- 「任务卡卡住」全套（F10、暂停→删除、配额收口、持仓聚合排除 `deleted`）：已移出本 stage。
- 若发现的问题属于上述两类，按 §8 **范围三分类**标注为 `pre-existing-*` 并附早于
  `base_sha` 的引入提交引用。

## Acceptance Checks

- 逐条回答 Goal 六项 + O1 裁定，每项给出明确判断与依据。
- 每条发现按 §8 标注**范围三分类**；`pre-existing-*` 须附引入提交引用。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修复
  要求放在同一次输出的正文里。本 stage 已有三轮评审因正文未随回执交出而无法直接封存。
- 用中文写结论。Human 会读它做合并决定，**不要交原始 diff、JSON 或技术审查过程**——
  说清楚：东西做出来实际效果如何、有什么风险、能不能合并、合并前他必须知道什么。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不提交、不移动 `HEAD`。
- 不做实现、不写修复代码、不启动其他终端。
- 不重做 review-1 的代码审查（重跑已 `ACCEPT`），除非你发现它漏判了影响资金判断的问题。
- 不替 Human 做合并、部署、实盘决策。**`ACCEPT` 不等于合并授权**（`AGENTS.md` §9）。
