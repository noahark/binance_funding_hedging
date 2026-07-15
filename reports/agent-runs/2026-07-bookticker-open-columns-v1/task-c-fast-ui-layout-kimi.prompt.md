# Task C — Kimi Fast UI Layout Adjustment

You are the frontend implementer for a user-approved fast UI adjustment inside
stage `2026-07-bookticker-open-columns-v1`. Make the smallest deterministic
frontend-only change. Do not redesign the backend contract or data semantics.

## Session And Git Rules

- Run in a fresh Kimi implementation Session using
  `kimi-code/kimi-for-coding`.
- Read `AGENTS.md`, `agents/developer-discipline.md`, this prompt, and the
  relevant current frontend source/tests before editing.
- Confirm branch `stage/2026-07-bookticker-open-columns-v1` and a clean starting
  worktree. Record the actual starting HEAD as `base_sha` in your report.
- Do not commit, merge, push, deploy, or call trading/private mutation APIs.
- Do not dispatch another model or subagent.

## Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md`

Everything else is forbidden, including backend, schemas, docs, API samples,
fixtures, Harness files, status/handoff files, and previous implementation or
review reports.

## Frozen UI Result

Keep exactly 12 table columns in this exact order:

1. `标的`
2. `标记价格 / 指数价格`
3. `正向开单`
4. `反向开单`
5. `资金费率`
6. `结算时间`
7. `日费率`
8. `年化 24h`
9. `年化 7D`
10. `年化 30D`
11. `日净收益`
12. `借贷状态 / 资产`

The empty-state must remain `colspan="12"`, and every rendered data row must
still contain exactly 12 `td` elements.

### 1. Symbol Cell

- Remove the rendered `现货腿: ...` / `B 后缀别名` line from the `标的` cell.
- Remove the now-unused local `spotAlias` rendering variable if applicable.
- Preserve symbol, base/quote text, direction badge, row selection, bStock row
  class, `data-symbol`, aria label, and all click/drawer behavior.
- Do **not** change the actual `row.spot.symbol`, bStock B-suffix join semantics,
  backend fields, fixture data, or the existing warnings-panel explanation of
  bStock aliases. This is display removal only.

### 2. Column Movement

- Move `标记价格 / 指数价格`, `正向开单`, and `反向开单` together to immediately
  follow `标的`, preserving that internal order.
- Move the combined `借贷状态 / 资产` cell to the final column.
- Preserve the combined cell's internal order and content: borrowing status and
  max-borrowable line above the asset tag. Preserve zero/borrowed-out semantics.
- Preserve the `日净收益` cell content and keep max-borrowable out of it.

### 3. Opening Quote Cell Layout

Both forward and reverse opening cells must be a vertical three-line stack:

- Forward line 1: `合约买一 <futures bid>`
- Forward line 2: `现货卖一 <spot ask>`
- Forward line 3: the formatted `forward_spread_pct`
- Reverse line 1: `现货买一 <spot bid>`
- Reverse line 2: `合约卖一 <futures ask>`
- Reverse line 3: the formatted `reverse_spread_pct`

The percentage must be below both prices, not beside them. Remove the current
side-by-side flex arrangement from `renderOpeningQuotesCell`. Preserve positive,
negative and muted classes, the independent percentage-point formatter, titles,
stale/unavailable whole-cell dash behavior, and incomplete per-direction
degradation. Do not multiply percentages by 100 or call `formatFundingRate`.

## Deterministic Self-Check Requirements

Update all cell-index assertions in `frontend/self-check.js` consistently with
the new mapping:

```text
0 symbol
1 mark/index
2 forward
3 reverse
4 funding
5 settlement
6 daily
7 annualized 24h
8 annualized 7d
9 annualized 30d
10 daily net yield
11 borrowing status / asset
```

Do not update only the final Task-B block; earlier daily/annualized/net-yield/
borrow-cost assertions also use hard-coded cell indexes and must remain valid.

Add or strengthen deterministic assertions for all of the following:

- exact ordered 12-header array above;
- every data row has 12 cells and empty state uses `colspan=12`;
- the last cell contains status before asset and the net-yield cell has no
  `可借:` duplication;
- a bStock fixture row's symbol cell contains neither `B 后缀别名` nor
  `现货腿:`, while existing resolved spot-symbol contract checks remain intact;
- forward DOM/text order is first leg < second leg < percentage;
- reverse DOM/text order is first leg < second leg < percentage;
- the opening-cell renderer no longer uses the old side-by-side `display:flex`
  layout;
- incomplete, stale, unavailable, missing-field, percentage sign/color and
  formatter tests still pass at the new column indexes.

Do not weaken an assertion merely to make it pass. Keep the expected frontend
PASS-line count explicit in the report.

## Required Commands

Run and report exact output for:

```bash
node frontend/self-check.js
node frontend/self-check.js | rg -c '^\[PASS\]'
python3 -m pytest backend/tests -q
git diff --check
git status --short
```

Also confirm `git diff --name-only <base_sha> --` contains only the three allowed
files. If a forbidden file changed, stop and report it; do not clean up user
work destructively.

## Implementation Report

Write `20-implementation-task-c.md` containing:

- actual provider/model/Session ID and source;
- base SHA and changed files;
- exact final header order and cell-index map;
- finding-to-change mapping for alias removal, column movement and three-line
  opening cells;
- exact command results and PASS-line count;
- confirmation that backend/schema/fixture/data semantics and side effects were
  not changed;
- remaining visual risks, if any.

End both the report and your response with:

```text
当前 Session ID: <provider-native Kimi Session ID>
Session ID 来源: <runtime_env|transcript_path|active_session_registry>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-c.md
本地北京时间: <obtain with local date command> CST
下一步模型: human
下一步任务: 执行页面显示验收；通过后由 Codex bookkeeper 准备唯一一次 fresh final review
```

Stop after implementation, tests and report. Return control to the human and
bookkeeper; do not start review yourself.
