# ADR — Hedge Open Real API v1

## ADR-1: Fixed-base concurrent two-leg orders

**Decision:** derive Decimal `q_common` before dispatch and concurrently submit
margin and UM MARKET legs with `quantity=q_common`.

**Why:** the approved contract fixes base quantity and prioritizes a one-second
immediate cadence. `quoteOrderQty` and serial spot-fill derivation are outside
this stage.

**Consequence:** validate/format each leg independently. Actual fills may
differ and are recorded without automatic action.

## ADR-2: Durable attempts and client-ID reconciliation

**Decision:** persist an immutable attempt and both client IDs before any POST.
Unknown transport results query before classification and are never blindly
resent.

**Why:** a response can be lost after Binance accepts an order. Durable IDs make
restart recovery and audit possible without duplicate market orders.

**Consequence:** storage grows beyond round-1 fill rows and tests inject crashes
and ambiguous responses.

## ADR-3: Submission-failure counter, not a fill-equality gate

**Decision:** a task-snapshotted configurable threshold, default 3, pauses only
after confirmed consecutive pair submission failures. Two accepted orders reset
the counter. Fill/residual values are observational.

**Why:** the user explicitly selects no ongoing quantity/value equality check
and a one-second cadence.

**Consequence:** no code may silently treat residual, partial fill, or pending
query as a numeric risk limit or automatic repair trigger.

## ADR-4: Live adapter is narrow and default-off

**Decision:** real PAPI writes exist only in a dedicated backend adapter and live
executor, gated by executor configuration, durable Start, and fresh preflight.
Disabled and record transport remain non-network write paths.

**Why:** PAPI has no suitable testnet for this contract and market-order writes
are irreversible.

**Consequence:** fake/record transports prove CI behavior; first real task is a
separate human authorization. Manual close is future scope, not a precondition.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md
本地北京时间: 2026-07-23 19:44:12 CST
下一步模型: Claude Opus 4.8
下一步任务: create an implementation task breakdown that respects these ADRs
