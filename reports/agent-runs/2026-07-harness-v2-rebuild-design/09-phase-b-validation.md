# Phase B Validation

## Scope

- Branch: `codex/harness-v2-rebuild`
- Design baseline: `5c6ac65be1647dc171274bcc3d935420560faa90`
- Business source changed: no
- Push or main merge: no
- Checked at: `2026-07-29 15:09:16 CST`

Phase B rewrites the startup entry, centralizes role routing, and creates the
small cross-stage state file required by startup. It does not redesign active
stage `status.json`, remove legacy workflow machinery, or touch business code.

## Mechanical Checks

```text
PASS headings=10
PASS AGENTS.md lines=154 (target 120..180)
PASS PROJECT_STATE.md bytes=1919 (target <=2048)
PASS default startup bytes=11077
PASS approximate default startup tokens=2770 (bytes/4 estimate; target <=8000)
PASS ACTIVE.json parses as JSON and contains only the active pointer
PASS every default-read and role/skill path named by AGENTS.md exists
PASS seven-rule safety kernel markers are present
PASS Human boundary marker is present
PASS roles.md contains claude_glm -> zhipu_glm provider mapping
PASS status field names match DRAFT-3.2 section 10
PASS AGENTS.md has no startup references to workflow YAML, registry, schemas,
     70-handoff, Output Footer, or Session ID
PASS git diff --check
```

Commands:

```text
python3 -m json.tool reports/agent-runs/ACTIVE.json
wc -lc AGENTS.md agents/roles.md PROJECT_STATE.md
rg -n '^## ' AGENTS.md agents/roles.md
rg provider and safety markers in AGENTS.md and agents/roles.md
git diff --check
```

No business test suite was run because Phase B changes Harness Markdown and the
`ACTIVE.json` pointer only.

## Context Estimate

Default startup reads:

```text
AGENTS.md
reports/agent-runs/ACTIVE.json
PROJECT_STATE.md
```

Their combined size is 11,077 bytes, approximately 2.8K tokens by the rough
bytes/4 method. A task then adds one dispatch, active `status.json`, one role
section, and at most one skill. Existing implementation/review skill sizes keep
the pre-source-file task context well below the 15K target in the normal case.
Phase D will measure actual model context rather than relying on this estimate.

## Deliberate Phase C Deferrals

- Create the v2 `status.json` template and transition rules.
- Create the v2 dispatch template.
- Migrate or archive active-stage directories.
- Retire legacy workflow YAML, registry, schemas, and validator paths after
  rehearsal proves they are no longer needed.

These legacy files remain tracked but are no longer startup dependencies in the
new `AGENTS.md`.
