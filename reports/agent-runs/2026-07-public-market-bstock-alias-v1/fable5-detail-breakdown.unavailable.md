# Fable5 Development Breakdown — UNAVAILABLE (runner-level check failed)

Stage: `2026-07-public-market-bstock-alias-v1`
Recorded: 2026-07-03 23:19 CST

## Runner-level availability check

The approved plan called for Claude/Fable5 (`claude-fable-5`, provider
`anthropic`) to author `fable5-detail-breakdown.md` as this stage's
design-involvement-of-record (MEDIUM default breakdown author per AGENTS.md).

Probe command:

```bash
claude --model claude-fable-5 -p "reply with just: OK"
```

Result:

```text
⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth
  source is set and takes precedence over your claude.ai login · Unset it to
  load your organization's connectors
API Error: 400 [1211][模型不存在，请检查模型代码。][2026070323193202005e174cf644f8]
```

Interpretation: the local `claude` CLI (Claude Code 2.1.199, `/Users/ark/.local/bin/claude`)
has its ANTHROPIC auth source pointed at the `zhipu_glm` provider, so
`--model claude-fable-5` routes to GLM, which has no such model (error 1211
"模型不存在"). The claude.ai login that would reach Anthropic Fable5 is
overridden by the configured auth source. Fable5 is therefore NOT reachable in
this controller session.

## Fallback (per approved plan §"Development breakdown [可调整]")

The approved plan explicitly allows a controller-direct `10-design.md` as a
user-approved lightweight shortcut when Fable5 is unavailable. This stage
therefore records design via controller-authored `00-task.md` + `10-design.md` +
`11-adr.md`, and sets `complexity.user_approved_lightweight_route = true`.
Review-1 and review-2 independent gates still run unchanged.

## Effect on review-2 disclosure

This stage's designer/breakdown author is the controller (`claude_glm`), which
is also the Task A implementer (hard-banned from review-2 by
`final_reviewer_not_code_author`). Fable5 has NO involvement this stage.
Review-2 therefore has a single prior-involvement source: Codex/GPT as prior
direction synthesizer (`approved_prior_stage`, covering contract-v2). Codex
reviews via the `direction_synthesis` strong-reviewer override; no separate
design/breakdown disclosure is needed because the designer is an implementer
(not a distinct decision model), not Fable5.

本地北京时间: 2026-07-03 23:19:31 CST
下一步模型: Claude-GLM (controller)
下一步任务: Proceed controller-direct design (00-task.md / 10-design.md / 11-adr.md); Fable5 breakdown re-runnable if an Anthropic-authed environment is provided.
