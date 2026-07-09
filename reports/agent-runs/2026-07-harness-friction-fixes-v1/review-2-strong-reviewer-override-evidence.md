# Review-2 Strong-Reviewer Override Evidence

Stage: `2026-07-harness-friction-fixes-v1`

## Reason

No decision-model provider is unrelated to the stage design set:

| Provider | Stage involvement | Review-2 implication |
|---|---|---|
| `openai` / Codex-GPT | Designer and bookkeeper | Eligible only with `reviewer_prior_involvement=design` disclosure |
| `anthropic` / Claude | Development breakdown author (`12-development-breakdown.md`) | Also design-set involvement (`breakdown`) |
| `zhipu_glm` / Claude-GLM | Implementer and fix author | Hard-banned from review-2 |
| `moonshot_kimi` / Kimi | Review-1 reviewer | Not the configured final decision model |

The user selected Claude/Anthropic for final review. This is allowed through
the strong-reviewer disclosure override because Claude has no implementation or
fix authorship and can run as a fresh read-only review session. The final
reviewer must treat raw artifacts, `AGENTS.md`, workflow YAML, and the
user-approved stage task as authority over any prior breakdown notes.

## Required Status Fields

- `review_2.reviewer`: `claude`
- `review_2.provider`: `claude`
- `review_2.model`: `claude-fable-5`
- `review_2.actual_model`: actual executed Claude model, filled after dispatch
- `review_2.reviewer_prior_involvement`: `breakdown`
- `review_2.fallback_reason`: user-selected Claude final reviewer under
  strong-reviewer disclosure override because no unrelated decision-model
  provider exists for this stage
- `review_2.design_conflict_override.used`: `true`

本地北京时间: 2026-07-09 20:39:01 CST
下一步模型: claude
下一步任务: execute `reports/agent-runs/2026-07-harness-friction-fixes-v1/review-2-claude.prompt.md`
