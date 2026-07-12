# T1 Inspection Merge — Bookkeeper + Fable5

Disposition: **ONE MERGED PRE-SEAL CORRECTION, ROUND 1 REVISION 2**

Sources:

- `21-bookkeeper-inspection-T1.md` — T1-B1 through T1-B5
- `22-second-inspection-T1-fable5.md` — confirms B1–B5 and proposes A1–A7

The first correction packet was checkpointed but never executed. Its immutable
prompt remains evidence and is superseded by
`task-T1-correction-round1-v2-claude-glm.prompt.md`. This remains one pre-seal
correction round; no formal review verdict exists and `rework_count` stays 0.

## Confirmed Existing Findings

Fable5 independently confirmed T1-B1 through T1-B5 and the direction of C1–C5:

- receipt required/null-able evidence keys;
- command-reference safety and adapter/reference pairing;
- executable workflow nodes/transitions/acceptance predicates and the
  authorization-conditioned runner exception;
- the P7 one-blocking-fix-then-escalate rule;
- rewrite-on-touch vocabulary, report errata, and raw test evidence.

No existing B finding is removed or weakened.

## Fable5 Additions — Bookkeeper Disposition

### A1 Authority Order — DEFERRED, not delegated to the correction model

The concern is recorded: `docs/auto-review-pipeline.md` calls itself a normative
human-readable contract but is not separately listed in AGENTS Authority Order.
However, promoting it beside `docs/parallel-development-mode.md` would place it
above schemas and registry and change the repository conflict-resolution model.
The frozen design assigns transitions to workflow, adapters to registry, and
machine output shape to schemas. That authority change is not a mechanical
T1-B1–B5 correction and must not be decided by Claude-GLM.

Round1-v2 therefore preserves the current authority order, performs only the
already-required terminology replacement in that sentence, and records A1 as a
design-amendment candidate for operator/final-review consideration.

### A2 Receipt/workflow transition alignment — REQUIRED

Absorbed as a concrete strengthening of T1-B3/C3:

- workflow must expose one machine-readable `allowed_next_transitions` set;
- non-null `runner-receipt.schema.json` `next_transition.enum` must equal it;
- `bookkeeper_decision` is removed because it has no auto-mode source (the
  historical manual node is spelled `bookkeeper-decision` and is unrelated);
- an automated equality/negative assertion is required.

Adapter command references are also restricted to the actual registry command
keys allowed for the relevant adapter/node, not merely an adapter-name prefix;
yolo, availability, or arbitrary same-prefix keys are invalid.

### A3 Seal receipt path — REQUIRED WITH COMPATIBLE NAMING

The missing path is real, but no new naming family is introduced. The frozen
generic receipt path is refined as:

`runner-<seq>-seal.receipt.json`

Docs and README must state that this is deterministic seal evidence with its
own T2-defined shape. It is not a model-adapter invocation receipt, does not
validate against `runner-receipt.schema.json`, and is excluded from the P11
adapter-call RECEIPT denominator.

### A4 Authorization schema hardening — REQUIRED, with branch-prefix carve-out

Required:

- safe repo-relative `approval_evidence_path`;
- safe repo-relative non-null `supersedes`;
- non-empty, unique `scope.task_ids`;
- non-empty/control-character-free `stage_branch` plus runtime exact match.

The proposed `^stage/` prefix is not adopted: AGENTS permits an explicit
user-approved stage-branch exception recorded at intake. Schema must not make
that higher-authority exception impossible; runner preflight still requires
exact equality with current status/branch.

### A5 Fingerprint formula copies — RECORD ONLY

The four textual copies are currently byte-equivalent and do not create a
second implementation path. Round1-v2 does not replace them with a new
indirection or touch registry for this minor. The correction report records the
duplication; T2 still must provide one canonical executable fingerprint
implementation shared by validator and seal.

### A6 Disabled representation — REQUIRED CLARIFICATION

Workflow and docs must state that transition-table `disabled` is a conceptual
state represented as:

```text
enabled=false + dispatch_mode=human_dispatch + runner_state=null
```

It is not a sixth `runner_state` enum value.

### A7 Historical registry machine key — RECORD ONLY

The existing `embedded_pre_review` registry machine key remains for
compatibility and is not a prose-vocabulary precedent. Round1-v2 must record
that distinction but must not rename the key or edit registry for A7.

## Merged Mandatory Set

The one human-dispatched correction packet contains:

- T1-B1–T1-B5 / C1–C5;
- A2;
- A3 with `runner-<seq>-seal.receipt.json`;
- A4 excluding a hard-coded `^stage/` prefix;
- A6;
- A5/A7 report notes;
- A1 deferred note, with no Authority Order promotion.

Additional writable delivery paths relative to the superseded packet are only:

- `schemas/auto-review-authorization.schema.json`
- `reports/agent-runs/README.md`

All paths remain inside frozen T1 ownership. Scripts, manifest, live
status/handoff, review files, product paths, and funding stages remain
forbidden.

## Non-Regression Guard

The correction must not disturb the already-passing T1 surfaces identified by
Fable5: authorization frozen numbers and nullable expiry semantics, default-off
templates, Pilot Evaluation Contract, post-cross-check blocking rerun,
seen-diff bind, review-2/merge human gates, product isolation, or unchanged
fingerprint formula.

本地北京时间: 2026-07-11 14:58:13 CST
下一步模型: human operator → Claude-GLM
下一步任务: 仅执行 round1-v2 merged correction packet；旧 round1 packet 已作废且从未执行。
