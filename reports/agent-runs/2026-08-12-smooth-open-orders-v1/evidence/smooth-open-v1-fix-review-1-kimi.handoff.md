# Task Handoff: smooth-open-v1-fix-review-1-kimi

## Source Report (author-only; immutable after task end)

- task_id: `smooth-open-v1-fix-review-1-kimi`
- role: `Reviewer`
- target model: `kimi` / provider `moonshot`
- stage_id: `2026-08-12-smooth-open-orders-v1`
- created_at: `2026-08-13 13:15:41 CST`
- base_sha: `9c333cdb58f38f7d19fa8d42b36379abd07baba8`
- delivery_sha: `dfd38a6b71e686caf02475aa7954056d670fcead`

### 审查方法

fresh 只读 Kimi 会话，跨 provider（作者 gpt-5.6-sol / openai，本复核 moonshot）。
按 dispatch 顺序读取 `AGENTS.md`、本 dispatch、`ACTIVE.json`、`PROJECT_STATE.md`、
`status.json`（revision `34` 与本 task_id 一致）、`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer 段）、
`agents/skills/code-reviewer.md`、实现 handoff `smooth-open-v1-fix-gpt56sol-xhigh.handoff.md`、
计划复核 handoff `smooth-open-v1-repair-plan-review-deepseek-v4-pro-r2.handoff.md`、
`docs/planning/smooth-open-orders-v1.md`（D8/D15/D16/§6.5/§16）与
`docs/planning/smooth-open-orders-v1-development-checklist.md`（§12）。

用 `git diff 9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead -- <path>`
逐个通读 12 个受审产品/测试文件 diff；需要理解接缝时用 `git show <固定 SHA>:<path>` 读取完整函数。
未移动 HEAD，未修改任何源码/测试/计划/状态/既有 evidence，未安装 ccxt，未联网，未读取凭证，未控制服务，未创建任务/下单。

### 逐项审查结论

1. **范围与回归边界**：产品 diff 严格落在 dispatch 列出的 12 个文件内；
   `backend/hedge_open_tasks/store.py`、executor、`live_hedge_executor.py`、
   `hedge_open_live_client.py`、`hedge_preflight_provider.py`、`snapshot.py`、
   `requirements.txt` 相对 base 零 diff。区间内的 dispatch/`status.json`/handoff 是控制上下文，
   不对其内容判阻塞。L1/L2/L3 未引入任何新锁、`stopping` 状态、store 复核、时钟改动或 capture selector 扩展。

2. **并发启动与订阅原子性**：`BestBidAskProvider.start()` 在 `_thread is None or not alive()` 时才新建线程，
   否则复用；所有调用者在线程创建后统一 `wait(_ready)` 同一个 event。`subscribe` 对新建 watcher 用
   `future.result(5)` 等待 `_start_watch` 完成，失败时 `pop` 掉 `_states` 中的条目并原样抛出，
   调用者看不到「已登记但无 watcher」的中间态。`_ensure_smooth_subscriptions` 先尝试两侧 `subscribe`，
   全部成功才写入 `_smooth_subscriptions`；单侧失败用 `release` 回滚已成功侧并抛出，下一次调用可重试。
   测试 `test_concurrent_cold_subscribers_wait_for_one_ready_watcher` 与
   `test_partial_subscription_failure_rolls_back_and_next_call_retries` 覆盖上述路径。

3. **失败循环与关闭**：`_watch` 的 `snapshot is None` 分支与 `except Exception` 分支均加入
   `await asyncio.sleep(_WATCH_RETRY_DELAY_SECONDS)`（`_WATCH_RETRY_DELAY_SECONDS = 0.05`），
   无指数退避/重试状态机/新配置；task cancellation/close 可立即打断 sleep。
   `test_failed_watch_retries_are_bounded_and_close_interrupts_wait` 断言 0.2 秒内 close 立即返回、
   watch 次数有界、线程已 join。

4. **offline 与 threshold 契约**：`backend/app/server.py::_build_hedge_service` 在 `config.offline` 为真时
   直接注入 `market_provider=None`，零构造/零线程/零订阅；非 offline + 无 ccxt 仍走原 400 路径不变。
   `validate_slippage_threshold_pct` 改用正则捕获后的字符串补位，不调用 `Decimal.quantize`，
   对任意长度合法整数保真，负零归一为 `0.00`；格式非法（超两位小数、科学记数、含 `%`、空值/非字符串）返回 400。
   测试覆盖 ±30 位/±100 位整数、`-0`、`.05` 的 API 201，以及非法格式的 400。

5. **D16 杠杆前移**：`_worker_round` 的 smooth 分支在 `_wait_for_smooth_gate` 之前调用
   `_set_leverage_before_open`；失败时 `PAUSE_REASON_LEVERAGE_SET_FAILED` 暂停并 `return False`，
   此时零订阅、零 gate、零 attempt、零订单。`_dispatch_one_for_task` 对 smooth 不再设置杠杆
   （条件增加 `and task.get("mode") != D.MODE_SMOOTH`）；immediate 与 close 原位置/条件不变。
   重启后可幂等重试（仍判 `scheduled_attempt_count == 0`）。

6. **D15 放行后零联网**：`_dispatch_one_for_task` 仅对 live immediate/close 调用
   `_resolve_fresh_preflight`；live smooth 走 `else` 分支，直接读取 task 固化的
   `q_common`/`position_side_mode`/`preflight_snapshot`。路由一致性检查对 smooth 自然恒真
   （frozen route = fresh route），未改变 immediate 语义。`prepare_attempt` 原子复核与
   `_dispatch_live` 两腿异步提交/查单/结算链原样复用。create-task 首次 preflight、
   regular_spot 预划转、缺腿/1000x 拒绝、immediate/close fresh preflight 均保留。
   `test_live_smooth_orders_leverage_gate_and_frozen_dispatch` 用 spy 断言
   `set_leverage → subscribe/open gate → market evaluation → prepare_attempt → dispatch`，
   且 market pass 后 `preflight.calls == 1`（仅 create-task）、`executor.leverage_calls == 1`。

7. **前端日志刷新**：`frontend/index.html` 两处日志刷新条件从 `task.status === 'running'`
   改为「任务仍存在」；收起或任务不存在才停止。未新增 timer，未触碰 L3 的 threshold capture selector。
   `frontend/self-check.js` 将原错误断言改为「非 running 且展开时仍应继续请求」。
   `test_frontend_field_binding.py` 覆盖真实调用条件（字符串断言 + 代码结构断言）。

8. **测试证据**：本复核在当前工作树独立复跑以下命令：
   - `.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py backend/tests/test_smooth_api.py backend/tests/test_hedge_domain.py backend/tests/test_frontend_field_binding.py backend/tests/test_service_health.py -q` → `250 passed`
   - `.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py backend/tests/test_hedge_cycle_core.py backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_leverage.py backend/tests/test_hedge_purity.py -q` → `352 passed`
   - `.venv/bin/python -m pytest backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_executor.py -q` → `75 passed`
   - `.venv/bin/python -m pytest backend/tests -q` → `1876 passed, 1 failed`
   - `node frontend/self-check.js` → `全部自检通过`
   - `.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q` → `13 passed`
   - `git diff --check` → 无输出
   - `.venv/bin/python -c 'import importlib.util; assert importlib.util.find_spec("ccxt") is None'` → 通过

   唯一失败仍为 `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients`，
   触发文件 `backend/services/public_ip_service.py`。该文件与 `backend/tests/test_private_client.py`
   相对 base 零 diff；`git log --oneline -- backend/services/public_ip_service.py | tail -1` 显示引入提交
   `73f525d4c3033cd4e8d7c7afb09a975816742913`，该提交是 base 的祖先
   （`git merge-base --is-ancestor 73f525d4c3033cd4e8d7c7afb09a975816742913 9c333cdb58f38f7d19fa8d42b36379abd07baba8` 返回 0）。
   按 `AGENTS.md` §8 分类为 `pre-existing-independent`，不阻塞本次交付。

9. **新假设场景**：未提出任何新的假设场景；所有结论均由固定树上的可执行证据或直接代码路径支持。

### 最终判定

固定范围 `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead` 内
无 `in-range` 阻塞发现；唯一测试失败为范围外 `pre-existing-independent`。返回 `ACCEPT`。

本 `ACCEPT` 不授权 Review-2、合并、安装依赖、联网、服务控制或实盘。

### 仓库内证据路径

- `backend/services/best_bid_ask_provider.py`
- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/service.py`
- `backend/app/server.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_best_bid_ask_provider.py`
- `backend/tests/test_smooth_gate_worker.py`
- `backend/tests/test_smooth_api.py`
- `backend/tests/test_hedge_domain.py`
- `backend/tests/test_frontend_field_binding.py`
- `backend/tests/test_service_health.py`
- `backend/tests/test_private_client.py`（范围外失败证据）
- `backend/services/public_ip_service.py`（范围外失败证据）

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md`；`reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
- 执行：Bookkeeper 核验本 handoff 的 source SHA-256、固定区间 `9c333cd..dfd38a6`、
  本 Review-1 的 `ACCEPT` verdict 与「无 in-range 发现」记录；核验通过后推进状态并准备
  跨 provider Review-2（默认 sonnet5 / anthropic）。
- 关卡：Bookkeeper 验证；通过后才可准备 Review-2，当前复核者不得自行启动 Review-2。
- 不能假设的事实：本 `ACCEPT` 只表示 Review-1 通过；合并、push、部署、实盘启用、服务控制、
  安装 ccxt、联网验证仍需 Human 逐项单独授权；`rework_count=3` 已达上限，若 Review-2 或
  Bookkeeper 提出 in-range 返工要求，须按 `AGENTS.md` §8 同根因刹车规则由 Human 决策。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-v1-fix-review-1-kimi
执行结果: completed（完成）
结果摘要: fresh Kimi 跨 provider Review-1 完成。固定 9c333cd..dfd38a6 逐项审查：范围边界、并发订阅原子性、失败循环与关闭、offline/threshold 契约、D16 杠杆前移、D15 零联网、前端日志刷新、测试证据均通过；唯一失败为 pre-existing-independent public_ip_service 白名单测试，不阻塞。返回 ACCEPT。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md]
检查结果: [pass：范围与回归边界，12 文件内 diff，禁止文件零 diff，L1/L2/L3 未改；pass：并发启动与订阅原子性，start/subscribe 同 ready 等待、单侧失败回滚；pass：失败循环与关闭，0.05s 固定等待可被 close 打断；pass：offline 零构造/零线程/零订阅，threshold 超长整数 201/非法格式 400；pass：D16 杠杆前移，失败零 gate/零订单，dispatch 对 smooth 不再设置；pass：D15 放行后零 fresh preflight，顺序型回归 spy 通过；pass：前端日志刷新非 running 仍继续、收起停止、无新 timer；pass：测试证据 250/352/75/1876+1/self-check/13 与 git diff --check 均复现]
阻塞项: [none]
本地北京时间: 2026-08-13 13:15:41 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md；执行：核验 source SHA-256、固定区间 9c333cd..dfd38a6 与 ACCEPT verdict；关卡：通过后准备跨 provider Review-2。
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md（范围外 pre-existing-independent 说明见 Source Report）
修复要求: none
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `78397b76570d1c62c72e8d82f0c5aff156c2a659c4f0bf007de1ddf90e415b92`
- verified_at: `2026-08-13 13:40:44 CST`
- status_revision_verified: `34`
- fixed_range: `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead`
- verdict: `verified-accept`
- identity_and_structure: task/stage/role/model/provider、固定 SHA、唯一 create-only handoff 与 source marker 均匹配 dispatch；摘要 202 字符、8 个不重复 `pass` 检查项、完整 `[TASK_RESULT v2]`、明确 `ACCEPT`、范围外问题记录与 `修复要求: none` 均合规。
- scope_and_findings: Reviewer 逐文件审查 12 个产品/测试文件，确认五项必修、D15/D16、L1/L2/L3 冻结边界及禁止文件零 diff；无 `in-range` 发现。唯一失败被分类为 `pre-existing-independent`：`public_ip_service.py` 与 `test_private_client.py` 相对 base 零 diff，提交 `73f525d4...` 是 base 祖先，与 Bookkeeper 独立复跑和先前裁定一致。
- tests: Kimi 独立复现专项 `250 passed`、核心 `352 passed`、executor `75 passed`、前端 self-check 全绿、字段绑定 `13 passed`、全后端 `1876 passed, 1 failed`（仅上述既存失败）与 `git diff --check` 无输出。
- decision: 接受 Review-1 verdict。下一步仅准备 fresh Sonnet 5（provider `anthropic`）Review-2，判断需求实际效果、运行风险与发布准备度；本 ACCEPT 不授权安装、联网、服务控制、合并或实盘。

## Errata (append-only)
