# Dispatch Packet — fix（Review-2 REWORK）（executor: human operator → claude_glm）

操作者：在 Claude-GLM 终端执行下面 PROMPT BODY（read-file-and-execute 或整段粘贴）。
fix 作者 = `claude_glm`（原实现者，允许当 fix 作者；Codex/Kimi 是审稿人不可自修）。
执行后原始输出与 `40-fix-report.md` 落到 stage；**不 commit**（bookkeeper 负责提交）。

- Review-2：Codex `final_reviewer` = **REWORK**（schema-valid，指纹匹配），原文
  `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md`。
- rework 账本：1 / 3。
- PROMPT BODY 为 Codex `fix_start_prompt` 原文逐字保留，bookkeeper 未改其 findings/
  边界/命令。
- **注意 F3 覆盖了 review-1 的 P1-9 裁决**：review-1 曾判定 bookticker `status.json`
  保持不动；review-2 判定它仍含未来/待办措辞需历史化。以 review-2（终审）为准，本次
  允许并要求编辑 bookticker `status.json`（保留全部 SHA/指纹/Session ID/verdict/授权/
  证据事实，仅改时态/时间锚定）。禁改的是**本 active stage 的** `status.json`/
  `70-handoff.md`/`60-test-output.txt`（bookkeeper-only）。

Claude-GLM 执行：
`claude-glm -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/45-dispatch-fix-claude-glm.md)"`
（或打开本文件把 `## PROMPT BODY` 段贴进 Claude-GLM。）

---

## PROMPT BODY

Fix stage `2026-07-docs-truth-sync-v1` after Review-2 REWORK. Reviewed fingerprint: `c72987dc5cfe288e8df887cd14a965a48e93e3f3:bfd3106dd5a636868a66c56adfc7fdf94c00e57b251878633c9edc9d7265d812`. Raw review and raw final verdict JSON: `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (JSON is the final block in the same raw file). Read the raw file, `00-task.md`, `10-design.md`, `12-development-breakdown.md`, the fixed diff, and all evidence cited below; do not work from a bookkeeper summary.

Ordered findings to fix:
F1 P1 — `docs/api/public-market-contract.md:280-283` says empty history proves an upstream fetch succeeded. `backend/services/snapshot_service.py:259-315` and `backend/tests/test_funding_history_endpoint.py:238-250` show a pure PublishedState projection and a non-prewarmed symbol returning 200/empty without on-demand fetch. Impact: false completeness/freshness inference. Fix: document that empty means no entries in the published row and does not prove upstream success; explicitly disclose the narrower stale prose in `funding-history.schema.json:34` as a deferred schema-alignment item.
F2 P1 — `docs/api/public-market-contract.md:313-318` narrows partial to borrow fallback and timeout to deadline. `snapshot_service.py:1420-1437,1527` plus `test_symbol_snapshot_endpoint.py:252-270` show premium/history failures also produce partial; `snapshot_service.py:347-359` and assembly paths also produce timeout for no worker or no new publication. Impact: clients may trust stale public/history data. Fix: describe ok/partial/timeout from current code and state that `warnings` carries source-specific reasons; disclose the stale narrower prose in `symbol-snapshot.schema.json:39` without changing schema in this stage.
F3 P1 — bookticker `status.json:518,653`, `70-handoff.md:63-66,129`, and `20-implementation.md:79-82` retain current/future wording after accepted/merged/pushed Review-2 ACCEPT. Impact: resumed sessions see contradictory state. Fix: convert to completed past tense or explicitly time-scoped historical snapshot wording while preserving every SHA, fingerprint, Session ID, verdict, user authorization, and raw evidence fact.

Required fixes are exactly F1-F3. Allowed delivery files: `docs/api/public-market-contract.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`; `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`. Also create `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md` mapping F1/F2/F3 to exact edits and command outputs. Forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; `STAGE_INDEX.md`, `ROADMAP.md`, `harness-manifest.yaml`, `docs/harness-design.md`, `AGENTS.md`, `docs/planning/stage-branch-mode.md`, `docs/README`, `docs/architecture/ADR/`; and active-stage `status.json`, `70-handoff.md`, `60-test-output.txt` (bookkeeper-only checkpoint/evidence files). No behavior, schema, endpoint, or product-scope change.

Run exactly:
1. `python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json >/dev/null`
2. `rg -n 'pure projection|does not prove|premium_refresh_failed|funding_history_unavailable|worker_not_running|warnings' docs/api/public-market-contract.md`
3. `if rg -n 'Empty only when the upstream fetch succeeded|public/history refreshed but borrow fell back|the command reached its shared deadline before publication' docs/api/public-market-contract.md; then exit 1; fi`
4. `if rg -n 'local evidence commit and the single fresh Codex final review remain|After deterministic verification, the user performs visual acceptance|fresh Codex final-review invocation is requested|must be amended by fix 2|Kimi performs one bounded frontend-only UI adjustment|the user visually accepts it|invocation inspects' reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json; then exit 1; fi`
5. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`
6. `git diff --check`
7. `git diff --name-only` and verify every changed delivery path is in the Allowed list plus `40-fix-report.md`.

`40-fix-report.md` must contain a finding-to-fix table with rows F1/F2/F3, exact file/line evidence, before/after semantic summary, all command outputs, changed-file boundary result, and a footer. Do not rewrite the raw Review-2 evidence. After the fix author stops, the bookkeeper must independently reconcile the diff, update `60-test-output.txt`, active `status.json`/`70-handoff.md`/`ACTIVE.json`, commit on the stage branch, recompute the standard fingerprint, run and preserve `scripts/validate-stage.py 2026-07-docs-truth-sync-v1 --phase pre-review`, then redispatch the configured review gates.

## END PROMPT BODY
