全部允许命令独立复跑通过且与记账证据一致。审查完毕，输出 verdict。

# Boundary C Task C — Formal Review-1 Round 2（Kimi / first_reviewer）

## 审查范围与身份核验（本会话实际执行）

- 固定范围 `c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81`。当前工作树 HEAD（`abd40ea`）晚于被审 head，经 `git diff --stat 87c19273..HEAD` 核实其增量仅为 stage 记账文件（status.json、70-handoff、round-2 prompt/dispatch、60-test-output、ACTIVE.json），未纳入产品 diff；工作树产品代码与被审 head 一致。
- 指纹独立重算：本会话实际执行 `git diff --binary c9df145..87c19273 -- . ":(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json" | shasum -a 256`，得 `29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162`，与 prompt/status.json 固定值逐字符一致。`git diff --check` clean。
- 必读工件逐项直接读取（AGENTS.md、workflow YAML test/review-1/fix 段、verdict schema、code-reviewer skill、parallel-development-mode.md R11-R12、status.json 全文、00-task/10-design/11-adr/12-breakdown/14-synthesis、上游 06-direction-synthesis、20-implementation 及其 bookkeeper 审计、30-review-1 及其 intake、40-fix-report 及其审计、fix-4/5/6 全部 prompt+dispatch、60-test-output、70-handoff、main-sync-authorization、Task H 的 50-review-2 与 80-user-acceptance、api-samples 证据索引与四个 raw 合同切片），并逐文件审查固定 diff 内全部产品代码、schema、前端、测试与 Harness 改动。
- Round-1 REWORK 仅作历史证据；F1/F2/F3 与 BK-R1-FIX4-001/002、BK-R1-FIX5-001 均在代码层独立重查，未继承 round-1 结论。

## 独立复跑（非采信报告）

- 核心十文件套件：**331 passed**；全量 backend：**630 passed**；`node frontend/self-check.js`：**97 [PASS] items，全部自检通过**；Harness 套件：**128 passed**；`py_compile`（九模块）：exit 0；compare 哨兵：**11/11 passed**。与 60-test-output.txt 的 post-sync 证据逐项一致。

## 十一项审查重点结论

1. **唯一 live write：通过。** 唯一 borrow POST 出口为 `portfolio_margin_borrow_client.py:150 post_margin_loan`；allowlist 仅 `POST /papi/v1/marginLoan` 与 `GET /papi/v1/margin/marginLoan` 两对，host 硬编码；`_require_whitelisted` 先于任何签名原语；唯一 HMAC 出口 `binance_signing.py`，签名即所发字节；`_send` 单次传输无 retry；专用 `BINANCE_BORROW_API_KEY/SECRET`；无第二 POST、无错误 URL、无敏感响应泄漏（`raw_body` 仅存未读，见 F4）。
2. **fail-closed 边界：通过。** 非法 `APP_BORROW_EXECUTOR` 在 config load 硬失败；live+缺凭证由 `_dispatch_one`（service.py:396）与 executor 凭证门（live_borrow_executor.py:259）双层拦截、零签名流量、`block_reason=borrow_credentials_missing`；ownership `flock(LOCK_EX|LOCK_NB)` 先于 scheduler；`execution_enabled` 默认 0；`live_authorized` 仅授权标志，成功只认规范化 `tranId`。
3. **意图原子落盘与分类：通过。** `insert_pending_attempt` 同事务复查全部 gate 并插入 pending/推进游标/置 marker，失败谓词零行零 POST；分类矩阵与冻结表逐项一致；unknown 只留标记不重发。
4. **reconciliation envelope 严格性：通过。** 严格消费 rows/total envelope；`total` 缺失/bool/非int/负值或与 raw 行数不等（多于或少于）均 fail closed；五字段行契约任一 malformed 整读失败；known-ID 验证 txId==tranId；response-less 候选 timestamp 必须落在派发窗口内；唯一 CONFIRMED 才证明成功。
5. **跨任务归属：通过。** `attribution_is_unique`（store.py:920）在候选 txId 已被认领或他任务存在同资产 Decimal 等额 pending/unknown attempt 时保持 blocked；非歧义正例仍可收敛（test_borrow_scheduler.py:521 双任务实证）。
6. **418/429/-1003 与 manual re-arm：通过。** 418 → 300s 最低冷却 + `requires_rearm=1`；`set_execution_enabled(True)` 在冷却未到期时只置位不清除（store.py:485-525）；reconcile GET 418 经 `ReconcileOutcome.requires_rearm` 持久化（test_borrow_scheduler.py:551 实证）；启动恢复不触碰 settings，重启/普通 cooldown 清理/Start 均不可绕过。
7. **F3 修复：通过。** 启动恢复幂等把 pending 孤儿转为 `resolved/unknown/crash_orphan_responseless`、step 0、+5s 首读，进入既有 +5/+15/+60/+300/+900 队列；`resolve_reconciliation_success` 同时收尾原 pending 行；成功/耗尽/跨重启计数与 marker 生命周期一致（store.py:202-229、456-483、824-887；test_borrow_store.py:606-712、test_borrow_scheduler.py:486 零第二 POST 实证）。
8. **F1/F2/Fix-6：通过。** 三处过期 no-real-borrow 文案已删除且 self-check 负向断言在位；创建前预览显示资产/数量/次数/BigInt 目标总量/真实当前间隔；`createBorrowTask` 在未加载、加载失败与 loaded→503（catch 作废缓存，index.html:2288）下均零 task POST，成功路径恰好一次 POST（self-check 66b 四相位实证）。
9. **契约与守卫：通过。** 三条 `/api/borrow-execution/*` 路由 + `borrow-execution/v1` schema（additionalProperties:false）经 HTTP 级测试验证；五个静态守卫均以精确文件名收窄并保留反向断言；启动观测仅输出模式枚举、owner 布尔与两个恢复计数，credential 值不出现在 stderr（test_service_health.py 实证）。
10. **Harness extractor sync：通过。** Task H 已经 review-2 ACCEPT + 用户验收落 main；sync 进本 stage 的 diff 仅改 `extract_last_json_object` 单 hunk + R12 文档措辞，receipt/Session-ID/identity/fingerprint/clean-worktree/historical-compare 门禁零改动（128 协议测试全绿 + compare 11/11 佐证）；findings-bearing top-level verdict 可正确提取（Task H review-2 的 14 探针与本 stage 五-findings 工件回放实证）。产品运行语义无变化。
11. **报告与 committed code 一致：通过。** post-sync 331/630/97/128、compare 11/11、py_compile 均经本会话独立复跑一致，非因全绿推定。

## Findings（延续历史 P3，非阻塞）

F4/F5 经本会话核实仍存在：`raw_body` 字段（portfolio_margin_borrow_client.py:68）仍无读取点；`.env.example` 仍未收录 `BINANCE_BORROW_API_KEY/SECRET`。两者均为 round-1 定级的 P3 可选打磨，不构成门禁，不升级不降级。

## Verdict 理由

三项 round-1 P1（F1/F2/F3）与全部 bookkeeper 残留 P1（BK-R1-FIX4-001/002、BK-R1-FIX5-001）在固定 committed diff 上逐一独立确认闭合，修复未引入新缺陷；冻结契约（AC #1-#15、ADR-001/004/006、D1-D10、breakdown §3-§9）与证据完整；固定 diff 无 P0/P1。verdict：**ACCEPT**，`next_action: continue`（进入 review-2 终审）。

当前 Session ID: 1f494594-8f80-4e81-be7b-18a261138285（本会话工具输出路径中出现的本地 Kimi CLI 会话 id；可由 operator 核验后记入 status.json.session_receipts）
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1-round-2.md
本地北京时间: 2026-07-21 20:55:17 CST
下一步模型: bookkeeper
下一步任务: intake 本 round-2 review 工件并解析 verdict，记录 review_1 结果后按 review-2 路由规则准备终审 dispatch（Codex 优先；若设计冲突则按 strong-reviewer 披露规则处理），更新 status.json 与 70-handoff.md

{
  "schema_version": 1,
  "stage_id": "2026-07-real-borrow-boundary-c-v1",
  "role": "first_reviewer",
  "model": "kimi-code/kimi-for-coding",
  "verdict": "ACCEPT",
  "diff_fingerprint": "87c19273c3f488cf6d9ca80f8541704bb198cb81:29f0f587f3ef0dcc01261fa84047ff56fdbf717dcaa7cf20dddb13495229c162",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Kimi previously supplied an independent design review at reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md (verdict REWORK, synthesized in 14-design-review-synthesis.md). This round-2 formal review-1 re-examined the new fixed committed diff independently in a fresh read-only session; provider isolation from the zhipu_glm implementation/fix author remains intact.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml (test/review-1/fix sections)",
    "schemas/review-verdict.schema.json",
    "agents/skills/code-reviewer.md",
    "docs/parallel-development-mode.md (R11-R12 and v0.5 dispatch rules)",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md",
    "reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/20-implementation-bookkeeper-audit.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.bookkeeper-intake.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/40-fix-report.bookkeeper-audit.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-4.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-4.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-5.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-5.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-6.prompt.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/task-C-bookkeeper-fix-6.dispatch.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/70-handoff.md",
    "reports/agent-runs/2026-07-real-borrow-boundary-c-v1/main-sync-authorization.md",
    "reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md",
    "reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/80-user-acceptance.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/evidence-index.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/margin-account-borrow.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/query-margin-loan-record.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/portfolio-margin-error-codes.md",
    "reports/api-samples/2026-07-real-borrow-boundary-c-v1/20260720T150836Z/raw/portfolio-margin-general-info.md",
    "git diff --binary c9df14591ac4ca00977ce0e4d80c0950aae44c19..87c19273c3f488cf6d9ca80f8541704bb198cb81 -- . ':(exclude)reports/agent-runs/2026-07-real-borrow-boundary-c-v1/status.json' (fingerprint independently recomputed and matched; git diff --check clean)",
    "backend/services/binance_signing.py",
    "backend/services/portfolio_margin_borrow_client.py",
    "backend/services/live_borrow_executor.py",
    "backend/services/private_client.py (diff)",
    "backend/borrow_tasks/domain.py",
    "backend/borrow_tasks/executor.py",
    "backend/borrow_tasks/ownership.py",
    "backend/borrow_tasks/scheduler.py",
    "backend/borrow_tasks/service.py",
    "backend/borrow_tasks/store.py",
    "backend/app/server.py",
    "backend/config.py (diff)",
    "schemas/api/borrow-tasks/execution-status.schema.json",
    "schemas/api/borrow-tasks/task.schema.json (diff)",
    "frontend/index.html (diff)",
    "frontend/self-check.js (diff)",
    "backend/tests/test_binance_signing.py",
    "backend/tests/test_portfolio_margin_borrow_client.py",
    "backend/tests/test_live_borrow_executor.py (spot-checked reconcile negatives/positives)",
    "backend/tests/test_borrow_store.py (spot-checked F3/count/418 suites)",
    "backend/tests/test_borrow_scheduler.py (spot-checked orphan/attribution/418 tests)",
    "backend/tests/test_borrow_api.py (diff)",
    "backend/tests/test_config.py (diff)",
    "backend/tests/test_private_client.py (diff)",
    "backend/tests/test_private_account_v1.py (diff)",
    "backend/tests/test_service_health.py (diff)",
    "scripts/validate-stage.py (diff, extract_last_json_object Task H hunk)",
    "docs/parallel-development-mode.md (diff, R12 wording)",
    "independent re-run: 10-file Boundary C suite (331 passed); python3 -m pytest backend/tests -q (630 passed); node frontend/self-check.js (97 [PASS] items, exit 0); python3 -m pytest scripts/tests -q (128 passed); python3 -m py_compile over nine product modules (exit 0); python3 scripts/test-validate-all-stages-compare.py --repo-root . (11/11 passed)"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "BorrowHttpResponse.raw_body is retained but never read (carried over from round 1, non-blocking)",
      "file": "backend/services/portfolio_margin_borrow_client.py",
      "line": 68,
      "evidence": "Re-verified this round: the dataclass field raw_body is still written on every transport call (line 147) and a grep over backend/ finds no reader outside the declaration. Round-1 F4; the fix author explicitly left it as non-gating polish.",
      "impact": "No leak today: the raw private response body is never persisted to the ledger and never logged. It remains unnecessary transient surface that could tempt future logging of full private bodies, which the design forbids.",
      "recommendation": "Drop the field, or add a comment justifying its retention; keep it out of any persisted or logged evidence. Non-blocking; may be handled in a later polish pass."
    },
    {
      "severity": "P3",
      "title": ".env.example does not document the new dedicated borrow credential names (carried over from round 1, non-blocking)",
      "file": ".env.example",
      "line": null,
      "evidence": "Re-verified this round: grep of .env.example finds no BINANCE_BORROW_API_KEY or BINANCE_BORROW_API_SECRET entry (only the unrelated pre-existing BINANCE_BORROW_CHECK_MAX_CALLS). The development breakdown file boundary lists .env.example as the documentation location for the new env names. Round-1 F5.",
      "impact": "The operator cannot discover the dedicated credential variable names from the example env file; minor documentation gap only, no runtime effect.",
      "recommendation": "Add both variable names with empty values and a short comment (documentation only, no secrets). Non-blocking; may be handled in a later polish pass."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "The +5/+15/+60/+300/+900s reconciliation window is a local conservative policy with no published Binance propagation SLA; a loan that becomes visible only after the fifth read leaves the task in terminal reconciliation_exhausted by design (operator exit is delete).",
    "The sidecar flock guarantees one execution owner per database path, but two different database paths on one machine are outside its scope (accepted by design).",
    "attribution_is_unique is deliberately more conservative than a timestamp-overlap gate: a competitor task's attempt keeps its result_category='unknown' even after delete/exhaustion, so a same-asset Decimal-equal-amount task can stay blocked until its own reads exhaust. This is the frozen fail-closed cross-task ambiguity behavior, not a defect.",
    "P3 findings (raw_body retention; .env.example credential-name documentation) are optional polish and are not gate-blocking."
  ],
  "next_action": "continue"
}
