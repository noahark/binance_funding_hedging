# Review-2: Public Market Contract V2

> **This is a controller dispatch-failure record, NOT a reviewer verdict.**
> The dispatched final reviewer (Claude `claude-fable-5`) did not return a
> verdict. No JSON verdict is fabricated below. The controller records the
> runner-level failure, the provider-identity conflict, and the resulting
> terminal stop. Per AGENTS.md the controller cannot declare final acceptance,
> and cannot hide or rewrite reviewer evidence — so this file records what
> actually happened, including the absence of a verdict.

Dispatch recorded at: `2026-07-03T08:15:32Z`.

## Dispatch attempt

- **Role**: review-2 final gate, `reality_checker` skill, read-only / plan mode.
- **Adapter**: `claude` (`agents/registry.yaml` `adapters.claude`, binary
  `/Users/ark/.local/bin/claude`, declared `provider_identity: anthropic`,
  `default_review_model: claude-fable-5`).
- **Command** (per `docs/model-adapters.md` and registry
  `read_only_review_command`):

  ```text
  claude --model claude-fable-5 --permission-mode plan \
    --json-schema "$(cat schemas/review-verdict.schema.json)" \
    -p "$(cat reports/agent-runs/2026-07-public-market-contract-v2/review-2.prompt.md)"
  ```

- **Prompt file** (read-only, raw artifacts + frozen diff + strict JSON contract):
  `reports/agent-runs/2026-07-public-market-contract-v2/review-2.prompt.md`.
- **Background task id**: `birc9183w`. **Process exit code**: `1`.
- **Raw captured output** (290 bytes):
  `reports/agent-runs/2026-07-public-market-contract-v2/review-2.raw-output.txt`.

## Runner-level failure (two independent causes)

### 1. Technical: `claude-fable-5` does not exist on the active gateway

The CLI errored out before producing any review:

```text
⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth
  source is set and takes precedence over your claude.ai login · Unset it to
  load your organization's connectors
API Error: 400 [1211][模型不存在，请检查模型代码。][202607031608327097993616204a51]
```

This is the local proxy gateway rejecting `claude-fable-5`. Per
`agents/registry.yaml` `review_2_fallback_allowed_on`, this is
`service_unavailable`. Per AGENTS.md the runner-level adapter check must fail
before a model is marked unavailable — it did: `claude --help` confirmed the
`--json-schema` / `--permission-mode plan` / `--model` flags are supported, the
adapter binary resolves, yet the actual dispatch returned a non-zero
`400 模型不存在`. This is a runner-level dispatch failure, not "the controller
session lacks a built-in Claude tool."

### 2. Identity: the local `claude` binary is hijacked to the same provider as the implementer

The active environment routes Anthropic-protocol traffic to Zhipu BigModel:

```text
ANTHROPIC_BASE_URL = https://open.bigmodel.cn/api/anthropic   (endpoint URL; not a credential)
ANTHROPIC_AUTH_TOKEN = SET (value redacted, never logged)
```

`https://open.bigmodel.cn/api/anthropic` is **Zhipu's** Anthropic-compatible
endpoint. The local `claude` binary therefore resolves at runtime to provider
**`zhipu_glm`** — the same model vendor as the stage implementer/controller
(`claude_glm` = `zhipu_glm`, see AGENTS.md §review-2).

AGENTS.md is explicit:

> `review-2` uses provider-level isolation for final decisioning. The final
> reviewer must not share the designer or implementer provider. Provider
> identity means model vendor, not CLI wrapper. `claude_glm` is `zhipu_glm`,
> not Anthropic, even though it is accessed through Claude Code.

So even if a model code acceptable to the gateway were chosen, the local
`claude` runtime provider is `zhipu_glm`, identical to the implementer — a
self-review. This is `anti_self_review_ineligible` under
`review_2_fallback_allowed_on` and violates
`review_2_provider_must_differ_from_implementer_provider`.

The registry *declares* `adapters.claude.provider_identity: anthropic`; the
runtime *observation* is `zhipu_glm` via the `ANTHROPIC_BASE_URL` hijack. The
discrepancy is recorded here rather than papered over, because anti-self-review
is about actual model vendor, not the registry label.

## Fallback-chain analysis (registry + AGENTS + feature-loop)

- `agents/registry.yaml` `review_2`: `primary: codex`, `fallback: claude`. The
  chain has exactly two entries.
- `primary = codex` is excluded: the stage designer is `codex`, and
  `final_review_2_must_differ_from_designer: true`.
- `fallback = claude` is the chain terminus. It is unavailable for the two
  reasons above (`service_unavailable` + `anti_self_review_ineligible`), both of
  which are listed in `review_2_fallback_allowed_on`.
- AGENTS.md allows the GPT/Codex → Claude review-2 fallback only for quota,
  authentication, service availability, or anti-self-review ineligibility — we
  are in that allowed-fallback condition, but the fallback target itself fails.
- No third final reviewer is registered. The controller must not silently
  substitute another model (e.g. Kimi or Grok) into review-2, by analogy to the
  hard gate that forbids silently substituting Grok into review-1.
- `status.json.review_2.availability_note` already foresaw exactly this case:
  "If Claude is quota-exhausted or unavailable, the stage routes to
  `decision_models_exhausted` because codex is designer-ineligible and no third
  final reviewer is registered."

## Terminal state

**`decision_models_exhausted`** (a registered terminal stop reason;
`workflows/templates/feature-loop.yaml` review-2 transition
`decision_models_exhausted: decision_models_exhausted`).

This is **not** an acceptance. The frozen contract under review
(`2bb47ad..d73eb10`, fingerprint
`d73eb10:de0c199bd7b9121ec2539c6a891f3167043bc1f4412704c3276fe6171b3fdd46`) is
unchanged. Review-1 (Kimi) `ACCEPT` stands as-is; review-2 could not be
produced by any provider-isolated decision model in this environment.

The frozen review subject is preserved for whichever path the user chooses:

```text
base_sha = 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a
head_sha = d73eb10187f34696aec4aea8f596c0d3578a1dcf
git diff --binary 2bb47ad13065827ed1ee91d5d0e231cd312fdc0a..d73eb10187f34696aec4aea8f596c0d3578a1dcf -- . ":(exclude)reports/agent-runs/2026-07-public-market-contract-v2/status.json" | shasum -a 256
```

## Options for the human (controller does not pick)

- **A. Provide a real Anthropic channel.** If the user has a Claude.ai Pro/Max
  login or an independent Anthropic API key, run the review-2 dispatch in a
  clean environment with `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` unset (or
  pointed at `api.anthropic.com`), so the local `claude` binary reaches real
  Anthropic and `claude-fable-5` resolves with provider `anthropic` (≠ designer
  `codex`/openai, ≠ implementer `claude_glm`/zhipu). The warning line above
  indicates a Claude.ai login exists but is currently overridden by the env
  vars. The existing prompt file can be reused unchanged.
- **B. Authorize a third review-2 fallback.** Explicitly extend the review-2
  pool (registry `review_2` + `workflows/templates/feature-loop.yaml`) with a
  provider-isolated decision model — e.g. Kimi (`moonshot_kimi`, ≠ openai ≠
  zhipu, already proven available in this repo's review-1) — and re-dispatch.
  This requires a registry/workflow change the user must approve; the controller
  will not make it unilaterally.
- **C. Accept the terminal stop and have the human perform the reality check.**
  The user reads the raw artifacts directly and makes the final accept/rework
  call, recorded as a human verdict.

## Evidence pointers

- Raw dispatch output:
  `reports/agent-runs/2026-07-public-market-contract-v2/review-2.raw-output.txt`
- Review-2 prompt (raw-artifact, frozen-diff, JSON-contract spec):
  `reports/agent-runs/2026-07-public-market-contract-v2/review-2.prompt.md`
- Gateway endpoint (non-secret URL): `ANTHROPIC_BASE_URL =
  https://open.bigmodel.cn/api/anthropic`
- Rules: `agents/registry.yaml` (`adapters.claude`, `review_2`,
  `review_2_fallback_allowed_on`, `review_policy`); `AGENTS.md` §review-2 and
  §Hard Gates (runner-level adapter check; codex→claude fallback reasons);
  `workflows/templates/feature-loop.yaml` review-2 stage transitions.
