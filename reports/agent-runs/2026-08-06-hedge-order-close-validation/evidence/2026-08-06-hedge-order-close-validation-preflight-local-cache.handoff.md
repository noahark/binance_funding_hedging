# Task Handoff: 2026-08-06-hedge-order-close-validation-preflight-local-cache

## Source Report (author-only; immutable after task end)

- task_id: `2026-08-06-hedge-order-close-validation-preflight-local-cache`
- role: `Implementer`（target_model: deepseek）
- stage_id: `2026-08-06-hedge-order-close-validation`
- created_at: `2026-08-06 20:23 CST`
- base_sha: `ee7ec4f`（`git rev-parse ee7ec4f` = `ee7ec4f3a41db8d896652101fcd1821972b381bc`）
- delivery_sha: `pending`（本任务未获提交授权，改动保留在工作树，由 Bookkeeper 处理交付提交）

### 背景

THE 事件问题 C（任务静默停摆 33 分钟）实证：`fapi exchangeInfo`（1.06MB）抖动
3.7~15.7s 击穿 `DEFAULT_TIMEOUT_SECONDS=10.0` → preflight incomplete → `service.py:1450`
worker 静默退出（任务仍 running、卡片零提示）。建卡路径 `fapi exchangeInfo` 被拉两次
（`check_symbol_legs` + `get_snapshot`）。SnapshotService 本地缓存已有 preflight 所需
绝大部分数据（私有源 60s TTL、exchangeInfo 1800s）。Human 三项决定 + 前端徽标醒目化
并入本任务（dispatch Goal 1-5）。

### 实际修改范围

**§1 只读注入 seam（两服务保持解耦）**

- `backend/services/snapshot_service.py`：新增只读 `get_cached_source(source_id) ->
  (monotonic_ts, value) | None`（复用 `_global_source_cache`，绝不触发刷新）。diff
  仅此一个方法。
- `backend/services/hedge_preflight_provider.py`：构造函数新增
  `snapshot_reader: Optional[Callable[[str], Optional[tuple]]] = None`（默认 None 时
  行为逐字不变——既有 provider 测试零修改通过）；新增后置注入
  `set_snapshot_reader`。
- `backend/app/server.py`：与 `configure_cache_refresh` 同处注入——
  `hedge_open_service.configure_snapshot_reader(...)` +
  `configure_preflight_reader(...)`（绑定 `SnapshotService.get_cached_source`）。
- `backend/hedge_open_tasks/service.py`：新增 `configure_snapshot_reader` /
  `configure_preflight_reader`（转发给 provider 的 setter）。全程无
  `import SnapshotService`（结构测试断言）。

**§2 缓存映射 + 陈旧上限**（provider，先查缓存 → 新鲜命中则用 → 否则降级实时 + stderr 留痕）

| 方法 | source_id | 陈旧上限 | 行为 |
|---|---|---|---|
| `_read_perp_filters` | `group_b_public.futures_exchange_info` | 2h | 降级实时 |
| `_read_spot_record` | `group_b_public.spot_exchange_info` | 2h | 降级实时 |
| `_read_est_price` | `price_map` | 5min | 降级实时 |
| `_read_balances` | `unified_balances`（`crossMarginFree`） | 5min | 降级实时 |
| `_read_spot_account_usdt` | `spot_balances`（`free` 取 USDT） | 5min | 降级实时 |
| `_read_collateral_cap_hit` | `restricted_asset`（按 value 自带 `checked_at` 判陈旧） | 10min | **fail-closed（返回 None，不降级、不猜）** |
| `check_symbol_legs` | `group_b_public`（两个 exchangeInfo） | 2h | 降级实时 |

- 缓存命中且 symbol 不存在 → 确定性 absent（与实时 2xx 一致）；缓存结构不符 →
  降级 + `_degrade_note`（stderr）。
- `restricted_asset` 是唯一 fail-closed 项：无 reader 时行为逐字不变（`_read_collateral_cap_hit_live`
  实时读）；有 reader 但缓存缺失/超龄/结构不符 → `None` + fail-closed（不猜路由）。
- 建卡重复读消除：`check_symbol_legs` 与 `get_snapshot` 命中同一份 `group_b_public`。

**§3 账户级配置 TTL**（provider 进程内缓存 600s，只缓存成功值，失败不缓存）：
`_read_position_mode` / `_read_rate_limit_order` / `_read_spot_rate_limit_order`。

**§4 平仓简化**（service.py）

- §4.1 平完判定收敛：`_worker_round` 中 close 任务**不再每轮**调
  `_verify_close_flat`；只在 `scheduled_attempt_count >= target_n`（次数用完、准备
  收尾）时调用**恰好一次**（仍实时，禁止读缓存——它决定「关周期 + 写结算日志」不可逆
  动作）。三分支语义不变：flat → `_finalize_close_task`；open → 部分平完成（done、
  周期不关、`close_partial_done` 日志）；failed → `PAUSE_REASON_CLOSE_VERIFY_FAILED`
  暂停（fail-closed）。
- §4.2 划转改造（`_ensure_close_spot_balance`）：删除后置复检（`recheck = q_spot(...)`
  及其两分支）——只认划转返回结果（缺 `tranId` 内部抛错 → 既有异常 → 暂停路径）；
  划转成功后 `time.sleep(0.1)` 让余额同步；缓存放行/实时确认才动手——新鲜
  `spot_balances` 缓存显示充足 → 直接放行（0 请求），不足/未知 → 实时确认 → 仍不足才
  `universal_transfer`；`unified_balances` 缓存（可划转量）为放行类。划转 ok 事件点
  记录进程内 `_close_transfer_done[task_id] = (amount, asset)`，forward close 余额
  不足暂停文案追加「本轮已完成划转 <数量> <资产>，若仍报余额不足，可能是划转尚未
  到账，请稍后手动恢复重试」（`_close_insufficient_pause_zh`）。

**§5 预检失败可见暂停**（Human 决定 4）

- worker 层 `SIGNAL_PREFLIGHT_INCOMPLETE` 分支由 `_worker_exit` 改为
  `_pause_preflight_incomplete`：任务置 `paused` + `PAUSE_REASON_PREFLIGHT_INCOMPLETE`
  + 中文原因**含失败读名** + `kind="preflight_incomplete"` 事件 + `return False`
  （worker 退出本轮，**无重试**，与 SIGNAL_TASK_LOCAL_PAUSE 分支一致）。
- `_record_preflight_incomplete` payload 增加 `failed_read` 字段（问题 C 第二个取证
  盲区修复）；`get_snapshot` 在 provider 侧记录第一个失败读名
  （`self.last_failed_read`，二选一方案中的 provider 侧记录，未改
  `PreflightSnapshot` 冻结形状）。
- 措辞统一：`_dispatch_one_for_task` / `_resolve_fresh_preflight` / `_FreshPreflight`
  docstring、`_ENTRY_EVENT_KINDS` 注释、domain.py 常量注释中「fail-closed retry」
  全部改为 exit/pause（验收 8：Allowed Files 内无残留 retry 表述）。
- 不变：fail-closed 语义、`SIGNAL_PREFLIGHT_FATAL` 停机路径、不引入重试。

**Goal 5 前端执行模式徽标醒目化**（frontend/index.html）

- `renderHedgeExecutionStatus`：dry-run/disabled 模式徽标加 `.warn` 警示色（live
  不变）；文本仍含 `dry-run`/`live`（既有 self-check 断言不破坏）。
- 任务卡「成交1次」/「立即成交所有」按钮：dry-run 模式标注「（演习）」。
- `loadHedgeSettings` 成功后重渲染任务卡（按钮标注依赖 executor_mode）。数据源仍为
  进程实时 `self._mode`（service.py:856），未新增提示通道、未改数据源。

### 测试变动说明（dispatch 要求逐条说明）

**新增（验收 1-7 证据，16 个测试函数）**：

- `test_hedge_preflight_provider.py`（+9）：
  `test_get_snapshot_cache_hit_zero_network_after_account_warmup`（全缓存命中 →
  public/client 调用均为 0）、`test_check_symbol_legs_cache_hit_zero_network`、
  `test_check_symbol_legs_cache_absent_coin_confirmed_false`、
  `test_stale_cache_degrades_to_realtime`（陈旧 → 实时读 spy）、
  `test_restricted_asset_stale_fails_closed_no_realtime`（超龄 → None 且不降级实时）、
  `test_restricted_asset_missing_fails_closed`、`test_account_config_ttl_read_once_per_600s_and_failure_not_cached`、
  `test_last_failed_read_names_first_failure`。
- `test_hedge_task_local.py`（+2）：`test_preflight_incomplete_pause_names_failed_read`
  （paused + 中文原因含 "balances" + 事件带 failed_read + 无重试）、
  `test_close_flat_verify_only_at_target_reached`（spy：verify 恰好 1 次；普通轮 0 次；
  周期关 + close_log 写）。
- `test_hedge_cycle_close.py`（+5）：缓存放行（0 查询 0 划转）、缓存不足→实时确认→
  才划转、unified 缓存放行、`sleep(0.1)` 且无复检（monkeypatch spy）、
  `_close_insufficient_pause_zh` 含「可能是划转尚未到账」。
- `test_account_cache_refresh_v1.py`（+1）：`test_get_cached_source_readonly_returns_entry_without_refresh`
  （只读、零刷新副作用）。dispatch 清单列 `test_snapshot_service.py`，实际仓内文件为
  `test_snapshot.py`（纯 domain 快照构建）与 `test_account_cache_refresh_v1.py`
  （SnapshotService 实例），get_cached_source 测试放在后者（兜底授权「为新增行为所
  必需的其他测试文件」）。
- `test_hedge_preflight_provider.py::test_preflight_provider_accepts_no_display_cache_input`
  改写：原断言「构造函数无 cache 参数」已被本任务有意改变；改为断言唯一新参数是
  `snapshot_reader`（默认 None）+ 无 `import snapshot_service`（解耦结构证明）。

**适配（行为变更的直接后果，3 个既有测试）**：

1. `test_hedge_task_local.py::test_r7_live_worker_active_tri_state_and_exit_reason`：
   sub A 断言从 `WORKER_EXIT_PREFLIGHT_INCOMPLETE` + `RUNNING`（静默）改为
   `PAUSED` + `PAUSE_REASON_PREFLIGHT_INCOMPLETE`（§5 可见暂停）。
2. `test_hedge_review2_regressions.py::test_3a_missing_preflight_fact_is_fail_closed`：
   同上一行为变更，断言改为 `PAUSED` + 正确 pause_reason（仍零 attempt / 零 POST /
   零失败计数）。
3. `test_hedge_cycle_close.py::test_ensure_close_spot_balance_recheck_insufficient`
   → `test_ensure_close_spot_balance_no_recheck_after_transfer`：后置复检已按 Human
   决定 3 删除，断言改为「划转成功即放行、余额只查一次」。
   `_CloseSpotExecutor.query_spot_free` 的复检模拟分支移除（§4.2 无复检）。

### 命令与结果

- `.venv/bin/python3 -m pytest backend/tests -q` → **1462 passed**（任务 03 基线 1446
  + 本任务净增 16；含全部新增与适配测试）。
- `node frontend/self-check.js` → 全部自检通过（含既有执行徽标断言）。
- 性能证据（验收 9，模拟每请求 50ms、无真实网络）：
  - 开单 `get_snapshot`：无缓存（实时 7 请求）**376ms** → 缓存命中 **0ms / 0 请求**。
  - 建卡 `check_symbol_legs`：无缓存 **109ms** 且 `fapi exchangeInfo` 读取 **2 次**
    （重复读实证）→ 缓存命中 **0ms / 0 次**（消除）。
- 解耦检查：`grep import.*SnapshotService backend/hedge_open_tasks/ backend/services/hedge_preflight_provider.py`
  → 仅 docstring 提及，无真实 import。
- `git status --short`：改动均在 Allowed Files 内；`snapshot_service.py` diff 仅新增
  `get_cached_source`；`.reasonix/` 与 `macos_input_outage_playbook.md` 为宿主/其他
  会话产物，非本任务文件。

### 未完成事项 / 不能假设的事实

- 本任务未提交（无提交授权）；工作树含 01/02/03 已交付（ee7ec4f）之上的本任务改动。
- `hedge_open_settings.executor_mode_snapshot` 陈旧死字段（停 2026-07-27）未清理
  （dispatch 附待办 2，另议）。
- review-1 后续项 S-1..S-3 / N-1..N-5 由 Bookkeeper 排期，未触碰。
- 周期表 `096232b7` 的 first/last_task_id 指向已删任务（既有待办，未动）。
- 服务当前停止；下一步由 Human 重启实盘复测（建卡回显、每轮预检、平仓收尾实时判定、
  断网预检暂停可见）。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-preflight-local-cache.handoff.md`
  2. `reports/agent-runs/2026-08-06-hedge-order-close-validation/05-preflight-local-cache-and-close-simplify.dispatch.md`
  3. `backend/services/hedge_preflight_provider.py`（`_cached` / `_cached_restricted_asset` / `_cached_account` / 各 `_read_*` / `last_failed_read`）
  4. `backend/hedge_open_tasks/service.py`（`:1404-1430` 平完判定、`_ensure_close_spot_balance`、`_pause_preflight_incomplete`、`_close_insufficient_pause_zh`）
  5. `backend/services/snapshot_service.py::get_cached_source`
  6. `frontend/index.html`（`renderHedgeExecutionStatus` / `renderHedgeTaskCard`）
- 执行：Human 用 `scripts/run-server.sh` 重启服务实盘复测——(a) 建卡回显秒内；
  (b) 连续开单/平仓每轮无数秒预检等待；(c) 平仓收尾仍以**实时**持仓判定是否全平
  （周期关闭正确）；(d) 断网/拔代理制造预检失败，确认任务**暂停并在卡片显示中文原因
  （含失败的读名）**而非静默消失。
- 关卡：以上四项均为 Human 目视验收。
- 不能假设的事实：服务未运行；`SnapshotService` 冷启动时 `restricted_asset` 无缓存 →
  forward open 会 fail-closed（restricted_asset 是唯一不降级的缓存项）；账户级 TTL
  为进程内 600s（重启后首次调用实时读一次）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: 2026-08-06-hedge-order-close-validation-preflight-local-cache
执行结果: completed
结果摘要: preflight 改读 SnapshotService 本地缓存（2h/5min/10min 陈旧上限，restricted_asset fail-closed 不降级）；账户配置 600s TTL；平完判定收敛到状态转换点；划转去复检+sleep(100ms)+缓存放行；预检失败改可见暂停（中文原因含失败读名）；前端徽标警示色+演习标注；1462 测试+self-check 全绿
产物: [backend/services/snapshot_service.py, backend/services/hedge_preflight_provider.py, backend/app/server.py, backend/hedge_open_tasks/service.py, backend/hedge_open_tasks/domain.py, frontend/index.html, backend/tests/test_hedge_preflight_provider.py, backend/tests/test_hedge_task_local.py, backend/tests/test_hedge_cycle_close.py, backend/tests/test_account_cache_refresh_v1.py, backend/tests/test_hedge_review2_regressions.py, reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-preflight-local-cache.handoff.md]
检查结果: [注入解耦：无 SnapshotService import、snapshot_reader=None 行为不变 通过(pass), 缓存命中 get_snapshot/check_symbol_legs 零网络 通过(pass), 陈旧降级+restricted_asset 超龄 fail-closed 通过(pass), 账户 TTL 600s 只读一次+失败不缓存 通过(pass), 平完判定普通轮 0 次/收尾轮恰好 1 次实时 通过(pass), 划转去复检+sleep(0.1)+缓存放行+文案提示 通过(pass), 预检失败 paused+中文原因含失败读名+无重试 通过(pass), 措辞无 retry 残留 通过(pass), 性能证据 376ms→0ms/建卡 fapi 2 次→0 次 通过(pass), 回归 1462 passed+self-check 全绿+范围核对 通过(pass)]
阻塞项: [none]
本地北京时间: 2026-08-06 20:23:49 CST
下一步模型: deepseek（Bookkeeper；本任务回执的直接接收者）
下一步任务: 读取：reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-preflight-local-cache.handoff.md；执行：核验交接件、确认工作树改动范围后封存 delivered/reported；关卡：Human 用 scripts/run-server.sh 重启服务实盘复测（建卡秒内 + 平仓收尾实时判定 + 断网预检暂停可见含失败读名）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-06 20:29:45 CST`
- source_sha256: `f6710a4fb06fa45d23c59484a1275827d2b80931d46385b7067ba331a22578e3`
- status_revision: 6（核验时 `status.json` 指向本任务，state `dispatched`）
- base_sha / delivery_sha: `ee7ec4f3a41db8d896652101fcd1821972b381bc` .. 见下文交付提交
- verdict: **verified（通过）**
- 依据（可复现）：
  - `python3 -m pytest backend/tests -q` → **1462 passed**（本 Bookkeeper 实测，92.49s）
  - `node frontend/self-check.js` → 全部自检通过（本 Bookkeeper 实测）
  - 解耦：`grep -rn "import.*SnapshotService" backend/hedge_open_tasks/ backend/services/hedge_preflight_provider.py` → 无真实 import（仅 docstring 提及）
  - `snapshot_service.py` diff 仅 +14 行（`get_cached_source` 只读，无刷新副作用，:1217-1229）
  - 预检失败可见暂停：`service.py:1556` `_pause_preflight_incomplete`、`:2421-2424` 中文原因含 `failed_read`（`last_failed_read` 来自 provider）、`:2406` payload `failed_read` 字段
  - 平完判定收敛：`:1507-1508` 仅 `scheduled_attempt_count >= target_n` 时调 `_verify_close_flat` 一次
  - 划转：`:1607` 记录 `_close_transfer_done`、`:1673` `sleep(100ms)`、`_close_insufficient_pause_zh` 含「可能是划转尚未到账」提示
  - 前端 Goal 5：`renderHedgeExecutionStatus` 加 `.warn` 警示色（仅非 live）、`:5130-5131` 成交按钮「（演习）」标注，数据源仍为 `executor_mode` 实时值
  - 性能证据：handoff 记录 376ms→0ms、建卡 fapi 2 次→0 次（模拟 50ms/请求，无真实网络）
- 观察点（不阻塞）：
  - dispatch 清单列 `test_snapshot_service.py`，实际测试落在 `test_account_cache_refresh_v1.py`（+1）——handoff 已按兜底授权说明（仓内无 `test_snapshot_service.py`，该文件为 SnapshotService 实例测试归属），合理
  - `test_hedge_review2_regressions.py` 的 1 处断言适配（预检失败改暂停）与 `test_hedge_cycle_close.py` 的 1 处改名（去复检）均为 Human 决定直接后果，handoff 逐条说明
- 后续状态：05 `dispatched` → `verified`；本任务属 `HIGH_RISK`（平仓完成判定 + 划转资金动作），按 §8 需 review-1 + review-2；是否评审与实盘复测由 Human 决定

## Errata (append-only)
