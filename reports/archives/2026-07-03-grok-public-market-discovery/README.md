# Grok Public Market Discovery Archive

Date: 2026-07-03

This archive preserves the abandoned Grok implementation and follow-up fixes for
the public-market discovery stage. The archived material is evidence only. It is
not an active implementation base for the next stage.

## Contents

- Committed Grok implementation reference: `c53664e` (`git show c53664e`).
  The full patch is intentionally not duplicated in this archive because it is
  already present in git history and contains large raw sample files.
- `uncommitted-tracked-fixes.patch`: tracked worktree changes from the later
  Grok fix rounds before cleanup.
- `untracked-files.txt`: untracked files present before cleanup.
- `untracked/`: copies of those untracked files.
- `git-status-before-cleanup.txt`: status snapshot before cleanup.
- `git-log-before-cleanup.txt`: recent commit snapshot before cleanup.

## Reason

The implementation exposed repeated reliability issues:

- Real Binance samples were not used consistently for core route classification.
- Tokenized equity perpetuals using `TRADIFI_PERPETUAL` were mishandled.
- Non-`TRADING` futures polluted the candidate table.
- The fake UI drifted from the agreed Chinese workstation style.
- Grok CLI child processes repeatedly stalled during fix rounds.

The next active phase restarts from the approved PRD and direction documents with
a contract-first split:

- Claude-GLM owns backend API contract discovery and backend implementation.
- Kimi owns frontend UI and integration against the frozen backend contract.
- Grok is excluded from core backend and contract work for this project phase.
