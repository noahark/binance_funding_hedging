# 10-design —— 四项待办的完整实现方案

- task_id: `plan-hedge-task-lifecycle-v1`
- 角色 / 模型：Planner / `claude_glm`（zhipu_glm）
- base_sha：`afa3d5228e64ed2399e3d24b6971245e20950d9f`（HEAD `4a40de8` 的后两提交为本阶段控制提交：status rev4 + D13 范围说明，`git diff afa3d52 HEAD -- backend/` 为空，故下列锚点在 HEAD 成立）
- 范围来源：`02-scope-decisions.md`（D1-D8）、`03-fake-ui-outcome-and-plan-scope.md`（D9-D13，D13 撤销 D11）、本 dispatch
- 展示形状基准：fake UI 交付 `63f5007`

本文件只写方案，不写代码。所有行号锚点已由作者在当前 HEAD 逐处复核（见下「已核实事实」）。

---

## 0. 已核实事实（方案立足点，不重挖）

1. **后端代码 base_sha..HEAD 无改动**：`git diff afa3d52 HEAD -- backend/` 空。dispatch 锚点在 HEAD 成立。
2. **六种暂停原因**（`domain.py:127-151`）：`consecutive_submission_failure` / `rate_limited` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full`，`ALL_PAUSE_REASONS` 六条。`rate_limited` 确在其中（`:134`）。
3. **51169 冻结文案**属 `collateral_cap_full`（`domain.py:1315-1324`，`:1317` 注释 `must NOT be reworded`）。
4. **A-1 计划上限家族四站**（谓词均为 `scheduled_attempt_count >= target_n`）：`store.py:690`（SQL 调度资格 `< target_n`）、`store.py:740`（`prepare_attempt` 预留守门 `>= target_n → None`）、`store.py:979`（R2-F1 收口 `>= target_n 且 running → done`）、`service.py:1172`（worker 退出 `>= target_n → WORKER_EXIT_TARGET_REACHED`）。清单外三处谓词不同（见 §2）。
5. **死锁路径**（`service.py:616` `post_start`）：只挡 `DELETED`（409）与 `DONE`（幂等 200），**不查配额**就 `set_task_status(RUNNING)` + `ensure_worker`；worker 在 `:1172` 因 `scheduled >= target_n` 立即 `WORKER_EXIT_TARGET_REACHED` 退出；R2-F1 收口（`store.py:975-990`）要求 `pair_outcome is not None` 且 `new_status == running`，而此时无待结算 attempt 触发收口 → 任务停在 `running` 无进展。复现条件 `target_n == failure_pause_threshold` 已由 intake 确认。另 `post_start` 不挡 `stopped`。
6. **三再武装入口**：`post_start`（`:616`）、`post_fill_once`（`:656`）、`post_fill_all`（`:670`），三者都汇到 `set_task_status(RUNNING)+ensure_worker`；`post_fill_once/all` 经 `_require_fillable`（`:694`，只挡 `DELETED`）同样不查配额。
7. **worker 自驱 + 仅对在途腿节流**（`service.py:1065-1082` `_run_task_worker`）：循环 `_worker_round`，**仅当存在非终态腿时**才 `ev.wait(interval_s)`；一对腿都终态即立刻进下一对（A-9 每任务串行）。
8. **LIVE 模式 `tick()` 是安全空操作**（`service.py:1500-1517`）：注释明写 "A periodic tick must NEVER scan all tasks"；live 派发/对账只在 per-task worker 上跑。→ `interval_us` 在 live 模式**只**节流 leg 重查（`:1079`），**不**驱动下单节奏，**不**抬高下单频率。
9. **两处 worker 429→暂停**：`service.py:1152-1160`（`_reconcile_own_legs` 返回 `SIGNAL_RATE_LIMITED` → `_pause_task_local(RATE_LIMITED)` → 退出）与 `service.py:1176-1180`（派发返回 `SIGNAL_RATE_LIMITED` → `_pause_task_local(RATE_LIMITED)` → 排空后退出）。
10. **`skip_counters` 限频结算不走 R2-F1**（`store.py:907-924` + `:976` 的 `not skip_counters`）：限频对结算不碰计数器/状态/阈值，故配额已耗仍可能非终态。
11. **`post_delete` drain 语义**（`service.py:645-654`）：只 `set_task_status(DELETED)`，**不打断** worker；worker 继续把在途腿 drain 到终态后在 `status != RUNNING` 检查处（`:1168`）退出。
12. **`pause_task`**（`store.py:1739-1763`）：写 `status=paused`+`pause_reason`+`pause_reason_zh`，清 `stop_reason`；由 worker 的 `_pause_task_local` / `_pause_from_signal` 调用。
13. **`resolve_leg_from_query`**（`store.py:1570-1619`）：UPDATE 中 `order_id = COALESCE(?, order_id)` 有保护，但 `cumulative_quote_amt = ?`、`avg_price = ?` **无 COALESCE** —— 后一次查询返回 `None` 覆盖已知值（④ 目标，PROJECT_STATE `[OPEN][RESIDUAL]`）。
14. **`aggregate_positions`**（`store.py:1937-2057`）：两条查询均 `WHERE t.status != DELETED`（`:1950`/`:1960`）；占位零在 `:2049-2053`（`open_basis_rate`/`price_pnl`/`accrued_funding`/`borrow_interest`/`net_pnl` 均字面量 `"0"`）。按 `(coin, direction)` 分桶，`spot_avg`/`perp_avg` 由 `Σ名义额/Σ数量` 算，带 `*_incomplete` 标记；`position_qty` 为签名 perp 净值。
15. **private_client 白名单冻结**（`hedge_preflight_provider.py:14-19`）：注释明写 "`private_client.py`'s frozen whitelist cannot be extended and lacks them"；hedge 服务只能经**自己的** `HedgeOpenLiveClient` allowlist 做私有读，且该 allowlist 只含三个 preflight 端点，**不含** snapshot 端点（`fetch_um_positions` / `fetch_unified_balances` / `fetch_spot_balances` / `fetch_pm_account` 走的是 `private_client.py` 的 snapshot 路径）。
16. **前端两源已在手**（`02-scope-decisions.md` §2 / `20-fake-ui-implementation.md` §9）：`state.snapshot.private_account`（`um_positions[]` / `balances_unified[]` / `balances_spot[]`）与 `state.hedgePositions` 同时在浏览器内；合并**零新增交易所请求、零新增限频权重**。`_infer_position_side`（`snapshot.py:893-895`）返回**大写** `LONG`/`SHORT`，零仓 `null`（fake-ui §11 已据此造假数据）。

---

## 1. 八个决策点裁定（P1-P8）

### P1 合并在哪一层做 —— 【前端 join】（最关键，ADR 见 `11-adr.md` ADR-001）

**结论**：在**前端** `index.html` 做合并，消费已在手的 `state.snapshot.private_account` 与 `state.hedgePositions` 两片 state，**不改后端 `aggregate_positions`，不扩 `private_client.py` 白名单，不新增任何交易所请求**。

**理由**：
- 后端合并被事实堵死：hedge 服务够不到 `private_account`（事实 15），`private_client.py` 白名单冻结不可扩，给 `HedgeOpenLiveClient` allowlist 新增 snapshot 端点 = 新读路径 + 重复抓取（snapshot 路径已为「UM 持仓」面板抓过一次）= 新增限频权重，违反 dispatch P1 与 `02-scope-decisions.md` §2「零新增限频权重」。
- 前端两源已在手（事实 16），join 是纯派生，零新增请求。
- **资金可见性（① 的本目的）由构造解决**：合并表骨架是 `um_positions`（真实持仓，独立于任务状态）。② 之后任务被删，`aggregate_positions`（`WHERE != DELETED`）会丢掉该任务的腿，但**真实 UM 持仓仍在 `um_positions`**，故敞口不从界面消失。后端 `WHERE != DELETED` 因此**本轮不动**（见非目标 §3）。
- fake UI `63f5007` 已用前端 join 证伪了形状并经 Human 认可（acceptance #8 基准）。

**放弃了什么**：合并逻辑在 JS（比 SQL 难测；以 `self-check.js` 断言 + 复用既有 `directionForPosition`/base-asset 归一函数缓解）；两张渲染器（合并表 + 任务卡）各自派生视图，口径漂移风险——以「合并表消费后端同一份 `pair_outcome`/`leg_exposure` 判定，不自行重推单腿敞口」（fake-ui §9 #6）收敛为单源。

### P2 手工部分平仓后的偏离 —— 【真实值为准、记录作参考、仅单向软标记】

**结论**：合并表的**数量列以真实值为权威**——perp 用 `um_positions[].position_amt`，现货腿用 `balances_spot[]`/`balances_unified[]` 的该 base asset 余额；任务记录累加值（`aggregate_positions` 的 `spot_qty`/`perp_qty`）作为同行的「本地记录」参考值显示。**仅当真实现货余额 < 记录累加值**（手工减仓方向）时，复用既有单腿敞口的视觉（红行 + 标记，fake 场景 d）加一行软标记「本地记录与实际不一致」；**不告警、不自动平仓、不净额**（D7 / 红线 #5）。

**理由**：真实 < 记录是风险相关方向（对冲腿被手工削弱，恰是合并表应暴露的）；真实 > 记录（额外入金）非风险相关，不标记，避免噪音。

**放弃了什么**：现货被挪作全仓抵押（移入 UM/cross）也会降低可见现货余额，从而触发该软标记——已知假阳源；接受，因为操作者能看到 UM/cross 侧并自行判断，且一个假标记远便宜于漏掉一次手工减仓。**不做**自动对账。

### P3 ②③ 相撞 —— 【rate_limited 剥离出「删除集」，改为调度层退避；另五种终态原因改自动删除】（ADR-002）

**结论**：
- **五种终态原因**（`consecutive_submission_failure` / `insufficient_balance` / `insufficient_margin` / `insufficient_available_qty` / `collateral_cap_full`）→ 自动写 `DELETED`（复用既有终态，不新增枚举，红线 #3），保留 `pause_reason`+`pause_reason_zh`（51169 冻结文案因此在已删卡上仍逐字显示，红线 #1）。
- **`rate_limited` 移出删除/暂停集**：worker 两处 429 站点（`service.py:1152-1160`、`:1176-1180`）不再调 `_pause_task_local`/`pause_task`，改为**指数退避 + 抖动重试**（不写 `paused`、不写 `deleted`）。
- **③ 仍做**，但加护栏（见 P6）：修整除显示、加下限、加抖动；并以 429 退避为全局背压阀门。**不做**投机性的全局 token-bucket 限流器（红线 #6），仅当实现期实测「抖动+退避后 429 仍频发」才作为证据触发的后续项（见非目标 §3）。

**为何不与 Human 已定的「六种全改」冲突**：「六种全改」的**深层意图**是「非人工暂停不得变成需手动恢复的僵尸态；`paused` 此后只剩人工」。对五种终态原因，删除达成该意图（任务确已死，需人工重建）；对 `rate_limited`，**删除反而违背意图**——它会把一个瞬时限频信号误判为终态失败，毁掉已部分成交任务的资金可见性（① 的全部意义），且 ③ 把查询量放大 10 倍后变成「一次 429 即批量删卡」。退避才符合意图（限频解除后自恢复，不产生僵尸，不写 `paused`）。因此 `rate_limited` 是**与意图对齐、与字面清单偏离**：从「六种全删」细化为「五种删 + 一种升格为调度层退避」。

**这是本方案唯一触碰 Human 已述决策之处**，已在 `11-adr.md` ADR-002 单独立 ADR，供计划评审（`deepseek`）与 Human 裁定。**回退方案**：若 Human 坚持字面「六种全删」，则**不做 ③**（保留 1s）——因为 ③ + 字面六删会让批量删卡常态化，对资金可见性不可接受。

**放弃了什么**：字面「六种」清单的整齐性；worker 多了退避状态（用既有 `stop_event.wait` 实现，不新增字段/枚举）。

### P4 ② 的死锁修法 —— 【在共享再武装路径加配额守门，未达或已耗配额不得再武装】

**结论**：在三再武装入口（`post_start` / `post_fill_once` / `post_fill_all`）汇到的共享路径上加一道与 A-1 同谓词的守门：`scheduled_attempt_count >= target_n` 时**不**置 `running`+`ensure_worker`，而是收口到 `DONE`（复用 `post_start` 既有 `DONE` 幂等路径，`:621-622`）。同时让 `post_start` 对 `stopped` 不再武装（与 `deleted`/`done` 一致归为不可再武装）。

**理由**：死锁根因是 `post_start` 这一站**缺**守门，而其余三站（事实 4）都有。补的是同一谓词、同一意图（不超 `target_n`），属**收紧**非放宽（红线 #2），且不切到 `accepted` 口径。worker 端 `:1172` 的退出保持不变（双保险）。

**放弃了什么**：`post_start` 对 `stopped` 态从「可重启」变为「不可重启」——这是行为收紧；`stopped` 是致命停止（fatal），本就不应被 Start 按钮无声重启，故合理。若 Human 想保留 stopped 可重启，则仅保留配额守门、不动 stopped（降级方案，已在 ADR 注明）。

### P5 自动删除的边界 —— 【复用 post_delete 不打断 drain；已成交腿靠 ① 的真实骨架保持可见】

**结论**：自动删除走 `post_delete` 同款「只置 `DELETED`、不打断 worker」路径（事实 11）。worker 若在终态原因触发时正有在途腿，继续 drain 到终态，后在 `status != RUNNING`（`:1168`，现为 `DELETED`）处退出——与人工删完全等价，**不杀在途腿**。被自动删除任务的已成交腿，其敞口仍出现在合并表里，因为**骨架是 `um_positions`（真实持仓，与任务状态无关）**（P1）。

**理由**：五种终态原因的触发点分布——`consecutive_submission_failure` 在 `_apply_task_counters`（结算一对已终态的 attempt，此刻无在途腿）；`insufficient_*`/`collateral_cap_full` 在 worker `_pause_from_signal`（派发/preflight 期，可能有在途腿）。无论哪点，只要复用 `post_delete` 的不打断语义，drain 安全就成立。

**放弃了什么**：被删任务的**成本基（task 记录的 `spot_avg`/`perp_avg`）**会从 `aggregate_positions` 消失（`WHERE != DELETED`），故合并表上该行的成本列缺失——但这是「无任务记录」的诚实降级（等同 fake 场景 b），敞口本身可见，非资金可见性漏洞。后端 `WHERE` 本轮不改（见非目标 §3）。

### P6 ③ 的前置与拆分 —— 【先修整除显示；不拆分，全局下调到 100ms；加下限；加抖动】（ADR-003）

**结论**：
1. **前置（必须先做）**：修 `service.py:178` 的 `int(settings["interval_us"]) // 1_000_000` 整除 → 渲染亚秒（显示 ms 或小数秒），否则 100ms 显示成 `0`。
2. **不拆分**：把唯一共享的 `interval_us` 默认值从 1s（`1_000_000`）下调到 100ms（`100_000`），**不**新增「下单调度间隔」字段。
3. **加下限**：在读取处（`get_interval_us`）夹一个下限（建议 50ms），防未来误配把 worker 转成忙轮询。
4. **加抖动**：worker 节流（`:1079`）的 `ev.wait(interval_s)` 加随机抖动，避免 10 个 worker 对齐成 100 req/s 脉冲。

**理由（关键新证据）**：事实 8——LIVE 模式 `tick()` 是空操作，`interval_us` 在 live **只**节流 leg 重查（`:1079`），**不**驱动下单节奏（A-9：下一对等两条腿都终态）。故下调它**只**缩短腿重查延迟，**不**抬高下单频率。又因 live `tick()` 不扫任务，「下单调度间隔」在 live 无对应物；拆分只对 DRY-RUN 节奏（`tick():1519`）有意义，而 DRY-RUN 是 record-only、不下单，其 10x 加速无害。**拆分解决的并非真实问题**（红线 #6 / 架构师第 1 条），故不拆。这偏离了 `PROJECT_STATE.md` follow-up 里「拆分两间隔」的旧建议——以事实 8 为据。

**放弃了什么**：DRY-RUN 模式 `tick()` 跑快 10 倍（无害，record-only）；下单频率不受影响（已由 A-9 保证）。

### P7 占位零的处理 —— 【真值 / 暂无 / 拿不到 三类，逐列定口径】

**结论**（与 fake UI §5 三分类一致，合并表为前端渲染口径，**不改后端占位零**）：

| 列 | 口径 | 来源 |
|---|---|---|
| 未实现盈亏（`price_pnl`） | **真值**（红绿数字） | `um_positions[].unrealized_profit`（合约腿） |
| 累计资金费（`accrued_funding`） | **暂无**（灰斜体「暂无」） | 后端字面量 `"0"`，本轮无数据源，**不画 0.00** |
| 借币利息（`borrow_interest`） | **暂无** | 同上 |
| 净盈亏（`net_pnl`） | **暂无** | 资金费/借币未知，净额无法真实算，**不画 0.00**（红线 #4） |
| 开仓基差（`open_basis_rate`） | 真值（前端现算，既有） | `index.html:4448` 既有逻辑保留 |

**拿不到**（淡灰 `—` / 忠实 `null` / 强平价 sentinel `0` 带说明）按 fake §5：合约均价缺失→`—`；全仓借款 `null`→`null`；强平价币安返回 `"0"`→显示 `0` 且带 title「该仓当前无强平价」（不得把 `"0"` 当价格参与计算/告警）。

**理由**：未实现盈亏有真数据源（`unrealized_profit`，事实 16 / `02-scope-decisions.md` §2.2）；资金费/借币/净额本轮无实时数据源，按红线 #4「不得用账户级数值冒充每币」与 money-zero tripwire（DEC-2026-07-30-001）不得编造。

**放弃了什么**：净盈亏本轮无法给出（缺两个分量）；用户若要需后续接资金费/借币数据源（非目标 §3）。

### P8 交付拆分与顺序 —— 【三个交付任务，序 ①→②→③，④ 搭车于 ②】

| # | 任务 | 范围 | 文件边界 | 风险 | 依赖 |
|---|---|---|---|---|---|
| 1 | `hedge-merged-positions-v1`（①） | 前端合并持仓表（真实 UM 骨架 + 现货/借款 + 任务记录成本 + 占位零三分类 + 偏离软标记 + 六场景口径） | `frontend/index.html`、`frontend/self-check.js` | **HIGH_RISK**（资金显示正确性 / money-meaning，但只读、无下单路径） | 无；是 ② 的前置 |
| 2 | `hedge-task-lifecycle-v1`（②+④+P3 剥离） | 死锁修法（再武装配额守门）、五种终态原因自动删除（保留 reason+drain）、`rate_limited` 改退避（两处 worker 429 站点）、A-1 守门补齐、`skip_counters` 非终态收口、④ `COALESCE` 搭车 | `backend/hedge_open_tasks/{service.py, store.py, domain.py}`、`backend/tests/test_hedge_{service,store,task_local,domain}.py` | **HIGH_RISK**（任务状态机 + 资金可见性 + 实盘写路径） | ① |
| 3 | `hedge-leg-requery-cadence-v1`（③） | 整除显示修复、`interval_us` 1s→100ms、下限、worker 抖动、退避节流参数调优 | `backend/hedge_open_tasks/{service.py, store.py, scheduler.py}`、`backend/tests/test_hedge_{service,task_local}.py` | **HIGH_RISK**（限频/操作性风险 + 触 worker 实盘路径 + 验收 oracle 非显然） | ②（`rate_limited` 语义与 worker 退避须先在 ② 落定，③ 只调节奏） |

**顺序硬约束**（dispatch P8）：① 在 ② 前（资金可见性先于「会隐藏任务」的自动删除）；③ 在 ② 后（`rate_limited` 语义须先定）。①② 文件独立（前端 vs 后端），可由两个终端并行**开发**，但 ② 不得先于 ① **合并**。③ 与 ② 都改 `service.py` worker 区，③ 须基于 ② 的 `delivery_sha` rebase。

**中间态安全**：② 落地后 `rate_limited` 已退避（不删不暂停），③ 只把节奏从 1s 调到 100ms——②→③ 之间无「半成品」危险态。

详见 `12-development-breakdown.md`。

---

## 2. A-1 计划上限家族覆盖（acceptance #4）

本方案对 A-1 家族的触碰**仅** P4 在 `post_start`/再武装路径**新增**一道同谓词守门（`scheduled_attempt_count >= target_n`）。逐站评估：

| 站点 | 现状 | 本方案影响 |
|---|---|---|
| `store.py:690`（SQL 调度资格 `< target_n`） | runnable 任务扫描 | **不受影响**：到达 `target_n` 的任务由 P4 收口为 `done`，非 `running`，本就被该扫描排除；谓词不变。 |
| `store.py:740`（`prepare_attempt` 预留守门 `>= target_n → None`） | 单 attempt 预留 | **不受影响**：仍保留，作为预留层双保险；谓词不变。 |
| `store.py:979`（R2-F1 收口 `>= target_n 且 running → done`） | 结算期收口 | **不受影响**：P4 在再武装入口收口，R2-F1 在结算期收口，两路径互补；R2-F1 触发条件不变。 |
| `service.py:1172`（worker 退出 `>= target_n`） | worker 自退 | **不受影响**：保留作双保险。 |
| **新增**：`post_start`/再武装守门（`service.py` 层） | 原缺 | **新增同谓词守门**：`>= target_n` → `done`，不置 `running`。收紧，非放宽，不切 `accepted` 口径（红线 #2）。 |

**清单外三处，谓词不同，不并入家族**（给出不适用理由）：
- `domain.py:1087`（`accepted_count >= target_n`）：**受理口径**——已成交对数达上限，语义是「成功受理满」，与「计划次数上限」不同；A-1 是后者。不并入。
- `service.py:687`（`success_count >= target_n`）：**成功口径**——DRY-RUN `post_fill_all` 同步循环的退出条件（已核实 `:686-688`），语义是「成功数满即停」，非计划次数；不并入。
- `store.py:811`（仅计数器 `+1`）：非判阈，是计数自增；不并入。

P3 的 `rate_limited` 剥离**不碰** A-1（`rate_limited` 走 `skip_counters`，本就不进 R2-F1，事实 10）。

---

## 3. 非目标（acceptance #6，本轮显式不做）

1. **资金费数据源**（`accrued_funding`）：本轮不接，合并表画「暂无」。
2. **借币利息实时数据源**（`borrow_interest`）：本轮不接（按资产查历史接口、未实时挂行），画「暂无」。
3. **净盈亏**（`net_pnl`）：因缺上述两分量，本轮不真实计算，画「暂无」。
4. **`done` 语义**（「次数用尽」vs「全部成功」）：D2 暂不处理，不新增状态枚举（红线 #3）。
5. **1000x 符号前缀剥离**（`normalize.py`）：本轮不做；BONK/FLOKI/LUNC/PEPE/SHIB/XEC 六币仍无法建任务，但**可能以手工仓出现在真实 UM 持仓**，合并表按「无任务记录」行照实显示（fake 场景 b）。
6. **同币双向**（D13，2026-07-31 移出本轮）：若出现，按 D7「都显示、标清楚」两行照实并列，**不做净额合并、不告警、不触发任何自动动作**。根治手段（开单前校验反向→改走平仓）是独立后续 stage（`[FUTURE]` HIGH_RISK）。
7. **后端 `aggregate_positions` 的 `WHERE != DELETED`**：本轮**不改**。合并表以 `um_positions` 为骨架已解决资金可见性；改后端 `WHERE` 非必需且会改变既有 `GET /api/hedge-open-positions` 契约口径，超范围。
8. **全局 token-bucket 请求限流器**：本轮不做（无证据，红线 #6）；仅当实现期实测「抖动+退避后 429 仍频发」才作为证据触发的后续项。
9. **逐仓每币清算价 / 逐仓账户价值 / 逐仓未实现盈亏列**：本项目是统一账户全仓，无此概念（红线 #4 / fake §10），不照抄参考脚本。
10. **现有 inline-log 功能的运行时真机验证**：仍 `[OPEN][RUNTIME-UNVERIFIED]`（PROJECT_STATE），本轮不负责；但 ② 改的正是任务状态机，此残风险在 §7 列出。
11. **删卡的「按原参数复制新建」按钮**：不做（Human 已定，重试靠手动重建）。
12. **多次开单的累加**：`aggregate_positions` 已做等价且更稳的累加（`03-fake-ui-outcome-and-plan-scope.md` §2.1 已核实），**非缺口**，本轮不动。

---

## 4. 六条红线逐条确认（acceptance #7）

1. **51169 文案逐字冻结** —— **遵守**。保证处：`12-development-breakdown.md` Task 2「自动删除保留 `pause_reason`+`pause_reason_zh`」——删卡仍渲染 `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE`（`domain.py:1315-1324`）逐字原文；Task 1 合并表/卡消费该模板不改字。只允许**追加**删除后缀（本轮无需追加）。严禁换「保证金不足」话术。
2. **不得放宽 A-1 计划上限** —— **遵守**。保证处：§2 + ADR——P4 守门用 `scheduled_attempt_count` 同谓词、是**收紧**（补缺守门），不切 `accepted` 口径。
3. **不得新增任务状态枚举** —— **遵守**。Task 2 复用既有 `DELETED`（自动删除）与 `DONE`（配额收口），不造新值。
4. **不得用账户级数值冒充每币数值** —— **遵守**。Task 1 合并表每币行用 `um_positions` 的逐币字段；账户级 `uniMMR` 只作表外摘要（建议放表外，不冒充为某币列），见 P7 / fake §10。
5. **不得自动执行任何交易动作** —— **遵守**。Task 1 纯展示；Task 2 的「删除」是任务状态转移，非交易；对冲不上的两类只展示不动作（D7）。
6. **不得扩大范围 / 不引入无证据抽象** —— **遵守**。每个新增点的证据见 §6；前端 join（证据：白名单冻结事实 15）、退避（证据：③ 放大 10 倍致 429 频发，事实 9）、下限（证据：误配致忙轮询）、抖动（证据：10 worker 对齐成脉冲）。全局限流器**因无证据而缓做**（§3 #8）。

---

## 5. 展示形状与 fake `63f5007` 的一致性（acceptance #8）

与 `63f5007` 预览**一致**：合并表以真实 UM 为骨架、每行横拼三源、六场景（normal/no_task/no_um/single_leg/missing/empty）、占位零三分类（真值/暂无/拿不到）、任务卡六原因对照 + 四张示例卡、51169 文案逐字。

**与 fake 不同之处（逐条列出，未列即一致）**：
1. **数据源**：fake 用脚本常量；真实实现消费 `state.snapshot.private_account` + `state.hedgePositions`。原因：fake 是设计探针，真实必须接真数据（fake-ui §0/§3 已声明零网络请求仅限预览）。
2. **`rate_limited` 卡的「新规则」文案**：fake 六原因对照表把 `rate_limited` 也标「自动软删除」；真实实现按 P3 剥离，`rate_limited` 改标「限频退避（不删除、不暂停）」。原因：P3 裁定 `rate_limited` 是瞬态背压而非终态失败（ADR-002）。
3. **偏离软标记（P2）**：fake 六场景无「手工部分平仓」场景；真实实现复用 single_leg 的红行视觉，新增标记文案「本地记录与实际不一致」。原因：P2 需暴露手工减仓偏离（视觉模式已在 fake 场景 d 内，仅标记文案新增）。
4. **「净盈亏」列**：fake §5 注明净盈亏口径待定；真实按 P7 定为「暂无」（不画 0.00）。原因：缺资金费/借币分量。

---

## 6. 每个新增模块/层次/接口的证据（acceptance #9）

| 新增点 | 解决的已观察到的问题 | 证据 |
|---|---|---|
| 前端合并 join | 后端够不到 `private_account` + 白名单冻结，合并须在前端 | 事实 15、16 |
| 再武装配额守门（P4） | `post_start` 缺守门致死锁 | 事实 5、6 |
| 五原因自动删除 | 非人工暂停变僵尸，需手动恢复 | dispatch ② / intake |
| `rate_limited` 退避 | ③ 放大查询 10x，一次 429 即删卡毁资金可见性 | 事实 9、P3 |
| `interval_us` 下限 | 误配致 worker 忙轮询 | P6 |
| worker 抖动 | 10 worker 对齐成 100 req/s 脉冲 | P3/P6 |
| ④ `COALESCE` | 后查返回 `None` 覆盖已知值（残 risk） | 事实 13 |
| 合并表消费后端 `pair_outcome`/`leg_exposure` | 避免双源口径漂移 | fake-ui §9 #6 |

**刻意不做**的抽象（无证据）：全局 token-bucket 限流器、拆分双间隔字段、逐仓列、防域防腐层——均按架构师第 1 条「No architecture astronautics」拒绝。

---

## 7. 实现阶段最可能出问题的三处 + 早期验证（acceptance #10）

1. **符号 / base-asset 三方对齐（最高风险）**：`um_positions[].symbol`（`BTCUSDT`/`1000PEPEUSDT`）↔ 任务 `coin` ↔ 现货/统一 `asset`（`BTC`/`PEPE`）。1000x 六币 UM 带 `1000` 前缀而现货资产名不带，`normalize.py` 不剥离（非目标 #5）。
   - **早期验证**：单元测试 base-asset 归一函数，覆盖六个已知 1000x 币 + 一个普通币；断言 `1000PEPEUSDT` um ↔ `PEPE` 现货的映射（或诚实地不匹配→落入「无任务记录」行，不假对齐）。
2. **`rate_limited` 剥离正确性**：两处 worker 429 站点必须完全停止写 `paused`/`deleted`，且退避不得忙轮询/死循环。
   - **早期验证**：用 `_pump_worker` 测试 seam（`service.py:1096`）注入 `SIGNAL_RATE_LIMITED`，断言**未**调 `pause_task`/写 `deleted`、发生了退避等待、worker 最终干净重试或退出。
3. **死锁修法完备性 + drain 安全**：P4 守门须覆盖三个再武装入口与 `target_n == failure_pause_threshold` 复现条件；自动删除在腿在途时触发仍须 drain 到终态。
   - **早期验证**：(a) 复现条件回归测试（`target_n == threshold`，`post_start` 再武装 → 断言 `done` 而非卡 `running`）；(b) A-1 家族穷举断言（四站同谓词）；(c) worker 在途腿 + 终态信号 → 断言腿达终态后才退出。

**附残风险（非本轮引入，须 Human 知情）**：② 改任务状态机，而现有 inline-log 功能**从未在真实服务跑过**（PROJECT_STATE `[OPEN][RUNTIME-UNVERIFIED]`）。动状态机前是否做一次 Human 授权的只读真机验证，由 Human 决定（D4 已选「跳过」）。
