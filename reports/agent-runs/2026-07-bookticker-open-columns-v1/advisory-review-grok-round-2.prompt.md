# User-Requested Advisory Review — Grok Round 2

You are an additional read-only advisory reviewer for stage
`2026-07-bookticker-open-columns-v1`. The user explicitly requested this round
before their own page-display acceptance and before formal review-2.

This is **not** formal review-1 or review-2 and must not be represented as a
Harness gate. Do not modify files, commit, merge, push, deploy, call trading
endpoints, or expose credentials. Return evidence and actionable findings only;
the human/bookkeeper will capture your response.

## Fixed Reviewed State

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Branch: `stage/2026-07-bookticker-open-columns-v1`
- Base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`
- Product/evidence head: `0a383f0f8528591898f12690c371108e7582a27e`
- Full-stage fingerprint:
  `0a383f0f8528591898f12690c371108e7582a27e:82b54a9742942623ea6ca63f53a4292da147fe9accd4daaff180648ad90a15ed`

Independently inspect the actual fixed diff. Later bookkeeping commits are not
part of the product/evidence range.

## Read These Raw Artifacts

- `AGENTS.md`
- stage-delivery workflow review rules relevant to advisory/final review
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`
- `14-design-review-reconciliation.md`
- `20-implementation-task-a.md`, `20-implementation-task-b.md`,
  `20-implementation.md`, `21-bookkeeper-task-b-verification.md`
- `30-review-1-task-a.md`, `30-review-1-task-b.md`, `30-review-1.md`
- `60-test-output.txt`
- actual backend/frontend/schema/docs/Harness diff and relevant source files
- live public sample evidence named by the stage under
  `reports/api-samples/2026-07-bookticker-discovery-v1/`

Do not rely on summaries alone. Challenge both review-1 ACCEPT verdicts.

## Advisory Focus

1. Verify the table is exactly 12 columns: `日净收益`, no rendered `提示标记`,
   combined borrowing status/asset cell, and no duplicated max-borrowable line.
2. Verify forward shows futures bid above spot ask, reverse shows spot bid above
   futures ask, and both use backend percentage-point strings without ×100.
3. Verify stale/unavailable/incomplete behavior, valid single-leg preservation,
   XAU no-substitute behavior, bStock alias behavior, and `—` rendering.
4. Verify the paired spot/futures full bookTicker cache is public, always-on,
   atomic on success, approximately 60 seconds, and unusable at about 120
   seconds without per-symbol HTTP or click-triggered extra requests.
5. Verify Decimal rounding/formula/schema compatibility and no trading/private
   mutation/WebSocket/credential surface.
6. Inspect the Session ID Harness amendment for boundedness and credential
   hygiene.
7. Identify any missed P0/P1/P2 finding, fragile regression coverage, or
   discrepancy between implementation reports, tests and actual diff.
8. Produce a short, concrete checklist for the user's subsequent visual page
   acceptance, including BTC/ANIME/HOME/XAU/bStock-style cases where useful.

Run useful read-only checks, including at least:

- fixed fingerprint recomputation
- `node frontend/self-check.js`
- `python3 -m pytest backend/tests -q`
- `git diff --check <base_sha>..<head_sha>`

## Output

Return:

1. `Advisory conclusion`: `READY_FOR_USER_VISUAL_ACCEPTANCE`,
   `ADVISORY_FINDINGS`, or `BLOCKED`.
2. Findings ordered P0 → P3 with file/line evidence, impact and recommendation.
3. Checks actually run and exact results.
4. A user visual-acceptance checklist.
5. Residual risks.

Do not output a formal Harness ACCEPT verdict and do not claim review-2 is
complete. End with:

```text
当前 Session ID: <provider-native Grok Session ID>
Session ID 来源: <runtime_env|transcript_path|active_session_registry>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/31-advisory-review-grok-round-2.md
本地北京时间: <obtain with local date command> CST
下一步模型: human
下一步任务: 根据 Grok findings 执行页面显示验收；之后由 bookkeeper 准备 Opus4.8 formal review-2
```
