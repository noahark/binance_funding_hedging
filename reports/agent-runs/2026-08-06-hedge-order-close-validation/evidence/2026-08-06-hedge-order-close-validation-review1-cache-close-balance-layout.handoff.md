# Task Handoff: 2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout`
- role: `Reviewer`（review-1）
- target_model: `opus5`（Claude Opus 5；provider=`anthropic`）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 22:10:29 CST`
- base_sha: `ee7ec4f3a41db8d896652101fcd1821972b381bc`
- delivery_sha: `10f1f014de424024a307d6ed90dffb6c8891ceb0`
- 评审结论：**REWORK（返工）** —— 唯一阻塞项 F-1（一行修复），其余 4 个交付全部通过。

### 隔离与利益披露

- **Provider 隔离满足**：实现作者 `deepseek`（provider=`deepseek`），本评审
  `opus5`（provider=`anthropic`）。本评审非实现或修复作者。
- **须披露的既往参与**：本模型起草了受审交付之一的 dispatch
  `05-preflight-local-cache-and-close-simplify.dispatch.md`，以及其实测依据
  （耗时/抖动数据、缓存映射表、陈旧上限取值、平仓两条硬边界的界定）。
  task 06/07 与 `10f1f01` 的 dispatch 非本模型起草。
  即：**交付 1 的验收基线由本模型定义，本次是核对他人实现是否满足该基线**。
  同 provider 禁令未违反（未触碰实现代码）；但对交付 1 的验收标准本身存在既得立场。
  本次 `REWORK` 发现 F-1 恰落在交付 1 的 Goal 5，为避免"自定标准自证达成"的偏向，
  F-1 的判定完全基于**可独立复核的客观证据**（HTML 元素 class、CSS 声明行号、
  JS toggle 语句、CSS 层叠规则），不依赖对 dispatch 意图的解释。
  Human 若认为该立场不可接受，可另派 review-1 复核 F-1。

### 只读评审范围

- 受审区间：`git diff ee7ec4f..10f1f01`（23 文件，+2692 / −102）。
- 评审主体：四个交付（task 05 `e4d5464` / task 06 `5388938` / task 07 `3006db3` /
  HTML 标签修复 `10f1f01`）。
- 区间内 bookkeeper 控制提交（dispatch / `status.json` / handoff）按
  `AGENTS.md` §8「评审范围口径」记为上下文，非受审交付。
- 本任务除创建本交接件外**未写入任何文件**：未改代码、证据、`status.json`，
  未提交、未移动 `HEAD`、未对实盘发单/划转/设杠杆、未记录任何凭证。

### 逐项验收结论

| 验收项 | 结论 | 依据 |
|---|---|---|
| 交付1 缓存只读、不触发刷新 | pass | `snapshot_service.py:1217-1229` `get_cached_source` 仅 `_global_source_cache.get()`，无 `_refresh_due_sources` 调用 |
| 交付1 两服务解耦 | pass | 复跑 `grep -rn "SnapshotService" backend/hedge_open_tasks/ backend/services/hedge_preflight_provider.py` → 仅注释字符串，**无 import**；注入走 `configure_snapshot_reader` / `configure_preflight_reader`（照抄 `configure_cache_refresh` 先例） |
| 交付1 陈旧上限取值 | pass | `hedge_preflight_provider.py:54-58`：exchangeInfo 2h / price 5min / balance 5min / restricted_asset 10min / 账户配置 600s，与 dispatch §2/§3 逐项一致 |
| 交付1 `restricted_asset` 唯一 fail-closed 不降级 | pass | `:584-617`：缓存缺失/超龄/结构不符 → `_degrade_note` + `return None`，**不回退实时读**；测试 `test_restricted_asset_stale_fails_closed_no_realtime` / `test_restricted_asset_missing_fails_closed` |
| 交付1 平完判定收敛 + 三分支语义不变 | pass | `service.py:1499-1527` 收敛进 `scheduled_attempt_count >= target_n` 分支，仍实时；测试 `test_close_flat_verify_only_at_target_reached` 断言 `verify_calls == 1`（两轮下单期间 0 次） |
| 交付1 划转：去复检 + `sleep(100ms)` + 缓存放行/实时确认 | pass | `service.py:1632-1674`；测试四条：`..._cache_sufficient_passes_without_realtime`（`free_calls == []`）、`..._cache_insufficient_confirms_realtime_then_transfers`（恰好 1 次）、`..._sleeps_100ms_and_no_recheck`、`..._no_recheck_after_transfer` |
| 交付1 缺 `tranId` 仍暂停 | pass | `universal_transfer` 内部抛错未改，`_ensure_close_spot_balance` 异常分支保留 |
| 交付1 预检失败 paused + 失败读名 + 无重试 | pass | `service.py:1550-1556` `_pause_preflight_incomplete`；`domain.py:169-183` 新增 `PAUSE_REASON_PREFLIGHT_INCOMPLETE` + 中文；测试 `test_preflight_incomplete_pause_names_failed_read` 断言事件含 `failed_read`；无重试路径 |
| 交付1 前端徽标未改数据源 | pass | 仍读 `doc.executor_mode`（进程实时 `self._mode`），未引入新通道 |
| **交付1 前端徽标 dry-run 警示色** | **fail** | **见 F-1** |
| 交付1 「成交」按钮演习标注 | pass | `frontend/index.html:5129-5130`，`drillMode` 由 `state.hedgeSettings.executor_mode` 派生；`loadHedgeSettings` 完成后重渲染 |
| 交付2 REVERSE 分支路由感知 | pass | `domain.py:1219-1223` 与 FORWARD 分支 `:1215-1218` **完全对称**（同为 `or Decimal(0)`）；`spot_account_base_free` 字段注释说明两个钱包区别 |
| 交付2 非 regular_spot 路径逐字不变 | pass | `else: available = snapshot.balances.get(base, Decimal(0))` 未改 |
| 交付2 FORWARD 零改动 | pass | diff 中 FORWARD 分支无改动 |
| 交付2 THE 场景 | pass | 测试 `test_close_forward_reads_standard_spot_base_free_the_scenario` |
| 交付3 滚动定位 | pass | `frontend/index.html:5786-5790`，在三处 `display` 赋值之后；`typeof window !== 'undefined'` 保护；self-check 全绿 |
| 交付4 HTML 标签配对 | pass | 评审者复跑标签栈核对：`section 6/6`、`main 1/1`、`div 261/261`、`header 1/1` 全平衡 |
| 交付4 `#history-view` 在 `<main>` 内 | pass | 实测位置：`<main>` 起 31950、`</main>` 止 48015、`#history-view` 在 47651 → **在 main 内** |
| 回归 | pass | 评审者复跑 `.venv/bin/python -m pytest backend/tests -q` → **1467 passed in 82.48s**；`node frontend/self-check.js` → **全部自检通过**，与 Bookkeeper 记录一致 |
| 范围 | pass | `git diff ee7ec4f..10f1f01` 无范围外改动；无未授权提交/实盘写 |

### REWORK 发现

#### 🔴 F-1（**in-range**，阻塞）dry-run 徽标警示色被 `muted` 覆盖，Goal 5 视觉区分未达成

**事实链（三条独立可复核证据）**

1. 元素初始 class：`frontend/index.html:1449`
   `<span class="badge muted" id="hedge-execution-badge">`
2. JS 只**添加** `warn`、**从不移除** `muted`：`:4508`
   `els.hedgeExecutionBadge.classList.toggle('warn', !liveMode);`
   （全文件 grep 确认无任何位置对该元素 `classList.remove('muted')`）
3. CSS 声明顺序：`.badge.warn` 在 **:262**，`.badge.muted` 在 **:266**

**判定**：两条规则特异性相同（均为 `0,0,2,0`，两个 class 选择器），CSS 层叠规则下
**后声明者胜出**。dry-run 时元素 class 为 `badge muted warn`，`.badge.muted`（:266）
覆盖 `.badge.warn`（:262）的全部三个属性（`border-color` / `background` / `color`）。
已排除 ID 选择器介入（`grep` 确认无 `#hedge-execution-badge` 的 CSS 规则）。

**后果**：dry-run/disabled 模式下徽标**仍呈灰色 muted 样式，与 live 模式视觉无差别**。
dispatch 05 Goal 5「dry-run 时状态栏变警示色 + 「成交 1 次」按钮标注演习模式」
的**前半项未达成**（后半项按钮标注已达成，故提示能力减半而非归零）。

**为何阻塞**：该 Goal 是 2026-08-06「服务被误启动为 disabled 半小时、产生 4 笔假成交
污染持仓口径（800/600 vs 真实 400/200）」事件的**直接防复发措施**；其存在意义就是
「一眼可辨」。当前实现使该防线在视觉主通道上失效。

**修复要求（任选其一，均为一行）**

- a) JS 同步互斥（推荐，最贴近意图）：在 `:4508` 同处加
  `els.hedgeExecutionBadge.classList.toggle('muted', liveMode);`
- b) CSS 顺序调整：把 `.badge.warn` 声明移到 `.badge.muted` 之后
  （**注意**：会影响其他同时带 `muted`+`warn` 的徽标，需全局确认）
- c) 先 `classList.remove('muted')` 再 `add('warn')`

**建议同时补的测试**：self-check 或前端断言中加一条——dry-run 时该元素的 class
集合**不同时包含** `muted` 与 `warn`（或按方案 b 断言声明顺序），避免回归。

### 建议与观察（不阻塞）

**💭 N-1（in-range，nit）** `renderHedgeExecutionStatus` 的 `!doc` 早退分支
（`:4497-4502`）只重置 `textContent`，**未重置 `warn` class**。settings 请求失败后
徽标可能残留上一次的模式配色，与「未加载」文案不一致。修 F-1 时可一并处理。

**💭 N-2（in-range，nit）** `_close_transfer_done`（`service.py:512`）是进程内
`dict[task_id -> (amount, asset)]`，**只写不清**——任务终结（done/deleted）后条目仍
保留。每个 forward close 任务一条，单条极小，属极轻微的单调增长；长期运行进程建议在
任务终结点或 `_worker_exit` 清理。注释已声明「重启后丢失只导致无提示（保守）」，
但未说明何时清理。

**💭 N-3（in-range，nit）** `loadHedgeSettings`（`:4523-4524`）在 settings 到达后
无条件调用 `renderHedgeTasks()`。功能正确（演习标注依赖 `executor_mode`），但与既有
tick 渲染存在一次重复渲染。任务列表规模小，开销可忽略。

**💭 N-4（观察，非缺陷）** `_cached_spot_free` / `_cached_unified_free`
（`service.py:634-694`）用 `time.monotonic()` 与 SnapshotService 存入的 monotonic
时间戳比较——两者同进程，语义正确。若将来 SnapshotService 移出进程，该比较会静默失效
（monotonic 跨进程不可比）。当前架构下无问题，仅记为演进风险。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md`
  2. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
  3. `reports/agent-runs/2026-08-06-hedge-order-close-validation/05-preflight-local-cache-and-close-simplify.dispatch.md`
- 执行：Bookkeeper（deepseek）核验本 review-1 `REWORK`，据 F-1 的修复要求准备一轮
  bounded repair dispatch（范围仅 `frontend/index.html` 的徽标 class/CSS 一行 +
  可选的 N-1 重置与防回归断言），并按 `AGENTS.md` §8 递增 `rework_count`
  （当前 1 → 2）。N-2/N-3/N-4 记为不阻塞后续项。
- 关卡：修复后回到 review-1（`AGENTS.md` §8：Review-1 `REWORK` 返回 review-1），
  或由 Human 行使 §8 的「已知风险暂不修、仍允许合并」授权并记录问题事实、可能影响、
  接受理由、观察方式与复看条件。
- 不能假设的事实：
  1. 除 F-1 外，四个交付的其余全部验收项**均已通过**，且回归已由评审者独立复跑
     （1467 passed + self-check 全绿）——修复轮**不需要重做**这些验证；
  2. F-1 是纯前端样式层缺陷，**不涉及任何后端逻辑、资金路径或数据正确性**；
     交付 2 的平仓余额修复、交付 1 的缓存与平仓简化均未受影响；
  3. 本评审**未做实盘复测**——建卡/下单提速、平仓收尾判定、THE 平仓不再误拦，
     均需 Human 实盘确认；
  4. 评审者与 task 05 dispatch 起草者为同一模型（见「隔离与利益披露」）；
  5. 本 stage Human 已决定不安排 review-2；F-1 修复后的复核范围由 Bookkeeper 与
     Human 决定。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout
执行结果: completed（完成）
结果摘要: review-1 审 ee7ec4f..10f1f01 四个交付。task 06 平仓余额修复、task 05 缓存/平仓简化/预检可见暂停、task 07 滚动、HTML 标签修复均通过；复跑 1467 passed + self-check 全绿、标签配对平衡、history-view 已在 main 内。仅 1 项阻塞：dry-run 徽标警示色被 muted 覆盖、视觉未生效（一行可修），结论 REWORK。
产物: [reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md]
检查结果: [交付1 缓存只读/解耦/陈旧上限/restricted_asset 唯一 fail-closed: pass, 交付1 平完判定收敛（verify_calls==1）+ 三分支语义不变: pass, 交付1 划转去复检+sleep100ms+缓存放行实时确认（四条测试）: pass, 交付1 预检失败 paused+失败读名+无重试: pass, 交付1 徽标警示色（Goal 5 前半项）: fail（F-1）, 交付2 REVERSE 路由感知与 FORWARD 完全对称、FORWARD 零改动: pass, 交付3+4 滚动定位/标签配对平衡/history-view 在 main 内: pass, 回归复跑 1467 passed + self-check 全绿、范围无越界: pass]
阻塞项: [F-1 dry-run 徽标警示色未生效（frontend/index.html:1449 元素带 muted、:4508 只加 warn 不移除 muted、CSS .badge.muted(:266) 后声明覆盖 .badge.warn(:262)）]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md
修复要求: reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md
本地北京时间: 2026-08-06 22:10:29 CST
下一步模型: deepseek（Bookkeeper，本 stage status.json 记录的簿记者）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md，reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json；执行：据 F-1 修复要求准备一轮 bounded repair dispatch（范围仅 frontend/index.html 徽标 class/CSS 一行 + 防回归断言）并递增 rework_count 1→2，N-2/N-3/N-4 记为不阻塞后续项；关卡：修复后回 review-1，或 Human 行使已知风险暂不修的合并授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->


- verified_at: `2026-08-06 22:17:26 CST`
- source_sha256: `f050047ecc87853a6eafdd24cdfed42e3e08e22e164c5024e809ef4c2087bac6`
- status_revision: 12（核验时 `status.json` 指向本 review-1 任务）
- base_sha / delivery_sha: `ee7ec4f3a41db8d896652101fcd1821972b381bc` .. `10f1f014de424024a307d6ed90dffb6c8891ceb0`（与 `status.json` 及 `git rev-parse` 一致）
- verdict: **review-1 REWORK 核验成立**（评审闭线字段齐全：`评审结论: REWORK`、`问题记录` 与 `修复要求` 均指向本 handoff；唯一阻塞 F-1）
- 依据（可复现）——F-1 三条证据本 Bookkeeper 独立复核全部属实：
  1. `frontend/index.html:1449` `<span class="badge muted" id="hedge-execution-badge">`
  2. `:4508` `classList.toggle('warn', !liveMode)`；全文件 `classList.remove('muted')` 计数为 0
  3. CSS `.badge.warn` 在 `:262`、`.badge.muted` 在 `:266`——同特异性下后声明胜出
  - 评审者复跑 1467 passed + self-check 全绿，与 Bookkeeper 此前实测一致；标签配对平衡与
    history-view 在 main 内（交付 4）属实
- 后续项（不阻塞）：N-1（`!doc` 早退未重置 warn class，随 F-1 修复顺带）、N-2（`_close_transfer_done`
  只写不清）、N-3（settings 到达后重复渲染任务列表）、N-4（monotonic 跨进程演进风险）
- 后续状态：本 review-1 `dispatched` → `verified`（REWORK 已确认）；已派发修复任务 09
  （badge-fix，bounded repair，`rework_count` 1→2）；修复后回 review-1 复审或 Human
  行使已知风险暂不修授权；N-2/N-3/N-4 由 Bookkeeper 排期

## Errata (append-only)