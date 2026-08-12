# Task Handoff: 04-review-2

## Source Report (author-only; immutable after task end)
- task_id: `04-review-2`
- role: `Reviewer`（review-2，只读，HIGH_RISK，`agents/skills/reality-checker.md`）
- target model: `sonnet5`（provider `anthropic`；实现作者为 `codex`/`openai`，provider 隔离成立；
  本终端与 review-1 的 `opus5` 终端无共享上下文，未参与本阶段计划、实现或 review-1）
- stage_id: `2026-08-12-hedge-slippage-spread-v1`
- status_revision: `7`（与 `status.json` 一致）
- created_at: `2026-08-12 09:29:49 CST`
- base_sha: `7da67bc87261386c117b98f2b63c6ac6083fd291`
- delivery_sha: `db552a7b224fcebc84bb23a087ff2b28a350bf04`

### 评审范围与方法

只读评审固定区间 `7da67bc..db552a7`。全程使用 `git show <sha>:<path>` / `git diff <base>..<delivery>`
读取受审内容，未以移动 HEAD 或工作区未提交文件替代交付事实；未修改任何文件（唯一写入为本
handoff）；未读写实盘数据库；未控制、重启或部署任何服务；未执行订单、资金、划转或凭证动作。

独立核对（均为本终端自行执行，未复用任何既有 handoff 的结论）：

1. `git cat-file -e <base>^{commit}` / `<delivery>^{commit}` → 均命中。
2. `git show --stat db552a7` → 恰为五路径：`backend/hedge_open_tasks/store.py`、
   `backend/tests/test_hedge_store.py`、`backend/tests/test_hedge_cycle_close.py`、
   `.../evidence/02-implement.handoff.md`、同阶段 `status.json`。
3. `git diff 7da67bc..db552a7 -- .../status.json` → 唯一变化为
   `current_task.state: "dispatched" → "reported"`，符合 `AGENTS.md` §7。
4. `git diff --stat 7da67bc..db552a7`（完整区间）另含 `PROJECT_STATE.md`、`ACTIVE.json`、三份
   本阶段 dispatch 与两份 evidence（`01-plan-review*`），均为本阶段控制提交，按 `AGENTS.md` §8
   「评审范围口径」仅作上下文，不计入产品交付。
5. `git diff --stat db552a7 -- backend`（对比当前工作区）→ 空，`backend/` 与 delivery 逐字节
   一致；`git status --short` 全程只显示既有 `frontend/index.html`、`frontend/self-check.js`
   两个未提交文件，未被当作受审交付。
6. 直接读取 `git show db552a7:backend/hedge_open_tasks/store.py` 的
   `cycle_slippage_pct`/`_cycle_leg_basis_locked`/`_num_or_none` 实现、
   `git show db552a7:backend/hedge_open_tasks/domain.py` 的 `direction_to_leg_actions`
   （`spot_side`/`perp_side` 四向映射，`position_side_mode` 只影响 `perp_position_side`）逐行核对
   公式、分母、四向卖买腿选择与降级路径，与 Human 口径及 dispatch Goal 完全一致。
7. 独立复算（不依赖任何交付代码或既有 handoff 数字）：
   `(0.09808666666666666666666666667-0.09786)/0.09786*100 = 0.23160...` → `0.2316`；
   `(0.10036-0.10058)/0.10036*100 = -0.21921...` → `-0.2192`。均与交付输出一致。
8. 只读复跑测试（`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`，禁用仓库内 bytecode/cache
   写入）：
   - `backend/tests/test_hedge_store.py backend/tests/test_hedge_cycle_close.py` → `131 passed`
   - `backend/tests` 全量 → `1763 passed`
   两次复跑后 `git status --short` 均只剩前述两个既有未提交前端文件，无 `__pycache__`/
   `.pytest_cache` 等仓库内写入泄漏（该目录已在 `.gitignore`，且复跑前后 `git status` 无变化）。
9. 对 O-1/O-4 相关调用链逐行核实（均为本终端独立读取，非复用 review-1 结论）：
   `backend/hedge_open_tasks/service.py:3305-3319 _query_verdict_terminal` 只看
   `exchange_status`（`FILLED` 即终态），从不检查 `verdict.cumulative_quote`；同文件
   `service.py:2035-2056` 在该 `terminal` 判定后立即以 `quote_amt=verdict.cumulative_quote`
   （可能为 `None`）调用 `resolve_leg_from_query(..., terminal=terminal)`，与
   `backend/hedge_open_tasks/service.py:3216-3230 _leg_terminal` 及
   `backend/services/live_hedge_executor.py:503-520 leg_is_terminal_fill`（两者均要求非 spot 腿
   `cumulative_quote is not None` 才算终态）逻辑不一致——inline 派发侧等 quote，drain 侧不等。
   `backend/tests/test_hedge_store.py::test_resolve_leg_from_query_persists_avg_price`
   （现有测试，非本轮新增）证明「`avg_price` 落库、`cumulative_quote_amt` 为 NULL、
   `terminal=True`」是系统已测试、已接受的合法状态；而
   `_cycle_leg_basis_locked`（`store.py:2347-2377`）只累加 `cumulative_quote_amt` 求均价，不回退
   `avg_price`，故该状态下 `cycle_slippage_pct` 对该腿判定不可定价 → 整体 `None`。
   引入提交核验：`git merge-base --is-ancestor 8af3f22 7da67bc` 与
   `git merge-base --is-ancestor d90f2f1 7da67bc` 均返回真，二者确为 `base_sha` 祖先，
   O-4 判定为 `pre-existing-independent` 成立。
10. 对 O-2 直接读取 `git show db552a7:frontend/index.html` 第 5339 行注释与 5360-5362 行表头
    `title`，确认仍为「成交均价 vs 开/平仓估价(est_price) 的偏离率 %（负=成交优于估价）」旧口径
    文本，未随本次交付同步；`git merge-base --is-ancestor 97ecb7f7 7da67bc` 返回真，确为
    `base_sha` 祖先，`pre-existing-release-critical` 判定成立。值渲染逻辑
    （`classForSignedNumber`/`hedgeNum`/`toFixed(4)`）未改动，新口径下正负号着色方向恰好正确，
    唯有文字说明与新口径相反。

### 验收检查逐项裁决（dispatch Acceptance Checks）

1. **pass** — 独立核对 Human 需求与实际公式、正负号、四向腿映射及四位输出完全一致。见方法
   第 6 条：`store.py:2379-2419` 公式 `(sell-buy)/min(spot,perp)*100`、`f"{...:.4f}"`；
   `domain.py` 四向映射 forward open=合约SELL/现货BUY、reverse open=现货SELL/合约BUY、
   `task_type=close` 反转，与 Human 锁定口径逐项一致。
2. **pass** — JSTUSDT `0.2316/-0.2192`、零价差、跨 attempt 与缺腿降级证据足以证明实际效果。
   见方法第 7、8 条：独立复算命中，测试只读复跑 131/1763 全绿，且测试用例（
   `test_cycle_slippage_uses_directional_sell_and_buy_legs`、
   `test_cycle_slippage_weights_both_legs_across_attempts`、
   `test_cycle_slippage_missing_invalid_and_zero_cases`）以无关/缺失 `est_price` 反证旧口径
   回归、覆盖跨 attempt 数量加权与缺腿/非法/非正降级。
3. **pass** — 固定 delivery、schema/API/caller 边界与两级测试证据可信，未把控制提交或工作区
   未提交前端改动当成交付。见方法第 2-5 条：delivery commit 恰五路径、`status.json` 仅一处状态
   迁移、区间内控制提交按 §8 归为上下文、`backend/` 与 delivery 逐字节一致、两个未提交前端文件
   全程未被当作受审事实。`store.py:196-197` schema 注释改动为纯行内注释，`_ensure_columns` 列
   声明未变，无迁移影响；`service.py:1925-1926` 调用点签名与既有调用者未变。
4. **pass** — 评估 O-1/O-4 的当前可达性、fail-closed 效果、用户影响、重开条件与是否阻塞发布。
   见「问题记录」小节：O-1/O-4 均经本终端独立代码核实为**当前可达**（非假设，drain 路径确有
   FILLED-但-quote-未知即判终态的分支，且该形态是系统已测试接受的合法状态），效果均为
   fail-closed（返回 `None`/展示 `—`，不臆造数值），用户影响仅限历史页该周期滑点列显示缺失、
   不影响资金或持仓；两者均**不阻塞本轮发布**（理由见下），但均应作为 Human 决策的具名事项。
5. **pass** — 确认 O-2 旧口径文案尚未同步，明确其合并/发布 gate；不得把 review ACCEPT 解释为
   文案已修复。见方法第 10 条：直接读取 delivery SHA 下的 `frontend/index.html` 源码确认文案
   未变，`frontend/index.html` 本身不在 delivery commit 内。本 ACCEPT 仅覆盖 `db552a7` 的代码
   正确性，不代表 O-2 已修复；O-2 已被本阶段具名为合并/发布前必须完成的文本同步项
   （`AGENTS.md` §7 Bookkeeper 收尾义务）。
6. **pass** — 确认历史 close-log 不会被本次代码自动重算，重启不会回填 JSTUSDT，补录仍需独立
   Human 授权与备份/行级核验。核实：`store.py` 的 `insert_close_log`
   （`git show db552a7:backend/hedge_open_tasks/store.py` 第 2268 行起）仅 `INSERT`，无任何
   `UPDATE hedge_open_cycle_close_log`；`_ensure_columns` 的 schema 迁移仅为幂等
   `ALTER TABLE ADD COLUMN`（新增列，不改写既有行的值）；`cycle_slippage_pct` 仅被
   `_finalize_close_task`（`service.py:1907-1926`）在**新**周期关闭时调用一次并写入新行。
   故 JSTUSDT 那条历史 `close_log` 行不会因本次交付、服务重启或任何自动路径被重算或回填；
   补录仍是独立 Human 授权动作，与 `PROJECT_STATE.md` Live Risk 原文一致。
7. **pass** — 无订单、资金、数据库写入、服务控制、部署或风险参数副作用；给出实际发布就绪结论。
   本次评审自身零副作用（见「评审范围与方法」首段）。**发布就绪结论**：`db552a7` 的代码正确性
   与测试证据已独立核实为可信、`ACCEPT`；但完整「发布」（合并 + 部署 + 实盘生效）在此 ACCEPT
   之外仍需三项独立前置：(a) O-2 前端/`service.py` 旧口径文案同步（当前未完成，已排入 stage
   收尾）；(b) `AGENTS.md` §3/§9 要求的 Human 显式合并与部署授权；(c) 历史 JSTUSDT 行是否补录由
   Human 单独决定，本交付不隐含已补录。三者均不由本次 review-2 `ACCEPT` 自动满足。
8. **pass** — 发现按范围三分类并附证据；新假设满足 Scenario Admission；明确最终 `ACCEPT|REWORK`
   及 Human 仍需决定的事项。见「问题记录」与「结论」小节。本终端未发现 review-1 未披露的新
   `in-range` 阻塞缺陷；对 O-1/O-4 的可达性给出了比 review-1 更进一步的独立代码级确证（非仅
   复述），未引入需要 Scenario Admission 但缺乏证据锚点的新假设。

### 问题记录（本终端独立复核，分类与证据锚点见上）

**O-1 `[in-range][不阻塞本轮，具名上交 Human]`** 合约腿「已成交、`avg_price` 在场、
`cumulative_quote_amt` 为 NULL」时，新 `cycle_slippage_pct` 返回 `None`（历史页显示 `—`），
而旧实现在该形态下会用 `avg_price` 直接出值。
- 可达性：**当前代码路径确实可达**（非假设）——见方法第 9 条完整调用链
  （`_query_verdict_terminal` 不查 quote → `resolve_leg_from_query` 落库 `avg_price` 且保持
  `cumulative_quote_amt=NULL` → attempt 正常结算 → `_cycle_leg_basis_locked` 不认这条腿的价）。
  是否有**真实历史周期**已落入该形态需要读实盘库，本任务只读且 Allowed Files 明确排除实盘库，
  本终端与 review-1 一样无法直接证实或证伪，按 `AGENTS.md` §1「受保护影响但可达性未决 → 具名
  上交，不作无据 REWORK」处理。
- fail-closed 效果：不产生假数值，同一行「合约均价」列也会同步显示 `—`，展示自洽。
- 用户影响：仅历史页该周期的滑点列可能保持缺失（本次修复对这个特定形态未必生效），不影响
  资金、持仓或订单状态。
- 是否阻塞发布：**不阻塞**。理由：(a) 该数据源口径（仅用 `cumulative_quote_amt` 加权、不回退
  `avg_price`）已被已 `ACCEPT` 的跨 provider 计划评审明确批准，交付严格符合被批准的 dispatch
  Goal；(b) 真实发生率不可只读证实；(c) 有廉价、明确的重开触发条件；(d) 最小修法会牵动同一
  helper 供给的另外四个展示列（合约/现货开平均价），风险与收益不对称，不宜在本轮夹带。
- 重开触发条件：Human 在历史页看到某已平仓周期「合约均价」有值而「滑点」为 `—`，或授权一次
  只读核对确认库中存在该组合的成交腿。

**O-2 `[pre-existing-release-critical]`** 前端滑点列 tooltip（`frontend/index.html:5361-5362`
及 `:5339` 注释）与 `service.py:1924` 注释仍写旧 `est_price` 口径，且符号解释
（「负=成交优于估价」）与新口径（负=买价高于卖价）方向相反。
- 引入提交 `97ecb7f7`，本终端 `git merge-base --is-ancestor` 独立核实为 `base_sha` 祖先；
  `frontend/index.html` 不在 delivery commit 内。
- 是否阻塞发布：不阻塞**本轮交付**（值渲染逻辑未改、无需改动，颜色方向在新口径下反而正确，
  不涉及资金动作），但**阻塞合并/发布前的文本同步 gate**——`AGENTS.md` §10 明确 Human 只读
  界面不读代码，符号解释相反的 tooltip 会直接误导账务判读。本 ACCEPT 不得被解释为该文案已
  修复；该项已被本阶段 dispatch 具名为收尾任务，落在 `AGENTS.md` §7 的 Bookkeeper 收尾义务内。

**O-3 `[nit][不需处理]`** 绝对值 `< 0.00005%` 的真实负价差格式化为字符串 `"-0.0000"`（四位
舍入后的真值，非假零）；前端 `hedgeNum` 转为 JS 数字后 `-0 === 0` 为真，
`classForSignedNumber` 判为 `muted`，无展示异常。本终端读取 `frontend/index.html:5143-5148,
5232-5236` 独立核实该结论成立。

**O-4 `[pre-existing-independent]`** drain 路径的腿终态规则（`service.py:3305-3319
_query_verdict_terminal`）只看 `exchange_status`，与 inline 派发路径的终态规则
（`service.py:3216-3230 _leg_terminal`、`live_hedge_executor.py:503-520
leg_is_terminal_fill`，均要求非 spot 腿 quote 已知）不一致，是 O-1 在真实环境下能否发生的
直接决定因素。
- 引入提交 `8af3f22`/`d90f2f1`，本终端独立以 `git merge-base --is-ancestor` 核实均为
  `base_sha` 祖先，且所在文件 `service.py` 不在 delivery commit 内。
- 影响：该笔成交的 notional 永久未知（四列均价与滑点均降级为 `—`），不动资金、不造假数，
  未知仍是未知（fail-closed）。早于且独立于本次交付，不阻塞本轮合并；但建议与 O-1 同批由
  Human 决定是否单开一轮修复（最小方向：drain 侧对非 spot 腿也检查 quote 是否已知再判终态）。

**范围说明**：历史 `hedge_open_cycle_close_log` 既有行（含 JSTUSDT）不会被本次交付、重启或
任何自动路径重算；补录须 Human 单独授权（见验收检查 6 的独立核实）。

### 结论

`ACCEPT（接受）`。八项验收检查全部 `pass`，无 `in-range` 阻塞缺陷。本终端独立、完整地重新核对
了固定 `base_sha..delivery_sha` 上的公式、四向腿映射、min 分母、×100 与四位 `Decimal` 文本、
跨 attempt 数量加权、缺腿/非法/非正降级、`est_price` 路径移除、schema/API/调用者契约不变，并
独立复算 JSTUSDT 两个期望值、独立只读复跑两级测试（131/1763 全绿，无仓库内写入泄漏）。对
review-1 具名的 O-1/O-4 完成了比 review-1 更深一层的独立调用链核实（非复述），结论一致：均为
当前代码可达、fail-closed、不阻塞本轮但需 Human 决策的具名事项；O-2 独立核实为**尚未同步**，
明确其为合并/发布前的文本 gate，不得由本 ACCEPT 推定已修复。历史 JSTUSDT 数据独立核实为不会
被本次交付自动重算。未发现 review-1 遗漏的新增 `in-range` 缺陷，未引入需要走 Scenario Admission
但缺乏证据锚点的新假设。

Human 仍需决定：(1) 是否/何时合并与部署（§3/§9 独立授权，本 ACCEPT 不隐含）；(2) O-2 前端/
`service.py` 文本同步的执行时点（已排入 stage 收尾，可与合并同批）；(3) O-1/O-4 是否单开一轮
（重开条件已给出，非强制立即修）；(4) 历史 JSTUSDT 行是否补录（独立授权，本轮不涉及）。

### Required Reading for the Next Task
- 读取路径及顺序：`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md`、`reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json`
- 执行：Bookkeeper 核验本 handoff 源区 SHA-256（`BOOKKEEPER_APPEND_ONLY` 标记前字节）、
  task_id/role/stage_id/`base_sha`/`delivery_sha` 与 dispatch/status/Git 一致，确认
  `ACCEPT（接受）` 与八项 `pass`，将 O-2 文本同步与 O-1/O-4 具名事项整理为 Human 可读的中文简报
  （不得直接转发原始 diff/JSON/代码），随后由 Human 做最终业务验收与合并/部署授权决定
- 关卡：Bookkeeper 核验通过后，Human 阅读简报并做出：是否合并/部署、O-2 文本同步执行时点、
  O-1/O-4 是否单开一轮、JSTUSDT 历史行是否补录，四项决定
- 不能假设的事实：本 `ACCEPT` 只覆盖 `db552a7` 的代码正确性与测试证据，不等于文案已同步、
  历史数据已补录、服务已重启或已获合并/部署授权；O-1 的实盘发生率与 O-4 的实盘后果均未经
  实盘数据证实或证伪（本任务 Allowed Files 明确排除实盘库）；工作区未提交的
  `frontend/index.html`、`frontend/self-check.js` 不属于本交付，不得被当作已完成的 O-2 修复

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 04-review-2
执行结果: completed（完成）
结果摘要: 全新只读终端独立复核固定区间 db552a7。公式/四向腿映射/min分母/四位小数/跨attempt加权/降级均核实正确；JSTUSDT 0.2316/-0.2192 独立复算命中；测试独立只读复跑131/1763全绿，无仓库写入泄漏；delivery仅五路径，控制提交与未提交前端文件均未混入交付。O-1/O-4经独立调用链核实为当前可达但fail-closed不阻塞；O-2独立核实尚未同步，为合并前文本gate；历史JSTUSDT行独立核实不会被自动重算。结论ACCEPT。
产物: [reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md]
检查结果: [
1. pass 公式/正负号/四向腿映射/四位输出与Human需求完全一致（独立核对源码）;
2. pass JSTUSDT 0.2316/-0.2192、零价差、跨attempt与缺腿降级证据充分（独立复算+独立复跑测试）;
3. pass 固定delivery五路径、schema/API/caller边界与两级测试证据可信，控制提交与未提交前端改动未混入交付;
4. pass O-1/O-4当前可达（独立核实完整调用链）、fail-closed、仅影响展示、不阻塞发布，具名上交Human;
5. pass O-2旧口径文案独立核实尚未同步，明确为合并/发布前gate，ACCEPT不等于文案已修复;
6. pass 历史close-log独立核实为INSERT-only不会自动重算，JSTUSDT不会因重启回填，补录须独立Human授权;
7. pass 本次评审零订单/资金/数据库/服务/部署副作用；发布就绪=代码ACCEPT，完整发布仍需O-2同步+Human合并部署授权+历史补录另决;
8. pass 发现按三分类记录并附证据，无遗漏的新in-range缺陷，未引入无据新假设，最终结论ACCEPT
]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md
修复要求: none
本地北京时间: 2026-08-12 09:29:49 CST
下一步模型: codex（本阶段 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md, reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/status.json；执行：Bookkeeper核验源SHA-256、任务身份与固定base_sha..delivery_sha，确认ACCEPT与八项pass，整理O-2/O-1/O-4为Human中文简报；关卡：Human阅读简报后做最终业务验收与合并/部署/文本同步/历史补录四项决定
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `3408c1b393280eff86a1bf717991f08711c33991463fc0960b6ed657faae4ced`
- verified_at: `2026-08-12 09:37:43 CST`
- status_revision_checked: `7`
- verification_result: `ACCEPTED`
- identity_and_fixed_range_check: `pass`（task_id、role、target model、stage_id、status revision、
  `base_sha..delivery_sha` 与 dispatch/status/Git 一致；base 为 delivery 祖先，delivery commit
  五路径与既有核验一致。）
- verdict_and_acceptance_checks: `pass`（明确 `ACCEPT（接受）`、八项 `pass`、问题记录与
  `修复要求: none` 均在场；Review-2 明确未发现新的 in-range 阻塞缺陷。）
- release_gate: O-2 旧口径 tooltip/注释尚未同步，继续阻塞合并/发布收口，但不推翻 review-2
  对固定产品 delivery 的 ACCEPT；O-1/O-4 为 fail-closed 的具名 Human 决策项，不阻塞本轮代码
  验收；历史 JSTUSDT 补录仍需独立授权。
- worktree_boundary: 当前 `frontend/index.html`、`frontend/self-check.js` 的未提交改动仅属于“尝试
  时间线最近 10 条”任务，未修改 O-2 文案且不属于固定 delivery，后续文本同步必须保留这些改动。
- reproducible_commands:
  - `perl -0ne '$i=index($_,"<!-- BOOKKEEPER_APPEND_ONLY:"); die if $i < 0; print substr($_,0,$i)' reports/agent-runs/2026-08-12-hedge-slippage-spread-v1/evidence/04-review-2.handoff.md | shasum -a 256`
  - `git rev-parse 7da67bc87261386c117b98f2b63c6ac6083fd291 db552a7b224fcebc84bb23a087ff2b28a350bf04`
  - `git show --format= --name-status db552a7b224fcebc84bb23a087ff2b28a350bf04`
- next_state: review-2 gate 通过，进入 Human 最终业务验收；O-2 完成前不得合并/发布收口。

## Errata (append-only)

none
