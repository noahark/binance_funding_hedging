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
  evidence, inspections, gate logs, implementation process reports, and
  incident evidence.
- `snapshots/status-before-slimming.json`: full pre-slimming authoritative
  status snapshot (first archive pass).
- `snapshots/70-handoff-before-slimming.md`: full pre-slimming handoff.
- `snapshots/status-before-post-accept-history-archive.json`: status before the
  post-accept process-packet archive pass.
- `snapshots/70-handoff-before-post-accept-history-archive.md`: handoff before
  that pass.

Compatibility symlinks remain at the former stage-root paths so historical
verdicts and reports still resolve their original references. The raw file
bytes were not rewritten or summarized.

## Archive Passes

1. **Pre-serial-slimming pass:** 67 root artifacts → `history/raw/` + symlinks.
2. **Post-accept process pass (2026-07-12):** 20 additional closed process
   artifacts (T4 packets, T4 review/verdict, implementation report, gate logs,
   intermediate bookkeeper checkpoints, short review summary stubs) →
   `history/raw/` + symlinks.

## Active Root (after pass 2)

Keep as real files:

- `status.json`, `70-handoff.md`, `60-test-output.txt`
- `00-task.md`
- design authority: `12-serial-v1-slimming-development-breakdown-codex.md`,
  `15-p8-wall-clock-withdrawal-design-amendment.md`,
  `16-serial-v1-slimming-design.md`,
  `19-model-routing-convergence-operator-decision.md`,
  `54-p8-wall-clock-withdrawal-operator-decision.md`
- historical design shells still useful for lineage: `10-design.md`, `11-adr.md`
  (partially superseded by serial-v1 design; treat `16-serial-*` as amendment
  authority)

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
- T4 delivered the serial-v1 slimming + model-routing convergence; Kimi
  review-1 and Opus review-2 ACCEPT; user accepted; fast-forward to `main`.
- `rework_count` remains 3/3 as historical fact. The slimming pass is a
  separately authorized contract amendment, not rework 4.

本地北京时间: 2026-07-12 15:11:00 CST
下一步模型: human
下一步任务: 非必要不读 history/raw；导航类语义冲突见 bookkeeper 汇总
