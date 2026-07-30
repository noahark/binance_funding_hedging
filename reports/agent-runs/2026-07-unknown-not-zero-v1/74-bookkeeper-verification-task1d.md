# Bookkeeper Verification — task1d-state-write-visibility

Verified 2026-07-30 by Opus 5 (Bookkeeper). Range `93728ce..9939b0c`; implementation
`7bd2bce`, ledger `9939b0c`.

**Verdict: VERIFIED.** All five sites converted, one residual to disclose, and one
correction to the implementer's own wording.

## 1. Checks

| Check | Result | How |
|---|---|---|
| File boundary | PASS | `service.py`, `test_hedge_task_local.py`, result file, `status.json` (one field). Nothing forbidden |
| Full suite | PASS | **1097 passed**, measured independently (1092 + 5). No flake this run |
| S1-S5 all converted | PASS | Each site now calls `_record_state_write_failure(task_id, attempt_id, operation, exc, now_us)` |
| New event kind, not a rename | PASS | `state_write_failed` appears in `service.py` only (`:1325` docstring, `:1342` the call). `settlement_failed` untouched |
| `_ENTRY_EVENT_KINDS` unchanged | PASS | `service.py:61-67` still the same five kinds. No new pause reason, status, operator copy, or UI field |
| F2's helper untouched | PASS | `_record_settlement_failure` extracted at both commits and compared: **byte-identical, 1,861 bytes**. Both `_record_settlement_failure(...)` call sites identical |
| S1 preserves the raw response | PASS | The `continue` no longer skips `_persist_leg_raw`; the test asserts the raw row still lands |
| Per-site mutation | PASS | Independently spot-checked: reverting S5 (`mark_leg_querying`) to a bare `pass` fails **exactly** `test_s5_mark_leg_querying_failure_is_recorded` and nothing else — 36 others still pass. Matches the implementer's claim that each site is individually load-bearing. Tree restored, `git status` clean |

## 2. S2's ordering guarantee — better than R3 required

R3 asked that a failed rate-limit stamp must not let the pair settle as an ordinary
failure. The implementation (`service.py:418-425`, `:1360-1387`):

- an in-process `_rate_limit_stamp_pending: set[int]` records attempts whose
  dispatch-time stamp failed;
- `_rate_limited_for_settlement(...)` retries the stamp at settlement time and, on a
  repeated failure, records it through `_record_state_write_failure` rather than
  swallowing it;
- **and returns `True` either way** — so a still-pending attempt settles without the
  counter whether or not the retry succeeds. The guarantee therefore does not depend
  on the retry working, which is stronger than a naive reading of R3.

**Coverage is complete**: both settlement call sites (`:1224-1232` drain,
`:1263-1271` crash-gap) route through the gate, and those are the only
`finalize_attempt` / `settle_attempt_no_counters` callers in the file. A gate that
covered one path would have leaked the guarantee; this one does not.

No new column or status, as the packet required.

## 3. Residual, disclosed — the pending set does not survive a restart

The set is in-process. The implementer states this in the code
(`service.py:423-424`: "a process restart loses it, same crash window the system
already has").

Consequence, stated concretely: if the process restarts between a failed stamp and
settlement, the attempt has neither the durable `rate_limited` column nor the
in-memory marker, so it settles as an ordinary failure and consumes one
consecutive-failure count. With the default threshold of 3, the visible effect is a
task pausing one failure earlier than it should. Fail-closed — it pauses, it never
orders or moves money.

The comparison to the existing crash window is fair: the crash-gap recovery loop
exists precisely because a crash between leg terminalisation and settlement already
has consequences. This adds one of the same class rather than a new class. Accepted
as a residual and carried to `PROJECT_STATE.md` at stage close; a durable fix means a
new column, which the packet explicitly routed to a blocker rather than an
implementer's choice.

## 4. Correction to the implementer's wording — for the reviewers

The result says "F2 的 settlement_failed 及两调用点字节不变". Precisely:

- the **recording** calls `_record_settlement_failure(...)` inside both `except`
  blocks are byte-identical — verified;
- but the **settlement condition immediately above them changed** at both sites, from
  `attempt.get("rate_limited")` to `self._rate_limited_for_settlement(...)`.

That change is required by R3 and is not a violation. But a reviewer told "F2 is
byte-identical" could reasonably conclude those lines were untouched. They were not:
F2's two blocks now begin with a different condition, on the reviewed settlement
path. Both review packets state this explicitly.

## 5. Route

`AGENTS.md:181`: the repair touches `service.py`, forbidden in the reviewed range, so
**review-1** (Grok 4.5, `xai`, cross-provider) then **review-2** (Codex, disclosure
per D-6).

```text
base_sha     ac8d493a903051394fc9fda3ca467590a6e2f837
delivery_sha 7bd2bcef7882a642f8bee64192770da924b7e5c6
```

`rework_count` stays **2 of 3** — this is the repair of round 2's findings. If a
reviewer returns `REWORK` again the cap is reached and `AGENTS.md:182` routes the next
decision to Human: narrow, redesign, accept a limitation, or stop.
