# Phase E Task 2 — Chinese Results, Authority Deduplication, V1 Retirement

## Identity

- task_id: `phase-e-task2-cn-results-and-v1-retirement`
- target_role: `Implementer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `10`
- required_skill: `agents/skills/minimal-change-engineer.md`

## Goal

Complete the approved v2 cutover as one bounded, reviewed change:

1. make formal task-result field labels Chinese-first for the Human;
2. remove duplicate active authority definitions;
3. retire the complete unreachable v1 Harness cluster without leaving broken
   scripts, templates, or navigation links.

Do not add a compatibility layer, replacement YAML, schema, validator, Hook,
handoff template, registry, or new permanent design document.

## A. Chinese Task Result Protocol

Keep the stable outer markers:

```text
[TASK_RESULT v2]
...
[/TASK_RESULT]
```

`AGENTS.md` is the only file that defines the complete field layout. Replace
the visible English field labels with:

```text
任务 ID: <id>
执行结果: completed（完成） | blocked（阻塞） | failed（失败）
结果摘要: <不超过 300 个总字符>
产物: [<paths>]
检查结果: [<最多八项，合并重复检查>]
阻塞项: [<none or concrete blockers>]
```

A review additionally uses:

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

The three existing Chinese handoff lines remain required.

Rules:

- Keep canonical route tokens `completed`, `blocked`, `failed`, `ACCEPT`, and
  `REWORK`; add the Chinese explanation in output.
- `结果摘要` is a hard maximum of 300 total characters, counting Chinese,
  English, numbers, spaces, and punctuation. It is not a soft target and not a
  Han-character-only count.
- `检查结果` is a hard maximum of eight grouped, non-duplicative items.
- Required detailed findings and executable repair requirements belong in the
  existing review evidence/result referenced by `问题记录` and `修复要求`; do not
  inflate the summary.
- The standalone closing marker remains the final non-whitespace line.
- Do not translate internal `status.json` keys or historical raw results.

Update active review skills to reference the single protocol in `AGENTS.md`.
They may retain task-specific review behavior and canonical verdict values, but
must not copy another complete field template.

## B. Single-Authority Audit And Cleanup

Use this ownership map:

| Fact | Only detailed authority |
|---|---|
| Universal startup and safety rules; full task-result protocol | `AGENTS.md` |
| Current stage progress and current Bookkeeper model id | active `status.json` |
| Role duties, provider mapping, model routing, minimal status/dispatch shape | `agents/roles.md` |
| Shared implementation/fix discipline | `agents/developer-discipline.md` |
| One task-specific technique | the one dispatch-named skill |
| Cross-stage live risks, open follow-ups, last archive | `PROJECT_STATE.md` |
| Current task scope, files, inputs, checks, stop point | active dispatch |

Apply these concrete corrections:

1. In `PROJECT_STATE.md`, remove the whole role-ownership clause
   `Stage Recorder writes; other roles report through TASK_RESULT`. Do not
   replace it with `Bookkeeper`; this file stores state, not role definitions.
2. In `AGENTS.md`, remove the copied exact `status.json` field enumeration and
   point to the Bookkeeper section of `agents/roles.md` as the sole detailed
   shape.
3. In `agents/skills/code-reviewer.md`,
   `agents/skills/reality-checker.md`, and
   `agents/skills/security-reviewer.md`, remove copied output-field layouts and
   old English field-label instructions. Refer to the single Task Result
   Protocol in `AGENTS.md`.
4. Keep short startup navigation and safety invariants in `AGENTS.md`; a
   one-line summary that points to a detailed authority is intentional
   progressive disclosure, not a second full definition.
5. Keep detailed Bookkeeper purpose, write boundary, behavior, and stop point
   in `agents/roles.md`. Do not copy Bookkeeper identity into dispatch.
6. Replace the retired role phrase `controller summary/summaries` in active
   Harness overrides with neutral `narrative summary/summaries`. Do not alter
   legitimate software-architecture uses of “controller”.
7. Define `rework_count` once in the `AGENTS.md` Review Rules: it counts only
   formal `REWORK` repair rounds for the current task, resets to zero for a new
   task, and does not count Human requirement refinement or pre-dispatch packet
   correction. In `agents/roles.md`, refer to that rule instead of restating a
   separate counting policy.
8. Inspect active v2 files listed under Inputs for any other same fact, list,
   schema, identity, or rule defined in two or more places. Consolidate an
   actual duplicate into the ownership map above. Do not rewrite historical
   evidence or remove cheap safety tripwires merely because they summarize a
   higher-level hard rule.
9. Report the duplicates found and the surviving authority in the final
   `检查结果`; do not create a permanent audit document.

## C. Delete The Complete Frozen V1 Cluster

Delete exactly these v1 authorities and direct dependents:

```text
.harness-version
harness-manifest.yaml
workflows/templates/stage-delivery.yaml
agents/registry.yaml
schemas/review-verdict.schema.json
scripts/validate-stage.py
scripts/tests/test_validate_stage_dispatch_protocol.py
scripts/validate-all-stages.py
scripts/test-validate-all-stages-compare.py
scripts/install-harness.sh
scripts/update-project-harness.sh
docs/parallel-development-mode.md
docs/harness-design.md
docs/model-adapters.md
reports/agent-runs/README.md
reports/agent-runs/_template/
```

Why the dependent files are included:

- `validate-all-stages.py` imports the deleted validator;
- its comparison test imports that deleted runner;
- install/update scripts require the deleted manifest;
- `_template` and its README encode the retired `70-handoff`, Session ID,
  registry, schema, and fingerprint workflow.

Update `docs/README.md` only to remove navigation links to deleted Harness
documents. Do not rewrite historical planning, decision, follow-up, or
completed-stage evidence that names v1 paths; Git history and cold evidence
preserve those facts.

Preserve:

- all product/API schemas under `schemas/api/`;
- `scripts/tests/test_service_control.py`;
- `CLAUDE.md` as the small compatibility pointer to `AGENTS.md`;
- agency skill files, provenance, license, and `agents/skills/UPSTREAM.md`;
- all business source, tests, runtime data, current Phase E evidence, and
  canonical product/architecture/planning documents.

## Allowed Files

Modify only:

```text
AGENTS.md
PROJECT_STATE.md
agents/roles.md
agents/developer-discipline.md
agents/skills/code-reviewer.md
agents/skills/reality-checker.md
agents/skills/security-reviewer.md
docs/README.md
reports/agent-runs/2026-07-harness-v2-phase-e/status.json
```

Delete only the exact paths listed in section C.

Do not modify any other path. In `status.json`, change only this task's state
from `dispatched` to `reported` after every check passes.

## Inputs

Read only:

1. `AGENTS.md`;
2. this dispatch;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. current Phase E `status.json`;
6. the `Implementer`, `Reviewer`, and `Bookkeeper` sections plus provider table
   in `agents/roles.md`;
7. `agents/developer-discipline.md`;
8. `agents/skills/minimal-change-engineer.md`;
9. the three review skills named under Allowed Files;
10. `docs/README.md`;
11. the exact deletion paths in section C only as needed to confirm they are
    the frozen v1 cluster;
12. `reports/agent-runs/2026-07-harness-v2-phase-e/42-task1-human-acceptance.md`;
13. `reports/agent-runs/2026-07-harness-v2-phase-e/41-phase-e-task1-opus5-review-result.md`.

Do not scan business source, runtime data, credentials, unrelated stages,
historical reports, or moving Git history.

## Acceptance Checks

1. `AGENTS.md` contains the Chinese result labels, canonical route values,
   hard 300-total-character summary limit, hard eight-check limit, and final
   standalone marker rule.
2. No active result-protocol file defines English labels as full-line fields.
3. Review skills reference `AGENTS.md` and do not duplicate a complete output
   template.
4. `PROJECT_STATE.md` contains no role identity or writer definition.
5. `status.json.bookkeeper` remains the single scalar `codex`; no dispatch
   Bookkeeper/result-recipient identity is added.
6. `rework_count` semantics are defined only in `AGENTS.md` and current Task 2
   remains at zero.
7. Active Harness role wording contains no retired `controller summary` alias.
8. The exact v1 cluster and dependents in section C are absent.
9. Product/API schemas, service-control test, CLAUDE pointer, agency skills,
   license, and current stage evidence remain.
10. `docs/README.md` has no dead navigation link to the deleted Harness docs.
11. No business source, main, remote, service, credential, runtime, or live
   state changes.
12. Run and return grouped results for:

```text
git diff --check
python3 -m json.tool reports/agent-runs/ACTIVE.json
python3 -m json.tool reports/agent-runs/2026-07-harness-v2-phase-e/status.json
rg -n "任务 ID:|执行结果:|结果摘要:|产物:|检查结果:|阻塞项:|评审结论:|问题记录:|修复要求:" AGENTS.md
! rg -n "^(task_id|outcome|summary|artifacts|checks|blockers|verdict|findings_path|fix_requirements_path):" AGENTS.md agents/roles.md agents/skills/*.md
! rg -n "Stage Recorder|stage_recorder|result_recipient|controller summar|70-handoff|Session ID|review-verdict\\.schema|stage-delivery\\.yaml|agents/registry\\.yaml|scripts/validate-stage\\.py" AGENTS.md PROJECT_STATE.md agents/roles.md agents/developer-discipline.md agents/skills docs/README.md
wc -l -c AGENTS.md PROJECT_STATE.md agents/roles.md agents/skills/reality-checker.md
```

Also mechanically assert every section-C path is absent and every named
preserved path is present.

## Stop

Return one concise result using the newly delivered Chinese labels:

```text
[TASK_RESULT v2]
任务 ID: phase-e-task2-cn-results-and-v1-retirement
执行结果: completed（完成） | blocked（阻塞） | failed（失败）
结果摘要: <最多 300 个总字符>
产物: [<paths>]
检查结果: [<最多八项合并结果>]
阻塞项: [<none or concrete blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: Codex（Bookkeeper，经 human_operator 转交）
下一步任务: 将本次 raw TASK_RESULT 交给 Codex 核实、固定 delivery_sha，并准备 Grok 4.5 review-1（初审）
[/TASK_RESULT]
```

Stop at `[/TASK_RESULT]`. Do not commit, push, modify `main`, start another
model, or perform any service, credential, runtime, or live action.
