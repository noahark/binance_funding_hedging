# Review-2 Report (final gate) ROUND 3 — 2026-07-docs-truth-sync-v1

> Bookkeeper capture: Codex read-only codex exec (resumed session 019f6a94), no file
> write. Raw round-3 output recovered verbatim below. Round-1 review-2 at
> 51-review-2-round1.md; round-2 at 52-review-2-round2.md. (RC9.)
> VERDICT: REWORK -> human_escalation_required (rework budget 3/3 reached).

---

Review-2 Round 3 结论：`REWORK`，按 3/3 rework 账本进入 `human_escalation_required`。

固定指纹与 pre-review validator 均通过；71 项后端测试、80 项前端自检全部通过。F4 指定的多路径/warnings 问题和 F5 已关闭，但仍存在一项 P1：合同声称 `published_version` 可与 full snapshot 做同版本关联，而 full snapshot 的 wire schema/响应并没有该字段，客户端无法验证此保证。F6 的历史 diff-check 说明也仍有可复现性错误。

本次严格只读，工作树保持干净。

当前 Session ID: unavailable (当前运行环境未暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: unavailable (只读 reviewer 未写文件；bookkeeper 应将本响应原样保存至 reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md)
本地北京时间: 2026-07-16 22:13:29 CST
下一步模型: human
下一步任务: 决定是否授权超出既定 rework 上限的最后一次限定修复；若授权，再按 fix_start_prompt 派发 claude_glm 与 bookkeeper

{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "final_reviewer",
  "model": "codex",
  "verdict": "REWORK",
  "diff_fingerprint": "568fd4160b67d3b73303134d6f078a6a59bb93d9:ec91074df380632652180548168583da1756669a9e63d0077f73041621fc1ffe",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/OpenAI participated in the earlier read-only four-model direction audit, but did not author the stage design, development breakdown, implementation, or either fix. Round 3 independently verified the fixed range against the PRD, schemas, server, frontend, tests, raw reviews, fix reports, and current stage ledger.",
  "reviewed_artifacts": [
    "workflows/templates/stage-delivery.yaml review-2 section",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/57-dispatch-review-2-codex-round3.md",
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
    "git diff --binary 127a600281d60b7332be8aeb9552740a5e8c3254..568fd4160b67d3b73303134d6f078a6a59bb93d9",
    "git diff --binary a77a18aa069ecc236c8448b8bdced40ea53bdeb1..568fd4160b67d3b73303134d6f078a6a59bb93d9",
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
    "backend/config.py",
    "backend/services/snapshot_service.py",
    "backend/domain/snapshot.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "scripts/service-control.py",
    "frontend/index.html",
    "frontend/self-check.js"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "symbol-snapshot 合同承诺了 wire payload 无法表达或验证的 full-snapshot 同版本保证",
      "file": "docs/api/public-market-contract.md",
      "line": 323,
      "evidence": "合同第 323-324 行称 projected row 与 full snapshot 共享同一 published_version，第 336 行又把 published_version 描述为与 full snapshot 相同的版本。然而 schemas/api/public-market/snapshot.schema.json 的 required/properties 均没有 published_version，backend/services/snapshot_service.py:237-257 和 backend/app/server.py:58-88 返回的 full snapshot 也不添加该字段。backend/tests/test_symbol_snapshot_endpoint.py:178-189 仅把 symbol payload 的 published_version 与内部 service._published_version 比较，并验证 row 等于当时内部 PublishedState 的 snapshot row；它没有也无法从 full snapshot wire payload 比较版本。不同 HTTP 请求之间还可能发生后续 publication，因此客户端不存在可观察的跨响应同版本保证。symbol-snapshot.schema.json:5 也含相同的陈旧 same-version prose，但当前 drift 注记只解释了无条件命令/新发布问题。",
      "impact": "API 使用者可能寻找 full snapshot 中不存在的 published_version，或错误地把两个独立 HTTP 响应视为具备可验证的原子同版本关系。该保证超出了现行 wire contract，违反本 stage 的核心目标：人类合同必须与 schema/server 真值一致。",
      "recommendation": "仅修订人工合同：把 symbol-snapshot 的 published_version 定义为所投影内部 PublishedState 的修订号；明确 full snapshot v1 wire payload 当前不暴露可比较的 published_version，因此不存在客户端可验证的跨请求同版本保证。保留 row 来源于该内部状态 snapshot 的事实，并把 symbol-snapshot.schema.json:5 的 same-version prose 一并列入 deferred schema drift。不要修改 server、schema 或产品行为。"
    },
    {
      "severity": "P2",
      "title": "F6 的历史 diff-check 范围说明仍记录了不可复现的 clean 结果",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt",
      "line": 132,
      "evidence": "第 132 行记录 `git diff --check c72987d..a77a18a` 为 clean，但独立执行该未限定路径的命令返回 exit 2，并报告旧 Round-1 `30-review-1.md` 第 3-5 行三处 trailing whitespace。只有把 c72987d..a77a18a 限定到四个修复交付文件时才 clean。当前 Round-3 固定全范围 `127a600..568fd41` 则确实 clean。",
      "impact": "不影响产品或当前 Round-3 fixed-range 门禁，但历史验证记录仍不能按所写命令复现，削弱审计证据的精确性。",
      "recommendation": "由 bookkeeper 向 60-test-output.txt 追加更正：分别记录未限定 c729..a77 的 exit 2、限定四个交付文件的 clean，以及当前 127a600..568fd41 的 clean；不得改写原始 reviewer 输出。"
    },
    {
      "severity": "P2",
      "title": "活动 handoff 正文与 ACTIVE 顶层时间仍未完全同步到 Round 3",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md",
      "line": 37,
      "evidence": "Recovery Header 已正确指向 review_2 Round 3，但同一 handoff 后续 Current State 仍写 status=planned、intake 未进入实现、tests=not_applicable，并保留旧的用户决策与开发前 Next Steps。ACTIVE.json 的 active.updated_at 为 20:50Z，而顶层 updated_at 仍为 20:35Z。启动快速路径仍可依靠 Recovery Header 与 status.json 正常恢复，因此不是阻断性运行问题。",
      "impact": "阶段主状态仍可恢复，但完整 handoff 与时间账本对审计读者呈现互相冲突的阶段快照。",
      "recommendation": "由 bookkeeper 在下一检查点同步 handoff 正文与 ACTIVE.json 顶层 updated_at，保留 Recovery Header 的当前 Round-3 事实。"
    }
  ],
  "required_fixes": [
    "修订 docs/api/public-market-contract.md，删除客户端可比较的 full-snapshot same-version 保证，准确说明 symbol payload 的 published_version 只标识内部 PublishedState 修订，并披露 full snapshot v1 wire payload不含可比较字段及 symbol-snapshot.schema.json:5 的相关 prose drift。",
    "由 bookkeeper 追加更正 60-test-output.txt 中 c72987d..a77a18a 的 diff-check 范围和实际结果，并同步 70-handoff.md 正文及 ACTIVE.json 顶层更新时间。",
    "若用户授权超出 3/3 rework 上限的限定修复，fix author 应在 40-fix-report.md 追加 Round-3 finding-to-fix 映射；bookkeeper 随后提交、重算标准指纹、保存 pre-review validator 结果并重新派发独立 review。若用户不授权，阶段保持 human_escalation_required。"
  ],
  "residual_risks": [
    "F4 指定的 live-worker/no-worker/offline 路径、wire-visible warnings 和内部 cmd.error 不暴露语义已经关闭；F5 的两道人类验收门也已正确分开。",
    "funding-history.schema.json:34 与 symbol-snapshot.schema.json:5/:39 的描述性 prose 仍需未来有事实证据的 contract-amendment stage 对齐；本轮不得修改 schema。",
    "Stage B 与 Harness-track 文件保持延后，固定受审范围没有越界。",
    "独立复算 fingerprint 与 pre-review validator 均通过；71 项目标后端测试和 80 项前端自检通过，固定 Round-3 全范围 diff-check 干净。"
  ],
  "fix_start_prompt": "Human-gated repair prompt for Review-2 Round-3 REWORK, stage `2026-07-docs-truth-sync-v1`. Reviewed fingerprint: `568fd4160b67d3b73303134d6f078a6a59bb93d9:ec91074df380632652180548168583da1756669a9e63d0077f73041621fc1ffe`. Raw Round-3 review and strict verdict JSON must be captured verbatim at `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`; prior Round-2 raw review is the content currently at that path and must be archived before replacement. Read the raw review, `40-fix-report.md`, `60-test-output.txt`, `70-handoff.md`, `status.json`, the fixed diff, and every source/schema/test cited below. Do not act automatically: rework_count reaches 3/3, so this prompt may be dispatched only after explicit human authorization to continue beyond the configured rework limit.\n\nFinding F7 P1 — `docs/api/public-market-contract.md:323-336` promises that symbol-snapshot `published_version` is the same version as the full snapshot. The full snapshot wire schema and response contain no `published_version`; tests compare only against internal `service._published_version`, and separate HTTP reads can cross a later publication. Impact: clients may expect a nonexistent correlation field or atomic cross-response guarantee. Fix the human contract only: define the value as the internal PublishedState revision used for this row; explicitly state that full snapshot v1 does not expose a comparable version and gives no client-verifiable cross-request equality guarantee; preserve the fact that the row was selected from that internal state's snapshot. Extend the deferred `symbol-snapshot.schema.json:5` prose-drift note to include its same-version claim. Do not edit server or schemas.\n\nFinding F8 P2 — `60-test-output.txt:132` says unscoped `git diff --check c72987d..a77a18a` is clean, but it exits 2 on three trailing-space lines in the historical raw Round-1 reviewer file. Only the four-delivery-file-scoped command is clean; `127a600..568fd41` is also clean. The active handoff body still describes intake/planned state and ACTIVE.json top-level updated_at trails active.updated_at. These are bookkeeper-owned corrections; do not edit raw reviewer artifacts.\n\nFix-author allowed files: `docs/api/public-market-contract.md` and append-only Round-3 content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Fix-author forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker living-docs; active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, and `ACTIVE.json` because those are bookkeeper-owned. No behavior, endpoint, schema, or product-scope change.\n\nFix author must run exactly:\n1. `rg -n 'published_version|full snapshot|internal PublishedState|cross-request|wire' docs/api/public-market-contract.md`\n2. `if rg -n 'shares the same published_version as the full snapshot|same version as the full snapshot' docs/api/public-market-contract.md; then exit 1; fi`\n3. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`\n4. `node frontend/self-check.js`\n5. `git diff --check`\n6. `git diff --name-only` and verify only the contract plus append-only `40-fix-report.md` changed.\n\nAppend a Round-3 section to `40-fix-report.md` mapping F7 to exact before/after text and command outputs, preserving prior reports verbatim. Then stop for bookkeeper reconciliation. If the human authorizes continuation, the bookkeeper must append—not rewrite—`60-test-output.txt` with: unscoped `git diff --check c72987d..a77a18a` exit 2 and its three historical reviewer lines; the same range restricted to the four delivery files clean; current fixed range `git diff --check 127a600..568fd41` clean. Synchronize the active handoff body and ACTIVE.json top-level timestamp, update status/session receipts, commit on the stage branch, recompute the standard fingerprint, run and preserve `python3 scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`, and redispatch review only under explicit human authorization. Otherwise record `human_escalation_required` and stop.",
  "next_action": "human_escalation_required"
}
