# Dispatch Receipt — review-2 (Claude Fable5, strong-reviewer fallback)

- **Use only after** `review-2-codex-unavailable.md` records a runner-level Codex
  failure. Do not use Claude for a second opinion after a valid Codex verdict.
- Reviewer: Claude Fable5 (`claude-fable-5`, `anthropic`); Opus4.8 if Fable5
  quota exhausted. Strong-reviewer with design-involvement disclosure
  (`reviewer_prior_involvement: "design"`). Provider isolation from the
  implementers/fix-authors (Kimi=moonshot, Claude-GLM=zhipu_glm) still holds.
- Prompt: `reports/agent-runs/2026-07-hedge-open-live-v1/review-2-claude.prompt.md`
- Executor: **human operator only**. Read-only.
- Range: `6639b0025682f406f9a726104ef8d3b9e6f8fadd..bd01eb52e9ec5464bb9f026f5ce666bc883db441`
- Command (fresh Claude terminal, `/clear` if reused):
```
claude --model claude-fable-5 -p "$(cat reports/agent-runs/2026-07-hedge-open-live-v1/review-2-claude.prompt.md)"
```
- Return raw output; bookkeeper archives to `50-review-2.md`, validates the JSON
  verdict + disclosure fields.

## Status
- `next_dispatch_executor: human_operator`; verdict pending.
