# 00-task：2026-07-31-hedge-task-inline-log-v1（实现 dispatch packet）

> 定稿状态：**revision 4——Human 需求变更后重写 Goal 3，待计划评审 round 2
> （`02-plan-review.dispatch.md`）**。计划评审 round 1 返回 REWORK 且需求随即变更，
> 详见 `04-plan-review-r1-verdict.md`。计划评审 ACCEPT 后由 Human 启动本 packet 的
> 实现终端。起草者 claude_glm（fast-fix bookkeeper），定稿者 opus5。
>
> **2026-07-31 变更记录**：Human 决定「非人工原因导致任务无法继续 → 任务卡直接进删除
> 终态，暂停只保留人工手动暂停」。原 Goal 3「方向 B」表述已被取代（方向 A 仍然否决，
> 理由不变）。`rework_count` 保持 0（需求变更 + 计划评审 verdict 均按 §8 豁免）。

## Identity

- task_id: 2026-07-31-hedge-task-inline-log-v1
- target_role: Implementer
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: 4
- required_skill: `agents/skills/senior-developer.md`
- 风险分级: **HIGH_RISK**（读订单/attempt 数据 + 触碰调度与完成判定语义，AGENTS §8）

## Goal

1. **任务卡内嵌日志（真实数据）**：每个开单任务卡在「暂停/启动」按钮行下增加单个
   toggle 按钮（展开日志 ↔ 收起日志），展开后任务卡向下伸出该任务的尝试日志表格。
   列固定为：进展 / 状态 / 成交时间 / 合约订单号 / 现货订单号 / 合约均价 / 现货均价 /
   合约数量 / 现货数量 / 错误原因。倒序（最新在上，进行中那行数据可为空）；失败与
   单腿成交行必须展示错误原因；订单号 / 均价 / 数量按该腿是否受理填充，未受理填 `—`。
   展开状态记入 `state.hedgeLogExpanded`，跨自动刷新保持。视觉与列语义以 fake 原型
   （commit `5871791`，`renderHedgeTaskCardFake`）为准。
   - 「进展」列口径 = 该任务**已调度尝试序号 / 计划次数**（含失败与单腿成交，与
     `scheduled_attempt_count` / `target_n` 同口径），与 Goal 3 的修法保持一致。
   - 数据必须覆盖该任务的**全部**尝试，不得是全局分页里恰好落在当前页的切片。
2. **任务卡展示 `#task-id`**：卡头显示任务唯一 id，便于人工定位与交流。
3. **自动暂停一律改为自动删除终态（Human 2026-07-31 决定）**：把当前所有**非人工**
   原因导致的 `paused` 改为直接进入 `deleted` 终态，使 `paused` 此后**只有一个来源**
   ——用户手动点「暂停」。目标是从根上消除「任务卡重启不生效」：自动结束的任务不可
   再启动，也就没有「重启」这个动作。
   - **六个自动暂停来源全部改为删除**（`domain.py:127-150` 的 `PAUSE_REASON_*`）：
     `consecutive_submission_failure`（连续提交失败达阈值）、`rate_limited`（429 限频）、
     `insufficient_balance`、`insufficient_margin`、`insufficient_available_qty`、
     `collateral_cap_full`（平台抵押额度打满）。**六个全改，无例外**——Bookkeeper 曾
     建议只改第一个（后五个是补一下就能继续的外部临时状况），Human 明确选择全改。
   - **删除原因必须可见**：现有 `_PAUSE_REASON_ZH`（`domain.py:1307`）的六条中文文案
     改写为删除语义（例如「触发交易所限频（429），任务已删除，如需继续请重新建卡」），
     并在任务卡上展示。自动删除不得是黑箱——用户必须知道卡为什么没了。
   - **【资金硬约束】自动删除不得隐藏未平敞口**：`single_leg_exposure` 计入失败刹车
     （R2-F1 / user authorization 28 §2.1），因此一个留有**未平单腿敞口**的任务可能被
     自动删除。交付必须证明：删除后该敞口仍在界面可见（敞口告警 / 持仓视图 / 已删除
     筛选），不因软删除而从默认列表消失即视为「已处理」。此条不可协商。
   - **【在途订单硬约束】删除不得丢单**：现有 `post_delete` 不打断 worker，worker 继续
     把在途腿 drain 到终态再退出（`service.py:609-619` 注释）。自动删除必须走同一路径，
     不得在有非终态腿时直接终止 worker。
   - **手动暂停仍须可恢复**：人工暂停且计划次数未用尽的任务，点「启动」必须真正恢复
     （worker 重新调度）。这是 `paused` 剩下的唯一语义，必须有测试证明。
   - 不改 `failure_pause_threshold` 的**触发条件**（仍是连续失败/单腿达阈值），只改
     触发后的**去向**（`paused` → `deleted`）。不得放宽或绕过该阈值。
   - 重试路径 = 用户手动重建任务卡。**不做**「按原参数复制新建」按钮（Human 决定，
     本 stage 不扩 scope）。
4. **计划次数用尽但未达成的任务必须收口**：这是 F10 实例的真正病根，与第 3 条相互独立
   ——COOKIEUSDT（计划 1 / 已调度 1 / 已受理 0 / 连续失败 1，阈值 3）从未进入暂停，
   卡在 `running`，第 3 条对它不生效。
   - **保持** `scheduled_attempt_count` = 计划调度上限（A-1 硬上限）的现有语义不变，
     让「计划次数已用尽但未达成」的任务进入明确终态，`post_start` 对这类任务给出明确
     结果而不是静默置 `running`。
   - **方向 A 已被否决**（不得实施）：把 worker 退出线改成 `accepted >= target_n`
     会让失败尝试无限重发新订单，突破用户设定的「计划 N 组」资金上限，属于资金语义
     变更；且 A-1 上限在 `store.py` 的预留事务中原子生效，只改 worker 退出线不会生效。
   - **根因家族必须一次穷举**（AGENTS §8 同根因刹车的预防性应用）：`scheduled_attempt_count
     >= target_n` 这一判据当前至少出现在 `service.py:1116`（worker 退出）、
     `store.py:686`（`list_eligible_tasks` 调度过滤）、`store.py:736`（预留原子上限）、
     `store.py:971`（R2-F1 结算收口为 `done`）。交付必须逐一列出该家族的全部站点，说明
     每处是「修改」还是「保持不变及理由」，清单外站点给出不适用理由。
   - **`store.py:971` 的收口是有效的，不要当新逻辑重写**（计划评审 round 1 已证：
     `test_hedge_store.py:174-192` 锁定「计划 1、连败 1 < 阈值 3 → 结算后 `done`」）。
     F10 findings 中 COOKIEUSDT「卡在 running」的叙述判定为**诊断过时**，不作为验收
     对象，也不去读实盘 DB 追溯该历史实例。
   - **真实残留死锁路径（本条的实际修复对象）**：`paused` 优先于配额收口
     （`store.py:967-982` 的 R2-F1 要求 `new_status == running`，而暂停先落）→
     `post_start`（`service.py:582-596`）对非 `deleted`/`done` 一律
     `set_task_status(RUNNING)` + `ensure_worker`，**不检查配额** → worker 立刻
     `WORKER_EXIT_TARGET_REACHED` 退出 → 任务留在 `running` 无进展。
     复现条件：`target_n == failure_pause_threshold`。
   - **再武装入口有三个，须一并处理**：`post_start`（`service.py:582`）、
     `post_fill_once`（`:622`）、`post_fill_all`（`:636`）——后两个在 live 下同样
     `set RUNNING + ensure_worker`。另：`post_start` 当前只挡 `deleted` 与 `done`，
     `stopped` 任务可被启动，配额已用尽时同样卡死。
   - **行为契约（钉死，最小实现即可）**：
     ① 终态**沿用现有 `done`**，不新造状态枚举；
     ② 上述三个入口在 `scheduled_attempt_count >= target_n` 且无法再派组时，
        **禁止静默置 `running` + 启 worker**，须返回可测的明确结果；
     ③ 对已是 `done` 的任务点启动，当前是幂等 200 且无中文说明
        （`service.py:587-588`），前端 `showHedgeTaskActionError` 只在 `!ok` 时提示
        （`index.html:4318`）→ 必须给出用户可见的中文反馈，不能「点了没反应」；
     ④ 前端文案须区分 `done` 的两种含义——「计划组已用尽（未全部成功）」与
        「全部成功」——否则业务误读。
   - **`skip_counters` 路径要扫一眼**：限频结算走 `settle_attempt_no_counters`
     （`store.py:899-916`），不经过 R2-F1 收口，配额已耗仍可能停在非终态。新需求下
     限频已改为自动删除（Goal 3），须确认这条路径的结局与 Goal 3 一致、不留悬空。
   - **家族清单外、不得并入的三处**（谓词不同，计划评审已确认）：`domain.py:1087`
     （`accepted_count >= target_n`，成功完成口径）、`service.py:653`（dry-run `fill_all`
     用 `success_count`）、`store.py:806-807`（只是计数器 +1，不是判据）。
5. **移除 fake 数据**：真实版落地后删除 `renderHedgeTaskCardFake`、`HEDGE_FAKE_TASK_ID`
   及其仅服务于假卡的样式/绑定分支；不得留下未被引用的死代码。

## Allowed Files

- `frontend/index.html`（任务卡、日志表格、展开状态、`#task-id`、移除 fake 卡）
- `frontend/self-check.js`（前端自测）
- `backend/hedge_open_tasks/service.py`（F10：worker 退出条件、`post_start` 反馈）
- `backend/hedge_open_tasks/store.py`（F10：调度过滤 / 预留上限 / 结算收口三处判据）
- `backend/hedge_open_tasks/domain.py`（口径常量、状态解析、注释同步）
- `backend/app/server.py`（仅当日志接口需要新增**可选**的按任务过滤查询参数时）
- `backend/tests/test_hedge_*.py`（新增/修改测试）
- `reports/agent-runs/2026-07-31-hedge-task-inline-log-v1/`（自测与交付证据）

超出上述边界即为 blocker，停下并回报，不得自行扩边界。

## Inputs

- F10 诊断：`reports/agent-runs/2026-07-hedge-fast-fix-v1/findings.md`（F10 行）。
  **⚠️ 该诊断已被计划评审判定为过时**：其 COOKIEUSDT 实例（计划 1 / 已调度 1 /
  已受理 0 / 连续失败 1，卡在 running）与 `test_hedge_store.py:174-192` 锁定的行为冲突。
  只当历史背景读，真实修复对象见 Goal 4 的「真实残留死锁路径」。
- 计划评审 round 1 全文与已核验的事实判断：`04-plan-review-r1-verdict.md`（本目录）。
- 可复用：`store.list_attempts_for_task`（`store.py:1403`）已存在，单任务日志不必新写查询。
- Human 需求变更与 Bookkeeper 上报的资金风险：`04-plan-review-r1-verdict.md`（本目录）。
- 根因站点：`backend/hedge_open_tasks/service.py:1116`、`backend/hedge_open_tasks/store.py:686`
  `:736`、`:971`、`backend/hedge_open_tasks/domain.py:1087`（`resolve_status_after_attempt`）。
- 自动暂停站点：`domain.py:127-150`（六个 `PAUSE_REASON_*` 与其集合）、`domain.py:1307`
  （`_PAUSE_REASON_ZH` 六条中文文案）、`service.py` 的 `_pause_task_local` /
  `_pause_from_signal` / `SIGNAL_TASK_LOCAL_PAUSE` 调用点、`domain.resolve_status_after_attempt`
  的 `STATUS_PAUSED` 分支。清单可能不全，实现方须自行穷举并列出。
- 软删除现状：`post_delete`（`service.py:609`，不打断 worker、继续 drain）、
  `post_start` 对 `deleted` 抛 409（`service.py:585`）、`store.py:599/1941/1951` 的
  已删除过滤、`service.py:1542` 的状态分组。
- fake 原型（UI / 列 / 交互的视觉与语义参考）：commit `5871791`，
  `frontend/index.html:4229` 起的 `renderHedgeTaskCardFake`。
- 现有日志接口：`GET /api/hedge-open-logs`（`backend/app/server.py:588`，
  `service.get_logs`）——当前只有 `cursor/limit` 与 `entries_cursor/entries_limit`，
  **没有**按任务过滤的参数。
- attempt / leg 字段与文档投影：`backend/hedge_open_tasks/domain.py`、
  `backend/hedge_open_tasks/store.py`（`list_attempts_page`）。

## Acceptance Checks

1. **前提确认**：回报中确认「`store.py:971` 的 R2-F1 收口有效、`test_hedge_store.py:174-192`
   已锁定、COOKIEUSDT 叙述为过时诊断、不作为验收对象」这一前提，未把该收口当新逻辑重写。
2. **真实残留死锁复现在先**：先写失败测试复现——任务处于**人工暂停**（新需求下 `paused`
   只剩此来源）且 `scheduled_attempt_count >= target_n` → `post_start` → 当前会置
   `running` + `ensure_worker`、worker 立刻 `WORKER_EXIT_TARGET_REACHED` 退出、无新
   attempt、任务留在 `running` 无进展。提交该测试的**原始失败输出**，再修到：不再静默置
   `running`，返回明确结果。`post_fill_once` / `post_fill_all` 各有同形态测试。
   另测：对已是 `done`（配额用尽）的任务点启动，有用户可见的明确中文反馈，不是静默 200。
3. **六种自动暂停全部改为删除**：六个 `PAUSE_REASON_*` 各有一个测试，证明触发后任务
   状态为 `deleted` 而非 `paused`，且删除原因的中文文案正确、在任务卡上可见。
4. **`paused` 只剩人工来源**：全量搜索证明代码中不再有非人工路径写入 `paused`
   （给出搜索命令与结果）；人工暂停且配额未用尽的任务，点「启动」后 worker 重新调度
   并继续尝试（测试证明，不靠人工观察）。
5. **【资金】自动删除不隐藏未平敞口**：构造一个「单腿敞口达阈值 → 自动删除」的用例，
   证明删除后该敞口仍在界面可见（敞口告警 / 持仓视图 / 已删除筛选至少其一），并说明
   用户从哪里能看到它。
6. **【资金】自动删除不丢在途单**：构造一个「有非终态腿时触发自动删除」的用例，证明
   worker 仍把在途腿 drain 到终态才退出，未终止查询、未重发订单。
7. **配额用尽的终态与反馈**：终态沿用 `done`（未新造状态枚举）；三个再武装入口
   （`post_start` / `post_fill_once` / `post_fill_all`）在配额用尽时均不再静默置
   `running`；`stopped` 任务的同一入口一并处理；前端文案区分「计划组已用尽（未全部
   成功）」与「全部成功」两种 `done`。
8. **根因家族清单**：回报中列出 `scheduled >= target_n` 家族的全部站点及每处的处理/
   不适用理由，并显式标注 `store.py:971` 为「保持/加强」而非新增；显式列出计划评审
   已确认的三处**清单外不适用**站点（`domain.py:1087`、`service.py:653`、
   `store.py:806-807`）及其不同谓词；`failure_pause_threshold` 的**触发条件**有测试
   证明未被放宽或绕过；`skip_counters` 限频结算路径（`store.py:899-916`）的结局已核并
   与 Goal 3 一致。
9. **日志表格**：可展开/收起；四种状态（进行中 / 已成交 / 失败 / 单腿成交）渲染正确；
   倒序；失败与单腿行显示错误原因；未受理腿的订单号/均价/数量显示 `—`。
10. **数据真实且完整**：日志来自后端真实 attempt/leg 数据，覆盖该任务全部尝试；
    `renderHedgeTaskCardFake` 等假数据代码已删除且无残留引用。
11. **展开状态**：跨自动刷新保持（`state.hedgeLogExpanded`）；未新增全局轮询定时器。
12. **回归**：`frontend/self-check.js` 全过；`pytest backend/tests` 全过（贴原始输出，
    不得以叙述替代）。

## Stop

- 不写 live task DB、不下真实单、不碰凭据、不开 live 闸门、不做部署。
- 不实施方向 A（不得把调度上限改成 `accepted` 口径），不放宽 A-1 计划上限。
- 不绕过、不放宽 `failure_pause_threshold` 的**触发条件**（只改触发后的去向）。
- 不做「按原参数复制新建」按钮或任何删除后的恢复入口（Human 决定：手动重建）。
- 不新增第六个任务状态；只在现有 `running/paused/done/stopped/deleted` 内改路由。
- 自动删除不得终止正在 drain 在途腿的 worker，不得让未平单腿敞口从界面消失。
- `post_start` / `post_fill_once` / `post_fill_all` 在配额用尽时不得静默再武装 worker。
- 不把 `store.py:971` 的 R2-F1 收口当新逻辑重写；不为追溯 COOKIEUSDT 历史实例去读实盘 DB。
- 不新增全局轮询定时器（沿用「日志不随 tick 轮询」原则）；不新增 API 路由（按任务
  过滤只能是既有 `/api/hedge-open-logs` 上的**可选**参数）。
- 不扩 scope：不做平仓 / 补腿 / 借还币 / 自动对冲 / 自动平仓。
- 自测完成后停下回报，不启动评审终端、不合并、不推送。
