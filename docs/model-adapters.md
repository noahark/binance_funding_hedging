# Model Adapters

This document records local command knowledge that the workflow YAML should not
inline. Controllers and human operators must consult this file before declaring a
model unavailable.

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
- A model is unavailable only after the runner-level adapter check fails. A
  controller session lacking a built-in tool for that model is not enough.
- For review gates, use `base_sha` and `head_sha` from `status.json`. Do not use
  the moving symbolic `HEAD` when unrelated Harness commits may have happened
  after the reviewed stage commit.

## Adapter Availability Checks

Run these checks from the same shell environment that will dispatch the model:

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
- Optional development/fix agent when the workflow selects Codex.

Default model policy:

- Use the locally configured GPT/Codex default for this Harness:
  `gpt5.5` with `xhigh` reasoning effort.
- If the local Codex CLI encodes effort through a profile or config file, the
  adapter must use that profile/config. Do not confuse `-p` with prompt input;
  Codex `-p` means profile.
- Do not silently downgrade the model or effort. If the requested model/profile
  fails because of quota, auth, or availability, route through the workflow
  fallback rules.

Command templates:

```bash
# Non-interactive write-capable execution.
codex -C <repo> -m gpt5.5 -s workspace-write -a never exec - < <prompt-file>

# Yolo execution, only when explicitly authorized.
codex -C <repo> -m gpt5.5 -s danger-full-access -a never exec - < <prompt-file>

# Schema-bound read-only review.
codex -C <repo> -m gpt5.5 -s read-only -a never exec \
  --output-schema schemas/review-verdict.schema.json \
  - < <prompt-file>

# Free-form review is allowed only outside schema-bound Harness gates.
codex -C <repo> review --base <base_sha> - < <prompt-file>
```

Review-2 Harness gates use `codex exec`, not `codex review`, because the verdict
must satisfy `schemas/review-verdict.schema.json`.

## Claude

Purpose:

- Review-2 fallback when Codex is quota-exhausted, unavailable,
  auth-failed, or anti-self-review ineligible.
- Direction panel member or designer when registered.

Default model policy:

- Claude review uses `claude-fable-5` unless the registry or user explicitly
  changes it.
- Review mode is read-only/plan. Do not let Claude modify files during review.

Command templates:

```bash
# Read-only/plan review.
claude --model claude-fable-5 --permission-mode plan \
  --json-schema "$(cat schemas/review-verdict.schema.json)" \
  -p "$(cat <prompt-file>)"

# Write-capable development, only when selected by workflow.
claude --model claude-fable-5 --permission-mode acceptEdits \
  -p "$(cat <prompt-file>)"

# Yolo execution, only when explicitly authorized.
claude --model claude-fable-5 --permission-mode bypassPermissions \
  -p "$(cat <prompt-file>)"
```

If `claude --json-schema` is not usable in the local version, the prompt must
still require the strict JSON verdict at the end and the runner must validate the
captured output against the schema.

## Claude-GLM

Purpose:

- Default controller through GLM5.2 with large context.
- Backend/contract implementation when explicitly selected for the stage.

Provider identity:

- `claude_glm` is `zhipu_glm`, not Anthropic. The Claude Code wrapper does not
  make it an Anthropic model for anti-self-review decisions.

Command templates:

```bash
# Availability check. This may require an interactive shell profile.
type claude-glm

# Non-interactive controller or implementation prompt, if the local alias
# supports Claude-compatible print mode.
claude-glm -p "$(cat <prompt-file>)"
```

If the alias is not available to the runner, stop at adapter setup and ask the
operator to expose the wrapper. Do not fall back to Anthropic Claude while
claiming the provider is GLM.

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

- Frontend implementation and other workflow-selected development tasks.
- Direction panel member when registered.

Default model policy:

- Use the local `kimi-for-coding`/Kimi Code default. The local CLI defaults to
  the configured current model when `-m` is omitted.
- Do not pin a stale model unless the stage explicitly requires reproducibility
  over automatic latest-model routing.

Command templates:

```bash
# Availability check.
command -v kimi || command -v kimi-for-coding

# Non-interactive prompt with the default configured model.
kimi -p "$(cat <prompt-file>)"

# Plan/read-only-style session.
kimi --plan -p "$(cat <prompt-file>)"

# Yolo execution, only when explicitly authorized.
kimi -y -p "$(cat <prompt-file>)"

# Resume or continue when the workflow explicitly references a session.
kimi -S <session-id>
kimi -c
```

If the local wrapper is named `kimi-for-coding`, the adapter may substitute that
binary for `kimi`. The workflow should still record provider identity as
`moonshot_kimi`.

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

Record the exact check command and stderr/stdout excerpt in the stage handoff or
review file, with secrets redacted.
