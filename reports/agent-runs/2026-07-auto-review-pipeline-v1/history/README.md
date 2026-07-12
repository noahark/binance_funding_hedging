# History — 2026-07-auto-review-pipeline-v1

This directory is cold audit storage. It is **not startup context**.

## Read Policy

New agent sessions must not recursively read `history/` or enumerate its raw
files during startup. Start with only:

1. repository `AGENTS.md`;
2. active workflow YAML;
3. this stage's root `status.json`;
4. this stage's root `70-handoff.md`;
5. files explicitly listed under `status.json.current_inputs`.

Read a history artifact only when a current finding, review, audit, or exact
evidence reference requires that file. Do not use history to reconstruct the
current plan when the active status/handoff already state it.

## Layout

- `raw/`: verbatim historical dispatch packets, reviews, verdict JSON, intake
  evidence, inspections, and incident evidence.
- `snapshots/status-before-slimming.json`: full pre-slimming authoritative
  status snapshot.
- `snapshots/70-handoff-before-slimming.md`: full pre-slimming handoff.

Compatibility symlinks remain at the former stage-root paths so historical
verdicts and reports still resolve their original references. The raw file
bytes were not rewritten or summarized.

## Concise Stage History

- T1 delivered policy/workflow/registry/docs/templates and authorization/
  receipt schemas.
- T2 delivered the shared library, two-commit seal, validator integration, and
  deterministic tests.
- T3 delivered the automatic runner and integration tests.
- Formal review exposed and closed authorization binding, verdict fidelity,
  shell quoting, ledger, locking, crash recovery, expiry, and resume defects.
- Round 3 found total-session wall-clock enforcement incomplete. The operator
  subsequently withdrew that requirement rather than adding more deadline
  guards.
- The operator then directed a v1 slimming pass: serial-only auto mode, smaller
  authorization, registry-driven per-call timeout, history cold storage, and
  startup-context reduction.
- `rework_count` remains 3/3 as historical fact. The slimming pass is a
  separately authorized contract amendment, not rework 4.

本地北京时间: 2026-07-12 10:59:45 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched implementation）
下一步任务: 只读 active root context；非必要不读取 history/raw
