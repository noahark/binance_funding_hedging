# Review-1: Public Market Contract V2

Role: `reviewer_1`, provider=`kimi`, model=`kimi-2.7`, skill=`code_reviewer`, mode=read-only/plan.

Review date: 2026-07-03.

## Overall Conclusion

The contract discovery products are materially sound: endpoint auth is supported by raw error bodies and live checks, the field matrix maps every frontend-visible field to source endpoint/raw path/type/nullability/semantics, the BSTOCK rule and `asset_tag`/`route_class` decoupling are evidenced, and the normalized snapshot validates against the schema with passing negative tests. The diff contains no backend implementation modules and no order/borrow/repay/transfer/websocket execution code.

However, `20-implementation.md` still contains an outdated "Evidence integrity note" that describes a worktree/HEAD fingerprint and claims the changes are uncommitted (`HEAD == base`). This directly contradicts the committed-state fingerprint recorded in `status.json` and the `workflows/templates/feature-loop.yaml` / `AGENTS.md` hard gate that forbids worktree fingerprints. Because this note instructs future reviewers how to verify evidence, it is a **P1** documentation-integrity issue that must be corrected before review-2.

Verdict: **REWORK**.

## Findings

### P1: Stale worktree-fingerprint semantics in 20-implementation.md

- **severity**: P1
- **title**: `20-implementation.md` contains stale worktree-fingerprint semantics that contradict the committed-state diff protocol
- **file**: `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`
- **line**: 49
- **evidence**: Lines 49-52 state: "Changes are uncommitted (HEAD == base), so the literal `git diff --binary <base>..HEAD` is empty; the recorded value in `status.json` is sha256 over the full working-tree state versus base including untracked new files, excluding `status.json` itself (self-referential)." This is factually incorrect: `status.json` records `commit_state: "committed"`, `base_sha: "2bb47ad13065827ed1ee91d5d0e231cd312fdc0a"`, `head_sha: "1943e8b55c1cfdba018e8eae07428861e444e016"`, and the standard committed-state diff produces a non-empty diff whose sha256 is `e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d`, which matches the recorded `diff_fingerprint`.
- **impact**: Review-2 or future auditors may follow the wrong instructions and use a worktree or `base..HEAD` fingerprint instead of the committed-state fingerprint required by `AGENTS.md` and `workflows/templates/feature-loop.yaml`. This undermines the evidence-integrity gate for a stage where the controller and implementer share provider identity.
- **recommendation**: Rewrite the "Evidence integrity note" in `20-implementation.md` to state the correct committed-state fingerprint formula (`head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")`), cite the exact reproduce command from `status.json.diff_fingerprint_note` / `70-handoff.md`, and remove all references to "HEAD == base", "working-tree", and "untracked new files".

## Historical Grok Dispatch Failure

Prior to this Kimi review-1, the controller attempted to dispatch Grok Build (`grok-build`) for review-1. The attempt failed with `model_unavailable`: the adapter preflight passed (`grok models` showed `grok-build` as default and the user was logged in), `scripts/validate-stage.py --phase pre-review` passed, but the dispatched `grok` process hung with 0 bytes of captured output beyond the 900-second timeout and no schema-valid verdict. Per `docs/model-adapters.md` and `agents/registry.yaml`, Grok is not a default Harness review gate; after user approval the stage was re-routed to the Kimi/Claude-GLM cross-review pool. The original timeout record is preserved in `status.json.review_1.prior_dispatch_failures` and the empty captured output is in `reports/agent-runs/2026-07-public-market-contract-v2/review-1-grok-timeout.raw-output.txt`.

## Fix Start Prompt

You are the fix implementer for `stage_id=2026-07-public-market-contract-v2`. The reviewed `diff_fingerprint` is `1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d`.

Read the review file `reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md` and the raw artifacts listed in its verdict JSON.

### Required fix

- In `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`, correct the "Evidence integrity note" so it no longer states that the changes are uncommitted, that `HEAD == base`, that the literal `git diff --binary <base>..HEAD` is empty, or that the fingerprint is computed over the working tree including untracked new files.
- Replace that text with the accurate committed-state description: `base_sha=2bb47ad13065827ed1ee91d5d0e231cd312fdc0a`, `head_sha=1943e8b55c1cfdba018e8eae07428861e444e016`, `commit_state=committed`, and the standard Harness fingerprint formula:
  ```text
  diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json")
  ```
- Include the exact reproduce command from `status.json.diff_fingerprint_note` / `70-handoff.md`:
  ```text
  git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256
  ```

### Allowed file boundaries

- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`

### Forbidden paths and side effects

- Do not modify `docs/api/public-market-contract.md`, `schemas/api/public-market/snapshot.schema.json`, raw samples, `normalized/public-market-snapshot.json`, `api-field-matrix.md`, `api-sample-index.md`, `60-test-output.txt`, `status.json`, or `70-handoff.md`.
- Do not create backend implementation modules, order/borrow/repay/transfer/websocket code, or frontend code.
- Do not change the contract shape or schema.

### Verification commands

Run after the edit and before writing the fix report:

```bash
# Confirm the reviewed diff still matches the recorded fingerprint before the fix commit.
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256

# Stage validation must still pass.
python3 scripts/validate-stage.py 2026-07-public-market-contract-v2 --phase pre-review
```

### Expected 40-fix-report.md mapping

Map finding P1 to the single edit in `20-implementation.md` that removes the stale worktree-fingerprint language and replaces it with the committed-state formula and reproduce command. The controller will recompute `diff_fingerprint` and update `status.json`/`70-handoff.md` after the fix is committed.

{"schema_version": 1, "stage_id": "2026-07-public-market-contract-v2", "role": "first_reviewer", "model": "kimi-2.7", "verdict": "REWORK", "diff_fingerprint": "1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d", "reviewed_artifacts": ["AGENTS.md", "workflows/templates/feature-loop.yaml", "agents/registry.yaml", "docs/model-adapters.md", "reports/agent-runs/README.md", "schemas/review-verdict.schema.json", "agents/skills/code-reviewer.md", "reports/agent-runs/2026-07-public-market-contract-v2/status.json", "reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md", "reports/agent-runs/2026-07-public-market-contract-v2/00-task.md", "reports/agent-runs/2026-07-public-market-contract-v2/10-design.md", "reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md", "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md", "reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md", "reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt", "docs/api/public-market-contract.md", "schemas/api/public-market/snapshot.schema.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-exchangeInfo.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-premiumIndex.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/fapi-v1-fundingRate-BTCUSDT-limit10.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-curated-BTCETHXVG.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/api-v3-exchangeInfo-full-summary.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-allPairs-nokey.json", "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/sapi-v1-margin-isolated-allPairs-nokey.json"], "findings": [{"severity": "P1", "title": "20-implementation.md contains stale worktree-fingerprint semantics that contradict the committed-state diff protocol", "file": "reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md", "line": 49, "evidence": "Lines 49-52 state: 'Changes are uncommitted (HEAD == base), so the literal git diff --binary <base>..HEAD is empty; the recorded value in status.json is sha256 over the full working-tree state versus base including untracked new files, excluding status.json itself (self-referential).' This is factually incorrect: status.json records commit_state='committed', base_sha='2bb47ad13065827ed1ee91d5d0e231cd312fdc0a', head_sha='1943e8b55c1cfdba018e8eae07428861e444e016', and the standard committed-state diff produces a non-empty diff whose sha256 is e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d, matching the recorded diff_fingerprint.", "impact": "Review-2 or future auditors may follow the wrong instructions and use a worktree or base..HEAD fingerprint instead of the committed-state fingerprint required by AGENTS.md and workflows/templates/feature-loop.yaml. This undermines the evidence-integrity gate for a stage where the controller and implementer share provider identity.", "recommendation": "Rewrite the 'Evidence integrity note' in 20-implementation.md to state the correct committed-state fingerprint formula (head_sha + ':' + sha256(git diff --binary <base_sha>..<head_sha> -- . ':(exclude)reports/agent-runs/<stage-id>/status.json')), cite the exact reproduce command from status.json.diff_fingerprint_note / 70-handoff.md, and remove all references to 'HEAD == base', 'working-tree', and 'untracked new files'."}], "required_fixes": ["Correct the fingerprint evidence note in 20-implementation.md to match the committed-state diff_fingerprint formula recorded in status.json and remove stale worktree/HEAD semantics."], "next_action": "fix", "fix_start_prompt": "You are the fix implementer for stage_id=2026-07-public-market-contract-v2. The reviewed diff_fingerprint is 1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d.\n\nRead the review file reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md and the raw artifacts listed in its verdict JSON.\n\nRequired fix:\n- In reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md, correct the 'Evidence integrity note' so it no longer states that the changes are uncommitted, that HEAD == base, that the literal git diff --binary <base>..HEAD is empty, or that the fingerprint is computed over the working tree including untracked new files.\n- Replace that text with the accurate committed-state description: base_sha=2bb47ad13065827ed1ee91d5d0e231cd312fdc0a, head_sha=1943e8b55c1cfdba018e8eae07428861e444e016, commit_state=committed, and the standard Harness fingerprint formula:\n  diff_fingerprint = head_sha + \":\" + sha256(git diff --binary <base_sha>..<head_sha> -- . \":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json\")\n- Include the exact reproduce command from status.json.diff_fingerprint_note / 70-handoff.md:\n  git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . \":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json\" | shasum -a 256\n\nAllowed file boundaries:\n- reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md\n\nForbidden paths and side effects:\n- Do not modify docs/api/public-market-contract.md, schemas/api/public-market/snapshot.schema.json, raw samples, normalized/public-market-snapshot.json, api-field-matrix.md, api-sample-index.md, 60-test-output.txt, status.json, or 70-handoff.md.\n- Do not create backend implementation modules, order/borrow/repay/transfer/websocket code, or frontend code.\n- Do not change the contract shape or schema.\n\nVerification commands:\nRun after the edit and before writing the fix report:\n  git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . \":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json\" | shasum -a 256\n  python3 scripts/validate-stage.py 2026-07-public-market-contract-v2 --phase pre-review\n\nExpected 40-fix-report.md mapping:\nMap finding P1 to the single edit in 20-implementation.md that removes the stale worktree-fingerprint language and replaces it with the committed-state formula and reproduce command. The controller will recompute diff_fingerprint and update status.json/70-handoff.md after the fix is committed."}
