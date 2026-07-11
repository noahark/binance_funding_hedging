# Bookkeeper Reinspection: T1 After Merged Correction Round 1 v2

Outcome: **REWORK BEFORE SEAL — CORRECTION ROUND 2 REQUIRED**

This is a bookkeeper pre-seal inspection, not formal review-1. The merged v2
correction closed the previously recorded B1–B5/A2/A3/A4/A6 mechanics and its
frozen JSON/YAML checks pass, but independent semantic counterexamples found
two linked contract defects. No delivery commit, fingerprint, `pre-review`, or
Kimi dispatch is allowed yet. The formal stage `rework_count` remains 0.

## Inspected State

- Branch: `stage/2026-07-auto-review-pipeline-v1`
- HEAD: `9b157e15eb1561b5f8e4b8b0d1ae7a4562e9967e`
- T1 base: `a385c7ad77da1611c6e952b2219aee56b49f442f`
- Executed packet:
  `task-T1-correction-round1-v2-claude-glm.prompt.md`
- Implementation evidence: `20-implementation.md`
- Raw checks: `60-test-output.txt`
- Implementer/correction provider: `zhipu_glm`

## Confirmed Passing Surface

- Worktree paths remain inside frozen T1 delivery/shared-evidence ownership.
- Receipt required list has 18 keys; unsafe paths, expanded refs,
  adapter/ref mismatch, same-prefix yolo refs, and unsupported
  `bookkeeper_decision` fail.
- Authorization safe paths/non-empty unique task scope and branch-exception
  semantics pass.
- Workflow and registry parse as YAML; receipt/workflow next-transition sets
  match; P7, disabled representation, and seal evidence path are present.
- Frozen JSON/validator/diff/vocabulary commands pass with expected exits.
- Authority Order, fingerprint formula, review-2/merge gates, manual mode, and
  this stage's disabled auto mode remain unchanged.

## New Blocking Findings

### T1-R2-1 — Receipt schema rejects configured serial review-1 fallbacks (P1)

The frozen D7/ADR route permits Kimi or Claude-GLM as a serial task-unit
review-1 fallback when the candidate provider is absent from the unit author
set. The receipt schema conditional for `node=review_1` instead requires
`adapter.id=grok` and the Grok optional-review reference.

Independent `Draft202012Validator` results:

```text
grok_primary error_count=0
kimi_serial_fallback error_count=2
glm_serial_fallback error_count=2
```

Both fallback receipts fail on the forced Grok id/ref. The schema therefore
makes a frozen workflow branch impossible. It must allow exactly Grok primary
plus Kimi/GLM embedded read-only refs. Provider isolation, serial topology,
author-set eligibility, and parallel-tip escalation remain runner/validator
checks; schema validity alone never declares fallback eligibility.

The new docs vocabulary also says embedded cross-check may use "or Grok", while
the frozen decision example and schema restrict that advisory cross-pool to
GLM/Kimi. The minimum correction removes that unfrozen phrase rather than
broadening embedded cross-check routing.

### T1-R2-2 — Workflow transitions are YAML-shaped prose, not executable maps (P1)

`auto_review_pipeline.executable_contract` has no `state_transitions` or
`node_transitions`. Its review-1 outcomes are strings such as
`"ACCEPT advances the unit"` and
`"retry same model once, then serial unit fallback or human escalation"`.
Activation and pilot conditions are likewise mostly prose strings/booleans.

A deterministic runner cannot derive exact event→next-state/node choices from
those sentences without hard-coding policy, contradicting the frozen rule that
workflow YAML defines transitions and runner only executes them. The v2
correction fixed YAML syntax and target-set equality, but T1-B3 is not fully
closed.

Round 2 must add structured data for:

- the eight frozen dispatch-mode/runner-state rows;
- node/event transitions for implementation, both blocking passes, cross-check,
  seal, review-1 primary/retry/fallback/REWORK, fix, completion, and escalation;
- structured review-1 primary/fallback command refs and eligibility fields;
- explicit pilot kinds, terminal status, minimum verdict count, 100% receipt
  completeness, escalation shape/drill, no threshold, and no automatic flip;
- structured activation field/schema/commit/human/mutex checks.

Human-readable `note` fields may remain, but no transition choice may exist only
as natural-language prose.

## Disposition

The bookkeeper prepared `task-T1-correction-round2-claude-glm.prompt.md`. It may
modify only the receipt schema, workflow auto contract, normative auto doc, and
append-only T1 evidence. After round 2 returns, bookkeeper re-runs fallback
positive cases and structured transition assertions before any seal decision.

本地北京时间: 2026-07-11 15:37:04 CST
下一步模型: human operator → Claude-GLM
下一步任务: 人工执行 T1 correction round 2；修复 review-1 fallback receipt 与 machine-readable transition maps，不得 commit 或派发 Kimi。
