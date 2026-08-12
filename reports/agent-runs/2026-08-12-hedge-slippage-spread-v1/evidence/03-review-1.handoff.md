# Task Handoff: 03-review-1

## Source Report (author-only; immutable after task end)
- task_id: `03-review-1`
- role: `Reviewer`（review-1，跨 provider 只读，HIGH_RISK）
- target model: `opus5`（provider `anthropic`；实现作者为 `codex`/`openai`，provider 隔离成立）
- stage_id: `2026-08-12-hedge-slippage-spread-v1`
- status_revision: `4`（与 `status.json` 一致）
- created_at: `2026-08-12 08:16:44 CST`
- base_sha: `7da67bc87261386c117b98f2b63c6ac6083fd291`
- delivery_sha: `db552a7b224fcebc84bb23a087ff2b28a350bf04`

### 评审范围与方法

只读评审固定区间 `7da67bc..db552a7`。区间内 `7a9fa19`/`336376d`/`6aa9dd7` 为本阶段控制提交
（dispatch、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`、计划评审证据），按 `AGENTS.md` §8
「评审范围口径」仅作上下文；受审产品交付是唯一 delivery commit `db552a7`。

受审文件均以 `git show <sha>:<path>` / `git diff <base>..<delivery>` 读取，未以移动 HEAD 或
未提交工作树替代交付事实。核对：`git rev-parse HEAD` = `34750c7`（后续 bookkeeper 控制提交），
`git diff --stat db552a7 -- backend` 为空，故本机 `backend/` 与 delivery 逐字节一致，测试即在
交付代码上运行；工作区 `frontend/index.html`、`frontend/self-check.js` 的未提交改动不在 delivery
commit，未被当作受审事实，评审全程未修改任何文件（唯一写入为本 handoff）。

### 验收检查逐项裁决（dispatch Acceptance Checks）

1. **pass — 交付范围与状态迁移合规。**
   `git show --stat db552a7` 恰为五路径：`backend/hedge_open_tasks/store.py`、
   `backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_cycle_close.py`、
   `reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/02-implement.handoff.md`、
   同阶段 `status.json`。`status.json` 在该提交中的唯一变化是
   `current_task.state: "dispatched" → "reported"`（`git show db552a7 -- .../status.json`），
   符合 `AGENTS.md` §7「实现者只能把自己的任务从 dispatched 移到 reported」。
   控制提交对 `PROJECT_STATE.md`（21 行）等的改动未计入产品交付。

2. **pass — 公式、四向映射、min 分母、×100、四位 Decimal 正确。**
   `store.py:2379-2419`：由 `cycle_id` 读 `hedge_open_cycle.direction`，经
   `D.direction_to_leg_actions(direction, D.POS_MODE_BOTH, task_type)` 取 `spot_side`
   选卖/买腿；`sell_price/buy_price` 与 `denominator = min(spot_price, perp_price)`，
   返回 `f"{(sell - buy) / denominator * 100:.4f}"`，全程 `Decimal`。
   `POS_MODE_BOTH` 为硬编码但安全：`domain.py:742-753` 中 `position_side_mode` 只影响
   `perp_position_side`（`BOTH`/`LONG`/`SHORT`），不影响 `spot_side`/`perp_side`，本函数
   也不使用 `perp_position_side`。四向映射（`domain.py:742-753`）：forward open = 现货 BUY /
   合约 SELL；reverse open = 现货 SELL / 合约 BUY；`task_type='close'` 反转双腿。
   与 Human 口径逐项一致。
   均价精度无损：`_cycle_leg_basis_locked` 以 `D.fmt_decimal`（`domain.py:1607-1620`，
   定点无科学计数、不截断有效位）输出，本函数再以 `_num_or_none` 解析回 `Decimal`，
   JSTUSDT 的 `0.09808666666666666666666666667`（28 位有效数字）往返无损。

3. **pass — 跨 attempt 聚合与降级不存在假零或异常泄漏。**
   两腿分别调用 `_cycle_leg_basis_locked(cycle_id, task_type, leg)`（`store.py:2347-2377`），
   SQL 以 `(a.cycle_id, t.task_type, l.leg)` 聚合并过滤
   `CAST(l.cumulative_base_qty AS REAL) > 0`，均价 = Σ已知 quote / Σ已定价 qty，
   天然覆盖跨 attempt 数量加权。
   降级：无周期、`direction ∉ ALL_DIRECTIONS`、`task_type ∉ ALL_TASK_TYPES`、任一腿
   `avg_price` 为 `None`/不可解析/非有限/非正、分母非正 → `None`。「未知」永远不变成 `0`：
   `"0.0000"` 只可能来自两腿都有真实正均价且差为零。异常面：`ALL_DIRECTIONS` 前置判断
   使 `direction_to_leg_actions` 的 `invalid_field` 抛出不可达；`_num`/`_num_or_none`
   捕获 `InvalidOperation`；`priced > 0` 守除零。
   锁与事务：`with self._lock, self._conn:` 内一次性读取 direction 与两腿基差，构成一致
   快照（旧实现的单条 SQL 无此需求，新实现三次读取放在同一事务内是正确的收紧）；
   内部只调 `_cycle_leg_basis_locked`（无锁版），不重复进入 `self._conn` 上下文；
   `self._lock` 为 `RLock`，无死锁面；块内全部为 SELECT，无写入副作用。

4. **pass — JSTUSDT 与零价差被真实测试钉住。**
   `test_hedge_store.py:test_cycle_slippage_matches_jst_reverse_open_and_close` 以真实成交
   数据写入两腿并断言 open `"0.2316"`、close `"-0.2192"`；该 close 任务
   `preflight_snapshot=None`，旧 `est_price` 路径在此必返回 `None`，故该断言同时反证旧口径
   回归。四向映射参数化用例的期望值全为 `"2.0000"`，若卖/买腿被互换则结果为 `"-2.0000"`，
   具备判别力。跨 attempt 用例（spot 105 / perp 103 → `"1.9417"`）钉住数量加权。
   零价差：`test_hedge_store.py` 的 `"0.0000"` 断言 + `test_hedge_cycle_close.py:230/421`
   经 `_finalize_close_task` 全链路写入 `close_log` 后断言 `open_slippage == "0.0000"`，
   覆盖了「真实零价差不得退化为缺失」的集成缝。
   独立复算（未依赖交付代码）：`(0.09808666666666666666666666667-0.09786)/0.09786*100`
   → `0.2316`；`(0.10036-0.10058)/0.10036*100` → `-0.2192`；`(105-103)/103*100` → `1.9417`。

5. **pass — `est_price` 计算路径已删除，契约未变。**
   `git diff` 显示 `preflight_snapshot`/`est_price` 的读取、`diff_sum/est_sum` 与
   `f"{pct:.2f}"` 整段被移除；delivery SHA 下 `git grep` 确认生产代码中已无任何滑点相关
   `est_price` 引用。函数签名 `cycle_slippage_pct(cycle_id, task_type) -> str | None` 未变，
   `service.py:1925-1926` 两个调用点与 `insert_close_log` 的 `open_slippage`/`close_slippage`
   列、`list_close_logs` 投影、`get_close_logs` API 形状均未改动；schema 变化仅为
   `store.py:196-197` 的 `--` 行内注释（SQLite 注释不进入列定义，`_ensure_columns`
   的 `("open_slippage","TEXT")` 未变，既有库无迁移影响）。
   `json`、`InvalidOperation` 两个导入在文件其他位置仍被使用，未产生孤儿导入。

6. **pass — 只读复跑两级测试全绿。**
   - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py -q` → `131 passed in 3.50s`
   - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q` → `1763 passed in 143.92s`
   - 复跑后 `git status --short` 仍只有既有两个前端未提交改动，未产生 `__pycache__`/`.pytest_cache` 写入。

7. **pass — 无订单、资金、schema、服务控制或恢复链副作用。**
   变更集中在一个只读查询函数与两份离线测试；未触碰下单、划转、借还、闸门、凭证、
   worker 恢复链、实盘数据库。本次评审自身未读写实盘库、未控制服务。
   既有调用者仅 `_finalize_close_task`，其 `insert_close_log` 已包在 `try/except` 中
   （结算日志失败不阻塞「周期已关」），本函数返回 `None` 时行为与既有 `None` 分支一致。

8. **pass — 发现已分类并附证据（见下节）。**
   两条记录：一条按 `AGENTS.md` §1「受保护影响但可达性未决 → 具名上交 Human，不作无据
   `REWORK`」处理；一条为 `pre-existing-release-critical`，附早于 `base_sha` 的引入提交。
   无 `in-range` 阻塞缺陷。

### 问题记录（发现与分类）

**O-1 `[in-range][具名上交 Human，不阻塞本轮]` 合约腿「有 `avg_price` 但 `cumulative_quote_amt`
为 NULL」时，滑点仍显示 `—`。**
- 事实：新实现的两腿均价完全来自 `_cycle_leg_basis_locked`，该函数只读
  `cumulative_quote_amt`（`store.py:2352-2372`）；被删除的旧实现原本以
  `l.avg_price` 优先、`cumulative_quote_amt / qty` 兜底（见 `git diff` 删除行）。
- 证据锚点（均为当前可执行/已记录事实，非假设）：
  `backend/tests/test_hedge_store.py:1453-1487`（既有测试直接构造该形态：
  `resolve_leg_from_query(..., quote_amt=None, avg_price="50123.45")` →
  `avg_price` 落库、`cumulative_quote_amt` 为 `None`）；
  `backend/services/live_hedge_executor.py:149,158-172`（币安 2026-07-14 起 UM POST 不再
  返回 quote/avgPrice，靠 order-detail GET 补，其 `cumQuote` 未必在场）；
  `PROJECT_STATE.md` Open Follow-ups「Perp average price can read blank」。
- 实际影响：此形态下合约腿均价为 `None` → 滑点返回 `None`，历史页该列显示 `—`。
  它**不造假数**（fail-closed，与「未知不归零」纪律一致），且同一行的「合约开单均价 /
  合约平单均价」由同一个 helper 供数，同样显示 `—`，展示自洽、无自相矛盾读数。
  但它意味着本次修复对该形态的周期**不产生数值**，即 Live Risk 里「平单滑点显示为 `—`」
  在这一形态下未必被完全关闭。
- 为何不作 `REWORK`：该数据源口径由已 `ACCEPT` 的跨 provider 计划评审明确批准
  （`01-plan-review-retry.handoff.md` 检查 4），交付严格符合其 dispatch Goal；且判定它是否
  在真实周期上发生，需要读取实盘库——本任务只读且 Allowed Files 不含实盘库，属
  `AGENTS.md` §1 所述「只读评审者无法取得必要实盘证据」的情形。按该条：具名上交，不作
  无据 `REWORK`。
- 重开触发条件：Human 在历史页看到某已平仓周期的「合约均价」有值而「滑点」为 `—`，
  或授权一次只读核对确认存在 `avg_price` 非空且 `cumulative_quote_amt` 为 NULL 的成交腿。
  届时最小修法方向是让均价来源在 quote 缺失时回落到「`avg_price × qty` 加权」；注意该
  helper 同时供给 `open_avg_price`/`spot_*_avg` 四列，改动会同步改变这些列的口径，
  应作为独立一轮评估，不宜在本轮夹带。

**O-2 `[pre-existing-release-critical]` 前端滑点列的 tooltip 与注释仍写旧 `est_price` 口径，
且符号解释与新口径相反。**
- 引入提交：`97ecb7f7`（2026-08-06），早于 `base_sha` `7da67bc`；文件
  `frontend/index.html` 不在 delivery commit 内。`git blame -L 5339,5341 db552a7` 与
  `git blame -L 5360,5363 db552a7` 已核实。
- 事实：`frontend/index.html:5361-5362` 表头 title 为「成交均价 vs 开/平仓估价(est_price)
  的偏离率 %（负=成交优于估价）」，`:5339` 注释同口径；`backend/hedge_open_tasks/service.py:1924`
  注释同族。交付后该列语义为「两腿真实成交价差 %，卖价高于买价为正」——**负号的含义与
  tooltip 所写正好相反**。
- 为何按 release-critical 上交而非阻塞：值渲染无需改动
  （`index.html:5340-5341` 已 `toFixed(4) + '%'`，`null → —`；`classForSignedNumber`
  正数绿、负数红，在新口径下反而是正确的方向），不涉及订单、资金动作，不改变任何计算；
  但 `AGENTS.md` §10 明确 Human 不读代码、只读界面，一个符号解释相反的 tooltip 会直接
  误导账务含义的人工判读，故应在合并/发布前完成文本同步。该项已被本阶段 dispatch 具名
  为后续文本同步任务，并落在 `AGENTS.md` §7「交付收口须同步 docs 活文档」的 Bookkeeper
  收尾义务内；本条只是确认它**尚未修复**，不得由本轮 `ACCEPT` 推定已完成。

**O-3 `[nit][不需处理]`** 真实为负但绝对值 `< 0.00005%` 的价差会被格式化为字符串
`"-0.0000"`（如两腿 `0.999999999` 与 `1`）。它是四位舍入后的真值而非假零；前端
`Number("-0.0000").toFixed(4)` 渲染为 `0.0000`、`classForSignedNumber` 判为 `muted`，
无展示异常。仅记录，不建议本轮改动。

**范围说明**：历史 `hedge_open_cycle_close_log` 既有行不会被本次交付重算，JSTUSDT 那条
历史记录仍保留旧值——补录须 Human 单独授权（`PROJECT_STATE.md` Live Risk 原文），
不得由本轮 `ACCEPT` 推定已修正历史数据。

### 结论

`ACCEPT（接受）`。八项验收检查全部 `pass`，无 `in-range` 阻塞缺陷。公式、四向腿映射、
min 分母、×100 与四位 `Decimal` 文本、跨 attempt 数量加权、缺腿/非法/非正降级、`est_price`
路径移除、契约与调用者不变均已在固定 `base_sha..delivery_sha` 上逐项核实，两级后端测试
只读复跑 131 / 1763 全绿。O-1 具名上交 Human 决定，O-2 为合并/发布前必须完成的文本同步，
二者均不阻塞本轮交付。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`、`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 执行：Bookkeeper 核验本 handoff 源区 SHA-256、任务身份与固定 `base_sha..delivery_sha`，确认 `ACCEPT` 与八项 `pass`，把 O-2 前端/`service.py` 文本同步排入本阶段收尾任务，把 O-1 作为具名事项带入 review-2 与 Human 决策，随后准备 review-2 dispatch（`agents/roles.md` 默认 `sonnet5`/anthropic；实现作者为 `codex`/openai，provider 隔离成立）
- 关卡：Bookkeeper 核验通过后由 Human 启动 review-2 终端；review-2 `ACCEPT` 后仍须 Human 最终业务验收，合并、部署、实盘动作与 JSTUSDT 历史补录各自单独授权
- 不能假设的事实：本 `ACCEPT` 只覆盖 `db552a7` 的代码正确性，不等于历史数据已补录、前端文案已同步、服务已重启或已获合并/部署授权；O-1 未经实盘数据证伪或证实；工作区未提交的 `frontend/index.html`、`frontend/self-check.js` 不属于本交付

## Human Brief / Console Receipt Source

```text
[TASK_RESULT v2]
任务 ID: 03-review-1
执行结果: completed（完成）
结果摘要: 跨 provider 只读 review-1 完成。两腿真实成交加权均价、卖减买、min 分母、×100 与四位 Decimal、四向腿映射、跨 attempt 加权与各类降级均正确；est_price 路径已删除，签名/schema/API/调用者未变。JSTUSDT 0.2316/-0.2192 与零价差已被真实测试钉住，131/1763 项测试只读复跑全绿。结论 ACCEPT，另有两条具名事项不阻塞本轮。
产物: [reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md]
检查结果: [
1. pass delivery 仅含授权五路径，status 仅 dispatched→reported，控制提交未计入产品交付；
2. pass 公式/四向映射/min 分母/×100/四位 Decimal 正确，POS_MODE_BOTH 不影响腿向，均价往返无精度损失；
3. pass 跨 attempt 数量加权，无周期/非法/非正/缺腿一律 None，未知不变零，锁与事务一致且无异常泄漏；
4. pass JSTUSDT 0.2316 与 -0.2192、零价差 0.0000 由真实测试与全链路结算断言钉住，并反证旧 est_price 回归；
5. pass 生产代码已无滑点 est_price 引用，签名、schema 列、API 形状与 service 调用契约未变，无孤儿导入；
6. pass 只读复跑定向 131 passed、全量 1763 passed，无缓存写入且工作区未被改动；
7. pass 无订单/资金/schema/服务控制/恢复链副作用，既有调用者行为不变；
8. pass 发现已分类：O-1 in-range 但受保护影响可达性未决、具名上交 Human；O-2 pre-existing-release-critical（引入 97ecb7f7，早于 base）；O-3 nit
]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md
修复要求: none
本地北京时间: 2026-08-12 08:16:44 CST
下一步模型: codex（本阶段 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json；执行：Bookkeeper 核验源 SHA-256、任务身份与固定 base_sha..delivery_sha，确认 ACCEPT 与八项 pass，把 O-2 文本同步排入本阶段收尾、把 O-1 带入 review-2 与 Human 决策，并准备 review-2 dispatch；关卡：Bookkeeper 核验通过后由 Human 启动 review-2 终端，review-2 ACCEPT 后仍须 Human 最终业务验收
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `16cb9da0cc0e0a3b95d594d207944855e2b73d3cf307529e20d21b6d96141f9c`
- verified_at: `2026-08-12 08:31:29 CST`
- status_revision_checked: `4`
- verification_result: `REJECTED_NON_ADVANCING`
- identity_and_fixed_range_check: `pass`（task_id、role、target model、stage_id、status revision、
  `base_sha..delivery_sha` 与 dispatch/status/Git 一致；八项检查与明确 `ACCEPT（接受）` 在场）
- rejection_basis: Source Report 的 O-1 明确读取并引用
  `backend/services/live_hedge_executor.py:149,158-172`，但 revision 4 dispatch 的 Allowed Files
  未授权该路径；违反 Reviewer file boundary。该文件是 O-1 数据生产缝证据，属于 review-1
  integration seam 所需输入，根因按 Bookkeeper pre-dispatch packet 漏项处理，不接受本 handoff
  的 verdict，不消耗 `rework_count`，不得进入 review-2。
- reproducible_commands:
  - `rg -n 'backend/services/live_hedge_executor.py' reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/03-review-1.dispatch.md reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md`
  - `perl -0ne '$i=index($_,"<!-- BOOKKEEPER_APPEND_ONLY:"); die if $i < 0; print substr($_,0,$i)' reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/03-review-1.handoff.md | shasum -a 256`
- next_state: 创建 `03-review-1-retry`，仅补齐该生产缝文件的只读权限；status revision 5
  保持固定 delivery、`review_1` 与 `rework_count=0`，由 Human 启动新的 Opus 5 只读终端。

## Errata (append-only)

none
