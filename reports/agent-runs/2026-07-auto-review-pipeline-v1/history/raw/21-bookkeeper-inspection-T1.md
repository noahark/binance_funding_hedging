# Bookkeeper Inspection: T1 `contract-and-schemas`

Outcome: **REWORK BEFORE SEAL**

This is a pre-review bookkeeper inspection, not a formal review-1 verdict. No
T1 delivery commit, `head_sha`, `diff_fingerprint`, or Kimi dispatch was
created. Because no formal verdict or code-changing fix dispatch has occurred,
the shared stage `rework_count` remains `0`.

## Inspected State

- Branch: `stage/2026-07-auto-review-pipeline-v1`
- HEAD before inspection checkpoint: `8d5fe3fb72f03cfc5b6288bbafcc9eb2d575eab0`
- Frozen T1 base: `a385c7ad77da1611c6e952b2219aee56b49f442f`
- Implementer report:
  `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
- Test evidence:
  `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`
- Implementer identity: `claude_glm` / `zhipu_glm`

## Boundary Disposition — PASS

The worktree contains exactly 13 changed paths:

- 11 T1 delivery paths from the frozen writable set;
- 2 shared evidence paths (`20-implementation.md` and
  `60-test-output.txt`);
- 0 forbidden, product, runtime, funding-stage, T2, or T3 paths.

`agents/developer-discipline.md` is the only writable T1 delivery path that was
not changed. Existing delivery files are additive-only except for the two
frozen E1 replacements in `_template/status.json`. `60-test-output.txt` is
append-only, and `20-implementation.md` is create-if-absent.

The frozen range already contains bookkeeper-only status/handoff/evidence
commits after T1 base. A later reviewer must receive the exact range and this
role attribution; those bookkeeper paths are not implementer boundary
violations.

## Blocking Findings

### T1-B1 — Receipt required fields are not required (P1)

`10-design.md` §Runner Receipt lists review-unit/task id and
prompt/raw-output/verdict paths among required fields. The new schema declares
those properties nullable but omits all five keys from top-level `required`:

- `review_unit_id`
- `task_id`
- `prompt_path`
- `raw_output_path`
- `verdict_path`

An otherwise valid receipt that omits all five keys currently passes
`Draft202012Validator` with zero errors. This would permit an evidence-free
receipt to count toward P11 completeness.

### T1-B2 — Command-reference and adapter pairing are not enforced (P1)

`adapter.registry_command_ref` has only `minLength: 1`. The schema currently
accepts both:

- an expanded command/secret-like string such as
  `grok --token SECRET --permission-mode plan`;
- `adapter.id: grok` paired with a Claude-GLM registry reference.

This does not meet the breakdown requirement to enforce the P13 forbidden
content boundary with pattern/absence constraints where machine-checkable.
The command reference must be an anchored `agents/registry.yaml#adapters.*`
reference and must match the selected adapter identity. Nullable artifact path
fields must reject empty, absolute, traversal, or newline-bearing strings when
non-null.

### T1-B3 — Executable workflow contract is incomplete and internally ambiguous (P1)

The new `stage-delivery.yaml:auto_review_pipeline` block records flags, state
enums, and reviewer references, but no machine-readable auto nodes, transition
map, or acceptance predicates. This conflicts with the frozen ownership rule
that workflow YAML defines transitions and the runner only executes them.

The workflow also retains the correct manual defaults
`model_dispatch_execution_requires_human: true` and bookkeeper single-write
authority, but the auto block does not condition its exception on a committed,
schema-valid human authorization or explicitly grant the runner sole
mechanical-write authority while keeping implementers non-committing. Without
that conditional activation, T3 would have to invent policy or contradict the
higher-authority workflow.

The minimum executable contract must freeze:

- default-off activation, authorization, branch, and mode-mutex predicates;
- runner-only automatic dispatch/mechanical writes as the authorized exception;
- ordered initial blocking → embedded cross-check → identical post-cross-check
  blocking rerun → seal;
- one P7 blocking-fix retry, then escalation on a second failure;
- fixed review-1 ACCEPT/REWORK/invalid/fallback/escalation transitions;
- `completed_review_1` only when every required unit has schema-valid ACCEPT
  bound to the unit fingerprint;
- two-pilot/default-flip eligibility predicates without inventing a Grok-rate
  threshold.

### T1-B4 — P7 one-retry rule is missing from normative operational prose (P1)

`docs/auto-review-pipeline.md` states that a blocking-test fix charges one and
that the aggregate auto change cap is two, but does not state the separate
frozen P7 rule: only one automatic blocking-fix retry is allowed; if the
identical blocking set still fails after that fix, write escalation evidence
and stop. A traceability-row label is not an executable rule. The normative
text and workflow transition must both say it.

### T1-B5 — Rewrite-on-touch terminology and evidence accuracy (record gate)

The touched parallel-mode §6 still uses the historical advisory-pass term in
two sentences. The frozen rewrite-on-touch rule requires those two sentences
to use `embedded cross-check`. The current AGENTS revision also retains four
advisory-pass occurrences using historical names; the correction must make the
AGENTS revision use the locked `embedded cross-check` term without changing
manual semantics. Every changed pre-existing sentence must be recorded
verbatim before/after in an appended implementation correction section.

The raw implementation report also needs an appended, attributed erratum:

- actual scope is 13 changed paths = 11 delivery + 2 shared evidence, not
  "12 touched delivery files";
- its `git status` snapshot omitted the newly created report itself;
- its original statement that all receipt required fields matched was false
  before T1-B1 is corrected.

Do not rewrite or delete the original report text. The correction author
appends the erratum and fix audit. The three `json.tool` entries in
`60-test-output.txt` contain result summaries rather than raw stdout; the
correction run must append the complete stdout and exit status, then rerun every
frozen T1 command unchanged.

## Independent Checks

- JSON parse: authorization schema PASS; receipt schema PASS; status template
  PASS.
- JSON Schema meta-validation: both new schemas PASS draft-2020-12 structure.
- Counterexample: omitted five receipt evidence keys → **0 validation errors**
  (finding reproduced).
- Counterexample: expanded command/secret-like `registry_command_ref` → **0
  validation errors** (finding reproduced).
- Counterexample: Grok id + Claude-GLM registry reference → **0 validation
  errors** (finding reproduced).
- Ruby YAML parse: workflow and registry PASS.
- `scripts/validate-stage.py ... --phase checkpoint`: PASS.
- `git diff --check`: PASS for tracked worktree changes; new-file whitespace is
  closed only after staging/committed-range verification.
- Frozen vocabulary negative scan: no forbidden review-1 alias match; expected
  exit 1.
- Machine boundary assertion: PASS, 13 paths, 0 extras.

## Disposition

T1 is not eligible for a delivery commit or review-1. The bookkeeper prepared
`task-T1-correction-round1-claude-glm.prompt.md` for human execution. After the
correction returns, the bookkeeper must re-inspect the full worktree, run the
frozen and counterexample checks independently, then decide whether to seal.

本地北京时间: 2026-07-11 14:26:44 CST
下一步模型: human operator → Claude-GLM
下一步任务: 人工执行 T1 correction packet；只修 T1-B1–B5，追加 raw evidence，不得 commit 或派发 Kimi。
