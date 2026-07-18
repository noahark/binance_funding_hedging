# ADR — Gate Spot-Leg Resolution On `TRADING`

- Status: accepted for implementation
- Date: 2026-07-18
- Designer: Codex/OpenAI

## Context

Binance keeps non-trading spot symbols in `exchangeInfo`. Symbol presence alone is therefore not
evidence that the spot leg can form a contract-spot hedge. Current live evidence shows BREAK
records with zero spot book prices while the same-symbol perpetuals quote normally.

## Decision

`resolve_spot_leg` will resolve only spot records whose status is exactly `TRADING`. Both exact and
bStock B-suffix alias candidates use the same rule. A non-trading exact record is skipped, so a
trading alias may still resolve.

## Alternatives Considered

1. Filter `spot_by_sym` only in `SnapshotService`.
   - Rejected because direct domain callers could still pass unfiltered exchange-info records.
2. Pass spot status into `classify_route`.
   - Rejected because it duplicates resolution semantics and still leaves quote joins holding an
     unusable spot object.
3. Preserve BREAK metadata in the v1 row while classifying it as no leg.
   - Deferred because it would overload `spot.exists` or require a new contract field. Historical
     observation metadata can be a separate future amendment if needed.

## Consequences

- AERGOUSDT, XMRUSDT, LITUSDT and future non-trading spot matches become
  `PERP_ONLY_EXCLUDED` automatically.
- No frontend or schema change is required.
- If a spot symbol returns to `TRADING`, it becomes eligible again on the next snapshot.
- Documentation must clarify resolved-leg versus raw-record existence.

## Reviewer Focus

Validate fail-closed handling of missing/unknown statuses and alias fallback ordering.

---
当前 Session ID: 019f734a-dd82-7a11-8367-93fc1a5e954c
Session ID 来源: runtime_env
原始输出路径: reports/agent-runs/2026-07-tradable-spot-leg-v1/11-adr.md
本地北京时间: 2026-07-18 12:23:14 CST
下一步模型: claude_glm
下一步任务: 按 ADR 实现，无 schema/frontend 扩项
