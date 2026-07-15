# Session ID Capture Evidence And Harness Amendment

## Purpose

This note records the session-identification evidence used to add Session
receipt v1 to the Harness. It is navigation evidence only. It does not replace
the raw model output, committed diff, test output, or formal review verdict.

The reusable provider instructions now live in
`docs/model-adapters.md#session-id-capture-and-execution-receipts`; future agents
should read that section instead of copying IDs or commands from this stage.

## Observed Sessions

### Codex bookkeeper

- Provider/model: OpenAI Codex / GPT-5
- Session ID: `019f639a-7890-7573-a04b-7a62debff633`
- Evidence: current runtime `CODEX_THREAD_ID`, cross-checked against the matching
  local rollout filename under `~/.codex/sessions/2026/07/15/`.
- Stage role: current bookkeeper/designer reconciliation session.

### Claude development breakdown

- Provider/model: Anthropic Claude / `opus4.8`
- Session ID: `d313bb8a-6355-45b9-b546-5995bd320862`
- Evidence: operator-supplied ID, cross-checked against the exact transcript
  filename under `~/.claude/projects/<encoded-project>/`. The session also
  reported a session-specific scratchpad path carrying the same UUID.
- Raw stage artifact: `12-development-breakdown.md`.
- Note: the original model file omitted the newly requested Session footer; the
  bookkeeper preserves it unchanged and supplies this companion receipt.

### Grok advisory design review

- Provider/model: xAI Grok / `grok-build`
- Session ID: `019f6457-54f7-7fd1-aba0-842c084fdde2`
- Evidence: operator-supplied ID, current-repository active-session registry,
  and successful local `grok export` of the same ID.
- Raw stage artifact: `13-design-review-grok.raw.md`.

### Claude-GLM method research

- Provider/model: Zhipu GLM through Claude Code / `glm-5.2`
- Session ID: `b17a0cf7-e41f-487c-9fb0-f8cb4358f04c`
- Evidence: operator-supplied ID, `CLAUDE_CODE_SESSION_ID` observed by that
  session, and matching Claude Code transcript filename.
- Stage role: method evidence only; not an implementer or reviewer for the
  current product diff at this checkpoint.
- Provider rule: sharing Claude Code storage does not make Claude-GLM an
  Anthropic provider.

### Kimi method research

- Provider/model: Moonshot Kimi Code
- Session ID: `session_524527c9-7b19-44a0-a02d-b49851e478f0`
- Evidence: operator-supplied provider-native ID; matching
  `~/.kimi-code/sessions/wd_<workspace>_<hash>/session_<uuid>/state.json` with
  the repository `workDir` and current `lastPrompt`.
- Stage role: method evidence only; not yet the Task B implementer.

## Resulting Harness Rules

- Every model-facing execution footer includes Session ID, evidence source,
  raw output path, local Beijing time, next model, and next task.
- The model never guesses. Missing runtime visibility becomes
  `unavailable (reason)` and may later be filled by a verified runner receipt.
- `status.json.session_receipts` is the machine-readable navigation ledger.
- Runtime/hook evidence outranks transcript-path inference; exact path/content
  matching outranks active-registry heuristics; newest mtime alone is invalid.
- Session IDs are not credentials and do not grant cross-provider transcript
  access. Cross-model review uses stage raw artifacts.
- Strict JSON review verdicts place the navigation footer before the final JSON
  object so schema parsing remains valid.

## Files Amended

- `AGENTS.md`
- `docs/model-adapters.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/_template/status.json`
- model-facing Markdown templates under `reports/agent-runs/_template/`

This amendment is intentionally included in the current stage because the user
explicitly requested that Task A, Task B, and later reviews use it immediately.
No product runtime behavior is changed by the amendment.

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/15-session-id-capture-evidence.md
本地北京时间: 2026-07-15 17:29:32 CST
下一步模型: codex_bookkeeper
下一步任务: 将验证过的 model session receipts 写入 status.json 并准备后端实现 packet
