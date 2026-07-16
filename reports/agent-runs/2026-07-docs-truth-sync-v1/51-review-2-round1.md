# Review-2 Report (final gate) — 2026-07-docs-truth-sync-v1

> Bookkeeper capture note: Codex ran read-only `codex exec` and did not write this
> file itself. Bookkeeper recovered the raw final-reviewer output verbatim from the
> Codex rollout session `019f6a94-9685-7f80-8b64-cb7ba5798daf`
> (2026-07-16T18:59Z) and landed it here as the raw review-2 artifact. This directly
> exercises RC9 (lossy cross-model evidence capture) documented in 80-...rootcause.

---

Review-2 结论：`REWORK`。

固定指纹、当前 `pre-review` validator、文件边界和 71 个针对性测试均通过；但发现 3 个 P1：

1. `funding-history` 的 `empty` 被错误描述为上游抓取成功，实际可能只是未预热的 PublishedState 空投影。
2. `symbol-snapshot` 的 `partial/timeout` 描述窄于服务器及测试锁定的行为。
3. bookticker 的 living-doc/status 仍把已完成的证据提交、视觉验收和终审写成待办。

本次审查只读，未修改文件。Operator 应将此原始输出保存至 `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`。

当前 Session ID: unavailable (当前运行时未暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md
本地北京时间: 2026-07-16 19:10:13 CST
下一步模型: claude_glm（由 bookkeeper 准备、human operator 执行派发）
下一步任务: 按 fix_start_prompt 限定修复 F1-F3，提交新指纹并重新进入评审

{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "final_reviewer",
  "model": "codex",
  "verdict": "REWORK",
  "diff_fingerprint": "c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/OpenAI participated in the earlier four-model read-only audit that informed the backlog, but did not author this stage's design, development breakdown, implementation, or fixes. This review independently re-verified the fixed diff against schemas, server code, tests, frontend, and stage evidence.",
  "reviewed_artifacts": [
    "workflows/templates/stage-delivery.yaml#review-2",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/11-adr.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/30-review-1.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/62-validate-pre-review.txt",
    "git diff 127a600281d60b7332be8aeb9552740a5e8c3254..c72987dc5cfe288e8df887cd14a965a48e93e3f3",
    "docs/api/public-market-contract.md",
    "docs/product/PRD.md",
    "docs/development/DEVELOPMENT_GUIDE.md",
    "docs/planning/DECISIONS.md",
    "docs/architecture/ARCHITECTURE.md",
    "reports/follow-ups/README.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
    "schemas/api/public-market/snapshot.schema.json",
    "schemas/api/public-market/funding-history.schema.json",
    "schemas/api/public-market/symbol-snapshot.schema.json",
    "backend/app/server.py",
    "backend/services/snapshot_service.py",
    "backend/config.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "scripts/service-control.py",
    "frontend/index.html"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "funding-history 的 empty 被错误描述为已成功上游抓取",
      "file": "docs/api/public-market-contract.md",
      "line": 280,
      "evidence": "合同第 280-283 行声称 funding_history 为空仅发生在上游成功但窗口无记录。当前端点实际上是纯 PublishedState 投影：backend/services/snapshot_service.py:259-315 只按已发布 row 是否有记录设置 available/empty，不执行上游抓取；backend/tests/test_funding_history_endpoint.py:238-250 明确锁定未预热 symbol 也返回 200/empty 且不做按需抓取。",
      "impact": "调用方会把 empty 误当成已成功验证的“零结算记录”，掩盖未预热或历史抓取失败，形成错误的新鲜度/完整性判断。",
      "recommendation": "把合同改为当前纯投影语义：empty 只表示已发布 row 中没有记录，不能证明本次或先前上游抓取成功；同时显式记录 funding-history schema 第 34 行描述比当前实现更窄，schema 对齐留给后续受控 contract-amendment stage。"
    },
    {
      "severity": "P1",
      "title": "symbol-snapshot 的 partial/timeout 语义窄于现有服务行为",
      "file": "docs/api/public-market-contract.md",
      "line": 313,
      "evidence": "合同第 314-318 行把 partial 限定为 public/history 已刷新而 borrow 回退，并把 timeout 限定为共享 deadline。实际 backend/services/snapshot_service.py:1420-1437 会为 premium 或 funding-history 失败加入 warning，:1527 将任何 warning 映射为 partial；backend/tests/test_symbol_snapshot_endpoint.py:252-270 明确断言 history/premium 失败均为 partial。服务 :347-359 还会在 worker 未运行时返回 timeout，assembly/validation 失败也走 timeout。",
      "impact": "客户端可能在 partial 时错误相信 public/history 已刷新，或在 timeout 时错误推断仅发生超时，导致对 projected last-good row 的来源和新鲜度判断错误。",
      "recommendation": "按服务器和测试描述状态：ok 为成功发布且无 warning，partial 为成功发布但存在一个或多个 source warning（含 premium/history/borrow），timeout 为未形成新发布并投影 last-good（deadline、worker 未运行或 assembly/validation 失败等）；warnings 才是细分原因。明确标注 symbol-snapshot schema 第 39 行描述尚未覆盖这些现有分支。"
    },
    {
      "severity": "P1",
      "title": "P1-9 living-doc 归一仍保留已完成事项的当前/未来态措辞",
      "file": "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
      "line": 518,
      "evidence": "status.json:518 仍写 local evidence commit 和 fresh Codex final review 'remain'，但同文件顶层 status=accepted、review_2.verdict=ACCEPT、user_acceptance=accepted_merged_and_pushed。70-handoff.md:63-66 仍写用户随后执行视觉验收且终审被请求，:129 仍写 Task B 报告 must be amended；status.json:653 与 20-implementation.md:79-82 也保留未完成时态。review-1 的 grep 未覆盖这些短语。",
      "impact": "恢复会话和审计读者会同时看到 accepted 机器状态与未完成叙述；这正是本 stage 要消除的 P1-9 事实漂移。",
      "recommendation": "在已批准的四个 bookticker living-doc 边界内把这些句子改成完成态，或明确标为带时间点的历史快照；保留 SHA、fingerprint、Session ID、原始 verdict 和用户授权事实，不改历史结果。"
    }
  ],
  "required_fixes": [
    "修正 docs/api/public-market-contract.md 的 funding-history empty 语义，说明它是 PublishedState 纯投影且 empty 不证明上游抓取成功，并披露现有 schema 描述差异。",
    "修正 docs/api/public-market-contract.md 的 symbol-snapshot ok/partial/timeout 语义，使其覆盖现有 premium/history/borrow warning、worker-not-running、deadline 与 assembly/validation 分支，并以 warnings 作为细分原因。",
    "完成 bookticker 70-handoff.md、20-implementation.md、status.json 的 P1-9 归一：清除或历史化仍把已完成视觉验收、证据提交、修复和 final review 写成未来/待办的措辞。",
    "由 fix author 写 40-fix-report.md 逐项映射 F1-F3；bookkeeper 提交限定修复、重跑并保存测试与 pre-review validator、更新指纹后重新派发 review-1/review-2。"
  ],
  "residual_risks": [
    "funding-history.schema.json:34 与 symbol-snapshot.schema.json:39 的 prose description 已与现有服务器/测试行为发生预存漂移；本 stage 禁止改 schema，需另建有原始事实证据的 contract-amendment stage 对齐。",
    "reports/agent-runs/ACTIVE.json 的 phase 仍为 intake，而 status/handoff 为 review_2；bookkeeper 应在记录本次 REWORK 的强制 checkpoint 中同步该指针。",
    "当前会话独立运行的 pre-review validator 为 PASS，71 个 funding-history/symbol-snapshot 针对性测试通过；修复后仍必须基于新提交和新指纹重跑并保存证据。"
  ],
  "fix_start_prompt": "Fix stage `2026-07-docs-truth-sync-v1` after Review-2 REWORK. Reviewed fingerprint: `c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`. Raw review and raw final verdict JSON: `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (JSON is the final block in the same raw file). Read the raw file, `00-task.md`, `10-design.md`, `12-development-breakdown.md`, the fixed diff, and all evidence cited below; do not work from a bookkeeper summary.\n\nOrdered findings to fix:\nF1 P1 — `docs/api/public-market-contract.md:280-283` says empty history proves an upstream fetch succeeded. `backend/services/snapshot_service.py:259-315` and `backend/tests/test_funding_history_endpoint.py:238-250` show a pure PublishedState projection and a non-prewarmed symbol returning 200/empty without on-demand fetch. Impact: false completeness/freshness inference. Fix: document that empty means no entries in the published row and does not prove upstream success; explicitly disclose the narrower stale prose in `funding-history.schema.json:34` as a deferred schema-alignment item.\nF2 P1 — `docs/api/public-market-contract.md:313-318` narrows partial to borrow fallback and timeout to deadline. `snapshot_service.py:1420-1437,1527` plus `test_symbol_snapshot_endpoint.py:252-270` show premium/history failures also produce partial; `snapshot_service.py:347-359` and assembly paths also produce timeout for no worker or no new publication. Impact: clients may trust stale public/history data. Fix: describe ok/partial/timeout from current code and state that `warnings` carries source-specific reasons; disclose the stale narrower prose in `symbol-snapshot.schema.json:39` without changing schema in this stage.\nF3 P1 — bookticker `status.json:518,653`, `70-handoff.md:63-66,129`, and `20-implementation.md:79-82` retain current/future wording after accepted/merged/pushed Review-2 ACCEPT. Impact: resumed sessions see contradictory state. Fix: convert to completed past tense or explicitly time-scoped historical snapshot wording while preserving every SHA, fingerprint, Session ID, verdict, user authorization, and raw evidence fact.\n\nRequired fixes are exactly F1-F3. Allowed delivery files: `docs/api/public-market-contract.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`. Also create `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md` mapping F1/F2/F3 to exact edits and command outputs. Forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; `STAGE_INDEX.md`, `ROADMAP.md`, `harness-manifest.yaml`, `docs/harness-design.md`, `AGENTS.md`, `docs/planning/stage-branch-mode.md`, `docs/README`, `docs/architecture/ADR/`; and active-stage `status.json`, `70-handoff.md`, `60-test-output.txt` (bookkeeper-only checkpoint/evidence files). No behavior, schema, endpoint, or product-scope change.\n\nRun exactly:\n1. `python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json >/dev/null`\n2. `rg -n 'pure projection|does not prove|premium_refresh_failed|funding_history_unavailable|worker_not_running|warnings' docs/api/public-market-contract.md`\n3. `if rg -n 'Empty only when the upstream fetch succeeded|public/history refreshed but borrow fell back|the command reached its shared deadline before publication' docs/api/public-market-contract.md; then exit 1; fi`\n4. `if rg -n 'local evidence commit and the single fresh Codex final review remain|After deterministic verification, the user performs visual acceptance|fresh Codex final-review invocation is requested|must be amended by fix 2|Kimi performs one bounded frontend-only UI adjustment|the user visually accepts it|invocation inspects' reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json; then exit 1; fi`\n5. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`\n6. `git diff --check`\n7. `git diff --name-only` and verify every changed delivery path is in the Allowed list plus `40-fix-report.md`.\n\n`40-fix-report.md` must contain a finding-to-fix table with rows F1/F2/F3, exact file/line evidence, before/after semantic summary, all command outputs, changed-file boundary result, and a footer. Do not rewrite the raw Review-2 evidence. After the fix author stops, the bookkeeper must independently reconcile the diff, update `60-test-output.txt`, active `status.json`/`70-handoff.md`/`ACTIVE.json`, commit on the stage branch, recompute the standard fingerprint, run and preserve `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`, then redispatch the configured review gates.",
  "next_action": "fix"
}
