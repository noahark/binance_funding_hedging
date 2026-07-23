# Dispatch Receipt — hedge-fe (Kimi)

- Task id: `hedge-fe` (frontend). Owner: Kimi (`moonshot_kimi`,
  `kimi-code/kimi-for-coding`).
- Prompt: `reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-fe-kimi.prompt.md`
- Executor: **human operator only**. Bookkeeper does not launch it.
- Branch: `stage/2026-07-hedge-open-live-v1`.
- Allowed files: `frontend/index.html`, `frontend/self-check.js`.
- Consumes only the frozen §3 API contract (runs concurrently with hedge-be;
  self-check mocks the §3 API same-origin).
- Self-test: `node frontend/self-check.js` (no real network).
- Adapter command (human operator, fresh Kimi terminal, repo root):

```
kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-fe-kimi.prompt.md)"
```

- Stop-for-bookkeeper: writes `20-implementation-hedge-fe.md` + appends
  `60-test-output.txt`, then stops. No commit, no status.json edit, no relay.
- review-1: Claude-GLM (cross-provider).

## Status
- `next_dispatch_executor: human_operator`; prepared_at: 2026-07-22 23:40 CST.
- Parallel with hedge-be; bookkeeper does R4 diff reconciliation before H_A/H_B
  evidence commits.
