# Task Handoff: smooth-open-v1-final-cumulative-review-1-claude-glm

## Source Report (author-only; immutable after task end)

- task_id: `smooth-open-v1-final-cumulative-review-1-claude-glm`
- role: `Reviewer`（累计 Review-1）
- target model: `claude_glm` / provider `zhipu_glm`
- stage_id: `2026-08-12-smooth-open-orders-v1`
- created_at: `2026-08-13 20:24:32 CST`
- base_sha: `e955bdd300d214c5c3ad5c1acd629c0d21080165`
- delivery_sha: `ad8c6317369e8a643f225cc37f22ad0eb949395b`
- status_revision: `52`（`ledger_sha` `d4e5c0bc42bb50171316703913190f78582e1605`）

### 评审身份与隔离

本 Reviewer provider 为 `zhipu_glm`。累计区间内产品实现/修复作者 provider 为 `openai`
（初始实现 + 两轮修复 `24074b1`/`dfd38a6`/`5d65a96`）、`xai`（D17–D19 `bba31ea`）、
`moonshot`（最终 running 卡刷新 `ad8c631`），与本 Reviewer 不同 provider，无自审。fresh 只读会话，
全程未改源码、测试、计划、契约、既有 evidence/dispatch、`status.json`、`ACTIVE.json`、
`PROJECT_STATE.md`、`.venv/`，未 commit/push/merge，未联网取证，未读凭证，未访问/控制
`127.0.0.1:8787`，未改 Start gate，未创建真实任务或下单。唯一写为创建本 handoff（create-only，
Bookkeeper 预检 `test ! -e` 已确认路径原不存在）。未复用 31 号窄 Review-1 会话结论；D17–D19 直接
从 `bba31ea` 代码与最终 tree 独立审查。

### 累计范围、作者隔离与最终文件集（Acceptance 1）—— 结论：成立

- 固定区间 `e955bdd..ad8c631`：`git merge-base --is-ancestor` 确认 base 是 delivery 祖先，
  `git rev-list --count` = 42 提交。区间含 planning/dispatch/status/review evidence 控制提交，
  仅作上下文；产品聚焦 delivery tree 相对原始基线。
- 产品 diff（`--stat`，backend/frontend/requirements/契约/planning）落在预期权威：新增
  `backend/services/best_bid_ask_provider.py`，改 `hedge_open_tasks/{domain,store,service,executor}.py`、
  `services/live_hedge_executor.py`、`app/server.py`、`frontend/index.html`、`frontend/self-check.js`、
  `requirements.txt`、`docs/api/public-market-contract.md`、两份 planning，及对应测试。无 schema 私改、
  无私有配置/凭证/运行时数据库触碰。
- 工作树全部产品/测试/计划/契约文件与 `ad8c631` 逐字一致（`git diff --name-only ad8c631` 对这些
  路径为空），故本会话独立复跑等价于固定 delivery tree。

### 公共盘口 provider 与组合根（Acceptance 2）—— 结论：正确

`backend/services/best_bid_ask_provider.py`（delivery tree 全文已读）+ `app/server.py` 组合根：

- 每 `(exchange_id, market_type, symbol)` key 一个 `_WatchState`，`refs` 引用计数；spot/swap 为两个
  独立 key/独立 coroutine（D3 故障隔离）。`subscribe` 增 refs 或建 watcher，`release` 减 refs、归零才
  `_cancel_state`（D14）。
- 冷启动修复（必修项 1）：`start()` 始终落到 `self._ready.wait(5)`（不再对 alive-but-not-ready 线程
  直接 return）；并发热启动所有调用者等同一 ready。`subscribe` 创建者负责 `_start_watch`，失败在
  `except` 回滚 `_states.pop` + cancel future，`finally: state.ready.set()`；并发等待者在 ready 后校验
  `self._states.get(key) is state and state.task is not None`，否则抛「启动失败」，不留僵尸。
- 不互锁（F1 已关闭，见下）：`_notify`/`_publish`/`_set_status` 在 `self._lock` **外**调 `_on_change`；
  组合根侧 `_ensure_smooth_subscriptions` 在 `_smooth_lock` **外** subscribe。
- 热循环修复（必修项 4）：`_WATCH_RETRY_DELAY_SECONDS=0.05`，无效快照与异常两分支重试前均
  `await asyncio.sleep(0.05)`，且 `asyncio.CancelledError` 重抛使 `close()` 可打断等待。
- 单侧失败不伪造对侧：每 key 独立，`_parse_snapshot` 返回 None 只置本侧 disconnected；对侧 snapshot
  不动（`_valid_l1` 在 service 侧再校验 `status=="live"` 且四值有限 >0）。
- 生命周期闭合：`close()` 排空 `_release_futures` → `_shutdown` 取消全部 task → `loop.stop` →
  `thread.join`，超时仍存活则抛 `TimeoutError`；`_watch` `finally` 关 source。
- offline 零构造（必修项 2）：`server.py` `if config.offline: market_provider=None`；
  `elif default_source_available(): BestBidAskProvider()`；`else: None`。`test_offline_hedge_service_
  never_constructs_market_provider` 守护。
- ccxt 缺失：`market_provider=None` → `create_task` smooth 分支 `400 smooth_market_unavailable`，
  immediate 不检查 provider 不受影响。
- `requirements.txt` 固定 `ccxt==4.5.64`；唯一 ccxt 导入点在 `_default_source_factory`（惰性），
  `default_source_available()` 用 `find_spec` 探测不导入。

### gate 数学、身份和次数安全（Acceptance 3）—— 结论：正确

`domain.py::evaluate_smooth_gate` + `validate_slippage_threshold_pct` + `store.py` gate 三方法 +
`prepare_attempt`：

- 阈值正则纯字符串归一（必修项 3）：`^(?:sign)?(?:[0-9]+(?:\.[0-9]{1,2})?|\.[0-9]{1,2})$`，拒绝空/
  科学记数/`%`/>2 位；归一仅 `lstrip("0")`/`ljust`，**无 `quantize`**，超长 signed 整数不触发
  `InvalidOperation`/500。合法超长整数被接受（201），仅格式非法返回 400。
- 严格 `>`（D4/D6）：`spread_pass = spread_pct is not None and spread_pct > threshold_pct`；spread 与
  threshold 均为两位 Decimal，比较精确，判断值=展示值。forward=`compute_opening_spread_pct(perp.bid,
  spot.ask)`、reverse=`compute_opening_spread_pct(spot.bid, perp.ask)`，coverage 取腿 forward
  (spot.ask_qty, perp.bid_qty) / reverse (spot.bid_qty, perp.ask_qty)，分母固化 `q_common`，`>=0.80`。
  wait_reason 诚实（market_pass→「已通过」；spread 未过→「等待当前方向开单率严格大于阈值」；coverage
  未过→「等待覆盖率 80%」），等值未过以文字如实表达。
- gate 持久化：`open_smooth_gate` 事务内重查 task_type=open/mode=smooth/status=running/count<target/
  seq==count+1/无在途；幂等重开保 `started_at_us`（L2 固定墙钟窗口、重启续原 gate）。`force_smooth_gate`
  仅在 gate 已开且仍活动时幂等置 force=1。`clear_smooth_gate`（status=running 守卫）。
- 三因一 gate + 次数硬门：`prepare_attempt` 同事务重查 `expected_gate_seq==task.smooth_gate_seq` 且
  `smooth_pass_reason ∈ ALL_SMOOTH_PASS_REASONS`、无在途，写 attempt+legs、`count+1` 并清 gate（无
  consumed-without-attempt 缝隙）。`_wait_for_smooth_gate` market/manual/timeout 产出同一 `(gate_seq,
  reason)`；market+manual 并发仅一个 prepare 成功（store 测试 `test_market_manual_race_prepares_
  exactly_one_attempt`）。10/10：`test_tenth_gate_market_manual_race_never_creates_eleventh_attempt`
  断言 count==10、attempts==10、records==10、DONE。
- running→非 running 清 gate 三路径：`set_task_status`(→非 running)、`pause_task`、`stop_task_fatal`
  均清 gate；`prepare_attempt` 消费时清；`_apply_task_counters` 结算不需再清（prepare 已清，且终态转换
  经 set_task_status 清），`test_settlement_path_neither_clears_again_nor_revives_gate` 守护不变量。
  fill-once 只 `force_smooth_gate` 当前 seq，不直接 dispatch；无活动 seq → 409。

### 订单路径、D15/D16 与既有执行链（Acceptance 4）—— 结论：正确

`service.py::_dispatch_one_for_task` + `_dispatch_live` + `live_hedge_executor.py`：

- D15：`if live and mode != SMOOTH:` 才 `_resolve_fresh_preflight`；smooth 走 `else` 复用固化
  `q_common`/`position_side_mode`/`preflight_snapshot`，**不**联网 fresh preflight。smooth 的
  `fresh_route==frozen_route`（同为 `task["preflight_snapshot"]`），`spot_route_changed` 暂停对 smooth
  不可达；immediate 仍每轮 fresh preflight + 路由变化拦截（逐字不变）。
- D16：`_worker_round` 在 `_wait_for_smooth_gate` **之前**，当 `live && open && count==0` 调
  `_set_leverage_before_open`，失败→`leverage_set_failed` 暂停（零订阅/gate/attempt/订单）；
  `_dispatch_one_for_task` 的杠杆块显式排除 smooth。`test_live_smooth_orders_leverage_gate_and_frozen_dispatch`
  断言 `set_leverage < open_gate < subscribe < market_evaluation < prepare_attempt < dispatch`，
  `preflight.calls==1`、`leverage_calls==1`（三种 pass reason 均适用）。
- 放行→订单客户端调用之间无联网/sleep/SQL：`_dispatch_live` 仅在内存 `audit` 上 `_smooth_audit_mark`
  （`service_dispatch`/`executor_entered`/`executor_returned`，monotonic），`append_log(smooth_dispatch_
  audit)` 与 `_persist_leg_raw` 均在 `self._executor.dispatch(ctx)` 返回**之后**；唯一前置 SQL 是
  `prepare_attempt` 的 ADR-2 durable-before-send 硬门（设计明确保留并单独计时）。
- 两腿并发：`live_hedge_executor` 两 `threading.Thread` 并发 `start`/`join`，原 prepare/dispatch/query/
  settle/单腿暂停链复用；immediate/close 不被 smooth gate/audit 改义。L1/L2/L3 为 Human 接受限制，
  无固定证据触发其重开条件，本轮不阻塞。

### D17 人工启动与恢复（Acceptance 5）—— 结论：正确

`create_task`：`mode==smooth && task_type==open` 时 `create_kw={initial_status:PAUSED,
initial_pause_reason:AWAITING_MANUAL_START}`，建卡仍跑首次完整 preflight + 固化身份/数量/route +
regular-spot 预划转，**不**调 `ensure_worker`。`post_start`→`set_task_status(RUNNING)`（清残留 gate）
→`ensure_worker(relaunch_after_current=True)` 为唯一首跑入口。`_require_fillable`：smooth +
awaiting_manual_start → `409 start_required`（不能绕过 Start）。`post_fill_all` smooth → `409
smooth_fill_all_unsupported`。`_recover_workers`/`start()` 不领取 paused 卡。immediate 创建仍 running、
无 pause reason、无 worker（`test_immediate_create_still_starts_running`）。
`test_smooth_create_is_paused_with_zero_execution_resources` 断言 create 后零 worker/订阅/gate/
attempt/订单、`_recover_workers` 不起 worker、fill-once 先于 start→`start_required`。

### D19 同次快照与延迟审计（Acceptance 6）—— 结论：正确

`_wait_for_smooth_gate` 用产生 pass 结论的**同一** `spot_snap/perp_snap/result` 调
`_build_smooth_pass_audit`，放行后无第二次 `latest()`
（`test_smooth_audit_uses_same_gate_snapshot_and_no_second_latest` 断言 pass 后再发布新价、
`latest_calls` 不变）。`live_hedge_executor._send_one_leg`：在 credentials 检查与 `_leg_product`
route 解析**之后**、实际 `post_*_order` **之前**标 `{leg}_order_client_call_started`，POST 后标
`_returned`；两腿各自独立线程 + 独立 `spot_marks/perp_marks`（无共享竞态/串腿），join 后 merge 入
`audit["marks"]` + `executor_joined`，全部以 `gate_pass_mono_us` 为零点
（`test_smooth_audit_marks_order_client_after_route_and_before_post`、
`test_blocked_spot_client_does_not_block_perp_order_client`）。审计在 executor 返回后 best-effort
`append_log`，`except: pass` 不改订单（`test_smooth_audit_append_failure_does_not_change_business`）；
immediate/close `ctx.smooth_audit=None` 不写审计。SHELLUSDT 实盘证据与代码口径一致：严格 `>` 解释
`0.05==0.05` 未过、后续 `0.15>0.05` market pass；gate→两腿 client call 由 monotonic marks 记录。

### 任务卡、统一刷新与 Human 接受展示限制（Acceptance 7）—— 结论：正确

D18 渲染门 `smoothExtras = (mode==='smooth' && status==='running') ? renderSmoothTaskExtras(task) : ''`
未运行 smooth 卡只显阈值/基础/按钮/错误/日志，无盘口块。统一刷新（31 号已审、累计确认）：task tab
共享 2s tick 先刷 task list，再请求 running∪仍存在且 expanded 去重集合，无 mode/task_type/方向特判、
无新 timer（`setInterval(()=>` 仍 4），页面刷新后空 `hedgeLogExpanded` running smooth 不再长期误报
incomplete；非 running 收起停止、展开继续 drain/settle；running 收起仍更新动态数据。Human 接受
「显示 +0.05% 但严格等值未过」醒目性限制；本评审只验证 wait reason/pass 语义诚实，未要求改 UI/gate。

### 回归、契约与发布边界（Acceptance 8）—— 结论：通过

本会话独立复跑（工作树与 ad8c631 逐字一致）：

- `pytest` suite A（provider/gate store/worker/smooth api/hedge domain/live executor/hedge service/
  frontend binding/service health）→ **362 passed**。
- suite B（hedge store/api/task local/review2 regressions/leverage/cycle core/close/purity）→ **311 passed**。
- `pytest backend/tests -q` → **1890 passed, 1 failed**。
- `node frontend/self-check.js` → **全部自检通过**（exit 0）。
- `git diff --check e955bdd..ad8c631` → 无输出（exit 0）。

唯一失败 `test_private_client.py::test_urlopen_only_in_designated_http_clients`（`public_ip_service.py:47`）
分类 **pre-existing-independent**：引入提交 `73f525d` 经 `git merge-base --is-ancestor` 为累计 base
`e955bdd` 的祖先，且 `public_ip_service.py`/`test_private_client.py` 在 `e955bdd..ad8c631` **零 diff**
（`git diff --stat` 对两文件为空）。满足 acceptance #8 的 git 证明条件，不阻塞。

契约 `docs/api/public-market-contract.md` smooth 段（v0.20）additive：smooth open create=`201 paused
+awaiting_manual_start`（中文「任务首次执行必须点击启动」）、不启动 worker/订阅/gate/订单、首次
preflight/固化/regular-spot 预划转仍在建卡、immediate 仍 running；未启动 fill-once=`409 start_required`；
task-id 日志 additive 返回 `smooth_dispatch_audits`（`kind=smooth_dispatch_audit`、按 ts_us/id 排序、
Decimal 为字符串、不含凭证/签名/私有 URL/私有 raw 响应、immediate/close 不产生）；既有
logs/attempts/smooth_market 不变。与最终代码行为一致。

### 发现分类与 verdict

- **in-range**：无。
- **pre-existing-release-critical**：无。
- **pre-existing-independent**：1 条——`public_ip_service.py:47` 白名单失败（git 证明早于 base、零 diff）。
- **非阻塞观察**（不带重开条件，仅 transparency）：
  1. 公共契约 smooth 段为行为级 additive 描述，未逐一枚举 `slippage_threshold_pct`/`smooth_gate_*`/
     `smooth_market`/audit payload 内层字段名（这些字段权威在 `docs/planning/smooth-open-orders-v1.md`
     §8 与测试）。契约与代码行为一致，非契约违反；若 Human 希望字段级枚举进契约可后续补。
  2. 无单个测试把 market+manual+timeout 三因同时竞速同一 gate（market+manual 已竞速、timeout 单测）；
     store 层 `prepare_attempt` 的 `expected_gate_seq` 原子复核对三因一致生效，属测试完备性细节非正确性缺口。

Human 已冻结 L1/L2/L3 与「等值未过」显示限制；本评审不凭偏好判 REWORK。F1（review-2 REWORK 的
provider×`_smooth_lock` 死锁）已由 f1-fix 关闭并经最终 tree 核验；五项必修根因均已修复。累计范围内
无资金/订单、并发、生命周期、契约、真实接线或关键测试缺口。

**verdict: ACCEPT（接受）**

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/32-smooth-open-v1-final-cumulative-review-1-claude-glm.dispatch.md`
- 执行：Bookkeeper 核验本累计 Review-1 handoff 的 source SHA-256、唯一 create-only 路径、固定累计 `base_sha=e955bdd`/`delivery_sha=ad8c631` 与 ACCEPT verdict
- 关卡：Bookkeeper 核验通过后准备 Human 已指定的 fresh Opus 5（provider `anthropic`）Review-2；push/merge/部署/实盘仍须 Human 单独授权
- 不能假设的事实：当前 `127.0.0.1:8787` 已加载产品 delivery `ad8c631` 但 `executor_mode=live`、Start gate=true、本任务只读未授权控制服务/改 gate/创建任务/下单；本累计 Review-1 ACCEPT 不等于 Review-2 通过或合并授权；最终 Review-2 须由 fresh Opus 5 执行，不得由本 Reviewer 启动或以 Review-1 冒充

## Human Brief / Console Receipt Source

[TASK_RESULT v2]
任务 ID: smooth-open-v1-final-cumulative-review-1-claude-glm
执行结果: completed（完成）
结果摘要: fresh 跨 provider 累计 Review-1 通过（zhipu_glm 审 openai/xai/moonshot 全部实现）。固定 e955bdd..ad8c631，独立审 provider 组合根、gate 数学/竞态/次数、D15/D16 订单路径、D17 启动、D19 同次快照审计、统一刷新。F1 死锁与五项必修均已修复并经最终 tree 核验。suite A 362、B 311、全后端 1890+1(pre-existing-independent)、self-check 全绿、diff --check 干净。L1/L2/L3 与等值显示限制为 Human 已接受。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md]
检查结果: [pass：累计范围/作者隔离/文件集，base 为 delivery 祖先、工作树==ad8c631；pass：provider 组合根 offline/ccxt/lifecycle/热循环/单侧隔离/F1 死锁已关闭；pass：gate 严格>/signed 超长阈值/取腿分母/竞态/次数/清 gate 三路径原子正确；pass：D15 smooth 复用固化无 fresh preflight、D16 杠杆前置、放行→client call 无联网/sleep/SQL；pass：D17 paused-create 零资源、Start 唯一入口、fill-once 409；pass：D19 同次快照无二次 latest、monotonic 计时含两腿 client-call 边界、延迟审计；pass：D18/统一刷新/等值显示限制只验语义诚实；pass：回归全绿、契约 additive 一致、唯一失败 pre-existing-independent 有 git 证明]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md
修复要求: none
本地北京时间: 2026-08-13 20:24:32 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md；reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json；reports/agent-runs/2026-08-12-smooth-open-orders-v1/32-smooth-open-v1-final-cumulative-review-1-claude-glm.dispatch.md；执行：核验本累计 Review-1 handoff 的 source SHA-256、create-only 路径、固定累计 base_sha=e955bdd/delivery_sha=ad8c631 与 ACCEPT verdict；关卡：核验通过后准备 Human 已指定的 fresh Opus 5（anthropic）Review-2，push/merge/部署/实盘仍须 Human 单独授权，不得由本 Reviewer 启动 Opus 5 或以 Review-1 冒充 Review-2。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `7a6e52ff8e39c83546f11a05f0ac92907c0a638a9403acf2b32e4bd0b71090c9`
- verified_at: `2026-08-13 20:33:16 CST`
- status_revision_verified: `52`
- verdict: `verified-accept`
- fixed_range: `e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b`
- create_only_and_identity: 本 handoff 是 Reviewer 唯一新增路径；task_id、role、stage、provider、status revision、base/delivery 与 32 号 dispatch 和 revision 52 状态一致，marker 与 Human Brief 闭合字段完整，明确 `ACCEPT（接受）`、`修复要求: none`，无 contested 项。
- git_verification: 两个 SHA 均为可解析 commit，base 是 delivery 祖先；产品/测试/计划/API/requirements 工作树与 delivery tree 一致；累计区间 `git diff --check` 无输出。
- independent_checks: Bookkeeper 独立复跑专项 `362 passed`、核心 `311 passed`、全后端 `1890 passed, 1 failed`、前端 self-check 全绿。唯一失败仍为 `backend/services/public_ip_service.py:47` 的 `urlopen` 白名单遗漏；该文件与失败测试在固定区间零 diff，且引入提交 `73f525d4c3033cd4e8d7c7afb09a975816742913` 早于 base，采信 `pre-existing-independent`，不阻塞本交付。
- operational_check: `.venv` 中 `ccxt==4.5.64`；PID `23396` 仍从 smooth worktree 运行。此只读核验不授权或执行服务控制、gate、任务、订单、push、merge、部署或其他实盘动作。
- gate: 累计 Review-1 正式通过。允许准备 Human 已指定的 fresh Opus 5（provider `anthropic`）最终 Review-2；本 ACCEPT 不得冒充 Review-2 或发布授权。
