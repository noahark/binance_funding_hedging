# T4 Root Cause Found — NOM Hit Binance's Platform-Wide Maximum Collateral Limit

**Recorded**: 2026-07-28 14:43 CST, by the bookkeeper.
**Effect on the stage**: T4's paid discriminator order is **no longer required**.
See §Consequences.

## What the user observed

On 2026-07-28 the user attempted, **in the Binance app by hand**, both a transfer
into the cross-margin account and a NOM buy in the cross-margin account. Both
were refused with (verbatim, Chinese UI):

> 代币NOM已达平台抵押金额上限。最大入/买入数量为0。请调低数量或使用其他代币重试。

Translation: *Token NOM has reached the platform collateral amount cap. The
maximum transfer-in / buy quantity is 0. Please lower the quantity or try another
token.*

This is a first-party observation from the exchange's own UI, on the same account
and the same asset as the 2026-07-27 rejection. It is not inference.

## The official rule behind it

Binance FAQ **"Maximum Collateral Limit for Margin Assets"**
(`https://www.binance.com/en/support/faq/detail/dca77ef963294b368b5ebad0affeda09`,
read 2026-07-28). Verbatim quotes:

> "The Maximum Collateral Limit sets a maximum amount of collateral for each
> token in all Binance Margin Accounts."

> "It applies to the total amount of assets held by all Margin Accounts, not just
> one specific user account."

> "If the asset total cap reaches the upper limit, users will not be allowed to
> transfer in or buy any more of this asset as collateral to the Margin Account."

Key properties:

| Property | Value |
| --- | --- |
| Scope | **Platform-wide, per asset, across all users** — not per-account |
| Applies to | **ALL Margin Accounts: Cross Margin Classic, Isolated Margin, and Portfolio Margin** |
| At 90–100% of the cap | "Only transfer in or buy up to the upper limit with the max capped at 50,000 USD equivalent value" |
| Above 100% | "Transfer in blocked" — no exceptions |
| API / data page for current cap and usage | **None documented.** The FAQ names no endpoint and no public data page. |

The Portfolio Margin FAQ on transfer-in limits and supported collateral
(`937b8e81d03f475c8d7a0d42ec381510`, read 2026-07-28) points users back to the
"Margin Asset Max Collateral Rule" and to a **web** Trading Parameters page for
collateral ratios. It likewise names no programmatic endpoint for the cap or its
current utilisation.

## Why this explains `51169`

`51169 = MARGIN_TRADE_COEFF_INSUFFICIENT`. Binance support had already told us
COEFF is the collateral/haircut coefficient and that the check is on *discounted
effective margin*, not nominal balance — but would not confirm which field is
validated.

With the cap exhausted, the collateral capacity available for **additional** NOM
is zero. A margin BUY of NOM is therefore refused on a collateral-coefficient
check that no account balance can satisfy. `MARGIN_TRADE_COEFF_INSUFFICIENT` is a
literal description of that state.

### It also explains the asymmetry of the 2026-07-27 attempt

The attempt's perp leg **filled** and its spot leg was **rejected**
(`01-live-record-evidence.md`, legs 5 and 6). That now follows directly: a UM
perpetual SELL does not require bringing NOM into the margin wallet as
collateral, while a margin BUY does. Only the leg that needed collateral capacity
was blocked.

## What this falsifies and what it leaves open

- **Sufficient cause established**: NOM is above its platform-wide collateral
  cap, so the margin BUY leg could not succeed at any size.
- **The concurrency hypothesis is now unnecessary.** The prior leading theory —
  that the concurrent UM fill consumed the margin the spot leg needed — is not
  strictly disproven, but it is no longer needed to explain anything, and the cap
  explanation predicts the identical failure with zero concurrency. Binance
  support's "likely" was inference from the same conversation in which they
  answered "not documented" about the balance field.
- **Still unknown**: whether *any* API surface exposes the cap or its current
  utilisation. The two official pages read today name none. Absence in two FAQ
  pages is not proof of absence in the API; this needs a targeted read-only
  recon, recorded as such and not assumed either way.
- **The condition is time-varying.** The cap is consumed by *all* users' margin
  holdings, so an asset blocked today can become available later and vice versa.
  This is not a static property of a coin and must not be cached as one.

## Consequences for this stage

### T4 — the paid discriminator is cancelled

T4's required first step was one real margin BUY on NOMUSDT with no concurrent UM
order, with the interpretation pre-registered in `00-task.md`:

> **success ⇒** concurrency contention is real; **same `51169` ⇒** the cause is
> the collateral coefficient or wallet placement, not contention.

We now know, from the exchange's own UI and its own documentation, that the
maximum buy quantity for NOM is **0**. The experiment's outcome is therefore
known in advance — it would return `51169` and select the branch we have already
reached — so running it spends real money to learn nothing. **Cancelled**, and
this file is the reason. The bookkeeper does not need a new user authorization to
*not* place an order; if the user wants it run anyway, that remains their call.

T4's remaining work becomes read-only and is re-scoped in `00-task.md`:

1. A targeted recon for whether any API surface exposes the per-asset collateral
   cap or its utilisation, landing raw evidence under
   `reports/api-samples/2026-07-hedge-order-truth-v1/`. Public/documentation
   reads and signed **GET** reads only.
2. The preflight decision then follows the recon's answer:
   - **If an endpoint exists**, the preflight can gain a real gate and the design
     specifies it.
   - **If none exists**, the preflight *cannot* predict this class of rejection,
     and the correct handling is entirely T2's: classify `51169` precisely and
     surface it. A preflight that cannot see the constraint must not pretend to.

### T2 — `51169` now has a known required verdict

This upgrades T2 from "make the sign conventions match" to a concrete
requirement. `51169` is:

- **not** an insufficient-funds condition of *this account* — adding balance does
  nothing;
- **not** usefully retryable on a short timescale — the cap is consumed
  platform-wide and will not clear in the seconds a task retries;
- **not** a permanent property of the coin either — it can clear later, so the
  coin must not be permanently blacklisted;
- **coin- and direction-specific** — it blocks the forward direction's spot leg
  (buy into margin) for that asset, while the perp leg is unaffected.

The design must therefore decide what task-level outcome `51169` produces and
what the operator is told, in Chinese, and that message should say what is
actually true: *this coin's platform collateral cap is full; the spot leg cannot
be bought into the margin account right now; try another coin or try later.*
"Margin insufficient" would be actively misleading.

Note this interacts with the 90–100% band: in that band a **smaller** order can
succeed (capped at 50,000 USD equivalent). So the failure is not always
all-or-nothing, and a design that treats `51169` as "quantity is irrelevant" would
be wrong in that band. For NOM today the maximum is 0, i.e. above 100%.

### Product-level consequence, out of scope here

Any coin above its collateral cap is **structurally un-hedgeable in the forward
direction** for as long as the cap holds, because the forward direction requires
buying the coin into the margin wallet. There is no documented way to know this
before trying. Surfacing that on the opportunity table, or remembering it
per-coin with an expiry, is a product question beyond this stage's scope and is
recorded as a follow-up rather than designed here.

## Sources

- Binance FAQ — Maximum Collateral Limit for Margin Assets:
  https://www.binance.com/en/support/faq/detail/dca77ef963294b368b5ebad0affeda09
- Binance FAQ — Portfolio Margin Mode Transfer-in Limits, Position Limits,
  Leverage, Supported Collateral and Rates:
  https://www.binance.com/en/support/faq/binance-portfolio-margin-mode-transfer-in-limits-position-limits-leverage-supported-collateral-and-rates-937b8e81d03f475c8d7a0d42ec381510
- Binance app UI message, observed by the user 2026-07-28 (quoted verbatim above).
- `01-live-record-evidence.md` — the production rows for the 2026-07-27 attempt.
