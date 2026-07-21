[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须对应你本会话内真实发生的动作。
3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task C — Review-1 Rework Round 1 / Micro Fix-6

目标：关闭 fix-5 唯一残留的 stale-interval fail-closed 路径，并补齐
implementer report 页脚。正式 `rework_count` 保持 `1`。

## 必读

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-5.prompt.md`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md`（末尾 Fix-5 intake addendum）
6. `frontend/index.html`
7. `frontend/self-check.js`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`

## Required code/test closure

当前 `loadSchedulerSettings()` 成功时写入 settings，但 GET 失败时只显示错误，
保留旧 settings。因此“先成功加载 interval=5，再刷新 503”后
`currentIntervalSeconds()` 仍返回旧值并允许任务 POST，不符合 fix-5 prompt 的
“加载失败零 POST”与 AC #12 的“当前间隔确认”。

必须：

- 在 scheduler-settings GET 的失败路径立即 invalidate
  `state.borrowSchedulerSettings`，再渲染 settings/preview；失败后预览不得继续显示
  旧间隔，创建必须 `ok=false` 且零 `/api/borrow-tasks` POST。
- 修改 self-check item 66b 的 503 用例：先保留已成功加载的 interval=5，随后让 GET
  返回 503；**不得**先调用 `clearBorrowSchedulerSettings`；验证失败后预览为未加载/
  错误状态、create 为 `ok=false`、task POST delta=0。
- 保留初次未加载 negative 与成功加载 positive；保留启动一次性 same-origin GET、
  timer/fetch-method/same-origin/BigInt/操作单元格所有守卫。
- 不新增定时器、浏览器调度/签名、Binance/外域请求、第二次 task POST、hidden retry、
  retry-anyway 或 force-clear。

## File boundaries

允许：

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md`
  （append-only micro fix-6 section，结尾必须是本 target runtime 生成的六行页脚）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`
  （append only）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-6.dispatch.md`
  （只回填 receipt 与其现有页脚）

禁止其他所有文件，特别是 backend、`status.json`、`70-handoff.md`、`ACTIVE.json`、
bookkeeper audit、raw review、task/design/ADR/breakdown、Harness/workflow/validator、
canonical docs、unrelated stage、`reports/agent-runs/_proposals/**`。不
commit/push/merge，不 dispatch 任何模型。

## 完成验证（真实输出 append 到 60-test-output.txt）

```text
node frontend/self-check.js
python3 -m pytest backend/tests/test_borrow_store.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/borrow_tasks/*.py backend/app/server.py backend/config.py
git diff --check
```

## 收尾

在 `40-fix-report.md` 末尾追加 micro fix-6 finding → root cause → changed files →
tests → result，随后追加以下六行页脚（Session ID 必须来自本 target runtime，未知则
写精确 unavailable 原因，不得猜测）：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md
本地北京时间: <local date command> CST
下一步模型: bookkeeper
下一步任务: intake micro fix-6, independently rerun tests, and create a new committed fingerprint only if every gate closes
```

真实输出只追加到 `60-test-output.txt`；回填
`task-C-bookkeeper-fix-6.dispatch.md`；然后停止交回 bookkeeper，不得宣称 review 或
acceptance。

当前 Session ID: unavailable (prompt preparation runtime does not expose provider-native Session ID; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-6.prompt.md
本地北京时间: 2026-07-21 13:34:51 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute this micro fix-6, prove loaded-to-503 invalidation and zero task POST, append the execution footer, fill the receipt, and stop for bookkeeper
