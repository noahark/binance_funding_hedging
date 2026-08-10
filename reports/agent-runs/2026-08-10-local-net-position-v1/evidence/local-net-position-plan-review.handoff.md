# Task Handoff: local-net-position-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `local-net-position-plan-review`
- role: Reviewer（独立高风险计划评审，只读 + 单一 create-only handoff）
- target model: `opus5`（provider identity: `anthropic`）
- stage_id: `2026-08-10-local-net-position-v1`
- created_at: 2026-08-10 12:01:50 CST
- base_sha: `53ed646f4b97d07ea478a834ed8eb6acb83bbedf`
- delivery_sha: `none`（本任务无交付提交；评审对象是尚未实现的计划文稿）
- 工作树 HEAD（仅上下文）：`38a384045382a10352d80e0546ec47277c460a60`
- required_skill: `agents/skills/software-architect.md`
- 评审对象：`reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
- 评审结论：**REWORK**

---

### 1. 评审范围与方法

本次是 `AGENTS.md` §8「计划评审」——实现开始前的一次独立跨 provider 只读评审，
verdict 返回 Planner，不触碰 `rework_count`。评审只判断计划本身是否最小、自洽、
可验证、可交给 `claude_glm` 实现；不实现、不改计划、不改状态。

方法：不以任务成功状态或计划自述为准，逐条对照当前仓库真实代码路径核验。全部为
只读检索与阅读（`grep` / 文件读取），未运行测试、未启动服务、未触碰 live DB、未
读取凭证。

### 2. 计划中被核验为成立的部分

以下五项经真实代码核对成立，实现者可以直接依赖：

**(a) 数量写入路径已穷举，计划口径覆盖全部结算路径。**
`cumulative_base_qty` 在生产代码里只有三处触碰：

- `backend/hedge_open_tasks/store.py:950-980`（`prepare_attempt` 建腿时种子 `'0'`）；
- `backend/hedge_open_tasks/store.py:1331-1357`（`resolve_attempt`，立即结算）；
- `backend/hedge_open_tasks/store.py:1805-1830`（`resolve_leg_from_query`，查询补录 /
  UNKNOWN reconcile / 限流后补drain）。

后两处**均不区分 `task_type`**，也不以 pair 成功为前提，因此 close 腿的真实成交与
open 腿同样落在 `hedge_open_leg` 上。计划 §3「只认 `cumulative_base_qty > 0`，不以
task `done`、pair `success`、literal status 或两腿同时成功为前提」与既有 A-6 策略
（`store.py:2590-2594` 的 `if _num(...) <= 0: continue`）完全一致。**结论：无需给任何
写路径增加数量双写。** 计划 §7 第一问成立。

**(b) close 腿确实落在同一个 cycle 桶里。**
`prepare_attempt` 通过 `_get_active_cycle_locked(task["coin"], task["direction"])`
分配 cycle（`store.py:925-929`），而 close 任务在创建时被强制沿用持仓行的
`coin`/`direction`（`service.py:766-780`，注释「平仓方向沿用持仓行方向」）。因此
close attempt 的 `cycle_id` 就是该活跃周期的 id，桶键 `(coin, direction, cycle_id)`
不会分裂。计划 §3 的逐腿净额在数据上可实现。

**(c) 只改中央聚合成立，不需要扩域到 `domain.py`。**
`aggregate_positions` 的唯一调用方是 `service.py:1336`（持仓端点）。下游
`single_leg_exposure`（`domain.py:1983-1990`）与 `drift`（`domain.py:2014-2022`）都是
从 `spot_qty`/`perp_qty` 现算的派生量，聚合改对后它们自动跟着对；前端平仓输入的
两道拦截读的是 `unified_balance` 与 `um_position_amt`（`frontend/index.html:5541-5560`），
不读 `spot_qty`/`perp_qty`。**计划 §7 第三问的答案是「不改 `domain.py` 足够」。**

**(d) 成本基与剩余数量确实彻底拆开，设计自洽。**
`spot_avg`/`perp_avg` 的分子分母是 `spot_notional`/`spot_qty_priced`
（`store.py:2646-2658`），与 `spot_qty` 是两套累加器；只要 close 腿只进数量、不进
notional 与 priced 分母，净量绝不会成为开仓均价的分母。且前端只把两个均价当**价格**
用（`frontend/index.html:6169` 现算基差率、6262-6263 直接展示），**没有任何消费者做
`qty × avg`**，所以「均价仍是全周期开仓成本基、数量已是剩余量」不会产生名义值矛盾。
历史页的开/平均价走独立的 `cycle_leg_basis(cycle_id, task_type)`（`store.py:2342-2377`），
不受影响。

**(e) 两个已观察事实都能被验收矩阵区分，且方向正确。**

- XVG（双腿部分平仓）：open 50000、close 2×10000 → 两腿各 30000，与交易所一致 →
  `drift` 由「误触发」变为 false，`single_leg_exposure` false。计划验收 1/2 覆盖。
- XLM（reverse 单腿平仓，`PROJECT_STATE.md` Live Risks 2026-08-10）：close 合约腿
  `FILLED 100`、close 现货腿被 `-2019` 拒绝 → 净额 spot 100 / perp 0 →
  `abs(100-0) > 100×1%` → `single_leg_exposure` **true**。
  **当前代码在这个形状下是 100/100、不报警**，即本改动不仅修了 XVG 误报，还顺带让
  XLM 型真实单腿失衡第一次能被本地账本看见。计划验收 3 正是这个形状，能区分误报与
  真实失衡。

以上三项在计划 §6 的最小测试命令覆盖的五个测试文件内均可执行验证：
`test_hedge_cycle_close.py` 已有 close 全链路脚手架（`RecordTransportFake` +
`post_fill_all`，见该文件 1-58 行），`test_hedge_api.py:58-89` 的 `_POSITION_KEYS`
是「API 固定字段集合不变」的现成断言，`test_hedge_cycle_core.py` 已有关闭周期过滤与
多周期桶用例，`test_hedge_store.py:286-308` 已有 `includes_deleted_task` 用例。

### 3. REWORK 发现（阻塞项，一条）

**F-1｜计划未定义「桶内只有 close 腿成交、没有 open 腿成交」时的输出，按现行计划
实现会产出负数量与反号的幻影持仓行，且两个安全标记同时静默。**

范围分类：**in-range**（本条不是既有缺陷——今天 SQL-B 的 `WHERE t.task_type = ?`
（`store.py:2476`）让这种桶在结构上不可能出现；它是本次改动新引入的分支，且计划
未对其取值）。

证据锚点（全部为当前代码/记录，非假设）：

1. `store.py:925-929`：`prepare_attempt` 在没有活跃周期时**直接新建一个周期**
   （`_create_cycle_locked`，`store.py:2216-2231`），这段代码不区分 `task_type`，而
   `service.py:2889` 是全仓唯一的 `prepare_attempt` 调用点，open 与 close 共用。
2. `service.py:766-780` + `service.py:819-844`：close 任务只在**创建时**校验活跃周期
   存在，随后以 `paused` / `awaiting_manual_start` 停在卡上等待 Human 手动启动；
   `post_start`（`service.py:1001-1015`）**不再复核周期是否还在**。
3. `service.py:1830-1879` 的派发前 close 门 `_close_um_position_error` 只读**交易所 UM
   持仓**，从不查 cycle。因此「周期已关闭但交易所仍有仓」时该门放行，随后
   `prepare_attempt` 为这次 close 新建一个空周期。
4. 周期可以在任务仍可启动时被关闭：`close_cycle`（`store.py:2243-2256`）同时服务
   `auto_close` 与 `manual_verify`，而 `PROJECT_STATE.md` Live Risks 2026-08-10 记录
   Human 已用 `manual_verify` 手工关闭过 XLM 周期，且同处的 OPEN 风险条明确把
   「reverse 自动平仓不要用、由 Human 逐腿人工收口」写成**当前操作规程**——手工收口
   与手工关周期是现行流程的一部分，不是臆造场景。
5. 后果落点：这种桶按计划 §3 逐腿相减后为负 → `spot_qty`/`perp_qty` 为负数；
   `position_qty = direction_sign × perp_remaining` 在 forward 下是 `-1 × (-q) = +q`，
   即**把一笔平仓渲染成一个同等数量的多头**。
6. 两个标记同时失效：`domain.py:1985-1989` 的 `larger > 0` 对负数为 false →
   `single_leg_exposure` 恒 false；`domain.py:2014-2015` 的 `recorded_spot <= 0` →
   `drift` 恒 false。该桶还会被 `domain.py:2143-2153` 作为独立 `no_um` 行输出，前端在
   无 UM 行时直接渲染 `position_qty`（`frontend/index.html:6255`）——**一个没有任何
   告警、方向相反的假持仓被展示为事实**。

为什么必须本轮在计划里定死、不能留作观察：本 stage 的 review-2 已被 Human 一次性
豁免，review-1 `ACCEPT` 后已预授权合并 `main`，计划门是这条语义唯一的廉价确定点；
且它属于 `AGENTS.md` §8 的受保护类（持仓 / 账务含义）。按 §1 Scenario Admission，本条
走 (b) 路径准入：受保护类影响 + 当前前提（手工关周期在用、close 卡长期停在
`paused`）+ 逐条代码锚点，且不要求完整静态调用链或已发生事故。修法不新增状态、
字段、契约或依赖，落在既有聚合函数与既有测试结构内。

**可直接改写计划的具体要求（三处，均为文本级修改，不扩文件边界）：**

- **R1（§3 唯一数量语义，补一条规则）**：明确「净额只在该桶存在 open 腿真实成交时
  成立」。推荐取法：**同一 `cycle_id` 桶内 open 腿累计成交为 0 时，该桶不输出持仓行**
  （它不是未平仓头寸），并说明该规则天然覆盖 `cycle_id IS NULL` 的历史腿，与 §4.7
  「不为无 `cycle_id` 的历史路径发明平仓语义」一致。若 Planner 选择保留该行，则必须
  在计划里显式定义负数量与 `position_qty` 反号的展示含义，并说明
  `single_leg_exposure`/`drift` 在 ≤0 时静默是否可接受——该取法会引入新的展示语义，
  与 §4.4「API 字段集合与语义不变」冲突，故不推荐。
- **R2（§6 验收检查，补一条）**：构造「同一 coin/direction 的周期已关闭 → 随后一次
  close 派发新建了空周期并双腿成交」的用例，断言持仓表不出现该行，且任何输出行的
  `spot_qty`/`perp_qty`/`position_qty` 均不为负。该用例用
  `test_hedge_cycle_close.py` 现有脚手架即可构造（`close_cycle` + 再次
  `post_start`/`post_fill_all`），不需要新框架。
- **R3（§4 或 §5 文档行，补一句具名后果）**：净额为 0 而交易所仍有仓时（close 腿已
  记账但周期尚未关闭 / 合约无仓核实未通过），`single_leg_exposure` 与 `drift` 都因
  `> 0` 前置条件而静默——今天这个状态下 `drift` 是会报的。这是本次口径变更的既定
  代价，须写进 §5 已经要改的
  `docs/api/public-market-contract.md` 追加段落，避免以后把「无告警」误读成「已对账」
  （与 `PROJECT_STATE.md`「drift 是弱告警不是对账」的既有定性一致）。

### 4. 非阻塞观察（不扩范围、不要求本轮处理）

- **O-1**：SQL-B 放开 `task_type` 后，`_take_identity`（`store.py:2511-2527`）会开始
  看到 close 腿。close 身份继承自周期首个 open 任务（`service.py:789-807`），正常一致；
  仅在回退查表且映射表变更时会多写一条 `identity_conflict` 审计事件。不改变聚合结果。
- **O-2**：手工收口只写 `hedge_open_cycle_close_log`（XLM `id=5`）而不进腿账本，因此
  「周期未关闭 + 手工在交易所平掉一部分」时本地净额会偏高，兜底仍只有弱告警
  `drift`。这与计划 §4.7 的立场一致，属已知边界，建议随 R3 一起写进文档段落。

### 5. 未做的事

未运行任何测试（本任务只读、计划尚未实现，无交付可测）；未修改计划、状态、源码、
测试、文档或既有证据；未创建后续 dispatch；未启动或联系任何其他模型终端。

### 6. 可复现命令（只读）

```bash
git rev-parse HEAD
grep -rn "cumulative_base_qty" backend --include="*.py" | grep -v "^backend/tests/"
grep -rn "prepare_attempt" backend --include="*.py" | grep -v tests
grep -rn "aggregate_positions" backend --include="*.py" | grep -v "^backend/tests/"
grep -n "spot_qty\|perp_qty\|position_qty" frontend/index.html
sed -n '920,935p;2460,2500p;2585,2640p' backend/hedge_open_tasks/store.py
sed -n '1980,1995p;2010,2025p' backend/hedge_open_tasks/domain.py
sed -n '760,850p;1000,1016p;1830,1880p;1905,1920p' backend/hedge_open_tasks/service.py
```

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md`
  2. `reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md`
  3. `reports/agent-runs/2026-08-10-local-net-position-v1/status.json`
- 执行：核验本交接件，按 `REWORK` 将 `current_task` 置 `reported` 并记录计划评审
  verdict；计划评审 verdict 返回 Planner，按 `AGENTS.md` §8 不递增 `rework_count`。
  修订要求为本交接件第 3 节的 R1/R2/R3 三条。
- 关卡：Planner 按 R1/R2/R3 改写 `00-change-plan.md` 后，由 Human 决定是再走一次计划
  评审还是直接生成 `claude_glm` 实现 dispatch。
- 不能假设的事实：
  - 本 verdict 不是 ACCEPT，不授权实现、合并、部署、服务重启或实盘操作；
  - 第 2 节 (a)-(e) 的成立结论是对**计划口径**的判断，不等于实现已被验证——实现后
    仍须走 review-1；
  - 本任务未运行任何测试，计划 §6 的最小测试命令尚未被执行过；
  - close attempt 的 `cycle_id` 由派发时的活跃周期决定，不是由创建时校验的那个周期
    锁定——R1/R2 正是针对这一点，实现者不得假设两者必然相同。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: local-net-position-plan-review
执行结果: completed（完成）
结果摘要: 只读计划评审完成，结论 REWORK。计划主干成立：数量写入路径只有两处且不分 open/close，逐腿净额无需双写；close 腿与 open 腿同属一个 cycle 桶；只改中央聚合足够，不必动 domain.py；成本基与净额彻底拆开；XVG 误报与 XLM 单腿失衡都能被区分。阻塞点一条：计划未定义「桶内只有 close 腿成交」的输出，照此实现会产生负数量与反号幻影持仓行，且两个安全标记同时静默。
产物: [reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md]
检查结果: [
  1 结算路径穷举（store.py:1331-1357 / 1805-1830 / 950-980 三处，均不分 task_type）：pass；
  2 仅改中央聚合成立、domain.py 无需扩域（唯一调用方 service.py:1336，派生标记自动跟随）：pass；
  3 close 进净额不进开仓成本分子分母，且无消费者做 qty×avg：pass；
  4 XVG 双腿部分平仓与 XLM 单腿平仓两个已观察事实均能被区分：pass；
  5 reverse/部分成交/已删除成交/同周期再加仓/关闭周期过滤/API 固定字段均有可执行验证：pass；
  6 空开仓桶（只有 close 腿）语义未定义，会产出负数量+反号 position_qty，single_leg_exposure 与 drift 双双静默：fail（唯一阻塞发现）；
  7 该发现按 AGENTS.md §1 Scenario Admission (b) 受保护类准入，未借新假设场景扩域：pass；
  8 Task Handoff Evidence Contract（唯一 create-only 文件、源区块、marker、delivery_sha=none、review closure 三行）：pass
]
阻塞项: [计划 00-change-plan.md 需按本交接件第 3 节 R1（§3 补「open 腿累计成交为 0 的桶不输出持仓行」）、R2（§6 补空周期 close 用例并断言无负数量）、R3（§4/§5 具名「净额为 0 时两个标记静默」并写入文档段落）改写后方可交付实现]
本地北京时间: 2026-08-10 12:01:50 CST
下一步模型: Codex（本 stage 的 Bookkeeper，负责状态核验与打包），由 Human 转交启动
下一步任务: 读取：reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md；reports/agent-runs/2026-08-10-local-net-position-v1/00-change-plan.md；reports/agent-runs/2026-08-10-local-net-position-v1/status.json；执行：核验本交接件并按 REWORK 把 current_task 置 reported、记录计划评审 verdict（计划评审不递增 rework_count），把 R1/R2/R3 作为 Planner 修订要求；关卡：Planner 改写计划后由 Human 决定再评审一次还是直接生成 claude_glm 实现 dispatch
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md
修复要求: reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `8e7d8f18e8f1667465bd3c854e21ce02c0ca6086ce1be76d2ca9aeca62923492`
- verified_at: `2026-08-10 12:19:28 CST`
- status_revision_checked: `1`
- identity_check: pass（task_id / role / stage_id / base_sha / target_model 与 dispatch、status、`git rev-parse main` 一致）
- create_only_check: pass（路径在 dispatch 前预检不存在，本次仅新增指定 handoff；Reviewer 未改其他文件）
- receipt_check: pass（`TASK_RESULT v2`、8 项检查、207 字符结果摘要、closure 三行与最终 marker 合规）
- verdict_recorded: `REWORK`（计划评审已真实执行；不等于计划 finding 已被 Planner 采纳，不递增 `rework_count`）
- planner_adjudication: F-1 被当前 live 顺序和本机数据反证，记为 contested；详见 `reports/agent-runs/2026-08-10-local-net-position-v1/evidence/plan-review-f1-counter-evidence.md`。原 Reviewer verdict 不改写，改由新的独立计划复评裁定。
- reproducible_checks: `perl -0777 ... | shasum -a 256`；`.venv/bin/python -m pytest backend/tests/test_hedge_cycle_close.py -k 'close_um_gate_requires_matching_sign_and_remaining_qty or close_um_guard_failure_pauses_before_attempt_or_post' -q`（10 passed）

## Errata (append-only)

- `2026-08-10 12:19:28 CST` Bookkeeper clarification：上方 source hash 的完整复现命令为 `perl -0777 -ne 'if (/^(.*?)<!-- BOOKKEEPER_APPEND_ONLY:/s) { print $1 }' reports/agent-runs/2026-08-10-local-net-position-v1/evidence/local-net-position-plan-review.handoff.md | shasum -a 256`；仅补全省略的命令文本，不改变 source payload、verdict 或 Planner 裁定。
