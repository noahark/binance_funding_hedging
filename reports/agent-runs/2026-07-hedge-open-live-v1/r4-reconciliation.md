# R4 Diff Reconciliation — Hedge Open Live v1 (Round 1)

Bookkeeper R4 check after the two parallel tasks (hedge-be Claude-GLM, hedge-fe
Kimi) stopped, before evidence commits + review-1.

## Boundaries — CLEAN
- hedge-be changed: `backend/app/server.py` (+203, hedge routes only, borrow
  untouched), `backend/hedge_open_tasks/**` (new module), `backend/tests/
  test_hedge_*.py` (5 new). All within the hedge-be allowed set.
- hedge-fe changed: `frontend/index.html`, `frontend/self-check.js`. Within the
  hedge-fe allowed set.
- Scopes disjoint; no cross-boundary edits; the unrelated untracked
  `scripts/check_symbol_mismatch.py` (pre-existing, not this stage's) was
  touched by neither.

## Independent re-run (not trusting model claims) — GREEN
- `python -m pytest backend/tests -q` → **785 passed** (matches hedge-be report).
- `node frontend/self-check.js` → exit 0, **108 PASS** (matches hedge-fe report).

## Interface reconciliation — 1 FINDING

### R4-001 (blocking): `single_amount` type mismatch across the frozen seam
- **FE** (`frontend/index.html:3484`) posts
  `single_amount: Number(amountStr)` → a JSON **number**.
- **BE** (`backend/hedge_open_tasks/domain.py:615-617`) `validate_single_amount`
  requires a **decimal string** `^[0-9]+(\.[0-9]+)?$`; a number is rejected with
  `invalid_field("single_amount", …)`.
- Consequence: against the real backend, FE task creation would fail every time
  (`400 invalid_field`). Both sides' tests passed only because each used its own
  mock (FE's same-origin mock does not type-check the body; BE's tests send a
  string), so the integration mismatch was masked — exactly the drift R4 exists
  to catch.
- **Adjudication:** BE is correct. Money amounts must cross as decimal strings to
  avoid float binary-precision error; the BE choice is the right engineering.
  **FE must align:** post the raw user-entered string, not `Number(...)`.
- **Root cause:** the breakdown §3.1 frozen contract did not pin the type of
  `single_amount`. Fixed by amending §3.1 (see below) to `single_amount` =
  decimal string.

### `target_n` — consistent (no action)
FE posts an integer number; BE `validate_target_n` requires `int`; a JSON integer
decodes to a Python `int`. Aligned.

## Resolution
1. Amend `12-development-breakdown.md` §3.1: `single_amount` is a **decimal
   string** (regex `^[0-9]+(\.[0-9]+)?$`); `target_n` an integer.
2. Dispatch a bounded hedge-fe R4-fix (Kimi): post `single_amount` as the raw
   string; add a self-check assertion that the POST body's `single_amount` is a
   string. BE is unchanged.
3. After the FE fix, re-run both self-tests, then create the evidence commit +
   fingerprint and dispatch review-1 (hedge-be→Kimi, hedge-fe→Claude-GLM).

## Status
R4-001 was routed to hedge-fe R4-fix-1 (checkpoint commit 1749d94 protected the
BE module).

## R4 re-check after hedge-fe R4-fix-1 (2026-07-23) — PASS
- FE now posts `single_amount` as the raw normalized decimal string
  (`frontend/index.html:3495` `single_amount: amountStr`; `normalizeHedgeAmount`
  at 3459 enforces `^[0-9]+(\.[0-9]+)?$`, `.5`→`0.5`, no float round-trip),
  matching BE `validate_single_amount`. `target_n` stays an integer (aligned).
- Boundaries still clean (only `frontend/index.html`, `frontend/self-check.js`).
- Independent re-run: `node frontend/self-check.js` exit 0, 108 PASS, 0 FAIL
  (incl. the new single_amount-is-string assertion). BE unchanged (pytest 785
  still green from the prior re-run).
- **R4 PASSED.** Proceeding to evidence commit + fingerprint + review-1.
