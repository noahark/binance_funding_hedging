# Task Handoff: 01-plan-review-retry

## Source Report (author-only; immutable after task end)
- task_id: `01-plan-review-retry`
- role: Reviewer（跨 provider 只读计划评审 / HIGH_RISK 实现前计划评审）
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-12-hedge-slippage-spread-v1`
- status_revision: `2`（与 `status.json` 一致）
- created_at: `2026-08-12 07:41:28 CST`
- base_sha: `7da67bc87261386c117b98f2b63c6ac6083fd291`（`git rev-parse` 命中；与 `status.json` 一致）
- delivery_sha: `none`（计划评审为只读、实现前评审；`status.json.delivery_sha` 为 `null`）

### 任务背景（retry）

前一任务 `01-plan-review` 因 Bookkeeper dispatch 的 Allowed Files 漏列方向映射权威
`backend/hedge_open_tasks/domain.py` 而被拒收（packet correction，非交付缺陷）。本 retry 版
仅补齐该只读输入，不改变 Human 要求、计划、验收或 `rework_count`（`status.json.rework_count`
仍为 `0`，符合 `AGENTS.md` §8「计划评审不触碰 rework_count / pre-dispatch packet correction
豁免」）。`base_sha` 未变，源码与测试内容与上一评审完全相同，故行号引用保持有效。

### 评审范围与口径

本任务只读评审 dispatch（`01-plan-review-retry.dispatch.md`）所述最小实现计划：把
`HedgeOpenStore.cycle_slippage_pct` 从「合约腿成交均价对 task preflight `est_price`」改为
「同一周期、同一 `task_type` 的现货腿与合约腿真实成交数量加权均价之差」，统一公式为
`(卖出腿加权均价 − 买入腿加权均价) / min(两腿加权均价) × 100`，全程 `Decimal`、保存四位百分数
文本、不再读 `est_price`，缺腿降级为 `None`；预计仅改 `backend/hedge_open_tasks/store.py`
与最少后端测试，不改 schema/API 字段/前端/实盘库/服务/闸门/订单/资金/历史记录。本任务不实现代码。

只读读取：`AGENTS.md`、retry dispatch、`ACTIVE.json`、`PROJECT_STATE.md`、`status.json`、
`agents/roles.md`（Reviewer + Task Handoff Evidence Contract）、`agents/skills/code-reviewer.md`、
`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、
`backend/hedge_open_tasks/domain.py`（方向映射权威，本版补齐）、
`backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_cycle_close.py`、`frontend/index.html`。

### 验收检查逐项裁决（dispatch Acceptance Checks）

1. **pass — 公式仅用两腿真实成交加权均价，完全不依赖 `est_price`。**
   计划明确「不再读取 `est_price`」并复用 `_cycle_leg_basis_locked`（`store.py:2347-2377`），
   该函数只用 `cumulative_base_qty` + `cumulative_quote_amt` 算腿均价，从不读
   `preflight_snapshot.est_price`。新 `cycle_slippage_pct` 将弃用现有实现
   （`store.py:2379-2433`，其 `t.preflight_snapshot.est_price` 与 `l.avg_price`/quote 回退
   均针对合约腿单腿对估价）改为两腿均价差。

2. **pass — open/close × forward/reverse 的卖腿/买腿映射与 Human 定义完全一致。**
   权威映射来自本版补齐的只读输入 `domain.direction_to_leg_actions`（`domain.py:730-759`）：
   `forward`→`spot BUY`/`perp SELL`，`reverse`→`spot SELL`/`perp BUY`；`task_type='close'`
   反转双腿（`domain.py:752-753` `spot_side, perp_side = perp_side, spot_side`）。故：
   - forward open：合约 SELL（卖腿）/ 现货 BUY（买腿）✓
   - reverse open：现货 SELL（卖腿）/ 合约 BUY（买腿）✓
   - forward close：现货 SELL（卖腿）/ 合约 BUY（买腿）✓
   - reverse close：合约 SELL（卖腿）/ 现货 BUY（买腿）✓
   与计划逐项一致。close 方向沿用持仓行方向（`service.py:766-767`；`service.py:888-892`
   `preflight_direction` 仅用于余额检查，不改变腿向），故 close 腿向由 `task_type` 反转决定。

3. **pass — 分母为两腿加权均价较低者；结果 ×100、用 `Decimal`、保存四位百分数文本。**
   JSTUSDT 实盘样本手算精确命中（`PROJECT_STATE.md` Live Risk 数据源）：
   - reverse open：卖=现货 `0.09808666…`、买=合约 `0.09786`、min=`0.09786` →
     `(0.09808666…−0.09786)/0.09786×100 = +0.23160…%` → `+0.2316%` ✓
   - reverse close：卖=合约 `0.10036`、买=现货 `0.10058`、min=`0.10036` →
     `(0.10036−0.10058)/0.10036×100 = −0.21921…%` → `-0.2192%` ✓
   四位文本由现 `f"{pct:.2f}"`（`store.py:2433`）改为四位；前端早已以
   `Number(...).toFixed(4)` 渲染（`frontend/index.html:5340-5341`），四位文本与展示一致。

4. **pass — 跨多个 attempt 分别聚合两腿；任一腿缺失/非正数/无真实成交均价→`None`，不臆造零。**
   `_cycle_leg_basis_locked` 以 `CAST(cumulative_base_qty AS REAL) > 0` 过滤（`store.py:2358`），
   仅已知且非零 notional 入均价分母（`quote is not None and quote != 0`，`store.py:2370`），
   无可定价成交时 `avg_price=None`（`store.py:2373`）。新函数取两腿均价，任一为 `None` 即整体
   `None`，与金额字段「未知不归零」纪律（`_num_or_none`，`store.py:367-380`）一致。两腿分别
   按 `(cycle_id, task_type, leg)` 聚合，天然覆盖跨 attempt 数量加权。

5. **pass — 最小实现边界足够，无需 schema/API/前端/service 功能逻辑改动。**
   `cycle_slippage_pct` 由 `_finalize_close_task` 以 `(cycle_id, task_type)` 调用
   （`service.py:1925-1926`），返回值原样写入 `open_slippage`/`close_slippage` 列
   （`service.py:1958-1959` → `store.py:2287`）。字段与 API 形状不变（`list_close_logs`
   `store.py:2293-2301`、`get_close_logs` `service.py:978-980`）；前端值渲染已兼容（见检查 3）。
   故只改 `store.py` 的 `cycle_slippage_pct`（及必要的内部辅助）即可，`service.py` 调用点无需动。

6. **pass — 测试计划覆盖四映射、数量加权、缺腿降级与 JSTUSDT 两期望值，且能反证旧 `est_price` 回归。**
   JSTUSDT reverse close 的 task snapshot 为 `no_preflight_snapshot`（`PROJECT_STATE.md`：旧口径
   下平单值为 NULL），钉住 `-0.2192%` 即证明旧 `est_price` 路径已不复返（旧路径必返回 `None`）。
   四向映射 + 跨 attempt 两腿数量加权 + 缺腿降级 `None` + 两 JSTUSDT 样本，构成对方向/单位/精度/
   加权/降级的完整钉死。

7. **pass — 明确排除实盘库补录、服务重启、部署及任何资金/订单动作。**
   计划第 4 点与 dispatch Stop 一致；历史 JSTUSDT 是否补录「由 Human 另行决定，模型不得直接改
   实盘库」（`PROJECT_STATE.md` Live Risk）。本计划只动计算函数与离线测试，保留这些为 Human
   独立授权关卡。

8. **pass — 已枚举 stage 收口须同步的旧口径残留位（不能把旧错误口径留在活文档）。**
   本次仅评审实现计划；下列旧 `est_price`/「负=成交优于估价」口径文本不在实现改动范围内，须按
   `AGENTS.md` §7「交付收口同步 docs 活文档」在 stage 收口时一并更正（活文档义务由 Bookkeeper
   在收尾时承担）：
   - `frontend/index.html:5339`（注释）、`:5340-5341`（列标题/tooltip）、`:5361-5362`（表头 tooltip，
     仍写「成交均价 vs 开/平仓估价(est_price)」「负=成交优于估价」）、`:1618`/`:1624`（副标题/注释）；
   - `backend/hedge_open_tasks/store.py:196-197`（`open_slippage`/`close_slippage` 列的 schema 注释，
     属本次在改文件，宜顺手更正为两腿价差口径——仅注释、非结构变更）；
   - `backend/hedge_open_tasks/service.py:1924`（`_finalize_close_task` 内注释，出计划声明边界，
     收口同步）。
   前端「值渲染」无需改动（已 `toFixed(4)` 且 `null→—`）；上述仅为描述性文本的口径同步。

### 实现侧提示（非计划缺陷，供实现者避免遗漏，不构成 REWORK）

- **方向来源**：新 `cycle_slippage_pct(cycle_id, task_type)` 签名不含 `direction`，须由 `cycle_id`
  读 `hedge_open_cycle.direction`（`store.py:172`，列已存在）以选定卖/买腿；保持签名不变可避免
  `service.py` 改动（与检查 5 一致）。卖/买腿选定须与 `domain.direction_to_leg_actions(direction,…,task_type)`
  的 `spot_side`/`perp_side` 同源（本检查 2 已逐项核对）。
- **既有断言需随公式更新**：`test_hedge_cycle_close.py:230` 与 `:421` 现断言 `open_slippage is None`
  （RecordTransportFake 双腿均以价 1、量 0.5 成交，旧口径无 `est_price` 故 None）。新两腿公式下等价
  成交 → 真值 `"0.0000"`（非 None）。这两处属计划「最少后端测试」范围内必须更新的回归断言。
- **分母零守卫**：两腿均价均来自 `priced>0` 且 `quote≠0`，理论上为正；实现仍宜在 `min(两腿均价) <= 0`
  时返回 `None`（防御性，与「不臆造」一致）。

### 结论

`ACCEPT`。八项验收检查全部通过（检查 5、8 附实现/收口同步说明）。公式、方向映射（以本版补齐的
`domain.py` 为权威）、单位/精度/加权、降级、最小边界、测试覆盖与实盘动作排除均满足 Human 已确认的
产品含义，且测试能阻止旧 `est_price` 算法回归。无 REWORK 发现。本 retry 仅补齐只读输入，结论与
评审实质与前次一致。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`、`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 执行：Bookkeeper 核验本 handoff 的源 SHA-256（`BOOKKEEPER_APPEND_ONLY` 标记前字节）与 `task_id`/`role`/`stage_id`/`base_sha` 同 `status.json` 及 `git rev-parse` 一致，确认 `ACCEPT` 与八项验收检查，随后准备实现任务 dispatch（目标仅 `backend/hedge_open_tasks/store.py` + 最少后端测试，沿用 `base_sha=7da67bc…`）
- 关卡：Bookkeeper 核验通过后，由 Human 启动实现任务终端；实现完成后再走 review-1 + review-2（HIGH_RISK）
- 不能假设的事实：实现不得改 schema/API 字段/前端/`service.py` 功能逻辑/实盘库/服务/闸门；历史 JSTUSDT 补录由 Human 另行授权；`cycle_slippage_pct` 须由 `cycle_id` 自取 `direction` 选腿（与 `domain.direction_to_leg_actions` 同源）；`test_hedge_cycle_close.py:230/:421` 须随公式更新；检查 8 所列旧口径文本由 stage 收口同步

## Human Brief / Console Receipt Source

```text
[TASK_RESULT v2]
任务 ID: 01-plan-review-retry
执行结果: completed（完成）
结果摘要: 跨 provider 只读计划评审（retry，补齐 domain.py 只读输入）完成：两腿加权价差公式、四向卖/买腿映射（以 domain.py 为权威）、min 分母×100/Decimal/四位文本、跨 attempt 聚合与缺腿降级、最小边界与测试覆盖（含 JSTUSDT +0.2316%/-0.2192%）、实盘动作排除均通过；前端值渲染已兼容，旧口径文案列为收口同步项。结论 ACCEPT。
产物: [reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md]
检查结果: [
1. pass 公式仅用两腿真实成交加权均价，完全不读 preflight est_price；
2. pass open/close×forward/reverse 卖/买腿映射与 domain.direction_to_leg_actions 一致；
3. pass 分母为两腿均价 min；×100、Decimal、四位文本（JSTUSDT +0.2316%/-0.2192% 手算命中）；
4. pass 跨 attempt 分别聚合两腿，任一腿无真实正数均价→None，不臆造零；
5. pass 最小边界充分：仅改 store.py(+测试)，无 schema/API/前端/service 功能逻辑改动；
6. pass 测试覆盖四映射+数量加权+缺腿降级+JSTUSDT 两期望值，且反证旧 est_price 回归；
7. pass 明确排除实盘补录/重启/部署及资金订单动作，保留 Human 独立授权；
8. pass 已枚举旧口径残留位（前端 tooltip/注释、store.py schema 注释、service.py 注释）供 stage 收口同步
]
阻塞项: [none]
评审结论: ACCEPT
问题记录: none
修复要求: none
本地北京时间: 2026-08-12 07:41:28 CST
下一步模型: codex（本阶段 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json；执行：Bookkeeper 核验本 handoff 源 SHA-256 及 task_id/role/stage_id/base_sha 一致并确认 ACCEPT，随后准备实现任务 dispatch（仅 store.py + 最少后端测试）；关卡：Bookkeeper 核验通过后由 Human 启动实现任务终端
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `555fc7af73837848d04a50fc3a50c67beb5b47f5731eeb21fd766e0dfc894277`
- verified_at: `2026-08-12 07:44:17 CST`
- status_revision_checked: `2`
- verification_result: `ACCEPTED`
- identity_check: `pass`（task_id、role、target model、stage_id、status revision、base_sha、
  delivery_sha 均与 dispatch/status/Git 已存在基线一致）
- scope_check: `pass`（Source Report 列出的全部只读路径均在 retry dispatch Allowed Files；唯一写入
  为预检时不存在的本 handoff）
- result_check: `pass`（`completed（完成）`、八项 pass、明确 `ACCEPT`、问题/修复均 none、
  Human Brief 与 Required Reading 路由一致）
- reproducible_commands:
  - `git cat-file -e 7da67bc87261386c117b98f2b63c6ac6083fd291^{commit}`
  - `perl -0ne '$i=index($_,"<!-- BOOKKEEPER_APPEND_ONLY:"); die if $i < 0; print substr($_,0,$i)' reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md | shasum -a 256`
  - `rg -n '^执行结果:|^评审结论:|^问题记录:|^修复要求:' reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/01-plan-review-retry.handoff.md`
- next_state: 计划评审关卡通过；准备 `02-implement` dispatch，status revision 3，
  `rework_count=0`，由 Human 启动新的 Codex 实现终端。

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或 Human Brief。
