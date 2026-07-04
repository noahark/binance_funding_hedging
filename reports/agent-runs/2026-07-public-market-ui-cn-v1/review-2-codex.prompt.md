# Review-2 (stage-level, FINAL GATE) — public-market-ui-cn-v1

You are Codex/GPT (`gpt5.5`, xhigh), acting as `reviewer_2` — the **final
review gate** — in **read-only** sandbox mode. Do not modify any file.

Stage: `2026-07-public-market-ui-cn-v1` (Binance public-market snapshot
workstation, public data only). This stage is a **contract-warning wording
amendment + frontend display/i18n polish** built on the two user-accepted prior
stages (`2026-07-public-market-impl-v1` head `ce00489` and
`2026-07-public-market-bstock-alias-v1` head `548ae0d`, both accepted at
`6d8c0c4`). It is **LOW complexity**: no logic change, no schema change, no
structural change to the API payload — the ONLY API-payload change allowed is
the `warnings[1]` text.

You review the **whole stage** (Task A wording + Task B frontend + Task C
integration), not a single task. Review-1 (two task-level verdicts, both ACCEPT)
already ran; you may read those verdicts but you are NOT bound by them —
re-verify the material claims yourself.

## Disclosure: prior direction-synthesis involvement (strong-reviewer override)

You (Codex/GPT) are the **prior direction synthesizer** for the covering
contract stage (`2026-07-public-market-contract-v2`), whose user-approved
direction synthesis covers Phase 1 public market (`direction_synthesis.status =
approved_prior_stage`; no new direction panel ran this stage — the user decided
the 5-point wording in-session on 2026-07-04). You therefore have **prior
direction-synthesis involvement**, not `none`.

You have **NO** stage-design, development-breakdown, implementation, or
fix-authorship involvement this stage:
- Designer + breakdown author = Anthropic/Fable5 (00-intake/00-task/10-design + the pre-written Task B dispatch prompt).
- Task A implementer = `claude_glm` (glm-5.2[1m]) — `CONTRACT_WARNINGS[1]` + contract doc + tests.
- Task B implementer = `kimi` (kimi-2.7) — frontend.
- Task C integration = the stage controller (`claude_glm`), no product code.

You wrote no delivery code this stage, so the review-2 implementer/fix-author
hard ban is satisfied. Per AGENTS.md, because no provider-unrelated decision
model exists (decision pool = {GPT/Codex, Anthropic}; Codex=prior direction,
Fable5=design+breakdown → excluded; both implementers hard-banned), you review
via the **strong-reviewer disclosure override** — the AGENTS.md-preferred
"GPT/Codex first" path, identical to impl-v1 / bstock-alias-v1.

**You MUST set `reviewer_prior_involvement: "direction_synthesis"`** and
disclose the above in `reviewer_prior_involvement_notes`.

Per AGENTS.md, treat the **user-approved direction synthesis, the PRD, and the
frozen contract** (`docs/api/public-market-contract.md`,
`schemas/api/public-market/snapshot.schema.json`) as the **top-level
requirements**. Fable5 design/breakdown artifacts are **reviewed evidence, not
the highest authority** — if design and contract disagree, the contract wins.

## Review subject (recompute this yourself — do not trust this summary)

Stage-level commit range:

- base_sha: `b84a34235aa5b37bb0ce83f23ac35e4e5e686899` (`H_intake`)
- head_sha: `9b0e62c4ef72691084443947e9bcdd4408480b6c` (`H_C`)

Recompute the stage `diff_fingerprint` from a clean shell in the repo root:

```bash
git diff --binary b84a34235aa5b37bb0ce83f23ac35e4e5e686899..9b0e62c4ef72691084443947e9bcdd4408480b6c -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json' | shasum -a 256
```

Expected (recorded in `status.json.diff_fingerprint`):

```text
9b0e62c4ef72691084443947e9bcdd4408480b6c:6e6e2d4d7ee28dc6547c727b6a4c99779605686e38af2586a42ac49171114854
```

If your recomputed value differs, that is a P0/P1 finding — return REWORK.

### Task-level boundaries (each task's diff must be owner-scoped; status.json excluded)

- **Task A** (`b84a342..dba4c12`): expect `8afc3dcf42da591bb171f6622937455315d78e1f2167cb672c4cad96a7d38318`.
  NOTE: this range physically spans `d3d6e7c` (intake/design dispatch prompts:
  `controller-start-prompt.md` + `task-b-kimi-frontend.prompt.md` — legitimate
  H_intake scope, no product code) + `dba4c12` (H_A). Task A's actual product
  scope is the single commit `dba4c12` (4 files: `backend/domain/snapshot.py`,
  `backend/tests/test_snapshot.py`, `docs/api/public-market-contract.md`,
  `20-implementation-backend.md`). Verify `git show --name-only dba4c12`.
- **Task B** (`dba4c12..0fd0d17`): expect `5552ed82f3bb57bdacb1d6f8c981cdc13829603ff865a6458547d6112f8e9835`,
  4 files all under `frontend/**` + `20-implementation-frontend.md`.
- **Task C** (`cc6ff1d..9b0e62c`): expect `28670f9807d372bfb60816e4839f230ea94aa50bab70197be971281eddd09a40`,
  stage summary/test-output/ADR/handoff; **no product code**.

Any cross-task leakage (frontend file in Task A's diff, backend file in Task B's
diff, product code in Task C's diff) is a P1 finding — return REWORK.

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these yourself:

- `reports/agent-runs/2026-07-public-market-ui-cn-v1/00-task.md` (scope, deliverables, acceptance — authoritative)
- `.../10-design.md`, `.../11-adr.md` (design/breakdown — evidence, not top authority)
- `.../20-implementation.md` (stage summary), `20-implementation-backend.md`, `20-implementation-frontend.md`
- `.../30-review-1.md` (aggregate), `30-review-1-backend.md`, `30-review-1-frontend.md` (review-1 — scrutinize, don't trust)
- `.../60-test-output.txt` (raw test evidence incl. rows-baseline replay)
- `.../status.json`
- `backend/domain/snapshot.py` (CONTRACT_WARNINGS, build_rows, assemble_snapshot)
- `backend/tests/test_snapshot.py`
- `frontend/index.html`, `frontend/self-check.js`, `frontend/fixture/public-market-snapshot.json`
- `schemas/api/public-market/snapshot.schema.json` (read-only contract / top authority)
- `docs/api/public-market-contract.md` (read-only contract / top authority)
- `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/` (the live lastFundingRate evidence the new warning cites: `evidence-index.md` sha256 + `verify-funding-semantics.py` PASS)
- The frozen stage diff:
  `git diff --binary b84a342..9b0e62c -- . ':(exclude)reports/agent-runs/2026-07-public-market-ui-cn-v1/status.json'`

## What to verify (each is a checkpoint)

### A. Hard constraints (security/safety — any breach is REWORK)

1. **No API key, signed endpoint, private account endpoint, user data stream,
   order/borrow-action/repay/transfer/websocket.** This stage is offline-only;
   the only live capture was at intake (anonymous public GET). Grep the diff:
   `grep -RniE 'apikey|api_key|secret|signature|userDataStream|listenKey|/sapi/|/dapi/v1/order|/fapi/v1/order|websocket' backend frontend` (expect none functional).
2. **No live HTTP during A/B/C.** Confirm the stage did not add any network call
   (evidence already captured at intake).
3. **Read-only inputs untouched.** `schemas/api/public-market/**` and
   `reports/api-samples/**` must NOT appear in the stage diff.
   `docs/api/public-market-contract.md` is touched ONLY by Task A (the
   lastFundingRate paragraph + its Open Verification Items entry) — confirm via
   `git diff b84a342..9b0e62c -- docs/api/public-market-contract.md`.
4. **Same-origin frontend; no forbidden interaction.** Default load fetches the
   relative `/api/public-market/snapshot`; fixture is a manual offline fallback.
   No order/buy/sell/borrow-action/repay/transfer/open-position/account UI.

### B. Wording amendment correctness (Task A) — the core of this stage

5. **`snapshot.py`: single string change.** `git diff d3d6e7c..dba4c12 --
   backend/domain/snapshot.py` is exactly one `-1/+1` line pair
   (`CONTRACT_WARNINGS[1]`). `build_rows` / `assemble_snapshot` / every other
   constant unchanged. Any logic change → REWORK.
6. **`warnings[1]` matches `00-task.md:51-57` verbatim** and cites the real
   evidence path `reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`.
   Semantics: `lastFundingRate` = real-time estimate for the CURRENT period,
   charged at nextFundingTime, drifts until settlement; settled history comes
   from `/fapi/v1/fundingRate`. Confirm `verify-funding-semantics.py` PASS.
7. **Contract doc in lockstep.** The lastFundingRate funding-semantics paragraph
   is revised to the evidenced wording, and the Open Verification Items entry
   moves PARTIALLY RESOLVED → RESOLVED (citing the verify script). Other doc
   content unchanged.
8. **rows / API payload otherwise frozen.** This is the central invariant: the
   ONLY API-payload change is `warnings[1]` text. Task C asserts rows are
   field-identical to the accepted `548ae0d` build (647==647). Re-verify
   independently if you wish (worktree checkout `548ae0d`, offline build, diff
   rows). Any rows drift → P0 REWORK. Also confirm `classify.py` /
   `normalize.py` / `snapshot_service.py` / `schemas/**` are NOT in the stage
   diff.

### C. Frontend (Task B)

9. **Rate percent formatting is string-shift only (DECIMAL DISCIPLINE).**
   `formatFundingRate` (`frontend/index.html:586-600`) shifts the decimal by
   string manipulation; `parseFloat` / `Number*100` on the funding rate is
   FORBIDDEN. `grep -nE 'parseFloat|Number\(' frontend/index.html` — the only
   hits must be `formatPrice` (mark/index thousands-sep) and
   `classForFundingRate` (CSS sign-class), both off the rate-percent path (ADR-3).
   Spot-check: `"0.00010000"`→`+0.01%`, `"-0.00005000"`→`-0.005%`,
   `"0.00000000"`→`0%`, `"0.00008556"`→`+0.008556%`.
10. **Column merge + flags de-noise + CN-first.** Cols 4/5 merged
    (「资金费率/结算时间」, `+0.01% / 16:00`); inline badges only for
    `PERP_ONLY_NO_SPOT_LEG`/`TRADIFI_BSTOCK`; `MARGIN_PUBLIC_UNVERIFIED` is a
    page-level note; warnings → neutral 「数据说明」 area (3 CN + English
    `<details>`); main table does not emit raw English enums (technical terms
    USDT/bStock/API/symbol excepted).
11. **fixture.warnings[1] synced.** `frontend/fixture/public-market-snapshot.json`
    `warnings[1]` byte-identical to backend
    `SnapshotService(Config(offline=True)).build_snapshot()['warnings'][1]`.

### D. Integration & test evidence (Task C)

12. **`60-test-output.txt`**: pytest 54 passed; `node frontend/self-check.js`
    14/14; `float(` audit clean; schema VALID; rows-baseline replay vs `548ae0d`
    = ROWS IDENTICAL (only warnings[1] differs).
13. Re-run the suites yourself:
    - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q` (expect 54 passed)
    - `node frontend/self-check.js` (expect 14 PASS)
14. **Review-1 scrutiny**: both review-1 verdicts ACCEPT — confirm the material
    claims (fingerprints, boundaries, decimal discipline, no forbidden
    interaction) hold independently. Do not rubber-stamp. The Task B P3
    (pre-existing sidebar wordmark "Funding Hedge") is correctly classified
    non-blocking/out-of-scope.

### E. Known non-blocking residuals (carry forward, do not block)

- The lastFundingRate evidence is a **single mid-period snapshot** (divergence +
  15-min drift); read-only intake evidence, not re-fetched this stage.
- Frontend tested on the frozen fixture; live endpoint serves the full market.
  Rendering is row-count-agnostic.
- The Task B P3 sidebar wordmark is pre-existing and out of this stage's CN
  checklist; leaving it is correct surgical-changes discipline.

If you find a genuine correctness/safety/boundary defect (snapshot.py changed
beyond the warnings[1] string; rows drift; parseFloat/Number*100 on the rate
path; forbidden interaction; read-only input modified; boundary crossing),
return `REWORK` with a `fix_start_prompt`. Otherwise return `ACCEPT`.

## Boundary (read-only)

You may read anything in the repository. You may NOT modify any file. You may
NOT be swayed by controller or review-1 narratives — recompute fingerprints and
re-check rules yourself against the raw code, the raw diff, and the frozen
contract.

## Output contract (strict)

Emit your review narrative, then a single JSON verdict object that validates
against `schemas/review-verdict.schema.json`. Read that schema. Use:

- `schema_version`: `1`
- `stage_id`: `2026-07-public-market-ui-cn-v1`
- `role`: `second_reviewer` *(if the schema enum requires `final_reviewer`, use
  that instead — read the schema and use the value it allows for review-2)*
- `model`: `gpt5.5`
- `verdict`: `ACCEPT` or `REWORK` (or `BLOCKED`)
- `diff_fingerprint`: your recomputed **stage-level** value
  (`9b0e62c…:<your sha256>`)
- `reviewer_prior_involvement`: **`direction_synthesis`** (NOT none — disclose in notes)
- `reviewer_prior_involvement_notes`: prior direction synthesis
  (approved_prior_stage, covers this stage, no new panel), no
  design/breakdown/code involvement, strong-reviewer override invoked, hard ban
  satisfied, same path as impl-v1/bstock-alias-v1.
- `reviewed_artifacts`: the paths you actually inspected
- `findings`: ordered by severity (P0 first); empty array allowed for ACCEPT
- `required_fixes`: empty for ACCEPT; concrete for REWORK
- `residual_risks`: the single-snapshot-evidence / fixture-vs-live / sidebar-wordmark notes
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings, required fixes, allowed boundaries, forbidden paths, and the
exact post-fix commands (`pytest`, `node frontend/self-check.js`).

Emit the JSON verdict as the final block of your reply, fenced in ```json.
