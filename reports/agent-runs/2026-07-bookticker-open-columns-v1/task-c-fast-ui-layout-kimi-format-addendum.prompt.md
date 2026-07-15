# Task C Addendum — Fixed Decimal Display For Funding Columns

Continue the existing Task C implementation in Kimi Session
`session_b4a656b7-91c8-43ae-a994-68cb2e10c03f`. The user added one small display
requirement before visual acceptance. Preserve all current uncommitted Task C
layout work; do not reset, discard, commit, merge or push it.

Read `AGENTS.md`, `agents/developer-discipline.md`, the original
`task-c-fast-ui-layout-kimi.prompt.md`, this addendum, and the current diff.

## Allowed Files

You may modify only:

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md`

The bookkeeper may have uncommitted stage prompt/status/handoff files in the
same shared worktree. They are not yours: do not edit, stage, revert or delete
them. Backend, schema, fixture, docs and every other source file remain
forbidden.

## Exact Display Requirement

In the default opportunity table:

- `资金费率`: fixed 3 decimal places after converting the raw fraction to a
  percentage, e.g. `-0.00030000` → `-0.030%`.
- `日费率`: fixed 3 decimal places, e.g. `-0.00060000` → `-0.060%`.
- `年化 24h`, `年化 7D`, `年化 30D`: fixed 2 decimal places, e.g.
  `-0.657` → `-65.70%`, `-0.00260714` → `-0.26%`, and
  `-0.00060833` → `-0.06%`.

The drawer's three annualized cards (`24h 预估`, `7D 已结算`, `30D 已结算`)
must use the same fixed 2-decimal display so annualized values are consistent
across the page.

Do not change these displays:

- `日净收益`;
- `日借币` account/VIP0 cost subline;
- settled funding-history item rates in the drawer;
- opening `*_spread_pct` (already fixed at 2 percentage-point decimals);
- price, amount or USDT-value formatters.

## Formatter Rules

- Preserve the existing `formatFundingRate(str)` behavior and its baseline test
  because other UI surfaces still use it.
- Add a narrowly named fixed-decimal helper (for example
  `formatFundingRateFixed(str, decimals)`) and expose it through
  `globalThis.__appHelpers` for deterministic testing.
- Work from the decimal string. Do not use binary floating-point multiplication
  plus `toFixed()` for financial display.
- Apply the existing semantic conversion first: raw fractional rate × 100.
- Round only for display using decimal `ROUND_HALF_UP` to the requested number
  of places.
- Preserve `+` for positive non-zero values and `-` for negative non-zero
  values.
- Normalize rounded negative zero to unsigned fixed zero:
  `0.000%` for 3 places or `0.00%` for 2 places.
- `null`, `undefined`, empty or invalid strings remain `—`.
- Keep existing color classes based on the raw value.

## Deterministic Tests

Update the visible table assertions to require the exact new strings, including
at least:

- a funding-rate cell with three places;
- all existing daily-rate fixture cases with three places and null → `—`;
- annualized 24h/7D/30D table values with two places and null → `—`;
- the drawer's three annualized values with two places.

Add direct helper vectors that lock:

- `-0.00030000`, 3 → `-0.030%`;
- `0.00030000`, 3 → `+0.030%`;
- `0`, 3 → `0.000%`;
- `-0.657`, 2 → `-65.70%`;
- `-0.00260714`, 2 → `-0.26%`;
- an exact HALF_UP carry boundary;
- a tiny negative value that rounds to unsigned zero;
- invalid and null inputs → `—`.

Retain all Task C column-order, alias-removal, three-line opening-cell, degraded
state, formatter isolation and no-side-effect assertions. Do not weaken prior
tests.

## Required Commands

Run and report exact results:

```bash
node frontend/self-check.js
node frontend/self-check.js | rg -c '^\[PASS\]'
python3 -m pytest backend/tests -q
git diff --check
git status --short
```

Amend `20-implementation-task-c.md` with this addendum's mapping, formatter
semantics, exact visible examples, updated PASS count and command results. Keep
the same Task C base SHA `f1790c15f56b9e9be8846b40fe03c88ed7210213`
and Session ID receipt.

End the report and response with:

```text
当前 Session ID: session_b4a656b7-91c8-43ae-a994-68cb2e10c03f
Session ID 来源: transcript_path (state.json workDir/lastPrompt cross-check)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md
本地北京时间: <obtain with local date command> CST
下一步模型: codex_bookkeeper
下一步任务: 核验 Task C 最终 bounded diff 与测试，然后交由用户页面显示验收
```

Stop after implementation, tests and report. Do not start review.
