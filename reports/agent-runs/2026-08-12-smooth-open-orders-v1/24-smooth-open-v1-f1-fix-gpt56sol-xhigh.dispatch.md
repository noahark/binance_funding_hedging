# Identity

- task_id: `smooth-open-v1-f1-fix-gpt56sol-xhigh`
- target_role: `Implementer`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `38`
- required_skill: `agents/skills/minimal-change-engineer.md`

# Goal

在唯一 worktree `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`、唯一分支 `smooth/v1-fullstack` 上，由原实现者 `gpt-5.6-sol`（reasoning `xhigh`）修复 Grok 4.6 Review-2 的唯一 `in-range` 发现 F1：真实 `BestBidAskProvider` 首次发布行情时，service 持 `_smooth_lock` 调用 `subscribe`，provider 回调又等待同一把锁，导致稳定约 5 秒 `TimeoutError`；订阅失败还会在 gate 已打开后让 worker 未捕获异常退出。

Human 于 2026-08-13 明确决定：本任务重，不限制 FIX 次数，直接继续修复。本轮记为 `rework_count=4`，不再因原三轮上限自动停下；但每轮仍须严格遵守独立评审与 Human 发布授权。本包是窄范围 Review-2 修复，只修 F1，不修或重开 Human 已接受的 L1/L2/L3，也不改变 D15/D16、immediate、close、executor、次数与成交 1 次语义。

固定修复基线为 `e74f3d5cf20f9f980ef023ed35a9c40ff3b8b174`。形成一个新的本地 delivery commit；不安装依赖、不联网、不控制服务、不 push、不 merge。

# Allowed Files

仅允许修改：

- `backend/hedge_open_tasks/service.py`
- `backend/tests/test_smooth_gate_worker.py`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-fix-gpt56sol-xhigh.handoff.md`（唯一新建、create-only）

Bookkeeper 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-fix-gpt56sol-xhigh.handoff.md
exit 0（路径不存在，可由本任务创建）
```

其他文件全部只读。特别禁止修改 `backend/services/best_bid_ask_provider.py`、`backend/hedge_open_tasks/store.py`、domain、server、frontend、executor、live client、preflight provider、snapshot、`requirements.txt`、任何既有 evidence、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md` 与 `.venv/`。若这两个生产/测试文件不足以完成 F1，创建 blocked handoff 后停止，不得自行扩权。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/24-smooth-open-v1-f1-fix-gpt56sol-xhigh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Implementer 段
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`，以 Bookkeeper Verification 的 `verified-rework`、F1 证据和最小修复要求为准
10. `backend/hedge_open_tasks/service.py` 的 `_ensure_smooth_subscriptions`、`_wait_for_smooth_gate`、`_on_smooth_market_change`、`_pause_task_local` 及其直接调用点
11. `backend/services/best_bid_ask_provider.py` 的 `subscribe/release/_start_watch/_watch/_notify`（只读，用于真实组合回归）
12. `backend/tests/test_smooth_gate_worker.py` 与只读 `backend/tests/test_best_bid_ask_provider.py` 中的立即返回 fake source 形状

启动必须核对：`pwd` 精确匹配 worktree；分支为 `smooth/v1-fullstack`；工作树干净；status revision `38`、task id/model/provider 与 packet 一致；`status.json.base_sha=e74f3d5cf20f9f980ef023ed35a9c40ff3b8b174`、`delivery_sha=null`、`rework_count=4`；handoff 路径不存在；`.venv` 中 `ccxt` 未安装。任一不一致即写 blocked handoff 并停止。

# Acceptance Checks

1. **先测红并钉死真实根因**
   - 在 `test_smooth_gate_worker.py` 增加真实组合回归：实际 `HedgeOpenTaskService` + 实际 `BestBidAskProvider` + 零网络、立即返回有效 bookTicker 的 fake source，对同一 smooth task 订阅 spot/swap。
   - 当前缺陷必须先表现为约 5 秒超时；修复后 `_ensure_smooth_subscriptions` 必须在 1 秒内返回，两侧 watcher/ref 存在且 `task_id` 已登记。测试不得继续只用同步 `_Market` 冒充真实 provider。

2. **最小锁范围修复**
   - `_ensure_smooth_subscriptions` 持 `_smooth_lock` 时只允许检查既有 task 登记以及成功后的原子登记；任何 `provider.subscribe`、`provider.release` 均必须在锁外执行。
   - 两侧都成功后才登记。任一侧失败时，在锁外释放本次已成功侧，不登记 task，并原样抛出。
   - 若并发调用在本次订阅完成前已由另一调用方登记同一 `task_id`，本调用须在锁外释放自己增加的全部多余 refs 后返回；不得泄漏引用、重复登记或新增 per-task manager/event loop/监督器/状态机。

3. **订阅失败必须暂停收口**
   - `_wait_for_smooth_gate` 捕获 `_ensure_smooth_subscriptions` 的失败，复用现有 `_pause_task_local` 和既有 pause reason；用 `pause_zh` 明确说明“公共盘口订阅失败，任务已暂停，未发单”。不得新增 domain 常量、持久化列或状态。
   - `pause_task` 必须清掉刚打开/恢复的 smooth gate；结果为 paused、零 attempt、零 executor dispatch/订单，worker 最终退出。
   - 增加确定性回归：第一次订阅失败后上述断言成立；修复 fake source 后 `post_start` 能重新启动并成功建立两侧订阅，不被前次失败残留阻塞。

4. **冻结边界**
   - 不修 L1：不增加 Start OFF/`stop()` 与 reserve→dispatch 的新准入锁、`stopping`、store 复核或额外 gate 清理。
   - 不修 L2：不改下一 gate 的时钟获取点。
   - 不修 L3：不改 threshold 输入保存/重绘。
   - 不改 `BestBidAskProvider`、store、domain、server、frontend、D15/D16、immediate/close、fill-once/fill-all、`prepare_attempt`、executor/query/settlement。不要顺手重构或处理既存白名单失败。

5. **回归与交付**
   - 在未安装 ccxt、零网络、不开服务、不读凭证的现有 `.venv` 中依次运行：

```bash
.venv/bin/python -m pytest backend/tests/test_smooth_gate_worker.py -q
.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py \
    backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
    backend/tests/test_smooth_api.py backend/tests/test_hedge_domain.py \
    backend/tests/test_frontend_field_binding.py backend/tests/test_service_health.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py \
    backend/tests/test_hedge_api.py backend/tests/test_hedge_cycle_core.py \
    backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_task_local.py \
    backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_leverage.py \
    backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests/test_live_hedge_executor.py \
    backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q
git diff --check
```

   - 除全后端既存 `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 外所有命令必须成功；该失败仍须证明触发文件相对本修复基线零 diff且引入早于本阶段产品基线。任何新失败均不通过。
   - `git diff --name-only e74f3d5cf20f9f980ef023ed35a9c40ff3b8b174..HEAD` 必须仅为两个 Allowed 既有文件和唯一 handoff；禁止文件零 diff。
   - 创建唯一 handoff，author 区写 `base_sha=e74f3d5cf20f9f980ef023ed35a9c40ff3b8b174`、`delivery_sha=pending`，逐条映射 F1 根因、锁范围、失败暂停、真实 provider 回归与冻结边界。只提交 Allowed Files 与 handoff，形成一个新增本地 delivery commit，不 amend、不 push、不 merge。
   - Human Brief 返回合规 `[TASK_RESULT v2]`。`下一步模型` 为 `Bookkeeper（codex）`；`下一步任务` 要求读取唯一 handoff、核验 source SHA-256/允许文件/提交/全部测试并固定本轮 `base_sha..delivery_sha`；关卡为核验通过后直接准备 fresh、跨 provider 的窄范围 Review-2，不重走 Review-1（前提是本轮未扩文件、契约或风险）。

# Stop

遇到身份/基线不一致、handoff 已存在、必须修改禁止文件、ccxt 已安装、无法用真实 provider 组合测试稳定证明、或修复需要触碰 L1/L2/L3/D15/D16/immediate/close/executor 语义时，创建 blocked handoff 后停止，不得猜测或扩权。

完成最小修复、全部测试、唯一 handoff 和一个 delivery commit 后输出 Human Brief 并停止。不得自行启动 Reviewer、修改状态、安装 ccxt、联网、读取凭证、控制服务、创建任务、下单、push、merge、部署或实盘。
