# Dispatch Packet — fix F7（user-authorized rework-limit override）（executor: human operator → claude_glm）

**用户已明确授权**超出 rework 上限(3/3→本轮为第 4 次)的最后一次限定 fix，且**豁免
round-4 review-1(Kimi)**——F7 fix 后直接派 Codex review-2。授权见
`status.user_authorizations[0]`。

在 Claude-GLM 终端执行 PROMPT BODY。fix 作者 = `claude_glm`。只改 F7 一处（契约一段
文字），不 commit。F8 已由 bookkeeper 处理，本包不含。

`claude-glm -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/47-dispatch-fix-f7-claude-glm.md)"`

---

## PROMPT BODY

Fix Review-2 Round-3 REWORK finding F7 for stage `2026-07-docs-truth-sync-v1` (user has authorized this fix beyond the 3/3 rework limit). Reviewed fingerprint: `568fd4160b67d3b73303134d6f078a6a59bb93d9:ec91074df380632652180548168583da1756669a9e63d0077f73041621fc1ffe`. Raw Round-3 review and strict verdict JSON: `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (JSON is the final block). Read that raw review, `40-fix-report.md`, the fixed diff, and every source/schema/test cited below; do not rely on a bookkeeper summary.

Finding F7 P1 — `docs/api/public-market-contract.md:323-336` promises that symbol-snapshot `published_version` is the same version as the full snapshot. The full snapshot wire schema and response contain no `published_version`; tests compare only against internal `service._published_version`, and separate HTTP reads can cross a later publication. Impact: clients may expect a nonexistent correlation field or atomic cross-response guarantee. Fix the human contract only: define the value as the internal PublishedState revision used for this row; explicitly state that full snapshot v1 does not expose a comparable version and gives no client-verifiable cross-request equality guarantee; preserve the fact that the row was selected from that internal state's snapshot. Extend the deferred `symbol-snapshot.schema.json:5` prose-drift note to include its same-version claim. Do not edit server or schemas.

Fix-author allowed files: `docs/api/public-market-contract.md` and append-only Round-3 content in `reports/agent-runs/2026-07-docs-truth-sync-v1/40-fix-report.md`. Fix-author forbidden: all `backend/`, `frontend/`, `schemas/`, `scripts/`; all Stage-B/Harness-track files; bookticker living-docs; active-stage `status.json`, `70-handoff.md`, `60-test-output.txt`, and `ACTIVE.json` (bookkeeper-owned). No behavior, endpoint, schema, or product-scope change.

Fix author must run exactly:
1. `rg -n 'published_version|full snapshot|internal PublishedState|cross-request|wire' docs/api/public-market-contract.md`
2. `if rg -n 'shares the same published_version as the full snapshot|same version as the full snapshot' docs/api/public-market-contract.md; then exit 1; fi`
3. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`
4. `node frontend/self-check.js`
5. `git diff --check`
6. `git diff --name-only` and verify only the contract plus append-only `40-fix-report.md` changed.

Append a Round-3 section to `40-fix-report.md` mapping F7 to exact before/after text and command outputs, preserving prior reports verbatim. Then stop for bookkeeper reconciliation.

## END PROMPT BODY
