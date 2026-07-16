# Dispatch Packet — fix round 2（Review-2 Round-2 REWORK）（executor: human operator → claude_glm）

在 Claude-GLM 终端执行 PROMPT BODY。fix 作者 = `claude_glm`（原实现者）。
**分工**：F4/F5 由 fix author 改文档；F6 是 bookkeeper-owned，**已由 bookkeeper 提前
处理**（ACTIVE.json phase、active status.json changed_files、60-test-output 范围说明），
fix author 不碰 F6 文件。执行后原始输出 + `40-fix-report.md` 追加段落落到 stage；不 commit。

- Review-2 round-2：Codex `final_reviewer` = REWORK（schema-valid，新指纹匹配），原文
  `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`（round-1 保留于 51-）。
- rework 账本：**2 / 3**（再一次 REWORK 将触发 human escalation）。
- PROMPT BODY 为 Codex fix_start_prompt 原文逐字。
- Bookkeeper 备注（不影响 finding 成立）：Codex verdict 的 reviewed_artifacts 误列了本仓
  不存在的 `workflows/templates/documentation-truth-sync.yaml`、`docs/planning/FOLLOWUPS.md`、
  `frontend/src/index.ts`；三个 finding F4/F5/F6 本身指向的都是真实文件，已核实。以真实
  文件为准。

`claude-glm -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/46-dispatch-fix-round2-claude-glm.md)"`

---

## PROMPT BODY

Fix Review-2 Round-2 REWORK for stage `2026-07-docs-truth-sync-v1`. Reviewed fingerprint: `a77a18aa069ecc236c8448b8bdced40ea53bdeb1:4185db381c588a8e07659feb265c3106cf903f06c4f2ef24fbb789add56626c9`. Raw Round-2 review and final verdict JSON: `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (the strict JSON is the final block in that same raw file). Read that raw artifact, the prior Round-1 verdict archived in `status.json.review_rounds[0]`, `40-fix-report.md`, the fixed diff, and every source/test path cited below; do not rely on a bookkeeper summary.

Ordered findings:
F4 P1 — `docs/api/public-market-contract.md:306-341` still over-promises symbol-snapshot. The intro says every request submits a command and projects a newly published state, but `snapshot_service.py:331-359,373-393` has offline projection and worker-not-running last-good paths without a command/new publication. The contract also implies response `warnings` diagnoses non-deadline timeout and lists `assemble_failed`/`validation_crossed_deadline`, while `snapshot_service.py:351-359` serializes only `cmd.warnings`; assembly/validation causes live only in internal `cmd.error` at :1499/:1516/:1532/:1537. Impact: false refresh/freshness and diagnostic guarantees. Fix the human contract only: distinguish live-worker/offline/no-worker behavior, say the row does not necessarily come from a publication created by this request, limit warnings claims to wire-visible values, and disclose schema prose drift at symbol-snapshot.schema.json:5 and :39. Do not change server/schema.
F5 P2 — bookticker `70-handoff.md:63-64` says visual acceptance was recorded as `accepted_merged_and_pushed`. Actual `human_visual_acceptance.status` is `accepted`; `accepted_merged_and_pushed` is the later `user_acceptance.status`. Impact: two human gates are conflated. Fix the sentence by naming each field separately; preserve every identifier and outcome.
F6 P2 — active stage `status.json:99-118` omits bookticker `status.json` from `delivery_files_under_review` and `changed_files`; `ACTIVE.json:4` remains `intake`; `60-test-output.txt:123` does not state the scope of its clean diff-check. Fixed range `127a600..a77a18a` reports three trailing-space lines in the superseded Round-1 reviewer file, while `c72987d..a77a18a` restricted to the four delivery-fix files and the current committed HEAD are clean. These are bookkeeper-owned corrections; do not edit raw `30-review-1.md`.

Fix-author allowed files: `docs/api/public-market-contract.md`, `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`, and append-only Round-2 correction/mapping content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Fix-author forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker `status.json`/`20-implementation.md`; active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, and `ACTIVE.json` (bookkeeper-owned). No behavior, schema, endpoint, or product-scope change.

Fix author must run exactly:
1. `rg -n 'offline|worker|latest published|last-good|cmd.error|not exposed|warnings|schema-prose drift' docs/api/public-market-contract.md`
2. `if rg -n 'then projects ONLY the selected row from the newly published|warnings.*diagnostic for a timeout|recorded as .accepted_merged_and_pushed.' docs/api/public-market-contract.md reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md; then exit 1; fi`
3. `python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json >/dev/null`
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`
5. `git diff --check`
6. `git diff --name-only` and verify only the two delivery docs plus append-only `40-fix-report.md` changed.

Append a Round-2 section to `40-fix-report.md` mapping F4/F5 to exact before/after text and command outputs; preserve the prior report text verbatim. Then stop for bookkeeper reconciliation. Bookkeeper must handle F6: add `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json` to active `delivery_files_under_review` and `changed_files`; update `ACTIVE.json` to the actual phase/timestamp; append—not rewrite—`60-test-output.txt` with exact scoped/full-range diff-check results; update active `status.json`/`70-handoff.md`; commit on the stage branch; recompute the standard fingerprint; run and preserve `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`; then redispatch Round-3 review-1 and review-2 under the existing provider-isolation rules.

## END PROMPT BODY
