# Dispatch Receipt — review-2 (Claude Fable5, strong-reviewer fallback)

- Stage: `2026-07-hedge-open-fake-ui-v1`, role `final_reviewer`.
- **Use only after** `review-2-codex-unavailable.md` records a runner-level
  Codex failure. Do not use Claude for a second opinion after a valid Codex
  verdict.
- Fallback reviewer: Claude Fable5 (`claude-fable-5`, `anthropic`); if Fable5
  quota is exhausted, Opus 4.8 under the same anthropic identity.
- Disclosure: designer/breakdown/bookkeeper are Claude/anthropic, so the
  reviewer has provider-level design involvement → verdict must carry
  `reviewer_prior_involvement: "design"` + notes citing this fallback and the
  evidence path. Provider isolation from the implementer Kimi (`moonshot`)
  still holds (hard requirement satisfied).
- Prompt: `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-claude.prompt.md`
- Executor: **human operator only**. Read-only.
- Review range: `46ea46f6caacf78dca4ef5345f60518c77d6e378..f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`
- Adapter command (human operator, fresh Claude terminal; `/clear` if reusing):

```
claude --model claude-fable-5 -p "$(cat reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-claude.prompt.md)"
```

- Return the full raw output to the bookkeeper for archival to `50-review-2.md`.
  The bookkeeper validates the JSON verdict, confirms the disclosure fields and
  evidence path (required by scripts/validate-stage.py), and on ACCEPT moves the
  stage to `stage_accepted_waiting_user`.

## Status
- `next_dispatch_executor: human_operator`
- prepared_at: 2026-07-22 21:11 CST
- verdict: pending.
