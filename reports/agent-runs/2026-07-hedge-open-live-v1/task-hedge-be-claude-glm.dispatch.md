# Dispatch Receipt — hedge-be (Claude-GLM)

- Task id: `hedge-be` (backend). Owner: Claude-GLM (`zhipu_glm`, `glm-5.2[1m]`).
- Prompt: `reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-be-claude-glm.prompt.md`
- Executor: **human operator only**. Bookkeeper does not launch it.
- Branch: `stage/2026-07-hedge-open-live-v1`.
- Allowed files: `backend/hedge_open_tasks/**`, `backend/app/server.py` (hedge
  routes only), `backend/tests/**`, `schemas/api/hedge-open/**`.
- Self-test: `python -m pytest backend/tests -q` (no real Binance request).
- Adapter command (human operator, repo root):

```
claude-glm -p "$(cat reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-be-claude-glm.prompt.md)"
```

- Stop-for-bookkeeper: writes `20-implementation-hedge-be.md` + appends
  `60-test-output.txt`, then stops. No commit, no status.json edit, no relay.
- review-1: Kimi (cross-provider).

## Status
- `next_dispatch_executor: human_operator`; prepared_at: 2026-07-22 23:40 CST.
- Parallel with hedge-fe; bookkeeper does R4 diff reconciliation before H_A/H_B
  evidence commits.
