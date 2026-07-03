# ADR: 2026-07-public-market-bstock-alias-v1

## ADR-1: Amend (not replace) the contract; keep `schema_version` unchanged

- Context: the bStock alias rule needs a new `spot.match_type` field and a
  formal route rule, but the rest of the snapshot shape is stable and already
  integrated by the frontend.
- Decision: additive amendment. `schema_version` stays
  `"public-market-snapshot/v1"`; `spot.match_type` is a nullable enum.
- Rationale: backward-compatible (consumers that ignore unknown/null fields are
  unaffected); avoids a contract-version churn that would force a parallel
  contract-v3 stage. The amendment is documented in-place as "Frozen amendment
  (2026-07-03)".

## ADR-2: Alias fires only for `contractType == "TRADIFI_PERPETUAL"`

- Context: the B-suffix spot symbol convention is specific to bStocks. Normal
  crypto spot symbols equal the futures symbol exactly.
- Decision: `resolve_spot_leg` tries `baseAsset+"B"+quoteAsset` ONLY when
  `contract_type == "TRADIFI_PERPETUAL"`. Normal crypto always uses exact join.
- Rationale: prevents any chance of a crypto symbol accidentally matching a
  `B`-suffixed spot pair; keeps the crypto path identical to impl-v1. `asset_tag`
  already marks TRADIFI as BSTOCK, so the gate is cheap and unambiguous.

## ADR-3: Do NOT change `classify.py`; the fix is the spot-leg join

- Context: the user asked for "bStock positive funding → candidate / negative
  funding → disabled". One could implement this inside the classifier.
- Decision: leave `classify_route` and `negative_funding_status` byte-for-byte
  unchanged; fix the join in `resolve_spot_leg` so the right `spot_symbol`
  reaches the classifier.
- Rationale: the existing priority (PERP_ONLY → BSTOCK → SPOT_ONLY →
  PRIVATE_BORROW) already yields `MARGIN_SPOT_CANDIDATE` + `DISABLED_BSTOCK` for
  a bStock with a margin-allowed spot leg. Touching the classifier would risk
  regressing the 688-row crypto market for no gain. `classify.py` is regression-
  asserted only.

## ADR-4: `match_type` cross-condition enforced in code + tests, not schema

- Context: `match_type` must be `null` exactly when `spot.exists=false`.
  jsonschema Draft 2020-12 cannot express this compactly inside the `spot`
  object without `if/then` bloat that also complicates the OpenAI strict
  response_format path used elsewhere.
- Decision: schema declares `match_type` as a nullable enum; the
  `exists ⟺ match_type!=null` invariant is enforced by `build_rows` logic and
  asserted by `test_snapshot.py`.
- Rationale: keeps the schema readable and reuse-friendly; the invariant is a
  single backend code path that is trivially testable.

## ADR-5: Synthetic offline bStock fixture; frozen samples stay read-only

- Context: the contract-v2 curated spot fixture contains only BTC/ETH/XVG (no
  bStock), and `reports/api-samples/public-market-contract-v2/**` is frozen
  historical evidence. Live capture would violate this stage's offline scope.
- Decision: add `backend/tests/fixtures/bstock-alias-raw/**` — synthetic raw
  payloads with `TSLAUSDT` (TRADIFI futures) + `TSLABUSDT` (spot,
  `isMarginTradingAllowed=true`). No frozen evidence is modified; no live HTTP.
- Rationale: covers the alias + classify + snapshot paths deterministically and
  offline; preserves contract-v2 evidence integrity.

## ADR-6: `CONTRACT_WARNINGS[2]` text is contract semantics, amended with the doc

- Context: the served `warnings[]` are part of the contract surface; warning 2
  ("TRADIFI have no spot leg") is now factually wrong.
- Decision: update `CONTRACT_WARNINGS[2]` in `snapshot.py` AND the contract doc
  in lockstep so the served warning matches the amended rule.
- Rationale: the frontend renders `warnings[]` verbatim and must not display a
  stale "no spot leg" claim next to a bStock row that now has a spot leg.

## ADR-7: impl-v1 finding closure is a status update, not a verdict rewrite

- Context: this stage closes impl-v1's open P1 finding
  `bstocks_b_suffix_spot_margin_alias`.
- Decision: after this stage passes review-2 + pre-accept, the controller sets
  impl-v1 `status.json.post_review_findings[…].status = "resolved_by_stage"`
  referencing this stage's id + head. impl-v1's `review_1`/`review_2` verdicts
  and `diff_fingerprint` are NOT touched (they remain valid for the contract
  impl-v1 reviewed). impl-v1 stays `stage_accepted_waiting_user`.
- Rationale: editing impl-v1 `status.json` does not affect its `diff_fingerprint`
  (status.json is excluded from the hash); the change is a finding-status
  bookkeeping, not an alteration of review evidence.

## ADR-8: Fable5 breakdown unavailable → controller-direct design (lightweight)

- Context: AGENTS.md makes Fable5 the default MEDIUM breakdown author, but the
  local `claude` CLI auth routes to `zhipu_glm`, so `claude-fable-5` is
  unreachable (error 1211). See `fable5-detail-breakdown.unavailable.md`.
- Decision: controller authors the design record (`00-task.md`, `10-design.md`,
  this file); `user_approved_lightweight_route = true` (approved plan
  `[可调整]`). Review-1 and review-2 still run as independent gates.
- Rationale: runner-level unavailability of the breakdown model is a documented
  fallback, not a gate skip. The amendment is narrow and fully specified by the
  user's 6 points + the approved plan, so controller-direct design is low-risk;
  independent review still validates it.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller)
下一步任务: Build `status.json` (task records A/B/C + model routing), author `70-handoff.md`, commit `H_intake`.
