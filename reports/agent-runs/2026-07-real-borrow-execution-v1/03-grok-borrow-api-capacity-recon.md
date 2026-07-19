# Grok Build — Read-Only Binance Borrow API Capacity Reconnaissance

Stage: `2026-07-real-borrow-execution-v1`  
Dispatch: `02-grok-borrow-api-capacity-recon.dispatch.md`  
Mode: repository samples + public documentation only. **No authenticated live calls. No writes. No credentials. No source edits.**

This report supports a **user frequency discussion** for a future Portfolio Margin borrow-task scheduler. It is **not** a product frequency decision, **not** production readiness, and **not** a review verdict.

---

## 1. Problem And Decision To Support

The direction synthesis (`06-direction-synthesis.md`) freezes A+B (durable task core + verified contract, **zero** Binance borrow POST) and defers C (live adapter) to a separate human-authorized stage. The user still wants a factual discussion of **high-frequency retry when `maxBorrowable` is zero**.

The decision this recon supports is only:

> Given documented PM rate limits, observed historical weight headers, and the current read-only refresh load, **what capacity envelope is defensible**, and **what remains unprovable** without a separately authorized one-attempt live probe?

It does **not** choose the production retry interval.

---

## 2. Evidence Inventory

Four evidence classes are kept separate.

### Class A — Documented endpoint limits / weights (official public docs)

| Claim | Source |
| --- | --- |
| PM IP weight limit **6000/min**; limits are **IP-based**, not API-key-based | [Portfolio Margin general-info](https://developers.binance.com/docs/derivatives/portfolio-margin/general-info) / [products general-info](https://developers.binance.com/en/docs/products/derivatives-trading-portfolio-margin/general-info) |
| Response headers expose **used** weight as `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)` | same |
| On limit violation, **429**; client must **back off** (not spam) | same |
| PM **order** limit **1200/min**, counted **per account** | same |
| `POST /papi/v1/marginLoan` — apply margin loan; **Request Weight(IP) 100**; params include **`asset`**, **`amount`** (single asset) | [Margin Account Borrow](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/Margin-Account-Borrow) |
| `GET /papi/v1/margin/marginLoan` — query loan records; **Request Weight 10**; `txId` matches `tranId` from POST marginLoan | [Query Margin Loan Record](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-Margin-Loan-Record) |
| PRD lists PM loan/history family for future execution discovery | `docs/product/PRD.md` (Portfolio Margin margin leg: maxBorrowable, marginLoan POST/GET, repayLoan, marginInterestHistory) |

### Class B — Observed historical response-header deltas (repo samples only)

| Capture | Path | Notes |
| --- | --- | --- |
| Private-account H_intake | `reports/api-samples/2026-07-private-account-v1/20260705T232800Z/evidence-index.md` | Sequential papi used-weight table after live GETs |
| Same structure (401 run) | `.../20260705T162920Z/evidence-index.md` | Same header deltas even when status=401 |
| Borrow-rate survey | `reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/sanitized/max_borrowable_*.json` | Nine `maxBorrowable` calls; used-weight sequence 195→235 step **+5** every time |
| Balance field shape | `.../20260705T232800Z/papi-v1-balance.json` | Fields present (amounts redacted): `crossMarginBorrowed`, `crossMarginInterest`, `updateTime`, etc. |
| Business zero-borrow | survey `max_borrowable_AIGENSYN.json` etc. | HTTP 400, code **51061**, pool-exhaustion message |

**Inference label:** deltas are **historical observations on specific capture IPs/minutes**, not perpetual official per-route weights, unless independently confirmed in Class A.

### Class C — Present repository refresh cadence and estimated papi load

| Fact | Evidence |
| --- | --- |
| Single HMAC GET-only client; audit records path/status/latency **only** — **no headers** | `backend/services/private_client.py` module docstring + `_signed_get` audit_log append |
| papi vs sapi vs api are distinct weight-pool comments | `private_client.py` WHITELIST / “api/papi are distinct X-MBX weight pools” |
| Group A private balances ~60s TTL | `backend/config.py` `private_channel_fast_ttl_seconds = 60` |
| Worker tick default 30s; history sweep batch 10 | `config.py` `background_tick_seconds=30`, `history_sweep_batch_size=10` |
| maxBorrowable / borrow-rate business TTL uses **funding history TTL default 1800s** | `snapshot_service.py` `_refresh_homepage_components` uses `funding_history_cache_ttl_seconds`; `config.py` default **1800** |
| borrow probe cap default **50** assets | `config.py` `borrow_check_max_calls=50` |
| Interest-history GETs whitelisted but **not** called by snapshot assembly | `private_client.py` comments E1/E1b |
| Balance assembly maps only `totalWalletBalance` → `total_balance` | `backend/domain/snapshot.py` `assemble_private_account` — **does not** surface `crossMarginBorrowed` |

### Class D — Unproven live behavior (explicitly **not** known from this recon)

- Whether `POST marginLoan` still costs IP weight **100** on the live cluster at the moment of a future probe (docs can change).
- Whether borrow POST counts against the **order** 1200/min limit.
- Acceptance latency until `tranId` is queryable / until `crossMarginBorrowed` moves.
- Idempotency / double-borrow under timeout.
- Exact **current** IP headroom on the operator’s machine.
- Whether 51061 / zero-pool recovers in seconds vs hours vs “tomorrow” (message text is not a timing SLA).

---

## 3. Endpoint And Limit Matrix

Portfolio Margin only. Classic `POST /sapi/v1/margin/borrow-repay` is **out of band** for this workstation’s PM posture (PRD + synthesis).

| Endpoint | Method | Security | Documented weight / limit scope | Required params (docs / code) | Identity / reconcile hook | Batch multi-asset? | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Margin Account Borrow | `POST` | `/papi/v1/marginLoan` | TRADE / signed | **Weight(IP)=100** (Class A docs) | `asset`, `amount` (+ recvWindow) | Response `tranId` (docs; also PRD) | **No** — single asset | [Margin Account Borrow](https://developers.binance.com/docs/derivatives/portfolio-margin/trade/Margin-Account-Borrow); `docs/product/PRD.md` |
| Query Margin Loan Record | `GET` | `/papi/v1/margin/marginLoan` | USER_DATA / signed | **Weight=10** (Class A docs; IP vs UID **not re-read as full HTML** — treat scope as documented page) | `asset`; optional `txId` = POST `tranId` | Match by `txId` / time window | No | [Query Margin Loan Record](https://developers.binance.com/docs/derivatives/portfolio-margin/account/Query-Margin-Loan-Record); PRD |
| Max Borrowable | `GET` | `/papi/v1/margin/maxBorrowable` | USER_DATA / signed | **Official per-call weight: UNVERIFIED** in this recon (docs page not fully archived). **Observed** consecutive +**5** used-weight on papi samples (Class B) | `asset` | Gate only; not loan identity | No — one asset | Code: `private_client.fetch_max_borrowable`; samples above |
| Account Balance | `GET` | `/papi/v1/balance` | USER_DATA / signed | Official weight **UNVERIFIED**. Observed first papi used-weight **20** in private-account capture (Class B inference if pool cold) | optional `asset` (skill tables / docs family) | `crossMarginBorrowed` / `updateTime` level signal | N/A | Sample `papi-v1-balance.json`; code `fetch_unified_balances` |
| UM position risk | `GET` | `/papi/v1/um/positionRisk` | USER_DATA | Official weight UNVERIFIED. Observed +**5** after balance in same capture | — | Exposure only; not loan proof | N/A | evidence-index |
| Margin interest history | `GET` | `/papi/v1/margin/marginInterestHistory` | USER_DATA | Official weight UNVERIFIED. Observed +**10** in capture; **not** used by assembly | optional asset/time | Interest ledger; not primary loan id | N/A | whitelist + evidence-index |
| Portfolio interest history | `GET` | `/papi/v1/portfolio/interest-history` | USER_DATA | Official weight UNVERIFIED. Observed +**50** in capture; **not** used by assembly | — | Negative-balance interest path | N/A | whitelist + evidence-index |
| Classic margin borrow/repay | `POST` | `/sapi/v1/margin/borrow-repay` | MARGIN / signed | Documented **1500(UID)** on classic margin docs family — **wrong account model for PM primary path** | asset/amount/type | Different product | No | Classic margin docs; synthesis: PM only |

**Shared limit envelope (Class A):**

```text
PM IP weight budget ≈ 6000 / minute / IP
PM order budget    ≈ 1200 / minute / account  (whether marginLoan counts: UNVERIFIED)
```

**Theoretical exclusive-write ceiling (INFERENCE only):**  
If marginLoan weight remains 100 and no other papi traffic:  
`floor(6000/100) = 60 POST/min ≈ 1 POST/s average`.  
This is a **quota ceiling**, not a safety recommendation.

---

## 4. Current Papi Load Envelope

### 4.1 Why there is no live historical used-weight curve

1. Runtime audit explicitly **does not store response headers**  
   (`private_client.py`: audit fields = logical_endpoint, method, http_status, error, latency_ms).  
2. No app path was found that persists `X-MBX-USED-WEIGHT-1M` to disk for the running workstation.  
3. Available numbers are **one-shot discovery captures** under `reports/api-samples/`, not continuous telemetry.

Therefore any “current headroom” number for the operator’s IP **cannot** be stated as measured fact.

### 4.2 Observed per-call papi used-weight deltas (Class B)

From `20260705T232800Z/evidence-index.md` sequential papi rows (same IP minute counter):

| Step | Path | USED-WEIGHT-1M | Δ (inference) |
| --- | --- | --- | --- |
| 1 | `/papi/v1/balance` | 20 | **~20** if cold |
| 2 | `/papi/v1/um/positionRisk` | 25 | **5** |
| 3 | `/papi/v1/margin/maxBorrowable` | 30 | **5** |
| 4 | `/papi/v1/margin/maxBorrowable` | 35 | **5** |
| 5 | `/papi/v1/margin/marginInterestHistory` | 45 | **10** |
| 6 | `/papi/v1/portfolio/interest-history` | 95 | **50** |

Survey nine `maxBorrowable` files: used weights **195,200,…,235** with every adjacent Δ = **5** (both 200 and 400 bodies).

**Inference:** treat **maxBorrowable ≈ 5 IP weight** as a well-repeated historical observation; treat balance ≈20 and um ≈5 as **weaker** (single capture series).

### 4.3 Steady-state load (code + inference)

Assumptions (explicit):

- Private channel enabled; worker running.  
- Group A private panels refresh when due at ~**60s** (`private_channel_fast_ttl_seconds`).  
- maxBorrowable business TTL ≈ **1800s** (`funding_history_cache_ttl_seconds`).  
- Up to **50** borrowability probe assets (`borrow_check_max_calls`), but only **due** assets in each homepage sweep batch (batch size 10 / tick 30s).  
- E1/E1b interest histories **not** polled by assembly.  
- Public fapi/spot market traffic is **out of papi pool** (separate hosts).

**Steady-state papi weight / minute (INFERENCE range):**

| Component | Calls (order of magnitude) | Weight estimate |
| --- | --- | --- |
| balance + um_positions | ~1 each / 60s | ~25 / min (if Δ20+5 holds) |
| maxBorrowable amortized | 50 assets / 1800s ≈ 1.67/min | ~8 / min at Δ5 |
| cold spikes / click force-refresh | occasional | +tens |
| **Total typical** | | **~30–80 / min** |
| **Stressed cold / many force** | | **~100–300 / min** (still ≪ 6000) |

Relative to 6000: **read path typically consumes well under ~5% of PM IP weight**.

### 4.4 Residual headroom for future borrow POSTs (INFERENCE)

```text
remaining_weight ≈ 6000 − used_papi
borrow_posts_ceiling ≈ remaining_weight / 100   # if weight stays 100
```

| Assumed used_papi | Residual weight | Theoretical POST marginLoan / min |
| --- | --- | --- |
| 50 | 5950 | ~59 |
| 200 | 5800 | ~58 |
| 500 | 5500 | ~55 |
| 1000 | 5000 | ~50 |

**Conclusion for frequency discussion:** under current **read-only** product load, **IP weight is unlikely to be the binding constraint** for moderate retry (seconds–tens of seconds). Binding constraints are more likely: **pool empty (51061)**, **unknown-outcome safety**, **reconciliation latency**, **account/business rejects**, and (if applicable) **order-rate** rules — the last still UNVERIFIED for marginLoan.

---

## 5. Balance-Field Reconciliation Assessment

### 5.1 Raw fields available in captured `/papi/v1/balance`

From `papi-v1-balance.json` (redacted amounts; structure retained):

| Field | Potential signal |
| --- | --- |
| `crossMarginBorrowed` | Level of cross-margin debt for that asset |
| `crossMarginInterest` | Accrued interest component |
| `updateTime` | Exchange-side update timestamp (ms) |
| `totalWalletBalance` / free/locked variants | Net wallet view; not loan identity |
| `negativeBalance` | Negative balance path; not loan id |

**Present product mapping gap:** snapshot `private_account.balances_unified` only keeps `asset`, `total_balance` (`totalWalletBalance`), `value_usdt` — **not** `crossMarginBorrowed` (`backend/domain/snapshot.py`). So even if balance is fetched every ~60s, **the UI/contract today does not expose the borrow level.**

### 5.2 What a balance delta could prove

**Could support (weak, non-unique):**

- After a **known successful** loan, `crossMarginBorrowed` for asset A may increase by approximately the borrowed amount (plus interest dynamics over time).  
- A zero→positive jump may corroborate “debt increased.”

**Cannot uniquely prove (hard limits):**

- Manual UI borrow, another API client, another task, or partial repay can move the same field.  
- Interest accrual moves `crossMarginInterest` / effective debt without a new loan.  
- Auto-exchange / portfolio mechanics may alter balances without a matching `marginLoan` attempt.  
- Sample existence of `crossMarginBorrowed` is **not** evidence of post-`marginLoan` propagation timing (dispatch hard rule).

Therefore: **balance is at best a corroborating signal**, never sole success proof under multi-source debt changes.

### 5.3 Freshness mismatch vs high-frequency tasks

| Signal | Current cadence | Implication |
| --- | --- | --- |
| Balance fetch | ~**60s** Group A | A 1s–10s borrow loop can complete **many** attempts between two balance samples |
| maxBorrowable | ~**1800s** business TTL (plus sweep) | “Still 0” on the UI can be **stale** relative to a fast task |
| Loan history GET | Not scheduled today | Would need explicit task-driven poll after attempt |

If confirmation waited only on the next 60s balance refresh, success accounting would lag and could mis-order concurrent activity.

### 5.4 When loan-history is mandatory

| Path | Balance-only OK? | Loan history / response id |
| --- | --- | --- |
| Happy path with `tranId` returned and durable persist | Still insufficient alone if other writers exist | **Mandatory** for unique attribution (`txId` / record match) |
| Timeout / connection loss after dispatch | **No** — balance may rise from *someone’s* loan | **Mandatory** before any retry |
| Known business reject (e.g. 51061 / insufficient) | Balance may be unchanged | History optional; treat as known fail |
| Cap / validation local reject (no network) | N/A | No exchange recon needed |

**Synthesis alignment:** success only after **reconciled loan evidence** (`06-direction-synthesis.md`); this recon agrees.

---

## 6. Frequency Envelope: Quota vs Safety

**Do not treat the right-hand column as a production recommendation.**  
Quota column uses **documented** 6000 IP + weight 100 for POST only, and **ignores** read companions and order-limit uncertainty.

| Interval | Attempts / min (one task) | Documented IP-quota feasibility (INFERENCE: POST only @100) | Safe product behavior (evidence-limited) |
| --- | --- | --- | --- |
| **1s** | 60 | At exclusive ceiling (~60/min). **Feasible only if** almost no other papi traffic and docs weight still 100. **No** safety evidence for recon latency. | **Not product-safe** with current evidence: no measured confirmation lag; unknown outcomes risk double borrow; 429 obligation; 51061 not fixed by speed. |
| **2s** | 30 | Well under exclusive ceiling; residual headroom for reads. | Still **unsafe as default**: faster than any proven recon path; balance cadence 60s cannot confirm. |
| **5s** | 12 | Comfortable vs 6000 if reads stay low. | Quota-OK ≠ safe. Requires known-fail classification + no auto-retry on unknown. |
| **10s** | 6 | Comfortable. | Possible **discussion band** for *known retryable* rejects only, after C verifies codes/latency — still not chosen here. |
| **30s** | 2 | Matches fake-UI copy cadence; negligible weight. | Aligns with prior fake semantics; still needs server authority + recon rules. |
| **60s** | 1 | Trivial vs quota; closer to balance refresh. | Conservative for human-supervised learning; not proven optimal. |

**Separate gate vs write:**

- Polling `maxBorrowable` every 1s at observed ~5 weight → ~300 weight/min → still under 6000, but **does not create loans** and still does not prove pool recovery timing.  
- Coupling “poll every 1s + POST every 1s when amount>0” multiplies risk and weight; POST remains the dangerous half.

**51061 / zero-pool (Class B message):**  
Survey bodies include *“insufficient loanable assets… try again tomorrow.”* That text is **not** a contractual retry schedule, but it is evidence that **sub-second hammering is not implied by the exchange**.

---

## 7. Unknowns That Cannot Be Solved Read-Only

1. Live **acceptance and visibility latency** after a successful `marginLoan` (until `tranId` queryable / borrowed level moves).  
2. Whether **order** rate limit applies to `marginLoan`.  
3. Full official **weight table** for all companion GETs (beyond partial docs snippets).  
4. Exact **current** `X-MBX-USED-WEIGHT-1M` on the operator IP.  
5. Idempotency under client timeout (does a second POST create a second loan?).  
6. Complete **retryable vs terminal** business-code set for PM borrow.  
7. Interaction of multi-task concurrency with account-level risk checks.  
8. Whether testnet/sandbox exists with faithful PM borrow semantics for safe soak tests.

---

## 8. Recommended Inputs For The User Frequency Discussion

Use these as discussion inputs — **not** frozen defaults:

1. **Treat IP quota as soft upper bound (~≤60 POST/min exclusive), not a target.**  
   Current read load leaves **most** of 6000 free (inference §4).

2. **Separate two clocks:**  
   - **Probe clock** for `maxBorrowable` / known-zero rechecks.  
   - **Write clock** only when gate says amount > min and task is armed.  
   Zero-pool should **lengthen** the probe clock; it should not equal “POST as fast as quota allows.”

3. **Never auto-retry faster than you can reconcile.**  
   Without measured recon latency, any interval **faster than loan-history round-trip + safety margin** is speculative.

4. **Prefer bands for human choice:**  
   - Learning / supervised C: **≥30–60s** write attempts.  
   - Later production discussion: only after C measures latency and error taxonomy; **10s** may enter the conversation for *known* retryable rejects only.  
   - **1–2s write loops:** discuss only as “quota-possible, product-unproven, high double-borrow risk.”

5. **Expose used-weight scalars before C** (design item, not done): log `used_weight_1m` + path only, so headroom becomes observable without secrets.

6. **Surface `crossMarginBorrowed` (or dedicated recon reads) only as corroboration**, with **loan-history/`tranId` as authority**.

7. **One-attempt observational protocol (minimum before claiming “real write limit”)** — for a **later, separately authorized** session only:

   | Step | Action | Forbidden |
   | --- | --- | --- |
   | 0 | Written human approval for one asset, min amount, max one POST | Bursts, loops, load tests |
   | 1 | Record pre-state: maxBorrowable, balance fields, used-weight header | Printing secrets |
   | 2 | Single `POST marginLoan` with pre-persisted local attempt id | Second POST |
   | 3 | Capture status, body ids (`tranId`), latency, used-weight | Interpreting timeout as “safe to retry” |
   | 4 | One or few **GET** loan-history by `txId` / asset window | Hammering |
   | 5 | Optional single balance GET for corroboration | Claiming unique attribution from balance alone |
   | 6 | Stop; write redacted evidence under `reports/api-samples/<stage>/` | 429 hunting, multi-asset storms |

   That protocol measures **one path’s latency and headers**. It does **not** measure the 60/min ceiling (and must not try to).

---

## 9. Non-goals And Safety Compliance

This recon did **not**:

- Send any POST/PUT/DELETE or `marginLoan` / repay / transfer / order / listenKey.  
- Perform any authenticated live GET.  
- Load or display credentials, `.env`, signatures, or full private payloads.  
- Benchmark, burst, or seek 429/418.  
- Modify product source, config, commit, or push.  
- Choose a production retry frequency.  
- Claim production readiness or emit review-verdict JSON.

Deliverable path only: this Markdown under the stage report directory.

---

## Summary Table For Operators

| Question | Answer class | Result |
| --- | --- | --- |
| Can we batch multi-asset borrow? | Class A | **No** — single `asset`+`amount` on `POST /papi/v1/marginLoan` |
| Documented POST weight | Class A | **100 IP** |
| PM IP budget | Class A | **6000/min** |
| Observed maxBorrowable cost | Class B | **~5 used-weight per call** (repeated) |
| App logs used-weight over time? | Class C | **No** |
| Steady papi read load | Class C inference | **~30–80 / min typical**, ≪ 6000 |
| Residual borrow POST capacity | Inference | **~50–59 / min** if weight 100 and reads stay low |
| Balance as sole success? | Class B+C analysis | **No** — history/`tranId` required |
| 1s retry product-safe? | Class D | **Not evidenced** — quota-only possible |

---

当前 Session ID: 019f778f-4efe-7ce0-ab37-483ed47b51c2  
Session ID 来源: active_session_registry  
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md  
本地北京时间: 2026-07-19 12:33:11 CST  
下一步模型: Codex / human operator  
下一步任务: 将本 recon 并入频率/对账讨论；修订或确认 `06-direction-synthesis.md` 后提交用户审批（A+B）；在用户批准与单独授权前禁止任何 live write
