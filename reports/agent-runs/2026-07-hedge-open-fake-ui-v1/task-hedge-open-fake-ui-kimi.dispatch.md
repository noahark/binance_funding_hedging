# Dispatch Receipt — hedge-open-fake-ui (Kimi)

- Task id: `OPEN-FAKE-UI`
- Implementer: Kimi (`moonshot_kimi`, `kimi-code/kimi-for-coding`), front-end domain.
- Prompt: `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/task-hedge-open-fake-ui-kimi.prompt.md`
- Executor: **human operator only**. The bookkeeper prepared this packet and
  does NOT launch Kimi. All cross-model dispatch is human-executed.
- Adapter command (human operator runs in a fresh Kimi terminal at repo root):

```
kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-hedge-open-fake-ui-v1/task-hedge-open-fake-ui-kimi.prompt.md)"
```

- Branch to run on: `stage/2026-07-hedge-open-fake-ui-v1` (already created from
  main `e6b836831391da8b98101d9c6a85353e9fa8273e`).
- Allowed files: `frontend/index.html`, `frontend/self-check.js` only.
- Self-test: `node frontend/self-check.js` (all existing + new `[PASS]`, exit 0).
- Stop-for-bookkeeper: Kimi writes `20-implementation.md` + `60-test-output.txt`
  and stops; no commit, no status.json edit, no relay.

## Status
- `next_dispatch_executor: human_operator`
- prepared_at: 2026-07-22 18:51 CST
- receipt to be completed by the human operator after the run (session id,
  verdict/result, recorded_at).
