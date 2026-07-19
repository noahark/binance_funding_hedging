<!-- RECEIPT — bookkeeper fills this metadata after the human operator executes the packet.
status: done
target_model: kimi / kimi-code/kimi-for-coding (fresh read-only review session)
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-real-borrow-execution-v1/review-1-task-A-by-kimi.prompt.md)"
started_at: unavailable (not captured by operator)
completed_at: 2026-07-19T20:30:10+08:00
session_id: session_e45eb13b-9589-405c-95c5-fbe7a4723e82
session_id_source: transcript_path (reviewer's reported Kimi session location)
output: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-backend.md
next_dispatch: ACCEPT → task-B Review-1 / then stage Review-2; REWORK → Task A scope-contained fix
-->

--- PROMPT BODY (immutable from this line) ---

你是一个全新的、只读的 Kimi Code 会话，担任正式 `reviewer_1`。审阅
stage `2026-07-real-borrow-execution-v1` 的 **Task A 后端交付**。你没有参与
Task A 的实现或修复；不得复用该任务实现或嵌入预审会话。Task B 由 Kimi 的另一个
会话实现，但它不是本次被审的代码；本次严格只审 Task A 的 committed range。

## 只读与范围

- 禁止写文件、改工作树、提交、网络请求、签名请求或访问凭据。
- 只审以下固定提交范围，不要使用移动的 `HEAD`：
  - base_sha: `6c870414a951550331676fe5db0c4e3a46aab555`
  - head_sha: `40efb028ead50d667bb32dbe10e9af6a7d77409e`
  - 预期 task fingerprint:
    `40efb028ead50d667bb32dbe10e9af6a7d77409e:a3e3a9bcd8b6233b581f4587e88b64478cc9cb356b1d40b1cddc9a1f3c33d3bc`
- Task A 允许范围：`backend/borrow_tasks/**`、`backend/app/server.py`、
  `backend/config.py`、`schemas/api/borrow-tasks/**`、`backend/tests/test_borrow_*.py`、
  `backend/tests/borrow_paper_executor.py`、必要时 `backend/tests/conftest.py`、
  `.gitignore` 的 data-path 条目。
- 任何范围外的 Harness evidence commit 都不是 Task A 产品 diff 的一部分；不要因
  `head_sha` 之后的提交产生误判。

## 必做独立核验

1. 重算 Task A 指纹（`status.json` 在 hash 输入中排除）：

   ```sh
   git diff --binary 6c870414a951550331676fe5db0c4e3a46aab555..40efb028ead50d667bb32dbe10e9af6a7d77409e -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-execution-v1/status.json' | shasum -a 256
   ```

   将输出 hash 与预期 fingerprint 的冒号后部分比较；不一致必须 `BLOCKED`。
2. 检查 `git diff --name-only <base>..<head>` 只在 Task A 允许范围，并实际阅读
   该 diff、相关源码与 schemas。
3. 阅读下列原始材料（不能只依赖本 prompt 或任何书面摘要）：
   - `AGENTS.md`、`workflows/templates/stage-delivery.yaml` 的 Review-1 部分；
   - `00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、
     `06-direction-synthesis.md`、`13-user-decisions-and-contract-amendment.md`；
   - `status.json`、`20-implementation.md`、`20-implementation-backend.md`、
     `60-test-output.txt`、`60-test-output-backend.txt`；
   - 原始嵌入审查链：`embedded-review-A-round1.raw-output.md`、
     `embedded-review-A-round1.fix-note.md`、
     `embedded-review-A-round2-retry-1.raw-output.md`、
     `61-r4-diff-reconciliation.txt`。
4. 独立重跑至少：

   ```sh
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_borrow_domain.py backend/tests/test_borrow_store.py backend/tests/test_borrow_scheduler.py backend/tests/test_borrow_executor.py backend/tests/test_borrow_api.py -q -p no:cacheprovider
   git diff --check
   ```

## 重点验收

- A+B 为 durable local task system：SQLite task/attempt/settings、Decimal 字符串与
  微秒时间、全局轮询 round-robin、创建即 `borrowing`；没有 Binance 写入、认证读、
  签名、凭据或 `maxBorrowable` 路径，runtime executor 只能 `disabled`。
- 两阶段调度在 executor 调用期间不持有 SQLite 锁或 transaction；pending 崩溃恢复
  fail-closed，含已经 resolve 成 `unknown` 的标记在重启后仍阻断该任务。
- 生命周期、乐观版本、未知 JSON 字段拒绝、body 上限、405 JSON（HEAD 无 body）、
  frozen API route/error/schema 契约正确；任务日志按
  `COALESCE(finished_at, dispatched_at, scheduled_at) DESC, id DESC`，cursor 不重不漏。
- 禁用执行器只写脱敏 `execution_disabled` 账本行；没有伪造成功或外部副作用；Task A
  不破坏现有 snapshot/private read-only 契约。

## 输出契约（严格）

你的回复先给简短审阅叙述和以下导航 footer，之后给**一个**符合
`schemas/review-verdict.schema.json` 的 JSON object。JSON 必须是回复/保存文件的
最终内容：不用 Markdown 围栏，末尾 `}` 后不得有任何字符或换行。

footer 格式：

当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-backend.md
本地北京时间: <用本地 date 命令取得的时间>
下一步模型: <model-or-human>
下一步任务: <specific next task>

JSON 必填：`schema_version: 1`、stage_id、`role: "first_reviewer"`、
`model: "kimi-code/kimi-for-coding"`、精确 `diff_fingerprint`、
`reviewer_prior_involvement: "none"`、reviewed_artifacts、findings、
required_fixes、next_action。若 `REWORK`，必须同时提供可直接派发的
`fix_start_prompt`，保留原始材料路径、所有 findings、Task A 文件边界、测试命令与
验收标准。严禁把嵌入预审 PASS 当作正式 ACCEPT 的替代。
