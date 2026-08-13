# Task Handoff: smooth-open-v1-fix-review-2-grok46

## Source Report (author-only; immutable after task end)

- task_id: `smooth-open-v1-fix-review-2-grok46`
- role: `Reviewer` / Review-2
- target model: `grok-4.6` / provider `xai`
- stage_id: `2026-08-12-smooth-open-orders-v1`
- created_at: `2026-08-13 14:01:03 CST`
- base_sha: `9c333cdb58f38f7d19fa8d42b36379abd07baba8`
- delivery_sha: `dfd38a6b71e686caf02475aa7954056d670fcead`

### 启动核对

fresh 只读会话。按 dispatch 顺序读取 `AGENTS.md`、本 dispatch、`ACTIVE.json`（`active=2026-08-12-smooth-open-orders-v1`）、`PROJECT_STATE.md`、`status.json`（revision `36`，`current_task.id=smooth-open-v1-fix-review-2-grok46`，固定 `base_sha=9c333cdb…` / `delivery_sha=dfd38a6b…`，`rework_count=3`）、`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer Review-2 段）、`agents/skills/reality-checker.md`、设计 D15/D16/§6.5/§16、清单活动 §12，以及实现/计划/Review-1 handoff（只作待核验声明）。

`git rev-parse` 两端 SHA 与 `status.json` 一致。区间提交为 `e369a23`（dispatch/status 控制上下文）+ `dfd38a6`（产品交付主体）。工作树 `HEAD=6825d37` 仅后续 harness 控制提交；`git diff dfd38a6 HEAD -- backend frontend` 为空，产品文件与 delivery 树一致。未移动 HEAD。`test ! -e` 本 handoff 路径通过。`.venv` 中 `ccxt` 未安装。

provider 披露：本复核为 `grok-4.6`（`xai`）。实现/修复作者为 `gpt-5.6-sol`（`openai`），跨 provider。Grok 4.6 曾参与本阶段更早版本产品设计的只读 advisory，但未撰写本轮返修计划或任何实现/修复代码；本结论只来自固定 SHA 源码与本会话可执行证据，不采信 advisory 观点，也不转述 Implementer / Kimi Review-1 作为证明。revision 35 的 Sonnet 5 Review-2 packet 未产生 handoff，未启动、未引用。

本任务只创建本 handoff。未改代码/计划/状态/既有 evidence，未安装依赖，未联网，未读凭证，未控制服务，未创建真实任务/下单，未 commit/push/merge/部署。

### 审查方法

用固定 SHA 的 `git diff` / `git show` 通读 12 个产品/测试文件，并阅读 `service.py` 建卡、worker、dispatch、provider 生命周期、前端刷新与 `captureMarketOpInputs`。禁止文件相对 base 零 diff。独立复跑专项、核心、executor、全后端、前端 self-check/字段绑定，并独立执行超长阈值、无盘口 400、以及真实 `BestBidAskProvider` + `HedgeOpenTaskService` 两侧订阅复现。

### 范围内发现（阻塞）

**F1 — in-range — 真实 provider 两侧订阅与 service `_smooth_lock` 死锁至 5 秒超时**

- 范围：本交付引入。旧代码在锁外调用 `subscribe`；`dfd38a6` 为做「全部成功才登记」把 `subscribe`/`release` 移进 `service.py::_ensure_smooth_subscriptions` 的 `with self._smooth_lock`。
- 证据锚点：
  - `backend/hedge_open_tasks/service.py` `_ensure_smooth_subscriptions`：持锁调用 `subscribe(key)`。
  - 同文件 `__init__` 把 `BestBidAskProvider.set_on_change(self._on_smooth_market_change)` 接到同一把锁。
  - `_on_smooth_market_change` 在 asyncio 线程上再取 `_smooth_lock`。
  - `backend/services/best_bid_ask_provider.py` `subscribe` 对新建 watcher 执行 `future.result(5)`，`_watch` 经 `_publish`/`_notify` 回调 `on_change`。
- 可执行复现（本会话，未改仓库；8/8 失败，每次 5.00–5.01 秒 `TimeoutError`，任务未写入 `_smooth_subscriptions`，provider `_states` 回滚为空）：

```text
HedgeOpenTaskService + 真实 BestBidAskProvider
+ test_best_bid_ask_provider._Source 立即返回 bookTicker
→ svc._ensure_smooth_subscriptions(task)
8/8: ('FAIL', ~5.01, 'TimeoutError', '', False, {})
```

- 当前实际影响：
  1. 现货 watcher 一旦在合约 `subscribe` 完成前发出回调，loop 线程堵在 `_smooth_lock`，合约 `_start_watch` 无法跑完，5 秒后 `TimeoutError`。
  2. `_wait_for_smooth_gate` 先 `open_smooth_gate` 再订阅且不捕获异常；失败后 worker 进 `_run_task_worker` 的 `WORKER_ERROR` 退出。启动恢复只在 `start()` 一次性执行，之后不会自动拉起。
  3. 结果是：任务仍可能显示 running、gate 已开或随后残留、没有有效订阅、5 分钟超时也不会成交；页面像在盯盘，实际没有。
  4. 已有任务在收行情时再开第二个平滑任务，任何一次 `on_change` 都可能在新任务持锁订阅期间打中这把锁，实盘比单测假市场更容易碰到。
- 现有测试测不到：`test_smooth_gate_worker` 注入的 `_Market.subscribe` 是同步假对象，不进 event loop，也不从 loop 线程回打 `_on_smooth_market_change`。
- 为何必须本轮修：这是必修 1 在真实组合根上的失败，不是 L1/L2/L3，也不是未安装 ccxt 的预期 400。未修前不能声称「可创建首个真实平滑任务」或「装上 ccxt 即可盯盘」。
- §1：这是固定树上的完整调用链 + 本会话 8/8 可执行失败，不是新假想场景。

### 修复要求（最小可执行）

只改本次 Allowed Files 内既有文件。禁止改 `store.py`、executor、live client、preflight provider、`snapshot.py`、`requirements.txt`。禁止为 L1/L2/L3 加锁、`stopping`、改时钟或扩大 `captureMarketOpInputs`。

1. **锁范围**：`_ensure_smooth_subscriptions` 不得在持有 `_smooth_lock` 时调用 `subscribe`/`release`。锁内只做「是否已登记」判断和成功后的登记。两侧订阅在锁外执行；任一侧失败则在锁外 `release` 已成功侧，不登记该 task。若提交登记前另一调用方已登记同一 task_id，释放本次多余引用后返回。不得新增第二个 event loop、manager 或监督器。
2. **调用方收口**：`_wait_for_smooth_gate` 必须接住订阅失败。不得让未捕获异常在 `open_smooth_gate` 之后把 worker 打死并留下 running。最小做法：捕获后走既有 `_pause_task_local`（`pause_task` 已清 gate），用中文 `pause_zh` 写明公共盘口订阅失败；零 attempt、零订单。不要新持久化列或新状态机。
3. **回归（必须能测红当前缺陷）**：用 `HedgeOpenTaskService` + 真实 `BestBidAskProvider` + 与 `test_best_bid_ask_provider._Source` 同类的立即返回源，对同一 task 订阅现货+合约，断言 `_ensure_smooth_subscriptions` 在 1 秒内返回、两侧有 ref、task 已登记。再覆盖：订阅抛错时任务暂停、无 attempt、worker 最终退出且可再次 `post_start` 重试。假 `_Market` 测试可留，但不能再当唯一证据。

修完后按清单 §12.6 复跑专项/核心/executor/前端/全后端；唯一允许失败仍是 `public_ip_service.py` 白名单测试。

### 已核对且不构成 REWORK 的项

- **必修 2**：`server.py::_build_hedge_service` 在 `config.offline` 时固定 `market_provider=None`，即使 `default_source_available()` 为真也不构造。无盘口时 `create_task` 仍 400 `smooth_market_unavailable`。本会话复跑确认。
- **必修 3**：`validate_slippage_threshold_pct` 改为正则补位，不再 `quantize`。本会话独立断言：±30/100 位整数与 `-0`/`.05` 规范化成功；`0.055`/`1e-2`/`5%`/空/非字符串 400。API 测试覆盖 201/400。
- **必修 4**：`_watch` 两条失败分支固定 `await asyncio.sleep(0.05)`，可被 cancel 打断；`test_failed_watch_retries_are_bounded_and_close_interrupts_wait` 通过。无指数退避或新配置。
- **必修 5**：`loadHedgeTasks` / `refreshExpandedRunningHedgeLogs` 改为任务仍存在即刷新；`setInterval(() =>` 仍为 4；self-check 对 paused+展开断言真实 URL `/api/hedge-open-logs?task_id=h-inline-1`。任务卡字段、暂停原因、日志按钮未删。
- **D16**：`_worker_round` 在 `_wait_for_smooth_gate` 前、且已确认 Start 开启后，对 live open + `scheduled_attempt_count==0` 调 `_set_leverage_before_open`；失败暂停且测试断言零订阅/零 gate/零 attempt/零订单。`_dispatch_one_for_task` 对 smooth 不再设杠杆；immediate/close 条件仍在原处。`test_hedge_leverage.py` 相对 base 零 diff 且本会话 352 核心回归通过。
- **D15**：live smooth 走固化 `q_common` / `position_side_mode` / `preflight_snapshot`，不调 `_resolve_fresh_preflight`。假市场顺序回归覆盖 market/manual/timeout：`set_leverage → open_gate/subscribe → market_evaluation → prepare_attempt → dispatch`，`preflight.calls==1`。放行后到 `prepare_attempt`/`_dispatch_live` 之间无 fresh preflight、无杠杆、无 sleep。建卡首次 preflight、regular_spot 预划转、缺腿/1000x 拒绝仍在 `create_task`。`store.py` 零 diff，`prepare_attempt` 原子复核未改。
- **次数与成交1次**：smooth `post_fill_once` 仍只 `force_smooth_gate` + `ensure_worker`，不直接 dispatch。硬上限仍由 store `prepare_attempt` 守。
- **L1/L2/L3**：未新增准入锁、`stopping`、store 复核、时钟改点；`captureMarketOpInputs` 仍不含 `hedge-threshold-*`。按 Human 决定只作发布限制，不判返工。
- **活文档**：不因文档缺失阻塞本 verdict。收尾时 Bookkeeper 应把 `docs/product/PRD.md`「smooth-open is visibly unavailable / No smooth execution」与 D15/D16/L1–L3/本 F1 同步到活文档和 `PROJECT_STATE.md`。`docs/api` 尚无平滑专章。

### 范围外

- `pre-existing-independent`：`backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 唯一失败，触发文件 `backend/services/public_ip_service.py`。两文件相对 base 零 diff。引入提交 `73f525d4c3033cd4e8d7c7afb09a975816742913` 是 base 祖先（`git merge-base --is-ancestor` 退出码 0）。不阻塞本交付。
- 无 `pre-existing-release-critical` 新项。
- 未提出其他新假设场景。

### Human 已接受限制（必须写入发布说明，不得当 REWORK）

- **L1**：Start 关闭或 `stop()` 可能落在行情放行与 reserve/dispatch 之间，仍可能发出该轮或误走模拟并消耗次数。关闸后先看任务卡和交易所。
- **L2**：新 gate 可能短于完整 5 分钟。把 5 分钟当上限，以任务卡剩余时间为准。
- **L3**：行情表重绘会把未提交的阈值输回 `0.05`。点平滑开单前再看输入框。
- **D15 代价**：smooth 放行后不再每轮查余额/规则/仓位模式/限频/路由；变化会变成交易所拒单或单腿，由任务卡告警与人工核对收口。
- **停机计入 5 分钟**：恢复时过期 gate 可直接 timeout。
- **D16**：首轮尚未调度的重启可在订阅/gate 前幂等再设杠杆。
- **未装 ccxt**：新建平滑任务 400，立即开单/平仓/其他功能不受影响。

### 发布准备度（ACCEPT 也不授权这些动作）

| 层级 | 本交付裁定 |
|---|---|
| 代码可进入 Human 合并决策 | **否**（F1 in-range） |
| 可安装生产依赖（ccxt） | 否；须 Human 单独授权，且 F1 未修前装上也会踩真实订阅死锁 |
| 可重启加载 | 否；本会话未授权重启。即便重启，未装 ccxt 时既存平滑任务只能超时/人工放行且无公共 WS |
| 可做真实公共 WS 验证 | 否；无连通证据，离线测试不能冒充 |
| 可创建首个真实平滑任务 | 否 |

上线前最小观察（不得由本会话执行）：F1 修复并经 Review-2；Human 授权装 ccxt、重启手动前台、小额真实公共 WS、再小额首个平滑任务。回退：停用平滑建卡（无 ccxt 或 offline 已拒绝新建）、暂停/删除运行中平滑任务、关 Start 前先暂停任务（L1）。

### 独立复跑命令与结果

- 专项/边界：`250 passed`（`test_best_bid_ask_provider` / `test_smooth_gate_store` / `test_smooth_gate_worker` / `test_smooth_api` / `test_hedge_domain` / `test_frontend_field_binding` / `test_service_health`）
- 核心：`352 passed`（含未改的 `test_hedge_leverage` / `test_hedge_cycle_*`）
- executor：`75 passed`
- 全后端：`1876 passed, 1 failed`（仅上述既存 `public_ip_service` 白名单）
- `node frontend/self-check.js` → 全部自检通过
- 字段绑定：`13 passed`
- `git diff --check` 固定区间：无输出
- 禁止文件相对 base：`store.py` / executor / live client / preflight provider / `snapshot.py` / `requirements.txt` 零 diff
- `importlib.util.find_spec("ccxt") is None`
- 真实 provider 两侧订阅：8/8 `TimeoutError` ≈ 5.01s（F1）

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`；`backend/hedge_open_tasks/service.py`；`backend/services/best_bid_ask_provider.py`；`backend/tests/test_smooth_gate_worker.py`
- 执行：Bookkeeper 核验本 handoff 的 source SHA-256、固定区间 `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead`、`REWORK` 与 F1 修复要求；因 `rework_count=3` 已达上限，向 Human 汇报四选一（缩窄/重设计/接受限制/停止），未经 Human 选择不得派发修复。
- 关卡：Human 决策。本 `REWORK` 不授权修复实现、安装 ccxt、重启、合并或实盘。
- 不能假设的事实：Kimi Review-1 `ACCEPT` 与实现 handoff 不能覆盖 F1；假 `_Market` 全绿不能证明真实 `BestBidAskProvider` 可订阅；L1/L2/L3 与 D15 代价仍是已接受限制，不得顺手改。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-v1-fix-review-2-grok46
执行结果: completed（完成）
结果摘要: 独立 Review-2：真实盘口 provider 与任务订阅锁互相卡住，两侧订阅必等 5 秒后 TimeoutError，worker 会异常退出。其余必修与 D15/D16 代码方向成立，但真实盯盘未通。L1/L2/L3 仍是已接受限制。返回 REWORK。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md]
检查结果: [fail：必修1 真实 BestBidAskProvider 两侧订阅与 _smooth_lock 死锁，8/8 约 5.01s TimeoutError，worker 会异常退出且无自动拉起；pass：offline 零构造、无 ccxt 平滑创建 400、超长阈值规范化/非法 400；pass：失败重试 0.05s 可被 close 打断，无新 timer；pass：非 running 展开日志续刷，任务卡字段/日志按钮仍在，L3 未改；pass：D15/D16 在假市场顺序回归与固化值路径成立，create-task 首次预检/划转/1000x 与 immediate 杠杆未改；pass：禁止文件零 diff、ccxt 未装、专项 250/核心 352/executor 75/前端 self-check+13；pass：全后端 1876+1，唯一失败为 base 前 public_ip_service 白名单，pre-existing-independent；pass：L1/L2/L3 与 D15 代价仅作发布限制，不判返工]
阻塞项: [F1 in-range：真实盘口订阅锁死锁，见本 handoff 修复要求]
本地北京时间: 2026-08-13 14:01:03 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md；reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json；backend/hedge_open_tasks/service.py；backend/services/best_bid_ask_provider.py；backend/tests/test_smooth_gate_worker.py；执行：核验 source SHA-256、固定区间 9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead 与 REWORK/F1；关卡：Human 决策（rework_count=3 已达上限，须先选择缩窄/重设计/接受限制/停止，未经选择不得派发修复）。
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md
修复要求: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-13 14:07:18 CST`
- source_sha256: `d441bf2366eb8d5738c34d96c7eb000232dcfbafbeefdbc2d0ec07c70361629c`
- status_revision_checked: `36`
- fixed_range_checked: `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead`
- verdict: `verified-rework`

核验通过：task/stage/role/provider、固定 SHA、唯一 create-only handoff、marker、`TASK_RESULT v2`、明确 `REWORK`、问题与修复路径、131 字摘要、八项合并检查和下一步 Human 关卡均符合 packet。`git diff dfd38a6..HEAD -- backend frontend` 为空，当前产品树仍等于固定 delivery。

Bookkeeper 独立复现 F1：用仓库测试源 `_Source/_Factory` 立即发布盘口，组合真实 `HedgeOpenTaskService` 与真实 `BestBidAskProvider`，连续两次调用 `_ensure_smooth_subscriptions` 均得到 `TimeoutError`，耗时分别 `5.011s`、`5.009s`；两次均 `task_registered=False`、`provider_state_count=0`。固定树源码同时证明 service 持 `_smooth_lock` 调 `subscribe`，而 provider event-loop 回调 `_on_smooth_market_change` 会再取同一把锁，且 `_wait_for_smooth_gate` 在开 gate 后未捕获该异常。因此 F1 是当前交付可重复的 `in-range` 阻塞，不是 L1/L2/L3，也不能被既有假 provider 全绿用例抵消。

状态推进边界：Review-2 结果可核验为 `verified`，但交付不接受。`rework_count=3` 已达 Harness 上限，保持 3，不自动派第四轮；须由 Human 在“缩窄、重设计、接受限制、停止”中明确选择。修复、安装 ccxt、重启、合并、push、部署和实盘均未获授权。
