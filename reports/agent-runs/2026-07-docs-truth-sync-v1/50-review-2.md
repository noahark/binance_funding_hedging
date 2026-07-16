# Review-2 Report (final gate) ROUND 2 — 2026-07-docs-truth-sync-v1

> Bookkeeper capture: Codex ran read-only codex exec (resumed session 019f6a94)
> and wrote no file. Raw round-2 final-reviewer output recovered verbatim below.
> Round-1 review-2 preserved at 51-review-2-round1.md. (RC9 evidence capture.)

---

Review-2 Round 2 结论：`REWORK`。

固定提交范围、指纹、前置校验均通过，71 项测试全部通过。F1 已关闭；F2 仍过度承诺 symbol-snapshot 的刷新与诊断语义；F3 修复本身保持了 JSON 事实，但 handoff 新增了验收状态混淆。此外，活动阶段账本与 diff-check 证据仍未同步。

本次严格只读，未修改仓库。请 bookkeeper 将本响应原样保存为 Round-2 原始审查证据。

当前 Session ID: unavailable (当前运行环境未暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: unavailable (只读 reviewer 未写文件；应由 bookkeeper 保存至 reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md)
本地北京时间: 2026-07-16 20:07:34 CST
下一步模型: claude_glm
下一步任务: 按 fix_start_prompt 修正文档，随后由 bookkeeper 校正阶段账本、提交并重新进入 review-1/review-2

{
  "schema_version": 1,
  "stage_id": "2026-07-docs-truth-sync-v1",
  "role": "final_reviewer",
  "model": "codex",
  "verdict": "REWORK",
  "diff_fingerprint": "a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9",
  "reviewer_prior_involvement": "direction_synthesis",
  "reviewer_prior_involvement_notes": "Codex/OpenAI participated in the earlier four-model read-only direction audit, but did not author the stage design, breakdown, implementation, or either fix. Round 2 independently re-verified the fixed range against code, schemas, tests, current stage state, and raw review/fix evidence.",
  "reviewed_artifacts": [
    "workflows/templates/documentation-truth-sync.yaml review-2 section",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/56-dispatch-review-2-codex-round2.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md",
    "reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md",
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
    "git diff --binary 127a600281d60b7332be8aeb9552740a5e8c3254..a77a18aa069ecc236c8448b8bdced40ea53bdeb1",
    "git diff --binary c72987d9c380224fb09063b6d7d08ff0d55ecbb9..a77a18aa069ecc236c8448b8bdced40ea53bdeb1",
    "docs/api/public-market-contract.md",
    "docs/product/PRD.md",
    "docs/development/DEVELOPMENT_GUIDE.md",
    "docs/planning/DECISIONS.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/planning/FOLLOWUPS.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
    "reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json",
    "schemas/funding-history.schema.json",
    "schemas/symbol-snapshot.schema.json",
    "backend/services/snapshot_service.py",
    "backend/tests/test_funding_history.py",
    "backend/tests/test_funding_history_endpoint.py",
    "backend/tests/test_symbol_snapshot_endpoint.py",
    "frontend/src/index.ts"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "F2 仍未关闭：symbol-snapshot 总述和 warnings 诊断能力继续过度承诺",
      "file": "docs/api/public-market-contract.md",
      "line": 306,
      "evidence": "合同第 306-311 行无条件声称后端提交 RefreshSymbolCommand、等待命令完成并从“新发布”的状态投影行；实际 snapshot_service.py:331-332 在 offline 模式直接调用 _offline_symbol_snapshot，不提交命令，339-359 也仅在 worker 运行时提交命令，否则返回 last-good timeout，373-393 的 offline 路径甚至可返回 refresh_status=ok 而没有本次请求触发的新 worker publication。合同第 333-341 行又把 assemble_failed、validation_crossed_deadline 列为 timeout 触发原因，并把 warnings 描述为非 deadline timeout 的诊断信息；但响应在 snapshot_service.py:351-359 只序列化 cmd.warnings，组装或验证失败原因仅写入 1499、1516、1532、1537 附近的内部 cmd.error，既不在响应 schema 中，也不进入 payload。合同的 schema drift 注记还只引用 symbol-snapshot.schema.json:39，遗漏第 5 行同样无条件的“提交命令/新发布状态”说明。",
      "impact": "调用方可能错误地把每个 200 响应理解为本次请求已经触发并观察到一次新发布，也可能错误地依赖 warnings 获得所有 timeout 的根因，形成错误的新鲜度、可观测性和故障诊断保证。",
      "recommendation": "仅修订人工合同：分别说明 live worker、offline 和 worker-not-running 路径；明确返回行来自当前可用状态，但不一定来自本次请求创建的新 publication；把 warnings 限定为线协议实际暴露的部分诊断值，并说明部分内部失败只表现为无具体原因的 timeout；同时披露 symbol-snapshot.schema.json 第 5 行和第 39 行的 schema prose drift。不要修改服务端或 schema。"
    },
    {
      "severity": "P2",
      "title": "F3 handoff 将视觉验收误归为阶段级 accepted_merged_and_pushed",
      "file": "reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md",
      "line": 63,
      "evidence": "新文本称用户视觉验收被记录为 accepted_merged_and_pushed。实际 status.json 中 human_visual_acceptance.status 是 accepted；accepted_merged_and_pushed 属于之后独立的 user_acceptance.status。两个字段代表不同的人类门禁。",
      "impact": "审计读者会把视觉确认与阶段接受、合并和推送混为同一事件，削弱阶段状态与用户授权链条的可追溯性。",
      "recommendation": "分别点名 human_visual_acceptance.status=accepted 和后续 user_acceptance.status=accepted_merged_and_pushed，并保持所有标识符、结果与时间顺序不变。"
    },
    {
      "severity": "P2",
      "title": "Round-2 阶段账本与验证范围仍未同步修复后的事实",
      "file": "reports/agent-runs/2026-07-docs-truth-sync-v1/status.json",
      "line": 99,
      "evidence": "status.json 的 delivery_files_under_review 与 changed_files 仍是旧的八个交付文件，遗漏本轮实际修改且进入固定指纹的 reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json。reports/agent-runs/ACTIVE.json 仍标记 phase=intake。60-test-output.txt 第 123 行只写 git diff --check clean，未声明它检查的是未提交修复增量；固定全范围 127a600..a77a18a 实际会因已被 Round-2 reviewer 覆盖的旧 Round-1 30-review-1.md 三处尾随空格返回非零，而 c72987d..a77a18a 限定四个修复交付文件和当前已提交 HEAD 均为 clean。当前 30-review-1.md 也错误声称固定全范围 clean，但它是原始 reviewer 输出，不应被改写。",
      "impact": "阶段账本不能完整解释固定指纹包含的文件，ACTIVE 指针与真实 review_2 状态冲突，diff-check 证据也无法按记录复现，降低正式门禁的审计可靠性。",
      "recommendation": "由 bookkeeper 将 bookticker status.json 加入两个文件清单，更新 ACTIVE.json 的真实阶段和时间，并在 60-test-output.txt 追加精确的全范围、修复范围和当前 HEAD diff-check 结果及解释；不要改写原始 30-review-1.md。"
    }
  ],
  "required_fixes": [
    "修订 docs/api/public-market-contract.md 的 symbol-snapshot 章节，关闭 F2：准确区分 live worker、offline 与 worker-not-running 路径，取消“本次请求必有新发布”和“warnings 必能解释 timeout”的保证，并同时披露 schema 第 5、39 行的 prose drift。",
    "修订 bookticker 70-handoff.md，分别记录 human_visual_acceptance.status=accepted 与后续 user_acceptance.status=accepted_merged_and_pushed，避免把两个门禁合并。",
    "由 bookkeeper 同步 active status.json 的文件清单、ACTIVE.json 阶段指针，并向 60-test-output.txt 追加准确的 diff-check 范围和结果；不得重写原始 reviewer 输出。",
    "fix author 在 40-fix-report.md 追加 Round-2 finding-to-fix 映射和命令输出；bookkeeper 随后提交、重算标准指纹、保存 pre-review validator 结果，并重新执行 review-1 与 review-2。"
  ],
  "residual_risks": [
    "symbol-snapshot.schema.json 的描述性 prose 与实际多路径行为仍存在漂移，本轮只要求人工合同明确披露，不扩大为 schema 或服务端变更。",
    "Stage-B 与 Harness-track 文档仍属于已批准的后续范围，本轮不得顺带修改。",
    "F1 已通过代码与非预热 endpoint 测试独立验证关闭；bookticker status.json 相对修复前提交仅有两个 note 标量变化，SHA、指纹、verdict、merge、session 与用户授权事实未变；目标测试 71 项全部通过。"
  ],
  "fix_start_prompt": "Fix Review-2 Round-2 REWORK for stage `2026-07-docs-truth-sync-v1`. Reviewed fingerprint: `a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9`. Raw Round-2 review and final verdict JSON: `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (the strict JSON is the final block in that same raw file). Read that raw artifact, the prior Round-1 verdict archived in `status.json.review_rounds[0]`, `40-fix-report.md`, the fixed diff, and every source/test path cited below; do not rely on a bookkeeper summary.\n\nOrdered findings:\nF4 P1 — `docs/api/public-market-contract.md:306-341` still over-promises symbol-snapshot. The intro says every request submits a command and projects a newly published state, but `snapshot_service.py:331-359,373-393` has offline projection and worker-not-running last-good paths without a command/new publication. The contract also implies response `warnings` diagnoses non-deadline timeout and lists `assemble_failed`/`validation_crossed_deadline`, while `snapshot_service.py:351-359` serializes only `cmd.warnings`; assembly/validation causes live only in internal `cmd.error` at :1499/:1516/:1532/:1537. Impact: false refresh/freshness and diagnostic guarantees. Fix the human contract only: distinguish live-worker/offline/no-worker behavior, say the row does not necessarily come from a publication created by this request, limit warnings claims to wire-visible values, and disclose schema prose drift at symbol-snapshot.schema.json:5 and :39. Do not change server/schema.\nF5 P2 — bookticker `70-handoff.md:63-64` says visual acceptance was recorded as `accepted_merged_and_pushed`. Actual `human_visual_acceptance.status` is `accepted`; `accepted_merged_and_pushed` is the later `user_acceptance.status`. Impact: two human gates are conflated. Fix the sentence by naming each field separately; preserve every identifier and outcome.\nF6 P2 — active stage `status.json:99-118` omits bookticker `status.json` from `delivery_files_under_review` and `changed_files`; `ACTIVE.json:4` remains `intake`; `60-test-output.txt:123` does not state the scope of its clean diff-check. Fixed range `127a600..a77a18a` reports three trailing-space lines in the superseded Round-1 reviewer file, while `c72987d..a77a18a` restricted to the four delivery-fix files and the current committed HEAD are clean. These are bookkeeper-owned corrections; do not edit raw `30-review-1.md`.\n\nFix-author allowed files: `docs/api/public-market-contract.md`, `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`, and append-only Round-2 correction/mapping content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Fix-author forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker `status.json`/`20-implementation.md`; active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, and `ACTIVE.json` (bookkeeper-owned). No behavior, schema, endpoint, or product-scope change.\n\nFix author must run exactly:\n1. `rg -n 'offline|worker|latest published|last-good|cmd.error|not exposed|warnings|schema-prose drift' docs/api/public-market-contract.md`\n2. `if rg -n 'then projects ONLY the selected row from the newly published|warnings.*diagnostic for a timeout|recorded as .accepted_merged_and_pushed.' docs/api/public-market-contract.md reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md; then exit 1; fi`\n3. `python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json >/dev/null`\n4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`\n5. `git diff --check`\n6. `git diff --name-only` and verify only the two delivery docs plus append-only `40-fix-report.md` changed.\n\nAppend a Round-2 section to `40-fix-report.md` mapping F4/F5 to exact before/after text and command outputs; preserve the prior report text verbatim. Then stop for bookkeeper reconciliation. Bookkeeper must handle F6: add `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json` to active `delivery_files_under_review` and `changed_files`; update `ACTIVE.json` to the actual phase/timestamp; append—not rewrite—`60-test-output.txt` with exact scoped/full-range diff-check results; update active `status.json`/`70-handoff.md`; commit on the stage branch; recompute the standard fingerprint; run and preserve `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`; then redispatch Round-3 review-1 and review-2 under the existing provider-isolation rules.",
  "next_action": "fix"
}
