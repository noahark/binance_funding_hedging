# 00-task：2026-07-31-hedge-task-inline-log-v1（实现 dispatch packet）

> 定稿状态：**revision 9 —— 计划评审已 `ACCEPT`，本 packet 可实现**。
> 计划评审 round 4（DeepSeek Pro / deepseek，全新独立方）返回 `ACCEPT`，确认 grok
> round 3 的六条修订已全部正确落实、Bookkeeper 三项追加判断成立、无新阻塞问题；
> 其两条非阻塞观察（O-1 优先扩 `attempt_to_doc`、O-2 `null` 需显式分支）已并入本文。
> verdict 见 `08-plan-review-r4-verdict.md`。
> 范围：本 stage 只做开单任务日志，「任务卡卡住」相关已全部移出（`06-scope-reduction.md`）。
> 起草者 claude_glm，定稿者 opus5。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1
- target_role: Implementer
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: 9
- required_skill: `agents/skills/senior-developer.md`
- 风险分级: **HIGH_RISK**（保持不变。理由：本 stage 向用户展示成交价格、成交数量与
  订单号——用户据此判断钱的去向；展示错误等同于错误的账务信息。且 §8 的 `LOW_RISK`
  只适用于「文档或机械性改动」，本 stage 是新功能 + 可能的读接口参数变更，不符合。
  仍走 review-1 + review-2。）

## Goal

1. **任务卡内嵌日志（真实数据）**：每个开单任务卡在「暂停/启动」按钮行下增加单个
   toggle 按钮（展开日志 ↔ 收起日志），展开后任务卡向下伸出该任务的尝试日志表格。
   列固定为：进展 / 状态 / 成交时间 / 合约订单号 / 现货订单号 / 合约均价 / 现货均价 /
   合约数量 / 现货数量 / 错误原因。倒序（最新在上，进行中那行数据可为空）；失败与
   单腿成交行必须展示错误原因；订单号 / 均价 / 数量按该腿是否受理填充。视觉与列语义
   以 fake 原型（commit `5871791`，`frontend/index.html:4229` 起的
   `renderHedgeTaskCardFake`）为准。
   - **「进展」列 = `attempt_seq / target_n`**（该行那次尝试的序号 / 该任务计划次数），
     与 fake 原型的 `n/10` 一致。`attempt_seq` 已在 `attempt_to_doc` 投影中
     （`service.py:256`）。**不得用 `scheduled_attempt_count`** ——那是任务级累计计数器，
     用它填每一行会让所有行数字相同。任务卡摘要行的 `countersLine` 继续用它，不受影响。
   - 数据必须覆盖该任务的**全部**尝试，不得是全局分页里恰好落在当前页的切片。
   - 展开状态记入 `state.hedgeLogExpanded`，跨自动刷新保持。
   - **绑定要改**：`bindHedgeTaskLogToggles` 当前只在 `showFakePreview` 时绑定
     （`index.html:4159`），真卡必须改绑定。
2. **任务卡展示 `#task-id`**：**已实现**（`index.html:4207` 真卡卡头已有）。本条降级为
   回归验收，不作为新工作；若已满足，AC8 只需给出证据。
3. **移除 fake 数据**：真实版落地后删除 `renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID`
   及其仅服务于假卡的样式/绑定分支；不得留下未被引用的死代码。

### 【钱的展示口径 · 硬约束】

日志表格展示的是用户判断资金去向的依据，以下不可协商：

- **数值原样透传**：均价、数量直接取后端 attempt/leg 的原始字符串，前端不做四舍五入、
  不做单位换算、不做精度截断。后端已按币种原生精度存储。
  - 金额格**只能用 `hedgeText`**（`index.html:3602`，原样透传）。
    **禁用 `formatHedgeDecimal`**（`:3631`，会去尾 0）与 `hedgeNum` 渲染金额格。
- **未受理的腿显示 `—`，绝不显示 `0`**。`0` 会被读成「成交了 0 个」，而事实是「这条腿
  根本没被受理」——两者含义完全不同。这条踩过坑（51061 错误码曾被映射成 `0`）。
  - **注意后端已经在发 `"0"`**：`_leg_to_doc`（`service.py:214-229`）里
    `base = Decimal(leg.get("cumulative_base_qty") or "0")` → 未受理腿的
    `cumulative_base_qty` 是字符串 `"0"` 而不是 `null`；`hedgeText("0")` 只把
    null/undefined/`''` 降为 `—`，**会原样显示 `0`**。
  - **门控判据（钉死）**：该腿 `order_id` 缺失 / null → 该行**订单号、均价、数量三个
    单元格一律 `—`**，即使 `cumulative_base_qty === "0"`、即使 `avg_price` 缺失。
    不得改后端投影来绕过（那是写路径以外的读路径改动，见 Stop）。
- **失败与单腿成交行的错误原因**：
  - 主字段 = `error_reason_zh`。**但它当前不在 `attempt_to_doc` 的投影里**
    （`service.py:239-265` 只投 `pair_outcome` / `spot` / `perp` / `residual` / `ts` 等），
    须在**读路径**上补投。**优先做法：扩 `attempt_to_doc` 加字段**
    （`error_reason_zh` / `error_code` / `error_category`）——内嵌表消费的就是 `attempts`
    数组，同源最省。改用 `entries` 字段是次选，仅在扩投影不可行时采用并说明理由。
    （计划评审 r4 观察 O-1）
  - **且它经常是 `NULL`**：`store.py:1085-1095` 对非 fatal 的 rollup 写
    `error_reason_zh = None`（普通确认失败与单腿都走这条）。因此「凡失败/单腿行必有
    非空中文原因」在只读范围内**做不到**，原约束已按此收窄。
  - **回退链（钉死，禁止前端编造中文业务句）**：
    `error_reason_zh` → 没有则展示 `error_code` / `error_category`（机器字段原样）→
    仍没有则固定占位 **「原因未记录」**。不得为了填满这一列去改结算或写路径。
- **单腿成交行必须视觉可辨**，因为它代表**未对冲的裸敞口**。

### 【状态映射 · 冻结表】

日志行的状态文案与徽标一律按此表，不得自创：

| `pair_outcome` | 中文 | badge class |
|---|---|---|
| `null`（未结算） | 进行中 | `info` |
（`null` **不是** `HEDGE_PAIR_OUTCOME_LABELS` / `_BADGE` 的键——那两个常量只有
`accepted_pair` / `confirmed_failed` / `single_leg` / `querying`。所以「进行中」必须走
**显式 `null` 分支**，不能指望查表命中；既有代码 `index.html:4466` 就是这么写的，照做。
计划评审 r4 观察 O-2。）

| `accepted_pair` | **已受理** | `success` |
| `confirmed_failed` | 已确认失败 | `danger` |
| `single_leg` | 单腿成交 | `warn` |

- **`accepted_pair` 用「已受理」而不是 fake 原型的「已成交」**：域语义是两条腿都拿到了
  `orderId`（被交易所受理），**不等于完全成交**——可能部分成交、也可能仍在挂单。写
  「已成交」是更强的断言，用户会以为钱已经落定。此处取保守文案。
  （Human 可推翻此选择，改动是一行；见交付报告中的说明。）
- **badge class 用 `warn` 不用 `warning`**：CSS 只定义了 `.badge.warn`
  （`index.html:229`），而既有 `HEDGE_PAIR_OUTCOME_BADGE`（`:3567`）把 `single_leg` 写成
  `'warning'` ——**这是既有的失效样式**。允许顺手把该处 `'warning'` 改为 `'warn'`
  （一行，是本表格正确展示的必要条件），并在回报中说明这一处属于顺带修复。
- 复用既有 `HEDGE_PAIR_OUTCOME_LABELS` / `HEDGE_PAIR_OUTCOME_BADGE`（`:3563-3568`），
  不要新建第二份映射。

### 【其余展示细则 · 计划评审列出的实现必撞点】

- **成交时间**：复用既有 `hedgeLogEntryTimeText`（`index.html:4516`，北京时间格式化），
  不要自创格式、不要展示裸 UTC ISO。
- **进行中行**：各值缺失时显示 `—`（fake 原型已示范）。
- **部分成交不得整行清空**：`accepted_pair` 且交易所状态为 `PARTIALLY_FILLED` 时，
  必须显示真实的数量与均价——不能因为「还没终态」就把整行抹成 `—`。那会让用户以为
  一分钱没动，而实际上已经成交了一部分。
- **渲染参照**：`renderHedgeLogEntryLeg`（`index.html:4524`）已经在用 `hedgeText` 逐字
  展示腿数据，是本表格金额格的正确写法参照。
- **展开后的刷新策略**：随现有 tick 重取或仅首次展开时拉取，二选一并说明；
  **禁止新增任何轮询定时器**。

## Allowed Files

- `frontend/index.html`（任务卡、日志表格、展开状态、`#task-id`、移除 fake 卡）
- `frontend/self-check.js`（前端自测）
- `backend/app/server.py`（**仅**为 `GET /api/hedge-open-logs` 新增**可选**的按任务过滤
  查询参数）
- `backend/hedge_open_tasks/service.py`（**仅** `get_logs` 的读路径接该过滤参数）
- `backend/hedge_open_tasks/store.py`（**仅**读查询；`list_attempts_for_task`
  （`store.py:1403`）已存在，优先复用）
- `backend/tests/test_hedge_*.py`（新增/修改测试）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（自测与交付证据）

**后端三个文件只允许动读路径。** 不得触碰任务状态机、调度、结算、计数器、暂停/删除
语义、worker 生命周期。超出边界即为 blocker，停下回报，不得自行扩边界。

## Inputs

- fake 原型（UI / 列 / 交互的视觉与语义参考）：commit `5871791`，
  `frontend/index.html:4229` 起的 `renderHedgeTaskCardFake`。
- 现有日志接口：`GET /api/hedge-open-logs`（`backend/app/server.py:588`，
  `service.get_logs`）——当前只有 `cursor/limit` 与 `entries_cursor/entries_limit`，
  **没有**按任务过滤的参数。计划评审已确认：新增可选 `task_id`（或等价）过滤**有必要**，
  只靠前端过滤全局分页页面会漏掉该任务的历史尝试。
- **`task_id` 模式的读语义（钉死）**：
  1. **无** `task_id`：响应契约完全不变。
  2. **有** `task_id`：`attempts` = 该任务的**全部** attempt + 两条腿，**一次返回全量**
     （满足 AC5），**不与 `entries_cursor` 混用分页**——两套游标共用会重蹈 R4 缺陷
     （任务事件每页重现，amendment 17 已修）。
  3. `logs` / `entries` 两个流以内嵌表消费的 `attempts` 为准；其余流可原样或同滤，
     但**不得使用共享游标**。
- 可复用但要注意：`store.list_attempts_for_task`（`store.py:1403`）**只返回 attempt 行、
  不带 legs**；`list_legs_for_attempt`（`store.py:1394`）已存在，可只读组装。
  （`list_attempts_page` / `list_attempts_entries_page` 才自带 spot/perp。）
- 分页上限参考：`LIMIT_DEFAULT = 50`、`LIMIT_MAX = 200`（`domain.py:518-520`）；
  `target_n` 只校验 `>= 1`，**无上限**，所以单任务 attempt 数可以超过 50。
- attempt / leg 字段与文档投影：`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/store.py`（`list_attempts_page`）。
- 范围收窄说明与被移出项：`06-scope-reduction.md`（本目录）。

## Acceptance Checks

1. **四种状态渲染正确**：按上面的**冻结映射表**逐项断言文案与 badge class（进行中/
   已受理/已确认失败/单腿成交，`info`/`success`/`danger`/`warn`），各有测试。
2. **【钱】数值原样透传**：测试证明均价与数量与后端原始字符串逐字一致，无四舍五入、
   无单位换算、无精度截断；断言金额格未经 `formatHedgeDecimal` / `hedgeNum`。
3. **【钱】未受理腿门控**：构造一条 `order_id` 缺失的腿（后端会给
   `cumulative_base_qty: "0"`），断言**该日志行该腿的订单号、均价、数量三个单元格**
   显示 `—`。断言范围限定在这三个单元格——**不要**断言「整页不出现 `0`」，任务卡计数器
   等处的 `0` 是合法的。
4. **【钱】错误原因回退链**：三个用例——① 后端已写入 `error_reason_zh` 的失败/单腿行，
   断言展示该字符串原文；② 只有 `error_code` / `error_category` 的行，断言展示机器字段
   原样；③ 两者皆无，断言展示固定占位「原因未记录」。断言前端**没有编造**任何中文业务句。
5. **数据真实且完整**：日志来自后端真实 attempt/leg 数据，覆盖该任务**全部**尝试。
   夹具的 attempt 数 **> 50**（默认页大小），断言一次 `task_id` 响应含全部，且未与
   `entries_cursor` 共用游标。
6. **「进展」列口径**：显示 `attempt_seq / target_n`，每行序号各不相同；断言未使用
   `scheduled_attempt_count`。
7. **展开状态**：跨自动刷新保持（`state.hedgeLogExpanded`）；**未新增任何轮询定时器**
   （给出证据）；真卡的 toggle 已绑定（不再依赖 `showFakePreview` 分支）。
8. **`#task-id` 可见**：回归验收——确认 `index.html:4207` 的既有实现仍然生效即可，
   无需新增实现。
9. **fake 代码已清干净**：`renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID` 及其专属样式/
   绑定分支已删除，全量搜索无残留引用。
10. **后端只动读路径**：给出 `git diff --stat` 与说明，证明未触碰状态机、调度、结算、
    计数器、暂停/删除语义、worker 生命周期。
11. **回归**：`frontend/self-check.js` 全过；`pytest backend/tests` 全过（贴原始输出，
    不得以叙述替代）。既有测试**不应有任何一条因本次改动转红**——若有，说明碰到了
    读路径以外的东西，停下回报。

## Stop

- 不写 live task DB、不下真实单、不碰凭据、不开 live 闸门、不做部署。
- **不做任何「任务卡卡住」相关的修复**（F10、暂停→删除、配额收口、`post_start` /
  `fill-once` / `fill-all` 的再武装检查）——已移出本 stage，见 `06-scope-reduction.md`。
- 不改任务状态机、不改 `PAUSE_REASON_*` 与其中文文案、不改 `aggregate_positions`、
  不改任何计数器或结算逻辑。
- **禁止为了填满错误原因列去改结算逻辑或 `error_reason_zh` 的写入语义**
  （`store.py:1085-1095`）。该列的数据缺失是既有事实，用回退链应对，不是本 stage 的
  修复对象。
- 禁止改 `_leg_to_doc` 的 `"0"` 投影来绕过未受理腿的门控——门控在前端按 `order_id` 做。
- 禁止新建第二份 `pair_outcome` → 文案/徽标映射；复用既有常量。
- 不新增全局轮询定时器（沿用「日志不随 tick 轮询」原则）；不新增 API 路由（按任务过滤
  只能是既有 `/api/hedge-open-logs` 上的**可选**参数）。
- 不扩 scope：不做平仓 / 补腿 / 借还币 / 自动对冲 / 自动平仓。
- 自测完成后停下回报，不启动评审终端、不合并、不推送。
