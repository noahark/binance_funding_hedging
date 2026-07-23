# API Recon Intake — Hedge Open Real API v1

## Raw Evidence Received

- Raw report: `reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`
- Research role: independent API recon, human-operator executed.
- Reported model/session: Claude Opus 4.6 Thinking /
  `3a6a68e2-87ec-4fd8-907f-7e91f7df7bfe`.
- Scope: documentation and public read-only samples only; no credential access,
  private stream, or order submission.

## Accepted Design Inputs

1. PAPI margin MARKET accepts one of base `quantity` or quote
   `quoteOrderQty`. The user selects base `quantity` for this stage; the quote
   capability is not used in the execution contract.
2. PAPI UM MARKET uses base `quantity`; it has no quote-order-quantity model.
3. Both directions use a fixed shared base `q_common`; filter parsing must
   honour zero-disabled MARKET_LOT_SIZE fields and per-constraint LOT_SIZE
   fallback.
4. All request quantities, quote amounts, estimated prices, and response values
   use Decimal fixed-point and per-leg formatting; precision display fields do
   not replace filters.
5. No PAPI testnet exists. CI uses fakes/record transports; a real-order sample
   remains a separately human-authorized evidence event.

## Bookkeeper Caveat

The raw report's serial proposal applied only to a quote-buy model that derives
UM quantity from exact spot `executedQty`. The user supersedes that model with
concurrent fixed base quantities on both legs. The implementation still pauses
on single-leg, partial, timeout, or unknown outcomes and never auto-repairs.

## Scope Assumption

The stage targets regular Portfolio Margin, the repository's documented account
mode. PM-Pro compatibility is not claimed or implemented unless the user changes
that assumption.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/02-api-recon-intake.md
本地北京时间: 2026-07-23 14:29:44 CST
下一步模型: human operator
下一步任务: execute the mandatory direction-panel packet for each registered panel member
