# Balance Response Shape — answered from the repository, no live read needed

Recorded 2026-07-30 by Opus 5 (Bookkeeper) after Human pointed out that the
existing reconnaissance and the account-balance panel already carry this data.

**Correction.** `41-review-2-codex-result.md` and `42-scope-decision-request.md`
both state that F1's sub-case question "cannot be determined from the repository"
and needs an authorized live read. **That was wrong.** Human was right; the
evidence is in the repository. My request for a live `get_balance` observation is
**withdrawn** — it was unnecessary and I should have looked before asking for a
signed live call.

F1 itself is out of scope by Human decision D-8. This file exists so that whoever
picks it up later does not redo the analysis.

## 1. It is the same endpoint the account panel already uses

The hedge preflight reads balances through `GET /papi/v1/balance`
(`hedge_open_live_client.py` allowlist, `test_hedge_purity.py:49`). That is
**exactly** endpoint E3 of the private-account panel
(`private_client.py:543-558`, `docs/private-account-v1-direction-draft.md:85`),
whose recon records it as carrying the unified account's full asset set — U-margin,
coin-margin and cross-margin sub-accounts combined.

## 2. Omission of zero balances is opt-in, and we do not opt in

The strongest evidence is in our own call sites:

- The **spot** endpoint E6 is called with an explicit
  `{"omitZeroBalances": "true"}` parameter (`private_client.py:575-586`). A
  parameter that must be passed to drop zero rows is evidence that the default
  behaviour **keeps** them.
- The **PAPI balance** call passes no such parameter (`private_client.py:555`), and
  neither does the hedge preflight's.

So the "row absent because the balance is genuinely zero" sub-case I raised as
blocking is unlikely on this endpoint as we call it. The remaining real trigger for
F1 is the one that was always the substantive half: a row present whose
`crossMarginFree` is missing or unparseable, or a truncated/partial list.

This is evidence, not proof — nobody has observed the response for an asset the
account has never held. But it is strong enough that no live call is warranted to
proceed, and a live call would not have been decisive either without such an asset
to hand.

## 3. The correct pattern already exists in this codebase

More useful than the shape question: **the account-balance panel already solved
F1's problem, properly, in a sibling module.** `backend/domain/snapshot.py:924-926`:

> each balance row carries `value_usdt` … Missing/bad amount or price -> **null
> with warning**; valid zero -> `"0.00000000"`. The frontend must not [conflate
> them]

It distinguishes "unknown" from "real zero", emits `null` rather than a fabricated
figure, and routes the reason into a `warnings` channel that reaches the UI
(`snapshot.py:955-971`). The related recon note even forbids the failure mode by
name: 「禁止静默截断装 verified」.

So when F1 is eventually addressed, it is **not** a design question. The in-house
precedent is: preserve `None`, attach a warning, never a silent zero — the same
rule this stage applied to order records. The hedge preflight simply never adopted
its sibling's pattern.

That is also the more interesting fact about F1: the codebase already knew the
right answer in one subsystem while the other one fabricated a zero and killed
tasks with it.

## 4. Standing note for whenever F1 is picked up

- Endpoint and shape: §1, §2 above. No new recon needed.
- Pattern to copy: `snapshot.py` — `None` + warning, real zero preserved.
- The trap to avoid, which is why this was worth writing down: mapping *every*
  missing asset to `preflight_incomplete` would trade a permanent stop for a
  permanent stall. Distinguish "field unreadable" from "asset legitimately absent".
- The operator-facing copy for "balance unreadable" is product meaning and needs
  Human approval, not an implementer's choice.
