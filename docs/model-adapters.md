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

## Adapter Availability Checks

Run these checks from the same shell environment that the human operator will
use to execute the prepared dispatch:

```bash
command -v codex
command -v claude
test -x "$PWD/scripts/model-adapters/claude-glm-wrapper"
"$PWD/scripts/model-adapters/claude-glm-wrapper" --version
command -v grok
command -v kimi || command -v kimi-for-coding
grok models
```

The Claude-GLM adapter must use the repository wrapper through its runtime
absolute path. The wrapper isolates the interactive-zsh alias that owns the
existing provider routing and suppresses shell-profile startup/exit chatter. If
the wrapper cannot resolve the alias, record `model_unavailable` for the adapter
instead of inventing a substitute command.

## Codex

Purpose:

- Direction synthesis and stage design when selected.
- Review-2 primary final reviewer, unless ineligible or unavailable.
- Not an implementation or fix author for delivery code in this Harness.

Default model policy:

- Use the locally configured GPT/Codex default for this Harness:
  `gpt-5.6-sol` with `xhigh` reasoning effort.
- If the local Codex CLI encodes effort through a profile or config file, the
  adapter must use that profile/config. Do not confuse `-p` with prompt input;
  Codex `-p` means profile.
- Do not silently downgrade the model or effort. If the requested model/profile
  fails because of quota, auth, or availability, route through the workflow
  fallback rules.

Command templates:

```bash
# Schema-bound read-only review.
codex exec -C <repo> -m gpt-5.6-sol -s read-only \
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
test -x "<repo>/scripts/model-adapters/claude-glm-pty-wrapper"
test -x "<repo>/scripts/model-adapters/claude-glm-wrapper"
"<repo>/scripts/model-adapters/claude-glm-wrapper" --version

# Runner-owned implementation prompt. The PTY wrapper reads the immutable
# prompt file, creates a real terminal, and supplies it as an initial positional
# prompt; it deliberately does not use -p/sdk-cli.
<repo>/scripts/model-adapters/claude-glm-pty-wrapper \
  --model glm-5.2 --policy implementation-v1 \
  --tool-policy-file <tool-policy-file> --prompt-file <prompt-file>

# Read-only/plan review.
<repo>/scripts/model-adapters/claude-glm-pty-wrapper \
  --model glm-5.2 --policy review-readonly-v1 \
  --tool-policy-file <tool-policy-file> --prompt-file <prompt-file>

# Embedded cross-review checkpoint. Same as read-only/plan review; use a fresh
# session and never reuse implementation/bookkeeper transcript.
<repo>/scripts/model-adapters/claude-glm-pty-wrapper \
  --model glm-5.2 --policy review-readonly-v1 \
  --tool-policy-file <tool-policy-file> --prompt-file <prompt-file>

# Yolo execution, only when explicitly authorized.
<repo>/scripts/model-adapters/claude-glm-pty-wrapper \
  --model glm-5.2 --dangerously-skip-permissions --prompt-file <prompt-file>
```

The PTY wrapper is the runner-facing entrypoint. It allocates a pseudo-terminal
and invokes the lower absolute zsh wrapper without `-p`. The lower wrapper
starts `/bin/zsh -lic` behind isolated file descriptors so profile startup and
exit-hook messages do not contaminate model output, restores output only for
the actual `claude-glm` call, and never prints the alias expansion or
environment. This keeps the existing secret routing in the user's shell
profile while making the runner invocation deterministic and absolute-path
based.

The PTY wrapper assigns a fresh Claude session UUID and watches only that
session's persisted transcript. Success requires an actual final assistant text
turn with `entrypoint=cli`; `<synthetic>` provider errors and any
`entrypoint=sdk-cli` result fail closed. It then exits the interactive TUI and
returns the captured raw terminal stream to the runner, which remains the sole
receipt writer and next-hop authority.

Permission policy does not come from the alias. The wrapper removes a legacy
alias-level `--dangerously-skip-permissions` token in memory without logging the
alias, then applies a frozen policy ID plus the runner-generated stage-local
settings file. `implementation-v1` uses `dontAsk` and exposes exactly
`Read,Glob,Grep,Edit,Write`; `review-readonly-v1` exposes exactly
`Read,Glob,Grep`. Both explicitly deny `Bash`, use Claude Code safe mode,
disable slash commands, and supply an empty strict MCP configuration. Only
`yolo_command` adds `--dangerously-skip-permissions`, and it still requires
separate explicit human authorization.

Write rules in the settings file are derived mechanically from the active
authorization's `scope.allowed_pathspecs`; protected Harness/evidence/secret
paths are denied. The model never runs tests, git, or chmod. The deterministic
runner runs frozen blocking checks and may normalize only predeclared
`mechanical_post_write.executable_paths` to mode `0755`.

If the alias is not available inside the wrapper, stop at adapter setup. Do not
fall back to Anthropic Claude while claiming the provider is GLM.

Observed on 2026-07-13: direct `/bin/sh` execution cannot resolve the
interactive-zsh `claude-glm` alias. Runner templates therefore invoke the
committed wrapper at its runtime absolute path. Never record the expanded alias
environment; it contains credentials.

Also observed on 2026-07-13: two adjacent `-p` attempts were recorded as
`entrypoint=sdk-cli`, returned synthetic zero-token API 529 responses after
approximately three minutes, and failed under both `bypassPermissions` and
`acceptEdits`. A typed interactive session was recorded as `entrypoint=cli` and
returned from the same `glm-5.2` model in approximately five seconds. Because
Claude Code also treats redirected non-TTY stdout as non-interactive, removing
`-p` alone is insufficient; the runner transport must supply a PTY.

Known local-pilot trade-off: every invocation loads the full interactive login
zsh profile. A profile hook that blocks without a TTY can therefore delay the
adapter until the registered runner timeout. Runtime tests use an isolated
`ZDOTDIR` to cover alias absence, permission stripping, and startup/exit noise;
the real profile remains a local operational dependency.

## Grok

Purpose:

- Direction drafts and optional experiments when explicitly enabled.
- Development only when explicitly enabled, using `grok-4.5`.
- Auto-mode review-1 primary (plan mode) also uses `grok-4.5`.
- Not a default manual Harness review-1 gate.

Observed local model names (2026-07 probe):

- `grok-4.5` (default; Harness dev + review)
- `grok-composer-2.5-fast` (still listed by CLI; not Harness default)

Availability check:

```bash
grok models
```

Do not silently use Grok as manual review-1. The default manual review-1 gate is
the Kimi/Claude-GLM cross-review pool. If a stage explicitly enables Grok review
(or auto mode uses it as primary), the runner must still fail closed on timeout,
invalid JSON, or missing model.

Command templates:

```bash
# Interactive Grok session in the repository.
grok --cwd <repo> --model grok-4.5

# Optional review, read-only/plan mode. Runner enforces the registered
# per-call timeout (grok.optional_review_timeout_seconds, 900s).
grok --cwd <repo> --model grok-4.5 \
  --permission-mode plan \
  --effort high \
  --prompt-file <prompt-file>

# Development, only when workflow enables Grok development.
grok --cwd <repo> --model grok-4.5 \
  --permission-mode acceptEdits \
  --check \
  --effort high \
  --prompt-file <prompt-file>

# Yolo execution, only when explicitly authorized.
grok --cwd <repo> --model grok-4.5 \
  --permission-mode bypassPermissions \
  --always-approve \
  --prompt-file <prompt-file>
```

If an explicitly enabled Grok review has no schema-valid verdict after the
registered per-call timeout, or the CLI process hangs, record `model_unavailable`
and route to `human_escalation_required`.

## Kimi

Purpose:

- Persistent default runner host until the human operator explicitly switches
  hosts. The host session only starts/watches `scripts/auto-review-runner.py`.
- A runner-host session must not implement, fix, review, or write authoritative
  stage state; any Kimi delivery/review route uses a fresh session.
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
- `timeout`: the adapter process exceeds its registered per-call timeout.
- `invalid_pre_review_output`: an embedded checkpoint returns output that cannot
  be interpreted as PASS/BLOCKER/escalated evidence.
- `scope_or_contract_dispute`: embedded review identifies a required fix outside
  the task scope or touching shared contract/schema boundaries.

Record the exact check command and stderr/stdout excerpt in the stage handoff or
review file, with secrets redacted.

For embedded cross-review checkpoints, use the canonical failure class list in
`agents/registry.yaml` at `failure_classes.embedded_checkpoint`.

## Auto Review Pipeline

`auto_review_pipeline/v1` is a default-off opt-in mode. Its normative contract
is `docs/auto-review-pipeline.md`; its machine-readable gates are
`schemas/auto-review-authorization.schema.json` and
`schemas/runner-receipt.schema.json`. Nothing here changes the manual adapter
rules above.

Under auto mode:

- The deterministic runner is the only automatic dispatcher. It invokes adapters
  through registry command references
  (`agents/registry.yaml#adapters.<id>.<command>`), never through expanded
  commands built from model output. A model session is never the auto-loop
  dispatcher.
- Auto review-1 uses Grok in plan mode via the existing
  `adapters.grok.optional_review_command` (`grok-4.5`). Serial fallback uses
  the Kimi/Claude-GLM cross-pool only when the candidate provider is absent
  from that unit's author set; when no eligible serial candidate remains, a
  Grok failure escalates. GPT/Claude are never auto-substituted.
- The automatic loop is limited to `claude_glm`, `kimi`, and `grok`. High-end
  (GPT/Claude) dispatch is fixed absent by workflow policy (no per-authorization
  flag is carried), so human-started high-end work (synthesis, breakdown,
  review-2) remains outside the runner.
- Adapter availability still uses the runner-level checks documented above. A
  bookkeeper or implementation session lacking a built-in tool for a model does
  not make that model unavailable.
- Receipts record adapter command references only. They never contain expanded
  aliases, environment dumps, tokens, cookies, or secrets
  (`never_log_expanded_environment`). If provider output itself exposes a secret,
  the runner stops and escalates rather than rewriting evidence.
