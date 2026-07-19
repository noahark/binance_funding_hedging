# Root Cause And Fast-Fix Plan

## Outcome

The six incidents share three system causes, not six unrelated operator
mistakes:

1. **Dispatch authority contradiction.** `AGENTS.md` says the human operator
   executes every model dispatch, while parallel-mode Phase 2/R10 says the
   implementing terminal must execute the opposite-model adapter, and the
   validator requires `next_dispatch_executor == "self"`.
2. **Duplicate review architecture.** The current default intentionally runs an
   uncommitted embedded cross-review and then repeats the same pairing against
   committed task fingerprints for formal Review-1.
3. **Evidence capture is advisory.** Packets name output paths, but no
   deterministic mechanism makes successful output creation and strict verdict
   validation part of the same operator command.

## Evidence In Current Harness

- `AGENTS.md:137-142`: Codex/GPT and Claude sessions prepare packets; the human
  operator executes implementation, embedded-review, Review-1, Review-2, and
  fix dispatches.
- `docs/parallel-development-mode.md:104-110`: implementer terminals must start
  the opposite review model themselves.
- `docs/parallel-development-mode.md:211-238`: `executor:self` is mandatory and
  R10 embeds the opposite-model adapter command in implementation prompts.
- `workflows/templates/stage-delivery.yaml:477-510`: repeats the self-execution
  and implementing-terminal embedded-review actor.
- `scripts/validate-stage.py:665-668`: rejects anything except
  `next_dispatch_executor == "self"` and forbids manual handoff.

Under the repository authority order, `AGENTS.md` wins. Therefore model-side
launch claims from the preceding stage were not sufficient dispatch evidence,
even when a subprocess may actually have run.

## Decision 1 — One Dispatch Authority

Use one rule everywhere:

```text
packet author/bookkeeper prepares → human operator launches exactly one target
model → deterministic capture helper records output → bookkeeper validates and
advances state
```

- External dispatch metadata uses `executor: human_operator`.
- Implementation and review prompts explicitly prohibit invoking `codex`,
  `claude`, `claude-glm`, `kimi`, or `grok` as child dispatches.
- A model that reaches a next dispatch stops and returns the target packet path.
- Session/provider identity comes from the operator receipt or verified runtime
  evidence, never from a nested model's narrative claim.
- Validator rejects `executor:self` for external model dispatches.

## Decision 2 — One Default Cross-Review Round

Replace the mandatory embedded-review + formal Review-1 pair with:

```text
parallel implementation
→ implementation reports and self-tests
→ bookkeeper scope reconciliation and committed H_A/H_B ranges
→ one fresh cross-provider formal Review-1 per committed task fingerprint
→ Review-2
```

Embedded review remains available only when the stage explicitly records an
opt-in reason such as unusually high implementation risk or a user request. It
never substitutes for formal Review-1 and is no longer a dispatch-ready
requirement by default.

This preserves the valuable gate—independent review of immutable committed
bytes—while removing the duplicated model round.

## Decision 3 — Raw Output And Verdict Are Separate Artifacts

Introduce a small **capture-only** helper invoked by the human operator. It does
not choose a model, invoke a second model, commit, edit status, or advance the
workflow.

Conceptual use:

```text
<human runs registered adapter command>
  | capture-review-output --raw <raw-output-path>
                          --verdict <strict-verdict-path>
                          --schema schemas/review-verdict.schema.json
```

Required behavior:

1. Read stdout from one explicitly launched review process.
2. Atomically persist exact bytes to `*.raw-output.md`.
3. Parse the response as one JSON object after allowing only terminal transport
   whitespace. Markdown fences or narrative outside the object are invalid.
4. Validate the object against `review-verdict.schema.json`.
5. Serialize the validated object to `*.verdict.json` with no Markdown and no
   terminal newline; preserve the raw artifact separately.
6. Print a mechanical receipt containing paths, byte counts, SHA-256 values,
   validation result, and optional operator-provided Session ID source.
7. On empty output, parse/schema failure, or write failure, exit non-zero and do
   not create/replace the canonical verdict file.

The gate reads `*.verdict.json`; reviewers' prose belongs in structured JSON
findings/residual risks. Footer/navigation data goes in the schema-approved
`reviewer_prior_involvement_notes` field.

## Versioning And Historical Compatibility

Add an explicit status protocol field for new stages, for example:

```json
"review_artifact_protocol": "raw-plus-strict-json/v1"
```

- New stages using the field must satisfy the new raw + verdict rules.
- Historical stages without the field retain legacy validation behavior.
- Do not mutate or mass-normalize completed evidence.
- `scripts/validate-all-stages.py` must remain green against historical stages.

## Validator Changes

### Dispatch-ready

- Default parallel mode no longer requires embedded-review prompts, patches,
  self-execution, or two-round metadata.
- Require task implementation owner, formal cross-reviewer, test commands, and
  committed-review output paths.
- Reject external `executor:self`; require `human_operator`.
- When `embedded_review.enabled == true`, validate its additional artifacts as
  an opt-in extension.

### Review-1 / Review-2

- Require raw output and strict verdict paths to exist and be non-empty.
- Parse the entire verdict file, validate schema, fingerprint, role, model, and
  reviewer-provider isolation.
- Reject Markdown fences and bytes after the JSON object.
- Do not advance based only on a model's chat claim or Session ID.

### Pre-accept

- Require all task Review-1 strict verdicts and the Review-2 strict verdict.
- Preserve the existing status fingerprint and provider-isolation rules.

## Required Test Matrix

Positive:

- GLM task implemented, human launches Kimi formal Review-1, raw + verdict files
  are atomically captured and accepted.
- Kimi task implemented, human launches GLM formal Review-1, same result.
- Fable5 Review-2 pure JSON is captured; transport newline is preserved in raw
  and absent from canonical verdict.
- A legacy completed stage without the new protocol still validates.

Negative:

- `executor:self` for an external model dispatch.
- Reviewer attempts to declare or launch a child reviewer.
- Missing `30-review-1-*.raw-output.md` or `.verdict.json`.
- Missing Review-2 raw/verdict output.
- Empty output, Markdown-fenced JSON, narrative around JSON, schema-invalid
  JSON, wrong fingerprint, wrong role/model, same-provider self-review.
- Capture interrupted before atomic rename; an earlier canonical verdict must
  remain untouched.

## Implementation Split

One bounded Harness implementation task is sufficient. The user will choose the
implementation model after an independent model reviews this plan. Codex does
not author implementation code.

Suggested order:

1. Update authority language and parallel-mode flow.
2. Update workflow/template/status protocol.
3. Implement capture helper and focused fixtures.
4. Update validator for protocol v1 and legacy compatibility.
5. Run focused tests, `py_compile`, `git diff --check`, relevant stage
   validation, and historical all-stage comparison.

## Reviewer Questions

The independent plan reviewer should answer:

1. Does removing mandatory embedded review preserve the strongest useful gate?
2. Is a capture-only helper sufficiently narrow to avoid recreating the retired
   autonomous review pipeline?
3. Is raw + strict verdict separation auditable and backward compatible?
4. Are there any validator bypasses or status transition gaps in this plan?
5. Can the file scope be reduced without reintroducing contradictory rules?

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-harness-review-dispatch-fast-fix-v1/05-root-cause-and-fix-plan.md
本地北京时间: 2026-07-19 22:12:37 CST
下一步模型: user-selected independent plan reviewer
下一步任务: 对五个 reviewer questions 给出 ACCEPT 或带证据的修改建议
