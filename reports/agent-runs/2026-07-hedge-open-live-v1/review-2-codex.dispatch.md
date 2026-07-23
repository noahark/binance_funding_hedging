# Dispatch Receipt — review-2 (Codex/GPT, preferred)

- Stage `2026-07-hedge-open-live-v1`, role `final_reviewer` (whole stage).
- Preferred reviewer: Codex/GPT (`openai`), unrelated to all stage roles,
  cross-provider from every implementer/reviewer. GPT quota reported restored.
- Prompt: `reports/agent-runs/2026-07-hedge-open-live-v1/review-2-codex.prompt.md`
- Executor: **human operator only**. Read-only.
- Range: `6639b0025682f406f9a726104ef8d3b9e6f8fadd..bd01eb52e9ec5464bb9f026f5ce666bc883db441`

## Step 1 — run Codex (read-only `codex exec`)
```
codex exec "$(cat reports/agent-runs/2026-07-hedge-open-live-v1/review-2-codex.prompt.md)"
```
- If Codex returns a review, return its full raw output; bookkeeper archives to
  `50-review-2.md`.
- If Codex fails at runner level (quota/auth/service/timeout/repeated invalid
  JSON), return that raw failure so the bookkeeper records
  `review-2-codex-unavailable.md`; only then fall back to Claude Fable5/Opus4.8
  (`review-2-claude.prompt.md`, strong-reviewer with design-involvement
  disclosure).

## Status
- `next_dispatch_executor: human_operator`; verdict pending.
