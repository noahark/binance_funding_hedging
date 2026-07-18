# Implementation Report — Tradable Spot Leg Status Gate

## Provider / Model / Session

- Provider: `zhipu_glm` (accessed as `claude_glm` through Claude Code).
- Model: `glm-5.2` (dispatch identity `glm-5.2[1m]`).
- Provider-native Session ID: `unavailable` — the implementation terminal cannot
  directly observe the zhipu provider-native session id through the Claude Code
  adapter. The runner / human operator may add the verified id to
  `status.json.session_receipts` under `role: implementer`.
- Session ID source: `unavailable`.

## Files Changed

All writes are inside the dispatch `allowed_files` boundary. No other file was
touched.

| File | Change |
|---|---|
| `backend/domain/normalize.py` | Added the `TRADING` status gate to `resolve_spot_leg`. |
| `backend/tests/test_snapshot.py` | Added 6 regression tests for the status gate. |
| `docs/product/PRD.md` | Narrow wording: `spot leg` / `PERP_ONLY_EXCLUDED` now mean a currently tradable resolved leg. |
| `docs/api/public-market-contract.md` | Narrow wording: spot-leg resolution rule gates on `status == "TRADING"`. |
| `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt` | Appended the four required command outputs. |

`git diff --stat`:

```text
 backend/domain/normalize.py                        |  45 +++++--
 backend/tests/test_snapshot.py                     |  89 +++++++++++-
 docs/api/public-market-contract.md                 |  26 +++-
 docs/product/PRD.md                                |  12 +-
 .../60-test-output.txt                             | 150 +++++++++++++++++++++
 5 files changed, 298 insertions(+), 24 deletions(-)
```

## Implementation Summary

The resolver invariant from `10-design.md` / `11-adr.md` is enforced inside
`backend/domain/normalize.py`, the domain boundary used by every row builder —
not only in a service-side index. A small private helper gates both candidates:

```python
def _tradable_spot(spot_by_sym: dict, symbol: str) -> Optional[dict]:
    spot = spot_by_sym.get(symbol)
    if spot is not None and spot.get("status") == "TRADING":
        return spot
    return None
```

`resolve_spot_leg` now resolves through that helper:

1. `exact = _tradable_spot(spot_by_sym, base_asset + quote_asset)`; on hit return
   `(exact, "exact_symbol")`.
2. For `contract_type == "TRADIFI_PERPETUAL"` only:
   `alias = _tradable_spot(spot_by_sym, base_asset + "B" + quote_asset)`; on hit
   return `(alias, "bstock_b_suffix_alias")`.
3. Otherwise `(None, None)`.

This satisfies the required invariant exactly:

- An exact spot record resolves only when `status == "TRADING"`.
- Absent, missing-`status`, `BREAK`, `HALT`, and every other value fail closed
  (helper returns `None`).
- For `TRADIFI_PERPETUAL`, a non-trading exact record is skipped before the
  B-suffix alias is tried, so a trading alias can still resolve.
- The B-suffix alias also resolves only when its own `status == "TRADING"`.
- Existing match-type strings (`exact_symbol`, `bstock_b_suffix_alias`) and all
  existing behavior for tradable exact and alias records are preserved.

Downstream, when `resolve_spot_leg` returns `(None, None)`, `build_rows`
(`backend/domain/snapshot.py`) already produces the required no-leg shape without
any further change: `spot.exists = false`, `spot.symbol/status/match_type = null`,
`route_class = PERP_ONLY_EXCLUDED`, `negative_funding_status =
DISABLED_PERP_ONLY`, `positive_funding_enabled = false`. This is the behavior
specified in `00-task.md` step 5, reached purely through the existing classifier
(`backend/domain/classify.py` is unchanged).

## Test Matrix Mapping

Six regression tests were added to `backend/tests/test_snapshot.py` under the
"tradable spot-leg status gate" section. Each maps to a dispatch / `10-design.md`
matrix case:

| # | Case | Test function | Asserts |
|---|---|---|---|
| 1 | exact `TRADING` remains eligible | `test_spot_leg_exact_trading_resolves` | `(spot, "exact_symbol")` |
| 2 | exact `BREAK` does not resolve + excluded route shape | `test_spot_leg_exact_break_does_not_resolve_and_excludes_route` | `(None, None)` and `build_rows` -> `PERP_ONLY_EXCLUDED` / `DISABLED_PERP_ONLY` / `positive_funding_enabled=False` / `spot.exists=False` / null spot fields |
| 3 | exact `HALT` does not resolve | `test_spot_leg_exact_halt_does_not_resolve` | `(None, None)` |
| 4 | non-trading exact does not block a `TRADING` B-suffix alias | `test_spot_leg_non_trading_exact_does_not_block_trading_alias` | `(TSLABUSDT, "bstock_b_suffix_alias")` |
| 5 | non-trading B-suffix alias does not resolve | `test_spot_leg_non_trading_alias_does_not_resolve` | `(None, None)` |
| 6 | missing or unknown status fails closed | `test_spot_leg_missing_or_unknown_status_fails_closed` | missing-`status` dict and `status="AUCTION_MATCHING"` both -> `(None, None)` |

`resolve_spot_leg` was added to the test module import line
(`from backend.domain.normalize import iso_from_ms, resolve_spot_leg`) so the
six tests call the resolver directly; case 2 also drives `build_rows` to verify
the full excluded row shape.

Raw output path: `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt`.

## Frozen Public Sample — What It Proves

Frozen sample: `reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`
(`request-manifest.md` + `raw/`, unsigned public GETs only).

It proves the contract-relevant fact that motivates this stage: a symbol can
remain present in spot `exchangeInfo` while not being a currently tradable spot
leg.

- `raw/api-v3-exchangeInfo-symbols.json`: `AERGOUSDT`, `XMRUSDT`, `LITUSDT` all
  carry `"status": "BREAK"` and `"isMarginTradingAllowed": false`.
- `raw/api-v3-ticker-bookTicker-symbols.json`: all three spot bookTickers are
  `bidPrice/askPrice = "0.00000000"` (no spot liquidity).
- `raw/fapi-v1-ticker-bookTicker-AERGOUSDT.json` (and XMR/LIT): the matching
  perpetuals quote normally (`AERGOUSDT` 0.0238300/0.0238400, `LITUSDT`
  2.248700/2.248800, `XMRUSDT` 332.03/332.06).

So symbol presence plus `isMarginTradingAllowed=false` is insufficient for route
classification; only `status == "TRADING"` is. After this change these three
futures rows resolve no usable spot leg and become `PERP_ONLY_EXCLUDED` /
`DISABLED_PERP_ONLY`. The implementation report cites this evidence path per the
`00-task.md` acceptance criterion.

## Unchanged Behavior Confirmation

- **Schema**: `schemas/api/public-market-snapshot/...` is not in the allowed
  boundary and was not touched. No field, enum, or `match_type` string was added
  or renamed; the no-leg shape is the pre-existing `spot.exists=false` /
  null-fields serialization.
- **Frontend**: `frontend/self-check.js` ran unchanged and every check passed
  (see `60-test-output.txt`); no frontend file was modified.
- **Private-account code**: untouched; private enrichment, borrow-validation,
  and account blocks are outside the boundary.
- **Execution**: no order, borrow, repay, transfer, or close surface exists or
  was added; the workstation remains read-only.

## BLOCKER — `backend/tests/test_normalize.py` (allowed-writes gap)

The full backend suite does **not** pass yet, and the cause is a dispatch
`allowed_files` gap, not a defect in the implementation. The user was asked and
chose **守边界 (hold the boundary)**: this report records the blocker rather
than expanding scope.

`backend/tests/test_normalize.py` has three pre-existing `resolve_spot_leg` unit
tests whose minimal spot fixtures omit the `status` field:

- `test_resolve_spot_leg_exact_symbol` (line 99): `{"BTCUSDT": {"symbol": "BTCUSDT"}}`
- `test_resolve_spot_leg_bstock_alias_for_tradifi` (line 107): `{"TSLABUSDT": {"symbol": "TSLABUSDT"}}`
- `test_resolve_spot_leg_exact_beats_alias_for_tradifi` (lines 130-133): both fixtures omit `status`

Under the new invariant (ADR / dispatch test case 6: missing `status` must fail
closed), a missing-`status` record is no longer tradable, so these three
assertions now hit `'NoneType' object is not subscriptable`. This is the intended
new semantics; the fixtures simply pre-date it and were not listed in the
dispatch `allowed_files` (only `backend/tests/test_snapshot.py` was).

`60-test-output.txt` records the真实 result: `pytest backend/tests -q` ->
`3 failed, 378 passed`, `exit=1`. `test_snapshot.py` alone is green
(`31 passed`, `exit=0`), and `node frontend/self-check.js` and `git diff --check`
are clean.

The mechanical fix is to give the three fixtures a `"status": "TRADING"` entry
(the test intents — exact resolves, alias resolves, exact beats alias — are
unchanged). It is out of scope here; the exact diff for the bookkeeper is:

```diff
--- a/backend/tests/test_normalize.py
+++ b/backend/tests/test_normalize.py
@@ -98,7 +98,7 @@ def test_iso_from_ms_ignores_subsecond_part():

 def test_resolve_spot_leg_exact_symbol():
-    spot = {"BTCUSDT": {"symbol": "BTCUSDT"}}
+    spot = {"BTCUSDT": {"symbol": "BTCUSDT", "status": "TRADING"}}
     obj, match_type = resolve_spot_leg("PERPETUAL", "BTC", "USDT", spot)
     assert obj["symbol"] == "BTCUSDT"
     assert match_type == "exact_symbol"
@@ -105,7 +105,7 @@ def test_resolve_spot_leg_exact_symbol():
 def test_resolve_spot_leg_bstock_alias_for_tradifi():
     # Futures TSLAUSDT -> spot TSLABUSDT via baseAsset+"B"+quoteAsset alias.
-    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT"}}
+    spot = {"TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"}}
     obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
     assert obj["symbol"] == "TSLABUSDT"
     assert match_type == "bstock_b_suffix_alias"
@@ -127,8 +127,8 @@ def test_resolve_spot_leg_none_when_no_spot():
     # If a TRADIFI futures symbol coincidentally also has an EXACT spot symbol,
     # exact-symbol matching wins (alias is a fallback, never a replacement).
     spot = {
-        "TSLAUSDT": {"symbol": "TSLAUSDT"},
-        "TSLABUSDT": {"symbol": "TSLABUSDT"},
+        "TSLAUSDT": {"symbol": "TSLAUSDT", "status": "TRADING"},
+        "TSLABUSDT": {"symbol": "TSLABUSDT", "status": "TRADING"},
     }
     obj, match_type = resolve_spot_leg("TRADIFI_PERPETUAL", "TSLA", "USDT", spot)
     assert obj["symbol"] == "TSLAUSDT"
```

After that fix the full backend suite is expected to be `381 passed` (378 + 3),
unblocking `review-1`. The other two `resolve_spot_leg` tests in that file
(`test_resolve_spot_leg_alias_not_triggered_for_perpetual`,
`test_resolve_spot_leg_none_when_no_spot`) already expect `None` and stay green.

The bookkeeper should either (a) extend `status.json` task `allowed_files` and
re-dispatch the one-line fixture update to `claude_glm`, or (b) apply the diff
itself as a bookkeeper-side test-fixture correction before the evidence commit.

## git status / Commits / Push

```text
$ git status --short
 M backend/domain/normalize.py
 M backend/tests/test_snapshot.py
 M docs/api/public-market-contract.md
 M docs/product/PRD.md
 M reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt
```

Branch: `stage/2026-07-tradable-spot-leg-v1` (HEAD `0e334e0`, unchanged — no
commit made). Worktree changes are uncommitted, which is allowed for an
in-progress checkpoint before a review gate.

No commit, no push, no merge, no rebase, no deploy, and no model dispatch was
performed. No credentials were inspected, printed, stored, or summarized. No
order, borrow, repay, transfer, or close action was taken.

## Blocker Resolution — `backend/tests/test_normalize.py` fixture repair

Resolved under the user-authorized scope extension
(`reports/agent-runs/2026-07-tradable-spot-leg-v1/07-scope-extension-authorization.md`,
`Authorized by: user`, `2026-07-18T13:43:26+08:00`) via dispatch
`09-dispatch-claude-glm-test-fixture-repair.md`. The original BLOCKER narrative
above is preserved unchanged.

Authorized file touched: `backend/tests/test_normalize.py` only.

Exact fixture-only change — four `"status": "TRADING"` field additions across
three tests. No assertion, test-name, production-code, documentation, or
resolver-semantics change; missing/unknown status still fails closed:

- `test_resolve_spot_leg_exact_symbol`: `BTCUSDT` spot record -> added
  `"status": "TRADING"`.
- `test_resolve_spot_leg_bstock_alias_for_tradifi`: `TSLABUSDT` spot record ->
  added `"status": "TRADING"`.
- `test_resolve_spot_leg_exact_beats_alias_for_tradifi`: both `TSLAUSDT` and
  `TSLABUSDT` spot records -> added `"status": "TRADING"`.

The separate `TSLABUSDT` fixture in
`test_resolve_spot_leg_alias_not_triggered_for_perpetual` was intentionally left
unchanged: that test asserts a `PERPETUAL` does not fall back to the alias
(expects `None`), independent of the status gate.

Command outcomes (new timestamped repair run appended to `60-test-output.txt`;
the earlier failing run is preserved verbatim as audit evidence):

```text
python3 -m pytest backend/tests/test_normalize.py -q  -> 17 passed,  exit=0
python3 -m pytest backend/tests/test_snapshot.py -q   -> 31 passed,  exit=0
python3 -m pytest backend/tests -q                     -> 381 passed, exit=0
node frontend/self-check.js                            -> 全部自检通过, exit=0
git diff --check                                       -> clean,     exit=0
git status --short                                     -> listed in evidence file
```

**Full backend suite is green: `381 passed` (was `3 failed, 378 passed`).** The
stage's test acceptance criteria are now met. No schema, frontend, private, or
execution behavior changed.

Provider-native Session ID for this implementation session is recorded by the
bookkeeper in `status.json.session_receipts` as
`bb16025d-d15d-47d1-969a-0df4a2f4be14` (provider `zhipu_glm`, model `glm-5.2`,
source `transcript_path`, role `implementation_backend_spot_status_gate`). The
implementation terminal cannot directly observe the provider-native id through
the Claude Code adapter, so this report cites the bookkeeper-recorded value
rather than a directly-observed one.

---
当前 Session ID: bb16025d-d15d-47d1-969a-0df4a2f4be14（经 bookkeeper 记录于 status.json.session_receipts；实现终端无法直接观测 provider-native id）
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md
本地北京时间: 2026-07-18 13:52:50 CST
下一步模型: Codex bookkeeper
下一步任务: 核验 fixture-only 修复和全量测试，创建本地 evidence commit 并准备 Kimi review-1
