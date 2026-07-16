# Review-2 Report (final gate) ROUND 5 — 2026-07-docs-truth-sync-v1

> Bookkeeper capture: Codex read-only codex exec (resumed session 019f6a94), no file
> write. Raw round-5 output recovered verbatim below. Rounds 1-4 raw at 51-/52-/53-/54-.
> VERDICT: REWORK -> human_escalation_required (rework 5, no 6th fix authorized). RC9.

---

Review-2 Round 5 结论：`REWORK`，重新进入 `human_escalation_required`。

固定指纹、validator、71 项后端测试、80 项前端自检和文件边界均通过。F9 的版本字段定义与 F10 的 `refresh_command_expired` 已修正，但仍有两项 P1：

- 合同仍无条件称离线 row 来自 published state，实际离线模式同步构建/缓存 snapshot，不创建发布状态。
- 新增的 `base_raw_unavailable` HTTP cold-path 承诺不可达：首次发布前公开端点直接返回 503；该 token 只存在于直接调用内部 command handler 的防御分支。

此外，handoff/status 正文仍记录“路由待用户决定”，与已经派发 Codex Round 5 的 Recovery Header、ACTIVE 和当前用户指令矛盾。

仓库未修改，工作树干净。

当前 Session ID: 019f6a94-9685-7f80-8b64-cb7ba5798daf  
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)  
原始输出路径: unavailable (只读 reviewer 未写文件；bookkeeper 应将本响应原样保存至 reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md)  
本地北京时间: 2026-07-16 23:38:19 CST  
下一步模型: human  
下一步任务: 决定是否授权第六次限定修复；否则阶段保持 human_escalation_required

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "final_reviewer",
  "model": "codex",
  "verdict": "REWORK",
  "diff_fingerprint": "e214d6f819d76daa3b85865c1021b5aa2497ee95:d93ff6d4be65eda9882a6145e69a8dfcb346b854af38f40da79ff49f5cdf965e",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/OpenAI participated in the earlier read-only direction audit but did not author design, development breakdown, implementation, or fixes. OpenAI is provider-isolated from the Zhipu GLM implementation/fix author and the Anthropic Fable5 Round-4 fix author.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml review-2 section",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/59-dispatch-review-2-codex-round5.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/11-adr.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/54-review-2-round4.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/62-validate-pre-review.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/status.json",
    "reports/agent-runs/ACTIVE.json",
    "git diff --binary 127a600281d60b7332be8aeb9552740a5e8c3254..e214d6f819d76daa3b85865c1021b5aa2497ee95",
    "git diff --binary a4322847d831105d587a36f6f5d305586d10c264..e214d6f819d76daa3b85865c1021b5aa2497ee95",
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
      "title": "离线 row 来源仍被无条件描述为 published state",
      "file": "docs/api/public-market-contract.md",
      "line": 306,
      "evidence": "第 306-309 行称 projected row always comes from the currently available published state；第 358-361 行又称 row always taken from latest published state；第 392 行称 row projected from the published state。可是 backend/services/snapshot_service.py:331-332,373-393 的离线路径直接调用 get_snapshot，投影同步构建或 60 秒缓存的 snapshot，并保持 _published_state=None。合同新加的第 328-330、351-353 行已经正确承认离线不创建 PublishedState，因此这些无条件 row-source 句子与同一合同及代码冲突。",
      "impact": "API 使用者仍可能把离线响应理解为 last-good PublishedState 投影，而实际离线数据来自同步 fixture build/cache。F9 的 published_version 字段已修，但相邻 row-source 契约尚未完全 mode-dependent。",
      "recommendation": "仅修改人工合同：把总述、refresh_status 总注和 row 字段改为 mode-dependent。Live row 来自 latest PublishedState；offline row 来自同步构建/缓存的 snapshot。保留 live-only same-PublishedState、offline 0 sentinel 和无跨请求保证。"
    },
    {
      "severity": "P1",
      "title": "合同把内部不可达的 base_raw_unavailable 分支误写成公开 HTTP cold-path outcome",
      "file": "docs/api/public-market-contract.md",
      "line": 371,
      "evidence": "第 371-389 行声称公开 symbol-snapshot 的 200 timeout 响应可能因 no base snapshot yet 携带 base_raw_unavailable:<symbol>。实际 get_symbol_snapshot 在 backend/services/snapshot_service.py:333-335 发现 _published_state=None 时立即返回 503 snapshot_not_ready，尚未提交 command。首次成功 tick 又在 :998 先设置 _base_raw，随后才在 :1016/:1564 发布 PublishedState；仓库中没有把 _base_raw 重置为 None 的路径。因此任何能通过 HTTP precondition 并提交 command 的正常状态都已有 _base_raw。test_not_ready_returns_503_before_first_publish 也断言公开冷启动为 503。base_raw_unavailable 仅由 test_base_raw_none_click_does_no_fetch_raw 直接调用内部 _handle_refresh_command 触发，不是当前 HTTP wire outcome。独立运行公开冷启动请求得到 503 {'error':'snapshot_not_ready'}。",
      "impact": "合同现在承诺客户端可能收到实际不可达的 200 timeout/token，并与同一端点的真实 503 failure matrix 冲突。这是本轮修复新引入的过度承诺。",
      "recommendation": "从公开 timeout 原因和 wire-visible warnings 清单删除 base_raw_unavailable:<symbol>；如需保存该事实，只能明确标为内部防御性 command-handler diagnostic、当前 HTTP 路由前置条件下不可达。继续保留实际可达的 refresh_command_expired、refresh_deadline_exceeded、worker_not_running 和 source warnings。"
    },
    {
      "severity": "P2",
      "title": "Round-5 路由决策未完整同步到 handoff 与机器状态",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md",
      "line": 18,
      "evidence": "Recovery Header 第 9-15 行已记录用户选择 Codex、路由约束已解，但第 18-23 行仍称用户待决；Current State 第 62、72 行仍写 round 5 待派发/待用户决策，Open Decisions 与 Next Steps 第 89-109 行也要求用户裁决路由。status.json.current_phase 仍是 awaiting-review-routing，human_escalation.resolved_by 仍称 routing pending，updated_at 为 23:20；与此同时 ACTIVE.json 已是 review-2-round-5-codex-dispatched，status.review_2.note/next_action 也记录 Codex 已选定。",
      "impact": "启动头仍可引导执行，但同一权威 handoff/status 对当前路由、是否已派发和 review-1 waiver 呈现互相冲突的机器与人工状态。",
      "recommendation": "由 bookkeeper 删除 Recovery Header 中已失效的待决块，同步 Current State、Open Decisions、Next Steps/footer、status.current_phase、human_escalation.resolved_by、updated_at，并把用户选择 Codex及直接 Round-5 review-2/review-1 waiver 的授权记录到机器状态。"
    }
  ],
  "required_fixes": [
    "修订 docs/api/public-market-contract.md 的 symbol-snapshot 总述、refresh_status 总注和 row 字段，使 row 来源明确区分 live PublishedState 与 offline synchronous/cache snapshot。",
    "从公开 HTTP timeout/warnings 契约删除 base_raw_unavailable:<symbol>，或明确标为当前 HTTP 前置条件下不可达的内部防御诊断；不得继续把它列为公开 wire outcome。",
    "由 bookkeeper 完整同步 Round-5 Codex 路由、review-1 waiver、current_phase、handoff 正文/footer、human_escalation 和更新时间。",
    "若用户授权第六次超限修复，fix author 应向 40-fix-report.md 追加 Round-5 finding-to-fix 映射；bookkeeper 提交后重算指纹、保存测试与 pre-review validator，再按新授权派发审查。"
  ],
  "residual_risks": [
    "F1-F8 保持关闭；F9 的 live/offline published_version 字段定义已正确，F10 指出的 refresh_command_expired 已正确进入公开 warning 契约。",
    "F12 的 fix-author 和 session-receipt 补录已经完成；F11 曾同步到修复后状态，但随后发生的 Codex 路由决策没有同步到正文和顶层状态。",
    "backend/services/snapshot_service.py:320-322 与 symbol-snapshot.schema.json:5/:39、funding-history.schema.json:34 的既有 prose drift 仍属已披露的 deferred 项；本 stage 不应修改 backend 或 schema。",
    "独立 fingerprint 重算匹配；pre-review validator PASS；71 项目标后端测试、80 项前端自检、JSON 校验和固定范围 diff-check 均通过；固定范围没有禁改产品/Harness-track 路径变化。",
    "review-1 指纹仍停在 568fd41。用户当前直接执行 Round-5 Codex review-2 构成实际路由指令，但 bookkeeper 仍需把该 waiver 明确写入 status，且不得伪造 review-1 指纹。"
  ],
  "fix_start_prompt": "Human-gated repair prompt for Review-2 Round-5 REWORK, stage `2026-07-docs-truth-sync-v1`. Reviewed fingerprint: `e214d6f819d76daa3b85865c1021b5aa2497ee95:d93ff6d4be65eda9882a6145e69a8dfcb346b854af38f40da79ff49f5cdf965e`. Capture the raw Round-5 review narrative and final strict JSON verbatim at `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`; Round-4 raw is already archived at `54-review-2-round4.md`. Do not dispatch automatically: rework_count is already 5 versus max_rework 3, and no sixth fix has been authorized.\n\nFinding F13 P1 — `docs/api/public-market-contract.md:306-309,358-361,392-395` still says every row comes from a published/latest published state. Offline `get_symbol_snapshot` instead calls `get_snapshot` and projects the synchronously built or cached snapshot while `_published_state` remains None (`backend/services/snapshot_service.py:331-332,373-393`). Fix the human contract only: live row source = latest PublishedState; offline row source = synchronous/cache snapshot. Preserve the correct live revision, offline 0 sentinel, live-only same-state row identity, and no cross-request guarantee.\n\nFinding F14 P1 — `docs/api/public-market-contract.md:371-389` newly lists `no base snapshot yet` and `base_raw_unavailable:<symbol>` as a public 200 timeout outcome. The public method returns 503 at `snapshot_service.py:333-335` whenever no PublishedState exists, before command submission. `_scheduled_tick` sets `_base_raw` at :998 before publishing state at :1016/:1564, and no code resets it to None. The base_raw_unavailable branch at :1395-1404 is a defensive internal command-handler branch exercised only by a direct unit call, not a reachable current HTTP response. Remove it from the public timeout/wire-visible list, or explicitly label it internal and HTTP-unreachable. Keep `refresh_command_expired:<symbol>` documented.\n\nFinding F15 P2 — active `70-handoff.md` and top-level `status.json` still say Round-5 routing is pending while Recovery Header, ACTIVE.json, status.review_2.note/next_action, dispatch 59, and the current user instruction select Codex. Bookkeeper must synchronize all current-state sections and record the direct Round-5 review-2/review-1-waiver authorization without changing historical receipts or fingerprints.\n\nFix-author allowed files: `docs/api/public-market-contract.md` and append-only Round-5 content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Bookkeeper-only files: active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, `62-validate-pre-review.txt`, `ACTIVE.json`, and review/dispatch evidence. Forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker living-docs; any behavior, schema, deployment, merge, push, or fingerprint fabrication.\n\nRun exactly after an explicitly authorized fix:\n1. `rg -n 'published state|PublishedState|Offline|synchronously built|base_raw_unavailable|refresh_command_expired|snapshot_not_ready|wire-visible' docs/api/public-market-contract.md backend/services/snapshot_service.py backend/tests/test_symbol_snapshot_endpoint.py`\n2. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_symbol_snapshot_endpoint.py::test_not_ready_returns_503_before_first_publish backend/tests/test_symbol_snapshot_endpoint.py::test_expired_queued_command_does_no_upstream_io backend/tests/test_symbol_snapshot_endpoint.py::test_base_raw_none_click_does_no_fetch_raw -q -p no:cacheprovider`\n3. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`\n4. `node frontend/self-check.js`\n5. `python3 -m json.tool reports/agent-runs/2026-07-docs-truth-sync-v1/status.json >/dev/null`\n6. `git diff --check`\n7. `git diff --name-only` and verify fix-author changes are only the contract plus append-only fix report, while bookkeeper changes are limited to authorized stage evidence files.\n\nAcceptance criteria: every row-source statement is mode-dependent; public cold start is documented as 503, not 200 timeout; base_raw_unavailable is absent from the public wire list or explicitly marked internal/HTTP-unreachable; refresh_command_expired remains documented; handoff/status uniformly record the Codex Round-5 route and review-1 waiver; 71 backend tests and 80 frontend checks pass; no forbidden files change. Append exact before/after mapping and command outputs to `40-fix-report.md`, then stop for bookkeeper reconciliation. Only a new explicit human authorization may start another over-limit fix/review cycle.",
  "next_action": "human_escalation_required"
}
```
