# Review-1 — Task A 后端交付（stage 2026-07-real-borrow-execution-v1）

审阅人：Kimi（`kimi-code/kimi-for-coding`），全新只读会话，未参与 Task A 实现或修复，未复用嵌入预审会话。审阅范围固定为 committed range `6c870414..40efb028`（Task B 前端交付不在本次范围内）。

## 独立核验结果

- **指纹**：重算 `git diff --binary 6c870414..40efb028`（排除 `status.json`）得 `a3e3a9bc…3d3bc`，与 `status.json` 记录的 Task A fingerprint 冒号后部分完全一致。
- **范围**：产品 diff 仅含 `backend/borrow_tasks/**`、`backend/app/server.py`、`backend/config.py`、`schemas/api/borrow-tasks/**`、`backend/tests/borrow_paper_executor.py` + `test_borrow_*.py`、`.gitignore`（仅 `data/` 条目）；其余为 stage Harness 证据文件，非产品 diff。未改 `conftest.py`，未触碰 snapshot/private-client/public-market schema。
- **原材料**：通读 workflow Review-1 节、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、`06-direction-synthesis.md`、`13-user-decisions-and-contract-amendment.md`、`status.json`、实现报告与测试输出、嵌入审查链（round1 BLOCKER → fix-note → round2 PASS）、`61-r4-diff-reconciliation.txt`，并逐行阅读全部产品源码、5 个 schema 与 5 个测试文件。
- **独立重跑**：borrow 切片 `113 passed`；全量后端 `507 passed`；`git diff --check` 干净；工作树干净，`data/borrow-tasks.sqlite3` 被 `.gitignore` 正确忽略。
- **自建 25 断言探针**（SQLite 在 /tmp、ephemeral 端口进程内服务器，脚本已在 /tmp 销毁）：A→B→C→A 轮转；resolved-`unknown` 标记跨重启保留（round-1 finding-1 回归点）与 pending 孤儿 fail-closed 双路径；**双线程探针证明 executor 调用期间另一线程可完成 store 写入**（不持有 SQLite 锁/事务，amendment §2）；含 pending 行的 `COALESCE(finished_at, dispatched_at, scheduled_at) DESC, id DESC` 排序正确、cursor 跨页不重不漏；DELETE/PATCH/HEAD/OPTIONS → 405 JSON 且 HEAD 无 body；非 borrow POST 与未知 borrow 子路径 → 404 JSON；17000 字节可选 body → 413 且任务状态未变；未知 JSON 键 → 400 指名；`limit=1.5`/垃圾 cursor → 400；disabled 运行时恰写一行脱敏 `execution_disabled`（无伪造成功）；`APP_BORROW_EXECUTOR=live` 被 `ValueError` 拒绝。

## 验收映射结论

durable SQLite 任务/尝试/设置、Decimal 字符串与微秒时间、创建即 `borrowing`、两阶段调度、崩溃 fail-closed、生命周期/乐观版本/错误词汇/正文上限/frozen 路由契约、脱敏 `execution_disabled` 账本、隔离性与零网络/零签名/零凭据证明均满足冻结契约；现有 snapshot/private 只读契约未被破坏（507 全量绿 + diff 级确认）。嵌入预审 round-1 的四项 findings 已逐一验证修复且本轮复核无新问题。仅一项 P3 观察（见 findings），不构成返工。

当前 Session ID: session_e45eb13b-9589-405c-95c5-fbe7a4723e82
Session ID 来源: transcript_path（后台任务 output 路径位于 ~/.kimi-code/sessions/…/session_e45eb13b-…/ 下）
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/30-review-1-backend.md
本地北京时间: 2026-07-19 20:30:10 CST
下一步模型: bookkeeper（人工/记账会话）
下一步任务: 将本回复原样保存为 30-review-1-backend.md 并记账；推进 Task B Review-1（Claude-GLM fresh session），随后进入 stage Review-2
{
  "schema_version": 1,
  "stage_id": "2026-07-real-borrow-execution-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "40efb028ead50d667bb32dbe10e9af6a7d77409e:a3e3a9bcd8b6233b581f4587e88b64478cc9cb356b1d40b1cddc9a1f3c33d3bc",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "reports/agent-runs/2026-07-real-borrow-execution-v1/review-1-task-A-by-kimi.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/00-task.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/10-design.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/11-adr.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/13-user-decisions-and-contract-amendment.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/status.json",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/20-implementation-backend.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/60-test-output-backend.txt",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.raw-output.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round1.fix-note.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/embedded-review-A-round2-retry-1.raw-output.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/61-r4-diff-reconciliation.txt",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/62-pre-review-validation.txt",
    "workflows/templates/stage-delivery.yaml (review-1 node)",
    "schemas/review-verdict.schema.json",
    "git diff 6c870414a951550331676fe5db0c4e3a46aab555..40efb028ead50d667bb32dbe10e9af6a7d77409e (full, incl. backend/app/server.py, backend/config.py, .gitignore)",
    "backend/borrow_tasks/__init__.py",
    "backend/borrow_tasks/domain.py",
    "backend/borrow_tasks/executor.py",
    "backend/borrow_tasks/scheduler.py",
    "backend/borrow_tasks/service.py",
    "backend/borrow_tasks/store.py",
    "schemas/api/borrow-tasks/task.schema.json",
    "schemas/api/borrow-tasks/task-list.schema.json",
    "schemas/api/borrow-tasks/log-page.schema.json",
    "schemas/api/borrow-tasks/scheduler-settings.schema.json",
    "schemas/api/borrow-tasks/error.schema.json",
    "backend/tests/borrow_paper_executor.py",
    "backend/tests/test_borrow_domain.py",
    "backend/tests/test_borrow_store.py",
    "backend/tests/test_borrow_scheduler.py",
    "backend/tests/test_borrow_executor.py",
    "backend/tests/test_borrow_api.py",
    "independent re-run: pytest borrow slice 113 passed; full backend/tests 507 passed; git diff --check clean",
    "independent 25-assertion probe (SQLite in /tmp, in-process server on ephemeral loopback port): round-robin order, restart recovery both halves, two-thread no-store-lock-during-executor proof, COALESCE ordering with pending row and disjoint cursor pages, 405/HEAD/404/413/400 error surfaces, sanitized execution_disabled row, config live-executor rejection"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "Round-robin restarts from the first eligible task when the cursor task itself is ineligible",
      "file": "backend/borrow_tasks/scheduler.py",
      "line": 33,
      "evidence": "select_next_task looks up cursor_task_id only within the eligible list; when the last-dispatched task is now paused/blocked/completed/deleted, cursor_seq stays None and selection returns eligible_tasks[0] instead of the task strictly after the cursor's creation_seq. test_select_next_task_cursor_points_at_removed_task pins this as intended semantics, and the two embedded rounds did not flag it.",
      "impact": "A single-tick fairness deviation in that edge (the first eligible task goes once earlier than strict after-cursor order); the cursor still advances transactionally, no task is persistently starved or double-dispatched, and the A→B→C→A acceptance, skip semantics, and durability invariants are unaffected. Not a violation of the frozen acceptance criteria.",
      "recommendation": "No A+B change. For Boundary C consider resolving the cursor task's creation_seq from the tasks table (not only the eligible list) so rotation continues strictly after the last-dispatched task even when it is ineligible."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Accepted per breakdown §6.3: ordinary runtime appends one execution_disabled ledger row per dispatched tick, so the local SQLite ledger grows without a retention cap; retention is a future decision, not to be invented in A+B.",
    "Accepted per breakdown §6.3: a crash-orphaned pending attempt blocks its task until operator deletion or Boundary-C reconciliation (fail-closed by design).",
    "Latent for Boundary C: BorrowScheduler._loop does not catch executor exceptions, so a raising future live adapter would end the scheduler thread; unreachable in A+B because the only runtime executor (DisabledBorrowExecutor) cannot raise, but the C adapter needs an exception policy.",
    "run() constructs BorrowTaskService at the real data/borrow-tasks.sqlite3 path even under process-level tests that stub build_server; the file is gitignored and the behavior is deliberate to keep out-of-scope test_service_health tests green (implementation report items 5-6)."
  ],
  "next_action": "continue"
}