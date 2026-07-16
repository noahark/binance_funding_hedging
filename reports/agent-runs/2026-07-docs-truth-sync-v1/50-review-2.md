# Review-2 Report (final gate) ROUND 4 — 2026-07-docs-truth-sync-v1

> Bookkeeper capture (this round: Fable5 acting bookkeeper, user-directed): Codex
> read-only codex exec (resumed session 019f6a94-9685-7f80-8b64-cb7ba5798daf), no
> file write. Raw round-4 output recovered verbatim below from the local codex
> session rollout (~/.codex/sessions/2026/07/16/rollout-2026-07-16T18-59-10-*.jsonl),
> per RC9 no-lossy-capture rule. Round-1 at 51-review-2-round1.md; round-2 at
> 52-review-2-round2.md; round-3 archived verbatim at 53-review-2-round3.md.
> VERDICT: REWORK (F9 P1, F10 P1, F11 P2, F12 P2) -> human_escalation_required.
> User resolved the escalation by re-routing: Fable5 authors the round-4 fix,
> opus4.8 reviews next (user message, 2026-07-16 ~23:00 CST).

---

Review-2 Round 4 结论：`REWORK`，进入 `human_escalation_required`。

固定指纹、pre-review validator、71 项后端测试、80 项前端自检及文件边界均通过；F7 的跨请求同版本承诺已删除，F8 的 diff-check 更正可复现。但仍有两项 P1 契约偏差：

- 离线模式不创建 `PublishedState`，但合同仍将离线 `published_version: 0` 描述为内部 `PublishedState` 修订号。
- 实际响应可暴露 `refresh_command_expired:<symbol>`，合同的 wire-visible warnings 清单却遗漏它。

此外，handoff 正文仍停留在 Round 3 escalation/旧 intake next steps，`status.json` 也未登记 Round-3 fix author 及已完成模型的 session receipts。

仓库未修改，工作树保持干净。由于本轮已经超过返工上限且用户只授权了这一轮，不能自动继续修复。

当前 Session ID: 019f6a94-9685-7f80-8b64-cb7ba5798daf  
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)  
原始输出路径: unavailable (只读 reviewer 未写文件；bookkeeper 应将本响应原样保存至 reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md)  
本地北京时间: 2026-07-16 22:57:13 CST  
下一步模型: human  
下一步任务: 决定是否再次明确授权限定修复；否则阶段保持 human_escalation_required

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "final_reviewer",
  "model": "codex",
  "verdict": "REWORK",
  "diff_fingerprint": "a4322847d831105d587a36f6f5d305586d10c264:06ea8e1a2bf7e8ffdb4c9bb7df626e6d91b5d0cca7712f824b07874726a15604",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/OpenAI participated in the earlier read-only direction audit but did not author design, development breakdown, implementation, or fixes. The reviewer provider is isolated from the Zhipu GLM implementation/fix provider and the Anthropic designer/bookkeeper provider.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml review-2 section",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/58-dispatch-review-2-codex-round4.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/11-adr.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/62-validate-pre-review.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/status.json",
    "reports/agent-runs/ACTIVE.json",
    "git diff --binary 127a600281d60b7332be8aeb9552740a5e8c3254..a4322847d831105d587a36f6f5d305586d10c264",
    "git diff --binary 568fd4160b67d3b73303134d6f078a6a59bb93d9..a4322847d831105d587a36f6f5d305586d10c264",
    "docs/api/public-market-contract.md",
    "docs/product/PRD.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/development/DEVELOPMENT_GUIDE.md",
    "docs/planning/DECISIONS.md",
    "reports/follow-ups/README.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
    "schemas/api/public-market/snapshot.schema.json",
    "schemas/api/public-market/funding-history.schema.json",
    "schemas/api/public-market/symbol-snapshot.schema.json",
    "backend/app/server.py",
    "backend/services/snapshot_service.py",
    "backend/domain/snapshot.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "frontend/self-check.js"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "离线 published_version 仍被错误描述为不存在的 PublishedState 修订号",
      "file": "docs/api/public-market-contract.md",
      "line": 323,
      "evidence": "合同第 323-332、344-348 行无条件称 published_version 是投影 row 所用内部 PublishedState 的修订号，并称 row 选自同一 PublishedState.snapshot。可是 backend/services/snapshot_service.py:331-332、373-393 的离线路径调用 get_snapshot 后直接组装响应，固定 published_version=0；它不创建 PublishedState。独立运行离线端点得到 HTTP 200、published_version=0，同时 service._published_state 仍为 None。",
      "impact": "合同仍把离线 sentinel 0 表述成真实发布状态修订号，并暗示离线 row 拥有不存在的 PublishedState 关联；这与本 stage 的文档追平代码真值目标冲突。",
      "recommendation": "仅修改人工合同，明确区分：live 模式的 published_version 是实际 PublishedState 修订号；offline 模式的 0 只是离线约定值，不代表创建了 PublishedState。row-from-same-PublishedState 的事实只适用于 live 路径；继续保留 full snapshot wire 无可比较字段、无跨请求相等保证。"
    },
    {
      "severity": "P1",
      "title": "合同的 wire-visible warnings 清单遗漏 refresh_command_expired",
      "file": "docs/api/public-market-contract.md",
      "line": 372,
      "evidence": "合同第 372-376 行声称 wire-visible values 只有四类 source warning、refresh_deadline_exceeded 和 worker_not_running。backend/services/snapshot_service.py:1389-1392 在命令排队期间过期时设置 refresh_status=timeout 与 refresh_command_expired:<symbol>；第 351-353 行会把 cmd.warnings 原样写入响应。独立组合该真实分支与序列化路径得到 HTTP 200、refresh_status=timeout、warnings=['refresh_command_expired:BTCUSDT']。",
      "impact": "客户端会收到合同宣称的 wire-visible 集合之外的诊断 token，F4 的 warnings 契约仍未完全与服务器一致。",
      "recommendation": "在人工合同的 timeout 和 warnings 说明中加入 refresh_command_expired:<symbol>，区分排队后过期与端点等待未结算产生的 refresh_deadline_exceeded；不要修改服务端或 schema。"
    },
    {
      "severity": "P2",
      "title": "F8 handoff 正文同步仍不完整",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md",
      "line": 47,
      "evidence": "Recovery Header 已指向 review-2 Round 4，但 Current State 第 47-58 行仍记录 human_escalation_required、Round-3 head 568fd41 和待用户决策；第 60-88 行仍是 intake-era What Landed/Open Decisions/Next Steps 与 14:33 footer。当前 status.json 已是 review_2、head a432284，ACTIVE.json 已是 review-2-round-4。",
      "impact": "快速恢复头可用，但完整 handoff 对审计者呈现互相冲突的当前阶段、受审 head 和下一步。",
      "recommendation": "由 bookkeeper 完整同步 Current State、What Landed、Open Decisions、Next Steps 和 footer 至 Round-4 终审结果；不要只更新 Recovery Header。"
    },
    {
      "severity": "P2",
      "title": "机器状态未完整登记 Round-3 fix author 与已完成模型 receipts",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/status.json",
      "line": 47,
      "evidence": "session_receipts 仅含 bookkeeper；已完成的 claude_glm implementation/fix 和 Kimi review-1 均未登记 unavailable reason 与 raw artifact path。顶层 fix_authors 数组也只列 Round 1/2，未列本次 F7 的 Round-3 claude_glm fix，虽然 review_rounds 与 40-fix-report.md 已记录该事实。",
      "impact": "人工材料足以确认 reviewer isolation，但权威机器状态不能完整复现作者身份和执行收据，削弱后续自动身份门与审计导航。",
      "recommendation": "由 bookkeeper补录 Round-3 fix author，并为已完成执行增加 session receipts；无法验证 Session ID 时按 AGENTS.md 写 unavailable 原因和原始输出路径，禁止猜测 ID。"
    }
  ],
  "required_fixes": [
    "修订 docs/api/public-market-contract.md，将 live PublishedState revision 与 offline published_version=0 sentinel 明确分开，并把 row-from-same-PublishedState 事实限定到 live 路径。",
    "修订同一合同的 timeout/warnings 说明，加入实际可序列化的 refresh_command_expired:<symbol> token。",
    "由 bookkeeper 完整同步 70-handoff.md 正文及 footer，并补齐 status.json 的 Round-3 fix author 与已完成模型 session receipts。",
    "若用户再次明确授权超限修复，fix author 应向 40-fix-report.md 追加 Round-4 finding-to-fix 映射；bookkeeper 随后提交、重算标准指纹、保存 pre-review validator 与测试输出，并按新授权决定是否需要新的 review-1。Round-4 的 review-1 waiver 不自动延伸到后续轮次。"
  ],
  "residual_risks": [
    "F1、F2、F3、F5、F6 已保持关闭；F4 因遗漏 refresh_command_expired 尚未完全关闭，F7 因离线 sentinel 语义尚未完全关闭。",
    "funding-history.schema.json:34 与 symbol-snapshot.schema.json:5/:39 的既有 prose drift 已在合同中披露并保持 deferred；本 stage 不应修改 schema。",
    "独立重算 fingerprint 完全匹配；pre-review validator PASS；71 项目标后端测试、80 项前端自检及固定范围 diff-check 均通过；禁改产品/Harness-track 路径没有变化。",
    "用户授权的 Round-4 review-1 waiver 将导致 pre-accept 的已知 fingerprint mismatch；若未来继续，必须由用户明确决定新的审查路由，不得伪造 review-1 指纹。"
  ],
  "fix_start_prompt": "Human-gated repair prompt for Review-2 Round-4 REWORK, stage `2026-07-docs-truth-sync-v1`. Reviewed fingerprint: `a4322847d831105d587a36f6f5d305586d10c264:06ea8e1a2bf7e8ffdb4c9bb7df626e6d91b5d0cca7712f824b07874726a15604`. Raw Round-4 review narrative and strict verdict JSON must be captured verbatim at `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`; preserve the committed Round-3 raw review before replacement. Do not dispatch automatically: this stage already exceeds max_rework=3, and the prior user authorization covered only the bounded F7 Round-4 fix/review.\n\nFinding F9 P1: `docs/api/public-market-contract.md:323-348` unconditionally defines `published_version` as the revision of an internal `PublishedState` and says the row comes from that state's snapshot. In `backend/services/snapshot_service.py:331-332,373-393`, offline mode creates no PublishedState, returns a synchronously built/cached row, and emits `published_version: 0` while `_published_state` remains None. Fix the human contract only: live mode uses the actual PublishedState revision; offline 0 is a sentinel/convention and does not represent a PublishedState. Limit the row-from-same-PublishedState statement to live mode. Preserve the correct statements that full snapshot v1 exposes no comparable version and independent HTTP requests have no client-verifiable equality guarantee.\n\nFinding F10 P1: `docs/api/public-market-contract.md:372-376` gives an incomplete wire-visible warnings list. `backend/services/snapshot_service.py:1389-1392` creates `refresh_command_expired:<symbol>` when a queued command expires, and `:351-353` serializes it on the HTTP payload. Add that token to the timeout/warnings contract and distinguish it from `refresh_deadline_exceeded`. Do not edit server or schemas.\n\nFinding F11 P2: active `70-handoff.md:47-88` remains at Round-3 escalation and intake-era next steps despite the Round-4 Recovery Header/status. Bookkeeper must synchronize the complete body and footer.\n\nFinding F12 P2: active `status.json.session_receipts` contains only bookkeeper and `fix_authors` omits the Round-3 F7 claude_glm fix. Bookkeeper must add the author and completed execution receipts using verified IDs or explicit unavailable reasons/raw paths; never invent identifiers.\n\nFix-author allowed files: `docs/api/public-market-contract.md` and append-only Round-4 content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Bookkeeper-only files: active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, `62-validate-pre-review.txt`, `ACTIVE.json`, and review/dispatch evidence. Forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker stage files; any product behavior, endpoint, schema, deployment, merge, or push change.\n\nRun exactly after an authorized fix:\n1. `rg -n 'published_version|PublishedState|Offline|sentinel|refresh_command_expired|refresh_deadline_exceeded|wire-visible|cross-request' docs/api/public-market-contract.md backend/services/snapshot_service.py`\n2. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`\n3. `node frontend/self-check.js`\n4. `python3 -m json.tool reports/agent-runs/2026-07-docs-truth-sync-v1/status.json >/dev/null`\n5. `git diff --check`\n6. `git diff --name-only` and verify fix-author changes are only the contract plus append-only fix report, while bookkeeper changes are limited to authorized stage evidence files.\n\nAcceptance criteria: the contract explicitly says live revision versus offline 0 sentinel/no PublishedState; no statement applies row-from-same-PublishedState to offline mode; `refresh_command_expired:<symbol>` is documented as wire-visible; full-snapshot no-field/no-cross-request guarantee remains; 71 backend tests and 80 frontend checks pass; handoff body matches the current phase/head/verdict; status records Round-3 fix authorship and completed receipts. Append exact before/after mapping and command outputs to `40-fix-report.md`. Then stop for bookkeeper reconciliation. Only if the human explicitly authorizes another over-limit cycle may the bookkeeper commit, recompute the fingerprint, run and preserve `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`, and prepare the newly authorized review route. The prior Round-4 review-1 waiver must not be reused without explicit authorization.",
  "next_action": "human_escalation_required"
}
```
