# Task Handoff: fix-review1-dual-ledger-flow-log-v1

## Source Report (author-only; immutable after task end)

- task_id: `fix-review1-dual-ledger-flow-log-v1`
- role: `Implementer`（修复轮；`required_skill: minimal-change-engineer`）
- target model: `claude_glm`（provider `zhipu_glm`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 22:28:06 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`（取自 `status.json.base_sha`；见「SHA 说明」）
- delivery_sha: `pending`（本 dispatch Stop 未授予提交权——与任务 A/B 不同，明确「等待 Bookkeeper 封存」；故不自行提交，留 Bookkeeper 封存并解析实际 delivery_sha）

### 任务背景

统一 review-1（deepseek，`review-1-dual-ledger-flow-log-v1`，verdict `REWORK`）对 A+B+C+前端最终交付的两项 in-range 发现。本任务为**修复轮**（`rework_count` 0→1，根因按 F1 命名：「任务 B 引入新装配依赖未同步既有测试桩，且回归声明未覆盖全量」）。**最小修复，不改交付行为**：不动 `server.py`/`scheduler.py`/`service.py`/`domain.py`/`store.py`/前端/契约。

### Finding → Fix 映射（minimal-change-engineer 必填）

| Finding | 范围/严重 | 根因 | 修复 | 文件 |
|---|---|---|---|---|
| **F1** | in-range / 🔴 阻塞 | `server.py:954`（任务 B `550f8b7`）新增 `LedgerFlowService(ledger_store, service.private_client, …)`，但既有桩 `_RunStubService` 无 `private_client` 属性，破坏 5 个 `run()` 生命周期测试；且 B handoff「194 回归全绿」未覆盖 `test_service_health.py` | 在 `_RunStubService.__init__` 增 `self.private_client = None`（`LedgerFlowService.is_usable()` 对 `client=None` 返回 `False`，调度器不启动，恰好走通 §15.3「通道不可用不调度」） | `backend/tests/test_service_health.py` |
| **F2** | in-range / 🟡 建议 | `backend/ledger_flow/scheduler.py` 无任何单元测试（`decide` 四判据、`_startup_catchup` 三分支无断言） | 新增 `test_ledger_flow_scheduler.py`，注入时钟覆盖 `decide` 四判据+满足返回 `scheduled`、`_startup_catchup` 三分支、`stop()` 幂等 | `backend/tests/test_ledger_flow_scheduler.py`（新建） |

### 实际修改范围（仅 Allowed Files）

1. `backend/tests/test_service_health.py` —— `_RunStubService.__init__` 末尾新增 `self.private_client = None`（附注释说明）。**仅此一行实质改动**，未动其它。
2. `backend/tests/test_ledger_flow_scheduler.py`（新建）—— 10 个 scheduler 单测。
3. `reports/.../evidence/fix-review1-dual-ledger-flow-log-v1.pytest.txt`（新建）—— 全量回归原始输出（1351 passed）。
4. `reports/.../status.json` —— 仅 `current_task.state` 由 `dispatched` 改为 `reported`，其余字段一字未动。

**未改动**（交付行为零改动，git diff 仅限 Allowed Files）：`server.py` 装配、`scheduler.py` 行为、`service.py`/`domain.py`/`store.py`/`__init__.py`、`frontend/*`、契约、snapshot schema、60 秒调度、cache-refresh、持仓合并、任何既有端点。

### 改动理由（逐条）

- **F1 `_RunStubService.private_client = None`**：`run()` 现从 `service.private_client` 构造 `LedgerFlowService`；桩缺该属性导致 `AttributeError`。补 `None` 后 `is_usable()` 为 `False`，调度器不启动——正是这些 `run()` 生命周期桩期望的「通道不可用」路径（不引入真实 client，不触发任何上游/线程）。这是评审给定的最小修复，且根因确在桩而非 `server.py`（桩能补通，无需改装配）。
- **F2 scheduler 单测**：`decide` 是纯判定、`_startup_catchup` 是确定性分支，注入时钟即可全覆盖，无需起线程。覆盖了计划评审 Q4（重启/时钟跳变/休眠不漏跑不重复）所关注的判定路径与重试预算。

### 命令与结果（离线，不启动真实服务/不访问网络/不读凭据/不写 `data/`）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.handoff.md` → `PASS(absent)`（2026-08-04 22:28 CST；与 Bookkeeper 预检一致）。
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`。
- `git rev-parse HEAD`（未提交，工作树态）→ `8c67c59f38c5a00c1b22f2b744af82d8eae00ecc`。
- F1 复测 `pytest backend/tests/test_service_health.py` → **16 passed**（前次 5 failed 已恢复）。
- F2 复测 `pytest backend/tests/test_ledger_flow_scheduler.py` → **10 passed**。
- **全量回归**（AC1 要求，原始输出已存 `.pytest.txt`）：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q backend/tests/` → **1351 passed in 86.44s, 0 failed**。
  - 对账：review-1 实测 `1336 passed, 5 failed`（共 1341）；本修复后 5 个失败恢复（1341 passed）+ F2 新增 10 = **1351 passed, 0 failed**。

### 残留风险 / 观察

- **无阻塞**。review-1 的 O1（run 表 `*_new_row_count` 恒 0）、O2（run 记录先于明细写入）、O3（`_build_coverage` by_source 半对象判定）均为**观察项，非本轮范围**，评审已确认不构成缺陷；本轮未改其行为。
- F2 测试覆盖 `decide`/`_startup_catchup` 的纯判定与分支；单飞（service 锁）与「通道未启用不 `start()`」由 service/server 既有测试覆盖（`test_run_once_single_flight_returns_none_when_busy`、装配 `is_usable()`）。

### SHA 说明

`status.json.base_sha = dc4cc6d`（dispatch 禁改除 `current_task.state` 外字段，故沿用）。本修复改动基于工作树 HEAD `8c67c59`（含 A/B/C+前端最终提交与控制提交）；评审区间以本任务 Allowed Files（`test_service_health.py`、`test_ledger_flow_scheduler.py`）为实际受审范围。本任务**未自行提交**（dispatch Stop 未授予提交权），留 Bookkeeper 封存并解析实际 `delivery_sha`。

### 仓库内证据路径

- review-1 原文：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`
- 任务 B 交接（scheduler/service 签名）：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/backend-ledger-schedule-api-v1.handoff.md`
- 改动：`backend/tests/test_service_health.py`、`backend/tests/test_ledger_flow_scheduler.py`
- 全量回归原始输出：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.pytest.txt`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.handoff.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md`；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- 执行：Bookkeeper 核验本修复交接件 + 全量回归原始输出（1351 passed, 0 failed），封存（提交并解析 delivery_sha），随后安排 review-1 复审（fixed `base_sha..delivery_sha`）。
- 关卡：review-1 复审 `ACCEPT` 后，按流程走 review-2（sonnet5）。
- 不能假设的事实：本任务未自行提交（工作树态，留 Bookkeeper 封存）；F1 根因在桩不在 `server.py`（已用桩补通验证）；review-1 的 O1/O2/O3 为观察项非本轮范围。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: fix-review1-dual-ledger-flow-log-v1
执行结果: completed（完成）
结果摘要: 修复 review-1 两项 in-range：F1 给 _RunStubService 补 private_client=None（恢复 5 个被破坏的 run() 生命周期测试，根因在桩不在 server.py）；F2 新增 test_ledger_flow_scheduler.py 10 个单测覆盖 decide 四判据+满足返回 scheduled/_startup_catchup 三分支/stop 幂等。全量 pytest backend/tests/ 实测 1351 passed 0 failed（前次 1336+5failed）。零交付行为改动，未动 server/scheduler/service/domain/store/前端/契约。本任务未自行提交（dispatch 未授提交权），留 Bookkeeper 封存。
产物: [backend/tests/test_service_health.py, backend/tests/test_ledger_flow_scheduler.py, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.pytest.txt, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.handoff.md, reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json]
检查结果: [F1 _RunStubService 补 private_client=None 后 test_service_health.py 单独 16 passed(5 failed 已恢复): pass, F1 全量 pytest backend/tests/ 1351 passed 0 failed 原始输出已存 .pytest.txt: pass, F2 test_ledger_flow_scheduler.py 覆盖 decide 四判据+满足返回 scheduled+_startup_catchup 三分支+stop 幂等 共10 passed: pass, 交付行为零改动(git diff 仅 test_service_health.py+新测试,未动 server/scheduler/service/domain/store/前端/契约): pass, 未启动服务/未访问网络/未读凭据/未写实盘: pass]
阻塞项: [none；本任务未自行提交(dispatch Stop 未授提交权,留 Bookkeeper 封存并解析 delivery_sha)；review-1 的 O1/O2/O3 为观察项非本轮范围]
本地北京时间: 2026-08-04 22:28:06 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/fix-review1-dual-ledger-flow-log-v1.handoff.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/review-1-dual-ledger-flow-log-v1.handoff.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json；执行：核验本修复交接件与全量回归原始输出（1351 passed 0 failed），封存（提交并解析 delivery_sha）并安排 review-1 复审；关卡：review-1 复审 ACCEPT 后走 review-2（sonnet5）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 22:35:00 CST
- source_sha256（marker 前字节）：`e8b67fa204b35d200a274c6996d8d44abf0c265c5b8a666d14d4aa8644b433c8`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：20（`current_task.id = fix-review1-dual-ledger-flow-log-v1`、`state = reported`，与交接件一致；预检 `test ! -e` 于 2026-08-04 22:22 CST 通过，实现者 22:28 CST 交付）
- **delivery_sha（已解析）**：见本封存提交（`git rev-parse` 直接值；父提交 `8c67c59`）。
- 结论：**通过（verified）**。F1 修复最小且正确（`_RunStubService.__init__` 补 `private_client=None`，`test_service_health.py` 单独 16 passed、5 个失败恢复；根因确在桩不在 `server.py`——桩补通即验证）；F2 新增 `test_ledger_flow_scheduler.py` 10 个单测（decide 四判据 + 满足返回 scheduled + `_startup_catchup` 三分支 + stop 幂等）；**全量回归原始输出核验：`1351 passed in 86.44s, 0 failed`**（对账：review-1 实测 1336+5failed = 1341 → 修复恢复 5 + 新增 10 = 1351，账目吻合）；交付行为零改动（git diff 仅 `test_service_health.py` + 新测试文件）；未启动服务/未访问网络/未读凭据。
- 后续状态：本任务 → `verified`；review-1 复审 `review-1-r2-dual-ledger-flow-log-v1`（deepseek，与修复作者 `zhipu_glm` 跨 provider）已路由，受审 = 本修复交付（F1/F2 diff + 全量回归证据）；复审 ACCEPT 后走 review-2（sonnet5）。

## Errata (append-only)

（无。）
