# Phase C Validation

## Fixed Delivery

```text
branch: codex/harness-v2-rebuild
base_sha: a15368c8ff9c0989968100e874e9ecb799a01c7d
delivery_sha: 0412ba16e2fa5003c087be9c4a824cb4e022d4b4
diff: a15368c8ff9c0989968100e874e9ecb799a01c7d..0412ba16e2fa5003c087be9c4a824cb4e022d4b4
checked_at: 2026-07-29 15:42:47 CST
```

No push, main merge, business-source edit, live action, credential access, or
legacy-cluster deletion occurred.

## Mechanical Results

```text
PASS ACTIVE.json parses and points only to 2026-07-harness-v2-phase-c
PASS active stage_id matches ACTIVE.json
PASS status.json has exactly the twelve DRAFT-3.2 top-level fields
PASS AGENTS.md has ten chapters and 153 lines (target 120..180)
PASS PROJECT_STATE.md is 1985 bytes (target <=2048)
PASS default active-stage startup is 11683 bytes, about 2.9K tokens
PASS PROJECT_STATE evidence is pinned to ACTIVE.json at commit 5c6ac65
PASS roles.md contains the minimal status and dispatch shapes
PASS roles.md defines non-self-referential ledger_sha semantics
PASS claude_glm maps to zhipu_glm
PASS reachable discipline and role-named skills have no operative dependency
     on workflow YAML, registry, v1 review schema, fix_start_prompt, or active
     v1 workflow wording
PASS code-reviewer, reality-checker, and security-reviewer are read-only and
     require TASK_RESULT v2 plus ACCEPT|REWORK and both REWORK paths
PASS complexity-evaluator uses LOW_RISK|HIGH_RISK and no direction-panel route
PASS AGENTS.md no longer points Human to docs/model-adapters.md
PASS git diff --check
```

Commands used:

```text
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-c/status.json
jq keys reports/agent-runs/2026-07-harness-v2-phase-c/status.json
rg legacy authority/output markers across reachable Harness files
rg v2 provider, verdict, state, and Human-boundary markers
wc -lc AGENTS.md PROJECT_STATE.md agents/roles.md status.json
git diff --check
git diff a15368c8..0412ba16
```

No business tests were run because the delivery changes Harness Markdown and
stage JSON only.

## Main Cutover Condition

The other worktree was on `stage/2026-07-hedge-order-truth-v1` at local commit
`db78114e5b103418b0882fe3424089e01e9809c4` during the final check. Its narrative
`next_action` says the stage was merged, but Git still showed:

```text
main: 05ee1b9ff9e4b0727f0a3f48447b5305ccaceb12
stage_branch.merged_back_to_main: false
```

Therefore Phase E must treat the v1 stage as not merged until the `main` ref and
Git ancestry prove otherwise. Narrative stage state cannot authorize or prove
the Harness merge.

## Deferred To Phase D/E

- Run a reversible, non-live stage entirely through v2.
- Measure actual model context instead of byte estimates.
- Prove no v2 task reads the legacy workflow cluster.
- Delete the unreachable v1 workflow/registry/schema/validator/docs cluster as
  one reviewed change.
- Synchronize the latest Git-confirmed main into this worktree, rerun checks,
  obtain Human acceptance, then merge v2 to main.
