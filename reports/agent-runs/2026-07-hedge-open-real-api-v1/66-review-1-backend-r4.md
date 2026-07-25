# 66 — Review-1（后端，第 4 轮）· 2026-07-hedge-open-real-api-v1

**审查者**：Claude Opus 5（Anthropic），只读会话，`[HARNESS-EXECUTOR-CONTRACT v1]`。
**被审代码作者**：Claude-GLM（`glm-5.2[1m]`，provider `zhipu_glm`）——供应商隔离成立。
**dispatch**：`66-review-1-backend-r4.dispatch.md`。

## 0. 身份披露（如实）

我在本 stage 已经做过三轮后端 Review-1（`30-review-1-backend.md` / `58-review-1-backend-r2.md` /
`64-review-1-backend-r3.md`），并按 bookkeeper 要求起草了用户授权回执
`26-user-authorized-settlement-and-pause-fix.md`。**我没有写过任何被审业务代码，也不是修复作者**，
因此 JSON 中 `reviewer_prior_involvement = none`（该枚举只描述 direction/breakdown/design 参与，
我三项皆无）。

按 dispatch 要求：**我没有把上一轮的结论当成本轮的既定事实**。本轮的每一条判断都来自重新阅读
`28c550d..9d1bac0` 的固定 diff 与当前源码，并在本机独立跑测试 + 写离线复现脚本（零网络、零凭据、
零真实 POST、零 live、零 Start、零 commit、未改任何业务文件）。凡是我"确认修好"的地方，都附了
本轮自己跑出来的原始输出。

## 1. 锚点校验

| 项 | 结果 |
| --- | --- |
| base | `28c550d87c1ca90983d5bde9c7102d42cffecd4e` |
| head | `9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c` |
| 指纹（本机按 harness 规则重算） | `fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db` — **逐字一致** |
| `validate-stage --phase pre-review` | `STAGE VALIDATION PASSED`，`status=review_1`，指纹同上 |
| `9d1bac0..HEAD`（4205710） | 仅 `60-test-output.txt` / `65`、`66` dispatch / `70-handoff.md` / `status.json` 四类簿记文件，**零业务改动** |

重算命令与输出：

```text
$ git diff --binary 28c550d..9d1bac0 -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json' | shasum -a 256
fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db  -
```

本轮实际返工范围（`ab3126d..9d1bac0`）：`domain.py +27`、`service.py +133/-…`、`store.py +118`、
`test_hedge_api.py +5`、`test_hedge_task_local.py +328`，其余为报告/簿记。
`live_hedge_executor.py` 未改（与实现报告一致）。

## 2. 先讲人话：这轮到底修好了没有

**四项 P1/P2 的生产代码，我逐条重新验证，结论是真的修好了。** 具体说：

1. **429 恢复后计数器复活了。** 人工按 Start 时 `pause_reason` 会被清掉，而"这一组不算失败"改成看
   **这一组自己**在 429 那一刻打的标记（attempt 行的 `rate_limited` 列），不再看那个会粘住的任务级
   字段。所以恢复之后，成交的组会正确记成 `accepted_pair`、成交笔数会涨，连续三次真失败仍然会
   踩下"自动暂停"这个刹车。
2. **按暂停键不再丢在飞订单了。** 我没有只信同步测试——我起了**真实的 worker 线程**，让它卡在第一次
   查询上，然后在两笔订单真的在飞的时刻调 `post_pause`，观察到 worker 没有被打断，把两条腿都查到
   终态、结算了这一组、**没有开下一组**、然后自己退出。删除卡片同理，且删掉的卡如果留了没查完的腿，
   进程重启时那一次恢复交接会给它拉一个"只对账不开新单"的 worker。
3. **429 组的结论按真事实写了。** 一腿真成交、另一腿真没有，现在会写成 `single_leg` 并落"单腿敞口"
   告警字段，不再一律写"已确认失败"。
4. **卡片能看出来"是不是真的有人在跑"了。** `worker_active`（真实模式 true/false、演练模式 null）
   和 `last_worker_exit_reason`（稳定的机器枚举）都进了任务接口字段集；没有新增时间线事件类型，
   前端一行没动。

**但我发现两个问题，都不影响上面这四条的正确性，却会在"以后"咬人：**

- **A（本轮直接相关）**：号称保护"暂停不丢单"的两条回归 **R3 / R4 是空的**——我用不改任何仓库文件的
  猴补丁把旧缺陷原样放回去，R3 的四条断言**全部照样通过**；我又把修复前的 seam 语义重建出来跑，
  R3 **在修复前也照样通过**。也就是说这两条回归既没复现过旧缺陷、也钉不住新修复。更讽刺的是，
  §4.5 那条 P3 建议的原话是"让 pause/delete 中断语义**可被同步测试观察**"，而实现的做法是在
  `_pump_worker` 开头**无条件清掉** stop event，等于把这个语义**从测试里彻底遮住了**——方向做反了。
  这正是上一轮 P1-2 能瞒过 897 个测试的同一个机制。
- **B（既存，但就在本轮改动的那一行上）**：`_recover_workers` 的"只对账"兜底这轮加了 `DELETED`，
  但**漏了 `DONE`**。一张卡打完最后一组达标变成 `done` 时，那一组的现货腿完全可能还停在
  "已受理、还在成交中"（`NEW`）——这时重启进程，**没有任何人再去查它**。结果：这笔真实成交的现货腿
  永远记 0，持仓面板会把一组**已经对冲好的**仓位显示成**裸空头**，且永久不会自愈。我写了离线脚本
  实测复现（见 §4.2）。

## 3. 逐项核对 dispatch 要求的六件事

### 3.1 429 → 人工恢复（要求 1）✅

- `store.set_task_status`（`store.py:439-457`）：转 `RUNNING` 时一次性把
  `pause_reason` / `pause_reason_zh` / `last_worker_exit_reason` 置 NULL；其余状态转移只动
  `status` + `updated_at_us`。我 grep 了全仓 `set_task_status` 的 5 个调用点
  （`service.py:530/547/558/569/582`），转 RUNNING 的三处都是**人工动作**
  （Start / fill-once / fill-all），没有自动路径会误清。
  `_apply_task_counters` 的自动状态迁移走独立 UPDATE，不经过这里，也不会把 paused 自动翻回 running
  （`domain.resolve_status_after_attempt` 只产出 deleted/stopped/done/paused/原状态）。
- 逐次尝试事实：`_dispatch_live` 的 429 分支 `mark_attempt_rate_limited(attempt["id"])`
  （`service.py:1452-1458`）；`_reconcile_own_legs` 改读 `get_attempt(...)["rate_limited"]`
  （`service.py:1076-1087`），与任务级 `pause_reason` 彻底解耦。
- **反向确认（重要）**：drain 阶段查询自己撞 429（`_reconcile_own_legs` 返回
  `SIGNAL_RATE_LIMITED`）**不会**给 attempt 打标记 —— 这是对的：那一组的失败不是限频造成的，
  它的真实结果该计就得计。这精确满足"不计失败必须只来自该 attempt 自身的限频事实"。
- **非限频 fatal 不被跳过**：`rate_limited=0` 的组走 `finalize_attempt`
  （`store.py:981-1046`），其中 `error_category == 'fatal'` → `stop_task_fatal` 路径原样保留，
  `test_4b_unconfirmed_minus_2010_stays_fatal_stop_not_pause` 本轮仍绿。
- R1 / R2 **确实钉住**修复：R1 断言 `resumed["pause_reason"] is None`（修复前必挂）、
  R2 断言恢复后 3 次确认失败仍 `pause_reason == consecutive_submission_failure` 且 `fail_count == 3`
  （修复前粘滞 `rate_paused` 会让 `fail_count` 停在 0，必挂）。

### 3.2 人工 pause / delete 的对账收尾（要求 2）✅ 生产行为正确，⚠️ 回归无效（见 P2-1）

生产路径我**用真实线程**独立验过（不是只跑给定的同步 seam）。脚本让 executor 卡在第一次
`query_leg`，确保 `post_pause` 落在"两笔订单真的在飞"的时刻：

```text
pacing interval_us           : 1000000
in-flight legs at pause time : 2
worker alive                 : False
query_calls                  : 2
both legs terminal           : True
pair settled                 : confirmed_failed
attempts opened              : 1 (scheduled_attempt_count 1 was 1 )
status                       : paused
last_worker_exit_reason      : task_not_running
worker_active (API doc)      : False
```

即：worker 未被打断 → 自己把两条腿查到终态 → 结算该组 → **`scheduled_attempt_count` 不变
（没开下一组）** → 因 `status != RUNNING` 退出并写下稳定退出原因。`post_delete` 同构
（`service.py:552-559`，`_worker_round:1010-1011` 保证绝不开新组）。

- `_wake_worker` 已整体删除，全仓零残留（grep 确认）；`service.stop()`（`service.py:412-418`）
  仍会 set 所有 stop event，进程关停语义未破坏。
- `_recover_workers`（`service.py:1219`）的只对账兜底集合已含 `STATUS_DELETED`；
  `store.list_tasks(STATUS_DELETED)` 的 else 分支按精确状态查，可正常返回被删卡
  （`store.py:431-436`）。R5 用**真实线程 + spy** 验证重启后 drain 到终态、`dispatch_calls == 1`
  （零重发）、`status` 保持 `deleted` sticky —— 这条回归**是有效的**（修复前 `DELETED` 不在集合里，
  `doc["id"] in ensured` 必挂）。
- **没有借机复活周期 tick / 全局 scanner / timer / 跨卡联动**：`tick()` 在 live 仍是
  `return False` 空操作（`service.py:1141-1142`）；`grep -rn "Thread(\|Timer(\|while True"`
  在 hedge 路径只命中「每卡 worker 线程」「dry-run 每卡 tick 线程」「HedgeOpenScheduler（live 不启）」
  「executor 的两条腿并发线程」四处，均为既有；`test_6a/6b/6c` 本轮全绿。

### 3.3 429 组的真实结果（要求 3）✅

`settle_attempt_no_counters`（`store.py:1049-1105`）现在读两条腿完整行，按 `order_id` 存在性推导
`accepted / single_leg / failed`，`single_leg` 时用 `_exposure_from_legs` 构造 advisory
`leg_exposure`，再经 `_apply_task_counters(..., skip_counters=True)` 落地。

`skip_counters` 早分支（`store.py:713-730`）我逐行核过：**只**推导 `pair_outcome` 与
`leg_exposure_json`；`new_accepted/new_success/new_fail/new_consecutive/new_status/pause_reason/
new_stop_reason` 全部保持读入时的原值，末尾那条 UPDATE 因此对计数器/状态/阈值/停机原因是等值写回；
两个 entries 事件的插入条件（`fatal and ...` / `new_status == PAUSED and task["status"] != PAUSED`）
在该分支下恒不成立，**不会污染时间线**。R6 钉住（修复前硬写 `confirmed_failed`，
`pair_outcome == single_leg` 必挂）。

### 3.4 可观测字段（要求 4，用户选 A）✅

- `worker_active`：`_worker_active_for`（`service.py:508-516`）先判 `_live_dispatch_capable()`，
  dry-run 直接返回 `None`；live 时在 `_workers_lock` 内取线程引用再判 `is_alive()`，
  由 `_run_task_worker` 的 `finally` 弹出注册表保证不是陈旧缓存。**派生、不落库、无 schema 变更**，
  符合规格。R8 断言 dry-run 为 `None`（不是 `False`）。
- `task_to_doc` 保持模块级函数，`worker_active` 走**可选关键字参数**注入，由 service 的薄包装
  `_doc()` 计算后传入（`service.py:118`、`518-519`）——采用了规格允许的两种最小改法之一，
  未让 `task_to_doc` 访问全局状态。全仓 9 个投影点已全部改走 `_doc`（grep 确认无漏网的裸
  `task_to_doc` 调用）。
- `last_worker_exit_reason`：`domain.py:185-208` 定义 8 个稳定枚举 + `ALL_WORKER_EXIT_REASONS`；
  `store._migrate` 的 `additions` 元组加性迁移（`store.py:322`），`PRAGMA table_info` 守卫、
  老库幂等；`_worker_round` 六个退出分支 + `_run_task_worker` 异常兜底全部写入
  （`service.py:989/992/1011/1013/1015/1029/1031/932-936`），进入 RUNNING 与 `ensure_worker`
  两处清除。
- **锁序无死锁**：`ensure_worker` 在 `_workers_lock` 内调 `store.set_worker_exit_reason`
  （取 store 锁），方向恒为 `_workers_lock → store._lock`；store 从不回调 service，
  `_run_task_worker` 的 `finally` 取 `_workers_lock` 时不持 store 锁。**"store 锁内不调 executor"
  这条 Q6 底线未被触碰**（`test_hedge_purity.py` 13 条本轮全绿）。
- **契约面**：两键已进 `test_hedge_api.py` 的冻结集 `_TASK_KEYS`（第 46-47 行）；
  `_ENTRY_EVENT_KINDS`（`service.py:56-62`）**逐字未动**；`frontend/**`、`docs/**`、
  `scheduler.py`、`server.py`、`backend/services/**` 在 `ab3126d..9d1bac0` 区间内 **零改动**
  （`git diff --stat` 输出为空）。

### 3.5 既有底线不回归（要求 5）✅

H-1 三条防线（`test_6a/6b/6c`）+ packet 62 的 `test_1`–`test_5`、`test_4b` 本轮本机复跑
**10 passed**。`git diff` 全区间 grep `api_key|secret|BINANCE_|password|token` 的新增行为空——
**未引入任何凭据**；`config.py` 无新增实盘开关，默认关闭未被改动；7 端点冻结 allowlist 与签名前置门
所在文件（`server.py` / `hedge_open_live_client.py`）本轮零改动；entries 独立分页兼容旧 logs 的实现
未被触及。

### 3.6 测试与范围（要求 6）✅ 数据全部对得上

本机独立复跑，与 packet 65 / `60-test-output.txt` 的记录一致：

| 命令 | 本轮实测 | 报告声称 |
| --- | --- | --- |
| 十组聚焦 | **229 passed** in 15.47s | 229 passed ✅ |
| `pytest backend/tests -q` | **905 passed** in 48.67s | 905 passed ✅ |
| `node frontend/self-check.js` | **全部自检通过** | 通过 ✅ |
| `scripts/tests/test_validate_stage_dispatch_protocol.py` | **55 passed** | 55 passed ✅ |
| `git diff --check` | exit 0 | exit 0 ✅ |
| `validate-stage --phase pre-review` | PASSED | — |

工作树干净，无越界文件，无凭据，无实盘激活。

## 4. Findings

### P2-1 —— R3 / R4 是空回归：既没复现旧缺陷，也钉不住新修复（本轮直接相关）

**根因**：`_pump_worker`（`service.py:942-964`）这轮新增的 P3 改动，在**每次调用开头无条件
`ev.clear()`**。而测试辅助 `_step()`（`test_hedge_task_local.py:57-63`）就是 `_pump_worker` 的一次
调用，R3/R4 的写法是 `_step(1) → post_pause() → _step(3)`——第二次 `_step` 把 `post_pause` 可能置位的
stop event **又清掉了**。

**证据 1（把旧缺陷放回去，R3 照样全绿）**：猴补丁把删掉的 `_wake_worker` 语义原样加回
`post_pause`，**不改仓库任何文件**：

```text
stop_event set right after the regressed post_pause : True
R3 assertions under the SIMULATED REGRESSION:
  query_calls >= 2                    : True (2)
  both legs terminal                  : True
  pair settled (pair_outcome not NULL) : True
  no new pair opened                  : True
```

**证据 2（重建修复前 seam 语义，R3 也照样全绿）**：把 `_pump_worker` 还原成"不注册 stop event"、
`post_pause` 还原成"调 `_wake_worker`"：

```text
R3 assertions under RECONSTRUCTED PRE-FIX semantics:
  stop_events registered at all       : {}
  query_calls >= 2                    : True (2)
  both legs terminal                  : True
  pair settled                        : True
  no new pair opened                  : True
```

**影响**：

1. 用户授权书 §10.1 的验收条件"§6 八条回归在**修复前可复现所述缺口**、修复后全绿"，
   **对 R3 / R4 客观未达成**；`44-fix-review-1-backend-r3.md` §3 表格里 R3/R4 那两行的
   "旧代码缺口 → 已复现"是**不成立的陈述**，证据链因此失真。
2. 本 stage 最危险的那条路径（人工按暂停/删除时不得丢弃在飞真实订单）**在 905 个测试里没有任何
   有效护栏**。任何后续重构把 `post_pause` 的中断加回去，全套测试仍然全绿。
3. §4.5 P3 建议的原始目的是"让 pause/delete 中断语义**可被同步测试观察**"；无条件 `clear()`
   把它**变得更不可观察**，方向与授权书相反。

**修法（最小、不动生产语义）**：`_pump_worker` 不要吞掉 stop event —— 例如只在**首次注册**时创建并
clear，已存在则保持原状（或加一个仅测试使用的 `reset_stop_event=False` 形参，由需要的用例显式重置）；
然后给 R3/R4 各加一条断言，直接观察 `post_pause` / `post_delete` **没有**置位该卡的 stop event
（`svc._stop_events[tid].is_set() is False`），并保留现有 drain 断言。可选加强：把 R3 改成
真实线程版（本报告 §3.2 的脚本即为可直接改写的模板），让它同时覆盖生产线程路径。

### P2-2 —— `_recover_workers` 的只对账兜底漏了 `STATUS_DONE`：达标那一组的真实成交腿永久不再对账

**根因**：`service.py:1219` 的兜底状态集合本轮从 `(PAUSED, STOPPED)` 扩到
`(PAUSED, STOPPED, DELETED)`，仍不含 `DONE`。而 `resolve_attempt(leg_terminal=...)`
（`store.py:892-924`）在"两腿都拿到 orderId、但其中一腿仍是 `NEW`/`PARTIALLY_FILLED`"时，
会**先把该组判为 accepted 并把任务推到 `done`**，同时把那条腿留在 `terminal=0`
（`service._leg_terminal`，`service.py:1530-1538`：已受理但未 FILLED 的腿故意保持非终态待轮询）。
在途中重启，该腿再也没有任何人去查。

**证据（离线复现，零网络）**：`target_n=1`，一组两腿都成交受理、perp FILLED、spot 仍 NEW：

```text
after dispatch:
  task status          = done
  accepted_pair_count  = 1
  leg perp order_id=p1 status=FILLED terminal=1 cum_base=0.5
  leg spot order_id=s1 status=NEW    terminal=0 cum_base=0
  non-terminal legs    = 1
  positions            = [{'coin': 'BTCUSDT', ..., 'position_qty': '-0.5', 'spot_avg': '0', 'perp_avg': '50000', ...}]

-- process restart (new service instance, same sqlite file) --
  ensure_worker calls during recovery = []
  query_calls made                    = 0
  leg spot terminal=0 status=NEW cum_base=0
  non-terminal legs still = 1
  positions               = [{... 'position_qty': '-0.5', 'spot_avg': '0' ...}]
```

**影响**：现货腿在币安其实已经成交，本系统永久记 0。`aggregate_positions`
（`store.py:1567-1576`）只累加 `exchange_status == FILLED` 的腿，于是一组**已经对冲好的**仓位在
持仓面板上被永久显示成 **`position_qty=-0.5` 的裸空头、`spot_avg=0`**，且不会自愈——正是本 stage
要防的那类账本失真。RUNNING/PAUSED/STOPPED/DELETED 都有兜底，唯独 `DONE` 没有。

**性质说明（对实现者公平）**：这是 base 提交就存在的既存缺口，**不是本轮引入的回归**；只是它恰好
落在本轮修改的同一行上，而本轮的主题正是"重启的那一次恢复交接必须救回在飞腿"。

**修法**：把 `D.STATUS_DONE` 加进 `service.py:1219` 的兜底元组（`ensure_worker` 拉起的 worker 在
`_worker_round` 里 drain 完即因 `status != RUNNING` 退出，不会开新组，与 DELETED 完全同构），
并加一条与 R5 同构的回归：done 卡带非终态受理腿 → 新实例 `start()` → 该腿被查到终态、
`dispatch_calls` 不增、`status` 仍 `done`。**注意：此项超出用户 §4/§5 授权范围，需 bookkeeper
先取得用户对第 6 次变更的授权再派发。**

### P3-1 —— `settle_attempt_no_counters` 不落 attempt 级 `error_category` / `error_code` / `error_reason_zh`

`finalize_attempt`（`store.py:1038-1045`）会把这三列写到 attempt 行，`settle_attempt_no_counters`
（`store.py:1096-1099`）只写 `pair_outcome`。于是 429 组即使某条腿查回带业务码的结果，
attempt 行的错误列仍为 NULL，审计与将来的排障少一手。**影响仅限可观测性**：`classify_query_response`
（`live_hedge_executor.py:288-341`）只会产出 `absent` 分类，**不会**产出 `fatal`，所以不存在
"429 组把致命腿的停机吞掉"的安全问题（我专门核过这条链路）。建议后续把这三列一并补齐。

### P3-2 —— 人工 Start 撞上 worker 退出窗口时可能静默空转

`ensure_worker`（`service.py:885-888`）看到注册表里线程 `is_alive()` 就复用。若 `_worker_round`
已判定退出、但线程尚未走到 `finally` 弹出注册表，此刻的 `post_start` 会返回 200 而**不真正拉起
worker**，卡片停在 `running` 却无人跑。窗口极窄（一次 store 写入的量级），且**本轮新增的
`worker_active` 恰好让操作员能直接看出来**（`worker_active=false` + `status=running`）。
既存问题，非本轮引入。建议 follow-up：`ensure_worker` 复用前顺带确认该线程不是正在退出，
或前端在这两个字段同时命中时提示"需再次 Start"。

### P3-3 —— `post_start` 响应把"派发前的任务行"和"派发后的 worker_active"拼在一起

`post_start`（`service.py:530-535`）先 `set_task_status` 取到 `updated`，再 `ensure_worker`，
最后 `self._doc(updated)`：`last_worker_exit_reason` 来自派生 worker 之前的快照，
`worker_active` 来自派生之后的注册表。单次响应内部时序不一致，下一次 GET 即自洽。纯展示层瑕疵。

## 5. 结论与理由

四项授权修复的**生产代码全部正确**，六条底线**无回归**，测试数据**逐条对得上**，范围**无越界**、
**零凭据**、**零实盘**。若只看功能，本轮已经达标。

我给 `REWORK` 的理由只有一条，而且是硬条件：**用户授权书 §10.1 明确把"八条回归在修复前可复现所述
缺口"写进了验收条件，而 R3/R4 客观不满足**——我用两个方向的实验证明了它们既没复现过旧缺陷、也钉不住
新修复，同时实现报告把"已复现"写成了既成事实。按 `AGENTS.md`，审查者不能把一条未达成的验收条件
normalize 掉。更实际的考虑是：这恰恰是**上一轮 P1-2 能瞒过 897 个测试的同一个 seam 盲区**，
而下一步就是第一笔真钱订单——在这个节点留一条空护栏，代价不对称。

P2-1 的修法非常小（一处 seam 语义 + 两条断言），P2-2 是一行加 `STATUS_DONE` 加一条同构回归。
建议 bookkeeper 把两项合并成**一次严格有界的第 6 次变更**；其中 P2-2 超出既有 §4/§5 授权，
需先取得用户授权。三条 P3 建议记为 follow-up，不进本次修复。

前端 Review-1 的 ACCEPT 应按 `26-...fix.md` §8.7 保留：`ab3126d..9d1bac0` 与 `28c550d..9d1bac0`
本轮区间内 `frontend/**` 均零改动。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md
本地北京时间: 2026-07-25 23:07:10 CST
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 REWORK verdict, obtain the user's authorization for a 6th bounded change (P2-2 is outside the §4/§5 scope), create the fix packet from the fix_start_prompt below, and keep routing the preserved frontend ACCEPT

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Opus 5",
  "verdict": "REWORK",
  "diff_fingerprint": "9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c:fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Claude Opus 5 wrote no reviewed code and is not the fix author (implementer/fix author is Claude-GLM, provider zhipu_glm — provider isolation holds). Disclosure: this reviewer produced the three prior backend Review-1 reports in this stage (30-review-1-backend.md, 58-review-1-backend-r2.md, 64-review-1-backend-r3.md) and, at the bookkeeper's request, drafted the user-authorization receipt 26-user-authorized-settlement-and-pause-fix.md. It took no part in direction synthesis, development breakdown, or design, hence the enum value 'none'. Per the dispatch, no prior-round conclusion was carried forward as established fact: every judgement here was re-derived from the pinned 28c550d..9d1bac0 diff, the current sources, locally re-run tests, and this reviewer's own offline reproduction scripts.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/26-user-authorized-settlement-and-pause-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/65-fix-review-1-backend-r3.dispatch.md",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/domain.py",
    "backend/services/live_hedge_executor.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_hedge_api.py",
    "backend/tests/test_hedge_purity.py"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "R3/R4 are vacuous regressions: they never reproduced the P1-2 defect and do not pin the fix",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 953,
      "evidence": "_pump_worker now unconditionally clears the per-task stop event at the top of EVERY call (service.py:953-958), and the test helper _step() (test_hedge_task_local.py:57-63) is exactly one _pump_worker call. R3/R4 run _step(1) -> post_pause()/post_delete() -> _step(3), so the second _step wipes any stop event the pause may have set. Reviewer experiment 1 (monkeypatch only, zero repo files touched) re-introduced the deleted _wake_worker semantics into post_pause and re-ran R3's exact scenario: 'stop_event set right after the regressed post_pause : True' yet 'query_calls >= 2 : True (2) / both legs terminal : True / pair settled : True / no new pair opened : True' — all four R3 assertions still pass with the defect present. Reviewer experiment 2 reconstructed the pre-fix seam (no stop-event registration in _pump_worker, _wake_worker in post_pause) and R3 also passed: 'stop_events registered at all : {}' plus the same four True results.",
      "impact": "The user's authorization §10.1 acceptance condition ('R1-R8 must reproduce the stated gap before the fix and be green after') is objectively not met for R3/R4, and 44-fix-review-1-backend-r3.md §3 asserts the reproduction happened, which is a false statement in the evidence record. Operationally, the single most dangerous path in this stage — a manual pause/delete must never abandon in-flight REAL orders — has no effective guard among the 905 tests: any future refactor can re-introduce the interrupt with the whole suite still green. This is the same seam blindness that hid the P1-2 defect through 897 tests last round, and it is inverted relative to the §4.5 P3 item, whose stated purpose was to make the pause/delete interrupt semantics OBSERVABLE in synchronous tests.",
      "recommendation": "Stop swallowing the stop event in _pump_worker: create+clear it only on first registration, or add a test-only keyword (e.g. reset_stop_event=False) so a case must opt in to resetting. Then add to R3 and R4 a direct assertion that post_pause/post_delete leaves the task's stop event UNSET (svc._stop_events[tid].is_set() is False) alongside the existing drain assertions. Optionally strengthen R3 into a real-thread variant (a gated executor that blocks the first query_leg until the pause is issued) so the production thread path is covered too. Do not change any production pause/delete semantics — they are correct as shipped."
    },
    {
      "severity": "P2",
      "title": "_recover_workers drain-only fallback omits STATUS_DONE, so a target-reaching pair's real accepted leg is never reconciled after a restart",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1219,
      "evidence": "The fallback set was widened this round from (PAUSED, STOPPED) to (PAUSED, STOPPED, DELETED) but still excludes DONE. resolve_attempt(leg_terminal=...) (store.py:892-924) marks a pair accepted — pushing the task to done — while leaving an accepted-but-NEW/PARTIALLY_FILLED leg at terminal=0 by design (service._leg_terminal, service.py:1530-1538). Reviewer offline reproduction (target_n=1, perp FILLED, spot accepted+NEW, zero network): after dispatch 'task status = done / leg spot order_id=s1 status=NEW terminal=0 cum_base=0 / non-terminal legs = 1'; after a fresh service instance on the same sqlite file called start(): 'ensure_worker calls during recovery = [] / query_calls made = 0 / leg spot terminal=0 status=NEW cum_base=0 / non-terminal legs still = 1'. aggregate_positions (store.py:1567-1576) only sums legs whose exchange_status == FILLED.",
      "impact": "A spot leg that really filled at Binance is recorded as 0 forever, so a fully hedged final pair renders permanently as a naked short (position_qty=-0.5, spot_avg=0) in the positions panel, with no self-healing path. RUNNING/PAUSED/STOPPED/DELETED all have a recovery fallback; only DONE does not. This is exactly the ledger-distortion class this stage exists to prevent. NOTE FOR FAIRNESS: this gap pre-dates the reviewed change (it is not a regression introduced this round) — it simply sits on the very line this round edited, in a round whose subject is 'the one startup handoff must rescue in-flight legs'.",
      "recommendation": "Add D.STATUS_DONE to the drain-only fallback tuple at service.py:1219 (a worker launched on a done task drains its own legs and then exits on the status != RUNNING check, opening no new pair — structurally identical to the DELETED case just added), and add one R5-isomorphic regression: a done card holding an accepted non-terminal leg -> new instance start() -> the leg is queried to terminal, dispatch_calls does not increase, status stays done. This item is OUTSIDE the user's §4/§5 authorization, so the bookkeeper must obtain the user's authorization for a 6th bounded change before dispatching it."
    },
    {
      "severity": "P3",
      "title": "settle_attempt_no_counters does not stamp the attempt-level error_category / error_code / error_reason_zh columns",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1096,
      "evidence": "finalize_attempt writes those three columns onto the attempt row (store.py:1038-1045); settle_attempt_no_counters writes only pair_outcome (store.py:1096-1099). A 429-settled pair therefore leaves them NULL even when a leg query returned a business code.",
      "impact": "Observability/audit only. There is NO safety consequence: classify_query_response (live_hedge_executor.py:288-341) can only produce error_category 'absent', never 'fatal', so a rate-limited pair cannot swallow a fatal-stop obligation. Verified by reading the full query classification chain.",
      "recommendation": "Follow-up: carry the same three columns through the settle path so a 429-settled pair's audit trail matches a finalized one. Not required for this fix round."
    },
    {
      "severity": "P3",
      "title": "A manual Start landing inside a worker's exit window can silently no-op",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 886,
      "evidence": "ensure_worker reuses the registry entry whenever existing.is_alive() (service.py:885-888). If _worker_round has already decided to exit but the thread has not yet reached the finally block that pops the registry, a concurrent post_start returns 200 without launching a worker, leaving the card at status=running with nobody running it. The window is on the order of one store write.",
      "impact": "Narrow and pre-existing (not introduced this round). Materially mitigated by this round's new field: the operator can now see worker_active=false together with status=running and press Start again.",
      "recommendation": "Follow-up: have ensure_worker confirm the reused thread is not already exiting (e.g. an 'exiting' marker set by _worker_exit), or have the frontend surface a 'press Start again' hint when worker_active is false while status is running."
    },
    {
      "severity": "P3",
      "title": "post_start's response mixes a pre-spawn task row with a post-spawn worker_active",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 530,
      "evidence": "post_start captures `updated` from set_task_status, then calls ensure_worker, then returns self._doc(updated): last_worker_exit_reason comes from the snapshot taken BEFORE the worker was spawned while worker_active is derived AFTER. service.py:530-535.",
      "impact": "Cosmetic, single-response internal inconsistency; the next GET is self-consistent. No behavioural effect.",
      "recommendation": "Follow-up: re-read the task row after ensure_worker before projecting, or document the ordering. Not required for this fix round."
    }
  ],
  "required_fixes": [
    "P2-1 (in scope, non-negotiable): stop _pump_worker from unconditionally clearing the per-task stop event (service.py:953-958) — register-and-clear only on first creation, or gate the reset behind an explicit test-only keyword — and add to R3 and R4 a direct assertion that post_pause / post_delete leaves the task's stop event UNSET, so both regressions genuinely fail if the _wake_worker interrupt is ever re-introduced. Keep every existing drain assertion. Do not change any production pause/delete semantics: they are verified correct as shipped.",
    "P2-2 (OUTSIDE the §4/§5 authorization — the bookkeeper must obtain the user's authorization for a 6th bounded change first): add D.STATUS_DONE to the drain-only recovery fallback at service.py:1219 and add one R5-isomorphic regression proving a done card holding an accepted non-terminal leg is drained to terminal by the ONE startup handoff, with dispatch_calls unchanged (zero resend) and status still done."
  ],
  "residual_risks": [
    "P3-1: a 429-settled attempt leaves error_category / error_code / error_reason_zh NULL, unlike a finalized one. Audit-only; no fatal-stop obligation can be swallowed because classify_query_response never emits 'fatal'.",
    "P3-2: the narrow ensure_worker reuse race can make a manual Start no-op; now detectable via worker_active=false + status=running.",
    "P3-3: post_start's single response mixes a pre-spawn task row with a post-spawn worker_active.",
    "Cross-process reservation guard (prepare_attempt relying on SQLite DEFERRED read-then-write) remains unaddressed by explicit user decision (26-...fix.md §4.6); only reachable if two service processes are made to share one sqlite file, which is not the deployment.",
    "Active throttling on X-MBX-ORDER-COUNT-* response headers is still unimplemented and truthfully recorded.",
    "worker_active is an instantaneous best-effort snapshot of the _workers registry, not a strongly consistent lock — this is its designed semantics, not a defect.",
    "aggregate_positions filters out DELETED tasks (store.py:1567-1576, pre-existing at base), so a deleted card's real single-leg exposure disappears from the positions panel even though the drain now settles it correctly."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 2026-07-hedge-open-real-api-v1 的后端返工实现者（第 6 次有界变更）。禁止调用、启动或转派任何其他模型会话或 adapter。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start、绝不 commit、绝不改 status.json / 70-handoff.md / 任何契约文档（15/16/17/19/21/23/24/25/26 号）与任何评审报告（30/42/50/58/64/66 号）。\n\n先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md（本评审全文，含 §4 两条 P2 的原始复现输出与末尾 JSON verdict）、26-user-authorized-settlement-and-pause-fix.md（用户第 5 次授权与 §10 验收条件）、21-task-local-runtime-and-manual-pause-amendment.md（运行时最高合同）、24-user-authorized-final-guardian-fix.md（H-1 边界）、15-immediate-loop-and-open-log-amendment.md（对账绝不放弃 + 错误矩阵）、44-fix-review-1-backend-r3.md（上一轮实现报告）、42-final-guardian-scanner-fix.md 与 40-fix-review-1-backend-r2.md（packet 62/63 必须保留的既有性质）。\n\n被审指纹 9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c:fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db 是你的起点，bookkeeper 会在你完成后重算新指纹。\n\n重要前提：**上一轮四项 P1/P2 的生产代码已被 Review-1 逐条重新验证为正确**（429 恢复清粘滞 + 逐次尝试 rate_limited 标记；人工 pause/delete 由本卡 worker drain 后退出且不开新组，已用真实线程独立复验；settle_attempt_no_counters 按两腿真实事实推导并落 leg_exposure；worker_active 三态 + last_worker_exit_reason）。**不要重做、不要重构、不要顺手改进这四项的生产语义。** 本次只做下面两件事。\n\n绝对不能破坏的既有性质（全部有回归钉住）：live start() 只做一次 _recover_workers() 后返回且不启动 HedgeOpenScheduler；live tick() 是安全空操作；post_start 只启动指定卡；每卡一个有界 worker 只查自己的腿；同卡 pair 串行、双腿并发；跨卡隔离；target_n 原子硬上限；无 orderId 只按 clientOrderId 查询绝不重发（ADR-2）；store 锁内不调 executor；7 端点冻结 allowlist 与签名前置门；默认关闭；_ENTRY_EVENT_KINDS 不得新增 kind；frontend/** 零改动。**不得引入任何全局守护/周期扫描器/timer。**\n\n必须修复两项：\n\n1) 【P2-1，必做】R3 / R4 是空回归 —— 既没复现过旧缺陷，也钉不住新修复。证据：_pump_worker（service.py:942-964）这轮新增的 P3 改动在**每次调用开头无条件 ev.clear()**，而测试辅助 _step()（test_hedge_task_local.py:57-63）就是一次 _pump_worker 调用；R3/R4 的写法是 _step(1) → post_pause()/post_delete() → _step(3)，第二次 _step 把 post_pause 可能置位的 stop event 又清掉了。Review-1 实测（猴补丁，未改仓库文件）：把删掉的 _wake_worker 语义原样加回 post_pause 后，'stop_event set right after the regressed post_pause : True'，而 R3 四条断言 query_calls>=2(2) / both legs terminal / pair settled / no new pair opened **全部照样通过**；又重建修复前 seam 语义（_pump_worker 不注册 stop event + post_pause 调 _wake_worker），'stop_events registered at all : {}'，R3 **同样全绿**。这违反用户授权书 §10.1 的验收条件，并使本 stage 最危险的路径（人工暂停/删除不得丢弃在飞真实订单）在 905 个测试里没有任何有效护栏。修法：(a) 让 _pump_worker 不再吞掉 stop event —— 只在**首次注册**时创建并 clear，已存在则保持原状；或加一个仅测试使用的形参（如 reset_stop_event: bool = False），由确实需要重置的用例显式传入。(b) 给 R3 与 R4 各加一条直接断言：post_pause / post_delete 之后该卡的 stop event **未被置位**（svc._stop_events[tid].is_set() is False），并保留现有全部 drain 断言。(c) 可选加强：把 R3 再加一个真实线程版本 —— 用一个在首次 query_leg 上阻塞的 executor，确保 post_pause 落在两腿真在飞的时刻，再断言 worker 自行 drain 到终态、结算该组、scheduled_attempt_count 不增、最终退出且 last_worker_exit_reason == task_not_running。**不要改动 post_pause / post_delete / _worker_round 的生产语义。**\n\n2) 【P2-2，需用户已授权后才做】_recover_workers 的只对账兜底（service.py:1219）本轮从 (PAUSED, STOPPED) 扩到 (PAUSED, STOPPED, DELETED)，仍漏了 DONE。证据：resolve_attempt(leg_terminal=...)（store.py:892-924）在两腿都拿到 orderId、但其中一腿仍 NEW/PARTIALLY_FILLED 时，会先把该组判为 accepted 并把任务推到 done，同时按设计把那条腿留在 terminal=0（service._leg_terminal, service.py:1530-1538）。Review-1 离线实测（target_n=1，perp FILLED，spot 受理但 NEW，零网络）：派发后 'task status = done / leg spot order_id=s1 status=NEW terminal=0 cum_base=0 / non-terminal legs = 1'；同一 sqlite 换新实例 start() 后 'ensure_worker calls during recovery = [] / query_calls made = 0 / leg spot terminal=0 cum_base=0 / non-terminal legs still = 1'。而 aggregate_positions（store.py:1567-1576）只累加 exchange_status == FILLED 的腿，于是这笔真实成交的现货腿永久记 0，一组**已经对冲好的**仓位被永久显示成裸空头（position_qty=-0.5, spot_avg=0），不会自愈。修法：把 D.STATUS_DONE 加进 service.py:1219 的兜底元组（该 worker drain 完即因 status != RUNNING 退出，绝不开新组，与刚加的 DELETED 完全同构），并新增一条与 R5 同构的确定性回归：done 卡带受理但非终态的腿 → 新实例 start() 的一次恢复交接把它查到终态、dispatch_calls 不增（零重发）、status 仍为 done。\n\n必须新增/加强的确定性回归（离线、fake transport、零 sleep race）：\n- R3 / R4 各加「post_pause / post_delete 后 stop event 未被置位」断言，并确认在把 _wake_worker 语义放回去时这两条会**失败**（在实现报告里给出你自己的验证输出）；\n- （可选）R3 的真实线程版本；\n- 【随 P2-2】done 卡带非终态受理腿 → 重启一次 recovery → drain 到终态、零重发、status 仍 done。\n\n允许修改：backend/hedge_open_tasks/service.py（仅 _pump_worker 的 stop-event 初始化 + _recover_workers 的兜底状态元组）、backend/tests/test_hedge_task_local.py、reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt（仅追加原始输出）、reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md（新建实现报告，不覆盖已有 40/41/42/44 号报告）。禁止修改：backend/hedge_open_tasks/{store.py,domain.py}、backend/services/**、backend/app/server.py、backend/hedge_open_tasks/scheduler.py、frontend/**、docs/**、PRD、10-design/11-adr、reports/api-samples/**、status.json、70-handoff.md、任何契约文档与评审报告、环境/凭据/网络配置文件。\n\n精确自测（提交前全部跑绿，原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：\n.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q\n.venv/bin/python -m pytest backend/tests -q\nnode frontend/self-check.js\n.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q\ngit diff --check\n\n基线参照（Review-1 本机实测）：十组聚焦 = 229 passed；backend/tests = 905 passed；前端自检全通过；Harness = 55 passed；git diff --check exit 0。新增回归后总数应上升。\n\n把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/46-fix-review-1-backend-r4.md，列出 changed files、每条新增/加强回归「先证明它在缺陷存在时会失败 → 再验证修复后转绿」的**你自己的原始输出**、H-1 与 packet 62/63/65 既有性质未被破坏的证据、剩余风险。然后**停止等待 bookkeeper** —— 不 commit、不派发评审、不自行判定验收。成功标准：R3/R4 在 _wake_worker 语义被放回时会失败、在当前代码下全绿；【若已授权】done 卡恢复回归新增并全绿；backend/tests 全量、前端自检、Harness 协议套件全绿；test_6a/6b/6c 与 test_1–test_5、test_4b 仍全绿；frontend/** 零改动；未新增任何 entries 事件 kind、全局守护、周期扫描器或 timer；全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start。",
  "next_action": "fix"
}
```
