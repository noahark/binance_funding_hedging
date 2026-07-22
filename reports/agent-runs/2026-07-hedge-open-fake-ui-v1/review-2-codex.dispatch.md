# Dispatch Receipt — review-2 (Codex/GPT, preferred)

- Stage: `2026-07-hedge-open-fake-ui-v1`, role `final_reviewer`.
- Preferred reviewer: Codex/GPT (`openai`), unrelated to all stage roles
  (no design/breakdown/implementation involvement), cross-provider isolated
  from implementer Kimi (`moonshot`). This is the correct first choice.
- Prompt: `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-codex.prompt.md`
- Executor: **human operator only**. Read-only.
- Review range: `46ea46f6caacf78dca4ef5345f60518c77d6e378..f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`

## Step 1 — runner-level availability check (required before any fallback)
Run Codex first. Per docs/model-adapters.md, schema-bound Harness review uses
read-only `codex exec` with the prompt:

```
codex exec "$(cat reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-codex.prompt.md)"
```

- If Codex runs and returns a review, return its full raw output to the
  bookkeeper for archival to `50-review-2.md`.
- If Codex fails at runner level (quota exhausted, auth, service, timeout,
  repeated invalid JSON), copy that raw failure output back so the bookkeeper
  can record it in `review-2-codex-unavailable.md`. Only after that evidence is
  recorded may review-2 fall back to Claude Fable5
  (`review-2-claude.prompt.md`). A model session lacking a tool is NOT
  sufficient — the adapter command itself must fail.

## Status
- `next_dispatch_executor: human_operator`
- prepared_at: 2026-07-22 21:11 CST
- verdict: pending (bookkeeper fills from the raw review artifact).
