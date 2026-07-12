# Handoff — 2026-07-auto-review-pipeline-v1

## Current State

- Status: `implementing` — implementation packet bound, awaiting human dispatch.
- Branch: `stage/2026-07-auto-review-pipeline-v1`.
- Current pre-slimming delivery head: `a057d06`.
- Current recorded fingerprint:
  `a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e`.
- Auto mode remains disabled for this bootstrap stage.
- Historical rework ledger remains 3/3. This operator-authorized amendment is
  not rework 4.
- Worktree contained no unrelated tracked changes before archival/slimming.

## Startup Read Budget

Read only:

1. `AGENTS.md`;
2. `workflows/templates/stage-delivery.yaml`;
3. root `status.json` and this handoff;
4. the four files under `status.json.current_inputs`.

Do not recursively read `history/` or old stage reports. History is cold audit
storage. Open one raw file only when an explicit finding/review/audit reference
requires it.

## Operator-Approved Target

Auto-review v1 is being reduced to a serial-only middle-loop pipeline:

- remove unimplemented auto parallel worktrees/tip/integration behavior;
- remove redundant authorization fields;
- remove total runner-session wall clock;
- use registry per-adapter and per-command timeouts;
- preserve call/rework/auto-change caps, expiry, locking, resume, receipts,
  fingerprint, seal, provider isolation, human review-2, and merge gate;
- add cold-history/startup-context rules;
- fix duplicate-test and stale-lock-docstring P3 items.

Authority and design:

- `54-p8-wall-clock-withdrawal-operator-decision.md`
- `16-serial-v1-slimming-design.md`
- `12-serial-v1-slimming-development-breakdown-codex.md`

## Roles

- Bookkeeper/designer/breakdown: Codex/OpenAI.
- Implementer: Claude-GLM / GLM-5.2.
- Review-1: fresh read-only Kimi.
- Review-2: Opus 4.8, reserved with no involvement in this amendment.
- Dispatch executor: human operator only.

Codex authored the prior round-3 REWORK and now acts as bookkeeper/designer by
operator assignment. It must not implement/fix code or declare final acceptance.

## History Slimming

- 67 historical root artifacts moved verbatim to `history/raw/`.
- Former paths are compatibility symlinks.
- Full pre-slimming status/handoff saved under `history/snapshots/`.
- Active root contains only current design/task/evidence/state files.
- Deleted safe local caches: `.mypy_cache`, `.pytest_cache`, `.ruff_cache`,
  project `__pycache__`, and `.DS_Store` outside `.venv`.
- `.venv`, `.env`, ignored business/sample files, and old raw evidence were not
  deleted.

## Baseline Verification

- Full suite before new implementation: 161 tests, OK.
- Checkpoint validator before archival: PASS.
- P8 decision/design evidence commits: `2c1ba02`, `54ce1c8`.
- Current archive/slimming checkpoint must be validated and committed before
  human implementation dispatch.

## Next Action

Human operator executes:

```bash
claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-serial-v1-slimming-claude-glm.prompt.md)"
```

Claude-GLM returns code/docs/test changes plus append-only `20-implementation.md`
and `60-test-output.txt`. Codex then verifies boundaries, tests, residue scans,
and commits evidence before preparing Kimi review-1.

本地北京时间: 2026-07-12 10:59:45 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched implementation）
下一步任务: 执行 task-serial-v1-slimming-claude-glm.prompt.md；不得读取非必要 history
