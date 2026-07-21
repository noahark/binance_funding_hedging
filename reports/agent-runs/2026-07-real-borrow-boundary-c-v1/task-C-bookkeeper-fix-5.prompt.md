[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task C — Review-1 Rework Round 1 / Fix-5 Intake Closure

你是 Task C 原实现者与 fix-4 作者：claude_glm / provider identity
`zhipu_glm` / `glm-5.2[1m]`。本轮只关闭 fix-4 bookkeeper intake 中的两个
残留 P1，不增加正式 rework 次数：`rework_count` 仍为 `1`。

## 必读 raw artifacts

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`（scope、AC #12/#13）
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`（D7、D9）
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`（ADR-006）
9. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`（§4.4、§6）
10. `frontend/index.html`、`frontend/self-check.js`
11. `backend/borrow_tasks/store.py`、`backend/app/server.py`
12. `backend/tests/test_borrow_store.py`、`backend/tests/test_service_health.py`
13. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`

## Required fix 1 — BK-R1-FIX4-001 (P1)

当前实现仅在 `state.borrowSchedulerSettings` 已加载时显示真实全局间隔；否则
预览写“当前全局间隔未加载”，但 `createBorrowTask()` 仍可直接 POST。启动的
`loadSchedulerSettings()` 也是未 await 的异步调用，因此用户可在初次 GET 完成前
或 GET 失败后创建立即可调度任务，违反“创建前确认当前全局间隔”。

必须：

- 在 `POST /api/borrow-tasks` 前 fail closed：只有已加载、形状有效的
  `interval_seconds` 存在时才允许创建；缺失/加载失败时返回就近中文错误且零任务
  POST。
- 提交入口在 POST 前重新投影预览，使资产、数量、次数、BigInt 目标总量和真实
  当前间隔与将提交的输入一致。
- 保留启动的一次性 same-origin scheduler-settings GET；不得新增 timer、浏览器
  调度、签名或 Binance/外域请求。
- `frontend/self-check.js` 增加 negative：settings 未加载/加载失败时确认创建为
  `ok=false` 且 `/api/borrow-tasks` POST 数量为 0；positive 仍在加载 interval=5 后
  显示完整预览并只发既有的一次 task POST。
- 不放宽现有 fetch-method、timer、same-origin、BigInt 或操作单元格守卫。

## Required fix 2 — BK-R1-FIX4-002 (P1)

fix-4 在 store 构造时把 pending orphan 转为
`resolved/unknown/crash_orphan_responseless`，但
`count_pending_orphan_attempts()` 只统计 `outcome='pending'`。因此
`server.run()` 在 store 构造后发出的 `recovered_orphan_blocker_count` 从 1 变成 0，
虽任务仍 blocked，也丢失了冻结 D7/ADR-006 启动恢复证据。

必须：

- 让该 sanitized count 表示当前仍由 crash orphan 阻塞的任务，而不是只按 pending
  outcome 统计。计数应覆盖：刚插入且 pending 的 blocker，以及启动恢复后仍由
  `crash_orphan_responseless` attempt 占据 `unresolved_attempt_id` 的 blocker。
- 第一次恢复后 count=1；第二次 reopen 仍 count=1（恢复幂等且证据不消失）；唯一
  匹配成功并清除 marker 后 count=0；无匹配耗尽且 marker 保留时 count 仍为 1。
- 按 task 当前 `unresolved_attempt_id` / 对应 attempt 计数，避免把已解决但历史仍在
  ledger 的 orphan 重复计入。
- 不记录资产、数量、txId、凭据或私有响应；不得改变 `server.py` 的事件字段名，除非
  测试证明绝对必要。
- 不改变 +5/+15/+60/+300/+900s 调度、唯一匹配、跨任务归属门、418/re-arm、零第二次
  POST、无 force-clear/retry-anyway 的现有行为。

## File boundaries

允许：

- `frontend/index.html`
- `frontend/self-check.js`
- `backend/borrow_tasks/store.py`
- `backend/tests/test_borrow_store.py`
- `backend/tests/test_borrow_scheduler.py`（仅必要时）
- `backend/tests/test_service_health.py`（仅生命周期计数断言必要时）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md`（append-only fix-5 section）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`（append only）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-5.dispatch.md`（只回填 receipt）

禁止：`status.json`、`70-handoff.md`、`ACTIVE.json`、
`30-review-1.bookkeeper-intake.md`、`40-fix-report.bookkeeper-audit.md`、raw review、
task/design/ADR/breakdown、`backend/app/server.py`、Harness/workflow/validator、canonical
docs、unrelated stage、`reports/agent-runs/_proposals/**`。不 commit/push/merge，不
dispatch 任何模型。

## 安全约束

- 严禁真实、认证或 production-reachable Binance 请求；只使用既有 fake/recording
  transport + dummy credentials。
- 不读取 `.env`、key file、cookie、credential store 或 expanded alias environment。
- 禁止第二次 borrow POST、hidden retry、retry-anyway、force-clear；禁止弱化
  exact-path/HMAC/urlopen/import/UI 守卫。

## 完成验证（真实输出 append 到 60-test-output.txt）

```text
python3 -m pytest backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_live_borrow_executor.py backend/tests/test_service_health.py -q
python3 -m pytest backend/tests/test_binance_signing.py backend/tests/test_portfolio_margin_borrow_client.py backend/tests/test_live_borrow_executor.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_api.py backend/tests/test_config.py backend/tests/test_private_client.py backend/tests/test_private_account_v1.py backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile backend/services/binance_signing.py backend/services/portfolio_margin_borrow_client.py backend/services/live_borrow_executor.py backend/services/private_client.py backend/borrow_tasks/*.py backend/app/server.py backend/config.py
git diff --check
```

## 收尾

在 `40-fix-report.md` 末尾追加 fix-5 小节，逐项映射 finding → root cause →
changed files → tests → result；真实输出只追加到 `60-test-output.txt`；回填
`task-C-bookkeeper-fix-5.dispatch.md` receipt；然后停止交回 bookkeeper。不得宣称
review 或 acceptance。

当前 Session ID: unavailable (prompt preparation runtime does not expose provider-native Session ID; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-5.prompt.md
本地北京时间: 2026-07-21 12:54:57 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute this fix-5 intake-closure packet, append real fake-only evidence, fill the receipt, and stop for bookkeeper
