# Review-1 Prompt — Public Market Contract V2

You are Grok Build acting as the **review-1 first reviewer** for
`stage_id=2026-07-public-market-contract-v2`, using the `code_reviewer` skill.

## Mode (hard)

- This is a **read-only / plan** review. Do **not** modify, create, or delete any
  file. Do **not** stage, commit, merge, push, or run destructive commands.
- Do **not** write `30-review-1.md` yourself (you are in plan mode and cannot).
  Instead, emit your entire review as your final response text; the controller
  will persist your response verbatim into `30-review-1.md`.
- Do **not** record credentials, tokens, cookies, private keys, or expanded auth
  environments.

## Stage context

- Stage: `2026-07-public-market-contract-v2`.
- Work type: **Binance public-market contract discovery only** — verify public
  endpoint request/response fields and freeze the Phase 1 backend→frontend
  public-market snapshot contract. This is **not** backend implementation.
- Designer provider: `codex`. Implementer/controller provider: `claude_glm`
  (`glm-5.2[1m]`).
- Anti-trust note: the controller and the backend implementer are the **same**
  model (`claude_glm`). You must rely on **raw artifacts and the raw git diff
  you recompute yourself**, never on the controller's narrative summary.

## Phase 1 hard constraints (must hold in the reviewed diff)

- Public data only.
- No API keys, no signed endpoints, no private account endpoints.
- No order, borrow, repay, transfer, or websocket execution path.
- Contract-first: no backend implementation modules are expected in this stage.
- Reviewer must recompute the diff fingerprint; do not trust recorded strings.

## Reviewed range and fingerprint (compute this yourself)

Use the **frozen subject range recorded in `status.json`**, not the moving
symbolic `HEAD` (later Harness commits have already advanced `HEAD` past
`head_sha`):

```text
base_sha = 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a
head_sha = 1943e8b55c1cfdba018e8eae07428861e444e016
```

Standard review diff command (this stage's `status.json` is excluded because it
stores the fingerprint):

```text
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json"
```

Recompute the fingerprint and confirm it equals:

```text
1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d
```

Record the value you recomputed in the verdict `diff_fingerprint` field. If your
recomputation does **not** match the value above, treat it as a P0 finding
(fingerprint integrity) and decide ACCEPT/REWORK/BLOCKED accordingly.

## Raw artifacts to read

Read every file below directly. Do not review from summaries:

- `AGENTS.md`
- `workflows/templates/feature-loop.yaml`
- `agents/registry.yaml`
- `docs/model-adapters.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `schemas/review-verdict.schema.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/00-task.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/10-design.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py`

## Review focus

1. **Field matrix evidence**: does `api-field-matrix.md` provide a real raw JSON
   path and endpoint for each frontend-visible field, with observed types?
2. **Margin-endpoint auth conclusion**: is the claim that
   `/sapi/v1/margin/allPairs` and `/sapi/v1/margin/isolated/allPairs` require an
   API key actually supported by the captured raw error bodies
   (`sapi-v1-margin-allPairs-nokey.json`,
   `sapi-v1-margin-isolated-allPairs-nokey.json`) and `60-test-output.txt`?
3. **`lastFundingRate` ambiguity**: is labeling the settled-vs-estimate meaning
   as `ambiguous` justified, or is there stronger evidence in the raw samples?
4. **BSTOCK / route_class decoupling**: is `contractType == TRADIFI_PERPETUAL ->
   asset_tag = BSTOCK` with `asset_tag` independent of `route_class` correctly
   derived from the raw `fapi-v1-exchangeInfo.json`? Are the sample rows
   (`MSTRUSDT`/`TSLAUSDT` = BSTOCK + PERP_ONLY_EXCLUDED) consistent?
5. **Normalized sample vs schema**: does
   `normalized/public-market-snapshot.json` actually validate against
   `schemas/api/public-market/snapshot.schema.json`? Spot-check row structure.
6. **`60-test-output.txt` reproducibility**: are the commands replayable and the
   negative tests non-vacuous (i.e., the schema actively rejects bad data)?
7. **Stale fingerprint semantics**: is there any residual old
   `base..HEAD`/worktree-fingerprint wording (e.g., in `20-implementation.md`)
   that would mislead a future reviewer? Flag exact locations.

Also confirm the diff contains no backend implementation modules and no
order/borrow/repay/transfer/websocket execution code (Phase 1 constraint).

## Verdict semantics

- `ACCEPT`: no open P0/P1 findings; contract discovery is sound and frozen.
- `REWORK`: there are findings that must be fixed. You **must** include
  `fix_start_prompt`.
- `BLOCKED`: required raw evidence is missing or the JSON contract cannot be
  satisfied; do not force a verdict.

## Output contract (your final response text)

Your response must contain, in order:

1. A short human-readable review: overall summary, then findings. Each finding
   has: `severity` (P0|P1|P2|P3), `title`, `file` (if applicable), `line` (if
   applicable, integer ≥1 or null), `evidence` (cite the raw artifact path and
   the concrete content you observed), `impact`, `recommendation`.
2. If `verdict == REWORK`, a section titled **`## Fix Start Prompt`** containing
   the ready-to-send repair prompt for the fix implementer. It must include:
   the `stage_id` and the `diff_fingerprint` under review; the raw review file
   path (`reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md`)
   and the raw verdict JSON location; the ordered findings with severity,
   file/line evidence, impact, and recommendation; the `required_fixes`; the
   **allowed file boundaries** (this stage's contract-discovery products only:
   `docs/api/public-market-contract.md`,
   `schemas/api/public-market/snapshot.schema.json`, and files under
   `reports/agent-runs/2026-07-public-market-contract-v2/` and
   `reports/api-samples/public-market-contract-v2/`); **forbidden** paths and
   side effects (no backend implementation modules; no order/borrow/repay/
   transfer/websocket code; do not touch unrelated Harness commits); the exact
   test/lint/typecheck commands to run after the fix (re-run the normalized
   sample build + schema validation recorded in `60-test-output.txt`); and the
   expected `40-fix-report.md` finding-to-fix mapping. It must **not** broaden
   scope beyond the reviewed findings and must **not** replace raw reviewer
   evidence with a controller summary.
3. Finally, a **single strict JSON object** and nothing after it, matching
   `schemas/review-verdict.schema.json`. Required fields:
   `schema_version` (integer `1`), `stage_id`
   (`2026-07-public-market-contract-v2`), `role` (`first_reviewer`), `model`
   (`grok-build`), `verdict` (`ACCEPT`|`REWORK`|`BLOCKED`), `diff_fingerprint`
   (the value you recomputed), `reviewed_artifacts` (array of the paths you
   actually read), `findings` (array of finding objects), `required_fixes`
   (array of strings), `next_action`. Optional: `residual_risks`,
   `fix_start_prompt` (required if `verdict == REWORK`).

`next_action` mapping: `ACCEPT` → `continue`; `REWORK` → `fix`; `BLOCKED` →
`human_escalation_required`.

Emit only valid JSON for the final object (no Markdown fences around it, no
trailing prose). If you cannot satisfy the JSON contract, return `BLOCKED`.
