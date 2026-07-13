# Human Dispatch — Formal Review-2

Target: a fresh Codex terminal/session using `gpt-5.6-sol` in read-only mode.
This bookkeeper session must not execute the dispatch.

From the repository root, the human operator runs the schema-bound adapter form
documented in `docs/model-adapters.md`:

```bash
codex exec -C '/Users/ark/Desktop/ai code/funding_hedging' \
  -m gpt-5.6-sol \
  -s read-only \
  --output-schema schemas/review-verdict.schema.json \
  - < reports/agent-runs/2026-07-local-service-launchd-v1/manual-review-2-T1-launchd-service.prompt.md
```

Dispatch rules:

1. Use a fresh session; do not continue this bookkeeper transcript.
2. Do not change the model, sandbox, schema, prompt, range, or fingerprint.
3. Do not approve any request to mutate files or invoke real `launchctl`.
4. Return the complete raw stdout and any sanitized failure output to the
   bookkeeper. Do not hand-edit the verdict JSON.
5. If the command fails for quota, authentication, service availability, or
   timeout, preserve that exact sanitized evidence. Do not silently switch to
   Claude; the bookkeeper applies fallback routing.

本地北京时间: 2026-07-13 21:36:31 CST
下一步模型: Codex / gpt-5.6-sol（fresh human-started review session）
下一步任务: 执行 schema-bound、read-only review-2，并返回完整原始输出
