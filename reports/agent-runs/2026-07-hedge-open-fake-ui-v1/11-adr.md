# ADR — Hedge Open Fake UI v1

## ADR-1: Pure front-end mock, no backend surface

**Decision.** This stage adds no backend endpoint, no SQLite, no websocket, no
order path. All task and position state lives in the browser (in-memory +
localStorage). Book prices are synthetic with periodic drift.

**Why.** The user chose to shape the OPEN interaction, task page, and position
display first, then build the real backend (stage 2). A pure client mock lets
UI/UX iterate at zero funds risk and zero backend coupling.

**Consequence.** The mock's data contracts (task shape, position aggregation,
open-rate/basis formula) are authored here so stage 2 can reuse the same field
names and math when it replaces the mock source with real executor + websocket.

## ADR-2: Direction and basis convention (locked)

**Decision.** Direction follows funding sign; basis is computed from the legs
that actually fill:

- Forward (positive funding): sell perp @ perp **bid1**, buy spot @ spot
  **ask1** → `forward_basis = (perp_bid1 − spot_ask1) / ref`.
- Reverse (negative funding): sell spot @ spot **bid1**, buy perp @ perp
  **ask1** → `reverse_basis = (spot_bid1 − perp_ask1) / ref`.
- `ref` = mid of the two relevant prices; a fill opens when the applicable
  basis >= 0.05%.

**Why.** The selling leg fills at the counterparty best bid and the buying leg
at the counterparty best ask; that spread is the gross edge locked at open.
User corrected and confirmed this convention on 2026-07-22.

**Consequence.** The market table `正向开单率` / `反向开单率` columns keep their
existing 60s-snapshot estimate semantics (name only gains `率`). The task card
shows the same rate combo computed from the mock live book — the two口径 can
differ (snapshot vs mock-live) and that is acceptable in the fake stage.

## ADR-3: Both direction columns always clickable, recommended one highlighted

**Decision.** Both `正向开单` and `反向开单` operation columns are always
clickable per row; the row's funding sign only highlights the recommended
direction's buttons (positive → forward, negative → reverse).

**Why.** User decision: allow manual override of direction while still guiding
the sensible choice. A hard lockout was explicitly rejected.

**Consequence.** Reverse-direction fake balance check still runs even on a
positive-funding row if the user forces it; the insufficient-balance modal is
direction-specific.

## ADR-4: Leg risk and failure handling in the mock

**Decision.** A simulated single-leg fill (one leg fills, the other fails)
records the exposure on the task, raises an alert state (敞口告警), and pauses
the task — no auto-hedge, no rollback. A cumulative > 3 fill failures in a plan
terminates the plan and pauses the task, with no re-send.

**Why.** Mirrors the locked live-stage risk policy so the UI states that stage 2
must drive already exist and are exercised in the mock.

**Consequence.** The task card must render 敞口告警 and terminated/paused states;
the self-check exercises the >3-fail termination path.
