# 13-review-2：2026-07-31-hedge-task-inline-log-v1（review-2 dispatch packet）

> `AGENTS.md` §8：review-2 查**需求、实际效果、证据、运营风险、发布就绪**——不是再做
> 一遍代码审查（review-1 已 `ACCEPT`）。本终端**只读**，锚定固定的
> `base_sha..delivery_sha`，不移动 `HEAD`、不看工作树。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-review-2
- target_role: Reviewer（review-2 终审，只读）
- target_model: `codex`
- provider: `openai`
- status_revision: 11
- required_skill: `agents/skills/reality-checker.md`

### 隔离状态

你（`codex` / openai）**未参与本 stage 的任何设计、计划评审或实现**，是完全独立的终审方。
实现作者 `claude_glm`（zhipu_glm）、review-1 与计划评审 r1-r3 `grok`（xai）、计划评审 r4
`deepseek`、bookkeeper `opus5`（anthropic）——与你均不同 provider。无需披露。

## 用户要的是什么

Human 的原话是要**开单任务卡内嵌日志**：展开任务卡后，能看到这个任务每一次尝试的战绩
——什么时候成交的、订单号多少、成交均价多少、成交了多少个、失败的话为什么失败。目的是
**判断钱的去向**。

本 stage 的范围被 Human 显式收窄过：原本还包含「任务卡卡住」的修复（F10、自动暂停改
自动删除等），2026-07-31 被移出，另立 stage（`06-scope-reduction.md`）。**不要**把那些
当作本次缺失。

## Goal

1. **实际效果：用户展开日志后真的能看清钱吗？**

   这是本轮最重要的问题。Bookkeeper 已把后端真实投影 + 前端渲染逻辑串起来跑过一遍，
   实际长这样（`—` 表示该格显示破折号）：

   | 进展 | 状态 | 合约均价 | 现货均价 | 合约数量 | 现货数量 |
   |---|---|---|---|---|---|
   | 4/10 | 进行中 | — | — | — | — |
   | 3/10 | 已确认失败 | — | — | — | — |
   | 2/10 | 单腿成交 | — | `0.0123` | — | `2000` |
   | 1/10 | 已受理 | **—** | `0.0123` | **2000** | `2000` |
   | 0/10 | 已受理 | `0.01241` | `0.0123` | `2000` | `2000` |

   请重点判断：

   - **`1/10` 那一行**：合约腿已受理、成交了 2000 个，但**合约均价是空的**。成因是
     币安 2026-07-14 从 UM 下单返回里移除了成交额/均价，靠事后 GET 补，补不到就是 `NULL`
     （`service.py:224` 用 `cumulative_quote_amt / cumulative_base_qty` 现算，quote 为
     `NULL` 则 avg 为 `None`）。**这种「买到了但不知道多少钱买的」在真实使用中有多常见？
     它是否让这个功能达不到「判断钱的去向」的目的？**
   - **`—` 的三种来源在均价列无法区分**（O-E）：「该腿未受理（钱没动）」「受理了但成交额
     未知（钱动了、价格未知）」「无数据」都渲染成 `—`。数量列可以区分，但需要用户自己
     对照。这个歧义在真实操作中会不会导致误判？值不值得在本轮修？
   - 「已受理」这个状态文案（而非 fake 原型的「已成交」）是否会造成另一种误读？
     Human 已确认采用「已受理」。

2. **证据是否可信**：`09-delivery.md` 的自测证据与 `10-bookkeeper-verification.md` 的
   独立复跑（`1104 passed`、self-check 全过、fake 零残留、`store.py` 未改）是否足以支撑
   验收结论。注意 Bookkeeper 已指出交付措辞的一处不精确（O-A：「均价原样透传含尾零
   `120.70000000`」用的是夹具值，真实数据经 `fmt_decimal` 已去尾零，界面上看不到尾零）
   ——请判断这是否影响证据的可信度。

3. **运营风险**：这是纯读路径改动（新增一个可选查询参数 + 三个字段投影 + 前端表格），
   不碰下单、状态机、结算。但请判断：
   - `task_id` 模式一次返回全部 attempt（不分页），`target_n` 无上限，1+N 次查询（O-B）
     ——真实使用中会不会拖慢界面或打爆响应体？现有 `BODY_MAX_BYTES = 16384` 是否构成限制？
   - 展开日志随既有 60s tick 重取，未新增定时器——刷新负担是否可接受？
   - 有无对既有功能的回归风险（`HEDGE_PAIR_OUTCOME_BADGE` 是共用常量，
     `'warning'→'warn'` 的一行修复会连带影响既有 attempt 时间线卡的徽标）。

4. **发布就绪**：这次交付能不能合并到 `main`？如果能，还有什么是 Human 在合并前必须
   知道的。如果不能，缺什么。

5. **遗漏**：以完全独立的视角看，前面四轮计划评审 + review-1 + Bookkeeper 都没提到、
   但会影响用户判断钱的去向的问题。

## Allowed Files

只读。不修改任何文件、不提交、不建分支。结论以 `[TASK_RESULT v2]` 文本返回给 Human，
由 Human 转交 Bookkeeper 落盘。

## Inputs

- **受审区间（唯一权威）**：
  `base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`
  `delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`
  用 `git diff 42de1aff..b14f55ce` 审查。**不要**看工作树、不要移动 `HEAD`。
- 需求与验收标准：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`
  （`status_revision: 9`）。
- 实现者自述与自测证据：同目录 `09-delivery.md`。
- Bookkeeper 独立核验（含五条观察项 O-A..O-E）：同目录 `10-bookkeeper-verification.md`。
- review-1 结论（`ACCEPT`，含对 O-A..O-E 的裁定）：同目录 `12-review-1-verdict.md`。
- 范围收窄说明：同目录 `06-scope-reduction.md`。
- 计划评审记录：同目录 `07-`（grok r3 REWORK）、`08-`（DeepSeek r4 ACCEPT）。
- 授权文件：`AGENTS.md`（§3 安全内核、§7 结果协议、§8 评审规则、§9 阶段完成）、
  `agents/roles.md` Reviewer 段、`agents/skills/reality-checker.md`。
- 跨 stage 风险台账：`PROJECT_STATE.md`。

### 已知且**不在**本次受审范围的事项（不要作为交付缺陷阻塞）

- **均价应取交易所返回值而非本地计算**：`live_hedge_executor.py:116` 已解析币安
  `avgPrice`，但 `hedge_open_leg` 表无该列（`store.py:85-99`），值被丢弃。Human
  2026-07-31 已决定改用交易所值，但需要 schema + 写路径改动，**超出本 stage「只动读
  路径」的边界**，已记为 `PROJECT_STATE.md` 的 `[OPEN][MONEY-ACCURACY]`。
  → 你可以（且应该）评估它对**本次交付实际价值**的影响，但不要把它当作本次交付的缺陷。
- 「任务卡卡住」全套（F10、暂停→删除、配额收口、持仓聚合排除 `deleted`）：已移出。
- 若发现的问题属于上述两类，按 `AGENTS.md` §8 的**范围三分类**标注为
  `pre-existing-independent` 或 `pre-existing-release-critical`，并附早于 `base_sha`
  的引入提交引用（`git blame` / `git log -L`）。

## Acceptance Checks

- 逐条回答上述 Goal 五项，每项给出明确判断与依据。
- 每条发现按 `AGENTS.md` §8 标注**范围三分类**；`pre-existing-*` 须附早于 `base_sha`
  的引入提交引用。
- 返回 `[TASK_RESULT v2]`（格式见 `AGENTS.md` §7），含 `评审结论: ACCEPT | REWORK`、
  `问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修复
  要求放在同一次输出的正文里。本 stage 的评审有两轮因正文未随回执交出而无法封存。
- 用中文写结论。Human 会读这份结论做合并决定，**不要交原始 diff、JSON 或技术审查过程**
  给他——说清楚：做出来的东西实际效果如何、有什么风险、能不能合并、合并前他必须知道什么。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交、不移动 `HEAD`。
- 不做实现、不写修复代码、不启动其他终端。
- 不重做 review-1 的代码审查（已 `ACCEPT`），除非你发现它漏判了影响资金判断的问题。
- 不替 Human 做合并、部署、实盘决策。**`ACCEPT` 不等于合并授权**（`AGENTS.md` §9）。
