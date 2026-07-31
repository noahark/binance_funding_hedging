# 11-review-1：2026-07-31-hedge-task-inline-log-v1（review-1 dispatch packet）

> `AGENTS.md` §8：`HIGH_RISK` 交付需 review-1 + review-2。review-1 查代码、契约、测试、
> 接缝。本终端**只读**，锚定固定的 `base_sha..delivery_sha`，不移动 `HEAD`、不看工作树。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1-review-1
- target_role: Reviewer（review-1，只读）
- target_model: `grok`
- provider: `xai`
- status_revision: 10
- required_skill: `agents/skills/code-reviewer.md`

### 隔离状态（须在结论中原样披露）

你（`grok` / xai）同时担任过本 stage 计划评审的 round 1-3。跨 provider 隔离成立
（xai ≠ 实现作者 `claude_glm` / zhipu_glm，你不是实现或修复作者），但
`agents/roles.md` 要求披露设计参与。请在 `[TASK_RESULT v2]` 中写明一行：
「review-1 与本 stage 计划评审 r1-r3 同为 grok/xai，已参与计划批准」。

补充事实：**最终批准该 packet 的是 DeepSeek（r4，ACCEPT）**，不是你——你 r3 的结论是
`REWORK`，其三条阻塞已被 Bookkeeper 修订落实后由 DeepSeek 独立确认。终审 review-2
（`codex` / openai）完全独立、未参与任何设计。

## Goal

审查 `base_sha..delivery_sha` 区间内的实现交付，判断代码、契约、测试与接缝是否成立。
重点：

1. **钱的展示口径是否真的守住**（本 stage 的 `HIGH_RISK` 理由就在这里）：
   - 均价/数量是否全程原样透传，有无任何二次加工路径漏网；
   - 未受理腿的门控（按 `order_id` 判空 → 订单号/均价/数量三格 `—`）是否有绕过路径，
     例如 `order_id` 为 `0`、`"0"`、`false` 等假值时的行为；
   - 错误原因回退链有没有可能渲染出前端编造的中文业务句；
   - 有没有 HTML 注入面（这些值最终进 `innerHTML`）。
2. **`task_id` 读路径的契约与接缝**：
   - 早返回分支是否真的没有触碰任何写路径；
   - `task_id` 未做存在性/格式校验（任意字符串返回空 `attempts`），是否可接受；
   - `logs`/`entries` 在该模式下为空、游标为 `None`，对既有消费方是否安全；
   - 与既有两套游标（legacy `cursor/limit`、`entries_cursor/entries_limit`）是否真的
     不共用，会不会重演 amendment 17 修掉的 R4 缺陷。
3. **测试是否真的锁住了行为**，而不是只覆盖了 happy path：
   - self-check 86a/86b 与新增的两个 pytest 用例，断言强度是否够；
   - 有没有「测试通过但真实数据形态不会出现」的夹具（见下 O-A）。
4. **接缝与既有代码的相互影响**：
   - `HEDGE_PAIR_OUTCOME_BADGE` 的 `'warning'` → `'warn'` 一行修复，是否影响既有
     attempt 时间线卡的展示（该常量是共用的）;
   - `attempt_to_doc` 新增三个字段，对既有消费方是否安全（该投影是冻结文档形状）。
5. **是否有超出 dispatch 边界的改动**。

## Allowed Files

只读。不修改任何文件、不提交、不建分支。结论以 `[TASK_RESULT v2]` 文本返回给 Human，
由 Human 转交 Bookkeeper 落盘。

## Inputs

- **受审区间（唯一权威）**：
  `base_sha = 42de1aff364e7c979d2fbb5dc56f1dec65287cc7`
  `delivery_sha = b14f55ce8c264635860bd5b54d61229b17bd9faa`
  用 `git diff 42de1aff..b14f55ce` 审查。**不要**看工作树、不要移动 `HEAD`。
- 需求与验收标准：`reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/00-task.md`
  （`status_revision: 9`，计划评审已 ACCEPT）。
- 实现者自述与自测证据：同目录 `09-delivery.md`。
- **Bookkeeper 核验记录与观察项**：同目录 `10-bookkeeper-verification.md`（**必读**，
  含独立复跑结果与五条观察项 O-A..O-E）。
- 计划评审记录（背景）：同目录 `07-`（你的 r3）、`08-`（DeepSeek 的 r4 ACCEPT）。
- 授权文件：`AGENTS.md`（§3 安全内核、§7 结果协议、§8 评审规则）、
  `agents/roles.md` Reviewer 段、`agents/skills/code-reviewer.md`。

### Bookkeeper 已发现、请你独立判断的观察项

- **O-A**：`09-delivery.md` 的 AC2 写「均价原样透传含尾零 `120.70000000`」。测试有效
  （证明前端不做二次加工），但那是夹具的手写值——**真实数据不可能带尾零**，后端
  `fmt_decimal`（`domain.py:1250-1252`）上线前已 `rstrip("0")`。属描述不精确。
  请判断这是否影响测试的有效性。
- **O-B**：`task_id` 分支是 1 + N 次查询（每 attempt 一次 `list_legs_for_attempt`），
  而 `target_n` 无上限。请判断是否需要现在改成 join。
- **O-C**：`task_id` 模式下 `logs`/`entries` 为空（交付声明为可推翻项）。
- **O-D**：`target_n` 取不到时进展列显示 `4/`（`findHedgeTask` 回退空串）。
- **O-E**：均价列的 `—` 有三种来源（未受理 / 受理但成交额未知 / 无数据），单看该列
  无法区分；数量列可区分。

### 已知且**不在**本次受审范围的事项（不要作为交付缺陷提出）

- 均价由后端本地 `quote / base` 现算，而非用交易所返回的 `avgPrice`
  （`hedge_open_leg` 无该列）。Human 2026-07-31 已决定改用交易所值，但需要 schema +
  写路径改动，**超出本 stage「只动读路径」边界**，已记为跨 stage follow-up
  （`PROJECT_STATE.md` 的 `[OPEN][MONEY-ACCURACY]`）。
- 「任务卡卡住」全套（F10、暂停→删除、配额收口、持仓聚合排除 `deleted`）已由 Human
  移出本 stage，见 `06-scope-reduction.md`。
- 若你发现的问题属于上述两类，按 `AGENTS.md` §8 的**范围三分类**标注为
  `pre-existing-independent` 或 `pre-existing-release-critical`，并附早于 `base_sha`
  的引入提交引用（`git blame` / `git log -L`），不要按 `in-range` 阻塞交付。

## Acceptance Checks

- 逐条回答上述 Goal 五项，每项给出明确判断与依据（引用 `文件:行号` 或 diff 位置）。
- 每条发现按 `AGENTS.md` §8 标注**范围三分类**（`in-range` /
  `pre-existing-independent` / `pre-existing-release-critical`），`pre-existing-*`
  须附早于 `base_sha` 的引入提交引用。
- 返回 `[TASK_RESULT v2]`（格式见 `AGENTS.md` §7），含 `评审结论: ACCEPT | REWORK`、
  `问题记录`、`修复要求`。
- **`问题记录` / `修复要求` 不要写 `none`**：写 `inline-full-text` 并把发现清单与修复
  要求放在同一次输出的正文里。本 stage 的计划评审有两轮因正文未随回执交出而无法封存，
  白跑一趟——请勿重演。
- 若判 `REWORK`，修复要求须可执行（具体到文件、行为、判据）。

## Stop

- 只读：不改代码、不改 packet、不改 `status.json`、不建分支、不提交、不移动 `HEAD`。
- 不做实现、不写修复代码、不启动其他终端。
- 不评审已移出本 stage 的工作，不把 follow-up 当作本次交付缺陷。
- 不替 Human 做合并、部署、实盘决策。`ACCEPT` 不等于合并授权。
