# 18-review-1（重跑）：2026-07-31-hedge-task-inline-log-v1

> 本轮修复扩了 schema + 写路径，按 `AGENTS.md` §8「review-2 阶段的修复若扩文件、改契约
> 或增风险，须重过 review-1」重跑。本终端**只读**，锚定固定区间，不移动 `HEAD`。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-review-1-rerun
- target_role: Reviewer（review-1，只读）
- target_model: `grok`
- provider: `xai`
- status_revision: 14
- required_skill: `agents/skills/code-reviewer.md`
- rework_count: 1（不因本次评审变化）

### 隔离披露（须在结论中原样给出）

你（`grok` / xai）担任过本 stage 计划评审 r1-r3 与首轮 review-1。跨 provider 相对实现
作者成立（xai ≠ `claude_glm` / zhipu_glm，你不是实现或修复作者）。请写明一行：
「review-1（重跑）与本 stage 计划评审 r1-r3、首轮 review-1 同为 grok/xai」。

## 本轮背景

你在首轮 review-1 给出 `ACCEPT`。随后 review-2（`codex`）判 `REWORK`，阻塞项一条：

> **R2-F1**：日志表「成交时间」列展示的是 attempt 的**创建时间**（下单前预留那一刻），
> 不是成交时间。异步成交时会误导用户判断资金何时成交。

Bookkeeper 核实后确认成立，且比表述更严重：**系统里根本没有成交时间**——attempt 表只有
`created_at_us`，leg 表只有 `dispatched_at_us` / `last_query_at_us`，交易所的
`transactTime` 从未落库。故列头是一个数据层面无法满足的断言。

随后 **Human 决定把「均价改用交易所返回值」并入同一轮修复**（原计划另立 stage），
使本轮扩出了原有的「只动读路径」边界——这是重跑你这一关的原因。

修复过程中实现者**两次**指出 Bookkeeper 的 packet 有缺口并停下回报（漏了 reconcile 写
路径、未裁定 r6 守卫与 entries 流），两处经核实全部属实，packet 已增补至 revision 13。
这些是 packet 缺陷而非实现缺陷，未额外递增 `rework_count`。

## Goal

审查 `base_sha..delivery_sha` 区间，重点在**本轮新增的写路径与资金语义变更**：

1. **`avg_price` 的资金语义契约变更是否安全**。该字段从「由 `quote / base` 算出」变为
   「库里存的交易所值优先 → 否则本地算 → 都无则 null」。请判断：
   - 三级优先级的实现（公共 helper `_resolve_avg_price`，`service.py:205`）是否正确；
   - **既有历史行是否真的不倒退**（该列为 NULL 时必须仍走本地计算，展示与修复前一致）；
   - 有没有路径会让一个**伪造的**或**不属于该腿**的价格进入展示。
2. **写路径改动是否安全**：
   - migration 是否幂等、是否可能损伤既有实盘数据；
   - 两处写入（`resolve_attempt` 与 `resolve_leg_from_query`）是否都正确落库，
     有无遗漏的第三条写入路径；
   - `_leg_final_fields` 由 6 元组扩为 7 元组，所有调用点是否都已同步。
3. **review-1 r6 守卫的拆分是否恰当**。Bookkeeper 裁定：r6 的意图是「不得用未知成交额
   做除法」（防凭空造价），而交易所返回的 `avgPrice` 不是除出来的，故拆为「NULL quote +
   无 avg → None」（保内核）与「NULL quote + 有 avg → 展示该值」（新语义）。
   **请独立判断这个裁定是否站得住**——如果你认为 r6 的原意被曲解了，现在就要说。
4. **既有资金契约是否被动到**：`cumulative_quote_amt` 的 NULL 语义、review-1 r4
   「不得用 `filled_qty × avg_price` 反推 quote」的既有决定、`_avg_price_decimal` 把
   `"0"` 映射为 `None` 的行为——三者是否都完好。
5. **Part A（时间列）** 的修法是否正确、有无遗留。
6. **是否超出 dispatch 边界**（`15-fix.dispatch.md` revision 13 的 Allowed Files 与 Stop）。

## Allowed Files

只读。不修改任何文件、不提交、不建分支。结论以 `[TASK_RESULT v2]` 文本返回给 Human。

## Inputs

- **受审区间（唯一权威）**：
  `base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`
  `delivery_sha = d85a2d3c1953d635dee59c8a1ccfccdbc40ba73b`
  用 `git diff 42de1aff..d85a2d3c` 审查。**不要**看工作树、不要移动 `HEAD`。
  该区间**含首轮交付与本轮修复的全部改动**（原 `b14f55ce` 已被取代）。
- 修复 packet（含九处清单、r6 裁定、硬约束）：同目录 `15-fix.dispatch.md`（revision 13）。
- 实现者修复自述：同目录 `16-fix-result.md`。
- **Bookkeeper 独立核验**：同目录 `17-bookkeeper-verification-fix1.md`（**必读**）。
- review-2 的 REWORK verdict 与 Bookkeeper 核实：同目录 `14-review-2-verdict.md`。
- 你的首轮 review-1 结论：同目录 `12-review-1-verdict.md`。
- 原需求与钱的展示硬约束：同目录 `00-task.md`（`status_revision: 9`）。
- 授权文件：`AGENTS.md`、`agents/roles.md` Reviewer 段、`agents/skills/code-reviewer.md`。

### 已知且**不在**本次受审范围的事项

- **订单重查间隔从 1 秒改为 100ms**：Human 2026-07-31 提出，已按其决定记为 follow-up
  （`PROJECT_STATE.md` 的 `[OPEN][DEFERRED]`），**不在本轮**。
- 「任务卡卡住」全套（F10、暂停→删除、配额收口、持仓聚合排除 `deleted`）：已移出本 stage。
- 若发现的问题属于上述两类，按 §8 **范围三分类**标注为 `pre-existing-*` 并附早于
  `base_sha` 的引入提交引用，不要按 `in-range` 阻塞交付。

## Acceptance Checks

- 逐条回答 Goal 六项，每项给出明确判断与依据（引用 `文件:行号` 或 diff 位置）。
- 每条发现按 §8 标注**范围三分类**；`pre-existing-*` 须附引入提交引用。
- 返回 `[TASK_RESULT v2]`，含 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修复
  要求放在同一次输出的正文里。本 stage 已有三轮评审因正文未随回执交出而无法直接封存。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不提交、不移动 `HEAD`。
- 不做实现、不写修复代码、不启动其他终端。
- 不重评已移出本 stage 的工作，不把 follow-up 当作本次交付缺陷。
- 不替 Human 做合并、部署、实盘决策。`ACCEPT` 不等于合并授权。
