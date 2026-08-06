# Task Handoff: 2026-08-hedge-position-cycle-v1-review-sonnet5

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-hedge-position-cycle-v1-review-sonnet5`
- role: `Reviewer`（target_model: `sonnet5`，provider: `anthropic`；required_skill:
  `agents/skills/reality-checker.md`；本评审合并 review-1+review-2 为一次，Human 2026-08 决定）
- stage_id: `2026-08-hedge-position-cycle-v1`
- created_at: `2026-08-06 10:52 CST`
- base_sha: `08127aabbb15548f46484257614f34f384c6cac8`（`git rev-parse HEAD`；本评审只读，未移动 HEAD）
- delivery_sha: `pending`（被审对象是工作树未提交改动，dispatch 明确指定「基线 08127aa 之后全部」；
  本 stage 全程未建分支、未提交，五份前置 handoff 的 `delivery_sha` 均为 `pending`——沿用同一操作模式，
  非本评审引入的偏差）

### 评审范围

被审对象：工作树未提交改动（`git diff 08127aa` 20 个已跟踪文件 + 7 个新文件，`+2145/-121`），
覆盖功能一（周期表）、功能二（费率/利息统计）、功能三（立即平仓执行 + 结算日志 + 历史页）、
平仓现货卖出路由重设计。依据 dispatch
`reports/agent-runs/_proposals/2026-08-hedge-position-cycle-v1.review-sonnet5.dispatch.md`
逐项核对：周期表、开平仓成本隔离、平仓执行、费率/利息统计、前端、回归、资金安全。

### 核对方法

逐文件读取 `git diff 08127aa` 全文（`domain.py`/`store.py`/`service.py`/`executor.py`/
`live_hedge_executor.py`/`hedge_open_live_client.py`/`hedge_preflight_provider.py`/`server.py`/
`ledger_flow/service.py`/`frontend/index.html`/`test_hedge_purity.py`），逐条比对设计权威
（`hedge-open-position-cycle-v1.md` 含 §12 append）与 stage2/stage3 文稿、五份 evidence handoff
的交付声明；独立复跑 `python3 -m pytest backend/tests -q`（**1419 passed**）与
`node frontend/self-check.js`（**全部通过**），复现 handoff 声明的测试数字；对可疑发现用独立
repro 脚本直接调用生产代码验证（非静态猜测）。

---

## 通过项（核对成立，不再复述）

1. **周期表（功能一）**：`hedge_open_cycle`/`hedge_open_attempt.cycle_id` 建表+迁移幂等；
   `prepare_attempt` 分配与 attempt 写入同事务（`_get_active_cycle_locked`/`_create_cycle_locked`
   内部无锁版，无嵌套 `with self._conn:`）；`aggregate_positions` 桶键改
   `(coin, direction, cycle_id)`；`merge_positions` P0-1（计划评审 r1 发现的静默丢弃缺陷）已
   按周期粒度重写（`domain.py:1846-1863`：`active` 列表 + `max(key=cycle_opened_at)` 取最近活跃周期，
   不再依赖列表顺序假设）；`close_cycle` 幂等/单向（`WHERE closed_at_us IS NULL`）核实成立。
2. **持仓表口径**：`aggregate_positions` SQL-B 加
   `WHERE t.task_type='open' AND (a.cycle_id IS NULL OR c.closed_at_us IS NULL)`
   （`store.py:2387-2394`）——已平仓周期从根源排除，只在历史页呈现，与 `PROJECT_STATE.md`
   记录的 Human 口径一致。
3. **开平仓成本隔离**：`aggregate_positions` 的 `task_type='open'` 过滤是唯一全局开关，
   close 任务的腿绝不参与开仓成本基；`cycle_leg_basis`（`store.py:365-395`）按 `task_type`
   分别加权，`close_log` 的 `open_avg_price`/`close_avg_price` 各自独立计算（`service.py:1587-1591`）。
4. **平仓方向反转 + reduceOnly**：`direction_to_leg_actions(task_type='close')`
   （`domain.py:698-700`）正确交换 spot/perp side；`build_perp_order_params`
   （`executor.py:139-163`）与 live 路径（`live_hedge_executor.py:838-859`）均正确按
   `task_type` 设置 `reduceOnly:"true"`，dry-run/live 两条路径一致核对成立。
5. **完成判定重构**：`_worker_round` 对 close 任务强制先走 `_verify_close_flat`
   （`service.py:1403-1424`）：`flat→finalize`/`open+次数用完→部分平 done`/
   `failed→暂停 close_verify_failed`（fail-closed，`query_symbol_um_qty` 返回 `None` 时不当
   `已平完`，`service.py:1466-1472` 与 `live_hedge_executor.py:588-614` 核对成立）；
   `resolve_status_after_attempt` 经 `suppress_done` 新分支（`store.py:1131-1141`）回退 DONE→RUNNING，
   仅对 `task_type=close` 生效（`service.py:2361-2363`/`2526-2528` 用
   `ctx.task_type==D.TASK_TYPE_CLOSE` 门控），开单任务行为逐字不受影响。
6. **平仓现货卖出重设计**：`decide_spot_route(task_type='close')`（`domain.py:990-993`）
   close+forward 固定 `regular_spot`（不读 cap）、close+reverse 固定 `papi_margin`，open 路径逐字不变；
   `_ensure_close_spot_balance`（`service.py:1491-1547`）余额检查→划转→复检→fail-closed 链路正确
   （不足才划转、划转前先查统一账户余额避免盲划、复检防「响应丢失但划转成功」误判、任一步失败
   即停不重试不发单）；`universal_transfer` type 冻结 `_ALLOWED_TRANSFER_TYPES`
   （`hedge_open_live_client.py:130-131`）、写语义不重试、`asset`/`amount` 均服务端内部计算
   （无外部注入面）；白名单 12→14 端点，`test_hedge_purity.py` 冻结测试同步（14/8/6，核对成立）。
7. **费率/利息统计**：`sum_funding_by_symbol`/`sum_interest_by_asset`/`coverage_for_window`
   （`ledger_flow/service.py:351-390`）纯读、复用既有 gap-aware `_build_coverage`（计划评审 P1-2
   已修复项延续正确）；`server.py:_hedge_open_positions` 组合根接线（`:800-864`）诚实降级——
   无周期/ledger 未注入/coverage 不完整（含窗口内 gaps）→ 三列 `None`+`stats_incomplete`，
   任一源不可解析 → `net_pnl=None`（绝不部分相加）；利息按资产计、资金费按 USDT 计的单位不一致
   问题已用 `price_map`（源=公开行情 `opening_quotes.spot_bid_price`，真零免价格、非零缺价格→None）
   正确处理，未拼错单位相加。
8. **前端**：`renderHedgeCloseInputs`/`requestHedgeCloseConfirm`/`submitHedgeClose` 真实 POST
   `task_type:'close'`；提前量检测（统一账户余额 vs 合约持仓，双向拦截，字段来自既有
   `unified_balance`/`um_position_amt`，非本次新增字段核实成立）；任务卡「平仓」/「开单」徽标、
   历史仓位导航与 `loadHedgeCloseLogs`/`renderHedgeHistory` 真实渲染（无 fake 横幅）；`statsCell`/
   `stats2Cell`/`≈U` 第二行渲染 wire 语义（`null`=暂无、字符串含 `"0"`=真值）核对成立。
9. **回归**：独立复跑 `python3 -m pytest backend/tests -q -p no:cacheprovider` → **1419 passed**
   （90.77s）；`node frontend/self-check.js` → **全部通过**。与五份 handoff 声明的数字一致，无回归。

---

## P0（阻塞，REWORK）

### F1 — `_resolve_fresh_preflight` 平仓余额校验方向未反转，close 任务在 live 模式下会被错误
FATAL 停止（`stopped`），且该错误发生在真实划转已执行之后

**位置**：`backend/hedge_open_tasks/service.py:2153-2183`（函数 `_resolve_fresh_preflight`），
问题行在 `:2177-2183` 的 `D.compute_preflight(...)` 调用，具体是 `:2180` 传入的方向参数。

**根因**：平仓现货卖出重设计（本次交付，close-spot-sell-redesign 任务）为消除 `create_task`
与「发单前 fresh preflight」之间的路由漂移（COOKIE 事故根因之一），在 `_resolve_fresh_preflight`
里新增了方向反转变量 `preflight_dir`（forward close → reverse；reverse close → forward），
正确用于 `get_snapshot(task["coin"], preflight_dir, task_type=...)`（`:2171-2174`，这一步的路由
决策 `spot_route` 因此正确）。但紧接着的余额校验调用：

```python
preflight = D.compute_preflight(
    snapshot,
    task["coin"],
    task["direction"],   # <- 应为 preflight_dir；此处仍是未反转的原始持仓方向
    D.Decimal(task["single_amount"]),
    task["target_n"],
)
```

用的是**未反转**的 `task["direction"]`，而不是刚刚算出、已经喂给 `get_snapshot` 的
`preflight_dir`。对照 `create_task`（`service.py:692-698`）——同一个反转变量
（那里叫 `preflight_direction`）被**一致地**同时喂给 `get_snapshot` 与 `compute_preflight`——
这是唯一另一处调用点（`grep compute_preflight(` 全仓库只有这两处），`_resolve_fresh_preflight`
是这个模式里唯一遗漏的一处。

**为什么错方向会产生错误结果**：`compute_preflight`（`domain.py:1170-1179`）按
`direction==DIR_FORWARD` 走「需要 USDT」分支（`required=q×n×price`，
`available=spot_account_usdt` 因为路由已是 `regular_spot`），否则走「需要 base 资产」分支
（`available=snapshot.balances[base]`，即 PAPI 统一账户余额）。forward close 的真实约束是
「卖出 base 资产」，需要检查的是 base 资产是否够（`create_task` 用 `preflight_dir=reverse`
正确命中「需要 base」分支，`available` 读**统一账户**里的真实持仓量）；但
`_resolve_fresh_preflight` 传入未反转的 `task["direction"]="forward"`，命中「需要 USDT」分支，
检查的是**普通现货账户里几乎恒为 0 的闲置 USDT**——与「卖出 base 资产是否够」完全无关。
reverse close 对称地错在另一侧（该查 USDT 却查了 base 资产）。

**实测复现**（独立 repro，构造 forward close 任务、`FakeSnapshot` 统一账户 COOKIE 余额
100000、普通账户 USDT 余额 0，`mode="live"` + 有 `.dispatch` 的假 executor 触发
`_live_dispatch_capable()`）：

```
compute_preflight(direction=forward)  <- 代码实际调用的分支
  required: 2000.0  available: 0  balance_ok: False  rejection: insufficient_balance
compute_preflight(direction=reverse)  <- create_task 用的、本应一致的分支
  required: 1000    available: 100000  balance_ok: True  rejection: None
```

`REJECT_INSUFFICIENT_BALANCE` 在 `PREFLIGHT_FATAL_REASONS`
（`domain.py:326-332`）里——`_resolve_fresh_preflight` 返回 `fatal=True`，
`_dispatch_one_for_task`（`service.py:2272-2274`）据此调用
`_stop_task_fatal_preflight`→`stop_task_fatal`，任务进入**终态 `stopped`**（不是可自愈的
`paused`）。

**实盘后果链**（`_worker_round` 实际执行顺序，`service.py:1428-1441`）：
1. `_ensure_close_spot_balance`（`scheduled_attempt_count==0`）正确核实/划转，
   把 base 资产从统一账户转进普通现货账户——**真实的 `universal_transfer` 已经发生**；
2. 紧接着 `_dispatch_one_for_task`→`_resolve_fresh_preflight` 因为上述 bug 检查了不相关的
   USDT 余额（≈0），几乎必然判定「insufficient_balance」并把任务**永久停止**；
3. 结果：资产已经被划到普通现货账户，但平仓单从未发出，任务停在 `stopped`，
   需要人工介入——这正是这一整条重设计链路要根治的「单腿/半完成」事故模式，
   只是换了个触发点，而且这次是本 bug 自己触发一次真实的资金划转副作用。
4. reverse close 对称受影响（该查 USDT 却查了 base 资产），同样会被错误 FATAL 停止。

**未被现有测试覆盖的原因**：`_resolve_fresh_preflight` 只在
`_live_dispatch_capable()`（要求 `self._live_mode` 为真且 executor 有 `.dispatch`）为真时才被调用；
`test_hedge_cycle_close.py` 的全部平仓用例都是 dry-run（`RecordTransportExecutor`，无
`.dispatch`），所以整条回归套件（1419 passed）里没有任何一条测试实际执行到这个分支——
这是一个测试覆盖盲区，不是「隐藏很深」的极端场景：只要 close_gate（默认开）+ Start gate
（PROJECT_STATE 记录常开）下发生一次真实的立即平仓点击，就会命中。

**修复要求（具体、可执行）**：
1. `backend/hedge_open_tasks/service.py:2180`：把 `task["direction"]` 改为 `preflight_dir`，
   与 `get_snapshot` 保持一致（也与 `create_task` 的既有正确模式一致）。
2. 补一组 live-dispatch 回归测试（`test_hedge_cycle_close.py` 或紧邻文件均可）：
   用有 `.dispatch` 的假 executor + `mode="live"` 直接调用 `_resolve_fresh_preflight`
   （或走 `_dispatch_one_for_task`），分别覆盖 forward close 与 reverse close 两个方向，
   断言「统一账户有仓、普通账户/统一账户对侧资产接近 0」时 `ok=True`
   （不误判 fatal insufficient_balance）——这是本次唯一的根因站点（全仓库 `compute_preflight(`
   只有两处调用，另一处 `create_task` 已经正确），补一处即可，不需要扩大范围。
3. 全量回归（`pytest` + `self-check.js`）确认无回归后再提交复审。

**范围分类**：`in-range`（本次交付 close-spot-sell-redesign 任务引入，文件在本次评审范围内）。

---

## 非阻塞观察（仅记录，不构成 REWORK，不要求本轮处理）

- **O-1** `PROJECT_STATE.md` 的 `[RESOLVED][OPERATIONS][2026-08-05]` 条目仍写「Remaining gates:
  live backfill still requires Human authorization」，但
  `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/backfill-live-20260805-163913.audit.json`
  显示实盘回填已于同日 16:39 执行完成（9 cycle 行、52 attempt 全覆盖）。文档滞后于事实，建议
  Bookkeeper/下一次接触 PROJECT_STATE.md 时顺手更正，不影响本次功能验收。
- **O-2** `frontend/index.html` 的 `renderHedgeCloseInputs` 函数头注释仍写「后端平仓任务未实现：
  确认后提示「后端开发中」，不发真实请求」，但其下方代码早已走真实 `submitHedgeClose` POST——
  注释过期，纯措辞问题（dispatch 明确「不找吹毛求疵」，仅记录不要求本轮改）。
- **O-3** `service.py`/前端多处新增 `print(...)`/`console.log(...)` 诊断日志（`[HEDGE-CREATE]`/
  `[HEDGE-CLOSE-SUBMIT]`），用于定位「平仓任务点击后未创建」问题，功能无害但为永久噪音输出；
  是否保留由 Human/后续 stage 决定，不阻塞本次验收。

---

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md`（本交接件）
  2. `backend/hedge_open_tasks/service.py`（`_resolve_fresh_preflight:2153-2183`、对照
     `create_task:690-698` 的既有正确模式）
  3. `backend/hedge_open_tasks/domain.py`（`compute_preflight:1028-1179`、
     `PREFLIGHT_FATAL_REASONS:326-332`）
- 执行：修复任务（原实现团队/deepseek）按上方「修复要求」三步修复 F1，全量回归后提交复审
- 关卡：F1 修复 + 回归绿 → 本评审判定的窄范围复审（直接回本次 review-2，按 AGENTS.md §8
  「narrow review-2 finding 直接回 review-2」；本次为 review-1+review-2 合一，故复审仍由本评审角色
  一次性核验）；本评审不授权任何实盘操作，close_gate/Start gate 现状不变
- 不能假设的事实：本次交付其余部分（周期表/成本隔离/reduceOnly/完成判定/划转时序/USDT 回流/
  费率统计/前端）均核对通过，只有 F1 一处需要修复；F1 修复前，close_gate 默认开 + Start gate 常开
  意味着实盘环境下任何一次真实「立即平仓」点击都可能触发 F1 描述的错误停止 + 已发生的资金划转
  副作用——建议 Human 在 F1 修复前避免对 forward 持仓使用「立即平仓」功能（reverse 方向同样受影响）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-hedge-position-cycle-v1-review-sonnet5
执行结果: completed（完成）
结果摘要: 综合评审完成（review-1+review-2 合一）。周期表/成本隔离/reduceOnly/完成判定/划转时序/费率统计/前端逐项核对通过，回归 1419+self-check 全绿复现。发现 1 处 P0：_resolve_fresh_preflight 平仓余额校验方向未反转（service.py:2180），live 模式下会把 close 任务错误 FATAL 停止，且发生在真实划转之后；已用独立 repro 实测复现。判 REWORK，修复要求具体可执行。
产物: [reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md]
检查结果: [周期表/回填/聚合拆分/merge P0-1 pass；开平仓成本隔离 pass；方向反转+reduceOnly pass；完成判定（合约无仓核实优先+fail-closed）pass；划转时序+USDT回流+白名单冻结 pass；费率/利息统计（诚实降级+单位换算）pass；前端（真实POST+提前量检测+历史页+徽标）pass；回归1419+self-check全绿 pass；资金安全深挖 fail（F1，live 平仓余额校验方向反转遗漏，实测复现，FATAL 停止+已执行划转副作用）]
阻塞项: [F1：backend/hedge_open_tasks/service.py:2180 平仓余额校验方向未反转，修复要求见本交接件 P0 节]
本地北京时间: 2026-08-06 10:52:25 CST
下一步模型: Bookkeeper（核验本评审 + 裁定 F1 修复路由；当前无活跃 stage/status.json，按本 stage 沿用的 Human 直接授权代记模式处理，或由 Human 指定下一步）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md；执行：路由 F1 修复任务（backend/hedge_open_tasks/service.py:2180，单行方向参数修正 + live-dispatch 回归测试补充）；关卡：修复+全量回归绿后复审，复审通过后方可考虑实盘启用「立即平仓」
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md（P0 节 F1）
修复要求: reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md（P0 节「修复要求」三步）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## 复评 Verification（sonnet5 本人追加，2026-08-06；无活跃 stage/Bookkeeper，Human 本会话直接授权复评）

- 复评对象：`reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-close-preflight-dir-fix.handoff.md`
  （修复 F1 的 Implementer 交接件，`base_sha` 同 `08127aabbb15548f46484257614f34f384c6cac8`，
  `delivery_sha=pending`，工作树未提交，沿用本 stage 一贯操作模式）。
- 复评方法（独立核实，非采信交接件自述）：
  1. 读取实际代码：`backend/hedge_open_tasks/service.py:2177-2183`，确认 `D.compute_preflight`
     第 3 参已由 `task["direction"]` 改为 `preflight_dir`（与上方 `get_snapshot` 同一反转变量），
     且这是唯一改动点——`grep compute_preflight(` 全仓库仍只有 `create_task`（既有正确）与
     `_resolve_fresh_preflight`（本次修复）两处调用，方向处理现已一致。
  2. 独立复跑：`python3 -m pytest backend/tests -q -p no:cacheprovider` → **1421 passed**（90.95s）；
     `node frontend/self-check.js` → **全部通过**（139 段）。数字与交接件声明一致。
  3. 读取新增两个用例（`test_hedge_cycle_close.py:869-908`）：`test_live_fresh_preflight_forward_close_checks_base_asset`
     / `test_live_fresh_preflight_reverse_close_checks_usdt`，确认二者用真实 `mode="live"` +
     带 `.dispatch` 的假 executor（满足 `_live_dispatch_capable()`）直接调用生产代码
     `_resolve_fresh_preflight`，非 dry-run 模拟。
  4. **受控负向验证（关键）**：把 `service.py:2180` 临时还原为修复前的 `task["direction"]`
     （单行替换，验证后立即用 `diff` 确认与修复版逐字节一致地还原，未污染工作树），单独
     重跑这两条新用例——**两条均失败**，失败断言与我 review-1 阶段的独立 repro 完全一致
     （`fp.ok is False`，`fp.fatal is True`，`fp.rejection == 'insufficient_balance'`，
     `test_live_fresh_preflight_reverse_close_checks_usdt` 的失败输出逐字确认）。这证明两条新
     用例真实钉住了 F1 缺陷，不是摆设断言。随后确认 `service.py` 已还原为修复版（`diff` 零差异），
     `test_hedge_cycle_close.py` 全量 36 用例复跑通过。
  5. 范围核对：`git status --short` 与 review-1 阶段核对时的文件列表一致（无新增文件路径），
     确认本轮修复未触碰前端/`ledger_flow`/白名单/close 完成判定/划转时序等本次评审已通过的部分。
- 行为不变性核对：`preflight_dir` 对 `task_type=open` 任务恒等于 `task["direction"]`
  （反转分支只在 `task_type==CLOSE` 时触发），故本次修复对开单任务路径零行为差异——与交接件
  自述一致。
- 结论：F1 已彻底修复且有真实回归测试防复发；本轮修复未引入新文件改动、未扩大范围、未触碰
  Allowed Files 之外内容；不触发 §8「同根因刹车」（首轮修复即通过，非连续两轮同根因）。
  评审升级为 **ACCEPT**。

```text
[TASK_RESULT v2]
任务 ID: 2026-08-hedge-position-cycle-v1-review-sonnet5（复评）
执行结果: completed（完成）
结果摘要: F1 复评通过。service.py:2180 已按要求改为 preflight_dir；两条新 live 回归用例独立核实——受控还原旧代码后二者确实失败（失败签名与原评审 repro 完全一致），证明测试真实钉住缺陷而非摆设；全量 1421 passed + self-check 全绿独立复现；范围核对无扩大。本 stage 四功能 + 修复链全部核对通过，转 ACCEPT。
产物: [reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md（本节）]
检查结果: [一行修复位置与内容 pass；两处 compute_preflight 调用方向处理一致 pass；新增 live 回归用例真实触发 _live_dispatch_capable 路径 pass；受控还原验证测试真实钉住缺陷 pass；回归 1421+self-check 全绿独立复现 pass；开单任务行为不变性 pass；范围核对无扩大 pass]
阻塞项: [none]
本地北京时间: 2026-08-06 11:20:00 CST
下一步模型: Human（决策者）
下一步任务: 读取：reports/agent-runs/2026-08-hedge-position-cycle-v1/evidence/2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md（含复评节）；执行：Human 决定本 stage 收尾方式（提交/合并/是否需要 Bookkeeper 补记 status.json）；关卡：合并、部署、close_gate 实盘启用均需 Human 单独明确授权，本评审不构成该授权
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
[/TASK_RESULT]
```

