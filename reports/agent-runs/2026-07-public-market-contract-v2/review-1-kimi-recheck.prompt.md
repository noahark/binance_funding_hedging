# Review-1 Recheck on Clean Contract-Stage Subject

You are Kimi (`kimi-2.7`), acting as `reviewer_1` with the `code_reviewer`
skill, in read-only / plan mode. Stage:
`2026-07-public-market-contract-v2` (Binance public market contract discovery,
Phase 1, public data only).

## Why this recheck exists

You previously accepted this stage's contract discovery on the review subject
range `2bb47ad..d73eb10`. A later review-2 (Codex, final reviewer) found that
that range bound unrelated Harness governance files (e.g. `AGENTS.md`,
`agents/registry.yaml`, `docs/model-adapters.md`, `scripts/validate-stage.py`,
workflow renames, `.harness-version`) into the contract review subject, even
though `20-implementation.md` / `status.changed_files` claimed a narrower set.

The evidence boundary has now been repaired: the review subject is redefined by
a **clean committed base** whose standard Harness diff contains only the
contract-stage paths allowed by `00-task.md`. **No Binance contract semantics
were changed by this repair** — the contract artifacts themselves are
unchanged; only the review subject's file scope was narrowed and the
implementation/handoff evidence files were updated to describe the clean
boundary.

Your job: confirm that the **clean** subject still passes review-1, and that
your verdict `diff_fingerprint` matches the clean subject. This is a
read-only recheck. Do not modify any files.

## The clean review subject (recompute this yourself — do not trust this summary)

base_sha: `2e6b5a0eaa0cd4dbbc94cc2bab9b142a7aaa3130`
head_sha: `a25e4316019197fd3e09bd6827b8aa7c4e2ce36f`

The base is a normal committed tree built from the head tree by reverting
contract-stage paths to the `2bb47ad` review-base state and leaving
out-of-scope Harness paths at the head version, so they cancel out of
`diff base..head`. This is the standard fingerprint protocol (no second
protocol, no worktree fingerprint).

Recompute the fingerprint yourself from a clean shell in the repository root:

```bash
git diff --binary 2e6b5a0eaa0cd4dbbc94cc2bab9b142a7aaa3130..a25e4316019197fd3e09bd6827b8aa7c4e2ce36f -- . ':(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json' | shasum -a 256
```

The expected `diff_fingerprint` value recorded in `status.json` is:

```text
a25e4316019197fd3e09bd6827b8aa7c4e2ce36f:53484d21b25373e524ae6abfd8c05883b4cd2c471ccc45f0e98aef51691b41bf
```

Recompute it. If your recomputed value differs, treat that as a P0/P1 finding
and return REWORK.

Also confirm the clean diff contains only contract-stage paths allowed by
`00-task.md`:

```bash
git diff --binary 2e6b5a0eaa0cd4dbbc94cc2bab9b142a7aaa3130..a25e4316019197fd3e09bd6827b8aa7c4e2ce36f --name-only -- . ':(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json'
```

It must list only contract-stage paths (the `docs/api/public-market-contract.md`,
`reports/agent-runs/2026-07-public-market-contract-v2/**`, and
`reports/api-samples/public-market-contract-v2/**` families). If any Harness
governance file remains in the list, return REWORK with a P1 finding.

## Raw artifacts to inspect directly (do not rely on controller summaries)

Read these files yourself:

- `reports/agent-runs/2026-07-public-market-contract-v2/00-task.md` (allowed file boundaries)
- `reports/agent-runs/2026-07-public-market-contract-v2/10-design.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/11-adr.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md` (your prior ACCEPT)
- `reports/agent-runs/2026-07-public-market-contract-v2/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/50-review-2.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/60-test-output.txt`
- `reports/agent-runs/2026-07-public-market-contract-v2/70-handoff.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/status.json`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`
- `reports/agent-runs/2026-07-public-market-contract-v2/api-sample-index.md`
- `docs/api/public-market-contract.md`
- `schemas/api/public-market/snapshot.schema.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/raw/*.json`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/build-normalized-sample.py`
- `reports/api-samples/public-market-contract-v2/20260703T051738Z/normalized/public-market-snapshot.json`
- The clean frozen diff:
  `git diff --binary 2e6b5a0eaa0cd4dbbc94cc2bab9b142a7aaa3130..a25e4316019197fd3e09bd6827b8aa7c4e2ce36f -- . ':(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json'`

## What to verify

1. Recompute the clean-subject fingerprint; it must equal the value above.
2. The clean diff file list contains only `00-task.md`-allowed contract-stage
   paths; no Harness governance files remain in the review subject.
3. The contract artifacts you previously accepted are materially unchanged
   on this clean subject (field matrix, raw samples, schema, normalized
   snapshot, frozen findings). Re-validate the normalized sample against
   `schemas/api/public-market/snapshot.schema.json` if you can run Python.
4. `20-implementation.md` now correctly describes the clean committed subject
   and points reviewers to the exact reproduce command in `status.json`
   (no stale worktree-fingerprint / `HEAD == base` language).
5. The repair changed no Binance contract semantics (the schema was not
   modified; the normalized sample still validates).

If a P0 or P1 problem remains, return `REWORK` with a `fix_start_prompt`.
Otherwise return `ACCEPT`.

Carry forward known non-blocking residual risks you already accepted
(`lastFundingRate` settled-vs-estimate ambiguity; `MARGIN_SPOT_CANDIDATE`
private borrowability deferred to Phase 2; negative schema tests recorded but
not packaged as a replay script) — these do not block acceptance.

## Output contract (strict)

Your response MUST end with a single JSON verdict object that validates
against `schemas/review-verdict.schema.json`. Read that schema file. Required
fields: `schema_version` (1), `stage_id`, `role`, `model`, `verdict`,
`diff_fingerprint`, `reviewer_prior_involvement`, `reviewed_artifacts`,
`findings`, `required_fixes`, `next_action`.

For this recheck use exactly:
- `role`: `first_reviewer`
- `model`: `kimi-2.7`
- `reviewer_prior_involvement`: `none` (you did not design, synthesize, or
  break down this stage; you are only the cross-reviewer)
- `diff_fingerprint`: your recomputed clean-subject value
- `next_action`: `continue` for ACCEPT, `fix` for REWORK

If `verdict` is `REWORK`, you MUST include `fix_start_prompt` with raw paths,
ordered findings (severity, file/line, evidence, impact, recommendation),
required fixes, allowed boundaries, forbidden paths, and the exact commands to
run after the fix.

Emit the JSON verdict as the final block of your reply, fenced in ```json.
