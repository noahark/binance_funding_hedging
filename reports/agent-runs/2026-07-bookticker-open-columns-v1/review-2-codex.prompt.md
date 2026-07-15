# Formal Review-2 Dispatch — Codex Final Reality Check

You are the final `reality_checker` for stage
`2026-07-bookticker-open-columns-v1`. Work read-only. Do not modify any file,
commit, merge, push, deploy, call trading endpoints, or expose credentials.

This prompt must run in a fresh Codex `gpt-5.5` Session with `xhigh` reasoning.
Do not reuse bookkeeper/design Session
`019f639a-7890-7573-a04b-7a62debff633`. Your provider did participate in stage
design, so the verdict must set `reviewer_prior_involvement` to `design` and the
narrative must disclose this. You did not implement or fix delivery code.

## Fixed Reviewed State

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Branch: `stage/2026-07-bookticker-open-columns-v1`
- Base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`
- Product/evidence head SHA: `0a383f0f8528591898f12690c371108e7582a27e`
- Required full-stage fingerprint:
  `0a383f0f8528591898f12690c371108e7582a27e:82b54a9742942623ea6ca63f53a4292da147fe9accd4daaff180648ad90a15ed`
- Fingerprint protocol:
  `head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json")`

Review exactly the fixed range above. Later Harness/bookkeeping commits are not
part of the reviewed delivery diff. Independently recompute the fingerprint and
return `BLOCKED` if it does not match.

## Authority And Prior-Involvement Rule

Read `AGENTS.md`, the review-2 section of
`workflows/templates/stage-delivery.yaml`,
`agents/skills/reality-checker.md`, and
`schemas/review-verdict.schema.json` first.

Because the Codex provider participated in design, review the design artifacts
themselves instead of treating them as unquestionable requirements. Use the
user-approved scope recorded in `00-intake.md`/`00-task.md`,
`docs/product/PRD.md`, canonical product documents, and actual runtime evidence
as the top-level requirements. Treat `10-design.md`, `11-adr.md`,
`12-development-breakdown.md`, and `14-design-review-reconciliation.md` as
evidence under review.

Read the override evidence:
`reports/agent-runs/2026-07-bookticker-open-columns-v1/review-2-eligibility-evidence.md`.

## Raw Artifacts You Must Inspect

- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/15-session-id-capture-evidence.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/21-bookkeeper-task-b-verification.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-a.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-b.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
- raw diff for the fixed range and every changed runtime/test/contract/Harness
  file in that range
- `reports/api-samples/2026-07-bookticker-discovery-v1/` evidence named by the
  current stage documents; do not scan unrelated stage history

Do not rely only on the bookkeeper aggregate. Inspect both raw task review files
and the actual committed diff.

## Mandatory Final-Review Focus

1. Confirm the requested UI meaning exactly: 12 columns, `日净收益`, no rendered
   `提示标记`, combined borrowing-status/asset cell, correct forward/reverse leg
   order, independent percentage-point formatting, and dash degradation.
2. Confirm paired full-universe spot/futures bookTicker acquisition is public,
   always-on, approximately 60 seconds, atomic on success, last-good retained,
   and stale at `age >= 2 * ttl` without per-symbol requests.
3. Confirm Decimal-only formula/order/rounding/negative-zero behavior, bStock
   alias joining, no substitute spot asset, and schema backward compatibility.
4. Confirm selected-symbol refresh performs no extra bookTicker HTTP and the
   implementation adds no trading, order, borrow, transfer, WebSocket, secret,
   or private-side-effect surface.
5. Confirm the Session ID Harness amendment is bounded, truthful, contains no
   credential values, and does not weaken review/provider isolation.
6. Challenge both review-1 ACCEPT verdicts and their P3 observations against
   the raw diff and deterministic tests. Report any missed P0/P1/P2 issue.
7. Confirm changed-file boundaries, fixed fingerprints, and that no failing
   test evidence is hidden.

Run at least these read-only checks:

- `git diff --check <base_sha>..<head_sha>`
- independent fixed fingerprint recomputation
- `node frontend/self-check.js`
- `python3 -m pytest backend/tests -q`
- `python3 -m py_compile backend/adapters/binance_public.py backend/domain/snapshot.py backend/services/snapshot_service.py`
- JSON parsing for the frontend fixture, stage status, and review verdicts

## Output Contract

Return a concise evidence-based narrative followed by the navigation footer,
then end the entire response with exactly one bare JSON object matching
`schemas/review-verdict.schema.json`. Do not put the final JSON in a code fence
and do not add text after it.

The JSON must use:

- `schema_version`: `1`
- `stage_id`: `2026-07-bookticker-open-columns-v1`
- `role`: `final_reviewer`
- `model`: the actual Codex model
- `diff_fingerprint`: the required full-stage fingerprint above
- `reviewer_prior_involvement`: `design`
- `verdict`: `ACCEPT`, `REWORK`, or `BLOCKED`

If `REWORK`, include a ready-to-send `fix_start_prompt` containing raw evidence
paths, ordered findings, required fixes, allowed/forbidden file boundaries,
exact checks, and the required `40-fix-report.md` mapping. If evidence is
missing or the fingerprint/schema cannot be satisfied, return `BLOCKED`.

Footer immediately before the final JSON:

```text
当前 Session ID: <provider-native fresh Codex Session ID>
Session ID 来源: <runtime_env|transcript_path|active_session_registry>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/50-review-2.md
本地北京时间: <obtain with local date command> CST
下一步模型: codex_bookkeeper
下一步任务: 校验 review-2 JSON、fingerprint、prior-involvement disclosure 和最终 gate
```
