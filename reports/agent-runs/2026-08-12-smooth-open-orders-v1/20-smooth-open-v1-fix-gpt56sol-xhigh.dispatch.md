# Identity

- task_id: `smooth-open-v1-fix-gpt56sol-xhigh`
- target_role: `Implementer`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `33`
- required_skill: `agents/skills/minimal-change-engineer.md`

# Goal

在唯一 worktree `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`、唯一分支 `smooth/v1-fullstack` 上，由原实现作者 `gpt-5.6-sol`（reasoning `xhigh`）完成平滑开单 V1 的第一轮代码返修。固定代码基线为 `9c333cdb58f38f7d19fa8d42b36379abd07baba8`。

Human 已于 2026-08-13 明确选择“接受当前限制，继续实现”：只修五项必修——provider 并发冷启动僵尸订阅、`APP_OFFLINE` 仍构造 provider、合法超长 signed threshold 逃逸 500、provider 持续失败零等待热循环、非 running 展开日志停止刷新；同时落实 D15（smooth 放行后删除每轮联网 fresh preflight）与 D16（首轮杠杆前移到任何订阅/gate/滑点计算之前）。L1/L2/L3 是 Human 接受的限制，本轮不得修、不得作为失败项。

这是代码层面的第一轮返修；`status.json.rework_count=3` 是阶段 Harness 对首轮交付后计划修订的累计记账，Human 已完成上限选择并允许当前收窄范围继续。实现形成一个新的本地 delivery commit，不 push、不 merge。

# Allowed Files

仅允许修改以下既有文件：

- 生产代码：
  - `backend/services/best_bid_ask_provider.py`
  - `backend/hedge_open_tasks/domain.py`
  - `backend/hedge_open_tasks/service.py`
  - `backend/app/server.py`
  - `frontend/index.html`
  - `frontend/self-check.js`
- 测试：
  - `backend/tests/test_best_bid_ask_provider.py`
  - `backend/tests/test_smooth_gate_worker.py`
  - `backend/tests/test_smooth_api.py`
  - `backend/tests/test_hedge_domain.py`
  - `backend/tests/test_frontend_field_binding.py`
  - `backend/tests/test_service_health.py`
- 唯一交接件（新建、create-only）：
  - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md`
  - Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md` 已通过。

其他所有文件均禁止修改，特别包括：

- `backend/hedge_open_tasks/store.py`、`executor.py`、`scheduler.py`
- `backend/services/live_hedge_executor.py`、`hedge_open_live_client.py`、`hedge_preflight_provider.py`
- `backend/domain/snapshot.py`
- `requirements.txt`
- `backend/tests/test_smooth_gate_store.py`、`test_hedge_store.py`、`test_hedge_service.py`、`test_hedge_api.py`、`test_hedge_cycle_core.py`、`test_hedge_cycle_close.py`、`test_hedge_task_local.py`、`test_hedge_review2_regressions.py`、`test_hedge_leverage.py`、`test_hedge_purity.py`、`test_live_hedge_executor.py`、`test_hedge_executor.py`、`test_private_client.py`
- `reports/agent-runs/**/status.json`、`reports/agent-runs/ACTIVE.json`、`PROJECT_STATE.md`、其他 stage 文件与 `.venv/`

本 dispatch 不授予 `status.json` 写权限；不要将任务自行改成 `reported`。若必须改禁止文件才能完成，写 blocked handoff 并停止，不得自行扩权。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/20-smooth-open-v1-fix-gpt56sol-xhigh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Task Handoff Evidence Contract 与 Implementer 两节
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-review-deepseek-v4-pro-r2.handoff.md`，以 Bookkeeper Verification 的 `verified-accept`、固定区间与 Human 决策关卡为准
10. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`，以 Bookkeeper Verification 的五项缺陷证据和 Human requirement change 为准
11. `docs/planning/smooth-open-orders-v1.md`，重点 D15、D16、§6.5、§16
12. `docs/planning/smooth-open-orders-v1-development-checklist.md`，重点活动 §12；§1–§11 仅是首轮历史
13. Allowed Files 中的既有源码与测试
14. 仅为回归边界只读：上述明确禁止修改的测试文件、`backend/hedge_open_tasks/store.py`、`backend/services/hedge_preflight_provider.py`、`backend/domain/snapshot.py`

启动必须核对：`pwd` 精确为 `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`，分支为 `smooth/v1-fullstack`，工作树干净，stage/task/model/provider/status revision `33` 与本 packet 一致，`status.json.base_sha=9c333cdb58f38f7d19fa8d42b36379abd07baba8`，handoff 路径不存在，`.venv` 中 `importlib.util.find_spec("ccxt") is None`。任一不一致即停止并返回 blocked。

# Acceptance Checks

1. **范围冻结与接受限制**
   - 不修 L1：不得增加 Start OFF/`service.stop()` 与 reserve→dispatch 的新准入锁、`stopping` 状态、store 侧复核或 gate 清理路径。
   - 不修 L2：不得改变下一 gate 的时钟获取点或承诺每轮严格完整 5 分钟。
   - 不修 L3：不得扩展行情表重绘时的 threshold 输入 capture/preserve selector。
   - 不改变 immediate、close、fill-once/fill-all、现有 executor/query/settlement 的既有语义；不新增状态列、event loop、manager、监督器、重试状态机、配置项或 timer。

2. **provider 并发启动与订阅回滚**
   - `BestBidAskProvider.start/subscribe` 的所有并发首次调用者必须等待同一个 ready 结果；loop 未 ready 或启动失败前不得登记任何可见 watcher/ref state。成功时同一 key 只创建一个 watcher。
   - `_ensure_smooth_subscriptions` 必须在 spot/perp 两侧都成功后才记录 task subscriptions；单侧失败要 release 已成功侧、task 不留登记、下一轮可重试。不得吞异常后伪装完成。
   - 回归必须确定性覆盖并发冷启动、已登记无 watcher 禁止态、单侧失败回滚与重试成功。

3. **offline 隔离与失败防自旋**
   - `config.offline=True` 时 `_build_hedge_service` 固定注入 `market_provider=None`，即使默认 source 被假设为可用也不得构造 provider、启动线程或 subscribe；非 offline 且 ccxt 缺失时既有 smooth 400 行为不变。
   - `_watch` 的异常分支和立即得到无效 snapshot 的分支在重试前使用一个最小、固定、可由 `close()` 立即打断的等待。不得使用指数退避、重试状态机或新配置。
   - fake source 测试须证明短窗口内 watch/on_change 次数有界，等待期间 close 立即返回且线程成功 join；所有测试零网络。

4. **threshold 与展开日志**
   - `validate_slippage_threshold_pct` 不依赖默认 Decimal context 对任意长度整数做 `quantize`。合法正负 30/100 位整数逐字保留整数位并规范化两位小数，API fake-provider 创建返回 `201`；`-0 → 0.00`、`.05 → 0.05`。
   - 超过两位小数、科学记数、`%`、空值/非字符串等格式非法输入返回 `400`。不得设置产品最大长度、改全局 Decimal context 或加依赖。
   - 只要任务仍存在且日志已展开，`running/paused/deleted/done/stopped` 都复用现有 2 秒 tick 刷新；收起或任务不存在才停止。不得新增 timer。self-check 与字段绑定测试必须覆盖 paused+展开仍请求、收起不请求。

5. **D16：杠杆严格前移**
   - live smooth 且 `scheduled_attempt_count == 0` 时，在进入 `_wait_for_smooth_gate` 以及任何 subscribe、gate 建立/恢复、第一次 `_smooth_eval` 之前调用现有 `_set_leverage_before_open`。
   - 失败沿用 `PAUSE_REASON_LEVERAGE_SET_FAILED` 与现有中文原因，此时必须零订阅、零 gate、零 attempt、零订单；首轮未调度后重新进入可幂等重试。不得提前到建卡，不新增持久化状态。
   - `_dispatch_one_for_task` 对 smooth 不得再次设置杠杆；immediate 的既有杠杆条件与位置保持不变，后续 smooth 轮次不重复设置。

6. **D15：smooth 放行后零联网、直接复用原链**
   - live smooth 的 market/manual/timeout 三种放行都直接使用建卡固化的 `q_common`、`position_side_mode`、`preflight_snapshot` 与 frozen `spot_route`，不得调用 `_resolve_fresh_preflight` 或 `HedgePreflightProvider.get_snapshot`。
   - 从 gate 判定通过到既有 `_dispatch_live` 两腿提交之间，只允许本地数据读取、既有 `prepare_attempt` 原子复核和请求对象构造；不得有联网读取、交易所设置、sleep 或其他等待。`prepare_attempt` 的任务状态、target、无在途 pair、gate seq、pass reason、次数硬上限与清 gate 语义保持不变。
   - 保留 create-task 首次完整 preflight、固化数据、regular_spot forward 预划转、缺腿/1000x 拒绝；immediate 与 close 的 live fresh preflight、immediate frozen/fresh route 检查保持不变；复用原有异步两腿提交、同步等返回、查单、结算与单腿暂停链，不复制 executor。
   - 用 spy 对 market/manual/timeout 分别断言顺序 `set_leverage → subscribe/open gate → market evaluation → prepare_attempt → dispatch`；放行后 leverage 与 preflight 调用计数不再增加，fake 网络/sleep 桩不被触达。

7. **测试、范围与交付**
   - 在未安装 ccxt、零网络、不开服务、不读凭证的现有 `.venv` 中依次运行：

```bash
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

   - 除全后端已知基线失败外，所有定向命令退出码必须为 0。全后端只允许原有唯一失败 `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients`，且触发仍只能是早于 base、零 diff 的 `backend/services/public_ip_service.py`；不得修改二者“修绿”。任何新增或不同失败均不通过。
   - `git diff --name-only 9c333cdb58f38f7d19fa8d42b36379abd07baba8..HEAD` 必须是 Allowed Files 与唯一 handoff 的子集；所有禁止文件零 diff。`git diff --check` 无输出，工作树在最终提交后干净。
   - 完成修改与全部测试后创建唯一 handoff；author 区写 `base_sha=9c333cdb58f38f7d19fa8d42b36379abd07baba8`、`delivery_sha=pending`，逐项映射五项必修与 D15/D16，记录所有命令结果及残余风险 L1/L2/L3。只提交 Allowed Files 与 handoff，形成一个新增本地 delivery commit，不 amend、不 push、不 merge。
   - Human Brief 返回合规 `[TASK_RESULT v2]`。`下一步模型` 写 `Bookkeeper（codex）`；`下一步任务` 写：读取唯一 handoff；执行核验 source SHA-256、允许文件、提交与全部测试并固定 `base_sha..delivery_sha`，并裁定任何 contested 项；关卡为通过后准备跨 provider Review-1。

# Stop

遇到身份/基线不一致、handoff 已存在、必须修改禁止文件、ccxt 已安装、无法在零网络下证明顺序、或发现会改变 L1/L2/L3/immediate/close/executor 既有语义的冲突，立即写 blocked handoff 并停止，不得猜测或扩权。

完成实现、自测、唯一 handoff 和一个 delivery commit 后输出 Human Brief 并停止。不得自行启动 Reviewer、修改状态、安装 ccxt、联网、读取凭证、控制服务、创建任务、下单、push、merge、部署或实盘。
