# Task Handoff: review-1-backend-cache-refresh-v1-deepseek

## Source Report (author-only; immutable after task end)

- task_id: `review-1-backend-cache-refresh-v1-deepseek`
- role: `Reviewer`（Review-1）
- target model: `deepseek`（provider `deepseek`；实现作者 `claude_glm`/`zhipu_glm`，provider 隔离满足）
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 19:18:47 CST`
- base_sha: `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7`
- delivery_sha: `8b624f733362e3a523d7f06613534af4f2451ad2`（Bookkeeper 已解析的固定评审 SHA）

### 评审范围与方式

只读审查固定区间 `6f1901ee..8b624f73`。区间内含 stage intake 控制提交 `1ab6bfe`（PROJECT_STATE.md、v4 设计、dispatch、ACTIVE.json、status.json 的 stage 启动改动），按 AGENTS.md §8 评审范围口径作为上下文而非受审交付；受审交付为 delivery commit `8b624f7` 触及的 14 个文件（代码、契约、schema、测试、handoff、status 的 `dispatched→reported`、两份 pytest 证据）。逐项对照 v4 设计 §3–§7 与 dispatch 8 条 Acceptance Checks。全程未改任何文件；仅复跑安全离线 pytest（新增测试 41 例）并核对 Bookkeeper 记录的 340/1256 证据。

### 评审结论

**评审结论: ACCEPT**

8 条 Acceptance Checks 的实现事实全部成立，测试真实有效（独立 stub + 真实 `PrivateClient`/`HedgeOpenStore` + schema 校验，非同构复述）。无阻塞性缺陷；全部发现为 in-range 非阻塞观察或程序性/风格项；无 pre-existing 发现。详细核验与发现如下。

### 逐项核验（对照 dispatch Acceptance Checks）

1. **唯一 refresh cycle（AC1）— pass**。`_scheduled_tick()` 主体收敛为唯一 worker-only `_run_refresh_cycle(*, force_account_panels)`；scheduled 走 `force=False`，POST 与状态钩子走 `force=True`。force 仅放松账户面板组（price_map/unified/um/spot/pm）的 due 检查，其余 source（premium、group_b、book_ticker、restricted、classic_reference、account_info）与全部 Group C 保留既有 due。compose→eligible→Group C→assemble→validate→publish 全复用。`_assemble` 是唯一发布 chokepoint（offline build `:485`、cycle `:1152`、click `:1768` 三调用点全经过），`source_checked_at` 在其中拷贝附加，不污染 click 路径复用的已发布 dict。无双 cache/双 worker/双 assemble。
2. **force 精确 transport 绕过（AC2 前半）— pass**。四个私有 fetcher 加 `force=False` 关键字；`force=True` 仅 `_evict` 精确 key，且逐条核对 `_evict` 与 `_cached_get` 的 key 构造完全一致（`(method, path, tuple(sorted(params.items())))`）：unified `/papi/v1/balance`、um `/papi/v1/um/positionRisk`、pm `/papi/v1/account`、spot `/api/v3/account`+`{"omitZeroBalances":"true"}`。`_cache.clear()` 从未使用；multi-asset scheduled key 不受影响（真 `PrivateClient` 单测 `test_force_only_evicts_exact_private_transport_key` 验证）。`price_map` 为公开源无 transport 缓存（`fetch_ticker_price_map` 每次真实 GET），force 下无条件读取，与设计 §3.3 一致。
3. **RefreshResult 分离（AC3）— pass**。`published` 与 `complete|partial|not_attempted` 完全分离；`complete` 需要 price_map+unified+um+spot 全成功且 capability 存在时 pm 也成功；全失败、UM 单源失败、price_map 失败、private disabled、base_raw 冷启动均不得称账户完整更新（6 个分类测试覆盖）。`base_raw is None` 冷启动返回 `published=False, not_attempted`。
4. **source_checked_at 契约（AC4）— pass**。worker-only `self._source_checked_at` 固定五 key；仅在成功写入 `_global_source_cache` 时推进为 UTC ISO-8601；失败保留 last-good 值与旧时间；PM capability 缺失时 `pm_account` 保持 null；`_assemble` 发布时拷贝附加 view，已发布 dict 不被原地修改。`checked_at`/`valuation.priced_at` 聚合语义未动（`_account_checked_at` 推进逻辑保留）。
5. **schema/契约/positions meta（AC5）— pass**。schema 将 `source_checked_at` 列为 `private_account` required，对象 fixed 五 key、`additionalProperties:false`、各值 `date-time|null`；`$id`/`schema_version` 未变（additive）。`_validate` 用更新后的 `_load_schema()`，发布路径强制五 key（缺/多 key 校验失败测试 3 例）。契约 v0.10 修订节与 schema 同次更新，语义、POST 行为、合并窗口、GET 纯读均如实记录。`GET /hedge-open-positions` 在 merge 后把完整对象附到 account meta，snapshot 缺失时输出全 null 五 key（2 测试覆盖）；`merge_positions` 未改。
6. **POST/GET（AC6）— pass**。`POST /api/public-market/cache-refresh` 只入队或复用 `RefreshCacheCommand` 并有界等待（独立 `cache_refresh_timeout_seconds=20s`，与 symbol click timeout 解耦）；无 worker→503 `cache_refresh_unavailable`（`_worker_running()` 检查，offline/杀开关关时不启动 worker）；超时→202 queued；完成→200 `{published, account_panels}`；handler 零上游 I/O、不直接写 cache，body 排空。GET `/snapshot` 零上游有测试（publish 后清计数器再读）。该 POST 无鉴权与既有 public-market GET 一致，服务默认绑定 `127.0.0.1`，副作用仅为本地入队，是既有暴露面的一致延伸，非新风险类别（设计 §5.1 明示）。
7. **状态钩子（AC7）— pass**。store 六个 public mutator 在事务内捕获 old status（`set_task_status`/`stop_task_fatal`/`pause_task` 为锁内 SELECT prev；`_apply_task_counters` 为事务内 task 快照），提交后经 `_attach_status_transition` 附加 `(old,new)`，返回形状保留。`_status_transition` 是私有 key：`task_to_doc` 固定字段集不投影，不外泄 API。service `_notify_cache_refresh` 仅 `old==running && new!=running` 调用注入的 `submit_cache_refresh(wait=False)`，cb 异常被吞、已提交状态不回滚；条件写未命中（rowcount==0 → None/(None,False)）与同状态/恢复 running 零触发。调用点覆盖 set_task_status（post_pause/post_delete）、pause_task（`_pause_task_local`）、stop_task_fatal、resolve_attempt（dispatch 两处+失败路径）、finalize_attempt（reconcile/crash-gap 两处）；settle_attempt_no_counters 走 skip_counters 零触发且不携带 transition（返回 bool）。
8. **离线测试（AC8）— pass**。新增 41 例覆盖全部关键 seam（evict 精确性、force 绕过、分类、source 时间推进/保留、schema 拒绝、positions meta、POST 五态、store transition 六场景、hook 触发/零触发/吞异常/未配置）；Bookkeeper 证据 340/1256 passed 与 handoff 一致；本次复跑 `test_account_cache_refresh_v1.py` → 41 passed in 10.83s。无真实 key/网络/服务。

### 发现（三分类，全部非阻塞）

- **发现 A（in-range，非阻塞，建议最小修复）**：`_release_cache_inflight` 无条件删除 inflight 中的 cache command，未按实例身份检查；对比 symbol 版 `_release_inflight` 的 `if self._inflight.get(cmd.symbol) is cmd`。极端窗口：worker 在 `_handle_cache_refresh_command` 的 `finally` 中先 `done.set()` 后 `_release_cache_inflight()`，若 POST 线程恰在这两条指令之间再次 `submit_cache_refresh()`，会创建新命令并替换 inflight 条目，随后 worker 的 release 会删除**新命令**的条目——第三次 submit 不再复用，多入队一次串行全 cycle 刷新。影响与设计 §4.2 显式接受的"罕见重复读取"同质：FIFO 串行无并发、无数据错误、无资金/订单影响；可达窗口为微秒级（人类按钮点击间隔远大于它；状态钩子不消费结果无感知）。修复建议：`_release_cache_inflight` 改为 `if self._inflight.get(_CACHE_INFLIGHT_KEY) is cmd: del ...`，与 symbol 版保持一致。
- **观察 1（in-range，非阻塞）**：`pytest-full.txt`/`pytest-subset.txt` 不在 dispatch Allowed Files 列表，但 Acceptance Check 8 要求"运行并保存"pytest 结果且文件位于 stage evidence 目录。属 dispatch 文本内部张力（验收要求 vs 文件列表），证据文件无风险、是验收所需。建议 Bookkeeper 在后续 dispatch 显式列出证据输出路径。
- **观察 2（in-range，非阻塞）**：`test_post_cache_refresh_503_when_worker_not_running` 首行断言自引用（`h.calls[0] == ("json", 503, h.calls[0][2])`），为弱断言；紧接的下行断言 `error == "cache_refresh_unavailable"` 补足有效性。
- **观察 3（in-range，非阻塞，小覆盖缺口）**：AC7 的 `finalize_attempt` 无 store 层 transition 直接测试；service 层 `_dispatch_*`/`_reconcile_own_legs`/`_recover_crash_gaps` 的钩子接线无直接测试（共享 `_apply_task_counters` helper 已由 resolve_attempt 测试覆盖；接线为各 2 行调用）。风险低。
- **观察 4（非功能）**：`docs/api/public-market-contract.md:1246` EOF 多余空行（`git diff --check` 报告），不影响代码行为、契约语义或验收事实。

无 pre-existing 发现；无资金/订单/凭证/部署边界被触碰；实现未越界到前端、订单、借贷或风险限制。

### 未完成事项

无阻塞。Review-2（reality check）与 merge/部署/实盘操作不在本任务授权内；由 Bookkeeper 推进路由。

### 命令与结果（离线，无真实 key/网络/服务）

- 复跑新增测试：`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/test_account_cache_refresh_v1.py` → `41 passed in 10.83s`。
- 核验证据一致性：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.pytest-subset.txt`（340 passed）/ `backend-cache-refresh-v1.pytest-full.txt`（1256 passed）与 handoff 声明一致。
- 范围核验：`git diff --stat 1ab6bfe..8b624f7` 仅 14 文件（全部在 Allowed Files 内，另见观察 1）；`git diff --check` 仅契约 EOF 空行（观察 4）。

### 仓库内证据路径

- 受审 diff：`6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2`
- 核心实现：`backend/services/snapshot_service.py`、`backend/services/private_client.py`、`backend/domain/snapshot.py`、`backend/app/server.py`、`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、`backend/config.py`
- 契约/schema：`schemas/api/public-market/snapshot.schema.json`、`docs/api/public-market-contract.md`
- 测试：`backend/tests/test_account_cache_refresh_v1.py`
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md`（本件，review-1 结论与发现）
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  4. `docs/planning/hedge-status-account-refresh-v4.md`
- 执行：Bookkeeper 核验本 review-1 handoff（`delivery_sha` 引用、发现分类、ACCEPT 闭包字段），并决定是否按 §8 派发跨 provider review-2（实现作者为 zhipu_glm，review-2 须不同 provider）。
- 关卡：review-2 ACCEPT 后由 Human 决定合并/部署/实盘授权；本阶段不授权部署或实盘操作。
- 不能假设的事实：本评审未做实盘/网络/凭证/部署；前端未接入；F4 未修（按设计保留）；发现 A 与观察 1–4 为非阻塞，不消耗 rework_count。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: review-1-backend-cache-refresh-v1-deepseek
执行结果: completed（完成）
结果摘要: Review-1 只读审查固定 diff 6f1901ee..8b624f73：8 条验收全部成立，唯一 refresh cycle、force 精确 evict、RefreshResult 分离、source_checked_at 契约、POST 纯入队、状态钩子、schema/测试均核验通过；复跑新增测试 41 passed。评审结论 ACCEPT，4 项 in-range 非阻塞观察（含 1 个建议一行修复的竞态一致性项），无 pre-existing 发现。
产物: [reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md]
检查结果: [pass 唯一 worker refresh cycle 与 _assemble 单一 chokepoint，无双 cache/双 worker/双 assemble, pass force 仅绕账户面板 due 与四个 private 精确 evict key（_evict/_cached_get key 构造一致，multi-asset key 不受影响，无 _cache.clear）, pass RefreshResult 分离 published 与 complete/partial/not_attempted，全失败/单源失败/disabled/冷启动均不得称完整, pass source_checked_at 固定五 key、worker-only、成功才推进、失败保留旧值旧时间、PM 缺失 null、发布时拷贝附加, pass schema required+additionalProperties:false 与契约 v0.10 同步；positions account meta 透传/全 null fallback, pass POST 503/200/202 全覆盖、GET 零上游 I/O；store 提交后真实 transition、钩子仅 running→非running 且吞异常不回滚, pass 离线测试 41+340+1256 通过（本次复跑 41 passed），无真实 key/网络/服务, pass 无越界到订单/借贷/凭证/部署/前端；无 pre-existing 发现]
阻塞项: [none]
本地北京时间: 2026-08-03 19:18:47 CST
下一步模型: codex（Bookkeeper，只读核验本 review-1 结果）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/review-1-backend-cache-refresh-v1-deepseek.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、docs/planning/hedge-status-account-refresh-v4.md；执行：Bookkeeper 核验本 review-1 handoff 的 delivery_sha 引用与 ACCEPT 闭包，按 §8 派发跨 provider review-2；关卡：review-2 ACCEPT 后由 Human 决定合并/部署/实盘授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-03 19:25:52 CST`
- source_sha256: `7b343b6fb3dc5b0fcc1d65b00d44969e478f319c0e035c9257ceb3d0a58e29cb`（首个完整 `BOOKKEEPER_APPEND_ONLY` marker 之前的原始 bytes）
- status_revision_checked: `3`；task/state: `review-1-backend-cache-refresh-v1-deepseek` / `dispatched`
- SHA and isolation: handoff 的 `base_sha=6f1901ee7eb552102645f41f1e124fd7cf6e3ff7`、`delivery_sha=8b624f733362e3a523d7f06613534af4f2451ad2` 与 stage status 一致；reviewer provider `deepseek` 不同于 implementation provider `zhipu_glm`。
- closure: Source Report 与 Human Brief 都含清晰 `评审结论: ACCEPT`，无 REWORK；四项 in-range 非阻塞观察和文档 EOF 空行均附事实、影响与不阻塞理由，无 pre-existing 结论或未分类阻塞项。
- evidence: reviewer 独立复跑新增离线测试 `41 passed in 10.83s`；先前 Bookkeeper 的 41/340 复跑记录及实现者 1256 原始输出均可读。任务包“保存 pytest 证据”与 Allowed Files 未逐项列出证据文件的文本张力已由 reviewer 记录；证据本身是验收所需、未增加产品行为，作为后续 packet 改进观察而非本交付返工。
- next state: Review-1 verified；Bookkeeper 派发 Review-2，固定审查范围保持 `6f1901ee7eb552102645f41f1e124fd7cf6e3ff7..8b624f733362e3a523d7f06613534af4f2451ad2`。

## Errata (append-only)

（预留）
