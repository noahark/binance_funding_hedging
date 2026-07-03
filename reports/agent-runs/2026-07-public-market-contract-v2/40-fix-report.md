# Fix Report: Public Market Contract V2

Timestamp: 2026-07-03T07:35:57Z

## Source Review

- Review file: `reports/agent-runs/2026-07-public-market-contract-v2/30-review-1.md`
- Reviewer: Kimi (`kimi-2.7`)
- Verdict: `REWORK`
- Reviewed fingerprint:
  `1943e8b55c1cfdba018e8eae07428861e444e016:e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d`

## Finding-To-Fix Mapping

| Finding | Fix |
|---|---|
| P1: `20-implementation.md` contained stale worktree-fingerprint semantics. | Replaced the obsolete `HEAD == base`, working-tree hash, and untracked-files language with the committed-state `base_sha..<head_sha>` formula and references to the exact reproduce command in `status.json` / `70-handoff.md`. |

## Files Changed

- `reports/agent-runs/2026-07-public-market-contract-v2/20-implementation.md`

## Verification

```text
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..1943e8b55c1cfdba018e8eae07428861e444e016 -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256
```

Expected hash from the original reviewed subject:

```text
e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d
```

Actual output:

```text
e0ae8c5cc404b0b0ebe45c8f637b6c30689337572a7248e9816181e34301311d  -
```

Controller will update `status.json` and `70-handoff.md` after the fix commit
with the new committed subject fingerprint for re-review.
