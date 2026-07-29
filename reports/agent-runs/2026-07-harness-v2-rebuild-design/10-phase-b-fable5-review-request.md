# Phase B Independent Review Request

This is a pre-activation advisory review of the Harness v2 Phase B delivery.
The v2 active-stage `status.json` contract is deliberately deferred to Phase C,
so this request does not claim to be a formal v2 review gate. The fixed Git
range below is authoritative.

## Executor Contract

- Target role: Reviewer
- Target model: Claude Fable5
- Provider identity: Anthropic
- Mode: read-only
- Task id: `harness-v2-phase-b-review`
- Required skill: `agents/skills/reality-checker.md` for its evidence and
  production-reality lens; `AGENTS.md` and this request override the skill's
  legacy v1 schema/output boilerplate.
- Do not edit files, commit, merge, push, launch another model, or delegate the
  review.
- Read raw files and the fixed diff; do not rely only on this request's summary.

Prior-involvement disclosure: Fable5 reviewed the DRAFT-2/DRAFT-3 design and the
Phase B execution plan. Fable5 did not author the Phase B files. This design
involvement is disclosed and is not implementation authorship.

## Fixed Review Range

```text
base_sha: 5c6ac65be1647dc171274bcc3d935420560faa90
delivery_sha: 894d05d34523a82b96725dcd5937a10416009c37
diff: 5c6ac65be1647dc171274bcc3d935420560faa90..894d05d34523a82b96725dcd5937a10416009c37
branch: codex/harness-v2-rebuild
```

Inspect:

```text
AGENTS.md
PROJECT_STATE.md
agents/roles.md
agents/skills/reality-checker.md
reports/agent-runs/ACTIVE.json
reports/agent-runs/2026-07-harness-v2-rebuild-design/08-harness-v2-minimal-design-r3.md
reports/agent-runs/2026-07-harness-v2-rebuild-design/09-phase-b-validation.md
git diff 5c6ac65be1647dc171274bcc3d935420560faa90..894d05d34523a82b96725dcd5937a10416009c37
```

## Review Questions

1. Does `AGENTS.md` use the exact ten-chapter structure approved in DRAFT-3.2,
   including a dedicated Review Rules chapter?
2. Are all seven safety-kernel rules preserved, especially no model relay and
   dispatch-approved file boundaries?
3. Is the full Human boundary preserved, including the statement that starting
   a prepared terminal only executes an already-made dispatch decision?
4. Does `agents/roles.md` preserve model duties, provider isolation, and the
   `claude_glm -> zhipu_glm` mapping without duplicating CLI commands?
5. Do the `status.json` field names in `AGENTS.md` exactly match DRAFT-3.2
   section 10?
6. Does `PROJECT_STATE.md` clearly distinguish last-known repository evidence
   from a current runtime check, and did `ACTIVE.json` safely become a pointer
   only after the durable facts moved?
7. Are high-risk two-review routing, low-risk one-review routing,
   `ACCEPT | REWORK`, return-to-origin-gate repair, scope-expansion review-1,
   and the rework limit all operationally clear?
8. Does progressive disclosure work without a startup dependency on legacy
   workflow YAML, registry, schemas, or completed-stage history?
9. Did Phase B avoid business code, push, merge, deployment, and live actions?
10. Is any remaining complexity unsupported by a real incident or current
    requirement?

## Required Output

Lead with plain Chinese and practical effect. Classify findings as:

- 必须修改：不改会丢规则、造成状态冲突、安全退化或无法执行；
- 建议修改：有明确收益但不阻塞阶段 B；
- 可接受风险：可以进入阶段 C 后再用真实演练验证。

End with:

```text
[TASK_RESULT v2]
task_id: harness-v2-phase-b-review
outcome: completed | blocked | failed
summary: <short Chinese summary>
artifacts:
  - reports/agent-runs/2026-07-harness-v2-rebuild-design/11-phase-b-fable5-review.md
checks:
  - git diff 5c6ac65be1647dc171274bcc3d935420560faa90..894d05d34523a82b96725dcd5937a10416009c37: <pass | fail>
blockers:
  - <none or concrete blocker>
verdict: ACCEPT | REWORK
findings_path: reports/agent-runs/2026-07-harness-v2-rebuild-design/11-phase-b-fable5-review.md | none
fix_requirements_path: reports/agent-runs/2026-07-harness-v2-rebuild-design/11-phase-b-fable5-review.md | none
[/TASK_RESULT]
```

The human operator will return the raw terminal output to a model session for
repository recording. Do not ask Human to inspect or edit the reviewed files.
