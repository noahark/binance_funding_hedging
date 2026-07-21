# Fable5 Runner Availability Evidence — Review-2

## Classification

- Stage: `2026-07-harness-verdict-extractor-fix-v1`
- Review gate: `review-2`
- Preferred model attempted: `claude-fable-5`
- Provider identity: `anthropic`
- Failure class: `quota_exhausted`
- Routed fallback: `opus4.8` under the same Anthropic provider identity
- Dispatch executor: `human_operator`

## Human-Operator Evidence

The human operator reported verbatim in the controlling conversation:

> fable5 额度不足，我让 opus4.8 执行的。

This is recorded as the runner-level availability result that authorized the
configured Fable5-to-Opus4.8 quota fallback. The bookkeeper did not execute
either model.

The raw Fable5 CLI error text and a Fable5 transcript were not preserved in the
repository and are therefore unavailable; no exact error wording, command,
timestamp, Session ID, or endpoint response is invented. The successful
fallback transcript independently records actual model metadata
`claude-opus-4-8`, repository cwd, `/clear`, the immutable Task H prompt, and
the final review output. No Claude-GLM/Zhipu model metadata appears in that
fallback review transcript.

This evidence authorizes only the configured same-provider model fallback for
this review attempt. It does not authorize a second opinion, provider change,
merge, deployment, Boundary C synchronization, or product acceptance.

当前 Session ID: unavailable (Fable5 attempt produced no preserved transcript or verified provider-native Session ID)
Session ID 来源: operator
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/review-2-fable5.unavailable.md
本地北京时间: 2026-07-21 20:08:12 CST
下一步模型: bookkeeper
下一步任务: bind this quota-exhaustion evidence to the Opus4.8 final-review receipt and validate the ACCEPT gate
