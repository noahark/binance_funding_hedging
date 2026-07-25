# 用户授权 + 修复方案 — 429 结算粘滞 与 人工暂停对账放弃（第 5 次代码变更）

> **本文件的身份（请先读这段）**
>
> 起草者：**Claude Opus 5（Anthropic）**，本 stage 的 Review-1（第一轮交叉复核）后端审查者，
> 见 `64-review-1-backend-r3.md`。
>
> 本文件是**交给 bookkeeper（Codex）的回执与修复方案**，用途是：①如实记录用户在
> 2026-07-25 给出的新授权；②把 Review-1 的 `required_fixes` 与 `fix_start_prompt` 完整、
> 不打折地落盘，便于 Codex 直接据此生成正式 dispatch packet。
>
> 它**不是**可执行 dispatch packet，**不是** stage state，**不构成**验收。按 `AGENTS.md`：
> 只有 bookkeeper 可以创建 packet、更新 `status.json` / `70-handoff.md`、创建证据提交；
> 只有人类操作员可以把 packet 投递到目标模型终端。审查者不越这条线。
> Codex 需要做的簿记动作清单见 §8。

## 1. 用户授权（如实记录）

- **时间**：2026-07-25（北京时间），在阅读 Review-1（`64-review-1-backend-r3.md`，
  verdict = `REWORK`，`next_action = human_escalation_required`）之后。
- **用户原话**：

  > 授权这次修复，给我一份回执 codex 的修复方案文档，然后我去跟 codex 同步下 bookkeeper 进展，
  > 再拍 glm 进行修复

- **授权含义**：
  1. 用户批准 Review-1 提出的**这一次**有界后端修复，即
     `64-review-1-backend-r3.md` 的 `fix_start_prompt` 所覆盖的范围（本文件 §4 逐条展开）。
  2. `status.json.rework_count` 当前为 **4**（`24-user-authorized-final-guardian-fix.md` 授权的
     「一次且仅一次」H-1 修复已被 packet 63 消耗）。本授权**把上限再抬高一次**，允许**第 5 次**
     代码变更，范围严格限定为本文件 §4 与 §5。
  3. 实现者路由：**Claude-GLM（`glm-5.2[1m]`，provider `zhipu_glm`）**，与既有后端 owner 一致
     （用户原话「再拍 glm 进行修复」）。
  4. 投递方式：由**人类操作员**把 Codex 生成的 packet 贴进 GLM 终端执行。任何模型不得自行派发。
  5. **§4.4 的二选一已由用户拍定为「A：加字段」**（2026-07-25，用户原话：「选 A，加字段」）。
     具体规格见 §4.4，已从「待用户决定」改为**必做项且规格写死**，GLM 不需要也不允许自行选择。

- **本授权明确**不**包含**：新产品功能、更大范围重构、smooth/WebSocket 平滑开单、凭据访问、
  真实 Binance 流量、启用 live、Start 动作、任何真实订单、前端源码改动、契约文档改动、
  自动补腿/撤单/平仓/还币/转账/完整会计。

## 2. 前置证据与固定锚点

| 项 | 值 |
| --- | --- |
| Review-1 原始评审 | `reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md` |
| 被审区间 base | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| 被审区间 head | `ab3126d73549266a615fe43c1aeaf374b0db2d32` |
| 被审指纹（已双向核验一致） | `ab3126d73549266a615fe43c1aeaf374b0db2d32:4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772` |
| 上游合同（运行时最高权威） | `21-task-local-runtime-and-manual-pause-amendment.md` |
| 上游合同（对账绝不放弃 + 错误矩阵） | `15-immediate-loop-and-open-log-amendment.md` |
| H-1 授权边界（必须继续遵守） | `24-user-authorized-final-guardian-fix.md` |
| 必须保留的既有实现 | `40-fix-review-1-backend-r2.md`（packet 62）、`42-final-guardian-scanner-fix.md`（packet 63） |
| Review-1 已核验的证据 | 897 后端测试、48 重点用例、前端自检、Harness 55、`validate-stage --phase pre-review` PASS、工作树干净 |

被审指纹是修复的**起点**，不是提交基线；bookkeeper 会在 GLM 完成后重算新指纹并重开 Review-1。

## 3. 业务含义（先讲人话，再讲代码）

Review-1 确认：真实模式的**守护进程已经彻底拿掉**（启动只做一次恢复交接，人工 Start 只启动指定
卡，周期性 tick 变成安全空操作，没有任何替代守护），上一轮的正反向价格 fail-closed（读不到价格
就拒绝发单）和「A 卡查询卡住不拖累 B 卡」也都真修好了，默认关闭、白名单、签名门这些安全门没有
回归。**这次要修的不是这些，而是「限频暂停」和「人工暂停」这两条路径的收尾逻辑。**

用一句话说清两个问题的后果：

1. **只要一张卡遇过一次 429（`Retry-After`，交易所限频）被暂停、然后你手动恢复它，这张卡的
   「连续失败 3 次自动暂停」这个安全刹车就悄悄失效了**，而且此后真正成功的组会被记成
   「已确认失败」，成交笔数长期显示 0。原因是暂停原因这个字段恢复后从来没被清掉，程序一直以为
   「我还在限频暂停中」，于是每组都走「不计数」的收尾分支。
2. **你按下「暂停」这个紧急刹车的那一刻，如果这张卡刚好有两笔单子发出去还没确认结果，程序会
   一次查询都不发就退出**——这两笔真实订单在币安可能已经成交了，但本系统不再对账、不落实际成交
   量和均价、不结算这一组。原来（packet 62）周期性 tick 会兜底把它捡回来，H-1 修复把 tick 变成
   空操作之后，这个兜底没了。而且现在唯一的进程内补救办法是再按一次 Start，那会让卡片重新变成
   运行中**继续开新单**——想「只对账、不再开单」目前做不到。删除卡片更糟：重启也救不回来，
   而持仓面板又会把已删除的卡过滤掉，于是真实敞口直接从界面上消失。

两个问题都**不会导致越权下单**（live 默认关闭，本轮零真实请求），但都会让**账本失真、安全闸门
失效**，所以必须在第一笔真实开单授权之前修掉。

## 4. 授权的修复范围（4 项必做 + 1 项建议）

### 4.1 【P1-1】清除粘滞的 `pause_reason`，并让「本组免计数」基于该组自身事实

- **根因证据**：`store.set_task_status`（`store.py:433-444`）恢复运行时的 `UPDATE` 只动
  `status` 和 `updated_at_us`，**从不清** `pause_reason` / `pause_reason_zh`；全仓唯一写入点是
  `store.pause_task`（`store.py:1365-1389`），`_apply_task_counters` 只原样回写。于是恢复后
  `pause_reason` 永久停在 `'rate_limited'`，`service._reconcile_own_legs:1026` 的 `rate_paused`
  恒为真，此后每一个 `pair_outcome IS NULL` 的组都走 `store.settle_attempt_no_counters`
  （`store.py:1009-1033`，硬盖 `PAIR_CONFIRMED_FAILED`、**完全不调** `_apply_task_counters`）
  而不是 `store.finalize_attempt`（`store.py:944-1007`）。
- **实测复现**（Review-1 离线 fake transport，原始输出）：

  ```text
  after 429 pair : status=paused pause_reason=rate_limited fail=0
  after resume   : status=running pause_reason=rate_limited (STALE)

  pair 2 legs really FILLED with orderIds s9/p9, yet:
    attempt[1].pair_outcome   = 'confirmed_failed'   (expected 'accepted_pair')
    accepted_pair_count       = 0   (expected 1)
    success_count             = 0   (expected 1)
    status                    = running   (expected done once target reached)
    dispatch (write) calls    = 2   (no resend: expected 2)
  ```

- **后果**：连续失败暂停闸门失效；`finalize_attempt` 里「对账到的腿带
  `error_category='fatal'` → `stop_task_fatal`」（`store.py:986-999`）被跳过，致命腿不再停卡；
  成功组被记成「已确认失败」；`success_count`/`accepted_pair_count` 长期 0，卡片永不 `done`；
  过期的 `pause_reason_zh` 仍出现在 running 卡的响应里。
- **修法（两处都要做，缺一不可）**：
  1. 任务回到 `RUNNING` 时清空 `pause_reason` 与 `pause_reason_zh`（与 `pause_task` 清
     `stop_reason` 对称）。
  2. 把「本组免计数」的判定改为**基于该 attempt 自身的事实**：例如 `_dispatch_live` 的 429 分支
     在 attempt 行写一个「因限频而结算」的标记，`_reconcile_own_legs` 读该标记选择
     `settle_attempt_no_counters` 还是 `finalize_attempt`，不再依赖任务级粘滞字段。
     （只做 1 会遗留「同一张 429 卡在恢复前又对账到别的组」的窄窗口；只做 2 会遗留 UI 的过期
     `pause_reason_zh`。）
- **验收**：见 §6 回归 R1、R2。

### 4.2 【P1-2】人工 `pause` / `delete` 必须先把本卡在飞腿查到终态并结算，再退出

- **根因证据**：`post_pause`（`service.py:517-525`）置位该卡 `stop_event`；`_worker_round` 的
  **第一行**（`service.py:939-941`）就在 `_reconcile_own_legs` **之前** `return True` 退出，
  因此「先 drain 后退」（Q2）这条不变式对人工暂停**根本不生效**（它只对 429 / 余额类信号生效，
  那两条走 `return False`）。packet 63 把 live `tick()` 变成空操作
  （`service.py:1088-1089`）后，原先由 `_recover_workers()` 提供的周期兜底消失。
  另：`_recover_workers`（`service.py:1163`）只遍历 `PAUSED` / `STOPPED`，**不含**
  `STATUS_DELETED`，被删卡片的在飞腿连进程重启都不会再被查询；而 `aggregate_positions` 又用
  `WHERE t.status != DELETED` 过滤（`store.py:1478,1487`，该过滤是 base 提交就有的既存行为）。
- **实测复现**（原始输出）：

  ```text
  after dispatch : non-terminal legs = 2  query_calls = 0
  after pause    : status = paused
  worker_round   : exit = True  query_calls = 0
  still pending  : non-terminal legs = 2
  after 5 ticks  : query_calls = 0 (unchanged: True )
  ```

- **与 H-1 授权的关系（关键，不要修错方向）**：
  `24-user-authorized-final-guardian-fix.md` 只禁止「周期性 scheduler/tick 反复发现全部任务」，
  **并未**要求放弃人工暂停后的本卡 drain。合规修法完全是**任务本地**的，**不得**引入任何全局
  扫描/守护/定时器。
- **修法**：
  1. `post_pause` 不再置位 `stop_event`，或改置一个「暂停」专用标志、由 `_worker_round` 在
     `_reconcile_own_legs` **之后**才检查。这样 worker 先把自己的腿查到终态、结算该组，然后
     因 `status != RUNNING` 退出（`service.py:962-963` 已保证**绝不开新组**）——「尽快停」的
     语义不被破坏。
  2. `post_delete` 同理给一个 drain-only 收尾路径，并把 `STATUS_DELETED` 加入
     `_recover_workers` 的兜底状态集合（否则重启也救不回来）。
- **验收**：见 §6 回归 R3、R4、R5。

### 4.3 【P2-1】`settle_attempt_no_counters` 改为按两腿真实事实推导 `pair_outcome`

- **根因证据**：`store.py:1029-1032` 硬编码 `pair_outcome = PAIR_CONFIRMED_FAILED`，无视两腿
  真实结果，也不写 `leg_exposure`。`_dispatch_live` 的 `rate_limited` 分支
  （`service.py:1379-1396`）既不解析两腿 verdict 也不 resolve 该组；两腿都不是
  `UNKNOWN_QUERYING` 时连 `_mark_legs_querying` 都不调（leg 行留在 `PREPARED`、`terminal=0`，
  **仍会被 drain 查到，无孤儿风险**，Review-1 已专门验过）。
- **实测复现**（原始输出）：

  ```text
  perp leg really accepted+FILLED: order_id=p7 status=FILLED base=0.5
  spot leg absent                : order_id=None status=UNKNOWN

    pair_outcome  = 'confirmed_failed'   (truth: 'single_leg' single-leg exposure)
    leg_exposure  = None
    positions     = [{'coin': 'BTCUSDT', 'direction': 'forward', 'position_qty': '-0.5', …}]
  ```

  一条真实裸空头已经开出来（持仓面板如实显示），组级结论却写「已确认失败」，且
  「单腿敞口」告警字段为空。
- **注意**：修好 §4.1 的第 1 点**不会**修掉这条——同一组内 429 当场就是 `rate_paused`，
  所以必须单独改。
- **修法**：让 `settle_attempt_no_counters` 复用 `finalize_attempt` 的**类别推导**（按两腿
  `order_id` 决定 accepted / single_leg / failed，`single_leg` 时写 `leg_exposure`），只跳过
  `_apply_task_counters` 的**计数器与阈值**部分（例如给 `_apply_task_counters` 加
  `skip_counters=True` 参数）。
- **验收**：见 §6 回归 R6。

### 4.4 【P2-2】给 task 文档加后端权威的 worker 存活 / 退出原因字段

- **根因证据**：H-1 修复后 live 没有周期 tick，worker 退出后只有人工 Start/recover 或进程重启
  会重启它。`_worker_round` 在预检不完整/致命（`service.py:980-981`）、Start gate 关
  （`964-965`）、异常兜底（`904-907`）后退出，而 task 行仍是 `status='running'`；
  `task_to_doc`（`service.py:118-148`）没有任何 worker 存活字段，
  `GET /api/hedge-open-tasks` 无法区分「正在跑」和「卡死等人工恢复」。
- **用户决定：选 A —— 加字段**（2026-07-25 拍定）。以下规格**写死**，GLM 按此实现，不得自选：

  **① `worker_active`（派生，不落库，无 schema 变更）**

  - 位置：`service.task_to_doc()` 新增键 `worker_active`。
  - 取值：`True` / `False` / `None`：
    - live 可派发模式（`_live_dispatch_capable()` 为真）：由 `_workers` 注册表派生——
      `t = self._workers.get(task_id)`；`bool(t is not None and t.is_alive())`。
      读取需在 `_workers_lock` 临界区内取引用，再在锁外判 `is_alive()`。
    - dry-run（record/disabled executor）：**必须是 `None`**，语义为「本模式不适用」。
      dry-run 根本没有任务本地 worker（派发在 tick 内同步完成），返回 `False` 会误导操作员
      以为卡片坏了。这一条是硬要求。
  - 诚实性依据：`_run_task_worker` 的 `finally` 块会把自己从 `_workers` 弹出
    （`service.py:908-911`），所以注册表反映真实存活，不是陈旧缓存。
  - 注意 `task_to_doc` 目前是**模块级函数**、不持有 service 实例。允许的最小改法二选一（由 GLM
    择其一并在报告说明）：把 `worker_active` 作为可选参数传入（各调用点由 service 方法计算后
    传递），或改为 service 上的一个薄包装方法。**不要**为此把 `task_to_doc` 变成访问全局状态。

  **② `last_worker_exit_reason`（落库，可为 NULL）**

  - 存储：`hedge_open_task` 新增 `TEXT` 可空列，走既有加性迁移模式
    （`store._migrate()` 的 `additions` 元组，与 `pause_reason` / `stop_reason` 同一写法，
    `store.py:310-321`），幂等、老库可读。
  - 写入点：`_worker_round` 的每个退出分支 + `_run_task_worker` 的异常兜底，各写一个稳定的
    机器可读枚举值。建议取值集合（在 `domain.py` 里定义常量，别散字符串）：
    `stopped_event`（被 pause/delete/stop 唤醒）、`task_not_running`、`start_gate_off`、
    `target_reached`、`preflight_incomplete`、`preflight_fatal`、`worker_error`、
    `task_missing`。
  - 清除：任务重新进入 `RUNNING` 时置 NULL（与 §4.1 清 `pause_reason` 同一处，一并做）。
  - 投影：`task_to_doc` 新增键 `last_worker_exit_reason`。**是否需要中文文案由前端后续决定，
    本轮不加 `_zh` 字段**（避免又冻一个文案契约）。

- **明确不做**：**不要**为此新增 entries 时间线的事件 kind。`_ENTRY_EVENT_KINDS`
  （`service.py:56-62`）是已被前端 Review-1 接受的冻结集合，新增 kind 会走
  `_event_to_entry` 的 else 分支被错标成 `next_action="waiting_query"`，等于污染已接受的
  前端契约。worker 退出原因走上面的 task 列，不走 entries。
- **前端边界**：本轮**只出后端字段，不动 `frontend/**`**（前端在其 Review-1 ACCEPT 后源码未变，
  必须保持）。UI 上如何展示「需人工恢复」留作**后续 follow-up**，请 bookkeeper 在
  `70-handoff.md` 记一条待办：「前端展示 `worker_active` / `last_worker_exit_reason`，
  提示需人工恢复」。
- **契约同步**：两个新键需加进 `backend/tests/test_hedge_api.py` 的冻结字段集（该文件已在
  §5 允许清单内）。
- **验收**：见 §6 回归 R7、R8。

### 4.5 【P3 建议项】让 `_pump_worker` 与 `ensure_worker` 共享 stop-event 初始化

`_pump_worker`（`service.py:913-925`）不注册 `_stop_events`，只有 `ensure_worker` 会建。因此所有
经该 seam 驱动的用例（含迁移过来的 review-2 17 用例）里 `_wake_worker` 都是空操作，
`_worker_round` 首行的 stop 检查恒不命中——**这正是 §4.2 的缺陷逃过 897 个测试的机制**
（也让 Review-1 第一次复现尝试失败，补上 event 后才稳定复现）。建议一并修，使 pause/delete
中断语义可被同步测试观察。

### 4.6 明确**不在**本次授权范围

- **P3 跨进程预留守卫**（`prepare_attempt` 依赖 SQLite DEFERRED 事务的读后写）：仅在人为让两个
  服务进程共用同一 `data/hedge-open-tasks.sqlite3` 时可触发，当前无此部署。保持为已记录的剩余
  风险，本轮**不改**。
- 实时订单计数/权重响应头（`X-MBX-ORDER-COUNT-*`）主动节流：仍为已如实记录的未实现项，本轮**不改**。

## 5. 文件边界（GLM 必须遵守）

**允许修改**：

```text
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/domain.py
backend/services/live_hedge_executor.py      # 仅本次分类/标记所需的最小改动
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_review2_regressions.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_api.py              # 仅当新增字段需同步冻结字段集
reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt   # 仅追加原始输出
reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md  # 新建实现报告
```

**禁止修改**：`frontend/**`、`docs/**`、PRD、`10-design.md`/`11-adr.md`、
`reports/api-samples/**`、`status.json`、`70-handoff.md`、任何契约文档
（15/16/17/19/21/23/24/25/26 号）、`42`/`50`/`58`/`64` 号评审与修复报告、
`backend/hedge_open_tasks/scheduler.py`、`backend/app/server.py`
（后两者除非新增字段确实需要最小接线，且必须在实现报告中说明理由）、
环境/凭据/网络配置文件。

**硬安全约束**：绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live、
绝不触发 Start、绝不 commit、绝不派发评审、绝不自行判定验收。

## 6. 必须新增的确定性回归（离线、fake transport、零 sleep race）

要求：每条先能在**修复前**的代码路径上复现所述缺口（或以清晰推导说明为何必然复现），修复后转绿。

| 编号 | 场景 | 断言 |
| --- | --- | --- |
| R1 | 429 暂停 → 人工恢复 → 下一组两腿 FILLED | `pair_outcome == accepted_pair`；`accepted_pair_count == 1`；`success_count == 1`；`pause_reason is None` |
| R2 | 429 暂停 → 人工恢复 → 连续 3 次已确认失败 | 仍触发阈值暂停（`pause_reason == consecutive_submission_failure`） |
| R3 | 一组两腿 UNKNOWN → `post_pause` | worker 退出前 `query_calls >= 2`；两腿 `terminal == 1`；该组 `pair_outcome` 非 NULL；`scheduled_attempt_count` **未增加**（没开新组） |
| R4 | 同上 → `post_delete` | 同构断言（drain 完再退出，不开新组） |
| R5 | `DELETED` 卡带非终态腿 → 进程重启 `start()` | `_recover_workers` 拉起 drain-only worker，把腿查到终态 |
| R6 | 429 落在一腿 + 另一腿 FILLED | `pair_outcome == single_leg`；`leg_exposure` 非空；`fail_count` 不变 |
| R7 | live 卡预检不完整 → worker 退出（task 仍 `running`） | `worker_active is False`；`last_worker_exit_reason == "preflight_incomplete"`；worker 存活期间 `worker_active is True`（用 holding executor 观测）；人工 Start 后 `last_worker_exit_reason is None` |
| R8 | dry-run（record/disabled）模式下的 running 卡 | `worker_active is None`（不适用），**不是** `False` |

另需**复跑并保持全绿**：`test_6a` / `test_6b` / `test_6c`（H-1 三条防线）、`test_1`–`test_5`、
`test_4b`、review-2 的 17 条迁移用例。

## 7. 精确自测命令（提交前全部跑绿，原始输出追加到 `60-test-output.txt`）

```bash
.venv/bin/python -m pytest \
  backend/tests/test_hedge_task_local.py \
  backend/tests/test_hedge_service.py \
  backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_domain.py \
  backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_purity.py \
  backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

基线参照（Review-1 本机实测）：`backend/tests` = **897 passed**；三聚焦文件 = **48 passed**；
前端自检全通过；Harness = **55 passed**；`git diff --check` 干净。新增 6 条回归后总数应上升。

**交付物**：实现说明写入
`reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md`（新文件，
不覆盖已有 40/41/42 号报告），列出 changed files、每条新增回归「先复现旧缺陷 → 再验证修复」的
证据、H-1 与 packet 62/63 既有性质未被破坏的证据、剩余风险。然后**停止等待 bookkeeper**。

## 8. bookkeeper（Codex）待办清单

1. **更正审查者模型元数据**：`64-review-1-backend-r3.dispatch.md` 的 RECEIPT 与 `status.json`
   里本次 review 的 `target_model` 由 `claude/Claude Sonnet 5` 更正为 **`claude/Claude Opus 5`**，
   并引用用户在派发执行时的模型替换决定（原话：「sonnet5 能力不够，我特意邀请你 opus5 进行
   review1」）。Review-1 的 JSON `model` 字段已如实写 `Claude Opus 5`。
2. **落盘本授权**：把本文件登记进 `status.json`（授权记录 + `rework_count` 由 4 → 允许第 5 次
   变更 + 授权范围指针），并更新 `70-handoff.md` 的 Recovery Header。
3. **生成正式 packet**：建议编号 `65-fix-review-1-backend-r3.dispatch.md`，
   `target_model: claude_glm / glm-5.2[1m]`，`executor: human_operator`。PROMPT BODY 直接采用
   §9 的逐字 prompt（`AGENTS.md` 要求 reviewer 的 `fix_start_prompt` 不得被 controller 摘要
   替换）。R10 checklist 数据放 RECEIPT / `status.json` 任务元数据，**不要**塞进 immutable
   PROMPT BODY。
4. **§4.4 已由用户拍定为「A：加字段」**（原话「选 A，加字段」），规格已在 §4.4 写死
   （`worker_active` 派生三态含 dry-run 必须为 `None`；`last_worker_exit_reason` 走既有加性列
   迁移；**不新增 entries 事件 kind**；本轮不动前端）。packet 里照抄即可，不需要再问用户。
   同时在 `70-handoff.md` 记一条 follow-up：「前端展示 `worker_active` /
   `last_worker_exit_reason`，提示需人工恢复」。
5. **门禁**：按 `AGENTS.md` 在派发前跑 `scripts/validate-stage.py 2026-07-hedge-open-real-api-v1
   --phase dispatch-ready`（若本 stage 走并行开发模式门）并保留输出；GLM 完成后跑
   `--phase pre-review`。
6. **GLM 完成后**：做 R4 差异核对、创建证据提交、**重算指纹**、准备**重新的后端 Review-1**
   （provider 需与 `zhipu_glm` 隔离）。本次修复触及结算与暂停路径，属于实质代码变更，
   不能沿用旧 verdict 机械重绑。
7. **前端**：`ab3126d..HEAD` 零前端改动，前端 Review-1 的 ACCEPT 按 `25-packet-63-final-
   reconciliation.md` 的路由保留。
8. **实盘门**：本授权**不**解除任何实盘门。live 启用、Start、第一笔真实订单仍是独立的人类授权，
   且应在这两条 P1 修好并通过新一轮 Review-1/Review-2 之后再谈。

## 9. 可直接投递的修复 prompt

**出处与改动说明（透明记录）**：本 prompt **除第 4 条与回归清单外，逐字取自 Review-1 的
`fix_start_prompt`**（`64-review-1-backend-r3.md`），请勿摘要改写。第 4 条原文把「加字段 vs 记为
已接受限制」留给用户选择，用户已于 2026-07-25 拍定为「A：加字段」，因此第 4 条按 §4.4 的规格
**定点替换**并在正文内用【】标注；回归清单相应补入 R7/R8。Review-1 的原始表述保留在
`64-review-1-backend-r3.md` 内，未被覆盖。

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是 2026-07-hedge-open-real-api-v1 的后端返工实现者。禁止调用、启动或转派任何其他模型会话或 adapter。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start、绝不 commit、绝不改 status.json / 70-handoff.md / 任何契约文档（15/16/21/23/24/25/42/50/58/64 号）。

先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md（本评审全文，含最后 JSON verdict 与三段实测复现输出）、21-task-local-runtime-and-manual-pause-amendment.md（运行时最高合同）、24-user-authorized-final-guardian-fix.md（H-1 授权边界）、15-immediate-loop-and-open-log-amendment.md（对账绝不放弃 + 错误矩阵）、42-final-guardian-scanner-fix.md（packet 63 已做的 H-1 修复，必须保留）、40-fix-review-1-backend-r2.md（packet 62 基线）。

被审指纹 ab3126d73549266a615fe43c1aeaf374b0db2d32:4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772 是你的起点，bookkeeper 会在你完成后重算新指纹。

绝对不能破坏的既有性质（packet 62 + 63，全部有回归钉住）：live start() 只做一次 _recover_workers() 后返回且不启动 HedgeOpenScheduler；live tick() 是安全空操作（不枚举任务、不拉 worker）；post_start 只启动指定卡；每卡一个有界 worker 只查自己的腿；target_n 原子硬上限 + 同卡 pair 串行 in-flight 守卫；双腿 pair 内并发；无 orderId 只按 clientOrderId 查询绝不重发；store 锁内不调 executor；7 端点冻结 allowlist 与签名前置门；默认关闭。**不得引入任何全局守护/周期扫描器**。

必须修复四项：

1) P1 —— 粘滞 pause_reason 导致计数器/阈值/致命停机失效。证据：store.set_task_status（store.py:433-444）只更新 status+updated_at_us，从不清 pause_reason/pause_reason_zh；全仓唯一写入点是 pause_task；于是 post_start 恢复后 pause_reason 永久停在 'rate_limited'，service._reconcile_own_legs:1026 的 rate_paused 恒为真，此后每个 pair_outcome IS NULL 的组都走 settle_attempt_no_counters（硬盖 confirmed_failed、完全不调 _apply_task_counters）而不是 finalize_attempt。实测：429 暂停 → 人工恢复 → 下一组两腿都 FILLED（orderId s9/p9）却被记成 confirmed_failed，accepted_pair_count=0、success_count=0、卡片停在 running。修法：(a) 任务回到 RUNNING 时清空 pause_reason 与 pause_reason_zh（与 pause_task 清 stop_reason 对称）；(b) 把「本组免计数」的判定改为基于该 attempt 自身的事实（例如 _dispatch_live 的 429 分支在 attempt 行写一个 rate-limit-settled 标记，_reconcile_own_legs 读该标记选路径），不要再依赖任务级粘滞字段。两者都要做。

2) P1 —— 人工 pause/delete 丢弃在飞真实订单。证据：post_pause（service.py:517-525）置位 stop_event，_worker_round 第一行（939-941）在 _reconcile_own_legs **之前**就 return True 退出，因此 Q2「先 drain 后退」对人工暂停不生效；packet 63 把 live tick 变 no-op 后不再有兜底。实测：一组两腿 UNKNOWN（两笔真实订单可能在交易所）→ post_pause → 一次 _worker_round 得 exit=True 且 query_calls=0、两腿仍 terminal=0，此后 5 次 tick() 零查询。另：_recover_workers（service.py:1163）只遍历 PAUSED/STOPPED，不含 STATUS_DELETED，被删卡片的在飞腿连重启都救不回来。修法：(a) post_pause 不再置位 stop_event，或改置一个 _worker_round 在 _reconcile_own_legs **之后**才检查的暂停标志——这样 worker 先把本卡腿查到终态并结算该组，再因 status != RUNNING 退出（962-963 已保证绝不开新组）；(b) post_delete 同样给一个 drain-only 收尾路径，并把 STATUS_DELETED 加入 _recover_workers 的兜底状态集合。保持任务本地，零全局扫描。

3) P2 —— settle_attempt_no_counters（store.py:1029-1032）硬编码 pair_outcome=PAIR_CONFIRMED_FAILED，无视两腿真实结果且不写 leg_exposure。实测：spot 429 后按 clientOrderId 查到 absent、perp 2xx FILLED（真实裸空头 position_qty=-0.5 已开出），组级却记 confirmed_failed 且 leg_exposure=None。修法：复用 finalize_attempt 的类别推导（按两腿 order_id 决定 accepted/single_leg/failed，single_leg 时写 leg_exposure），只跳过 _apply_task_counters 的计数器/阈值部分（例如给 _apply_task_counters 加 skip_counters 参数）。

4) P2 —— live 卡片可停在 status=running 却无 worker，API 无法分辨。task_to_doc（service.py:118-148）没有 worker 存活字段；worker 在预检不完整/致命、Start gate 关、异常兜底后退出而 task 仍 running。【本条已按用户 2026-07-25 的决定固化为「加字段」，替换 Review-1 原文的二选一表述；原文见 64-review-1-backend-r3.md 的 fix_start_prompt。规格如下，不得自选其它方案】加两个后端权威的加性字段，不改任何调度语义：

   (a) worker_active —— 派生、不落库、无 schema 变更，新增到 task_to_doc。三态：live 可派发模式（_live_dispatch_capable() 为真）由 _workers 注册表派生（在 _workers_lock 临界区内取线程引用，锁外判 is_alive()）；dry-run（record/disabled executor）**必须返回 None**（语义「本模式不适用」），因为 dry-run 没有任务本地 worker（派发在 tick 内同步完成），返回 False 会误导操作员——这是硬要求。诚实性依据：_run_task_worker 的 finally 会把自己从 _workers 弹出（service.py:908-911），注册表反映真实存活。注意 task_to_doc 是模块级函数、不持有 service 实例：允许的最小改法是把 worker_active 作为可选参数传入（各调用点由 service 方法算好再传），或改成 service 上的薄包装方法；**不要**让 task_to_doc 去访问全局状态。二选一并在实现报告说明理由。

   (b) last_worker_exit_reason —— 落库、可为 NULL、新增到 task_to_doc。存储走既有加性迁移模式：在 store._migrate() 的 additions 元组里加一个 TEXT 可空列（与 pause_reason / stop_reason 完全同一写法，store.py:310-321），幂等、老库可读。写入点是 _worker_round 的每个退出分支 + _run_task_worker 的异常兜底，各写一个稳定的机器可读枚举值；枚举常量定义在 domain.py，不要散字符串。建议取值：stopped_event（被 pause/delete/stop 唤醒）、task_not_running、start_gate_off、target_reached、preflight_incomplete、preflight_fatal、worker_error、task_missing。任务重新进入 RUNNING 时把它置 NULL（与第 1 条清 pause_reason 同一处，一并做）。**本轮不加 _zh 中文文案字段**，中文展示留给前端后续决定。

   (c) 明确不做：**不要**新增 entries 时间线的事件 kind。_ENTRY_EVENT_KINDS（service.py:56-62）是已被前端 Review-1 接受的冻结集合，新增 kind 会走 _event_to_entry 的 else 分支被错标成 next_action="waiting_query"，污染已接受的前端契约。worker 退出原因走上面的 task 列，不走 entries。

   (d) 前端边界：本轮**只出后端字段，绝不动 frontend/**（前端在其 Review-1 ACCEPT 后源码未变，必须保持）。UI 展示留作后续 follow-up。两个新键需加进 backend/tests/test_hedge_api.py 的冻结字段集。

（建议项，可一并做）_pump_worker（service.py:913-925）不注册 _stop_events，导致 pause/delete 中断路径零同步覆盖——这正是 P1 #2 逃过 897 个测试的原因。让 seam 与 ensure_worker 共享 stop-event 初始化。

必须新增的确定性回归（离线、fake transport、零 sleep race，先能在修复前复现旧缺陷再验证修复）：
- 429 暂停 → 人工恢复 → 下一组两腿 FILLED ⇒ pair_outcome=accepted_pair、accepted_pair_count=1、success_count=1、pause_reason is None；
- 恢复后连续 3 次已确认失败 ⇒ 仍触发阈值暂停；
- 一组 UNKNOWN 腿 → post_pause ⇒ worker 退出前 query_calls>=2、两腿 terminal=1、该组已结算、scheduled_attempt_count 未增加（没开新组）；
- post_delete 同构一条；DELETED 卡重启后 _recover_workers 能 drain 一条；
- 429 + 另一腿 FILLED ⇒ pair_outcome=single_leg、leg_exposure 非空、fail_count 不变；
- 【随第 4 条固化新增】live 卡预检不完整导致 worker 退出（task 仍 running）⇒ worker_active is False、last_worker_exit_reason == "preflight_incomplete"；worker 存活期间（用 holding executor 观测）⇒ worker_active is True；人工 Start 后 ⇒ last_worker_exit_reason is None；
- 【随第 4 条固化新增】dry-run（record/disabled）模式下的 running 卡 ⇒ worker_active is None（不适用），**不是** False。

允许修改：backend/hedge_open_tasks/{service.py,store.py,domain.py}，backend/services/live_hedge_executor.py（仅本次分类/标记所需的最小改动），backend/tests/test_hedge_task_local.py、test_hedge_review2_regressions.py、test_hedge_store.py、test_hedge_service.py、test_hedge_api.py（若新增字段需同步冻结字段集）。禁止修改：frontend/**、docs/**、PRD、10-design/11-adr、reports/api-samples/**、status.json、70-handoff.md、任何契约文档与本评审文件、环境/凭据/网络配置、backend/hedge_open_tasks/scheduler.py 与 backend/app/server.py（除非新增字段确实需要最小接线，需在报告中说明理由）。

精确自测（提交前全部跑绿，原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：
.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md（新文件，不覆盖已有 40/41/42 号报告），列出 changed files、每条新增回归先复现旧缺陷再验证修复的证据、H-1 与 packet 62 既有性质未被破坏的证据、新增 schema 列的迁移幂等性证据、剩余风险，然后停止等待 bookkeeper——不 commit、不派发评审、不自行判定验收。成功标准：上述八条新增回归在修复前可复现所述缺口、修复后全绿；backend/tests 全量与前端自检、Harness 协议套件全绿；live start()/tick()/post_start 的 H-1 性质与 test_6a/6b/6c 仍全绿；frontend/** 零改动；未新增任何 entries 事件 kind；全程零真实 POST、零私有网络、零凭据访问。
```

## 10. 验收条件（用于新一轮 Review-1）

1. §6 八条回归（R1–R8）在修复前可复现所述缺口、修复后全绿。
2. `backend/tests` 全量、前端自检、Harness 协议套件全绿；`git diff --check` 干净。
3. H-1 三条防线（`test_6a`/`test_6b`/`test_6c`）与 packet 62 的 `test_1`–`test_5`、`test_4b` 仍全绿；
   **没有任何新的全局守护/定时器/周期扫描器被引入**（可用 grep 复核 hedge 路径的
   `Thread(` / `Timer(` / `while True`）。
4. 默认关闭、7 端点冻结 allowlist、签名前置门、store 不持 executor 等安全门无回归。
5. `frontend/**` 零改动；`_ENTRY_EVENT_KINDS` 未被新增 kind；新增的两个 task 字段已进
   `test_hedge_api.py` 冻结字段集；新增列的迁移幂等（老库可读）。
6. 全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/26-user-authorized-settlement-and-pause-fix.md
本地北京时间: 2026-07-25 20:56:34 CST（§4.4 用户决定「选 A，加字段」后更新）
下一步模型: bookkeeper（Codex）
下一步任务: register this user authorization plus the raised rework allowance and the pinned §4.4 decision (choice A, add fields) in status.json/70-handoff.md, correct the reviewer model metadata to Claude Opus 5, record the frontend follow-up for surfacing worker_active, then create packet 65-fix-review-1-backend-r3.dispatch.md carrying the §9 prompt for human-operator execution in a fresh write-capable Claude-GLM session
