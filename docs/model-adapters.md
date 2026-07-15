# Model Adapters

This document records local command knowledge that the workflow YAML should not
inline. Bookkeepers, stage operators, implementation terminals, and human
operators must consult this file before declaring a model unavailable.

The registry remains the machine-readable source of routing truth:
`agents/registry.yaml`.

## General Rules

- Use prompt files for long prompts. Avoid shell-quoted multi-line prompts when
  raw artifact paths, diffs, or schemas are included.
- Set the repository working directory explicitly.
- Reviewers must run in read-only or plan mode.
- Development/fix agents may use write mode only inside the active stage scope.
- Yolo/bypass modes require explicit user or runner authorization. They are not
  default review modes.
- Codex/GPT and Claude provider sessions may prepare dispatch prompt files and
  command templates, but must not execute model-dispatch commands or invoke
  other model terminals. Human operators execute prepared dispatch packets in
  the selected model terminal and record the raw output or receipt evidence.
- A model is unavailable only after the runner-level adapter check fails. A
  bookkeeper or implementation session lacking a built-in tool for that model is
  not enough.
- For review gates, use `base_sha` and `head_sha` from `status.json`. Do not use
  the moving symbolic `HEAD` when unrelated Harness commits may have happened
  after the reviewed stage commit.

## Session ID Capture And Execution Receipts

Every completed model execution must expose the navigation footer defined in
`AGENTS.md`. The model should report its provider-native Session ID when the
runtime exposes it; the runner or human operator then verifies and records the
receipt in `status.json.session_receipts`.

Use this evidence order. Stop at the first source that identifies the current
session without ambiguity:

1. Runtime environment or hook payload dedicated to the model session.
2. Session ID printed by the CLI or runner for the current invocation.
3. A session-specific scratchpad or exact transcript path tied to the current
   invocation.
4. An active-session registry matched by working directory and process id.
5. A session-store directory matched by working directory plus transcript
   content such as the current prompt.
6. Operator-supplied ID, cross-checked against one of the sources above when
   local evidence is available.

Do not identify a session from newest modification time alone: several sessions
for the same repository may be active, and transcript writes can lag. Never run
`resume` merely to discover an ID, never invent an ID, and never record tokens,
cookies, credentials, expanded environments, or unrelated diagnostic logs.

The status receipt uses this shape:

```json
{
  "role": "implementation_task_a",
  "provider": "claude_glm",
  "model": "glm-5.2",
  "session_id": "<provider-native id or null>",
  "session_id_source": "runtime_env",
  "unavailable_reason": null,
  "raw_output_path": "reports/agent-runs/<stage-id>/20-implementation-task-a.md",
  "recorded_at": "<UTC date-time>"
}
```

`session_id_source` is one of `runtime_env`, `hook_payload`, `cli_output`,
`transcript_path`, `active_session_registry`, `operator`, or `unavailable`.
When `session_id` is null, `unavailable_reason` is required. The raw output path
is the evidence handoff; a Session ID by itself does not let another provider
read the conversation.

### Codex

- Preferred runtime source: `CODEX_THREAD_ID`.
- Cross-check: the current rollout file under
  `~/.codex/sessions/YYYY/MM/DD/rollout-...-<thread-id>.jsonl`.
- The CLI can manage saved sessions with `codex resume`, but resume is not a
  discovery mechanism and must not be invoked by a bookkeeper just to inspect a
  session.

If `CODEX_THREAD_ID` is absent, use an exact runner receipt or a rollout file
whose metadata matches the current invocation. Do not choose only by mtime.

### Claude And Claude-GLM

- Preferred runtime source inside Claude Code-launched tools/hooks:
  `CLAUDE_CODE_SESSION_ID`.
- Hook JSON payloads may expose `session_id` directly.
- A session-specific scratchpad path may contain the same UUID.
- Cross-check transcript:
  `~/.claude/projects/<encoded-project-path>/<session-id>.jsonl`.

Claude-GLM uses the Claude Code session container, so it uses the same lookup
mechanics. This does not change its provider identity: `claude_glm` remains
`zhipu_glm`, not Anthropic. When the environment variable is unavailable, an
exact scratchpad/transcript match is stronger than newest-file inference.

### Grok

- Inspect `~/.grok/active_sessions.json` and match both repository cwd and the
  live Grok process id when available.
- Cross-check the corresponding directory under
  `~/.grok/sessions/<encoded-cwd>/<session-id>/`.
- Preserve a local transcript without a new model call with:
  `grok export <session-id> <stage-raw-output-path>`.

An active-session registry match is heuristic if multiple Grok processes share
the same cwd; record `unavailable` instead of guessing when pid/cwd cannot
disambiguate it.

### Kimi

- Locate the repository workspace under
  `~/.kimi-code/sessions/wd_<workspace>_<hash>/session_<uuid>/`.
- Verify `state.json` fields such as `workDir`, `lastPrompt`, and title against
  the current invocation. Do not select only the newest directory.
- `kimi -S <session-id>` resumes an already known session; it is not required
  for discovery.
- Optional local export uses
  `kimi export <session-id> -o <zip-path> -y --no-include-global-log` so the
  unrelated global diagnostic log is not bundled. The stage-facing raw Markdown
  response must still be captured separately.

Provider-native formatting may include a `session_` prefix. Preserve the exact
value printed or verified by that provider instead of normalizing it.

## Adapter Availability Checks

Run these checks from the same shell environment that the human operator will
use to execute the prepared dispatch:

```bash
command -v codex
command -v claude
command -v claude-glm
command -v grok
command -v kimi || command -v kimi-for-coding
grok models
```

If `claude-glm` is a shell alias or function, non-interactive scripts must load
the shell profile that defines it, or use the absolute wrapper path. If it still
cannot be resolved, record `model_unavailable` for the adapter instead of
inventing a substitute command.

## Codex

Purpose:

- Direction synthesis and stage design when selected.
- Review-2 primary final reviewer, unless ineligible or unavailable.
- Not an implementation or fix author for delivery code in this Harness.

Default model policy:

- Use the locally configured GPT/Codex default for this Harness:
  `gpt-5.5` with `xhigh` reasoning effort.
- If the local Codex CLI encodes effort through a profile or config file, the
  adapter must use that profile/config. Do not confuse `-p` with prompt input;
  Codex `-p` means profile.
- Do not silently downgrade the model or effort. If the requested model/profile
  fails because of quota, auth, or availability, route through the workflow
  fallback rules.

Command templates:

```bash
# Schema-bound read-only review.
codex exec -C <repo> -m gpt-5.5 -s read-only \
  --output-schema schemas/review-verdict.schema.json \
  - < <prompt-file>

# Free-form review is allowed only outside schema-bound Harness gates.
codex exec review --base <base_sha> - < <prompt-file>
```

Review-2 Harness gates use `codex exec`, not `codex review`, because the verdict
must satisfy `schemas/review-verdict.schema.json`.

Do not dispatch implementation or fix tasks to Codex. Backend and frontend
delivery work routes through Claude-GLM and Kimi according to the stage's domain
ownership rules.

## Claude

Purpose:

- Review-2 fallback when Codex is quota-exhausted, unavailable,
  auth-failed, or anti-self-review ineligible.
- Direction panel member or designer when registered.

Default model policy:

- Claude review uses `claude-fable-5` first. If Fable5 quota is exhausted, use
  `opus4.8` as the Anthropic fallback model unless the registry or user
  explicitly changes it.
- Review mode is read-only/plan. Do not let Claude modify files during review.

Command templates:

```bash
# Read-only/plan review.
claude --model claude-fable-5 --permission-mode plan \
  --json-schema "$(cat schemas/review-verdict.schema.json)" \
  -p "$(cat <prompt-file>)"

# Read-only/plan review fallback after Fable5 quota exhaustion.
claude --model opus4.8 --permission-mode plan \
  --json-schema "$(cat schemas/review-verdict.schema.json)" \
  -p "$(cat <prompt-file>)"

# Write-capable development, only when selected by workflow.
claude --model claude-fable-5 --permission-mode acceptEdits \
  -p "$(cat <prompt-file>)"

# Write-capable fallback after Fable5 quota exhaustion, only when selected by
# workflow.
claude --model opus4.8 --permission-mode acceptEdits \
  -p "$(cat <prompt-file>)"

# Yolo execution, only when explicitly authorized.
claude --model claude-fable-5 --permission-mode bypassPermissions \
  -p "$(cat <prompt-file>)"
```

If `claude --json-schema` is not usable in the local version, the prompt must
still require the strict JSON verdict at the end and the runner must validate the
captured output against the schema.

### Probing Anthropic availability when auth may be re-routed

Before recording Claude/Fable5 as quota-exhausted, or Claude/Fable5 and
Opus4.8 as unavailable, confirm the probe actually reached an Anthropic
endpoint. In environments where the `claude` CLI auth is overridden to a
non-Anthropic provider (for example `zhipu_glm`), a probe such as
`claude --model claude-fable-5` fails at the GLM endpoint with that provider's
own error (for example "model not found" / error 1211) — that is NOT evidence
that Fable5 is absent from Anthropic or that Opus4.8 fallback is unavailable.

Strip the GLM/Zhipu environment variables and auth overrides from the probe
shell first, or run the probe in an Anthropic-authenticated environment. A
failure caused by re-routing to the GLM endpoint must be recorded as "Anthropic
endpoint not probed (auth re-routed to GLM/Zhipu)", not as "Fable5 model
unavailable" or "Opus4.8 unavailable". Do not propagate a GLM-endpoint failure
into an Anthropic-unavailable conclusion elsewhere in the stage record.

## Claude-GLM

Purpose:

- Eligible bookkeeper/stage-operator model when explicitly assigned.
- Default backend/API/contract/schema/data-semantics implementation owner.
- May own a whole bounded mixed task when backend work is the large majority and
  frontend work is light integration or display wiring.

Provider identity:

- `claude_glm` is `zhipu_glm`, not Anthropic. The Claude Code wrapper does not
  make it an Anthropic model for anti-self-review decisions.

Command templates:

```bash
# Availability check. This may require an interactive shell profile.
type claude-glm
zsh -lic 'type claude-glm'

# Non-interactive bookkeeper or implementation prompt, if the local alias
# supports Claude-compatible print mode.
claude-glm --model glm-5.2 -p "$(cat <prompt-file>)"

# Read-only/plan review.
claude-glm --model glm-5.2 --permission-mode plan -p "$(cat <prompt-file>)"

# Embedded cross-review checkpoint. Same as read-only/plan review; use a fresh
# session and never reuse implementation/bookkeeper transcript.
claude-glm --model glm-5.2 --permission-mode plan -p "$(cat <prompt-file>)"

# Yolo execution, only when explicitly authorized.
claude-glm --model glm-5.2 --dangerously-skip-permissions -p "$(cat <prompt-file>)"
```

If the alias is not available to the runner, stop at adapter setup and ask the
operator to expose the wrapper. Do not fall back to Anthropic Claude while
claiming the provider is GLM.

Observed on 2026-07-04: in this repository's shell, `claude-glm` is defined by
the interactive zsh profile and may not be visible to non-interactive shells.
Runner scripts should either load the same profile or use `zsh -lic '<command>'`.
Never record the expanded alias environment; it contains credentials.

## Grok

Purpose:

- Direction drafts and optional experiments when explicitly enabled.
- Development only when explicitly enabled, using Composer 2.5.
- Not a default Harness review gate.

Observed local model names:

- `grok-build`
- `grok-composer-2.5-fast`

Availability check:

```bash
grok models
```

Do not silently use Grok as review-1. The default review-1 gate is the
Kimi/Claude-GLM cross-review pool. If a stage explicitly enables Grok review,
the runner must still fail closed on timeout, invalid JSON, or missing model.

Command templates:

```bash
# Interactive Grok Build session in the repository.
grok --cwd <repo> --model grok-build

# Optional review, read-only/plan mode. Runner enforces the stage timeout.
grok --cwd <repo> --model grok-build \
  --permission-mode plan \
  --effort high \
  --prompt-file <prompt-file>

# Development with Composer 2.5, only when workflow enables Grok development.
grok --cwd <repo> --model grok-composer-2.5-fast \
  --permission-mode acceptEdits \
  --check \
  --effort high \
  --prompt-file <prompt-file>

# Yolo execution, only when explicitly authorized.
grok --cwd <repo> --model grok-composer-2.5-fast \
  --permission-mode bypassPermissions \
  --always-approve \
  --prompt-file <prompt-file>
```

If an explicitly enabled Grok review has no schema-valid verdict after the stage
timeout, or the CLI process hangs, record `model_unavailable` and route to
`human_escalation_required`.

## Kimi

Purpose:

- Default frontend/UI/client-integration implementation owner.
- May own a whole bounded mixed task when frontend work is the large majority
  and backend work is light endpoint or schema glue.
- Direction panel member when registered.

Default model policy:

- Use the Kimi Code latest coding alias explicitly:
  `--model kimi-code/kimi-for-coding`.
- Observed on 2026-07-04, this resolves to Kimi K2.5 in this local CLI.

Command templates:

```bash
# Availability check.
command -v kimi || command -v kimi-for-coding

# Non-interactive prompt with the latest Kimi coding model alias.
kimi --model kimi-code/kimi-for-coding -p "$(cat <prompt-file>)"

# Embedded cross-review checkpoint. Kimi's current one-shot prompt mode has no
# compatible read-only flag, so read-only behavior is enforced by the prompt,
# wrapper, file boundaries, and Harness evidence checks.
kimi --model kimi-code/kimi-for-coding -p "$(cat <prompt-file>)"

# Plan/read-only-style interactive session. Current Kimi CLI rejects combining
# --plan with -p/--prompt, so do not use this as a one-shot prompt command.
kimi --model kimi-code/kimi-for-coding --plan

# Yolo interactive session, only when explicitly authorized. Current Kimi CLI
# rejects combining -y/--yolo with -p/--prompt.
kimi --model kimi-code/kimi-for-coding -y

# Resume or continue when the workflow explicitly references a session.
kimi -S <session-id>
kimi -c
```

If the local wrapper is named `kimi-for-coding`, the adapter may substitute that
binary for `kimi`. The workflow should still record provider identity as
`moonshot_kimi`.

Do not use `kimi --plan -p ...` or `kimi -y -p ...`; the current CLI returns
`Cannot combine --prompt with --plan/--yolo`.

## Dispatch Failure Semantics

- `quota_exhausted`: authenticated adapter reports quota/rate limit exhaustion.
- `auth_failure`: login/token problem or account not authorized for the model.
- `service_unavailable`: provider outage, transport failure, or repeated CLI
  startup failure.
- `model_unavailable`: adapter exists but the required model is missing, cannot
  be selected, or no schema-valid result arrives before the configured timeout.
- `adapter_missing`: runner shell cannot resolve the configured command. Treat
  as `model_unavailable` for non-decision models, or as the corresponding
  decision model unavailable for review-2 fallback.
- `command_error`: the adapter command is malformed or exits before reaching the
  model because of local invocation syntax.
- `permission_error`: the adapter refuses the requested mode or lacks local file
  permissions.
- `timeout`: the adapter process exceeds the stage timeout.
- `invalid_pre_review_output`: an embedded checkpoint returns output that cannot
  be interpreted as PASS/BLOCKER/escalated evidence.
- `scope_or_contract_dispute`: embedded review identifies a required fix outside
  the task scope or touching shared contract/schema boundaries.

Record the exact check command and stderr/stdout excerpt in the stage handoff or
review file, with secrets redacted.

For embedded cross-review checkpoints, use the canonical failure class list in
`agents/registry.yaml` at `failure_classes.embedded_checkpoint`.
