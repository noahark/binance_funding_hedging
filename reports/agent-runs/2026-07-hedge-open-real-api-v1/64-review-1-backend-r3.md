# Review-1（第一轮交叉复核）— 后端：Hedge Open Real API v1（packet 62 + 63 合并提交后的重启轮）

## 审查身份、模型替换披露与锚点

- **本次审查者：Claude Opus 5（Anthropic）**。派发文件 `64-review-1-backend-r3.dispatch.md` 的
  `target_model` 写的是 `Claude Sonnet 5`；**用户在派发执行时明确指定改由 Opus 5 承担本次
  Review-1**（原话：「sonnet5 能力不够，我特意邀请你 opus5 进行 review1」）。因此最终 JSON 的
  `model` 字段如实写 `Claude Opus 5`，与派发 PROMPT BODY 里预写的 `model=Claude Sonnet 5` 不一致。
  这是**如实记录而非违规**：审查者身份必须是真实执行会话，不能按派发预填值伪报。请 bookkeeper 在
  `status.json` / dispatch RECEIPT 里把 `target_model` 更正为 `claude/Claude Opus 5` 并记录该用户决定。
- **供应商隔离成立**。被审后端代码的唯一实现/返工作者是 Claude-GLM（`glm-5.2[1m]`，provider =
  `zhipu_glm`）。本会话是 Anthropic，与被审后端作者不共享 provider、会话状态、prompt transcript 或
  工具状态，满足 Review-1 的 provider 级交叉复核要求。
- **先前参与如实披露**：本 Opus 5 会话在本 stage 未写过任何一行代码、文档或评审。同 provider
  （Anthropic）的**另一个** Claude Sonnet 5 会话在本 stage 早前轮次写过**前端**返工
  （`40-fix-review-2-frontend.md`、`41-fix-open-log-pagination-frontend.md`、
  `45-review-1-frontend-rfix.md` 相关返工），但没有写过本次被审的任何后端代码
  （`backend/hedge_open_tasks/**`、`backend/services/hedge_*`、`backend/app/server.py`）。
  `reviewer_prior_involvement` 枚举没有「同阶段其他域代码作者（同 provider）」这一类别，按派发要求记
  `none`，实情写在此处与 JSON 的 `reviewer_prior_involvement_notes`。本次只审后端及其
  HTTP/entries 接缝，不评审前端视觉实现。
- **固定审查区间（未使用移动 HEAD）**：
  - `base = 28c550d87c1ca90983d5bde9c7102d42cffecd4e`
  - `head = ab3126d73549266a615fe43c1aeaf374b0db2d32`
  - 本机独立重算指纹：
    `git diff --binary <base>..<head> -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json' | shasum -a 256`
    = `4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772`，与派发值、`status.json`
    记录值**逐字一致**。
  - 当前 `HEAD = 1b42004`（比 `head` 多两个 chore 提交）；实测
    `git diff --stat ab3126d..HEAD` 只动 `60-test-output.txt`、`64-…dispatch.md`、`70-handoff.md`、
    `status.json` 四个簿记文件，**零后端源码差异**，因此在 HEAD 上跑出的测试结论对锚点区间有效。
- **只读、离线**：未修改仓库任何文件、未 commit、未读取凭据、未连接 Binance、未发送任何真实
  POST、未启用 live、未触发 Start。用于复现缺陷的三个一次性校验脚本写在会话 scratchpad
  （`/private/tmp/claude-501/.../scratchpad/`），使用临时 SQLite 与 fake transport，**不在仓库内、
  不进入 diff**；脚本全文与原始输出见下文「缺陷复现」各节，bookkeeper 如需可要求转成正式回归。

## 已实际阅读的原始材料

`AGENTS.md`（全文）；`workflows/templates/stage-delivery.yaml` review_1 段；
`schemas/review-verdict.schema.json`（全文）；`docs/product/PRD.md`（即时开单/风险/实盘门控段）；
stage 文件 `00-task.md`、`06-direction-synthesis.md`、`10-design.md`、`11-adr.md`、
`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`、
`21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`、
`23-packet-62-reconciliation-hold.md`、`25-packet-63-final-reconciliation.md`、`50-review-2.md`、
`58-review-1-backend-r2.md`（含其 JSON verdict）、`40-fix-review-1-backend-r2.md`、
`42-final-guardian-scanner-fix.md`、`60-test-output.txt`、`status.json`；
实际 `git diff --binary 28c550d..ab3126d`（110 文件 / +20198 −1075）；
后端源码逐行：`backend/hedge_open_tasks/{domain.py,service.py,store.py,executor.py,scheduler.py}`、
`backend/services/{hedge_open_live_client.py,hedge_preflight_provider.py,live_hedge_executor.py}`、
`backend/app/server.py`（hedge 路由 + `_build_hedge_service` + `run`）、`backend/config.py`；
测试源码：`backend/tests/{test_hedge_task_local.py,test_hedge_purity.py,test_hedge_review2_regressions.py}`
全文与 `test_hedge_api.py`、`test_hedge_domain.py`、`test_hedge_store.py`、`test_hedge_service.py` 的关键用例。

## 本机独立验证（全部离线命令，原始结果）

| 命令 | 结果 |
| --- | --- |
| 指纹重算（见上） | `4538945a…9772`，与冻结值逐字一致 |
| `.venv/bin/python -m pytest backend/tests -q` | **897 passed** in 48.70s（与 `42` 报告 CMD#2、`25` 号一致） |
| `pytest test_hedge_task_local.py test_hedge_service.py test_hedge_review2_regressions.py -q` | **48 passed** in 1.56s（与 CMD#1 声称的 48 一致） |
| `node frontend/self-check.js` | 全部自检通过（同源白名单/零 Binance/零新定时器/localStorage 白名单），exit 0 |
| `pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q` | **55 passed** in 1.15s |
| `.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review` | **STAGE VALIDATION PASSED**，`diff_fingerprint` 打印值与锚点一致（上一轮阻塞门禁的未提交文件 P3 已消除） |
| `git diff --check` / `git status --porcelain` | 均干净 |
| 全仓 grep `Thread(` / `Timer(` / `while True` / `daemon=True`（hedge 路径） | live 模式下只有「每卡有界 worker」与「每组两腿并发线程」；`_dispatch_eligible_concurrently` 仅 dry-run；**无任何替代守护/定时器** |

## 结论

**REWORK（需要返工）**，但性质与上一轮不同，请先读清这段业务判断：

1. **本轮派发点名的三大必查项全部真正修复，且有确定性回归钉住**——包括上一轮我方 P1 的正反向
   `est_price` fail-closed、任务 A 慢查询不阻塞 B、双 Start/恢复不双 POST，以及用户额外授权的
   **H-1 守护扫描器移除**。H-1 的修法在结构上是干净、可验证的（详见「已核实的修复」§H-1）。
2. **但在 429 / 暂停这条结算接缝上，仍存在两个真实、可复现、后果落在真钱上的 P1 缺陷**。两者都
   不是「加固建议」，而是与用户冻结合同逐字冲突：一个会**静默关掉连续失败暂停闸门与致命腿停机**
   并把成功组记成「已确认失败」；另一个会在操作员按下「暂停」时**放弃对已在交易所的在飞订单的
   对账**，正是 amendment 15/21「对账绝不放弃」这条不变式。
3. 两个缺陷都**不会导致越权下单**（默认关闭、live 未启用、本轮零真实请求，这些安全门我逐条验过
   都无回归），所以它们不阻断「代码已提交」这件事；但它们**必须在任何实盘授权之前修掉**——否则
   第一次真实开单遇到 429 或人工暂停时，账本与安全闸门都会失真。

**流程提示（重要）**：`status.json.rework_count` 已是 **4**，用户 2026-07-25 在
`24-user-authorized-final-guardian-fix.md` 里授权的「一次且仅一次」额外修复已被 packet 63 消耗完。
因此本 REWORK **不能由 bookkeeper 直接派发**：`next_action` 记为 `human_escalation_required`，
需要用户就这两条 P1 再给一次明确的、边界更窄的修复授权（我已把可直接投递的 `fix_start_prompt`
写在 JSON 里，授权一到即可原样派发，无需重新总结证据）。

## 已核实的修复（逐项与实际源码/测试对照）

### H-1（用户额外授权项）— 守护扫描器已真正移除

- `service.start()`（`service.py:385-403`）：`_live_dispatch_capable()` 为真时**只**调用一次
  `_recover_workers()` 后 `return`，**不执行** `self._scheduler.start()`；dry-run 分支保留
  `_scheduler.start()`。核实无误。
- `service.tick()`（`service.py:1072-1089`）：live 分支第一行 `return False`，在触达
  `_recover_workers()` / `list_tasks()` / `ensure_worker()` **之前**返回。即便未来被误调也不会退化成
  扫描器——这是结构性保证，不是约定。核实无误。
- `post_start(task_id)`（`service.py:501-515`）：live 只 `ensure_worker(task_id)`，仅本卡。
  `post_fill_once`/`post_fill_all` 的 live 路径同样只 arm 本卡 + `ensure_worker`，无同步 POST 循环。
- **无替代守护**：我独立 grep 了 hedge 全路径的 `Thread(`/`Timer(`/`while True`/`daemon=True`，
  live 模式下存活的线程只有 ①每卡一个有界 `hedge-worker-<id>`、②每组两腿的 `hgo-leg-spot/perp`
  （`live_hedge_executor.py:488-495`，pair 内并发，join 后返回）。`_dispatch_eligible_concurrently`
  只在 dry-run tick 里调用。`server.py:773` 的唯一 `start()` 调用点与 `790` 的 `stop()` 清理均兼容
  （`HedgeOpenScheduler.stop()` 对未启动线程安全）。
- 回归质量：`test_6a`（spy 证 `_recover_workers` 恰好 1 次 + `scheduler.start` 0 次 +
  `_scheduler._thread is None`）、`test_6b`（连续 5 次 live `tick()`，三条防线计数全 0，两张
  RUNNING 卡始终无 worker）、`test_6c`（`post_start(A)` 后 A 有 worker、B 无 worker）。三个用例的
  断言与它们声称证明的性质**确实对应**，不是空转。`test_5` 由 `svc2.tick()` 改为 `svc2.start()` 后
  仍断言零第二次 write + `query_calls>=2` + 对账到终态。

### 上一轮 P1 #1 — 正反向 `est_price` fail-closed（已彻底修复）

`domain.compute_preflight`（`domain.py:735-753`）把价格完整性检查提到**方向分支之前**：
`if snapshot.est_price is None or snapshot.est_price <= 0: return REJECT_PREFLIGHT_INCOMPLETE`。
因此 `_check_common_quantity` 的 minNotional 分支再也不会在缺价时被静默跳过，反向分支也不再绕过。
`REJECT_PREFLIGHT_INCOMPLETE` 不在 `PREFLIGHT_FATAL_REASONS` 内，`_resolve_fresh_preflight`
（`service.py:1197-1198`）将其映射为 `None` → fail-closed 重试：**零 attempt、零 POST、零失败计数**。
`test_hedge_domain.py` 已覆盖 forward/reverse × None/0/负 四组。核实无误。

### 上一轮 P1 #2 — 对账阻塞派发（已彻底修复，且修法优于我上轮的建议）

旧的全局 `_reconcile_pending` 扫描、`service._lock` 重量级串行、进程级 429 冷却
（`RATE_LIMIT_COOLDOWN_US`）全部删除，改为每卡一个有界 worker，只查自己的腿
（`store.list_non_terminal_legs_for_task(task_id)`，`store.py:1174-1191`）。executor 调用全部落在
短事务**之间**，无任何 store 锁/事务被持有（Q6）。`test_1` 用 Event 屏障（非 sleep race）证明 A 的
`query_leg` 被阻塞期间 B 仍能 reserve+submit。结构性 + 行为性双证据，核实无误。

### 任务本地 worker 的其余合同项

| 用户冻结合同 | 实现证据 | 结论 |
| --- | --- | --- |
| 同卡 pair 严格串行 | `prepare_attempt` 事务内 `pair_outcome IS NULL` 在途守卫（`store.py:547-553`）+ `list_eligible_tasks` 同谓词（`477-499`）+ worker 先 drain 后派发（`_worker_round`） | ✅ |
| `target_n` 原子硬上限 | 同一事务内 `scheduled_attempt_count >= target_n → None`，与 `+1` 同事务（`store.py:542-543,611-615`）；任何入口共享 | ✅ |
| 双腿并发 | `LiveHedgeExecutor.dispatch` 两线程 start→join，pair 内并发、pair 间串行 | ✅ |
| 只查自己的腿 | `list_non_terminal_legs_for_task` 按 `task_id` 子查询限定 | ✅ |
| 无 `orderId` 绝不盲发 | `classify_leg_response` 把 transport error / 5xx / 2xx-无 orderId / 429 全部映射为 `UNKNOWN_QUERYING`；`_send_one_leg` 只**查一次**、写 POST 永不重发；`client._send` 单次尝试无内部 retry；`_mark_legs_querying` 只改状态不重发 | ✅ |
| 429 先按 client-ID 对账、再仅暂停本卡、不计失败 | `_dispatch_live` 的 `rate_limited` 分支 → `SIGNAL_RATE_LIMITED` → `_pause_task_local(rate_limited)` + `return False`（先 drain 后退），`settle_attempt_no_counters` 不动计数器；`test_3` 断言 `fail_count==0` 且 B 不受影响 | ✅（但见 P1 #1 / P2 #1 的**后续**结算缺陷） |
| 余额/保证金/可用数量不足只暂停本卡 | `is_insufficient_funds_code` 仅 `-2019`/`-3041` 无歧义、`-2010` 需 msg 命中 → `insufficient_funds` → `_pause_task_local`；`test_4` 参数化覆盖 | ✅ |
| 未确认 `-2010` 走 fatal stop（宁可硬停） | `classify_leg_response` 先查 insufficient 再查 `FATAL_EXCHANGE_CODES`，未确认 `-2010` 落 fatal；`test_4b` 断言 `STATUS_STOPPED` + `exchange_fatal` | ✅ |
| 重启只按 clientOrderId 查询、绝不重发 | `test_5`（新实例 + 同一 SQLite 文件 + 共享 executor 计数器）断言 `dispatch_calls` 不增、`query_calls>=2`、pair 对账到终态 | ✅ |
| store 锁内不调 executor | `test_store_never_invokes_or_holds_an_executor` AST/正则静态守卫（`.dispatch(`/`.query_leg(`/`.query(`/`self._executor` 全禁） | ✅ |
| 签名/网络纯度 | `test_hedge_purity.py`：`hedge_open_tasks/**` 零 urllib/socket/requests/hmac/hashlib 导入、零 live 模块导入；7 端点冻结 allowlist 逐字比对、host 硬编码、gate 在签名**之前**抛 `PermissionError`（fake urlopen 若被触达即失败） | ✅ |
| real POST 默认关闭无回归 | `config.hedge_executor` 默认 `disabled` 且非法值在 `from_env` 抛错（不静默钳制）；`_build_hedge_service` 仅 live 才构造 `LiveHedgeExecutor`；凭据缺失时构造但拒发并 emit `hedge_open_execution_blocked`；`_live_dispatch_capable()` 每次发送前再判一次 | ✅ |
| entries 独立分页不改旧 logs 分页 | `get_logs` 的 `logs`/`next_cursor` 仍走 `list_logs_page(limit, cursor_ts, cursor_id)`；`entries` 走独立 `entries_limit`/`entries_cursor` 三元组 `(ts_us, rank, id)`；`server.py` 新增两个可选 query 参数，`parse_qs` 丢空值＝首页。前端自检通过，`test_hedge_api` 冻结字段集加 `pause_reason_zh` 后全绿 | ✅ |
| 本次后端字段无破坏前端已接受契约 | 仅**加**字段（`pause_reason_zh`、entries 系列），无改名/删除；`node frontend/self-check.js` 通过 | ✅ |

### 上一轮 P2（实时限频用量响应头）— 已按要求「如实标注未实现」

`hedge_open_live_client.py` 仍只解析 `Retry-After`，未捕获 `X-MBX-ORDER-COUNT-*` / 权重头；
`hedge_preflight_provider._read_rate_limit_order` 仍只读账户配置上限。**但** `40-fix-review-1-backend-r2.md`
§9.2 已明确写为「本轮未实现」的剩余风险，没有再声称「已完全解决 finding #3」——这正是我上轮
required fix #3 的可接受出路。**不再计为本轮问题**，转入剩余风险。

---

## Findings

### P1 #1 — 一次 429 暂停 + 人工恢复后，后续所有「经对账结算」的组永久丢失计数器：连续失败暂停闸门与致命腿停机被静默关闭，成功组被记成「已确认失败」

- **文件/行**：`backend/hedge_open_tasks/service.py:1026`（`_reconcile_own_legs` 的
  `rate_paused = task.get("pause_reason") == D.PAUSE_REASON_RATE_LIMITED`）与
  `backend/hedge_open_tasks/store.py:433-444`（`set_task_status` 不清 `pause_reason`）。
- **机理**：`store.pause_task()` 写入 `pause_reason='rate_limited'`；`post_start()` 走
  `set_task_status(task_id, STATUS_RUNNING, …)`，该 SQL **只更新 `status` 和 `updated_at_us`**，
  从不清空 `pause_reason` / `pause_reason_zh`。全仓 grep 确认**没有任何代码路径**清除
  `pause_reason`（`_apply_task_counters` 只原样回写 `task["pause_reason"]`，唯一的写入点是
  `pause_task`）。于是 `pause_reason` 变成**粘滞**字段：卡片恢复运行后仍是 `'rate_limited'`。
  `_reconcile_own_legs` 用它来选择结算路径——粘滞值使**此后每一个** `pair_outcome IS NULL` 的组
  都走 `settle_attempt_no_counters()`（`store.py:1009-1033`）而不是 `finalize_attempt()`
  （`store.py:944-1007`）。`settle_attempt_no_counters` 只盖一个硬编码的
  `pair_outcome = PAIR_CONFIRMED_FAILED`，**完全不调用 `_apply_task_counters`**。
- **实测复现（离线 fake transport，scratchpad 脚本 `verify_stale_rate_paused.py`，原始输出）**：

  ```text
  after 429 pair : status=paused pause_reason=rate_limited fail=0
  after resume   : status=running pause_reason=rate_limited (STALE)

  pair 2 legs really FILLED with orderIds s9/p9, yet:
    attempt[1].pair_outcome   = 'confirmed_failed'   (expected 'accepted_pair')
    accepted_pair_count       = 0   (expected 1)
    success_count             = 0   (expected 1)
    status                    = running   (expected done once target reached)
    dispatch (write) calls    = 2   (no resend: expected 2)

  DEFECT CONFIRMED: True
  ```

  场景：`target_n=2`；第 1 组遇确认 429 → 本卡暂停（正确，`fail_count=0`）；操作员人工恢复
  （脚本调用与 `post_start` 完全相同的 `set_task_status(RUNNING)`）；第 2 组两腿 POST 无权威结果
  → 标 querying → 对账查到**两腿都 FILLED 且都有 orderId**（这是一次完全成功的受理对）。结果被记成
  `confirmed_failed`，`accepted_pair_count`/`success_count` 停在 0，卡片永不进 `done`。
- **影响（按业务后果排序）**：
  1. **连续失败暂停闸门被静默关闭**：`consecutive_submission_failures` 再也不递增，用户冻结的
     「默认 3 次已确认连续失败即暂停」这条安全刹车对该卡失效——它可以一路把 `target_n` 全部打完。
  2. **致命腿停机被静默关闭**：`finalize_attempt` 里「对账到的腿带 `error_category='fatal'` →
     `stop_task_fatal`」的整段逻辑（`store.py:986-999`）被跳过，amendment 21 第 3 行的
     symbol/mode/filter/min-notional 致命事实不再停卡。
  3. **账本失真**：真实成功的受理对在 `开单日志` 里显示「已确认失败」，`success_count` /
     `accepted_pair_count` 长期为 0，与实际 Binance 成交对不上；`leg_exposure` 也不再记录。
  4. UI 侧附带：`pause_reason_zh`（「触发交易所限频（429）…请等待限频解除后手动恢复」）在卡片已
     恢复 `running` 后仍留在响应里，前端可能展示过期停机原因。
- **触发条件普通、非边缘**：单卡只需经历一次 429 暂停 + 一次人工恢复；429 恰恰是本阶段用户最关心
  的、必然会遇到的路径。现有 48 个重点用例中 `test_3` 只验到「暂停时 `fail_count==0`」就结束，
  **没有任何用例在 429 暂停后恢复该卡并继续跑下一组**，所以这个缺口逃过了全部回归。
- **建议修复（两处，缺一不可）**：
  1. 恢复/重新运行时清除粘滞状态：让 `post_start`（或 `set_task_status` 走向 `RUNNING` 时）把
     `pause_reason`、`pause_reason_zh` 置 NULL，与 `pause_task` 清 `stop_reason` 对称。
  2. 让「本组是否免计数」这个决定**来自该组自身的事实而非任务的粘滞字段**：例如在 attempt 行上
     打一个「因限频暂停而结算」的标记（`prepare_attempt`/`_dispatch_live` 的 429 分支写入），
     `_reconcile_own_legs` 读该 attempt 的标记来选 `settle_attempt_no_counters` 与
     `finalize_attempt`。只做 (1) 会遗留「同一 429 卡在恢复前又对账到别的组」的窄窗口，只做 (2)
     会遗留 UI 的过期 `pause_reason_zh`。
  3. 补确定性回归：429 暂停 → 人工恢复 → 下一组两腿 FILLED，断言
     `pair_outcome == accepted_pair`、`accepted_pair_count == 1`、`success_count == 1`、
     `pause_reason is None`；再补一条「恢复后连续 3 次已确认失败仍能触发阈值暂停」。

### P1 #2 — 人工「暂停」（及「删除」）会在**未对账完**的情况下丢弃在飞真实订单，且 packet 63 移除周期 tick 后再无任何组件把它们捡回来

- **文件/行**：`backend/hedge_open_tasks/service.py:517-533`（`post_pause`/`post_delete` 调
  `_wake_worker`）、`:939-941`（`_worker_round` 首行 `stop_event.is_set() → return True`）、
  `:1145-1171`（`_recover_workers` 只覆盖 `RUNNING`/`PAUSED`/`STOPPED`）、`:1088-1089`
  （live `tick()` 已是 no-op）。
- **机理**：`post_pause` 先 `set_task_status(PAUSED)` 再 `_wake_worker(task_id)` → 置位该卡
  `stop_event`。worker 下一轮在 `_worker_round` **第一行**就 `return True` 退出——**在
  `_reconcile_own_legs` 之前**，所以 Q2「先 drain 后退」这条不变式对**人工暂停**根本不生效
  （它只对 429/余额类信号生效，那两条走的是 `return False`）。packet 62 时代，live `tick()` 的
  `_recover_workers()` 会在一个 interval 内为「任意 status 但仍有非终态腿」的卡拉起 drain-only
  worker 兜底；packet 63 把 live tick 变成 no-op 后，**这个兜底消失了**。
- **实测复现（scratchpad 脚本 `verify_manual_pause_drain.py`，原始输出）**：

  ```text
  after dispatch : non-terminal legs = 2  query_calls = 0
  after pause    : status = paused
  worker_round   : exit = True  query_calls = 0
  still pending  : non-terminal legs = 2
  after 5 ticks  : query_calls = 0 (unchanged: True )

  DEFECT CONFIRMED: True
  ```

  场景：第 1 组两腿 POST 回来都无权威结果（**两笔真实订单可能正躺在 Binance 上**，等待按
  clientOrderId 对账）；操作员按「暂停」；worker 的下一轮**一次查询都没发**就退出；两条腿永久停在
  `terminal=0`；此后连续 5 次 `tick()` 也不产生任何查询。
- **首次尝试的自我纠正（如实记录）**：我第一次写这个脚本时用 `_pump_worker` 驱动，结果 worker
  照常 drain 了，`DEFECT CONFIRMED: False`。原因是 **`_pump_worker` 这个测试 seam 根本不注册
  `_stop_events` 条目**（只有 `ensure_worker` 会建），所以 `_wake_worker` 找不到 event、变成空操作。
  按 `ensure_worker` 的真实行为补上 event 后缺陷稳定复现。这件事本身是一条独立发现（见 P3 #2）：
  **生产 worker 的 pause/delete 中断路径完全没有被同步 seam 测试覆盖**。
- **影响**：
  1. 「暂停」是操作员的**紧急刹车**。按下它之后，本卡已在交易所的订单可能继续成交（市价单几乎
     必然成交），而本应用不再查询、不落实际成交量/均价/手续费、不结算该组、不清 in-flight 守卫。
     这与 amendment 15「reconciliation is never abandoned」、amendment 21「Timeout/5xx/ambiguous →
     this task continues only its own client-ID reconciliation」逐字冲突。
  2. **进程内唯一补救手段是再按一次 Start**，而 `post_start` 会把卡置回 `RUNNING`：drain 完之后
     worker 发现 `status == RUNNING` 且未达 `target_n`，**会继续下一组真实开单**。也就是说操作员
     想「只对账不再开单」在当前 API 下做不到（没有独立的 recover-only 动作）。
  3. **`delete` 更差**：`_recover_workers` 的兜底循环只遍历 `PAUSED`/`STOPPED`，**不含
     `STATUS_DELETED`**（`service.py:1163`），所以被删卡片的在飞腿**连进程重启都不会再被查询**；
     而 `aggregate_positions` 又用 `WHERE t.status != DELETED` 过滤（`store.py:1478,1487`，注：该
     过滤是 base 提交就有的既存行为），于是删卡产生的真实敞口在持仓面板里直接消失。
  4. 唯一仍生效的补救是**进程重启**时 `start()` 的一次性 `_recover_workers()`（对 PAUSED/STOPPED
     有效、对 DELETED 无效）。
- **与用户合同的关系（这不是用户已接受的取舍）**：`24-user-authorized-final-guardian-fix.md` 只
  禁止「周期性 scheduler/tick 反复发现全部任务」，并未要求放弃人工暂停后的本卡 drain。合规的最小
  修法完全是任务本地的、不引入任何全局扫描。`42-final-guardian-scanner-fix.md` §9.4 把它写成剩余
  风险，但只描述为「退出当下不立即 drain」，**低估了「packet 63 之后已无 tick 兜底」这一半**——
  这正是 `23-packet-62-reconciliation-hold.md` 判定 H-1 时提醒过的连带效应。
- **建议修复（任务本地，零全局扫描）**：
  1. `post_pause` 不再置位 `stop_event`（或改置一个「暂停」专用的、`_worker_round` 在
     `_reconcile_own_legs` **之后**才检查的标志）。这样 Q2 天然生效：worker 先把自己的腿查到终态、
     结算该组，然后因 `status != RUNNING` 退出——**绝不会开新组**（`_worker_round:962-963` 就是
     这个判断），所以「尽快停」的语义不被破坏。
  2. `post_delete` 同理：置 `deleted` 后仍派一个 drain-only worker 收尾；并把 `STATUS_DELETED`
     加入 `_recover_workers` 的兜底状态集合（否则重启也救不回来）。
  3. 补确定性回归：dispatch 出一组 UNKNOWN 腿 → `post_pause` → 断言 worker 退出前
     `query_calls >= 2`、两腿 `terminal=1`、该组已结算（`pair_outcome` 非 NULL）、且
     `scheduled_attempt_count` 未增加（没开新组）；`post_delete` 同构一条；再补一条「DELETED 卡
     重启后 `_recover_workers` 能 drain」。

### P2 #1 — `settle_attempt_no_counters` 硬编码 `confirmed_failed`：429 与「另一腿真成交」同时发生时，真实单腿敞口被记成「已确认失败」且不记 `leg_exposure`

- **文件/行**：`backend/hedge_open_tasks/store.py:1029-1032`
  （`UPDATE … SET pair_outcome = PAIR_CONFIRMED_FAILED`，无视两腿真实结果）。
- **机理**：`_dispatch_live` 的 `rate_limited` 分支（`service.py:1379-1396`）**不解析**两腿真实
  verdict、**不 resolve** 该组；若两腿都不是 `UNKNOWN_QUERYING`（例如一腿 429→立即按 client-ID 查到
  absent、另一腿 2xx 直接 FILLED），连 `_mark_legs_querying` 都不调，两条 leg 行仍是 `PREPARED`
  （`terminal=0`，因此**仍会被 drain 查到**，无孤儿风险——这点我专门验过）。drain 把两腿查到终态后，
  `rate_paused` 为真 → `settle_attempt_no_counters` → 硬盖 `confirmed_failed`。
- **实测复现（scratchpad 脚本 `verify_429_mislabel.py`，原始输出）**：

  ```text
  perp leg really accepted+FILLED: order_id=p7 status=FILLED base=0.5
  spot leg absent                : order_id=None status=UNKNOWN

    pair_outcome  = 'confirmed_failed'   (truth: 'single_leg' single-leg exposure)
    leg_exposure  = None   (expected the advisory naked-leg record)
    positions     = [{'coin': 'BTCUSDT', 'direction': 'forward', 'position_qty': '-0.5', …}]

  DEFECT CONFIRMED: True
  ```

- **影响**：一条真实的裸空头（`position_qty=-0.5`）已经开出来了，持仓面板**如实**显示（
  `aggregate_positions` 纳入任何 `cumulative_base_qty>0` 的腿，这部分是对的），但开单日志的组级
  结论写成「已确认失败」，且 `leg_exposure` 这个「单腿敞口」告警字段为空。「单腿敞口」是本产品最
  安全关键的标签之一，把它降级成「失败」有让操作员误判「什么都没发生」的现实风险。
- **为何定 P2 而非 P1**：每条腿的 `order_id`/`status`/累计数量与持仓聚合都仍然真实可见，信息没有
  丢失、只是组级标签与告警字段错了；且需要「429 与另一腿成功」同时命中。修 P1 #1 的 (1) 清粘滞
  字段**不会**修掉这条（同一组内 429 当场就是 `rate_paused`），所以必须单列。
- **建议修复**：让 `settle_attempt_no_counters` 复用 `finalize_attempt` 的**类别推导**
  （按两腿 `order_id` 决定 accepted/single_leg/failed，并在 single-leg 时写 `leg_exposure`），
  只跳过 `_apply_task_counters` 的**计数器与阈值**部分；或改为给 `_apply_task_counters` 传一个
  `skip_counters=True` 参数。补一条回归：429 + 另一腿 FILLED → `pair_outcome == single_leg`、
  `leg_exposure` 非空、`fail_count == 0`。

### P2 #2 — live 卡片可能停在 `status=running` 但没有任何 worker 在跑，而 API/UI 无法分辨

- **文件/行**：`service.py:980-981`（预检不完整/致命 → `return True` 退出）、`:964-965`（Start gate
  关 → 退出）、`:904-907`（worker 异常兜底 `pass` 后退出）；`task_to_doc`（`service.py:118-148`）
  无任何 worker 存活字段。
- **机理**：H-1 修复后 live 模式没有周期 tick，worker 退出后**只有**人工 Start/recover 或进程重启
  会重启它。一次偶发的价格/余额读取失败（`_resolve_fresh_preflight` 返回 `None`）就会让 worker
  以 fail-closed 退出，而卡片状态仍是 `running`、计数停在半途。
- **影响**：这是**安全方向**的失效（少开单，不是多开单），也是用户在 amendment 21/24 里明确选择的
  「无守护、人工恢复」语义的必然结果，`42` 报告 §9.1 已如实记录。但**操作员没有任何信号**可以区分
  「卡片正在跑」和「卡片卡死等我手动恢复」——`GET /api/hedge-open-tasks` 只回 `status=running`。
  日志里确有 `preflight_incomplete` 事件可查，但需要主动翻日志。
- **建议**：在 task 文档里加一个后端权威的、非猜测的 worker 存活/最后活动字段（例如
  `worker_active: bool` 由 `_workers` 注册表派生，或 `last_worker_exit_reason` 由退出分支写入
  task_event），让前端能提示「需人工恢复」。这是**加字段的加性变更**，不改任何调度语义。
  （若用户认为翻日志足够，可作为已接受限制显式记录在 PRD/handoff，不再算缺口。）

### P3 #1 — 跨进程的「同卡单组」保证依赖 SQLite DEFERRED 事务的读后写，理论上可被两个进程共用同一 DB 打破

`prepare_attempt` 在 `with self._lock, self._conn:` 内先 SELECT 在途守卫再 INSERT。同进程有
`threading.RLock` 完全串行化（`test_2` 已证峰值并发 1）；但跨进程时 SQLite 默认 DEFERRED 事务在
第一次写之前不持写锁，两个进程理论上可都读到「无在途」再各自 INSERT。实际触发需要人为让两个服务
进程指向同一个 `data/hedge-open-tasks.sqlite3`（端口不同）。`40-fix-review-1-backend-r2.md` §9.3
已如实记录「跨进程恢复仅同进程模拟」。若未来允许多进程部署，需要 `BEGIN IMMEDIATE` 或一个进程级
单例锁。**本轮不构成阻断**。

### P3 #2 — `_pump_worker` 测试 seam 不注册 `_stop_events`，导致 pause/delete 中断路径零同步覆盖

`_pump_worker`（`service.py:913-925`）直接循环 `_worker_round`，从不创建 `_stop_events[task_id]`；
只有 `ensure_worker` 会创建。因此所有用该 seam 驱动的用例（含迁移过来的 review-2 17 用例）里
`_wake_worker` 都是空操作，`_worker_round` 首行的 stop 检查恒不命中。这正是 P1 #2 逃过 897 个
测试的机制。建议 seam 与 `ensure_worker` 共享同一套 event 初始化（或在 seam 里显式建 event），
使 pause/delete 语义可被同步测试观察。

---

## 必须修复后才能重审（按优先级）

1. **P1 #1**：清除 `pause_reason`/`pause_reason_zh` 的粘滞（恢复运行时置 NULL），并把「本组免计数」
   的判定改为基于该 attempt 自身的事实而非任务粘滞字段；补「429 → 人工恢复 → 下一组 FILLED 应
   记为 `accepted_pair` 且计数器正确」与「恢复后阈值暂停仍生效」两条确定性回归。
2. **P1 #2**：人工 `pause`/`delete` 必须先把本卡在飞腿查到终态并结算该组、再退出（不得开新组），
   并把 `STATUS_DELETED` 纳入 `_recover_workers` 的重启兜底；补三条确定性回归（pause drain、
   delete drain、DELETED 重启兜底）。**不得**为此引入任何全局扫描/守护——按 amendment 21 保持
   任务本地。
3. **P2 #1**：`settle_attempt_no_counters` 改为复用两腿事实推导 `pair_outcome` 并在单腿时写
   `leg_exposure`，只跳过计数器/阈值；补「429 + 另一腿 FILLED → single_leg + leg_exposure 非空 +
   fail_count 不变」回归。
4. **P2 #2**（可与上述一并做，或由用户判定为已接受限制并显式记录）：给 task 文档加后端权威的
   worker 存活/退出原因字段，让操作员能识别「需人工恢复」的卡。
5. **P3 #2**（建议）：让 `_pump_worker` 与 `ensure_worker` 共享 stop-event 初始化，使中断语义可测。

第 1、2 项是本次 REWORK 判定的直接依据；第 3 项虽定 P2，但与第 1 项同处一个结算函数，建议同批修完
以免下一轮再开一次授权。

## Residual risks（已知，本轮不要求消除）

- 冻结政策允许单腿敞口后继续调度，不自动撤单/补腿/平仓/修复；`target_n` 限量但不消除真实裸敞口
  风险——这是用户既定产品选择，非缺陷。
- 实时订单计数/权重响应头（`X-MBX-ORDER-COUNT-*`）仍未捕获，本地无法做主动频率门禁；交易所
  429/-1003 兜底已正确接到本卡暂停。已由 `40-fix-review-1-backend-r2.md` §9.2 如实记录为未实现。
- 本次评审未访问任何真实 Binance 私有接口。参数兼容性、账户字段真实形态、`recvWindow=60000ms` 与
  10s 查询超时在真实网络下的表现，仍需人工授权的脱敏采集证据。
- live 模式下 worker 退出后无自动重启（用户选择），需人工 Start/recover；见 P2 #2 的可观测性建议。
- 跨进程并发仅靠 SQLite 事务 + clientOrderId 不重发保证，无多进程集成测试（P3 #1）。
- 自动补单/撤单/平仓/还币/转账/完整会计仍不在本阶段范围，UI 必须继续如实标注不存在。

## 给 bookkeeper 的簿记提示（非缺陷）

1. 把 dispatch RECEIPT 与 `status.json` 的本次 review 记录里的 `target_model` 由
   `claude/Claude Sonnet 5` 更正为 `claude/Claude Opus 5`，并引用用户在派发执行时的模型替换决定。
2. `status.json.rework_count` 已是 4，`24` 号授权已消耗；本 REWORK 需要**新的**用户授权才能派发
   （`next_action = human_escalation_required`）。JSON 里的 `fix_start_prompt` 可在授权到位后原样
   投递，无需重写证据。
3. 前端在其 Review-1 ACCEPT 后源码未变（我核对 diff 内 `frontend/**` 的改动全部属于 `head` 之前
   已被接受的范围，`ab3126d..HEAD` 零前端改动），可按 `25` 号的路由保留该 ACCEPT。

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md
本地北京时间: 2026-07-25 20:34:50 CST
下一步模型: bookkeeper
下一步任务: record this REWORK verdict, correct the reviewer model metadata to Claude Opus 5, preserve the raw findings, and escalate to the user for one further narrowly bounded authorization covering the two P1 settlement/pause defects before dispatching the prepared fix_start_prompt

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "Claude Opus 5",
  "verdict": "REWORK",
  "diff_fingerprint": "ab3126d73549266a615fe43c1aeaf374b0db2d32:4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "MODEL SUBSTITUTION DISCLOSURE: the dispatch packet 64-review-1-backend-r3.dispatch.md names target_model 'Claude Sonnet 5', but the human operator explicitly assigned this Review-1 to Claude Opus 5 at execution time ('sonnet5 能力不够，我特意邀请你 opus5 进行 review1'). The model field above reports the real executing session, not the pre-written dispatch value; the bookkeeper must correct target_model in the RECEIPT and status.json. PRIOR INVOLVEMENT: this Opus 5 session authored nothing in this stage — no code, no document, no prior review. Another session of the same provider (Anthropic, Claude Sonnet 5) authored FRONTEND rework earlier in this stage (40-fix-review-2-frontend.md, 41-fix-open-log-pagination-frontend.md and the related frontend rework), but wrote none of the reviewed backend code (backend/hedge_open_tasks/**, backend/services/hedge_*, backend/app/server.py, backend/config.py), whose sole implementer/fixer across packets 62 and 63 is Claude-GLM (glm-5.2[1m], provider zhipu_glm). Review-1 provider-level cross-review isolation from the implementer of the reviewed task therefore holds. The schema enum has no category for 'same-provider author of another domain in the same stage', so 'none' is recorded per the dispatch instruction with the full disclosure here.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml#review_1",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/23-packet-62-reconciliation-hold.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/25-packet-63-final-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/42-final-guardian-scanner-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..ab3126d73549266a615fe43c1aeaf374b0db2d32",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/service.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/executor.py",
    "backend/hedge_open_tasks/scheduler.py",
    "backend/services/hedge_open_live_client.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/services/live_hedge_executor.py",
    "backend/app/server.py",
    "backend/config.py",
    "backend/tests/test_hedge_task_local.py",
    "backend/tests/test_hedge_purity.py",
    "backend/tests/test_hedge_review2_regressions.py",
    "backend/tests/test_hedge_api.py",
    "backend/tests/test_hedge_domain.py",
    "backend/tests/test_hedge_store.py",
    "backend/tests/test_hedge_service.py"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Sticky pause_reason after a 429 pause + manual resume permanently disables pair counters, the consecutive-failure pause gate and the fatal-leg stop, and records accepted pairs as confirmed failures",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 1026,
      "evidence": "store.pause_task writes pause_reason='rate_limited'; post_start resumes via store.set_task_status (store.py:433-444) whose UPDATE touches only status + updated_at_us and never clears pause_reason/pause_reason_zh. A repo-wide grep shows NO code path clears pause_reason (_apply_task_counters only re-writes task['pause_reason']; pause_task is the sole writer). service._reconcile_own_legs:1026 reads that sticky field as `rate_paused` and therefore routes EVERY later attempt whose pair_outcome IS NULL to store.settle_attempt_no_counters (store.py:1009-1033) instead of finalize_attempt (store.py:944-1007). settle_attempt_no_counters hardcodes pair_outcome=PAIR_CONFIRMED_FAILED and never calls _apply_task_counters. Reproduced offline with a fake transport and a temp SQLite DB (scratchpad verify_stale_rate_paused.py): after a confirmed 429 pause (fail_count=0, correct) and a manual resume identical to post_start, pair 2 whose BOTH legs reconciled to FILLED with orderIds s9/p9 was recorded as pair_outcome='confirmed_failed' with accepted_pair_count=0, success_count=0, task stuck at status='running'; dispatch (write) calls stayed at 2, i.e. no resend. No existing test resumes a 429-paused card and runs a further pair, which is why all 897 tests pass.",
      "impact": "After a single 429 pause plus a manual recovery — the most expected live path for this stage — the user's frozen 'pause after N consecutive confirmed failures' brake silently stops working for that card (consecutive_submission_failures never increments), the amendment-21 fatal-leg stop path in finalize_attempt (store.py:986-999) is skipped so a reconciled symbol/mode/filter/min-notional fatal no longer stops the card, successful accepted pairs are shown as '已确认失败' in the opening log, success_count/accepted_pair_count stay at 0 so the card never reaches done, leg_exposure is never recorded, and the stale pause_reason_zh keeps surfacing an expired 429 pause message on a running card.",
      "recommendation": "(1) Clear pause_reason and pause_reason_zh whenever a task transitions back to RUNNING (mirror pause_task's clearing of stop_reason). (2) Base the 'settle without counters' decision on a fact stored on the attempt itself (a rate-limit-settled marker written by _dispatch_live's 429 branch) rather than on the task's sticky pause_reason, so no window remains. (3) Add deterministic regressions: 429 pause -> manual resume -> next pair both legs FILLED must yield pair_outcome=accepted_pair, accepted_pair_count=1, success_count=1, pause_reason None; and after a resume, three consecutive confirmed failures must still trigger the threshold pause."
    },
    {
      "severity": "P1",
      "title": "Manual pause (and delete) abandons an unreconciled pair's live orders, and packet 63's removal of the periodic live tick leaves no component to recover them",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 939,
      "evidence": "post_pause (service.py:517-525) sets status=paused then calls _wake_worker, which sets that task's stop_event. _worker_round's FIRST statement (service.py:939-941) returns True on a set stop_event — BEFORE _reconcile_own_legs — so the Q2 drain-before-exit invariant does not apply to a manual pause (it only applies to the 429/insufficient signals, which return False). Under packet 62 the live tick's _recover_workers() re-launched a drain-only worker for any-status tasks holding non-terminal legs; packet 63 made live tick() a no-op (service.py:1088-1089), removing that safety net. Reproduced offline (scratchpad verify_manual_pause_drain.py, with the per-task stop event registered exactly as ensure_worker does): after one pair dispatched with both legs UNKNOWN (two possibly-live real orders), post_pause then one _worker_round gives exit=True with query_calls=0 and 2 legs still terminal=0; five further tick() calls produce zero queries. NOTE: a first attempt using only the _pump_worker seam did NOT reproduce, because _pump_worker never registers _stop_events, so _wake_worker is a no-op there — that seam gap is filed separately as P3. _recover_workers (service.py:1163) iterates only PAUSED and STOPPED, never STATUS_DELETED, so a deleted card's in-flight legs are not recovered even by a process restart, while aggregate_positions filters DELETED tasks out (store.py:1478,1487, pre-existing).",
      "impact": "Pause is the operator's emergency brake. After pressing it, this task's already-submitted market orders can still fill at Binance while the application stops querying them: actual fills/averages/fees are never persisted, the pair is never settled, and the in-flight guard never clears. That contradicts amendment 15 ('reconciliation is never abandoned') and amendment 21 row 5 verbatim. The only in-process remedy is pressing Start again, which sets the card back to RUNNING and therefore resumes submitting NEW real pairs after the drain — there is no recover-only action. For delete the exposure is worse: never recovered even on restart, and hidden from the positions panel.",
      "recommendation": "Keep it strictly task-local (no global scanner, per amendment 21/24): (1) do not set the stop_event on post_pause, or check a pause-specific flag only AFTER _reconcile_own_legs — the worker then drains its own legs, settles the pair, and exits because status != RUNNING (service.py:962-963), so it can never open a new pair; (2) do the same for post_delete and add STATUS_DELETED to _recover_workers' fallback status set; (3) add deterministic regressions: dispatch an UNKNOWN pair -> post_pause -> assert query_calls >= 2, both legs terminal=1, pair settled, and scheduled_attempt_count unchanged; the same for post_delete; plus a DELETED-card restart recovery case."
    },
    {
      "severity": "P2",
      "title": "settle_attempt_no_counters hardcodes confirmed_failed, so a 429 coinciding with a genuinely accepted leg records a real single-leg exposure as a confirmed failure with no leg_exposure",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 1029,
      "evidence": "store.settle_attempt_no_counters (store.py:1029-1032) stamps pair_outcome=PAIR_CONFIRMED_FAILED unconditionally, ignoring the two legs' real outcomes, and never records leg_exposure. service._dispatch_live's rate_limited branch (service.py:1379-1396) neither parses the leg verdicts nor resolves the pair; when neither leg is UNKNOWN_QUERYING it does not even call _mark_legs_querying (the leg rows stay PREPARED with terminal=0, so they are still drained — verified, no orphan). Reproduced offline (scratchpad verify_429_mislabel.py): spot POST hit 429 and its immediate client-ID query proved the order absent, while perp was accepted and FILLED (a real naked short, position_qty=-0.5 correctly shown by aggregate_positions) — yet pair_outcome='confirmed_failed' (truth: single_leg) and leg_exposure=None.",
      "impact": "An actually-open naked leg is labelled '已确认失败' at pair level and the advisory single-leg exposure marker is missing, so an operator scanning the opening log can conclude nothing happened. Per-leg orderId/status/cumulative figures and the positions aggregate remain truthful, which is why this is P2 rather than P1; the fix for the sticky-pause_reason P1 does not fix this case because within the same pair rate_paused is legitimately true.",
      "recommendation": "Reuse finalize_attempt's category derivation (accepted / single_leg / failed from the two legs' order_id, writing leg_exposure on single_leg) inside settle_attempt_no_counters, skipping only _apply_task_counters' counter/threshold work — e.g. add a skip_counters flag to _apply_task_counters. Add a regression: 429 on one leg + FILLED on the other must yield pair_outcome=single_leg, non-null leg_exposure and unchanged fail_count."
    },
    {
      "severity": "P2",
      "title": "A live card can sit at status=running with no worker at all, and no API field lets the operator tell it needs manual recovery",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 980,
      "evidence": "With H-1 fixed there is no periodic live tick, so a worker that exits is relaunched only by a manual Start/recover or a process restart. _worker_round exits on a fail-closed preflight-incomplete or preflight-fatal signal (service.py:980-981), on Start-gate-off (964-965), and after the last-resort exception containment in _run_task_worker (904-907) — while the task row stays status='running'. task_to_doc (service.py:118-148) exposes no worker-liveness or last-exit field, so GET /api/hedge-open-tasks cannot distinguish 'running' from 'stalled, awaiting manual recovery'. 42-final-guardian-scanner-fix.md §9.1 records the no-auto-restart semantics as intended.",
      "impact": "A single transient ticker/balance read failure can leave a half-finished card that looks live but will never progress until the operator notices and presses Start. The failure direction is safe (under-execution, no unauthorized order) and the semantics are the user's explicit choice, but the operator has no positive signal — only a preflight_incomplete row buried in the log.",
      "recommendation": "Add a backend-authoritative additive field (e.g. worker_active derived from the _workers registry, or last_worker_exit_reason written by the exit branches as a task_event) so the UI can prompt '需人工恢复'. This changes no scheduling semantics. If the user prefers relying on the log, record it explicitly as an accepted limitation in the PRD/handoff instead."
    },
    {
      "severity": "P3",
      "title": "Cross-process one-pair-per-task guarantee relies on a read-then-write inside a SQLite DEFERRED transaction",
      "file": "backend/hedge_open_tasks/store.py",
      "line": 527,
      "evidence": "prepare_attempt performs the in-flight SELECT and the INSERT inside `with self._lock, self._conn:`. In-process the threading.RLock fully serializes it (test_2 observes peak concurrent dispatch = 1). Across processes SQLite's default DEFERRED transaction takes no write lock before the first write, so two processes sharing one data/hedge-open-tasks.sqlite3 could both read 'no in-flight pair' and both insert. 40-fix-review-1-backend-r2.md §9.3 already records that cross-process recovery is only simulated in-process.",
      "impact": "Only reachable by deliberately running two server processes against the same SQLite file (different ports); no such deployment exists today. Would allow two concurrent reservations and therefore two real pairs for one card.",
      "recommendation": "If multi-process deployment ever becomes possible, use BEGIN IMMEDIATE for prepare_attempt or add a process-singleton lock on the data directory. No change required this round."
    },
    {
      "severity": "P3",
      "title": "_pump_worker test seam never registers a stop event, so the pause/delete interrupt path has zero synchronous test coverage",
      "file": "backend/hedge_open_tasks/service.py",
      "line": 913,
      "evidence": "_pump_worker (service.py:913-925) loops _worker_round directly and never creates _stop_events[task_id]; only ensure_worker (866-884) does. Every case driven through the seam — including the 17 migrated review-2 regressions — therefore has _wake_worker as a no-op and can never hit _worker_round's first-line stop check. This is the exact mechanism by which the P1 manual-pause defect escaped all 897 tests, and it also made my own first reproduction attempt fail before I registered the event as ensure_worker does.",
      "impact": "The seam silently diverges from the production worker on interrupt semantics, so pause/delete/stop behaviour cannot be asserted deterministically and future regressions in that path will not be caught.",
      "recommendation": "Have _pump_worker share ensure_worker's stop-event initialization (or create the event explicitly), so pause/delete interrupts are observable through the synchronous seam."
    }
  ],
  "required_fixes": [
    "Clear the sticky pause_reason/pause_reason_zh when a task returns to RUNNING, and base the 'settle without counters' decision on a per-attempt fact rather than the task's pause_reason, so that after a 429 pause + manual resume the pair counters, the consecutive-failure threshold pause and the fatal-reconciled-leg stop all keep working and an accepted pair is no longer recorded as confirmed_failed. Add the two named deterministic regressions.",
    "Make manual pause and delete drain their own in-flight legs to terminal and settle the pair before the worker exits (without opening a new pair), and add STATUS_DELETED to _recover_workers' restart fallback, keeping everything task-local with no global scanner. Add pause-drain, delete-drain and DELETED-restart regressions.",
    "Make settle_attempt_no_counters derive pair_outcome from the two legs' real outcomes and record leg_exposure for a single-leg result, skipping only the counter/threshold updates; add a regression for 429-on-one-leg plus FILLED-on-the-other yielding single_leg with a non-null leg_exposure and unchanged fail_count.",
    "Either expose a backend-authoritative worker-liveness / last-exit field so an operator can see that a status=running live card actually needs manual recovery, or have the user explicitly accept and record the log-only visibility as a known limitation."
  ],
  "residual_risks": [
    "The frozen policy intentionally keeps scheduling after a single-leg exposure and adds no automatic repair; target_n bounds but does not remove real naked-exposure risk. This is a product choice, not a defect.",
    "Live order-count/weight response headers (X-MBX-ORDER-COUNT-*) are still not captured, so no local active rate gate exists; the exchange's own 429/-1003 is the backstop and is correctly wired to a task-local pause. Honestly recorded as unimplemented in 40-fix-review-1-backend-r2.md §9.2.",
    "No real Binance private request was made in this review. Live field compatibility, the 60000ms recvWindow and the 10s query timeout still need authorized, sanitized factual evidence before first live use.",
    "In live mode a worker that exits is never auto-restarted (the user's explicit choice); manual Start/recover or a process restart is required — see the P2 observability finding.",
    "Cross-process concurrency rests on SQLite transaction behaviour plus client-ID no-resend, with no multi-process integration test (P3).",
    "Cancel, close, repay, transfer, automatic remediation and full accounting remain outside this stage; the UI must keep stating they do not exist."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是 2026-07-hedge-open-real-api-v1 的后端返工实现者。禁止调用、启动或转派任何其他模型会话或 adapter。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start、绝不 commit、绝不改 status.json / 70-handoff.md / 任何契约文档（15/16/21/23/24/25/42/50/58/64 号）。\n\n先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/64-review-1-backend-r3.md（本评审全文，含最后 JSON verdict 与三段实测复现输出）、21-task-local-runtime-and-manual-pause-amendment.md（运行时最高合同）、24-user-authorized-final-guardian-fix.md（H-1 授权边界）、15-immediate-loop-and-open-log-amendment.md（对账绝不放弃 + 错误矩阵）、42-final-guardian-scanner-fix.md（packet 63 已做的 H-1 修复，必须保留）、40-fix-review-1-backend-r2.md（packet 62 基线）。\n\n被审指纹 ab3126d73549266a615fe43c1aeaf374b0db2d32:4538945aa1e6ed3ea89a4f00f60a7dc71c97cc634dcb042c45d39ecc5a6e9772 是你的起点，bookkeeper 会在你完成后重算新指纹。\n\n绝对不能破坏的既有性质（packet 62 + 63，全部有回归钉住）：live start() 只做一次 _recover_workers() 后返回且不启动 HedgeOpenScheduler；live tick() 是安全空操作（不枚举任务、不拉 worker）；post_start 只启动指定卡；每卡一个有界 worker 只查自己的腿；target_n 原子硬上限 + 同卡 pair 串行 in-flight 守卫；双腿 pair 内并发；无 orderId 只按 clientOrderId 查询绝不重发；store 锁内不调 executor；7 端点冻结 allowlist 与签名前置门；默认关闭。**不得引入任何全局守护/周期扫描器**。\n\n必须修复四项：\n\n1) P1 —— 粘滞 pause_reason 导致计数器/阈值/致命停机失效。证据：store.set_task_status（store.py:433-444）只更新 status+updated_at_us，从不清 pause_reason/pause_reason_zh；全仓唯一写入点是 pause_task；于是 post_start 恢复后 pause_reason 永久停在 'rate_limited'，service._reconcile_own_legs:1026 的 rate_paused 恒为真，此后每个 pair_outcome IS NULL 的组都走 settle_attempt_no_counters（硬盖 confirmed_failed、完全不调 _apply_task_counters）而不是 finalize_attempt。实测：429 暂停 → 人工恢复 → 下一组两腿都 FILLED（orderId s9/p9）却被记成 confirmed_failed，accepted_pair_count=0、success_count=0、卡片停在 running。修法：(a) 任务回到 RUNNING 时清空 pause_reason 与 pause_reason_zh（与 pause_task 清 stop_reason 对称）；(b) 把「本组免计数」的判定改为基于该 attempt 自身的事实（例如 _dispatch_live 的 429 分支在 attempt 行写一个 rate-limit-settled 标记，_reconcile_own_legs 读该标记选路径），不要再依赖任务级粘滞字段。两者都要做。\n\n2) P1 —— 人工 pause/delete 丢弃在飞真实订单。证据：post_pause（service.py:517-525）置位 stop_event，_worker_round 第一行（939-941）在 _reconcile_own_legs **之前**就 return True 退出，因此 Q2「先 drain 后退」对人工暂停不生效；packet 63 把 live tick 变 no-op 后不再有兜底。实测：一组两腿 UNKNOWN（两笔真实订单可能在交易所）→ post_pause → 一次 _worker_round 得 exit=True 且 query_calls=0、两腿仍 terminal=0，此后 5 次 tick() 零查询。另：_recover_workers（service.py:1163）只遍历 PAUSED/STOPPED，不含 STATUS_DELETED，被删卡片的在飞腿连重启都救不回来。修法：(a) post_pause 不再置位 stop_event，或改置一个 _worker_round 在 _reconcile_own_legs **之后**才检查的暂停标志——这样 worker 先把本卡腿查到终态并结算该组，再因 status != RUNNING 退出（962-963 已保证绝不开新组）；(b) post_delete 同样给一个 drain-only 收尾路径，并把 STATUS_DELETED 加入 _recover_workers 的兜底状态集合。保持任务本地，零全局扫描。\n\n3) P2 —— settle_attempt_no_counters（store.py:1029-1032）硬编码 pair_outcome=PAIR_CONFIRMED_FAILED，无视两腿真实结果且不写 leg_exposure。实测：spot 429 后按 clientOrderId 查到 absent、perp 2xx FILLED（真实裸空头 position_qty=-0.5 已开出），组级却记 confirmed_failed 且 leg_exposure=None。修法：复用 finalize_attempt 的类别推导（按两腿 order_id 决定 accepted/single_leg/failed，single_leg 时写 leg_exposure），只跳过 _apply_task_counters 的计数器/阈值部分（例如给 _apply_task_counters 加 skip_counters 参数）。\n\n4) P2 —— live 卡片可停在 status=running 却无 worker，API 无法分辨。task_to_doc（service.py:118-148）没有 worker 存活字段；worker 在预检不完整/致命、Start gate 关、异常兜底后退出而 task 仍 running。修法：加一个后端权威的加性字段（worker_active 由 _workers 注册表派生，或 last_worker_exit_reason 由退出分支写 task_event），不改任何调度语义。若你判断该字段会牵动前端契约，就只写后端字段 + 记录，不要改 frontend/**。\n\n（建议项，可一并做）_pump_worker（service.py:913-925）不注册 _stop_events，导致 pause/delete 中断路径零同步覆盖——这正是 P1 #2 逃过 897 个测试的原因。让 seam 与 ensure_worker 共享 stop-event 初始化。\n\n必须新增的确定性回归（离线、fake transport、零 sleep race，先能在修复前复现旧缺陷再验证修复）：\n- 429 暂停 → 人工恢复 → 下一组两腿 FILLED ⇒ pair_outcome=accepted_pair、accepted_pair_count=1、success_count=1、pause_reason is None；\n- 恢复后连续 3 次已确认失败 ⇒ 仍触发阈值暂停；\n- 一组 UNKNOWN 腿 → post_pause ⇒ worker 退出前 query_calls>=2、两腿 terminal=1、该组已结算、scheduled_attempt_count 未增加（没开新组）；\n- post_delete 同构一条；DELETED 卡重启后 _recover_workers 能 drain 一条；\n- 429 + 另一腿 FILLED ⇒ pair_outcome=single_leg、leg_exposure 非空、fail_count 不变。\n\n允许修改：backend/hedge_open_tasks/{service.py,store.py,domain.py}，backend/services/live_hedge_executor.py（仅本次分类/标记所需的最小改动），backend/tests/test_hedge_task_local.py、test_hedge_review2_regressions.py、test_hedge_store.py、test_hedge_service.py、test_hedge_api.py（若新增字段需同步冻结字段集）。禁止修改：frontend/**、docs/**、PRD、10-design/11-adr、reports/api-samples/**、status.json、70-handoff.md、任何契约文档与本评审文件、环境/凭据/网络配置、backend/hedge_open_tasks/scheduler.py 与 backend/app/server.py（除非新增字段确实需要最小接线，需在报告中说明理由）。\n\n精确自测（提交前全部跑绿，原始输出追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt）：\n.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_purity.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q\n.venv/bin/python -m pytest backend/tests -q\nnode frontend/self-check.js\n.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q\ngit diff --check\n\n把实现说明写入 reports/agent-runs/2026-07-hedge-open-real-api-v1/44-fix-review-1-backend-r3.md（新文件，不覆盖已有 40/41/42 号报告），列出 changed files、每条新增回归先复现旧缺陷再验证修复的证据、H-1 与 packet 62 既有性质未被破坏的证据、剩余风险，然后停止等待 bookkeeper——不 commit、不派发评审、不自行判定验收。成功标准：上述六条新增回归在修复前可复现所述缺口、修复后全绿；backend/tests 全量与前端自检、Harness 协议套件全绿；live start()/tick()/post_start 的 H-1 性质与 test_6a/6b/6c 仍全绿；全程零真实 POST、零私有网络、零凭据访问。",
  "next_action": "human_escalation_required"
}
```
