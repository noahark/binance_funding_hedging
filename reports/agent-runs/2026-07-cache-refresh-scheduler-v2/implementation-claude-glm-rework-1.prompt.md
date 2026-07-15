# Claude-GLM Implementation Correction 1

You are continuing the implementation of stage
`2026-07-cache-refresh-scheduler-v2` as the existing backend implementer
(`claude_glm`, provider identity `zhipu_glm`). This is a pre-commit correction,
not review-1 and not a new product-design round.

## Read First

Read, in this order:

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/00-task.md`
4. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/10-design.md`
5. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/11-adr.md`
6. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/12-development-breakdown.md`
7. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`
8. `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/60-test-output.txt`
9. the current uncommitted diff in the allowed files below.

Do not read another stage or any `history/` directory. Do not start Kimi or any
other model. Do not commit, merge, rebase, push, run a server, use network
access, or call Binance.

## Current State

- Branch: `stage/2026-07-cache-refresh-scheduler-v2`
- Committed HEAD before the implementation worktree: `52b84f48fcf3b5066cc771c83c6536bb3dcb5cf5`
- Frozen review task base remains:
  `4c9d43800bd0d6d908892afa46c8b08e00b88877`
- The existing uncommitted implementation has independently passed
  `python3 -m pytest backend/tests -q` with `325 passed`.
- The bookkeeper found two frozen-contract defects before any implementation
  commit or review dispatch. Fix only these defects and their regression tests.

## Finding 1 — CC-3 exit/re-entry ledger is not implemented

Evidence:

- `backend/services/snapshot_service.py` only calls
  `self._coverage_attempted.add(base)`.
- No code removes assets that leave the current homepage borrow universe.
- `_gather_private_inputs_scheduled()` filters counts against the current
  universe but leaves the ledger itself unchanged.
- Reproduction already recorded in `60-test-output.txt`: after `BTC` leaves the
  universe, `_coverage_attempted` still contains `BTC`; when it re-enters before
  a new max-borrowable attempt, coverage incorrectly reports `probed=1`.

Required behavior from `12-development-breakdown.md` CC-3 / INV-4:

- an actual scheduled max-borrowable attempt, including failure, adds the asset;
- leaving the current universe removes it from the ledger;
- re-entry begins unattempted;
- merely crossing the cursor with a still-fresh max-borrowable component does
  not count as a new attempt;
- `reason == "rate_limit_budget"` exactly when current-universe `skipped > 0`.

Add a deterministic entry/exit/re-entry test that fails on the current code.
Test the actual ledger and externally assembled coverage, not only a helper
predicate.

## Finding 2 — FR-2/INV-5 business/transport timestamp skew permits false refresh

Evidence:

- `_scheduled_tick()` captures `now = time.monotonic()` before network work.
- `_refresh_due_sources(now)`, `_refresh_borrow_rates(..., now)`, and
  `_refresh_max_borrowable(..., now)` store that pre-call value as the business
  success timestamp.
- `PrivateClient._cached_get()` captures its transport timestamp after the
  service's pre-call timestamp. Therefore a real transport entry can expire
  slightly later than the corresponding business entry.
- At business age `1800.0`, a still-valid transport entry with expiry `1800.1`
  was reproduced: `signed_get_calls=0`, yet the business timestamp advanced to
  `1800.0`. That can suppress real upstream I/O for another full business
  cycle.

Required behavior from `10-design.md` lines 51-62 and
`12-development-breakdown.md` FR-2 / INV-5:

- the transport entry must be timestamped no later than the corresponding
  successful business-cache update;
- a business timestamp is written only after the source returns successfully;
- at business age `>=1800s`, the slow private transport entry is also expired,
  so the scheduled call performs real upstream I/O;
- failure/`None` must not advance the successful business timestamp.

Use completion-time business timestamps for successful slow-private source and
component updates. Do not use `force=True` or evict transport keys to bypass the
contract. Preserve independent per-source and per-asset timestamps. Add a
deterministic test that includes non-zero ordering/skew between the transport
cache timestamp and the business success timestamp; the existing isolated
transport test where both clocks begin at exactly `0.0` is insufficient by
itself.

Apply the same completion-time discipline wherever the current implementation
stores a successful business-cache timestamp from the single pre-fetch tick
value, if needed to keep FR-2 internally consistent. Do not redesign the
scheduler.

## Allowed Writes

You may edit only:

- `backend/services/snapshot_service.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_private_client.py`
- `reports/agent-runs/2026-07-cache-refresh-scheduler-v2/20-implementation.md`

Do not edit the other four already-modified frozen files unless you stop and
explain why a finding cannot be fixed without them. In particular, do not edit:

- `backend/domain/snapshot.py`
- `backend/config.py`
- `backend/adapters/binance_public.py`
- frontend, schemas, canonical `docs/`, workflow/Harness files, `status.json`,
  `70-handoff.md`, `60-test-output.txt`, or review/fix reports.

The failure/error-presentation behavior explicitly deferred by the design is
not part of this correction. Do not broaden into it.

## Verification

Run exactly:

```bash
python3 -m pytest backend/tests/test_background_worker.py backend/tests/test_private_client.py -q
python3 -m pytest backend/tests -q
python3 -m py_compile backend/config.py backend/adapters/binance_public.py backend/services/private_client.py backend/services/snapshot_service.py
git diff --check
git status --short
```

Update `20-implementation.md` by appending a clearly labeled
`Implementation Correction 1` section that maps each finding to code, tests,
and exact results. Correct the earlier claim that CC-3 exit/re-entry was already
implemented; preserve the old report text as historical evidence and append the
correction instead of silently rewriting it.

Return control to the human/bookkeeper after verification. Do not commit and do
not dispatch review.

本地北京时间: 2026-07-15 00:42:46 CST
下一步模型: human → bookkeeper
下一步任务: 检查两项提交前修复、复跑测试并决定是否生成 review-1 提示
