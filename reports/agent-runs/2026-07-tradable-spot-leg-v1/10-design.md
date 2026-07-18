# Design — Tradable Spot Leg Resolution

## Current Failure

`SnapshotService` correctly filters futures symbols to `status == "TRADING"`, but its spot
index contains every exchange-info record. `resolve_spot_leg` currently returns the first exact
record regardless of status. Classification then sees a spot symbol with
`isMarginTradingAllowed=false` and incorrectly produces `SPOT_ONLY_CANDIDATE`.

## Design Decision

Enforce tradability inside `backend.domain.normalize.resolve_spot_leg`, the domain boundary used
by every row builder, rather than filtering only one service caller.

Conceptually:

```python
def tradable(symbol):
    spot = spot_by_sym.get(symbol)
    return spot if spot is not None and spot.get("status") == "TRADING" else None

exact = tradable(base_asset + quote_asset)
if exact is not None:
    return exact, "exact_symbol"
if contract_type == "TRADIFI_PERPETUAL":
    alias = tradable(base_asset + "B" + quote_asset)
    if alias is not None:
        return alias, "bstock_b_suffix_alias"
return None, None
```

The exact implementation may use a small local helper or equivalent simple checks. No new public
helper or abstraction is required.

## Why This Boundary

- All callers receive the same invariant, including direct `build_rows` tests and future callers.
- A BREAK/HALT exact record can be skipped before trying a valid bStock alias.
- The service may keep the raw exchange-info index without implying every entry is usable.
- Downstream classification, quote joining, flags, and UI labels already behave correctly when
  the resolver returns `(None, None)`.

## Contract Semantics

Within `public-market-snapshot/v1`, `spot.exists` means a currently usable resolved spot leg, not
merely that Binance retains a historical/non-trading exchange-info record. A non-`TRADING` record
therefore serializes as the existing no-leg shape; no schema field or enum changes.

## Test Matrix

| Futures | Exact spot | Alias spot | Expected match | Expected route |
|---|---|---|---|---|
| PERPETUAL/TRADING | TRADING | n/a | exact_symbol | existing candidate behavior |
| PERPETUAL/TRADING | BREAK | n/a | none | PERP_ONLY_EXCLUDED |
| PERPETUAL/TRADING | HALT | n/a | none | PERP_ONLY_EXCLUDED |
| TRADIFI/TRADING | BREAK | TRADING | bstock_b_suffix_alias | existing alias candidate behavior |
| TRADIFI/TRADING | absent | BREAK | none | PERP_ONLY_EXCLUDED |

## Risks And Review Focus

- Ensure status matching is exact and fail-closed; absent/unknown status is not tradable.
- Ensure a non-trading exact record does not suppress alias fallback.
- Ensure existing BTC/ETH/metal/bStock tests remain unchanged.
- Ensure documentation does not claim the raw symbol never existed.

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/10-design.md
本地北京时间: 2026-07-18 12:23:14 CST
下一步模型: claude_glm
下一步任务: 实现 resolver 状态门并完成测试矩阵
