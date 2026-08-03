# Task Handoff: backend-cache-refresh-v1

## Source Report (author-only; immutable after task end)

- task_id: `backend-cache-refresh-v1`
- role: `Implementer`
- target model: `claude_glm` (provider `zhipu_glm`)
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 19:00:51 CST`
- base_sha: `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7`
- delivery_sha: `pending`（Implementer 在包含本件的唯一 delivery commit 之前创建；Bookkeeper 在 delivery commit 后用 `git rev-parse` 解析实际 SHA 写入 `status.json` 与同文件核验块，不回填本字段）

### 任务背景与实际修改范围

实现已批准设计 `docs/planning/hedge-status-account-refresh-v4.md` 的后端、HTTP 契约、schema、开单任务状态钩子与离线测试，不接入前端。三个触发者（约 60 秒 scheduled tick、人工缓存刷新 POST、开单任务真实 `running → 非 running`）复用同一条 worker-only refresh cycle；所有 Binance I/O 仍只在 worker 内。只改了 dispatch Allowed Files 列出的文件。

实际改动（均在 Allowed Files 内）：

- `backend/services/snapshot_service.py`：把 `_scheduled_tick()` 主体收敛为唯一 worker-only `_run_refresh_cycle(*, force_account_panels)`；新增 `RefreshResult`（`published` 与 `complete|partial|not_attempted` 分离）、`RefreshCacheCommand`（独立 `done`/`result`、固定 in-flight key `__cache_refresh__`）；`_refresh_due_sources(now, *, force_account_panels)` 返回 panel outcomes，force 时仅账户面板组（price_map/unified/um/spot/pm）bypass due 且对四个 private fetcher 传 `force=True`，其余 source/Group C 保留既有 due；新增 worker-only `self._source_checked_at`（固定 5 key，成功写 cache 才推进，失败保留旧值与旧时间）、`_source_checked_at_view()`、`_panel_result()`；`submit_cache_refresh()`/`_handle_cache_refresh_command()`/`_release_cache_inflight()`（入队或复用、异常隔离、worker 继续下一条）；`_worker_loop` 按 `isinstance` 分派 symbol/cache command 与 sentinel；`_assemble` 在单一 chokepoint 拷贝 private_account 并附加 `source_checked_at`（不污染已发布 dict）。scheduled `force=false` 保留 due/TTL；offline `_assemble` 附加全 null 五 key。
- `backend/services/private_client.py`：四个账户 fetcher（`fetch_unified_balances`/`fetch_um_positions`/`fetch_pm_account`/`fetch_spot_balances`）增加 `force=False`；`force=True` 仅 `_evict` 删除该 endpoint 的精确 transport-cache key，禁用 `_cache.clear()`。
- `backend/domain/snapshot.py`：`assemble_private_account` 增加 `source_checked_at` 参数（默认全 null 五 key），两个返回块均输出该固定形状，使直接调用也 schema-valid；service 在发布时用当前 view 覆盖。
- `backend/hedge_open_tasks/store.py`：`set_task_status`/`pause_task`/`stop_task_fatal` 在事务内 SELECT old status、提交后经 `_attach_status_transition` 把 `(old,new)` 附加在返回 task dict（保留原有 task/bool 返回形状，`task_to_doc` 不投影它故不泄漏 API）；`_apply_task_counters` 同样附加（覆盖 resolve_attempt/finalize_attempt；`settle_attempt_no_counters` 走 `skip_counters=True`，old==new 零触发且其返回 bool 不携带 transition）。
- `backend/hedge_open_tasks/service.py`：构造器注入 `cache_refresh_submitter`（默认 None）；新增 `configure_cache_refresh()` 与 `_notify_cache_refresh()`（仅真实 `running→非running` 调用、吞异常不回滚）；在 post_pause/post_delete（set_task_status）、`_pause_task_local`（pause_task）、`_stop_task_fatal_preflight`（stop_task_fatal）、`_dispatch_simulated` 与 `_dispatch_live` 两处（resolve_attempt）、`_reconcile_own_legs` 与 `_recover_crash_gaps`（finalize_attempt）调用点通知；settle 零触发不通知。
- `backend/app/server.py`：新增首个 public-market 写路由 `POST /api/public-market/cache-refresh` 与 `_handle_cache_refresh`（仅入队/复用并有界等待；无 worker→503；超时→202 queued；完成→200 `{published, account_panels}`，不执行上游 I/O）；`_hedge_open_positions` 在 `merge_positions` 后后置把完整 `source_checked_at` 附到 `account` meta（private_account 缺失时输出全 null 五 key，不改 `backend/hedge_open_tasks/domain.py`）；`run()` 用 `getattr` 把 snapshot worker 的 `submit_cache_refresh` 注入 hedge service（对桩鲁棒）。
- `schemas/api/public-market/snapshot.schema.json`：`private_account` 增加 required `source_checked_at`（固定 5 key，各 `date-time | null`，`additionalProperties:false`）。
- `docs/api/public-market-contract.md`：追加 v0.10 修订节（source_checked_at 语义、POST 路由、positions account meta、合并窗口与 GET 纯读不变）。
- `backend/tests/test_account_cache_refresh_v1.py`（新建）：覆盖 8 条 Acceptance Checks 的离线测试，41 个用例。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`：仅把 `current_task.state` 从 `dispatched` 改为 `reported`。

### 关键设计取舍（供核验）

- **唯一 refresh cycle**：`_run_refresh_cycle` 是 offline build/scheduled/click/force 共用的唯一后半段；force 仅新增账户面板 due 分支与四个 private `force=True`，compose/Group C/assemble/validate/publish 全部复用，无双缓存/双 worker/双 assemble。
- **source_checked_at vs 既有聚合**：新增 worker-only 五 key 只表示“源成功写入 cache 的时间”；`checked_at`/`valuation.priced_at` 既有聚合语义不变；`price_map` 计入完整性但不占账户标题。
- **force transport 绕过**：仅 `_evict` 精确 key（单测 `test_force_only_evicts_exact_private_transport_key` 验证 multi-asset scheduled key 与其他 endpoint key 不被清除），禁用 `_cache.clear()`。
- **合并窗口**：未完成 cache command 存在时，button 与状态钩子复用同一实例；事件落在“账户读取已结束、命令未结束”短窗口内只得到该 command 结果（如实训退回 ~60s tick），无 generation/tail/自排队。
- **状态钩子**：store 提交后返回 transition，service 仅对真实 `running→非running` 提交非等待命令；settle/同状态/恢复 running/条件写未命中为零触发；submitter 异常被吞，已提交任务状态不回滚。
- **未接入前端**：本任务不含前端改动；按钮/右上角/账户区域时间为前端任务。
- **F4 未修**：按设计本轮不修 F4（last-good 与冷启动区别保留）；`PROJECT_STATE.md` 的 F4 记录未改动。

### 未完成事项

无阻塞。本任务范围（后端/HTTP/schema/钩子/离线测试）已完成并自测。前端集成、review-1/review-2、merge、部署、实盘操作均不在本任务授权内，留给后续。

### 命令与结果（离线，无真实 key/网络/服务）

- 编译：`python3 -m py_compile` 覆盖全部改动后端文件 → `PY_COMPILE_OK`；schema JSON 解析 OK。
- 离线 pytest（dispatch 要求子集，含新增 + private client/account + snapshot + hedge API/service/store）：**340 passed**，证据 `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-subset.txt`。
- 完整后端回归套件：**1256 passed**（1215 既有 + 41 新增，零回归），证据 `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-full.txt`。

### 仓库内证据路径

- 新增测试：`backend/tests/test_account_cache_refresh_v1.py`
- pytest 子集结果：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-subset.txt`
- pytest 全量结果：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-full.txt`
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`（本件，author 源区块 + Human Brief）
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-cache-refresh-v1.dispatch.md`
  4. `docs/planning/hedge-status-account-refresh-v4.md`（已批准设计权威）
- 执行：Bookkeeper 核验本任务（`base_sha`/`delivery_sha`、status revision、handoff 同文件 SHA-256 边界、引用证据路径与可复现命令），并按 Acceptance Checks 复跑离线 pytest。
- 关卡：Bookkeeper 通过则把 `current_task.state` 推进为 `verified` 并解析 `delivery_sha`；未通过则在同文件追加拒收 `Bookkeeper Verification` 块、`status.json.blockers` 写具名条目，后续修复任务递增 `rework_count`。
- 不能假设的事实：本任务未做实盘/网络/凭证/部署；前端未接入；F4 未修（按设计保留）；`delivery_sha` 在本件为 `pending`，由 Bookkeeper 在 delivery commit 后解析。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: backend-cache-refresh-v1
执行结果: completed（完成）
结果摘要: 实现缓存刷新后端：唯一 worker refresh cycle、RefreshCacheCommand/RefreshResult、source_checked_at 五 key、POST /api/public-market/cache-refresh、开单 running→非running 钩子、schema/contract 同步、离线测试 41 例。1256 全过零回归。
产物: [backend/services/snapshot_service.py, backend/services/private_client.py, backend/domain/snapshot.py, backend/hedge_open_tasks/store.py, backend/hedge_open_tasks/service.py, backend/app/server.py, backend/config.py, schemas/api/public-market/snapshot.schema.json, docs/api/public-market-contract.md, backend/tests/test_account_cache_refresh_v1.py, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-subset.txt, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-full.txt]
检查结果: [pass 三触发者共用唯一 _run_refresh_cycle，force 仅绕账户面板 due 与四个 private 精确 key（单测验证 evict 不误伤）, pass RefreshCacheCommand 独立 done/result + 固定 in-flight key；worker 按 isinstance 分派；cache 命令异常不杀 worker；无 worker 时 POST 立即 503, pass RefreshResult 分离 published 与 complete/partial/not_attempted；全失败/UM 失败/price_map 失败/disabled 均不得称账户完整更新, pass source_checked_at 固定 5 key、成功才推进、失败保留旧值旧时间、PM 缺失为 null；checked_at 聚合语义不变, pass snapshot 与 /hedge-open-positions account meta 同步字段；schema required 且拒绝缺 key/多 key；GET 纯读, pass POST 成功/partial/not_attempted/失败/202 queued 覆盖；GET /snapshot 与 /hedge-open-positions 零上游 I/O, pass store 提交后真实 old/new；service 仅真 running→非running 提交非等待命令，settle/同状态/恢复 running 零触发且异常不回滚, pass 离线 pytest 子集 340 与全量 1256 通过，无真实 key/网络/服务]
阻塞项: [none]
本地北京时间: 2026-08-03 19:00:51 CST
下一步模型: codex（Bookkeeper，只读核验本任务）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/backend-cache-refresh-v1.dispatch.md、docs/planning/hedge-status-account-refresh-v4.md；执行：Bookkeeper 核验 base_sha/delivery_sha、同文件 handoff SHA-256 边界、引用证据与可复现离线 pytest（子集 340 / 全量 1256），并把本任务推进为 verified 或拒收；关卡：Codex 核验通过后由 Human 决定是否进入跨 provider review-1（claude_glm 实现的 review-1 须用不同 provider，默认 Kimi）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。

## Errata (append-only)
