# Handoff: Public Market bStock Alias Amendment V1

## Stage start: contract amendment + backend/frontend repair of the bStock B-suffix alias

Stage `2026-07-public-market-bstock-alias-v1` closes the impl-v1 post-review P1
finding `bstocks_b_suffix_spot_margin_alias`. impl-v1 accepted against the
FROZEN `public-market-contract-v2`; the bStock alias case was found AFTER
review-2, so this is a **contract amendment** (not a rework of the frozen
contract). impl-v1's review-2 verdict is NOT altered.

The amendment promotes the alias rule into:
- `schemas/api/public-market/snapshot.schema.json` — new `spot.match_type` field.
- `docs/api/public-market-contract.md` — descriptive note → frozen amendment rule.
- `backend/domain/normalize.py` — `resolve_spot_leg` pure function (exact →
  bStock B-suffix alias → none).
- `backend/domain/snapshot.py` — `build_rows` uses `resolve_spot_leg`, fills
  `match_type`, updates `CONTRACT_WARNINGS[2]`.
- `frontend/**` — futures symbol vs actual spot symbol + match source.
- `backend/tests/**` + synthetic `bstock-alias-raw/` fixture.

**Semantic core**: `classify.py` is NOT changed. The existing
`negative_funding_status` priority (PERP_ONLY → BSTOCK → SPOT_ONLY →
PRIVATE_BORROW) already yields `MARGIN_SPOT_CANDIDATE` + `DISABLED_BSTOCK` for
a bStock with a margin-allowed spot leg, once the correct spot symbol reaches
`classify_route`. The real fix is the spot-leg join.

## Fable5 breakdown UNAVAILABLE → controller-direct design

The plan called for Fable5 (`claude-fable-5`, anthropic) to author
`fable5-detail-breakdown.md`. Runner-level probe failed: the local `claude` CLI
auth routes to `zhipu_glm`, so `--model claude-fable-5` returns error 1211
(模型不存在); the claude.ai login is overridden. Evidence:
`fable5-detail-breakdown.unavailable.md`. Per the approved plan's `[可调整]`
clause, the controller authors the design record directly (`00-task.md`,
`10-design.md`, `11-adr.md`); `user_approved_lightweight_route=true`. Fable5 is
re-runnable if an Anthropic-authed environment is provided. Review-1 and
review-2 still run as independent gates. This SIMPLIFIES review-2 disclosure:
Fable5 has no involvement, so the only prior involvement is Codex
(`direction_synthesis`).

## Task boundaries (from 00-task.md)

- Task A — contract amendment + backend repair. Owner Claude-GLM. Writes
  `schemas/api/public-market/snapshot.schema.json`,
  `docs/api/public-market-contract.md`, `backend/domain/{normalize,snapshot}.py`,
  `backend/tests/**`, `backend/tests/fixtures/bstock-alias-raw/**`,
  `20-implementation-backend.md`. (`classify.py` forbidden.)
- Task B — frontend display. Owner Kimi. Writes `frontend/**` +
  `20-implementation-frontend.md`. Depends on Task A freezing `match_type`.
- Task C — integration verification. Owner controller. No product code.

A boundary crossing is REWORK regardless of code quality.

## Commit-order strategy (keeps task fingerprints clean)

Same as impl-v1. Serial commits so each task's `base..head` diff is
owner-scoped:

1. `H_intake` — stage evidence (intake, task, design, ADR, status, handoff,
   Fable5 unavailable record). This is the task base. **THIS COMMIT.**
2. `H_A` — Task A: amendable contract schema/doc + `backend/**` + tests +
   `20-implementation-backend.md` + `60-test-output.txt` (Task A). Task A
   `base_sha=H_intake`, `head_sha=H_A`. NEXT.
3. `H_B` — Task B: `frontend/**` + `20-implementation-frontend.md`. Task B
   `base_sha=H_A checkpoint`, `head_sha=H_B`.
4. `H_C` — Task C: `20-implementation.md` + `60-test-output.txt` Section 4 +
   integration sample + final `status.json`/handoff. Stage-level top-level
   `base_sha=H_intake`, `head_sha=H_C`.

Same fingerprint formula at both scopes; no second protocol.

## Evidence policy (controller == contract+backend implementer)

Controller and Task A implementer share provider (`claude_glm`). Mitigations
(recorded in `status.json.evidence_policy`): reviewers recompute
`diff_fingerprint` from raw `base..head`; test output is replayable raw
command output; review prompts pass raw artifact and raw diff paths, not
controller summaries; Task B review-1 uses a fresh read-only Claude-GLM session
(not the controller/Task A transcript).

## Review routing (planned)

- Task A review-1: Kimi (`code_reviewer`, read-only) → `30-review-1-backend.md`.
- Task B review-1: fresh read-only Claude-GLM → `30-review-1-frontend.md`.
- Stage review-2: Codex/GPT (`codex`, gpt5.5 xhigh). Codex is the prior
  direction_synthesizer (covers this stage); Fable5 unavailable; both
  implementers (`zhipu_glm`, `kimi`) barred from review-2. Codex reviews via
  the `direction_synthesis` strong-reviewer override.
- Grok excluded from implementation and review.

## Branch / state

- Branch: `main` (local only, ahead of origin). Current HEAD `35e032a`
  (impl-v1 bStock finding record); `H_intake` commits on top.
- `status.json` is the authoritative machine state; this handoff is a human
  navigation aid.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller / Task A implementer)
下一步任务: Commit `H_intake` (stage evidence), then implement Task A (contract amendment + `resolve_spot_leg` + `build_rows` + synthetic fixture + tests) → `H_A`.

---

## Review outcome (completed — appended after the gates ran)

The "Review routing (planned)" section above was the plan; the actual outcomes:

- **Task A review-1** (Kimi, cross-review): **ACCEPT** — `30-review-1-backend.md`;
  fingerprint recomputed independently and matching `tasks.A`; `classify.py` diff
  empty; 52 pytest passed; `float()` clean. Raw: `review-1-task-a-kimi.raw-output.txt`.
- **Task B review-1** (fresh read-only Claude-GLM Agent session, cross-review):
  **ACCEPT** — `30-review-1-frontend.md`; isolated context (did not inherit the
  controller/Task-A transcript); fingerprint matching `tasks.B`; self-check 11/11.
- **Stage review-2** (Codex/GPT `gpt5.5` xhigh, `final_reviewer`,
  `reviewer_prior_involvement=direction_synthesis`, strong-reviewer override):
  **ACCEPT** — `50-review-2.md`; raw `review-2-codex.raw-output.txt`. Dispatched
  via the user-directed `codex exec --model gpt-5.5` on the locally-configured
  default provider (proxy2233=402 payment_required, proxy6651=403
  subscription_not_found; Fable5/Anthropic unreachable). `--output-schema` was
  unusable on the route (OpenAI strict mode rejects the verdict schema shape),
  so the verdict was emitted as a fenced json block and controller-validated
  post-hoc (jsonschema valid; fingerprint matches `status.diff_fingerprint`).
- **`scripts/validate-stage.py --phase pre-accept`**: **PASSED**
  (status `stage_accepted_waiting_user`).

Stage state: `stage_accepted_waiting_user`, `can_accept_final=false`. The
controller does NOT declare final acceptance; the stage awaits the user. The
impl-v1 P1 finding `bstocks_b_suffix_spot_margin_alias` is closed
(`resolved_by_stage`, this stage id + head `0842820`); impl-v1 review
verdicts/diff_fingerprint unchanged; impl-v1 pre-accept still PASSED. Both
stages await user final acceptance together.

本地北京时间: 2026-07-04 00:33:00 CST
下一步模型: user (final acceptance decision)
下一步任务: User reviews this stage + impl-v1 and decides final acceptance. No further automated work; controller holds.

---

## Evidence-backfill round (2026-07-04) — review-2 recheck trigger

After the stage reached `stage_accepted_waiting_user`, a user-directed
evidence-backfill round grounded the bStock alias amendment in LIVE public
evidence, not only the synthetic fixture. The prior review-2 ACCEPT (bound to
head `0842820`, synthetic-only scope) is preserved verbatim as `review_2_prior`
in `status.json`; it is NOT deleted or altered.

Backfill changes (all in-scope for the recheck; `base_sha=d240e43` unchanged):

1. Harness adapter corrections + new Hard Gates rule (commit `0578191`): a
   contract amendment must carry raw public samples; synthetic fixtures only
   supplement. Claude/Fable5 probes must strip GLM/Zhipu env vars first and must
   not record a GLM-endpoint failure as Anthropic/Fable5 unavailable.
2. Live public capture (commit `9f4764c`):
   `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/` —
   anonymous `/fapi/v1/exchangeInfo` + `/api/v3/exchangeInfo` (no key / signed /
   private / order / borrow / repay / transfer / websocket). `evidence-index.md`
   cross-verifies the 15 user-listed bStocks: 15/15 spot legs present with
   `isMarginTradingAllowed=true`, 15/15 futures legs with
   `contractType=TRADIFI_PERPETUAL`, 15/15 satisfy
   `futures_baseAsset+"B"+quoteAsset == spot_symbol`.
3. Live-raw alias recheck (this commit): drives the REAL
   `backend/domain/snapshot.build_rows` + `assemble_snapshot` with the live
   exchangeInfo. 15/15 bStocks → `MARGIN_SPOT_CANDIDATE` +
   `bstock_b_suffix_alias` + `DISABLED_BSTOCK`; BTCUSDT negative control
   exact-matches (alias does not pollute crypto); assembled snapshot
   jsonschema-valid against the amended `snapshot.schema.json`. Section 5 of
   `60-test-output.txt`: PASS.

Stage `head_sha` advanced to the backfill head; `diff_fingerprint` recomputed
(`base_sha=d240e43` unchanged). `status` returned to `review_2` (recheck
pending). `scripts/validate-stage.py --phase pre-review` PASSED; `--phase
pre-accept` is expected to FAIL until the Codex/GPT recheck returns ACCEPT
(review_2 rebinds to the new head/fingerprint). The controller does NOT declare
final acceptance.

### Open items (carry forward; do NOT block this evidence backfill)

Deferred to a later position-opening planning contract's pre-trade verification,
not this alias-amendment stage:

- **bStock token vs US-equity 1:1 equivalence** is NOT proven from public
  exchangeInfo alone. Whether one bStock token tracks one share of the
  underlying US equity, and any redemption/conversion constraints, must be
  verified before any position is opened.
- **bStock spot session vs perpetual 7x24**: the spot/margin leg may not trade
  24/7 (equity-market sessions), while the TRADIFI perpetual runs 7x24. The
  resulting funding/price-gap and hedge-continuity implications must be assessed
  before opening positions.

本地北京时间: 2026-07-04 01:15:23 CST
下一步模型: Codex/GPT (review-2 recheck)
下一步任务: Codex review-2 recheck on the expanded scope (`base d240e43..backfill head`) via `codex exec --model gpt-5.5`. On ACCEPT, rebind `review_2` to the new head/fingerprint, set `status=stage_accepted_waiting_user`, run pre-accept (must PASS). Controller holds; does not declare final acceptance.

---

## Post-review external finding -> rework round 1 (2026-07-04)

After the review-2 recheck ACCEPT (head `b189440`), a user-directed external
post-review by **anthropic / claude-fable-5** (no prior involvement this stage;
Fable5 is reachable again as of 2026-07-04, superseding the earlier
"unavailable" records for future routing) found a **P1 regression**:

- `backend/domain/snapshot.py:70` passes the literal `"USDT"` as `quote_asset`
  to `resolve_spot_leg` instead of the row's real `quoteAsset`. With no
  upstream quoteAsset filter, 39 of the 43 non-USDT-quoted live perpetuals get
  a wrong spot leg labeled `exact_symbol` (`BTCUSDC`->`BTCUSDT`,
  `ETHBTC`->`ETHUSDT`, ...) and `PNUTUSDC` flips route
  `SPOT_ONLY_CANDIDATE`->`MARGIN_SPOT_CANDIDATE`. Verified offline against this
  stage's own committed live raw (`20260703T170827Z`). The bStock alias closure
  (15/15) itself remains valid; `resolve_spot_leg` and the frozen contract
  wording are correct — the defect is the single call site.

Records:

- Finding evidence: `post-review-quote-asset-hardcode-finding.md`
- Fix dispatch: `fix-start-prompt-spot-leg-quote-asset.md`
- `status.json`: `status=fixing`, `rework_count=1/3`,
  `post_review_findings[spot_leg_quote_asset_hardcode]` open; review-1/review-2
  ACCEPT verdicts preserved verbatim (their fixtures/live checks covered only
  USDT-quoted symbols).
- Pre-existing `quote_asset={"const":"USDT"}` vs unfiltered universe recorded in
  `open_items` as a user scope decision — NOT part of this rework.

本地北京时间: 2026-07-04 10:27:11 CST
下一步模型: Claude-GLM (controller / Task A owner)
下一步任务: Execute rework round 1 per `fix-start-prompt-spot-leg-quote-asset.md`; then review-1 re-verdict on the fix diff, review-2 re-run bound to the new head (re-evaluate the decision pool now that Fable5 is reachable), fingerprints rebound, status -> review_1 -> review_2 -> stage_accepted_waiting_user.

### User decision (2026-07-04): USDT-only universe, folded into rework round 1

用户决策：Phase 1 快照仅覆盖 USDT 计价交易对，其他稳定币计价（USDC/USD1/U/...）
推迟到未来阶段。universe 过滤新增 `quoteAsset == "USDT"`——兑现既有冻结 schema
的 `row.quote_asset const "USDT"` 声明，不构成合约修订（schema/docs 不动）。
该项与 P1 调用点修复一并纳入 rework 第 1 轮 required_fixes；
`fix-start-prompt-spot-leg-quote-asset.md` 与 `status.json`（`user_decisions`、
`post_review_findings`、`open_items`、`next_action`）已同步更新。live raw 复验
预期：universe 648 行全 USDT，无 exact_symbol 错配，15/15 bStock alias 不变。
