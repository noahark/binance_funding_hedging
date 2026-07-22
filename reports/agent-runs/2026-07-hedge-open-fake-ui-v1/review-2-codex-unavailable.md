# Review-2 Preferred Reviewer (Codex/GPT) — Runner-Level Unavailability Evidence

This file records the runner-level availability check that gates the
strong-reviewer fallback to Claude (AGENTS.md: the fallback is allowed only
after the unrelated decision model fails a runner-level check for quota, auth,
service, timeout, or repeated invalid verdict output; the failure evidence path
must be recorded).

- Stage: `2026-07-hedge-open-fake-ui-v1`
- Preferred review-2 reviewer: Codex/GPT (`openai`)
- Checked by: human operator (dispatch only)

## Status: PENDING OPERATOR EVIDENCE

The bookkeeper cannot execute the adapter check. Before review-2 may fall back
to Claude Fable5, the human operator must run the Codex adapter and paste the
raw failure output here. A model session simply lacking a Codex tool is NOT
sufficient — the `codex exec` adapter command itself must fail.

### Command run
```
codex exec "$(cat reports/agent-runs/2026-07-hedge-open-fake-ui-v1/review-2-codex.prompt.md)"
```

### Raw failure output (paste verbatim)
```
<operator: paste the exact Codex quota/auth/service failure output here>
```

- Failure class: <quota | auth | service | timeout | repeated_invalid_json>
- Local time: <YYYY-MM-DD HH:MM:SS CST>

Once this evidence is filled in and returned, the bookkeeper records it and
authorizes dispatch of `review-2-claude.prompt.md`.
