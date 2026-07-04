# Post-Review Finding: Spot-Leg Join Hardcodes quote_asset="USDT"

Stage: `2026-07-public-market-bstock-alias-v1`
Finding time: 2026-07-04 10:27 CST
Severity: P1 regression fix required before user final acceptance
Reviewer: anthropic / claude-fable-5 (user-directed external post-review; NO
prior involvement in this stage — this session also corrects the earlier
"Fable5 unavailable" record: Fable5 is reachable as of 2026-07-04)
Reviewed diff: base `d240e43e75034a6718ede79bc295d39e77cd860e` .. head
`b1894406cf50173fc110f92b63fc3fe2f7ad7fc1`
(stage diff_fingerprint `b1894406cf50173fc110f92b63fc3fe2f7ad7fc1:9d6569d15b987c10eaa008b8b9b344f11c70aeaea7fe84d82dbb6030c89f0aba`)

## Summary

Task A replaced the exact spot-leg join `spot = spot_by_sym.get(sym)` with
`resolve_spot_leg(...)`. The pure function
`backend/domain/normalize.py:resolve_spot_leg` is correct and matches the
frozen contract amendment. The defect is at the single call site
`backend/domain/snapshot.py:70`, which passes the literal `"USDT"` as
`quote_asset` instead of `obj.get("quoteAsset", "")`:

```python
spot, match_type = resolve_spot_leg(
    contract_type, obj.get("baseAsset", ""), "USDT", spot_by_sym
)
```

The upstream universe filter (`backend/services/snapshot_service.py:61-66`)
selects on `status == "TRADING"` and `contractType in ("PERPETUAL",
"TRADIFI_PERPETUAL")` only — it does NOT filter on `quoteAsset`. Every
non-USDT-quoted perpetual therefore has its spot leg resolved as
`baseAsset + "USDT"` instead of its own symbol, and the result is labeled
`match_type = "exact_symbol"` even though the futures and spot symbols differ.

This violates the stage's own frozen contract amendment
(`docs/api/public-market-contract.md` lines 96-99): "normal crypto: join by
exact symbol (`BTCUSDT` -> `BTCUSDT`)", alias rule
`futures.baseAsset + "B" + futures.quoteAsset`. It also falsifies the design
claim in `00-task.md` / `10-design.md` that "normal crypto exact-symbol
matching is never polluted".

## Live Evidence (replayable, offline, from this stage's own captured raw)

Raw inputs (already committed, read-only):

- `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/fapi-v1-exchangeInfo.json`
- `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/api-v3-exchangeInfo.json`

Observed on that raw (checked 2026-07-04):

- Eligible universe = 691 TRADING perpetuals/TRADIFI; quoteAsset distribution:
  USDT 648, USDC 38, USD1 2, U 2, BTC 1 — **43 non-USDT rows**.
- **39 of the 43 rows change observable output** under head `b189440` relative
  to the pre-stage behavior (impl-v1 head `ce00489`, exact `sym` lookup):
  - `BTCUSDC` futures: spot leg was `BTCUSDC`, now resolves to `BTCUSDT`,
    labeled `exact_symbol`.
  - `ETHBTC` futures: spot leg was `ETHBTC`, now resolves to `ETHUSDT`.
  - `PNUTUSDC`: route flips `SPOT_ONLY_CANDIDATE` -> `MARGIN_SPOT_CANDIDATE`
    because the margin flag is read from the wrong pair (`PNUTUSDT`).
  - `BTCU`/`ETHU`/`BTCUSD1`/`ETHUSD1` similarly remap to the `*USDT` spot pair.
- `spot.min_notional`, `spot.step_size`, and `isMarginTradingAllowed` for all
  39 rows are sourced from the wrong spot pair.
- Sanity check for the fix: all 691 eligible symbols satisfy
  `baseAsset + quoteAsset == symbol`, so passing the real `quoteAsset` at the
  call site is exactly equivalent to the pre-stage `spot_by_sym.get(sym)`
  behavior for the exact branch, while keeping the bStock alias branch intact.

Replay:

```bash
python3 - <<'EOF'
import json
d='reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/'
raw=json.load(open(d+'fapi-v1-exchangeInfo.json'))
spot=json.load(open(d+'api-v3-exchangeInfo.json'))
spot_by={s['symbol']:s for s in spot['symbols']}
syms=[s for s in raw['symbols'] if s.get('status')=='TRADING'
      and s.get('contractType') in ('PERPETUAL','TRADIFI_PERPETUAL')]
assert all(s['baseAsset']+s['quoteAsset']==s['symbol'] for s in syms)
for s in syms:
    if s['quoteAsset']!='USDT':
        old=spot_by.get(s['symbol']); new=spot_by.get(s['baseAsset']+'USDT')
        if (old and old['symbol'])!=(new and new['symbol']):
            print(s['symbol'],'old:',old and old['symbol'],'new:',new and new['symbol'])
EOF
```

## Why review-1 / review-2 / live recheck missed it

- All synthetic fixtures (`backend/tests/fixtures/bstock-alias-raw/`) contain
  only USDT-quoted symbols; the 52-test suite passes with the bug present.
- `resolve_spot_leg` unit tests exercise the pure function's `quote_asset`
  parameter correctly — the call site is the only untested path.
- `verify-on-live-raw.py` checks the 15 bStocks plus one negative control
  (`BTCUSDT`, itself USDT-quoted); it never inspects a USDC-quoted perpetual,
  although the disproving data is in the very raw files it loads.

## Impact

For a funding-rate hedging tool, `spot.symbol` is the identity of the hedge
leg. 39 live rows advertise a hedge leg in a different quote currency than the
futures contract (e.g. short `BTCUSDC` perp hedged with long `BTCUSDT` spot),
with min-notional/step-size/margin data from the wrong pair, and one route
misclassification (`PNUTUSDC`). The bStock alias closure itself (15/15) is
unaffected and remains valid.

## Required Fix (rework round 1, minimal scope)

1. `backend/domain/snapshot.py:70`: pass `obj.get("quoteAsset", "")` instead
   of the literal `"USDT"`. Do NOT change `resolve_spot_leg` itself, and do
   NOT change `classify.py`.
2. Regression tests: extend the synthetic fixture with at least one
   USDC-quoted PERPETUAL (e.g. futures `BTCUSDC` + spot `BTCUSDC` +
   spot `BTCUSDT` both present) and assert:
   - its `spot.symbol == "BTCUSDC"`, `match_type == "exact_symbol"`;
   - it does NOT resolve to `BTCUSDT`;
   - existing bStock alias and USDT exact cases unchanged.
3. Offline re-verification against the already-captured live raw (no new HTTP):
   assert zero rows where `match_type == "exact_symbol"` and
   `spot.symbol != futures.symbol`; append output to `60-test-output.txt`.
4. `40-fix-report.md` with finding-to-fix mapping; then review-1 (task-level)
   re-verdict on the fix diff and a review-2 re-run bound to the new head.

## Out of Scope (pre-existing, deferred to user decision)

`schemas/api/public-market/snapshot.schema.json` declares
`row.quote_asset = {"const": "USDT"}` while the universe filter admits
non-USDT rows and `build_rows` hardcodes the field to `"USDT"`
(`backend/domain/snapshot.py:99`). This inconsistency predates this stage
(impl-v1) and the field value is wrong for 43 live rows. Options — (a) filter
the universe to `quoteAsset == "USDT"` to honor the schema const (removes 43
rows from the snapshot), or (b) widen the contract to multi-quote — change
observable scope and are the user's call, NOT part of this rework. Recorded in
`status.json.open_items`.

## Operational Footer

本地北京时间: 2026-07-04 10:27:11 CST
下一步模型: Claude-GLM (controller / Task A owner)
下一步任务: 按 `fix-start-prompt-spot-leg-quote-asset.md` 执行 rework 第 1 轮（修复 snapshot.py 调用点 + 回归测试 + 离线 live-raw 复验 + 40-fix-report.md），随后重跑 review-1/review-2 并重新绑定指纹。
