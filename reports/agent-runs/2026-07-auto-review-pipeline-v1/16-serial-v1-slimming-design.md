# Design Amendment — Serial-Only Auto Review v1 Slimming

## Authority

The human operator directed Codex to close and slim the branch by:

1. removing unimplemented automatic parallel topology;
2. removing redundant authorization fields;
3. completing P8 total wall-clock withdrawal;
4. aligning timeout behavior with registered per-adapter values;
5. archiving history and preventing unnecessary startup reads;
6. deleting safe temporary/cache files.

This amendment supersedes the narrower
`15-p8-wall-clock-withdrawal-design-amendment.md` where scope differs. It does
not reopen fingerprint, seal, review-2, merge, provider-isolation, raw-evidence,
or product safety rules.

## Target v1

Auto-review v1 is a **serial-only**, default-off middle-loop automation:

```text
human authorization
  -> preflight
  -> bounded implementation
  -> blocking checks
  -> optional/required embedded cross-check
  -> identical blocking rerun
  -> H_snapshot/H_bind seal
  -> Grok review-1
  -> bounded serial fix or escalation
  -> completed_review_1
  -> human-started review-2
  -> explicit user merge decision
```

Automatic parallel task worktrees, integrated tips, parallel-tip routing, and
automatic integration review units are deferred to a future version after real
serial pilots. Legacy manual `parallel_mode` remains a separate workflow and is
still mutually exclusive with auto mode.

## Authorization v1 Slim Shape

Keep:

```text
schema_version
contract_version
stage_id
stage_branch
authorized_by
approval_evidence_path
approval_recorded_by
authorized_at
expires_at
scope.task_ids
scope.allowed_pathspecs
scope.forbidden_pathspecs
budgets.max_model_calls
budgets.max_auto_code_changes
supersedes
```

Remove as redundant or unimplemented:

```text
authorized                              # artifact existence + human approval is the gate
allowed_adapters                        # fixed by committed workflow/registry
review_1_provider                       # runner route is fixed Grok + serial fallback
auto_high_end_dispatch_allowed          # fixed false by workflow; high-end loop route absent
scope.topology                          # v1 is serial-only
budgets.wall_clock_seconds              # operator withdrew total-session clock
budgets.max_stage_rework                # global AGENTS/workflow invariant = 3
budgets.invalid_json_max_attempts_per_model  # workflow invariant = 2
```

Authorization uses `additionalProperties: false`; stale artifacts carrying a
removed field fail closed. There is no compatibility-normalization path because
v1 has not been accepted, merged, or piloted.

Status stores usage, not duplicate cap truth:

```text
model_calls_used
auto_code_changes_used
```

The top-level `rework_count` remains the authoritative shared stage ledger.
The authorization remains authoritative for its two configurable caps.

## Timeout Contract

There is no total runner-session deadline. Individual adapter calls use the
committed registry:

- default command timeout: `adapters.<id>.timeout_seconds`;
- command-specific override when defined, currently
  `grok.optional_review_timeout_seconds` for Grok review-1;
- no model output may choose or extend a timeout;
- timeout still consumes one model call and produces the existing receipt and
  escalation behavior.

The runner's single constructor-wide 1800-second production default must no
longer override registry values. Test injection may provide an explicit
override only as a test collaborator, not as production policy.

## History And Startup Budget

- `reports/agent-runs/<stage>/history/` is cold storage.
- Startup reads only AGENTS, active workflow, active status, active handoff,
  and `status.current_inputs`.
- Do not recursively read `reports/agent-runs/` or any `history/` directory.
- Historical raw artifacts remain verbatim and are read only for an exact
  review/audit/finding reference.
- Mutable status/handoff may be compacted after their full snapshots are placed
  in history.
- Compatibility symlinks may preserve old artifact paths without making raw
  history part of normal file enumeration.

## Preserved Invariants

- manual mode unchanged;
- auto mode default-off and bootstrap self-host forbidden;
- exact stage/branch/task/path binding;
- committed human approval evidence;
- call charge immediately before adapter start;
- one blocking automatic fix and aggregate automatic-change cap;
- required nullable `expires_at`, checked before calls and commits;
- runner lock and zero-write lock loser;
- resume fail-closed behavior;
- strict final-and-only verdict JSON and byte fidelity;
- provider isolation;
- seen-diff byte equality;
- canonical committed-range fingerprint;
- H_snapshot/H_bind crash recovery;
- human review-2 and explicit merge authority.

## Non-Goals

- no backend/frontend/API/product changes;
- no parallel auto implementation;
- no new fingerprint or clock protocol;
- no changes to `schemas/review-verdict.schema.json`;
- no automatic high-end GPT/Claude dispatch;
- no implementation by Codex/OpenAI;
- no deletion or rewriting of raw historical evidence.

## Acceptance

1. Normative docs and workflow describe serial-only auto v1.
2. Authorization schema and handwritten validator agree on the slim shape.
3. Every removed authorization field is rejected as an unknown field.
4. Runner no longer reads topology, allowed-adapters, review-provider,
   high-end flag, total wall clock, duplicated stage-rework cap, or auth-side
   invalid-JSON cap.
5. Invalid-JSON attempts remain fixed at two from workflow/runtime constant.
6. Stage rework remains fixed at three from top-level policy/status.
7. Registry per-adapter and command-specific timeouts drive subprocess timeout.
8. Long fake-clock advances alone do not stop an otherwise healthy run.
9. Adapter timeout, expiry, call cap, rework cap, and auto-change cap remain
   independently tested.
10. Auto review units are task-only; parallel/tip/integration auto behavior is
    absent from v1 docs, workflow, validator, runner, and tests.
11. Legacy manual parallel-mode regression still passes.
12. History is cold by default and active startup context is explicit.
13. Existing FX1-FX7 safety tests remain or are equivalently preserved.
14. Full suite, py_compile, validator, diff check, forbidden-product scan, and
    normative residue scans pass.

本地北京时间: 2026-07-12 10:59:45 CST
下一步模型: Claude-GLM / GLM-5.2（human-dispatched implementation）
下一步任务: 按 12-serial-v1-slimming-development-breakdown-codex.md 实现单一有界任务
