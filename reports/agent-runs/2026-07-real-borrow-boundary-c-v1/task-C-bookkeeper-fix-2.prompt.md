[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

# Task C — Bookkeeper Intake Fix 2（仅 BK-C-001 residual）

你是 Task C 原实现者：`claude_glm` / provider identity `zhipu_glm` /
`glm-5.2[1m]`。fix 1 复审已关闭 BK-C-002、003、004；本轮只关闭
BK-C-001 剩余的 fail-closed 缺口。实现仍未 commit、未进入 formal review-1，
formal rework count 仍为 0。

## 必读

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`（D6）
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md`（§5.3）
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md`（Fix 1 Re-audit）
6. `reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/query-margin-loan-record.md`
7. `backend/services/portfolio_margin_borrow_client.py`
8. `backend/services/live_borrow_executor.py`
9. 对应两个测试文件与当前 `20-implementation.md` / `60-test-output.txt`

## 唯一修复范围

让 loan-record 响应只有在 envelope 与每个 row 都足以证明唯一归属时才返回
`matched=True`：

1. `total` 必须是 non-bool、non-negative integer；missing/bool/string/negative
   一律 fail closed。
2. 当前实现只检查一页，因此只有 `total == raw rows length` 才算完整；
   `total > rows` 和 `total < rows` 都 fail closed。不得用过滤后的长度掩盖
   non-dict/malformed row。
3. 不得静默丢弃 malformed row 后继续用另一行证明成功。每个返回 row 必须先
   满足冻结字段契约：`txId`, `asset`, `principal`, `timestamp`, `status` 均存在且
   可按冻结类型/枚举安全解析；任一 row malformed 则整个本次 read 不能证明
   success。`timestamp` 至少必须是 non-bool int64-compatible value；
   response-less window 还必须位于实际发送的 `[startTime,endTime]` 内。
4. known-id 路径除发送 `txId` query 外，必须验证返回 candidate 的 canonical
   `txId == attempt.tran_id`；不相等时 stay blocked。
5. 保留已闭合的 envelope、pagination、window cap、cross-task、418 与 lifecycle
   行为，不扩展范围。

## 必须新增的回归测试

以下每个输入均须断言 `matched is False`：

- unique matching row + missing `total`；
- unique matching row + `total=true`；
- one raw row + `total=0`；
- known `tran_id="555"` + response `txId="999"`；
- unique row missing/invalid `timestamp`；
- one valid matching row plus one malformed row（不能过滤后误判 unique）。

同时保留/断言：完整 `rows`/`total` envelope 的 unique positive case 仍成功；
known `555` + response `555` 成功；response-less candidate timestamp 位于发送窗口
时成功。

## Allowed Files

- `backend/services/portfolio_margin_borrow_client.py`
- `backend/services/live_borrow_executor.py`
- `backend/tests/test_portfolio_margin_borrow_client.py`
- `backend/tests/test_live_borrow_executor.py`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md`
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt`（append only）
- `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-2.dispatch.md`
  （只回填 Receipt）

禁止修改其它 source/test、`status.json`、`70-handoff.md`、`ACTIVE.json`、bookkeeper
audit、task/design/ADR/breakdown、canonical docs、Harness/workflow/validator、
unrelated stage 或 `_proposals/**`。不 commit/push/merge，不 dispatch reviewer。

## 安全约束

- 零真实、认证或 production-reachable Binance 请求；只用 injected fake/
  recording transport + dummy credentials。
- 不读取 `.env`、key file、cookie、credential store 或 expanded alias environment。
- 不新增 endpoint、retry、force-clear、second POST 或任何借币以外副作用。

## 完成验证

```text
python3 -m pytest \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py -q
python3 -m pytest \
  backend/tests/test_binance_signing.py \
  backend/tests/test_portfolio_margin_borrow_client.py \
  backend/tests/test_live_borrow_executor.py \
  backend/tests/test_borrow_store.py \
  backend/tests/test_borrow_scheduler.py \
  backend/tests/test_borrow_api.py \
  backend/tests/test_config.py \
  backend/tests/test_private_client.py \
  backend/tests/test_private_account_v1.py \
  backend/tests/test_service_health.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
python3 -m py_compile \
  backend/services/binance_signing.py \
  backend/services/portfolio_margin_borrow_client.py \
  backend/services/live_borrow_executor.py \
  backend/services/private_client.py \
  backend/borrow_tasks/*.py \
  backend/app/server.py backend/config.py
git diff --check
```

把真实输出追加到 `60-test-output.txt`。在 `20-implementation.md` 增加
`Bookkeeper intake fix 2 — BK-C-001 residual closure`，逐条映射六个 negative
reproduction 与三个 positive case。回填 dispatch Receipt 和六行页脚后停止等待
bookkeeper；不得宣称 review 或 acceptance。

当前 Session ID: unavailable (prompt preparation session; target runtime must record its own verified ID or exact unavailable reason)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-2.prompt.md
本地北京时间: 2026-07-21 09:32:08 CST
下一步模型: human operator → Claude-GLM / GLM-5.2
下一步任务: execute this fix-2 packet, close residual BK-C-001 fail-closed matching gaps, rerun fake-only tests, and stop for bookkeeper
