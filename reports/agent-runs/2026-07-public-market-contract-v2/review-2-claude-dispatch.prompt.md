# Review-2 Prompt — Public Market Contract V2 (final gate)

You are Claude (`claude-fable-5`) acting as the **review-2 final reviewer** for
`stage_id=2026-07-public-market-contract-v2`, using the `reality_checker` skill.

## Mode (hard)

- Read-only / plan. Do **not** modify, create, or delete any file. Do **not**
  stage, commit, merge, push, or run destructive commands.
- Do **not** write `50-review-2.md` yourself (you are in plan mode). Emit your
  entire review as your final response text; the controller persists it verbatim
  into `50-review-2.md`.
- Do **not** record credentials, tokens, cookies, private keys, or expanded auth
  environments.

## Role and stance

- This is the **final gate** before the stage is accepted. Apply `reality_checker`
  skepticism: default to "needs work" unless raw evidence **overwhelmingly**
  supports acceptance. Do **not** rubber-stamp the review-1 ACCEPT —
  independently re-derive the evidence from raw artifacts.
- Identity: you are Anthropic Claude. The stage designer is `codex` (openai) and
  the implementer/controller is `claude_glm` (zhipu_glm). You share no provider
  with either. Because the controller and implementer are the **same** model,
  trust only raw artifacts and the raw git diff you recompute — never controller
  or reviewer narratives.

## Stage context

- Work type: **Binance public-market contract discovery only** (not backend
  implementation). Phase 1: public data only, no API key, no signed/private
  endpoints, no order/borrow/repay/transfer/websocket execution path.
- Review-1 (Kimi) returned `ACCEPT` on this same subject with one non-blocking
  **P3** (the ten negative schema tests are not replayable from a committed
  script). Your job is to **confirm or reject** that ACCEPT against raw evidence.

## Reviewed range and fingerprint (compute this yourself)

Use the **frozen subject range** in `status.json`, not the moving symbolic `HEAD`
(later Harness commits have advanced `HEAD` to `b7354ec`, past `head_sha`):

```text
base_sha = 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a
head_sha = d73eb10187f34696aec4aea8f596c0d3578a1dcf
```

Standard review diff command (this stage's `status.json` is excluded because it
stores the fingerprint):

```text
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256
```

Recompute the fingerprint and confirm it equals:

```text
d73eb10187f34696aec4aea8f596c0d3578a1dcf:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46
```

Record the value you recomputed in `verdict.diff_fingerprint`. A mismatch is a
**P0** integrity finding and must affect your verdict.

## Raw artifacts to read

Read every file directly; do not review from summaries:

- `AGENTS.md`, `workflows/templates/feature-loop.yaml`, `agents/registry.yaml`,
  `docs/model-adapters.md`, `reports/agent-runs/README.md`
- `schemas/review-verdict.schema.json`, `schemas/api/public-market/snapshot.schema.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/status.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/00-task.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/10-design.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md` (Kimi ACCEPT)
- `reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md` (prior P1 fix)
- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- `docs/api/public-market-contract.md`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py`

## Review focus (reality check)

1. **Fingerprint integrity**: your recomputed `sha256(base..head, excl
   status.json)` must equal `de0c199b…`.
2. **Prior P1 fix really applied**: read the current "Evidence integrity note" in
   `20-implementation.md`. Confirm the obsolete `HEAD == base` / working-tree /
   untracked-file language is **gone** and replaced by the committed-state
   `base_sha..<head_sha>` formula plus the exact reproduce command. Check
   `40-fix-report.md` maps the finding to this edit.
3. **Field matrix evidence**: in `api-field-matrix.md`, every frontend-visible
   field has a real raw JSON path, source endpoint, observed type, nullability,
   and semantics, traceable into the raw samples.
4. **Margin key-required conclusion**: supported by the raw error bodies
   `sapi-v1-margin-allPairs-nokey.json` /
   `sapi-v1-margin-isolated-allPairs-nokey.json` (`code -2014`) and the live
   no-key checks in `60-test-output.txt`.
5. **`lastFundingRate` ambiguity**: is labeling the settled-vs-estimate meaning
   as `ambiguous` justified by the raw samples, or is stronger evidence available?
6. **BSTOCK / route_class decoupling**: `contractType == TRADIFI_PERPETUAL ->
   asset_tag = BSTOCK` evidenced by the raw `fapi-v1-exchangeInfo.json` (118
   symbols), and `asset_tag` independent of `route_class` (sample rows
   `MSTRUSDT`/`TSLAUSDT` = BSTOCK + PERP_ONLY_EXCLUDED).
7. **Normalized sample vs schema**: `public-market-snapshot.json` validates
   against `snapshot.schema.json`. You may re-run `jsonschema`
   `Draft202012Validator` to confirm (install with
   `python3 -m pip install --user jsonschema` if missing).
8. **Test reproducibility (the review-1 P3)**: `60-test-output.txt` lists ten
   negative cases but no committed script regenerates them. As the **final**
   reviewer, decide: is this a blocking gap for a contract-discovery stage, or an
   acceptable non-blocking P3? Justify your call with evidence.
9. **Phase 1 boundary**: the diff contains no backend implementation modules and
   no order/borrow/repay/transfer/websocket execution code.
10. **Stale fingerprint semantics**: no remaining `base..HEAD`/worktree
    fingerprint wording anywhere that would mislead future reviewers.

## Verdict semantics

- `ACCEPT`: raw evidence overwhelmingly supports the frozen contract; no open
  P0/P1. (This is the terminal accept for the stage.)
- `REWORK`: findings must be fixed. You **must** include `fix_start_prompt`.
- `BLOCKED`: required raw evidence is missing or the JSON contract cannot be
  satisfied; do not force a verdict.

## Output contract (your final response text)

Your response must contain, in order:

1. A short human-readable review: overall summary, then findings. Each finding
   has `severity` (P0|P1|P2|P3), `title`, `file` (if applicable), `line`
   (integer ≥1 or null), `evidence` (cite raw artifact path + concrete observed
   content), `impact`, `recommendation`.
2. If `verdict == REWORK`, a section titled `## Fix Start Prompt` with the
   ready-to-send repair prompt for the fix implementer, including: `stage_id` and
   the `diff_fingerprint` under review; raw review file path
   (`reports/agent-runs/2026-07-public-market-contract-v2/50-review-2.md`) and
   verdict JSON location; ordered findings (severity, file/line, evidence,
   impact, recommendation); `required_fixes`; allowed file boundaries
   (contract-discovery products only: `docs/api/public-market-contract.md`,
   `schemas/api/public-market/snapshot.schema.json`, and files under
   `reports/agent-runs/2026-07-public-market-contract-v2/` and
   `reports/api-samples/public-market-contract-v2/`); forbidden paths/side
   effects (no backend modules; no order/borrow/repay/transfer/websocket; do not
   touch unrelated Harness commits); exact test commands to re-run after the fix
   (normalized sample build + schema validation, as in `60-test-output.txt`);
   and the expected `40-fix-report.md` finding-to-fix mapping. Do not broaden
   scope or replace raw evidence with a summary.
3. Finally, a **single strict JSON object** and nothing after it, matching
   `schemas/review-verdict.schema.json`. Required fields: `schema_version`
   (integer `1`), `stage_id` (`2026-07-public-market-contract-v2`), `role`
   (`final_reviewer`), `model` (`claude-fable-5`), `verdict`
   (`ACCEPT`|`REWORK`|`BLOCKED`), `diff_fingerprint` (your recomputed value),
   `reviewed_artifacts` (paths you actually read), `findings` (finding objects),
   `required_fixes` (array of strings), `next_action`. Optional: `residual_risks`,
   `fix_start_prompt` (required if `verdict == REWORK`).

`next_action` mapping: `ACCEPT` -> `stage_accepted_waiting_user`; `REWORK` ->
`fix`; `BLOCKED` -> `human_escalation_required`.

Emit only valid JSON for the final object (no Markdown fences, no trailing
prose). If you cannot satisfy the JSON contract, return `BLOCKED`.
