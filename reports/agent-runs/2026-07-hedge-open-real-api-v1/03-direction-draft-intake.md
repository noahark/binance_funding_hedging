# Direction-Draft Intake — Hedge Open Real API v1

## Receipt And Identity

The following raw independent panel artifacts were received unchanged and are
not bookkeeper summaries:

| Panel member | Actual model | Raw artifact | Receipt state |
| --- | --- | --- | --- |
| `claude` | Claude Opus 4.8 | `direction-drafts/claude-opus-4-8.md` | received |
| `glm52` | GLM-5.2 | `direction-drafts/glm52.md` | received |
| `kimi_k3` | Kimi K3 | `direction-drafts/kimi27.md` | received; historical filename only |

The human operator confirmed on 2026-07-23 that `kimi27.md` was run by K3
before the K3 routing rename. The filename is preserved as raw evidence, while
the stage metadata identifies it as the K3 result. It must not be rerun merely
to obtain a K3-labelled filename.

The default MILESTONE panel is not yet complete: `codex` and `grok-build` still
need independent raw drafts, or an explicit unavailable/quota record. No formal
`06-direction-synthesis.md` is produced until that condition is met.

## Cross-Draft Consensus

All three received drafts support the frozen execution contract:

1. MARKET BUY by base `quantity=q_common` is a supported PAPI path. Both legs
   can use the same precomputed base quantity and be submitted concurrently.
   `quoteOrderQty` and the serial spot-fill-to-UM derivation are out of scope.
2. `q_common` must be computed with Decimal fixed-point from both venue's
   effective MARKET filters; zero-disabled `MARKET_LOT_SIZE` falls back to the
   applicable `LOT_SIZE` constraint, then every leg is formatted independently.
3. Every attempt needs fresh read-only preflight, an immutable snapshot, and a
   durable record containing both client IDs committed before either POST.
4. The real PAPI adapter belongs in this stage but remains gated by executor
   configuration, global Start, and separate human authorization of the first
   live task. No private call or live order is authorized by this intake.
5. Single-leg, timeout, unknown, or actual partial outcomes require pause and
   reconciliation by client ID; there is no automatic close, repair, borrow,
   or repay. F-003 through F-006 remain delivery work, not optional notes.

## Evidence Applicability Note

The raw API recon remains authoritative for endpoint capabilities, filters,
signing, rate-limit facts, and reconciliation endpoints. Its prior application
of those facts to a **quote-amount forward BUY** is superseded by the user's
later fixed-base concurrent decision. Consequently, the following recon
application claims are not implementation requirements for this stage:

- serial spot-fill then derived UM quantity (B-1);
- `quoteOrderQtyMarketAllowed` as an execution gate (B-3);
- UM quantity derived from spot `executedQty` (B-4); and
- related quote-buy model changes C-1, C-2, C-4, and C-6.

This note narrows applicability; it does not alter the raw recon artifact.

## Design Tension To Resolve In Synthesis

The raw drafts correctly flag a distinction that must be written precisely:
the user has frozen **no equality check between the two filled legs' actual
quantities**. Therefore a final design may record a signed residual and leave a
two-leg `FILLED` outcome unpaused solely because those two actual values differ.

It must not silently replace that decision with a tolerance or a numerical
product limit. Separately, the final state machine still needs a non-numeric
definition of exchange-reported partial/unknown execution (for example,
non-final order status, timeout, or a reconciliation result that reports a
partial state). The synthesis will distinguish those cases without turning a
cross-leg residual comparison into a gate.

## Remaining Questions For Direction

- For a forward base-quantity BUY, define the factual USDT-availability
  preflight source and estimate. Any extra slippage buffer is a risk-policy
  number and needs explicit user approval rather than an implicit new limit.
- Choose the F-006 live behavior: retain `fill-all` only if every attempt is
  re-gated, or remove it from the live surface. The received drafts favor
  re-gating/removing the old bypass behavior; no final choice is made here.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/03-direction-draft-intake.md
本地北京时间: 2026-07-23 16:45:40 CST
下一步模型: human operator
下一步任务: obtain the remaining mandatory Codex and Grok direction-panel evidence
