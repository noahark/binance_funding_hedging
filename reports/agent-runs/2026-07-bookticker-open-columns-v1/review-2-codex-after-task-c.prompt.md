# Formal Review-2 Dispatch — Post-Task-C Codex Final Review

You are the sole new final `reality_checker` for stage
`2026-07-bookticker-open-columns-v1`. Work strictly read-only. Do not modify any
file, commit, merge, push, deploy, call a trading/private mutation endpoint, or
expose credentials.

Run this packet exactly once in a fresh Codex `gpt-5.5` Session with `xhigh`
reasoning. Do not reuse bookkeeper/design Session
`019f639a-7890-7573-a04b-7a62debff633`. Codex participated in stage design but
did not implement or fix delivery code, so set
`reviewer_prior_involvement: "design"` and disclose the override evidence in
`reviewer_prior_involvement_notes`.

## Fixed Reviewed State

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Required branch: `stage/2026-07-bookticker-open-columns-v1`
- Full-stage base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`
- Fixed product/evidence head SHA:
  `a9218b7f1f8b8b5273cd382b29c015e33ad3cf4c`
- Required full-stage fingerprint:
  `a9218b7f1f8b8b5273cd382b29c015e33ad3cf4c:dd72d6aec09a8e95c19af528dafd46635c3114d44dcb43fc3bebd5f75fd64377`
- Task C base SHA: `f1790c15f56b9e9be8846b40fe03c88ed7210213`
- Task C fixed fingerprint:
  `a9218b7f1f8b8b5273cd382b29c015e33ad3cf4c:2e35b267686d86f94d652bbec2da2ed6630de9436f2d1ebadd2b39e7e8ece4c2`

Fingerprint protocol:

```text
head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json")
```

Review exactly the fixed full-stage range. Later dispatch/bookkeeping commits
are outside the reviewed delivery range. Independently recompute both
fingerprints and return `BLOCKED` if either differs.

The older `review-2-codex.prompt.md` is superseded and must not be used. No
formal review-2 Session has executed before this one.

## Authority And Isolation

Read first:

- `AGENTS.md`;
- only the `review-2` workflow section in
  `workflows/templates/stage-delivery.yaml`;
- `agents/skills/reality-checker.md`;
- `schemas/review-verdict.schema.json`;
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/review-2-eligibility-evidence.md`.

Because Codex previously designed this stage, treat `10-design.md`, `11-adr.md`,
the development breakdown and reconciliation as evidence under review, not as
unquestionable authority. Use the user's approved scope, `docs/product/PRD.md`,
canonical product documents, actual code and runtime evidence as higher
authority.

Implementation providers are Claude-GLM/`zhipu_glm` and Kimi/`moonshot_kimi`.
Codex/OpenAI authored no delivery or fix code. Verify that isolation from the
raw reports and status instead of accepting this statement on trust.

## Raw Evidence To Inspect

- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/15-session-id-capture-evidence.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/21-bookkeeper-task-b-verification.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-a.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-b.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/31-advisory-review-grok-round-2.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/task-c-fast-ui-layout-kimi.prompt.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/task-c-fast-ui-layout-kimi-format-addendum.prompt.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/60-test-output.txt`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
- the actual committed diff and every changed runtime, test, contract, Harness
  and public-sample file in the fixed full-stage range.

Do not recursively scan unrelated stages or any `history/` directory. Do not
rely only on the aggregate reports.

## Mandatory Final-Review Focus

1. Challenge the backend/public-contract implementation: paired full-universe
   spot/futures `bookTicker`, approximately 60-second cache cadence, atomic
   success, last-good retention, staleness boundary, Decimal formula/order,
   bStock alias join, schema compatibility and selected-symbol no-extra-fetch
   behavior.
2. Verify the final 12-column UI order exactly:
   `标的 → 标记价格 / 指数价格 → 正向开单 → 反向开单 → 资金费率 → 结算时间 → 日费率 → 年化 24h → 年化 7D → 年化 30D → 日净收益 → 借贷状态 / 资产`.
3. Verify Task C removed only the symbol-cell B-suffix alias display, preserved
   bStock semantics/warnings, moved the combined borrowing/asset cell last and
   retained its status-above-asset ordering.
4. Verify forward opening displays futures bid above spot ask; reverse displays
   spot bid above futures ask; each spread is its third vertical line and is
   already percentage points without a second ×100 conversion.
5. Verify table funding and daily rates use fixed 3-decimal percentage display;
   annualized 24h/7D/30D use fixed 2 decimals in table and drawer. Confirm the
   implementation uses decimal-string `ROUND_HALF_UP`, carries correctly and
   normalizes rounded negative zero without binary float/`toFixed()`.
6. Confirm Task C did not change the display semantics of daily net yield,
   borrow-cost sublines, settled history rates, opening spreads, prices,
   amounts or USDT values.
7. Verify degraded/null/stale/incomplete states remain safe, interactions still
   work, exactly 12 cells render, and there is no trading/order/borrow/repay/
   transfer/private mutation surface.
8. Challenge both formal review-1 ACCEPT verdicts, the Grok advisory findings,
   Kimi Task C report, the bookkeeper test evidence and the user's recorded
   visual acceptance against the code. Report every missed P0/P1/P2 and any
   useful P3 residual risk.
9. Verify Session IDs and Harness amendments are bounded and contain no secrets,
   and verify changed-file/authorship boundaries.

## Required Read-Only Checks

Run at least:

```bash
git branch --show-current
git diff --check fea9fdc3ecce7675b34b01fe0a4b9de08811f939..a9218b7f1f8b8b5273cd382b29c015e33ad3cf4c
git diff --name-status fea9fdc3ecce7675b34b01fe0a4b9de08811f939..a9218b7f1f8b8b5273cd382b29c015e33ad3cf4c
node frontend/self-check.js
node frontend/self-check.js | rg -c '^\[PASS\]'
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider backend/tests -q
python3 -m json.tool frontend/fixture/public-market-snapshot.json
python3 -m json.tool reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json
```

Recompute the full and Task C fingerprints with the exact protocol. Inspect
source directly around every material formula/formatter and do not infer
correctness from passing tests alone.

## Strict Output Contract

Your response must end with exactly one bare JSON object matching
`schemas/review-verdict.schema.json`; do not wrap it in a code fence and do not
write anything after it. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-bookticker-open-columns-v1`
- `role`: `final_reviewer`
- `model`: the actual Codex model
- `diff_fingerprint`: the required full-stage fingerprint above
- `reviewer_prior_involvement`: `design`
- `reviewer_prior_involvement_notes`: disclose the fresh-Session design
  override and cite `review-2-eligibility-evidence.md`

For `ACCEPT`, `required_fixes` must be empty and `next_action` must be
`stage_accepted_waiting_user`. For `REWORK`, include `fix_start_prompt` with the
raw finding paths, ordered fixes, Kimi/Claude-GLM domain routing, allowed and
forbidden files, exact tests and required `40-fix-report.md` mapping. For
missing evidence, fingerprint mismatch or an unresolvable read-only check,
return `BLOCKED` with `next_action: human_escalation_required`.

Immediately before the final JSON object, print this navigation footer using
the real fresh reviewer Session ID and a timestamp from local `date`:

```text
当前 Session ID: <provider-native fresh Codex Session ID>
Session ID 来源: <runtime_env|transcript_path|active_session_registry>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/50-review-2.md
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: codex_bookkeeper
下一步任务: 校验唯一一次 review-2 的 JSON、fingerprint、prior-involvement disclosure 与 gate transition
```
