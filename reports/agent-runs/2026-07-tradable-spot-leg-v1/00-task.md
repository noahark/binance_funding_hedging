# Task — Exclude Non-Trading Spot Legs

## Objective

Only a Binance spot symbol with `status == "TRADING"` may resolve as the public spot leg for a
funding-hedge row. Non-trading exact or bStock-alias records must be treated as no usable spot
leg.

## Required Behavior

1. Exact spot `TRADING` remains eligible and preserves current classification.
2. Exact spot `BREAK`, `HALT`, missing, or any other non-`TRADING` status does not resolve.
3. For `TRADIFI_PERPETUAL`, a non-trading exact record must not block fallback to a trading
   B-suffix alias.
4. A non-trading B-suffix alias does not resolve.
5. A futures `TRADING` row with no usable spot leg becomes:
   - `spot.exists = false`, `spot.symbol/status/match_type = null`;
   - `route_class = PERP_ONLY_EXCLUDED`;
   - `negative_funding_status = DISABLED_PERP_ONLY`;
   - `positive_funding_enabled = false`.
6. Existing `TRADING` exact and alias behavior remains unchanged.

## Acceptance Criteria

- Regression tests cover exact `TRADING`, exact `BREAK`, exact `HALT`, alias fallback after a
  non-trading exact record, and a non-trading alias.
- AERGOUSDT, XMRUSDT, and LITUSDT raw evidence is cited by the implementation report.
- Backend focused tests pass.
- Full backend suite passes.
- Frontend self-check passes unchanged.
- Documentation defines `spot.exists` and "spot leg" as a currently tradable resolved leg.
- No schema or frontend files change.

## Allowed Files

- `backend/domain/normalize.py`
- `backend/tests/test_snapshot.py`
- `docs/product/PRD.md`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/20-implementation.md`
- `reports/agent-runs/2026-07-tradable-spot-leg-v1/60-test-output.txt`

## Forbidden Files And Actions

- Frontend files, API schemas, adapters, private-account code, Harness scripts, other stages.
- Rewriting raw samples or review artifacts.
- Commits, pushes, merges, rebases, deployment, or model dispatch.

## Test Commands

```bash
python3 -m pytest backend/tests/test_snapshot.py -q
python3 -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/00-task.md
本地北京时间: 2026-07-18 12:23:14 CST
下一步模型: claude_glm
下一步任务: 按 08 派工包实现可交易现货腿状态门并提交原始测试证据
