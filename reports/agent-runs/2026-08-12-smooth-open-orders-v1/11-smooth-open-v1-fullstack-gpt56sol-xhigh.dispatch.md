# Identity

- task_id: `smooth-open-v1-fullstack-gpt56sol-xhigh`
- target_role: `Implementer`
- target_model: `gpt-5.6-sol`
- provider: `openai`
- status_revision: `18`
- required_skill: `agents/skills/senior-developer.md`

# Goal

在唯一 worktree `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`、唯一分支 `smooth/v1-fullstack` 上，由 Human 选定的 `gpt-5.6-sol`（reasoning `xhigh`）一次完成平滑开单 V1：公共一档盘口 provider、每轮持久化 gate、worker/API 接线与前端真实接线。固定代码基线为 `e955bdd300d214c5c3ad5c1acd629c0d21080165`；分支含本任务控制提交，但受审范围仍固定为该 `base_sha` 到最终 `delivery_sha`。

严格沿用现有立即开单的两腿提交、查单、结算及单腿处理链；平滑功能只决定本轮何时获准进入该链。按 CP1 provider → CP2 domain/store → CP3 worker/API → CP4 frontend 顺序推进，全部通过后写唯一 handoff，并形成一个新增的本地 delivery commit；不 push、不 merge。

# Allowed Files

仅允许修改或新建以下文件：

- 生产代码：
  - `backend/services/best_bid_ask_provider.py`（新建）
  - `backend/hedge_open_tasks/domain.py`
  - `backend/hedge_open_tasks/store.py`
  - `backend/hedge_open_tasks/service.py`
  - `backend/app/server.py`
  - `frontend/index.html`
  - `requirements.txt`（新建；只写定稿内容，不安装）
- 测试与自检：
  - `backend/tests/test_best_bid_ask_provider.py`（新建）
  - `backend/tests/test_smooth_gate_store.py`（新建）
  - `backend/tests/test_smooth_gate_worker.py`（新建）
  - `backend/tests/test_smooth_api.py`（新建）
  - `backend/tests/test_hedge_domain.py`
  - `backend/tests/test_hedge_store.py`
  - `backend/tests/test_hedge_service.py`
  - `backend/tests/test_hedge_api.py`
  - `backend/tests/test_frontend_field_binding.py`
  - `frontend/self-check.js`
- 唯一交接件（新建、create-only）：
  - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`
  - Bookkeeper 预检：`test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md` 已通过。

以下文件明确禁止修改：

- `backend/services/live_hedge_executor.py`
- `backend/services/hedge_open_live_client.py`
- `backend/services/hedge_preflight_provider.py`
- `backend/hedge_open_tasks/executor.py`
- `backend/hedge_open_tasks/scheduler.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_hedge_purity.py`
- `backend/tests/test_hedge_cycle_core.py`
- `backend/tests/test_hedge_cycle_close.py`
- `backend/tests/test_hedge_task_local.py`
- `backend/tests/test_hedge_review2_regressions.py`
- `backend/tests/test_live_hedge_executor.py`
- `backend/tests/test_hedge_executor.py`
- `backend/tests/test_book_ticker.py`
- `reports/agent-runs/**/status.json`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- 其他 stage 的任何文件与 `.venv/`

本 dispatch 未授予 `status.json` 写权限：不要把任务改为 `reported`。`agents/roles.md` 中 Implementer 的一般权限只是上限；本任务以本 Allowed Files 为准，回执返回后由 Bookkeeper 核验并记账。范围不足时返回 `blocked`，不得自行扩权。

# Inputs

严格按以下顺序读取；除这些输入与 Allowed Files 外不要扩展扫描：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/11-smooth-open-v1-fullstack-gpt56sol-xhigh.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 两节
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-final-plan-rereview-deepseek-v4-pro.handoff.md`
10. `docs/planning/smooth-open-orders-v1.md`
11. `docs/planning/smooth-open-orders-v1-development-checklist.md`
12. `docs/planning/ccxt-bookticker-recon-2026-08-13.md`
13. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md`
14. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md` §4
15. Allowed Files 中既有源码与测试；只读输入 `backend/domain/snapshot.py`、`backend/tests/test_hedge_purity.py`、`backend/tests/test_hedge_cycle_core.py`、`backend/tests/test_hedge_cycle_close.py`、`backend/tests/test_hedge_task_local.py`、`backend/tests/test_hedge_review2_regressions.py`、`backend/tests/test_live_hedge_executor.py`、`backend/tests/test_hedge_executor.py`、`backend/tests/test_book_ticker.py`

启动必须核对：cwd 是上述 worktree、分支是 `smooth/v1-fullstack`、stage/task/model/provider/status revision 与本 packet 一致、`status.json.base_sha` 等于 `e955bdd300d214c5c3ad5c1acd629c0d21080165`。任一不一致即停止并返回 `blocked`。

# Acceptance Checks

1. **CP1：依赖与公共盘口 provider**
   - `requirements.txt` 只有中文运行时说明注释和 `ccxt==4.5.64`；不得执行 `pip install` 或修改 `.venv`。
   - 实现定稿的 `MarketKey`、不可变 `BookTickerSnapshot`、同步 `BestBidAskProvider`；CCXT Pro 只在默认 source factory 函数体内惰性 import，未安装 ccxt 时模块仍可 import、fake source 测试全绿。
   - 一个专用 asyncio event-loop 线程管理 spot/swap watcher；两侧、不同 symbol、同 key 引用计数互不干扰。`latest`、generation、失效、重连、release、幂等 close/join 严格按清单 §4.1/§5。
   - 四价四量只从 `info.b/B/a/A` 原始字符串构造 `Decimal`；任一缺失、空、非数、零、负数均不得产生 live，normalized float 禁止进入。`contractSize != 1` 或未知均 fail-closed，且不得借此解除 1000x 拒绝。
   - provider 验收只用可脚本化 fake async source；禁止真实 WebSocket、HTTP 或任何网络连接。

2. **CP2：Gate domain/store**
   - `validate_slippage_threshold_pct`、`L1Quote`、`SmoothGateEval`、`evaluate_smooth_gate` 符合清单 §4.2.1；阈值支持负数和零、最多两位小数。方向开单率复用只读的 `compute_opening_spread_pct`，比较严格 `>`，两腿一档覆盖率各自 `>= 80%`。
   - 迁移只增加定稿列；`open_smooth_gate`、`force_smooth_gate`、`clear_smooth_gate`、`prepare_attempt` 在既有事务中原子复核。smooth 缺 `expected_gate_seq` fail-closed；成功 prepare 同事务记原因、递增一次、清 gate；immediate 行为不变。
   - 穷举处理清单 §4.2.3 四条状态写路径：前三条只在 UPDATE 命中时同事务清 gate；`_apply_task_counters` 保持不清并用不变量测试证明。`clear_smooth_gate` 只用于仍 running 而 Start gate 关闭。
   - R2 六组回归全部实现；未命中测试必须在隔离 DB 写入 `777 / 123456789 / 1` 三个非空 sentinel 并逐值保持，禁止用原本为 NULL 的空断言代替。

3. **CP3：Worker/API**
   - 每 task 使用独立 `threading.Condition + wake_version`，禁止忙循环、禁止复用 `_stop_events`；唤醒源恰好为 provider 变化、force 成功、pause/delete、Start gate 变化、`service.stop()`、deadline 到期。
   - 每个未调度 seq 打开完整 5 分钟 gate；市场严格通过、当前 gate manual force、deadline timeout 三种理由只能选一，并在 `prepare_attempt` 原子复核后进入既有立即开单两腿链。异步两腿提交、同步等返回、单腿、查单、结算全部复用既有路径。
   - smooth 的 `成交1次` 只持久化当前 `gate_seq` 放行并唤醒，绝不直接下单或增加计划次数；并发市场通过仍最多消费一次。seq 不符、无活动 gate、非 running、已达目标、有在途 pair 均 409 且不改 task。immediate fill-once 不变；smooth fill-all 返回 409。
   - 创建、任务读模型、动态盘口日志模型及 `server.py` 只为 fill-once 读可选 body 的契约符合清单 §4.3。生产组合根在 ccxt 缺失时注入 `None` 并中文告警；新建 smooth 返回 400，既存 smooth 仍可 timeout/manual；测试 fake provider 可完整驱动。
   - 系统 pause 后 Human resume 必须为同一未调度 seq 重开新的完整 5 分钟窗口。

4. **CP4：前端真实接线**
   - 平滑按钮解除冻结；右侧显示 signed 阈值输入和 `%`，默认 `0.05`。立即开单、开单/平单区域与任务卡既有字段、展开日志和错误原因不得丢失或重排成已知错误布局。
   - smooth 任务卡展示阈值、连接状态、两侧一档价量、正向/反向开单率、覆盖率与等待原因；`status != live` 的价量显示 `—`，不得把保留快照冒充当前盘口。
   - 动态盘口复用 `EXECUTION_POLL_MS = 2000` 的现有展开日志读链，不新增 timer。`成交1次` 先取当前 `smooth_gate_seq` 再 POST，无活动 seq 或非 running 时禁用；smooth 不显示 fill-all。

5. **固定回归与边界证明**
   - 每个 checkpoint 先跑清单 §3.4 对应测试；红灯不得前进，不得修改禁止测试或用 skip/`-k`/放宽断言绕过。
   - 在未安装 ccxt 的现有开发虚拟环境依次运行，均须退出码 0：

```bash
.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py \
    backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
    backend/tests/test_smooth_api.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
    backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
    backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_close.py \
    backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
    backend/tests/test_hedge_leverage.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

   - 额外运行：`.venv/bin/python -m pytest backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q`。
   - `git diff --stat e955bdd300d214c5c3ad5c1acd629c0d21080165..HEAD` 的实现文件必须是 Allowed Files 子集，禁止文件零 diff；不得记录凭证、token、cookie、私钥、完整鉴权环境、真实账户或订单数据。

6. **交付与 handoff**
   - 全部修改与测试完成后，按 Task Handoff Evidence Contract 在唯一路径写 source report；author 区 `base_sha` 写 `e955bdd300d214c5c3ad5c1acd629c0d21080165`，`delivery_sha` 写 `pending`。
   - Source Report 说明四个 checkpoint、实际文件、所有命令结果和未完成项；Required Reading 按顺序指向唯一 handoff 与本 dispatch，下一动作是 Bookkeeper 核验 source SHA、文件、提交、测试并固定 delivery SHA，下一关卡为 Review-1。Human Brief 必须与控制台唯一 `[TASK_RESULT v2]` 完全一致。
   - 只提交 Allowed Files 与 handoff，形成一个新增本地 delivery commit。不得 amend 控制提交，不 push、不 merge。

# Stop

遇到身份/基线不一致、handoff 已存在、必须修改禁止文件、无法在未安装 ccxt 且零网络条件下完成、或发现会改变立即开单资金语义的冲突，立即停止并写 `blocked` handoff；不要猜测或扩权。

完成实现、自测、handoff 和唯一 delivery commit 后，输出 Human Brief 中的 `[TASK_RESULT v2]` 并停止。`下一步模型` 写 `Bookkeeper（codex）`；`下一步任务` 写为：读取唯一 handoff；执行核验 source SHA-256、允许文件、提交与全部测试并固定 `base_sha..delivery_sha`；关卡为通过后准备跨 provider Review-1。不得自行启动 Reviewer、安装依赖、联网、控制服务、下单、push、merge、部署或修改状态文件。
