# 实施任务：传输层异常证据保全 + 彻底移除 dry-run 下单/成交模式（含历史假数据清理）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景：2026-08-06 THE 实盘暴露两个问题，已完成双模型取证（claude-opus-5 独立排查 + glm
交叉复核，两份证据见 `evidence/`）：

- **A（取证盲区）**：16:41:59 双腿并发发单，现货腿 `api.binance.com` 成交（834390514），
  合约腿 `papi.binance.com` 抛 `URLError` → 传输层失败 → 47 秒后 drain query 拿到 `-2013`
  确认 absent → `single_leg` 裸露。**链路处理正确（ADR-2 不重发），但异常详情被丢弃**：
  `_send` 的 `except URLError as exc` 只写死字符串 `"connection_error"`，`exc` 整个扔掉，
  无法区分 refused / reset / TLS / DNS / 代理断开。另有一处同类缺陷（`_error_leg`）连 raw
  都不落库，异常完全静默。
- **B（假成交污染真实记账）**：16:35 改代码后重启服务**漏加载 `.env`** →
  `APP_HEDGE_EXECUTOR` 取缺省值 `disabled` → 默认注入 `RecordTransportExecutor`
  → 16:38:06 任务 `e22ce275` 产生 **2 笔假成交**（`dryspot-*` / `dryperp-*`）。
  `disabled` 不是「不执行」而是「假执行 + 真记账」：持仓聚合（`store.py:2487-2530`）对
  leg 行无差别累加，导致本地口径 **现货虚增 400、合约虚增 400**（面板 800/600 vs 交易所
  真实 400/200）。**Human 拍板：删除系统内 dry-run 类的下单和成交模式。**

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun`
- target_role: `Implementer`
- target_model: `deepseek`（Human 指定）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 3
- required_skill: `agents/skills/senior-developer.md`

## Goal

### A. 传输层异常证据保全（两处，同类缺陷）

任何传输层失败都必须把**异常类型 + 消息**落进 `hedge_open_raw_response.transport_error`，
不得只留分类词，不得静默。

### B. 移除 dry-run 下单/成交模式

`RecordTransportExecutor`（假成交模拟器）**从生产代码彻底移除**，降级为测试专用 fake；
运行时唯一的非 live 执行器是 `DisabledHedgeExecutor`（零 I/O、零模拟成交、
`category=ATTEMPT_DISABLED`）。并清理库内已产生的 4 笔假成交 leg 行。

---

## 实现要求

### A-1 `backend/services/hedge_open_live_client.py`（`_send`，:210-235）

现状：

```python
except TimeoutError:
    return HedgeHttpResponse(None, None, "", "timeout", None)
except urllib.error.URLError as exc:
    return HedgeHttpResponse(None, None, "", "connection_error", None)   # exc 被丢弃
except Exception as exc:
    return HedgeHttpResponse(None, None, "", type(exc).__name__, None)   # 仅类型名
```

要求：三个分支都保留详情，格式 **`"<分类>:<异常类型>: <消息>"`**，例如
`connection_error:ConnectionResetError: [Errno 54] Connection reset by peer`。

**强制约束**：

1. **分类词必须仍是前缀**（`timeout` / `connection_error` / `<ExcType>` 不变），保持既有
   语义可读；
2. **总长度截断 ≤ 200 字符**（沿用 `universal_transfer` 的 body 截断先例）；
3. **绝不带凭证/签名/URL query**：只取 `type(exc).__name__` 与 `str(exc)`；`URLError.reason`
   优先于 `str(exc)`。若 `str(exc)` 含 `http` 或 `?`（可能带 query），**只保留
   `type(exc).__name__`**——签名/API key 泄漏的风险高于取证价值；
4. **不改 `HedgeHttpResponse` 字段结构、不改 DB schema**：`transport_error` 已由
   `_raw_response_dict`（`live_hedge_executor.py:189-201`）直通
   `hedge_open_raw_response.transport_error` TEXT 列（`store.py:156`），无迁移。

**兼容性（已核验，实现者无需再查）**：生产代码对 `transport_error` **只有
`is not None` 判断，没有任何等值比较**（`classify_leg_response:359`、
`classify_query_response:445`、`hedge_preflight_provider` 各 `_read_*`），加后缀安全。
**唯一需要同步的断言**在 `backend/tests/test_hedge_open_live_client.py:188`
（`assert resp.transport_error == "connection_error"`）→ 改为前缀断言
（`startswith("connection_error")`）。

### A-2 `backend/services/live_hedge_executor.py`（`_error_leg`，:958-969）

现状：函数签名收 `exc` 但**函数体一行都没用**，且不设 `raw_response`（默认 None）
→ `_persist_leg_raw`（`service.py:2644` `if raw is None: return`）直接跳过
→ **该路径下异常完全静默、raw 表无任何记录**。

触发条件：`_run` 线程内 `_send_one_leg` 抛出 Python 异常（签名构造 / `Request` 构造 /
白名单 `PermissionError` 等）。本次 THE 事件**没有**走这条路（`URLError` 在 `_send` 内部
已被包成带 raw 的 response），属未触发的潜在盲区——但同一类缺陷，一并修。

要求：

1. `_error_leg` 用 `exc` 构造 raw dict，形状与 `_raw_response_dict` 一致：
   `{"http_status": None, "transport_error": "<分类>:<ExcType>: <msg>", "code": None,
   "msg": None, "body": ""}`，分类词用 `leg_send_exception`；脱敏 + 截断规则同 A-1；
   `exc is None` 时 `transport_error` 写 `"leg_send_exception:unknown"`。
2. `dispatch` 的 `_run` except（`:901-902`）加一行 stderr 诊断日志（沿用
   `[SET_LEVERAGE]` 的 `print(..., file=sys.stderr, flush=True)` 先例），便于服务终端即时可见。
3. **不改变控制流语义**：该腿仍是 `LEG_UNKNOWN_QUERYING`（查询、绝不重发），
   仅补证据。

### B-1 移除生产代码中的 dry-run 执行器

1. **`backend/hedge_open_tasks/executor.py`**：
   - 删除 `class RecordTransportExecutor`（**:253-368**）及其**私有辅助**
     `_snapshot_price`（:370）、`_leg_qty_filters`（:381）——已核验二者仅服务于该类；
   - `OutcomeSpec`（:86-107）随之移出（仅 `RecordTransportExecutor` 的 seeds 使用）；
   - 保留 `AttemptContext` / `AttemptOutcome` / `HedgeExecutor` Protocol /
     `DisabledHedgeExecutor`（:233-250）——后者成为**唯一**运行时非 live 执行器；
   - 更新模块 docstring（当前首句即「dry-run record-transport port」，须改写为
     disabled + live 两态）。
2. **`backend/hedge_open_tasks/__init__.py`**：移除 `RecordTransportExecutor`
   的 import（:24）与 `__all__` 条目（:46）；`OutcomeSpec` 同理（若有导出）。
3. **`backend/hedge_open_tasks/service.py`**：
   - `:36` import 改为 `DisabledHedgeExecutor`；
   - **`:481`** `self._executor = executor or RecordTransportExecutor()`
     → `executor or DisabledHedgeExecutor()`，并改写其上方 12 行注释块
     （现文案称默认是 record transport，已过时）；
   - `_dispatch_simulated`（:2397）**保留**——`DisabledHedgeExecutor` 仍走它，
     但须更新 docstring：它不再产生任何模拟成交，只写
     `category=ATTEMPT_DISABLED` + `filled_qty=0` 的 attempt/leg 行
     （`cumulative_base_qty=0` 不参与持仓聚合，`store.py:2493` 已 `continue`）。
4. **`backend/services/live_hedge_executor.py` / `hedge_preflight_provider.py`**：
   凡注释中「dry-run 假成交 / record transport」的表述改为「disabled（零成交）」。
   仅改注释，不改逻辑。

### B-2 测试夹具迁移（保住 60 处覆盖）

新建 **`backend/tests/fakes.py`**（或沿用仓内既有测试夹具约定，若已有同类文件则并入）：

- 迁入 `RecordTransportFake`（原 `RecordTransportExecutor` 逐字搬运，仅改名 + 改 import）
  与 `OutcomeSpec`、`_leg_qty_filters`、`_snapshot_price`；
- 7 个测试文件的 import 改指向 `backend.tests.fakes`：
  `test_hedge_executor.py`(20) / `test_hedge_api.py`(12) / `test_hedge_service.py`(10) /
  `test_hedge_wire_constraints.py`(8) / `test_hedge_cycle_close.py`(6) /
  `test_hedge_task_local.py`(2) / `test_hedge_leverage.py`(2)；
- **测试断言逻辑逐字不变**——单腿暴露 / 连续失败暂停 / qty_mismatch 等端到端场景覆盖
  **一条都不许少**。这是本项选「降级为夹具」而非「物理删除」的唯一理由，
  若为省事删测试，本任务判不合格。
- 新增纯度断言：`backend/hedge_open_tasks/` 与 `backend/services/` 下
  **grep 不到 `RecordTransport`**（沿用 `test_hedge_purity.py` 的 grep 证明模式）。

### B-3 历史假数据清理（**破坏性，Human 已授权**）

已核验的清理目标（`data/hedge-open-tasks.sqlite3`）：

| 表 | 目标 | 实测量 |
|---|---|---|
| `hedge_open_leg` | `order_id LIKE 'dry%'` | **4 行**（attempt 4/5 各 2 腿） |
| `hedge_open_attempt` | `id IN (4, 5)` | 2 行 |
| `hedge_open_task` | `e22ce275-bdc1-4302-998c-c50acdaa8161` | `success_count 2→0`、`scheduled_attempt_count 2→0`、`accepted_pair_count 2→0`、`status done→deleted` |
| `hedge_open_raw_response` | attempt 4/5 | **0 行**（dry-run 不发请求，无需清理） |
| `hedge_open_log` | 16:38:06 两条 `record_transport` | **保留**——它们是本次定性的关键证据，不删 |

要求：

1. 写成**可复核的一次性脚本**放 `scripts/`（命名沿用 `backfill-cycles.py` 风格），
   **不写成手工 SQL 贴在报告里**；
2. **执行前先备份**：`data/hedge-open-tasks.sqlite3.bak-dryclean-<YYYYMMDD-HHMMSS>`
   （沿用 `data/` 现有 `.bak-*` 命名惯例）；
3. **前后对账证据**（写进交接件）：清理前后各跑一次持仓聚合，证明

   ```
   spot_qty  800 → 400   （= 交易所 spot_bal 400）
   perp_qty  600 → 200   （= 交易所 um_amt -200）
   ```

   `position_qty` 由 −600 → −200；
4. 任务 `e22ce275` 全部 attempt 均为假成交，**无任何真实腿**，故整卡置 `deleted` 是安全的
   （已核验：该任务名下无非 dry 订单号）；
5. **不得触碰** attempt 6/7 及其 leg / raw 行（真实成交，`834390514` / `834392365` /
   `2031628184`）。

### B-4 启动模式可见性（防复发，最小实现）

本次事故的直接诱因是「服务被误启动成 disabled 而无人察觉」。要求最小改动：

- 服务启动已有 `hedge_open_execution_mode` 事件日志（`server.py:1079`），**保留不动**；
- `disabled` 模式下服务启动时**额外打一行醒目 stderr 警告**，明确「对冲下单已禁用，
  任何任务不会真实发单，也不会产生成交记录」；
- **不做**前端改造（Opus 报告的 P0-3 前端常驻标识另开任务，本次不含）。

---

## 不在本次范围

- **问题 C**（`preflight_incomplete` 后 worker 直接退出 `service.py:1450`、任务静默停摆
  33 分钟不自愈）——Human 已决定单开 dispatch，本次**不碰** `_worker_exit` /
  `HedgePreflightProvider` 的重试语义；
- preflight 的 TTL 缓存（`fapi/exchangeInfo` 1.06 MB 全量）——同上，下一个任务；
- 前端 executor_mode 常驻标识、`hedge_open_settings.executor_mode_snapshot`
  陈旧死字段（停在 2026-07-27）的修正；
- 不改 A 的控制流：`connection_error → UNKNOWN → 不重发 → drain query → absent`
  这条链路**按设计正确**，本次只补证据，**严禁**改成「传输失败即重发」；
- 不动 `leverage` 修复（`/papi/v1/um/leverage`）、SPOT_ONLY 路由修复等既有工作树改动；
- 不动周期表 `hedge_open_cycle`（`096232b7` 的 `first/last_task_id` 指向已删任务是
  另一条已记录的待办）。

## Allowed Files

可修改：

- `backend/hedge_open_tasks/executor.py`（删 RecordTransportExecutor + 辅助 + docstring）
- `backend/hedge_open_tasks/__init__.py`（导出清理）
- `backend/hedge_open_tasks/service.py`（:36 import、:481 默认执行器、`_dispatch_simulated` docstring）
- `backend/services/hedge_open_live_client.py`（`_send` 三分支异常详情）
- `backend/services/live_hedge_executor.py`（`_error_leg` + `_run` stderr log + 注释）
- `backend/app/server.py`（仅 disabled 模式启动警告一行）
- `backend/tests/fakes.py`（新建）+ 上述 7 个测试文件的 import
- `backend/tests/test_hedge_open_live_client.py`（transport_error 前缀断言）
- `backend/tests/test_hedge_purity.py`（新增 grep 纯度断言）
- `scripts/`（新增一次性清理脚本）

只读：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `evidence/2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`
- `evidence/2026-08-06-hedge-order-close-validation-glm-diagnosis-crosscheck.md`
- `backend/hedge_open_tasks/store.py`（持仓聚合 :2487-2530、raw 落库 :2031-2045）

禁止：

- 回退既有改动（leverage / SPOT_ONLY 路由等）、未授权提交、移动 HEAD、访问凭证；
- **对实盘发单/划转/设杠杆**（本任务只做代码 + 测试库 + 本地 DB 清理）；
- 为省事删减测试覆盖（见 B-2）；
- 触碰 attempt 6/7 的真实成交数据。

交接件：`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/
2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun.handoff.md`

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Implementer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/developer-discipline.md`
8. `agents/skills/senior-developer.md`
9. 两份取证报告（`evidence/` 下 `*-diagnosis.md` 与 `*-crosscheck.md`）——
   **必读**，本 dispatch 的所有行号/数量均出自其中，已双模型互证
10. 按需：`backend/hedge_open_tasks/executor.py`、`service.py:481 / :2397 / :2644`、
    `live_hedge_executor.py:189 / :958`、`hedge_open_live_client.py:210-235`

## Acceptance Checks

1. **A-1 证据**：构造 `URLError` / `TimeoutError` / 其他异常三种传输失败，
   `transport_error` 均为 `<分类>:<ExcType>: <msg>` 形态、分类词仍在最前、长度 ≤ 200；
   落库后从 `hedge_open_raw_response.transport_error` 可读回详情。
2. **A-1 脱敏**：`str(exc)` 含 `http`/`?` 时只留异常类型名（负向测试）。
3. **A-2 证据**：`_send_one_leg` 抛异常时，该腿有 raw 行落库（不再被
   `if raw is None: return` 跳过），且 `dispatch_state` 仍为 `LEG_UNKNOWN_QUERYING`
   （控制流未变）。
4. **B-1 纯度**：`backend/hedge_open_tasks/` + `backend/services/` grep 不到
   `RecordTransport`；`service.py:481` 默认执行器为 `DisabledHedgeExecutor`；
   非 live 模式下**不产生任何 filled_qty>0 的 leg 行**。
5. **B-2 覆盖不减**：7 个测试文件全部改指 `backend/tests/fakes.py`，
   **测试条数与断言逐字不变**；`git diff` 中测试文件仅 import 行变动
   （断言若有变动须在交接件逐条说明理由）。
6. **B-3 对账**：清理前后 `spot_qty 800→400`、`perp_qty 600→200`、
   `position_qty −600→−200`，与交易所 `spot_bal=400` / `um_amt=-200` 一致；
   备份文件存在；attempt 6/7 数据零改动（附前后 diff 证据）。
7. **B-4**：`disabled` 模式启动打出醒目警告；`live` 模式行为逐字不变。
8. **回归**：`python3 -m pytest backend/tests -q` 全绿 + `node frontend/self-check.js` 全绿。
9. **范围核对**：`git status --short` 仅列 Allowed Files；无前端功能改动、无实盘写。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接），`下一步任务` 用可执行形式
`读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：Human 用 `scripts/run-server.sh` 重启服务实盘复测——确认
(a) 面板持仓回到 400/200 与交易所一致；
(b) 故意用 `python3 -m backend.app.server`（不加载 `.env`）启动一次，确认 disabled 模式
有醒目警告、且点「成交 1 次」**不再产生任何假成交记录**。

**评审状态**：本 stage 为验证 + 小 bug 修复（Human 拍板）；B-3 涉及**生产数据删除**，
执行前必须完成备份，交接件须附前后对账证据。修复完成经核验后，是否复评由 Human 决定。

---

## 附：Bookkeeper 待办

本 dispatch 由 claude-opus-5 起草（取证 + 范围界定），**未改 `status.json`**。
派发前需 bookkeeper（deepseek）将 `status.json` 的 `current_task` 更新为本任务、
`status_revision` 递增至 3。
