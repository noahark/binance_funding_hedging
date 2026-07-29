# Live Record Evidence — What The Production Database Actually Holds

Read by the bookkeeper from `data/hedge-open-tasks.sqlite3` at
**2026-07-28 07:26 CST**, at stage intake, before any code was touched.

This is a **read-only capture of primary evidence**. Nothing was written to the
database. The rows below are the durable record of the two real hedge attempts of
2026-07-27 (the rejected COOKIEUSDT pair and the NOMUSDT pair that half-filled),
and they demonstrate T1, T2, T3 and T5 directly, without relying on any prior
report's narrative.

Reviewers: prefer this file over any summary. If a claim in `00-task.md`
disagrees with these rows, these rows win.

## `hedge_open_leg`

```text
id  attempt  leg   client_order_id                       endpoint               dispatch_state     order_id   status    cum_base  cum_quote  fee  err_code  err_category
3   2        spot  hgo-760686fa...c334f3d2-s (38 ch)     /papi/v1/margin/order  TERMINAL_RECORDED  (null)     REJECTED  0         0          -    -4015     (null)
4   2        perp  hgo-760686fa...c334f3d2-p (38 ch)     /papi/v1/um/order      TERMINAL_RECORDED  (null)     REJECTED  0         0          -    -4015     (null)
5   3        spot  hgd1a45d5b7df0423a8840d72556767f82s   /papi/v1/margin/order  TERMINAL_RECORDED  (null)     REJECTED  0         0          -    51169     (null)
6   3        perp  hgd1a45d5b7df0423a8840d72556767f82p   /papi/v1/um/order      TERMINAL_RECORDED  888412130  FILLED    10000     0          -    (null)    (null)
```

Legs 3–4 are the pre-fix 38-character `clientOrderId` rejections; legs 5–6 are
the post-fix run on the 35-character derivation. Both `client_order_id` forms are
reproduced above because the contrast is the previous stage's proof, and because
leg 6 is the first real fill this system has ever produced.

### What leg 6 proves — T1

`exchange_status = FILLED`, `cumulative_base_qty = 10000`, and
`cumulative_quote_amt = 0`.

Ten thousand NOMUSDT genuinely traded and the recorded notional is zero. Not
rounded, not stale — zero. Trace:

1. `backend/services/live_hedge_executor.py:242-246` — reads
   `cummulativeQuoteQty`, falls back to `cumQuote`. A UM order response has
   carried neither since 2026-07-14, so `_decimal_str(None)` returns its default
   `"0"`.
2. `live_hedge_executor.py:247-248` — `avgPrice` is likewise absent, so
   `avg_price` becomes `None`. (This half degrades honestly rather than
   fabricating a number.)
3. `backend/hedge_open_tasks/store.py:660-668` — `_leg_final_fields` treats
   `"0"` as *absent* and tries the `filled_qty * avg_price` fallback;
   `avg_price` is `None`, so control reaches the final `else` and stores
   `Decimal(0)`.

The position table's average price and unrealised PnL are derived from
`cumulative_quote_amt`.

### What leg 5 proves — T2 and T3

`error_code = 51169`, `error_category = (null)`.

A real, unambiguous rejection was classified as nothing. `51169` is positive;
`FATAL_EXCHANGE_CODES`, `AUTH_AMBIGUOUS_EXCHANGE_CODES` and
`INSUFFICIENT_FUNDS_CODES` (`backend/hedge_open_tasks/domain.py:306-353`) hold
only negative literals, so no margin-endpoint code can match any of them and the
value fell through to the unlisted-4xx default.

And the row has **nowhere to put what Binance said**. The table's columns are
listed above in full: there is no message column and no payload column.
`_business_msg()` (`live_hedge_executor.py:77`) extracts the message, uses it for
`-2010` disambiguation, and drops it.

## `hedge_open_attempt`

```text
id  task_id                               attempt_seq  q_common  pair_outcome      err_category  err_code
2   01e9a662-402e-46fd-aff6-ce7d02cb175c  1            2000      confirmed_failed  (null)        (null)
3   a1d0a9ac-288c-4508-bb36-2803b4408a5b  1            10000     single_leg        (null)        (null)
```

Attempt 3's `pair_outcome = single_leg` is correct and expected — advisory, per
the settled decision. Note that the attempt row's own `error_category` /
`error_code` are also NULL even though its spot leg carried `51169`; whether the
attempt row should carry up the leg's classification is a T2 design question.

## `hedge_open_task` — the NOMUSDT card

```text
id                  = a1d0a9ac-288c-4508-bb36-2803b4408a5b
coin                = NOMUSDT
status              = done
success_count       = 0
fail_count          = 1
q_common            = 10000
leg_exposure        = {"leg": "perp", "qty": "10000", "price": null,
                       "ts": "1970-01-01T00:00:00.000000Z"}
preflight_snapshot  = {"available": true, "spot_step": "1.00000000",
                       "perp_step": "1", "grid": "1.00000000",
                       "est_price": "0.00153000", "position_mode": "BOTH"}
last_worker_exit_reason = task_not_running
```

`status = done` with an outstanding naked short is **correct per the frozen
design** and was re-confirmed by the user on 2026-07-28.

### NEW FINDING — T5: the exposure record is timestamped 1970

`leg_exposure.ts = "1970-01-01T00:00:00.000000Z"`.

This was **not** in the stage proposal. The bookkeeper found it while grounding
this intake, and verified the cause in the code:

- `backend/hedge_open_tasks/service.py:1688` (inside `_dispatch_to_outcome`, the
  **live** dispatch path) calls `D.build_leg_exposure(spot_leg, perp_leg, 0)` —
  a hardcoded literal `0`.
- `build_leg_exposure` (`domain.py:882-910`) does `"ts": us_to_iso(ts_us)`, so
  `0` renders as the Unix epoch.
- `backend/hedge_open_tasks/executor.py:342`, the dry-run / record-transport
  path, passes the real `ctx.ts_us`.

Consequences:

1. The only durable record of a live single-leg exposure says it happened in
   1970. The user has such a position outstanding right now.
2. The offline suite cannot catch it, because the offline path is the one that
   passes a real timestamp. Same shape as the S1/S5 lesson from
   `2026-07-hedge-open-live-hardening-v1`: a live-only path with no offline
   counterpart.

`leg_exposure.price = null` on the same document is a *downstream* symptom of T1
(no `avgPrice`), not a separate defect; fixing T1's price source should fix it,
and the design should confirm that rather than patch the exposure document
separately.

## Runtime state observed in the same read

```text
hedge_open_settings: id=1  start_gate=1  version=4
                     executor_mode_snapshot=disabled  interval_seconds=1
backend service:     PID 96409, live mode, up 9h31m at capture time
hedge_open_task:     5 rows — 3 paused KORUUSDT cards (creation_seq 1..3,
                     never dispatched), 2 done (COOKIEUSDT, NOMUSDT)
```

The Start gate is **OPEN** and the service is **running**. The user was offered
closing both before this stage opened and chose to leave them as they are. No
agent working this stage may create a card, press Start, place an order, or write
to `hedge_open_settings`.

The three paused KORUUSDT cards are the perp-only symbol from the previous
stage's S4 investigation. They will not dispatch on their own, but they are one
operator click away from a real attempt while the gate is open.
