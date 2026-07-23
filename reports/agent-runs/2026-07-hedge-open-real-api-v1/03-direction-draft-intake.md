# Direction-Draft Intake — Hedge Open Real API v1

## Receipt And Identity

The following raw independent panel artifacts were received unchanged and are
not bookkeeper summaries:

| Panel member | Actual model | Raw artifact | Receipt state |
| --- | --- | --- | --- |
| `claude` | Claude Opus 4.8 | `direction-drafts/claude-opus-4-8.md` | received |
| `glm52` | GLM-5.2 | `direction-drafts/glm52.md` | received |
| `kimi_k3` | Kimi K3 | `direction-drafts/kimi27.md` | received; historical filename only |
| `codex` | GPT-5 Codex | `direction-drafts/codex.md` | received; SHA-256 verified |
| `grok-build` | — | `direction-drafts/grok-build.unavailable.md` | unavailable: operator reported no quota |

The human operator confirmed on 2026-07-23 that `kimi27.md` was run by K3
before the K3 routing rename. The filename is preserved as raw evidence, while
the stage metadata identifies it as the K3 result. It must not be rerun merely
to obtain a K3-labelled filename.

The default MILESTONE panel now has every available independent draft and an
explicit unavailable record for Grok. The formal `06-direction-synthesis.md`
may proceed after this user-policy update is incorporated.

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
5. Client-ID reconciliation, persistent order accounting, and no automatic
   close, repair, borrow, or repay remain required. The later user-selected
   one-second cadence supersedes earlier fill-state pause recommendations.

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

The user subsequently selected a one-second immediate cadence: actual fills,
residuals, partial states, and prior unresolved attempts are recorded and
queried but do not gate the next scheduled pair. A configurable default of
three confirmed consecutive failed pairs pauses further opening. See
`04-user-execution-policy.md` for the authoritative update.

## Remaining Questions For Direction

- Resolved on 2026-07-23: the user approved replacement of the stale PRD
  notional/rounds and cap model with the current fixed-base-quantity immediate
  contract, and removal of the stale manual-close-first-live-open gate.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/03-direction-draft-intake.md
本地北京时间: 2026-07-23 16:45:40 CST
下一步模型: human operator
下一步任务: obtain the remaining mandatory Codex and Grok direction-panel evidence
